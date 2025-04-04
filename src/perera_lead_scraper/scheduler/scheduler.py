#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Export Scheduler

Handles scheduling of lead exports to CRM systems based on configured intervals
and time windows. Uses APScheduler for job scheduling.
"""

import time
import datetime
from typing import Dict, Any, Optional, List, Tuple
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from pytz import utc

from models.lead import Lead, LeadStatus
from utils.storage import LeadStorage
from utils.logger import get_logger
from src.perera_lead_scraper.pipelines.export_pipeline import CRMExportPipeline
from src.perera_lead_scraper.config import config


# Configure logger
logger = get_logger(__name__)

# Default settings
DEFAULT_EXPORT_INTERVAL_MINUTES = 60
DEFAULT_EXPORT_BATCH_SIZE = 25
DEFAULT_EXPORT_WINDOW_START_HOUR = None  # No restriction by default
DEFAULT_EXPORT_WINDOW_END_HOUR = None    # No restriction by default


class ExportScheduler:
    """
    Scheduler for exporting leads to CRM systems.
    
    Uses APScheduler to periodically fetch processed leads and trigger
    their export via the CRMExportPipeline.
    """
    
    def __init__(
        self,
        local_storage: LeadStorage,
        crm_export_pipeline: CRMExportPipeline
    ):
        """
        Initialize the export scheduler.
        
        Args:
            local_storage: Storage manager for local lead data
            crm_export_pipeline: Pipeline for exporting leads to CRM
        """
        self.local_storage = local_storage
        self.crm_export_pipeline = crm_export_pipeline
        
        # Scheduler configuration from environment
        self.interval_minutes = getattr(config, 'export_interval_minutes', DEFAULT_EXPORT_INTERVAL_MINUTES)
        self.batch_size = getattr(config, 'export_batch_size', DEFAULT_EXPORT_BATCH_SIZE)
        self.window_start_hour = getattr(config, 'export_window_start_hour', DEFAULT_EXPORT_WINDOW_START_HOUR)
        self.window_end_hour = getattr(config, 'export_window_end_hour', DEFAULT_EXPORT_WINDOW_END_HOUR)
        
        # Configure scheduler
        jobstores = {
            'default': MemoryJobStore()
        }
        executors = {
            'default': ThreadPoolExecutor(10)
        }
        job_defaults = {
            'coalesce': True,
            'max_instances': 1
        }
        
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone=utc
        )
        
        # Statistics
        self.stats = {
            "total_batches_processed": 0,
            "total_leads_exported": 0,
            "total_leads_failed": 0,
            "last_batch_time": None,
            "scheduler_status": "initialized"
        }
    
    def _process_export_batch(self) -> None:
        """
        Process a batch of leads for export.
        
        Fetches leads with status=ENRICHED from local storage and exports them
        to HubSpot via the export pipeline.
        """
        # Check if we're within the export window
        if not self._is_within_export_window():
            logger.info("Current time is outside the configured export window, skipping this batch")
            return
        
        logger.info(f"Starting export batch (size: {self.batch_size})")
        batch_start_time = datetime.datetime.now()
        
        # Get enriched leads
        leads, total_count = self.local_storage.get_leads_by_status(
            status=LeadStatus.ENRICHED,
            limit=self.batch_size,
            offset=0
        )
        
        if not leads:
            logger.info("No leads to export in this batch")
            return
        
        logger.info(f"Found {len(leads)} leads to export (out of {total_count} total enriched leads)")
        
        # Track batch results
        batch_results = {
            "attempted": len(leads),
            "succeeded": 0,
            "failed": 0
        }
        
        # Process each lead
        for lead in leads:
            lead_identifier = f"{lead.project_name} (ID: {lead.id})"
            logger.info(f"Exporting lead: {lead_identifier}")
            
            success = self.crm_export_pipeline.export_lead(lead)
            
            if success:
                logger.info(f"Successfully exported lead: {lead_identifier}")
                batch_results["succeeded"] += 1
                self.stats["total_leads_exported"] += 1
            else:
                logger.error(f"Failed to export lead: {lead_identifier}")
                batch_results["failed"] += 1
                self.stats["total_leads_failed"] += 1
        
        # Update statistics
        batch_processing_time = datetime.datetime.now() - batch_start_time
        self.stats["total_batches_processed"] += 1
        self.stats["last_batch_time"] = datetime.datetime.now()
        
        # Log batch summary
        logger.info(f"Export batch completed in {batch_processing_time.total_seconds():.2f} seconds")
        logger.info(f"Batch results: {batch_results['succeeded']} succeeded, {batch_results['failed']} failed")
    
    def _is_within_export_window(self) -> bool:
        """
        Check if the current time falls within the configured export window.
        
        Returns:
            bool: True if within window or no window configured, False otherwise
        """
        # If no window configured, always allow exports
        if self.window_start_hour is None or self.window_end_hour is None:
            return True
        
        current_hour = datetime.datetime.now().hour
        
        # Check if current hour is within the window
        if self.window_start_hour < self.window_end_hour:
            # Simple case: window doesn't cross midnight
            return self.window_start_hour <= current_hour < self.window_end_hour
        else:
            # Window crosses midnight
            return current_hour >= self.window_start_hour or current_hour < self.window_end_hour
    
    def start_scheduler(self) -> None:
        """
        Start the export scheduler.
        
        Adds the export job to the scheduler and starts it.
        """
        # Add export job
        self.scheduler.add_job(
            func=self._process_export_batch,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
            id='export_job',
            name='Export leads to HubSpot',
            replace_existing=True
        )
        
        # Start scheduler
        self.scheduler.start()
        self.stats["scheduler_status"] = "running"
        
        logger.info(f"Export scheduler started with interval: {self.interval_minutes} minutes, batch size: {self.batch_size}")
        
        if self.window_start_hour is not None and self.window_end_hour is not None:
            logger.info(f"Export window configured: {self.window_start_hour}:00 to {self.window_end_hour}:00")
    
    def stop_scheduler(self) -> None:
        """Stop the export scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            self.stats["scheduler_status"] = "stopped"
            logger.info("Export scheduler stopped")
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """
        Get the current status of the scheduler.
        
        Returns:
            Dict: Scheduler status information
        """
        self.stats["scheduler_status"] = "running" if self.scheduler.running else "stopped"
        return self.stats
    
    def run_export_now(self) -> Dict[str, Any]:
        """
        Run an export batch immediately.
        
        Returns:
            Dict: Updated scheduler statistics
        """
        logger.info("Running export batch immediately")
        self._process_export_batch()
        return self.stats
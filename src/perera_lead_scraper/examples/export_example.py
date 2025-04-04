#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Export Pipeline Example

Demonstrates how to use the CRMExportPipeline and ExportScheduler
to export leads to HubSpot.
"""

import os
import time
import logging
from datetime import datetime

from models.lead import Lead, LeadStatus
from utils.storage import LeadStorage
from utils.logger import get_logger, configure_logging
from integrations.hubspot_client import HubSpotClient
from src.perera_lead_scraper.hubspot.hubspot_mapper import HubSpotMapper
from src.perera_lead_scraper.pipelines.export_pipeline import CRMExportPipeline
from src.perera_lead_scraper.scheduler.scheduler import ExportScheduler

# Configure logging
configure_logging()
logger = get_logger(__name__)


def initialize_components():
    """Initialize the required components for the export pipeline."""
    # Initialize storage
    logger.info("Initializing local storage")
    storage = LeadStorage()
    
    # Initialize HubSpot client
    logger.info("Initializing HubSpot client")
    hubspot_client = HubSpotClient()
    
    # Initialize HubSpot mapper
    logger.info("Initializing HubSpot mapper")
    hubspot_mapper = HubSpotMapper()
    
    # Initialize export pipeline
    logger.info("Initializing CRM export pipeline")
    export_pipeline = CRMExportPipeline(
        hubspot_client=hubspot_client,
        hubspot_mapper=hubspot_mapper,
        local_storage=storage
    )
    
    # Initialize scheduler
    logger.info("Initializing export scheduler")
    scheduler = ExportScheduler(
        local_storage=storage,
        crm_export_pipeline=export_pipeline
    )
    
    return storage, export_pipeline, scheduler


def export_single_lead(storage, export_pipeline):
    """Export a single lead using the pipeline."""
    # Get a lead to export
    leads, count = storage.get_leads_by_status(LeadStatus.ENRICHED, limit=1)
    
    if not leads:
        logger.warning("No enriched leads found for export")
        return
    
    lead = leads[0]
    logger.info(f"Exporting lead: {lead.project_name} (ID: {lead.id})")
    
    # Export the lead
    success = export_pipeline.export_lead(lead)
    
    if success:
        logger.info(f"Successfully exported lead: {lead.project_name}")
    else:
        logger.error(f"Failed to export lead: {lead.project_name}")


def run_scheduled_export(scheduler):
    """Run a scheduled export using the scheduler."""
    # Start the scheduler
    logger.info("Starting export scheduler")
    scheduler.start_scheduler()
    
    try:
        # Run for a short time
        logger.info("Scheduler running. Press Ctrl+C to stop...")
        
        # Also trigger an immediate export
        logger.info("Triggering immediate export batch")
        scheduler.run_export_now()
        
        # Show status
        status = scheduler.get_scheduler_status()
        logger.info(f"Scheduler status: {status}")
        
        # Keep running for a while
        time.sleep(60)  # Run for 1 minute
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        # Stop the scheduler
        logger.info("Stopping scheduler")
        scheduler.stop_scheduler()


def main():
    """Main function to demonstrate the export pipeline and scheduler."""
    logger.info("Starting export example")
    
    # Initialize components
    storage, export_pipeline, scheduler = initialize_components()
    
    # Example 1: Export a single lead
    logger.info("EXAMPLE 1: EXPORT SINGLE LEAD")
    export_single_lead(storage, export_pipeline)
    
    # Example 2: Run scheduled export
    logger.info("EXAMPLE 2: RUN SCHEDULED EXPORT")
    run_scheduled_export(scheduler)
    
    logger.info("Export example completed")


if __name__ == "__main__":
    main()
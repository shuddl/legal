#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lead Generation Orchestrator

Central coordination module for the Perera Construction Lead Scraper system.
Manages component lifecycle, scheduling, resource allocation, and system health.
"""

import os
import time
import uuid
import logging
import threading
import multiprocessing
import signal
import datetime
import psutil
from typing import Dict, List, Any, Optional, Tuple, Set, Callable, Type
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

# Scheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor as APThreadPoolExecutor
from pytz import utc

# Application Modules
from models.lead import Lead, LeadStatus, MarketSector, LeadType, DataSource
from utils.storage import LeadStorage
from utils.logger import get_logger, log_integration_event
from src.perera_lead_scraper.config import config, AppConfig
from src.perera_lead_scraper.pipelines.export_pipeline import CRMExportPipeline
from src.perera_lead_scraper.scheduler.scheduler import ExportScheduler
from src.perera_lead_scraper.hubspot.hubspot_mapper import HubSpotMapper
from integrations.hubspot_client import HubSpotClient

# Configure logger
logger = get_logger(__name__)

# Constants
DEFAULT_MAX_WORKERS = 5
DEFAULT_MAX_CONCURRENT_SOURCES = 3
DEFAULT_MIN_SOURCE_INTERVAL_MINS = 60
DEFAULT_RESOURCE_CHECK_INTERVAL_SECS = 60
DEFAULT_MAX_CPU_PERCENT = 80
DEFAULT_MAX_MEMORY_PERCENT = 80
DEFAULT_SOURCE_TIMEOUT_SECS = 300  # 5 minutes
DEFAULT_LEAD_BATCH_SIZE = 50
DEFAULT_SOURCE_COOLDOWN_MINS = 15
DEFAULT_PERFORMANCE_HISTORY_SIZE = 10


class OrchestratorStatus(str, Enum):
    """Status of the lead generation orchestrator."""
    INITIALIZED = "initialized"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class SourcePerformanceMetrics:
    """Performance metrics for a data source."""
    source_id: uuid.UUID
    name: str
    last_execution_time: Optional[datetime.datetime] = None
    avg_execution_time_ms: float = 0.0
    total_leads_found: int = 0
    valid_leads_found: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    success_rate: float = 1.0
    quality_score: float = 0.0
    priority_score: float = 0.0
    execution_times: List[float] = field(default_factory=list)
    execution_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def update_metrics(self, 
                      execution_time_ms: float,
                      leads_found: int,
                      valid_leads: int,
                      had_error: bool = False) -> None:
        """
        Update source performance metrics.
        
        Args:
            execution_time_ms: Execution time in milliseconds
            leads_found: Total number of leads found
            valid_leads: Number of valid leads found
            had_error: Whether an error occurred during processing
        """
        self.last_execution_time = datetime.datetime.now()
        
        # Update execution time metrics
        self.execution_times.append(execution_time_ms)
        if len(self.execution_times) > DEFAULT_PERFORMANCE_HISTORY_SIZE:
            self.execution_times.pop(0)
        
        self.avg_execution_time_ms = sum(self.execution_times) / len(self.execution_times)
        
        # Update lead metrics
        self.total_leads_found += leads_found
        self.valid_leads_found += valid_leads
        
        # Update error metrics
        if had_error:
            self.error_count += 1
            self.consecutive_errors += 1
        else:
            self.consecutive_errors = 0
        
        # Calculate success rate
        execution_count = len(self.execution_history) + 1
        self.success_rate = (execution_count - self.error_count) / execution_count if execution_count > 0 else 1.0
        
        # Calculate quality score - ratio of valid leads to total leads found
        if self.total_leads_found > 0:
            self.quality_score = self.valid_leads_found / self.total_leads_found
        
        # Update execution history
        history_entry = {
            "timestamp": self.last_execution_time,
            "execution_time_ms": execution_time_ms,
            "leads_found": leads_found,
            "valid_leads": valid_leads,
            "had_error": had_error
        }
        
        self.execution_history.append(history_entry)
        if len(self.execution_history) > DEFAULT_PERFORMANCE_HISTORY_SIZE:
            self.execution_history.pop(0)
            
        # Calculate priority score - combines quality, success rate, and lead volume
        lead_volume_factor = min(1.0, self.valid_leads_found / 100)  # Normalize to 0-1
        self.priority_score = (
            0.4 * self.quality_score +
            0.4 * self.success_rate +
            0.2 * lead_volume_factor
        )


class LeadGenerationOrchestrator:
    """
    Central orchestration for lead generation process.
    
    Coordinates all system components, manages scheduling, resource allocation,
    and ensures overall system health and performance.
    """
    
    def __init__(self, app_config: Optional[AppConfig] = None):
        """
        Initialize the lead generation orchestrator.
        
        Args:
            app_config: Application configuration (or None to use default)
        """
        self.config = app_config or config
        self.status = OrchestratorStatus.INITIALIZED
        
        # Component references
        self.storage = None
        self.hubspot_client = None
        self.hubspot_mapper = None
        self.export_pipeline = None
        self.export_scheduler = None
        
        # Source registry
        self.sources: Dict[uuid.UUID, DataSource] = {}
        self.source_metrics: Dict[uuid.UUID, SourcePerformanceMetrics] = {}
        
        # Execution tracking
        self.active_source_jobs: Dict[uuid.UUID, Dict[str, Any]] = {}
        self.source_locks: Dict[uuid.UUID, threading.Lock] = {}
        
        # Schedulers and executors
        self.scheduler = None
        self.executor = None
        self.max_workers = self.config.orchestrator_max_workers if hasattr(self.config, 'orchestrator_max_workers') else DEFAULT_MAX_WORKERS
        self.max_concurrent_sources = self.config.orchestrator_max_concurrent_sources if hasattr(self.config, 'orchestrator_max_concurrent_sources') else DEFAULT_MAX_CONCURRENT_SOURCES
        
        # System monitoring
        self.system_metrics = {
            "start_time": None,
            "uptime_seconds": 0,
            "total_sources": 0,
            "active_sources": 0,
            "total_leads_processed": 0,
            "leads_exported": 0,
            "total_errors": 0,
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "source_executions": 0,
            "system_status": OrchestratorStatus.INITIALIZED.value,
            "last_update": datetime.datetime.now().isoformat()
        }
        
        # Shutdown handling
        self._shutdown_requested = False
        self._shutdown_event = threading.Event()
        self._resource_monitor_thread = None
        
        # Scheduling parameters
        self.min_source_interval_mins = self.config.orchestrator_min_source_interval_mins if hasattr(self.config, 'orchestrator_min_source_interval_mins') else DEFAULT_MIN_SOURCE_INTERVAL_MINS
        self.max_cpu_percent = self.config.orchestrator_max_cpu_percent if hasattr(self.config, 'orchestrator_max_cpu_percent') else DEFAULT_MAX_CPU_PERCENT
        self.max_memory_percent = self.config.orchestrator_max_memory_percent if hasattr(self.config, 'orchestrator_max_memory_percent') else DEFAULT_MAX_MEMORY_PERCENT
        
        # Initialize lock for metrics
        self._metrics_lock = threading.Lock()
        
        # Register signal handlers for graceful shutdown
        self._register_signal_handlers()
        
        logger.info("Lead Generation Orchestrator initialized")
    
    def _register_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame) -> None:
        """
        Signal handler for graceful shutdown.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.shutdown_gracefully()
    
    def initialize_components(self) -> bool:
        """
        Initialize and validate all required components.
        
        Returns:
            bool: True if initialization was successful, False otherwise
        """
        try:
            logger.info("Initializing system components")
            self.status = OrchestratorStatus.STARTING
            self._update_system_metrics(system_status=OrchestratorStatus.STARTING.value)
            
            # Initialize storage
            logger.info("Initializing storage")
            self.storage = LeadStorage()
            
            # Initialize HubSpot components if export is enabled
            if self.config.export_to_hubspot:
                logger.info("Initializing HubSpot components")
                
                # Check for required HubSpot API key
                if not self.config.hubspot_api_key:
                    logger.error("HubSpot API key is missing but export_to_hubspot is True")
                    return False
                
                # Initialize HubSpot client
                self.hubspot_client = HubSpotClient(api_key=self.config.hubspot_api_key)
                
                # Initialize HubSpot mapper
                self.hubspot_mapper = HubSpotMapper()
                
                # Initialize export pipeline
                self.export_pipeline = CRMExportPipeline(
                    hubspot_client=self.hubspot_client,
                    hubspot_mapper=self.hubspot_mapper,
                    local_storage=self.storage
                )
                
                # Initialize export scheduler
                self.export_scheduler = ExportScheduler(
                    local_storage=self.storage,
                    crm_export_pipeline=self.export_pipeline
                )
            else:
                logger.info("HubSpot export is disabled, skipping related components")
            
            # Initialize scheduler
            logger.info("Initializing job scheduler")
            jobstores = {
                'default': MemoryJobStore()
            }
            executors = {
                'default': APThreadPoolExecutor(self.max_workers)
            }
            job_defaults = {
                'coalesce': True,
                'max_instances': 1,
                'misfire_grace_time': 60  # Allow jobs to be executed up to 60 seconds late
            }
            
            self.scheduler = BackgroundScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone=utc
            )
            
            # Add job execution listener
            self.scheduler.add_listener(
                self._job_execution_listener,
                EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
            )
            
            # Initialize thread pool executor
            logger.info(f"Initializing thread pool with {self.max_workers} workers")
            self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
            
            # Load data sources
            logger.info("Loading data sources")
            self._load_data_sources()
            
            # Initialize metrics
            self.system_metrics["total_sources"] = len(self.sources)
            
            # Start resource monitoring
            self._start_resource_monitoring()
            
            logger.info("Component initialization completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing components: {str(e)}", exc_info=True)
            self.status = OrchestratorStatus.ERROR
            self._update_system_metrics(system_status=OrchestratorStatus.ERROR.value)
            return False
    
    def _load_data_sources(self) -> None:
        """Load data sources from configuration."""
        try:
            # Check if sources path exists
            sources_path = self.config.sources_path
            if not os.path.exists(sources_path):
                logger.error(f"Sources configuration file not found: {sources_path}")
                return
            
            # Load sources JSON configuration
            sources_config = self.config.load_source_config(sources_path)
            sources_list = sources_config.get("sources", [])
            
            logger.info(f"Loaded {len(sources_list)} sources from configuration")
            
            # Convert to DataSource objects and store in registry
            for source_dict in sources_list:
                try:
                    source = DataSource.model_validate(source_dict)
                    
                    # Store in registry
                    self.sources[source.id] = source
                    
                    # Initialize source metrics
                    self.source_metrics[source.id] = SourcePerformanceMetrics(
                        source_id=source.id,
                        name=source.name
                    )
                    
                    # Initialize source lock
                    self.source_locks[source.id] = threading.Lock()
                    
                    logger.info(f"Registered source: {source.name} ({source.id})")
                    
                except Exception as e:
                    logger.error(f"Error parsing source configuration: {str(e)}")
            
            # Log summary
            active_sources = sum(1 for s in self.sources.values() if s.active)
            logger.info(f"Loaded {len(self.sources)} total sources ({active_sources} active)")
            
        except Exception as e:
            logger.error(f"Error loading data sources: {str(e)}", exc_info=True)
    
    def _start_resource_monitoring(self) -> None:
        """Start the resource monitoring thread."""
        self._resource_monitor_thread = threading.Thread(
            target=self._resource_monitor_task,
            daemon=True,
            name="ResourceMonitor"
        )
        self._resource_monitor_thread.start()
        logger.info("Resource monitoring started")
    
    def _resource_monitor_task(self) -> None:
        """Continuously monitor system resources."""
        logger.info("Resource monitor thread started")
        
        interval = getattr(self.config, 'resource_check_interval_secs', DEFAULT_RESOURCE_CHECK_INTERVAL_SECS)
        
        while not self._shutdown_event.is_set():
            try:
                # Get current resource usage
                cpu_percent = psutil.cpu_percent(interval=0.1)
                memory_percent = psutil.virtual_memory().percent
                
                # Update metrics
                with self._metrics_lock:
                    self.system_metrics["cpu_usage"] = cpu_percent
                    self.system_metrics["memory_usage"] = memory_percent
                    
                    # Update uptime if system is running
                    if self.system_metrics["start_time"] and self.status == OrchestratorStatus.RUNNING:
                        start_time = datetime.datetime.fromisoformat(self.system_metrics["start_time"])
                        uptime = (datetime.datetime.now() - start_time).total_seconds()
                        self.system_metrics["uptime_seconds"] = uptime
                    
                    self.system_metrics["last_update"] = datetime.datetime.now().isoformat()
                
                # Check if we need to throttle source processing
                if cpu_percent > self.max_cpu_percent or memory_percent > self.max_memory_percent:
                    logger.warning(f"Resource limits exceeded: CPU {cpu_percent}%, Memory {memory_percent}%")
                    self.balance_resource_usage()
                
                # Sleep for the monitoring interval
                self._shutdown_event.wait(interval)
                
            except Exception as e:
                logger.error(f"Error in resource monitoring: {str(e)}")
                # Sleep briefly to avoid spinning in case of persistent errors
                time.sleep(5)
    
    def _job_execution_listener(self, event) -> None:
        """
        Listen for job execution events.
        
        Args:
            event: Job execution event
        """
        job_id = event.job_id
        
        # Update job execution statistics
        if hasattr(event, 'exception') and event.exception:
            logger.error(f"Job {job_id} failed with exception: {event.exception}")
            with self._metrics_lock:
                self.system_metrics["total_errors"] += 1
        else:
            logger.debug(f"Job {job_id} executed successfully")
    
    def start_processing(self) -> None:
        """Begin the orchestration process."""
        if self.status not in [OrchestratorStatus.INITIALIZED, OrchestratorStatus.STOPPED, OrchestratorStatus.ERROR]:
            logger.warning(f"Cannot start processing: Orchestrator is in {self.status} state")
            return
        
        try:
            logger.info("Starting lead generation process")
            
            # Update status
            self.status = OrchestratorStatus.RUNNING
            
            # Initialize system metrics
            with self._metrics_lock:
                self.system_metrics["start_time"] = datetime.datetime.now().isoformat()
                self.system_metrics["system_status"] = OrchestratorStatus.RUNNING.value
            
            # Start scheduler
            logger.info("Starting job scheduler")
            self.scheduler.start()
            
            # Start export scheduler if available
            if self.export_scheduler:
                logger.info("Starting export scheduler")
                self.export_scheduler.start_scheduler()
            
            # Schedule source processing
            self.schedule_source_processing()
            
            logger.info("Lead generation process started successfully")
            
        except Exception as e:
            logger.error(f"Error starting lead generation process: {str(e)}", exc_info=True)
            self.status = OrchestratorStatus.ERROR
            self._update_system_metrics(system_status=OrchestratorStatus.ERROR.value)
    
    def schedule_source_processing(self) -> None:
        """
        Set up source processing schedules based on priority and performance.
        
        This method prioritizes sources and schedules them with appropriate intervals
        based on their historical performance and value.
        """
        logger.info("Setting up source processing schedules")
        
        # Clear existing job schedules
        for job in self.scheduler.get_jobs():
            if job.id.startswith('source_'):
                self.scheduler.remove_job(job.id)
        
        # Get prioritized sources
        prioritized_sources = self.prioritize_sources()
        
        # Schedule each source
        for source in prioritized_sources:
            if not source.active:
                logger.info(f"Skipping inactive source: {source.name}")
                continue
            
            # Determine processing interval
            interval_minutes = self.determine_optimal_frequency(source)
            
            # Create job ID
            job_id = f"source_{source.id}"
            
            # Add source processing job
            self.scheduler.add_job(
                func=self._process_source_job,
                args=[source],
                trigger=IntervalTrigger(minutes=interval_minutes),
                id=job_id,
                name=f"Process {source.name}",
                replace_existing=True
            )
            
            logger.info(f"Scheduled source {source.name} with {interval_minutes} minute interval")
        
        logger.info(f"Scheduled {len(prioritized_sources)} sources for processing")
    
    def prioritize_sources(self) -> List[DataSource]:
        """
        Order sources by value and priority.
        
        Returns:
            List[DataSource]: Ordered list of sources
        """
        # Get active sources
        active_sources = [s for s in self.sources.values() if s.active]
        
        # Get metrics for each source
        source_with_metrics = []
        for source in active_sources:
            metrics = self.source_metrics.get(source.id)
            if not metrics:
                # Create default metrics if not available
                metrics = SourcePerformanceMetrics(
                    source_id=source.id, 
                    name=source.name
                )
                self.source_metrics[source.id] = metrics
            
            # Add to list with metrics
            source_with_metrics.append((source, metrics))
        
        # Sort by priority score (descending)
        source_with_metrics.sort(key=lambda x: x[1].priority_score, reverse=True)
        
        # Extract sorted sources
        prioritized_sources = [s for s, _ in source_with_metrics]
        
        # Log priorities
        logger.info("Source priorities:")
        for i, (source, metrics) in enumerate(source_with_metrics):
            logger.info(f"{i+1}. {source.name}: Score {metrics.priority_score:.2f}")
        
        return prioritized_sources
    
    def determine_optimal_frequency(self, source: DataSource) -> int:
        """
        Calculate ideal scraping interval for a source.
        
        Args:
            source: Data source
        
        Returns:
            int: Optimal interval in minutes
        """
        # Get source metrics
        metrics = self.source_metrics.get(source.id)
        if not metrics:
            # Use default interval for sources without metrics
            return self.min_source_interval_mins
        
        # Base interval on source quality and performance
        base_interval = self.min_source_interval_mins
        
        # Adjust based on quality score (higher quality = more frequent)
        quality_factor = 1.0 - metrics.quality_score  # Invert so higher quality means lower factor
        
        # Adjust based on success rate (higher success = more frequent)
        success_factor = 1.0 - metrics.success_rate  # Invert so higher success means lower factor
        
        # Adjust based on error count (more errors = less frequent)
        error_factor = min(1.0, metrics.consecutive_errors / 5.0)  # Scale up to 1.0 after 5 consecutive errors
        
        # Combine factors (all factors increase the interval)
        adjustment_factor = 1.0 + (quality_factor * 0.5) + (success_factor * 0.3) + (error_factor * 1.0)
        
        # Calculate adjusted interval
        adjusted_interval = base_interval * adjustment_factor
        
        # Ensure the interval is reasonable
        min_interval = self.min_source_interval_mins
        max_interval = self.min_source_interval_mins * 6  # Max 6x the minimum interval
        
        # Apply limits
        optimal_interval = max(min_interval, min(max_interval, int(adjusted_interval)))
        
        return optimal_interval
    
    def calculate_source_value(self, source: DataSource) -> float:
        """
        Score source based on lead quality and volume.
        
        Args:
            source: Data source
        
        Returns:
            float: Source value score (0.0-1.0)
        """
        # Get source metrics
        metrics = self.source_metrics.get(source.id)
        if not metrics:
            # Default value for sources without metrics
            return 0.5
        
        # Calculate value based on quality score and lead volume
        quality_component = metrics.quality_score * 0.7  # 70% weight on quality
        
        # Calculate volume component (logarithmic scale to avoid overwhelming by volume)
        max_expected_leads = 1000  # Normalize to this value
        volume_ratio = min(1.0, metrics.valid_leads_found / max_expected_leads)
        volume_component = volume_ratio * 0.3  # 30% weight on volume
        
        # Combine components
        value_score = quality_component + volume_component
        
        return value_score
    
    def balance_resource_usage(self) -> bool:
        """
        Distribute processing load to avoid resource contention.
        
        Returns:
            bool: True if balancing actions were taken, False otherwise
        """
        logger.info("Balancing system resource usage")
        
        try:
            # Get current resource usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            
            # Check if we're over resource limits
            cpu_over_limit = cpu_percent > self.max_cpu_percent
            memory_over_limit = memory_percent > self.max_memory_percent
            
            # If within limits, nothing to do
            if not cpu_over_limit and not memory_over_limit:
                logger.info(f"Resource usage within limits: CPU {cpu_percent}%, Memory {memory_percent}%")
                return False
            
            # Count active source jobs
            active_jobs = len(self.active_source_jobs)
            
            # If no active jobs, can't do much about resource usage
            if active_jobs == 0:
                logger.warning(f"Resource usage high but no active jobs: CPU {cpu_percent}%, Memory {memory_percent}%")
                return False
            
            if cpu_over_limit or memory_over_limit:
                logger.warning(f"Resource limits exceeded: CPU {cpu_percent}%, Memory {memory_percent}%")
                
                # Option 1: Reduce concurrent jobs
                if self.max_concurrent_sources > 1:
                    old_limit = self.max_concurrent_sources
                    self.max_concurrent_sources = max(1, self.max_concurrent_sources - 1)
                    logger.info(f"Reduced concurrent source limit from {old_limit} to {self.max_concurrent_sources}")
                    return True
                
                # Option 2: Adjust scheduler intervals
                self.adjust_schedules_dynamically()
                
                # Option 3: Pause processing if still over limits
                if cpu_percent > self.max_cpu_percent * 1.2 or memory_percent > self.max_memory_percent * 1.2:
                    logger.warning("Resource usage critically high, pausing orchestrator")
                    self.pause_processing()
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error balancing resource usage: {str(e)}")
            return False
    
    def pause_processing(self) -> None:
        """Pause processing to allow resources to recover."""
        if self.status != OrchestratorStatus.RUNNING:
            return
        
        logger.info("Pausing orchestrator processing")
        
        # Update status
        self.status = OrchestratorStatus.PAUSED
        self._update_system_metrics(system_status=OrchestratorStatus.PAUSED.value)
        
        # Pause scheduler
        self.scheduler.pause()
        
        # Schedule automatic resume after cooldown
        cooldown_mins = getattr(self.config, 'orchestrator_pause_cooldown_mins', 5)
        
        def resume_after_cooldown():
            logger.info(f"Cooldown period of {cooldown_mins} minutes completed")
            self.resume_processing()
        
        # Schedule resume job
        self.scheduler.add_job(
            func=resume_after_cooldown,
            trigger='date',
            run_date=datetime.datetime.now() + datetime.timedelta(minutes=cooldown_mins),
            id='resume_after_cooldown',
            replace_existing=True
        )
        
        logger.info(f"Processing paused, will resume after {cooldown_mins} minutes")
    
    def resume_processing(self) -> None:
        """Resume processing after a pause."""
        if self.status != OrchestratorStatus.PAUSED:
            return
        
        logger.info("Resuming orchestrator processing")
        
        # Update status
        self.status = OrchestratorStatus.RUNNING
        self._update_system_metrics(system_status=OrchestratorStatus.RUNNING.value)
        
        # Resume scheduler
        self.scheduler.resume()
        
        logger.info("Processing resumed")
    
    def handle_rate_limits(self, source: DataSource) -> bool:
        """
        Implement rate limiting to prevent scraping detection.
        
        Args:
            source: Data source
        
        Returns:
            bool: True if rate limiting was applied, False otherwise
        """
        # Check if source is currently being processed
        if source.id in self.active_source_jobs:
            logger.info(f"Rate limiting: Source {source.name} is already being processed")
            return True
        
        # Check when source was last processed
        metrics = self.source_metrics.get(source.id)
        if metrics and metrics.last_execution_time:
            # Calculate time since last execution
            time_since_last = datetime.datetime.now() - metrics.last_execution_time
            
            # Get source-specific cooldown period
            cooldown_mins = source.config.get("cooldown_minutes", DEFAULT_SOURCE_COOLDOWN_MINS)
            
            # Apply rate limit if too soon
            if time_since_last.total_seconds() < (cooldown_mins * 60):
                remaining_seconds = (cooldown_mins * 60) - time_since_last.total_seconds()
                logger.info(f"Rate limiting: Source {source.name} on cooldown for {remaining_seconds:.1f} more seconds")
                return True
        
        # No rate limiting needed
        return False
    
    def adjust_schedules_dynamically(self) -> bool:
        """
        Modify schedules based on system performance and resource usage.
        
        Returns:
            bool: True if schedules were adjusted, False otherwise
        """
        logger.info("Dynamically adjusting source schedules")
        
        try:
            # Get current jobs
            jobs = [job for job in self.scheduler.get_jobs() if job.id.startswith('source_')]
            
            if not jobs:
                logger.info("No source jobs to adjust")
                return False
            
            # Get current resource utilization
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory_percent = psutil.virtual_memory().percent
            
            # Determine how aggressive to be with adjustments
            if cpu_percent > self.max_cpu_percent * 1.2 or memory_percent > self.max_memory_percent * 1.2:
                # Critical resource pressure - more aggressive adjustments
                adjustment_factor = 2.0
                min_adjusted_jobs = max(1, len(jobs) // 2)  # Adjust at least half
            elif cpu_percent > self.max_cpu_percent or memory_percent > self.max_memory_percent:
                # Moderate resource pressure
                adjustment_factor = 1.5
                min_adjusted_jobs = max(1, len(jobs) // 3)  # Adjust at least a third
            else:
                # Low resource pressure - minor adjustments
                adjustment_factor = 1.2
                min_adjusted_jobs = 1
            
            # Get source metrics to prioritize adjustments
            source_metrics_list = list(self.source_metrics.values())
            
            # Sort by priority (lowest first, so we adjust less valuable sources first)
            source_metrics_list.sort(key=lambda m: m.priority_score)
            
            # Collect sources to adjust
            adjusted_jobs = 0
            
            # Process jobs in order of lowest priority first
            for metrics in source_metrics_list:
                # Find the corresponding job
                job = next((j for j in jobs if j.id == f"source_{metrics.source_id}"), None)
                
                if not job:
                    continue
                
                # Get current interval
                current_interval = job.trigger.interval.total_seconds() / 60  # Convert to minutes
                
                # Calculate new interval
                new_interval = current_interval * adjustment_factor
                
                # Ensure within reasonable bounds
                max_interval = self.min_source_interval_mins * 12  # Max 12x the minimum
                new_interval = min(max_interval, new_interval)
                
                # Only adjust if significant change
                if new_interval > current_interval * 1.1:
                    # Reschedule with new interval
                    self.scheduler.reschedule_job(
                        job_id=job.id,
                        trigger=IntervalTrigger(minutes=int(new_interval))
                    )
                    
                    logger.info(f"Adjusted schedule for {job.name}: {current_interval:.1f}min -> {new_interval:.1f}min")
                    adjusted_jobs += 1
                
                # Stop if we've adjusted enough jobs
                if adjusted_jobs >= min_adjusted_jobs:
                    break
            
            logger.info(f"Adjusted schedules for {adjusted_jobs} sources")
            return adjusted_jobs > 0
            
        except Exception as e:
            logger.error(f"Error adjusting schedules: {str(e)}")
            return False
    
    def track_source_performance(self) -> Dict[str, Any]:
        """
        Monitor source quality metrics and performance.
        
        Returns:
            Dict[str, Any]: Source performance metrics
        """
        # Compile performance metrics for all sources
        performance_data = {}
        
        for source_id, metrics in self.source_metrics.items():
            source = self.sources.get(source_id)
            if not source:
                continue
            
            performance_data[str(source_id)] = {
                "source_name": source.name,
                "active": source.active,
                "last_execution": metrics.last_execution_time.isoformat() if metrics.last_execution_time else None,
                "avg_execution_time_ms": metrics.avg_execution_time_ms,
                "total_leads_found": metrics.total_leads_found,
                "valid_leads_found": metrics.valid_leads_found,
                "error_count": metrics.error_count,
                "consecutive_errors": metrics.consecutive_errors,
                "success_rate": metrics.success_rate,
                "quality_score": metrics.quality_score,
                "priority_score": metrics.priority_score
            }
        
        return performance_data
    
    def _process_source_job(self, source: DataSource) -> None:
        """
        Process a data source as a scheduled job.
        
        Args:
            source: Data source to process
        """
        # Skip processing if orchestrator is paused or stopping
        if self.status in [OrchestratorStatus.PAUSED, OrchestratorStatus.STOPPING, OrchestratorStatus.STOPPED]:
            logger.info(f"Skipping source {source.name} processing: Orchestrator is {self.status}")
            return
        
        # Skip if source is being rate limited
        if self.handle_rate_limits(source):
            return
        
        # Skip if we've reached the max concurrent sources
        with self._metrics_lock:
            active_count = len(self.active_source_jobs)
            if active_count >= self.max_concurrent_sources:
                logger.info(f"Reached max concurrent sources ({self.max_concurrent_sources}), skipping {source.name}")
                return
        
        # Track the start of processing
        start_time = time.time()
        
        # Create a job entry
        job_entry = {
            "source_id": source.id,
            "source_name": source.name,
            "start_time": start_time,
            "status": "running"
        }
        
        # Register active job
        with self._metrics_lock:
            self.active_source_jobs[source.id] = job_entry
            self.system_metrics["active_sources"] = len(self.active_source_jobs)
            self.system_metrics["source_executions"] += 1
        
        logger.info(f"Starting processing of source: {source.name}")
        
        # Process the source
        try:
            # Try to acquire the source lock
            if not self.source_locks[source.id].acquire(blocking=False):
                logger.warning(f"Source {source.name} is locked by another thread, skipping")
                return
            
            try:
                # Process the source
                leads = self.process_source(source)
                
                # Handle the extracted leads
                if leads:
                    self.handle_new_leads(leads)
                    
                    # Update metrics
                    execution_time_ms = (time.time() - start_time) * 1000
                    valid_leads = len([l for l in leads if l.status != LeadStatus.REJECTED])
                    
                    # Update source metrics
                    metrics = self.source_metrics[source.id]
                    metrics.update_metrics(
                        execution_time_ms=execution_time_ms,
                        leads_found=len(leads),
                        valid_leads=valid_leads,
                        had_error=False
                    )
                    
                    # Log success
                    logger.info(f"Successfully processed source {source.name}: Found {len(leads)} leads ({valid_leads} valid)")
                    
                    # Update job entry
                    job_entry["status"] = "completed"
                    job_entry["leads_found"] = len(leads)
                    job_entry["valid_leads"] = valid_leads
                    job_entry["execution_time_ms"] = execution_time_ms
                    
                else:
                    logger.info(f"No leads found from source: {source.name}")
                    
                    # Update metrics with zero leads
                    execution_time_ms = (time.time() - start_time) * 1000
                    metrics = self.source_metrics[source.id]
                    metrics.update_metrics(
                        execution_time_ms=execution_time_ms,
                        leads_found=0,
                        valid_leads=0,
                        had_error=False
                    )
                    
                    # Update job entry
                    job_entry["status"] = "completed"
                    job_entry["leads_found"] = 0
                    job_entry["valid_leads"] = 0
                    job_entry["execution_time_ms"] = execution_time_ms
                
            finally:
                # Always release the lock
                self.source_locks[source.id].release()
                
        except Exception as e:
            # Handle errors
            logger.error(f"Error processing source {source.name}: {str(e)}", exc_info=True)
            
            # Update source metrics
            execution_time_ms = (time.time() - start_time) * 1000
            metrics = self.source_metrics[source.id]
            metrics.update_metrics(
                execution_time_ms=execution_time_ms,
                leads_found=0,
                valid_leads=0,
                had_error=True
            )
            
            # Update job entry
            job_entry["status"] = "error"
            job_entry["error"] = str(e)
            job_entry["execution_time_ms"] = execution_time_ms
            
            # Update system metrics
            with self._metrics_lock:
                self.system_metrics["total_errors"] += 1
        
        finally:
            # Always remove from active jobs
            with self._metrics_lock:
                if source.id in self.active_source_jobs:
                    del self.active_source_jobs[source.id]
                self.system_metrics["active_sources"] = len(self.active_source_jobs)
    
    def process_source(self, source: DataSource) -> List[Lead]:
        """
        Process a single data source to extract leads.
        
        Args:
            source: Data source to process
        
        Returns:
            List[Lead]: Extracted leads
        """
        logger.info(f"Processing source: {source.name} ({source.type.value})")
        
        # Import appropriate scraper based on source type
        source_type = source.type.value
        
        if source_type == "rss":
            from src.perera_lead_scraper.scrapers.rss_scraper import RssScraper
            scraper = RssScraper()
        elif source_type == "website":
            from src.perera_lead_scraper.scrapers.website_scraper import WebsiteScraper
            scraper = WebsiteScraper()
        elif source_type == "city_portal":
            from src.perera_lead_scraper.scrapers.city_portal_scraper import CityPortalScraper
            scraper = CityPortalScraper()
        elif source_type == "permit_database":
            from src.perera_lead_scraper.scrapers.permit_scraper import PermitScraper
            scraper = PermitScraper()
        elif source_type == "api":
            from src.perera_lead_scraper.scrapers.api_scraper import ApiScraper
            scraper = ApiScraper()
        else:
            logger.error(f"Unsupported source type: {source_type}")
            return []
        
        # Set source timeout
        timeout = source.config.get("timeout_seconds", DEFAULT_SOURCE_TIMEOUT_SECS)
        
        try:
            # Execute scraper with timeout
            leads = scraper.scrape(source, timeout=timeout)
            
            # Check result
            if not leads:
                logger.info(f"No leads found from source: {source.name}")
                return []
            
            logger.info(f"Extracted {len(leads)} leads from source: {source.name}")
            return leads
            
        except Exception as e:
            logger.error(f"Error scraping source {source.name}: {str(e)}", exc_info=True)
            return []
    
    def handle_new_leads(self, leads: List[Lead]) -> None:
        """
        Process extracted leads through validation, enrichment, and storage.
        
        Args:
            leads: List of leads to process
        """
        if not leads:
            return
        
        logger.info(f"Processing {len(leads)} new leads")
        
        # Process in batches to avoid memory issues with large numbers of leads
        batch_size = DEFAULT_LEAD_BATCH_SIZE
        
        for i in range(0, len(leads), batch_size):
            batch = leads[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} of {(len(leads) + batch_size - 1) // batch_size} ({len(batch)} leads)")
            
            # Process each lead in the batch
            processed_leads = []
            
            for lead in batch:
                try:
                    # Step 1: Validate the lead
                    validated_lead = self._validate_lead(lead)
                    
                    if not validated_lead:
                        logger.info(f"Lead failed validation: {lead.project_name}")
                        continue
                    
                    # Step 2: Enrich the lead
                    enriched_lead = self._enrich_lead(validated_lead)
                    
                    if not enriched_lead:
                        logger.warning(f"Lead enrichment failed: {validated_lead.project_name}")
                        # Still keep the validated lead
                        processed_leads.append(validated_lead)
                        continue
                    
                    # Add enriched lead to processed leads
                    processed_leads.append(enriched_lead)
                    
                except Exception as e:
                    logger.error(f"Error processing lead {lead.project_name}: {str(e)}")
            
            # Store processed leads
            if processed_leads:
                try:
                    for lead in processed_leads:
                        # Save to storage
                        saved_lead = self.storage.save_lead(lead)
                        
                        # Update metrics
                        with self._metrics_lock:
                            self.system_metrics["total_leads_processed"] += 1
                    
                    logger.info(f"Saved {len(processed_leads)} processed leads")
                    
                except Exception as e:
                    logger.error(f"Error saving processed leads: {str(e)}")
    
    def _validate_lead(self, lead: Lead) -> Optional[Lead]:
        """
        Validate a lead to ensure quality.
        
        Args:
            lead: Lead to validate
        
        Returns:
            Optional[Lead]: Validated lead or None if invalid
        """
        try:
            from src.perera_lead_scraper.validation.lead_validator import LeadValidator
            
            validator = LeadValidator()
            validation_result = validator.validate(lead)
            
            if validation_result.is_valid:
                # Update lead status to validated
                lead.status = LeadStatus.VALIDATED
                return lead
            else:
                # Mark as rejected
                lead.status = LeadStatus.REJECTED
                logger.info(f"Lead rejected during validation: {lead.project_name}. Reasons: {validation_result.reasons}")
                return None
                
        except Exception as e:
            logger.error(f"Error validating lead {lead.project_name}: {str(e)}")
            return None
    
    def _enrich_lead(self, lead: Lead) -> Optional[Lead]:
        """
        Enrich a lead with additional data.
        
        Args:
            lead: Lead to enrich
        
        Returns:
            Optional[Lead]: Enriched lead or None if enrichment failed
        """
        try:
            from src.perera_lead_scraper.enrichment.enrichment import LeadEnricher
            
            enricher = LeadEnricher()
            enriched_lead = enricher.enrich(lead)
            
            if enriched_lead:
                # Update lead status to enriched
                enriched_lead.status = LeadStatus.ENRICHED
                return enriched_lead
            else:
                logger.warning(f"Lead enrichment returned no data: {lead.project_name}")
                return None
                
        except Exception as e:
            logger.error(f"Error enriching lead {lead.project_name}: {str(e)}")
            return None
    
    def trigger_export_pipeline(self) -> Dict[str, Any]:
        """
        Initiate HubSpot export process.
        
        Returns:
            Dict[str, Any]: Export statistics
        """
        if not self.export_pipeline or not self.export_scheduler:
            logger.warning("Export pipeline or scheduler not initialized")
            return {"error": "Export components not initialized"}
        
        logger.info("Triggering manual lead export process")
        
        try:
            # Trigger an immediate export
            stats = self.export_scheduler.run_export_now()
            
            # Update system metrics
            with self._metrics_lock:
                export_stats = self.export_pipeline.get_export_statistics()
                self.system_metrics["leads_exported"] = export_stats.get("total_succeeded", 0)
            
            logger.info(f"Export process triggered successfully. Stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error triggering export process: {str(e)}")
            return {"error": str(e)}
    
    def shutdown_gracefully(self) -> bool:
        """
        Properly terminate all components.
        
        Returns:
            bool: True if shutdown was successful, False otherwise
        """
        if self.status == OrchestratorStatus.STOPPED:
            logger.info("Orchestrator already stopped")
            return True
        
        logger.info("Initiating graceful shutdown")
        
        # Update status
        self.status = OrchestratorStatus.STOPPING
        self._update_system_metrics(system_status=OrchestratorStatus.STOPPING.value)
        
        try:
            # Signal shutdown to all threads
            self._shutdown_requested = True
            self._shutdown_event.set()
            
            # Stop the export scheduler if running
            if self.export_scheduler:
                logger.info("Stopping export scheduler")
                self.export_scheduler.stop_scheduler()
            
            # Stop the job scheduler if running
            if self.scheduler and self.scheduler.running:
                logger.info("Stopping job scheduler")
                self.scheduler.shutdown(wait=True)
            
            # Shutdown thread pool
            if self.executor:
                logger.info("Shutting down thread pool")
                self.executor.shutdown(wait=True)
            
            # Wait for resource monitor to terminate
            if self._resource_monitor_thread and self._resource_monitor_thread.is_alive():
                logger.info("Waiting for resource monitor to terminate")
                self._resource_monitor_thread.join(timeout=5.0)
            
            # Update status
            self.status = OrchestratorStatus.STOPPED
            self._update_system_metrics(system_status=OrchestratorStatus.STOPPED.value)
            
            logger.info("Orchestrator shutdown completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}", exc_info=True)
            return False
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """
        Retrieve current performance metrics.
        
        Returns:
            Dict[str, Any]: System metrics
        """
        with self._metrics_lock:
            # Create a copy of metrics
            metrics = self.system_metrics.copy()
            
            # Add current time
            metrics["current_time"] = datetime.datetime.now().isoformat()
            
            # Add source metrics summary
            active_sources = len([s for s in self.sources.values() if s.active])
            metrics["active_source_count"] = active_sources
            metrics["total_source_count"] = len(self.sources)
            
            # Add orchestrator status
            metrics["orchestrator_status"] = self.status.value
        
        return metrics
    
    def _update_system_metrics(self, **kwargs) -> None:
        """
        Update system metrics with the provided values.
        
        Args:
            **kwargs: Metric values to update
        """
        with self._metrics_lock:
            for key, value in kwargs.items():
                if key in self.system_metrics:
                    self.system_metrics[key] = value
            
            # Always update the last update timestamp
            self.system_metrics["last_update"] = datetime.datetime.now().isoformat()


# Main execution
def main():
    """
    Main function to run the lead generation orchestrator.
    """
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("Starting lead generation orchestrator")
    
    # Create orchestrator
    orchestrator = LeadGenerationOrchestrator()
    
    # Initialize components
    if not orchestrator.initialize_components():
        logger.error("Failed to initialize components, exiting")
        return
    
    # Start processing
    orchestrator.start_processing()
    
    try:
        # Keep running until shutdown requested
        while not orchestrator._shutdown_requested:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    finally:
        # Ensure graceful shutdown
        orchestrator.shutdown_gracefully()
    
    logger.info("Lead generation orchestrator exited")


if __name__ == "__main__":
    main()
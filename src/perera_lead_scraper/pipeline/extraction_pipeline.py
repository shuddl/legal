"""
Extraction Pipeline - Core orchestration component for lead extraction.

This module implements the central orchestration component for the lead extraction process,
connecting source management, NLP processing, and storage components. It provides a configurable
pipeline architecture that handles the entire lead extraction workflow from different source types.
"""

import os
import time
import json
import logging
import asyncio
import traceback
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple, Set, Union, Callable
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from functools import partial

# Local imports
from perera_lead_scraper.models.lead import Lead
from perera_lead_scraper.utils.source_registry import DataSource
from perera_lead_scraper.nlp.nlp_processor import NLPProcessor
from perera_lead_scraper.legal.legal_processor import LegalProcessor
from perera_lead_scraper.utils.storage import LocalStorage
import perera_lead_scraper.config as config

# Set up logger
logger = logging.getLogger(__name__)

class PipelineStage(Enum):
    """Enumeration of pipeline stages for tracking and configuration."""
    EXTRACTION = "extraction"
    FILTERING = "filtering"
    DEDUPLICATION = "deduplication"
    ENRICHMENT = "enrichment"
    PRIORITIZATION = "prioritization"
    STORAGE = "storage"

class ProcessingStatus(Enum):
    """Enumeration of processing statuses for leads and sources."""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    PENDING = "pending"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"

class PipelineMetrics:
    """Class for tracking and reporting pipeline metrics."""
    
    def __init__(self):
        self.start_time: datetime = datetime.now()
        self.end_time: Optional[datetime] = None
        self.total_sources: int = 0
        self.processed_sources: int = 0
        self.successful_sources: int = 0
        self.failed_sources: int = 0
        self.total_leads_extracted: int = 0
        self.leads_after_filtering: int = 0
        self.leads_after_deduplication: int = 0
        self.leads_stored: int = 0
        self.stage_timings: Dict[PipelineStage, float] = {stage: 0.0 for stage in PipelineStage}
        self.source_type_stats: Dict[str, Dict[str, int]] = {}
        self.error_counts: Dict[str, int] = {}
        
    def record_stage_time(self, stage: PipelineStage, execution_time: float) -> None:
        """Record the execution time for a pipeline stage."""
        self.stage_timings[stage] += execution_time
        
    def record_source_processed(self, source_type: str, status: ProcessingStatus) -> None:
        """Record a source being processed with its status."""
        self.processed_sources += 1
        
        if source_type not in self.source_type_stats:
            self.source_type_stats[source_type] = {
                'total': 0,
                'success': 0,
                'failed': 0,
                'partial': 0,
                'leads_extracted': 0
            }
        
        self.source_type_stats[source_type]['total'] += 1
        
        if status == ProcessingStatus.SUCCESS:
            self.successful_sources += 1
            self.source_type_stats[source_type]['success'] += 1
        elif status == ProcessingStatus.PARTIAL_SUCCESS:
            self.successful_sources += 1
            self.source_type_stats[source_type]['partial'] += 1
        elif status == ProcessingStatus.FAILED:
            self.failed_sources += 1
            self.source_type_stats[source_type]['failed'] += 1
    
    def record_error(self, error_type: str) -> None:
        """Record an error occurrence by type."""
        if error_type not in self.error_counts:
            self.error_counts[error_type] = 0
        self.error_counts[error_type] += 1
    
    def record_leads_extracted(self, source_type: str, count: int) -> None:
        """Record the number of leads extracted from a source type."""
        self.total_leads_extracted += count
        if source_type in self.source_type_stats:
            self.source_type_stats[source_type]['leads_extracted'] += count
    
    def finalize(self) -> None:
        """Finalize metrics collection, recording end time."""
        self.end_time = datetime.now()
    
    def get_execution_time(self) -> float:
        """Get the total execution time in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.now() - self.start_time).total_seconds()
    
    def get_report(self) -> Dict[str, Any]:
        """Generate a comprehensive metrics report."""
        self.finalize()
        
        report = {
            'execution_time_seconds': self.get_execution_time(),
            'sources': {
                'total': self.total_sources,
                'processed': self.processed_sources,
                'successful': self.successful_sources,
                'failed': self.failed_sources,
                'success_rate': (self.successful_sources / self.total_sources) if self.total_sources > 0 else 0
            },
            'leads': {
                'extracted': self.total_leads_extracted,
                'after_filtering': self.leads_after_filtering,
                'after_deduplication': self.leads_after_deduplication,
                'stored': self.leads_stored,
                'filter_rate': (1 - (self.leads_after_filtering / self.total_leads_extracted)) 
                               if self.total_leads_extracted > 0 else 0,
                'deduplication_rate': (1 - (self.leads_after_deduplication / self.leads_after_filtering))
                                      if self.leads_after_filtering > 0 else 0
            },
            'stage_timings': {stage.value: timing for stage, timing in self.stage_timings.items()},
            'source_type_stats': self.source_type_stats,
            'error_counts': self.error_counts
        }
        
        return report


class LeadExtractionPipeline:
    """
    Central orchestration component for lead extraction process.
    
    This class integrates various components (source management, NLP processing, storage)
    to provide a complete lead extraction pipeline with configurable stages.
    """
    
    def __init__(self, 
                 nlp_processor: Optional[NLPProcessor] = None,
                 legal_processor: Optional[LegalProcessor] = None,
                 storage: Optional[LocalStorage] = None,
                 config_override: Optional[Dict[str, Any]] = None):
        """
        Initialize the lead extraction pipeline.
        
        Args:
            nlp_processor: Optional NLPProcessor instance. If not provided, one will be created.
            legal_processor: Optional LegalProcessor instance for processing legal documents.
            storage: Optional LocalStorage instance. If not provided, one will be created.
            config_override: Optional configuration overrides.
        """
        self.nlp_processor = nlp_processor or NLPProcessor()
        self.legal_processor = legal_processor
        self.storage = storage or LocalStorage()
        
        # Load configuration
        self._load_configuration(config_override)
        
        # Pipeline state
        self.metrics = PipelineMetrics()
        self._processed_lead_cache: Dict[str, datetime] = {}
        self._processing_lock = threading.RLock()
        self._pipeline_stages: Dict[PipelineStage, bool] = {
            PipelineStage.EXTRACTION: True,
            PipelineStage.FILTERING: self.config.get('enable_filtering', True),
            PipelineStage.DEDUPLICATION: self.config.get('enable_deduplication', True),
            PipelineStage.ENRICHMENT: self.config.get('enable_enrichment', True),
            PipelineStage.PRIORITIZATION: self.config.get('enable_prioritization', True),
            PipelineStage.STORAGE: self.config.get('enable_storage', True)
        }
        
        logger.info(f"Lead extraction pipeline initialized with configuration: {self.config}")
        
        # Initialize the lead cache if deduplication is enabled
        if self.is_stage_enabled(PipelineStage.DEDUPLICATION):
            self._init_lead_cache()
    
    def _load_configuration(self, config_override: Optional[Dict[str, Any]] = None) -> None:
        """
        Load pipeline configuration from config module and apply overrides.
        
        Args:
            config_override: Optional configuration overrides.
        """
        # Default configuration
        default_config = {
            'enable_filtering': True,
            'enable_deduplication': True,
            'enable_enrichment': True,
            'enable_prioritization': True,
            'enable_storage': True,
            'min_confidence_threshold': 0.7,
            'similarity_threshold': 0.85,
            'deduplication_lookback_days': 30,
            'max_workers': 4,
            'timeout': {
                'rss': 30,  # seconds
                'website': 60,
                'api': 30,
                'legal': 120,
                'default': 60
            },
            'retries': {
                'max_attempts': 3,
                'backoff_factor': 1.5,
                'max_backoff': 30
            },
            'batch_size': 100,
            'cache_size': 1000
        }
        
        # Load from config module
        try:
            pipeline_config = getattr(config, 'PIPELINE_CONFIG', {})
            default_config.update(pipeline_config)
        except (AttributeError, ImportError) as e:
            logger.warning(f"Failed to load pipeline configuration from config module: {e}")
        
        # Apply overrides
        if config_override:
            default_config.update(config_override)
        
        # Apply environment variable overrides
        for key in default_config:
            env_var = f"PERERA_PIPELINE_{key.upper()}"
            if env_var in os.environ:
                try:
                    # Convert string to appropriate type based on default
                    value = os.environ[env_var]
                    if isinstance(default_config[key], bool):
                        default_config[key] = value.lower() in ('true', 'yes', '1')
                    elif isinstance(default_config[key], int):
                        default_config[key] = int(value)
                    elif isinstance(default_config[key], float):
                        default_config[key] = float(value)
                    elif isinstance(default_config[key], dict):
                        # For nested configs, we'd need more sophisticated parsing
                        try:
                            default_config[key] = json.loads(value)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse JSON from environment variable {env_var}")
                    else:
                        default_config[key] = value
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse environment variable {env_var}: {e}")
        
        self.config = default_config
    
    def _init_lead_cache(self) -> None:
        """Initialize the lead cache for deduplication by loading recent leads from storage."""
        cache_size = self.config.get('cache_size', 1000)
        lookback_days = self.config.get('deduplication_lookback_days', 30)
        
        try:
            # Load recent leads from storage for deduplication cache
            recent_leads = self.storage.get_recent_leads(
                days=lookback_days, 
                limit=cache_size
            )
            
            # Extract fingerprints and timestamps for cache
            with self._processing_lock:
                for lead in recent_leads:
                    fingerprint = self._generate_lead_fingerprint(lead)
                    timestamp = lead.extraction_date or datetime.now()
                    self._processed_lead_cache[fingerprint] = timestamp
            
            logger.info(f"Initialized lead cache with {len(self._processed_lead_cache)} entries")
        except Exception as e:
            logger.error(f"Failed to initialize lead cache: {e}")
            # Continue with empty cache rather than failing pipeline
            self._processed_lead_cache = {}
    
    def is_stage_enabled(self, stage: PipelineStage) -> bool:
        """
        Check if a pipeline stage is enabled.
        
        Args:
            stage: The pipeline stage to check.
            
        Returns:
            True if the stage is enabled, False otherwise.
        """
        return self._pipeline_stages.get(stage, False)
    
    def enable_stage(self, stage: PipelineStage) -> None:
        """
        Enable a pipeline stage.
        
        Args:
            stage: The pipeline stage to enable.
        """
        self._pipeline_stages[stage] = True
        logger.info(f"Enabled pipeline stage: {stage.value}")
    
    def disable_stage(self, stage: PipelineStage) -> None:
        """
        Disable a pipeline stage.
        
        Args:
            stage: The pipeline stage to disable.
        """
        # Extraction can't be disabled
        if stage == PipelineStage.EXTRACTION:
            logger.warning("Cannot disable the extraction stage")
            return
            
        self._pipeline_stages[stage] = False
        logger.info(f"Disabled pipeline stage: {stage.value}")
    
    def _timed_execution(self, stage: PipelineStage, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with timing for metrics.
        
        Args:
            stage: The pipeline stage for metrics tracking.
            func: The function to execute.
            *args: Arguments to pass to the function.
            **kwargs: Keyword arguments to pass to the function.
            
        Returns:
            The result of the function execution.
        """
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time
        
        # Record metrics
        self.metrics.record_stage_time(stage, execution_time)
        logger.debug(f"Executed stage {stage.value} in {execution_time:.2f}s")
        
        return result
    
    def process_sources(self, sources: List[DataSource]) -> Dict[str, Any]:
        """
        Process multiple data sources in parallel.
        
        Args:
            sources: List of DataSource objects to process.
            
        Returns:
            Dictionary with processing results and metrics.
        """
        max_workers = self.config.get('max_workers', 4)
        self.metrics = PipelineMetrics()  # Reset metrics for new run
        self.metrics.total_sources = len(sources)
        
        all_leads: List[Lead] = []
        processing_results: Dict[str, Any] = {}
        
        logger.info(f"Starting processing of {len(sources)} sources with {max_workers} workers")
        
        # Process sources in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all processing tasks
            future_to_source = {
                executor.submit(self.process_source, source): source 
                for source in sources
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    result = future.result()
                    leads = result.get('leads', [])
                    status = result.get('status', ProcessingStatus.FAILED)
                    
                    # Record metrics
                    self.metrics.record_source_processed(source.source_type, status)
                    self.metrics.record_leads_extracted(source.source_type, len(leads))
                    
                    # Store result
                    processing_results[source.source_id] = result
                    all_leads.extend(leads)
                    
                    logger.info(f"Processed source {source.source_id} ({source.source_type}): "
                                f"{len(leads)} leads extracted, status: {status.value}")
                except Exception as e:
                    logger.error(f"Error processing source {source.source_id}: {e}")
                    self.metrics.record_error(type(e).__name__)
                    self.metrics.record_source_processed(source.source_type, ProcessingStatus.FAILED)
                    
                    # Store error result
                    processing_results[source.source_id] = {
                        'source_id': source.source_id,
                        'status': ProcessingStatus.FAILED,
                        'error': str(e),
                        'leads': []
                    }
        
        # Process the combined results through remaining pipeline stages
        if all_leads:
            # Apply filter stage if enabled
            if self.is_stage_enabled(PipelineStage.FILTERING):
                all_leads = self._timed_execution(
                    PipelineStage.FILTERING,
                    self.filter_leads,
                    all_leads
                )
                self.metrics.leads_after_filtering = len(all_leads)
            else:
                self.metrics.leads_after_filtering = len(all_leads)
            
            # Apply deduplication stage if enabled
            if self.is_stage_enabled(PipelineStage.DEDUPLICATION):
                all_leads = self._timed_execution(
                    PipelineStage.DEDUPLICATION,
                    self.deduplicate_leads,
                    all_leads
                )
                self.metrics.leads_after_deduplication = len(all_leads)
            else:
                self.metrics.leads_after_deduplication = len(all_leads)
            
            # Apply enrichment stage if enabled
            if self.is_stage_enabled(PipelineStage.ENRICHMENT):
                all_leads = self._timed_execution(
                    PipelineStage.ENRICHMENT,
                    self.enrich_leads,
                    all_leads
                )
            
            # Apply prioritization stage if enabled
            if self.is_stage_enabled(PipelineStage.PRIORITIZATION):
                all_leads = self._timed_execution(
                    PipelineStage.PRIORITIZATION,
                    self.prioritize_leads,
                    all_leads
                )
            
            # Apply storage stage if enabled
            if self.is_stage_enabled(PipelineStage.STORAGE):
                stored_count = self._timed_execution(
                    PipelineStage.STORAGE,
                    self._store_leads,
                    all_leads
                )
                self.metrics.leads_stored = stored_count
        
        # Finalize metrics
        self.metrics.finalize()
        
        # Return complete results
        return {
            'processing_results': processing_results,
            'metrics': self.metrics.get_report(),
            'total_leads': len(all_leads),
            'leads': all_leads
        }
    
    def process_source(self, source: DataSource) -> Dict[str, Any]:
        """
        Main entry point that dispatches to appropriate extraction method based on source type.
        
        Args:
            source: DataSource object to process.
            
        Returns:
            Dictionary with processing results including leads and status.
        """
        logger.info(f"Processing source: {source.source_id} ({source.source_type})")
        
        # Set default timeout based on source type
        timeout = self.config.get('timeout', {}).get(
            source.source_type, 
            self.config.get('timeout', {}).get('default', 60)
        )
        
        result = {
            'source_id': source.source_id,
            'source_type': source.source_type,
            'processing_time': 0,
            'leads': [],
            'status': ProcessingStatus.PENDING,
            'error': None
        }
        
        try:
            start_time = time.time()
            
            # Dispatch to appropriate extraction method based on source type
            if source.source_type == 'rss':
                leads = self._timed_execution(
                    PipelineStage.EXTRACTION, 
                    self.extract_from_rss,
                    source
                )
            elif source.source_type == 'website':
                leads = self._timed_execution(
                    PipelineStage.EXTRACTION,
                    self.extract_from_website,
                    source
                )
            elif source.source_type == 'api':
                leads = self._timed_execution(
                    PipelineStage.EXTRACTION,
                    self.extract_from_api,
                    source
                )
            elif source.source_type == 'legal':
                leads = self._timed_execution(
                    PipelineStage.EXTRACTION,
                    self.extract_from_legal,
                    source
                )
            else:
                error_msg = f"Unsupported source type: {source.source_type}"
                logger.error(error_msg)
                result['error'] = error_msg
                result['status'] = ProcessingStatus.FAILED
                return result
            
            processing_time = time.time() - start_time
            
            # Update result with extracted leads
            result['leads'] = leads
            result['lead_count'] = len(leads)
            result['processing_time'] = processing_time
            
            # Set success status
            if leads:
                result['status'] = ProcessingStatus.SUCCESS
            else:
                result['status'] = ProcessingStatus.PARTIAL_SUCCESS
                result['error'] = "No leads extracted"
            
            logger.info(f"Successfully processed {source.source_id}: "
                         f"extracted {len(leads)} leads in {processing_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error processing source {source.source_id}: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            
            result['status'] = ProcessingStatus.FAILED
            result['error'] = str(e)
            result['traceback'] = traceback.format_exc()
            self.metrics.record_error(type(e).__name__)
        
        return result
    
    def extract_from_rss(self, source: DataSource) -> List[Lead]:
        """
        Extract leads from an RSS feed source.
        
        Args:
            source: RSS feed data source.
            
        Returns:
            List of extracted Lead objects.
        """
        from perera_lead_scraper.utils.rss_parser import RSSFeedParser
        
        # Get source-specific configuration
        feed_url = source.config.get('feed_url')
        if not feed_url:
            raise ValueError(f"Missing feed_url in source configuration for {source.source_id}")
        
        # Initialize parser
        parser = RSSFeedParser()
        
        # Apply retry logic
        max_attempts = self.config.get('retries', {}).get('max_attempts', 3)
        backoff_factor = self.config.get('retries', {}).get('backoff_factor', 1.5)
        max_backoff = self.config.get('retries', {}).get('max_backoff', 30)
        
        attempts = 0
        last_error = None
        
        while attempts < max_attempts:
            try:
                logger.debug(f"Fetching RSS feed: {feed_url} (attempt {attempts+1}/{max_attempts})")
                
                # Parse the feed
                entries = parser.parse_feed(feed_url)
                
                if not entries:
                    logger.warning(f"No entries found in RSS feed: {feed_url}")
                    return []
                
                logger.info(f"Extracted {len(entries)} entries from RSS feed: {feed_url}")
                
                # Process entries and convert to leads
                leads: List[Lead] = []
                
                for entry in entries:
                    try:
                        # Process with NLP
                        nlp_results = self.nlp_processor.process_text(
                            entry.get('description', ''),
                            include_entities=True,
                            include_sentiment=True,
                            include_classification=True
                        )
                        
                        # Extract relevant information
                        project_type = nlp_results.get('classification', {}).get('project_type')
                        project_stage = nlp_results.get('classification', {}).get('project_stage')
                        location = next((e for e in nlp_results.get('entities', []) 
                                         if e.get('type') == 'LOCATION'), None)
                        organization = next((e for e in nlp_results.get('entities', [])
                                             if e.get('type') == 'ORGANIZATION'), None)
                        amount = next((e for e in nlp_results.get('entities', [])
                                       if e.get('type') == 'MONEY'), None)
                        dates = [e for e in nlp_results.get('entities', [])
                                if e.get('type') == 'DATE']
                        
                        # Create lead object
                        lead = Lead(
                            source_id=source.source_id,
                            source_type=source.source_type,
                            title=entry.get('title', ''),
                            description=entry.get('description', ''),
                            url=entry.get('link', ''),
                            published_date=entry.get('published_parsed'),
                            extraction_date=datetime.now(),
                            project_type=project_type,
                            project_stage=project_stage,
                            location=location.get('text') if location else None,
                            organization=organization.get('text') if organization else None,
                            project_value=amount.get('text') if amount else None,
                            start_date=dates[0].get('text') if dates else None,
                            end_date=dates[1].get('text') if len(dates) > 1 else None,
                            confidence_score=nlp_results.get('confidence', 0.0),
                            raw_data=entry
                        )
                        
                        leads.append(lead)
                    except Exception as e:
                        logger.error(f"Error processing RSS entry: {e}")
                        continue
                
                return leads
                
            except Exception as e:
                attempts += 1
                last_error = e
                
                if attempts < max_attempts:
                    # Calculate backoff time
                    backoff_time = min(backoff_factor ** (attempts - 1), max_backoff)
                    logger.warning(f"RSS feed fetch failed, retrying in {backoff_time:.1f}s: {e}")
                    time.sleep(backoff_time)
                else:
                    logger.error(f"Failed to fetch RSS feed after {max_attempts} attempts: {e}")
        
        # If we get here, all attempts failed
        if last_error:
            raise last_error
        else:
            raise RuntimeError(f"Failed to process RSS feed: {feed_url}")
    
    def extract_from_website(self, source: DataSource) -> List[Lead]:
        """
        Extract leads from a website source.
        
        Args:
            source: Website data source.
            
        Returns:
            List of extracted Lead objects.
        """
        try:
            # Import scraper components
            from perera_lead_scraper.scrapers.scraper_manager import WebScraperManager
            
            # Get source configuration
            url = source.config.get('url')
            selectors = source.config.get('selectors', {})
            
            if not url:
                raise ValueError(f"Missing URL in source configuration for {source.source_id}")
            
            if not selectors:
                logger.warning(f"No selectors defined for {source.source_id}, using defaults")
            
            # Initialize scraper
            scraper_manager = WebScraperManager()
            
            # Scrape website
            scraped_data = scraper_manager.scrape_website(url, selectors)
            
            if not scraped_data:
                logger.warning(f"No data scraped from website: {url}")
                return []
            
            logger.info(f"Scraped {len(scraped_data)} items from website: {url}")
            
            # Process scraped data and convert to leads
            leads: List[Lead] = []
            
            for item in scraped_data:
                try:
                    # Extract content for NLP processing
                    content = item.get('description', '') or item.get('content', '')
                    if not content and 'title' in item:
                        content = item.get('title', '')
                    
                    # Skip items with no content
                    if not content:
                        continue
                    
                    # Process with NLP
                    nlp_results = self.nlp_processor.process_text(
                        content,
                        include_entities=True,
                        include_sentiment=True,
                        include_classification=True
                    )
                    
                    # Extract relevant information
                    project_type = nlp_results.get('classification', {}).get('project_type')
                    project_stage = nlp_results.get('classification', {}).get('project_stage')
                    location = next((e for e in nlp_results.get('entities', []) 
                                     if e.get('type') == 'LOCATION'), None)
                    organization = next((e for e in nlp_results.get('entities', [])
                                         if e.get('type') == 'ORGANIZATION'), None)
                    amount = next((e for e in nlp_results.get('entities', [])
                                   if e.get('type') == 'MONEY'), None)
                    dates = [e for e in nlp_results.get('entities', [])
                             if e.get('type') == 'DATE']
                    
                    # Create lead object
                    lead = Lead(
                        source_id=source.source_id,
                        source_type=source.source_type,
                        title=item.get('title', ''),
                        description=content,
                        url=item.get('url', url),
                        published_date=item.get('date'),
                        extraction_date=datetime.now(),
                        project_type=project_type,
                        project_stage=project_stage,
                        location=location.get('text') if location else None,
                        organization=organization.get('text') if organization else None,
                        project_value=amount.get('text') if amount else None,
                        start_date=dates[0].get('text') if dates else None,
                        end_date=dates[1].get('text') if len(dates) > 1 else None,
                        confidence_score=nlp_results.get('confidence', 0.0),
                        raw_data=item
                    )
                    
                    leads.append(lead)
                except Exception as e:
                    logger.error(f"Error processing scraped item: {e}")
                    continue
            
            return leads
            
        except Exception as e:
            logger.error(f"Error scraping website: {e}")
            raise
    
    def extract_from_api(self, source: DataSource) -> List[Lead]:
        """
        Extract leads from an API source.
        
        Args:
            source: API data source.
            
        Returns:
            List of extracted Lead objects.
        """
        try:
            import requests
            
            # Get source configuration
            api_url = source.config.get('api_url')
            api_key = source.config.get('api_key')
            method = source.config.get('method', 'GET')
            headers = source.config.get('headers', {})
            params = source.config.get('params', {})
            data_path = source.config.get('data_path', '')
            mapping = source.config.get('field_mapping', {})
            
            if not api_url:
                raise ValueError(f"Missing api_url in source configuration for {source.source_id}")
            
            # Add API key to headers if provided
            if api_key:
                headers['Authorization'] = f"Bearer {api_key}"
            
            # Apply retry logic
            max_attempts = self.config.get('retries', {}).get('max_attempts', 3)
            backoff_factor = self.config.get('retries', {}).get('backoff_factor', 1.5)
            max_backoff = self.config.get('retries', {}).get('max_backoff', 30)
            
            attempts = 0
            last_error = None
            
            while attempts < max_attempts:
                try:
                    logger.debug(f"Making API request to: {api_url} (attempt {attempts+1}/{max_attempts})")
                    
                    # Make API request
                    if method.upper() == 'GET':
                        response = requests.get(api_url, headers=headers, params=params, timeout=30)
                    elif method.upper() == 'POST':
                        response = requests.post(api_url, headers=headers, json=params, timeout=30)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")
                    
                    # Check for successful response
                    response.raise_for_status()
                    
                    # Parse response
                    api_data = response.json()
                    
                    # Extract data using path if provided
                    if data_path:
                        parts = data_path.split('.')
                        for part in parts:
                            if part in api_data:
                                api_data = api_data[part]
                            else:
                                raise ValueError(f"Data path '{data_path}' not found in API response")
                    
                    # Ensure data is a list
                    if not isinstance(api_data, list):
                        if isinstance(api_data, dict):
                            api_data = [api_data]
                        else:
                            raise ValueError("API response is not a list or dict")
                    
                    logger.info(f"Retrieved {len(api_data)} items from API: {api_url}")
                    
                    # Process API data and convert to leads
                    leads: List[Lead] = []
                    
                    for item in api_data:
                        try:
                            # Map fields according to configuration
                            mapped_item = {}
                            for target_field, source_field in mapping.items():
                                if '.' in source_field:
                                    # Handle nested fields
                                    parts = source_field.split('.')
                                    value = item
                                    for part in parts:
                                        if part in value:
                                            value = value[part]
                                        else:
                                            value = None
                                            break
                                    if value is not None:
                                        mapped_item[target_field] = value
                                elif source_field in item:
                                    mapped_item[target_field] = item[source_field]
                            
                            # If no mapping defined, use the item as is
                            if not mapping:
                                mapped_item = item
                            
                            # Extract content for NLP processing
                            content = mapped_item.get('description', '') or mapped_item.get('content', '')
                            if not content and 'title' in mapped_item:
                                content = mapped_item.get('title', '')
                            
                            # Skip items with no content
                            if not content:
                                continue
                            
                            # Process with NLP
                            nlp_results = self.nlp_processor.process_text(
                                content,
                                include_entities=True,
                                include_sentiment=True,
                                include_classification=True
                            )
                            
                            # Extract or use mapped fields
                            project_type = mapped_item.get('project_type') or nlp_results.get('classification', {}).get('project_type')
                            project_stage = mapped_item.get('project_stage') or nlp_results.get('classification', {}).get('project_stage')
                            
                            location = mapped_item.get('location')
                            if not location:
                                loc_entity = next((e for e in nlp_results.get('entities', []) 
                                                 if e.get('type') == 'LOCATION'), None)
                                location = loc_entity.get('text') if loc_entity else None
                            
                            organization = mapped_item.get('organization')
                            if not organization:
                                org_entity = next((e for e in nlp_results.get('entities', [])
                                                 if e.get('type') == 'ORGANIZATION'), None)
                                organization = org_entity.get('text') if org_entity else None
                            
                            project_value = mapped_item.get('project_value')
                            if not project_value:
                                amount_entity = next((e for e in nlp_results.get('entities', [])
                                                   if e.get('type') == 'MONEY'), None)
                                project_value = amount_entity.get('text') if amount_entity else None
                            
                            start_date = mapped_item.get('start_date')
                            end_date = mapped_item.get('end_date')
                            if not start_date:
                                dates = [e for e in nlp_results.get('entities', [])
                                       if e.get('type') == 'DATE']
                                start_date = dates[0].get('text') if dates else None
                                end_date = dates[1].get('text') if len(dates) > 1 else None
                            
                            # Create lead object
                            lead = Lead(
                                source_id=source.source_id,
                                source_type=source.source_type,
                                title=mapped_item.get('title', ''),
                                description=content,
                                url=mapped_item.get('url', api_url),
                                published_date=mapped_item.get('published_date'),
                                extraction_date=datetime.now(),
                                project_type=project_type,
                                project_stage=project_stage,
                                location=location,
                                organization=organization,
                                project_value=project_value,
                                start_date=start_date,
                                end_date=end_date,
                                confidence_score=nlp_results.get('confidence', 0.0),
                                raw_data=item
                            )
                            
                            leads.append(lead)
                        except Exception as e:
                            logger.error(f"Error processing API item: {e}")
                            continue
                    
                    return leads
                    
                except requests.RequestException as e:
                    attempts += 1
                    last_error = e
                    
                    if attempts < max_attempts:
                        # Calculate backoff time
                        backoff_time = min(backoff_factor ** (attempts - 1), max_backoff)
                        logger.warning(f"API request failed, retrying in {backoff_time:.1f}s: {e}")
                        time.sleep(backoff_time)
                    else:
                        logger.error(f"Failed to make API request after {max_attempts} attempts: {e}")
            
            # If we get here, all attempts failed
            if last_error:
                raise last_error
            else:
                raise RuntimeError(f"Failed to process API: {api_url}")
                
        except Exception as e:
            logger.error(f"Error processing API source: {e}")
            raise
    
    def extract_from_legal(self, source: DataSource) -> List[Lead]:
        """
        Extract leads from legal documents.
        
        Args:
            source: Legal document data source.
            
        Returns:
            List of extracted Lead objects.
        """
        if not self.legal_processor:
            raise RuntimeError("Legal processor not initialized. Cannot process legal documents.")
        
        try:
            # Get source configuration
            documents_path = source.config.get('documents_path')
            document_type = source.config.get('document_type')
            source_type = source.config.get('source_type', 'file')  # 'file' or 'api'
            
            # If source type is API, use API extraction
            if source_type == 'api':
                # Get API-specific configuration
                api_provider = source.config.get('api_provider')
                location = source.config.get('location')
                days = source.config.get('days', 7)
                max_results = source.config.get('max_results', 25)
                
                if not api_provider:
                    raise ValueError(f"Missing api_provider in source configuration for {source.source_id}")
                
                # Process documents from API
                lead_dicts = self.legal_processor.extract_leads_from_api(
                    provider=api_provider,
                    document_type=document_type,
                    location=location,
                    days=days,
                    max_results=max_results
                )
                
                logger.info(f"Extracted {len(lead_dicts)} leads from {api_provider} API")
                
            else:
                # Traditional file-based extraction
                if not documents_path:
                    raise ValueError(f"Missing documents_path in source configuration for {source.source_id}")
                
                # Process documents from file system
                lead_dicts = self.legal_processor.extract_leads_from_documents(
                    documents_path, 
                    document_type=document_type
                )
                
                logger.info(f"Extracted {len(lead_dicts)} leads from legal documents at: {documents_path}")
            
            # Convert lead dictionaries to Lead objects
            leads = []
            for lead_dict in lead_dicts:
                try:
                    # Create a Lead object from the dictionary
                    lead = Lead(
                        source_id=source.source_id,
                        source_type=source.source_type,
                        title=lead_dict.get('title', ''),
                        description=lead_dict.get('description', ''),
                        url=lead_dict.get('url', ''),
                        published_date=lead_dict.get('published_date'),
                        extraction_date=datetime.now(),
                        project_type=lead_dict.get('market_sector'),
                        location=lead_dict.get('location'),
                        organization=lead_dict.get('entities', {}).get('organization'),
                        project_value=lead_dict.get('project_value'),
                        confidence_score=lead_dict.get('metadata', {}).get('relevance_score', 0.5),
                        raw_data=lead_dict
                    )
                    leads.append(lead)
                except Exception as e:
                    logger.error(f"Error converting lead dictionary to Lead object: {e}")
            
            return leads
            
        except Exception as e:
            logger.error(f"Error processing legal documents: {e}")
            raise
    
    def filter_leads(self, leads: List[Lead], min_confidence: Optional[float] = None) -> List[Lead]:
        """
        Filter leads based on confidence threshold and other criteria.
        
        Args:
            leads: List of leads to filter.
            min_confidence: Optional confidence threshold, overrides configuration.
            
        Returns:
            Filtered list of leads.
        """
        if not leads:
            return []
        
        # Get confidence threshold from config if not provided
        if min_confidence is None:
            min_confidence = self.config.get('min_confidence_threshold', 0.7)
        
        logger.info(f"Filtering {len(leads)} leads with confidence threshold: {min_confidence}")
        
        # Load target markets from configuration
        target_markets = getattr(config, 'TARGET_MARKETS', [])
        target_sectors = getattr(config, 'TARGET_SECTORS', [])
        
        filtered_leads = []
        filter_reasons = {
            'confidence': 0,
            'location': 0,
            'sector': 0,
            'missing_fields': 0,
            'other': 0
        }
        
        for lead in leads:
            # Skip leads below confidence threshold
            if lead.confidence_score < min_confidence:
                filter_reasons['confidence'] += 1
                logger.debug(f"Filtered lead {lead.title[:30]}... due to low confidence: {lead.confidence_score}")
                continue
            
            # Skip leads without required fields
            if not lead.title or not lead.description:
                filter_reasons['missing_fields'] += 1
                logger.debug(f"Filtered lead due to missing required fields: {lead.title}")
                continue
            
            # Skip leads outside target markets (if defined)
            if target_markets and lead.location:
                if not any(market.lower() in lead.location.lower() for market in target_markets):
                    filter_reasons['location'] += 1
                    logger.debug(f"Filtered lead {lead.title[:30]}... outside target markets: {lead.location}")
                    continue
            
            # Skip leads outside target sectors (if defined)
            if target_sectors and lead.project_type:
                if not any(sector.lower() in lead.project_type.lower() for sector in target_sectors):
                    filter_reasons['sector'] += 1
                    logger.debug(f"Filtered lead {lead.title[:30]}... outside target sectors: {lead.project_type}")
                    continue
            
            # If passes all filters, keep it
            filtered_leads.append(lead)
        
        # Log filtering results
        filtered_count = len(leads) - len(filtered_leads)
        if filtered_count > 0:
            logger.info(f"Filtered out {filtered_count} leads: " 
                        f"confidence={filter_reasons['confidence']}, "
                        f"location={filter_reasons['location']}, "
                        f"sector={filter_reasons['sector']}, "
                        f"missing_fields={filter_reasons['missing_fields']}, "
                        f"other={filter_reasons['other']}")
        
        return filtered_leads
    
    def _generate_lead_fingerprint(self, lead: Lead) -> str:
        """
        Generate a fingerprint for a lead to use in deduplication.
        
        Args:
            lead: The lead to generate a fingerprint for.
            
        Returns:
            A string fingerprint.
        """
        # Create a fingerprint using key fields
        # This is a simplified version - could be improved with more sophisticated hashing
        key_parts = [
            lead.title or '',
            lead.description[:100] if lead.description else '',
            lead.organization or '',
            lead.location or '',
            lead.project_type or '',
            str(lead.project_value or '')
        ]
        
        fingerprint = '_'.join(key_parts)
        import hashlib
        return hashlib.md5(fingerprint.encode('utf-8')).hexdigest()
    
    def _calculate_similarity(self, lead1: Lead, lead2: Lead) -> float:
        """
        Calculate similarity between two leads using Jaccard similarity.
        
        Args:
            lead1: First lead.
            lead2: Second lead.
            
        Returns:
            Similarity score between 0 and 1.
        """
        # Helper function to tokenize text
        def tokenize(text):
            if not text:
                return set()
            return set(text.lower().split())
        
        # Get tokens from key fields
        lead1_tokens = tokenize(lead1.title or '') | tokenize(lead1.description or '')
        lead2_tokens = tokenize(lead2.title or '') | tokenize(lead2.description or '')
        
        # Add other key fields
        for field in [lead1.organization, lead1.location, lead1.project_type]:
            if field:
                lead1_tokens |= tokenize(field)
        
        for field in [lead2.organization, lead2.location, lead2.project_type]:
            if field:
                lead2_tokens |= tokenize(field)
        
        # Calculate Jaccard similarity
        if not lead1_tokens or not lead2_tokens:
            return 0.0
        
        intersection = len(lead1_tokens & lead2_tokens)
        union = len(lead1_tokens | lead2_tokens)
        
        return intersection / union if union > 0 else 0.0
    
    def deduplicate_leads(self, leads: List[Lead]) -> List[Lead]:
        """
        Deduplicate leads using fuzzy matching and cached leads.
        
        Args:
            leads: List of leads to deduplicate.
            
        Returns:
            Deduplicated list of leads.
        """
        if not leads:
            return []
        
        logger.info(f"Deduplicating {len(leads)} leads")
        
        # Get similarity threshold from config
        similarity_threshold = self.config.get('similarity_threshold', 0.85)
        
        # First deduplicate within the input lead list
        unique_leads: List[Lead] = []
        duplicate_count = 0
        
        # Sort leads by confidence score (descending) so we keep the highest confidence version
        sorted_leads = sorted(leads, key=lambda x: x.confidence_score or 0, reverse=True)
        
        # Track fingerprints we've seen
        seen_fingerprints: Set[str] = set()
        
        # First pass: exact duplicate removal with fingerprints
        for lead in sorted_leads:
            fingerprint = self._generate_lead_fingerprint(lead)
            
            # Check if this is a duplicate within the batch
            if fingerprint in seen_fingerprints:
                duplicate_count += 1
                continue
            
            # Check if this is a duplicate of a previously processed lead
            with self._processing_lock:
                if fingerprint in self._processed_lead_cache:
                    duplicate_count += 1
                    continue
            
            # Add to unique leads and update tracking
            unique_leads.append(lead)
            seen_fingerprints.add(fingerprint)
        
        # Second pass: fuzzy matching within the batch
        deduplicated_leads: List[Lead] = []
        for lead in unique_leads:
            is_duplicate = False
            
            # Compare against leads we've already determined to be unique
            for existing_lead in deduplicated_leads:
                similarity = self._calculate_similarity(lead, existing_lead)
                
                if similarity >= similarity_threshold:
                    is_duplicate = True
                    duplicate_count += 1
                    logger.debug(f"Found fuzzy duplicate: {lead.title[:30]}... -> {existing_lead.title[:30]}... "
                                 f"(similarity: {similarity:.2f})")
                    break
            
            if not is_duplicate:
                deduplicated_leads.append(lead)
        
        # Update cache with new leads
        with self._processing_lock:
            for lead in deduplicated_leads:
                fingerprint = self._generate_lead_fingerprint(lead)
                self._processed_lead_cache[fingerprint] = datetime.now()
            
            # Prune old cache entries
            current_time = datetime.now()
            lookback_days = self.config.get('deduplication_lookback_days', 30)
            cutoff_time = current_time - timedelta(days=lookback_days)
            
            self._processed_lead_cache = {
                fp: ts for fp, ts in self._processed_lead_cache.items() 
                if ts >= cutoff_time
            }
        
        # Log deduplication results
        if duplicate_count > 0:
            logger.info(f"Removed {duplicate_count} duplicate leads")
        
        return deduplicated_leads
    
    def enrich_leads(self, leads: List[Lead]) -> List[Lead]:
        """
        Enrich leads with additional information.
        
        Args:
            leads: List of leads to enrich.
            
        Returns:
            Enriched list of leads.
        """
        if not leads:
            return []
        
        logger.info(f"Enriching {len(leads)} leads")
        
        # This is a placeholder for more sophisticated enrichment in Phase 4
        # For now, we'll just do some basic normalizations
        
        for lead in leads:
            # Normalize location if present
            if lead.location:
                # Very basic normalization - would be replaced with proper geocoding
                lead.location = lead.location.strip()
                
                # Check for common abbreviations
                state_abbr = {
                    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
                    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
                    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
                    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
                    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
                    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
                    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
                    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
                    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
                    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
                    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
                    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
                    "WI": "Wisconsin", "WY": "Wyoming"
                }
                
                # Check for state abbreviations and expand them
                for abbr, full in state_abbr.items():
                    pattern = rf"\b{abbr}\b"
                    import re
                    if re.search(pattern, lead.location):
                        lead.location = re.sub(pattern, full, lead.location)
            
            # Normalize project value if present
            if lead.project_value and isinstance(lead.project_value, str):
                try:
                    # Extract numeric value from string (e.g., "$1.5 million" -> 1500000)
                    import re
                    value_str = lead.project_value.strip()
                    
                    # Extract numbers
                    numbers = re.findall(r'\d+\.?\d*', value_str)
                    if numbers:
                        numeric_value = float(numbers[0])
                        
                        # Check for magnitude indicators
                        if 'million' in value_str.lower() or 'm' in value_str.lower():
                            numeric_value *= 1000000
                        elif 'billion' in value_str.lower() or 'b' in value_str.lower():
                            numeric_value *= 1000000000
                        elif 'thousand' in value_str.lower() or 'k' in value_str.lower():
                            numeric_value *= 1000
                            
                        lead.project_value = numeric_value
                except Exception as e:
                    logger.warning(f"Failed to normalize project value '{lead.project_value}': {e}")
                    # Keep the original string if normalization fails
            
            # Normalize dates if present
            for date_field in ['published_date', 'start_date', 'end_date']:
                date_value = getattr(lead, date_field, None)
                if date_value and isinstance(date_value, str):
                    try:
                        # Try to parse date string
                        from dateutil import parser as date_parser
                        parsed_date = date_parser.parse(date_value)
                        setattr(lead, date_field, parsed_date)
                    except Exception as e:
                        logger.warning(f"Failed to normalize date '{date_value}': {e}")
                        # Keep the original string if normalization fails
        
        return leads
    
    def prioritize_leads(self, leads: List[Lead]) -> List[Lead]:
        """
        Prioritize leads based on multiple factors.
        
        Args:
            leads: List of leads to prioritize.
            
        Returns:
            Prioritized list of leads.
        """
        if not leads:
            return []
        
        logger.info(f"Prioritizing {len(leads)} leads")
        
        # Load configuration values
        target_markets = getattr(config, 'TARGET_MARKETS', [])
        target_sectors = getattr(config, 'TARGET_SECTORS', [])
        
        # Define scoring weights
        weights = {
            'confidence': 0.3,
            'project_value': 0.25,
            'market_match': 0.2,
            'sector_match': 0.15,
            'recency': 0.1
        }
        
        # Get current date for recency calculation
        current_date = datetime.now()
        
        # Calculate priority score for each lead
        for lead in leads:
            score_components = {}
            
            # Confidence score (0-1)
            score_components['confidence'] = lead.confidence_score or 0
            
            # Project value score (0-1)
            if lead.project_value and isinstance(lead.project_value, (int, float)):
                # Normalize project value score
                # Assuming $10M is the max value for full score
                score_components['project_value'] = min(lead.project_value / 10000000, 1.0)
            else:
                score_components['project_value'] = 0.5  # Default mid-range if no value
            
            # Market match score (0-1)
            if lead.location and target_markets:
                score_components['market_match'] = any(
                    market.lower() in lead.location.lower() for market in target_markets
                )
            else:
                score_components['market_match'] = 0.5  # Default mid-range if no location
            
            # Sector match score (0-1)
            if lead.project_type and target_sectors:
                score_components['sector_match'] = any(
                    sector.lower() in lead.project_type.lower() for sector in target_sectors
                )
            else:
                score_components['sector_match'] = 0.5  # Default mid-range if no project type
            
            # Recency score (0-1)
            if lead.published_date and isinstance(lead.published_date, datetime):
                # Calculate days since publishing
                days_old = (current_date - lead.published_date).days
                # Newer is better (1.0 for today, scaling down to 0.0 for 30+ days old)
                score_components['recency'] = max(0, 1 - (days_old / 30))
            else:
                score_components['recency'] = 0.5  # Default mid-range if no date
            
            # Calculate weighted score
            priority_score = sum(
                score * weights[component]
                for component, score in score_components.items()
            )
            
            # Store priority score and components
            lead.priority_score = priority_score
            lead.priority_factors = score_components
        
        # Sort leads by priority score (descending)
        prioritized_leads = sorted(leads, key=lambda x: x.priority_score or 0, reverse=True)
        
        return prioritized_leads
    
    def _store_leads(self, leads: List[Lead]) -> int:
        """
        Store leads in the persistence layer.
        
        Args:
            leads: List of leads to store.
            
        Returns:
            Number of leads successfully stored.
        """
        if not leads:
            return 0
        
        logger.info(f"Storing {len(leads)} leads")
        
        # Use batch operations for efficiency
        batch_size = self.config.get('batch_size', 100)
        stored_count = 0
        
        # Process in batches
        for i in range(0, len(leads), batch_size):
            batch = leads[i:i+batch_size]
            
            try:
                # Store the batch
                result = self.storage.store_leads(batch)
                stored_count += result.get('success', 0)
                
                if result.get('errors', 0) > 0:
                    logger.warning(f"Failed to store {result.get('errors', 0)} leads in batch {i//batch_size + 1}")
            except Exception as e:
                logger.error(f"Error storing lead batch {i//batch_size + 1}: {e}")
        
        logger.info(f"Successfully stored {stored_count} out of {len(leads)} leads")
        return stored_count
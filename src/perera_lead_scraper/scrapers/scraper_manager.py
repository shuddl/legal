#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scraper Manager - Orchestrates the operation of multiple scrapers.
"""

import os
import time
import logging
import threading
import concurrent.futures
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Type, Set

from src.perera_lead_scraper.utils.source_registry import SourceRegistry, DataSource
from src.perera_lead_scraper.utils.storage import LeadStorage
from src.perera_lead_scraper.scrapers.base_scraper import BaseScraper
from src.perera_lead_scraper.config import config

# Configure logger
logger = logging.getLogger(__name__)


class ScraperManager:
    """
    Manages and orchestrates multiple scrapers.
    
    Responsibilities:
    - Load and maintain a registry of scraper instances
    - Schedule and execute scraping jobs
    - Handle dependencies between scrapers
    - Provide status monitoring and reporting
    """
    
    def __init__(self, registry: SourceRegistry):
        """
        Initialize the scraper manager.
        
        Args:
            registry: Source registry containing data sources
        """
        self.registry = registry
        self.storage = LeadStorage()
        self.scrapers: Dict[str, BaseScraper] = {}
        self.failed_scrapers: Set[str] = set()
        self.running_scrapers: Set[str] = set()
        self.last_run_times: Dict[str, datetime] = {}
        self.lock = threading.RLock()
        
        # Initialize scrapers
        self._initialize_scrapers()
    
    def _initialize_scrapers(self) -> None:
        """Initialize all scrapers from the registry."""
        logger.info("Initializing scrapers from source registry")
        
        with self.lock:
            for source in self.registry.get_active_sources():
                try:
                    scraper = self._create_scraper_for_source(source)
                    if scraper:
                        self.scrapers[source.name] = scraper
                        logger.info(f"Initialized scraper for source: {source.name}")
                except Exception as e:
                    logger.error(f"Failed to initialize scraper for {source.name}: {str(e)}")
                    self.failed_scrapers.add(source.name)
        
        logger.info(f"Initialized {len(self.scrapers)} scrapers")
    
    def _create_scraper_for_source(self, source: DataSource) -> Optional[BaseScraper]:
        """
        Create a scraper instance for a data source.
        
        Args:
            source: Data source
        
        Returns:
            BaseScraper or None: Scraper instance or None if not supported
        """
        # Import the appropriate scraper class based on source type
        if source.type == "rss":
            from src.perera_lead_scraper.scrapers.rss_scraper import RSSFeedScraper
            
            # Get RSS feed URLs from configuration
            rss_config = config.load_source_config(config.rss_sources_path)
            feed_urls = []
            
            for site in rss_config.get("sites", []):
                if site.get("name") == source.name:
                    feed_urls = [source.url]
                    break
            
            if not feed_urls:
                feed_urls = [source.url]
            
            return RSSFeedScraper(source.name, feed_urls, source.config.get("scrape_frequency", config.scrape_interval_hours))
            
        elif source.type == "website" or source.type == "city_portal":
            if source.type == "city_portal":
                from src.perera_lead_scraper.scrapers.city_portal_scraper import CityPortalScraper
                
                city_name = source.config.get("city_name", source.name)
                return CityPortalScraper(city_name, str(config.city_portals_path), source.config.get("scrape_frequency", config.scrape_interval_hours))
                
            else:
                from src.perera_lead_scraper.scrapers.news_scraper import NewsWebsiteScraper
                
                return NewsWebsiteScraper(source.name, source.url, str(config.news_sources_path), source.config.get("scrape_frequency", config.scrape_interval_hours))
        
        elif source.type == "api":
            logger.warning(f"API scrapers not yet implemented for {source.name}")
            return None
        
        else:
            logger.warning(f"Unsupported source type: {source.type} for {source.name}")
            return None
    
    def register_scraper(self, scraper: BaseScraper) -> None:
        """
        Register a scraper with the manager.
        
        Args:
            scraper: Scraper instance to register
        """
        with self.lock:
            self.scrapers[scraper.source_name] = scraper
            logger.info(f"Registered scraper: {scraper.source_name}")
    
    def run_scraper(self, source_name: str) -> bool:
        """
        Execute a specific scraper.
        
        Args:
            source_name: Name of the source to scrape
        
        Returns:
            bool: True if successful, False otherwise
        """
        with self.lock:
            if source_name not in self.scrapers:
                logger.error(f"Scraper not found: {source_name}")
                return False
            
            if source_name in self.running_scrapers:
                logger.warning(f"Scraper already running: {source_name}")
                return False
            
            scraper = self.scrapers[source_name]
            self.running_scrapers.add(source_name)
        
        logger.info(f"Running scraper: {source_name}")
        
        try:
            # Execute the scraper
            leads = scraper.execute()
            
            if leads is None:
                logger.error(f"Scraper failed: {source_name}")
                self.handle_scraper_failure(source_name, "Execution failed")
                return False
            
            if not leads:
                logger.info(f"No leads found for: {source_name}")
            else:
                logger.info(f"Found {len(leads)} leads for: {source_name}")
                
                # Save leads to storage
                for lead in leads:
                    self.storage.save_lead(lead)
            
            # Update last run time
            with self.lock:
                self.last_run_times[source_name] = datetime.now()
                if source_name in self.failed_scrapers:
                    self.failed_scrapers.remove(source_name)
            
            logger.info(f"Scraper completed successfully: {source_name}")
            return True
            
        except Exception as e:
            logger.exception(f"Error running scraper {source_name}: {str(e)}")
            self.handle_scraper_failure(source_name, str(e))
            return False
            
        finally:
            with self.lock:
                self.running_scrapers.discard(source_name)
    
    def run_scrapers_by_type(self, source_type: str) -> bool:
        """
        Run all scrapers of a specific type.
        
        Args:
            source_type: Type of sources to run
        
        Returns:
            bool: True if all successful, False if any failed
        """
        logger.info(f"Running scrapers of type: {source_type}")
        
        # Get all scrapers of this type
        sources_to_run = []
        with self.lock:
            for source_name, scraper in self.scrapers.items():
                if self.registry.get_source(source_name).type == source_type:
                    sources_to_run.append(source_name)
        
        if not sources_to_run:
            logger.warning(f"No active scrapers found for type: {source_type}")
            return False
        
        # Run the scrapers in parallel
        return self.run_scrapers(sources_to_run)
    
    def run_all_scrapers(self) -> bool:
        """
        Run all registered scrapers.
        
        Returns:
            bool: True if all successful, False if any failed
        """
        logger.info("Running all scrapers")
        
        # Get all scraper names
        with self.lock:
            sources_to_run = list(self.scrapers.keys())
        
        if not sources_to_run:
            logger.warning("No active scrapers found")
            return False
        
        # Run the scrapers in parallel
        return self.run_scrapers(sources_to_run)
    
    def run_scrapers(self, source_names: List[str]) -> bool:
        """
        Run multiple scrapers in parallel.
        
        Args:
            source_names: List of source names to run
        
        Returns:
            bool: True if all successful, False if any failed
        """
        if not source_names:
            return True
        
        logger.info(f"Running {len(source_names)} scrapers")
        
        # Use a thread pool to run scrapers in parallel
        max_workers = min(8, len(source_names))
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all scraper tasks
            future_to_source = {
                executor.submit(self.run_scraper, source_name): source_name
                for source_name in source_names
            }
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_source):
                source_name = future_to_source[future]
                try:
                    success = future.result()
                    results.append(success)
                    logger.info(f"Scraper {source_name} completed with status: {'success' if success else 'failure'}")
                except Exception as e:
                    logger.exception(f"Scraper {source_name} raised an exception: {str(e)}")
                    results.append(False)
        
        # Return True only if all scrapers succeeded
        return all(results)
    
    def get_scraper_status(self, source_name: str) -> Dict[str, Any]:
        """
        Get status information for a scraper.
        
        Args:
            source_name: Name of the source
        
        Returns:
            Dict: Status information
        """
        with self.lock:
            if source_name not in self.scrapers:
                return {"status": "not_found", "source_name": source_name}
            
            running = source_name in self.running_scrapers
            failed = source_name in self.failed_scrapers
            last_run = self.last_run_times.get(source_name)
            
            status = "running" if running else "failed" if failed else "idle"
            
            return {
                "source_name": source_name,
                "status": status,
                "last_run": last_run.isoformat() if last_run else None,
                "failed": failed
            }
    
    def handle_scraper_failure(self, source_name: str, error: str) -> None:
        """
        Handle a scraper failure.
        
        Args:
            source_name: Name of the failed source
            error: Error message
        """
        with self.lock:
            self.failed_scrapers.add(source_name)
            self.running_scrapers.discard(source_name)
            
            # Update the source status in the registry
            source = self.registry.get_source(source_name)
            if source:
                source.status = "failed"
                source.metrics["last_error"] = error
                source.metrics["last_error_time"] = datetime.now().isoformat()
                self.registry.update_source(source)
        
        logger.error(f"Scraper {source_name} failed: {error}")
    
    def get_all_scraper_statuses(self) -> List[Dict[str, Any]]:
        """
        Get status information for all scrapers.
        
        Returns:
            List[Dict]: Status information for all scrapers
        """
        with self.lock:
            return [self.get_scraper_status(name) for name in self.scrapers]
    
    def get_failed_scrapers(self) -> List[str]:
        """
        Get list of failed scrapers.
        
        Returns:
            List[str]: Names of failed scrapers
        """
        with self.lock:
            return list(self.failed_scrapers)
    
    def reset_failed_scraper(self, source_name: str) -> bool:
        """
        Reset a failed scraper.
        
        Args:
            source_name: Name of the source to reset
        
        Returns:
            bool: True if successful, False otherwise
        """
        with self.lock:
            if source_name not in self.scrapers:
                logger.error(f"Scraper not found: {source_name}")
                return False
            
            if source_name not in self.failed_scrapers:
                logger.warning(f"Scraper {source_name} is not in failed state")
                return False
            
            self.failed_scrapers.remove(source_name)
            
            # Update the source status in the registry
            source = self.registry.get_source(source_name)
            if source:
                source.status = "active"
                self.registry.update_source(source)
            
            logger.info(f"Reset failed scraper: {source_name}")
            return True
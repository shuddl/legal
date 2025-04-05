#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Base Scraper - Abstract base class for all scrapers.
"""

import abc
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from src.perera_lead_scraper.models.lead import Lead

logger = logging.getLogger(__name__)

class BaseScraper(abc.ABC):
    """
    Abstract base class for all scrapers.
    
    All scraper implementations must inherit from this class.
    """
    
    def __init__(self, source_name: str, scrape_frequency_hours: float = 24.0):
        """
        Initialize the base scraper.
        
        Args:
            source_name: Name of the source
            scrape_frequency_hours: How often to scrape (in hours)
        """
        self.source_name = source_name
        self.scrape_frequency_hours = scrape_frequency_hours
        self.last_scrape_time: Optional[datetime] = None
        self.status: str = "initialized"
        self.error: Optional[str] = None
        self.leads: List[Lead] = []
        self.metrics: Dict[str, Any] = {
            "total_leads_found": 0,
            "total_scrape_time_seconds": 0,
            "average_scrape_time_seconds": 0,
            "scrape_count": 0
        }
        logger.info(f"Initialized {self.__class__.__name__} for source: {source_name}")
    
    @abc.abstractmethod
    def scrape(self) -> List[Lead]:
        """
        Scrape the source for leads.
        
        This method must be implemented by all subclasses.
        
        Returns:
            List[Lead]: List of leads found
        """
        pass
    
    def execute(self) -> Optional[List[Lead]]:
        """
        Execute the scraper with timing and error handling.
        
        Returns:
            Optional[List[Lead]]: List of leads if successful, None if failed
        """
        logger.info(f"Executing {self.__class__.__name__} for source: {self.source_name}")
        
        # Check if it's time to scrape
        if self._should_wait():
            logger.info(f"Skipping scrape for {self.source_name}, not time yet")
            return self.leads
        
        start_time = datetime.now()
        self.status = "running"
        self.error = None
        
        try:
            # Execute the actual scraping
            self.leads = self.scrape()
            
            # Update metrics
            end_time = datetime.now()
            scrape_time = (end_time - start_time).total_seconds()
            
            self.metrics["total_leads_found"] += len(self.leads)
            self.metrics["total_scrape_time_seconds"] += scrape_time
            self.metrics["scrape_count"] += 1
            self.metrics["average_scrape_time_seconds"] = (
                self.metrics["total_scrape_time_seconds"] / self.metrics["scrape_count"]
            )
            self.metrics["last_scrape_time"] = start_time.isoformat()
            self.metrics["last_lead_count"] = len(self.leads)
            
            self.last_scrape_time = start_time
            self.status = "completed"
            
            logger.info(f"Successfully scraped {len(self.leads)} leads from {self.source_name} in {scrape_time:.2f}s")
            return self.leads
            
        except Exception as e:
            # Update status on failure
            end_time = datetime.now()
            scrape_time = (end_time - start_time).total_seconds()
            
            self.error = str(e)
            self.status = "failed"
            self.metrics["last_error"] = self.error
            self.metrics["last_error_time"] = end_time.isoformat()
            self.metrics["total_failures"] = self.metrics.get("total_failures", 0) + 1
            
            logger.exception(f"Error scraping {self.source_name}: {str(e)}")
            return None
    
    def _should_wait(self) -> bool:
        """
        Check if we should wait before scraping again.
        
        Returns:
            bool: True if we should wait, False if we should scrape
        """
        if self.last_scrape_time is None:
            return False
        
        next_scrape_time = self.last_scrape_time + timedelta(hours=self.scrape_frequency_hours)
        return datetime.now() < next_scrape_time
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of the scraper.
        
        Returns:
            Dict[str, Any]: Status information
        """
        return {
            "source_name": self.source_name,
            "status": self.status,
            "last_scrape": self.last_scrape_time.isoformat() if self.last_scrape_time else None,
            "metrics": self.metrics,
            "error": self.error,
            "lead_count": len(self.leads)
        }
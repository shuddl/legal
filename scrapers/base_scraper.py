#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Base Scraper - Abstract base class for all scrapers.
"""

import os
import time
import random
import abc
import re
from datetime import datetime
from urllib.parse import urlparse

from utils.logger import get_logger, log_scraping_event

class BaseScraper(abc.ABC):
    """
    Abstract base class for all scrapers. All specific scrapers must inherit from this class.
    """
    
    def __init__(self, source_name, base_url, scrape_frequency=24):
        """
        Initialize a new scraper.
        
        Args:
            source_name (str): Name of the data source
            base_url (str): Base URL for the source
            scrape_frequency (int): How often to scrape this source (in hours)
        """
        self.source_name = source_name
        self.base_url = base_url
        self.scrape_frequency = scrape_frequency
        self.logger = get_logger(f"scraper.{source_name}")
        self.last_request_time = 0
        self.request_delay = 1.0  # Default delay between requests in seconds
        
        # Validate base_url
        parsed_url = urlparse(base_url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError(f"Invalid base URL: {base_url}")
    
    @abc.abstractmethod
    def initialize(self):
        """
        Set up any necessary configuration or authentication.
        Must be implemented by child classes.
        
        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        pass
    
    @abc.abstractmethod
    def scrape(self):
        """
        Execute the actual scraping process.
        Must be implemented by child classes.
        
        Returns:
            object: Raw scraped data (format depends on the scraper)
        """
        pass
    
    @abc.abstractmethod
    def parse(self, raw_data):
        """
        Convert raw scraped data into a standardized lead format.
        Must be implemented by child classes.
        
        Args:
            raw_data (object): Raw data from the scrape method
        
        Returns:
            list: List of lead dictionaries in standardized format
        """
        pass
    
    @abc.abstractmethod
    def clean_up(self):
        """
        Handle any necessary clean-up operations.
        Must be implemented by child classes.
        
        Returns:
            bool: True if clean-up succeeded, False otherwise
        """
        pass
    
    def execute(self):
        """
        Execute the full scraping process.
        
        Returns:
            list: List of lead dictionaries in standardized format, or None if error
        """
        try:
            log_scraping_event(self.source_name, "start", "Starting scrape")
            
            # Step 1: Initialize
            if not self.initialize():
                log_scraping_event(self.source_name, "error", "Initialization failed", level="ERROR")
                return None
            
            # Step 2: Scrape
            raw_data = self.scrape()
            if raw_data is None:
                log_scraping_event(self.source_name, "error", "Scraping failed", level="ERROR")
                return None
            
            # Step 3: Parse
            leads = self.parse(raw_data)
            if not leads:
                log_scraping_event(self.source_name, "warning", "No leads found", level="WARNING")
                return []
            
            # Step 4: Clean up
            self.clean_up()
            
            log_scraping_event(
                self.source_name, 
                "complete", 
                f"Scrape completed successfully. Found {len(leads)} leads."
            )
            
            return leads
            
        except Exception as e:
            log_scraping_event(
                self.source_name, 
                "error", 
                f"Error during scraping: {str(e)}", 
                level="ERROR"
            )
            self.logger.exception("Detailed error information:")
            return None
    
    def get_user_agent(self):
        """
        Return a randomized user agent string.
        
        Returns:
            str: User agent string
        """
        user_agents = [
            # Chrome
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            # Firefox
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
            # Safari
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            # Edge
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59"
        ]
        return random.choice(user_agents)
    
    def handle_rate_limiting(self, attempt=0, max_attempts=5):
        """
        Implement exponential backoff for rate limit handling.
        
        Args:
            attempt (int): Current attempt number
            max_attempts (int): Maximum number of attempts
        
        Returns:
            bool: True if should retry, False if max attempts reached
        """
        if attempt >= max_attempts:
            return False
            
        # Calculate delay with exponential backoff and jitter
        delay = min(60, (2 ** attempt) + random.random())
        
        self.logger.info(f"Rate limited. Backing off for {delay:.2f} seconds (attempt {attempt+1}/{max_attempts})")
        time.sleep(delay)
        
        return True
    
    def sanitize_text(self, text):
        """
        Clean and normalize text content.
        
        Args:
            text (str): Text to sanitize
        
        Returns:
            str: Sanitized text
        """
        if not text:
            return ""
            
        # Convert to string if not already
        text = str(text)
        
        # Remove excess whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Fix common unicode issues
        text = text.replace('\xa0', ' ')
        
        return text
    
    def extract_date(self, text):
        """
        Attempt to parse dates from various formats.
        
        Args:
            text (str): Text that may contain a date
        
        Returns:
            datetime or None: Parsed date if successful, None otherwise
        """
        if not text:
            return None
            
        # Common date formats to try
        date_formats = [
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%d/%m/%Y',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d %b %Y',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%SZ',
        ]
        
        # Try to parse with different formats
        for date_format in date_formats:
            try:
                return datetime.strptime(text.strip(), date_format)
            except ValueError:
                continue
                
        # If we couldn't parse with exact formats, try regex patterns
        date_patterns = [
            # YYYY-MM-DD
            r'(\d{4}-\d{1,2}-\d{1,2})',
            # MM/DD/YYYY
            r'(\d{1,2}/\d{1,2}/\d{4})',
            # Month DD, YYYY
            r'([A-Za-z]+\s+\d{1,2},\s+\d{4})',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                for date_format in date_formats:
                    try:
                        return datetime.strptime(date_str, date_format)
                    except ValueError:
                        continue
                        
        return None
        
    def delay_request(self):
        """
        Delay the next request to respect rate limits.
        """
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
            
        self.last_request_time = time.time()


# Example implementation for testing
class ExampleScraper(BaseScraper):
    """Example implementation of BaseScraper for testing."""
    
    def initialize(self):
        self.logger.info("Initializing example scraper")
        return True
        
    def scrape(self):
        self.logger.info("Performing example scrape")
        # Simulate getting data
        return [{"title": "Example Project", "description": "A test project"}]
        
    def parse(self, raw_data):
        self.logger.info("Parsing example data")
        leads = []
        for item in raw_data:
            leads.append({
                "lead_id": "example-1",
                "source": self.source_name,
                "project_name": item["title"],
                "description": item["description"],
                "publication_date": datetime.now().isoformat(),
                "retrieved_date": datetime.now().isoformat()
            })
        return leads
        
    def clean_up(self):
        self.logger.info("Cleaning up example scraper")
        return True
        

if __name__ == "__main__":
    # Test the example implementation
    scraper = ExampleScraper("example", "https://example.com")
    leads = scraper.execute()
    
    if leads:
        print(f"Successfully scraped {len(leads)} leads:")
        for lead in leads:
            print(lead)
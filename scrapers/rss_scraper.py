#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RSS Feed Scraper - Implementation of the BaseScraper for RSS feeds.
"""

import os
import time
import hashlib
import datetime
from typing import List, Dict, Any, Optional, Set
import requests
import feedparser
from urllib.parse import urlparse

from scrapers.base_scraper import BaseScraper
from utils.logger import get_logger, log_scraping_event

class RSSFeedScraper(BaseScraper):
    """
    RSS Feed Scraper class for extracting content from RSS feeds.
    Inherits from BaseScraper.
    """
    
    def __init__(self, source_name: str, feed_urls: List[str], scrape_frequency: int = 24):
        """
        Initialize the RSS Feed Scraper.
        
        Args:
            source_name: Name of the data source
            feed_urls: List of RSS feed URLs to scrape
            scrape_frequency: How often to scrape this source (in hours)
        """
        # Call the parent constructor with the first feed URL as base_url
        # This is just to satisfy the BaseScraper requirement
        base_url = feed_urls[0] if feed_urls else ""
        super().__init__(source_name, base_url, scrape_frequency)
        
        self.feed_urls = feed_urls
        self.logger = get_logger(f"scraper.rss.{source_name}")
        self.parsed_feeds = []
        self.feed_formats = {}  # Store detected format for each feed
        
        # Dictionary to store feed entries, keyed by feed URL
        self.entries = {}
        
        # Set a reasonable timeout for feed requests
        self.timeout = 30
    
    def initialize(self) -> bool:
        """
        Verify feed URLs are accessible.
        
        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        self.logger.info(f"Initializing RSS scraper for {self.source_name} with {len(self.feed_urls)} feeds")
        
        if not self.feed_urls:
            self.logger.error("No feed URLs provided")
            return False
        
        # Verify each feed URL is accessible
        accessible_urls = []
        for url in self.feed_urls:
            try:
                # Just check if the URL is reachable
                headers = {"User-Agent": self.get_user_agent()}
                response = requests.head(url, timeout=self.timeout, headers=headers)
                
                if response.status_code < 400:
                    accessible_urls.append(url)
                    self.logger.info(f"Feed URL accessible: {url}")
                else:
                    self.logger.warning(f"Feed URL returned status {response.status_code}: {url}")
            except Exception as e:
                self.logger.warning(f"Error checking feed URL {url}: {str(e)}")
        
        # Update feed_urls with only accessible URLs
        self.feed_urls = accessible_urls
        
        if not self.feed_urls:
            self.logger.error("No accessible feed URLs found")
            return False
        
        return True
    
    def scrape(self) -> Dict[str, Any]:
        """
        Fetch the latest content from all feeds.
        
        Returns:
            Dict[str, Any]: Dictionary with feed URLs as keys and parsed feeds as values
        """
        self.logger.info(f"Scraping {len(self.feed_urls)} RSS feeds")
        
        results = {}
        
        for url in self.feed_urls:
            try:
                self.logger.info(f"Fetching feed: {url}")
                self.delay_request()  # Respect rate limits
                
                # Parse the feed
                feed = feedparser.parse(url)
                
                # Check if parsing was successful
                if feed.get('bozo', 0) == 1 and not feed.get('entries'):
                    self.logger.warning(f"Failed to parse feed {url}: {feed.get('bozo_exception')}")
                    continue
                
                # Store the feed format
                self.feed_formats[url] = self.detect_feed_format(feed)
                self.logger.info(f"Detected feed format for {url}: {self.feed_formats[url]}")
                
                # Store the results
                results[url] = feed
                self.logger.info(f"Successfully parsed feed {url} with {len(feed.entries)} entries")
                
            except Exception as e:
                self.logger.error(f"Error fetching feed {url}: {str(e)}")
                continue
        
        if not results:
            self.logger.error("Failed to fetch any feeds")
            return {}
        
        return results
    
    def parse(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract relevant fields from feed entries.
        
        Args:
            raw_data: Dictionary with feed URLs as keys and parsed feeds as values
        
        Returns:
            List[Dict[str, Any]]: List of lead dictionaries in standardized format
        """
        self.logger.info("Parsing feed data")
        
        all_entries = []
        
        # Process each feed
        for url, feed in raw_data.items():
            feed_format = self.feed_formats.get(url, "unknown")
            self.logger.info(f"Processing {len(feed.entries)} entries from {url} ({feed_format})")
            
            # Extract entries from this feed
            for entry in feed.entries:
                try:
                    lead = self.extract_lead_from_entry(entry, url, feed_format)
                    if lead:
                        all_entries.append(lead)
                except Exception as e:
                    self.logger.warning(f"Error processing entry: {str(e)}")
                    continue
        
        # Deduplicate entries
        unique_entries = self.deduplicate_entries(all_entries)
        
        self.logger.info(f"Extracted {len(unique_entries)} unique leads from {len(raw_data)} feeds")
        
        return unique_entries
    
    def clean_up(self) -> bool:
        """
        Handle any temporary files or connections.
        
        Returns:
            bool: True if clean-up succeeded, False otherwise
        """
        self.logger.info("Cleaning up RSS scraper")
        
        # Reset stored data
        self.parsed_feeds = []
        self.entries = {}
        
        return True
    
    def detect_feed_format(self, feed: Dict[str, Any]) -> str:
        """
        Determine if feed is RSS, Atom, or other format.
        
        Args:
            feed: Parsed feed object
        
        Returns:
            str: Feed format ('rss', 'atom', or 'unknown')
        """
        # Check for Atom indicators
        if feed.get('namespaces') and any('atom' in ns for ns in feed.get('namespaces', {}).values()):
            return 'atom'
        
        # Check for RSS version
        if hasattr(feed, 'version') and feed.version:
            if feed.version.startswith('rss'):
                return 'rss'
            if feed.version.startswith('atom'):
                return 'atom'
        
        # Check feed structure
        if 'feed' in feed and 'entry' in str(feed.keys()):
            return 'atom'
        
        if 'channel' in feed and 'item' in str(feed.keys()):
            return 'rss'
        
        # Default to RSS as it's more common
        return 'rss'
    
    def extract_content_from_entry(self, entry: Dict[str, Any], feed_format: str) -> str:
        """
        Pull content from feed entry based on feed format.
        
        Args:
            entry: Feed entry dictionary
            feed_format: Format of the feed ('rss', 'atom', or 'unknown')
        
        Returns:
            str: Extracted content
        """
        # Try to get content from various possible fields based on feed format
        content = ""
        
        # Check for content in Atom-specific fields
        if feed_format == 'atom':
            if 'content' in entry:
                if isinstance(entry.content, list) and entry.content:
                    content = entry.content[0].value
                else:
                    content = str(entry.content)
            elif 'summary' in entry:
                content = entry.summary
        
        # Check for content in RSS-specific fields
        elif feed_format == 'rss':
            if 'content' in entry:
                if isinstance(entry.content, list) and entry.content:
                    content = entry.content[0].value
                else:
                    content = str(entry.content)
            elif 'summary' in entry:
                content = entry.summary
            elif 'description' in entry:
                content = entry.description
        
        # Fallback to common fields if not found yet
        if not content:
            for field in ['content', 'summary', 'description', 'content_encoded']:
                if field in entry:
                    content_field = getattr(entry, field)
                    if isinstance(content_field, list) and content_field:
                        content = content_field[0].value
                    else:
                        content = str(content_field)
                    break
        
        # Sanitize the content
        return self.sanitize_text(content)
    
    def extract_lead_from_entry(self, entry: Dict[str, Any], feed_url: str, feed_format: str) -> Dict[str, Any]:
        """
        Convert a feed entry to a standardized lead format.
        
        Args:
            entry: Feed entry dictionary
            feed_url: URL of the feed this entry came from
            feed_format: Format of the feed ('rss', 'atom', or 'unknown')
        
        Returns:
            Dict[str, Any]: Lead dictionary in standardized format
        """
        # Extract the title
        title = self.sanitize_text(entry.get('title', ''))
        
        # Extract the link
        link = entry.get('link', '')
        
        # Extract the description/content
        description = self.extract_content_from_entry(entry, feed_format)
        
        # Extract the publication date
        published_date = None
        for date_field in ['published', 'pubDate', 'updated', 'created', 'date']:
            if date_field in entry:
                date_value = entry.get(date_field)
                published_date = self.extract_date(date_value)
                if published_date:
                    break
        
        if not published_date:
            published_date = datetime.datetime.now()
        
        # Generate a unique ID for this lead
        lead_id = self.generate_lead_id(title, link, published_date)
        
        # Create the lead dictionary
        lead = {
            'lead_id': lead_id,
            'source': self.source_name,
            'source_url': feed_url,
            'project_name': title,
            'description': description,
            'url': link,
            'publication_date': published_date.isoformat(),
            'retrieved_date': datetime.datetime.now().isoformat(),
            'feed_format': feed_format,
            'raw_content': str(entry),
        }
        
        return lead
    
    def deduplicate_entries(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate entries across feeds.
        
        Args:
            entries: List of lead dictionaries
        
        Returns:
            List[Dict[str, Any]]: Deduplicated list of lead dictionaries
        """
        # Use a set to track seen lead IDs
        seen_ids: Set[str] = set()
        unique_entries = []
        
        for entry in entries:
            lead_id = entry.get('lead_id', '')
            
            # Skip if we've already seen this lead
            if lead_id in seen_ids:
                continue
            
            # Add to the set of seen IDs and keep this entry
            seen_ids.add(lead_id)
            unique_entries.append(entry)
        
        return unique_entries
    
    def generate_lead_id(self, title: str, link: str, date: datetime.datetime) -> str:
        """
        Create a unique hash-based identifier for a lead.
        
        Args:
            title: Title of the lead
            link: URL of the lead
            date: Publication date of the lead
        
        Returns:
            str: Unique identifier
        """
        # Create a string combining the key fields
        combined = f"{title}|{link}|{date.isoformat()}"
        
        # Generate a hash of the combined string
        hash_obj = hashlib.sha256(combined.encode('utf-8'))
        
        # Return the first 16 characters of the hexadecimal hash
        return hash_obj.hexdigest()[:16]


# Test the RSS scraper if run directly
if __name__ == "__main__":
    # Test feed URLs
    test_feeds = [
        "https://www.constructiondive.com/feeds/news/",
        "https://www.enr.com/rss/all-news",
        "https://www.bdcnetwork.com/rss.xml"
    ]
    
    # Initialize the scraper
    scraper = RSSFeedScraper("test_rss", test_feeds)
    
    # Execute the scraper
    leads = scraper.execute()
    
    if leads:
        print(f"Successfully scraped {len(leads)} leads:")
        for i, lead in enumerate(leads[:5], 1):  # Show first 5 leads
            print(f"\nLead {i}:")
            print(f"  ID: {lead['lead_id']}")
            print(f"  Title: {lead['project_name']}")
            print(f"  URL: {lead['url']}")
            print(f"  Date: {lead['publication_date']}")
            print(f"  Feed Format: {lead['feed_format']}")
            
            # Show a preview of the description
            description = lead['description']
            if len(description) > 100:
                description = description[:100] + "..."
            print(f"  Description: {description}")
    else:
        print("No leads were scraped.")
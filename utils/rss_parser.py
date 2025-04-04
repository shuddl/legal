#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
RSS Parser - Utility for fetching and parsing RSS feeds.
"""

import time
import random
import requests
import feedparser
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse

from utils.logger import get_logger

class RSSParser:
    """Utility class for fetching and parsing RSS feeds."""
    
    def __init__(self, timeout: int = 15, user_agent: Optional[str] = None):
        """
        Initialize the RSS parser.
        
        Args:
            timeout: HTTP request timeout in seconds
            user_agent: User agent string to use for requests
        """
        self.logger = get_logger('rss_parser')
        self.timeout = timeout
        
        # Set default user agent if none provided
        if not user_agent:
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
        self.user_agent = user_agent
    
    def fetch_feed(self, url: str) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Fetch and parse an RSS feed.
        
        Args:
            url: URL of the RSS feed
        
        Returns:
            Tuple containing:
            - bool: Success status
            - Dict: Feed data or empty dict if failed
            - Optional[str]: Error message if failed, None otherwise
        """
        self.logger.debug(f"Fetching feed: {url}")
        
        try:
            # Add a small random delay to avoid overwhelming the server
            time.sleep(random.uniform(0.1, 0.5))
            
            # Parse the URL to validate it
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return False, {}, f"Invalid URL format: {url}"
            
            # Set up headers
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml'
            }
            
            # Fetch the feed content
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # Parse the feed using feedparser
            feed = feedparser.parse(response.content)
            
            # Check if parsing was successful
            if feed.get('bozo', 0) == 1 and not feed.get('entries'):
                exception = feed.get('bozo_exception')
                return False, feed, f"Feed parsing error: {str(exception)}"
            
            # Check if the feed has entries
            if not feed.get('entries'):
                return True, feed, "Feed has no entries"
            
            return True, feed, None
            
        except requests.exceptions.Timeout:
            return False, {}, f"Timeout fetching feed: {url}"
        except requests.exceptions.RequestException as e:
            return False, {}, f"Request error: {str(e)}"
        except Exception as e:
            return False, {}, f"Unexpected error: {str(e)}"
    
    def get_feed_metrics(self, feed: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metrics from a parsed feed.
        
        Args:
            feed: Parsed feed data
        
        Returns:
            Dict: Feed metrics (entry count, etc.)
        """
        metrics = {
            'entry_count': len(feed.get('entries', [])),
        }
        
        # Feed type
        feed_type = 'unknown'
        if feed.get('version', '').startswith('rss'):
            feed_type = 'rss'
        elif feed.get('version', '').startswith('atom'):
            feed_type = 'atom'
        elif any('atom' in ns for ns in feed.get('namespaces', {}).values()):
            feed_type = 'atom'
        metrics['feed_type'] = feed_type
        
        # Feed title if available
        if 'feed' in feed and 'title' in feed.feed:
            metrics['feed_title'] = feed.feed.get('title', '')
        
        # Latest entry date if available
        if feed.get('entries') and 'published_parsed' in feed.entries[0]:
            metrics['latest_entry_date'] = time.strftime(
                '%Y-%m-%d %H:%M:%S', feed.entries[0].published_parsed
            )
        
        return metrics
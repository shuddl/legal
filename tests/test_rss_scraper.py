#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test module for RSS Feed Scraper
"""

import os
import sys
import unittest
import json
from unittest.mock import patch, MagicMock
import feedparser

# Add the parent directory to the path so we can import from the root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scrapers.rss_scraper import RSSFeedScraper

class TestRSSFeedScraper(unittest.TestCase):
    """Test cases for RSSFeedScraper"""

    def setUp(self):
        """Set up test fixtures"""
        self.test_feeds = [
            "https://www.constructiondive.com/feeds/news/",
            "https://www.enr.com/rss/all-news",
            "https://www.bdcnetwork.com/rss.xml"
        ]
        self.scraper = RSSFeedScraper("test_rss", self.test_feeds)
        
        # Load test data
        test_data_dir = os.path.join(os.path.dirname(__file__), 'test_data')
        os.makedirs(test_data_dir, exist_ok=True)
        
        # Sample RSS feed content
        self.rss_feed_content = """
        <?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0">
        <channel>
            <title>Test RSS Feed</title>
            <description>Test RSS Feed Description</description>
            <link>https://example.com/feed</link>
            <item>
                <title>Test Project 1</title>
                <description>This is a test construction project</description>
                <link>https://example.com/project1</link>
                <pubDate>Mon, 01 Apr 2025 12:00:00 GMT</pubDate>
            </item>
            <item>
                <title>Test Project 2</title>
                <description>Another test construction project</description>
                <link>https://example.com/project2</link>
                <pubDate>Tue, 02 Apr 2025 12:00:00 GMT</pubDate>
            </item>
        </channel>
        </rss>
        """
        
        # Sample Atom feed content
        self.atom_feed_content = """
        <?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>Test Atom Feed</title>
            <subtitle>Test Atom Feed Description</subtitle>
            <link href="https://example.com/atom"/>
            <id>https://example.com/atom</id>
            <updated>2025-04-01T12:00:00Z</updated>
            <entry>
                <title>Atom Project 1</title>
                <summary>This is a test construction project in Atom format</summary>
                <link href="https://example.com/atom/project1"/>
                <id>https://example.com/atom/project1</id>
                <updated>2025-04-01T12:00:00Z</updated>
                <content type="html">Detailed content for Project 1</content>
            </entry>
            <entry>
                <title>Atom Project 2</title>
                <summary>Another test construction project in Atom format</summary>
                <link href="https://example.com/atom/project2"/>
                <id>https://example.com/atom/project2</id>
                <updated>2025-04-02T12:00:00Z</updated>
                <content type="html">Detailed content for Project 2</content>
            </entry>
        </feed>
        """
        
        # Create test feed files
        with open(os.path.join(test_data_dir, 'rss_feed.xml'), 'w', encoding='utf-8') as f:
            f.write(self.rss_feed_content)
        
        with open(os.path.join(test_data_dir, 'atom_feed.xml'), 'w', encoding='utf-8') as f:
            f.write(self.atom_feed_content)
            
        self.test_data_dir = test_data_dir

    def test_initialization(self):
        """Test proper initialization of the RSS scraper"""
        self.assertEqual(self.scraper.source_name, "test_rss")
        self.assertEqual(len(self.scraper.feed_urls), 3)

    @patch('requests.head')
    def test_initialize_method(self, mock_head):
        """Test the initialize method that verifies feed URLs"""
        # Mock successful responses for all URLs
        mock_head.return_value = MagicMock(status_code=200)
        
        result = self.scraper.initialize()
        self.assertTrue(result)
        self.assertEqual(mock_head.call_count, 3)

    @patch('feedparser.parse')
    def test_scrape_method(self, mock_parse):
        """Test the scrape method that fetches feeds"""
        # Mock feedparser.parse responses
        rss_feed = feedparser.parse(os.path.join(self.test_data_dir, 'rss_feed.xml'))
        atom_feed = feedparser.parse(os.path.join(self.test_data_dir, 'atom_feed.xml'))
        
        # Set up the mock to return different values for different inputs
        mock_parse.side_effect = lambda url: rss_feed if 'constructiondive' in url else (
            atom_feed if 'enr.com' in url else rss_feed
        )
        
        # Run the scrape method
        result = self.scraper.scrape()
        
        # Verify the results
        self.assertEqual(len(result), 3)
        self.assertIn(self.test_feeds[0], result)
        self.assertIn(self.test_feeds[1], result)
        self.assertIn(self.test_feeds[2], result)

    def test_detect_feed_format(self):
        """Test the detect_feed_format method"""
        # Parse the test feeds
        rss_feed = feedparser.parse(os.path.join(self.test_data_dir, 'rss_feed.xml'))
        atom_feed = feedparser.parse(os.path.join(self.test_data_dir, 'atom_feed.xml'))
        
        # Detect formats
        rss_format = self.scraper.detect_feed_format(rss_feed)
        atom_format = self.scraper.detect_feed_format(atom_feed)
        
        # Verify the results
        self.assertEqual(rss_format, 'rss')
        self.assertEqual(atom_format, 'atom')

    def test_extract_content_from_entry(self):
        """Test the extract_content_from_entry method"""
        # Parse the test feeds
        rss_feed = feedparser.parse(os.path.join(self.test_data_dir, 'rss_feed.xml'))
        atom_feed = feedparser.parse(os.path.join(self.test_data_dir, 'atom_feed.xml'))
        
        # Extract content from entries
        rss_content = self.scraper.extract_content_from_entry(rss_feed.entries[0], 'rss')
        atom_content = self.scraper.extract_content_from_entry(atom_feed.entries[0], 'atom')
        
        # Verify the results
        self.assertIn('test construction project', rss_content)
        self.assertIn('content for Project 1', atom_content)

    @patch('feedparser.parse')
    def test_parse_method(self, mock_parse):
        """Test the parse method that extracts leads from feed entries"""
        # Mock feedparser.parse responses
        rss_feed = feedparser.parse(os.path.join(self.test_data_dir, 'rss_feed.xml'))
        atom_feed = feedparser.parse(os.path.join(self.test_data_dir, 'atom_feed.xml'))
        
        # Create raw_data in the format expected by parse
        raw_data = {
            self.test_feeds[0]: rss_feed,
            self.test_feeds[1]: atom_feed
        }
        
        # Set feed formats
        self.scraper.feed_formats = {
            self.test_feeds[0]: 'rss',
            self.test_feeds[1]: 'atom'
        }
        
        # Run the parse method
        leads = self.scraper.parse(raw_data)
        
        # Verify the results
        self.assertEqual(len(leads), 4)  # 2 from RSS + 2 from Atom
        
        # Check that leads have the expected fields
        for lead in leads:
            self.assertIn('lead_id', lead)
            self.assertIn('source', lead)
            self.assertIn('project_name', lead)
            self.assertIn('description', lead)
            self.assertIn('publication_date', lead)
            self.assertIn('url', lead)

    def test_deduplicate_entries(self):
        """Test the deduplicate_entries method"""
        # Create some test entries with duplicate IDs
        entries = [
            {'lead_id': '1234', 'project_name': 'Project 1'},
            {'lead_id': '5678', 'project_name': 'Project 2'},
            {'lead_id': '1234', 'project_name': 'Project 1 Duplicate'},
            {'lead_id': '9012', 'project_name': 'Project 3'},
        ]
        
        # Run the deduplication
        unique_entries = self.scraper.deduplicate_entries(entries)
        
        # Verify the results
        self.assertEqual(len(unique_entries), 3)
        
        # Check that the duplicate was removed
        lead_ids = [entry['lead_id'] for entry in unique_entries]
        self.assertEqual(lead_ids.count('1234'), 1)

if __name__ == '__main__':
    unittest.main()
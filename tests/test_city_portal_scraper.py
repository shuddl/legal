#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test module for City Portal Scraper
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add the parent directory to the path so we can import from the root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from scrapers.city_portal_scraper import CityPortalScraper

class TestCityPortalScraper(unittest.TestCase):
    """Test cases for CityPortalScraper"""

    def setUp(self):
        """Set up test fixtures"""
        # Create a mock configuration file
        self.test_config_path = os.path.join(os.path.dirname(__file__), 'test_data', 'test_city_portals.json')
        os.makedirs(os.path.dirname(self.test_config_path), exist_ok=True)
        
        # Create test config with mock city
        import json
        test_config = {
            "cities": [
                {
                    "name": "test_city",
                    "base_url": "https://test-city.example.com",
                    "search_url": "https://test-city.example.com/search",
                    "state": "CA",
                    "browser": "chromium",
                    "timeout_ms": 5000,
                    "form": {
                        "fields": {
                            "date_from": {
                                "selector": "#date_from",
                                "type": "date",
                                "default_value": "01/01/2025"
                            },
                            "status": {
                                "selector": "#status",
                                "type": "select",
                                "default_value": "active"
                            }
                        },
                        "submit_selector": "#search_button"
                    },
                    "results": {
                        "results_selector": "#results_table",
                        "no_results_selector": "#no_results",
                        "item_selector": ".result_item",
                        "fields": {
                            "permit_number": {
                                "selector": ".permit_number",
                                "extraction_type": "text"
                            },
                            "address": {
                                "selector": ".address",
                                "extraction_type": "text"
                            },
                            "description": {
                                "selector": ".description",
                                "extraction_type": "text"
                            },
                            "status": {
                                "selector": ".status",
                                "extraction_type": "text"
                            },
                            "url": {
                                "selector": ".permit_link",
                                "extraction_type": "href"
                            }
                        }
                    },
                    "pagination": {
                        "type": "click",
                        "next_selector": "#next_page",
                        "disabled_class": "disabled"
                    }
                }
            ]
        }
        
        with open(self.test_config_path, 'w', encoding='utf-8') as f:
            json.dump(test_config, f, indent=2)

    def test_initialization(self):
        """Test proper initialization of the CityPortalScraper"""
        with patch('scrapers.city_portal_scraper.sync_playwright') as mock_playwright:
            # Create the scraper but mock the browser initialization
            scraper = CityPortalScraper("test_city", self.test_config_path)
            
            # Check initialization
            self.assertEqual(scraper.city_name, "test_city")
            self.assertEqual(scraper.base_url, "https://test-city.example.com")
            self.assertEqual(scraper.city_config['state'], "CA")

    @patch('scrapers.city_portal_scraper.sync_playwright')
    def test_initialize_method(self, mock_playwright):
        """Test the initialize method that sets up the browser"""
        # Mock the playwright components
        mock_instance = MagicMock()
        mock_playwright.return_value.start.return_value = mock_instance
        mock_instance.chromium.launch.return_value = MagicMock()
        
        # Create the scraper
        scraper = CityPortalScraper("test_city", self.test_config_path)
        
        # Call initialize method
        result = scraper.initialize()
        
        # Verify the results
        self.assertTrue(result)
        self.assertTrue(mock_playwright.return_value.start.called)
        self.assertTrue(mock_instance.chromium.launch.called)

    @patch('scrapers.city_portal_scraper.sync_playwright')
    def test_navigate_to_search_page(self, mock_playwright):
        """Test the navigate_to_search_page method"""
        # Mock the playwright components
        mock_instance = MagicMock()
        mock_playwright.return_value.start.return_value = mock_instance
        mock_browser = MagicMock()
        mock_instance.chromium.launch.return_value = mock_browser
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page
        
        # Create the scraper
        scraper = CityPortalScraper("test_city", self.test_config_path)
        scraper.initialize()
        
        # Set up the page object with necessary methods
        scraper.page = mock_page
        
        # Call the navigate_to_search_page method
        result = scraper.navigate_to_search_page(scraper.city_config)
        
        # Verify the results
        self.assertTrue(result)
        mock_page.goto.assert_called_with("https://test-city.example.com/search")

    @patch('scrapers.city_portal_scraper.sync_playwright')
    def test_input_search_criteria(self, mock_playwright):
        """Test the input_search_criteria method"""
        # Mock the playwright components
        mock_instance = MagicMock()
        mock_playwright.return_value.start.return_value = mock_instance
        mock_browser = MagicMock()
        mock_instance.chromium.launch.return_value = mock_browser
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page
        
        # Create the scraper
        scraper = CityPortalScraper("test_city", self.test_config_path)
        scraper.initialize()
        
        # Set up the page object with necessary methods
        scraper.page = mock_page
        
        # Define the search criteria
        search_criteria = {
            "date_from": "01/01/2025",
            "status": "active"
        }
        
        # Call the input_search_criteria method
        result = scraper.input_search_criteria(search_criteria)
        
        # Verify the results
        self.assertTrue(result)
        mock_page.fill.assert_any_call("#date_from", "01/01/2025")
        mock_page.select_option.assert_any_call("#status", value="active")
        mock_page.click.assert_called_with("#search_button")

    @patch('scrapers.city_portal_scraper.sync_playwright')
    def test_extract_results_from_page(self, mock_playwright):
        """Test the extract_results_from_page method"""
        # Mock the playwright components
        mock_instance = MagicMock()
        mock_playwright.return_value.start.return_value = mock_instance
        mock_browser = MagicMock()
        mock_instance.chromium.launch.return_value = mock_browser
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page
        
        # Create the scraper
        scraper = CityPortalScraper("test_city", self.test_config_path)
        scraper.initialize()
        
        # Set up the page object with necessary methods
        scraper.page = mock_page
        
        # Mock the query selector results
        mock_item1 = MagicMock()
        mock_item2 = MagicMock()
        mock_page.query_selector_all.return_value = [mock_item1, mock_item2]
        
        # Mock the item.query_selector results
        def mock_query_selector(selector):
            mock_element = MagicMock()
            if selector == ".permit_number":
                mock_element.inner_text.return_value = "BP123456"
            elif selector == ".address":
                mock_element.inner_text.return_value = "123 Main St"
            elif selector == ".description":
                mock_element.inner_text.return_value = "New Construction"
            elif selector == ".status":
                mock_element.inner_text.return_value = "Active"
            elif selector == ".permit_link":
                mock_element.get_attribute.return_value = "/permits/BP123456"
            return mock_element
            
        mock_item1.query_selector.side_effect = mock_query_selector
        mock_item2.query_selector.side_effect = mock_query_selector
        
        # Call the extract_results_from_page method
        results = scraper.extract_results_from_page()
        
        # Verify the results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["permit_number"], "BP123456")
        self.assertEqual(results[0]["address"], "123 Main St")
        self.assertEqual(results[0]["description"], "New Construction")
        self.assertEqual(results[0]["status"], "Active")
        self.assertEqual(results[1]["permit_number"], "BP123456")

    @patch('scrapers.city_portal_scraper.sync_playwright')
    def test_handle_pagination(self, mock_playwright):
        """Test the handle_pagination method"""
        # Mock the playwright components
        mock_instance = MagicMock()
        mock_playwright.return_value.start.return_value = mock_instance
        mock_browser = MagicMock()
        mock_instance.chromium.launch.return_value = mock_browser
        mock_context = MagicMock()
        mock_browser.new_context.return_value = mock_context
        mock_page = MagicMock()
        mock_context.new_page.return_value = mock_page
        
        # Create the scraper
        scraper = CityPortalScraper("test_city", self.test_config_path)
        scraper.initialize()
        
        # Set up the page object with necessary methods
        scraper.page = mock_page
        
        # Mock the query selector for next button
        mock_next_button = MagicMock()
        mock_next_button.get_attribute.return_value = None  # Not disabled
        mock_page.query_selector.return_value = mock_next_button
        
        # Call the handle_pagination method
        pagination_config = scraper.city_config["pagination"]
        result = scraper.handle_pagination(pagination_config, 1)
        
        # Verify the results
        self.assertTrue(result)
        mock_page.query_selector.assert_called_with("#next_page")
        mock_next_button.click.assert_called_once()

    def test_parse_method(self):
        """Test the parse method that converts raw data to leads"""
        # Create the scraper
        with patch('scrapers.city_portal_scraper.sync_playwright'):
            scraper = CityPortalScraper("test_city", self.test_config_path)
            
            # Create raw permit data
            raw_data = [
                {
                    "permit_number": "BP123456",
                    "address": "123 Main St",
                    "description": "New office building construction",
                    "status": "Active",
                    "application_date": "01/15/2025",
                    "url": "https://test-city.example.com/permits/BP123456"
                },
                {
                    "permit_number": "BP789012",
                    "address": "456 Oak Ave",
                    "description": "Tenant improvement for healthcare facility",
                    "status": "In Review",
                    "application_date": "01/10/2025",
                    "url": "https://test-city.example.com/permits/BP789012"
                }
            ]
            
            # Call the parse method
            leads = scraper.parse(raw_data)
            
            # Verify the results
            self.assertEqual(len(leads), 2)
            
            # Check the first lead
            lead1 = leads[0]
            self.assertEqual(lead1["lead_id"], "test_city_BP123456")
            self.assertEqual(lead1["source"], "city_portal_test_city")
            self.assertEqual(lead1["project_name"], "New office building construction")
            self.assertEqual(lead1["address"], "123 Main St")
            self.assertEqual(lead1["city"], "test_city")
            self.assertEqual(lead1["state"], "CA")
            self.assertEqual(lead1["permit_number"], "BP123456")
            self.assertEqual(lead1["status"], "Active")
            
            # Check the second lead
            lead2 = leads[1]
            self.assertEqual(lead2["lead_id"], "test_city_BP789012")
            self.assertEqual(lead2["project_name"], "Tenant improvement for healthcare facility")
            self.assertTrue("healthcare" in lead2["description"].lower())

if __name__ == '__main__':
    unittest.main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
City Planning Portal Scraper - Implementation of the BaseScraper for city planning websites.
"""

import os
import time
import json
import datetime
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PlaywrightTimeoutError
import re

from scrapers.base_scraper import BaseScraper
from utils.logger import get_logger, log_scraping_event

class CityPortalScraper(BaseScraper):
    """
    City Planning Portal Scraper class for extracting permit and planning data.
    Inherits from BaseScraper.
    Uses Playwright to handle JavaScript-rendered websites.
    """
    
    def __init__(self, city_name: str, config_path: Optional[str] = None, scrape_frequency: int = 24):
        """
        Initialize the City Portal Scraper.
        
        Args:
            city_name: Name of the city
            config_path: Path to the configuration file (defaults to config/city_portals.json)
            scrape_frequency: How often to scrape this source (in hours)
        """
        self.city_name = city_name
        self.logger = get_logger(f"scraper.city.{city_name}")
        
        # Load configuration
        if config_path is None:
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(root_dir, 'config', 'city_portals.json')
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading configuration from {config_path}: {str(e)}")
            raise ValueError(f"Could not load configuration: {str(e)}")
        
        # Get city-specific configuration
        city_config = None
        for city in self.config.get('cities', []):
            if city.get('name').lower() == city_name.lower():
                city_config = city
                break
        
        if not city_config:
            raise ValueError(f"City '{city_name}' not found in configuration")
        
        self.city_config = city_config
        base_url = city_config.get('base_url')
        
        # Initialize browser and page to None
        self.browser = None
        self.page = None
        self.context = None
        
        # Call the parent constructor
        super().__init__(city_name, base_url, scrape_frequency)
    
    def initialize(self) -> bool:
        """
        Set up Playwright browser and initial configuration.
        
        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        self.logger.info(f"Initializing city portal scraper for {self.city_name}")
        
        try:
            # Launch playwright browser
            self.playwright = sync_playwright().start()
            
            # Use chromium by default
            browser_type = self.city_config.get('browser', 'chromium')
            
            # Setup browser options
            browser_options = {
                'headless': True
            }
            
            # Check if we need to use a proxy
            if self.city_config.get('use_proxy', False):
                proxy_config = self.city_config.get('proxy', {})
                if proxy_config:
                    browser_options['proxy'] = {
                        'server': proxy_config.get('server'),
                        'username': proxy_config.get('username', None),
                        'password': proxy_config.get('password', None)
                    }
            
            # Launch browser based on type
            if browser_type == 'firefox':
                self.browser = self.playwright.firefox.launch(**browser_options)
            elif browser_type == 'webkit':
                self.browser = self.playwright.webkit.launch(**browser_options)
            else:  # Default to chromium
                self.browser = self.playwright.chromium.launch(**browser_options)
            
            # Create a context with appropriate viewport and user agent
            context_options = {
                'viewport': {'width': 1920, 'height': 1080},
                'user_agent': self.get_user_agent()
            }
            
            self.context = self.browser.new_context(**context_options)
            self.page = self.context.new_page()
            
            # Set navigation timeout
            timeout = self.city_config.get('timeout_ms', 30000)
            self.page.set_default_navigation_timeout(timeout)
            self.page.set_default_timeout(timeout)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing browser: {str(e)}")
            self.clean_up()
            return False
    
    def scrape(self) -> List[Dict[str, Any]]:
        """
        Execute the scraping process for the city portal.
        
        Returns:
            List[Dict[str, Any]]: List of raw permit/planning data
        """
        self.logger.info(f"Scraping permits for {self.city_name}")
        
        results = []
        
        try:
            # Navigate to the search page
            if not self.navigate_to_search_page(self.city_config):
                self.logger.error("Failed to navigate to search page")
                return []
            
            # Input search criteria
            search_criteria = self.city_config.get('search_criteria', {})
            if not self.input_search_criteria(search_criteria):
                self.logger.error("Failed to input search criteria")
                return []
            
            # Extract results from the first page
            page_results = self.extract_results_from_page()
            if page_results:
                results.extend(page_results)
            
            # Handle pagination if needed
            max_pages = self.city_config.get('max_pages', 5)
            pagination_config = self.city_config.get('pagination', {})
            
            page_num = 1
            while page_num < max_pages:
                try:
                    # Check if we should continue to the next page
                    if not self.handle_pagination(pagination_config, page_num):
                        break
                    
                    # Extract results from the current page
                    page_results = self.extract_results_from_page()
                    if page_results:
                        results.extend(page_results)
                    else:
                        # No more results
                        break
                    
                    page_num += 1
                    
                except Exception as e:
                    self.logger.error(f"Error during pagination on page {page_num}: {str(e)}")
                    break
            
            # Get full details for each result if configured
            detailed_results = []
            if self.city_config.get('fetch_details', False):
                for result in results:
                    try:
                        if 'url' in result:
                            detailed_result = self.extract_permit_details(result['url'], result)
                            if detailed_result:
                                detailed_results.append(detailed_result)
                            else:
                                detailed_results.append(result)
                        else:
                            detailed_results.append(result)
                    except Exception as e:
                        self.logger.error(f"Error fetching details for result: {str(e)}")
                        detailed_results.append(result)
                
                results = detailed_results
            
            self.logger.info(f"Successfully scraped {len(results)} permits from {self.city_name}")
            return results
            
        except Exception as e:
            self.logger.error(f"Error during scraping: {str(e)}")
            return []
    
    def parse(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert raw permit data into a standardized lead format.
        
        Args:
            raw_data: List of raw permit dictionaries
        
        Returns:
            List[Dict[str, Any]]: List of lead dictionaries in standardized format
        """
        self.logger.info(f"Parsing {len(raw_data)} permits from {self.city_name}")
        
        leads = []
        
        for permit in raw_data:
            try:
                # Extract required fields
                project_name = permit.get('project_name', '')
                if not project_name and 'description' in permit:
                    # Use the first part of the description as project name if not available
                    project_name = permit['description'].split('.')[0]
                
                description = permit.get('description', '')
                
                # Generate a lead ID
                lead_id = f"{self.city_name}_{permit.get('permit_number', permit.get('id', ''))}"
                
                # Extract address components
                address = permit.get('address', '')
                city = permit.get('city', self.city_name)
                state = permit.get('state', self.city_config.get('state', 'CA'))
                zip_code = permit.get('zip', '')
                
                # Format the full location
                location = f"{address}, {city}, {state}"
                if zip_code:
                    location += f" {zip_code}"
                
                # Extract dates
                application_date = permit.get('application_date', '')
                status_date = permit.get('status_date', '')
                
                # Use the application date as the publication date if available
                if application_date:
                    try:
                        publication_date = self.extract_date(application_date)
                        if publication_date:
                            publication_date = publication_date.isoformat()
                    except:
                        publication_date = datetime.datetime.now().isoformat()
                else:
                    publication_date = datetime.datetime.now().isoformat()
                
                # Create the standardized lead
                lead = {
                    'lead_id': lead_id,
                    'source': f"city_portal_{self.city_name}",
                    'project_name': project_name,
                    'description': description,
                    'location': location,
                    'address': address,
                    'city': city,
                    'state': state,
                    'zip': zip_code,
                    'permit_number': permit.get('permit_number', ''),
                    'permit_type': permit.get('permit_type', ''),
                    'status': permit.get('status', ''),
                    'value': permit.get('value', ''),
                    'applicant': permit.get('applicant', ''),
                    'contractor': permit.get('contractor', ''),
                    'application_date': application_date,
                    'status_date': status_date,
                    'publication_date': publication_date,
                    'retrieved_date': datetime.datetime.now().isoformat(),
                    'url': permit.get('url', ''),
                    'raw_data': json.dumps(permit)
                }
                
                leads.append(lead)
                
            except Exception as e:
                self.logger.error(f"Error parsing permit: {str(e)}")
                continue
        
        self.logger.info(f"Parsed {len(leads)} leads from {len(raw_data)} permits")
        return leads
    
    def clean_up(self) -> bool:
        """
        Close browser and clean up resources.
        
        Returns:
            bool: True if clean-up succeeded, False otherwise
        """
        self.logger.info(f"Cleaning up browser resources for {self.city_name}")
        
        try:
            # Close page if open
            if self.page:
                self.page.close()
                self.page = None
            
            # Close context if open
            if self.context:
                self.context.close()
                self.context = None
            
            # Close browser if open
            if self.browser:
                self.browser.close()
                self.browser = None
            
            # Stop Playwright
            if hasattr(self, 'playwright'):
                self.playwright.stop()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
            return False
    
    def navigate_to_search_page(self, portal_config: Dict[str, Any]) -> bool:
        """
        Access the search interface using portal-specific configuration.
        
        Args:
            portal_config: Configuration for the city portal
        
        Returns:
            bool: True if navigation succeeded, False otherwise
        """
        search_url = portal_config.get('search_url')
        if not search_url:
            search_url = self.base_url
        
        self.logger.info(f"Navigating to search page: {search_url}")
        
        try:
            # Navigate to the search page
            self.page.goto(search_url)
            
            # Check if we need to handle login
            if portal_config.get('requires_login', False):
                login_config = portal_config.get('login', {})
                if not self._handle_login(login_config):
                    self.logger.error("Failed to log in")
                    return False
            
            # Check if we need to navigate through intermediate pages
            intermediate_steps = portal_config.get('intermediate_steps', [])
            for step in intermediate_steps:
                if not self._handle_intermediate_step(step):
                    self.logger.error(f"Failed to handle intermediate step: {step.get('description', 'unnamed')}")
                    return False
            
            # Check if we've reached the search page
            search_page_ready = portal_config.get('search_page_ready_selector')
            if search_page_ready:
                try:
                    self.page.wait_for_selector(search_page_ready, timeout=30000)
                except PlaywrightTimeoutError:
                    self.logger.error(f"Search page ready selector not found: {search_page_ready}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error navigating to search page: {str(e)}")
            return False
    
    def input_search_criteria(self, criteria: Dict[str, Any]) -> bool:
        """
        Enter search parameters based on configuration.
        
        Args:
            criteria: Search criteria configuration
        
        Returns:
            bool: True if search criteria were entered successfully, False otherwise
        """
        self.logger.info("Inputting search criteria")
        
        try:
            # Wait a moment for the page to be fully loaded
            self.page.wait_for_load_state('networkidle')
            
            # Get form selectors from config
            form_config = self.city_config.get('form', {})
            
            # Fill in form fields
            for field_name, field_config in form_config.get('fields', {}).items():
                selector = field_config.get('selector')
                if not selector:
                    continue
                
                field_type = field_config.get('type', 'text')
                value = criteria.get(field_name, field_config.get('default_value', ''))
                
                if not value and field_config.get('required', False):
                    self.logger.warning(f"Required field {field_name} has no value")
                    continue
                
                # Handle different field types
                if field_type == 'text':
                    # Clear the field first if needed
                    if field_config.get('clear_first', True):
                        self.page.fill(selector, '')
                    
                    self.page.fill(selector, str(value))
                
                elif field_type == 'select':
                    self.page.select_option(selector, value=str(value))
                
                elif field_type == 'checkbox':
                    if value:
                        self.page.check(selector)
                    else:
                        self.page.uncheck(selector)
                
                elif field_type == 'radio':
                    self.page.check(f"{selector}[value='{value}']")
                
                elif field_type == 'date':
                    # Format the date if needed
                    if isinstance(value, datetime.datetime):
                        value = value.strftime(field_config.get('date_format', '%Y-%m-%d'))
                    
                    self.page.fill(selector, str(value))
                
                elif field_type == 'button':
                    self.page.click(selector)
                
                # Wait after each field if specified
                if field_config.get('wait_after', 0) > 0:
                    time.sleep(field_config.get('wait_after'))
            
            # Submit the form
            submit_selector = form_config.get('submit_selector')
            if submit_selector:
                self.logger.info(f"Submitting search form with selector: {submit_selector}")
                self.page.click(submit_selector)
                
                # Wait for results to load
                results_selector = self.city_config.get('results', {}).get('results_selector')
                if results_selector:
                    try:
                        self.page.wait_for_selector(results_selector, timeout=30000)
                    except PlaywrightTimeoutError:
                        self.logger.warning(f"Results selector not found after form submission: {results_selector}")
                        # Take a screenshot for debugging
                        screenshot_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                                       'logs', f"{self.city_name}_search_error.png")
                        self.page.screenshot(path=screenshot_path)
                        return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error inputting search criteria: {str(e)}")
            return False
    
    def extract_results_from_page(self) -> List[Dict[str, Any]]:
        """
        Parse the results from current page.
        
        Returns:
            List[Dict[str, Any]]: List of permit dictionaries from the current page
        """
        self.logger.info("Extracting results from current page")
        
        try:
            # Wait for the results to load
            results_config = self.city_config.get('results', {})
            results_selector = results_config.get('results_selector')
            
            if not results_selector:
                self.logger.error("No results selector configured")
                return []
            
            try:
                self.page.wait_for_selector(results_selector, timeout=10000)
            except PlaywrightTimeoutError:
                self.logger.warning(f"Results selector not found: {results_selector}")
                return []
            
            # Check if there are no results
            no_results_selector = results_config.get('no_results_selector')
            if no_results_selector and self.page.is_visible(no_results_selector):
                self.logger.info("No results found")
                return []
            
            # Extract results
            results = []
            item_selector = results_config.get('item_selector')
            
            if not item_selector:
                self.logger.error("No item selector configured")
                return []
            
            # Get all result items
            items = self.page.query_selector_all(item_selector)
            self.logger.info(f"Found {len(items)} results on current page")
            
            # Define field extraction function
            def extract_field(item, field_config):
                field_selector = field_config.get('selector')
                
                if not field_selector:
                    return None
                
                # Handle different selector types
                extraction_type = field_config.get('extraction_type', 'text')
                
                try:
                    if extraction_type == 'text':
                        # Get element using the selector relative to item
                        element = item.query_selector(field_selector)
                        if element:
                            return element.inner_text().strip()
                    
                    elif extraction_type == 'attribute':
                        attribute = field_config.get('attribute', 'value')
                        element = item.query_selector(field_selector)
                        if element:
                            return element.get_attribute(attribute)
                    
                    elif extraction_type == 'href':
                        element = item.query_selector(field_selector)
                        if element:
                            href = element.get_attribute('href')
                            if href:
                                # Convert to absolute URL if it's relative
                                if not href.startswith('http'):
                                    href = urljoin(self.base_url, href)
                                return href
                except Exception as e:
                    self.logger.debug(f"Error extracting field: {str(e)}")
                
                return None
            
            # Process each result item
            for i, item in enumerate(items):
                try:
                    result = {}
                    
                    # Extract fields based on configuration
                    field_configs = results_config.get('fields', {})
                    for field_name, field_config in field_configs.items():
                        value = extract_field(item, field_config)
                        if value is not None:
                            result[field_name] = value
                    
                    # Add result if it has data
                    if result:
                        results.append(result)
                except Exception as e:
                    self.logger.error(f"Error processing result item {i}: {str(e)}")
            
            self.logger.info(f"Extracted {len(results)} valid results from current page")
            return results
            
        except Exception as e:
            self.logger.error(f"Error extracting results from page: {str(e)}")
            return []
    
    def handle_pagination(self, pagination_config: Dict[str, Any], current_page: int) -> bool:
        """
        Navigate through multiple result pages.
        
        Args:
            pagination_config: Pagination configuration
            current_page: Current page number (0-based or 1-based depending on site)
        
        Returns:
            bool: True if navigation to next page succeeded, False if no more pages
        """
        self.logger.info(f"Handling pagination - moving to page {current_page + 1}")
        
        try:
            pagination_type = pagination_config.get('type', 'click')
            
            if pagination_type == 'click':
                # Check if there's a next page button
                next_selector = pagination_config.get('next_selector')
                
                if not next_selector:
                    self.logger.error("No next page selector configured")
                    return False
                
                # Check if the next button is disabled
                disabled_attr = pagination_config.get('disabled_attribute')
                disabled_class = pagination_config.get('disabled_class')
                
                next_element = self.page.query_selector(next_selector)
                
                if not next_element:
                    self.logger.info("Next button not found - no more pages")
                    return False
                
                # Check if next button is disabled
                if disabled_attr and next_element.get_attribute(disabled_attr) is not None:
                    self.logger.info(f"Next button is disabled ({disabled_attr})")
                    return False
                
                if disabled_class and disabled_class in (next_element.get_attribute('class') or ''):
                    self.logger.info(f"Next button has disabled class ({disabled_class})")
                    return False
                
                # Click the next button
                next_element.click()
                
                # Wait for results to load
                results_selector = self.city_config.get('results', {}).get('results_selector')
                if results_selector:
                    try:
                        self.page.wait_for_selector(results_selector, timeout=30000)
                    except PlaywrightTimeoutError:
                        self.logger.warning(f"Results selector not found after pagination: {results_selector}")
                        return False
                else:
                    # Default wait
                    self.page.wait_for_load_state('networkidle')
                
                return True
                
            elif pagination_type == 'page_number':
                # Get the selector for specific page numbers
                page_selector_template = pagination_config.get('page_selector_template')
                
                if not page_selector_template:
                    self.logger.error("No page selector template configured")
                    return False
                
                # Get the next page number
                next_page = current_page + 1
                
                # Format the selector for the specific page
                if '{page}' in page_selector_template:
                    page_selector = page_selector_template.format(page=next_page)
                else:
                    page_selector = page_selector_template + str(next_page)
                
                # Check if the page element exists
                page_element = self.page.query_selector(page_selector)
                
                if not page_element:
                    self.logger.info(f"Page {next_page} selector not found - no more pages")
                    return False
                
                # Click the page number
                page_element.click()
                
                # Wait for results to load
                results_selector = self.city_config.get('results', {}).get('results_selector')
                if results_selector:
                    try:
                        self.page.wait_for_selector(results_selector, timeout=30000)
                    except PlaywrightTimeoutError:
                        self.logger.warning(f"Results selector not found after pagination: {results_selector}")
                        return False
                else:
                    # Default wait
                    self.page.wait_for_load_state('networkidle')
                
                return True
                
            elif pagination_type == 'form':
                # Get the page input selector
                page_input_selector = pagination_config.get('page_input_selector')
                submit_selector = pagination_config.get('submit_selector')
                
                if not page_input_selector or not submit_selector:
                    self.logger.error("Missing page input or submit selector")
                    return False
                
                # Get the next page number
                next_page = current_page + 1
                
                # Fill in the page number
                self.page.fill(page_input_selector, str(next_page))
                
                # Submit the form
                self.page.click(submit_selector)
                
                # Wait for results to load
                results_selector = self.city_config.get('results', {}).get('results_selector')
                if results_selector:
                    try:
                        self.page.wait_for_selector(results_selector, timeout=30000)
                    except PlaywrightTimeoutError:
                        self.logger.warning(f"Results selector not found after pagination: {results_selector}")
                        return False
                else:
                    # Default wait
                    self.page.wait_for_load_state('networkidle')
                
                return True
            
            else:
                self.logger.error(f"Unsupported pagination type: {pagination_type}")
                return False
            
        except Exception as e:
            self.logger.error(f"Error handling pagination: {str(e)}")
            return False
    
    def extract_permit_details(self, permit_url: str, base_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get full details from a permit page.
        
        Args:
            permit_url: URL of the permit details page
            base_data: Base data already extracted from the results page
        
        Returns:
            Dict[str, Any]: Enhanced permit data with details
        """
        self.logger.info(f"Extracting permit details from: {permit_url}")
        
        if base_data is None:
            base_data = {}
        
        # Create a shallow copy of the base data
        detailed_data = dict(base_data)
        detailed_data['url'] = permit_url
        
        try:
            # Navigate to the permit details page
            self.page.goto(permit_url)
            
            # Wait for the page to load
            self.page.wait_for_load_state('networkidle')
            
            # Extract fields based on configuration
            details_config = self.city_config.get('details', {})
            field_configs = details_config.get('fields', {})
            
            for field_name, field_config in field_configs.items():
                selector = field_config.get('selector')
                
                if not selector:
                    continue
                
                try:
                    # Handle different selector types
                    extraction_type = field_config.get('extraction_type', 'text')
                    
                    if extraction_type == 'text':
                        element = self.page.query_selector(selector)
                        if element:
                            value = element.inner_text().strip()
                            detailed_data[field_name] = value
                    
                    elif extraction_type == 'attribute':
                        attribute = field_config.get('attribute', 'value')
                        element = self.page.query_selector(selector)
                        if element:
                            value = element.get_attribute(attribute)
                            if value:
                                detailed_data[field_name] = value
                    
                    elif extraction_type == 'table':
                        # Extract data from a table
                        label_selector = field_config.get('label_selector')
                        value_selector = field_config.get('value_selector')
                        
                        if label_selector and value_selector:
                            labels = self.page.query_selector_all(label_selector)
                            values = self.page.query_selector_all(value_selector)
                            
                            for i, label_elem in enumerate(labels):
                                if i < len(values):
                                    label = label_elem.inner_text().strip()
                                    value = values[i].inner_text().strip()
                                    
                                    # Clean up the label
                                    label = re.sub(r'[^a-zA-Z0-9 ]', '', label).strip()
                                    label = re.sub(r'\s+', '_', label).lower()
                                    
                                    if label and value:
                                        detailed_data[label] = value
                    
                except Exception as e:
                    self.logger.debug(f"Error extracting field {field_name}: {str(e)}")
            
            # Process any specific transformations
            for transform in details_config.get('transformations', []):
                try:
                    source_field = transform.get('source_field')
                    target_field = transform.get('target_field')
                    regex = transform.get('regex')
                    
                    if source_field and target_field and regex and source_field in detailed_data:
                        match = re.search(regex, detailed_data[source_field])
                        if match:
                            detailed_data[target_field] = match.group(1)
                except Exception as e:
                    self.logger.debug(f"Error applying transformation: {str(e)}")
            
            return detailed_data
            
        except Exception as e:
            self.logger.error(f"Error extracting permit details: {str(e)}")
            return detailed_data
    
    def _handle_login(self, login_config: Dict[str, Any]) -> bool:
        """
        Handle login process if required by the portal.
        
        Args:
            login_config: Login configuration
        
        Returns:
            bool: True if login succeeded, False otherwise
        """
        self.logger.info("Handling login process")
        
        try:
            username_selector = login_config.get('username_selector')
            password_selector = login_config.get('password_selector')
            submit_selector = login_config.get('submit_selector')
            
            if not username_selector or not password_selector or not submit_selector:
                self.logger.error("Missing login selectors")
                return False
            
            username = login_config.get('username', os.getenv('CITY_PORTAL_USERNAME'))
            password = login_config.get('password', os.getenv('CITY_PORTAL_PASSWORD'))
            
            if not username or not password:
                self.logger.error("Missing login credentials")
                return False
            
            # Enter username
            self.page.fill(username_selector, username)
            
            # Enter password
            self.page.fill(password_selector, password)
            
            # Submit the form
            self.page.click(submit_selector)
            
            # Wait for login to complete
            success_selector = login_config.get('success_selector')
            failure_selector = login_config.get('failure_selector')
            
            if success_selector:
                try:
                    self.page.wait_for_selector(success_selector, timeout=10000)
                    return True
                except PlaywrightTimeoutError:
                    pass
            
            if failure_selector and self.page.is_visible(failure_selector):
                self.logger.error("Login failed - error message visible")
                return False
            
            # Default to success if we couldn't determine otherwise
            return True
            
        except Exception as e:
            self.logger.error(f"Error during login: {str(e)}")
            return False
    
    def _handle_intermediate_step(self, step_config: Dict[str, Any]) -> bool:
        """
        Handle an intermediate navigation step.
        
        Args:
            step_config: Step configuration
        
        Returns:
            bool: True if step handled successfully, False otherwise
        """
        step_type = step_config.get('type', 'click')
        description = step_config.get('description', 'unnamed step')
        
        self.logger.info(f"Handling intermediate step: {description}")
        
        try:
            if step_type == 'click':
                selector = step_config.get('selector')
                
                if not selector:
                    self.logger.error(f"No selector provided for click step: {description}")
                    return False
                
                # Wait for the element to be available
                try:
                    self.page.wait_for_selector(selector, timeout=10000)
                except PlaywrightTimeoutError:
                    self.logger.error(f"Element not found for click step: {selector}")
                    return False
                
                # Click the element
                self.page.click(selector)
                
                # Wait after click if specified
                wait_time = step_config.get('wait_after', 0)
                if wait_time > 0:
                    time.sleep(wait_time)
                
                # Wait for a specific element if specified
                wait_for = step_config.get('wait_for')
                if wait_for:
                    try:
                        self.page.wait_for_selector(wait_for, timeout=10000)
                    except PlaywrightTimeoutError:
                        self.logger.warning(f"Wait for element not found: {wait_for}")
                
                return True
                
            elif step_type == 'form':
                # Fill form fields
                fields = step_config.get('fields', {})
                
                for field_name, field_config in fields.items():
                    selector = field_config.get('selector')
                    value = field_config.get('value', '')
                    
                    if not selector:
                        continue
                    
                    field_type = field_config.get('type', 'text')
                    
                    # Handle different field types
                    if field_type == 'text':
                        self.page.fill(selector, value)
                    elif field_type == 'select':
                        self.page.select_option(selector, value=value)
                    elif field_type == 'checkbox':
                        if value:
                            self.page.check(selector)
                        else:
                            self.page.uncheck(selector)
                
                # Submit the form
                submit_selector = step_config.get('submit_selector')
                if submit_selector:
                    self.page.click(submit_selector)
                
                # Wait after submission if specified
                wait_time = step_config.get('wait_after', 0)
                if wait_time > 0:
                    time.sleep(wait_time)
                
                # Wait for a specific element if specified
                wait_for = step_config.get('wait_for')
                if wait_for:
                    try:
                        self.page.wait_for_selector(wait_for, timeout=10000)
                    except PlaywrightTimeoutError:
                        self.logger.warning(f"Wait for element not found: {wait_for}")
                
                return True
                
            else:
                self.logger.error(f"Unsupported step type: {step_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error handling intermediate step: {str(e)}")
            return False


# Test the city portal scraper if run directly
if __name__ == "__main__":
    # Get the city name from args if provided
    import sys
    city_name = sys.argv[1] if len(sys.argv) > 1 else "los_angeles"
    
    # Initialize the scraper
    try:
        scraper = CityPortalScraper(city_name)
        
        # Execute the scraper
        if scraper.initialize():
            raw_data = scraper.scrape()
            if raw_data:
                leads = scraper.parse(raw_data)
                print(f"Successfully scraped {len(leads)} leads from {city_name}")
                
                # Print first 3 leads
                for i, lead in enumerate(leads[:3]):
                    print(f"\nLead {i+1}:")
                    print(f"  Project: {lead.get('project_name')}")
                    print(f"  Address: {lead.get('location')}")
                    print(f"  Type: {lead.get('permit_type')}")
                    print(f"  Value: {lead.get('value')}")
            else:
                print(f"No data scraped from {city_name}")
        
        # Clean up
        scraper.clean_up()
        
    except Exception as e:
        print(f"Error: {str(e)}")
        # Ensure browser is closed
        if 'scraper' in locals() and hasattr(scraper, 'clean_up'):
            scraper.clean_up()
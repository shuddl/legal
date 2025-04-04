#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Source Testing Script

Tests the availability and health of various data sources used by the Construction Lead Scraper.
Supports parallel testing, configurable retries, and detailed reporting.
"""

import os
import sys
import time
import json
import random
import logging
import argparse
import csv
import concurrent.futures
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from utils.source_registry import SourceRegistry, DataSource
from utils.rss_parser import RSSParser
from utils.logger import configure_logging, get_logger

# Configure logger
logger = get_logger('test_sources')

class SourceTester:
    """
    Tests data sources for availability and health.
    """
    
    def __init__(self, registry: SourceRegistry, args: argparse.Namespace):
        """
        Initialize the source tester.
        
        Args:
            registry: Source registry containing data sources
            args: Command line arguments
        """
        self.registry = registry
        self.args = args
        self.rss_parser = RSSParser(timeout=args.timeout)
        self.results = []
        self.playwright = None
        self.browser = None
        
        # Initialize Playwright for deep web checks if needed
        if args.deep_web_check:
            try:
                self.playwright = sync_playwright().start()
                self.browser = self.playwright.chromium.launch(headless=True)
                logger.info("Initialized Playwright browser for deep web checks")
            except Exception as e:
                logger.error(f"Failed to initialize Playwright: {str(e)}")
                self.args.deep_web_check = False
    
    def __del__(self):
        """
        Clean up resources on deletion.
        """
        if self.browser:
            try:
                self.browser.close()
            except:
                pass
        
        if self.playwright:
            try:
                self.playwright.stop()
            except:
                pass
    
    def test_all_sources(self) -> List[Dict[str, Any]]:
        """
        Test all active sources in parallel.
        
        Returns:
            List[Dict[str, Any]]: List of test results
        """
        logger.info("Starting source testing...")
        
        # Get active sources
        sources = self.registry.get_active_sources()
        if not sources:
            logger.warning("No active sources found in registry")
            return []
        
        logger.info(f"Found {len(sources)} active sources to test")
        
        # Test sources in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.args.workers) as executor:
            # Start a slightly staggered set of futures for each source
            futures = {}
            for source in sources:
                # Add a small random delay to stagger the start times
                time.sleep(random.uniform(0.1, 0.5))
                future = executor.submit(self.test_source, source)
                futures[future] = source.name
            
            # Collect the results as they complete
            results = []
            for future in concurrent.futures.as_completed(futures):
                source_name = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    # Log the result
                    if result['status'] == 'Success':
                        logger.info(f"Source {source_name} tested successfully")
                    else:
                        logger.warning(f"Source {source_name} test failed: {result.get('error', 'Unknown error')}")
                    
                except Exception as e:
                    logger.error(f"Error testing source {source_name}: {str(e)}")
                    # Add a result for the failed source
                    results.append({
                        'name': source_name,
                        'url': None,
                        'type': None,
                        'status': 'Error',
                        'duration_ms': 0,
                        'metric_name': None,
                        'metric_value': None,
                        'error': f"Unexpected error: {str(e)}",
                        'timestamp': datetime.now().isoformat()
                    })
        
        self.results = results
        return results
    
    def test_source(self, source: DataSource) -> Dict[str, Any]:
        """
        Test a single source.
        
        Args:
            source: DataSource to test
        
        Returns:
            Dict[str, Any]: Test result
        """
        logger.debug(f"Testing source: {source.name} ({source.type})")
        
        start_time = time.time()
        result = {
            'name': source.name,
            'url': source.url,
            'type': source.type,
            'status': 'Failed',
            'duration_ms': 0,
            'metric_name': None,
            'metric_value': None,
            'error': None,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Select the appropriate testing method based on source type
            if source.type == 'rss':
                success, metric_name, metric_value, error = self.test_rss_source(source)
            elif source.type in ['website', 'city_portal', 'permit_database']:
                # Use deep web check if enabled and source requires JS
                if self.args.deep_web_check and source.requires_js:
                    success, metric_name, metric_value, error = self.test_website_deep(source)
                else:
                    success, metric_name, metric_value, error = self.test_website_source(source)
            elif source.type == 'api':
                success, metric_name, metric_value, error = self.test_api_source(source)
            else:
                success, metric_name, metric_value, error = False, None, None, f"Unsupported source type: {source.type}"
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Update result
            result['status'] = 'Success' if success else 'Failed'
            result['duration_ms'] = duration_ms
            result['metric_name'] = metric_name
            result['metric_value'] = metric_value
            result['error'] = error
            
            # Update source in registry
            source.last_checked = datetime.now().isoformat()
            source.status = 'active' if success else 'failed'
            if metric_name and metric_value is not None:
                source.metrics[metric_name] = metric_value
            if error:
                source.metrics['last_error'] = error
            
            return result
            
        except Exception as e:
            # Handle unexpected errors
            duration_ms = int((time.time() - start_time) * 1000)
            result['status'] = 'Failed'
            result['duration_ms'] = duration_ms
            result['error'] = f"Unexpected error: {str(e)}"
            
            # Update source in registry
            source.last_checked = datetime.now().isoformat()
            source.status = 'failed'
            source.metrics['last_error'] = str(e)
            
            logger.error(f"Error testing source {source.name}: {str(e)}")
            return result
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, TimeoutError))
    )
    def test_rss_source(self, source: DataSource) -> Tuple[bool, str, Any, Optional[str]]:
        """
        Test an RSS feed source.
        
        Args:
            source: RSS DataSource to test
        
        Returns:
            Tuple containing:
            - bool: Success status
            - str: Metric name
            - Any: Metric value
            - Optional[str]: Error message if failed, None otherwise
        """
        logger.debug(f"Testing RSS source: {source.name}")
        
        success, feed, error = self.rss_parser.fetch_feed(source.url)
        
        if not success:
            return False, 'rss_status', 'failed', error
        
        # Get entry count
        entry_count = len(feed.get('entries', []))
        
        # Check if feed is empty
        if entry_count == 0:
            return False, 'entry_count', 0, "RSS feed has no entries"
        
        return True, 'entry_count', entry_count, None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def test_website_source(self, source: DataSource) -> Tuple[bool, str, Any, Optional[str]]:
        """
        Test a website source using basic HTTP request.
        
        Args:
            source: Website DataSource to test
        
        Returns:
            Tuple containing:
            - bool: Success status
            - str: Metric name
            - Any: Metric value
            - Optional[str]: Error message if failed, None otherwise
        """
        logger.debug(f"Testing website source: {source.name}")
        
        # Set up headers
        headers = {
            'User-Agent': (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        
        # Make request
        response = requests.get(source.url, headers=headers, timeout=self.args.timeout)
        
        # Check status code
        if response.status_code != 200:
            return False, 'http_status', response.status_code, f"HTTP error: {response.status_code}"
        
        # Get content length
        content_length = len(response.content)
        
        # Check if content is too small (likely an error page)
        if content_length < 1000:  # 1KB minimum
            return False, 'content_length', content_length, "Response content too small"
        
        return True, 'content_length', content_length, None
    
    def test_website_deep(self, source: DataSource) -> Tuple[bool, str, Any, Optional[str]]:
        """
        Test a website source using Playwright for JS-heavy sites.
        
        Args:
            source: Website DataSource to test
        
        Returns:
            Tuple containing:
            - bool: Success status
            - str: Metric name
            - Any: Metric value
            - Optional[str]: Error message if failed, None otherwise
        """
        logger.debug(f"Testing website source with deep check: {source.name}")
        
        if not self.browser:
            return False, 'browser_check', 'unavailable', "Playwright browser not available"
        
        try:
            # Create a new context and page
            context = self.browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                )
            )
            page = context.new_page()
            
            # Navigate to the URL
            page.goto(source.url, timeout=self.args.timeout * 1000)
            
            # Wait for the page to be fully loaded
            page.wait_for_load_state('networkidle', timeout=10000)
            
            # Get page content
            content = page.content()
            content_length = len(content)
            
            # Check if we can find the main content element
            main_content_found = False
            for selector in ['main', '#main', '.main', 'article', '.content', '#content']:
                if page.query_selector(selector):
                    main_content_found = True
                    break
            
            # Close the page and context
            page.close()
            context.close()
            
            if not main_content_found:
                return False, 'content_check', 'missing_main', "Could not find main content element"
            
            return True, 'content_length', content_length, None
            
        except PlaywrightTimeoutError:
            return False, 'browser_check', 'timeout', "Page load timed out"
        except Exception as e:
            return False, 'browser_check', 'error', f"Browser error: {str(e)}"
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(requests.RequestException)
    )
    def test_api_source(self, source: DataSource) -> Tuple[bool, str, Any, Optional[str]]:
        """
        Test an API source.
        
        Args:
            source: API DataSource to test
        
        Returns:
            Tuple containing:
            - bool: Success status
            - str: Metric name
            - Any: Metric value
            - Optional[str]: Error message if failed, None otherwise
        """
        logger.debug(f"Testing API source: {source.name}")
        
        # Set up headers
        headers = {
            'User-Agent': (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ),
            'Accept': 'application/json'
        }
        
        # Add authentication if required
        config = source.config
        if config.get('auth_required', False):
            auth_type = config.get('auth_type')
            
            if auth_type == 'api_key':
                header_name = config.get('header_name', 'X-API-Key')
                api_key = os.environ.get(config.get('api_key_env_var', ''))
                if api_key:
                    headers[header_name] = api_key
                else:
                    return False, 'api_auth', 'missing_key', f"API key environment variable not set: {config.get('api_key_env_var')}"
            
            elif auth_type == 'bearer':
                token = os.environ.get(config.get('auth_token_env_var', ''))
                if token:
                    headers['Authorization'] = f"Bearer {token}"
                else:
                    return False, 'api_auth', 'missing_token', f"Auth token environment variable not set: {config.get('auth_token_env_var')}"
        
        # Make request
        response = requests.get(source.url, headers=headers, timeout=self.args.timeout)
        
        # Check status code
        if response.status_code != 200:
            return False, 'http_status', response.status_code, f"HTTP error: {response.status_code}"
        
        # Try to parse JSON response
        try:
            data = response.json()
            
            # Check for success indicator in response
            if 'status' in data and data['status'] not in ['ok', 'success', 'UP']:
                return False, 'api_status', data['status'], f"API reported non-success status: {data['status']}"
            
            return True, 'api_status', 'ok', None
            
        except ValueError:
            return False, 'api_response', 'invalid_json', "API response is not valid JSON"
    
    def generate_report(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Generate a summary report of the test results.
        
        Returns:
            Tuple containing:
            - Dict: Summary statistics
            - List: Failed sources
            - List: Low value sources
        """
        if not self.results:
            return {
                'total': 0,
                'success': 0,
                'failure': 0,
                'success_percent': 0,
                'failure_percent': 0,
                'avg_duration_ms': 0
            }, [], []
        
        # Calculate statistics
        total = len(self.results)
        successful = sum(1 for r in self.results if r['status'] == 'Success')
        failed = total - successful
        
        success_percent = round((successful / total) * 100, 2) if total > 0 else 0
        failure_percent = round((failed / total) * 100, 2) if total > 0 else 0
        
        durations = [r['duration_ms'] for r in self.results if r['duration_ms'] > 0]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        # Identify failed sources
        failed_sources = [r for r in self.results if r['status'] != 'Success']
        
        # Identify low value sources
        low_value_sources = []
        for r in self.results:
            # Consider a source low value if it failed or is empty
            if r['status'] != 'Success':
                low_value_sources.append(r)
            elif r['type'] == 'rss' and r['metric_name'] == 'entry_count' and r['metric_value'] == 0:
                low_value_sources.append(r)
            elif r['type'] in ['website', 'city_portal'] and r['metric_name'] == 'content_length' and r['metric_value'] < 5000:
                low_value_sources.append(r)
        
        # Create summary
        summary = {
            'total': total,
            'success': successful,
            'failure': failed,
            'success_percent': success_percent,
            'failure_percent': failure_percent,
            'avg_duration_ms': round(avg_duration, 2)
        }
        
        return summary, failed_sources, low_value_sources
    
    def print_report(self) -> None:
        """
        Print a formatted report of the test results.
        """
        summary, failed_sources, low_value_sources = self.generate_report()
        
        print("\n=== SOURCE TESTING REPORT ===\n")
        print(f"Total sources tested: {summary['total']}")
        print(f"Successful: {summary['success']} ({summary['success_percent']}%)")
        print(f"Failed: {summary['failure']} ({summary['failure_percent']}%)")
        print(f"Average response time: {summary['avg_duration_ms']} ms")
        
        if failed_sources:
            print("\n=== FAILED SOURCES ===\n")
            for source in failed_sources:
                print(f"- {source['name']} ({source['type']}): {source['error']}")
        
        if low_value_sources:
            print("\n=== LOW VALUE SOURCES ===\n")
            for source in low_value_sources:
                if source['status'] != 'Success':
                    print(f"- {source['name']} ({source['type']}): Failed - {source['error']}")
                else:
                    print(f"- {source['name']} ({source['type']}): {source['metric_name']}={source['metric_value']}")
        
        print("\n=== END OF REPORT ===\n")
    
    def save_results_to_csv(self, output_file: str) -> None:
        """
        Save test results to a CSV file.
        
        Args:
            output_file: Path to the output CSV file
        """
        if not self.results:
            logger.warning("No results to save")
            return
        
        try:
            with open(output_file, 'w', newline='') as csvfile:
                fieldnames = [
                    'name', 'url', 'type', 'status', 'duration_ms', 
                    'metric_name', 'metric_value', 'error', 'timestamp'
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for result in self.results:
                    writer.writerow(result)
            
            logger.info(f"Results saved to {output_file}")
            
        except Exception as e:
            logger.error(f"Error saving results to {output_file}: {str(e)}")
    
    def save_results_to_json(self, output_file: str) -> None:
        """
        Save test results to a JSON file.
        
        Args:
            output_file: Path to the output JSON file
        """
        if not self.results:
            logger.warning("No results to save")
            return
        
        try:
            summary, failed_sources, low_value_sources = self.generate_report()
            
            data = {
                'summary': summary,
                'timestamp': datetime.now().isoformat(),
                'results': self.results
            }
            
            with open(output_file, 'w') as jsonfile:
                json.dump(data, jsonfile, indent=2)
            
            logger.info(f"Results saved to {output_file}")
            
        except Exception as e:
            logger.error(f"Error saving results to {output_file}: {str(e)}")


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description='Test data sources for availability and health.')
    
    parser.add_argument('--sources', type=str, default='config/sources.json',
                        help='Path to sources JSON file (default: config/sources.json)')
    
    parser.add_argument('--workers', type=int, default=10,
                        help='Number of worker threads for parallel testing (default: 10)')
    
    parser.add_argument('--retries', type=int, default=3,
                        help='Number of retry attempts for failed requests (default: 3)')
    
    parser.add_argument('--timeout', type=int, default=15,
                        help='Request timeout in seconds (default: 15)')
    
    parser.add_argument('--output', type=str,
                        help='Output file for results (CSV or JSON based on extension)')
    
    parser.add_argument('--deep-web-check', action='store_true',
                        help='Use Playwright for deep web checks on JS-heavy sites')
    
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose logging')
    
    return parser.parse_args()


def main():
    """
    Main entry point for the script.
    """
    # Parse arguments
    args = parse_arguments()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    configure_logging(level=log_level)
    
    # Initialize source registry
    registry = SourceRegistry(args.sources)
    
    # Create source tester
    tester = SourceTester(registry, args)
    
    # Test all sources
    tester.test_all_sources()
    
    # Print report
    tester.print_report()
    
    # Save results if output file specified
    if args.output:
        if args.output.lower().endswith('.csv'):
            tester.save_results_to_csv(args.output)
        elif args.output.lower().endswith('.json'):
            tester.save_results_to_json(args.output)
        else:
            logger.warning(f"Unsupported output format: {args.output}")
    
    # Save updated source registry
    if registry.save_sources(args.sources):
        logger.info(f"Updated source registry saved to {args.sources}")


if __name__ == '__main__':
    main()
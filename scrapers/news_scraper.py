#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
News Website Scraper - Implementation of the BaseScraper for construction news websites.
"""

import os
import time
import json
import datetime
import hashlib
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper
from utils.logger import get_logger, log_scraping_event

class NewsWebsiteScraper(BaseScraper):
    """
    News Website Scraper class for extracting content from construction industry news websites.
    Inherits from BaseScraper.
    """
    
    def __init__(self, source_name: str, base_url: str, config_path: Optional[str] = None, scrape_frequency: int = 24):
        """
        Initialize the News Website Scraper.
        
        Args:
            source_name: Name of the data source
            base_url: Base URL for the website
            config_path: Path to the configuration file (defaults to config/news_sources.json)
            scrape_frequency: How often to scrape this source (in hours)
        """
        super().__init__(source_name, base_url, scrape_frequency)
        self.logger = get_logger(f"scraper.news.{source_name}")
        
        # Load configuration
        if config_path is None:
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(root_dir, 'config', 'news_sources.json')
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading configuration from {config_path}: {str(e)}")
            raise ValueError(f"Could not load configuration: {str(e)}")
        
        # Get site-specific configuration
        site_config = None
        for site in self.config.get('sites', []):
            if site.get('name') == source_name:
                site_config = site
                break
        
        if not site_config:
            raise ValueError(f"Site '{source_name}' not found in configuration")
        
        self.site_config = site_config
        
        # Initialize session for requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.get_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        # Track processed articles to avoid duplicates
        self.processed_urls = set()
    
    def initialize(self) -> bool:
        """
        Set up any necessary configuration or authentication.
        
        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        self.logger.info(f"Initializing news scraper for {self.source_name}")
        
        try:
            # Check robots.txt if available
            robots_url = urljoin(self.base_url, '/robots.txt')
            try:
                response = self.session.get(robots_url, timeout=10)
                if response.status_code == 200:
                    self.logger.debug(f"Found robots.txt at {robots_url}")
                    # Check for sitemap
                    sitemap_match = re.search(r'Sitemap:\s*(.+)', response.text)
                    if sitemap_match:
                        self.site_config['sitemap_url'] = sitemap_match.group(1).strip()
                        self.logger.info(f"Found sitemap URL: {self.site_config['sitemap_url']}")
            except requests.RequestException:
                self.logger.debug(f"Could not fetch robots.txt from {robots_url}")
            
            # Test main site accessibility
            response = self.session.get(self.base_url, timeout=10)
            response.raise_for_status()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Initialization failed: {str(e)}")
            return False
    
    def scrape(self) -> Dict[str, Any]:
        """
        Execute the actual scraping process.
        
        Returns:
            Dict[str, Any]: Raw scraped data (article URLs and metadata)
        """
        self.logger.info(f"Scraping news website: {self.source_name}")
        
        results = {
            'article_list': [],
            'metadata': {
                'source': self.source_name,
                'base_url': self.base_url,
                'timestamp': datetime.datetime.now().isoformat()
            }
        }
        
        try:
            # Check if we should use sitemap first
            if 'sitemap_url' in self.site_config and self.site_config.get('use_sitemap', True):
                articles = self.get_articles_from_sitemap()
                if articles:
                    results['article_list'].extend(articles)
                    self.logger.info(f"Extracted {len(articles)} articles from sitemap")
            
            # If no articles from sitemap or sitemap not available, use category pages
            if not results['article_list']:
                articles = self.get_article_list(self.site_config)
                results['article_list'].extend(articles)
                self.logger.info(f"Extracted {len(articles)} articles from category pages")
            
            # If configured, extract content for each article
            if self.site_config.get('fetch_content', True):
                self.logger.info("Fetching full content for articles")
                
                # Limit articles to process
                max_articles = self.site_config.get('max_articles', 10)
                articles_to_process = results['article_list'][:max_articles]
                
                # Process articles
                for i, article in enumerate(articles_to_process):
                    self.logger.debug(f"Processing article {i+1}/{len(articles_to_process)}: {article['title']}")
                    
                    try:
                        # Respect crawl delay
                        time.sleep(self.site_config.get('crawl_delay', 2))
                        
                        # Extract full content
                        content = self.extract_article_content(article['url'], self.site_config)
                        
                        if content:
                            article.update(content)
                            
                            # Check relevance
                            if self.identify_construction_relevance(article['title'], article.get('content', '')):
                                article['relevant'] = True
                            else:
                                article['relevant'] = False
                    
                    except Exception as e:
                        self.logger.error(f"Error processing article {article['url']}: {str(e)}")
                        continue
            
            return results
            
        except Exception as e:
            self.logger.error(f"Scraping failed: {str(e)}")
            return results
    
    def parse(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert raw scraped data into a standardized lead format.
        
        Args:
            raw_data: Raw data from the scrape method
        
        Returns:
            List[Dict[str, Any]]: List of lead dictionaries in standardized format
        """
        self.logger.info(f"Parsing {len(raw_data.get('article_list', []))} articles from {self.source_name}")
        
        leads = []
        
        for article in raw_data.get('article_list', []):
            # Skip irrelevant articles if relevance was determined
            if 'relevant' in article and not article['relevant']:
                self.logger.debug(f"Skipping irrelevant article: {article['title']}")
                continue
            
            try:
                # Generate a unique ID
                lead_id = self.generate_lead_id(article)
                
                # Extract publication date
                publication_date = article.get('publication_date')
                if isinstance(publication_date, datetime.datetime):
                    publication_date = publication_date.isoformat()
                
                # Create the lead
                lead = {
                    'lead_id': lead_id,
                    'source': self.source_name,
                    'project_name': article.get('title', ''),
                    'description': article.get('content', article.get('summary', '')),
                    'url': article.get('url', ''),
                    'publication_date': publication_date,
                    'retrieved_date': datetime.datetime.now().isoformat(),
                    'author': article.get('author', ''),
                    'categories': article.get('categories', []),
                    'location': self.extract_location_from_article(article),
                    'raw_content': json.dumps(article)
                }
                
                leads.append(lead)
                
            except Exception as e:
                self.logger.error(f"Error parsing article: {str(e)}")
                continue
        
        self.logger.info(f"Extracted {len(leads)} leads from {self.source_name}")
        return leads
    
    def clean_up(self) -> bool:
        """
        Handle any necessary clean-up operations.
        
        Returns:
            bool: True if clean-up succeeded, False otherwise
        """
        self.logger.info(f"Cleaning up resources for {self.source_name}")
        
        try:
            # Close the session
            self.session.close()
            
            # Clear processed URLs
            self.processed_urls.clear()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Clean-up failed: {str(e)}")
            return False
    
    def get_article_list(self, config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract list of articles from main or category pages.
        
        Args:
            config: Site-specific configuration
        
        Returns:
            List[Dict[str, Any]]: List of article dictionaries with basic info
        """
        self.logger.info("Extracting article list from category pages")
        
        articles = []
        category_urls = config.get('category_urls', [])
        
        if not category_urls:
            category_urls = [self.base_url]
        
        for url in category_urls:
            try:
                self.logger.debug(f"Processing category URL: {url}")
                
                # Respect crawl delay
                time.sleep(config.get('crawl_delay', 2))
                
                # Fetch the page
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                
                # Parse the HTML
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Extract articles based on configuration
                article_list_selector = config.get('article_list_selector')
                if not article_list_selector:
                    self.logger.warning(f"No article list selector configured for {url}")
                    continue
                
                # Find all article elements
                article_elements = soup.select(article_list_selector)
                self.logger.debug(f"Found {len(article_elements)} article elements on {url}")
                
                for element in article_elements:
                    try:
                        # Extract article URL
                        url_selector = config.get('article_url_selector', 'a')
                        url_element = element.select_one(url_selector)
                        
                        if not url_element:
                            continue
                        
                        article_url = url_element.get('href')
                        if not article_url:
                            continue
                        
                        # Convert to absolute URL if it's relative
                        if not article_url.startswith('http'):
                            article_url = urljoin(self.base_url, article_url)
                        
                        # Skip if already processed
                        if article_url in self.processed_urls:
                            continue
                        
                        self.processed_urls.add(article_url)
                        
                        # Extract title
                        title_selector = config.get('article_title_selector')
                        title = ''
                        if title_selector:
                            title_element = element.select_one(title_selector)
                            if title_element:
                                title = title_element.get_text(strip=True)
                        
                        if not title and url_element.get_text(strip=True):
                            title = url_element.get_text(strip=True)
                        
                        # Extract summary if available
                        summary_selector = config.get('article_summary_selector')
                        summary = ''
                        if summary_selector:
                            summary_element = element.select_one(summary_selector)
                            if summary_element:
                                summary = summary_element.get_text(strip=True)
                        
                        # Extract date if available
                        date_selector = config.get('article_date_selector')
                        publication_date = None
                        if date_selector:
                            date_element = element.select_one(date_selector)
                            if date_element:
                                date_text = date_element.get_text(strip=True)
                                publication_date = self.extract_date(date_text)
                        
                        # Create article entry
                        article = {
                            'url': article_url,
                            'title': title,
                            'summary': summary,
                            'publication_date': publication_date.isoformat() if publication_date else None
                        }
                        
                        articles.append(article)
                        
                    except Exception as e:
                        self.logger.debug(f"Error extracting article from element: {str(e)}")
                        continue
                
            except Exception as e:
                self.logger.error(f"Error processing category URL {url}: {str(e)}")
                continue
        
        self.logger.info(f"Extracted {len(articles)} articles from category pages")
        return articles
    
    def get_articles_from_sitemap(self) -> List[Dict[str, Any]]:
        """
        Extract articles from sitemap XML if available.
        
        Returns:
            List[Dict[str, Any]]: List of article dictionaries with basic info
        """
        sitemap_url = self.site_config.get('sitemap_url')
        if not sitemap_url:
            return []
        
        self.logger.info(f"Extracting articles from sitemap: {sitemap_url}")
        
        articles = []
        
        try:
            # Fetch the sitemap
            response = self.session.get(sitemap_url, timeout=15)
            response.raise_for_status()
            
            # Parse XML
            soup = BeautifulSoup(response.content, 'xml')
            
            # Find all URLs in the sitemap
            url_elements = soup.find_all('url')
            
            # Process each URL
            for url_elem in url_elements:
                try:
                    # Get the location (URL)
                    loc_elem = url_elem.find('loc')
                    if not loc_elem:
                        continue
                    
                    url = loc_elem.text.strip()
                    
                    # Check if URL matches article pattern
                    article_pattern = self.site_config.get('article_url_pattern')
                    if article_pattern and not re.search(article_pattern, url):
                        continue
                    
                    # Skip if already processed
                    if url in self.processed_urls:
                        continue
                    
                    self.processed_urls.add(url)
                    
                    # Get the last modified date if available
                    lastmod_elem = url_elem.find('lastmod')
                    publication_date = None
                    if lastmod_elem:
                        lastmod_text = lastmod_elem.text.strip()
                        publication_date = self.extract_date(lastmod_text)
                    
                    # Create article entry
                    article = {
                        'url': url,
                        'title': '',  # Title will be extracted from the article page
                        'publication_date': publication_date.isoformat() if publication_date else None
                    }
                    
                    articles.append(article)
                    
                except Exception as e:
                    self.logger.debug(f"Error processing sitemap URL: {str(e)}")
                    continue
            
            return articles
            
        except Exception as e:
            self.logger.error(f"Error fetching sitemap {sitemap_url}: {str(e)}")
            return []
    
    def extract_article_content(self, url: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse full article content using site-specific selectors.
        
        Args:
            url: URL of the article
            config: Site-specific configuration
        
        Returns:
            Dict[str, Any]: Article content and metadata
        """
        self.logger.debug(f"Extracting content from article: {url}")
        
        try:
            # Fetch the article page
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract content using selector
            content_selector = config.get('article_content_selector')
            content = ''
            if content_selector:
                content_element = soup.select_one(content_selector)
                if content_element:
                    # Remove unwanted elements
                    for sel in config.get('content_remove_selectors', []):
                        for elem in content_element.select(sel):
                            elem.decompose()
                    
                    # Get the content
                    content = content_element.get_text(separator=' ', strip=True)
            
            # Extract title if not already available
            title_selector = config.get('page_title_selector', 'title')
            title = ''
            title_element = soup.select_one(title_selector)
            if title_element:
                title = title_element.get_text(strip=True)
            
            # Extract publication date
            date_selector = config.get('page_date_selector')
            publication_date = None
            if date_selector:
                date_element = soup.select_one(date_selector)
                if date_element:
                    date_text = date_element.get_text(strip=True)
                    publication_date = self.extract_date(date_text)
            
            # Extract author
            author_selector = config.get('page_author_selector')
            author = ''
            if author_selector:
                author_element = soup.select_one(author_selector)
                if author_element:
                    author = author_element.get_text(strip=True)
            
            # Extract categories
            categories = []
            category_selector = config.get('page_category_selector')
            if category_selector:
                category_elements = soup.select(category_selector)
                categories = [elem.get_text(strip=True) for elem in category_elements if elem.get_text(strip=True)]
            
            # Return the extracted data
            return {
                'title': title,
                'content': content,
                'publication_date': publication_date.isoformat() if publication_date else None,
                'author': author,
                'categories': categories
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting content from {url}: {str(e)}")
            return {}
    
    def extract_publication_date(self, article_soup: BeautifulSoup) -> Optional[datetime.datetime]:
        """
        Parse publication dates in various formats.
        
        Args:
            article_soup: BeautifulSoup object for the article
        
        Returns:
            Optional[datetime.datetime]: Parsed date if found, None otherwise
        """
        date_selectors = self.site_config.get('date_selectors', [
            'meta[property="article:published_time"]',
            'meta[name="publication_date"]',
            'time',
            '.date',
            '.published'
        ])
        
        for selector in date_selectors:
            try:
                element = article_soup.select_one(selector)
                if not element:
                    continue
                
                # Check for content attribute (meta tags)
                if element.get('content'):
                    date_text = element.get('content')
                # Check for datetime attribute (time tags)
                elif element.get('datetime'):
                    date_text = element.get('datetime')
                # Use text content
                else:
                    date_text = element.get_text(strip=True)
                
                # Try to parse the date
                date = self.extract_date(date_text)
                if date:
                    return date
                
            except Exception:
                continue
        
        return None
    
    def identify_construction_relevance(self, title: str, content: str) -> bool:
        """
        Basic keyword matching to verify relevance to construction.
        
        Args:
            title: Article title
            content: Article content
        
        Returns:
            bool: True if the article is relevant to construction, False otherwise
        """
        if not title and not content:
            return False
        
        # Combine title and content for searching
        text = f"{title} {content}".lower()
        
        # Check for construction-related keywords
        construction_keywords = self.site_config.get('construction_keywords', [
            'construction', 'build', 'project', 'development', 'contractor',
            'building', 'infrastructure', 'architect', 'engineering', 'renovation',
            'commercial', 'residential', 'industrial', 'concrete', 'steel',
            'construction site', 'property development', 'real estate development'
        ])
        
        # Check for category-specific keywords
        category_keywords = []
        for category in self.site_config.get('target_categories', []):
            if category == 'healthcare':
                category_keywords.extend([
                    'hospital', 'medical center', 'clinic', 'healthcare facility',
                    'medical office', 'ambulatory', 'patient tower', 'treatment center'
                ])
            elif category == 'education':
                category_keywords.extend([
                    'school', 'university', 'college', 'campus', 'classroom',
                    'educational facility', 'dormitory', 'student housing', 'academic'
                ])
            elif category == 'energy':
                category_keywords.extend([
                    'power plant', 'utility', 'renewable energy', 'solar', 'wind farm',
                    'energy facility', 'substation', 'transmission', 'grid', 'generation'
                ])
        
        # Combine all keywords
        all_keywords = construction_keywords + category_keywords
        
        # Check if any keywords are present
        for keyword in all_keywords:
            if keyword.lower() in text:
                return True
        
        return False
    
    def extract_location_from_article(self, article: Dict[str, Any]) -> str:
        """
        Extract location information from article text.
        
        Args:
            article: Article dictionary
        
        Returns:
            str: Extracted location or empty string if none found
        """
        # Combine title and content for searching
        text = f"{article.get('title', '')} {article.get('content', '')}"
        
        # Check for location in categories
        for category in article.get('categories', []):
            if category.lower() in ['california', 'los angeles', 'san diego', 'orange county', 'socal', 'southern california']:
                return category
        
        # Check for common California locations
        ca_locations = [
            'Los Angeles', 'San Diego', 'Orange County', 'Irvine', 'Anaheim',
            'Long Beach', 'San Francisco', 'Sacramento', 'San Jose',
            'California', 'Southern California', 'Northern California'
        ]
        
        for location in ca_locations:
            pattern = r'\b' + re.escape(location) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                return location
        
        return ""
    
    def generate_lead_id(self, article: Dict[str, Any]) -> str:
        """
        Generate a unique identifier for a lead based on article URL.
        
        Args:
            article: Article dictionary
        
        Returns:
            str: Unique lead ID
        """
        url = article.get('url', '')
        if not url:
            # Fallback to title and publication date if URL not available
            title = article.get('title', '')
            date = article.get('publication_date', '')
            source = self.source_name
            input_string = f"{source}:{title}:{date}"
        else:
            # Use URL as basis for ID
            input_string = url
        
        # Create hash
        hash_obj = hashlib.sha256(input_string.encode('utf-8'))
        return f"{self.source_name}_{hash_obj.hexdigest()[:12]}"


# Test the news website scraper if run directly
if __name__ == "__main__":
    # Test site and configuration
    site_name = "construction_dive"
    base_url = "https://www.constructiondive.com"
    
    # Create test configuration file if it doesn't exist
    test_config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config')
    os.makedirs(test_config_dir, exist_ok=True)
    
    test_config_path = os.path.join(test_config_dir, 'news_sources.json')
    
    if not os.path.exists(test_config_path):
        test_config = {
            "sites": [
                {
                    "name": "construction_dive",
                    "base_url": "https://www.constructiondive.com",
                    "category_urls": ["https://www.constructiondive.com/topic/commercial-building/"],
                    "article_list_selector": ".feed__item",
                    "article_url_selector": "h3.feed__title a",
                    "article_title_selector": "h3.feed__title",
                    "article_summary_selector": "p.feed__description",
                    "article_date_selector": ".feed__pub-date",
                    "article_content_selector": ".article-body__content-block",
                    "page_title_selector": "h1.article-head__headline",
                    "page_date_selector": ".article-head__publish-date",
                    "page_author_selector": ".article-head__author-name",
                    "content_remove_selectors": [".ad", ".subscription-prompt", ".related-articles"],
                    "crawl_delay": 3,
                    "max_articles": 5,
                    "construction_keywords": ["construction", "building", "project", "development"],
                    "target_categories": ["healthcare", "education", "energy"]
                }
            ]
        }
        with open(test_config_path, 'w', encoding='utf-8') as f:
            json.dump(test_config, f, indent=2)
    
    # Initialize the scraper
    try:
        scraper = NewsWebsiteScraper(site_name, base_url, test_config_path)
        
        # Execute the scraper
        if scraper.initialize():
            raw_data = scraper.scrape()
            if raw_data.get('article_list'):
                leads = scraper.parse(raw_data)
                print(f"Successfully scraped {len(leads)} leads from {site_name}")
                
                # Print first 3 leads
                for i, lead in enumerate(leads[:3]):
                    print(f"\nLead {i+1}:")
                    print(f"  Title: {lead.get('project_name')}")
                    print(f"  URL: {lead.get('url')}")
                    print(f"  Date: {lead.get('publication_date')}")
                    print(f"  Location: {lead.get('location')}")
                    
                    # Show a preview of the description
                    description = lead.get('description', '')
                    if len(description) > 100:
                        description = description[:100] + "..."
                    print(f"  Description: {description}")
            else:
                print(f"No articles scraped from {site_name}")
        
        # Clean up
        scraper.clean_up()
        
    except Exception as e:
        print(f"Error: {str(e)}")
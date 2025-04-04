"""
Lead Enrichment Module - Enhances lead data with additional information.

This module provides functionality to enhance construction lead data with additional
company information, contact details, project insights, and other relevant data.
It uses various sources including web scraping, API integrations, and data analysis
to improve the quality and actionability of leads.
"""

import os
import re
import json
import time
import logging
import threading
import hashlib
from typing import Dict, List, Any, Optional, Union, Tuple, Set
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
import concurrent.futures
from functools import lru_cache

# Third-party imports
import requests
from bs4 import BeautifulSoup

# Local imports
from ..config import AppConfig
from ..utils.timeout import timeout_handler
from ..utils.storage import LocalStorage
from ..nlp.nlp_processor import NLPProcessor

# Set up logging
logger = logging.getLogger(__name__)

class EnrichmentError(Exception):
    """Base exception for enrichment errors."""
    pass

class EnrichmentSourceError(EnrichmentError):
    """Exception for errors with enrichment data sources."""
    pass

class RateLimitError(EnrichmentError):
    """Exception for rate limit errors."""
    pass

class LeadEnricher:
    """
    Enhances lead data with additional company and project information.
    
    This class provides methods to enrich construction lead data with additional
    information such as company details, contact information, project insights,
    and other relevant data to improve lead quality and actionability.
    """
    
    def __init__(self, config: Optional[AppConfig] = None):
        """
        Initialize the lead enricher.
        
        Args:
            config: Application configuration object. If not provided, a default one will be created.
        """
        self.config = config or AppConfig()
        self.nlp_processor = NLPProcessor()
        self.storage = LocalStorage()
        self.session = requests.Session()
        
        # Configure requests session
        self._configure_session()
        
        # Load API credentials
        self._load_api_credentials()
        
        # Cache settings
        self.cache_enabled = self.config.get('enable_cache', True)
        self.cache_ttl = self.config.get('cache_ttl', 86400 * 7)  # 7 days default
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_lock = threading.RLock()
        
        # Set up concurrent processing
        self.max_workers = self.config.get('max_workers', 4)
        
        logger.info("Lead enricher initialized")
    
    def _configure_session(self) -> None:
        """Configure the requests session with appropriate headers and settings."""
        # Set default headers for web requests
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        
        # Configure proxies if enabled
        if self.config.get('use_proxies', False) and self.config.get('proxy_url'):
            self.session.proxies = {
                "http": self.config.get('proxy_url'),
                "https": self.config.get('proxy_url')
            }
        
        # Configure timeouts
        self.timeout = self.config.get('timeout', 30)  # Default timeout in seconds
    
    def _load_api_credentials(self) -> None:
        """Load API credentials from configuration files."""
        self.credentials = {}
        
        # Path to credentials file
        credentials_path = os.path.join(
            os.path.dirname(self.config.get('sources_path', '')), 
            "enrichment_api_credentials.json"
        )
        
        try:
            if os.path.exists(credentials_path):
                with open(credentials_path, 'r') as f:
                    self.credentials = json.load(f)
                logger.info(f"Loaded credentials for {len(self.credentials)} enrichment API providers")
            else:
                logger.warning(f"Enrichment API credentials file not found at {credentials_path}")
        except Exception as e:
            logger.error(f"Error loading enrichment API credentials: {e}")
    
    def _get_auth_headers(self, provider: str) -> Dict[str, str]:
        """
        Get authentication headers for the specified provider.
        
        Args:
            provider: API provider name
        
        Returns:
            Dictionary of authentication headers
        
        Raises:
            EnrichmentSourceError: If credentials are not found or invalid
        """
        if provider not in self.credentials:
            raise EnrichmentSourceError(f"No credentials found for provider: {provider}")
        
        creds = self.credentials[provider]
        
        # Different authentication methods based on provider
        if provider == "company_data":
            if "api_key" not in creds:
                raise EnrichmentSourceError(f"API key missing for provider: {provider}")
            return {"Authorization": f"Bearer {creds['api_key']}"}
            
        elif provider == "contact_finder":
            if "api_key" not in creds:
                raise EnrichmentSourceError(f"API key missing for provider: {provider}")
            return {"X-API-Key": creds["api_key"]}
            
        elif provider == "business_directory":
            if "username" not in creds or "password" not in creds:
                raise EnrichmentSourceError(f"Username or password missing for provider: {provider}")
            
            # Basic auth
            auth_string = f"{creds['username']}:{creds['password']}"
            import base64
            encoded = base64.b64encode(auth_string.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
            
        elif provider == "project_database":
            if "api_key" not in creds:
                raise EnrichmentSourceError(f"API key missing for provider: {provider}")
            return {"apikey": creds["api_key"]}
            
        else:
            return {}
    
    def _get_cache_key(self, function_name: str, *args, **kwargs) -> str:
        """
        Generate a cache key for the given function call.
        
        Args:
            function_name: Name of the function being cached
            *args, **kwargs: Function arguments
        
        Returns:
            Cache key string
        """
        # Create a string representation of the arguments
        args_str = str(args) + str(sorted(kwargs.items()))
        
        # Create a hash of the function name and arguments
        key = f"{function_name}:{hashlib.md5(args_str.encode('utf-8')).hexdigest()}"
        return key
    
    def _get_cached_result(self, cache_key: str) -> Optional[Any]:
        """
        Get a cached result if it exists and is not expired.
        
        Args:
            cache_key: The cache key to look up
        
        Returns:
            Cached result or None if not found or expired
        """
        if not self.cache_enabled:
            return None
        
        with self.cache_lock:
            if cache_key in self.cache:
                entry = self.cache[cache_key]
                # Check if entry is expired
                if time.time() - entry['timestamp'] < self.cache_ttl:
                    logger.debug(f"Cache hit: {cache_key}")
                    return entry['data']
                else:
                    # Remove expired entry
                    del self.cache[cache_key]
                    
        return None
    
    def _store_cache_result(self, cache_key: str, result: Any) -> None:
        """
        Store a result in the cache.
        
        Args:
            cache_key: The cache key to store under
            result: The data to cache
        """
        if not self.cache_enabled:
            return
        
        with self.cache_lock:
            self.cache[cache_key] = {
                'data': result,
                'timestamp': time.time()
            }
            
            # Trim cache if it gets too large
            max_cache_size = self.config.get('max_cache_size', 1000)
            if len(self.cache) > max_cache_size:
                # Remove oldest entries
                oldest_keys = sorted(
                    self.cache.keys(), 
                    key=lambda k: self.cache[k]['timestamp']
                )[:len(self.cache) - max_cache_size]
                
                for key in oldest_keys:
                    del self.cache[key]
    
    def enrich_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main method to enrich a lead with additional information.
        
        Args:
            lead: Lead data dictionary
        
        Returns:
            Enriched lead data dictionary
        """
        logger.info(f"Enriching lead: {lead.get('title', 'Untitled')[:50]}...")
        
        # Create a copy of the lead to avoid modifying the original
        enriched_lead = lead.copy()
        
        # Initialize enrichment metadata
        if 'enrichment' not in enriched_lead:
            enriched_lead['enrichment'] = {
                'timestamp': datetime.now().isoformat(),
                'sources_used': [],
                'confidence_scores': {}
            }
        
        try:
            # Look up company information if organization is available
            organization_name = lead.get('organization')
            if organization_name:
                company_data = self.lookup_company_data(organization_name)
                if company_data:
                    enriched_lead['enrichment']['sources_used'].append('company_data')
                    enriched_lead['company'] = company_data
            
            # Find company website if not already available
            if not lead.get('company_url') and organization_name:
                website = self.find_company_website(organization_name, lead.get('location'))
                if website:
                    enriched_lead['company_url'] = website
                    enriched_lead['enrichment']['sources_used'].append('website_finder')
            
            # Extract contact details from company website or other sources
            if enriched_lead.get('company_url'):
                contacts = self.extract_contact_details(enriched_lead['company_url'], organization_name)
                if contacts:
                    enriched_lead['contacts'] = contacts
                    enriched_lead['enrichment']['sources_used'].append('contact_extraction')
            
            # Estimate company size if not available
            if not enriched_lead.get('company_size') and organization_name:
                company_size = self.estimate_company_size(organization_name, enriched_lead.get('company', {}))
                if company_size:
                    enriched_lead['company_size'] = company_size
                    enriched_lead['enrichment']['sources_used'].append('company_size_estimation')
            
            # Determine project stage if not already available or enhance existing info
            if not lead.get('project_stage') or lead.get('project_stage') == 'unknown':
                project_stage = self.determine_project_stage(lead)
                if project_stage:
                    enriched_lead['project_stage'] = project_stage
                    enriched_lead['enrichment']['sources_used'].append('project_stage_analysis')
            
            # Find related projects
            related_projects = self.find_related_projects(lead)
            if related_projects:
                enriched_lead['related_projects'] = related_projects
                enriched_lead['enrichment']['sources_used'].append('related_projects')
            
            # Calculate lead score
            lead_score = self.calculate_lead_score(enriched_lead)
            enriched_lead['lead_score'] = lead_score
            enriched_lead['enrichment']['sources_used'].append('lead_scoring')
            
            # Mark enrichment as successful
            enriched_lead['enrichment']['status'] = 'success'
            
        except Exception as e:
            logger.error(f"Error enriching lead {lead.get('id', 'unknown')}: {str(e)}")
            
            # Mark enrichment as failed but return partially enriched data
            enriched_lead['enrichment']['status'] = 'partial'
            enriched_lead['enrichment']['error'] = str(e)
        
        return enriched_lead
    
    def enrich_leads(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Enrich multiple leads in parallel.
        
        Args:
            leads: List of lead data dictionaries
        
        Returns:
            List of enriched lead data dictionaries
        """
        logger.info(f"Enriching {len(leads)} leads")
        
        enriched_leads = []
        
        # Process leads in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all enrichment tasks
            future_to_lead = {executor.submit(self.enrich_lead, lead): lead for lead in leads}
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_lead):
                try:
                    enriched_lead = future.result()
                    enriched_leads.append(enriched_lead)
                except Exception as e:
                    lead = future_to_lead[future]
                    logger.error(f"Error enriching lead {lead.get('id', 'unknown')}: {str(e)}")
                    
                    # Add the original lead with error information
                    error_lead = lead.copy()
                    if 'enrichment' not in error_lead:
                        error_lead['enrichment'] = {}
                    error_lead['enrichment']['status'] = 'failed'
                    error_lead['enrichment']['error'] = str(e)
                    error_lead['enrichment']['timestamp'] = datetime.now().isoformat()
                    
                    enriched_leads.append(error_lead)
        
        return enriched_leads
    
    @timeout_handler(timeout_sec=30)
    def lookup_company_data(self, company_name: str, location: Optional[str] = None) -> Dict[str, Any]:
        """
        Look up company information from business data providers.
        
        Args:
            company_name: Name of the company to look up
            location: Optional location to narrow down search
        
        Returns:
            Dictionary of company information
        """
        # Check cache first
        cache_key = self._get_cache_key('lookup_company_data', company_name, location)
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            return cached_result
        
        logger.debug(f"Looking up company data for: {company_name}")
        
        # Try different data providers in sequence
        providers = ["company_data", "business_directory"]
        
        for provider in providers:
            try:
                if provider not in self.credentials:
                    logger.debug(f"Skipping provider {provider} - no credentials")
                    continue
                
                result = self._lookup_company_from_provider(provider, company_name, location)
                if result:
                    # Cache and return the result
                    self._store_cache_result(cache_key, result)
                    return result
                    
            except RateLimitError as e:
                logger.warning(f"Rate limit reached for provider {provider}: {e}")
                continue
            except EnrichmentSourceError as e:
                logger.warning(f"Error with provider {provider}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error looking up company data from {provider}: {e}")
                continue
        
        # If all providers failed, return a minimal result with the information we have
        minimal_result = {
            "name": company_name,
            "location": location,
            "source": "minimal",
            "confidence": 0.3
        }
        
        self._store_cache_result(cache_key, minimal_result)
        return minimal_result
    
    def _lookup_company_from_provider(self, 
                                      provider: str, 
                                      company_name: str,
                                      location: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Look up company information from a specific data provider.
        
        Args:
            provider: Provider identifier
            company_name: Company name to look up
            location: Optional location to narrow search
        
        Returns:
            Company data dictionary or None if not found
        """
        if provider not in self.credentials:
            raise EnrichmentSourceError(f"No credentials for provider: {provider}")
        
        base_url = self.credentials[provider].get("base_url")
        if not base_url:
            raise EnrichmentSourceError(f"Base URL not configured for provider: {provider}")
        
        # Prepare request
        headers = self._get_auth_headers(provider)
        
        # Provider-specific endpoints and parameters
        if provider == "company_data":
            endpoint = "api/v1/companies/search"
            url = urljoin(base_url, endpoint)
            
            params = {"name": company_name, "limit": 1}
            if location:
                params["location"] = location
                
            response = self.session.get(url, headers=headers, params=params, timeout=self.timeout)
            
        elif provider == "business_directory":
            endpoint = "api/businesses"
            url = urljoin(base_url, endpoint)
            
            params = {"query": company_name, "max_results": 1}
            if location:
                params["location"] = location
                
            response = self.session.get(url, headers=headers, params=params, timeout=self.timeout)
            
        else:
            raise EnrichmentSourceError(f"Unsupported provider: {provider}")
        
        # Check for rate limiting
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            raise RateLimitError(f"Rate limit exceeded. Retry after {retry_after} seconds.")
        
        # Check for other errors
        if response.status_code != 200:
            raise EnrichmentSourceError(
                f"API error ({response.status_code}): {response.text}"
            )
        
        # Parse and format the response
        try:
            data = response.json()
            
            # Format according to provider-specific response structure
            if provider == "company_data":
                companies = data.get("companies", [])
                if not companies:
                    return None
                
                company = companies[0]
                return {
                    "name": company.get("name"),
                    "description": company.get("description"),
                    "website": company.get("website"),
                    "industry": company.get("industry"),
                    "founded_year": company.get("founded_year"),
                    "size": company.get("employee_count"),
                    "revenue": company.get("revenue"),
                    "location": {
                        "address": company.get("address"),
                        "city": company.get("city"),
                        "state": company.get("state"),
                        "postal_code": company.get("postal_code"),
                        "country": company.get("country")
                    },
                    "social_media": company.get("social_media", {}),
                    "source": "company_data",
                    "confidence": 0.9
                }
                
            elif provider == "business_directory":
                businesses = data.get("results", [])
                if not businesses:
                    return None
                
                business = businesses[0]
                return {
                    "name": business.get("business_name"),
                    "description": business.get("description"),
                    "website": business.get("website_url"),
                    "industry": business.get("category"),
                    "founded_year": business.get("established"),
                    "size": business.get("employee_range"),
                    "revenue": business.get("annual_revenue"),
                    "location": {
                        "address": business.get("address", {}).get("street"),
                        "city": business.get("address", {}).get("city"),
                        "state": business.get("address", {}).get("state"),
                        "postal_code": business.get("address", {}).get("zip"),
                        "country": business.get("address", {}).get("country")
                    },
                    "phone": business.get("phone"),
                    "email": business.get("email"),
                    "source": "business_directory",
                    "confidence": 0.8
                }
            
        except json.JSONDecodeError as e:
            raise EnrichmentSourceError(f"Invalid JSON response: {str(e)}")
        
        return None
    
    @timeout_handler(timeout_sec=20)
    def find_company_website(self, 
                           company_name: str, 
                           location: Optional[str] = None) -> Optional[str]:
        """
        Find a company's website using search engines and business directories.
        
        Args:
            company_name: Name of the company
            location: Optional location to narrow search
        
        Returns:
            Website URL or None if not found
        """
        # Check cache first
        cache_key = self._get_cache_key('find_company_website', company_name, location)
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            return cached_result
        
        logger.debug(f"Finding website for company: {company_name}")
        
        # Try looking up from company data API first
        try:
            company_data = self.lookup_company_data(company_name, location)
            if company_data and company_data.get("website"):
                website = company_data["website"]
                # Validate and clean the URL
                if website and self._is_valid_url(website):
                    self._store_cache_result(cache_key, website)
                    return website
        except Exception as e:
            logger.warning(f"Error looking up company website from API: {str(e)}")
        
        # If API lookup fails, try a search-based approach
        try:
            search_query = f"{company_name}"
            if location:
                search_query += f" {location}"
                
            # This would be replaced with an actual search API integration
            # For demo purposes, we're simulating with a placeholder
            websites = self._search_for_company_website(search_query)
            
            if websites:
                # Take the first result
                website = websites[0]
                self._store_cache_result(cache_key, website)
                return website
                
        except Exception as e:
            logger.error(f"Error finding company website: {str(e)}")
        
        # No website found
        self._store_cache_result(cache_key, None)
        return None
    
    def _search_for_company_website(self, query: str) -> List[str]:
        """
        Search for company websites using a search query.
        
        Args:
            query: Search query string
        
        Returns:
            List of potential website URLs
        """
        # This is a placeholder for an actual search API integration
        # In a real implementation, you would:
        # 1. Call a search API (Google, Bing, etc.)
        # 2. Parse the results for website URLs
        # 3. Filter and validate the URLs
        
        # For demo purposes, we'll just return a simulated result
        # This would be replaced with actual search logic
        logger.info(f"Searching for websites with query: {query}")
        
        # In a real implementation, return actual search results
        return []
    
    def _is_valid_url(self, url: str) -> bool:
        """
        Validate a URL.
        
        Args:
            url: URL to validate
        
        Returns:
            True if the URL is valid, False otherwise
        """
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    @timeout_handler(timeout_sec=30)
    def extract_contact_details(self, 
                              website_url: str,
                              company_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Extract contact details from a company website.
        
        Args:
            website_url: URL of the company website
            company_name: Optional company name for validation
        
        Returns:
            List of contact detail dictionaries
        """
        # Check cache first
        cache_key = self._get_cache_key('extract_contact_details', website_url, company_name)
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            return cached_result
        
        logger.debug(f"Extracting contact details from website: {website_url}")
        
        contacts = []
        
        try:
            # Try API-based contact finder first if available
            if "contact_finder" in self.credentials:
                api_contacts = self._find_contacts_from_api(website_url, company_name)
                if api_contacts:
                    self._store_cache_result(cache_key, api_contacts)
                    return api_contacts
            
            # If API fails or isn't available, try web scraping
            scraped_contacts = self._scrape_contacts_from_website(website_url)
            if scraped_contacts:
                self._store_cache_result(cache_key, scraped_contacts)
                return scraped_contacts
                
        except Exception as e:
            logger.error(f"Error extracting contact details: {str(e)}")
        
        # Return empty list if no contacts found
        self._store_cache_result(cache_key, [])
        return []
    
    def _find_contacts_from_api(self, 
                              website_url: str,
                              company_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Find contacts using a contact finder API.
        
        Args:
            website_url: Company website URL
            company_name: Optional company name
        
        Returns:
            List of contact dictionaries
        """
        if "contact_finder" not in self.credentials:
            return []
        
        provider = "contact_finder"
        base_url = self.credentials[provider].get("base_url")
        if not base_url:
            raise EnrichmentSourceError(f"Base URL not configured for provider: {provider}")
        
        # Prepare request
        headers = self._get_auth_headers(provider)
        endpoint = "api/v1/contacts"
        url = urljoin(base_url, endpoint)
        
        params = {"domain": website_url}
        if company_name:
            params["company_name"] = company_name
        
        response = self.session.get(url, headers=headers, params=params, timeout=self.timeout)
        
        # Check for rate limiting
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            logger.warning(f"Rate limit exceeded for contact finder API. Retry after {retry_after} seconds.")
            return []
        
        # Check for other errors
        if response.status_code != 200:
            logger.warning(f"Contact finder API error ({response.status_code}): {response.text}")
            return []
        
        # Parse and format the response
        try:
            data = response.json()
            contacts = data.get("contacts", [])
            
            formatted_contacts = []
            for contact in contacts:
                formatted_contact = {
                    "name": f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip(),
                    "title": contact.get("title"),
                    "email": contact.get("email"),
                    "phone": contact.get("phone"),
                    "linkedin": contact.get("linkedin_url"),
                    "confidence": contact.get("confidence", 0.5),
                    "source": "contact_finder_api"
                }
                formatted_contacts.append(formatted_contact)
            
            return formatted_contacts
            
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON response from contact finder API: {str(e)}")
            return []
    
    def _scrape_contacts_from_website(self, website_url: str) -> List[Dict[str, Any]]:
        """
        Scrape contact details directly from a website.
        
        Args:
            website_url: URL of the company website
        
        Returns:
            List of contact dictionaries
        """
        contacts = []
        
        try:
            # Define pages to check for contacts
            pages_to_check = [
                website_url,
                urljoin(website_url, "contact"),
                urljoin(website_url, "contact-us"),
                urljoin(website_url, "about"),
                urljoin(website_url, "about-us"),
                urljoin(website_url, "team"),
            ]
            
            # Check each page
            for page_url in pages_to_check:
                try:
                    response = self.session.get(page_url, timeout=self.timeout)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # Extract emails from page
                        emails = self._extract_emails_from_html(soup)
                        
                        # Extract phone numbers from page
                        phones = self._extract_phones_from_html(soup)
                        
                        # Extract potential contact names and titles
                        potential_contacts = self._extract_potential_contacts(soup)
                        
                        # If we found both emails and potential contacts, try to match them
                        if emails and potential_contacts:
                            for i, contact in enumerate(potential_contacts):
                                if i < len(emails):
                                    contact['email'] = emails[i]
                                if i < len(phones):
                                    contact['phone'] = phones[i]
                                contacts.append(contact)
                        else:
                            # Otherwise, just create contacts from emails and phones
                            for i, email in enumerate(emails):
                                contact = {
                                    'email': email,
                                    'confidence': 0.5,
                                    'source': 'website_scraping'
                                }
                                if i < len(phones):
                                    contact['phone'] = phones[i]
                                contacts.append(contact)
                except Exception as e:
                    logger.debug(f"Error scraping contacts from {page_url}: {str(e)}")
                    continue
                
                # If we found contacts, don't need to check more pages
                if contacts:
                    break
                    
        except Exception as e:
            logger.error(f"Error scraping contacts from website: {str(e)}")
        
        return contacts
    
    def _extract_emails_from_html(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract email addresses from HTML content.
        
        Args:
            soup: BeautifulSoup object of HTML content
        
        Returns:
            List of email addresses
        """
        emails = set()
        
        # Regular expression for finding emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        # Extract from text
        text = soup.get_text()
        found_emails = re.findall(email_pattern, text)
        emails.update(found_emails)
        
        # Extract from mailto links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('mailto:'):
                email = href[7:]  # Remove 'mailto:'
                # Remove any additional parameters
                email = email.split('?')[0].split('&')[0]
                if re.match(email_pattern, email):
                    emails.add(email)
        
        return list(emails)
    
    def _extract_phones_from_html(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract phone numbers from HTML content.
        
        Args:
            soup: BeautifulSoup object of HTML content
        
        Returns:
            List of phone numbers
        """
        phones = set()
        
        # Regular expressions for finding phones
        phone_patterns = [
            r'\b(?:\+\d{1,2}\s)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b',  # US/CAN: (123) 456-7890
            r'\b\d{3}[\s.-]?\d{3}[\s.-]?\d{4}\b',  # 123-456-7890
            r'\b\+\d{1,3}[\s.-]?\d{1,14}\b'  # International: +1 123...
        ]
        
        # Extract from text
        text = soup.get_text()
        for pattern in phone_patterns:
            found_phones = re.findall(pattern, text)
            phones.update(found_phones)
        
        # Extract from tel: links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('tel:'):
                phone = href[4:]  # Remove 'tel:'
                phones.add(phone)
        
        return list(phones)
    
    def _extract_potential_contacts(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """
        Extract potential contact names and titles from HTML.
        
        Args:
            soup: BeautifulSoup object of HTML content
        
        Returns:
            List of potential contact dictionaries
        """
        contacts = []
        
        # Look for team sections, contact cards, etc.
        # This is a simplified implementation - would be more sophisticated in practice
        
        # Check for team member sections
        team_sections = soup.find_all(['div', 'section'], class_=lambda c: c and any(
            term in c.lower() for term in ['team', 'staff', 'employee', 'people', 'leadership']
        ))
        
        for section in team_sections:
            # Find potential team member cards
            cards = section.find_all(['div', 'article'], class_=lambda c: c and any(
                term in c.lower() for term in ['card', 'member', 'profile', 'person']
            ))
            
            if not cards:
                # If no obvious cards, look for list items or other divs
                cards = section.find_all(['li', 'div'])
            
            for card in cards:
                name = None
                title = None
                
                # Look for name in headings
                heading = card.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                if heading:
                    name = heading.get_text().strip()
                
                # Look for title in paragraphs or spans near the heading
                if heading:
                    title_elem = heading.find_next(['p', 'span', 'div'])
                    if title_elem:
                        title = title_elem.get_text().strip()
                
                if name:
                    contacts.append({
                        'name': name,
                        'title': title,
                        'confidence': 0.6,
                        'source': 'website_scraping'
                    })
        
        return contacts
    
    @timeout_handler(timeout_sec=15)
    def estimate_company_size(self, 
                            company_name: str,
                            company_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Estimate the size of a company.
        
        Args:
            company_name: Name of the company
            company_data: Optional company data from previous lookup
        
        Returns:
            Company size category or None if estimation fails
        """
        # Check cache first
        cache_key = self._get_cache_key('estimate_company_size', company_name)
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            return cached_result
        
        # If we already have company data with size information, use that
        if company_data and company_data.get('size'):
            size = company_data.get('size')
            
            # Convert numeric size to category if needed
            if isinstance(size, (int, float)):
                category = self._employee_count_to_category(size)
                self._store_cache_result(cache_key, category)
                return category
            elif isinstance(size, str):
                self._store_cache_result(cache_key, size)
                return size
        
        # If no existing data, try to look it up
        try:
            # Try different providers
            if "company_data" in self.credentials:
                company_info = self._lookup_company_from_provider("company_data", company_name)
                if company_info and company_info.get('size'):
                    size = company_info.get('size')
                    if isinstance(size, (int, float)):
                        category = self._employee_count_to_category(size)
                        self._store_cache_result(cache_key, category)
                        return category
                    elif isinstance(size, str):
                        self._store_cache_result(cache_key, size)
                        return size
            
            # If no API data, use NLP-based estimation from company description
            if company_data and company_data.get('description'):
                description = company_data.get('description')
                estimated_size = self._estimate_size_from_description(description, company_name)
                if estimated_size:
                    self._store_cache_result(cache_key, estimated_size)
                    return estimated_size
                    
        except Exception as e:
            logger.error(f"Error estimating company size: {str(e)}")
        
        # Default to "Unknown" if estimation fails
        self._store_cache_result(cache_key, "Unknown")
        return "Unknown"
    
    def _employee_count_to_category(self, count: Union[int, float, str]) -> str:
        """
        Convert employee count to size category.
        
        Args:
            count: Employee count (numeric or string)
        
        Returns:
            Size category string
        """
        if isinstance(count, str):
            try:
                # Try to convert string to number
                count = float(count.replace(',', '').split('-')[0])
            except (ValueError, TypeError):
                # If it's already a descriptive category, return it
                return count
        
        # Convert numeric count to category
        if count < 10:
            return "Micro (1-9)"
        elif count < 50:
            return "Small (10-49)"
        elif count < 250:
            return "Medium (50-249)"
        elif count < 1000:
            return "Large (250-999)"
        else:
            return "Enterprise (1000+)"
    
    def _estimate_size_from_description(self, 
                                      description: str,
                                      company_name: str) -> Optional[str]:
        """
        Estimate company size from description text using NLP.
        
        Args:
            description: Company description text
            company_name: Company name for context
        
        Returns:
            Estimated size category or None if inconclusive
        """
        # This would use NLP to extract clues about company size
        # For demo purposes, using a simplified keyword approach
        
        description = description.lower()
        
        # Size indicators
        indicators = {
            "Micro (1-9)": ["startup", "sole proprietor", "founder", "small team", "newly established"],
            "Small (10-49)": ["small business", "growing team", "family business", "small company"],
            "Medium (50-249)": ["medium-sized", "regional", "established company"],
            "Large (250-999)": ["large company", "national", "industry leader"],
            "Enterprise (1000+)": ["global", "enterprise", "multinational", "corporation", "industry giant"]
        }
        
        # Check for indicators and count matches
        matches = {}
        for size, keywords in indicators.items():
            matches[size] = sum(1 for keyword in keywords if keyword in description)
        
        # Return the size with the most matches, if any
        if matches:
            best_match = max(matches.items(), key=lambda x: x[1])
            if best_match[1] > 0:
                return best_match[0]
        
        return None
    
    @timeout_handler(timeout_sec=20)
    def determine_project_stage(self, lead: Dict[str, Any]) -> Optional[str]:
        """
        Determine the stage of a construction project.
        
        Args:
            lead: Lead data dictionary
        
        Returns:
            Project stage string or None if determination fails
        """
        # Stages in order of project lifecycle
        stages = [
            "Planning", 
            "Design", 
            "Bidding", 
            "Pre-Construction", 
            "Construction", 
            "Post-Construction", 
            "Completed"
        ]
        
        # Extract key fields that might contain stage information
        title = lead.get('title', '')
        description = lead.get('description', '')
        raw_data = lead.get('raw_data', {})
        
        # Check cache first
        cache_key = self._get_cache_key('determine_project_stage', title, description[:100])
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            return cached_result
        
        # Check if stage is explicitly mentioned
        combined_text = f"{title} {description}"
        
        # Look for explicit mentions of stages
        for stage in stages:
            pattern = r'\b' + re.escape(stage) + r'\b'
            if re.search(pattern, combined_text, re.IGNORECASE):
                self._store_cache_result(cache_key, stage)
                return stage
        
        # Check for stage-specific keywords
        keywords = {
            "Planning": ["planning", "proposed", "concept", "feasibility", "zoning", "approval"],
            "Design": ["design", "architect", "engineering", "drawing", "blueprint", "scheme"],
            "Bidding": ["bid", "tender", "proposal", "quotation", "estimate", "contractor selection"],
            "Pre-Construction": ["pre-construction", "mobilization", "site prep", "preparation"],
            "Construction": ["construction", "building", "erecting", "in progress", "ongoing", "phase"],
            "Post-Construction": ["finishing", "handover", "punch list", "cleanup", "final inspection"],
            "Completed": ["completed", "finished", "done", "delivered", "inaugurated", "opening"]
        }
        
        # Count matches for each stage
        matches = {}
        for stage, terms in keywords.items():
            count = 0
            for term in terms:
                count += len(re.findall(r'\b' + re.escape(term) + r'\b', combined_text, re.IGNORECASE))
            matches[stage] = count
        
        # If we have matches, return the stage with the most matches
        if matches and max(matches.values()) > 0:
            best_match = max(matches.items(), key=lambda x: x[1])
            self._store_cache_result(cache_key, best_match[0])
            return best_match[0]
        
        # Use NLP processor for more sophisticated analysis
        try:
            nlp_results = self.nlp_processor.process_text(
                combined_text,
                include_classification=True
            )
            
            if nlp_results and 'classification' in nlp_results:
                stage = nlp_results['classification'].get('project_stage')
                if stage:
                    self._store_cache_result(cache_key, stage)
                    return stage
        except Exception as e:
            logger.warning(f"Error during NLP classification for project stage: {e}")
        
        # If no stage could be determined, return None
        return None
    
    @timeout_handler(timeout_sec=30)
    def find_related_projects(self, lead: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find projects related to this lead.
        
        Args:
            lead: Lead data dictionary
        
        Returns:
            List of related project dictionaries
        """
        # Check cache first
        company_name = lead.get('organization')
        location = lead.get('location')
        
        if not company_name and not location:
            return []
        
        cache_key = self._get_cache_key('find_related_projects', company_name, location)
        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            return cached_result
        
        related_projects = []
        
        try:
            # Try to find projects by the same company
            if company_name:
                company_projects = self._find_projects_by_company(company_name)
                for project in company_projects:
                    if self._is_different_project(project, lead):
                        related_projects.append(project)
            
            # Try to find projects in the same location
            if location and len(related_projects) < 5:
                location_projects = self._find_projects_by_location(location)
                for project in location_projects:
                    if self._is_different_project(project, lead) and project not in related_projects:
                        related_projects.append(project)
                        
                        # Limit to 5 related projects
                        if len(related_projects) >= 5:
                            break
                            
        except Exception as e:
            logger.error(f"Error finding related projects: {str(e)}")
        
        # Store in cache and return
        self._store_cache_result(cache_key, related_projects)
        return related_projects
    
    def _find_projects_by_company(self, company_name: str) -> List[Dict[str, Any]]:
        """
        Find projects associated with a specific company.
        
        Args:
            company_name: Name of the company
        
        Returns:
            List of project dictionaries
        """
        # This would query your existing lead database or external sources
        # For demo purposes, we'll just query the local storage
        
        projects = []
        
        try:
            # Try to find leads with the same organization in storage
            existing_leads = self.storage.search_leads(
                {"organization": company_name}, 
                limit=5
            )
            
            # Format the leads as projects
            for lead in existing_leads:
                projects.append({
                    "id": lead.get("id"),
                    "title": lead.get("title"),
                    "description": lead.get("description", "")[:100] + "..." if lead.get("description") else "",
                    "location": lead.get("location"),
                    "project_type": lead.get("project_type"),
                    "project_value": lead.get("project_value"),
                    "date": lead.get("published_date"),
                    "relation_type": "same_company"
                })
                
        except Exception as e:
            logger.warning(f"Error querying local storage for company projects: {e}")
        
        # If we have a project database provider, query it as well
        if "project_database" in self.credentials:
            try:
                projects.extend(self._query_project_database("company", company_name))
            except Exception as e:
                logger.warning(f"Error querying project database for company projects: {e}")
        
        return projects
    
    def _find_projects_by_location(self, location: str) -> List[Dict[str, Any]]:
        """
        Find projects in a specific location.
        
        Args:
            location: Project location
        
        Returns:
            List of project dictionaries
        """
        # This would query your existing lead database or external sources
        # For demo purposes, we'll just query the local storage
        
        projects = []
        
        try:
            # Try to find leads with the same location in storage
            existing_leads = self.storage.search_leads(
                {"location": location}, 
                limit=5
            )
            
            # Format the leads as projects
            for lead in existing_leads:
                projects.append({
                    "id": lead.get("id"),
                    "title": lead.get("title"),
                    "description": lead.get("description", "")[:100] + "..." if lead.get("description") else "",
                    "organization": lead.get("organization"),
                    "project_type": lead.get("project_type"),
                    "project_value": lead.get("project_value"),
                    "date": lead.get("published_date"),
                    "relation_type": "same_location"
                })
                
        except Exception as e:
            logger.warning(f"Error querying local storage for location projects: {e}")
        
        # If we have a project database provider, query it as well
        if "project_database" in self.credentials:
            try:
                projects.extend(self._query_project_database("location", location))
            except Exception as e:
                logger.warning(f"Error querying project database for location projects: {e}")
        
        return projects
    
    def _query_project_database(self, 
                              search_type: str, 
                              search_value: str) -> List[Dict[str, Any]]:
        """
        Query external project database for related projects.
        
        Args:
            search_type: Type of search (company, location, etc.)
            search_value: Value to search for
        
        Returns:
            List of project dictionaries
        """
        if "project_database" not in self.credentials:
            return []
        
        provider = "project_database"
        base_url = self.credentials[provider].get("base_url")
        if not base_url:
            return []
        
        # Prepare request
        headers = self._get_auth_headers(provider)
        endpoint = "api/projects/search"
        url = urljoin(base_url, endpoint)
        
        params = {"limit": 5}
        if search_type == "company":
            params["company"] = search_value
        elif search_type == "location":
            params["location"] = search_value
        
        try:
            response = self.session.get(url, headers=headers, params=params, timeout=self.timeout)
            
            # Check for rate limiting
            if response.status_code == 429:
                logger.warning("Rate limit exceeded for project database API")
                return []
            
            # Check for other errors
            if response.status_code != 200:
                logger.warning(f"Project database API error ({response.status_code}): {response.text}")
                return []
            
            # Parse response
            data = response.json()
            projects = data.get("projects", [])
            
            # Format projects
            formatted_projects = []
            for project in projects:
                formatted_project = {
                    "id": project.get("id"),
                    "title": project.get("name"),
                    "description": project.get("description", "")[:100] + "..." if project.get("description") else "",
                    "organization": project.get("company"),
                    "location": project.get("location"),
                    "project_type": project.get("type"),
                    "project_value": project.get("value"),
                    "date": project.get("start_date"),
                    "relation_type": f"same_{search_type}"
                }
                formatted_projects.append(formatted_project)
            
            return formatted_projects
            
        except Exception as e:
            logger.warning(f"Error querying project database: {str(e)}")
            return []
    
    def _is_different_project(self, project: Dict[str, Any], lead: Dict[str, Any]) -> bool:
        """
        Check if a project is different from the current lead.
        
        Args:
            project: Project dictionary
            lead: Lead dictionary
        
        Returns:
            True if it's a different project, False if it's likely the same
        """
        # Check if IDs match
        if project.get("id") == lead.get("id"):
            return False
        
        # Check if titles are very similar
        if project.get("title") and lead.get("title"):
            from difflib import SequenceMatcher
            title_similarity = SequenceMatcher(None, project.get("title", ""), lead.get("title", "")).ratio()
            if title_similarity > 0.8:
                return False
        
        # If we pass all checks, it's a different project
        return True
    
    def calculate_lead_score(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate a score for the lead based on multiple factors.
        
        Args:
            lead: Lead data dictionary
        
        Returns:
            Dictionary with total score and component scores
        """
        # Define scoring components and weights
        components = {
            "company_data": 15,      # Does the lead have company information?
            "contact_details": 20,   # Does the lead have contact information?
            "project_details": 15,   # How complete are the project details?
            "project_value": 15,     # How valuable is the project?
            "project_timeliness": 20,  # Is the project in an actionable stage?
            "market_fit": 15         # Does it fit our target markets/sectors?
        }
        
        scores = {}
        
        # Score: Company Data (0-15)
        company_score = 0
        if lead.get('company'):
            company_score += 5  # Basic company data
            
            # Additional points for completeness
            company = lead.get('company', {})
            if company.get('website'):
                company_score += 3
            if company.get('description'):
                company_score += 2
            if company.get('size') or lead.get('company_size'):
                company_score += 2
            if company.get('location', {}).get('address'):
                company_score += 3
        
        scores["company_data"] = min(company_score, 15)
        
        # Score: Contact Details (0-20)
        contact_score = 0
        contacts = lead.get('contacts', [])
        if contacts:
            contact_score += 5  # Basic contact list
            
            # Points for first contact completeness
            first_contact = contacts[0] if contacts else {}
            if first_contact.get('name'):
                contact_score += 3
            if first_contact.get('title'):
                contact_score += 2
            if first_contact.get('email'):
                contact_score += 5
            if first_contact.get('phone'):
                contact_score += 5
        
        scores["contact_details"] = min(contact_score, 20)
        
        # Score: Project Details (0-15)
        project_score = 0
        if lead.get('title'):
            project_score += 3
        if lead.get('description') and len(lead.get('description', '')) > 100:
            project_score += 3
        if lead.get('location'):
            project_score += 3
        if lead.get('project_type'):
            project_score += 3
        if lead.get('project_stage'):
            project_score += 3
        
        scores["project_details"] = min(project_score, 15)
        
        # Score: Project Value (0-15)
        value_score = 0
        project_value = lead.get('project_value')
        if project_value:
            if isinstance(project_value, (int, float)):
                # Scale based on value (example thresholds)
                if project_value >= 10000000:  # $10M+
                    value_score = 15
                elif project_value >= 5000000:  # $5M+
                    value_score = 12
                elif project_value >= 1000000:  # $1M+
                    value_score = 10
                elif project_value >= 500000:  # $500K+
                    value_score = 8
                elif project_value >= 100000:  # $100K+
                    value_score = 5
                else:
                    value_score = 3
            else:
                # String value - just give partial credit
                value_score = 5
        
        scores["project_value"] = value_score
        
        # Score: Project Timeliness (0-20)
        timeliness_score = 0
        project_stage = lead.get('project_stage', '')
        
        # Preferred stages get full points
        if project_stage in ["Bidding", "Pre-Construction"]:
            timeliness_score = 20
        # Early stages get good points
        elif project_stage in ["Planning", "Design"]:
            timeliness_score = 15
        # Construction phase gets moderate points
        elif project_stage == "Construction":
            timeliness_score = 10
        # Late or completed stages get fewer points
        elif project_stage in ["Post-Construction", "Completed"]:
            timeliness_score = 5
        # Unknown stage gets minimal points
        else:
            timeliness_score = 3
        
        scores["project_timeliness"] = timeliness_score
        
        # Score: Market Fit (0-15)
        market_score = 0
        
        # Get target markets and sectors from config
        target_markets = self.config.get('target_markets', [])
        target_sectors = self.config.get('target_sectors', [])
        
        # Location match
        if lead.get('location') and target_markets:
            for market in target_markets:
                if market.lower() in lead.get('location', '').lower():
                    market_score += 8
                    break
        else:
            # No target markets defined or no location - give partial credit
            market_score += 4
        
        # Sector match
        if lead.get('project_type') and target_sectors:
            for sector in target_sectors:
                if sector.lower() in lead.get('project_type', '').lower():
                    market_score += 7
                    break
        else:
            # No target sectors defined or no project type - give partial credit
            market_score += 3
        
        scores["market_fit"] = min(market_score, 15)
        
        # Calculate total score (0-100)
        total_raw = sum(scores[component] * (weight/100) for component, weight in components.items())
        total = round(total_raw)
        
        # Determine quality category
        if total >= 80:
            quality = "Excellent"
        elif total >= 60:
            quality = "Good"
        elif total >= 40:
            quality = "Average"
        elif total >= 20:
            quality = "Fair"
        else:
            quality = "Poor"
        
        return {
            "total": total,
            "quality": quality,
            "components": scores
        }
"""Legal API client for retrieving legal documents from external sources.

This module provides functionality to connect to various legal document APIs
and retrieve construction-related legal documents such as permits, contracts,
zoning applications, and regulatory filings.
"""

import os
import json
import time
import logging
import requests
from typing import Dict, List, Any, Optional, Union, BinaryIO, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import base64
import hashlib
from urllib.parse import urljoin

from ..config import AppConfig
from ..utils.timeout import timeout_handler
from .document_parser import DocumentParser, ParseError

logger = logging.getLogger(__name__)

class LegalAPIError(Exception):
    """Base exception for legal API errors."""
    pass

class AuthenticationError(LegalAPIError):
    """Exception raised when authentication fails."""
    pass

class RateLimitError(LegalAPIError):
    """Exception raised when API rate limit is exceeded."""
    pass

class DocumentNotFoundError(LegalAPIError):
    """Exception raised when a document is not found."""
    pass


class LegalAPI:
    """Client for accessing legal documents from external APIs.
    
    This class provides methods for connecting to various legal document APIs
    and retrieving construction-related documents such as permits, contracts,
    zoning applications, and regulatory filings.
    """
    
    # Supported API providers
    SUPPORTED_PROVIDERS = [
        "public_records",
        "permit_data",
        "contract_finder",
        "court_records",
        "regulatory_filings"
    ]
    
    def __init__(self, config: Optional[AppConfig] = None):
        """Initialize the Legal API client.
        
        Args:
            config: Application configuration object
        """
        self.config = config or AppConfig()
        self.session = requests.Session()
        self._configure_session()
        self._load_api_credentials()
        self.document_parser = DocumentParser(config)
        logger.info("Legal API client initialized")
    
    def _configure_session(self) -> None:
        """Configure the requests session with headers, proxies, etc."""
        # Set default headers
        self.session.headers.update({
            "User-Agent": "Perera Construction Lead Scraper",
            "Accept": "application/json"
        })
        
        # Configure proxies if enabled
        if self.config.use_proxies and self.config.proxy_url:
            self.session.proxies = {
                "http": self.config.proxy_url,
                "https": self.config.proxy_url
            }
        
        # Configure timeouts
        self.timeout = 30  # Default timeout in seconds
    
    def _load_api_credentials(self) -> None:
        """Load API credentials from configuration."""
        self.credentials = {}
        
        # Path to credentials file
        credentials_path = Path(os.getenv(
            "LEGAL_API_CREDENTIALS_PATH", 
            str(Path(self.config.sources_path).parent / "legal_api_credentials.json")
        ))
        
        try:
            if credentials_path.exists():
                with open(credentials_path, "r") as f:
                    self.credentials = json.load(f)
                logger.info(f"Loaded credentials for {len(self.credentials)} legal API providers")
            else:
                logger.warning(f"Legal API credentials file not found at {credentials_path}")
        except Exception as e:
            logger.error(f"Error loading legal API credentials: {e}")
    
    def _get_auth_headers(self, provider: str) -> Dict[str, str]:
        """Get authentication headers for the specified provider.
        
        Args:
            provider: API provider name
            
        Returns:
            Dictionary of authentication headers
            
        Raises:
            AuthenticationError: If credentials are not found or incomplete
        """
        if provider not in self.credentials:
            raise AuthenticationError(f"No credentials found for provider: {provider}")
        
        creds = self.credentials[provider]
        
        # Different authentication methods based on provider
        if provider == "public_records":
            if "api_key" not in creds:
                raise AuthenticationError(f"API key missing for provider: {provider}")
            
            return {"Authorization": f"Bearer {creds['api_key']}"}
            
        elif provider == "permit_data":
            if "username" not in creds or "password" not in creds:
                raise AuthenticationError(f"Username or password missing for provider: {provider}")
            
            # Basic auth
            auth_string = f"{creds['username']}:{creds['password']}"
            encoded = base64.b64encode(auth_string.encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
            
        elif provider == "contract_finder":
            if "api_key" not in creds:
                raise AuthenticationError(f"API key missing for provider: {provider}")
            
            return {"X-API-Key": creds["api_key"]}
            
        elif provider == "court_records":
            if "client_id" not in creds or "client_secret" not in creds:
                raise AuthenticationError(f"Client ID or secret missing for provider: {provider}")
            
            # OAuth token
            # Note: In a real implementation, this would include token caching and refresh logic
            return {"Authorization": f"Bearer {self._get_oauth_token(provider)}"}
            
        elif provider == "regulatory_filings":
            if "api_key" not in creds:
                raise AuthenticationError(f"API key missing for provider: {provider}")
            
            return {"Authorization": f"ApiKey {creds['api_key']}"}
            
        else:
            return {}
    
    def _get_oauth_token(self, provider: str) -> str:
        """Get OAuth token for the specified provider.
        
        Args:
            provider: API provider name
            
        Returns:
            OAuth token
            
        Raises:
            AuthenticationError: If token cannot be obtained
        """
        # This is a placeholder for OAuth token acquisition
        # In a real implementation, this would request a token from the provider's OAuth endpoint
        # and implement proper caching and refreshing of tokens
        creds = self.credentials[provider]
        
        # For demo purposes, just return a fake token
        # In production, you would implement actual OAuth flow
        token_data = f"{creds['client_id']}:{creds['client_secret']}:{int(time.time())}"
        return hashlib.sha256(token_data.encode()).hexdigest()
    
    def _handle_rate_limit(self, response: requests.Response) -> None:
        """Handle rate limit responses.
        
        Args:
            response: API response
            
        Raises:
            RateLimitError: With details about the rate limit
        """
        # Extract rate limit information from headers if available
        remaining = response.headers.get("X-RateLimit-Remaining", "Unknown")
        reset_time = response.headers.get("X-RateLimit-Reset", "Unknown")
        
        error_msg = f"API rate limit exceeded. Remaining: {remaining}, Reset: {reset_time}"
        logger.warning(error_msg)
        
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                # Convert to seconds and add a small buffer
                retry_seconds = int(retry_after) + 1
                error_msg += f". Retry after {retry_seconds} seconds."
            except ValueError:
                pass
        
        raise RateLimitError(error_msg)
    
    @timeout_handler(timeout_sec=60)
    def search_documents(self, 
                        provider: str, 
                        search_params: Dict[str, Any],
                        max_results: int = 25) -> List[Dict[str, Any]]:
        """Search for legal documents using the specified provider.
        
        Args:
            provider: API provider name
            search_params: Search parameters (varies by provider)
            max_results: Maximum number of results to return
            
        Returns:
            List of document metadata dictionaries
            
        Raises:
            LegalAPIError: If the API request fails
            AuthenticationError: If authentication fails
            RateLimitError: If the API rate limit is exceeded
        """
        if provider not in self.SUPPORTED_PROVIDERS:
            raise LegalAPIError(f"Unsupported provider: {provider}")
        
        try:
            # Get base URL for the provider
            base_url = self.credentials.get(provider, {}).get("base_url")
            if not base_url:
                raise LegalAPIError(f"Base URL not configured for provider: {provider}")
            
            # Prepare request
            headers = self._get_auth_headers(provider)
            search_endpoint = self._get_search_endpoint(provider)
            url = urljoin(base_url, search_endpoint)
            
            # Add max results parameter
            # The parameter name varies by provider
            if provider == "public_records":
                search_params["limit"] = max_results
            elif provider == "permit_data":
                search_params["max_results"] = max_results
            elif provider == "contract_finder":
                search_params["page_size"] = max_results
            elif provider == "court_records":
                search_params["max"] = max_results
            elif provider == "regulatory_filings":
                search_params["size"] = max_results
            
            # Make the request
            logger.debug(f"Searching {provider} API with params: {search_params}")
            response = self.session.get(
                url, 
                params=search_params, 
                headers=headers,
                timeout=self.timeout
            )
            
            # Check for errors
            if response.status_code == 401:
                raise AuthenticationError(f"Authentication failed for provider: {provider}")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden for provider: {provider}")
            elif response.status_code == 429:
                self._handle_rate_limit(response)
            elif response.status_code >= 400:
                raise LegalAPIError(f"API error ({response.status_code}): {response.text}")
            
            # Parse response
            data = response.json()
            
            # Extract results based on provider-specific response format
            results = self._extract_search_results(provider, data)
            
            logger.info(f"Found {len(results)} documents from {provider}")
            return results
            
        except requests.RequestException as e:
            logger.error(f"Request error searching {provider}: {e}")
            raise LegalAPIError(f"Request failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error from {provider}: {e}")
            raise LegalAPIError(f"Invalid JSON response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error searching {provider}: {e}")
            raise LegalAPIError(f"Unexpected error: {str(e)}")
    
    def _get_search_endpoint(self, provider: str) -> str:
        """Get the search endpoint for the specified provider.
        
        Args:
            provider: API provider name
            
        Returns:
            Search endpoint path
        """
        endpoints = {
            "public_records": "api/v1/documents/search",
            "permit_data": "permits/search",
            "contract_finder": "api/contracts",
            "court_records": "v2/records/search",
            "regulatory_filings": "api/filings/search"
        }
        
        return endpoints.get(provider, "search")
    
    def _extract_search_results(self, provider: str, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract search results from API response based on provider format.
        
        Args:
            provider: API provider name
            data: API response data
            
        Returns:
            List of document metadata dictionaries
        """
        if provider == "public_records":
            return data.get("documents", [])
        elif provider == "permit_data":
            return data.get("permits", [])
        elif provider == "contract_finder":
            return data.get("results", [])
        elif provider == "court_records":
            return data.get("records", [])
        elif provider == "regulatory_filings":
            return data.get("filings", [])
        else:
            return []
    
    @timeout_handler(timeout_sec=60)
    def get_document(self, provider: str, document_id: str) -> Dict[str, Any]:
        """Retrieve a specific document by ID.
        
        Args:
            provider: API provider name
            document_id: Document identifier
            
        Returns:
            Document metadata dictionary
            
        Raises:
            LegalAPIError: If the API request fails
            DocumentNotFoundError: If the document is not found
            AuthenticationError: If authentication fails
            RateLimitError: If the API rate limit is exceeded
        """
        if provider not in self.SUPPORTED_PROVIDERS:
            raise LegalAPIError(f"Unsupported provider: {provider}")
        
        try:
            # Get base URL for the provider
            base_url = self.credentials.get(provider, {}).get("base_url")
            if not base_url:
                raise LegalAPIError(f"Base URL not configured for provider: {provider}")
            
            # Prepare request
            headers = self._get_auth_headers(provider)
            document_endpoint = self._get_document_endpoint(provider, document_id)
            url = urljoin(base_url, document_endpoint)
            
            # Make the request
            logger.debug(f"Fetching document {document_id} from {provider}")
            response = self.session.get(
                url, 
                headers=headers,
                timeout=self.timeout
            )
            
            # Check for errors
            if response.status_code == 404:
                raise DocumentNotFoundError(f"Document not found: {document_id}")
            elif response.status_code == 401:
                raise AuthenticationError(f"Authentication failed for provider: {provider}")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden for provider: {provider}")
            elif response.status_code == 429:
                self._handle_rate_limit(response)
            elif response.status_code >= 400:
                raise LegalAPIError(f"API error ({response.status_code}): {response.text}")
            
            # Parse response
            data = response.json()
            
            logger.info(f"Retrieved document {document_id} from {provider}")
            return data
            
        except requests.RequestException as e:
            logger.error(f"Request error fetching document {document_id} from {provider}: {e}")
            raise LegalAPIError(f"Request failed: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error from {provider}: {e}")
            raise LegalAPIError(f"Invalid JSON response: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error fetching document {document_id} from {provider}: {e}")
            raise LegalAPIError(f"Unexpected error: {str(e)}")
    
    def _get_document_endpoint(self, provider: str, document_id: str) -> str:
        """Get the document endpoint for the specified provider.
        
        Args:
            provider: API provider name
            document_id: Document identifier
            
        Returns:
            Document endpoint path
        """
        endpoints = {
            "public_records": f"api/v1/documents/{document_id}",
            "permit_data": f"permits/{document_id}",
            "contract_finder": f"api/contracts/{document_id}",
            "court_records": f"v2/records/{document_id}",
            "regulatory_filings": f"api/filings/{document_id}"
        }
        
        return endpoints.get(provider, f"documents/{document_id}")
    
    @timeout_handler(timeout_sec=120)
    def download_document_file(self, 
                              provider: str, 
                              document_id: str, 
                              file_format: str = "pdf") -> Tuple[bytes, str]:
        """Download a document file in the specified format.
        
        Args:
            provider: API provider name
            document_id: Document identifier
            file_format: Desired file format (pdf, docx, txt)
            
        Returns:
            Tuple of (file_content_bytes, content_type)
            
        Raises:
            LegalAPIError: If the API request fails
            DocumentNotFoundError: If the document is not found
            AuthenticationError: If authentication fails
            RateLimitError: If the API rate limit is exceeded
        """
        if provider not in self.SUPPORTED_PROVIDERS:
            raise LegalAPIError(f"Unsupported provider: {provider}")
        
        if file_format not in ["pdf", "docx", "txt"]:
            raise LegalAPIError(f"Unsupported file format: {file_format}")
        
        try:
            # Get base URL for the provider
            base_url = self.credentials.get(provider, {}).get("base_url")
            if not base_url:
                raise LegalAPIError(f"Base URL not configured for provider: {provider}")
            
            # Prepare request
            headers = self._get_auth_headers(provider)
            download_endpoint = self._get_download_endpoint(provider, document_id, file_format)
            url = urljoin(base_url, download_endpoint)
            
            # Make the request
            logger.debug(f"Downloading {file_format} file for document {document_id} from {provider}")
            response = self.session.get(
                url, 
                headers=headers,
                timeout=self.timeout * 2  # Double timeout for downloads
            )
            
            # Check for errors
            if response.status_code == 404:
                raise DocumentNotFoundError(f"Document not found: {document_id}")
            elif response.status_code == 401:
                raise AuthenticationError(f"Authentication failed for provider: {provider}")
            elif response.status_code == 403:
                raise AuthenticationError(f"Access forbidden for provider: {provider}")
            elif response.status_code == 429:
                self._handle_rate_limit(response)
            elif response.status_code >= 400:
                raise LegalAPIError(f"API error ({response.status_code}): {response.text}")
            
            content_type = response.headers.get("Content-Type", "application/octet-stream")
            
            logger.info(f"Downloaded {file_format} file for document {document_id} from {provider} ({len(response.content)} bytes)")
            return response.content, content_type
            
        except requests.RequestException as e:
            logger.error(f"Request error downloading document {document_id} from {provider}: {e}")
            raise LegalAPIError(f"Request failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error downloading document {document_id} from {provider}: {e}")
            raise LegalAPIError(f"Unexpected error: {str(e)}")
    
    def _get_download_endpoint(self, provider: str, document_id: str, file_format: str) -> str:
        """Get the download endpoint for the specified provider.
        
        Args:
            provider: API provider name
            document_id: Document identifier
            file_format: Desired file format
            
        Returns:
            Download endpoint path
        """
        endpoints = {
            "public_records": f"api/v1/documents/{document_id}/download?format={file_format}",
            "permit_data": f"permits/{document_id}/file?format={file_format}",
            "contract_finder": f"api/contracts/{document_id}/download?format={file_format}",
            "court_records": f"v2/records/{document_id}/document?format={file_format}",
            "regulatory_filings": f"api/filings/{document_id}/download?format={file_format}"
        }
        
        return endpoints.get(provider, f"documents/{document_id}/download?format={file_format}")
    
    def extract_text_from_document(self, 
                                  provider: str, 
                                  document_id: str) -> str:
        """Download and extract text from a document.
        
        Args:
            provider: API provider name
            document_id: Document identifier
            
        Returns:
            Extracted text content
            
        Raises:
            LegalAPIError: If the API request fails
            DocumentNotFoundError: If the document is not found
            ParseError: If the document cannot be parsed
        """
        try:
            # Try to download in PDF format first
            content, content_type = self.download_document_file(provider, document_id, "pdf")
            
            # Parse the content
            try:
                # Determine format from content type
                format_type = "pdf"
                if "application/pdf" in content_type:
                    format_type = "pdf"
                elif "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in content_type:
                    format_type = "docx"
                elif "text/plain" in content_type:
                    format_type = "txt"
                elif "text/html" in content_type:
                    format_type = "html"
                
                text = self.document_parser.parse_content(content, format_type)
                return text
                
            except ParseError as e:
                logger.warning(f"Error parsing PDF for document {document_id}, trying other formats: {e}")
                
                # Try to download in other formats
                for format_type in ["docx", "txt"]:
                    try:
                        content, _ = self.download_document_file(provider, document_id, format_type)
                        text = self.document_parser.parse_content(content, format_type)
                        return text
                    except (LegalAPIError, ParseError) as e:
                        logger.warning(f"Error with {format_type} format for document {document_id}: {e}")
                
                # If all formats fail, raise the original error
                raise
                
        except Exception as e:
            logger.error(f"Error extracting text from document {document_id} from {provider}: {e}")
            if isinstance(e, (DocumentNotFoundError, ParseError)):
                raise
            else:
                raise LegalAPIError(f"Failed to extract text: {str(e)}")
    
    def fetch_recent_documents(self, 
                              provider: str, 
                              document_type: Optional[str] = None,
                              location: Optional[str] = None,
                              days: int = 7,
                              max_results: int = 25) -> List[Dict[str, Any]]:
        """Fetch recent documents of the specified type and location.
        
        Args:
            provider: API provider name
            document_type: Type of document to fetch (permit, contract, zoning, regulatory)
            location: Location filter (city, county, state)
            days: Number of days to look back
            max_results: Maximum number of results to return
            
        Returns:
            List of document metadata dictionaries
        """
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Format dates based on provider requirements
        if provider in ["public_records", "regulatory_filings"]:
            date_format = "%Y-%m-%d"
        else:
            date_format = "%m/%d/%Y"
            
        start_date_str = start_date.strftime(date_format)
        end_date_str = end_date.strftime(date_format)
        
        # Prepare search parameters based on provider
        search_params = {}
        
        if provider == "public_records":
            search_params = {
                "date_from": start_date_str,
                "date_to": end_date_str,
                "sort": "date_desc"
            }
            if document_type:
                search_params["document_type"] = document_type
            if location:
                search_params["location"] = location
                
        elif provider == "permit_data":
            search_params = {
                "issue_date_from": start_date_str,
                "issue_date_to": end_date_str,
                "sort_by": "issue_date",
                "sort_order": "desc"
            }
            if document_type:
                search_params["permit_type"] = document_type
            if location:
                search_params["jurisdiction"] = location
                
        elif provider == "contract_finder":
            search_params = {
                "published_from": start_date_str,
                "published_to": end_date_str,
                "sort": "published_date,desc"
            }
            if document_type:
                search_params["contract_type"] = document_type
            if location:
                search_params["location"] = location
                
        elif provider == "court_records":
            search_params = {
                "filed_after": start_date_str,
                "filed_before": end_date_str,
                "sort": "filed_date_desc"
            }
            if document_type:
                search_params["case_type"] = document_type
            if location:
                search_params["jurisdiction"] = location
                
        elif provider == "regulatory_filings":
            search_params = {
                "filing_date_start": start_date_str,
                "filing_date_end": end_date_str,
                "sort": "filing_date:desc"
            }
            if document_type:
                search_params["filing_type"] = document_type
            if location:
                search_params["location"] = location
        
        # Execute the search
        return self.search_documents(provider, search_params, max_results)
    
    def batch_download_documents(self, 
                               provider: str, 
                               document_ids: List[str],
                               extract_text: bool = True) -> Dict[str, Any]:
        """Download multiple documents in batch.
        
        Args:
            provider: API provider name
            document_ids: List of document identifiers
            extract_text: Whether to extract text from the documents
            
        Returns:
            Dictionary mapping document IDs to results
        """
        results = {}
        
        for doc_id in document_ids:
            try:
                logger.info(f"Processing document {doc_id} from {provider}")
                
                # Get document metadata
                doc_metadata = self.get_document(provider, doc_id)
                
                result = {
                    "metadata": doc_metadata,
                    "error": None
                }
                
                # Extract text if requested
                if extract_text:
                    try:
                        text = self.extract_text_from_document(provider, doc_id)
                        result["text"] = text
                    except Exception as e:
                        logger.error(f"Error extracting text from document {doc_id}: {e}")
                        result["text"] = None
                        result["error"] = f"Text extraction failed: {str(e)}"
                
                results[doc_id] = result
                
            except Exception as e:
                logger.error(f"Error processing document {doc_id}: {e}")
                results[doc_id] = {
                    "metadata": None,
                    "text": None,
                    "error": str(e)
                }
        
        return results
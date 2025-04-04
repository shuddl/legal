"""
Unit tests for the Legal API client.
"""

import unittest
from unittest.mock import MagicMock, patch, ANY
import json
import os
from pathlib import Path
from datetime import datetime
import tempfile
import io

# Import the modules to test
from perera_lead_scraper.legal.legal_api import (
    LegalAPI,
    LegalAPIError,
    AuthenticationError,
    RateLimitError,
    DocumentNotFoundError
)
from perera_lead_scraper.config import AppConfig


class TestLegalAPI(unittest.TestCase):
    """Test the LegalAPI class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock config
        self.mock_config = MagicMock(spec=AppConfig)
        self.mock_config.use_proxies = False
        self.mock_config.proxy_url = None
        
        # Create a temporary credentials file
        self.temp_creds_file = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        self.temp_creds_path = Path(self.temp_creds_file.name)
        
        # Create mock credentials
        self.credentials = {
            "public_records": {
                "base_url": "https://api.publicrecords.example.com/",
                "api_key": "test_api_key_123"
            },
            "permit_data": {
                "base_url": "https://permitdata.example.com/",
                "username": "test_user",
                "password": "test_password"
            },
            "court_records": {
                "base_url": "https://courtrecords.example.com/",
                "client_id": "test_client_id",
                "client_secret": "test_client_secret"
            }
        }
        
        # Write credentials to the temporary file
        with open(self.temp_creds_path, 'w') as f:
            json.dump(self.credentials, f)
        
        # Configure mock for sources_path
        self.mock_config.sources_path = str(self.temp_creds_path.parent / "sources.json")
        
        # Patch environment variable for credentials
        self.env_patcher = patch.dict('os.environ', {
            'LEGAL_API_CREDENTIALS_PATH': str(self.temp_creds_path)
        })
        self.env_patcher.start()
        
        # Create the API client with the mock config
        self.api = LegalAPI(self.mock_config)
        
        # Replace the requests session with a mock
        self.mock_session = MagicMock()
        self.api.session = self.mock_session
    
    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
        os.unlink(self.temp_creds_path)
    
    def test_initialization(self):
        """Test API client initialization."""
        # Verify credentials were loaded
        self.assertEqual(len(self.api.credentials), 3)
        self.assertIn("public_records", self.api.credentials)
        self.assertIn("permit_data", self.api.credentials)
        self.assertIn("court_records", self.api.credentials)
    
    def test_get_auth_headers_public_records(self):
        """Test getting authentication headers for public records API."""
        headers = self.api._get_auth_headers("public_records")
        self.assertEqual(headers, {"Authorization": "Bearer test_api_key_123"})
    
    def test_get_auth_headers_permit_data(self):
        """Test getting authentication headers for permit data API."""
        headers = self.api._get_auth_headers("permit_data")
        # Should contain basic auth header
        self.assertIn("Authorization", headers)
        self.assertTrue(headers["Authorization"].startswith("Basic "))
    
    def test_get_auth_headers_invalid_provider(self):
        """Test getting authentication headers for invalid provider."""
        with self.assertRaises(AuthenticationError):
            self.api._get_auth_headers("invalid_provider")
    
    def test_search_documents_success(self):
        """Test successful document search."""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "documents": [
                {"id": "doc1", "title": "Document 1"},
                {"id": "doc2", "title": "Document 2"}
            ]
        }
        self.mock_session.get.return_value = mock_response
        
        # Call the search method
        results = self.api.search_documents(
            provider="public_records",
            search_params={"keyword": "construction"}
        )
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], "doc1")
        self.assertEqual(results[1]["title"], "Document 2")
        
        # Verify correct URL and parameters were used
        self.mock_session.get.assert_called_once()
        call_args = self.mock_session.get.call_args
        url = call_args[0][0]
        params = call_args[1]["params"]
        
        self.assertTrue(url.endswith("api/v1/documents/search"))
        self.assertEqual(params["keyword"], "construction")
        self.assertEqual(params["limit"], 25)  # Default max_results
    
    def test_search_documents_authentication_error(self):
        """Test document search with authentication error."""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        self.mock_session.get.return_value = mock_response
        
        # Call the search method and verify exception
        with self.assertRaises(AuthenticationError):
            self.api.search_documents(
                provider="public_records",
                search_params={"keyword": "construction"}
            )
    
    def test_search_documents_rate_limit(self):
        """Test document search with rate limit error."""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limit exceeded"
        mock_response.headers = {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "60",
            "Retry-After": "30"
        }
        self.mock_session.get.return_value = mock_response
        
        # Call the search method and verify exception
        with self.assertRaises(RateLimitError) as context:
            self.api.search_documents(
                provider="public_records",
                search_params={"keyword": "construction"}
            )
        
        # Verify error message contains rate limit information
        error_msg = str(context.exception)
        self.assertIn("Rate limit exceeded", error_msg)
        self.assertIn("Remaining: 0", error_msg)
        self.assertIn("Retry after", error_msg)
    
    def test_get_document_success(self):
        """Test getting a document successfully."""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "doc123",
            "title": "Building Permit",
            "description": "New commercial building",
            "issue_date": "2025-01-15"
        }
        self.mock_session.get.return_value = mock_response
        
        # Call the get_document method
        result = self.api.get_document(
            provider="public_records",
            document_id="doc123"
        )
        
        # Verify result
        self.assertEqual(result["id"], "doc123")
        self.assertEqual(result["title"], "Building Permit")
        
        # Verify correct URL was used
        self.mock_session.get.assert_called_once()
        call_args = self.mock_session.get.call_args
        url = call_args[0][0]
        
        self.assertTrue(url.endswith("api/v1/documents/doc123"))
    
    def test_get_document_not_found(self):
        """Test getting a document that doesn't exist."""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Document not found"
        self.mock_session.get.return_value = mock_response
        
        # Call the get_document method and verify exception
        with self.assertRaises(DocumentNotFoundError):
            self.api.get_document(
                provider="public_records",
                document_id="nonexistent"
            )
    
    @patch('perera_lead_scraper.legal.document_parser.DocumentParser.parse_content')
    def test_extract_text_from_document(self, mock_parse_content):
        """Test extracting text from a document."""
        # Configure mocks
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_response.content = b"PDF content"
        self.mock_session.get.return_value = mock_response
        
        # Configure parser mock
        mock_parse_content.return_value = "Extracted document text"
        
        # Call the extract_text method
        result = self.api.extract_text_from_document(
            provider="public_records",
            document_id="doc123"
        )
        
        # Verify result
        self.assertEqual(result, "Extracted document text")
        
        # Verify correct URL was used and parser was called
        self.mock_session.get.assert_called_once()
        call_args = self.mock_session.get.call_args
        url = call_args[0][0]
        
        self.assertTrue(url.endswith("api/v1/documents/doc123/download?format=pdf"))
        mock_parse_content.assert_called_once_with(b"PDF content", "pdf")
    
    def test_fetch_recent_documents(self):
        """Test fetching recent documents."""
        # Configure mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "permits": [
                {"id": "permit1", "title": "Permit 1"},
                {"id": "permit2", "title": "Permit 2"}
            ]
        }
        self.mock_session.get.return_value = mock_response
        
        # Call the fetch_recent_documents method
        results = self.api.fetch_recent_documents(
            provider="permit_data",
            document_type="building",
            location="San Francisco",
            days=14
        )
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], "permit1")
        
        # Verify correct parameters were used
        self.mock_session.get.assert_called_once()
        call_args = self.mock_session.get.call_args
        params = call_args[1]["params"]
        
        self.assertEqual(params["permit_type"], "building")
        self.assertEqual(params["jurisdiction"], "San Francisco")
        self.assertIn("issue_date_from", params)
        self.assertIn("issue_date_to", params)
    

if __name__ == "__main__":
    unittest.main()
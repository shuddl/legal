"""Unit tests for the LeadEnricher class."""

import unittest
from unittest.mock import patch, MagicMock, Mock
import json
import os
from datetime import datetime
from bs4 import BeautifulSoup

# Import the LeadEnricher class
from perera_lead_scraper.enrichment.enrichment import LeadEnricher, EnrichmentError

class TestLeadEnricher(unittest.TestCase):
    """Tests for the LeadEnricher class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock config object
        self.mock_config = MagicMock()
        self.mock_config.get.return_value = None
        
        # Create enricher with mocked dependencies
        with patch('perera_lead_scraper.enrichment.enrichment.NLPProcessor'), \
             patch('perera_lead_scraper.enrichment.enrichment.LocalStorage'), \
             patch('perera_lead_scraper.enrichment.enrichment.requests.Session'):
            self.enricher = LeadEnricher(self.mock_config)
            
            # Mock the session
            self.enricher.session = MagicMock()
            self.enricher.session.get.return_value = MagicMock()
            
            # Setup cache for testing
            self.enricher.cache_enabled = True
            self.enricher.cache = {}
    
    def test_enrich_lead_success(self):
        """Test the enrich_lead method with a valid lead."""
        # Sample lead for testing
        lead = {
            "id": "test123",
            "title": "New Office Building Construction",
            "description": "Construction of a 5-story office building in downtown Seattle",
            "organization": "Acme Construction",
            "location": "Seattle, WA",
            "project_type": "Commercial",
            "project_value": "5000000"
        }
        
        # Mock all the component methods
        with patch.object(self.enricher, 'lookup_company_data') as mock_lookup, \
             patch.object(self.enricher, 'find_company_website') as mock_find_website, \
             patch.object(self.enricher, 'extract_contact_details') as mock_extract, \
             patch.object(self.enricher, 'estimate_company_size') as mock_estimate, \
             patch.object(self.enricher, 'determine_project_stage') as mock_stage, \
             patch.object(self.enricher, 'find_related_projects') as mock_related, \
             patch.object(self.enricher, 'calculate_lead_score') as mock_score:
            
            # Configure mocks
            mock_lookup.return_value = {"name": "Acme Construction", "size": "Medium"}
            mock_find_website.return_value = "https://acmeconstruction.com"
            mock_extract.return_value = [{"name": "John Doe", "email": "john@acmeconstruction.com"}]
            mock_estimate.return_value = "Medium (50-249)"
            mock_stage.return_value = "Pre-Construction"
            mock_related.return_value = [{"title": "Related Project 1"}]
            mock_score.return_value = {"total": 85, "quality": "Excellent"}
            
            # Call the method
            result = self.enricher.enrich_lead(lead)
            
            # Verify results
            self.assertEqual(result["organization"], "Acme Construction")
            self.assertEqual(result["company"]["name"], "Acme Construction")
            self.assertEqual(result["company_url"], "https://acmeconstruction.com")
            self.assertEqual(result["contacts"][0]["name"], "John Doe")
            self.assertEqual(result["company_size"], "Medium (50-249)")
            self.assertEqual(result["project_stage"], "Pre-Construction")
            self.assertEqual(result["related_projects"][0]["title"], "Related Project 1")
            self.assertEqual(result["lead_score"]["total"], 85)
            self.assertEqual(result["enrichment"]["status"], "success")
    
    def test_enrich_lead_partial_failure(self):
        """Test the enrich_lead method with a partial failure."""
        # Sample lead for testing
        lead = {
            "id": "test456",
            "title": "Highway Expansion Project",
            "description": "Expansion of Highway 101 in northern California",
            "organization": "State DOT",
            "location": "California",
            "project_type": "Infrastructure",
            "project_value": "25000000"
        }
        
        # Mock component methods, with one raising an exception
        with patch.object(self.enricher, 'lookup_company_data') as mock_lookup, \
             patch.object(self.enricher, 'find_company_website') as mock_find_website, \
             patch.object(self.enricher, 'extract_contact_details') as mock_extract, \
             patch.object(self.enricher, 'calculate_lead_score') as mock_score:
            
            # Configure mocks - one raises exception
            mock_lookup.return_value = {"name": "State DOT", "size": "Large"}
            mock_find_website.return_value = "https://dot.ca.gov"
            mock_extract.side_effect = EnrichmentError("API error")
            mock_score.return_value = {"total": 65, "quality": "Good"}
            
            # Call the method
            result = self.enricher.enrich_lead(lead)
            
            # Verify partial enrichment succeeded
            self.assertEqual(result["organization"], "State DOT")
            self.assertEqual(result["company"]["name"], "State DOT")
            self.assertEqual(result["company_url"], "https://dot.ca.gov")
            self.assertEqual(result["lead_score"]["total"], 65)
            self.assertEqual(result["enrichment"]["status"], "partial")
            self.assertIn("error", result["enrichment"])
    
    def test_enrich_leads_batch(self):
        """Test the enrich_leads method with multiple leads."""
        # Sample batch of leads
        leads = [
            {
                "id": "batch1",
                "title": "Residential Development",
                "organization": "HomeBuilders Inc"
            },
            {
                "id": "batch2",
                "title": "Shopping Mall Renovation",
                "organization": "Mall Properties LLC"
            }
        ]
        
        # Mock the enrich_lead method
        with patch.object(self.enricher, 'enrich_lead') as mock_enrich:
            # Configure mock to return different values for each lead
            mock_enrich.side_effect = [
                {
                    "id": "batch1",
                    "title": "Residential Development",
                    "organization": "HomeBuilders Inc",
                    "enrichment": {"status": "success"}
                },
                {
                    "id": "batch2",
                    "title": "Shopping Mall Renovation",
                    "organization": "Mall Properties LLC",
                    "enrichment": {"status": "success"}
                }
            ]
            
            # Call the method
            result = self.enricher.enrich_leads(leads)
            
            # Verify results
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["id"], "batch1")
            self.assertEqual(result[1]["id"], "batch2")
            self.assertEqual(result[0]["enrichment"]["status"], "success")
            self.assertEqual(result[1]["enrichment"]["status"], "success")
    
    def test_lookup_company_data(self):
        """Test the lookup_company_data method."""
        # Mock the _lookup_company_from_provider method
        with patch.object(self.enricher, '_lookup_company_from_provider') as mock_lookup:
            # Configure mock
            mock_lookup.return_value = {
                "name": "Test Company",
                "description": "A test company",
                "website": "https://testcompany.com",
                "industry": "Technology",
                "size": 150,
                "source": "company_data",
                "confidence": 0.9
            }
            
            # Set credentials to include provider
            self.enricher.credentials = {"company_data": {"base_url": "https://api.example.com"}}
            
            # Call the method
            result = self.enricher.lookup_company_data("Test Company", "New York")
            
            # Verify results
            self.assertEqual(result["name"], "Test Company")
            self.assertEqual(result["website"], "https://testcompany.com")
            self.assertEqual(result["industry"], "Technology")
            self.assertEqual(result["size"], 150)
            self.assertEqual(result["source"], "company_data")
            
            # Verify the cache was used on second call
            self.enricher.lookup_company_data("Test Company", "New York")
            mock_lookup.assert_called_once()
    
    def test_find_company_website(self):
        """Test the find_company_website method."""
        # First mock the company data lookup to return a website
        with patch.object(self.enricher, 'lookup_company_data') as mock_lookup:
            mock_lookup.return_value = {
                "name": "Website Test",
                "website": "https://websitetest.com"
            }
            
            # Call the method
            result = self.enricher.find_company_website("Website Test", "Chicago")
            
            # Verify result
            self.assertEqual(result, "https://websitetest.com")
    
    def test_extract_contact_details(self):
        """Test the extract_contact_details method."""
        # Mock the _find_contacts_from_api method
        with patch.object(self.enricher, '_find_contacts_from_api') as mock_api_contacts:
            # Configure mock
            mock_api_contacts.return_value = [
                {
                    "name": "John Smith",
                    "title": "CEO",
                    "email": "john@example.com",
                    "confidence": 0.9
                }
            ]
            
            # Call the method
            result = self.enricher.extract_contact_details("https://example.com", "Example Inc")
            
            # Verify results
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["name"], "John Smith")
            self.assertEqual(result[0]["title"], "CEO")
            self.assertEqual(result[0]["email"], "john@example.com")
            
            # Verify cache works on second call
            self.enricher.extract_contact_details("https://example.com", "Example Inc")
            mock_api_contacts.assert_called_once()
    
    def test_estimate_company_size(self):
        """Test the estimate_company_size method."""
        # Test with company data containing size information
        company_data = {"size": 250}
        result = self.enricher.estimate_company_size("Size Test Inc", company_data)
        self.assertEqual(result, "Large (250-999)")
        
        # Test with string size
        company_data = {"size": "Medium"}
        result = self.enricher.estimate_company_size("Size Test Inc", company_data)
        self.assertEqual(result, "Medium")
    
    def test_determine_project_stage(self):
        """Test the determine_project_stage method."""
        # Lead with explicit stage mention in title
        lead = {
            "title": "Construction Phase: Downtown Office Tower",
            "description": "The project is progressing with foundation work."
        }
        result = self.enricher.determine_project_stage(lead)
        self.assertEqual(result, "Construction")
        
        # Lead with stage keywords in description
        lead = {
            "title": "New Highway Interchange",
            "description": "The design phase has been completed and bids are now being accepted."
        }
        result = self.enricher.determine_project_stage(lead)
        self.assertEqual(result, "Bidding")
    
    def test_calculate_lead_score(self):
        """Test the calculate_lead_score method."""
        # High-quality lead with all information
        lead = {
            "title": "Major Hospital Expansion",
            "description": "Expansion of Memorial Hospital adding 50,000 sq ft and 100 beds",
            "organization": "Memorial Healthcare",
            "location": "Chicago, IL",
            "project_type": "Healthcare",
            "project_value": 50000000,
            "project_stage": "Pre-Construction",
            "company": {
                "name": "Memorial Healthcare",
                "website": "https://memorial.org",
                "description": "Leading healthcare provider",
                "size": "Large"
            },
            "company_url": "https://memorial.org",
            "contacts": [
                {
                    "name": "Jane Doe",
                    "title": "Facilities Director",
                    "email": "jane@memorial.org",
                    "phone": "555-123-4567"
                }
            ]
        }
        
        # Set up target markets/sectors in config
        self.mock_config.get.side_effect = lambda key, default=None: {
            "target_markets": ["Chicago", "New York", "Los Angeles"],
            "target_sectors": ["Healthcare", "Education", "Commercial"]
        }.get(key, default)
        
        # Calculate score
        result = self.enricher.calculate_lead_score(lead)
        
        # Check results
        self.assertGreaterEqual(result["total"], 75)  # Should be a high score
        self.assertEqual(result["quality"], "Excellent")
        self.assertIn("components", result)
        self.assertGreaterEqual(result["components"]["company_data"], 10)
        self.assertGreaterEqual(result["components"]["contact_details"], 15)
        self.assertGreaterEqual(result["components"]["project_value"], 10)

if __name__ == '__main__':
    unittest.main()
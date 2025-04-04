"""Unit tests for the legal document analyzer module."""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import os
import json
from pathlib import Path

from src.perera_lead_scraper.legal.legal_document_analyzer import (
    LegalDocumentAnalyzer,
    DocumentAnalysisError,
    LeadExtractionError
)
from src.perera_lead_scraper.models.lead import Lead, MarketSector


class TestLegalDocumentAnalyzer(unittest.TestCase):
    """Test cases for the LegalDocumentAnalyzer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock config
        self.mock_config = MagicMock()
        self.mock_config.get = MagicMock(return_value=0.6)
        
        # Create mock components
        self.mock_legal_processor = MagicMock()
        self.mock_document_parser = MagicMock()
        self.mock_document_validator = MagicMock()
        self.mock_nlp_processor = MagicMock()
        self.mock_legal_api = MagicMock()
        
        # Sample test data
        self.sample_document_text = """
        BUILDING PERMIT
        Permit #: BLD-2023-12345
        Property Address: 123 Main St, Los Angeles, CA 90001
        Description of Work: New construction of a 3-story commercial office building
        with 25,000 square feet. Project includes parking garage and retail space on
        ground floor.
        Estimated Value: $12,500,000
        Owner: ABC Development Corp
        Contractor: XYZ Construction
        Issue Date: 06/15/2023
        """
        
        # Create analyzer with mocked components
        with patch('src.perera_lead_scraper.legal.legal_document_analyzer.LegalProcessor') as mock_legal_processor_cls, \
             patch('src.perera_lead_scraper.legal.legal_document_analyzer.DocumentParser') as mock_document_parser_cls, \
             patch('src.perera_lead_scraper.legal.legal_document_analyzer.DocumentValidator') as mock_document_validator_cls, \
             patch('src.perera_lead_scraper.legal.legal_document_analyzer.NLPProcessor') as mock_nlp_processor_cls, \
             patch('src.perera_lead_scraper.legal.legal_document_analyzer.LegalAPI') as mock_legal_api_cls:
            
            mock_legal_processor_cls.return_value = self.mock_legal_processor
            mock_document_parser_cls.return_value = self.mock_document_parser
            mock_document_validator_cls.return_value = self.mock_document_validator
            mock_nlp_processor_cls.return_value = self.mock_nlp_processor
            mock_legal_api_cls.return_value = self.mock_legal_api
            
            self.analyzer = LegalDocumentAnalyzer(self.mock_config)
    
    def test_initialization(self):
        """Test analyzer initialization."""
        self.assertIsNotNone(self.analyzer)
        self.assertEqual(self.analyzer.config, self.mock_config)
        self.assertEqual(self.analyzer.legal_processor, self.mock_legal_processor)
        self.assertEqual(self.analyzer.document_parser, self.mock_document_parser)
        self.assertEqual(self.analyzer.document_validator, self.mock_document_validator)
        self.assertEqual(self.analyzer.nlp_processor, self.mock_nlp_processor)
        self.assertEqual(self.analyzer.legal_api, self.mock_legal_api)
        self.assertTrue(self.analyzer.api_available)
    
    def test_analyze_document_empty(self):
        """Test analyzing an empty document."""
        result = self.analyzer.analyze_document("")
        self.assertIn("error", result)
        self.assertEqual(result["lead_potential"], 0.0)
    
    def test_analyze_document(self):
        """Test document analysis with valid input."""
        # Mock the legal processor response
        self.mock_legal_processor.process_document.return_value = {
            "document_type": "permit",
            "permit_number": "BLD-2023-12345",
            "property_address": "123 Main St, Los Angeles, CA 90001",
            "work_description": "New construction of a 3-story commercial office building",
            "estimated_value": 12500000,
            "relevance_score": 0.85
        }
        
        # Mock the NLP processor response
        self.mock_nlp_processor.process_text.return_value = {
            "entities": {"ORG": ["ABC Development Corp", "XYZ Construction"]},
            "locations": ["Los Angeles", "CA"],
            "project_value": 12500000,
            "market_sector": "COMMERCIAL"
        }
        
        # Analyze document
        result = self.analyzer.analyze_document(
            self.sample_document_text,
            document_type="permit",
            document_source="test"
        )
        
        # Verify results
        self.assertIn("lead_potential", result)
        self.assertGreaterEqual(result["lead_potential"], 0.0)
        self.assertLessEqual(result["lead_potential"], 1.0)
        self.assertIn("lead_category", result)
        self.assertIn("meets_requirements", result)
        self.assertIn("document_source", result)
        self.assertEqual(result["document_source"], "test")
        
        # Verify component calls
        self.mock_legal_processor.process_document.assert_called_once_with(
            self.sample_document_text, "permit"
        )
        self.mock_nlp_processor.process_text.assert_called_once_with(
            self.sample_document_text
        )
    
    def test_analyze_document_error(self):
        """Test handling of processing errors during document analysis."""
        # Mock an error in the legal processor
        self.mock_legal_processor.process_document.side_effect = Exception("Processing error")
        
        # Test that the error is properly caught and raised
        with self.assertRaises(DocumentAnalysisError):
            self.analyzer.analyze_document(self.sample_document_text)
    
    def test_extract_leads_from_document_meets_requirements(self):
        """Test lead extraction when document meets requirements."""
        # Mock the analyze_document method
        self.analyzer.analyze_document = MagicMock(return_value={
            "document_type": "permit",
            "permit_number": "BLD-2023-12345",
            "property_address": "123 Main St, Los Angeles, CA 90001",
            "work_description": "New construction of a 3-story commercial office building",
            "estimated_value": 12500000,
            "project_value": 12500000,
            "lead_potential": 0.85,
            "meets_requirements": True,
            "locations": ["Los Angeles", "CA"],
            "market_sector": "COMMERCIAL"
        })
        
        # Extract lead
        lead = self.analyzer.extract_leads_from_document(
            self.sample_document_text,
            document_type="permit",
            document_source="test",
            document_id="doc123"
        )
        
        # Verify lead
        self.assertIsNotNone(lead)
        self.assertIsInstance(lead, Lead)
        self.assertEqual(lead.source, "test")
        self.assertEqual(lead.source_id, "doc123")
        self.assertIn("Building Permit", lead.title)
        self.assertEqual(lead.market_sector, "COMMERCIAL")
        self.assertEqual(lead.project_value, 12500000)
        self.assertEqual(lead.confidence, 0.85)
    
    def test_extract_leads_from_document_does_not_meet_requirements(self):
        """Test lead extraction when document doesn't meet requirements."""
        # Mock the analyze_document method
        self.analyzer.analyze_document = MagicMock(return_value={
            "document_type": "permit",
            "lead_potential": 0.3,
            "meets_requirements": False
        })
        
        # Extract lead
        lead = self.analyzer.extract_leads_from_document(
            self.sample_document_text,
            document_type="permit"
        )
        
        # Verify no lead returned
        self.assertIsNone(lead)
    
    def test_batch_analyze_documents(self):
        """Test batch document analysis."""
        # Create sample documents
        documents = [
            {"text": "Sample doc 1", "type": "permit", "source": "test", "id": "doc1"},
            {"text": "Sample doc 2", "type": "contract", "source": "test", "id": "doc2"}
        ]
        
        # Mock analyze_document to return different results for each document
        self.analyzer.analyze_document = MagicMock(side_effect=[
            {"document_type": "permit", "lead_potential": 0.8, "meets_requirements": True},
            {"document_type": "contract", "lead_potential": 0.4, "meets_requirements": False}
        ])
        
        # Batch analyze
        results = self.analyzer.batch_analyze_documents(documents)
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["document_id"], "doc1")
        self.assertEqual(results[0]["lead_potential"], 0.8)
        self.assertEqual(results[1]["document_id"], "doc2")
        self.assertEqual(results[1]["lead_potential"], 0.4)
    
    @patch('src.perera_lead_scraper.legal.legal_document_analyzer.Path')
    def test_extract_leads_from_local_documents(self, mock_path):
        """Test extracting leads from local documents."""
        # Create mock path and glob result
        mock_path_instance = MagicMock()
        mock_path.return_value = mock_path_instance
        mock_path_instance.exists.return_value = True
        mock_path_instance.is_dir.return_value = True
        
        # Mock file paths
        mock_file1 = MagicMock()
        mock_file1.name = "permit1.pdf"
        mock_file2 = MagicMock()
        mock_file2.name = "contract1.pdf"
        mock_path_instance.glob.return_value = [mock_file1, mock_file2]
        
        # Mock is_supported_format
        self.mock_document_parser.is_supported_format.return_value = True
        
        # Mock _process_local_document to return a lead for the first file only
        mock_lead = MagicMock(spec=Lead)
        self.analyzer._process_local_document = MagicMock(side_effect=[mock_lead, None])
        
        # Extract leads
        leads = self.analyzer.extract_leads_from_local_documents("/path/to/documents")
        
        # Verify results
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0], mock_lead)
        self.assertEqual(self.analyzer._process_local_document.call_count, 2)
    
    def test_extract_leads_from_api(self):
        """Test extracting leads from a legal API."""
        # Mock API method responses
        self.mock_legal_api.fetch_recent_documents.return_value = [
            {"id": "doc1", "document_type": "permit"},
            {"id": "doc2", "document_type": "contract"}
        ]
        
        # Mock _process_api_document to return a lead for the first document only
        mock_lead = MagicMock(spec=Lead)
        self.analyzer._process_api_document = MagicMock(side_effect=[mock_lead, None])
        
        # Mock is_recent_search
        self.analyzer._is_recent_search = MagicMock(return_value=False)
        self.analyzer._record_search = MagicMock()
        
        # Extract leads
        leads = self.analyzer.extract_leads_from_api(
            provider="public_records",
            location="Los Angeles"
        )
        
        # Verify results
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0], mock_lead)
        self.mock_legal_api.fetch_recent_documents.assert_called_once_with(
            provider="public_records",
            document_type=None,
            location="Los Angeles",
            days=14,
            max_results=50
        )
        self.assertEqual(self.analyzer._process_api_document.call_count, 2)
        self.analyzer._record_search.assert_called_once()
    
    def test_extract_leads_from_api_recent_search(self):
        """Test skipping recent API searches."""
        # Mock is_recent_search to indicate a recent search
        self.analyzer._is_recent_search = MagicMock(return_value=True)
        
        # Extract leads
        leads = self.analyzer.extract_leads_from_api(
            provider="public_records",
            location="Los Angeles"
        )
        
        # Verify no API call was made
        self.assertEqual(len(leads), 0)
        self.mock_legal_api.fetch_recent_documents.assert_not_called()
    
    def test_discover_leads_from_multiple_sources(self):
        """Test discovering leads from multiple configured sources."""
        # Mock _load_discovery_config
        self.analyzer._load_discovery_config = MagicMock(return_value=[
            {
                "source_type": "local",
                "path": "/path/to/documents",
                "name": "Local Documents"
            },
            {
                "source_type": "api",
                "api_provider": "public_records",
                "location": "Los Angeles",
                "name": "LA Public Records"
            }
        ])
        
        # Mock lead extraction methods
        local_leads = [MagicMock(spec=Lead), MagicMock(spec=Lead)]
        api_leads = [MagicMock(spec=Lead)]
        
        self.analyzer.extract_leads_from_local_documents = MagicMock(return_value=local_leads)
        self.analyzer.extract_leads_from_api = MagicMock(return_value=api_leads)
        
        # Discover leads
        leads = self.analyzer.discover_leads_from_multiple_sources()
        
        # Verify results
        self.assertEqual(len(leads), 3)  # 2 local + 1 API
        self.analyzer.extract_leads_from_local_documents.assert_called_once_with("/path/to/documents")
        self.analyzer.extract_leads_from_api.assert_called_once_with(
            provider="public_records",
            document_type=None,
            location="Los Angeles",
            days=14,
            max_results=50
        )
    
    def test_contains_exclusions(self):
        """Test exclusion keyword checking."""
        # Set exclusion keywords
        self.analyzer.exclusion_keywords = ["demolition only", "temporary", "minor alterations"]
        
        # Test document with exclusion
        text_with_exclusion = "This is a minor alterations project for the kitchen."
        self.assertTrue(self.analyzer._contains_exclusions(text_with_exclusion))
        
        # Test document without exclusion
        text_without_exclusion = "This is a major renovation project for the building."
        self.assertFalse(self.analyzer._contains_exclusions(text_without_exclusion))
    
    def test_passes_value_check(self):
        """Test project value threshold checking."""
        # Set value threshold
        self.analyzer.value_threshold = 100000
        
        # Test project with value above threshold
        analysis_above_threshold = {"project_value": 500000}
        self.assertTrue(self.analyzer._passes_value_check(analysis_above_threshold))
        
        # Test project with value below threshold
        analysis_below_threshold = {"project_value": 50000}
        self.assertFalse(self.analyzer._passes_value_check(analysis_below_threshold))
        
        # Test project with no value but high lead potential
        analysis_no_value_high_potential = {"lead_potential": 0.8}
        self.assertTrue(self.analyzer._passes_value_check(analysis_no_value_high_potential))
        
        # Test project with no value and low lead potential
        analysis_no_value_low_potential = {"lead_potential": 0.3}
        self.assertFalse(self.analyzer._passes_value_check(analysis_no_value_low_potential))


if __name__ == '__main__':
    unittest.main()
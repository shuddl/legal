"""Unit tests for the legal processor module."""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import tempfile
import os
from pathlib import Path

# Mock NLPProcessor to avoid import issues
class MockNLPProcessor:
    def __init__(self, config):
        pass
    
    def process_text(self, text):
        return {
            'entities': {
                'organizations': ['Acme Construction'],
                'people': ['John Doe'],
                'locations': ['123 Main St']
            },
            'locations': ['123 Main St, Anytown, CA'],
            'project_value': 500000.0,
            'market_sector': 'commercial',
            'relevance_score': 0.8,
            'document_type': 'permit' if 'permit' in text.lower() else 'contract' if 'contract' in text.lower() else None
        }

# Create a patch for the import
with patch('src.perera_lead_scraper.legal.legal_processor.NLPProcessor', MockNLPProcessor):
    from src.perera_lead_scraper.legal.legal_processor import (
        LegalProcessor,
        LegalDocumentError,
        ParseError,
        ValidationError
    )
from src.perera_lead_scraper.config import AppConfig


class TestLegalProcessor(unittest.TestCase):
    """Test cases for the LegalProcessor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock config
        self.mock_config = MagicMock(spec=AppConfig)
        self.mock_config.get.return_value = 'config/legal_patterns.json'
        
        # Create a temporary patterns file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.patterns_path = Path(self.temp_dir.name) / 'legal_patterns.json'
        
        # Sample patterns for testing
        self.test_patterns = {
            "type_indicators": {
                "permit": ["building permit", "work description"],
                "contract": ["construction contract", "agreement between"],
                "zoning": ["zoning application", "variance request"],
                "regulatory": ["environmental impact", "regulatory approval"]
            },
            "permit": {
                "permit_number": ["permit\\s*#?\\s*(\\w+-?\\w*)"],
                "work_description": ["description\\s*of\\s*work\\s*:?\\s*(.+?(?:\\n\\s*\\n|$))"]
            },
            "contract": {
                "parties": ["between\\s+(.+?)\\s+and\\s+(.+?)(?:\\s+dated|\\.|\"|$)"]
            }
        }
        
        with open(self.patterns_path, 'w') as f:
            json.dump(self.test_patterns, f)
        
        # Update mock config to use our temporary file
        self.mock_config.get.return_value = str(self.patterns_path)
        
        # Create processor instance
        with patch('src.perera_lead_scraper.legal.legal_processor.NLPProcessor', MockNLPProcessor):
            self.processor = LegalProcessor(self.mock_config)
            # Replace loaded patterns with our test patterns
            self.processor.patterns = self.test_patterns
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.temp_dir.cleanup()
    
    def test_initialization(self):
        """Test processor initialization."""
        self.assertIsNotNone(self.processor)
        self.assertEqual(self.processor.config, self.mock_config)
        self.assertEqual(self.processor.patterns, self.test_patterns)
    
    def test_identify_document_type_permit(self):
        """Test document type identification for permits."""
        text = "This is a building permit application for 123 Main St."
        doc_type = self.processor._identify_document_type(text)
        self.assertEqual(doc_type, "permit")
    
    def test_identify_document_type_contract(self):
        """Test document type identification for contracts."""
        text = "This construction contract is made between ABC Corp and XYZ Ltd."
        doc_type = self.processor._identify_document_type(text)
        self.assertEqual(doc_type, "contract")
    
    def test_identify_document_type_unknown(self):
        """Test document type identification for unknown types."""
        text = "This document contains no specific indicators of its type."
        doc_type = self.processor._identify_document_type(text)
        self.assertEqual(doc_type, "unknown")
    
    def test_extract_permit_info(self):
        """Test extraction of permit information."""
        text = """
        Building Permit
        Permit #: BP-2025-1234
        
        Property Address: 123 Main St, Anytown CA
        
        Description of Work: Construction of a new 2-story commercial building
        with 5,000 sq ft retail space on first floor and 3,000 sq ft office space
        on second floor.
        
        Estimated Cost: $750,000
        Contractor: ABC Builders Inc.
        """
        
        result = self.processor._extract_permit_info(text)
        
        self.assertEqual(result["permit_number"], "BP-2025-1234")
        self.assertIn("Construction of a new 2-story commercial building", result["work_description"])
    
    def test_extract_contract_info(self):
        """Test extraction of contract information."""
        text = """
        CONSTRUCTION CONTRACT
        
        This agreement made between ABC Development Corp and XYZ Contractors Inc.
        dated this 15th day of March, 2025.
        
        Project: Commercial Office Building at 456 Business Park
        
        Contract Sum: $2,500,000
        
        Completion Date: 12/31/2025
        """
        
        result = self.processor._extract_contract_info(text)
        
        self.assertEqual(result["party_a"], "ABC Development Corp")
        self.assertEqual(result["party_b"], "XYZ Contractors Inc.")
    
    def test_process_document_permit(self):
        """Test processing a permit document."""
        text = """
        Building Permit
        Permit #: BP-2025-1234
        
        Description of Work: Construction of a new commercial building
        """
        
        result = self.processor.process_document(text, "permit")
        
        self.assertEqual(result["document_type"], "permit")
        self.assertEqual(result["permit_number"], "BP-2025-1234")
        self.assertEqual(result["market_sector"], "commercial")
        self.assertEqual(result["project_value"], 500000.0)
        self.assertEqual(result["relevance_score"], 0.8)
        self.assertIn("organizations", result["entities"])
    
    def test_process_document_with_type_detection(self):
        """Test processing a document with automatic type detection."""
        text = """
        Building Permit
        Permit #: BP-2025-1234
        
        Description of Work: Construction of a new commercial building
        """
        
        result = self.processor.process_document(text)  # No type specified
        
        self.assertEqual(result["document_type"], "permit")
        self.assertEqual(result["permit_number"], "BP-2025-1234")
    
    def test_process_document_error(self):
        """Test error handling in document processing."""
        with patch.object(self.processor.nlp_processor, 'process_text', side_effect=Exception("NLP processing failed")):
            text = "Some document text"
            
            with self.assertRaises(ParseError):
                self.processor.process_document(text)
    
    def test_extract_leads_from_documents(self):
        """Test extracting leads from documents."""
        # Setup two test documents
        doc1 = ("""
        Building Permit
        Permit #: BP-2025-1234
        Issue Date: 4/1/2025
        Property Address: 123 Main St, Anytown CA
        
        Description of Work: Construction of a new commercial building
        
        Estimated Cost: $750,000
        """, "permit")
        
        doc2 = ("""
        CONSTRUCTION CONTRACT
        
        This agreement made between ABC Development Corp and XYZ Contractors Inc.
        dated this 15th day of March, 2025.
        
        Project: Commercial Office Building at 456 Business Park
        
        Contract Sum: $2,500,000
        """, "contract")
        
        # Extract leads
        leads = self.processor.extract_leads_from_documents([doc1, doc2])
        
        # Verify results
        self.assertEqual(len(leads), 2)
        
        self.assertEqual(leads[0]["source"], "legal_document")
        self.assertEqual(leads[0]["source_id"], "BP-2025-1234")
        self.assertIn("Building Permit", leads[0]["title"])
        
        self.assertEqual(leads[1]["source"], "legal_document")
        self.assertIn("Contract", leads[1]["title"])
        self.assertIn("ABC Development Corp", leads[1]["description"])
    
    def test_batch_process(self):
        """Test batch processing of documents."""
        # Setup test documents
        doc1 = ("Building Permit #BP-12345", "permit")
        doc2 = ("Agreement between A and B", "contract")
        doc3 = ("Invalid document that will cause an error", "unknown")
        
        # Mock to make the third document fail
        with patch.object(self.processor, '_extract_generic_info', side_effect=lambda text: 
                        {'error': 'Test error'} if "Invalid document" in text else {}):
            
            # Batch process
            with patch.object(self.processor, 'process_document', side_effect=lambda text, doc_type: 
                            {'document_type': doc_type} if not "Invalid document" in text 
                            else exec('raise Exception("Test error")')):
                
                results = self.processor.batch_process([doc1, doc2, doc3])
                
                # Verify results
                self.assertEqual(len(results), 3)
                self.assertEqual(results[0]["document_type"], "permit")
                self.assertEqual(results[1]["document_type"], "contract")
                self.assertIn("error", results[2])
    
    def test_generate_lead_title(self):
        """Test lead title generation."""
        # Test with project name
        doc1 = {"project_name": "New Office Building", "document_type": "contract"}
        title1 = self.processor._generate_lead_title(doc1)
        self.assertEqual(title1, "New Office Building")
        
        # Test without project name, permit type
        doc2 = {
            "document_type": "permit", 
            "work_description": "Construction of a 3-story commercial building with retail on ground floor"
        }
        title2 = self.processor._generate_lead_title(doc2)
        self.assertTrue(title2.startswith("Building Permit:"))
        self.assertIn("commercial building", title2)
        
        # Test with long description that needs truncation
        doc3 = {
            "document_type": "permit", 
            "work_description": "This is a very long description that should be truncated because it exceeds the maximum length for a title and would look bad in the UI if we showed the whole thing"
        }
        title3 = self.processor._generate_lead_title(doc3)
        self.assertIn("...", title3)
        self.assertLessEqual(len(title3), 70)  # Ensure it was truncated
    
    def test_generate_lead_description(self):
        """Test lead description generation."""
        # Test permit description
        doc1 = {
            "document_type": "permit",
            "work_description": "New commercial building",
            "estimated_value": 750000,
            "contractor": "ABC Builders",
            "property_address": "123 Main St",
            "permit_number": "BP-2025-1234",
            "issue_date": "4/1/2025"
        }
        desc1 = self.processor._generate_lead_description(doc1)
        self.assertIn("Work Description: New commercial building", desc1)
        self.assertIn("Estimated Value: $750,000.00", desc1)
        self.assertIn("Contractor: ABC Builders", desc1)
        self.assertIn("Location: 123 Main St", desc1)
        self.assertIn("Permit #: BP-2025-1234", desc1)
        self.assertIn("Issued: 4/1/2025", desc1)
        
        # Test contract description
        doc2 = {
            "document_type": "contract",
            "party_a": "ABC Development",
            "party_b": "XYZ Contractors",
            "project_name": "New Office Complex",
            "contract_amount": 2500000,
            "completion_date": "12/31/2025",
            "contract_date": "3/15/2025"
        }
        desc2 = self.processor._generate_lead_description(doc2)
        self.assertIn("Contract between ABC Development and XYZ Contractors", desc2)
        self.assertIn("Project: New Office Complex", desc2)
        self.assertIn("Contract Amount: $2,500,000.00", desc2)
        self.assertIn("Completion Date: 12/31/2025", desc2)
        self.assertIn("Contract Date: 3/15/2025", desc2)


if __name__ == '__main__':
    unittest.main()
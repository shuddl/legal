"""Unit tests for the document validator module."""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import tempfile
import os
from pathlib import Path

from src.perera_lead_scraper.legal.document_validator import (
    DocumentValidator,
    DocumentValidationError
)
from src.perera_lead_scraper.config import Config


class TestDocumentValidator(unittest.TestCase):
    """Test cases for the DocumentValidator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock config
        self.mock_config = MagicMock(spec=Config)
        self.mock_config.get.return_value = 'config/legal_validation_rules.json'
        
        # Create a temporary validation rules file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.rules_path = Path(self.temp_dir.name) / 'legal_validation_rules.json'
        
        # Sample validation rules for testing
        self.test_rules = {
            "document_types": ["permit", "contract", "zoning", "regulatory"],
            "required_fields": {
                "permit": [
                    {"field": "permit_number", "regex": "\\S+"},
                    {"field": "work_description", "regex": ".+", "min_length": 10}
                ],
                "contract": [
                    {"field": "party_a", "regex": ".+"},
                    {"field": "party_b", "regex": ".+"}
                ]
            },
            "min_content_length": 200
        }
        
        with open(self.rules_path, 'w') as f:
            json.dump(self.test_rules, f)
        
        # Update mock config to use our temporary file
        self.mock_config.get.return_value = str(self.rules_path)
        
        # Create validator instance
        self.validator = DocumentValidator(self.mock_config)
        # Replace loaded rules with our test rules
        self.validator.rules = self.test_rules
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.temp_dir.cleanup()
    
    def test_initialization(self):
        """Test validator initialization."""
        self.assertIsNotNone(self.validator)
        self.assertEqual(self.validator.config, self.mock_config)
        self.assertEqual(self.validator.rules, self.test_rules)
    
    def test_get_default_rules(self):
        """Test that default rules are loaded correctly."""
        default_rules = self.validator._get_default_rules()
        self.assertIn("document_types", default_rules)
        self.assertIn("required_fields", default_rules)
        self.assertIn("min_content_length", default_rules)
        self.assertIn("permit", default_rules["required_fields"])
        self.assertIn("contract", default_rules["required_fields"])
        self.assertIn("zoning", default_rules["required_fields"])
        self.assertIn("regulatory", default_rules["required_fields"])
    
    def test_validate_minimum_length(self):
        """Test validation of minimum document length."""
        # Document is too short
        short_text = "This document is too short."
        with self.assertRaises(DocumentValidationError) as context:
            self.validator.validate_document(short_text, "permit")
        self.assertIn("too short", str(context.exception))
        
        # Document meets minimum length
        long_text = "A" * 201
        result = self.validator.validate_document(long_text, "unknown")
        self.assertTrue(result)
    
    def test_validate_unknown_type(self):
        """Test validation of documents with unknown type."""
        text = "A" * 201  # Ensure it meets minimum length
        result = self.validator.validate_document(text, "unknown")
        self.assertTrue(result)
    
    def test_validate_unsupported_type(self):
        """Test validation of documents with unsupported type."""
        text = "A" * 201  # Ensure it meets minimum length
        result = self.validator.validate_document(text, "unsupported_type")
        self.assertTrue(result)
    
    def test_validate_permit(self):
        """Test validation of permit documents."""
        # Valid permit
        valid_permit = """
        Building Permit
        Permit #: BP-2025-1234
        
        Description of Work: Construction of a new 2-story commercial building
        with 5,000 sq ft retail space on first floor and 3,000 sq ft office space
        on second floor.
        """
        
        # Ensure it meets minimum length
        valid_permit = valid_permit + "A" * 100
        
        result = self.validator.validate_document(valid_permit, "permit")
        self.assertTrue(result)
        
        # Invalid permit (missing permit number)
        invalid_permit = """
        Building Permit
        
        Description of Work: Construction of a new 2-story commercial building.
        """
        
        # Ensure it meets minimum length
        invalid_permit = invalid_permit + "A" * 100
        
        with self.assertRaises(DocumentValidationError) as context:
            self.validator.validate_document(invalid_permit, "permit")
        self.assertIn("permit_number", str(context.exception))
        
        # Invalid permit (work description too short)
        invalid_permit2 = """
        Building Permit
        Permit #: BP-2025-1234
        
        Description of Work: Too short
        """
        
        # Ensure it meets minimum length
        invalid_permit2 = invalid_permit2 + "A" * 100
        
        with self.assertRaises(DocumentValidationError) as context:
            self.validator.validate_document(invalid_permit2, "permit")
        self.assertIn("too short", str(context.exception))
    
    def test_validate_contract(self):
        """Test validation of contract documents."""
        # Valid contract
        valid_contract = """
        CONSTRUCTION CONTRACT
        
        This agreement made between ABC Development Corp and XYZ Contractors Inc.
        dated this 15th day of March, 2025.
        """
        
        # Ensure it meets minimum length
        valid_contract = valid_contract + "A" * 100
        
        result = self.validator.validate_document(valid_contract, "contract")
        self.assertTrue(result)
        
        # Invalid contract (missing parties)
        invalid_contract = """
        CONSTRUCTION CONTRACT
        
        This document outlines the terms of construction
        """
        
        # Ensure it meets minimum length
        invalid_contract = invalid_contract + "A" * 100
        
        with self.assertRaises(DocumentValidationError) as context:
            self.validator.validate_document(invalid_contract, "contract")
        self.assertIn("party_a", str(context.exception))
    
    def test_get_validation_summary(self):
        """Test getting detailed validation summary."""
        # Valid document
        valid_document = """
        Building Permit
        Permit #: BP-2025-1234
        
        Description of Work: Construction of a new 2-story commercial building
        with 5,000 sq ft retail space on first floor and 3,000 sq ft office space
        on second floor.
        """
        
        # Ensure it meets minimum length
        valid_document = valid_document + "A" * 100
        
        summary = self.validator.get_validation_summary(valid_document, "permit")
        
        self.assertTrue(summary["valid"])
        self.assertEqual(summary["document_type"], "permit")
        self.assertGreaterEqual(summary["length"], 200)
        self.assertIn("passed all validation checks", summary["issues"][0])
        
        # Check detected fields
        self.assertEqual(len(summary["detected_fields"]), 2)  # Two required fields
        
        permit_number_field = next(f for f in summary["detected_fields"] if f["name"] == "permit_number")
        self.assertTrue(permit_number_field["found"])
        self.assertEqual(permit_number_field["value"], "BP-2025-1234")
        self.assertEqual(len(permit_number_field["issues"]), 0)
        
        # Invalid document
        invalid_document = """
        Building Permit
        
        Description of Work: Too short
        """
        
        # Ensure it meets minimum length
        invalid_document = invalid_document + "A" * 100
        
        summary = self.validator.get_validation_summary(invalid_document, "permit")
        
        self.assertFalse(summary["valid"])
        
        permit_number_field = next(f for f in summary["detected_fields"] if f["name"] == "permit_number")
        self.assertFalse(permit_number_field["found"])
        self.assertIn("Field not found", permit_number_field["issues"][0])
        
        work_desc_field = next(f for f in summary["detected_fields"] if f["name"] == "work_description")
        self.assertTrue(work_desc_field["found"])
        self.assertEqual(work_desc_field["value"], "Too short")
        self.assertIn("too short", work_desc_field["issues"][0])
    
    def test_batch_validate(self):
        """Test batch validation of documents."""
        # Create test documents
        valid_doc = {
            "text": """
            Building Permit
            Permit #: BP-2025-1234
            
            Description of Work: Construction of a new 2-story commercial building
            with 5,000 sq ft retail space on first floor and 3,000 sq ft office space
            on second floor.
            """ + "A" * 100,  # Ensure it meets minimum length
            "type": "permit"
        }
        
        invalid_doc = {
            "text": """
            Building Permit
            
            Description of Work: Too short
            """ + "A" * 100,  # Ensure it meets minimum length
            "type": "permit"
        }
        
        error_doc = {
            "text": "Too short",
            "type": "permit"
        }
        
        # Batch validate
        results = self.validator.batch_validate([valid_doc, invalid_doc, error_doc])
        
        self.assertEqual(len(results), 3)
        
        # Check valid document result
        self.assertTrue(results[0]["valid"])
        self.assertEqual(results[0]["type"], "permit")
        self.assertIsNone(results[0]["error"])
        
        # Check invalid document result
        self.assertFalse(results[1]["valid"])
        self.assertEqual(results[1]["type"], "permit")
        self.assertIn("permit_number", results[1]["error"])
        
        # Check error document result
        self.assertFalse(results[2]["valid"])
        self.assertEqual(results[2]["type"], "permit")
        self.assertIn("too short", results[2]["error"])


if __name__ == '__main__':
    unittest.main()
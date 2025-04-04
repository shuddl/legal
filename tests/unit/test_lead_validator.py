"""
Unit tests for the lead validator module.
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import os
import sys
import json

# Import the modules to test
from perera_lead_scraper.validation.lead_validator import (
    LeadValidator,
    ValidationResult,
    ValidationLevel
)
from perera_lead_scraper.models.lead import Lead, MarketSector

class TestValidationResult(unittest.TestCase):
    """Test the ValidationResult class."""
    
    def test_initialization(self):
        """Test basic initialization of ValidationResult."""
        result = ValidationResult()
        self.assertTrue(result.is_valid)
        self.assertEqual(result.messages, [])
        self.assertEqual(result.confidence_adjustment, 0.0)
        self.assertIsNone(result.normalized_data)
        self.assertEqual(result.level, ValidationLevel.STANDARD)
        
        # Test with parameters
        result = ValidationResult(
            is_valid=False,
            messages=["Test message"],
            confidence_adjustment=-0.1,
            normalized_data="normalized",
            level=ValidationLevel.CRITICAL
        )
        self.assertFalse(result.is_valid)
        self.assertEqual(result.messages, ["Test message"])
        self.assertEqual(result.confidence_adjustment, -0.1)
        self.assertEqual(result.normalized_data, "normalized")
        self.assertEqual(result.level, ValidationLevel.CRITICAL)
    
    def test_append_message(self):
        """Test appending messages to ValidationResult."""
        result = ValidationResult()
        result.append_message("Message 1")
        result.append_message("Message 2")
        
        self.assertEqual(result.messages, ["Message 1", "Message 2"])
    
    def test_merge(self):
        """Test merging two ValidationResults."""
        # Test merging valid results
        result1 = ValidationResult(is_valid=True, messages=["Result 1"], confidence_adjustment=0.1)
        result2 = ValidationResult(is_valid=True, messages=["Result 2"], confidence_adjustment=0.2)
        
        merged = result1.merge(result2)
        self.assertTrue(merged.is_valid)
        self.assertEqual(merged.messages, ["Result 1", "Result 2"])
        self.assertEqual(merged.confidence_adjustment, 0.3)
        self.assertIs(merged, result1)  # Should return self
        
        # Test merging with invalid STANDARD result
        result1 = ValidationResult(is_valid=True, messages=["Result 1"], confidence_adjustment=0.1)
        result2 = ValidationResult(is_valid=False, messages=["Result 2"], confidence_adjustment=-0.2)
        
        merged = result1.merge(result2)
        self.assertFalse(merged.is_valid)
        self.assertEqual(merged.messages, ["Result 1", "Result 2"])
        self.assertEqual(merged.confidence_adjustment, -0.1)
        
        # Test merging with invalid CRITICAL result
        result1 = ValidationResult(is_valid=True, messages=["Result 1"], confidence_adjustment=0.1)
        result2 = ValidationResult(
            is_valid=False, 
            messages=["Critical failure"], 
            confidence_adjustment=-0.2,
            level=ValidationLevel.CRITICAL
        )
        
        merged = result1.merge(result2)
        self.assertFalse(merged.is_valid)
        self.assertEqual(merged.messages, ["Result 1", "Critical failure"])
        self.assertEqual(merged.confidence_adjustment, -0.1)


class TestLeadValidator(unittest.TestCase):
    """Test the LeadValidator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mocks for dependencies
        self.mock_storage = MagicMock()
        self.mock_nlp_processor = MagicMock()
        
        # Configure NLP mock to return valid project intent by default
        self.mock_nlp_processor.analyze_project_intent.return_value = {
            'intent_score': 0.8,
            'indicators': ['construction', 'building', 'project']
        }
        
        # Create test configuration
        self.test_config = {
            'required_fields': ['title', 'source_id', 'description'],
            'min_title_length': 5,
            'min_description_length': 20,
            'duplicate_similarity_threshold': 0.8,
            'publication_date_window_days': 7
        }
        
        # Create validator with mocked dependencies
        self.validator = LeadValidator(
            storage=self.mock_storage,
            nlp_processor=self.mock_nlp_processor,
            config_override=self.test_config
        )
        
        # Set test target markets and sectors
        self.validator.target_markets = ["San Francisco", "Oakland", "Berkeley", "San Jose"]
        self.validator.target_sectors = [sector.value for sector in MarketSector]
        
        # Configure storage mock to return empty list for recent leads by default
        self.mock_storage.get_recent_leads.return_value = []
    
    def test_initialization(self):
        """Test validator initialization."""
        self.assertEqual(self.validator.config['min_title_length'], 5)
        self.assertEqual(self.validator.config['min_description_length'], 20)
        self.assertEqual(len(self.validator.target_markets), 4)
        self.assertEqual(len(self.validator.target_sectors), len(MarketSector))
    
    def test_check_required_fields_valid(self):
        """Test validation of required fields with valid data."""
        lead = Lead(
            title="Test Lead",
            source_id="12345",
            description="This is a test lead with sufficient description length."
        )
        
        result = self.validator.check_required_fields(lead)
        
        self.assertTrue(result.is_valid)
        self.assertGreater(result.confidence_adjustment, 0)
    
    def test_check_required_fields_invalid(self):
        """Test validation of required fields with invalid data."""
        # Missing description
        lead = Lead(
            title="Test Lead",
            source_id="12345",
            description=""
        )
        
        result = self.validator.check_required_fields(lead)
        
        self.assertFalse(result.is_valid)
        self.assertLess(result.confidence_adjustment, 0)
        
        # Short title
        lead = Lead(
            title="Test",  # Less than min_title_length
            source_id="12345",
            description="This is a test lead description."
        )
        
        result = self.validator.check_required_fields(lead)
        
        self.assertTrue(result.is_valid)  # Still valid, but with warning
        self.assertIn("Title too short", result.messages[0])
        self.assertLess(result.confidence_adjustment, 0)
    
    def test_validate_location_in_target(self):
        """Test location validation with locations in target markets."""
        # Exact match
        result = self.validator.validate_location("San Francisco")
        self.assertTrue(result.is_valid)
        self.assertGreater(result.confidence_adjustment, 0)
        
        # Partial match
        result = self.validator.validate_location("Downtown San Francisco")
        self.assertTrue(result.is_valid)
        self.assertGreater(result.confidence_adjustment, 0)
        
        # Case insensitive match
        result = self.validator.validate_location("san francisco")
        self.assertTrue(result.is_valid)
        self.assertGreater(result.confidence_adjustment, 0)
    
    def test_validate_location_not_in_target(self):
        """Test location validation with locations not in target markets."""
        result = self.validator.validate_location("Los Angeles")
        self.assertFalse(result.is_valid)
        self.assertLess(result.confidence_adjustment, 0)
    
    def test_validate_market_sector_valid(self):
        """Test market sector validation with valid sectors."""
        for sector in MarketSector:
            result = self.validator.validate_market_sector(sector.value)
            self.assertTrue(result.is_valid)
            self.assertGreater(result.confidence_adjustment, 0)
        
        # Test case insensitive match
        result = self.validator.validate_market_sector("commercial")
        self.assertTrue(result.is_valid)
        self.assertGreater(result.confidence_adjustment, 0)
    
    def test_validate_market_sector_invalid(self):
        """Test market sector validation with invalid sectors."""
        result = self.validator.validate_market_sector("Unknown Sector")
        self.assertFalse(result.is_valid)
        self.assertLess(result.confidence_adjustment, 0)
    
    def test_validate_contact_info_valid(self):
        """Test contact information validation with valid data."""
        contacts = [
            {
                'name': 'John Doe',
                'email': 'john.doe@example.com',
                'phone': '(555) 123-4567'
            }
        ]
        
        result = self.validator.validate_contact_info(contacts)
        
        self.assertTrue(result.is_valid)
        self.assertGreater(result.confidence_adjustment, 0)
        self.assertEqual(len(result.normalized_data), 1)
    
    def test_validate_contact_info_invalid(self):
        """Test contact information validation with invalid data."""
        contacts = [
            {
                'name': 'John Doe',
                'email': 'invalid-email',  # Invalid email format
                'phone': '(555) 123-4567'
            }
        ]
        
        result = self.validator.validate_contact_info(contacts)
        
        self.assertTrue(result.is_valid)  # Still valid but with warnings
        self.assertIn("invalid email format", result.messages[0].lower())
        self.assertEqual(len(result.normalized_data), 1)  # Still includes the contact with valid fields
    
    def test_check_duplicates_no_duplicates(self):
        """Test duplicate checking with no duplicates."""
        lead = Lead(
            title="Unique Lead",
            description="This is a unique lead description."
        )
        
        # Configure storage mock to return no leads
        self.mock_storage.get_recent_leads.return_value = []
        
        result = self.validator.check_duplicates(lead)
        
        self.assertTrue(result.is_valid)
        self.assertGreater(result.confidence_adjustment, 0)
        self.assertIn("No duplicates", result.messages[0])
    
    def test_check_duplicates_with_duplicates(self):
        """Test duplicate checking with duplicates."""
        lead = Lead(
            title="Duplicate Lead",
            description="This is a lead with potential duplicates."
        )
        
        # Configure storage mock to return similar leads
        similar_lead = Lead(
            id="existing-lead-1",
            title="Duplicate Lead",
            description="This is a lead with potential duplicates."
        )
        self.mock_storage.get_recent_leads.return_value = [similar_lead]
        
        result = self.validator.check_duplicates(lead)
        
        self.assertFalse(result.is_valid)
        self.assertLess(result.confidence_adjustment, 0)
        self.assertIn("Found", result.messages[0])  # Should mention duplicates found
    
    def test_validate_project_timeline_recent(self):
        """Test project timeline validation with recent dates."""
        # Recent publication date
        lead = Lead(
            published_date=datetime.now() - timedelta(days=3)
        )
        
        result = self.validator.validate_project_timeline(lead)
        
        self.assertTrue(result.is_valid)
        self.assertGreater(result.confidence_adjustment, 0)
        self.assertIn("acceptable window", result.messages[0])
    
    def test_validate_project_timeline_old(self):
        """Test project timeline validation with old dates."""
        # Old publication date
        lead = Lead(
            published_date=datetime.now() - timedelta(days=30)
        )
        
        result = self.validator.validate_project_timeline(lead)
        
        self.assertTrue(result.is_valid)  # Still valid but with reduced confidence
        self.assertLess(result.confidence_adjustment, 0)
        self.assertIn("older than", result.messages[0])
    
    def test_check_project_intent_valid(self):
        """Test project intent validation with valid intent."""
        lead = Lead(
            title="Construction Project",
            description="Building a new office in San Francisco."
        )
        
        # Configure NLP mock to return high intent score
        self.mock_nlp_processor.analyze_project_intent.return_value = {
            'intent_score': 0.8,
            'indicators': ['construction', 'building', 'project']
        }
        
        result = self.validator.check_project_intent(lead)
        
        self.assertTrue(result.is_valid)
        self.assertGreater(result.confidence_adjustment, 0)
        self.assertIn("Project intent confirmed", result.messages[0])
    
    def test_check_project_intent_invalid(self):
        """Test project intent validation with insufficient intent."""
        lead = Lead(
            title="General News",
            description="A news article with no construction details."
        )
        
        # Configure NLP mock to return low intent score
        self.mock_nlp_processor.analyze_project_intent.return_value = {
            'intent_score': 0.3,
            'indicators': []
        }
        
        result = self.validator.check_project_intent(lead)
        
        self.assertFalse(result.is_valid)
        self.assertLess(result.confidence_adjustment, 0)
        self.assertIn("Insufficient project intent", result.messages[0])
    
    def test_evaluate_lead_quality(self):
        """Test lead quality evaluation."""
        lead = Lead(
            title="High Quality Lead",
            description="This is a high quality lead with good details.",
            location="San Francisco",
            project_type=MarketSector.COMMERCIAL.value,
            confidence_score=0.8,
            published_date=datetime.now() - timedelta(days=2)
        )
        
        quality_score = self.validator.evaluate_lead_quality(lead)
        
        self.assertGreaterEqual(quality_score, 0.0)
        self.assertLessEqual(quality_score, 1.0)
        self.assertGreater(quality_score, 0.5)  # Should be above average
    
    def test_validate_lead_valid(self):
        """Test full lead validation with valid lead."""
        lead = Lead(
            title="Valid Construction Project",
            source_id="test-1234",
            description="This is a valid construction project in one of our target markets.",
            location="San Francisco",
            project_type=MarketSector.COMMERCIAL.value,
            confidence_score=0.7,
            published_date=datetime.now() - timedelta(days=2)
        )
        
        # Configure NLP mock
        self.mock_nlp_processor.analyze_project_intent.return_value = {
            'intent_score': 0.85,
            'indicators': ['construction', 'building', 'project']
        }
        
        # Configure storage mock
        self.mock_storage.get_recent_leads.return_value = []
        
        # Validate lead
        is_valid, messages, adjusted_confidence = self.validator.validate_lead(lead)
        
        self.assertTrue(is_valid)
        self.assertGreater(adjusted_confidence, lead.confidence_score)
        self.assertGreater(len(messages), 0)
    
    def test_validate_lead_invalid(self):
        """Test full lead validation with invalid lead."""
        lead = Lead(
            title="Invalid Lead",
            source_id="",  # Missing required field
            description="This lead has missing required fields.",
            confidence_score=0.5
        )
        
        # Validate lead
        is_valid, messages, adjusted_confidence = self.validator.validate_lead(lead)
        
        self.assertFalse(is_valid)
        self.assertIn("Missing required field", messages[0])
        self.assertEqual(adjusted_confidence, lead.confidence_score)  # Should not adjust invalid lead's confidence


if __name__ == "__main__":
    unittest.main()
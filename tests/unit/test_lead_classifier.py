#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Unit tests for the Lead Classifier module."""

import unittest
from unittest.mock import patch, MagicMock, Mock
import json
import os
from datetime import datetime

# Import the lead classifier
from perera_lead_scraper.classification.classifier import (
    LeadClassifier, ValueCategory, TimelineCategory, 
    DecisionStage, CompetitionLevel, PriorityLevel, ClassificationError
)
from perera_lead_scraper.models.lead import Lead, MarketSector, Location

class TestLeadClassifier(unittest.TestCase):
    """Tests for the LeadClassifier class and its methods."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock NLP processor
        self.mock_nlp = MagicMock()
        self.mock_nlp.preprocess_text.return_value = "Preprocessed text"
        
        # Test configuration
        self.test_config = {
            "value_tiers": {
                "default": {
                    "small": 2000000,      # $2M
                    "medium": 10000000,    # $10M
                    "large": 50000000      # $50M
                },
                "healthcare": {
                    "small": 5000000,      # $5M
                    "medium": 20000000,    # $20M
                    "large": 100000000     # $100M
                }
            },
            "win_probability_factors": {
                "market_sector_fit": 0.20,
                "geographical_proximity": 0.15,
                "project_size_fit": 0.15,
                "competition_level": 0.20,
                "relationship_strength": 0.15,
                "timeline_alignment": 0.15
            },
            "sector_expertise_levels": {
                "healthcare": 0.9,
                "education": 0.85,
                "commercial": 0.8,
                "other": 0.5
            },
            "strategic_locations": [
                "Los Angeles", "Orange County", "San Diego"
            ],
            "primary_client_list": [
                "Test Client Inc", "Sample Hospital"
            ]
        }
        
        # Initialize classifier with mocks and test config
        self.classifier = LeadClassifier(self.mock_nlp, self.test_config)
    
    def test_categorize_by_value_default_tiers(self):
        """Test value categorization with default tiers."""
        # Test small projects
        category, confidence = self.classifier.categorize_by_value(1000000)
        self.assertEqual(category, ValueCategory.SMALL.value)
        self.assertEqual(confidence, 1.0)
        
        # Test medium projects
        category, confidence = self.classifier.categorize_by_value(5000000)
        self.assertEqual(category, ValueCategory.MEDIUM.value)
        self.assertEqual(confidence, 1.0)
        
        # Test large projects
        category, confidence = self.classifier.categorize_by_value(25000000)
        self.assertEqual(category, ValueCategory.LARGE.value)
        self.assertEqual(confidence, 1.0)
        
        # Test major projects
        category, confidence = self.classifier.categorize_by_value(75000000)
        self.assertEqual(category, ValueCategory.MAJOR.value)
        self.assertEqual(confidence, 1.0)
        
        # Test boundary values with reduced confidence
        category, confidence = self.classifier.categorize_by_value(1900000)  # Close to small/medium boundary
        self.assertEqual(category, ValueCategory.SMALL.value)
        self.assertLess(confidence, 1.0)
    
    def test_categorize_by_value_sector_specific(self):
        """Test value categorization with sector-specific tiers."""
        # Test healthcare sector
        category, confidence = self.classifier.categorize_by_value(4000000, "healthcare")
        self.assertEqual(category, ValueCategory.SMALL.value)
        
        category, confidence = self.classifier.categorize_by_value(15000000, "healthcare")
        self.assertEqual(category, ValueCategory.MEDIUM.value)
        
        category, confidence = self.classifier.categorize_by_value(50000000, "healthcare")
        self.assertEqual(category, ValueCategory.MEDIUM.value)
        
        category, confidence = self.classifier.categorize_by_value(150000000, "healthcare")
        self.assertEqual(category, ValueCategory.MAJOR.value)
        
        # Test invalid value
        with self.assertRaises(ValueError):
            self.classifier.categorize_by_value(-1000)
    
    def test_categorize_by_timeline(self):
        """Test timeline categorization."""
        # Test immediate timeline
        text = "Construction will begin next month with completion expected within 90 days."
        category, confidence, indicators = self.classifier.categorize_by_timeline(text)
        self.assertEqual(category, TimelineCategory.IMMEDIATE.value)
        self.assertGreater(confidence, 0.7)
        self.assertTrue(indicators)
        
        # Test short-term timeline
        text = "Project is scheduled to begin in 4-6 months with Q3 2023 targeted for completion."
        category, confidence, indicators = self.classifier.categorize_by_timeline(text)
        self.assertEqual(category, TimelineCategory.SHORT_TERM.value)
        self.assertGreater(confidence, 0.7)
        self.assertTrue(indicators)
        
        # Test mid-term timeline
        text = "The development is planned for mid-term implementation in the next fiscal year."
        category, confidence, indicators = self.classifier.categorize_by_timeline(text)
        self.assertEqual(category, TimelineCategory.MID_TERM.value)
        self.assertGreater(confidence, 0.7)
        self.assertTrue(indicators)
        
        # Test long-term timeline
        text = "This project is part of the city's long-term vision with construction expected to begin in 2-3 years."
        category, confidence, indicators = self.classifier.categorize_by_timeline(text)
        self.assertEqual(category, TimelineCategory.LONG_TERM.value)
        self.assertGreater(confidence, 0.7)
        self.assertTrue(indicators)
        
        # Test mixed timeline indicators with conflicting signals
        text = "Although initial work begins next month, the main construction is scheduled for next year as part of the long-term development plan."
        category, confidence, indicators = self.classifier.categorize_by_timeline(text)
        self.assertTrue(indicators)
        self.assertLess(confidence, 0.7)  # Confidence should be lower due to conflicting signals
        
        # Test unknown timeline
        text = "The project has been announced but no timeline information is available."
        category, confidence, indicators = self.classifier.categorize_by_timeline(text)
        self.assertEqual(category, TimelineCategory.UNKNOWN.value)
        self.assertEqual(confidence, 0.0)
        self.assertFalse(indicators)
        
        # Test empty text
        category, confidence, indicators = self.classifier.categorize_by_timeline("")
        self.assertEqual(category, TimelineCategory.UNKNOWN.value)
        self.assertEqual(confidence, 0.0)
        self.assertFalse(indicators)
    
    def test_determine_decision_stage(self):
        """Test decision stage determination."""
        # Test conceptual stage
        text = "The developer is exploring a concept for a new office complex and conducting initial feasibility studies."
        stage, confidence, indicators = self.classifier.determine_decision_stage(text)
        self.assertEqual(stage, DecisionStage.CONCEPTUAL.value)
        self.assertGreater(confidence, 0.7)
        self.assertTrue(indicators)
        
        # Test planning stage
        text = "Architects have been hired and are actively designing the school expansion. Engineering plans are underway."
        stage, confidence, indicators = self.classifier.determine_decision_stage(text)
        self.assertEqual(stage, DecisionStage.PLANNING.value)
        self.assertGreater(confidence, 0.7)
        self.assertTrue(indicators)
        
        # Test approval stage
        text = "The project is currently seeking zoning permits and regulatory approvals from the city council."
        stage, confidence, indicators = self.classifier.determine_decision_stage(text)
        self.assertEqual(stage, DecisionStage.APPROVAL.value)
        self.assertGreater(confidence, 0.7)
        self.assertTrue(indicators)
        
        # Test funding stage
        text = "The hospital is securing financing for the expansion, with a bond measure to be voted on next month."
        stage, confidence, indicators = self.classifier.determine_decision_stage(text)
        self.assertEqual(stage, DecisionStage.FUNDING.value)
        self.assertGreater(confidence, 0.7)
        self.assertTrue(indicators)
        
        # Test implementation stage
        text = "The RFP has been issued and construction bids are now being accepted for the project."
        stage, confidence, indicators = self.classifier.determine_decision_stage(text)
        self.assertEqual(stage, DecisionStage.IMPLEMENTATION.value)
        self.assertGreater(confidence, 0.7)
        self.assertTrue(indicators)
        
        # Test unknown stage
        text = "A new development has been announced in the downtown area."
        stage, confidence, indicators = self.classifier.determine_decision_stage(text)
        self.assertEqual(stage, DecisionStage.UNKNOWN.value)
        self.assertEqual(confidence, 0.0)
        self.assertFalse(indicators)
    
    def test_assess_competition(self):
        """Test competition level assessment."""
        # Test low competition
        text = "The specialized nature of this project limits the field to a few qualified contractors with niche expertise."
        level, confidence, indicators = self.classifier.assess_competition(text)
        self.assertEqual(level, CompetitionLevel.LOW.value)
        self.assertGreater(confidence, 0.7)
        self.assertTrue(indicators)
        
        # Test medium competition
        text = "The hospital has invited several qualified regional firms to submit competitive bids."
        level, confidence, indicators = self.classifier.assess_competition(text)
        self.assertEqual(level, CompetitionLevel.MEDIUM.value)
        self.assertGreater(confidence, 0.7)
        self.assertTrue(indicators)
        
        # Test high competition
        text = "This is a highly competitive public tender with numerous national contractors expected to participate."
        level, confidence, indicators = self.classifier.assess_competition(text)
        self.assertEqual(level, CompetitionLevel.HIGH.value)
        self.assertGreater(confidence, 0.7)
        self.assertTrue(indicators)
        
        # Test explicit competitor count - low
        text = "The county has invited 3 pre-qualified contractors to bid on this project."
        level, confidence, indicators = self.classifier.assess_competition(text)
        self.assertEqual(level, CompetitionLevel.LOW.value)
        self.assertGreater(confidence, 0.7)
        self.assertTrue(indicators)
        
        # Test explicit competitor count - high
        text = "With over 15 contractors expected to bid, competition for this project will be intense."
        level, confidence, indicators = self.classifier.assess_competition(text)
        self.assertEqual(level, CompetitionLevel.HIGH.value)
        self.assertGreater(confidence, 0.7)
        self.assertTrue(indicators)
        
        # Test unknown competition
        text = "The project was announced yesterday by the city council."
        level, confidence, indicators = self.classifier.assess_competition(text)
        self.assertEqual(level, CompetitionLevel.UNKNOWN.value)
        self.assertEqual(confidence, 0.0)
        self.assertFalse(indicators)
    
    def test_calculate_win_probability(self):
        """Test win probability calculation."""
        # Create test lead with good fit
        good_lead = Lead(
            id=None,
            source="test",
            project_name="New Medical Center",
            location=Location(
                city="Los Angeles",
                state="California"
            ),
            market_sector=MarketSector.HEALTHCARE,
            estimated_value=15000000,
            extra_data={
                "classification": {
                    "competition_level": "low",
                    "timeline_category": "immediate"
                },
                "company": {
                    "name": "Sample Hospital"
                }
            }
        )
        
        # Calculate win probability
        probability, factors = self.classifier.calculate_win_probability(good_lead)
        
        # Check results
        self.assertGreater(probability, 0.7)  # Should be high probability
        self.assertEqual(len(factors), 6)  # Should have all 6 factors
        self.assertGreater(factors["market_sector_fit"], 0.8)  # Healthcare has high expertise
        self.assertGreater(factors["geographical_proximity"], 0.8)  # Los Angeles is strategic
        
        # Create test lead with poor fit
        poor_lead = Lead(
            id=None,
            source="test",
            project_name="Industrial Warehouse",
            location=Location(
                city="Phoenix",
                state="Arizona"
            ),
            market_sector=MarketSector.INDUSTRIAL,
            estimated_value=1000000,
            extra_data={
                "classification": {
                    "competition_level": "high",
                    "timeline_category": "long_term"
                },
                "company": {
                    "name": "Unknown Developer"
                }
            }
        )
        
        # Calculate win probability
        probability, factors = self.classifier.calculate_win_probability(poor_lead)
        
        # Check results
        self.assertLess(probability, 0.5)  # Should be low probability
        self.assertEqual(len(factors), 6)  # Should have all 6 factors
        self.assertLess(factors["market_sector_fit"], 0.7)  # Industrial has lower expertise
        self.assertLess(factors["geographical_proximity"], 0.5)  # Phoenix is not strategic
        self.assertLess(factors["competition_level"], 0.5)  # High competition
    
    def test_assign_priority_score(self):
        """Test priority score calculation."""
        # Create high priority lead
        high_priority_lead = Lead(
            id=None,
            source="test",
            project_name="UCLA Medical Center Expansion",
            location=Location(
                city="Los Angeles",
                state="California"
            ),
            market_sector=MarketSector.HEALTHCARE,
            estimated_value=50000000,
            extra_data={
                "classification": {
                    "value_category": "major",
                    "timeline_category": "immediate",
                    "win_probability": 0.85
                }
            }
        )
        
        # Calculate priority
        score, level, factors = self.classifier.assign_priority_score(high_priority_lead)
        
        # Check results
        self.assertGreaterEqual(score, 80)  # Should be high score
        self.assertEqual(level, PriorityLevel.CRITICAL.value)
        self.assertEqual(len(factors), 4)  # Should have all 4 factors
        self.assertGreaterEqual(factors["value_score"], 0.9)
        self.assertGreaterEqual(factors["timeline_score"], 0.9)
        
        # Create low priority lead
        low_priority_lead = Lead(
            id=None,
            source="test",
            project_name="Small Warehouse Renovation",
            location=Location(
                city="Tucson",
                state="Arizona"
            ),
            market_sector=MarketSector.INDUSTRIAL,
            estimated_value=500000,
            extra_data={
                "classification": {
                    "value_category": "small",
                    "timeline_category": "long_term",
                    "win_probability": 0.3
                }
            }
        )
        
        # Calculate priority
        score, level, factors = self.classifier.assign_priority_score(low_priority_lead)
        
        # Check results
        self.assertLess(score, 40)  # Should be low score
        self.assertIn(level, [PriorityLevel.LOW.value, PriorityLevel.MINIMAL.value])
        self.assertEqual(len(factors), 4)  # Should have all 4 factors
        self.assertLess(factors["value_score"], 0.5)
        self.assertLess(factors["timeline_score"], 0.5)
    
    def test_classify_lead_end_to_end(self):
        """Test the end-to-end lead classification process."""
        # Create a comprehensive test lead
        test_lead = Lead(
            id=None,
            source="test",
            project_name="UCLA Health Sciences Building",
            description="New 120,000 square foot medical research building on the UCLA campus. "
                       "Project includes laboratory space, offices, and clinical areas. "
                       "Estimated budget of $75 million. Construction to begin in Q2 2023 "
                       "with completion scheduled for late 2025. RFP will be issued next month "
                       "with 5-7 pre-qualified contractors invited to bid.",
            location=Location(
                city="Los Angeles",
                state="California"
            ),
            market_sector=MarketSector.HEALTHCARE,
            estimated_value=75000000,
            extra_data={}
        )
        
        # Set up mock returns for NLP processing
        self.mock_nlp.preprocess_text.return_value = test_lead.description
        
        # Apply classification
        classified_lead = self.classifier.classify_lead(test_lead)
        
        # Verify classification results
        classification = classified_lead.extra_data["classification"]
        
        # Check core classifications
        self.assertEqual(classification["value_category"], ValueCategory.MAJOR.value)
        self.assertIn(classification["timeline_category"], [TimelineCategory.IMMEDIATE.value, TimelineCategory.SHORT_TERM.value])
        self.assertIn(classification["decision_stage"], [DecisionStage.PLANNING.value, DecisionStage.IMPLEMENTATION.value])
        self.assertEqual(classification["competition_level"], CompetitionLevel.MEDIUM.value)
        
        # Check advanced metrics
        self.assertGreaterEqual(classification["win_probability"], 0.7)
        self.assertGreaterEqual(classification["priority_score"], 70)
        self.assertIn(classification["priority_level"], [PriorityLevel.CRITICAL.value, PriorityLevel.HIGH.value])
        
        # Check confidence scores
        self.assertGreaterEqual(classification["overall_confidence"], 0.7)
        
        # Check model metadata
        self.assertIn("model_version", classification)
        self.assertIn("classified_at", classification)

if __name__ == "__main__":
    unittest.main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for the NLP processor module.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
import tempfile
import json

from src.perera_lead_scraper.nlp.nlp_processor import (
    NLPProcessor,
    TextPreprocessingError,
    EntityExtractionError,
    ClassificationError,
    ProcessingTimeoutError,
)


class TestNLPProcessor:
    """Tests for the NLPProcessor class."""

    @pytest.fixture
    def sample_text(self):
        """Sample construction project text."""
        return """
        Construction is set to begin on the new $45 million Santa Monica Medical Center expansion project in July 2023. 
        The 65,000-square-foot facility will include a new emergency department, six operating rooms, and specialized 
        cardiac care units. ABC Construction has been selected as the general contractor, with XYZ Architecture handling 
        design. The project is expected to be completed by October 2024 and will create approximately 200 construction 
        jobs. The three-story building will be located at 1234 Ocean Avenue in Santa Monica, California.
        """

    @pytest.fixture
    def processor(self):
        """NLP processor instance with mocked spaCy model."""
        # Create mock configuration files
        with tempfile.TemporaryDirectory() as temp_dir:
            keywords_file = os.path.join(temp_dir, "keywords.json")
            entities_file = os.path.join(temp_dir, "construction_entities.json")
            locations_file = os.path.join(temp_dir, "target_locations.json")
            
            # Create basic keywords file
            with open(keywords_file, "w") as f:
                json.dump({
                    "healthcare": ["hospital", "medical center", "emergency department", "cardiac"],
                    "education": ["school", "university", "campus"],
                    "energy": ["power plant", "utility", "renewable"]
                }, f)
            
            # Create basic entities file
            with open(entities_file, "w") as f:
                json.dump({
                    "PROJECT_TYPE": ["expansion", "new construction"],
                    "BUILDING_TYPE": ["medical center", "hospital"],
                    "MATERIAL": ["concrete", "steel"]
                }, f)
            
            # Create basic locations file
            with open(locations_file, "w") as f:
                json.dump({
                    "southern_california": {
                        "states": ["CA", "California"],
                        "counties": ["Los Angeles", "Orange", "San Diego"],
                        "cities": ["Los Angeles", "San Diego", "Santa Monica", "Irvine"]
                    }
                }, f)
            
            # Patch the configuration paths
            with patch("src.perera_lead_scraper.nlp.nlp_processor.KEYWORDS_FILE", keywords_file), \
                 patch("src.perera_lead_scraper.nlp.nlp_processor.CONSTRUCTION_ENTITIES_FILE", entities_file), \
                 patch("src.perera_lead_scraper.nlp.nlp_processor.TARGET_MARKETS_FILE", locations_file), \
                 patch("src.perera_lead_scraper.nlp.nlp_processor.spacy.load") as mock_load:
                
                # Create a mock spaCy model
                mock_nlp = MagicMock()
                mock_nlp.pipe_names = ["ner"]
                mock_load.return_value = mock_nlp
                
                # Create processor instance
                processor = NLPProcessor(model_name="en_core_web_sm")
                
                # Configure the mock spaCy model behavior
                mock_tokenizer = MagicMock()
                mock_tokenizer.pipe.return_value = []
                mock_nlp.tokenizer = mock_tokenizer
                
                # Add a custom pipe method to process text
                def mock_process(text):
                    doc = MagicMock()
                    doc.ents = []
                    
                    # Mock entities based on text content
                    if "medical center" in text.lower():
                        building_entity = MagicMock()
                        building_entity.text = "Medical Center"
                        building_entity.label_ = "BUILDING_TYPE"
                        doc.ents.append(building_entity)
                    
                    if "santa monica" in text.lower():
                        location_entity = MagicMock()
                        location_entity.text = "Santa Monica"
                        location_entity.label_ = "GPE"
                        doc.ents.append(location_entity)
                    
                    if "california" in text.lower():
                        location_entity = MagicMock()
                        location_entity.text = "California"
                        location_entity.label_ = "GPE"
                        doc.ents.append(location_entity)
                    
                    if "$45 million" in text:
                        money_entity = MagicMock()
                        money_entity.text = "$45 million"
                        money_entity.label_ = "MONEY"
                        doc.ents.append(money_entity)
                    
                    if "july 2023" in text.lower():
                        date_entity = MagicMock()
                        date_entity.text = "July 2023"
                        date_entity.label_ = "DATE"
                        date_entity.start_char = text.lower().find("july 2023")
                        date_entity.end_char = date_entity.start_char + 9
                        doc.ents.append(date_entity)
                    
                    if "october 2024" in text.lower():
                        date_entity = MagicMock()
                        date_entity.text = "October 2024"
                        date_entity.label_ = "DATE"
                        date_entity.start_char = text.lower().find("october 2024")
                        date_entity.end_char = date_entity.start_char + 12
                        doc.ents.append(date_entity)
                    
                    if "abc construction" in text.lower():
                        org_entity = MagicMock()
                        org_entity.text = "ABC Construction"
                        org_entity.label_ = "ORG"
                        doc.ents.append(org_entity)
                    
                    if "expansion" in text.lower():
                        type_entity = MagicMock()
                        type_entity.text = "expansion"
                        type_entity.label_ = "PROJECT_TYPE"
                        doc.ents.append(type_entity)
                    
                    # Mock sentences
                    class Sentence:
                        def __init__(self, text):
                            self.text = text
                    
                    # Split text into sentences
                    sentences = text.split('. ')
                    doc.sents = [Sentence(s.strip()) for s in sentences if s.strip()]
                    
                    return doc
                
                mock_nlp.side_effect = mock_process
                processor.nlp = mock_nlp
                
                # Add basic patterns for entity matching
                mock_matcher = MagicMock()
                mock_matcher.side_effect = lambda doc: []
                processor.nlp.matcher = mock_matcher
                
                yield processor

    def test_preprocess_text(self, processor):
        """Test text preprocessing."""
        # Test with HTML content
        html_text = "<p>This is <b>formatted</b> text with <a href='#'>links</a>.</p>"
        preprocessed = processor.preprocess_text(html_text)
        assert "<p>" not in preprocessed
        assert "<b>" not in preprocessed
        assert "This is formatted text with links." in preprocessed
        
        # Test with special characters
        special_chars = "Text with special chars: é, ñ, ç, and unicode: \u2022"
        preprocessed = processor.preprocess_text(special_chars)
        assert "Text with special chars" in preprocessed
        
        # Test with whitespace
        whitespace_text = "Too    many   spaces   and\nline\nbreaks"
        preprocessed = processor.preprocess_text(whitespace_text)
        assert "Too many spaces and line breaks" == preprocessed

    def test_extract_entities(self, processor, sample_text):
        """Test entity extraction."""
        entities = processor.extract_entities(sample_text)
        
        # Check that expected entities are extracted
        assert "ORG" in entities
        assert "ABC Construction" in entities["ORG"]
        
        assert "GPE" in entities
        assert "Santa Monica" in entities["GPE"]
        assert "California" in entities["GPE"]
        
        assert "MONEY" in entities
        assert "$45 million" in entities["MONEY"]
        
        assert "DATE" in entities
        assert "July 2023" in entities["DATE"]
        assert "October 2024" in entities["DATE"]
        
        assert "PROJECT_TYPE" in entities
        assert "expansion" in entities["PROJECT_TYPE"]
        
        assert "BUILDING_TYPE" in entities
        assert "Medical Center" in entities["BUILDING_TYPE"]

    def test_extract_locations(self, processor, sample_text):
        """Test location extraction."""
        locations = processor.extract_locations(sample_text)
        
        # Check that expected locations are extracted and normalized
        assert "Santa Monica" in locations
        assert "California" in locations
        assert len(locations) == 2

    def test_extract_project_values(self, processor, sample_text):
        """Test project value extraction."""
        values = processor.extract_project_values(sample_text)
        
        # Check monetary values
        assert "monetary_values" in values
        assert "$45 million" in values["monetary_values"]
        
        # Check estimated value (converted from $45 million)
        assert "estimated_value" in values
        assert values["estimated_value"] > 40000000 
        
        # Check square footage
        assert "square_footage" in values
        assert values["square_footage"] == 65000

    def test_extract_dates(self, processor, sample_text):
        """Test date extraction."""
        dates = processor.extract_dates(sample_text)
        
        # Check all dates
        assert "all_dates" in dates
        assert "July 2023" in dates["all_dates"]
        assert "October 2024" in dates["all_dates"]
        
        # Check categorized dates
        assert "start_date" in dates
        assert dates["start_date"] == "July 2023"
        
        assert "completion_date" in dates
        assert dates["completion_date"] == "October 2024"
        
        # Check project phase
        assert "project_phase" in dates

    def test_classify_market_sector(self, processor, sample_text):
        """Test market sector classification."""
        sector, confidence = processor.classify_market_sector(sample_text)
        
        # Should classify as healthcare due to keywords
        assert sector == "healthcare"
        assert confidence > 0.5

    def test_calculate_relevance_score(self, processor):
        """Test relevance scoring algorithm."""
        # High relevance text
        high_relevance = "This hospital project includes emergency rooms and a specialized cardiac care unit."
        high_score = processor.calculate_relevance_score(
            high_relevance, 
            ["hospital", "emergency", "cardiac"]
        )
        
        # Low relevance text
        low_relevance = "This project is located near a park and includes landscaping."
        low_score = processor.calculate_relevance_score(
            low_relevance, 
            ["hospital", "emergency", "cardiac"]
        )
        
        # Medium relevance text (partial matches)
        medium_relevance = "The building has some medical facilities."
        medium_score = processor.calculate_relevance_score(
            medium_relevance, 
            ["hospital", "medical center", "emergency department"]
        )
        
        # Check that scores are correctly ordered
        assert high_score > medium_score > low_score
        assert 0 <= low_score <= 1
        assert 0 <= medium_score <= 1
        assert 0 <= high_score <= 1

    def test_summarize_content(self, processor, sample_text):
        """Test content summarization."""
        summary = processor.summarize_content(sample_text, max_length=100)
        
        # Check summary length
        assert len(summary) <= 100
        
        # Check that key information is included
        assert "Medical Center" in summary or "Santa Monica" in summary
        
        # Test with short text (should return as is)
        short_text = "This is a short description of a project."
        short_summary = processor.summarize_content(short_text)
        assert short_summary == short_text

    def test_error_handling(self, processor):
        """Test error handling for edge cases."""
        # Test with empty input
        assert processor.preprocess_text("") == ""
        assert processor.extract_entities("") == {}
        assert processor.extract_locations("") == []
        assert processor.extract_project_values("") == {}
        assert processor.extract_dates("") == {}
        assert processor.classify_market_sector("") == ("other", 0.0)
        assert processor.summarize_content("") == ""
        
        # Test with None input
        assert processor.preprocess_text(None) == ""
        assert processor.extract_entities(None) == {}
        assert processor.extract_locations(None) == []
        assert processor.extract_project_values(None) == {}
        assert processor.extract_dates(None) == {}
        assert processor.classify_market_sector(None) == ("other", 0.0)
        assert processor.summarize_content(None) == ""

    def test_normalize_location(self, processor):
        """Test location normalization."""
        # Test state abbreviations
        assert processor._normalize_location("CA") == "California"
        assert processor._normalize_location("ca") == "California"
        
        # Test city abbreviations
        assert processor._normalize_location("LA") == "Los Angeles"
        
        # Test prefixes and suffixes
        assert processor._normalize_location("City of Sacramento") == "Sacramento"
        assert processor._normalize_location("Orange County") == "Orange"
        
        # Test case normalization
        assert processor._normalize_location("santa monica") == "Santa Monica"
        assert processor._normalize_location("IRVINE") == "Irvine"

    def test_validate_against_target_markets(self, processor):
        """Test location validation against target markets."""
        # Test locations in target markets
        assert processor._validate_against_target_markets("Santa Monica") is True
        assert processor._validate_against_target_markets("Los Angeles") is True
        assert processor._validate_against_target_markets("California") is True
        assert processor._validate_against_target_markets("SoCal") is True
        
        # Test locations not in target markets
        assert processor._validate_against_target_markets("New York") is False
        assert processor._validate_against_target_markets("Chicago") is False
        assert processor._validate_against_target_markets("Texas") is False

    def test_parse_money_value(self, processor):
        """Test parsing monetary values."""
        # Test millions
        assert processor._parse_money_value("$45 million") == 45000000
        assert processor._parse_money_value("45 million dollars") == 45000000
        assert processor._parse_money_value("45M") == 45000000
        
        # Test billions
        assert processor._parse_money_value("$2.5 billion") == 2500000000
        assert processor._parse_money_value("2.5B") == 2500000000
        
        # Test thousands
        assert processor._parse_money_value("500 thousand") == 500000
        assert processor._parse_money_value("500K") == 500000
        
        # Test simple values
        assert processor._parse_money_value("$1,000") == 1000
        assert processor._parse_money_value("1000 dollars") == 1000

    def test_estimate_project_value(self, processor):
        """Test project value estimation."""
        # Test with square footage
        sf_values = {
            "square_footage": 50000
        }
        sf_value = processor._estimate_project_value(sf_values, "office building")
        assert sf_value is not None
        assert sf_value > 0
        
        # Test with units
        unit_values = {
            "units": 100
        }
        unit_value = processor._estimate_project_value(unit_values, "apartment complex")
        assert unit_value is not None
        assert unit_value > 0
        
        # Test with stories
        story_values = {
            "stories": 5
        }
        story_value = processor._estimate_project_value(story_values, "commercial building")
        assert story_value is not None
        assert story_value > 0
        
        # Test with insufficient information
        empty_values = {}
        empty_value = processor._estimate_project_value(empty_values, "project")
        assert empty_value is None
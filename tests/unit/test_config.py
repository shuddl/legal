#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Unit tests for the configuration module.
"""

import os
import pytest
from pathlib import Path

from src.perera_lead_scraper.config import AppConfig


class TestAppConfig:
    """Tests for the AppConfig class."""
    
    def test_load_from_env(self, mock_env_vars, temp_db_path, temp_log_path):
        """Test that config loads values from environment variables."""
        config = AppConfig()
        
        assert config.log_level == 10  # DEBUG
        assert config.log_file_path == temp_log_path
        assert config.db_path == temp_db_path
        assert config.hubspot_api_key == "test_api_key"
        assert config.scrape_interval_hours == 1
        assert config.max_leads_per_run == 10
        assert config.export_to_hubspot is False
        assert config.debug_mode is True
    
    def test_validate_valid_config(self, mock_env_vars, tmp_path):
        """Test validation with valid configuration."""
        config = AppConfig()
        
        # Make sure parent directories exist
        os.makedirs(config.db_path.parent, exist_ok=True)
        os.makedirs(config.log_file_path.parent, exist_ok=True)
        config.sources_path = tmp_path / "sources.json"
        config.rss_sources_path = tmp_path / "rss_sources.json"
        config.city_portals_path = tmp_path / "city_portals.json"
        config.news_sources_path = tmp_path / "news_sources.json"
        config.hubspot_config_path = tmp_path / "hubspot_config.json"
        
        # Create parent directories
        os.makedirs(config.sources_path.parent, exist_ok=True)
        
        # Validation should pass
        errors = config.validate()
        assert len(errors) == 0
    
    def test_validate_invalid_config(self):
        """Test validation with invalid configuration."""
        config = AppConfig()
        
        # Set invalid values
        config.scrape_interval_hours = 0
        config.max_leads_per_run = -1
        config.export_to_hubspot = True
        config.hubspot_api_key = None
        
        # Set paths to non-existent directories
        config.db_path = Path("/non/existent/path/db.sqlite")
        config.log_file_path = Path("/non/existent/path/log.txt")
        
        # Validation should fail
        errors = config.validate()
        assert len(errors) > 0
        assert any("SCRAPE_INTERVAL_HOURS must be positive" in error for error in errors)
        assert any("MAX_LEADS_PER_RUN must be positive" in error for error in errors)
        assert any("HUBSPOT_API_KEY is required" in error for error in errors)
        assert any("Database path parent does not exist" in error for error in errors)
        assert any("Log file path parent does not exist" in error for error in errors)
    
    def test_load_source_config(self, sample_sources_file):
        """Test loading a source configuration file."""
        config = AppConfig()
        
        # Load the sample sources file
        sources_config = config.load_source_config(sample_sources_file)
        
        # Check that it loaded correctly
        assert "sources" in sources_config
        assert len(sources_config["sources"]) > 0
        assert sources_config["sources"][0]["name"] == "test_source"
    
    def test_load_nonexistent_source_config(self, tmp_path):
        """Test loading a non-existent source configuration file."""
        config = AppConfig()
        
        # Try to load a non-existent file
        non_existent_file = tmp_path / "nonexistent.json"
        sources_config = config.load_source_config(non_existent_file)
        
        # Should return an empty dict
        assert sources_config == {}
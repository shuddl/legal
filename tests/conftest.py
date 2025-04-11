#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pytest configuration file for the Perera Construction Lead Scraper test suite.
"""

import os
import sys
import pytest
from pathlib import Path

# Add the project root directory to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
    
# Add the src directory to Python path for accessing perera_lead_scraper
src_path = os.path.join(project_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import the package
import src.perera_lead_scraper as perera_lead_scraper

# Define pytest markers
def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "integration: mark test as requiring integration setup"
    )
    config.addinivalue_line(
        "markers", "hubspot: mark test as requiring HubSpot access"
    )


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Path to the test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def sample_config_dir(test_data_dir: Path) -> Path:
    """Path to the sample configuration directory."""
    config_dir = test_data_dir / "config"
    config_dir.mkdir(exist_ok=True)
    return config_dir


@pytest.fixture(scope="session")
def sample_sources_file(sample_config_dir: Path) -> Path:
    """Path to a sample sources.json file."""
    sources_file = sample_config_dir / "sources.json"
    if not sources_file.exists():
        # Create a minimal sources.json file
        with open(sources_file, "w") as f:
            f.write('''
            {
                "sources": [
                    {
                        "name": "test_source",
                        "url": "https://example.com/feed",
                        "type": "rss",
                        "category": "Test",
                        "active": true
                    }
                ]
            }
            ''')
    return sources_file


@pytest.fixture(scope="function")
def temp_db_path(tmp_path: Path) -> Path:
    """Temporary database path for testing."""
    return tmp_path / "test.db"


@pytest.fixture(scope="function")
def temp_log_path(tmp_path: Path) -> Path:
    """Temporary log file path for testing."""
    return tmp_path / "test.log"


@pytest.fixture(scope="function")
def mock_env_vars(monkeypatch, temp_db_path: Path, temp_log_path: Path):
    """
    Set up environment variables for testing.
    
    Args:
        monkeypatch: Pytest monkeypatch fixture
        temp_db_path: Temporary database path
        temp_log_path: Temporary log file path
    """
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FILE_PATH", str(temp_log_path))
    monkeypatch.setenv("LEAD_DB_PATH", str(temp_db_path))
    monkeypatch.setenv("HUBSPOT_API_KEY", "test_api_key")
    monkeypatch.setenv("SCRAPE_INTERVAL_HOURS", "1")
    monkeypatch.setenv("MAX_LEADS_PER_RUN", "10")
    monkeypatch.setenv("EXPORT_TO_HUBSPOT", "false")
    monkeypatch.setenv("DEBUG_MODE", "true")
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration management for the Perera Construction Lead Scraper.

This module loads configuration from environment variables, files, and provides
sensible defaults. It also validates configuration values.
"""

import os
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Union, cast

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directories
ROOT_DIR = Path(__file__).parent.parent.parent.absolute()
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"

# Ensure required directories exist
for directory in [CONFIG_DIR, DATA_DIR, LOGS_DIR]:
    directory.mkdir(exist_ok=True)

# Default configuration file paths
DEFAULT_SOURCES_PATH = CONFIG_DIR / "sources.json"
DEFAULT_RSS_SOURCES_PATH = CONFIG_DIR / "rss_sources.json"
DEFAULT_CITY_PORTALS_PATH = CONFIG_DIR / "city_portals.json"
DEFAULT_NEWS_SOURCES_PATH = CONFIG_DIR / "news_sources.json"
DEFAULT_HUBSPOT_CONFIG_PATH = CONFIG_DIR / "hubspot_config.json"
DEFAULT_DB_PATH = DATA_DIR / "leads.db"

# Log levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


@dataclass
class AppConfig:
    """Application configuration."""

    # Database
    db_path: Path = field(
        default_factory=lambda: Path(os.getenv("LEAD_DB_PATH", str(DEFAULT_DB_PATH)))
    )

    # Logging
    log_level: int = field(
        default_factory=lambda: LOG_LEVELS.get(
            os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO
        )
    )
    log_file_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("LOG_FILE_PATH", str(LOGS_DIR / "scraper.log"))
        )
    )

    # Scraping
    scrape_interval_hours: int = field(
        default_factory=lambda: int(os.getenv("SCRAPE_INTERVAL_HOURS", "24"))
    )
    max_leads_per_run: int = field(
        default_factory=lambda: int(os.getenv("MAX_LEADS_PER_RUN", "100"))
    )

    # Source configuration
    sources_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("SOURCES_PATH", str(DEFAULT_SOURCES_PATH))
        )
    )
    rss_sources_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("RSS_SOURCES_PATH", str(DEFAULT_RSS_SOURCES_PATH))
        )
    )
    city_portals_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("CITY_PORTALS_PATH", str(DEFAULT_CITY_PORTALS_PATH))
        )
    )
    news_sources_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("NEWS_SOURCES_PATH", str(DEFAULT_NEWS_SOURCES_PATH))
        )
    )

    # HubSpot
    hubspot_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("HUBSPOT_API_KEY")
    )
    hubspot_config_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("HUBSPOT_CONFIG_PATH", str(DEFAULT_HUBSPOT_CONFIG_PATH))
        )
    )
    
    # HubSpot property IDs
    hubspot_property_ids: Dict[str, str] = field(default_factory=lambda: {
        # Custom properties for deals
        "lead_source": os.getenv("HUBSPOT_PROP_LEAD_SOURCE", ""),
        "source_url": os.getenv("HUBSPOT_PROP_SOURCE_URL", ""),
        "source_id": os.getenv("HUBSPOT_PROP_SOURCE_ID", ""),
        "lead_id": os.getenv("HUBSPOT_PROP_LEAD_ID", ""),
        "publication_date": os.getenv("HUBSPOT_PROP_PUBLICATION_DATE", ""),
        "retrieved_date": os.getenv("HUBSPOT_PROP_RETRIEVED_DATE", ""),
        "confidence_score": os.getenv("HUBSPOT_PROP_CONFIDENCE_SCORE", ""),
        "location_city": os.getenv("HUBSPOT_PROP_LOCATION_CITY", ""),
        "location_state": os.getenv("HUBSPOT_PROP_LOCATION_STATE", ""),
        "estimated_square_footage": os.getenv("HUBSPOT_PROP_EST_SQ_FOOTAGE", ""),
    })
    
    # HubSpot deal stage IDs
    hubspot_dealstage_ids: Dict[str, str] = field(default_factory=lambda: {
        "new": os.getenv("HUBSPOT_STAGE_NEW", ""),
        "processing": os.getenv("HUBSPOT_STAGE_PROCESSING", ""),
        "validated": os.getenv("HUBSPOT_STAGE_VALIDATED", ""),
        "enriched": os.getenv("HUBSPOT_STAGE_ENRICHED", ""),
        "exported": os.getenv("HUBSPOT_STAGE_EXPORTED", ""),
        "archived": os.getenv("HUBSPOT_STAGE_ARCHIVED", ""),
        "rejected": os.getenv("HUBSPOT_STAGE_REJECTED", ""),
    })

    # Proxy configuration
    use_proxies: bool = field(
        default_factory=lambda: os.getenv("USE_PROXIES", "false").lower() == "true"
    )
    proxy_url: Optional[str] = field(default_factory=lambda: os.getenv("PROXY_URL"))

    # Output configuration
    export_csv: bool = field(
        default_factory=lambda: os.getenv("EXPORT_CSV", "true").lower() == "true"
    )
    export_to_hubspot: bool = field(
        default_factory=lambda: os.getenv("EXPORT_TO_HUBSPOT", "true").lower() == "true"
    )

    # Debug options
    debug_mode: bool = field(
        default_factory=lambda: os.getenv("DEBUG_MODE", "false").lower() == "true"
    )
    
    # Export scheduler configuration
    export_interval_minutes: int = field(
        default_factory=lambda: int(os.getenv("EXPORT_INTERVAL_MINUTES", "60"))
    )
    export_batch_size: int = field(
        default_factory=lambda: int(os.getenv("EXPORT_BATCH_SIZE", "25"))
    )
    export_window_start_hour: Optional[int] = field(
        default_factory=lambda: int(os.getenv("EXPORT_WINDOW_START_HOUR")) if os.getenv("EXPORT_WINDOW_START_HOUR") else None
    )
    export_window_end_hour: Optional[int] = field(
        default_factory=lambda: int(os.getenv("EXPORT_WINDOW_END_HOUR")) if os.getenv("EXPORT_WINDOW_END_HOUR") else None
    )

    def validate(self) -> List[str]:
        """
        Validate configuration values.

        Returns:
            List[str]: List of validation errors, empty if valid
        """
        errors = []

        # Check if required paths exist
        for path_name, path in [
            ("Database path parent", self.db_path.parent),
            ("Log file path parent", self.log_file_path.parent),
            ("Sources path parent", self.sources_path.parent),
            ("RSS sources path parent", self.rss_sources_path.parent),
            ("City portals path parent", self.city_portals_path.parent),
            ("News sources path parent", self.news_sources_path.parent),
            ("HubSpot config path parent", self.hubspot_config_path.parent),
        ]:
            if not path.exists():
                errors.append(f"{path_name} does not exist: {path}")

        # Check if required source configs exist
        if self.export_to_hubspot and not self.hubspot_api_key:
            errors.append("HUBSPOT_API_KEY is required when EXPORT_TO_HUBSPOT is true")

        # Validate numeric values
        if self.scrape_interval_hours <= 0:
            errors.append("SCRAPE_INTERVAL_HOURS must be positive")

        if self.max_leads_per_run <= 0:
            errors.append("MAX_LEADS_PER_RUN must be positive")

        return errors

    def load_source_config(self, path: Path) -> Dict[str, Any]:
        """
        Load a JSON configuration file.

        Args:
            path: Path to the configuration file

        Returns:
            Dict: Loaded configuration or empty dict if file doesn't exist
        """
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                return {}
        except Exception as e:
            logging.error(f"Error loading configuration from {path}: {str(e)}")
            return {}


# Create a global config instance
config = AppConfig()
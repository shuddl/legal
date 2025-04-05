#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Verify Legal API Access - CLI Tool

This script verifies access to all configured legal API portals and displays the results.
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add the project path to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.perera_lead_scraper.config import AppConfig
from src.perera_lead_scraper.legal.legal_api import LegalAPI

def setup_logging(log_level: str = "INFO"):
    """Configure logging."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    """Run the main verification process."""
    parser = argparse.ArgumentParser(description="Verify access to legal API portals")
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level"
    )
    parser.add_argument(
        "--config-dir",
        type=str,
        help="Custom configuration directory path"
    )
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.log_level)
    
    # Initialize config
    config_kwargs = {}
    if args.config_dir:
        config_kwargs["config_dir"] = args.config_dir
    
    config = AppConfig(**config_kwargs)

    try:
        # Initialize the legal API client
        api = LegalAPI(config)
        
        # Verify access to all configured API providers
        print("\n===== LEGAL API ACCESS VERIFICATION =====\n")
        access_status = api.verify_api_access()
        
        # Display results
        if not access_status:
            print("No legal API providers are configured.")
            return
            
        print("\nAPI Access Status:")
        print("─" * 50)
        print(f"{'API Provider':<25} {'Status':<10}")
        print("─" * 50)
        
        for provider, status in access_status.items():
            status_str = "✅ ACCESSIBLE" if status else "❌ UNAVAILABLE"
            print(f"{provider:<25} {status_str:<10}")
        print("─" * 50)
        
        # Summary
        accessible = sum(1 for status in access_status.values() if status)
        total = len(access_status)
        
        print(f"\nSummary: {accessible}/{total} API providers are accessible")
        
        if accessible < total:
            print("\nTroubleshooting tips for unavailable APIs:")
            print("1. Verify credentials in your legal_api_credentials.json file")
            print("2. Check if the API base URLs are correct")
            print("3. Ensure your network can access the API endpoints")
            print("4. Verify API key or token has not expired")
        
        print("\nFor detailed connection logs, run with --log-level DEBUG")
        
    except Exception as e:
        logging.error(f"Error verifying API access: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
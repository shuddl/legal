#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Construction Lead Scraper - Main Entry Point
"""

import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def setup_environment():
    """Set up the environment for the scraper."""
    # Verify environment variables are loaded
    required_vars = ['HUBSPOT_API_KEY', 'LOG_LEVEL', 'SCRAPE_INTERVAL_HOURS', 'MAX_LEADS_PER_RUN']
    missing_vars = [var for var in required_vars if os.getenv(var) is None]
    
    if missing_vars:
        print(f"Warning: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please check your .env file or environment settings.")
        return False
    
    return True

def test_environment():
    """Test function to verify the environment is working properly."""
    # Check for required directories
    required_dirs = ['scrapers', 'processors', 'integrations', 'utils', 'data', 'tests']
    for directory in required_dirs:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")
    
    # Test environment variables
    log_level = os.getenv('LOG_LEVEL', 'INFO')
    print(f"Log level set to: {log_level}")
    
    # Test imports
    try:
        import scrapy
        import selenium
        import requests
        import pandas
        import nltk
        import spacy
        import pytest
        print("All required packages imported successfully.")
    except ImportError as e:
        print(f"Error importing packages: {e}")
        print("Please install required packages using: pip install -r requirements.txt")
        return False
    
    return True

def main():
    """Main entry point for the application."""
    print("Construction Lead Scraper initialized")
    
    # Set up environment
    if not setup_environment():
        print("Environment setup failed.")
        return
    
    # Test environment
    if not test_environment():
        print("Environment test failed.")
        return
    
    # TODO: Initialize scraper manager
    # TODO: Set up scheduled jobs
    # TODO: Start processing pipeline
    
    print("Construction Lead Scraper ready.")

if __name__ == "__main__":
    main()
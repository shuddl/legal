#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script to run the Perera Construction Lead Scraper.

This is a convenience script for running the scraper from the command line.
It is functionally equivalent to running the module directly:
  python -m perera_lead_scraper.main

Usage:
  python run_scraper.py run
  python run_scraper.py status
  python run_scraper.py test-sources
  python run_scraper.py export
  python run_scraper.py sync-hubspot
  python run_scraper.py list-sources
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the main function from the package
from src.perera_lead_scraper.main import main

if __name__ == "__main__":
    # Run the main function
    sys.exit(main())
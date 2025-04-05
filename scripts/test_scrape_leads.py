#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test Lead Scraping Script

This script runs the scrapers to collect and test real lead data.
It can be used to validate the end-to-end functionality of the lead generation system.
"""

import os
import sys
import logging
import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add the project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.perera_lead_scraper.utils.source_registry import SourceRegistry
from src.perera_lead_scraper.scrapers.scraper_manager import ScraperManager
from src.perera_lead_scraper.utils.storage import LeadStorage
from src.perera_lead_scraper.config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"logs/test_scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)

logger = logging.getLogger("test_scrape")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test scraping of construction leads")
    parser.add_argument(
        "--source-type", 
        type=str, 
        choices=["rss", "website", "city_portal", "api", "all"],
        default="all",
        help="Type of sources to scrape"
    )
    parser.add_argument(
        "--source-name", 
        type=str, 
        help="Name of a specific source to scrape"
    )
    parser.add_argument(
        "--tag", 
        type=str, 
        help="Filter sources by tag (e.g., 'socal', 'healthcare')"
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        default=0,
        help="Limit number of sources to process (0 = no limit)"
    )
    parser.add_argument(
        "--export", 
        type=str, 
        help="Export results to file (JSON format)"
    )
    parser.add_argument(
        "--no-store", 
        action="store_true",
        help="Don't store leads in the database"
    )
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose output"
    )
    
    return parser.parse_args()


def run_test(args):
    """Run the scraping test with the given arguments."""
    logger.info("Starting lead scraping test")
    
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize registry and load sources
    sources_file = os.path.join("config", "sources.json")
    registry = SourceRegistry(sources_file)
    
    if not registry.sources:
        logger.error("No sources loaded from registry")
        return False
    
    # Create scraper manager
    scraper_manager = ScraperManager(registry)
    
    # Initialize storage (if not disabled)
    storage = None
    if not args.no_store:
        storage = LeadStorage()
    
    # Determine which sources to run
    sources_to_run = []
    
    if args.source_name:
        # Run a specific source
        if args.source_name in registry.sources:
            sources_to_run = [args.source_name]
        else:
            logger.error(f"Source not found: {args.source_name}")
            return False
    elif args.tag:
        # Run sources with a specific tag
        tagged_sources = registry.get_sources_by_tag(args.tag)
        sources_to_run = [source.name for source in tagged_sources]
    elif args.source_type != "all":
        # Run sources of a specific type
        type_sources = registry.get_sources_by_type(args.source_type)
        sources_to_run = [source.name for source in type_sources]
    else:
        # Run all active sources
        active_sources = registry.get_active_sources()
        sources_to_run = [source.name for source in active_sources]
    
    # Apply limit if specified
    if args.limit > 0 and len(sources_to_run) > args.limit:
        logger.info(f"Limiting to {args.limit} sources")
        sources_to_run = sources_to_run[:args.limit]
    
    logger.info(f"Will process {len(sources_to_run)} sources: {', '.join(sources_to_run)}")
    
    # Keep track of results
    results = {
        "timestamp": datetime.now().isoformat(),
        "sources_processed": 0,
        "sources_succeeded": 0,
        "sources_failed": 0,
        "total_leads_found": 0,
        "leads_by_source": {},
        "failures": []
    }
    
    # Process each source
    for source_name in sources_to_run:
        logger.info(f"Processing source: {source_name}")
        results["sources_processed"] += 1
        
        try:
            # Run the scraper
            success = scraper_manager.run_scraper(source_name)
            
            # Check for leads in the scraper
            scraper = scraper_manager.scrapers.get(source_name)
            if not scraper:
                logger.warning(f"No scraper found for {source_name}")
                results["sources_failed"] += 1
                results["failures"].append({
                    "source": source_name,
                    "reason": "No scraper found"
                })
                continue
            
            if not hasattr(scraper, "leads") or not scraper.leads:
                logger.warning(f"No leads found for {source_name}")
                results["leads_by_source"][source_name] = 0
                if success:
                    results["sources_succeeded"] += 1
                else:
                    results["sources_failed"] += 1
                    results["failures"].append({
                        "source": source_name,
                        "reason": "No leads found"
                    })
                continue
            
            # Record leads found
            lead_count = len(scraper.leads)
            results["leads_by_source"][source_name] = lead_count
            results["total_leads_found"] += lead_count
            
            logger.info(f"Found {lead_count} leads for {source_name}")
            
            # Store leads if storage is enabled
            if storage and not args.no_store:
                for lead in scraper.leads:
                    storage.save_lead(lead)
                logger.info(f"Stored {lead_count} leads in database")
            
            if success:
                results["sources_succeeded"] += 1
            else:
                results["sources_failed"] += 1
                results["failures"].append({
                    "source": source_name,
                    "reason": "Scraper reported failure"
                })
                
        except Exception as e:
            logger.exception(f"Error processing {source_name}: {str(e)}")
            results["sources_failed"] += 1
            results["failures"].append({
                "source": source_name,
                "reason": str(e)
            })
    
    # Print summary
    logger.info("\n" + "="*50)
    logger.info(f"SCRAPING TEST RESULTS SUMMARY:")
    logger.info(f"Sources processed: {results['sources_processed']}")
    logger.info(f"Sources succeeded: {results['sources_succeeded']}")
    logger.info(f"Sources failed: {results['sources_failed']}")
    logger.info(f"Total leads found: {results['total_leads_found']}")
    
    # Show lead counts by source
    if results['leads_by_source']:
        logger.info("\nLeads by source:")
        for source, count in sorted(results['leads_by_source'].items(), key=lambda x: x[1], reverse=True):
            logger.info(f"  {source}: {count}")
    
    # Show failures
    if results['failures']:
        logger.info("\nFailures:")
        for failure in results['failures']:
            logger.info(f"  {failure['source']}: {failure['reason']}")
    
    logger.info("="*50 + "\n")
    
    # Export results if requested
    if args.export:
        try:
            with open(args.export, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"Results exported to {args.export}")
        except Exception as e:
            logger.error(f"Error exporting results: {str(e)}")
    
    return results['sources_succeeded'] > 0


def main():
    """Main entry point."""
    args = parse_args()
    success = run_test(args)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
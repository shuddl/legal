#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test Live Scraping

This script allows testing the scraping functionality in a way that simulates
the live environment. It provides options to:
- Run scraping on specific sources or all configured sources
- Show detailed progress and results
- Test the full pipeline from scraping to enrichment to export
- Validate the quality of extracted leads
"""

import os
import sys
import logging
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add the project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.perera_lead_scraper.utils.storage import LeadStorage
from src.perera_lead_scraper.models.lead import Lead, MarketSector, LeadStatus
from src.perera_lead_scraper.config import config
from src.perera_lead_scraper.scrapers.base_scraper import BaseScraper
from src.perera_lead_scraper.scrapers.rss_scraper import RssScraper
from src.perera_lead_scraper.scrapers.news_scraper import NewsScraper
from src.perera_lead_scraper.scrapers.city_portal_scraper import CityPortalScraper
from src.perera_lead_scraper.enrichment.enrichment import LeadEnricher
from src.perera_lead_scraper.nlp.nlp_processor import NLPProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("test_live_scraping")

class LiveScrapingTester:
    """Handles testing of live scraping functionality."""
    
    def __init__(self, verbose: bool = False):
        """Initialize the tester with storage and configuration."""
        self.verbose = verbose
        self.storage = LeadStorage()
        self.nlp_processor = NLPProcessor()
        self.enricher = LeadEnricher()
        
        # Load configuration for sources
        self.sources = self._load_sources()
        logger.info(f"Loaded {len(self.sources)} sources from configuration")
    
    def _load_sources(self) -> Dict[str, Dict[str, Any]]:
        """Load scraping sources from configuration files."""
        sources = {}
        
        # Load RSS sources
        try:
            with open(config.RSS_SOURCES_PATH, "r", encoding="utf-8") as f:
                rss_sources = json.load(f)
                for source_id, source in rss_sources.items():
                    sources[source_id] = {**source, "type": "rss"}
        except Exception as e:
            logger.warning(f"Could not load RSS sources: {e}")
        
        # Load news sources
        try:
            with open(config.NEWS_SOURCES_PATH, "r", encoding="utf-8") as f:
                news_sources = json.load(f)
                for source_id, source in news_sources.items():
                    sources[source_id] = {**source, "type": "news"}
        except Exception as e:
            logger.warning(f"Could not load news sources: {e}")
        
        # Load city portal sources
        try:
            with open(config.CITY_PORTALS_PATH, "r", encoding="utf-8") as f:
                portal_sources = json.load(f)
                for source_id, source in portal_sources.items():
                    sources[source_id] = {**source, "type": "city_portal"}
        except Exception as e:
            logger.warning(f"Could not load city portal sources: {e}")
        
        return sources
    
    def list_sources(self) -> None:
        """Display all available sources for testing."""
        print("\nAvailable Sources:")
        print("-" * 80)
        print(f"{'ID':<20} {'Type':<15} {'Name':<30} {'Status':<10}")
        print("-" * 80)
        
        for source_id, source in sorted(self.sources.items()):
            source_type = source.get('type', 'unknown')
            source_name = source.get('name', source_id)
            source_status = source.get('enabled', True)
            
            status_str = "Enabled" if source_status else "Disabled"
            print(f"{source_id:<20} {source_type:<15} {source_name:<30} {status_str:<10}")
    
    def create_scraper(self, source_id: str, source_config: Dict[str, Any]) -> BaseScraper:
        """Create appropriate scraper based on source type."""
        source_type = source_config.get('type')
        
        if source_type == 'rss':
            return RssScraper(source_id, source_config)
        elif source_type == 'news':
            return NewsScraper(source_id, source_config)
        elif source_type == 'city_portal':
            return CityPortalScraper(source_id, source_config)
        else:
            raise ValueError(f"Unknown source type: {source_type}")
    
    def test_source(self, source_id: str, limit: int = 5, 
                   process_leads: bool = False) -> List[Lead]:
        """
        Test scraping from a specific source.
        
        Args:
            source_id: ID of source to test
            limit: Maximum number of leads to retrieve
            process_leads: Whether to process leads with NLP and enrichment
            
        Returns:
            List[Lead]: List of scraped leads
        """
        if source_id not in self.sources:
            logger.error(f"Source {source_id} not found in configuration")
            return []
        
        source_config = self.sources[source_id]
        logger.info(f"Testing source: {source_id} ({source_config.get('name', 'Unknown')})")
        
        try:
            # Create appropriate scraper
            scraper = self.create_scraper(source_id, source_config)
            
            # Execute scraping
            start_time = datetime.now()
            leads = scraper.scrape(limit=limit)
            end_time = datetime.now()
            
            # Log results
            duration = (end_time - start_time).total_seconds()
            logger.info(f"Scraped {len(leads)} leads in {duration:.2f} seconds")
            
            # Process leads if requested
            if process_leads and leads:
                leads = self.process_leads(leads)
            
            # Display leads
            if self.verbose:
                self.display_leads(leads)
            
            return leads
            
        except Exception as e:
            logger.error(f"Error testing source {source_id}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return []
    
    def process_leads(self, leads: List[Lead]) -> List[Lead]:
        """Process leads with NLP and enrichment."""
        processed_leads = []
        
        for lead in leads:
            try:
                # Apply NLP processing
                logger.info(f"Applying NLP processing to lead: {lead.id}")
                
                # Extract entities
                if lead.description:
                    entities = self.nlp_processor.extract_entities(lead.description)
                    if entities:
                        lead.extra_data = lead.extra_data or {}
                        lead.extra_data["entities"] = entities
                
                # Classify market sector
                if lead.description:
                    market_sector, confidence = self.nlp_processor.classify_market_sector(lead.description)
                    lead.market_sector = market_sector
                    lead.confidence_score = confidence
                
                # Extract locations
                if lead.description and not lead.location:
                    locations = self.nlp_processor.extract_locations(lead.description)
                    if locations:
                        from src.perera_lead_scraper.models.lead import Location
                        lead.location = Location(city=locations[0])
                
                # Extract project values
                if lead.description:
                    values = self.nlp_processor.extract_project_values(lead.description)
                    if values and "estimated_value" in values:
                        lead.estimated_value = values["estimated_value"]
                
                # Enrich lead
                logger.info(f"Enriching lead: {lead.id}")
                enriched_data = self.enricher.enrich_lead(lead)
                if enriched_data:
                    lead.extra_data = lead.extra_data or {}
                    lead.extra_data.update(enriched_data)
                
                processed_leads.append(lead)
                
            except Exception as e:
                logger.error(f"Error processing lead {lead.id}: {str(e)}")
                import traceback
                logger.error(traceback.format_exc())
                processed_leads.append(lead)
        
        return processed_leads
    
    def test_all_sources(self, limit_per_source: int = 2, 
                        include_disabled: bool = False,
                        process_leads: bool = False,
                        source_types: Optional[List[str]] = None) -> Dict[str, List[Lead]]:
        """
        Test scraping from all configured sources.
        
        Args:
            limit_per_source: Maximum leads per source
            include_disabled: Whether to include disabled sources
            process_leads: Whether to process leads with NLP and enrichment
            source_types: List of source types to include (e.g. ['rss', 'news'])
            
        Returns:
            Dict[str, List[Lead]]: Dictionary of source IDs and their scraped leads
        """
        results = {}
        
        for source_id, source_config in self.sources.items():
            # Skip disabled sources unless explicitly included
            if not source_config.get('enabled', True) and not include_disabled:
                logger.info(f"Skipping disabled source: {source_id}")
                continue
            
            # Filter by source type if specified
            if source_types and source_config.get('type') not in source_types:
                logger.info(f"Skipping source {source_id} with type {source_config.get('type')}")
                continue
            
            leads = self.test_source(source_id, limit=limit_per_source, 
                                    process_leads=process_leads)
            
            results[source_id] = leads
        
        # Summary
        total_leads = sum(len(leads) for leads in results.values())
        total_sources = len(results)
        logger.info(f"Completed testing {total_sources} sources, found {total_leads} leads")
        
        return results
    
    def display_leads(self, leads: List[Lead]) -> None:
        """Display detailed lead information."""
        if not leads:
            print("\nNo leads found.")
            return
        
        print(f"\nDisplaying {len(leads)} leads:")
        print("=" * 80)
        
        for i, lead in enumerate(leads, 1):
            print(f"\nLead #{i}: {lead.id}")
            print("-" * 80)
            print(f"Title: {lead.project_name}")
            print(f"Source: {lead.source}")
            print(f"URL: {lead.source_url}")
            print(f"Market Sector: {lead.market_sector}")
            print(f"Location: {lead.location}")
            print(f"Confidence: {lead.confidence_score:.2f}")
            print(f"Retrieved: {lead.retrieved_date}")
            print(f"Value: ${lead.estimated_value:,.2f}" if lead.estimated_value else "Value: Unknown")
            
            if lead.description:
                print("\nDescription:")
                print(lead.description[:300] + "..." if len(lead.description) > 300 else lead.description)
            
            if lead.extra_data:
                print("\nExtra Data:")
                for key, value in lead.extra_data.items():
                    if isinstance(value, dict):
                        print(f"  {key}:")
                        for k, v in value.items():
                            print(f"    {k}: {v}")
                    else:
                        print(f"  {key}: {value}")
            
            print("=" * 80)
    
    def save_test_results(self, results: Dict[str, List[Lead]], 
                         output_path: Optional[str] = None) -> None:
        """Save test results to a file."""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"test_results/scraping_test_{timestamp}.json"
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Convert leads to JSON-serializable format
        serialized_results = {}
        for source_id, leads in results.items():
            serialized_results[source_id] = [lead.dict() for lead in leads]
        
        # Save to file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(serialized_results, f, indent=2, default=str)
        
        logger.info(f"Test results saved to: {output_path}")
    
    def store_leads(self, leads: List[Lead]) -> int:
        """Store leads in the database."""
        stored_count = 0
        for lead in leads:
            try:
                lead_id = self.storage.store_lead(lead)
                if lead_id:
                    stored_count += 1
            except Exception as e:
                logger.error(f"Error storing lead: {str(e)}")
        
        logger.info(f"Stored {stored_count} leads in database")
        return stored_count


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Test the lead scraping functionality in a simulated live environment"
    )
    
    parser.add_argument(
        "--source", "-s",
        help="ID of the specific source to test (omit to list all sources)",
        type=str,
        default=None
    )
    
    parser.add_argument(
        "--all", "-a",
        help="Test all available sources",
        action="store_true"
    )
    
    parser.add_argument(
        "--type", "-t",
        help="Filter sources by type (rss, news, city_portal)",
        type=str,
        choices=["rss", "news", "city_portal"],
        default=None
    )
    
    parser.add_argument(
        "--limit", "-l",
        help="Maximum number of leads to retrieve per source",
        type=int,
        default=5
    )
    
    parser.add_argument(
        "--process", "-p",
        help="Process leads with NLP and enrichment",
        action="store_true"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        help="Show detailed information about each lead",
        action="store_true"
    )
    
    parser.add_argument(
        "--store", 
        help="Store the retrieved leads in the database",
        action="store_true"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Save test results to the specified file",
        type=str,
        default=None
    )
    
    parser.add_argument(
        "--include-disabled",
        help="Include disabled sources when testing all",
        action="store_true"
    )
    
    args = parser.parse_args()
    
    # Create tester
    tester = LiveScrapingTester(verbose=args.verbose)
    
    if args.source:
        # Test specific source
        leads = tester.test_source(args.source, limit=args.limit, 
                                  process_leads=args.process)
        
        if args.store and leads:
            tester.store_leads(leads)
        
        if args.output:
            tester.save_test_results({args.source: leads}, args.output)
            
    elif args.all:
        # Test all sources
        source_types = [args.type] if args.type else None
        results = tester.test_all_sources(
            limit_per_source=args.limit,
            include_disabled=args.include_disabled,
            process_leads=args.process,
            source_types=source_types
        )
        
        # Get flat list of all leads
        all_leads = [lead for leads in results.values() for lead in leads]
        
        if args.store and all_leads:
            tester.store_leads(all_leads)
        
        if args.output:
            tester.save_test_results(results, args.output)
    else:
        # No source specified, list available sources
        tester.list_sources()


if __name__ == "__main__":
    main()
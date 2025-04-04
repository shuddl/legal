#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Main entry point for the Perera Construction Lead Scraper.

This module initializes the application, sets up logging, and provides
the main command-line interface.
"""

import os
import sys
import argparse
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from perera_lead_scraper.config import config
from perera_lead_scraper.utils.logger import configure_logger
from perera_lead_scraper.utils.source_registry import SourceRegistry
from perera_lead_scraper.scrapers.scraper_manager import ScraperManager


def setup_argparse() -> argparse.ArgumentParser:
    """
    Set up command-line argument parsing.

    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="Perera Construction Lead Scraper",
        epilog="A tool for finding and managing construction project leads from various sources.",
    )

    # Main commands
    parser.add_argument(
        "command",
        choices=[
            "run",
            "status",
            "test-sources",
            "export",
            "sync-hubspot",
            "list-sources",
            "analyze-legal",
            "discover-legal-leads",
        ],
        help="Command to execute",
    )

    # Run options
    parser.add_argument(
        "--source",
        type=str,
        help="Run only a specific source (by name)",
    )
    parser.add_argument(
        "--source-type",
        type=str,
        choices=["rss", "website", "city_portal", "permit_database", "api", "legal"],
        help="Run only sources of a specific type",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=config.max_leads_per_run,
        help=f"Maximum number of leads to process (default: {config.max_leads_per_run})",
    )

    # Export options
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path for exports",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["csv", "json"],
        default="csv",
        help="Export format (default: csv)",
    )
    
    # Testing options
    parser.add_argument(
        "--deep-check",
        action="store_true",
        help="Perform deep checks when testing sources",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Number of parallel workers (default: 10)",
    )

    # Legal document analysis options
    parser.add_argument(
        "--file",
        type=str,
        help="Legal document file to analyze",
    )
    parser.add_argument(
        "--directory",
        type=str,
        help="Directory of legal documents to analyze",
    )
    parser.add_argument(
        "--provider",
        type=str,
        help="Legal API provider to use",
    )
    parser.add_argument(
        "--location",
        type=str,
        help="Location to filter legal documents by",
    )
    parser.add_argument(
        "--document-type",
        type=str,
        choices=["permit", "contract", "zoning", "regulatory"],
        help="Type of legal document to process",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Number of days to look back for API sources (default: 14)",
    )

    # Common options
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level",
    )
    parser.add_argument(
        "--config-dir",
        type=str,
        help="Custom configuration directory path",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version information",
    )

    return parser


def run_scraper(
    source: Optional[str] = None,
    source_type: Optional[str] = None,
    limit: int = 100,
) -> bool:
    """
    Run the scraper with the specified options.

    Args:
        source: Specific source to run (by name)
        source_type: Run only sources of this type
        limit: Maximum number of leads to process

    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    logger.info("Initializing scraper manager")
    
    # Initialize source registry
    registry = SourceRegistry(str(config.sources_path))
    if not registry:
        logger.error("Failed to initialize source registry")
        return False
    
    # Initialize scraper manager
    manager = ScraperManager(registry)
    
    # Execute scraping
    try:
        if source:
            logger.info(f"Running scraper for source: {source}")
            success = manager.run_scraper(source)
        elif source_type:
            logger.info(f"Running scrapers of type: {source_type}")
            success = manager.run_scrapers_by_type(source_type)
        else:
            logger.info("Running all active scrapers")
            success = manager.run_all_scrapers()
        
        if not success:
            logger.error("Failed to execute scrapers")
            return False
        
        logger.info("Scraping completed successfully")
        return True
    
    except Exception as e:
        logger.exception(f"Error running scrapers: {str(e)}")
        return False


def test_sources(deep_check: bool = False, workers: int = 10) -> bool:
    """
    Test the availability and health of configured sources.

    Args:
        deep_check: Whether to perform deep checks (browser-based)
        workers: Number of parallel workers

    Returns:
        bool: True if all tests passed, False otherwise
    """
    logger = logging.getLogger(__name__)
    logger.info("Testing source availability")
    
    try:
        from perera_lead_scraper.utils.source_tester import SourceTester
        
        # Initialize source registry
        registry = SourceRegistry(str(config.sources_path))
        
        # Create arguments namespace
        class Args:
            def __init__(self):
                self.deep_web_check = deep_check
                self.workers = workers
                self.timeout = 15
                self.retries = 3
                self.verbose = config.debug_mode
                self.output = None
        
        # Run tests
        tester = SourceTester(registry, Args())
        results = tester.test_all_sources()
        
        # Print report
        tester.print_report()
        
        # Determine success based on high-value source availability
        summary, failed, low_value = tester.generate_report()
        success_rate = summary["success_percent"]
        
        logger.info(f"Source test completed. Success rate: {success_rate}%")
        
        # Consider test successful if at least 70% of sources are available
        return success_rate >= 70.0
    
    except Exception as e:
        logger.exception(f"Error testing sources: {str(e)}")
        return False


def export_leads(output: Optional[str] = None, format: str = "csv") -> bool:
    """
    Export leads to a file.

    Args:
        output: Output file path
        format: Export format (csv or json)

    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        from perera_lead_scraper.utils.storage import LeadStorage
        from datetime import datetime
        
        # Initialize storage
        storage = LeadStorage()
        
        # Determine output file path
        if not output:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output = str(config.DATA_DIR / f"leads_export_{timestamp}.{format}")
        
        # Export based on format
        if format.lower() == "csv":
            file_path = storage.export_leads_to_csv(output)
            logger.info(f"Exported leads to CSV: {file_path}")
        elif format.lower() == "json":
            file_path = storage.export_leads_to_json(output)
            logger.info(f"Exported leads to JSON: {file_path}")
        else:
            logger.error(f"Unsupported export format: {format}")
            return False
        
        return True
    
    except Exception as e:
        logger.exception(f"Error exporting leads: {str(e)}")
        return False


def sync_with_hubspot() -> bool:
    """
    Synchronize leads with HubSpot CRM.

    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    if not config.hubspot_api_key:
        logger.error("HUBSPOT_API_KEY not configured")
        return False
    
    try:
        from perera_lead_scraper.utils.storage import LeadStorage
        from perera_lead_scraper.integrations.hubspot_client import HubSpotClient
        
        # Initialize storage and HubSpot client
        storage = LeadStorage()
        hubspot = HubSpotClient(config.hubspot_api_key, str(config.hubspot_config_path))
        
        # Get leads to sync
        from perera_lead_scraper.models.lead import LeadStatus
        leads, total = storage.get_leads_by_status(LeadStatus.VALIDATED)
        
        if not leads:
            logger.info("No validated leads to sync with HubSpot")
            return True
        
        logger.info(f"Syncing {len(leads)} leads with HubSpot")
        
        # Sync leads
        result_map = hubspot.sync_leads(leads)
        
        # Update lead statuses
        for lead_id, hubspot_id in result_map.items():
            if hubspot_id:
                storage.update_lead_status(lead_id, LeadStatus.EXPORTED)
        
        logger.info(f"Successfully synced {len(result_map)} leads with HubSpot")
        return True
    
    except Exception as e:
        logger.exception(f"Error syncing with HubSpot: {str(e)}")
        return False


def list_sources() -> bool:
    """
    List all configured sources.

    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        from perera_lead_scraper.utils.source_registry import SourceRegistry
        
        # Initialize source registry
        registry = SourceRegistry(str(config.sources_path))
        
        # Get all sources
        sources = registry.sources.values()
        active_sources = [s for s in sources if s.active]
        inactive_sources = [s for s in sources if not s.active]
        
        # Print source information
        print(f"Total sources: {len(sources)}")
        print(f"Active sources: {len(active_sources)}")
        print(f"Inactive sources: {len(inactive_sources)}")
        print("\nActive sources:")
        
        for source in active_sources:
            status = source.status or "unknown"
            print(f"- {source.name} ({source.type}) - {status}")
        
        if inactive_sources and logger.level <= logging.INFO:
            print("\nInactive sources:")
            for source in inactive_sources:
                print(f"- {source.name} ({source.type})")
        
        return True
    
    except Exception as e:
        logger.exception(f"Error listing sources: {str(e)}")
        return False


def show_status() -> bool:
    """
    Show application status information.

    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        from perera_lead_scraper.utils.storage import LeadStorage
        from perera_lead_scraper.utils.source_registry import SourceRegistry
        import perera_lead_scraper
        
        # Print version and configuration
        print(f"Perera Construction Lead Scraper v{perera_lead_scraper.__version__}")
        print(f"Configuration:")
        print(f"  Database: {config.db_path}")
        print(f"  Log file: {config.log_file_path}")
        print(f"  Sources config: {config.sources_path}")
        
        # Initialize storage and source registry
        storage = LeadStorage()
        registry = SourceRegistry(str(config.sources_path))
        
        # Get source statistics
        sources = registry.sources.values()
        active_sources = [s for s in sources if s.active]
        
        # Get lead statistics
        lead_counts_by_status = storage.count_leads_by_status()
        lead_counts_by_source = storage.count_leads_by_source()
        lead_counts_by_sector = storage.count_leads_by_market_sector()
        
        # Print lead statistics
        total_leads = sum(lead_counts_by_status.values())
        print(f"\nLead Statistics:")
        print(f"  Total leads: {total_leads}")
        
        print(f"\n  Leads by status:")
        for status, count in lead_counts_by_status.items():
            print(f"    {status}: {count}")
        
        print(f"\n  Leads by market sector:")
        for sector, count in lead_counts_by_sector.items():
            print(f"    {sector}: {count}")
        
        print(f"\n  Top sources by lead count:")
        sources_by_count = sorted(
            [(s, lead_counts_by_source.get(s, 0)) for s in lead_counts_by_source],
            key=lambda x: x[1],
            reverse=True
        )
        for source, count in sources_by_count[:5]:  # Show top 5
            print(f"    {source}: {count}")
        
        return True
    
    except Exception as e:
        logger.exception(f"Error showing status: {str(e)}")
        return False


def analyze_legal_document(
    file_path: Optional[str] = None,
    directory_path: Optional[str] = None,
    document_type: Optional[str] = None
) -> bool:
    """
    Analyze legal documents and display results.

    Args:
        file_path: Path to a single legal document file
        directory_path: Path to a directory of legal documents
        document_type: Type of legal document

    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        from perera_lead_scraper.legal.legal_document_analyzer import LegalDocumentAnalyzer
        
        # Initialize analyzer
        analyzer = LegalDocumentAnalyzer()
        
        # Process a single file
        if file_path:
            path = Path(file_path)
            if not path.exists() or not path.is_file():
                logger.error(f"File not found: {file_path}")
                return False
            
            logger.info(f"Analyzing legal document: {path}")
            
            # Parse the document
            document_text = analyzer.document_parser.parse_file(path)
            
            # Analyze the document
            analysis = analyzer.analyze_document(document_text, document_type)
            
            # Print analysis results
            print(f"Document Analysis Results for {path.name}:")
            print(f"  Document Type: {analysis.get('document_type', 'unknown')}")
            print(f"  Lead Potential: {analysis.get('lead_potential', 0.0):.2f}")
            print(f"  Lead Category: {analysis.get('lead_category', 'unknown')}")
            print(f"  Meets Requirements: {analysis.get('meets_requirements', False)}")
            
            if analysis.get("project_value"):
                print(f"  Estimated Value: ${analysis.get('project_value'):,.2f}")
            
            if analysis.get("market_sector"):
                print(f"  Market Sector: {analysis.get('market_sector')}")
            
            if analysis.get("locations"):
                print(f"  Locations: {', '.join(analysis.get('locations', []))}")
            
            if analysis.get("meets_requirements", False):
                # Extract a lead
                lead = analyzer.extract_leads_from_document(document_text, document_type)
                if lead:
                    print(f"\nLead Extracted:")
                    print(f"  Title: {lead.title}")
                    if lead.project_value:
                        print(f"  Value: ${lead.project_value:,.2f}")
                    print(f"  Market Sector: {lead.market_sector}")
                    print(f"  Confidence: {lead.confidence:.2f}")
                    print(f"  Location: {lead.location}")
            
            return True
        
        # Process a directory of documents
        elif directory_path:
            path = Path(directory_path)
            if not path.exists() or not path.is_dir():
                logger.error(f"Directory not found: {directory_path}")
                return False
            
            logger.info(f"Processing legal documents in: {path}")
            
            # Extract leads from documents
            leads = analyzer.extract_leads_from_local_documents(path)
            
            # Print results
            print(f"Extracted {len(leads)} leads from {path}:")
            for i, lead in enumerate(leads, 1):
                print(f"\n{i}. {lead.title}")
                if lead.project_value:
                    print(f"   Value: ${lead.project_value:,.2f}")
                print(f"   Market Sector: {lead.market_sector}")
                print(f"   Confidence: {lead.confidence:.2f}")
                print(f"   Location: {lead.location}")
            
            return True
        
        else:
            logger.error("No file or directory specified for legal document analysis")
            return False
    
    except Exception as e:
        logger.exception(f"Error analyzing legal documents: {str(e)}")
        return False


def discover_legal_leads(
    provider: Optional[str] = None,
    location: Optional[str] = None,
    document_type: Optional[str] = None,
    days: int = 14
) -> bool:
    """
    Discover leads from legal document APIs.

    Args:
        provider: API provider to use
        location: Location to filter by
        document_type: Type of document to search for
        days: Number of days to look back

    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger(__name__)
    
    try:
        from perera_lead_scraper.legal.legal_document_analyzer import LegalDocumentAnalyzer
        from perera_lead_scraper.utils.storage import LeadStorage
        
        # Initialize analyzer and storage
        analyzer = LegalDocumentAnalyzer()
        storage = LeadStorage()
        
        # Discover leads from specific provider or all configured sources
        if provider:
            logger.info(f"Discovering leads from {provider} API")
            leads = analyzer.extract_leads_from_api(
                provider=provider,
                location=location,
                document_type=document_type,
                days=days
            )
        else:
            logger.info("Discovering leads from all configured legal sources")
            leads = analyzer.discover_leads_from_multiple_sources()
        
        # Print discovery results
        print(f"Discovered {len(leads)} leads from legal documents:")
        for i, lead in enumerate(leads, 1):
            print(f"\n{i}. {lead.title}")
            if lead.project_value:
                print(f"   Value: ${lead.project_value:,.2f}")
            print(f"   Market Sector: {lead.market_sector}")
            print(f"   Confidence: {lead.confidence:.2f}")
            print(f"   Source: {lead.source}")
            print(f"   Location: {lead.location}")
        
        # Ask if leads should be stored
        if leads and input("\nStore these leads? (y/n): ").lower().startswith("y"):
            for lead in leads:
                storage.store_lead(lead)
            print(f"Stored {len(leads)} leads in the database")
        
        return True
    
    except Exception as e:
        logger.exception(f"Error discovering legal leads: {str(e)}")
        return False


def main() -> int:
    """
    Main entry point for the application.

    Returns:
        int: Exit code (0 for success, non-zero for failure)
    """
    # Parse command-line arguments
    parser = setup_argparse()
    args = parser.parse_args()
    
    # Show version and exit if requested
    if args.version:
        import perera_lead_scraper
        print(f"Perera Construction Lead Scraper v{perera_lead_scraper.__version__}")
        return 0
    
    # Override log level if specified
    if args.log_level:
        config.log_level = getattr(logging, args.log_level)
    
    # Configure logging
    logger = configure_logger(
        level=logging.DEBUG if args.verbose else config.log_level,
        log_file=str(config.log_file_path),
    )
    
    # Validate configuration
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        return 1
    
    # Execute the requested command
    try:
        if args.command == "run":
            success = run_scraper(args.source, args.source_type, args.limit)
        elif args.command == "status":
            success = show_status()
        elif args.command == "test-sources":
            success = test_sources(args.deep_check, args.workers)
        elif args.command == "export":
            success = export_leads(args.output, args.format)
        elif args.command == "sync-hubspot":
            success = sync_with_hubspot()
        elif args.command == "list-sources":
            success = list_sources()
        elif args.command == "analyze-legal":
            success = analyze_legal_document(args.file, args.directory, args.document_type)
        elif args.command == "discover-legal-leads":
            success = discover_legal_leads(args.provider, args.location, args.document_type, args.days)
        else:
            logger.error(f"Unknown command: {args.command}")
            return 1
        
        return 0 if success else 1
    
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        return 130  # Standard exit code for SIGINT
    except Exception as e:
        logger.exception(f"Unhandled error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
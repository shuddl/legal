#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lead Viewer Utility

This script allows viewing and analyzing leads that have been collected and stored
in the database. It provides filtering, sorting, and export capabilities.
"""

import os
import sys
import logging
import argparse
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from tabulate import tabulate

# Add the project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.perera_lead_scraper.utils.storage import LeadStorage
from src.perera_lead_scraper.config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("lead_viewer")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="View and analyze stored leads")
    
    # Filtering options
    parser.add_argument("--source", type=str, help="Filter by source")
    parser.add_argument("--category", type=str, help="Filter by category")
    parser.add_argument("--min-confidence", type=float, help="Minimum confidence score")
    parser.add_argument("--days", type=int, default=30, help="Max age in days (0 = no limit)")
    parser.add_argument("--tag", type=str, help="Filter by tag")
    parser.add_argument("--location", type=str, help="Filter by location (city, state, etc.)")
    
    # Output options
    parser.add_argument("--limit", type=int, default=20, help="Limit number of results")
    parser.add_argument("--format", choices=["table", "json", "csv"], default="table", help="Output format")
    parser.add_argument("--output", type=str, help="Output file path (if not specified, prints to console)")
    parser.add_argument("--detail", action="store_true", help="Show detailed lead information")
    parser.add_argument("--sort-by", type=str, default="retrieved_date", help="Field to sort by")
    parser.add_argument("--desc", action="store_true", help="Sort in descending order")
    
    return parser.parse_args()


def filter_leads(leads, args):
    """Filter leads based on command line arguments."""
    filtered_leads = leads
    
    # Filter by source
    if args.source:
        filtered_leads = [lead for lead in filtered_leads if args.source.lower() in (lead.source or "").lower()]
    
    # Filter by category
    if args.category:
        filtered_leads = [lead for lead in filtered_leads 
                         if lead.market_sector and args.category.lower() in lead.market_sector.lower()]
    
    # Filter by confidence score
    if args.min_confidence:
        filtered_leads = [lead for lead in filtered_leads 
                         if getattr(lead, "confidence_score", 0) >= args.min_confidence]
    
    # Filter by age
    if args.days > 0:
        cutoff_date = datetime.now() - timedelta(days=args.days)
        filtered_leads = [lead for lead in filtered_leads 
                         if not lead.retrieved_date or lead.retrieved_date >= cutoff_date]
    
    # Filter by tag (checking in metadata or tags)
    if args.tag:
        filtered_leads = [lead for lead in filtered_leads 
                         if (hasattr(lead, "tags") and args.tag.lower() in [t.lower() for t in lead.tags])
                         or (hasattr(lead, "metadata") and lead.metadata and 
                             args.tag.lower() in str(lead.metadata).lower())]
    
    # Filter by location
    if args.location:
        location_query = args.location.lower()
        filtered_leads = [lead for lead in filtered_leads 
                         if (hasattr(lead, "location") and lead.location and 
                            (location_query in (getattr(lead.location, "city", "") or "").lower() or
                             location_query in (getattr(lead.location, "state", "") or "").lower() or
                             location_query in (getattr(lead.location, "address", "") or "").lower()))]
    
    return filtered_leads


def format_lead_for_display(lead, detailed=False):
    """Format a lead for display in a table."""
    if not detailed:
        # Basic information
        return {
            "ID": getattr(lead, "id", ""),
            "Title": getattr(lead, "project_name", getattr(lead, "title", "")),
            "Source": getattr(lead, "source", ""),
            "Market Sector": getattr(lead, "market_sector", ""),
            "Location": str(getattr(lead, "location", "")),
            "Confidence": f"{getattr(lead, 'confidence_score', 0):.2f}",
            "Retrieved": getattr(lead, "retrieved_date", "").strftime("%Y-%m-%d") if getattr(lead, "retrieved_date", None) else ""
        }
    else:
        # Detailed information
        lead_data = {
            "ID": getattr(lead, "id", ""),
            "Title": getattr(lead, "project_name", getattr(lead, "title", "")),
            "Description": getattr(lead, "description", "")[:100] + "..." if len(getattr(lead, "description", "") or "") > 100 else getattr(lead, "description", ""),
            "Source": getattr(lead, "source", ""),
            "Source URL": str(getattr(lead, "source_url", "")),
            "Market Sector": getattr(lead, "market_sector", ""),
            "Location": str(getattr(lead, "location", "")),
            "Project Value": getattr(lead, "estimated_value", ""),
            "Status": getattr(lead, "status", ""),
            "Confidence": f"{getattr(lead, 'confidence_score', 0):.2f}",
            "Publication Date": getattr(lead, "publication_date", "").strftime("%Y-%m-%d") if getattr(lead, "publication_date", None) else "",
            "Retrieved Date": getattr(lead, "retrieved_date", "").strftime("%Y-%m-%d") if getattr(lead, "retrieved_date", None) else ""
        }
        
        # Add contacts if available
        if hasattr(lead, "contacts") and lead.contacts:
            lead_data["Contacts"] = ", ".join([contact.name for contact in lead.contacts])
        
        return lead_data


def sort_leads(leads, sort_field, descending=False):
    """Sort leads by the specified field."""
    def _get_sort_key(lead):
        if sort_field == "retrieved_date":
            return getattr(lead, "retrieved_date", datetime.min)
        elif sort_field == "publication_date":
            return getattr(lead, "publication_date", datetime.min)
        elif sort_field == "confidence":
            return getattr(lead, "confidence_score", 0)
        elif sort_field == "title" or sort_field == "project_name":
            return getattr(lead, "project_name", getattr(lead, "title", "")).lower()
        elif sort_field == "source":
            return getattr(lead, "source", "").lower()
        elif sort_field == "market_sector":
            return getattr(lead, "market_sector", "").lower()
        else:
            # Default fallback
            return getattr(lead, sort_field, None) or ""
    
    return sorted(leads, key=_get_sort_key, reverse=descending)


def output_leads(leads, args):
    """Output leads in the specified format."""
    # Apply sorting
    if args.sort_by:
        sort_field = args.sort_by
        leads = sort_leads(leads, sort_field, args.desc)
    
    # Apply limit
    if args.limit > 0:
        leads = leads[:args.limit]
    
    # Format leads for output
    lead_data = [format_lead_for_display(lead, args.detail) for lead in leads]
    
    # Output based on specified format
    if args.format == "json":
        output = json.dumps(lead_data, indent=2, default=str)
    elif args.format == "csv":
        output = ""
        if not lead_data:
            return "No leads found."
        
        fields = lead_data[0].keys()
        output_buffer = []
        csv_writer = csv.DictWriter(output_buffer, fieldnames=fields)
        csv_writer.writeheader()
        for lead in lead_data:
            csv_writer.writerow(lead)
        output = "\n".join(output_buffer)
    else:  # table
        if not lead_data:
            return "No leads found."
        output = tabulate(lead_data, headers="keys", tablefmt="grid")
    
    # Write to file if specified
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        return f"Written {len(leads)} leads to {args.output}"
    else:
        # Return for printing
        return output


def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        # Initialize storage
        storage = LeadStorage()
        
        # Get all leads
        all_leads = storage.get_all_leads()
        logger.info(f"Retrieved {len(all_leads)} leads from storage")
        
        # Filter leads
        filtered_leads = filter_leads(all_leads, args)
        logger.info(f"Filtered to {len(filtered_leads)} leads")
        
        # Output results
        result = output_leads(filtered_leads, args)
        print(result)
        
        return 0
    except Exception as e:
        logger.exception(f"Error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HubSpot Mapper Usage Example

Demonstrates how to use the HubSpotMapper class to transform internal Lead objects
to HubSpot API format for use with the HubSpotClient.
"""

from typing import Dict, List, Any, Optional, Tuple
from uuid import uuid4
from datetime import datetime
from pydantic import HttpUrl

from models.lead import Lead, Contact, Location, LeadStatus, MarketSector, LeadType
from src.perera_lead_scraper.hubspot.hubspot_mapper import HubSpotMapper
from integrations.hubspot_client import HubSpotClient


def example_usage():
    """
    Example of how to use the HubSpotMapper with the HubSpotClient.
    """
    # Create a test lead
    lead = Lead(
        id=uuid4(),
        source="city_portal",
        source_id="CP12345",
        source_url=HttpUrl("https://example.com/projects/12345"),
        project_name="New Hospital Building",
        description="Construction of a new 50,000 sq ft hospital wing",
        market_sector=MarketSector.HEALTHCARE,
        lead_type=LeadType.NEW_CONSTRUCTION,
        status=LeadStatus.NEW,
        estimated_value=5000000.0,
        estimated_square_footage=50000,
        location=Location(
            address="123 Main St",
            city="Boston",
            state="MA",
            zip_code="02110"
        ),
        contacts=[
            Contact(
                name="Jane Doe",
                title="Project Manager",
                email="jane@example.com",
                phone="(555) 123-4567"
            )
        ],
        publication_date=datetime.now(),
        retrieved_date=datetime.now(),
        confidence_score=0.95
    )
    
    # Initialize the mapper
    mapper = HubSpotMapper()
    
    # Map the lead to HubSpot format
    company, contact, deal = mapper.map_lead_to_hubspot(lead)
    
    print("Company Properties:")
    print(company)
    print("\nContact Properties:")
    print(contact)
    print("\nDeal Properties:")
    print(deal)
    
    # Example of how to use with HubSpotClient (commented out for example only)
    """
    # Initialize the HubSpot client
    hubspot_client = HubSpotClient()
    
    # Create company
    company_id = hubspot_client.create_company(company)
    
    # Create contact
    contact_id = None
    if contact:
        contact_id = hubspot_client.create_contact(contact)
    
    # Create deal
    deal_id = hubspot_client.create_or_update_deal(deal)
    
    # Associate company to deal
    if company_id and deal_id:
        hubspot_client.associate_company_to_deal(company_id, deal_id)
    
    # Associate contact to deal
    if contact_id and deal_id:
        hubspot_client.associate_contact_to_deal(contact_id, deal_id)
    """


if __name__ == "__main__":
    example_usage()
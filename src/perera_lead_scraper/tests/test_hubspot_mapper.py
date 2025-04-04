#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Test HubSpot Mapper

Tests for the HubSpot data mapper, ensuring leads are properly formatted for HubSpot.
"""

import os
import unittest
from uuid import uuid4
from datetime import datetime
from unittest.mock import patch, MagicMock
from pydantic import HttpUrl

from models.lead import Lead, Contact, Location, LeadStatus, MarketSector, LeadType
from src.perera_lead_scraper.hubspot.hubspot_mapper import HubSpotMapper


class TestHubSpotMapper(unittest.TestCase):
    """Tests for the HubSpot mapper."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock config for testing
        config_patcher = patch('src.perera_lead_scraper.hubspot.hubspot_mapper.config')
        self.mock_config = config_patcher.start()
        self.mock_config.hubspot_config_path.return_value = "mock_path"
        self.mock_config.hubspot_property_ids = {
            "lead_source": "prop_lead_source",
            "source_url": "prop_source_url",
            "source_id": "prop_source_id",
            "lead_id": "prop_lead_id",
            "publication_date": "prop_publication_date",
            "retrieved_date": "prop_retrieved_date",
            "confidence_score": "prop_confidence_score",
            "location_city": "prop_location_city",
            "location_state": "prop_location_state",
            "estimated_square_footage": "prop_est_sq_footage",
        }
        self.mock_config.hubspot_dealstage_ids = {
            "new": "stage_new",
            "processing": "stage_processing",
            "validated": "stage_validated",
            "enriched": "stage_enriched",
            "exported": "stage_exported",
            "archived": "stage_archived",
            "rejected": "stage_rejected",
        }
        self.addCleanup(config_patcher.stop)
        
        # Create a mapper with a mocked config loader
        with patch.object(HubSpotMapper, '_load_config') as mock_load_config:
            mock_load_config.return_value = {
                "field_mappings": {
                    "contact": {
                        "name": "firstname",
                        "company": "company",
                        "email": "email",
                        "phone": "phone",
                        "title": "title"
                    },
                    "deal": {
                        "project_name": "dealname",
                        "description": "description",
                        "estimated_value": "amount",
                        "market_sector": "industry",
                        "lead_type": "deal_type",
                        "status": "dealstage",
                        "source": "lead_source"
                    }
                },
                "deal_stages": {
                    "new": "qualifiedtobuy",
                    "processing": "decisionmakerboughtin",
                    "validated": "contractsent",
                    "enriched": "closedwon",
                    "exported": "closedwon",
                    "archived": "closedlost",
                    "rejected": "closedlost"
                },
                "deal_pipeline": "default"
            }
            self.mapper = HubSpotMapper()
    
    def test_map_contact(self):
        """Test mapping a contact to HubSpot format."""
        # Test with a valid contact
        contact = Contact(
            name="Jane Doe",
            title="Project Manager",
            company="ABC Construction",
            email="jane@example.com",
            phone="(555) 123-4567"
        )
        
        contact_properties = self.mapper.map_contact(contact)
        
        self.assertIsNotNone(contact_properties)
        self.assertEqual(contact_properties["firstname"], "Jane Doe")
        self.assertEqual(contact_properties["title"], "Project Manager")
        self.assertEqual(contact_properties["company"], "ABC Construction")
        self.assertEqual(contact_properties["email"], "jane@example.com")
        self.assertEqual(contact_properties["phone"], "(555) 123-4567")
        
        # Test with a contact missing email (should return None)
        contact_no_email = Contact(
            name="John Smith",
            title="Engineer"
        )
        
        contact_properties = self.mapper.map_contact(contact_no_email)
        self.assertIsNone(contact_properties)
    
    def test_map_company(self):
        """Test mapping a lead to a HubSpot company."""
        lead = Lead(
            id=uuid4(),
            source="city_portal",
            project_name="New Hospital Building",
            description="Construction of a new 50,000 sq ft hospital wing",
            market_sector=MarketSector.HEALTHCARE,
            location=Location(
                address="123 Main St",
                city="Boston",
                state="MA",
                zip_code="02110"
            )
        )
        
        company_properties = self.mapper.map_company(lead)
        
        self.assertEqual(company_properties["name"], "New Hospital Building")
        self.assertEqual(company_properties["address"], "123 Main St")
        self.assertEqual(company_properties["city"], "Boston")
        self.assertEqual(company_properties["state"], "MA")
        self.assertEqual(company_properties["zip"], "02110")
        self.assertEqual(company_properties["industry"], "healthcare")
    
    def test_map_deal(self):
        """Test mapping a lead to a HubSpot deal."""
        lead_id = uuid4()
        publication_date = datetime.now()
        retrieved_date = datetime.now()
        
        lead = Lead(
            id=lead_id,
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
            publication_date=publication_date,
            retrieved_date=retrieved_date,
            confidence_score=0.95
        )
        
        deal_properties = self.mapper.map_deal(lead)
        
        # Check standard fields
        self.assertEqual(deal_properties["dealname"], "New Hospital Building")
        self.assertEqual(deal_properties["description"], "Construction of a new 50,000 sq ft hospital wing")
        self.assertEqual(deal_properties["amount"], 5000000.0)
        self.assertEqual(deal_properties["industry"], "healthcare")
        self.assertEqual(deal_properties["deal_type"], "new_construction")
        
        # Check location fields
        self.assertEqual(deal_properties["address"], "123 Main St")
        self.assertEqual(deal_properties["city"], "Boston")
        self.assertEqual(deal_properties["state"], "MA")
        self.assertEqual(deal_properties["zip"], "02110")
        
        # Check custom properties
        self.assertEqual(deal_properties["lead_source"], "city_portal")
        self.assertEqual(deal_properties["source_url"], "https://example.com/projects/12345")
        self.assertEqual(deal_properties["source_id"], "CP12345")
        self.assertEqual(deal_properties["lead_id"], str(lead_id))
        self.assertEqual(deal_properties["publication_date"], publication_date.strftime("%Y-%m-%d"))
        self.assertEqual(deal_properties["retrieved_date"], retrieved_date.strftime("%Y-%m-%d"))
        self.assertEqual(deal_properties["confidence_score"], 0.95)
        self.assertEqual(deal_properties["estimated_square_footage"], 50000)
        
        # Check deal stage mapping (should use ID from config)
        self.assertEqual(deal_properties["dealstage"], "stage_new")
        
        # Check pipeline
        self.assertEqual(deal_properties["pipeline"], "default")
    
    def test_map_lead_to_hubspot(self):
        """Test mapping a complete lead to HubSpot format."""
        lead = Lead(
            id=uuid4(),
            source="city_portal",
            project_name="New Hospital Building",
            description="Construction of a new 50,000 sq ft hospital wing",
            market_sector=MarketSector.HEALTHCARE,
            status=LeadStatus.NEW,
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
            ]
        )
        
        company, contact, deal = self.mapper.map_lead_to_hubspot(lead)
        
        # Check that all components were created
        self.assertIsNotNone(company)
        self.assertIsNotNone(contact)
        self.assertIsNotNone(deal)
        
        # Check basic fields from each component
        self.assertEqual(company["name"], "New Hospital Building")
        self.assertEqual(contact["firstname"], "Jane Doe")
        self.assertEqual(deal["dealname"], "New Hospital Building")
        
        # Test with no contacts
        lead.contacts = []
        company, contact, deal = self.mapper.map_lead_to_hubspot(lead)
        
        self.assertIsNotNone(company)
        self.assertIsNone(contact)  # Should be None when there are no contacts
        self.assertIsNotNone(deal)


if __name__ == '__main__':
    unittest.main()
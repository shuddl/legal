#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HubSpot Data Mapper

Maps internal lead data to HubSpot API format, handling the conversion between
Perera Construction Lead Scraper's data models and HubSpot's required formats.
"""

from typing import Dict, List, Any, Optional, Tuple, Union
import json
import os
from pathlib import Path

from models.lead import Lead, LeadStatus, MarketSector, LeadType, Contact, Location
from src.perera_lead_scraper.config import config

class HubSpotMapper:
    """
    Maps internal lead data to HubSpot format.
    
    Responsible for translating Lead objects and their related data into the
    format required by HubSpot's API, including mapping custom properties and
    deal stages.
    """
    
    def __init__(self):
        """Initialize the HubSpot mapper with configuration."""
        # Load HubSpot configuration
        self.config_path = config.hubspot_config_path
        self.config = self._load_config()
        
        # Extract relevant mappings
        self.field_mappings = self.config.get("field_mappings", {})
        self.deal_stages = self.config.get("deal_stages", {})
        self.custom_properties = self.config.get("custom_properties", {})
        self.deal_pipeline = self.config.get("deal_pipeline", "default")
        
        # HubSpot property IDs - would be loaded from environment variables or config
        self.hubspot_property_ids = {
            # Custom properties for deals
            "lead_source": config.hubspot_property_ids.get("lead_source", ""),
            "source_url": config.hubspot_property_ids.get("source_url", ""),
            "source_id": config.hubspot_property_ids.get("source_id", ""),
            "lead_id": config.hubspot_property_ids.get("lead_id", ""),
            "publication_date": config.hubspot_property_ids.get("publication_date", ""),
            "retrieved_date": config.hubspot_property_ids.get("retrieved_date", ""),
            "confidence_score": config.hubspot_property_ids.get("confidence_score", ""),
            "location_city": config.hubspot_property_ids.get("location_city", ""),
            "location_state": config.hubspot_property_ids.get("location_state", ""),
            "estimated_square_footage": config.hubspot_property_ids.get("estimated_square_footage", ""),
            
            # Deal stages
            "dealstage_new": config.hubspot_dealstage_ids.get("new", ""),
            "dealstage_processing": config.hubspot_dealstage_ids.get("processing", ""),
            "dealstage_validated": config.hubspot_dealstage_ids.get("validated", ""),
            "dealstage_enriched": config.hubspot_dealstage_ids.get("enriched", ""),
            "dealstage_exported": config.hubspot_dealstage_ids.get("exported", ""),
            "dealstage_archived": config.hubspot_dealstage_ids.get("archived", ""),
            "dealstage_rejected": config.hubspot_dealstage_ids.get("rejected", ""),
        }
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load HubSpot configuration from file.
        
        Returns:
            Dict[str, Any]: HubSpot configuration
        """
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                return {}
        except Exception as e:
            print(f"Error loading HubSpot configuration: {str(e)}")
            return {}
    
    def map_contact(self, contact: Contact) -> Optional[Dict[str, Any]]:
        """
        Map a Contact to HubSpot contact properties.
        
        Args:
            contact: Contact to map
        
        Returns:
            Optional[Dict[str, Any]]: HubSpot contact properties or None if no valid contact
        """
        if not contact or not contact.email:
            return None
        
        contact_mappings = self.field_mappings.get("contact", {})
        contact_properties = {}
        
        # Map standard properties
        for contact_field, hubspot_field in contact_mappings.items():
            if hasattr(contact, contact_field) and getattr(contact, contact_field) is not None:
                contact_properties[hubspot_field] = getattr(contact, contact_field)
        
        # Ensure required fields are present
        if "email" not in contact_properties or not contact_properties["email"]:
            return None
        
        return contact_properties
    
    def map_location(self, location: Location) -> Dict[str, Any]:
        """
        Map a Location to HubSpot location properties.
        
        Args:
            location: Location to map
        
        Returns:
            Dict[str, Any]: HubSpot location properties
        """
        location_properties = {}
        
        if location:
            if location.address:
                location_properties["address"] = location.address
            
            if location.city:
                location_properties["city"] = location.city
                location_properties["location_city"] = location.city
            
            if location.state:
                location_properties["state"] = location.state
                location_properties["location_state"] = location.state
            
            if location.zip_code:
                location_properties["zip"] = location.zip_code
        
        return location_properties
    
    def map_company(self, lead: Lead) -> Dict[str, Any]:
        """
        Map a Lead to HubSpot company properties.
        
        Args:
            lead: Lead to map
        
        Returns:
            Dict[str, Any]: HubSpot company properties
        """
        company_properties = {
            "name": lead.project_name
        }
        
        # Add location information
        company_properties.update(self.map_location(lead.location))
        
        # Add industry from market sector if available
        if lead.market_sector:
            sector_value = lead.market_sector.value if hasattr(lead.market_sector, "value") else lead.market_sector
            company_properties["industry"] = sector_value
        
        return company_properties
    
    def map_deal(self, lead: Lead) -> Dict[str, Any]:
        """
        Map a Lead to HubSpot deal properties.
        
        Args:
            lead: Lead to map
        
        Returns:
            Dict[str, Any]: HubSpot deal properties
        """
        deal_mappings = self.field_mappings.get("deal", {})
        deal_properties = {}
        
        # Map standard properties
        for lead_field, hubspot_field in deal_mappings.items():
            if hasattr(lead, lead_field) and getattr(lead, lead_field) is not None:
                value = getattr(lead, lead_field)
                
                # Convert enum values to strings
                if hasattr(value, "value"):
                    value = value.value
                
                deal_properties[hubspot_field] = value
        
        # Map location
        deal_properties.update(self.map_location(lead.location))
        
        # Add custom properties
        if lead.source:
            deal_properties["lead_source"] = lead.source
        
        if lead.source_url:
            deal_properties["source_url"] = str(lead.source_url)
        
        if lead.source_id:
            deal_properties["source_id"] = lead.source_id
        
        if lead.id:
            deal_properties["lead_id"] = str(lead.id)
        
        if lead.publication_date:
            deal_properties["publication_date"] = lead.publication_date.strftime("%Y-%m-%d")
        
        if lead.retrieved_date:
            deal_properties["retrieved_date"] = lead.retrieved_date.strftime("%Y-%m-%d")
        
        if lead.confidence_score is not None:
            deal_properties["confidence_score"] = lead.confidence_score
        
        if lead.estimated_square_footage is not None:
            deal_properties["estimated_square_footage"] = lead.estimated_square_footage
        
        # Map deal stage using IDs
        status_value = lead.status.value if hasattr(lead.status, "value") else lead.status
        deal_stage_key = f"dealstage_{status_value}"
        
        if deal_stage_key in self.hubspot_property_ids and self.hubspot_property_ids[deal_stage_key]:
            deal_properties["dealstage"] = self.hubspot_property_ids[deal_stage_key]
        elif status_value in self.deal_stages:
            # Fallback to name-based mapping
            deal_properties["dealstage"] = self.deal_stages[status_value]
        
        # Set pipeline
        if self.deal_pipeline:
            deal_properties["pipeline"] = self.deal_pipeline
        
        return deal_properties
    
    def map_lead_to_hubspot(self, lead: Lead) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]], Dict[str, Any]]:
        """
        Map a Lead to HubSpot company, contact, and deal properties.
        
        Args:
            lead: Lead to map
        
        Returns:
            Tuple containing:
            - Dict[str, Any]: Company properties
            - Optional[Dict[str, Any]]: Contact properties (or None if no valid contact)
            - Dict[str, Any]: Deal properties
        """
        company = self.map_company(lead)
        
        # Get primary contact if available
        contact = None
        if lead.contacts and len(lead.contacts) > 0:
            contact = self.map_contact(lead.contacts[0])
        
        deal = self.map_deal(lead)
        
        return company, contact, deal
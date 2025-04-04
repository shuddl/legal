#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
HubSpot API Integration

Provides a client for interacting with the HubSpot API to create and update leads.
"""

import os
import time
import json
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
import uuid

import hubspot
from hubspot.crm.contacts import ApiException as ContactsApiException
from hubspot.crm.contacts.exceptions import ApiException as ContactApiException
from hubspot.crm.deals import ApiException as DealsApiException
from hubspot.crm.properties import ApiException as PropertiesApiException
from hubspot.auth.oauth import ApiException as OAuthApiException
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from models.lead import Lead, LeadStatus, Location, Contact
from utils.logger import get_logger, log_integration_event, log_sensitive

# Configure logger
logger = get_logger(__name__)

# Constants
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_TIMEOUT = 30  # seconds
RATE_LIMIT_WAIT = 10  # seconds


class HubSpotClient:
    """
    Client for interacting with the HubSpot API.
    
    Handles creating and updating leads, contacts, and deals in HubSpot.
    """
    
    def __init__(self, api_key: Optional[str] = None, config_path: Optional[str] = None):
        """
        Initialize the HubSpot client.
        
        Args:
            api_key: HubSpot API key (or None to use environment variable)
            config_path: Path to configuration file (or None to use default)
        """
        # Get API key from environment if not provided
        self.api_key = api_key or os.environ.get("HUBSPOT_API_KEY")
        if not self.api_key:
            raise ValueError("HubSpot API key is required")
        
        # Initialize client
        self.client = hubspot.Client.create(api_key=self.api_key)
        
        # Load configuration
        self.config = self._load_config(config_path)
        
        # Cache for property definitions
        self.property_cache = {}
        
        # Track rate limiting
        self.last_request_time = 0
        self.min_request_interval = 0.1  # seconds
        
        log_integration_event("hubspot", "initialize", "Initialized HubSpot client")
    
    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load HubSpot configuration.
        
        Args:
            config_path: Path to configuration file
        
        Returns:
            Dict: Configuration dictionary
        """
        # Use default path if not provided
        if not config_path:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config',
                'hubspot_config.json'
            )
        
        # Check if file exists
        if not os.path.exists(config_path):
            logger.warning(f"HubSpot configuration file not found: {config_path}")
            return self._get_default_config()
        
        # Load configuration
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            logger.info(f"Loaded HubSpot configuration from {config_path}")
            return config
            
        except Exception as e:
            logger.error(f"Error loading HubSpot configuration: {str(e)}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default HubSpot configuration.
        
        Returns:
            Dict: Default configuration
        """
        return {
            "field_mappings": {
                "contact": {
                    "name": "firstname",
                    "company": "company",
                    "email": "email",
                    "phone": "phone"
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
            "custom_properties": {
                "contact": [
                    {
                        "name": "title",
                        "label": "Title",
                        "type": "string",
                        "group_name": "contactinformation"
                    }
                ],
                "deal": [
                    {
                        "name": "lead_source",
                        "label": "Lead Source",
                        "type": "string",
                        "group_name": "dealinformation"
                    },
                    {
                        "name": "source_url",
                        "label": "Source URL",
                        "type": "string",
                        "group_name": "dealinformation"
                    },
                    {
                        "name": "source_id",
                        "label": "Source ID",
                        "type": "string",
                        "group_name": "dealinformation"
                    },
                    {
                        "name": "publication_date",
                        "label": "Publication Date",
                        "type": "date",
                        "group_name": "dealinformation"
                    },
                    {
                        "name": "retrieved_date",
                        "label": "Retrieved Date",
                        "type": "date",
                        "group_name": "dealinformation"
                    },
                    {
                        "name": "confidence_score",
                        "label": "Confidence Score",
                        "type": "number",
                        "group_name": "dealinformation"
                    }
                ]
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
    
    def _delay_request(self) -> None:
        """
        Delay request to respect rate limits.
        """
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        
        self.last_request_time = time.time()
    
    @retry(
        stop=stop_after_attempt(DEFAULT_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=(
            retry_if_exception_type(ContactsApiException) |
            retry_if_exception_type(DealsApiException) |
            retry_if_exception_type(PropertiesApiException)
        )
    )
    def _make_api_request(self, request_func, *args, **kwargs) -> Any:
        """
        Make an API request with error handling and retries.
        
        Args:
            request_func: Function to call for the request
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
        
        Returns:
            Any: Response from the API
        """
        self._delay_request()
        
        try:
            return request_func(*args, **kwargs)
            
        except (ContactApiException, DealsApiException, PropertiesApiException) as e:
            # Check for rate limiting
            if e.status == 429:
                logger.warning("Rate limited by HubSpot API, waiting before retry")
                time.sleep(RATE_LIMIT_WAIT)
                raise
            
            # Log error details
            logger.error(f"HubSpot API error: {e.reason}")
            raise
    
    def map_lead_to_hubspot_properties(self, lead: Lead) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Map a lead to HubSpot properties.
        
        Args:
            lead: Lead to map
        
        Returns:
            Tuple containing:
            - Dict: Deal properties
            - List[Dict]: Contact properties
        """
        # Map deal properties
        deal_mappings = self.config.get("field_mappings", {}).get("deal", {})
        deal_properties = {}
        
        for lead_field, hubspot_field in deal_mappings.items():
            if hasattr(lead, lead_field) and getattr(lead, lead_field) is not None:
                value = getattr(lead, lead_field)
                
                # Convert enum values to strings
                if hasattr(value, "value"):
                    value = value.value
                
                # Convert dates to string
                if isinstance(value, datetime):
                    value = value.isoformat()
                
                deal_properties[hubspot_field] = value
        
        # Add custom properties
        if lead.source_url:
            deal_properties["source_url"] = str(lead.source_url)
        
        if lead.source_id:
            deal_properties["source_id"] = lead.source_id
        
        if lead.publication_date:
            deal_properties["publication_date"] = lead.publication_date.strftime("%Y-%m-%d")
        
        if lead.retrieved_date:
            deal_properties["retrieved_date"] = lead.retrieved_date.strftime("%Y-%m-%d")
        
        if lead.confidence_score is not None:
            deal_properties["confidence_score"] = lead.confidence_score
        
        # Map location
        if lead.location:
            location = lead.location
            if location.address:
                deal_properties["address"] = location.address
            
            if location.city:
                deal_properties["city"] = location.city
            
            if location.state:
                deal_properties["state"] = location.state
            
            if location.zip_code:
                deal_properties["zip"] = location.zip_code
        
        # Convert lead status to deal stage
        deal_stages = self.config.get("deal_stages", {})
        status_value = lead.status.value if hasattr(lead.status, "value") else lead.status
        if status_value in deal_stages:
            deal_properties["dealstage"] = deal_stages[status_value]
        
        # Set pipeline
        pipeline = self.config.get("deal_pipeline")
        if pipeline:
            deal_properties["pipeline"] = pipeline
        
        # Map contacts
        contact_mappings = self.config.get("field_mappings", {}).get("contact", {})
        contact_properties_list = []
        
        for contact in lead.contacts:
            contact_properties = {}
            
            for contact_field, hubspot_field in contact_mappings.items():
                if hasattr(contact, contact_field) and getattr(contact, contact_field) is not None:
                    contact_properties[hubspot_field] = getattr(contact, contact_field)
            
            # Set deal association
            if lead.project_name:
                # Add project name to the contact for reference
                contact_properties["company"] = lead.project_name
            
            # Only add contacts with email (required by HubSpot)
            if "email" in contact_properties and contact_properties["email"]:
                contact_properties_list.append(contact_properties)
        
        return deal_properties, contact_properties_list
    
    def check_existing_lead(self, lead_id: Optional[uuid.UUID] = None, 
                          source_id: Optional[str] = None,
                          source_url: Optional[str] = None) -> Optional[str]:
        """
        Check if a lead already exists in HubSpot.
        
        Args:
            lead_id: Lead ID
            source_id: Source-specific ID
            source_url: Source URL
        
        Returns:
            Optional[str]: HubSpot deal ID if found, None otherwise
        """
        if not any([lead_id, source_id, source_url]):
            logger.warning("No identifiers provided to check for existing lead")
            return None
        
        try:
            # Check by source ID if provided
            if source_id:
                search_request = {
                    "filterGroups": [
                        {
                            "filters": [
                                {
                                    "propertyName": "source_id",
                                    "operator": "EQ",
                                    "value": source_id
                                }
                            ]
                        }
                    ]
                }
                
                result = self._make_api_request(
                    self.client.crm.deals.search_api.do_search,
                    public_object_search_request=search_request
                )
                
                if result.results and len(result.results) > 0:
                    return result.results[0].id
            
            # Check by source URL if provided
            if source_url:
                search_request = {
                    "filterGroups": [
                        {
                            "filters": [
                                {
                                    "propertyName": "source_url",
                                    "operator": "EQ",
                                    "value": str(source_url)
                                }
                            ]
                        }
                    ]
                }
                
                result = self._make_api_request(
                    self.client.crm.deals.search_api.do_search,
                    public_object_search_request=search_request
                )
                
                if result.results and len(result.results) > 0:
                    return result.results[0].id
            
            # Check by custom lead ID property if provided
            if lead_id:
                search_request = {
                    "filterGroups": [
                        {
                            "filters": [
                                {
                                    "propertyName": "lead_id",
                                    "operator": "EQ",
                                    "value": str(lead_id)
                                }
                            ]
                        }
                    ]
                }
                
                result = self._make_api_request(
                    self.client.crm.deals.search_api.do_search,
                    public_object_search_request=search_request
                )
                
                if result.results and len(result.results) > 0:
                    return result.results[0].id
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking for existing lead: {str(e)}")
            return None
    
    def get_contact_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a contact by email.
        
        Args:
            email: Contact email
        
        Returns:
            Optional[Dict]: Contact data if found, None otherwise
        """
        try:
            # Create filter
            filter_query = {
                "filterGroups": [
                    {
                        "filters": [
                            {
                                "propertyName": "email",
                                "operator": "EQ",
                                "value": email
                            }
                        ]
                    }
                ]
            }
            
            # Search for contacts
            result = self._make_api_request(
                self.client.crm.contacts.search_api.do_search,
                public_object_search_request=filter_query
            )
            
            if result.results and len(result.results) > 0:
                # Get full contact details
                contact_id = result.results[0].id
                contact = self._make_api_request(
                    self.client.crm.contacts.basic_api.get_by_id,
                    contact_id=contact_id,
                    properties=["email", "firstname", "lastname", "company", "phone", "title"]
                )
                
                return {
                    "id": contact.id,
                    "properties": contact.properties
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting contact by email: {str(e)}")
            return None
    
    def create_contact(self, properties: Dict[str, Any]) -> Optional[str]:
        """
        Create a new contact in HubSpot.
        
        Args:
            properties: Contact properties
        
        Returns:
            Optional[str]: Contact ID if created, None otherwise
        """
        try:
            # Check if contact already exists
            if "email" in properties and properties["email"]:
                existing_contact = self.get_contact_by_email(properties["email"])
                if existing_contact:
                    return existing_contact["id"]
            
            # Create new contact
            log_sensitive(logger, logging.INFO, f"Creating contact with properties: {properties}", 
                        email=properties.get('email'))
            
            contact = self._make_api_request(
                self.client.crm.contacts.basic_api.create,
                simple_public_object_input={"properties": properties}
            )
            
            return contact.id
            
        except Exception as e:
            logger.error(f"Error creating contact: {str(e)}")
            return None
    
    def create_or_update_deal(self, properties: Dict[str, Any], existing_deal_id: Optional[str] = None) -> Optional[str]:
        """
        Create or update a deal in HubSpot.
        
        Args:
            properties: Deal properties
            existing_deal_id: Existing deal ID (if updating)
        
        Returns:
            Optional[str]: Deal ID if created/updated, None otherwise
        """
        try:
            if existing_deal_id:
                # Update existing deal
                log_integration_event("hubspot", "update_deal", f"Updating deal {existing_deal_id}")
                
                deal = self._make_api_request(
                    self.client.crm.deals.basic_api.update,
                    deal_id=existing_deal_id,
                    simple_public_object_input={"properties": properties}
                )
                
                return existing_deal_id
            else:
                # Create new deal
                log_integration_event("hubspot", "create_deal", "Creating new deal")
                
                deal = self._make_api_request(
                    self.client.crm.deals.basic_api.create,
                    simple_public_object_input={"properties": properties}
                )
                
                return deal.id
            
        except Exception as e:
            logger.error(f"Error creating/updating deal: {str(e)}")
            return None
    
    def associate_contact_to_deal(self, contact_id: str, deal_id: str) -> bool:
        """
        Associate a contact with a deal.
        
        Args:
            contact_id: Contact ID
            deal_id: Deal ID
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create association
            self._make_api_request(
                self.client.crm.deals.associations_api.create,
                deal_id=deal_id,
                to_object_type="contacts",
                to_object_id=contact_id,
                association_type="deal_to_contact"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error associating contact to deal: {str(e)}")
            return False
    
    def ensure_custom_properties(self) -> bool:
        """
        Ensure that required custom properties exist in HubSpot.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get custom properties from config
            custom_properties = self.config.get("custom_properties", {})
            
            # Create contact properties
            for prop in custom_properties.get("contact", []):
                self._ensure_property("contacts", prop)
            
            # Create deal properties
            for prop in custom_properties.get("deal", []):
                self._ensure_property("deals", prop)
            
            return True
            
        except Exception as e:
            logger.error(f"Error ensuring custom properties: {str(e)}")
            return False
    
    def _ensure_property(self, object_type: str, property_def: Dict[str, Any]) -> None:
        """
        Ensure that a property exists in HubSpot.
        
        Args:
            object_type: Object type (contacts, deals, etc.)
            property_def: Property definition
        """
        # Check cache first
        cache_key = f"{object_type}_{property_def['name']}"
        if cache_key in self.property_cache:
            return
        
        try:
            # Check if property exists
            self._make_api_request(
                getattr(self.client.crm.properties, object_type).core_api.get_by_name,
                property_name=property_def["name"]
            )
            
            # If we get here, property exists
            self.property_cache[cache_key] = True
            
        except Exception:
            # Property doesn't exist, create it
            logger.info(f"Creating custom property: {property_def['name']} for {object_type}")
            
            property_create = {
                "name": property_def["name"],
                "label": property_def.get("label", property_def["name"]),
                "type": property_def.get("type", "string"),
                "fieldType": property_def.get("field_type", "text"),
                "groupName": property_def.get("group_name", "contactinformation" if object_type == "contacts" else "dealinformation"),
                "hidden": False,
                "formField": True
            }
            
            self._make_api_request(
                getattr(self.client.crm.properties, object_type).core_api.create,
                property_create=property_create
            )
            
            self.property_cache[cache_key] = True
    
    def sync_lead(self, lead: Lead) -> Optional[str]:
        """
        Sync a lead to HubSpot.
        
        Args:
            lead: Lead to sync
        
        Returns:
            Optional[str]: HubSpot deal ID if successful, None otherwise
        """
        # Ensure required custom properties exist
        self.ensure_custom_properties()
        
        # Check if lead already exists
        existing_deal_id = self.check_existing_lead(
            lead_id=lead.id,
            source_id=lead.source_id,
            source_url=lead.source_url
        )
        
        # Map lead to HubSpot properties
        deal_properties, contact_properties_list = self.map_lead_to_hubspot_properties(lead)
        
        # Set lead ID property
        if lead.id:
            deal_properties["lead_id"] = str(lead.id)
        
        # Create or update deal
        deal_id = self.create_or_update_deal(deal_properties, existing_deal_id)
        if not deal_id:
            logger.error("Failed to create or update deal")
            return None
        
        # Create contacts and associate with deal
        for contact_properties in contact_properties_list:
            contact_id = self.create_contact(contact_properties)
            if contact_id:
                self.associate_contact_to_deal(contact_id, deal_id)
        
        log_integration_event("hubspot", "sync_complete", f"Lead sync completed for {lead.project_name}")
        return deal_id
    
    def sync_leads(self, leads: List[Lead]) -> Dict[uuid.UUID, str]:
        """
        Sync multiple leads to HubSpot.
        
        Args:
            leads: List of leads to sync
        
        Returns:
            Dict: Dictionary mapping lead IDs to HubSpot deal IDs
        """
        results = {}
        
        for lead in leads:
            try:
                deal_id = self.sync_lead(lead)
                if deal_id and lead.id:
                    results[lead.id] = deal_id
            except Exception as e:
                logger.error(f"Error syncing lead {lead.id}: {str(e)}")
        
        log_integration_event("hubspot", "batch_sync_complete", f"Synced {len(results)} leads")
        return results
    
    def get_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a deal from HubSpot.
        
        Args:
            deal_id: HubSpot deal ID
        
        Returns:
            Optional[Dict]: Deal data if found, None otherwise
        """
        try:
            # Get all properties
            deal = self._make_api_request(
                self.client.crm.deals.basic_api.get_by_id,
                deal_id=deal_id,
                properties=["*"]
            )
            
            return {
                "id": deal.id,
                "properties": deal.properties
            }
            
        except Exception as e:
            logger.error(f"Error getting deal: {str(e)}")
            return None
    
    def delete_deal(self, deal_id: str) -> bool:
        """
        Delete a deal from HubSpot.
        
        Args:
            deal_id: HubSpot deal ID
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self._make_api_request(
                self.client.crm.deals.basic_api.archive,
                deal_id=deal_id
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting deal: {str(e)}")
            return False
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CRM Export Pipeline

Manages the export of leads to CRM systems, including HubSpot.
Handles object creation, association, and tracking export status.
"""

import uuid
import datetime
import logging
from typing import Dict, Any, Optional, List, Tuple

from models.lead import Lead, LeadStatus
from utils.storage import LeadStorage
from utils.logger import get_logger
from integrations.hubspot_client import HubSpotClient
from src.perera_lead_scraper.hubspot.hubspot_mapper import HubSpotMapper

# Configure logger
logger = get_logger(__name__)


class CRMExportPipeline:
    """
    Pipeline for exporting leads to CRM systems.
    
    Responsible for mapping internal lead data to CRM formats,
    creating or updating CRM records, and tracking export status.
    """
    
    def __init__(
        self,
        hubspot_client: HubSpotClient,
        hubspot_mapper: HubSpotMapper,
        local_storage: LeadStorage
    ):
        """
        Initialize the CRM export pipeline.
        
        Args:
            hubspot_client: Client for interacting with HubSpot API
            hubspot_mapper: Mapper for converting leads to HubSpot format
            local_storage: Storage manager for local lead data
        """
        self.hubspot_client = hubspot_client
        self.hubspot_mapper = hubspot_mapper
        self.local_storage = local_storage
        
        # Statistics tracking
        self.export_stats = {
            "total_attempted": 0,
            "total_succeeded": 0,
            "total_failed": 0,
            "last_export_time": None
        }
    
    def export_lead(self, lead: Lead) -> bool:
        """
        Export a lead to HubSpot.
        
        Maps the lead to HubSpot format, creates or updates the company, contact, and deal,
        and associates them properly. Also creates a summary note and updates the lead status.
        
        Args:
            lead: Lead to export
        
        Returns:
            bool: True if export was successful, False otherwise
        """
        self.export_stats["total_attempted"] += 1
        lead_identifier = f"{lead.project_name} (ID: {lead.id})"
        
        try:
            logger.info(f"Starting export of lead {lead_identifier} to HubSpot")
            
            # Check lead status
            if lead.status == LeadStatus.EXPORTED:
                logger.info(f"Lead {lead_identifier} already marked as exported, skipping")
                return True
            
            # Map lead to HubSpot format
            logger.debug(f"Mapping lead {lead_identifier} to HubSpot format")
            company_payload, contact_payload, deal_payload = self.hubspot_mapper.map_lead_to_hubspot(lead)
            
            # Find or create company
            logger.info(f"Creating/updating company for lead {lead_identifier}")
            company_id = self._find_or_create_company(company_payload, lead)
            if not company_id:
                logger.error(f"Failed to create/update company for lead {lead_identifier}")
                self.export_stats["total_failed"] += 1
                return False
            
            # Find or create contact (if we have one)
            contact_id = None
            if contact_payload:
                logger.info(f"Creating/updating contact for lead {lead_identifier}")
                contact_id = self._find_or_create_contact(contact_payload, lead)
                if not contact_id:
                    logger.warning(f"Failed to create/update contact for lead {lead_identifier}, continuing without contact")
            else:
                logger.info(f"No valid contact data for lead {lead_identifier}, skipping contact creation")
            
            # Create deal and associate with company and contact
            logger.info(f"Creating deal and associations for lead {lead_identifier}")
            deal_id = self._create_deal_and_associate(deal_payload, company_id, contact_id, lead)
            if not deal_id:
                logger.error(f"Failed to create deal for lead {lead_identifier}")
                self.export_stats["total_failed"] += 1
                return False
            
            # Add notes to the deal
            logger.info(f"Adding summary note to deal for lead {lead_identifier}")
            self._attach_notes(deal_id, lead)
            
            # Update lead status to exported
            logger.info(f"Updating lead {lead_identifier} status to EXPORTED")
            self.local_storage.update_lead_status(lead.id, LeadStatus.EXPORTED)
            
            # Update statistics
            self.export_stats["total_succeeded"] += 1
            self.export_stats["last_export_time"] = datetime.datetime.now()
            
            logger.info(f"Successfully exported lead {lead_identifier} to HubSpot")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting lead {lead_identifier} to HubSpot: {str(e)}")
            self.export_stats["total_failed"] += 1
            return False
    
    def _find_or_create_company(self, company_payload: Dict[str, Any], lead: Lead) -> Optional[str]:
        """
        Find or create a company in HubSpot.
        
        Args:
            company_payload: Company properties
            lead: Source lead
        
        Returns:
            Optional[str]: Company ID if successful, None otherwise
        """
        try:
            if not company_payload or "name" not in company_payload:
                logger.warning(f"Invalid company payload for lead {lead.id}")
                return None
            
            logger.debug(f"Finding or creating company '{company_payload.get('name')}' for lead {lead.id}")
            company_id = self.hubspot_client.find_or_create_company(company_payload)
            
            if company_id:
                logger.info(f"Company ID for lead {lead.id}: {company_id}")
                return company_id
            else:
                logger.error(f"Failed to find or create company for lead {lead.id}")
                return None
                
        except Exception as e:
            logger.error(f"Error in find_or_create_company for lead {lead.id}: {str(e)}")
            return None
    
    def _find_or_create_contact(self, contact_payload: Dict[str, Any], lead: Lead) -> Optional[str]:
        """
        Find or create a contact in HubSpot.
        
        Args:
            contact_payload: Contact properties
            lead: Source lead
        
        Returns:
            Optional[str]: Contact ID if successful, None otherwise
        """
        try:
            if not contact_payload or "email" not in contact_payload:
                logger.warning(f"Invalid contact payload for lead {lead.id}")
                return None
            
            logger.debug(f"Finding or creating contact with email '{contact_payload.get('email')}' for lead {lead.id}")
            contact_id = self.hubspot_client.find_or_create_contact(contact_payload)
            
            if contact_id:
                logger.info(f"Contact ID for lead {lead.id}: {contact_id}")
                return contact_id
            else:
                logger.error(f"Failed to find or create contact for lead {lead.id}")
                return None
                
        except Exception as e:
            logger.error(f"Error in find_or_create_contact for lead {lead.id}: {str(e)}")
            return None
    
    def _create_deal_and_associate(
        self,
        deal_payload: Dict[str, Any],
        company_id: str,
        contact_id: Optional[str],
        lead: Lead
    ) -> Optional[str]:
        """
        Create a deal and associate it with a company and contact.
        
        Args:
            deal_payload: Deal properties
            company_id: Company ID to associate
            contact_id: Contact ID to associate (if available)
            lead: Source lead
        
        Returns:
            Optional[str]: Deal ID if successful, None otherwise
        """
        try:
            if not deal_payload or "dealname" not in deal_payload:
                logger.warning(f"Invalid deal payload for lead {lead.id}")
                return None
            
            # Check if lead already exists in HubSpot
            existing_deal_id = self.hubspot_client.check_existing_lead(
                lead_id=lead.id,
                source_id=lead.source_id,
                source_url=lead.source_url
            )
            
            # Create or update deal
            logger.debug(f"Creating or updating deal for lead {lead.id}")
            deal_id = self.hubspot_client.create_or_update_deal(deal_payload, existing_deal_id)
            
            if not deal_id:
                logger.error(f"Failed to create or update deal for lead {lead.id}")
                return None
            
            # Associate deal with company
            logger.debug(f"Associating deal {deal_id} with company {company_id}")
            company_association_success = self.hubspot_client.associate_company_to_deal(company_id, deal_id)
            
            if not company_association_success:
                logger.warning(f"Failed to associate deal {deal_id} with company {company_id}")
            
            # Associate deal with contact if available
            if contact_id:
                logger.debug(f"Associating deal {deal_id} with contact {contact_id}")
                contact_association_success = self.hubspot_client.associate_contact_to_deal(contact_id, deal_id)
                
                if not contact_association_success:
                    logger.warning(f"Failed to associate deal {deal_id} with contact {contact_id}")
            
            return deal_id
            
        except Exception as e:
            logger.error(f"Error in create_deal_and_associate for lead {lead.id}: {str(e)}")
            return None
    
    def _attach_notes(self, deal_id: str, lead: Lead) -> bool:
        """
        Attach notes to a deal.
        
        Args:
            deal_id: Deal ID
            lead: Source lead
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create summary note
            note_title = f"Lead Export Summary: {lead.project_name}"
            
            note_content = (
                f"Lead exported from Perera Construction Lead Scraper.\n\n"
                f"Project: {lead.project_name}\n"
                f"Source: {lead.source}\n"
                f"Market Sector: {lead.market_sector.value if lead.market_sector else 'Unknown'}\n"
                f"Lead Type: {lead.lead_type.value if lead.lead_type else 'Unknown'}\n"
                f"Estimated Value: ${lead.estimated_value if lead.estimated_value else 'Unknown'}\n"
                f"Location: {lead.location.city}, {lead.location.state if lead.location.city and lead.location.state else 'Unknown'}\n"
                f"Retrieved: {lead.retrieved_date.strftime('%Y-%m-%d') if lead.retrieved_date else 'Unknown'}\n"
                f"Publication Date: {lead.publication_date.strftime('%Y-%m-%d') if lead.publication_date else 'Unknown'}\n"
                f"Confidence Score: {lead.confidence_score if lead.confidence_score is not None else 'Unknown'}\n\n"
                f"Exported on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            logger.debug(f"Creating note for deal {deal_id}")
            note_id = self.hubspot_client.create_note(deal_id, "deal", note_content, note_title)
            
            return note_id is not None
            
        except Exception as e:
            logger.error(f"Error in attach_notes for lead {lead.id}: {str(e)}")
            return False
    
    def get_export_statistics(self) -> Dict[str, Any]:
        """
        Get export statistics.
        
        Returns:
            Dict: Export statistics
        """
        return self.export_stats
    
    def reset_statistics(self) -> None:
        """Reset export statistics."""
        self.export_stats = {
            "total_attempted": 0,
            "total_succeeded": 0,
            "total_failed": 0,
            "last_export_time": None
        }
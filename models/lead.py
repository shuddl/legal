#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lead Model - Defines the structure of construction leads.
"""

import uuid
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Union

@dataclass
class Location:
    """Location information for a lead."""
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = "USA"
    
    def __str__(self) -> str:
        """String representation of the location."""
        parts = []
        if self.city:
            parts.append(self.city)
        if self.state:
            parts.append(self.state)
        if self.zip_code:
            parts.append(self.zip_code)
        
        if not parts and self.address:
            return self.address
        
        return ", ".join(parts)

@dataclass
class Contact:
    """Contact information for a lead."""
    name: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None

@dataclass
class Lead:
    """
    Construction lead representation.
    
    Contains all information about a potential construction lead.
    """
    
    # Basic information
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    project_name: Optional[str] = None
    description: Optional[str] = None
    
    # Source information
    source: str = ""
    source_url: Optional[str] = None
    publication_date: Optional[datetime] = None
    retrieved_date: datetime = field(default_factory=datetime.now)
    
    # Project details
    location: Optional[Location] = None
    estimated_value: Optional[float] = None
    scope: Optional[str] = None
    market_sector: Optional[str] = None
    project_type: Optional[str] = None
    project_phase: Optional[str] = None
    start_date: Optional[datetime] = None
    completion_date: Optional[datetime] = None
    status: Optional[str] = None
    
    # Contacts and companies
    contacts: List[Contact] = field(default_factory=list)
    owner: Optional[str] = None
    general_contractor: Optional[str] = None
    architect: Optional[str] = None
    
    # Classification and metadata
    tags: Set[str] = field(default_factory=set)
    confidence_score: float = 0.0
    enriched: bool = False
    classified: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert lead to dictionary."""
        data = {
            "id": self.id,
            "title": self.title,
            "project_name": self.project_name,
            "description": self.description,
            "source": self.source,
            "source_url": self.source_url,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "retrieved_date": self.retrieved_date.isoformat() if self.retrieved_date else None,
            "estimated_value": self.estimated_value,
            "scope": self.scope,
            "market_sector": self.market_sector,
            "project_type": self.project_type,
            "project_phase": self.project_phase,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "completion_date": self.completion_date.isoformat() if self.completion_date else None,
            "status": self.status,
            "owner": self.owner,
            "general_contractor": self.general_contractor,
            "architect": self.architect,
            "tags": list(self.tags),
            "confidence_score": self.confidence_score,
            "enriched": self.enriched,
            "classified": self.classified,
            "metadata": self.metadata
        }
        
        # Add location if present
        if self.location:
            data["location"] = {
                "address": self.location.address,
                "city": self.location.city,
                "state": self.location.state,
                "zip_code": self.location.zip_code,
                "country": self.location.country
            }
        
        # Add contacts if present
        if self.contacts:
            data["contacts"] = []
            for contact in self.contacts:
                data["contacts"].append({
                    "name": contact.name,
                    "title": contact.title,
                    "company": contact.company,
                    "email": contact.email,
                    "phone": contact.phone,
                    "role": contact.role
                })
        
        return data
    
    def to_json(self) -> str:
        """Convert lead to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Lead':
        """Create a lead from dictionary data."""
        # Create a new lead object
        lead = cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""),
            project_name=data.get("project_name"),
            description=data.get("description"),
            source=data.get("source", ""),
            source_url=data.get("source_url"),
            estimated_value=data.get("estimated_value"),
            scope=data.get("scope"),
            market_sector=data.get("market_sector"),
            project_type=data.get("project_type"),
            project_phase=data.get("project_phase"),
            status=data.get("status"),
            owner=data.get("owner"),
            general_contractor=data.get("general_contractor"),
            architect=data.get("architect"),
            confidence_score=data.get("confidence_score", 0.0),
            enriched=data.get("enriched", False),
            classified=data.get("classified", False),
            metadata=data.get("metadata", {}),
            raw_data=data.get("raw_data", {})
        )
        
        # Parse dates
        if data.get("publication_date"):
            try:
                lead.publication_date = datetime.fromisoformat(data["publication_date"])
            except (ValueError, TypeError):
                pass
                
        if data.get("retrieved_date"):
            try:
                lead.retrieved_date = datetime.fromisoformat(data["retrieved_date"])
            except (ValueError, TypeError):
                lead.retrieved_date = datetime.now()
                
        if data.get("start_date"):
            try:
                lead.start_date = datetime.fromisoformat(data["start_date"])
            except (ValueError, TypeError):
                pass
                
        if data.get("completion_date"):
            try:
                lead.completion_date = datetime.fromisoformat(data["completion_date"])
            except (ValueError, TypeError):
                pass
        
        # Parse location
        if data.get("location"):
            loc_data = data["location"]
            lead.location = Location(
                address=loc_data.get("address"),
                city=loc_data.get("city"),
                state=loc_data.get("state"),
                zip_code=loc_data.get("zip_code"),
                country=loc_data.get("country", "USA")
            )
        
        # Parse contacts
        if data.get("contacts"):
            for contact_data in data["contacts"]:
                contact = Contact(
                    name=contact_data.get("name"),
                    title=contact_data.get("title"),
                    company=contact_data.get("company"),
                    email=contact_data.get("email"),
                    phone=contact_data.get("phone"),
                    role=contact_data.get("role")
                )
                lead.contacts.append(contact)
        
        # Parse tags
        if data.get("tags"):
            lead.tags = set(data["tags"])
        
        return lead
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Lead':
        """Create a lead from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
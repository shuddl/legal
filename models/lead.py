#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lead Data Models

Provides Pydantic models for leads and related data.
"""

import uuid
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator, HttpUrl, UUID4, EmailStr, BeforeValidator
from typing_extensions import Annotated


class MarketSector(str, Enum):
    """
    Enumeration of market sectors for leads.
    
    Defines the primary business sectors targeted for construction leads.
    """
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    ENERGY = "energy"
    UTILITIES = "utilities"
    COMMERCIAL = "commercial"
    ENTERTAINMENT = "entertainment"
    RESIDENTIAL = "residential"
    GOVERNMENT = "government"
    INDUSTRIAL = "industrial"
    OTHER = "other"


class LeadStatus(str, Enum):
    """
    Enumeration of lead statuses.
    
    Tracks the current status of a lead in the pipeline.
    """
    NEW = "new"
    PROCESSING = "processing"
    VALIDATED = "validated"
    ENRICHED = "enriched"
    EXPORTED = "exported"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class LeadType(str, Enum):
    """
    Enumeration of lead types.
    
    Categorizes the type of construction project.
    """
    NEW_CONSTRUCTION = "new_construction"
    RENOVATION = "renovation"
    EXPANSION = "expansion"
    TENANT_IMPROVEMENT = "tenant_improvement"
    INFRASTRUCTURE = "infrastructure"
    MAINTENANCE = "maintenance"
    OTHER = "other"


class SourceType(str, Enum):
    """
    Enumeration of source types.
    
    Defines the different types of lead sources supported by the system.
    """
    RSS = "rss"
    WEBSITE = "website"
    CITY_PORTAL = "city_portal"
    PERMIT_DATABASE = "permit_database"
    API = "api"
    MANUAL = "manual"


class Location(BaseModel):
    """
    Location data for a lead.
    
    Contains detailed address information and geographic coordinates.
    """
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: str = "USA"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    model_config = {"extra": "forbid"}
    
    @field_validator("zip_code")
    @classmethod
    def validate_zip_code(cls, v: Optional[str]) -> Optional[str]:
        """Validate US ZIP code format."""
        if v is None:
            return None
        
        # Strip any whitespace
        v = v.strip()
        
        # Check for 5-digit or ZIP+4 format
        if len(v) == 5 and v.isdigit():
            return v
        elif len(v) == 10 and v[5] == "-" and v[:5].isdigit() and v[6:].isdigit():
            return v
        else:
            raise ValueError("ZIP code must be 5 digits or ZIP+4 format (XXXXX-XXXX)")


class Contact(BaseModel):
    """
    Contact information for a lead.
    
    Contains details about a person or organization associated with the lead.
    """
    name: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    
    model_config = {"extra": "forbid"}
    
    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Format and validate phone number."""
        if v is None:
            return None
        
        # Remove all non-numeric characters
        digits = ''.join(c for c in v if c.isdigit())
        
        # Check for valid length (10 or 11 digits for US)
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            raise ValueError("Phone number must be 10 or 11 digits")


class Credentials(BaseModel):
    """
    Credentials for external API access.
    
    Securely stores authentication details for third-party services.
    """
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    token_expiry: Optional[datetime] = None
    
    model_config = {"extra": "forbid"}


class DataSource(BaseModel):
    """
    Data source configuration.
    
    Defines a source of lead data with configuration details.
    """
    id: UUID4 = Field(default_factory=uuid.uuid4)
    name: str
    url: HttpUrl
    type: SourceType
    market_sectors: List[MarketSector] = Field(default_factory=list)
    active: bool = True
    requires_js: bool = False
    config: Dict[str, Any] = Field(default_factory=dict)
    credentials: Optional[Credentials] = None
    last_checked: Optional[datetime] = None
    status: Optional[str] = None
    metrics: Dict[str, Any] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    model_config = {"extra": "forbid"}
    
    @model_validator(mode="after")
    def validate_credentials_for_api(self) -> "DataSource":
        """Validate that API sources have credentials."""
        if self.type == SourceType.API and self.active and not self.credentials:
            raise ValueError("API sources must have credentials")
        return self


def ensure_uuid(id_value: Union[str, uuid.UUID, None]) -> Optional[UUID4]:
    """
    Ensure the provided value is a valid UUID.
    
    Used as a BeforeValidator to convert string UUIDs to UUID objects.
    
    Args:
        id_value: String or UUID object
        
    Returns:
        UUID object or None
    """
    if id_value is None:
        return None
    
    if isinstance(id_value, str):
        return uuid.UUID(id_value)
    
    return id_value


class Lead(BaseModel):
    """
    Lead model representing a construction project opportunity.
    
    Central data structure for storing lead information from various sources.
    """
    id: Annotated[Optional[UUID4], BeforeValidator(ensure_uuid)] = Field(default_factory=uuid.uuid4)
    source: str
    source_url: Optional[HttpUrl] = None
    source_id: Optional[str] = None
    
    project_name: str
    description: Optional[str] = None
    
    location: Location = Field(default_factory=Location)
    contacts: List[Contact] = Field(default_factory=list)
    
    market_sector: Optional[MarketSector] = None
    lead_type: Optional[LeadType] = None
    status: LeadStatus = LeadStatus.NEW
    
    estimated_value: Optional[float] = None
    estimated_square_footage: Optional[int] = None
    
    publication_date: Optional[datetime] = None
    retrieved_date: datetime = Field(default_factory=datetime.now)
    
    confidence_score: Optional[float] = None
    
    raw_content: Optional[str] = None
    extra_data: Dict[str, Any] = Field(default_factory=dict)
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    model_config = {"extra": "forbid"}
    
    @field_validator("confidence_score")
    @classmethod
    def validate_confidence_score(cls, v: Optional[float]) -> Optional[float]:
        """Validate confidence score is between 0 and 1."""
        if v is not None and (v < 0 or v > 1):
            raise ValueError("Confidence score must be between 0 and 1")
        return v
    
    @model_validator(mode="after")
    def validate_dates(self) -> "Lead":
        """Validate that retrieved_date is not earlier than publication_date."""
        if (self.publication_date and self.retrieved_date and 
                self.publication_date > self.retrieved_date):
            raise ValueError("Publication date cannot be after retrieval date")
        return self
    
    @model_validator(mode="after")
    def validate_value(self) -> "Lead":
        """Validate that estimated_value is positive."""
        if self.estimated_value is not None and self.estimated_value <= 0:
            raise ValueError("Estimated value must be positive")
        return self
    
    def update_timestamp(self) -> None:
        """Update the updated_at timestamp to the current time."""
        self.updated_at = datetime.now()


class LeadSearchParams(BaseModel):
    """
    Parameters for searching leads.
    
    Used to filter lead queries in the storage backend.
    """
    source: Optional[str] = None
    market_sector: Optional[MarketSector] = None
    lead_type: Optional[LeadType] = None
    status: Optional[LeadStatus] = None
    location_city: Optional[str] = None
    location_state: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_date: Optional[datetime] = None
    max_date: Optional[datetime] = None
    keyword: Optional[str] = None
    limit: int = 100
    offset: int = 0
    
    model_config = {"extra": "forbid"}
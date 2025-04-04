#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Storage utilities for persisting and retrieving lead data.

Implements SQLAlchemy ORM for database operations with proper session management.
"""

import os
import csv
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Type, TypeVar, Iterator, ContextManager
from contextlib import contextmanager
import urllib.parse

from sqlalchemy import create_engine, Column, String, Float, Integer, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.sql import func
from sqlalchemy.exc import SQLAlchemyError

from models.lead import Lead, LeadStatus, MarketSector, LeadType, LeadSearchParams, Location, Contact
from utils.logger import get_logger

# Configure logger
logger = get_logger(__name__)

# Get database path from environment variable or use default
DB_PATH = os.environ.get("LEAD_DB_PATH", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
    'data', 
    'leads.db'
))

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Create engine
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

# Create session factory
SessionFactory = sessionmaker(bind=engine)

# Create base class for ORM models
Base = declarative_base()

# Type variable for model classes
T = TypeVar('T')


class LeadModel(Base):
    """SQLAlchemy ORM model for leads."""
    
    __tablename__ = 'leads'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String(255), nullable=False, index=True)
    source_url = Column(String(1024))
    source_id = Column(String(255), index=True)
    
    project_name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    
    # Location fields
    address = Column(String(255))
    city = Column(String(100), index=True)
    state = Column(String(50), index=True)
    zip_code = Column(String(20), index=True)
    country = Column(String(50), default="USA")
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Classification fields
    market_sector = Column(String(50), index=True)
    lead_type = Column(String(50), index=True)
    status = Column(String(50), nullable=False, default="new", index=True)
    
    # Project details
    estimated_value = Column(Float, index=True)
    estimated_square_footage = Column(Integer)
    
    # Dates
    publication_date = Column(DateTime, index=True)
    retrieved_date = Column(DateTime, nullable=False, default=datetime.now, index=True)
    
    # Metadata
    confidence_score = Column(Float)
    raw_content = Column(Text)
    extra_data = Column(JSON)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    contacts = relationship("ContactModel", back_populates="lead", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_leads_source_url', 'source_url'),
        Index('idx_leads_project_name', 'project_name'),
        Index('idx_leads_publication_date', 'publication_date'),
        Index('idx_leads_market_sector_status', 'market_sector', 'status'),
        Index('idx_leads_status_retrieved', 'status', 'retrieved_date'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ORM model to dictionary."""
        result = {c.name: getattr(self, c.name) for c in self.__table__.columns}
        
        # Convert dates to ISO format
        for date_field in ['publication_date', 'retrieved_date', 'created_at', 'updated_at']:
            if result[date_field]:
                result[date_field] = result[date_field].isoformat()
        
        # Add contacts
        result['contacts'] = [contact.to_dict() for contact in self.contacts]
        
        # Create location dictionary
        result['location'] = {
            'address': result.pop('address'),
            'city': result.pop('city'),
            'state': result.pop('state'),
            'zip_code': result.pop('zip_code'),
            'country': result.pop('country'),
            'latitude': result.pop('latitude'),
            'longitude': result.pop('longitude'),
        }
        
        return result
    
    @classmethod
    def from_lead(cls, lead: Lead) -> "LeadModel":
        """Create ORM model from Pydantic model."""
        lead_dict = lead.model_dump()
        
        # Extract location fields
        location = lead_dict.pop('location', {})
        
        # Extract contacts
        contacts = lead_dict.pop('contacts', [])
        
        # Convert UUID to string
        if lead_dict.get('id'):
            lead_dict['id'] = str(lead_dict['id'])
        
        # Create ORM model
        lead_model = cls(**{
            **lead_dict,
            'address': location.get('address'),
            'city': location.get('city'),
            'state': location.get('state'),
            'zip_code': location.get('zip_code'),
            'country': location.get('country', 'USA'),
            'latitude': location.get('latitude'),
            'longitude': location.get('longitude'),
        })
        
        # Add contacts
        for contact in contacts:
            lead_model.contacts.append(ContactModel.from_contact(contact, lead_model))
        
        return lead_model
    
    def update_from_lead(self, lead: Lead) -> None:
        """Update ORM model from Pydantic model."""
        lead_dict = lead.model_dump(exclude={'id', 'created_at', 'contacts'})
        
        # Extract location fields
        location = lead_dict.pop('location', {})
        
        # Update fields
        for key, value in lead_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        # Update location fields
        if location:
            self.address = location.get('address', self.address)
            self.city = location.get('city', self.city)
            self.state = location.get('state', self.state)
            self.zip_code = location.get('zip_code', self.zip_code)
            self.country = location.get('country', self.country)
            self.latitude = location.get('latitude', self.latitude)
            self.longitude = location.get('longitude', self.longitude)
        
        # Update contacts
        if lead.contacts:
            # Remove existing contacts
            self.contacts.clear()
            
            # Add new contacts
            for contact in lead.contacts:
                self.contacts.append(ContactModel.from_contact(contact, self))
        
        # Update timestamp
        self.updated_at = datetime.now()


class ContactModel(Base):
    """SQLAlchemy ORM model for contacts."""
    
    __tablename__ = 'contacts'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id = Column(String(36), ForeignKey('leads.id', ondelete='CASCADE'), nullable=False)
    
    name = Column(String(255))
    title = Column(String(255))
    company = Column(String(255))
    email = Column(String(255), index=True)
    phone = Column(String(50))
    
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    
    # Relationships
    lead = relationship("LeadModel", back_populates="contacts")
    
    # Indexes
    __table_args__ = (
        Index('idx_contacts_email', 'email'),
        Index('idx_contacts_lead_id', 'lead_id'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ORM model to dictionary."""
        result = {c.name: getattr(self, c.name) for c in self.__table__.columns
                  if c.name not in ['lead_id']}
        
        # Convert dates to ISO format
        for date_field in ['created_at', 'updated_at']:
            if result[date_field]:
                result[date_field] = result[date_field].isoformat()
        
        return result
    
    @classmethod
    def from_contact(cls, contact: Contact, lead_model: LeadModel) -> "ContactModel":
        """Create ORM model from Pydantic model."""
        contact_dict = contact.model_dump()
        
        return cls(
            lead_id=lead_model.id,
            **contact_dict
        )


class LeadStorage:
    """
    Storage manager for leads.
    
    Provides methods for saving, retrieving, and querying leads.
    """
    
    def __init__(self):
        """Initialize the lead storage."""
        # Initialize tables if they don't exist
        Base.metadata.create_all(engine)
    
    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        """
        Provide a transactional scope around a series of operations.
        
        Yields:
            Session: SQLAlchemy session
        """
        session = SessionFactory()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        except Exception as e:
            session.rollback()
            logger.error(f"Unexpected error: {str(e)}")
            raise
        finally:
            session.close()
    
    def save_lead(self, lead: Lead) -> Lead:
        """
        Save a lead to the database.
        
        Args:
            lead: Lead to save
        
        Returns:
            Lead: Saved lead with ID
        """
        # Generate ID if not provided
        if not lead.id:
            lead.id = uuid.uuid4()
        
        with self.session_scope() as session:
            # Check if lead already exists
            existing = session.query(LeadModel).filter(LeadModel.id == str(lead.id)).first()
            
            if existing:
                # Update existing lead
                existing.update_from_lead(lead)
                session.add(existing)
                lead_model = existing
            else:
                # Create new lead
                lead_model = LeadModel.from_lead(lead)
                session.add(lead_model)
            
            # Flush to get ID
            session.flush()
            
            # Convert back to Pydantic model
            result = self._orm_to_pydantic(lead_model)
        
        return result
    
    def get_lead_by_id(self, lead_id: uuid.UUID) -> Optional[Lead]:
        """
        Get a lead by ID.
        
        Args:
            lead_id: Lead ID
        
        Returns:
            Lead or None: Lead if found, None otherwise
        """
        with self.session_scope() as session:
            lead_model = session.query(LeadModel).filter(LeadModel.id == str(lead_id)).first()
            
            if not lead_model:
                return None
            
            return self._orm_to_pydantic(lead_model)
    
    def get_lead_by_source_id(self, source: str, source_id: str) -> Optional[Lead]:
        """
        Get a lead by source and source ID.
        
        Args:
            source: Lead source
            source_id: Source-specific ID
        
        Returns:
            Lead or None: Lead if found, None otherwise
        """
        with self.session_scope() as session:
            lead_model = session.query(LeadModel).filter(
                LeadModel.source == source,
                LeadModel.source_id == source_id
            ).first()
            
            if not lead_model:
                return None
            
            return self._orm_to_pydantic(lead_model)
    
    def get_lead_by_source_url(self, source_url: str) -> Optional[Lead]:
        """
        Get a lead by source URL.
        
        Args:
            source_url: URL of the lead source
        
        Returns:
            Lead or None: Lead if found, None otherwise
        """
        with self.session_scope() as session:
            lead_model = session.query(LeadModel).filter(LeadModel.source_url == source_url).first()
            
            if not lead_model:
                return None
            
            return self._orm_to_pydantic(lead_model)
    
    def get_leads_by_status(self, status: LeadStatus, limit: int = 100, offset: int = 0) -> Tuple[List[Lead], int]:
        """
        Get leads by status.
        
        Args:
            status: Lead status
            limit: Maximum number of leads to return
            offset: Offset for pagination
        
        Returns:
            Tuple containing:
            - List[Lead]: List of leads
            - int: Total count
        """
        with self.session_scope() as session:
            query = session.query(LeadModel).filter(LeadModel.status == status.value)
            
            # Get total count
            total_count = query.count()
            
            # Paginate results
            leads = query.order_by(LeadModel.updated_at.desc()).limit(limit).offset(offset).all()
            
            return [self._orm_to_pydantic(lead) for lead in leads], total_count
    
    def get_leads_by_market_sector(self, sector: MarketSector, limit: int = 100, offset: int = 0) -> Tuple[List[Lead], int]:
        """
        Get leads by market sector.
        
        Args:
            sector: Market sector
            limit: Maximum number of leads to return
            offset: Offset for pagination
        
        Returns:
            Tuple containing:
            - List[Lead]: List of leads
            - int: Total count
        """
        with self.session_scope() as session:
            query = session.query(LeadModel).filter(LeadModel.market_sector == sector.value)
            
            # Get total count
            total_count = query.count()
            
            # Paginate results
            leads = query.order_by(LeadModel.updated_at.desc()).limit(limit).offset(offset).all()
            
            return [self._orm_to_pydantic(lead) for lead in leads], total_count
    
    def get_leads_by_source(self, source: str, limit: int = 100, offset: int = 0) -> Tuple[List[Lead], int]:
        """
        Get leads by source.
        
        Args:
            source: Lead source
            limit: Maximum number of leads to return
            offset: Offset for pagination
        
        Returns:
            Tuple containing:
            - List[Lead]: List of leads
            - int: Total count
        """
        with self.session_scope() as session:
            query = session.query(LeadModel).filter(LeadModel.source == source)
            
            # Get total count
            total_count = query.count()
            
            # Paginate results
            leads = query.order_by(LeadModel.updated_at.desc()).limit(limit).offset(offset).all()
            
            return [self._orm_to_pydantic(lead) for lead in leads], total_count
    
    def get_leads_by_location(self, city: Optional[str] = None, state: Optional[str] = None, 
                             limit: int = 100, offset: int = 0) -> Tuple[List[Lead], int]:
        """
        Get leads by location.
        
        Args:
            city: City name
            state: State code
            limit: Maximum number of leads to return
            offset: Offset for pagination
        
        Returns:
            Tuple containing:
            - List[Lead]: List of leads
            - int: Total count
        """
        with self.session_scope() as session:
            query = session.query(LeadModel)
            
            # Apply filters
            if city:
                query = query.filter(LeadModel.city == city)
            
            if state:
                query = query.filter(LeadModel.state == state)
            
            # Get total count
            total_count = query.count()
            
            # Paginate results
            leads = query.order_by(LeadModel.updated_at.desc()).limit(limit).offset(offset).all()
            
            return [self._orm_to_pydantic(lead) for lead in leads], total_count
    
    def search_leads(self, params: LeadSearchParams) -> Tuple[List[Lead], int]:
        """
        Search leads using multiple criteria.
        
        Args:
            params: Search parameters
        
        Returns:
            Tuple containing:
            - List[Lead]: List of leads
            - int: Total count
        """
        with self.session_scope() as session:
            query = session.query(LeadModel)
            
            # Apply filters
            if params.source:
                query = query.filter(LeadModel.source == params.source)
            
            if params.market_sector:
                query = query.filter(LeadModel.market_sector == params.market_sector.value)
            
            if params.lead_type:
                query = query.filter(LeadModel.lead_type == params.lead_type.value)
            
            if params.status:
                query = query.filter(LeadModel.status == params.status.value)
            
            if params.location_city:
                query = query.filter(LeadModel.city == params.location_city)
            
            if params.location_state:
                query = query.filter(LeadModel.state == params.location_state)
            
            if params.min_value is not None:
                query = query.filter(LeadModel.estimated_value >= params.min_value)
            
            if params.max_value is not None:
                query = query.filter(LeadModel.estimated_value <= params.max_value)
            
            if params.min_date is not None:
                query = query.filter(LeadModel.publication_date >= params.min_date)
            
            if params.max_date is not None:
                query = query.filter(LeadModel.publication_date <= params.max_date)
            
            if params.keyword:
                # Search in project name and description
                keyword_filter = f"%{params.keyword}%"
                query = query.filter(
                    (LeadModel.project_name.like(keyword_filter)) | 
                    (LeadModel.description.like(keyword_filter))
                )
            
            # Get total count
            total_count = query.count()
            
            # Paginate results
            leads = query.order_by(LeadModel.updated_at.desc()).limit(params.limit).offset(params.offset).all()
            
            return [self._orm_to_pydantic(lead) for lead in leads], total_count
    
    def update_lead_status(self, lead_id: uuid.UUID, status: LeadStatus) -> Optional[Lead]:
        """
        Update a lead's status.
        
        Args:
            lead_id: Lead ID
            status: New status
        
        Returns:
            Lead or None: Updated lead if found, None otherwise
        """
        with self.session_scope() as session:
            lead_model = session.query(LeadModel).filter(LeadModel.id == str(lead_id)).first()
            
            if not lead_model:
                return None
            
            lead_model.status = status.value
            lead_model.updated_at = datetime.now()
            
            return self._orm_to_pydantic(lead_model)
    
    def update_lead(self, lead: Lead) -> Optional[Lead]:
        """
        Update an existing lead.
        
        Args:
            lead: Lead with updated data
        
        Returns:
            Lead or None: Updated lead if found, None otherwise
        """
        if not lead.id:
            raise ValueError("Lead ID is required for updates")
        
        with self.session_scope() as session:
            lead_model = session.query(LeadModel).filter(LeadModel.id == str(lead.id)).first()
            
            if not lead_model:
                return None
            
            lead_model.update_from_lead(lead)
            
            return self._orm_to_pydantic(lead_model)
    
    def delete_lead(self, lead_id: uuid.UUID) -> bool:
        """
        Delete a lead.
        
        Args:
            lead_id: Lead ID
        
        Returns:
            bool: True if deleted, False if not found
        """
        with self.session_scope() as session:
            lead_model = session.query(LeadModel).filter(LeadModel.id == str(lead_id)).first()
            
            if not lead_model:
                return False
            
            session.delete(lead_model)
            
            return True
    
    def export_leads_to_csv(self, filename: str, leads: List[Lead] = None) -> str:
        """
        Export leads to a CSV file.
        
        Args:
            filename: Output filename
            leads: List of leads to export (or None to export all)
        
        Returns:
            str: Path to the exported file
        """
        # Ensure data directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        # Get leads from database if not provided
        if leads is None:
            with self.session_scope() as session:
                lead_models = session.query(LeadModel).all()
                leads = [self._orm_to_pydantic(lead) for lead in lead_models]
        
        # Define CSV fields
        fieldnames = [
            'id', 'source', 'project_name', 'description', 'market_sector', 
            'lead_type', 'status', 'estimated_value', 'publication_date', 
            'address', 'city', 'state', 'zip_code', 'country',
            'contact_name', 'contact_email', 'contact_phone'
        ]
        
        # Write to CSV
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for lead in leads:
                lead_dict = lead.model_dump()
                
                # Extract location
                location = lead_dict.get('location', {})
                
                # Extract primary contact
                contact = lead_dict.get('contacts', [{}])[0] if lead_dict.get('contacts') else {}
                
                # Create row
                row = {
                    'id': str(lead_dict.get('id')),
                    'source': lead_dict.get('source'),
                    'project_name': lead_dict.get('project_name'),
                    'description': lead_dict.get('description'),
                    'market_sector': lead_dict.get('market_sector'),
                    'lead_type': lead_dict.get('lead_type'),
                    'status': lead_dict.get('status'),
                    'estimated_value': lead_dict.get('estimated_value'),
                    'publication_date': lead_dict.get('publication_date').isoformat() if lead_dict.get('publication_date') else '',
                    'address': location.get('address', ''),
                    'city': location.get('city', ''),
                    'state': location.get('state', ''),
                    'zip_code': location.get('zip_code', ''),
                    'country': location.get('country', ''),
                    'contact_name': contact.get('name', ''),
                    'contact_email': contact.get('email', ''),
                    'contact_phone': contact.get('phone', '')
                }
                
                writer.writerow(row)
        
        return filename
    
    def export_leads_to_json(self, filename: str, leads: List[Lead] = None) -> str:
        """
        Export leads to a JSON file.
        
        Args:
            filename: Output filename
            leads: List of leads to export (or None to export all)
        
        Returns:
            str: Path to the exported file
        """
        # Ensure data directory exists
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        # Get leads from database if not provided
        if leads is None:
            with self.session_scope() as session:
                lead_models = session.query(LeadModel).all()
                leads = [self._orm_to_pydantic(lead) for lead in lead_models]
        
        # Convert leads to dictionaries
        lead_dicts = [lead.model_dump() for lead in leads]
        
        # Convert dates to strings
        for lead_dict in lead_dicts:
            for key, value in lead_dict.items():
                if isinstance(value, datetime):
                    lead_dict[key] = value.isoformat()
                elif isinstance(value, uuid.UUID):
                    lead_dict[key] = str(value)
        
        # Write to JSON
        with open(filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(lead_dicts, jsonfile, indent=2)
        
        return filename
    
    def count_leads_by_source(self) -> Dict[str, int]:
        """
        Count leads by source.
        
        Returns:
            Dict[str, int]: Dictionary with sources as keys and counts as values
        """
        with self.session_scope() as session:
            counts = session.query(
                LeadModel.source,
                func.count(LeadModel.id).label('count')
            ).group_by(LeadModel.source).all()
            
            return {source: count for source, count in counts}
    
    def count_leads_by_status(self) -> Dict[str, int]:
        """
        Count leads by status.
        
        Returns:
            Dict[str, int]: Dictionary with statuses as keys and counts as values
        """
        with self.session_scope() as session:
            counts = session.query(
                LeadModel.status,
                func.count(LeadModel.id).label('count')
            ).group_by(LeadModel.status).all()
            
            return {status: count for status, count in counts}
    
    def count_leads_by_market_sector(self) -> Dict[str, int]:
        """
        Count leads by market sector.
        
        Returns:
            Dict[str, int]: Dictionary with sectors as keys and counts as values
        """
        with self.session_scope() as session:
            counts = session.query(
                LeadModel.market_sector,
                func.count(LeadModel.id).label('count')
            ).group_by(LeadModel.market_sector).all()
            
            return {sector if sector else 'unknown': count for sector, count in counts}
    
    def _orm_to_pydantic(self, lead_model: LeadModel) -> Lead:
        """
        Convert ORM model to Pydantic model.
        
        Args:
            lead_model: SQLAlchemy model
        
        Returns:
            Lead: Pydantic model
        """
        # Convert to dictionary
        lead_dict = lead_model.to_dict()
        
        # Create Pydantic model
        return Lead.model_validate(lead_dict)
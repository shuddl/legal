#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lead Enrichment and Classification Testing Framework

This module provides comprehensive testing capabilities for validating
the quality, accuracy, and performance of lead enrichment and classification
processes. It includes test datasets, mock services, metrics collection,
failure analysis, and detailed reporting.
"""

import os
import sys
import json
import time
import logging
import unittest
import statistics
import datetime
import random
import csv
import tempfile
import uuid
import re
import concurrent.futures
from typing import Dict, List, Any, Optional, Union, Set, Tuple
from pathlib import Path
from dataclasses import dataclass, field, asdict
from unittest.mock import patch, MagicMock, PropertyMock
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from io import StringIO
import psutil
import requests

# Local imports
from perera_lead_scraper.config import config
from perera_lead_scraper.models.lead import Lead, MarketSector, LeadType, Location
from perera_lead_scraper.enrichment.enrichment import LeadEnricher, EnrichmentError
from perera_lead_scraper.classification.classifier import (
    LeadClassifier, ValueCategory, TimelineCategory, 
    DecisionStage, CompetitionLevel, PriorityLevel, ClassificationError
)
from perera_lead_scraper.nlp.nlp_processor import NLPProcessor
from perera_lead_scraper.utils.storage import LocalStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
TEST_DATA_DIR = Path(config.TEST_DATA_DIR) if hasattr(config, 'TEST_DATA_DIR') else Path(__file__).parent / "test_data"
GROUND_TRUTH_FILE = TEST_DATA_DIR / "enrichment_ground_truth.json"
TEST_REPORT_DIR = TEST_DATA_DIR / "reports"
DEFAULT_SAMPLE_SIZE = 50
API_THROTTLING = True  # Set to False to test with real APIs (caution: may use quota)


@dataclass
class TestMetrics:
    """Container for test metrics and results."""
    # Enrichment metrics
    company_data_success_rate: float = 0.0
    website_discovery_success_rate: float = 0.0
    contact_extraction_success_rate: float = 0.0
    company_size_success_rate: float = 0.0
    project_stage_success_rate: float = 0.0
    related_projects_success_rate: float = 0.0
    lead_scoring_accuracy: float = 0.0
    
    # Classification metrics
    value_classification_accuracy: float = 0.0
    timeline_classification_accuracy: float = 0.0
    decision_stage_accuracy: float = 0.0
    competition_level_accuracy: float = 0.0
    win_probability_calibration: float = 0.0
    priority_score_correlation: float = 0.0
    
    # Performance metrics
    avg_enrichment_time: float = 0.0
    avg_classification_time: float = 0.0
    memory_usage_mb: float = 0.0
    api_calls_count: Dict[str, int] = field(default_factory=dict)
    
    # Error metrics
    enrichment_errors: Dict[str, int] = field(default_factory=dict)
    classification_errors: Dict[str, int] = field(default_factory=dict)
    
    # Overall metrics
    overall_data_completeness: float = 0.0
    overall_classification_accuracy: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return asdict(self)


class EnrichmentMock:
    """Mock service for external APIs used in enrichment."""
    
    def __init__(self, mock_level: str = "partial"):
        """
        Initialize the enrichment mock service.
        
        Args:
            mock_level: Level of mocking ('full', 'partial', 'none')
        """
        self.mock_level = mock_level
        self.mock_data = self._load_mock_data()
        self.api_calls = {}
        
    def _load_mock_data(self) -> Dict[str, Any]:
        """Load mock data from test fixtures."""
        mock_data_path = TEST_DATA_DIR / "mock_api_responses.json"
        try:
            if mock_data_path.exists():
                with open(mock_data_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                logger.warning(f"Mock data file not found: {mock_data_path}")
                self._create_default_mock_data(mock_data_path)
                return self._load_mock_data()
        except Exception as e:
            logger.error(f"Error loading mock data: {e}")
            return {}
    
    def _create_default_mock_data(self, path: Path) -> None:
        """Create default mock data if not found."""
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        
        default_data = {
            "company_data_api": {
                "acme_construction": {
                    "name": "Acme Construction",
                    "description": "A leading construction company specializing in commercial projects.",
                    "website": "https://acmeconstruction.example.com",
                    "industry": "Construction",
                    "size": "Medium (50-249)",
                    "location": {
                        "address": "123 Builder St",
                        "city": "Los Angeles",
                        "state": "California",
                        "postal_code": "90001"
                    }
                },
                "healthcare_builders": {
                    "name": "Healthcare Builders Inc",
                    "description": "Specialized construction company focused on healthcare facilities.",
                    "website": "https://healthcarebuilders.example.com",
                    "industry": "Construction - Healthcare",
                    "size": "Large (250-999)",
                    "location": {
                        "address": "456 Medical Plaza",
                        "city": "San Diego",
                        "state": "California",
                        "postal_code": "92101"
                    }
                }
            },
            "contact_finder_api": {
                "acmeconstruction.example.com": [
                    {
                        "name": "John Smith",
                        "title": "Project Manager",
                        "email": "john.smith@acmeconstruction.example.com",
                        "phone": "(555) 123-4567"
                    },
                    {
                        "name": "Jane Doe",
                        "title": "Business Development Director",
                        "email": "jane.doe@acmeconstruction.example.com",
                        "phone": "(555) 123-4568"
                    }
                ],
                "healthcarebuilders.example.com": [
                    {
                        "name": "Robert Johnson",
                        "title": "Healthcare Division Director",
                        "email": "robert.johnson@healthcarebuilders.example.com",
                        "phone": "(555) 987-6543"
                    }
                ]
            },
            "project_database_api": {
                "acme_construction": [
                    {
                        "id": "proj001",
                        "title": "Downtown Office Tower",
                        "description": "25-story office building in downtown Los Angeles",
                        "location": "Los Angeles, CA",
                        "project_type": "Commercial",
                        "project_value": 75000000,
                        "date": "2023-08-15"
                    },
                    {
                        "id": "proj002",
                        "title": "Retail Complex Renovation",
                        "description": "Major renovation of 150,000 sq ft shopping center",
                        "location": "Orange County, CA",
                        "project_type": "Commercial",
                        "project_value": 15000000,
                        "date": "2023-06-22"
                    }
                ],
                "healthcare_builders": [
                    {
                        "id": "proj003",
                        "title": "Memorial Hospital Wing",
                        "description": "New pediatric wing for Memorial Hospital",
                        "location": "San Diego, CA",
                        "project_type": "Healthcare",
                        "project_value": 45000000,
                        "date": "2023-07-10"
                    }
                ]
            }
        }
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=2)
        
        logger.info(f"Created default mock data at: {path}")
    
    def get_company_data(self, company_name: str) -> Dict[str, Any]:
        """
        Get mock company data.
        
        Args:
            company_name: Name of the company to look up
            
        Returns:
            Dictionary of company information
        """
        self._record_api_call("company_data_api")
        
        # Normalize company name for lookup
        normalized_name = self._normalize_key(company_name)
        
        # Check in mock data
        for key, data in self.mock_data.get("company_data_api", {}).items():
            if normalized_name in key or key in normalized_name:
                return data
        
        # Generate mock data for unknown company
        return {
            "name": company_name,
            "description": f"A construction company active in Southern California.",
            "website": f"https://{normalized_name.replace(' ', '')}.example.com",
            "industry": "Construction",
            "size": random.choice(["Small (10-49)", "Medium (50-249)", "Large (250-999)"]),
            "location": {
                "city": random.choice(["Los Angeles", "San Diego", "Orange County"]),
                "state": "California"
            }
        }
    
    def get_contacts(self, website: str) -> List[Dict[str, Any]]:
        """
        Get mock contact information for a company website.
        
        Args:
            website: Company website URL
            
        Returns:
            List of contact dictionaries
        """
        self._record_api_call("contact_finder_api")
        
        # Extract domain from URL
        domain = self._extract_domain(website)
        
        # Check in mock data
        for key, data in self.mock_data.get("contact_finder_api", {}).items():
            if domain in key or key in domain:
                return data
        
        # Generate mock data for unknown website
        first_names = ["John", "Jane", "Michael", "Emily", "David", "Sarah"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia"]
        titles = ["Project Manager", "Director", "CEO", "Business Development", "Operations Manager"]
        
        # Generate 1-3 contacts
        num_contacts = random.randint(1, 3)
        contacts = []
        
        for _ in range(num_contacts):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            title = random.choice(titles)
            
            contacts.append({
                "name": f"{first_name} {last_name}",
                "title": title,
                "email": f"{first_name.lower()}.{last_name.lower()}@{domain}",
                "phone": f"(555) {random.randint(100, 999)}-{random.randint(1000, 9999)}"
            })
        
        return contacts
    
    def get_related_projects(self, company_name: str) -> List[Dict[str, Any]]:
        """
        Get mock related projects for a company.
        
        Args:
            company_name: Name of the company
            
        Returns:
            List of project dictionaries
        """
        self._record_api_call("project_database_api")
        
        # Normalize company name for lookup
        normalized_name = self._normalize_key(company_name)
        
        # Check in mock data
        for key, data in self.mock_data.get("project_database_api", {}).items():
            if normalized_name in key or key in normalized_name:
                return data
        
        # Generate mock data for unknown company
        project_types = ["Commercial", "Healthcare", "Education", "Residential", "Industrial"]
        locations = ["Los Angeles, CA", "San Diego, CA", "Orange County, CA", "Riverside, CA"]
        titles = [
            "Office Building", "Medical Center", "School Renovation", "Apartment Complex",
            "Retail Development", "Hospital Wing", "University Building", "Data Center"
        ]
        
        # Generate 1-3 projects
        num_projects = random.randint(1, 3)
        projects = []
        
        for i in range(num_projects):
            project_type = random.choice(project_types)
            location = random.choice(locations)
            title = f"{random.choice(titles)} - {location.split(',')[0]}"
            
            projects.append({
                "id": f"proj{random.randint(1000, 9999)}",
                "title": title,
                "description": f"A {project_type.lower()} project in {location}",
                "location": location,
                "project_type": project_type,
                "project_value": random.randint(5, 100) * 1000000,
                "date": self._random_date()
            })
        
        return projects
    
    def _normalize_key(self, input_str: str) -> str:
        """Normalize string for key comparison."""
        if not input_str:
            return ""
        return input_str.lower().replace(" ", "_")
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        if not url:
            return ""
        
        match = re.search(r'https?://(?:www\.)?([^/]+)', url)
        if match:
            return match.group(1)
        return url
    
    def _random_date(self) -> str:
        """Generate a random date in ISO format within the last year."""
        days = random.randint(0, 365)
        date = datetime.datetime.now() - datetime.timedelta(days=days)
        return date.strftime('%Y-%m-%d')
    
    def _record_api_call(self, api_name: str) -> None:
        """Record an API call for metrics tracking."""
        if api_name not in self.api_calls:
            self.api_calls[api_name] = 0
        self.api_calls[api_name] += 1


@dataclass
class TestLead:
    """Sample lead data for testing."""
    id: str
    project_name: str
    description: str
    market_sector: str
    estimated_value: Optional[float]
    location_city: Optional[str]
    location_state: Optional[str]
    company_name: Optional[str]
    
    # Ground truth for validation
    ground_truth: Dict[str, Any] = field(default_factory=dict)
    
    def to_lead_obj(self) -> Lead:
        """Convert to Lead model object."""
        location = Location(
            city=self.location_city,
            state=self.location_state
        )
        
        try:
            market_sector = MarketSector(self.market_sector)
        except ValueError:
            market_sector = MarketSector.OTHER
        
        return Lead(
            id=self.id,
            source="test",
            project_name=self.project_name,
            description=self.description,
            market_sector=market_sector,
            estimated_value=self.estimated_value,
            location=location,
            extra_data={"company": {"name": self.company_name} if self.company_name else {}}
        )


class EnrichmentTestDataset:
    """Dataset of test leads with ground truth for enrichment validation."""
    
    def __init__(self, sample_size: int = DEFAULT_SAMPLE_SIZE):
        """
        Initialize the test dataset.
        
        Args:
            sample_size: Number of test leads to generate
        """
        self.sample_size = sample_size
        self.test_leads = []
        self.ground_truth = {}
        
        # Create or load test data
        self._initialize_dataset()
    
    def _initialize_dataset(self) -> None:
        """Initialize the test dataset from file or generate new data."""
        ground_truth_path = GROUND_TRUTH_FILE
        
        if ground_truth_path.exists():
            try:
                # Load existing dataset
                with open(ground_truth_path, "r", encoding="utf-8") as f:
                    loaded_data = json.load(f)
                    self.ground_truth = loaded_data.get("ground_truth", {})
                    
                    # Create test leads from loaded data
                    test_leads_data = loaded_data.get("test_leads", [])
                    self.test_leads = [TestLead(**lead_data) for lead_data in test_leads_data]
                    
                    # If we need more test leads, generate them
                    if len(self.test_leads) < self.sample_size:
                        additional_leads = self._generate_test_leads(
                            self.sample_size - len(self.test_leads)
                        )
                        self.test_leads.extend(additional_leads)
                
                logger.info(f"Loaded {len(self.test_leads)} test leads from file")
                
            except Exception as e:
                logger.error(f"Error loading test dataset: {e}")
                self._generate_dataset()
        else:
            logger.info("Ground truth file not found, generating new dataset")
            self._generate_dataset()
    
    def _generate_dataset(self) -> None:
        """Generate a new test dataset."""
        self.test_leads = self._generate_test_leads(self.sample_size)
        self._generate_ground_truth()
        self._save_dataset()
    
    def _generate_test_leads(self, count: int) -> List[TestLead]:
        """
        Generate sample test leads.
        
        Args:
            count: Number of test leads to generate
            
        Returns:
            List of generated TestLead objects
        """
        test_leads = []
        
        # Sample data for lead generation
        project_types = {
            "healthcare": [
                "Medical Center", "Hospital Expansion", "Emergency Department", 
                "Medical Office Building", "Surgery Center", "Rehabilitation Facility"
            ],
            "education": [
                "University Building", "School Renovation", "Campus Housing",
                "Laboratory Facility", "Student Center", "Athletic Complex"
            ],
            "energy": [
                "Power Plant", "Solar Farm", "Energy Storage Facility",
                "Substation Upgrade", "Grid Expansion", "Battery Storage"
            ],
            "commercial": [
                "Office Tower", "Retail Development", "Mixed-Use Building",
                "Corporate Campus", "Hotel Construction", "Restaurant Complex"
            ],
            "entertainment": [
                "Theater Complex", "Museum Expansion", "Sports Stadium",
                "Concert Venue", "Convention Center", "Theme Park Attraction"
            ]
        }
        
        locations = [
            ("Los Angeles", "California"),
            ("San Diego", "California"),
            ("Orange County", "California"),
            ("Riverside", "California"),
            ("San Bernardino", "California"),
            ("Ventura", "California"),
            ("Santa Barbara", "California"),
            ("Long Beach", "California"),
            ("Irvine", "California"),
            ("Pasadena", "California"),
            ("Anaheim", "California"),
            ("Phoenix", "Arizona"),
            ("Las Vegas", "Nevada")
        ]
        
        companies = [
            "Acme Construction",
            "Healthcare Builders Inc",
            "Education Constructors",
            "Commercial Development Group",
            "Energy Construction Services",
            "Entertainment Venues Builders",
            "Pacific Contractors",
            "West Coast Development",
            "Southern California Construction",
            "Metro Builders",
            "Regional Development Corporation",
            "Urban Constructors Ltd",
            "Specialized Projects Group"
        ]
        
        # Generate leads
        for i in range(count):
            # Select random sector
            sector = random.choice(list(project_types.keys()))
            project_type = random.choice(project_types[sector])
            
            # Select random location
            location_city, location_state = random.choice(locations)
            
            # Select random company
            company_name = random.choice(companies)
            
            # Generate value based on sector and project type
            if sector == "healthcare" or sector == "energy":
                value_range = (10000000, 100000000)  # $10M - $100M
            elif sector == "education" or sector == "entertainment":
                value_range = (5000000, 50000000)  # $5M - $50M
            else:  # commercial
                value_range = (2000000, 30000000)  # $2M - $30M
            
            value = random.randint(value_range[0], value_range[1])
            
            # Decide if some fields should be missing (for edge cases)
            has_value = random.random() > 0.1
            has_company = random.random() > 0.2
            
            # Create description with varying detail levels
            description_parts = [
                f"Construction of a new {project_type} in {location_city}, {location_state}.",
                f"The project involves approximately {random.randint(10000, 200000)} square feet of space.",
                f"Estimated completion date is Q{random.randint(1, 4)} {random.randint(2023, 2026)}.",
                f"The project will include {random.choice(['state-of-the-art', 'modern', 'cutting-edge'])} facilities.",
                f"This development is part of a larger {random.choice(['expansion', 'revitalization', 'growth'])} initiative."
            ]
            
            # Use varying number of description parts
            desc_count = random.randint(1, len(description_parts))
            description = " ".join(description_parts[:desc_count])
            
            # Create test lead
            lead = TestLead(
                id=str(uuid.uuid4()),
                project_name=f"{location_city} {project_type}",
                description=description,
                market_sector=sector,
                estimated_value=value if has_value else None,
                location_city=location_city,
                location_state=location_state,
                company_name=company_name if has_company else None
            )
            
            test_leads.append(lead)
        
        return test_leads
    
    def _generate_ground_truth(self) -> None:
        """Generate ground truth data for validation."""
        # Create mock enricher for generating data
        mock = EnrichmentMock()
        
        for lead in self.test_leads:
            lead_id = lead.id
            self.ground_truth[lead_id] = {}
            
            # Company data ground truth
            if lead.company_name:
                company_data = mock.get_company_data(lead.company_name)
                self.ground_truth[lead_id]["company"] = company_data
                
                # Website
                if "website" in company_data:
                    self.ground_truth[lead_id]["company_url"] = company_data["website"]
                    
                    # Contacts
                    contacts = mock.get_contacts(company_data["website"])
                    self.ground_truth[lead_id]["contacts"] = contacts
                
                # Company size
                if "size" in company_data:
                    self.ground_truth[lead_id]["company_size"] = company_data["size"]
                
                # Related projects
                related_projects = mock.get_related_projects(lead.company_name)
                self.ground_truth[lead_id]["related_projects"] = related_projects
            
            # Project stage ground truth - derived from description
            project_stages = ["Planning", "Design", "Approval", "Funding", "Construction"]
            self.ground_truth[lead_id]["project_stage"] = random.choice(project_stages)
            
            # Lead score ground truth
            value_score = 0.3 if lead.estimated_value and lead.estimated_value > 10000000 else 0.2
            timeline_score = random.uniform(0.2, 0.4)
            location_score = 0.3 if lead.location_state == "California" else 0.1
            sector_score = 0.3 if lead.market_sector in ["healthcare", "education"] else 0.2
            
            self.ground_truth[lead_id]["lead_score"] = {
                "total": int(min(100, (value_score + timeline_score + location_score + sector_score) * 100)),
                "quality": self._score_to_quality(value_score + timeline_score + location_score + sector_score)
            }
            
            # Classification ground truth
            self._add_classification_ground_truth(lead)
    
    def _score_to_quality(self, score: float) -> str:
        """Convert a score to quality rating."""
        if score >= 0.8:
            return "Excellent"
        elif score >= 0.6:
            return "Good"
        elif score >= 0.4:
            return "Average"
        elif score >= 0.2:
            return "Fair"
        else:
            return "Poor"
    
    def _add_classification_ground_truth(self, lead: TestLead) -> None:
        """Add classification ground truth for a lead."""
        lead_id = lead.id
        
        # Value category
        if lead.estimated_value:
            if lead.estimated_value < 2000000:
                value_category = ValueCategory.SMALL.value
            elif lead.estimated_value < 10000000:
                value_category = ValueCategory.MEDIUM.value
            elif lead.estimated_value < 50000000:
                value_category = ValueCategory.LARGE.value
            else:
                value_category = ValueCategory.MAJOR.value
        else:
            value_category = ValueCategory.UNKNOWN.value
        
        # Timeline category - derived from description
        timeline_keywords = {
            TimelineCategory.IMMEDIATE.value: ["this month", "next month", "immediately", "60 days", "90 days", "Q1", "Q2"],
            TimelineCategory.SHORT_TERM.value: ["soon", "this quarter", "next quarter", "6 months", "Q2", "Q3"],
            TimelineCategory.MID_TERM.value: ["mid-term", "later this year", "next year", "Q3", "Q4"],
            TimelineCategory.LONG_TERM.value: ["long-term", "future", "years", "Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025"]
        }
        
        # Check for timeline indicators in description
        timeline_category = TimelineCategory.UNKNOWN.value
        for category, keywords in timeline_keywords.items():
            if any(keyword in lead.description.lower() for keyword in keywords):
                timeline_category = category
                break
                
        # If no match found, assign randomly but weighted toward mid-term
        if timeline_category == TimelineCategory.UNKNOWN.value:
            weights = [0.2, 0.3, 0.4, 0.1]  # Weights for immediate, short, mid, long
            timeline_category = random.choices(
                [cat.value for cat in TimelineCategory if cat != TimelineCategory.UNKNOWN],
                weights=weights
            )[0]
        
        # Decision stage - based on timeline
        if timeline_category == TimelineCategory.IMMEDIATE.value:
            decision_stage = random.choice([DecisionStage.APPROVAL.value, DecisionStage.IMPLEMENTATION.value])
        elif timeline_category == TimelineCategory.SHORT_TERM.value:
            decision_stage = random.choice([DecisionStage.PLANNING.value, DecisionStage.APPROVAL.value])
        elif timeline_category == TimelineCategory.MID_TERM.value:
            decision_stage = random.choice([DecisionStage.CONCEPTUAL.value, DecisionStage.PLANNING.value])
        else:
            decision_stage = DecisionStage.CONCEPTUAL.value
        
        # Competition level - based on market sector and value
        high_competition_sectors = ["commercial", "residential"]
        if lead.market_sector in high_competition_sectors:
            competition_level = CompetitionLevel.HIGH.value
        elif lead.estimated_value and lead.estimated_value > 20000000:
            competition_level = CompetitionLevel.HIGH.value
        elif lead.market_sector in ["healthcare", "energy"]:
            competition_level = CompetitionLevel.MEDIUM.value
        else:
            competition_level = random.choice([CompetitionLevel.LOW.value, CompetitionLevel.MEDIUM.value])
        
        # Win probability - based on multiple factors
        base_probability = 0.5
        
        # Adjust for sector
        if lead.market_sector in ["healthcare", "education"]:
            sector_adj = 0.2
        elif lead.market_sector == "commercial":
            sector_adj = 0.1
        elif lead.market_sector == "energy":
            sector_adj = 0.0
        else:
            sector_adj = -0.1
            
        # Adjust for location
        if lead.location_state == "California":
            location_adj = 0.2
        else:
            location_adj = -0.1
            
        # Adjust for competition
        if competition_level == CompetitionLevel.LOW.value:
            competition_adj = 0.1
        elif competition_level == CompetitionLevel.MEDIUM.value:
            competition_adj = 0.0
        else:
            competition_adj = -0.1
            
        win_probability = min(0.95, max(0.05, base_probability + sector_adj + location_adj + competition_adj))
        
        # Priority level - derived from other classifications
        priority_score = 0
        
        if value_category == ValueCategory.MAJOR.value:
            priority_score += 30
        elif value_category == ValueCategory.LARGE.value:
            priority_score += 25
        elif value_category == ValueCategory.MEDIUM.value:
            priority_score += 15
        elif value_category == ValueCategory.SMALL.value:
            priority_score += 10
            
        if timeline_category == TimelineCategory.IMMEDIATE.value:
            priority_score += 25
        elif timeline_category == TimelineCategory.SHORT_TERM.value:
            priority_score += 20
        elif timeline_category == TimelineCategory.MID_TERM.value:
            priority_score += 15
        elif timeline_category == TimelineCategory.LONG_TERM.value:
            priority_score += 5
            
        priority_score += int(win_probability * 30)
        
        if lead.location_state == "California":
            priority_score += 15
        else:
            priority_score += 5
            
        priority_score = min(100, max(1, priority_score))
        
        if priority_score >= 80:
            priority_level = PriorityLevel.CRITICAL.value
        elif priority_score >= 60:
            priority_level = PriorityLevel.HIGH.value
        elif priority_score >= 40:
            priority_level = PriorityLevel.MEDIUM.value
        elif priority_score >= 20:
            priority_level = PriorityLevel.LOW.value
        else:
            priority_level = PriorityLevel.MINIMAL.value
        
        # Store all classification ground truth
        self.ground_truth[lead_id]["classification"] = {
            "value_category": value_category,
            "timeline_category": timeline_category,
            "decision_stage": decision_stage,
            "competition_level": competition_level,
            "win_probability": win_probability,
            "priority_score": priority_score,
            "priority_level": priority_level
        }
    
    def _save_dataset(self) -> None:
        """Save the generated dataset to file."""
        ground_truth_path = GROUND_TRUTH_FILE
        
        # Ensure directory exists
        ground_truth_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Prepare data for saving
        save_data = {
            "test_leads": [
                {
                    "id": lead.id,
                    "project_name": lead.project_name,
                    "description": lead.description,
                    "market_sector": lead.market_sector,
                    "estimated_value": lead.estimated_value,
                    "location_city": lead.location_city,
                    "location_state": lead.location_state,
                    "company_name": lead.company_name
                }
                for lead in self.test_leads
            ],
            "ground_truth": self.ground_truth
        }
        
        # Save to file
        with open(ground_truth_path, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=2)
        
        logger.info(f"Saved test dataset to {ground_truth_path}")
    
    def get_leads(self) -> List[TestLead]:
        """Get the list of test leads."""
        return self.test_leads
    
    def get_ground_truth(self, lead_id: str) -> Dict[str, Any]:
        """
        Get ground truth data for a specific lead.
        
        Args:
            lead_id: ID of the lead
            
        Returns:
            Ground truth data dictionary
        """
        return self.ground_truth.get(lead_id, {})


class LeadEnrichmentTester:
    """
    Test framework for lead enrichment and classification.
    
    This class provides methods for testing the enrichment and classification
    processes, measuring performance, and generating reports.
    """
    
    def __init__(self, 
                mock_level: str = "partial",
                sample_size: int = DEFAULT_SAMPLE_SIZE):
        """
        Initialize the tester.
        
        Args:
            mock_level: Level of API mocking ('full', 'partial', 'none')
            sample_size: Number of test leads to use
        """
        self.mock_level = mock_level
        self.sample_size = sample_size
        
        # Load test dataset
        self.dataset = EnrichmentTestDataset(sample_size)
        
        # Create mock service
        self.mock = EnrichmentMock(mock_level)
        
        # Initialize test metrics
        self.metrics = TestMetrics()
        
        # Create output directory for reports
        TEST_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initialized LeadEnrichmentTester with mock_level={mock_level}, sample_size={sample_size}")
    
    def setup_enricher(self) -> LeadEnricher:
        """
        Set up the lead enricher with appropriate mocks.
        
        Returns:
            Configured LeadEnricher instance
        """
        # Create mock config
        mock_config = MagicMock()
        
        # Create enricher
        enricher = LeadEnricher(config=mock_config)
        
        # Apply mocks based on mock level
        if self.mock_level in ["full", "partial"]:
            # Mock company data lookup
            enricher.lookup_company_data = self.mock.get_company_data
            
            # Mock contact extraction
            enricher.extract_contact_details = self.mock.get_contacts
            
            # Mock related projects lookup
            enricher.find_related_projects = self.mock.get_related_projects
        
        return enricher
    
    def setup_classifier(self) -> LeadClassifier:
        """
        Set up the lead classifier with appropriate mocks.
        
        Returns:
            Configured LeadClassifier instance
        """
        # Create mock NLP processor
        mock_nlp = MagicMock()
        mock_nlp.preprocess_text.side_effect = lambda text: text
        
        # Create test config
        test_config = {
            "value_tiers": {
                "default": {
                    "small": 2000000,      # $2M
                    "medium": 10000000,    # $10M
                    "large": 50000000      # $50M
                },
                "healthcare": {
                    "small": 5000000,      # $5M
                    "medium": 20000000,    # $20M
                    "large": 100000000     # $100M
                }
            },
            "sector_expertise_levels": {
                "healthcare": 0.9,
                "education": 0.85,
                "commercial": 0.8,
                "other": 0.5
            },
            "strategic_locations": [
                "Los Angeles", "Orange County", "San Diego", "Riverside",
                "San Bernardino", "Ventura", "Santa Barbara", "Long Beach"
            ]
        }
        
        # Create classifier
        classifier = LeadClassifier(nlp_processor=mock_nlp, config_override=test_config)
        
        return classifier
    
    def test_enrichment(self) -> TestMetrics:
        """
        Test the lead enrichment process.
        
        Returns:
            TestMetrics with enrichment results
        """
        logger.info("Starting enrichment testing")
        
        # Setup enricher
        enricher = self.setup_enricher()
        
        # Get test leads
        test_leads = self.dataset.get_leads()
        lead_objs = [lead.to_lead_obj() for lead in test_leads]
        
        # Tracking metrics
        company_data_success = 0
        website_discovery_success = 0
        contact_extraction_success = 0
        company_size_success = 0
        project_stage_success = 0
        related_projects_success = 0
        lead_scoring_match = 0
        
        enrichment_times = []
        api_calls = {}
        
        # Process each lead
        for i, (test_lead, lead_obj) in enumerate(zip(test_leads, lead_objs)):
            lead_id = test_lead.id
            ground_truth = self.dataset.get_ground_truth(lead_id)
            
            try:
                # Measure memory usage
                process = psutil.Process(os.getpid())
                mem_before = process.memory_info().rss / 1024 / 1024  # MB
                
                # Time the enrichment
                start_time = time.time()
                enriched_lead = enricher.enrich_lead(asdict(lead_obj))
                elapsed_time = time.time() - start_time
                
                # Record API calls
                for api, count in self.mock.api_calls.items():
                    if api not in api_calls:
                        api_calls[api] = 0
                    api_calls[api] += count
                
                # Clear API calls for next lead
                self.mock.api_calls = {}
                
                # Measure memory after
                mem_after = process.memory_info().rss / 1024 / 1024  # MB
                memory_used = mem_after - mem_before
                
                # Record time
                enrichment_times.append(elapsed_time)
                
                # Compare with ground truth
                if ground_truth:
                    # Check company data
                    if enriched_lead.get('company') and ground_truth.get('company'):
                        company_match = self._compare_company_data(
                            enriched_lead.get('company', {}),
                            ground_truth.get('company', {})
                        )
                        if company_match >= 0.7:
                            company_data_success += 1
                    
                    # Check website discovery
                    if enriched_lead.get('company_url') and ground_truth.get('company_url'):
                        if self._normalize_url(enriched_lead['company_url']) == self._normalize_url(ground_truth['company_url']):
                            website_discovery_success += 1
                    
                    # Check contact extraction
                    if enriched_lead.get('contacts') and ground_truth.get('contacts'):
                        contact_match = self._compare_contacts(
                            enriched_lead.get('contacts', []),
                            ground_truth.get('contacts', [])
                        )
                        if contact_match >= 0.5:  # Lower threshold for contacts
                            contact_extraction_success += 1
                    
                    # Check company size
                    if enriched_lead.get('company_size') and ground_truth.get('company_size'):
                        if self._compare_company_size(
                            enriched_lead.get('company_size', ''),
                            ground_truth.get('company_size', '')
                        ):
                            company_size_success += 1
                    
                    # Check project stage
                    if enriched_lead.get('project_stage') and ground_truth.get('project_stage'):
                        if enriched_lead['project_stage'] == ground_truth['project_stage']:
                            project_stage_success += 1
                    
                    # Check related projects
                    if enriched_lead.get('related_projects') and ground_truth.get('related_projects'):
                        if len(enriched_lead['related_projects']) > 0:
                            related_projects_success += 1
                    
                    # Check lead score
                    if enriched_lead.get('lead_score') and ground_truth.get('lead_score'):
                        score_diff = abs(
                            enriched_lead['lead_score'].get('total', 0) - 
                            ground_truth['lead_score'].get('total', 0)
                        )
                        if score_diff <= 20:  # Allow some variance
                            lead_scoring_match += 1
                
                # Log progress
                if (i + 1) % 10 == 0 or i + 1 == len(test_leads):
                    logger.info(f"Processed {i + 1}/{len(test_leads)} leads for enrichment testing")
                
            except Exception as e:
                logger.error(f"Error testing enrichment for lead {lead_id}: {str(e)}")
        
        # Calculate metrics
        test_count = len(test_leads)
        
        def calc_percentage(value, total):
            return (value / total) * 100 if total > 0 else 0
        
        # Store in metrics object
        self.metrics.company_data_success_rate = calc_percentage(company_data_success, test_count)
        self.metrics.website_discovery_success_rate = calc_percentage(website_discovery_success, test_count)
        self.metrics.contact_extraction_success_rate = calc_percentage(contact_extraction_success, test_count)
        self.metrics.company_size_success_rate = calc_percentage(company_size_success, test_count)
        self.metrics.project_stage_success_rate = calc_percentage(project_stage_success, test_count)
        self.metrics.related_projects_success_rate = calc_percentage(related_projects_success, test_count)
        self.metrics.lead_scoring_accuracy = calc_percentage(lead_scoring_match, test_count)
        
        self.metrics.avg_enrichment_time = statistics.mean(enrichment_times) if enrichment_times else 0
        self.metrics.api_calls_count = api_calls
        
        # Calculate overall data completeness
        self.metrics.overall_data_completeness = statistics.mean([
            self.metrics.company_data_success_rate,
            self.metrics.website_discovery_success_rate,
            self.metrics.contact_extraction_success_rate,
            self.metrics.company_size_success_rate,
            self.metrics.project_stage_success_rate,
            self.metrics.related_projects_success_rate
        ]) / 100  # Convert percentage to decimal
        
        logger.info("Completed enrichment testing")
        
        return self.metrics
    
    def test_classification(self) -> TestMetrics:
        """
        Test the lead classification process.
        
        Returns:
            TestMetrics with classification results
        """
        logger.info("Starting classification testing")
        
        # Setup classifier
        classifier = self.setup_classifier()
        
        # Get test leads
        test_leads = self.dataset.get_leads()
        lead_objs = [lead.to_lead_obj() for lead in test_leads]
        
        # Tracking metrics
        value_classification_correct = 0
        timeline_classification_correct = 0
        decision_stage_correct = 0
        competition_level_correct = 0
        win_probability_close = 0
        priority_score_close = 0
        
        classification_times = []
        classification_errors = {}
        
        # Process each lead
        for i, (test_lead, lead_obj) in enumerate(zip(test_leads, lead_objs)):
            lead_id = test_lead.id
            ground_truth = self.dataset.get_ground_truth(lead_id)
            
            try:
                # Time the classification
                start_time = time.time()
                classified_lead = classifier.classify_lead(lead_obj)
                elapsed_time = time.time() - start_time
                
                # Record time
                classification_times.append(elapsed_time)
                
                # Get classification results
                classification = classified_lead.extra_data.get('classification', {})
                
                # Compare with ground truth
                if ground_truth and 'classification' in ground_truth:
                    gt_classification = ground_truth['classification']
                    
                    # Check value category
                    if classification.get('value_category') == gt_classification.get('value_category'):
                        value_classification_correct += 1
                    
                    # Check timeline category
                    if classification.get('timeline_category') == gt_classification.get('timeline_category'):
                        timeline_classification_correct += 1
                    
                    # Check decision stage
                    if classification.get('decision_stage') == gt_classification.get('decision_stage'):
                        decision_stage_correct += 1
                    
                    # Check competition level
                    if classification.get('competition_level') == gt_classification.get('competition_level'):
                        competition_level_correct += 1
                    
                    # Check win probability
                    if 'win_probability' in classification and 'win_probability' in gt_classification:
                        prob_diff = abs(
                            classification['win_probability'] - 
                            gt_classification['win_probability']
                        )
                        if prob_diff <= 0.15:  # Within 15% is acceptable
                            win_probability_close += 1
                    
                    # Check priority score
                    if 'priority_score' in classification and 'priority_score' in gt_classification:
                        score_diff = abs(
                            classification['priority_score'] - 
                            gt_classification['priority_score']
                        )
                        if score_diff <= 20:  # Within 20 points is acceptable
                            priority_score_close += 1
                
                # Log progress
                if (i + 1) % 10 == 0 or i + 1 == len(test_leads):
                    logger.info(f"Processed {i + 1}/{len(test_leads)} leads for classification testing")
                
            except Exception as e:
                logger.error(f"Error testing classification for lead {lead_id}: {str(e)}")
                error_type = type(e).__name__
                
                if error_type not in classification_errors:
                    classification_errors[error_type] = 0
                classification_errors[error_type] += 1
        
        # Calculate metrics
        test_count = len(test_leads)
        
        def calc_percentage(value, total):
            return (value / total) * 100 if total > 0 else 0
        
        # Store in metrics object
        self.metrics.value_classification_accuracy = calc_percentage(value_classification_correct, test_count)
        self.metrics.timeline_classification_accuracy = calc_percentage(timeline_classification_correct, test_count)
        self.metrics.decision_stage_accuracy = calc_percentage(decision_stage_correct, test_count)
        self.metrics.competition_level_accuracy = calc_percentage(competition_level_correct, test_count)
        self.metrics.win_probability_calibration = calc_percentage(win_probability_close, test_count)
        self.metrics.priority_score_correlation = calc_percentage(priority_score_close, test_count)
        
        self.metrics.avg_classification_time = statistics.mean(classification_times) if classification_times else 0
        self.metrics.classification_errors = classification_errors
        
        # Calculate overall classification accuracy
        self.metrics.overall_classification_accuracy = statistics.mean([
            self.metrics.value_classification_accuracy,
            self.metrics.timeline_classification_accuracy,
            self.metrics.decision_stage_accuracy,
            self.metrics.competition_level_accuracy,
            self.metrics.win_probability_calibration,
            self.metrics.priority_score_correlation
        ]) / 100  # Convert percentage to decimal
        
        logger.info("Completed classification testing")
        
        return self.metrics
    
    def test_integration(self) -> TestMetrics:
        """
        Test the integration between enrichment and classification.
        
        Returns:
            TestMetrics with integration results
        """
        logger.info("Starting integration testing")
        
        # Setup components
        enricher = self.setup_enricher()
        classifier = self.setup_classifier()
        
        # Get test leads
        test_leads = self.dataset.get_leads()
        lead_objs = [lead.to_lead_obj() for lead in test_leads]
        
        # Process a sample of leads through full pipeline
        sample_size = min(10, len(test_leads))
        sample_indices = random.sample(range(len(test_leads)), sample_size)
        
        combined_times = []
        success_count = 0
        
        for idx in sample_indices:
            test_lead = test_leads[idx]
            lead_obj = lead_objs[idx]
            lead_id = test_lead.id
            
            try:
                # Process through full pipeline
                start_time = time.time()
                
                # Step 1: Enrich the lead
                enriched_lead = enricher.enrich_lead(asdict(lead_obj))
                
                # Step 2: Convert to Lead object
                # We need to update the original lead object with enriched data
                for key, value in enriched_lead.items():
                    if key not in ['id', 'source']:  # Preserve original values
                        if key == 'extra_data':
                            for extra_key, extra_value in value.items():
                                lead_obj.extra_data[extra_key] = extra_value
                        else:
                            try:
                                setattr(lead_obj, key, value)
                            except:
                                pass  # Skip if attribute can't be set
                
                # Step 3: Classify the lead
                classified_lead = classifier.classify_lead(lead_obj)
                
                elapsed_time = time.time() - start_time
                combined_times.append(elapsed_time)
                
                # Check if both enrichment and classification succeeded
                enrichment_success = 'company' in enriched_lead or 'contacts' in enriched_lead
                classification_success = 'classification' in classified_lead.extra_data
                
                if enrichment_success and classification_success:
                    success_count += 1
                
            except Exception as e:
                logger.error(f"Error in integration test for lead {lead_id}: {str(e)}")
        
        # Record integration metrics
        self.metrics.integration_success_rate = (success_count / sample_size) * 100 if sample_size > 0 else 0
        self.metrics.avg_integration_time = statistics.mean(combined_times) if combined_times else 0
        
        logger.info("Completed integration testing")
        
        return self.metrics
    
    def test_performance(self) -> TestMetrics:
        """
        Test performance characteristics.
        
        Returns:
            TestMetrics with performance results
        """
        logger.info("Starting performance testing")
        
        # Setup components
        enricher = self.setup_enricher()
        classifier = self.setup_classifier()
        
        # Get test leads
        test_leads = self.dataset.get_leads()
        lead_objs = [lead.to_lead_obj() for lead in test_leads]
        
        # Prepare batch sizes for testing
        batch_sizes = [1, 5, 10, 25]
        max_batch = min(50, len(test_leads))
        if max_batch > 25:
            batch_sizes.append(max_batch)
        
        batch_timing = {}
        memory_usage = []
        
        # Measure baseline memory
        process = psutil.Process(os.getpid())
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Test each batch size
        for batch_size in batch_sizes:
            if batch_size > len(test_leads):
                continue
                
            batch = lead_objs[:batch_size]
            
            try:
                # Measure memory before
                mem_before = process.memory_info().rss / 1024 / 1024  # MB
                
                # Time batch enrichment
                start_time = time.time()
                enriched_leads = enricher.enrich_leads([asdict(lead) for lead in batch])
                enrich_time = time.time() - start_time
                
                # Measure memory after enrichment
                mem_after_enrich = process.memory_info().rss / 1024 / 1024  # MB
                
                # Record memory usage
                memory_usage.append({
                    "batch_size": batch_size,
                    "operation": "enrichment",
                    "memory_before": mem_before,
                    "memory_after": mem_after_enrich,
                    "memory_delta": mem_after_enrich - mem_before
                })
                
                # Record timing
                batch_timing[f"enrich_{batch_size}"] = {
                    "total_time": enrich_time,
                    "per_lead_time": enrich_time / batch_size if batch_size > 0 else 0
                }
                
                logger.info(f"Batch enrichment with size {batch_size}: {enrich_time:.3f}s total, "
                          f"{enrich_time / batch_size:.3f}s per lead")
                
            except Exception as e:
                logger.error(f"Error testing batch enrichment with size {batch_size}: {str(e)}")
        
        # Record performance metrics
        self.metrics.memory_usage_mb = statistics.mean([item["memory_delta"] for item in memory_usage])
        self.metrics.batch_timing = batch_timing
        
        logger.info("Completed performance testing")
        
        return self.metrics
    
    def run_all_tests(self) -> TestMetrics:
        """
        Run all test suites.
        
        Returns:
            TestMetrics with all results
        """
        logger.info("Starting comprehensive testing suite")
        
        # Run each test suite
        self.test_enrichment()
        self.test_classification()
        self.test_integration()
        self.test_performance()
        
        # Generate report
        self.generate_report()
        
        logger.info("Completed comprehensive testing suite")
        
        return self.metrics
    
    def generate_report(self) -> None:
        """Generate comprehensive test reports."""
        logger.info("Generating test reports")
        
        # Create report directory if it doesn't exist
        TEST_REPORT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Generate JSON report
        json_report_path = TEST_REPORT_DIR / f"enrichment_test_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_report_path, "w", encoding="utf-8") as f:
            json.dump(self.metrics.to_dict(), f, indent=2)
        
        # Generate CSV report
        csv_report_path = TEST_REPORT_DIR / f"enrichment_test_report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self._generate_csv_report(csv_report_path)
        
        # Generate visualization
        viz_path = TEST_REPORT_DIR / f"enrichment_test_viz_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        self._generate_visualization(viz_path)
        
        logger.info(f"Reports generated at {TEST_REPORT_DIR}")
    
    def _generate_csv_report(self, path: Path) -> None:
        """
        Generate CSV report of test results.
        
        Args:
            path: Path to save the CSV report
        """
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow(["Metric", "Value"])
            
            # Write enrichment metrics
            writer.writerow(["", ""])
            writer.writerow(["ENRICHMENT METRICS", ""])
            writer.writerow(["Company Data Success Rate (%)", f"{self.metrics.company_data_success_rate:.1f}"])
            writer.writerow(["Website Discovery Success Rate (%)", f"{self.metrics.website_discovery_success_rate:.1f}"])
            writer.writerow(["Contact Extraction Success Rate (%)", f"{self.metrics.contact_extraction_success_rate:.1f}"])
            writer.writerow(["Company Size Success Rate (%)", f"{self.metrics.company_size_success_rate:.1f}"])
            writer.writerow(["Project Stage Success Rate (%)", f"{self.metrics.project_stage_success_rate:.1f}"])
            writer.writerow(["Related Projects Success Rate (%)", f"{self.metrics.related_projects_success_rate:.1f}"])
            writer.writerow(["Lead Scoring Accuracy (%)", f"{self.metrics.lead_scoring_accuracy:.1f}"])
            writer.writerow(["Overall Data Completeness", f"{self.metrics.overall_data_completeness:.3f}"])
            
            # Write classification metrics
            writer.writerow(["", ""])
            writer.writerow(["CLASSIFICATION METRICS", ""])
            writer.writerow(["Value Classification Accuracy (%)", f"{self.metrics.value_classification_accuracy:.1f}"])
            writer.writerow(["Timeline Classification Accuracy (%)", f"{self.metrics.timeline_classification_accuracy:.1f}"])
            writer.writerow(["Decision Stage Accuracy (%)", f"{self.metrics.decision_stage_accuracy:.1f}"])
            writer.writerow(["Competition Level Accuracy (%)", f"{self.metrics.competition_level_accuracy:.1f}"])
            writer.writerow(["Win Probability Calibration (%)", f"{self.metrics.win_probability_calibration:.1f}"])
            writer.writerow(["Priority Score Correlation (%)", f"{self.metrics.priority_score_correlation:.1f}"])
            writer.writerow(["Overall Classification Accuracy", f"{self.metrics.overall_classification_accuracy:.3f}"])
            
            # Write performance metrics
            writer.writerow(["", ""])
            writer.writerow(["PERFORMANCE METRICS", ""])
            writer.writerow(["Average Enrichment Time (s)", f"{self.metrics.avg_enrichment_time:.3f}"])
            writer.writerow(["Average Classification Time (s)", f"{self.metrics.avg_classification_time:.3f}"])
            writer.writerow(["Memory Usage (MB)", f"{self.metrics.memory_usage_mb:.1f}"])
            
            # Write API calls
            writer.writerow(["", ""])
            writer.writerow(["API CALLS", ""])
            for api, count in self.metrics.api_calls_count.items():
                writer.writerow([api, count])
    
    def _generate_visualization(self, path: Path) -> None:
        """
        Generate visualization of test results.
        
        Args:
            path: Path to save the visualization
        """
        try:
            # Create figure with multiple subplots
            fig, axs = plt.subplots(2, 2, figsize=(12, 10))
            
            # 1. Enrichment Success Rates
            enrichment_metrics = [
                ('Company Data', self.metrics.company_data_success_rate),
                ('Website Discovery', self.metrics.website_discovery_success_rate),
                ('Contact Extraction', self.metrics.contact_extraction_success_rate),
                ('Company Size', self.metrics.company_size_success_rate),
                ('Project Stage', self.metrics.project_stage_success_rate),
                ('Related Projects', self.metrics.related_projects_success_rate),
                ('Lead Scoring', self.metrics.lead_scoring_accuracy)
            ]
            
            labels, values = zip(*enrichment_metrics)
            axs[0, 0].bar(labels, values)
            axs[0, 0].set_title('Enrichment Success Rates (%)')
            axs[0, 0].set_ylim(0, 100)
            axs[0, 0].set_xticklabels(labels, rotation=45, ha='right')
            axs[0, 0].axhline(y=80, color='r', linestyle='--', label='Target (80%)')
            axs[0, 0].legend()
            
            # 2. Classification Accuracy
            classification_metrics = [
                ('Value', self.metrics.value_classification_accuracy),
                ('Timeline', self.metrics.timeline_classification_accuracy),
                ('Decision Stage', self.metrics.decision_stage_accuracy),
                ('Competition', self.metrics.competition_level_accuracy),
                ('Win Probability', self.metrics.win_probability_calibration),
                ('Priority Score', self.metrics.priority_score_correlation)
            ]
            
            labels, values = zip(*classification_metrics)
            axs[0, 1].bar(labels, values)
            axs[0, 1].set_title('Classification Accuracy (%)')
            axs[0, 1].set_ylim(0, 100)
            axs[0, 1].set_xticklabels(labels, rotation=45, ha='right')
            axs[0, 1].axhline(y=85, color='r', linestyle='--', label='Target (85%)')
            axs[0, 1].legend()
            
            # 3. Performance Metrics
            performance_metrics = [
                ('Enrichment Time (s)', self.metrics.avg_enrichment_time),
                ('Classification Time (s)', self.metrics.avg_classification_time)
            ]
            
            labels, values = zip(*performance_metrics)
            axs[1, 0].bar(labels, values)
            axs[1, 0].set_title('Average Processing Time (seconds)')
            axs[1, 0].axhline(y=0.2, color='r', linestyle='--', label='Target (<0.2s)')
            axs[1, 0].legend()
            
            # 4. Overall Metrics
            overall_metrics = [
                ('Data Completeness', self.metrics.overall_data_completeness * 100),
                ('Classification Accuracy', self.metrics.overall_classification_accuracy * 100)
            ]
            
            labels, values = zip(*overall_metrics)
            axs[1, 1].bar(labels, values)
            axs[1, 1].set_title('Overall Quality Metrics (%)')
            axs[1, 1].set_ylim(0, 100)
            axs[1, 1].axhline(y=85, color='r', linestyle='--', label='Target (85%)')
            axs[1, 1].legend()
            
            # Adjust layout and save
            plt.tight_layout()
            plt.savefig(path)
            plt.close()
            
            logger.info(f"Visualization saved to {path}")
            
        except Exception as e:
            logger.error(f"Error generating visualization: {str(e)}")
    
    def _compare_company_data(self, enriched: Dict[str, Any], ground_truth: Dict[str, Any]) -> float:
        """
        Compare enriched company data with ground truth.
        
        Args:
            enriched: Enriched company data
            ground_truth: Ground truth company data
            
        Returns:
            Match score (0.0-1.0)
        """
        if not enriched or not ground_truth:
            return 0.0
        
        # Key fields to compare
        key_fields = ['name', 'website', 'industry', 'size']
        
        # Count matches
        matches = 0
        total_fields = 0
        
        for field in key_fields:
            if field in enriched and field in ground_truth:
                total_fields += 1
                
                if field == 'name':
                    # Name comparison - more lenient
                    if self._compare_names(enriched[field], ground_truth[field]):
                        matches += 1
                elif field == 'website':
                    # Website comparison
                    if self._normalize_url(enriched[field]) == self._normalize_url(ground_truth[field]):
                        matches += 1
                else:
                    # Other fields - exact match
                    if enriched[field] == ground_truth[field]:
                        matches += 1
        
        # Calculate match score
        return matches / total_fields if total_fields > 0 else 0.0
    
    def _compare_names(self, name1: str, name2: str) -> bool:
        """
        Compare two company names for similarity.
        
        Args:
            name1: First company name
            name2: Second company name
            
        Returns:
            True if names are similar, False otherwise
        """
        if not name1 or not name2:
            return False
        
        # Normalize names
        name1 = name1.lower().replace(',', '').replace('.', '')
        name2 = name2.lower().replace(',', '').replace('.', '')
        
        # Check for exact match
        if name1 == name2:
            return True
        
        # Check if one is contained in the other
        if name1 in name2 or name2 in name1:
            return True
        
        # Check word overlap
        words1 = set(name1.split())
        words2 = set(name2.split())
        
        # If there are common words (excluding common terms)
        common_words = words1.intersection(words2)
        common_words = {word for word in common_words 
                        if word not in {'inc', 'llc', 'corp', 'corporation', 'company', 'co', 'ltd'}}
        
        return len(common_words) > 0
    
    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL for comparison.
        
        Args:
            url: URL to normalize
            
        Returns:
            Normalized URL
        """
        if not url:
            return ""
        
        # Remove protocol, www, and trailing slash
        url = re.sub(r'^https?://', '', url)
        url = re.sub(r'^www\.', '', url)
        url = url.rstrip('/')
        
        return url.lower()
    
    def _compare_contacts(self, contacts1: List[Dict[str, Any]], contacts2: List[Dict[str, Any]]) -> float:
        """
        Compare two lists of contacts.
        
        Args:
            contacts1: First contact list
            contacts2: Second contact list
            
        Returns:
            Match score (0.0-1.0)
        """
        if not contacts1 or not contacts2:
            return 0.0
        
        # Check for presence of contacts
        if len(contacts1) == 0 or len(contacts2) == 0:
            return 0.0
        
        # Compare only up to 3 contacts
        max_contacts = min(3, min(len(contacts1), len(contacts2)))
        
        matches = 0
        
        # For each contact in first list, find best match in second list
        for i in range(max_contacts):
            if i >= len(contacts1):
                break
                
            contact1 = contacts1[i]
            best_match = 0
            
            for contact2 in contacts2:
                match_score = self._compare_contact(contact1, contact2)
                best_match = max(best_match, match_score)
            
            matches += best_match
        
        # Calculate average match score
        return matches / max_contacts
    
    def _compare_contact(self, contact1: Dict[str, Any], contact2: Dict[str, Any]) -> float:
        """
        Compare two contact dictionaries.
        
        Args:
            contact1: First contact
            contact2: Second contact
            
        Returns:
            Match score (0.0-1.0)
        """
        # Key fields to compare
        key_fields = ['name', 'title', 'email', 'phone']
        
        # Field weights
        weights = {
            'name': 0.4,
            'title': 0.2,
            'email': 0.3,
            'phone': 0.1
        }
        
        # Calculate weighted match score
        score = 0.0
        total_weight = 0.0
        
        for field in key_fields:
            if field in contact1 and field in contact2 and contact1[field] and contact2[field]:
                weight = weights.get(field, 0.0)
                total_weight += weight
                
                if field == 'name':
                    # Name comparison - more lenient
                    name_match = self._compare_names(contact1[field], contact2[field])
                    score += weight if name_match else 0.0
                elif field == 'email':
                    # Email comparison - exact match
                    if contact1[field].lower() == contact2[field].lower():
                        score += weight
                elif field == 'phone':
                    # Phone comparison - normalize and compare
                    phone1 = ''.join(c for c in contact1[field] if c.isdigit())
                    phone2 = ''.join(c for c in contact2[field] if c.isdigit())
                    if phone1 == phone2:
                        score += weight
                else:
                    # Other fields - exact match
                    if contact1[field].lower() == contact2[field].lower():
                        score += weight
        
        # Return normalized score
        return score / total_weight if total_weight > 0 else 0.0
    
    def _compare_company_size(self, size1: str, size2: str) -> bool:
        """
        Compare two company size strings.
        
        Args:
            size1: First size string
            size2: Second size string
            
        Returns:
            True if sizes match, False otherwise
        """
        if not size1 or not size2:
            return False
        
        # Normalize size strings
        size1 = size1.lower()
        size2 = size2.lower()
        
        # Check for exact match
        if size1 == size2:
            return True
        
        # Check for pattern match (e.g., "Small (10-49)" matches "Small")
        size_patterns = {
            'micro': ['micro', '1-9', 'less than 10'],
            'small': ['small', '10-49', 'less than 50'],
            'medium': ['medium', '50-249', 'less than 250'],
            'large': ['large', '250-999', 'less than 1000'],
            'enterprise': ['enterprise', '1000+', 'more than 1000']
        }
        
        # Find pattern matches for each size
        size1_category = None
        size2_category = None
        
        for category, patterns in size_patterns.items():
            if any(pattern in size1 for pattern in patterns):
                size1_category = category
            if any(pattern in size2 for pattern in patterns):
                size2_category = category
        
        # If both match the same category
        return size1_category is not None and size1_category == size2_category


def main():
    """Main function to run tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test lead enrichment and classification')
    parser.add_argument('--mock', choices=['full', 'partial', 'none'], default='partial',
                        help='Level of API mocking (default: partial)')
    parser.add_argument('--sample', type=int, default=DEFAULT_SAMPLE_SIZE,
                        help=f'Number of test leads to use (default: {DEFAULT_SAMPLE_SIZE})')
    parser.add_argument('--test', choices=['all', 'enrichment', 'classification', 'integration', 'performance'],
                        default='all', help='Test suite to run (default: all)')
    parser.add_argument('--report', action='store_true',
                        help='Generate test reports')
    parser.add_argument('--verbose', action='store_true',
                        help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize tester
    tester = LeadEnrichmentTester(mock_level=args.mock, sample_size=args.sample)
    
    # Run tests
    if args.test == 'all':
        tester.run_all_tests()
    elif args.test == 'enrichment':
        tester.test_enrichment()
    elif args.test == 'classification':
        tester.test_classification()
    elif args.test == 'integration':
        tester.test_integration()
    elif args.test == 'performance':
        tester.test_performance()
    
    # Generate report if requested
    if args.report:
        tester.generate_report()
    
    # Print summary
    print("\nTest Results Summary:")
    print(f"Enrichment Data Completeness: {tester.metrics.overall_data_completeness:.2%}")
    print(f"Classification Accuracy: {tester.metrics.overall_classification_accuracy:.2%}")
    print(f"Average Enrichment Time: {tester.metrics.avg_enrichment_time:.3f} seconds")
    print(f"Average Classification Time: {tester.metrics.avg_classification_time:.3f} seconds")
    print(f"Memory Usage: {tester.metrics.memory_usage_mb:.1f} MB")


if __name__ == "__main__":
    main()
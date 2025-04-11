#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generate Sample Leads

This script generates a set of sample leads for testing the Perera Construction
Lead Scraper dashboard and other components.
"""

import os
import sys
import uuid
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

# Add the project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.perera_lead_scraper.models.lead import Lead, MarketSector, LeadStatus, Location, Contact
from src.perera_lead_scraper.utils.storage import LocalStorage

def generate_sample_leads(count: int = 20) -> List[Lead]:
    """
    Generate a list of sample leads for testing.
    
    Args:
        count: Number of leads to generate
        
    Returns:
        List of sample Lead objects
    """
    leads = []
    
    # Sample data for generation
    project_types = {
        "healthcare": ["Hospital", "Medical Center", "Clinic", "Healthcare Facility"],
        "education": ["University Building", "School", "Campus Center", "Education Center"],
        "commercial": ["Office Tower", "Corporate Campus", "Retail Development", "Mixed-Use Building"],
        "energy": ["Solar Farm", "Wind Farm", "Energy Center", "Power Plant"],
        "entertainment": ["Stadium", "Theater", "Museum", "Entertainment Complex"]
    }
    
    cities = [
        ("Los Angeles", "CA"), 
        ("San Diego", "CA"), 
        ("Riverside", "CA"), 
        ("San Francisco", "CA"),
        ("Long Beach", "CA"), 
        ("Santa Monica", "CA"), 
        ("Orange County", "CA"), 
        ("San Bernardino", "CA"),
        ("Ventura", "CA"), 
        ("Santa Barbara", "CA"),
        ("Oakland", "CA")
    ]
    
    companies = [
        "Healthcare Builders Inc",
        "Education Constructors",
        "Commercial Development Group",
        "Energy Construction Services",
        "Entertainment Venues Builders",
        "Pacific Contractors",
        "West Coast Development",
        "Southern California Construction",
        "Metro Builders",
        "Regional Development Corporation"
    ]
    
    for i in range(count):
        # Select random sector
        sector_name = random.choice(list(project_types.keys()))
        sector = MarketSector(sector_name)
        project_type = random.choice(project_types[sector_name])
        
        # Select random city
        city, state = random.choice(cities)
        
        # Select random company
        company_name = random.choice(companies)
        
        # Generate value based on sector and project type
        if sector_name == "healthcare" or sector_name == "energy":
            value_base = random.randint(5, 10) * 10000000  # $50M - $100M
        elif sector_name == "commercial" or sector_name == "entertainment":
            value_base = random.randint(2, 8) * 10000000  # $20M - $80M
        else:  # education
            value_base = random.randint(1, 5) * 10000000  # $10M - $50M
            
        # Add some randomization
        value = value_base + random.randint(-1000000, 1000000)
        
        # Project description parts
        description_parts = [
            f"Construction of a new {project_type} in {city}, {state}.",
            f"The project involves approximately {random.randint(10000, 200000)} square feet of space.",
            f"Estimated completion date is Q{random.randint(1, 4)} {random.randint(2025, 2028)}.",
            f"This development is part of a larger {random.choice(['expansion', 'revitalization', 'growth'])} initiative."
        ]
        
        # Use varying number of description parts
        desc_count = random.randint(2, len(description_parts))
        description = " ".join(description_parts[:desc_count])
        
        # Generate random dates within the last 30 days
        days_ago = random.randint(1, 30)
        retrieved_date = datetime.now() - timedelta(days=days_ago)
        
        # Create location object
        location = Location(
            address=f"{random.randint(100, 9999)} Main St",
            city=city,
            state=state,
            zip_code=f"9{random.randint(1000, 9999)}"
        )
        
        # Create contacts (for some leads)
        contacts = []
        if random.random() > 0.3:  # 70% of leads have contacts
            first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "Robert", "Lisa"]
            last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
            titles = ["Project Manager", "CEO", "Director", "VP of Construction", "Site Manager", "Architect"]
            
            contact_count = random.randint(1, 3)
            for _ in range(contact_count):
                first_name = random.choice(first_names)
                last_name = random.choice(last_names)
                contacts.append(Contact(
                    name=f"{first_name} {last_name}",
                    email=f"{first_name.lower()}.{last_name.lower()}@{company_name.lower().replace(' ', '')}.com",
                    phone=f"(555) {random.randint(100, 999)}-{random.randint(1000, 9999)}",
                    title=random.choice(titles)
                ))
        
        # Create metadata (for some leads)
        metadata = {
            "company": {
                "name": company_name,
                "size": random.choice(["Small", "Medium", "Large"]),
                "website": f"https://{company_name.lower().replace(' ', '')}.com"
            }
        }
        
        # Assign a status
        status_weights = {
            LeadStatus.NEW: 0.4,
            LeadStatus.QUALIFIED: 0.3,
            LeadStatus.ENRICHED: 0.2,
            LeadStatus.CONTACTED: 0.1
        }
        
        statuses, weights = zip(*status_weights.items())
        status = random.choices(statuses, weights=weights)[0]
        
        # Create lead object with the correct parameters based on the Lead class definition
        lead = Lead(
            id=str(uuid.uuid4()),
            title=f"{city} {project_type}",
            project_name=f"{city} {project_type}",
            description=description,
            source=f"sample_data_{sector_name}",
            source_url=f"https://example.com/projects/{i+1}",
            market_sector=sector,
            estimated_value=value,
            confidence_score=round(random.uniform(0.5, 0.95), 2),
            location=location,
            retrieved_date=retrieved_date,
            contacts=contacts,
            metadata=metadata,
            status=status
        )
        
        leads.append(lead)
    
    return leads


def main():
    """Main entry point for the script."""
    print("Generating sample leads for testing...")
    
    # Generate sample leads
    leads = generate_sample_leads(30)
    print(f"Generated {len(leads)} sample leads")
    
    # Store leads in the database
    storage = LocalStorage()
    for lead in leads:
        storage.save_lead(lead)
    
    print(f"Saved {len(leads)} leads to storage")
    print("Sample leads are ready for testing the dashboard")


if __name__ == "__main__":
    main()
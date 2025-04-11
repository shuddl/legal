#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Base Scraper - Abstract base class for all scrapers.
"""

import abc
import logging
import json
import os
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from pathlib import Path

from src.perera_lead_scraper.models.lead import Lead, MarketSector, LeadStatus, Location
from src.perera_lead_scraper.config import config

logger = logging.getLogger(__name__)

class BaseScraper(abc.ABC):
    """
    Abstract base class for all scrapers.
    
    All scraper implementations must inherit from this class.
    """
    
    def __init__(self, source_id: str, source_config: Dict[str, Any]):
        """
        Initialize the base scraper.
        
        Args:
            source_id: ID of the source
            source_config: Configuration dictionary for the source
        """
        self.source_id = source_id
        self.source_config = source_config
        self.source_name = source_config.get('name', source_id)
        self.scrape_frequency_hours = float(source_config.get('scrape_frequency_hours', 24.0))
        self.last_scrape_time: Optional[datetime] = None
        self.status: str = "initialized"
        self.error: Optional[str] = None
        self.leads: List[Lead] = []
        
        # Load configuration data
        self._load_configuration()
        
        self.metrics: Dict[str, Any] = {
            "total_leads_found": 0,
            "total_scrape_time_seconds": 0,
            "average_scrape_time_seconds": 0,
            "scrape_count": 0,
            "qualified_leads": 0,
            "rejected_leads": 0
        }
        
        logger.info(f"Initialized {self.__class__.__name__} for source: {self.source_name} (ID: {source_id})")
    
    def _load_configuration(self) -> None:
        """Load configuration data for filtering and validation."""
        # Load target locations
        self.target_locations = self._load_target_locations()
        
        # Load keywords for filtering
        self.keywords = self._load_keywords()
        
        # Early stage indicators
        self.early_stage_keywords = self._get_early_stage_keywords()
    
    def _load_target_locations(self) -> Dict[str, Set[str]]:
        """Load target locations from configuration."""
        target_locations = {"state": set(), "county": set(), "city": set()}
        
        try:
            locations_path = config.TARGET_LOCATIONS_PATH
            if os.path.exists(locations_path):
                with open(locations_path, 'r', encoding='utf-8') as f:
                    locations_data = json.load(f)
                
                # Convert to sets for faster lookups
                if "states" in locations_data:
                    target_locations["state"] = set(locations_data["states"])
                
                if "counties" in locations_data:
                    target_locations["county"] = set(locations_data["counties"])
                
                if "cities" in locations_data:
                    target_locations["city"] = set(locations_data["cities"])
                    
                logger.info(f"Loaded {len(target_locations['city'])} target cities, {len(target_locations['county'])} counties, and {len(target_locations['state'])} states")
        except Exception as e:
            logger.warning(f"Error loading target locations: {str(e)}")
        
        return target_locations
    
    def _load_keywords(self) -> Dict[str, List[str]]:
        """Load keywords for different market sectors."""
        keywords = {}
        
        try:
            keywords_path = config.KEYWORDS_PATH
            if os.path.exists(keywords_path):
                with open(keywords_path, 'r', encoding='utf-8') as f:
                    keywords = json.load(f)
                logger.info(f"Loaded keywords for {len(keywords)} categories")
        except Exception as e:
            logger.warning(f"Error loading keywords: {str(e)}")
        
        return keywords
    
    def _get_early_stage_keywords(self) -> List[str]:
        """Get keywords that indicate a project is in early stages."""
        # These keywords match the requirements in the project overview
        return [
            "planning", "design review", "entitlement", "permit application", 
            "seeking bids", "approved funding", "future development",
            "proposed", "under consideration", "preliminary", "concept",
            "early stage", "feasibility study", "seeking approval", "pre-construction",
            "in design", "upcoming project", "future project", "planned development",
            "zoning approval", "master plan", "initial phase", "evaluation phase"
        ]
    
    @abc.abstractmethod
    def scrape(self, limit: Optional[int] = None) -> List[Lead]:
        """
        Scrape the source for leads.
        
        This method must be implemented by all subclasses.
        
        Args:
            limit: Optional maximum number of leads to retrieve (for testing)
            
        Returns:
            List[Lead]: List of leads found
        """
        pass
    
    def execute(self, limit: Optional[int] = None) -> Optional[List[Lead]]:
        """
        Execute the scraper with timing and error handling.
        
        Args:
            limit: Optional maximum number of leads to retrieve (for testing)
        
        Returns:
            Optional[List[Lead]]: List of leads if successful, None if failed
        """
        logger.info(f"Executing {self.__class__.__name__} for source: {self.source_name}")
        
        # Check if it's time to scrape
        if self._should_wait():
            logger.info(f"Skipping scrape for {self.source_name}, not time yet")
            return self.leads
        
        start_time = datetime.now()
        self.status = "running"
        self.error = None
        
        try:
            # Execute the actual scraping
            raw_leads = self.scrape(limit)
            
            # Filter and validate leads
            self.leads = self._filter_and_validate_leads(raw_leads)
            
            # Update metrics
            end_time = datetime.now()
            scrape_time = (end_time - start_time).total_seconds()
            
            self.metrics["total_leads_found"] += len(raw_leads)
            self.metrics["qualified_leads"] += len(self.leads)
            self.metrics["rejected_leads"] += len(raw_leads) - len(self.leads)
            self.metrics["total_scrape_time_seconds"] += scrape_time
            self.metrics["scrape_count"] += 1
            self.metrics["average_scrape_time_seconds"] = (
                self.metrics["total_scrape_time_seconds"] / self.metrics["scrape_count"]
            )
            self.metrics["last_scrape_time"] = start_time.isoformat()
            self.metrics["last_lead_count"] = len(self.leads)
            self.metrics["conversion_rate"] = (
                self.metrics["qualified_leads"] / self.metrics["total_leads_found"]
                if self.metrics["total_leads_found"] > 0 else 0
            )
            
            self.last_scrape_time = start_time
            self.status = "completed"
            
            logger.info(f"Successfully scraped {len(raw_leads)} leads from {self.source_name}, qualified {len(self.leads)} leads in {scrape_time:.2f}s")
            return self.leads
            
        except Exception as e:
            # Update status on failure
            end_time = datetime.now()
            scrape_time = (end_time - start_time).total_seconds()
            
            self.error = str(e)
            self.status = "failed"
            self.metrics["last_error"] = self.error
            self.metrics["last_error_time"] = end_time.isoformat()
            self.metrics["total_failures"] = self.metrics.get("total_failures", 0) + 1
            
            logger.exception(f"Error scraping {self.source_name}: {str(e)}")
            return None
    
    def _filter_and_validate_leads(self, leads: List[Lead]) -> List[Lead]:
        """
        Filter and validate leads based on project requirements.
        
        Args:
            leads: List of raw leads to filter
            
        Returns:
            List[Lead]: Filtered, valid leads
        """
        filtered_leads = []
        
        for lead in leads:
            # Ensure all leads have the source set
            if not lead.source:
                lead.source = self.source_name
                
            # Ensure all leads have a source_id set
            if not lead.source_id:
                lead.source_id = self.source_id
            
            # Perform validation and filtering
            if self._validate_lead(lead):
                # Pre-compute confidence score based on available data
                lead.confidence_score = self._calculate_confidence_score(lead)
                
                # Set initial status
                lead.status = LeadStatus.NEW
                
                # Append to filtered leads
                filtered_leads.append(lead)
                
        return filtered_leads
    
    def _validate_lead(self, lead: Lead) -> bool:
        """
        Validate if a lead meets the requirements.
        
        Args:
            lead: Lead to validate
            
        Returns:
            bool: True if the lead is valid, False otherwise
        """
        # Must have a title/project name
        if not lead.project_name:
            logger.debug(f"Rejecting lead: Missing project name")
            return False
        
        # Must have a description or some content
        if not lead.description:
            logger.debug(f"Rejecting lead: Missing description for '{lead.project_name}'")
            return False
        
        # Must have a source URL
        if not lead.source_url:
            logger.debug(f"Rejecting lead: Missing source URL for '{lead.project_name}'")
            return False
        
        # Check timeliness (if publication date is available)
        if lead.publication_date:
            max_age_days = self.source_config.get('max_age_days', 14)
            if (datetime.now() - lead.publication_date).days > max_age_days:
                logger.debug(f"Rejecting lead: Too old ({lead.publication_date}) for '{lead.project_name}'")
                return False
        
        # Check location if available
        if lead.location and self.target_locations:
            if not self._is_location_in_target_area(lead.location):
                logger.debug(f"Rejecting lead: Location {lead.location} not in target area for '{lead.project_name}'")
                return False
        
        return True
    
    def _is_location_in_target_area(self, location: Location) -> bool:
        """
        Check if a location is within the target area.
        
        Args:
            location: Location to check
            
        Returns:
            bool: True if within target area, False otherwise
        """
        # If no target locations specified, accept all
        if not self.target_locations:
            return True
            
        # Check city
        if location.city and location.city.lower() in {city.lower() for city in self.target_locations["city"]}:
            return True
            
        # Check state
        if location.state and location.state.lower() in {state.lower() for state in self.target_locations["state"]}:
            return True
            
        # Check county (if available)
        if hasattr(location, 'county') and location.county and location.county.lower() in {county.lower() for county in self.target_locations["county"]}:
            return True
            
        # If we have target locations but none match, reject
        if self.target_locations["city"] or self.target_locations["state"] or self.target_locations["county"]:
            return False
            
        # Default accept if no specific locations were checked
        return True
    
    def _calculate_confidence_score(self, lead: Lead) -> float:
        """
        Calculate a confidence score for the lead based on available data.
        
        Args:
            lead: Lead to score
            
        Returns:
            float: Confidence score between 0 and 1
        """
        score = 0.5  # Start at middle
        points = 0
        
        # Award points for having good data
        if lead.project_name and len(lead.project_name) > 5:
            score += 0.05
            points += 1
            
        if lead.description and len(lead.description) > 100:
            score += 0.1
            points += 1
        
        if lead.location and lead.location.city:
            score += 0.1
            points += 1
            # Extra points if it's in our target area
            if self._is_location_in_target_area(lead.location):
                score += 0.1
                points += 1
        
        if lead.estimated_value and lead.estimated_value > 0:
            score += 0.1
            points += 1
        
        # Check for early stage keywords in description
        if lead.description:
            desc_lower = lead.description.lower()
            early_stage_matches = sum(1 for keyword in self.early_stage_keywords if keyword.lower() in desc_lower)
            if early_stage_matches > 0:
                score += min(0.15, early_stage_matches * 0.03)  # Up to 0.15 for early stage indicators
                points += 1
        
        # Check if it matches our target market sectors based on keywords
        market_sector_score = self._estimate_market_sector(lead)
        if market_sector_score[1] > 0.6:  # If confidence in sector is high
            lead.market_sector = market_sector_score[0]  # Set the market sector
            score += 0.15
            points += 1
        
        # Normalize based on points awarded
        if points > 0:
            score = min(0.98, score)  # Cap at 0.98 to leave room for NLP improvements
        
        return score
    
    def _estimate_market_sector(self, lead: Lead) -> Tuple[MarketSector, float]:
        """
        Estimate the market sector of a lead based on keywords.
        
        Args:
            lead: Lead to analyze
            
        Returns:
            Tuple[MarketSector, float]: Market sector and confidence score
        """
        if not lead.description:
            return (MarketSector.GENERAL_COMMERCIAL, 0.0)
            
        desc_lower = lead.description.lower()
        title_lower = lead.project_name.lower() if lead.project_name else ""
        
        sector_scores = {
            MarketSector.HEALTHCARE: 0,
            MarketSector.HIGHER_EDUCATION: 0,
            MarketSector.ENERGY_UTILITIES: 0,
            MarketSector.THEMED_ENTERTAINMENT: 0,
            MarketSector.GENERAL_COMMERCIAL: 0
        }
        
        # Check keywords for each sector
        if "healthcare" in self.keywords:
            healthcare_matches = sum(1 for keyword in self.keywords["healthcare"] 
                                    if keyword.lower() in desc_lower or keyword.lower() in title_lower)
            sector_scores[MarketSector.HEALTHCARE] = healthcare_matches * 0.2
            
        if "education" in self.keywords:
            education_matches = sum(1 for keyword in self.keywords["education"] 
                                   if keyword.lower() in desc_lower or keyword.lower() in title_lower)
            sector_scores[MarketSector.HIGHER_EDUCATION] = education_matches * 0.2
            
        if "energy" in self.keywords:
            energy_matches = sum(1 for keyword in self.keywords["energy"] 
                                if keyword.lower() in desc_lower or keyword.lower() in title_lower)
            sector_scores[MarketSector.ENERGY_UTILITIES] = energy_matches * 0.2
            
        if "entertainment" in self.keywords:
            entertainment_matches = sum(1 for keyword in self.keywords["entertainment"] 
                                       if keyword.lower() in desc_lower or keyword.lower() in title_lower)
            sector_scores[MarketSector.THEMED_ENTERTAINMENT] = entertainment_matches * 0.2
            
        if "commercial" in self.keywords:
            commercial_matches = sum(1 for keyword in self.keywords["commercial"] 
                                    if keyword.lower() in desc_lower or keyword.lower() in title_lower)
            sector_scores[MarketSector.GENERAL_COMMERCIAL] = commercial_matches * 0.2
        
        # Get the sector with highest score
        best_sector = max(sector_scores.items(), key=lambda x: x[1])
        
        if best_sector[1] > 0:
            return (best_sector[0], min(best_sector[1], 1.0))
        else:
            # Default to general commercial with low confidence
            return (MarketSector.GENERAL_COMMERCIAL, 0.3)
    
    def _should_wait(self) -> bool:
        """
        Check if we should wait before scraping again.
        
        Returns:
            bool: True if we should wait, False if we should scrape
        """
        if self.last_scrape_time is None:
            return False
        
        next_scrape_time = self.last_scrape_time + timedelta(hours=self.scrape_frequency_hours)
        return datetime.now() < next_scrape_time
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the status of the scraper.
        
        Returns:
            Dict[str, Any]: Status information
        """
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "status": self.status,
            "last_scrape": self.last_scrape_time.isoformat() if self.last_scrape_time else None,
            "metrics": self.metrics,
            "error": self.error,
            "lead_count": len(self.leads),
            "config": {
                "frequency_hours": self.scrape_frequency_hours,
                "enabled": self.source_config.get("enabled", True)
            }
        }
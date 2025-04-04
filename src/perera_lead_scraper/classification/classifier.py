#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lead Classification Module

This module provides comprehensive classification capabilities for construction leads,
enabling categorization by value, timeline, decision stage, competition level,
win probability, and overall priority. It integrates with NLP processing and
enrichment to deliver accurate, sector-specific classifications.
"""

import os
import re
import json
import time
import logging
import datetime
from enum import Enum
from typing import Dict, List, Set, Tuple, Optional, Any, Pattern, Union, Callable
from pathlib import Path
import statistics
from functools import lru_cache

# Local imports
from perera_lead_scraper.config import config
from perera_lead_scraper.models.lead import Lead, MarketSector, LeadType
from perera_lead_scraper.nlp.nlp_processor import NLPProcessor
from perera_lead_scraper.utils.timeout import timeout_handler

# Configure logger
logger = logging.getLogger(__name__)

# Constants
CONFIG_DIR = Path(config.CONFIG_DIR)
CLASSIFICATION_CONFIG_FILE = CONFIG_DIR / "classification_config.json"
CONFIDENCE_THRESHOLD = 0.65  # Minimum confidence for reliable classification


class ValueCategory(str, Enum):
    """
    Enumeration of project value categories.
    
    Categorizes construction leads based on estimated project value.
    """
    SMALL = "small"           # <$2M
    MEDIUM = "medium"         # $2M-$10M
    LARGE = "large"           # $10M-$50M
    MAJOR = "major"           # >$50M
    UNKNOWN = "unknown"       # Value cannot be determined


class TimelineCategory(str, Enum):
    """
    Enumeration of project timeline categories.
    
    Categorizes timeline from immediate (0-3 months) to long-term (12+ months).
    """
    IMMEDIATE = "immediate"   # 0-3 months
    SHORT_TERM = "short_term" # 3-6 months
    MID_TERM = "mid_term"     # 6-12 months
    LONG_TERM = "long_term"   # 12+ months
    UNKNOWN = "unknown"       # Timeline cannot be determined


class DecisionStage(str, Enum):
    """
    Enumeration of project decision stages.
    
    Tracks where a project is in the decision-making process.
    """
    CONCEPTUAL = "conceptual"       # Initial concept/vision stage
    PLANNING = "planning"           # Active planning/design
    APPROVAL = "approval"           # Seeking approvals/permits
    FUNDING = "funding"             # Securing funding/budget
    IMPLEMENTATION = "implementation" # Ready for implementation/construction
    UNKNOWN = "unknown"             # Stage cannot be determined


class CompetitionLevel(str, Enum):
    """
    Enumeration of competition levels for a project.
    
    Indicates the level of competition expected for a project.
    """
    LOW = "low"               # Few competitors, niche project
    MEDIUM = "medium"         # Standard competitive field
    HIGH = "high"             # Highly competitive project
    UNKNOWN = "unknown"       # Competition level cannot be determined


class PriorityLevel(str, Enum):
    """
    Enumeration of priority levels for leads.
    
    Used for lead routing and handling prioritization.
    """
    CRITICAL = "critical"     # Highest priority, immediate action needed
    HIGH = "high"             # High priority, prompt action needed
    MEDIUM = "medium"         # Standard priority
    LOW = "low"               # Lower priority, handle when convenient
    MINIMAL = "minimal"       # Minimal priority, may be deprioritized


class ClassificationError(Exception):
    """Base exception for classification-related errors."""
    pass


class LeadClassifier:
    """
    Comprehensive lead classification system.
    
    This class provides methods to classify construction leads based on multiple
    factors including project value, timeline, decision stage, competition level,
    win probability, and overall priority. It integrates with NLP processing and
    applies sector-specific rules for accurate classification.
    """
    
    def __init__(self, 
                 nlp_processor: Optional[NLPProcessor] = None,
                 config_override: Optional[Dict[str, Any]] = None):
        """
        Initialize the lead classifier.
        
        Args:
            nlp_processor: Optional NLPProcessor instance for text analysis.
                           If not provided, a new instance will be created.
            config_override: Optional configuration overrides.
        """
        self.nlp_processor = nlp_processor or NLPProcessor()
        
        # Load configuration
        self.config = self._load_configuration(config_override)
        
        # Initialize classification models/rules
        self._initialize_classification_models()
        
        # Track performance metrics
        self.performance_metrics = {
            "total_classifications": 0,
            "classification_times": [],
            "confidence_scores": {},
            "success_rate": 1.0
        }
        
        logger.info("Lead classifier initialized")
    
    def _load_configuration(self, config_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Load classification configuration.
        
        Args:
            config_override: Optional configuration overrides.
            
        Returns:
            Dict containing configuration settings.
        """
        # Default configuration
        default_config = {
            "value_tiers": {
                "default": {
                    "small": 2000000,         # $2M
                    "medium": 10000000,       # $10M
                    "large": 50000000         # $50M
                },
                "healthcare": {
                    "small": 5000000,         # $5M
                    "medium": 20000000,       # $20M
                    "large": 100000000        # $100M
                },
                "education": {
                    "small": 5000000,         # $5M
                    "medium": 25000000,       # $25M
                    "large": 75000000         # $75M
                },
                "energy": {
                    "small": 10000000,        # $10M
                    "medium": 50000000,       # $50M
                    "large": 200000000        # $200M
                },
                "entertainment": {
                    "small": 5000000,         # $5M
                    "medium": 25000000,       # $25M
                    "large": 100000000        # $100M
                },
                "commercial": {
                    "small": 2000000,         # $2M
                    "medium": 10000000,       # $10M
                    "large": 50000000         # $50M
                }
            },
            "timeline_indicators": {
                "immediate": [
                    "immediate", "urgent", "emergency", "asap", "right away",
                    "this month", "next month", "within 30 days", "within 60 days",
                    "within 90 days", "q1", "q2", "breaking ground", "construction imminent"
                ],
                "short_term": [
                    "short-term", "soon", "this quarter", "next quarter",
                    "within 6 months", "3-6 months", "coming months", 
                    "summer", "fall", "winter", "spring"  # Current or next season
                ],
                "mid_term": [
                    "mid-term", "mid term", "medium-term", "medium term", 
                    "6-12 months", "within a year", "later this year", "next year",
                    "q3", "q4", "fiscal year"
                ],
                "long_term": [
                    "long-term", "long term", "future", "years", "multi-year",
                    "next fiscal year", "beyond a year", "planning stage",
                    "master plan", "long-range", "vision", "roadmap"
                ]
            },
            "decision_stage_indicators": {
                "conceptual": [
                    "concept", "vision", "idea", "proposed", "preliminary",
                    "exploring", "feasibility study", "initial planning",
                    "considering", "evaluating", "assessing", "potential project"
                ],
                "planning": [
                    "planning", "design", "designing", "architect", "engineering",
                    "drawings", "blueprint", "schematics", "program development",
                    "requirements gathering", "site selection", "development plan"
                ],
                "approval": [
                    "approval", "permit", "permitting", "zoning", "variance",
                    "environmental review", "public hearing", "commission review",
                    "board approval", "council approval", "regulatory", "compliance"
                ],
                "funding": [
                    "funding", "budget", "financing", "investment", "investors",
                    "capital", "appropriation", "bonds", "levy", "fundraising",
                    "grant", "allocation", "financial close", "committed funds"
                ],
                "implementation": [
                    "implementation", "execution", "construction", "building",
                    "groundbreaking", "breaking ground", "site work", "contractor",
                    "bid", "procurement", "rfp", "request for proposal", "tender"
                ]
            },
            "competition_indicators": {
                "low": [
                    "sole source", "specialized", "unique", "proprietary", "niche",
                    "limited competition", "selective", "invited", "negotiated",
                    "exclusive", "preferred provider", "prequalified", "targeted"
                ],
                "medium": [
                    "competitive", "multiple bidders", "several companies",
                    "qualified bidders", "short list", "selected firms",
                    "local contractors", "regional competition"
                ],
                "high": [
                    "highly competitive", "many bidders", "open bid", "public tender",
                    "open rfp", "national competition", "advertised", "widespread interest",
                    "numerous", "low barriers", "open to all"
                ]
            },
            "win_probability_factors": {
                "market_sector_fit": 0.20,
                "geographical_proximity": 0.15,
                "project_size_fit": 0.15,
                "competition_level": 0.20,
                "relationship_strength": 0.15,
                "timeline_alignment": 0.15
            },
            "priority_scoring": {
                "value_weight": 0.30,
                "timeline_weight": 0.25,
                "win_probability_weight": 0.30,
                "strategic_alignment_weight": 0.15
            },
            "sector_expertise_levels": {
                "healthcare": 0.9,
                "education": 0.85,
                "energy": 0.75,
                "commercial": 0.80,
                "entertainment": 0.75,
                "residential": 0.60,
                "government": 0.70,
                "industrial": 0.65,
                "utilities": 0.70,
                "other": 0.50
            },
            "strategic_locations": [
                "Los Angeles", "Orange County", "San Diego", "Riverside",
                "San Bernardino", "Ventura", "Santa Barbara", "Imperial"
            ],
            "primary_client_list": [
                # Example clients would be populated here
                # This would be a list of major existing clients
            ],
            "model_version": "1.0.0"
        }
        
        # Try to load from configuration file
        try:
            if CLASSIFICATION_CONFIG_FILE.exists():
                with open(CLASSIFICATION_CONFIG_FILE, "r", encoding="utf-8") as f:
                    file_config = json.load(f)
                    # Update default configuration with file configuration
                    self._deep_update(default_config, file_config)
                    logger.info(f"Loaded classification configuration from {CLASSIFICATION_CONFIG_FILE}")
        except Exception as e:
            logger.warning(f"Failed to load classification configuration file: {e}")
        
        # Apply any overrides
        if config_override:
            self._deep_update(default_config, config_override)
        
        # Apply environment variable overrides
        self._apply_env_overrides(default_config)
        
        return default_config
    
    def _deep_update(self, d: Dict[str, Any], u: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively update a dictionary with another dictionary.
        
        Args:
            d: Base dictionary to update
            u: Dictionary with updates
            
        Returns:
            Updated dictionary
        """
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                self._deep_update(d[k], v)
            else:
                d[k] = v
        return d
    
    def _apply_env_overrides(self, config_dict: Dict[str, Any]) -> None:
        """
        Apply environment variable overrides to configuration.
        
        This allows for runtime configuration via environment variables.
        
        Args:
            config_dict: Configuration dictionary to update
        """
        # Check for model version override
        model_version_env = os.environ.get("PERERA_CLASSIFICATION_MODEL_VERSION")
        if model_version_env:
            config_dict["model_version"] = model_version_env
            logger.info(f"Applied model version override from environment: {model_version_env}")
        
        # Check for value tier overrides
        for sector in config_dict["value_tiers"]:
            env_prefix = f"PERERA_VALUE_TIER_{sector.upper()}"
            for tier in ["small", "medium", "large"]:
                env_var = f"{env_prefix}_{tier.upper()}"
                if env_var in os.environ:
                    try:
                        value = float(os.environ[env_var])
                        config_dict["value_tiers"][sector][tier] = value
                        logger.info(f"Applied value tier override from environment: {env_var}={value}")
                    except ValueError:
                        logger.warning(f"Invalid value for environment variable {env_var}: {os.environ[env_var]}")
        
        # Check for win probability factor overrides
        for factor in config_dict["win_probability_factors"]:
            env_var = f"PERERA_WIN_PROB_{factor.upper()}"
            if env_var in os.environ:
                try:
                    value = float(os.environ[env_var])
                    if 0 <= value <= 1:
                        config_dict["win_probability_factors"][factor] = value
                        logger.info(f"Applied win probability factor override from environment: {env_var}={value}")
                    else:
                        logger.warning(f"Win probability factor must be between 0 and 1: {env_var}={value}")
                except ValueError:
                    logger.warning(f"Invalid value for environment variable {env_var}: {os.environ[env_var]}")
    
    def _initialize_classification_models(self) -> None:
        """
        Initialize models and patterns for classification.
        
        This includes preparing keyword patterns, compiling regular expressions,
        and setting up any machine learning models for classification tasks.
        """
        # Compile regex patterns for matching indicators
        self.timeline_patterns = self._compile_indicator_patterns(self.config["timeline_indicators"])
        self.decision_stage_patterns = self._compile_indicator_patterns(self.config["decision_stage_indicators"])
        self.competition_patterns = self._compile_indicator_patterns(self.config["competition_indicators"])
        
        # Pre-process indicator keywords for NLP matching
        self.timeline_keywords = self._flatten_indicators(self.config["timeline_indicators"])
        self.decision_stage_keywords = self._flatten_indicators(self.config["decision_stage_indicators"])
        self.competition_keywords = self._flatten_indicators(self.config["competition_indicators"])
        
        # Initialize any ML models here (placeholder for future extension)
        # self.value_prediction_model = self._load_value_prediction_model()
        # self.win_probability_model = self._load_win_probability_model()
        
        logger.debug("Classification models initialized")
    
    def _compile_indicator_patterns(self, indicator_dict: Dict[str, List[str]]) -> Dict[str, List[Pattern]]:
        """
        Compile regex patterns for indicator keywords.
        
        Args:
            indicator_dict: Dictionary of category -> list of indicator keywords
            
        Returns:
            Dictionary of category -> list of compiled regex patterns
        """
        pattern_dict = {}
        
        for category, indicators in indicator_dict.items():
            patterns = []
            for indicator in indicators:
                # Create word boundary-aware pattern
                pattern = re.compile(r'\b' + re.escape(indicator) + r'\b', re.IGNORECASE)
                patterns.append(pattern)
            pattern_dict[category] = patterns
        
        return pattern_dict
    
    def _flatten_indicators(self, indicator_dict: Dict[str, List[str]]) -> Dict[str, Set[str]]:
        """
        Flatten indicator keywords for easier matching.
        
        Args:
            indicator_dict: Dictionary of category -> list of indicator keywords
            
        Returns:
            Dictionary of category -> set of lowercase keywords
        """
        flattened = {}
        
        for category, indicators in indicator_dict.items():
            flattened[category] = set(ind.lower() for ind in indicators)
        
        return flattened
    
    @timeout_handler(timeout_sec=5)
    def classify_lead(self, lead: Lead) -> Lead:
        """
        Apply all classification operations to a lead.
        
        This method orchestrates the full classification process, applying
        all classification categories and calculations to the lead. It updates
        the lead with classification results and returns the updated lead.
        
        Args:
            lead: Lead object to classify
            
        Returns:
            Updated lead with classification data
            
        Raises:
            ClassificationError: If classification fails
        """
        start_time = time.time()
        
        try:
            # Ensure lead has required fields for classification
            if not lead.project_name and not lead.description:
                raise ClassificationError("Lead lacks sufficient text for classification")
            
            # Initialize classification data if not present
            if "classification" not in lead.extra_data:
                lead.extra_data["classification"] = {}
            
            classification = lead.extra_data["classification"]
            
            # Prepare combined text for analysis
            text = f"{lead.project_name} {lead.description or ''}"
            
            # Record classification metadata
            classification["model_version"] = self.config["model_version"]
            classification["classified_at"] = datetime.datetime.now().isoformat()
            
            # Apply each classification
            if lead.estimated_value is not None:
                value_category, value_confidence = self.categorize_by_value(
                    lead.estimated_value, 
                    lead.market_sector.value if lead.market_sector else None
                )
                classification["value_category"] = value_category
                classification["value_confidence"] = value_confidence
            else:
                classification["value_category"] = ValueCategory.UNKNOWN
                classification["value_confidence"] = 0.0
            
            timeline_category, timeline_confidence, timeline_indicators = self.categorize_by_timeline(text)
            classification["timeline_category"] = timeline_category
            classification["timeline_confidence"] = timeline_confidence
            classification["timeline_indicators"] = timeline_indicators
            
            decision_stage, decision_confidence, stage_indicators = self.determine_decision_stage(text)
            classification["decision_stage"] = decision_stage
            classification["decision_confidence"] = decision_confidence
            classification["stage_indicators"] = stage_indicators
            
            competition_level, competition_confidence, competition_indicators = self.assess_competition(text)
            classification["competition_level"] = competition_level
            classification["competition_confidence"] = competition_confidence
            classification["competition_indicators"] = competition_indicators
            
            # Calculate advanced metrics
            win_probability, probability_factors = self.calculate_win_probability(lead)
            classification["win_probability"] = win_probability
            classification["probability_factors"] = probability_factors
            
            priority_score, priority_level, priority_factors = self.assign_priority_score(lead)
            classification["priority_score"] = priority_score
            classification["priority_level"] = priority_level
            classification["priority_factors"] = priority_factors
            
            # Calculate overall classification confidence
            confidence_values = [
                classification.get("value_confidence", 0),
                classification.get("timeline_confidence", 0),
                classification.get("decision_confidence", 0),
                classification.get("competition_confidence", 0)
            ]
            classification["overall_confidence"] = statistics.mean([c for c in confidence_values if c > 0])
            
            # Update performance metrics
            self.performance_metrics["total_classifications"] += 1
            elapsed_time = time.time() - start_time
            self.performance_metrics["classification_times"].append(elapsed_time)
            
            for category in ["value_confidence", "timeline_confidence", "decision_confidence", 
                           "competition_confidence", "overall_confidence"]:
                if category not in self.performance_metrics["confidence_scores"]:
                    self.performance_metrics["confidence_scores"][category] = []
                
                if category in classification:
                    self.performance_metrics["confidence_scores"][category].append(
                        classification[category]
                    )
            
            logger.info(f"Classified lead '{lead.project_name}' in {elapsed_time:.3f}s "
                      f"(priority: {classification['priority_level']}, "
                      f"win probability: {classification['win_probability']:.2f})")
            
            return lead
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"Error classifying lead: {str(e)}")
            
            # Update performance metrics with failure
            self.performance_metrics["total_classifications"] += 1
            self.performance_metrics["classification_times"].append(elapsed_time)
            self.performance_metrics["success_rate"] = (
                (self.performance_metrics["success_rate"] * 
                 (self.performance_metrics["total_classifications"] - 1) + 0) / 
                self.performance_metrics["total_classifications"]
            )
            
            # Add basic error info to lead if possible
            try:
                if lead and hasattr(lead, "extra_data"):
                    if "classification" not in lead.extra_data:
                        lead.extra_data["classification"] = {}
                    
                    lead.extra_data["classification"]["error"] = str(e)
                    lead.extra_data["classification"]["classified_at"] = datetime.datetime.now().isoformat()
            except:
                pass
                
            raise ClassificationError(f"Failed to classify lead: {str(e)}")
    
    def categorize_by_value(self, 
                          estimated_value: float,
                          market_sector: Optional[str] = None) -> Tuple[str, float]:
        """
        Classify lead into a value tier based on estimated project value.
        
        This method applies sector-specific value tier thresholds to categorize
        projects based on their estimated monetary value.
        
        Args:
            estimated_value: Estimated project value in dollars
            market_sector: Optional market sector for sector-specific thresholds
            
        Returns:
            Tuple of (value_category, confidence)
            
        Raises:
            ValueError: If estimated_value is negative
        """
        if estimated_value < 0:
            raise ValueError("Estimated value cannot be negative")
        
        # Get appropriate value tiers based on market sector
        sector = market_sector.lower() if market_sector else "default"
        if sector not in self.config["value_tiers"]:
            sector = "default"
            
        tiers = self.config["value_tiers"][sector]
        
        # Categorize based on value
        if estimated_value < tiers["small"]:
            category = ValueCategory.SMALL
        elif estimated_value < tiers["medium"]:
            category = ValueCategory.MEDIUM
        elif estimated_value < tiers["large"]:
            category = ValueCategory.LARGE
        else:
            category = ValueCategory.MAJOR
        
        # Calculate confidence
        # Higher for values well within a tier, lower for values near boundaries
        confidence = 1.0  # Default high confidence
        
        # If value is close to tier boundary, reduce confidence
        tolerance = 0.10  # 10% tolerance around boundaries
        
        if category == ValueCategory.SMALL and estimated_value > tiers["small"] * (1 - tolerance):
            confidence = 0.8
        elif category == ValueCategory.MEDIUM:
            if estimated_value < tiers["small"] * (1 + tolerance):
                confidence = 0.8
            elif estimated_value > tiers["medium"] * (1 - tolerance):
                confidence = 0.8
        elif category == ValueCategory.LARGE:
            if estimated_value < tiers["medium"] * (1 + tolerance):
                confidence = 0.8
            elif estimated_value > tiers["large"] * (1 - tolerance):
                confidence = 0.8
        elif category == ValueCategory.MAJOR and estimated_value < tiers["large"] * (1 + tolerance):
            confidence = 0.8
            
        return category.value, confidence
    
    def categorize_by_timeline(self, text: str) -> Tuple[str, float, List[str]]:
        """
        Analyze text to determine project timeline category.
        
        This method examines the text for timeline indicators and classifies
        the project timeline as Immediate, Short-term, Mid-term, or Long-term.
        
        Args:
            text: Text to analyze for timeline indicators
            
        Returns:
            Tuple of (timeline_category, confidence, indicators_found)
            
        Raises:
            ClassificationError: If analysis fails
        """
        if not text:
            return TimelineCategory.UNKNOWN.value, 0.0, []
        
        try:
            # Preprocess text
            text = text.lower()
            
            # Initialize counters for each category
            match_counts = {
                "immediate": 0,
                "short_term": 0,
                "mid_term": 0,
                "long_term": 0
            }
            
            indicators_found = []
            
            # Check for specific date indicators
            date_indicators = self._extract_date_indicators(text)
            if date_indicators:
                # Add date-based indicators to the matches
                for category, indicator in date_indicators:
                    match_counts[category] += 2  # Date indicators given higher weight
                    indicators_found.append(indicator)
            
            # Check pattern matches for each category
            for category, patterns in self.timeline_patterns.items():
                for pattern in patterns:
                    matches = pattern.findall(text)
                    if matches:
                        match_counts[category] += len(matches)
                        indicators_found.extend(matches)
            
            # Get the category with the most matches
            if sum(match_counts.values()) == 0:
                return TimelineCategory.UNKNOWN.value, 0.0, []
                
            best_category = max(match_counts.items(), key=lambda x: x[1])
            category_name, match_count = best_category
            
            # Calculate confidence based on match distribution
            total_matches = sum(match_counts.values())
            confidence = match_count / total_matches if total_matches > 0 else 0
            
            # Boost confidence if we have multiple different indicators
            unique_indicators = len(set(indicators_found))
            if unique_indicators > 1:
                confidence = min(1.0, confidence + 0.1)
            if unique_indicators > 2:
                confidence = min(1.0, confidence + 0.1)
            
            # Reduce confidence if there's an even split between categories
            sorted_counts = sorted(match_counts.values(), reverse=True)
            if len(sorted_counts) > 1 and sorted_counts[0] == sorted_counts[1]:
                confidence *= 0.7
            
            return category_name, confidence, list(set(indicators_found))
            
        except Exception as e:
            logger.error(f"Error categorizing timeline: {str(e)}")
            return TimelineCategory.UNKNOWN.value, 0.0, []
    
    def _extract_date_indicators(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract date-based timeline indicators from text.
        
        This method looks for specific dates or time periods mentioned in text
        and categorizes them into timeline categories.
        
        Args:
            text: Text to analyze
            
        Returns:
            List of tuples (category, indicator_text)
        """
        indicators = []
        
        # Current date reference
        now = datetime.datetime.now()
        current_month = now.month
        current_year = now.year
        
        # Month and season references
        current_quarter = (current_month - 1) // 3 + 1
        month_names = ["january", "february", "march", "april", "may", "june", 
                      "july", "august", "september", "october", "november", "december"]
        
        # Look for month/year patterns
        month_year_pattern = re.compile(
            r'\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
            r'jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|'
            r'dec(?:ember)?)[,\s]+(\d{4})\b', 
            re.IGNORECASE
        )
        for match in month_year_pattern.finditer(text):
            try:
                month_str = match.group(1).lower()
                year_str = match.group(2)
                
                # Get month number (1-12)
                month_num = None
                for i, name in enumerate(month_names):
                    if name.startswith(month_str[:3].lower()):
                        month_num = i + 1
                        break
                
                if month_num and year_str:
                    year = int(year_str)
                    target_date = datetime.datetime(year, month_num, 1)
                    months_away = (year - current_year) * 12 + (month_num - current_month)
                    
                    indicator_text = f"{match.group(1)} {year_str}"
                    
                    if months_away <= 3:
                        indicators.append(("immediate", indicator_text))
                    elif months_away <= 6:
                        indicators.append(("short_term", indicator_text))
                    elif months_away <= 12:
                        indicators.append(("mid_term", indicator_text))
                    else:
                        indicators.append(("long_term", indicator_text))
            except (ValueError, TypeError):
                continue
        
        # Look for quarter references
        quarter_pattern = re.compile(r'\bq([1-4])[\s,]+(\d{4})\b', re.IGNORECASE)
        for match in quarter_pattern.finditer(text):
            try:
                quarter = int(match.group(1))
                year = int(match.group(2))
                
                # Calculate how many quarters away
                quarters_away = (year - current_year) * 4 + (quarter - current_quarter)
                indicator_text = f"Q{quarter} {year}"
                
                if quarters_away <= 1:
                    indicators.append(("immediate", indicator_text))
                elif quarters_away <= 2:
                    indicators.append(("short_term", indicator_text))
                elif quarters_away <= 4:
                    indicators.append(("mid_term", indicator_text))
                else:
                    indicators.append(("long_term", indicator_text))
            except (ValueError, TypeError):
                continue
        
        # Look for relative time references
        time_spans = [
            (r'\b(?:in\s+)?(\d+)\s*(?:to|-)\s*(\d+)\s*days\b', lambda x, y: ("immediate", f"{x}-{y} days") if int(y) <= 90 else ("short_term", f"{x}-{y} days")),
            (r'\b(?:in\s+)?(\d+)\s*(?:to|-)\s*(\d+)\s*weeks\b', lambda x, y: ("immediate", f"{x}-{y} weeks") if int(y) <= 12 else ("short_term", f"{x}-{y} weeks")),
            (r'\b(?:in\s+)?(\d+)\s*(?:to|-)\s*(\d+)\s*months\b', lambda x, y: 
                ("immediate", f"{x}-{y} months") if int(x) <= 3 else 
                ("short_term", f"{x}-{y} months") if int(x) <= 6 else 
                ("mid_term", f"{x}-{y} months") if int(y) <= 12 else 
                ("long_term", f"{x}-{y} months")),
            (r'\b(?:in\s+)?(\d+)\s*(?:to|-)\s*(\d+)\s*years\b', lambda x, y: ("long_term", f"{x}-{y} years")),
            (r'\b(?:in\s+)?(\d+)\s+days?\b', lambda x, _: ("immediate", f"{x} days") if int(x) <= 90 else ("short_term", f"{x} days")),
            (r'\b(?:in\s+)?(\d+)\s+weeks?\b', lambda x, _: ("immediate", f"{x} weeks") if int(x) <= 12 else ("short_term", f"{x} weeks")),
            (r'\b(?:in\s+)?(\d+)\s+months?\b', lambda x, _: 
                ("immediate", f"{x} months") if int(x) <= 3 else 
                ("short_term", f"{x} months") if int(x) <= 6 else 
                ("mid_term", f"{x} months") if int(x) <= 12 else 
                ("long_term", f"{x} months")),
            (r'\b(?:in\s+)?(\d+)\s+years?\b', lambda x, _: ("long_term", f"{x} years"))
        ]
        
        for pattern_str, categorizer in time_spans:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            for match in pattern.finditer(text):
                try:
                    x = match.group(1)
                    y = match.group(2) if len(match.groups()) > 1 else None
                    category, indicator_text = categorizer(x, y)
                    indicators.append((category, indicator_text))
                except (ValueError, TypeError, IndexError):
                    continue
        
        return indicators
    
    def determine_decision_stage(self, text: str) -> Tuple[str, float, List[str]]:
        """
        Identify the project's current decision stage.
        
        This method analyzes text to determine where the project stands in the
        decision-making process, from conceptual through implementation.
        
        Args:
            text: Text to analyze
            
        Returns:
            Tuple of (decision_stage, confidence, indicators_found)
            
        Raises:
            ClassificationError: If analysis fails
        """
        if not text:
            return DecisionStage.UNKNOWN.value, 0.0, []
        
        try:
            # Preprocess text
            text = text.lower()
            
            # Initialize counters for each stage
            match_counts = {
                "conceptual": 0,
                "planning": 0,
                "approval": 0,
                "funding": 0,
                "implementation": 0
            }
            
            indicators_found = []
            
            # Check pattern matches for each stage
            for stage, patterns in self.decision_stage_patterns.items():
                for pattern in patterns:
                    matches = pattern.findall(text)
                    if matches:
                        match_counts[stage] += len(matches)
                        indicators_found.extend(matches)
            
            # Process with NLP for context-aware stage detection
            doc = self.nlp_processor.preprocess_text(text)
            sentences = doc.split('.')
            
            # Check the context of each indicator keyword
            for stage, keywords in self.decision_stage_keywords.items():
                for sentence in sentences:
                    sentence = sentence.lower().strip()
                    for keyword in keywords:
                        if keyword in sentence:
                            # Check if keyword is negated
                            if any(neg in sentence for neg in ["not", "isn't", "aren't", "wasn't", "weren't"]):
                                # Negated keywords lower the count
                                match_counts[stage] -= 0.5
                            else:
                                match_counts[stage] += 1
                                if keyword not in indicators_found:
                                    indicators_found.append(keyword)
            
            # Get the stage with the most matches
            if sum(match_counts.values()) == 0:
                return DecisionStage.UNKNOWN.value, 0.0, []
                
            best_stage = max(match_counts.items(), key=lambda x: x[1])
            stage_name, match_count = best_stage
            
            # Calculate confidence based on match distribution
            total_matches = sum(v for v in match_counts.values() if v > 0)
            confidence = match_count / total_matches if total_matches > 0 else 0
            
            # Check for stages that should be sequential
            stage_sequence = ["conceptual", "planning", "approval", "funding", "implementation"]
            best_stage_idx = stage_sequence.index(stage_name)
            
            # If earlier stages have stronger signals than later ones, reduce confidence
            for i in range(best_stage_idx + 1, len(stage_sequence)):
                later_stage = stage_sequence[i]
                if match_counts[later_stage] > 0 and match_counts[later_stage] > 0.7 * match_count:
                    confidence *= 0.9
            
            # Boost confidence if we have multiple different indicators
            unique_indicators = len(set(indicators_found))
            if unique_indicators > 1:
                confidence = min(1.0, confidence + 0.1)
            if unique_indicators > 2:
                confidence = min(1.0, confidence + 0.1)
            
            return stage_name, confidence, list(set(indicators_found))
            
        except Exception as e:
            logger.error(f"Error determining decision stage: {str(e)}")
            return DecisionStage.UNKNOWN.value, 0.0, []
    
    def assess_competition(self, text: str) -> Tuple[str, float, List[str]]:
        """
        Analyze text for competitive landscape indicators.
        
        This method examines text for mentions of competing contractors and 
        estimates the competitive landscape for the project.
        
        Args:
            text: Text to analyze
            
        Returns:
            Tuple of (competition_level, confidence, indicators_found)
            
        Raises:
            ClassificationError: If analysis fails
        """
        if not text:
            return CompetitionLevel.UNKNOWN.value, 0.0, []
        
        try:
            # Preprocess text
            text = text.lower()
            
            # Initialize counters for each level
            match_counts = {
                "low": 0,
                "medium": 0,
                "high": 0
            }
            
            indicators_found = []
            
            # Check pattern matches for each level
            for level, patterns in self.competition_patterns.items():
                for pattern in patterns:
                    matches = pattern.findall(text)
                    if matches:
                        match_counts[level] += len(matches)
                        indicators_found.extend(matches)
            
            # Count mentions of competitors, bids, proposals
            competitor_count = 0
            
            # Check for number of bidders/competitors mentioned
            num_bidders_pattern = re.compile(
                r'(\d+)\s+(?:bidders|competitors|proposals|firms|companies|contractors)', 
                re.IGNORECASE
            )
            for match in num_bidders_pattern.finditer(text):
                try:
                    count = int(match.group(1))
                    competitor_count = max(competitor_count, count)
                    indicators_found.append(f"{count} bidders/competitors")
                except (ValueError, TypeError):
                    pass
            
            # Adjust match counts based on explicit competitor count
            if competitor_count > 0:
                if competitor_count <= 3:
                    match_counts["low"] += 2
                elif competitor_count <= 7:
                    match_counts["medium"] += 2
                else:
                    match_counts["high"] += 2
            
            # Check for RFP/RFQ/bid terms
            bid_terms = ["rfp", "rfq", "request for proposal", "request for quote", 
                       "invitation to bid", "competitive bid", "tender"]
            
            for term in bid_terms:
                if re.search(r'\b' + re.escape(term) + r'\b', text, re.IGNORECASE):
                    match_counts["medium"] += 1
                    indicators_found.append(term)
            
            # Get the level with the most matches
            if sum(match_counts.values()) == 0:
                return CompetitionLevel.UNKNOWN.value, 0.0, []
                
            best_level = max(match_counts.items(), key=lambda x: x[1])
            level_name, match_count = best_level
            
            # Calculate confidence based on match distribution
            total_matches = sum(match_counts.values())
            confidence = match_count / total_matches if total_matches > 0 else 0
            
            # Boost confidence if we have multiple different indicators
            unique_indicators = len(set(indicators_found))
            if unique_indicators > 1:
                confidence = min(1.0, confidence + 0.1)
            if unique_indicators > 2:
                confidence = min(1.0, confidence + 0.1)
            
            # Reduce confidence if competition level is unknown
            if not indicators_found:
                level_name = "medium"  # Default to medium if unknown
                confidence = 0.5
            
            return level_name, confidence, list(set(indicators_found))
            
        except Exception as e:
            logger.error(f"Error assessing competition: {str(e)}")
            return CompetitionLevel.UNKNOWN.value, 0.0, []
    
    def calculate_win_probability(self, lead: Lead) -> Tuple[float, Dict[str, float]]:
        """
        Calculate win probability based on multiple factors.
        
        This method applies a weighted model to estimate the probability of
        winning a lead based on market sector fit, geographical proximity,
        project size, competition level, relationships, and timeline.
        
        Args:
            lead: Lead to analyze
            
        Returns:
            Tuple of (win_probability, factor_scores)
            
        Raises:
            ClassificationError: If calculation fails
        """
        try:
            # Initialize factor scores
            factor_scores = {
                "market_sector_fit": 0.0,
                "geographical_proximity": 0.0,
                "project_size_fit": 0.0,
                "competition_level": 0.0,
                "relationship_strength": 0.0,
                "timeline_alignment": 0.0
            }
            
            # Get classification data if available
            classification = lead.extra_data.get("classification", {})
            
            # 1. Market Sector Fit
            if lead.market_sector:
                # Get sector expertise level
                sector = lead.market_sector.value.lower()
                expertise_level = self.config["sector_expertise_levels"].get(sector, 0.5)
                factor_scores["market_sector_fit"] = expertise_level
            
            # 2. Geographical Proximity
            if lead.location and lead.location.city:
                # Check if location is in strategic locations
                city = lead.location.city
                state = lead.location.state
                
                if city in self.config["strategic_locations"]:
                    factor_scores["geographical_proximity"] = 0.9
                elif state == "California":
                    factor_scores["geographical_proximity"] = 0.7
                else:
                    # Calculate distance-based score (simplified)
                    # In a real implementation, would use geocoding and distance calculation
                    factor_scores["geographical_proximity"] = 0.4
            
            # 3. Project Size Fit
            if lead.estimated_value:
                # Different size ranges have different win probabilities
                if lead.estimated_value < 1000000:  # <$1M
                    factor_scores["project_size_fit"] = 0.6  # Small projects are less strategic
                elif lead.estimated_value < 5000000:  # $1M-$5M
                    factor_scores["project_size_fit"] = 0.8  # Good size range
                elif lead.estimated_value < 50000000:  # $5M-$50M
                    factor_scores["project_size_fit"] = 0.9  # Ideal size range
                elif lead.estimated_value < 100000000:  # $50M-$100M
                    factor_scores["project_size_fit"] = 0.7  # Challenging but possible
                else:  # >$100M
                    factor_scores["project_size_fit"] = 0.5  # Very large projects are more competitive
            else:
                # Default middle score if no value available
                factor_scores["project_size_fit"] = 0.5
            
            # 4. Competition Level
            competition_level = classification.get("competition_level", CompetitionLevel.UNKNOWN.value)
            if competition_level == CompetitionLevel.LOW.value:
                factor_scores["competition_level"] = 0.9
            elif competition_level == CompetitionLevel.MEDIUM.value:
                factor_scores["competition_level"] = 0.6
            elif competition_level == CompetitionLevel.HIGH.value:
                factor_scores["competition_level"] = 0.3
            else:
                factor_scores["competition_level"] = 0.5  # Unknown competition
            
            # 5. Relationship Strength
            # Check if the client is in our primary client list
            if lead.extra_data.get("company") and "name" in lead.extra_data["company"]:
                company_name = lead.extra_data["company"]["name"]
                
                if company_name in self.config["primary_client_list"]:
                    factor_scores["relationship_strength"] = 0.9
                else:
                    # Check for partial matches (simplified)
                    for client in self.config["primary_client_list"]:
                        if client.lower() in company_name.lower() or company_name.lower() in client.lower():
                            factor_scores["relationship_strength"] = 0.7
                            break
                    else:
                        factor_scores["relationship_strength"] = 0.4
            else:
                factor_scores["relationship_strength"] = 0.4  # Unknown relationship
            
            # 6. Timeline Alignment
            timeline_category = classification.get("timeline_category", TimelineCategory.UNKNOWN.value)
            if timeline_category == TimelineCategory.IMMEDIATE.value:
                factor_scores["timeline_alignment"] = 0.9  # Ready to act
            elif timeline_category == TimelineCategory.SHORT_TERM.value:
                factor_scores["timeline_alignment"] = 0.8  # Good planning window
            elif timeline_category == TimelineCategory.MID_TERM.value:
                factor_scores["timeline_alignment"] = 0.7  # Enough time to prepare
            elif timeline_category == TimelineCategory.LONG_TERM.value:
                factor_scores["timeline_alignment"] = 0.5  # May lose focus over time
            else:
                factor_scores["timeline_alignment"] = 0.6  # Unknown timeline
            
            # Calculate weighted probability
            weighted_sum = 0
            weight_sum = 0
            
            for factor, score in factor_scores.items():
                weight = self.config["win_probability_factors"].get(factor, 0)
                weighted_sum += score * weight
                weight_sum += weight
            
            if weight_sum > 0:
                win_probability = weighted_sum / weight_sum
            else:
                win_probability = 0.5  # Default 50% if no weights
            
            # Ensure probability is in valid range
            win_probability = min(1.0, max(0.0, win_probability))
            
            return win_probability, factor_scores
            
        except Exception as e:
            logger.error(f"Error calculating win probability: {str(e)}")
            return 0.5, {}  # Default 50% on error
    
    def assign_priority_score(self, lead: Lead) -> Tuple[int, str, Dict[str, float]]:
        """
        Calculate overall priority score for lead handling.
        
        This method assesses the lead's overall priority using a configurable
        scoring algorithm that considers value, timeline, win probability, and
        strategic alignment.
        
        Args:
            lead: Lead to assess
            
        Returns:
            Tuple of (priority_score, priority_level, factor_scores)
            
        Raises:
            ClassificationError: If calculation fails
        """
        try:
            # Initialize factor scores
            factor_scores = {
                "value_score": 0.0,
                "timeline_score": 0.0,
                "win_probability": 0.0,
                "strategic_alignment": 0.0
            }
            
            # Get classification data if available
            classification = lead.extra_data.get("classification", {})
            
            # 1. Value Score
            value_category = classification.get("value_category", ValueCategory.UNKNOWN.value)
            if value_category == ValueCategory.MAJOR.value:
                factor_scores["value_score"] = 1.0
            elif value_category == ValueCategory.LARGE.value:
                factor_scores["value_score"] = 0.8
            elif value_category == ValueCategory.MEDIUM.value:
                factor_scores["value_score"] = 0.6
            elif value_category == ValueCategory.SMALL.value:
                factor_scores["value_score"] = 0.4
            else:
                # Unknown value
                if lead.estimated_value:
                    # Calculate based on value directly
                    if lead.estimated_value > 50000000:  # >$50M
                        factor_scores["value_score"] = 1.0
                    elif lead.estimated_value > 10000000:  # >$10M
                        factor_scores["value_score"] = 0.8
                    elif lead.estimated_value > 2000000:  # >$2M
                        factor_scores["value_score"] = 0.6
                    else:
                        factor_scores["value_score"] = 0.4
                else:
                    factor_scores["value_score"] = 0.5  # Unknown value, middle score
            
            # 2. Timeline Score
            timeline_category = classification.get("timeline_category", TimelineCategory.UNKNOWN.value)
            if timeline_category == TimelineCategory.IMMEDIATE.value:
                factor_scores["timeline_score"] = 1.0
            elif timeline_category == TimelineCategory.SHORT_TERM.value:
                factor_scores["timeline_score"] = 0.8
            elif timeline_category == TimelineCategory.MID_TERM.value:
                factor_scores["timeline_score"] = 0.6
            elif timeline_category == TimelineCategory.LONG_TERM.value:
                factor_scores["timeline_score"] = 0.4
            else:
                factor_scores["timeline_score"] = 0.5  # Unknown timeline, middle score
            
            # 3. Win Probability
            win_probability = classification.get("win_probability", 0.5)
            factor_scores["win_probability"] = win_probability
            
            # 4. Strategic Alignment
            strategic_alignment = 0.0
            
            # Is it in our target market sectors?
            if lead.market_sector:
                sector = lead.market_sector.value.lower()
                strategic_sectors = ["healthcare", "education", "energy", "entertainment", "commercial"]
                if sector in strategic_sectors:
                    strategic_alignment += 0.5
                else:
                    strategic_alignment += 0.2
            
            # Is it in our target geographic areas?
            if lead.location and lead.location.city:
                if lead.location.city in self.config["strategic_locations"]:
                    strategic_alignment += 0.5
                elif lead.location.state == "California":
                    strategic_alignment += 0.3
                else:
                    strategic_alignment += 0.1
            
            factor_scores["strategic_alignment"] = min(1.0, strategic_alignment)
            
            # Calculate weighted score
            weighted_sum = (
                factor_scores["value_score"] * self.config["priority_scoring"]["value_weight"] +
                factor_scores["timeline_score"] * self.config["priority_scoring"]["timeline_weight"] +
                factor_scores["win_probability"] * self.config["priority_scoring"]["win_probability_weight"] +
                factor_scores["strategic_alignment"] * self.config["priority_scoring"]["strategic_alignment_weight"]
            )
            
            # Convert to 1-100 scale
            priority_score = int(weighted_sum * 100)
            priority_score = min(100, max(1, priority_score))
            
            # Determine priority level
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
            
            return priority_score, priority_level, factor_scores
            
        except Exception as e:
            logger.error(f"Error calculating priority score: {str(e)}")
            return 50, PriorityLevel.MEDIUM.value, {}  # Default medium priority on error
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get performance metrics for the classifier.
        
        Returns:
            Dictionary of performance metrics
        """
        metrics = self.performance_metrics.copy()
        
        # Calculate average classification time
        if metrics["classification_times"]:
            metrics["avg_classification_time"] = statistics.mean(metrics["classification_times"])
            metrics["max_classification_time"] = max(metrics["classification_times"])
        
        # Calculate average confidence scores
        for category, scores in metrics["confidence_scores"].items():
            if scores:
                metrics["confidence_scores"][category] = {
                    "avg": statistics.mean(scores),
                    "min": min(scores),
                    "max": max(scores)
                }
        
        return metrics
    
    @lru_cache(maxsize=100)
    def get_sector_rules(self, sector: str) -> Dict[str, Any]:
        """
        Get sector-specific classification rules.
        
        This provides a cached lookup for sector-specific rules to speed up
        classification operations.
        
        Args:
            sector: Market sector name
            
        Returns:
            Dictionary of sector-specific rules
        """
        sector = sector.lower() if sector else "default"
        
        # Combine default rules with sector-specific overrides
        rules = {
            "value_tiers": self.config["value_tiers"].get("default", {}),
            "win_probability_boost": 0.0,
            "priority_boost": 0.0
        }
        
        # Apply sector-specific value tiers if available
        if sector in self.config["value_tiers"]:
            rules["value_tiers"] = self.config["value_tiers"][sector]
        
        # Apply expertise level as win probability boost
        if sector in self.config["sector_expertise_levels"]:
            expertise = self.config["sector_expertise_levels"][sector]
            rules["win_probability_boost"] = (expertise - 0.5) * 0.2  # -0.1 to +0.1 adjustment
        
        # Strategic sectors get priority boost
        strategic_sectors = ["healthcare", "education", "energy", "entertainment", "commercial"]
        if sector in strategic_sectors:
            rules["priority_boost"] = 0.1
        
        return rules
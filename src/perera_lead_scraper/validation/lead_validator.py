"""
Lead Validator - Validation logic for ensuring lead quality.

This module implements comprehensive validation rules to ensure that only 
high-quality leads matching our business criteria are processed. It provides
functions for validating various aspects of a lead, including required fields,
location, market sector, contact information, duplicates, project timeline,
and project intent.
"""

import re
import logging
import difflib
from typing import Tuple, List, Dict, Any, Optional, Set, Union
from datetime import datetime, timedelta
import json
import os
from enum import Enum
import time

# Local imports
from perera_lead_scraper.models.lead import Lead, MarketSector
from perera_lead_scraper.utils.storage import LocalStorage
from perera_lead_scraper.nlp.nlp_processor import NLPProcessor
import perera_lead_scraper.config as config

# Set up logger
logger = logging.getLogger(__name__)

class ValidationLevel(Enum):
    """Enumeration of validation severity levels."""
    CRITICAL = "critical"  # Validation must pass or lead is rejected
    STANDARD = "standard"  # Important validation that affects score significantly
    ADVISORY = "advisory"  # Minor validation that slightly affects score

class ValidationResult:
    """Class representing the result of a validation operation."""
    
    def __init__(self, 
                 is_valid: bool = True, 
                 messages: List[str] = None, 
                 confidence_adjustment: float = 0.0,
                 normalized_data: Any = None,
                 level: ValidationLevel = ValidationLevel.STANDARD):
        """
        Initialize a validation result.
        
        Args:
            is_valid: Boolean indicating if validation passed.
            messages: List of validation messages/reasons.
            confidence_adjustment: Adjustment to confidence score (positive or negative).
            normalized_data: Any normalized data resulting from validation.
            level: ValidationLevel indicating severity of this validation.
        """
        self.is_valid = is_valid
        self.messages = messages or []
        self.confidence_adjustment = confidence_adjustment
        self.normalized_data = normalized_data
        self.level = level
    
    def append_message(self, message: str) -> None:
        """Append a message to the validation messages."""
        self.messages.append(message)
    
    def merge(self, other: 'ValidationResult') -> 'ValidationResult':
        """
        Merge another validation result into this one.
        
        Args:
            other: Another ValidationResult to merge with this one.
            
        Returns:
            The merged ValidationResult.
        """
        # If other is invalid and is CRITICAL, this becomes invalid too
        if not other.is_valid and other.level == ValidationLevel.CRITICAL:
            self.is_valid = False
        # If this is CRITICAL and invalid, it stays invalid
        elif not self.is_valid and self.level == ValidationLevel.CRITICAL:
            pass
        # Otherwise, both must be valid for the result to be valid
        else:
            self.is_valid = self.is_valid and other.is_valid
        
        # Merge messages
        self.messages.extend(other.messages)
        
        # Sum confidence adjustments
        self.confidence_adjustment += other.confidence_adjustment
        
        # Return self for chaining
        return self


class LeadValidator:
    """
    Validator for ensuring leads meet business criteria.
    
    This class implements comprehensive validation rules to ensure that only 
    high-quality leads matching our business criteria are processed.
    """
    
    def __init__(self, 
                 storage: Optional[LocalStorage] = None,
                 nlp_processor: Optional[NLPProcessor] = None,
                 config_override: Optional[Dict[str, Any]] = None):
        """
        Initialize the lead validator.
        
        Args:
            storage: Optional LocalStorage instance. If not provided, one will be created.
            nlp_processor: Optional NLPProcessor instance. If not provided, one will be created.
            config_override: Optional configuration overrides.
        """
        self.storage = storage or LocalStorage()
        self.nlp_processor = nlp_processor or NLPProcessor()
        
        # Load configuration
        self._load_configuration(config_override)
        
        # Initialize caches
        self._initialize_caches()
        
        logger.info(f"Lead validator initialized with configuration: {self.config}")
    
    def _load_configuration(self, config_override: Optional[Dict[str, Any]] = None) -> None:
        """
        Load validator configuration from config module and apply overrides.
        
        Args:
            config_override: Optional configuration overrides.
        """
        # Default configuration
        default_config = {
            'required_fields': ['title', 'source_id', 'description'],
            'min_title_length': 10,
            'min_description_length': 50,
            'contact_email_regex': r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            'contact_phone_regex': r'(\+\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}',
            'duplicate_lookback_days': 30,
            'duplicate_similarity_threshold': 0.85,
            'publication_date_window_days': 14,
            'confidence_thresholds': {
                'high': 0.8,
                'medium': 0.6,
                'low': 0.4
            },
            'validation_weights': {
                'required_fields': 0.2,
                'location': 0.15,
                'market_sector': 0.15,
                'contact_info': 0.1,
                'duplicates': 0.15,
                'project_timeline': 0.1,
                'project_intent': 0.15
            },
            'enable_learning': True,
            'cache_ttl_seconds': 3600,  # 1 hour cache lifetime
            'validation_timeout_ms': 1000,  # Max time for full validation
        }
        
        # Load from config module
        try:
            validator_config = getattr(config, 'VALIDATOR_CONFIG', {})
            default_config.update(validator_config)
        except (AttributeError, ImportError) as e:
            logger.warning(f"Failed to load validator configuration from config module: {e}")
        
        # Apply overrides
        if config_override:
            default_config.update(config_override)
        
        # Apply environment variable overrides
        for key in default_config:
            env_var = f"PERERA_VALIDATOR_{key.upper()}"
            if env_var in os.environ:
                try:
                    # Convert string to appropriate type based on default
                    value = os.environ[env_var]
                    if isinstance(default_config[key], bool):
                        default_config[key] = value.lower() in ('true', 'yes', '1')
                    elif isinstance(default_config[key], int):
                        default_config[key] = int(value)
                    elif isinstance(default_config[key], float):
                        default_config[key] = float(value)
                    elif isinstance(default_config[key], dict):
                        # For nested configs, we'd need more sophisticated parsing
                        try:
                            default_config[key] = json.loads(value)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse JSON from environment variable {env_var}")
                    else:
                        default_config[key] = value
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse environment variable {env_var}: {e}")
        
        self.config = default_config
        
        # Load target markets from configuration
        self.target_markets = getattr(config, 'TARGET_MARKETS', [])
        
        # Load target sectors from configuration
        self.target_sectors = [sector.value for sector in MarketSector]
    
    def _initialize_caches(self) -> None:
        """Initialize caches for frequently accessed data."""
        # Cache for location validation
        self.location_cache: Dict[str, Tuple[bool, str, float]] = {}
        self.location_cache_timestamp = time.time()
        
        # Cache for duplicate checks
        self.duplicate_cache: Dict[str, Tuple[bool, List[str], float]] = {}
        self.duplicate_cache_timestamp = time.time()
        
        # Cache for recently validated leads - used for feedback loop
        self.validation_history: List[Dict[str, Any]] = []
        
        # Initialize other caches as needed
    
    def _refresh_caches_if_needed(self) -> None:
        """Check cache freshness and refresh if TTL has expired."""
        current_time = time.time()
        ttl = self.config.get('cache_ttl_seconds', 3600)
        
        # Check location cache
        if current_time - self.location_cache_timestamp > ttl:
            logger.debug("Refreshing location cache")
            self.location_cache = {}
            self.location_cache_timestamp = current_time
        
        # Check duplicate cache
        if current_time - self.duplicate_cache_timestamp > ttl:
            logger.debug("Refreshing duplicate cache")
            self.duplicate_cache = {}
            self.duplicate_cache_timestamp = current_time
    
    def validate_lead(self, lead: Lead) -> Tuple[bool, List[str], float]:
        """
        Main entry point for lead validation, applying all validation rules.
        
        This method orchestrates the validation process, applying all relevant
        validation rules to the lead and aggregating the results.
        
        Args:
            lead: The Lead object to validate.
            
        Returns:
            Tuple containing:
                - Boolean indicating if lead passes validation
                - List of validation messages/reasons
                - Updated confidence score after validation adjustments
        """
        start_time = time.time()
        logger.info(f"Validating lead: {lead.title}")
        
        # Refresh caches if needed
        self._refresh_caches_if_needed()
        
        # Track validation results
        all_results = ValidationResult()
        original_confidence = lead.confidence_score or 0.5
        
        # Apply all validation rules
        
        # 1. Check required fields - CRITICAL validation
        required_fields_result = self.check_required_fields(lead)
        required_fields_result.level = ValidationLevel.CRITICAL
        all_results.merge(required_fields_result)
        
        # If critical validation fails, return early
        if not all_results.is_valid:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.info(f"Lead validation failed (critical checks) in {elapsed_ms:.2f}ms: {lead.title}")
            return all_results.is_valid, all_results.messages, original_confidence
        
        # 2. Validate location
        if lead.location:
            location_result = self.validate_location(lead.location)
            if location_result.normalized_data:
                lead.location = location_result.normalized_data
            all_results.merge(location_result)
        
        # 3. Validate market sector
        if lead.project_type:
            market_sector_result = self.validate_market_sector(lead.project_type)
            all_results.merge(market_sector_result)
        
        # 4. Validate contact information
        if hasattr(lead, 'contacts') and lead.contacts:
            contact_result = self.validate_contact_info(lead.contacts)
            if contact_result.normalized_data:
                lead.contacts = contact_result.normalized_data
            all_results.merge(contact_result)
        
        # 5. Check for duplicates
        duplicate_result = self.check_duplicates(lead)
        all_results.merge(duplicate_result)
        
        # 6. Validate project timeline
        timeline_result = self.validate_project_timeline(lead)
        all_results.merge(timeline_result)
        
        # 7. Check project intent
        intent_result = self.check_project_intent(lead)
        all_results.merge(intent_result)
        
        # Calculate overall quality score
        quality_score = self.evaluate_lead_quality(lead, all_results)
        
        # Calculate adjusted confidence score
        adjusted_confidence = original_confidence + all_results.confidence_adjustment
        adjusted_confidence = max(0.0, min(1.0, adjusted_confidence))  # Clamp to [0, 1]
        
        # Store validation result for learning
        if self.config.get('enable_learning', True):
            self._store_validation_result(lead, all_results, adjusted_confidence, quality_score)
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"Lead validation completed in {elapsed_ms:.2f}ms. Valid: {all_results.is_valid}, " +
                     f"Confidence: {original_confidence:.2f} -> {adjusted_confidence:.2f}, " +
                     f"Quality: {quality_score:.2f}")
        
        if elapsed_ms > self.config.get('validation_timeout_ms', 1000):
            logger.warning(f"Lead validation exceeded timeout ({self.config.get('validation_timeout_ms', 1000)}ms)")
        
        # Update lead's confidence score
        lead.confidence_score = adjusted_confidence
        lead.quality_score = quality_score
        
        return all_results.is_valid, all_results.messages, adjusted_confidence
    
    def check_required_fields(self, lead: Lead) -> ValidationResult:
        """
        Verify that all required fields are present and valid.
        
        Args:
            lead: The Lead object to validate.
            
        Returns:
            ValidationResult with validation outcome and messages.
        """
        logger.debug(f"Checking required fields for lead: {lead.title}")
        
        result = ValidationResult(is_valid=True)
        required_fields = self.config.get('required_fields', ['title', 'source_id', 'description'])
        
        for field in required_fields:
            value = getattr(lead, field, None)
            
            # Check if field exists and is not empty
            if value is None or (isinstance(value, str) and not value.strip()):
                result.is_valid = False
                result.append_message(f"Missing required field: {field}")
                result.confidence_adjustment -= 0.1
                continue
            
            # Field-specific validation
            if field == 'title':
                min_length = self.config.get('min_title_length', 10)
                if isinstance(value, str) and len(value) < min_length:
                    result.append_message(f"Title too short (min {min_length} characters)")
                    result.confidence_adjustment -= 0.05
            
            elif field == 'description':
                min_length = self.config.get('min_description_length', 50)
                if isinstance(value, str) and len(value) < min_length:
                    result.append_message(f"Description too short (min {min_length} characters)")
                    result.confidence_adjustment -= 0.05
        
        if result.is_valid:
            if len(result.messages) == 0:
                result.append_message("All required fields present and valid")
            result.confidence_adjustment += 0.05
        
        return result
    
    def validate_location(self, location: str) -> ValidationResult:
        """
        Check if location is within Perera's target geographical areas.
        
        Args:
            location: The location string to validate.
            
        Returns:
            ValidationResult with validation outcome, normalized location, and confidence adjustment.
        """
        if not location:
            return ValidationResult(
                is_valid=False,
                messages=["Empty location"],
                confidence_adjustment=-0.1
            )
        
        # Check cache first
        cache_key = location.lower()
        if cache_key in self.location_cache:
            is_valid, normalized_location, conf_adj = self.location_cache[cache_key]
            messages = ["Location from cache"]
            if not is_valid:
                messages.append("Location not in target markets")
            return ValidationResult(
                is_valid=is_valid,
                messages=messages,
                confidence_adjustment=conf_adj,
                normalized_data=normalized_location
            )
        
        # Normalize location (strip whitespace, standardize format)
        normalized_location = location.strip()
        confidence_adjustment = 0.0
        
        # Check if location is in target markets
        is_in_target_market = False
        matched_market = None
        
        # Check for empty target markets list (if empty, any location is valid)
        if not self.target_markets:
            is_in_target_market = True
            confidence_adjustment += 0.02
        else:
            # Try prefix matching first (e.g., "San Francisco" should match "San Francisco, CA")
            for market in self.target_markets:
                if normalized_location.lower().startswith(market.lower()) or market.lower().startswith(normalized_location.lower()):
                    is_in_target_market = True
                    matched_market = market
                    confidence_adjustment += 0.05
                    break
            
            # If no prefix match, try containment matching
            if not is_in_target_market:
                for market in self.target_markets:
                    if market.lower() in normalized_location.lower() or normalized_location.lower() in market.lower():
                        is_in_target_market = True
                        matched_market = market
                        confidence_adjustment += 0.03
                        break
            
            # If still no match, try fuzzy matching
            if not is_in_target_market:
                best_ratio = 0
                for market in self.target_markets:
                    ratio = difflib.SequenceMatcher(None, normalized_location.lower(), market.lower()).ratio()
                    if ratio > 0.8 and ratio > best_ratio:  # 0.8 is a reasonable threshold for fuzzy location matching
                        best_ratio = ratio
                        matched_market = market
                
                if matched_market:
                    is_in_target_market = True
                    # Use best_ratio to adjust confidence (close match = higher confidence)
                    confidence_adjustment += best_ratio * 0.03
                    normalized_location = matched_market  # Use the matched market as normalized location
        
        # Create result
        messages = []
        if is_in_target_market:
            messages.append(f"Location in target market{': ' + matched_market if matched_market else ''}")
        else:
            messages.append("Location not in target markets")
            confidence_adjustment -= 0.1
        
        # Store in cache
        self.location_cache[cache_key] = (is_in_target_market, normalized_location, confidence_adjustment)
        
        return ValidationResult(
            is_valid=is_in_target_market,
            messages=messages,
            confidence_adjustment=confidence_adjustment,
            normalized_data=normalized_location
        )
    
    def validate_market_sector(self, sector: str) -> ValidationResult:
        """
        Confirm sector is one of our focus areas.
        
        Args:
            sector: The market sector to validate.
            
        Returns:
            ValidationResult with validation outcome and confidence adjustment.
        """
        if not sector:
            return ValidationResult(
                is_valid=False,
                messages=["Empty market sector"],
                confidence_adjustment=-0.1
            )
        
        # Normalize sector (strip whitespace, convert to lowercase)
        normalized_sector = sector.strip().lower()
        confidence_adjustment = 0.0
        
        # Check if sector is in target sectors
        is_in_target_sector = False
        matched_sector = None
        
        # Check for empty target sectors list (if empty, any sector is valid)
        if not self.target_sectors:
            is_in_target_sector = True
            confidence_adjustment += 0.02
        else:
            # Try exact matching first
            for target_sector in self.target_sectors:
                if normalized_sector == target_sector.lower():
                    is_in_target_sector = True
                    matched_sector = target_sector
                    confidence_adjustment += 0.05
                    break
            
            # If no exact match, try containment matching
            if not is_in_target_sector:
                for target_sector in self.target_sectors:
                    if target_sector.lower() in normalized_sector or normalized_sector in target_sector.lower():
                        is_in_target_sector = True
                        matched_sector = target_sector
                        confidence_adjustment += 0.03
                        break
            
            # If still no match, try fuzzy matching
            if not is_in_target_sector:
                best_ratio = 0
                for target_sector in self.target_sectors:
                    ratio = difflib.SequenceMatcher(None, normalized_sector, target_sector.lower()).ratio()
                    if ratio > 0.7 and ratio > best_ratio:  # 0.7 threshold for sector fuzzy matching
                        best_ratio = ratio
                        matched_sector = target_sector
                
                if matched_sector:
                    is_in_target_sector = True
                    # Use best_ratio to adjust confidence (close match = higher confidence)
                    confidence_adjustment += best_ratio * 0.03
        
        # Create result
        messages = []
        if is_in_target_sector:
            messages.append(f"Sector in target markets{': ' + matched_sector if matched_sector else ''}")
        else:
            messages.append("Sector not in target markets")
            confidence_adjustment -= 0.1
        
        return ValidationResult(
            is_valid=is_in_target_sector,
            messages=messages,
            confidence_adjustment=confidence_adjustment
        )
    
    def validate_contact_info(self, contact_info: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate contact information.
        
        Args:
            contact_info: List of contact information dictionaries.
            
        Returns:
            ValidationResult with validation outcome, normalized contact info, and messages.
        """
        if not contact_info:
            return ValidationResult(
                is_valid=True,  # Contact info is not required for valid lead
                messages=["No contact information provided"],
                confidence_adjustment=-0.02  # Slight penalty for no contacts
            )
        
        result = ValidationResult(is_valid=True)
        normalized_contacts = []
        has_valid_contact = False
        
        # Email and phone regex patterns
        email_regex = re.compile(self.config.get('contact_email_regex', r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'))
        phone_regex = re.compile(self.config.get('contact_phone_regex', r'(\+\d{1,3}[- ]?)?\(?\d{3}\)?[- ]?\d{3}[- ]?\d{4}'))
        
        for i, contact in enumerate(contact_info):
            normalized_contact = contact.copy()
            contact_is_valid = False
            
            # Check name
            if 'name' in contact and contact['name']:
                contact_is_valid = True
            else:
                result.append_message(f"Contact {i+1} missing name")
            
            # Check and normalize email
            if 'email' in contact and contact['email']:
                email = contact['email'].strip().lower()
                if email_regex.match(email):
                    normalized_contact['email'] = email
                    contact_is_valid = True
                else:
                    result.append_message(f"Contact {i+1} has invalid email format: {email}")
            
            # Check and normalize phone
            if 'phone' in contact and contact['phone']:
                phone = re.sub(r'[^0-9+]', '', contact['phone'])  # Keep only digits and + sign
                if phone_regex.match(contact['phone']):
                    normalized_contact['phone'] = phone
                    contact_is_valid = True
                else:
                    result.append_message(f"Contact {i+1} has invalid phone format: {contact['phone']}")
            
            # If contact has at least one valid field, include it
            if contact_is_valid:
                has_valid_contact = True
                normalized_contacts.append(normalized_contact)
        
        # Adjust confidence based on contact quality
        if has_valid_contact:
            result.confidence_adjustment += min(0.05 * len(normalized_contacts), 0.15)  # Up to +0.15 for multiple contacts
            result.append_message(f"Found {len(normalized_contacts)} valid contacts")
        else:
            result.confidence_adjustment -= 0.05
            result.append_message("No valid contacts found")
        
        result.normalized_data = normalized_contacts
        return result
    
    def check_duplicates(self, lead: Lead, days: int = None) -> ValidationResult:
        """
        Check if lead is a duplicate of existing leads.
        
        Args:
            lead: The Lead object to check.
            days: Optional number of days to look back for duplicates.
                 If None, uses the configured default.
            
        Returns:
            ValidationResult with duplication status, references to potential duplicates, and confidence adjustment.
        """
        # Use configured default if days not specified
        if days is None:
            days = self.config.get('duplicate_lookback_days', 30)
        
        # Create a fingerprint for this lead
        fingerprint = self._generate_lead_fingerprint(lead)
        
        # Check cache first
        if fingerprint in self.duplicate_cache:
            is_duplicate, duplicate_refs, conf_adj = self.duplicate_cache[fingerprint]
            messages = ["Duplicate check from cache"]
            if is_duplicate:
                messages.extend([f"Potential duplicate: {ref}" for ref in duplicate_refs])
            return ValidationResult(
                is_valid=not is_duplicate,  # Valid if NOT a duplicate
                messages=messages,
                confidence_adjustment=conf_adj
            )
        
        # Query recent leads from storage
        recent_leads = self.storage.get_recent_leads(days=days)
        
        if not recent_leads:
            logger.debug("No recent leads found for duplicate check")
            # No duplicates possible if no recent leads
            self.duplicate_cache[fingerprint] = (False, [], 0.05)
            return ValidationResult(
                is_valid=True,
                messages=["No recent leads to check for duplicates"],
                confidence_adjustment=0.05
            )
        
        # Check for duplicates
        similarity_threshold = self.config.get('duplicate_similarity_threshold', 0.85)
        duplicate_refs = []
        max_similarity = 0.0
        
        for existing_lead in recent_leads:
            # Skip self-comparison if this lead is already in storage
            if existing_lead.id == lead.id:
                continue
                
            # Calculate similarity
            similarity = self._calculate_lead_similarity(lead, existing_lead)
            
            if similarity > max_similarity:
                max_similarity = similarity
                
            if similarity >= similarity_threshold:
                duplicate_refs.append(f"{existing_lead.id}:{existing_lead.title}")
        
        # Determine if this is a duplicate
        is_duplicate = len(duplicate_refs) > 0
        
        # Adjust confidence based on duplicate check
        if is_duplicate:
            confidence_adjustment = -0.2 * max_similarity  # More similar = bigger penalty
        else:
            confidence_adjustment = 0.05  # Bonus for no duplicates
        
        # Create messages
        messages = []
        if is_duplicate:
            messages.append(f"Found {len(duplicate_refs)} potential duplicates (max similarity: {max_similarity:.2f})")
            messages.extend([f"Potential duplicate: {ref}" for ref in duplicate_refs[:3]])  # Show top 3 duplicates
            if len(duplicate_refs) > 3:
                messages.append(f"... and {len(duplicate_refs) - 3} more")
        else:
            messages.append("No duplicates found")
        
        # Store in cache
        self.duplicate_cache[fingerprint] = (is_duplicate, duplicate_refs, confidence_adjustment)
        
        return ValidationResult(
            is_valid=not is_duplicate,  # Valid if NOT a duplicate
            messages=messages,
            confidence_adjustment=confidence_adjustment
        )
    
    def validate_project_timeline(self, lead: Lead) -> ValidationResult:
        """
        Validate the lead's timeline information.
        
        Args:
            lead: The Lead object to validate.
            
        Returns:
            ValidationResult with validation outcome and confidence adjustment.
        """
        result = ValidationResult(is_valid=True)
        
        # Check publication date recency
        if lead.published_date:
            # Convert to datetime if string
            if isinstance(lead.published_date, str):
                try:
                    from dateutil import parser
                    published_date = parser.parse(lead.published_date)
                except (ValueError, TypeError):
                    result.append_message("Invalid publication date format")
                    result.confidence_adjustment -= 0.05
                    published_date = None
            else:
                published_date = lead.published_date
            
            if published_date:
                # Check if publication is within acceptable window
                window_days = self.config.get('publication_date_window_days', 14)
                days_old = (datetime.now() - published_date).days
                
                if days_old < 0:
                    result.append_message("Publication date is in the future")
                    result.confidence_adjustment -= 0.1
                elif days_old > window_days:
                    result.append_message(f"Publication date older than {window_days} days")
                    # Penalty scales with age
                    result.confidence_adjustment -= min(0.1 + 0.01 * (days_old - window_days), 0.3)
                else:
                    result.append_message("Publication date within acceptable window")
                    # Bonus for fresh content
                    freshness_factor = 1.0 - (days_old / window_days)
                    result.confidence_adjustment += 0.05 * freshness_factor
        
        # Check project start date if available
        if lead.start_date:
            # Convert to datetime if string
            if isinstance(lead.start_date, str):
                try:
                    from dateutil import parser
                    start_date = parser.parse(lead.start_date)
                except (ValueError, TypeError):
                    result.append_message("Invalid start date format")
                    result.confidence_adjustment -= 0.03
                    start_date = None
            else:
                start_date = lead.start_date
            
            if start_date:
                # Check if start date is reasonable (not too far in past or future)
                now = datetime.now()
                days_until_start = (start_date - now).days
                
                if days_until_start < -180:  # More than 6 months in the past
                    result.append_message("Project start date is far in the past")
                    result.confidence_adjustment -= 0.05
                elif days_until_start > 365:  # More than a year in the future
                    result.append_message("Project start date is far in the future")
                    result.confidence_adjustment -= 0.03
                else:
                    result.append_message("Project start date is reasonable")
                    result.confidence_adjustment += 0.03
                    
                    # Extra bonus for projects starting soon (1-60 days)
                    if 1 <= days_until_start <= 60:
                        result.append_message("Project starting soon")
                        result.confidence_adjustment += 0.07
        
        # Check project end date if available
        if lead.end_date and lead.start_date:
            # Convert to datetime if strings
            try:
                from dateutil import parser
                if isinstance(lead.start_date, str):
                    start_date = parser.parse(lead.start_date)
                else:
                    start_date = lead.start_date
                    
                if isinstance(lead.end_date, str):
                    end_date = parser.parse(lead.end_date)
                else:
                    end_date = lead.end_date
                
                # Check if end date is after start date
                if end_date < start_date:
                    result.append_message("Project end date is before start date")
                    result.confidence_adjustment -= 0.05
                else:
                    project_duration = (end_date - start_date).days
                    
                    # Check if project duration is reasonable
                    if project_duration < 7:  # Less than a week
                        result.append_message("Project duration is very short")
                        result.confidence_adjustment -= 0.02
                    elif project_duration > 1095:  # More than 3 years
                        result.append_message("Project duration is very long")
                        result.confidence_adjustment -= 0.02
                    else:
                        result.append_message("Project duration is reasonable")
                        result.confidence_adjustment += 0.02
            except (ValueError, TypeError):
                result.append_message("Invalid date format in project timeline")
                result.confidence_adjustment -= 0.03
        
        return result
    
    def check_project_intent(self, lead: Lead) -> ValidationResult:
        """
        Verify lead contains indicators of construction project intent.
        
        Args:
            lead: The Lead object to validate.
            
        Returns:
            ValidationResult with validation outcome, identified intent markers, and confidence adjustment.
        """
        result = ValidationResult(is_valid=True)
        
        # Extract text for analysis
        text = f"{lead.title} {lead.description}"
        
        # Use NLP to identify project intent
        project_intent_analysis = self.nlp_processor.analyze_project_intent(text)
        
        # Get intent confidence score
        intent_score = project_intent_analysis.get('intent_score', 0.0)
        intent_indicators = project_intent_analysis.get('indicators', [])
        
        # Set threshold for valid intent
        intent_threshold = 0.6
        
        if intent_score >= intent_threshold:
            result.is_valid = True
            result.append_message(f"Project intent confirmed (score: {intent_score:.2f})")
            
            # Higher intent score = higher confidence adjustment
            result.confidence_adjustment += intent_score * 0.1
            
            # Add identified indicators to messages
            if intent_indicators:
                result.append_message(f"Intent indicators: {', '.join(intent_indicators[:3])}")
                if len(intent_indicators) > 3:
                    result.append_message(f"... and {len(intent_indicators) - 3} more")
        else:
            result.is_valid = False
            result.append_message(f"Insufficient project intent (score: {intent_score:.2f})")
            result.confidence_adjustment -= (1 - intent_score) * 0.1
        
        return result
    
    def evaluate_lead_quality(self, lead: Lead, validation_results: ValidationResult = None) -> float:
        """
        Calculate overall quality score based on all validation results.
        
        Args:
            lead: The Lead object to evaluate.
            validation_results: Optional ValidationResult aggregating previous validation.
            
        Returns:
            Normalized quality score (0-1).
        """
        # Start with base score
        quality_score = 0.5
        adjustments = []
        
        # Get validation weights from config
        weights = self.config.get('validation_weights', {
            'required_fields': 0.2,
            'location': 0.15,
            'market_sector': 0.15,
            'contact_info': 0.1,
            'duplicates': 0.15,
            'project_timeline': 0.1,
            'project_intent': 0.15
        })
        
        # If we have validation_results from previous steps, use confidence adjustment
        if validation_results:
            quality_score += validation_results.confidence_adjustment
            
            # Already validated, just adjust based on confidence and weights
            confidence = lead.confidence_score or 0.5
            quality_score += (confidence - 0.5) * 0.3  # Confidence influences quality
        else:
            # Perform lightweight quality evaluation without running full validation
            
            # Required fields
            if not lead.title or not lead.description:
                adjustments.append(-0.2 * weights['required_fields'])
            else:
                title_len_factor = min(1.0, len(lead.title) / 20)  # Scale up to 20 chars
                desc_len_factor = min(1.0, len(lead.description) / 100)  # Scale up to 100 chars
                adjustments.append(0.5 * (title_len_factor + desc_len_factor) * weights['required_fields'])
            
            # Location
            if lead.location and self.target_markets:
                in_target = any(market.lower() in lead.location.lower() for market in self.target_markets)
                adjustments.append((0.2 if in_target else -0.1) * weights['location'])
            
            # Market sector
            if lead.project_type and self.target_sectors:
                in_target = any(sector.lower() in lead.project_type.lower() for sector in self.target_sectors)
                adjustments.append((0.2 if in_target else -0.1) * weights['market_sector'])
            
            # Contact info
            if hasattr(lead, 'contacts') and lead.contacts:
                adjustments.append(0.15 * weights['contact_info'])
            
            # Project timeline
            if lead.published_date:
                if isinstance(lead.published_date, str):
                    try:
                        from dateutil import parser
                        published_date = parser.parse(lead.published_date)
                    except (ValueError, TypeError):
                        published_date = None
                else:
                    published_date = lead.published_date
                
                if published_date:
                    days_old = (datetime.now() - published_date).days
                    if 0 <= days_old <= 14:  # Fresh content bonus
                        adjustments.append((0.2 * (1 - days_old/14)) * weights['project_timeline'])
                    elif days_old < 0:  # Future date penalty
                        adjustments.append(-0.1 * weights['project_timeline'])
                    else:  # Older content penalty
                        adjustments.append((-0.1 * min(days_old/30, 1)) * weights['project_timeline'])
            
            # Use confidence score as proxy for other quality factors
            confidence = lead.confidence_score or 0.5
            adjustments.append((confidence - 0.5) * 0.3)  # Confidence influences quality
        
        # Apply adjustments
        for adj in adjustments:
            quality_score += adj
        
        # Clamp to [0, 1] range
        quality_score = max(0.0, min(1.0, quality_score))
        
        return quality_score
    
    def _store_validation_result(self, 
                               lead: Lead, 
                               validation_results: ValidationResult,
                               adjusted_confidence: float,
                               quality_score: float) -> None:
        """
        Store validation result for learning and improvement.
        
        Args:
            lead: The validated Lead.
            validation_results: Validation results.
            adjusted_confidence: Adjusted confidence score.
            quality_score: Calculated quality score.
        """
        # Add to validation history cache
        validation_record = {
            'lead_id': lead.id,
            'title': lead.title,
            'is_valid': validation_results.is_valid,
            'original_confidence': lead.confidence_score,
            'adjusted_confidence': adjusted_confidence,
            'quality_score': quality_score,
            'timestamp': datetime.now().isoformat(),
            'message_count': len(validation_results.messages)
        }
        
        self.validation_history.append(validation_record)
        
        # Limit history size
        max_history = 1000
        if len(self.validation_history) > max_history:
            self.validation_history = self.validation_history[-max_history:]
        
        # In a full implementation, we might:
        # 1. Periodically save validation history for analysis
        # 2. Track validation rule effectiveness
        # 3. Use feedback to automatically adjust thresholds
    
    def _generate_lead_fingerprint(self, lead: Lead) -> str:
        """
        Generate a fingerprint for a lead to use in caching and duplicate detection.
        
        Args:
            lead: The lead to generate a fingerprint for.
            
        Returns:
            A string fingerprint.
        """
        # Create a fingerprint using key fields
        # This is a simplified version - could be improved with more sophisticated hashing
        key_parts = [
            lead.title or '',
            lead.description[:100] if lead.description else '',
            lead.organization or '',
            lead.location or '',
            lead.project_type or '',
            str(lead.project_value or '')
        ]
        
        fingerprint = '_'.join(key_parts)
        import hashlib
        return hashlib.md5(fingerprint.encode('utf-8')).hexdigest()
    
    def _calculate_lead_similarity(self, lead1: Lead, lead2: Lead) -> float:
        """
        Calculate similarity between two leads.
        
        Args:
            lead1: First lead.
            lead2: Second lead.
            
        Returns:
            Similarity score between 0 and 1.
        """
        # Helper function to tokenize text
        def tokenize(text):
            if not text:
                return set()
            return set(text.lower().split())
        
        # Get tokens from key fields
        lead1_tokens = tokenize(lead1.title or '') | tokenize(lead1.description[:500] if lead1.description else '')
        lead2_tokens = tokenize(lead2.title or '') | tokenize(lead2.description[:500] if lead2.description else '')
        
        # Add other key fields
        for field in [lead1.organization, lead1.location, lead1.project_type]:
            if field:
                lead1_tokens |= tokenize(field)
        
        for field in [lead2.organization, lead2.location, lead2.project_type]:
            if field:
                lead2_tokens |= tokenize(field)
        
        # Calculate Jaccard similarity
        if not lead1_tokens or not lead2_tokens:
            return 0.0
        
        intersection = len(lead1_tokens & lead2_tokens)
        union = len(lead1_tokens | lead2_tokens)
        
        return intersection / union if union > 0 else 0.0
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
NLP Processor Module

Provides natural language processing capabilities for analyzing construction leads,
extracting entities, classifying content, and assessing relevance.
"""

import os
import re
import json
import logging
import unicodedata
import time
from typing import Dict, List, Set, Tuple, Optional, Any, Pattern, Match, Union
from datetime import datetime, date
from pathlib import Path
import html
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import warnings

import spacy
from spacy.tokens import Doc, Span, Token
from spacy.language import Language
from spacy.matcher import Matcher, PhraseMatcher
from spacy.pipeline import EntityRuler
import nltk
from nltk.tokenize import sent_tokenize
from bs4 import BeautifulSoup

from perera_lead_scraper.config import config
from perera_lead_scraper.models.lead import MarketSector

# Configure logger
logger = logging.getLogger(__name__)

# Download required NLTK resources if not already available
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

# Constants
DEFAULT_MODEL = "en_core_web_lg"
CONFIG_DIR = Path(config.CONFIG_DIR)
CONSTRUCTION_ENTITIES_FILE = CONFIG_DIR / "construction_entities.json"
KEYWORDS_FILE = CONFIG_DIR / "keywords.json"
TARGET_MARKETS_FILE = CONFIG_DIR / "target_locations.json"

# Default timeouts
DEFAULT_TIMEOUT = 30  # seconds

# Custom entity types
PROJECT_TYPE = "PROJECT_TYPE"
BUILDING_TYPE = "BUILDING_TYPE"
MATERIAL = "MATERIAL"
CONSTRUCTION_PHASE = "CONSTRUCTION_PHASE"
PROJECT_SCOPE = "PROJECT_SCOPE"
CONSTRUCTION_ROLE = "CONSTRUCTION_ROLE"

# Singleton lock for thread safety during initialization
_nlp_lock = Lock()


class NLPError(Exception):
    """Base exception class for NLP-related errors."""
    pass


class TextPreprocessingError(NLPError):
    """Exception raised for errors in text preprocessing."""
    pass


class EntityExtractionError(NLPError):
    """Exception raised for errors in entity extraction."""
    pass


class ClassificationError(NLPError):
    """Exception raised for errors in content classification."""
    pass


class ProcessingTimeoutError(NLPError):
    """Exception raised when processing exceeds timeout limit."""
    pass


@Language.factory("construction_entities")
class ConstructionEntityComponent:
    """
    Custom spaCy pipeline component for construction-specific entities.
    
    This component adds construction-specific entity recognition capabilities to
    the spaCy pipeline using pattern matching and rule-based approaches.
    """
    
    def __init__(self, nlp: Language, name: str) -> None:
        """
        Initialize the component.
        
        Args:
            nlp: The spaCy language pipeline
            name: Name of the component
        """
        self.nlp = nlp
        self.name = name
        self.matcher = Matcher(nlp.vocab)
        self.phrase_matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
        self._load_patterns()
    
    def _load_patterns(self) -> None:
        """Load construction-specific patterns from configuration."""
        # Default patterns if file doesn't exist
        default_patterns = {
            PROJECT_TYPE: [
                "new construction", "renovation", "expansion", "remodel", 
                "tenant improvement", "infrastructure", "maintenance",
                "demolition", "retrofit", "addition", "rebuild"
            ],
            BUILDING_TYPE: [
                "hospital", "medical center", "school", "university", 
                "office building", "retail", "warehouse", "data center",
                "laboratory", "hotel", "apartment complex", "stadium",
                "power plant", "substation", "treatment plant", "factory"
            ],
            MATERIAL: [
                "concrete", "steel", "glass", "wood", "masonry", "brick", "aluminum",
                "copper", "plastic", "asphalt", "ceramic", "composite", "titanium"
            ],
            CONSTRUCTION_PHASE: [
                "planning", "design", "bidding", "permitting", "pre-construction",
                "construction", "closeout", "commissioning", "completion"
            ],
            PROJECT_SCOPE: [
                "square feet", "sq ft", "ft²", "acres", "stories",
                "units", "beds", "rooms", "parking spaces", "floors"
            ],
            CONSTRUCTION_ROLE: [
                "architect", "engineer", "contractor", "subcontractor", "developer",
                "owner", "project manager", "consultant", "construction manager",
                "designer", "supplier", "inspector", "estimator"
            ]
        }
        
        patterns = default_patterns
        
        # Try to load patterns from file
        if CONSTRUCTION_ENTITIES_FILE.exists():
            try:
                with open(CONSTRUCTION_ENTITIES_FILE, "r", encoding="utf-8") as f:
                    patterns = json.load(f)
                logger.info(f"Loaded construction entity patterns from {CONSTRUCTION_ENTITIES_FILE}")
            except Exception as e:
                logger.warning(f"Failed to load construction entity patterns: {str(e)}")
        
        # Add patterns to matchers
        for entity_type, terms in patterns.items():
            # Add phrase matcher patterns
            phrases = list(self.nlp.tokenizer.pipe(terms))
            self.phrase_matcher.add(entity_type, phrases)
            
            # Add regex patterns for more complex matching
            if entity_type == PROJECT_SCOPE:
                self.matcher.add(
                    "PROJECT_SCOPE_SIZE", 
                    [
                        [{"LIKE_NUM": True}, {"LOWER": {"IN": ["square", "sq"]}}, {"LOWER": {"IN": ["feet", "foot", "ft"]}}],
                        [{"LIKE_NUM": True}, {"LOWER": "sf"}],
                        [{"LIKE_NUM": True}, {"LOWER": {"IN": ["story", "stories"]}}],
                        [{"LIKE_NUM": True}, {"LOWER": {"IN": ["unit", "units"]}}],
                        [{"LIKE_NUM": True}, {"LOWER": {"IN": ["bed", "beds"]}}],
                        [{"LIKE_NUM": True}, {"LOWER": {"IN": ["acre", "acres"]}}],
                        [{"LIKE_NUM": True}, {"TEXT": "-"}, {"LIKE_NUM": True}, {"LOWER": {"IN": ["square", "sq"]}}, {"LOWER": {"IN": ["feet", "foot", "ft"]}}],
                    ]
                )
    
    def __call__(self, doc: Doc) -> Doc:
        """
        Apply the component to a Doc.
        
        Args:
            doc: The document to process
        
        Returns:
            Doc: The processed document
        """
        # Apply phrase matcher
        matches = self.phrase_matcher(doc)
        
        # Apply regex matcher
        regex_matches = self.matcher(doc)
        
        # Process both match types
        spans = []
        for match_id, start, end in matches + regex_matches:
            # Get entity label from match ID
            if isinstance(match_id, int):
                label = self.nlp.vocab.strings[match_id]
            else:
                label = match_id
            
            # Create span
            span = Span(doc, start, end, label=label)
            spans.append(span)
        
        # Add spans to document
        if spans:
            # Filter out overlapping spans by prioritizing longer ones
            filtered_spans = spacy.util.filter_spans(spans)
            doc.ents = tuple(filtered_spans) + doc.ents
        
        return doc


class NLPProcessor:
    """
    Natural Language Processing tools for construction lead analysis.
    
    This class provides methods for extracting relevant information from
    construction project descriptions, including entities, locations, dates,
    and market sectors. It also includes tools for assessing relevance and
    generating summaries.
    """
    
    def __init__(
        self, 
        model_name: str = DEFAULT_MODEL,
        load_construction_entities: bool = True,
        load_keywords: bool = True,
        load_target_markets: bool = True,
        timeout: int = DEFAULT_TIMEOUT
    ) -> None:
        """
        Initialize the NLP processor.
        
        Args:
            model_name: Name of the spaCy model to use
            load_construction_entities: Whether to load construction entity patterns
            load_keywords: Whether to load keywords from configuration
            load_target_markets: Whether to load target markets from configuration
            timeout: Default timeout for operations in seconds
        """
        self.model_name = model_name
        self.timeout = timeout
        
        # Load spaCy model with thread safety
        with _nlp_lock:
            try:
                self.nlp = self._load_spacy_model(model_name)
                logger.info(f"Loaded spaCy model: {model_name}")
            except Exception as e:
                logger.error(f"Failed to load spaCy model {model_name}: {str(e)}")
                # Fall back to a simpler model if available
                try:
                    self.nlp = self._load_spacy_model("en_core_web_sm")
                    logger.warning(f"Falling back to en_core_web_sm model")
                except Exception:
                    # Last resort - create a blank English model
                    self.nlp = spacy.blank("en")
                    logger.error("Falling back to blank English model")
        
        # Add custom components to pipeline
        if load_construction_entities and "construction_entities" not in self.nlp.pipe_names:
            self.nlp.add_pipe("construction_entities", last=True)
            logger.info("Added construction entities component to pipeline")
        
        # Load keywords from configuration
        self.keywords: Dict[str, List[str]] = {}
        if load_keywords:
            self._load_keywords()
        
        # Load target markets
        self.target_markets: Dict[str, Dict[str, Any]] = {}
        if load_target_markets:
            self._load_target_markets()
        
        # Precompile regex patterns
        self.money_pattern = re.compile(r'[\$£€¥]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?:million|m|billion|b|thousand|k)?(?:\s*(?:dollars|usd|gbp|eur|euro?s?|pounds|rupees|yuan|yen))?', re.IGNORECASE)
        self.size_pattern = re.compile(r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?:square\s*(?:feet|foot|ft)|sq\s*(?:ft|feet|foot)|ft²|sf|acres?|hectares?)', re.IGNORECASE)
        self.date_pattern = re.compile(r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{2,4}|\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{2,4})\b', re.IGNORECASE)
    
    def _load_spacy_model(self, model_name: str) -> Language:
        """
        Load a spaCy model with timeout handling.
        
        Args:
            model_name: Name of the model to load
        
        Returns:
            Language: Loaded spaCy model
        
        Raises:
            ProcessingTimeoutError: If loading times out
            ValueError: If model loading fails
        """
        try:
            # First, check if the model is installed
            if not spacy.util.is_package(model_name):
                logger.warning(f"spaCy model {model_name} is not installed. Downloading...")
                import subprocess
                subprocess.check_call([sys.executable, "-m", "spacy", "download", model_name])
            
            # Load the model with a timeout
            import signal
            
            def timeout_handler(signum, frame):
                raise ProcessingTimeoutError(f"Loading model {model_name} timed out after {self.timeout} seconds")
            
            # Set timeout
            prev_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self.timeout)
            
            try:
                # Load model
                nlp = spacy.load(model_name)
                
                # Optimize for construction text analysis
                # Disable unnecessary components for performance
                if 'ner' not in nlp.pipe_names:
                    logger.warning(f"Model {model_name} does not have NER component")
                
                return nlp
            finally:
                # Reset timeout
                signal.alarm(0)
                signal.signal(signal.SIGALRM, prev_handler)
        
        except ImportError:
            logger.error(f"spaCy model {model_name} is not available")
            raise ValueError(f"spaCy model {model_name} is not available")
        except ProcessingTimeoutError:
            logger.error(f"Loading model {model_name} timed out")
            raise
        except Exception as e:
            logger.error(f"Error loading spaCy model {model_name}: {str(e)}")
            raise ValueError(f"Failed to load spaCy model: {str(e)}")
    
    def _load_keywords(self) -> None:
        """Load keywords from configuration."""
        # Default keywords if file doesn't exist
        default_keywords = {
            "healthcare": [
                "hospital", "medical center", "clinic", "healthcare facility",
                "patient tower", "medical office", "ambulatory", "treatment center",
                "emergency room", "operating room", "pharmacy", "rehabilitation",
                "long-term care", "nursing home", "assisted living"
            ],
            "education": [
                "school", "university", "college", "campus", "classroom",
                "educational facility", "dormitory", "student housing", "academic",
                "laboratory", "research facility", "library", "administrative building",
                "student center", "athletic facility"
            ],
            "energy": [
                "power plant", "utility", "renewable energy", "solar", "wind farm",
                "energy facility", "substation", "transmission", "grid", "generation",
                "battery storage", "nuclear", "hydroelectric", "geothermal",
                "biomass", "cogeneration"
            ],
            "utilities": [
                "water treatment", "sewage", "wastewater", "pipeline", "pump station",
                "distribution center", "electrical substation", "gas line",
                "communications infrastructure", "telecom", "data center", "fiber optic"
            ],
            "commercial": [
                "office building", "retail", "shopping center", "mall", "hotel",
                "restaurant", "mixed-use", "warehouse", "industrial park",
                "logistics center", "manufacturing facility", "distribution center",
                "corporate campus", "business park"
            ],
            "entertainment": [
                "stadium", "arena", "theater", "performing arts", "museum",
                "gallery", "convention center", "exhibition hall", "entertainment venue",
                "theme park", "amusement park", "amphitheater", "concert hall",
                "cinema", "recreational facility"
            ]
        }
        
        # Try to load keywords from file
        if KEYWORDS_FILE.exists():
            try:
                with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
                    self.keywords = json.load(f)
                logger.info(f"Loaded keywords from {KEYWORDS_FILE}")
            except Exception as e:
                logger.warning(f"Failed to load keywords: {str(e)}")
                self.keywords = default_keywords
        else:
            self.keywords = default_keywords
            logger.info("Using default keywords")
    
    def _load_target_markets(self) -> None:
        """Load target markets from configuration."""
        # Default target markets if file doesn't exist
        default_target_markets = {
            "southern_california": {
                "states": ["CA", "California"],
                "counties": [
                    "Los Angeles", "Orange", "San Diego", "Riverside", 
                    "San Bernardino", "Ventura", "Imperial"
                ],
                "cities": [
                    "Los Angeles", "San Diego", "Irvine", "Anaheim", "Long Beach",
                    "Santa Ana", "Riverside", "San Bernardino", "Oxnard", "Fontana",
                    "Huntington Beach", "Moreno Valley", "Santa Clarita", "Ontario",
                    "Garden Grove", "Oceanside", "Rancho Cucamonga", "Corona", "Lancaster",
                    "Palmdale", "Pomona", "Torrance", "Pasadena", "Orange", "Fullerton",
                    "Costa Mesa", "Victorville", "Santa Monica", "Burbank", "Newport Beach"
                ]
            },
            "northern_california": {
                "states": ["CA", "California"],
                "counties": [
                    "San Francisco", "San Mateo", "Santa Clara", "Alameda",
                    "Contra Costa", "Sacramento", "San Joaquin", "Marin", "Sonoma"
                ],
                "cities": [
                    "San Francisco", "San Jose", "Sacramento", "Oakland", "Fremont",
                    "Santa Rosa", "Sunnyvale", "Concord", "Santa Clara", "Berkeley",
                    "Fairfield", "Hayward", "Vallejo", "Richmond", "Antioch",
                    "Palo Alto", "Cupertino", "Mountain View", "Napa", "Redwood City"
                ]
            }
        }
        
        # Try to load target markets from file
        if TARGET_MARKETS_FILE.exists():
            try:
                with open(TARGET_MARKETS_FILE, "r", encoding="utf-8") as f:
                    self.target_markets = json.load(f)
                logger.info(f"Loaded target markets from {TARGET_MARKETS_FILE}")
            except Exception as e:
                logger.warning(f"Failed to load target markets: {str(e)}")
                self.target_markets = default_target_markets
        else:
            self.target_markets = default_target_markets
            logger.info("Using default target markets")
    
    def preprocess_text(self, text: str) -> str:
        """
        Clean and normalize input text.
        
        This method performs several preprocessing operations:
        - Removes HTML tags
        - Normalizes whitespace
        - Handles encoding issues
        - Converts unicode characters to ASCII where possible
        - Segments large documents for processing
        
        Args:
            text: Raw text to preprocess
        
        Returns:
            str: Preprocessed text ready for NLP analysis
        
        Raises:
            TextPreprocessingError: If preprocessing fails
        """
        if not text:
            return ""
        
        try:
            # Convert to string if not already
            text = str(text)
            
            # Remove HTML tags
            try:
                soup = BeautifulSoup(text, 'html.parser')
                text = soup.get_text()
            except:
                # Fallback to regex-based HTML removal
                text = re.sub(r'<[^>]+>', ' ', text)
            
            # Decode HTML entities
            text = html.unescape(text)
            
            # Normalize unicode characters
            text = unicodedata.normalize('NFKD', text)
            
            # Handle encoding issues - replace problematic characters
            text = text.encode('ascii', 'replace').decode('ascii')
            
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text).strip()
            
            # Replace common abbreviations
            abbreviations = {
                'sq ft': 'square feet',
                'sq. ft.': 'square feet',
                'sqft': 'square feet',
                'SF': 'square feet',
                'cu ft': 'cubic feet',
                'cu. ft.': 'cubic feet',
                'cf': 'cubic feet',
                'CF': 'cubic feet',
                'lin ft': 'linear feet',
                'LF': 'linear feet',
                'sq m': 'square meters',
                'sq. m.': 'square meters',
                'TI': 'tenant improvement',
                'CM': 'construction management',
                'GC': 'general contractor',
                'M&E': 'mechanical and electrical',
                'MEP': 'mechanical, electrical, and plumbing',
                'HVAC': 'heating, ventilation, and air conditioning',
                'CY': 'cubic yards',
                'B/L': 'building',
                'bldg': 'building',
                'const': 'construction',
                'constr': 'construction',
                'dev': 'development',
                'dept': 'department',
                'fndtn': 'foundation',
                'med': 'medical',
                'hosp': 'hospital'
            }
            
            for abbr, full in abbreviations.items():
                text = re.sub(r'\b' + re.escape(abbr) + r'\b', full, text, flags=re.IGNORECASE)
            
            return text
            
        except Exception as e:
            logger.error(f"Error preprocessing text: {str(e)}")
            raise TextPreprocessingError(f"Failed to preprocess text: {str(e)}")
    
    def _process_with_timeout(self, func, *args, **kwargs):
        """
        Execute a function with a timeout.
        
        Args:
            func: Function to execute
            *args: Arguments to pass to the function
            **kwargs: Keyword arguments to pass to the function
        
        Returns:
            Any: Result of the function
        
        Raises:
            ProcessingTimeoutError: If execution times out
        """
        import signal
        
        def timeout_handler(signum, frame):
            raise ProcessingTimeoutError(f"Processing timed out after {self.timeout} seconds")
        
        # Set timeout
        prev_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(self.timeout)
        
        try:
            # Execute function
            result = func(*args, **kwargs)
            return result
        finally:
            # Reset timeout
            signal.alarm(0)
            signal.signal(signal.SIGALRM, prev_handler)
    
    def _process_text_in_chunks(self, text: str, chunk_size: int = 5000) -> List[Doc]:
        """
        Process long text in chunks to avoid memory issues.
        
        Args:
            text: Text to process
            chunk_size: Maximum size of each chunk in characters
        
        Returns:
            List[Doc]: List of processed spaCy Doc objects
        """
        # For short texts, process as a single chunk
        if len(text) <= chunk_size:
            return [self.nlp(text)]
        
        # Split text into sentences
        sentences = sent_tokenize(text)
        
        # Group sentences into chunks
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            if current_length + len(sentence) > chunk_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_length = len(sentence)
            else:
                current_chunk.append(sentence)
                current_length += len(sentence)
        
        # Add the last chunk if it's not empty
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        # Process each chunk
        with ThreadPoolExecutor(max_workers=min(4, len(chunks))) as executor:
            doc_chunks = list(executor.map(self.nlp, chunks))
        
        return doc_chunks
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """
        Extract entities from text.
        
        This method identifies various entity types including:
        - Organizations: Construction companies, developers, architects
        - People: Project stakeholders, contacts
        - Locations: Project sites, cities, regions
        - Money: Budget figures, costs
        - Dates: Project timelines, deadlines
        - Construction-specific entities:
          - PROJECT_TYPE: New construction, renovation, etc.
          - BUILDING_TYPE: Hospital, school, office building, etc.
          - MATERIAL: Concrete, steel, etc.
          - CONSTRUCTION_PHASE: Planning, design, etc.
          - PROJECT_SCOPE: Square footage, units, etc.
          - CONSTRUCTION_ROLE: Architect, contractor, etc.
        
        Args:
            text: Text to extract entities from
        
        Returns:
            Dict[str, List[str]]: Dictionary of entity types and their occurrences
        
        Raises:
            EntityExtractionError: If entity extraction fails
        """
        if not text:
            return {}
        
        try:
            # Preprocess text
            text = self.preprocess_text(text)
            
            # Process in chunks if needed
            processed_chunks = self._process_with_timeout(
                self._process_text_in_chunks, text
            )
            
            # Initialize result dictionary
            entities = {
                "ORG": [],
                "PERSON": [],
                "GPE": [],  # Cities, states, countries
                "LOC": [],  # Non-GPE locations
                "MONEY": [],
                "DATE": [],
                PROJECT_TYPE: [],
                BUILDING_TYPE: [],
                MATERIAL: [],
                CONSTRUCTION_PHASE: [],
                PROJECT_SCOPE: [],
                CONSTRUCTION_ROLE: []
            }
            
            # Extract entities from each chunk
            for doc in processed_chunks:
                for ent in doc.ents:
                    if ent.label_ in entities:
                        # Normalize entity text
                        entity_text = ent.text.strip()
                        # Add to results if not already present
                        if entity_text not in entities[ent.label_]:
                            entities[ent.label_].append(entity_text)
            
            # Extract additional entities using regex
            money_matches = self.money_pattern.findall(text)
            for match in money_matches:
                money_text = match.strip()
                # Only add if not already present and not just a single number
                if money_text not in entities["MONEY"] and re.search(r'[mb]illion|thousand|[a-z]', money_text, re.IGNORECASE):
                    entities["MONEY"].append(money_text)
            
            # Extract size information
            size_matches = self.size_pattern.findall(text)
            for match in size_matches:
                size_text = match.strip()
                if size_text not in entities[PROJECT_SCOPE]:
                    entities[PROJECT_SCOPE].append(size_text)
            
            # Return only entity types that have values
            return {k: v for k, v in entities.items() if v}
            
        except ProcessingTimeoutError:
            logger.error(f"Entity extraction timed out for text: {text[:100]}...")
            raise
            
        except Exception as e:
            logger.error(f"Error extracting entities: {str(e)}")
            raise EntityExtractionError(f"Failed to extract entities: {str(e)}")
    
    def extract_locations(self, text: str) -> List[str]:
        """
        Identify and normalize location references in text.
        
        This method extracts geographic locations from text, normalizes them,
        and validates them against our target markets.
        
        Args:
            text: Text to extract locations from
        
        Returns:
            List[str]: List of normalized, validated locations
        
        Raises:
            EntityExtractionError: If location extraction fails
        """
        if not text:
            return []
        
        try:
            # Preprocess text
            text = self.preprocess_text(text)
            
            # Process in chunks if needed
            processed_chunks = self._process_with_timeout(
                self._process_text_in_chunks, text
            )
            
            # Extract location entities
            locations = []
            
            for doc in processed_chunks:
                for ent in doc.ents:
                    if ent.label_ in ("GPE", "LOC"):
                        location = ent.text.strip()
                        locations.append(location)
            
            # Normalize and validate locations
            normalized_locations = []
            for location in locations:
                normalized = self._normalize_location(location)
                if normalized and self._validate_against_target_markets(normalized):
                    if normalized not in normalized_locations:
                        normalized_locations.append(normalized)
            
            return normalized_locations
            
        except ProcessingTimeoutError:
            logger.error(f"Location extraction timed out for text: {text[:100]}...")
            raise
            
        except Exception as e:
            logger.error(f"Error extracting locations: {str(e)}")
            raise EntityExtractionError(f"Failed to extract locations: {str(e)}")
    
    def _normalize_location(self, location: str) -> str:
        """
        Normalize location names.
        
        Args:
            location: Location name to normalize
        
        Returns:
            str: Normalized location name
        """
        # Convert to uppercase for state abbreviations, but lowercase otherwise
        location = location.strip()
        
        # State abbreviation normalization
        state_mapping = {
            "CA": "California",
            "AZ": "Arizona",
            "NV": "Nevada",
            "OR": "Oregon",
            "WA": "Washington",
            "TX": "Texas",
            "FL": "Florida",
            "NY": "New York",
            "IL": "Illinois",
            "CO": "Colorado",
            "CALIF": "California",
            "CALIFORNIA": "California",
            "ARIZ": "Arizona",
            "ARIZONA": "Arizona",
            "NEV": "Nevada",
            "NEVADA": "Nevada",
            "CALI": "California",
            "CAL": "California"
        }
        
        # Check if the location is a state abbreviation
        if location.upper() in state_mapping:
            return state_mapping[location.upper()]
        
        # City normalization
        city_mapping = {
            "LA": "Los Angeles",
            "SF": "San Francisco",
            "SAN FRAN": "San Francisco",
            "OC": "Orange County",
            "SD": "San Diego",
            "LB": "Long Beach"
        }
        
        if location.upper() in city_mapping:
            return city_mapping[location.upper()]
        
        # Handle common prefixes/suffixes
        if location.lower().endswith(" county"):
            location = location[:-7]  # Remove " county" suffix
        
        if location.lower().startswith("city of "):
            location = location[8:]  # Remove "city of " prefix
        
        # Title case for city and county names
        location_words = location.split()
        if len(location_words) <= 3:  # Only normalize short names to avoid changing organization names
            location = " ".join(word.capitalize() for word in location_words)
        
        return location
    
    def _validate_against_target_markets(self, location: str) -> bool:
        """
        Check if a location is within our target markets.
        
        Args:
            location: Normalized location name
        
        Returns:
            bool: True if the location is in our target markets, False otherwise
        """
        location = location.strip()
        location_lower = location.lower()
        
        # Check each target market
        for market, details in self.target_markets.items():
            # Check states
            for state in details.get("states", []):
                if location == state or location_lower == state.lower():
                    return True
            
            # Check counties
            for county in details.get("counties", []):
                county_pattern = fr'\b{re.escape(county)}\b'
                if (location == county or 
                    location_lower == county.lower() or
                    re.search(county_pattern, location, re.IGNORECASE)):
                    return True
            
            # Check cities
            for city in details.get("cities", []):
                city_pattern = fr'\b{re.escape(city)}\b'
                if (location == city or 
                    location_lower == city.lower() or
                    re.search(city_pattern, location, re.IGNORECASE)):
                    return True
        
        # Check generic California/SoCal terms
        socal_terms = ["southern california", "socal", "southland", "south california", "california", "los angeles area", "orange county area", "san diego area"]
        if any(term == location_lower or term in location_lower for term in socal_terms):
            return True
        
        return False
    
    def extract_project_values(self, text: str) -> Dict[str, Any]:
        """
        Extract monetary values and project scope information.
        
        This method identifies:
        - Project budgets and costs
        - Square footage
        - Unit counts
        - Other size/scope metrics
        
        Args:
            text: Text to extract values from
        
        Returns:
            Dict[str, Any]: Dictionary containing extracted values
        
        Raises:
            EntityExtractionError: If extraction fails
        """
        if not text:
            return {}
        
        try:
            # Preprocess text
            text = self.preprocess_text(text)
            
            # Initialize result
            result = {
                "monetary_values": [],
                "square_footage": None,
                "units": None,
                "stories": None,
                "acres": None,
                "estimated_value": None
            }
            
            # Extract monetary values
            money_matches = list(self.money_pattern.finditer(text))
            
            for match in money_matches:
                money_text = match.group(0)
                
                # Capture monetary values
                result["monetary_values"].append(money_text)
                
                # Try to convert to numeric value
                try:
                    numeric_value = self._parse_money_value(money_text)
                    if numeric_value:
                        if result["estimated_value"] is None or numeric_value > result["estimated_value"]:
                            result["estimated_value"] = numeric_value
                except:
                    pass
            
            # Extract square footage
            sf_pattern = re.compile(r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*(?:square\s*(?:feet|foot|ft)|sq\s*(?:ft|feet|foot)|ft²|sf)', re.IGNORECASE)
            sf_matches = list(sf_pattern.finditer(text))
            
            if sf_matches:
                sf_text = sf_matches[0].group(0)
                try:
                    sf_value = self._parse_numeric_value(sf_matches[0].group(1))
                    result["square_footage"] = sf_value
                except:
                    result["square_footage"] = sf_text
            
            # Extract units
            units_pattern = re.compile(r'(\d{1,3}(?:,\d{3})*|\d+)\s*(?:units|unit|rooms|room|beds|bed|apartments|apartment)', re.IGNORECASE)
            units_matches = list(units_pattern.finditer(text))
            
            if units_matches:
                units_text = units_matches[0].group(0)
                try:
                    units_value = self._parse_numeric_value(units_matches[0].group(1))
                    result["units"] = units_value
                except:
                    result["units"] = units_text
            
            # Extract stories
            stories_pattern = re.compile(r'(\d{1,2})\s*(?:-|to)?\s*(?:\d{1,2}\s*)?(?:stor(?:y|ies)|floors?|levels?)', re.IGNORECASE)
            stories_matches = list(stories_pattern.finditer(text))
            
            if stories_matches:
                stories_text = stories_matches[0].group(0)
                try:
                    stories_value = int(stories_matches[0].group(1))
                    result["stories"] = stories_value
                except:
                    result["stories"] = stories_text
            
            # Extract acres
            acres_pattern = re.compile(r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s*acres?', re.IGNORECASE)
            acres_matches = list(acres_pattern.finditer(text))
            
            if acres_matches:
                acres_text = acres_matches[0].group(0)
                try:
                    acres_value = self._parse_numeric_value(acres_matches[0].group(1))
                    result["acres"] = acres_value
                except:
                    result["acres"] = acres_text
            
            # Estimate value if not found explicitly
            if result["estimated_value"] is None:
                result["estimated_value"] = self._estimate_project_value(result, text)
            
            # Remove None values
            return {k: v for k, v in result.items() if v is not None}
            
        except Exception as e:
            logger.error(f"Error extracting project values: {str(e)}")
            raise EntityExtractionError(f"Failed to extract project values: {str(e)}")
    
    def _parse_money_value(self, money_text: str) -> Optional[float]:
        """
        Parse a monetary value from text.
        
        Args:
            money_text: Text containing a monetary value
        
        Returns:
            Optional[float]: Parsed monetary value or None if parsing fails
        """
        # Remove currency symbols and commas
        cleaned_text = re.sub(r'[\$£€¥,]', '', money_text)
        
        # Extract the numeric part
        match = re.search(r'(\d+(?:\.\d+)?)', cleaned_text)
        if not match:
            return None
        
        value = float(match.group(1))
        
        # Check for multipliers
        if 'million' in cleaned_text.lower() or 'm' in cleaned_text.lower():
            value *= 1000000
        elif 'billion' in cleaned_text.lower() or 'b' in cleaned_text.lower():
            value *= 1000000000
        elif 'thousand' in cleaned_text.lower() or 'k' in cleaned_text.lower():
            value *= 1000
        
        return value
    
    def _parse_numeric_value(self, value_text: str) -> float:
        """
        Parse a numeric value from text.
        
        Args:
            value_text: Text containing a numeric value
        
        Returns:
            float: Parsed numeric value
        """
        # Remove commas and convert to float
        return float(value_text.replace(',', ''))
    
    def _estimate_project_value(self, extracted_values: Dict[str, Any], text: str) -> Optional[float]:
        """
        Estimate project value based on extracted metrics and project type.
        
        Args:
            extracted_values: Dictionary of extracted project metrics
            text: Full text for context
        
        Returns:
            Optional[float]: Estimated project value or None if estimation fails
        """
        # Determine project type
        project_types = self._identify_project_types(text)
        building_types = self._identify_building_types(text)
        
        # Use square footage for estimation if available
        sf = extracted_values.get("square_footage")
        if sf is not None:
            # Default cost per square foot
            cost_per_sf = 300  # General commercial average
            
            # Adjust based on building type
            if "hospital" in building_types or "medical center" in building_types:
                cost_per_sf = 800  # Healthcare is expensive
            elif "school" in building_types or "university" in building_types:
                cost_per_sf = 450  # Educational
            elif "data center" in building_types:
                cost_per_sf = 1200  # Very high for data centers
            elif "warehouse" in building_types or "industrial" in building_types:
                cost_per_sf = 150  # Lower for industrial
            elif "office" in building_types:
                cost_per_sf = 350  # Office buildings
            elif "hotel" in building_types or "residential" in building_types:
                cost_per_sf = 400  # Hotels and multifamily
            
            # Adjust based on project type
            if "renovation" in project_types or "remodel" in project_types:
                cost_per_sf *= 0.7  # Renovations typically cost less than new construction
            elif "tenant improvement" in project_types:
                cost_per_sf *= 0.5  # TIs are usually cheaper
            
            return sf * cost_per_sf
        
        # Use units for estimation if available
        units = extracted_values.get("units")
        if units is not None:
            # Default cost per unit
            cost_per_unit = 250000  # General residential average
            
            # Adjust based on building type
            if "hospital" in building_types:
                cost_per_unit = 1500000  # Hospital beds
            elif "hotel" in building_types:
                cost_per_unit = 200000  # Hotel rooms
            elif "luxury" in text.lower() or "high-end" in text.lower():
                cost_per_unit = 450000  # Luxury apartments
            
            return units * cost_per_unit
        
        # Fall back to generic estimation based on stories
        stories = extracted_values.get("stories")
        if stories is not None:
            # Assume moderate-sized commercial building
            return stories * 5000000  # $5M per floor as a rough estimate
        
        # Cannot estimate
        return None
    
    def _identify_project_types(self, text: str) -> List[str]:
        """
        Identify project types mentioned in text.
        
        Args:
            text: Text to analyze
        
        Returns:
            List[str]: Project types found in the text
        """
        project_types = []
        
        # Common project type terms
        type_terms = [
            "new construction", "renovation", "expansion", "remodel", 
            "tenant improvement", "infrastructure", "maintenance",
            "demolition", "retrofit", "addition", "rebuild"
        ]
        
        # Look for each term
        for term in type_terms:
            if re.search(r'\b' + re.escape(term) + r'\b', text, re.IGNORECASE):
                project_types.append(term)
        
        return project_types
    
    def _identify_building_types(self, text: str) -> List[str]:
        """
        Identify building types mentioned in text.
        
        Args:
            text: Text to analyze
        
        Returns:
            List[str]: Building types found in the text
        """
        building_types = []
        
        # Common building type terms
        type_terms = [
            "hospital", "medical center", "school", "university", 
            "office building", "retail", "warehouse", "data center",
            "laboratory", "hotel", "apartment", "stadium", "residential",
            "power plant", "substation", "treatment plant", "factory",
            "industrial", "commercial"
        ]
        
        # Look for each term
        for term in type_terms:
            if re.search(r'\b' + re.escape(term) + r'\b', text, re.IGNORECASE):
                building_types.append(term)
        
        return building_types
    
    def extract_dates(self, text: str) -> Dict[str, Any]:
        """
        Extract and categorize dates related to project timelines.
        
        This method identifies:
        - Start dates
        - Completion dates
        - Bid dates
        - Permit dates
        - Other timeline information
        
        Args:
            text: Text to extract dates from
        
        Returns:
            Dict[str, Any]: Dictionary of date categories and values
        
        Raises:
            EntityExtractionError: If date extraction fails
        """
        if not text:
            return {}
        
        try:
            # Preprocess text
            text = self.preprocess_text(text)
            
            # Process text with spaCy
            doc = self.nlp(text)
            
            # Initialize result
            result = {
                "start_date": None,
                "completion_date": None,
                "bid_date": None,
                "permit_date": None,
                "publication_date": None,
                "all_dates": []
            }
            
            # Extract dates using spaCy's NER
            for ent in doc.ents:
                if ent.label_ == "DATE":
                    # Add to all dates
                    result["all_dates"].append(ent.text)
                    
                    # Try to categorize the date
                    date_context = text[max(0, ent.start_char - 50):min(len(text), ent.end_char + 50)]
                    
                    if any(term in date_context.lower() for term in ["start", "begin", "commence", "commencing", "break ground", "groundbreaking"]):
                        result["start_date"] = ent.text
                    elif any(term in date_context.lower() for term in ["complete", "completion", "finish", "deliver", "occupancy", "opening"]):
                        result["completion_date"] = ent.text
                    elif any(term in date_context.lower() for term in ["bid", "proposal", "submission", "respond", "rfp", "due date"]):
                        result["bid_date"] = ent.text
                    elif any(term in date_context.lower() for term in ["permit", "approval", "approved", "filing"]):
                        result["permit_date"] = ent.text
                    elif any(term in date_context.lower() for term in ["published", "announced", "release", "article date"]):
                        result["publication_date"] = ent.text
            
            # Extract dates using regex for backup
            date_matches = list(self.date_pattern.finditer(text))
            
            # Add any dates found via regex that weren't already extracted
            for match in date_matches:
                date_text = match.group(0)
                if date_text not in result["all_dates"]:
                    result["all_dates"].append(date_text)
            
            # Try to parse the dates and set phase info
            parsed_dates = {}
            for date_type, date_text in result.items():
                if date_type != "all_dates" and date_text is not None:
                    try:
                        parsed_date = self._parse_date(date_text)
                        if parsed_date:
                            parsed_dates[date_type] = parsed_date.isoformat()
                    except:
                        # Keep the text version if parsing fails
                        parsed_dates[date_type] = date_text
            
            # Add parsed dates to result
            if parsed_dates:
                result["parsed_dates"] = parsed_dates
            
            # Determine project phase based on dates
            result["project_phase"] = self._determine_project_phase(parsed_dates)
            
            # Remove None values
            return {k: v for k, v in result.items() if v is not None and (k != "all_dates" or v)}
            
        except Exception as e:
            logger.error(f"Error extracting dates: {str(e)}")
            raise EntityExtractionError(f"Failed to extract dates: {str(e)}")
    
    def _parse_date(self, date_text: str) -> Optional[datetime]:
        """
        Parse a date from text into a datetime object.
        
        Args:
            date_text: Text containing a date
        
        Returns:
            Optional[datetime]: Parsed date or None if parsing fails
        """
        import dateutil.parser
        
        try:
            # Handle formats like "early 2023" or "mid-2023"
            if re.match(r'(?:early|mid|late)[\s-]+(\d{4})', date_text, re.IGNORECASE):
                year_match = re.search(r'(\d{4})', date_text)
                if year_match:
                    year = int(year_match.group(1))
                    if "early" in date_text.lower():
                        return datetime(year, 3, 1)
                    elif "mid" in date_text.lower():
                        return datetime(year, 6, 1)
                    elif "late" in date_text.lower():
                        return datetime(year, 10, 1)
            
            # Try to parse with dateutil
            return dateutil.parser.parse(date_text)
        except:
            # If parsing fails, return None
            return None
    
    def _determine_project_phase(self, parsed_dates: Dict[str, str]) -> Optional[str]:
        """
        Determine the project phase based on extracted dates.
        
        Args:
            parsed_dates: Dictionary of parsed dates
        
        Returns:
            Optional[str]: Project phase or None if indeterminable
        """
        # Get current date
        today = datetime.now().date()
        
        # Extract and parse dates
        start_date = None
        completion_date = None
        bid_date = None
        
        for date_type, date_str in parsed_dates.items():
            try:
                parsed_date = datetime.fromisoformat(date_str).date()
                
                if date_type == "start_date":
                    start_date = parsed_date
                elif date_type == "completion_date":
                    completion_date = parsed_date
                elif date_type == "bid_date":
                    bid_date = parsed_date
            except:
                pass
        
        # Determine phase
        if bid_date and bid_date > today:
            return "pre-bid"
        elif bid_date and bid_date <= today and (not start_date or start_date > today):
            return "bidding"
        elif start_date and start_date > today:
            return "pre-construction"
        elif start_date and start_date <= today and (not completion_date or completion_date > today):
            return "construction"
        elif completion_date and completion_date <= today:
            return "completed"
        
        # Cannot determine
        return None
    
    def classify_market_sector(self, text: str) -> Tuple[str, float]:
        """
        Classify content into one of our target market sectors.
        
        This method categorizes text into one of the following sectors:
        - Healthcare
        - Education
        - Energy
        - Utilities
        - Commercial
        - Entertainment
        
        Args:
            text: Text to classify
        
        Returns:
            Tuple[str, float]: Tuple containing the sector name and confidence score
        
        Raises:
            ClassificationError: If classification fails
        """
        if not text:
            return (MarketSector.OTHER.value, 0.0)
        
        try:
            # Preprocess text
            text = self.preprocess_text(text)
            
            # Score each sector
            scores = {}
            
            for sector, keywords in self.keywords.items():
                score = self.calculate_relevance_score(text, keywords)
                scores[sector] = score
            
            # Find the highest scoring sector
            if not scores:
                return (MarketSector.OTHER.value, 0.0)
            
            best_sector = max(scores.items(), key=lambda x: x[1])
            sector_name, confidence = best_sector
            
            # Map to MarketSector enum if possible
            try:
                sector_enum = MarketSector(sector_name)
                sector_name = sector_enum.value
            except ValueError:
                # If not in enum, use the string as is
                pass
            
            # Only return a sector if confidence is above threshold
            if confidence < 0.3:
                return (MarketSector.OTHER.value, confidence)
            
            return (sector_name, confidence)
            
        except Exception as e:
            logger.error(f"Error classifying market sector: {str(e)}")
            raise ClassificationError(f"Failed to classify market sector: {str(e)}")
    
    def calculate_relevance_score(self, text: str, keywords: List[str]) -> float:
        """
        Calculate the relevance score for a text based on keywords.
        
        This method implements a sophisticated scoring algorithm that considers:
        - Keyword presence (exact and partial matches)
        - Keyword position (higher weight for earlier occurrences)
        - Semantic similarity to construction terminology
        - Length and frequency of matched terms
        
        Args:
            text: Text to score
            keywords: List of keywords to check against
        
        Returns:
            float: Normalized relevance score (0-1)
        
        Raises:
            ValueError: If inputs are invalid
        """
        if not text or not keywords:
            return 0.0
        
        # Normalize inputs
        text = text.lower()
        normalized_keywords = [k.lower() for k in keywords]
        
        # Initialize score components
        exact_matches = 0
        partial_matches = 0
        positional_score = 0
        
        # Get total text length for position weighting
        text_length = len(text)
        if text_length == 0:
            return 0.0
        
        # Check each keyword
        for keyword in normalized_keywords:
            # Skip empty keywords
            if not keyword:
                continue
            
            # Look for exact matches
            matches = list(re.finditer(r'\b' + re.escape(keyword) + r'\b', text))
            exact_matches += len(matches)
            
            # Calculate positional score (earlier matches get higher weight)
            for match in matches:
                # Position factor (0-1): higher score for matches near the beginning
                position = match.start() / text_length
                position_factor = 1 - (position * 0.7)  # Still give some weight to later matches
                
                # Length factor: longer keyword matches get higher weight
                length_factor = min(1.0, len(keyword) / 20)  # Cap at 20 chars
                
                # Add to positional score
                positional_score += position_factor * length_factor
            
            # Look for partial matches (only if no exact match)
            if not matches and len(keyword) > 4:  # Only consider partial matches for longer keywords
                partial_matches += text.count(keyword)
        
        # Calculate base score components
        if not normalized_keywords:
            return 0.0
            
        exact_score = min(1.0, exact_matches / len(normalized_keywords))
        partial_score = min(0.5, partial_matches / (2 * len(normalized_keywords)))
        positional_score = min(1.0, positional_score / len(normalized_keywords))
        
        # Apply weights to components
        weighted_score = (
            exact_score * 0.6 +
            partial_score * 0.1 +
            positional_score * 0.3
        )
        
        # Add bonus for multiple matches of different keywords
        unique_matches = set()
        for keyword in normalized_keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', text):
                unique_matches.add(keyword)
        
        diversity_factor = min(1.0, len(unique_matches) / min(5, len(normalized_keywords)))
        
        # Apply diversity bonus
        final_score = weighted_score * (1 + (diversity_factor * 0.3))
        
        # Normalize to 0-1 range
        return min(1.0, max(0.0, final_score))
    
    def summarize_content(self, text: str, max_length: int = 200) -> str:
        """
        Create a concise summary highlighting key project details.
        
        This method generates a summary that focuses on the most important
        construction-relevant information in the text.
        
        Args:
            text: Text to summarize
            max_length: Maximum summary length in characters
        
        Returns:
            str: Concise summary
        
        Raises:
            ValueError: If text is empty
        """
        if not text:
            return ""
        
        # Preprocess text
        text = self.preprocess_text(text)
        
        # For short texts, return as is
        if len(text) <= max_length:
            return text
        
        try:
            # Process text with spaCy
            doc = self.nlp(text)
            
            # Extract the most important sentences
            sentences = [sent.text.strip() for sent in doc.sents]
            
            # Score sentences based on relevance
            scored_sentences = []
            
            for i, sentence in enumerate(sentences):
                # Calculate base score
                score = 0
                
                # Check for construction-relevant entities
                sent_doc = self.nlp(sentence)
                construction_entities = [
                    ent for ent in sent_doc.ents 
                    if ent.label_ in [PROJECT_TYPE, BUILDING_TYPE, MATERIAL, PROJECT_SCOPE, "MONEY"]
                ]
                
                # Boost score for sentences with construction entities
                score += len(construction_entities) * 0.5
                
                # Check for market sector keywords
                for sector, keywords in self.keywords.items():
                    for keyword in keywords:
                        if re.search(r'\b' + re.escape(keyword.lower()) + r'\b', sentence.lower()):
                            score += 0.3
                
                # Position bonus (earlier sentences often more important)
                score += max(0, 1 - (i * 0.1))
                
                # Length penalty (avoid very long sentences)
                if len(sentence) > 100:
                    score -= (len(sentence) - 100) / 100
                
                scored_sentences.append((sentence, score))
            
            # Sort by score
            scored_sentences.sort(key=lambda x: x[1], reverse=True)
            
            # Build summary by adding sentences until max_length is reached
            summary = ""
            for sentence, _ in scored_sentences:
                if len(summary) + len(sentence) + 1 <= max_length:
                    if summary:
                        summary += " " + sentence
                    else:
                        summary = sentence
                else:
                    break
            
            # If no sentences were selected, use the first sentence
            if not summary and sentences:
                summary = sentences[0][:max_length]
            
            return summary
            
        except Exception as e:
            logger.error(f"Error summarizing content: {str(e)}")
            # Fallback to first paragraph
            paragraphs = text.split("\n\n")
            return paragraphs[0][:max_length]


# Example usage
if __name__ == "__main__":
    import sys
    
    # Initialize processor
    processor = NLPProcessor()
    
    # Sample text
    sample_text = """
    Construction is set to begin on the new $45 million Santa Monica Medical Center expansion project in July 2023. 
    The 65,000-square-foot facility will include a new emergency department, six operating rooms, and specialized 
    cardiac care units. ABC Construction has been selected as the general contractor, with XYZ Architecture handling 
    design. The project is expected to be completed by October 2024 and will create approximately 200 construction 
    jobs. The three-story building will be located at 1234 Ocean Avenue in Santa Monica, California.
    """
    
    print("Sample text:")
    print(sample_text)
    print("\nEntities:")
    entities = processor.extract_entities(sample_text)
    for entity_type, values in entities.items():
        print(f"  {entity_type}: {values}")
    
    print("\nLocations:")
    locations = processor.extract_locations(sample_text)
    print(locations)
    
    print("\nProject values:")
    values = processor.extract_project_values(sample_text)
    print(values)
    
    print("\nDates:")
    dates = processor.extract_dates(sample_text)
    print(dates)
    
    print("\nMarket sector:")
    sector, confidence = processor.classify_market_sector(sample_text)
    print(f"{sector} (confidence: {confidence:.2f})")
    
    print("\nSummary:")
    summary = processor.summarize_content(sample_text)
    print(summary)
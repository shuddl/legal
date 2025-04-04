#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Legal Document Analyzer for Lead Discovery

This module provides advanced functionality for analyzing legal documents to discover
and extract high-value construction leads. It builds on the basic legal document
processing pipeline and applies specialized analysis techniques to identify
potential project opportunities from permits, contracts, zoning applications,
and regulatory filings.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple, Union
from datetime import datetime, timedelta
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from perera_lead_scraper.config import config, AppConfig
from perera_lead_scraper.utils.timeout import timeout_handler
from perera_lead_scraper.legal.legal_processor import LegalProcessor
from perera_lead_scraper.legal.legal_api import LegalAPI
from perera_lead_scraper.legal.document_parser import DocumentParser
from perera_lead_scraper.legal.document_validator import DocumentValidator
from perera_lead_scraper.nlp.nlp_processor import NLPProcessor
from perera_lead_scraper.models.lead import Lead, MarketSector

# Configure logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_CONFIDENCE_THRESHOLD = 0.6
DEFAULT_VALUE_THRESHOLD = 100000  # $100k minimum project value
MAX_CONCURRENT_PROCESSES = 4
HIGH_PRIORITY_KEYWORDS = [
    "new construction", "development", "redevelopment", "expansion", 
    "renovation", "building", "commercial", "multifamily", "residential",
    "data center", "hospital", "medical", "school", "university",
    "infrastructure", "mixed-use", "office", "retail", "warehouse"
]


class DocumentAnalysisError(Exception):
    """Base exception for document analysis errors."""
    pass


class LeadExtractionError(DocumentAnalysisError):
    """Exception raised when lead extraction fails."""
    pass


class LegalDocumentAnalyzer:
    """
    Advanced analyzer for extracting construction leads from legal documents.
    
    This class provides sophisticated analysis of legal documents to identify and
    extract high-value construction project opportunities. It applies multiple
    techniques including NLP, pattern matching, entity recognition, and machine
    learning to identify relevant projects, estimate their value, and prioritize
    leads based on business rules.
    """
    
    def __init__(self, config: Optional[AppConfig] = None):
        """
        Initialize the legal document analyzer.
        
        Args:
            config: Configuration object. If None, will load the default config.
        """
        self.config = config or AppConfig()
        
        # Initialize components
        self.legal_processor = LegalProcessor(config)
        self.document_parser = DocumentParser(config)
        self.document_validator = DocumentValidator(config)
        self.nlp_processor = NLPProcessor()
        
        # Try to initialize API client if credentials are available
        try:
            self.legal_api = LegalAPI(config)
            self.api_available = True
        except Exception as e:
            logger.warning(f"Legal API client initialization failed: {e}. API features will be disabled.")
            self.api_available = False
        
        # Load analysis configuration
        self._load_analysis_config()
        
        # Initialize processing lock
        self._processing_lock = Lock()
        
        logger.info("Legal document analyzer initialized")
    
    def _load_analysis_config(self) -> None:
        """Load analysis configuration from settings."""
        # Default configuration
        self.confidence_threshold = self.config.get(
            'LEGAL_CONFIDENCE_THRESHOLD', DEFAULT_CONFIDENCE_THRESHOLD
        )
        self.value_threshold = self.config.get(
            'LEGAL_VALUE_THRESHOLD', DEFAULT_VALUE_THRESHOLD
        )
        self.max_concurrent = min(
            int(self.config.get('LEGAL_MAX_CONCURRENT', MAX_CONCURRENT_PROCESSES)),
            MAX_CONCURRENT_PROCESSES
        )
        
        # Load priority sectors
        self.priority_sectors = self.config.get('LEGAL_PRIORITY_SECTORS', [
            MarketSector.HEALTHCARE.value,
            MarketSector.COMMERCIAL.value,
            MarketSector.ENERGY.value,
            MarketSector.EDUCATION.value
        ])
        
        # Load priority locations
        self.priority_locations = self.config.get('LEGAL_PRIORITY_LOCATIONS', [
            "Los Angeles", "San Diego", "Orange County", "Riverside", "San Francisco",
            "San Jose", "Sacramento", "Santa Monica", "Irvine", "Long Beach"
        ])
        
        # Load exclusion keywords (projects to ignore)
        self.exclusion_keywords = self.config.get('LEGAL_EXCLUSION_KEYWORDS', [
            "demolition only", "temporary", "repair only", "minor alterations",
            "sign installation", "tree removal", "fence", "swimming pool",
            "playground", "landscaping only", "maintenance"
        ])
        
        # Load recent search queries to avoid duplicates
        self.recent_searches = {}
        recent_searches_path = Path(self.config.get('LEGAL_RECENT_SEARCHES_PATH', 'data/legal_recent_searches.json'))
        if recent_searches_path.exists():
            try:
                with open(recent_searches_path, "r") as f:
                    self.recent_searches = json.load(f)
                logger.info(f"Loaded {len(self.recent_searches)} recent legal searches")
            except Exception as e:
                logger.warning(f"Failed to load recent searches: {e}")
    
    def analyze_document(self, document_text: str, document_type: Optional[str] = None, 
                        document_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform comprehensive analysis of a legal document.
        
        This method applies multiple analysis techniques to extract valuable
        information from legal documents and assess their potential as leads.
        
        Args:
            document_text: The text content of the document
            document_type: Optional hint about the document type (permit, contract, etc.)
            document_source: Source of the document for tracking
            
        Returns:
            Dict[str, Any]: Analysis results including lead potential
            
        Raises:
            DocumentAnalysisError: If analysis fails
        """
        if not document_text:
            return {"error": "Empty document", "lead_potential": 0.0}
        
        try:
            # Process document with legal processor first
            processed_data = self.legal_processor.process_document(
                document_text, document_type
            )
            
            # Enhance with NLP processing
            nlp_data = self.nlp_processor.process_text(document_text)
            
            # Merge results
            analysis = {**processed_data, **nlp_data}
            
            # Add source information
            if document_source:
                analysis["document_source"] = document_source
            
            # Calculate lead potential score
            analysis["lead_potential"] = self._calculate_lead_potential(analysis, document_text)
            
            # Categorize by confidence
            if analysis["lead_potential"] >= self.confidence_threshold:
                if analysis["lead_potential"] >= 0.8:
                    analysis["lead_category"] = "high_potential"
                else:
                    analysis["lead_category"] = "medium_potential"
            else:
                analysis["lead_category"] = "low_potential"
            
            # Verify if this meets minimum requirements
            analysis["meets_requirements"] = (
                analysis["lead_potential"] >= self.confidence_threshold and
                self._passes_value_check(analysis) and
                not self._contains_exclusions(document_text)
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing document: {e}")
            raise DocumentAnalysisError(f"Document analysis failed: {str(e)}")
    
    def _calculate_lead_potential(self, analysis: Dict[str, Any], 
                                 document_text: str) -> float:
        """
        Calculate a lead potential score based on document analysis.
        
        The score is based on multiple factors including:
        - Relevance to construction
        - Project value
        - Location match to target markets
        - Market sector match to priority sectors
        - Presence of key construction terminology
        - Project phase (earlier phases score higher)
        
        Args:
            analysis: Analysis data from document processing
            document_text: Original document text
            
        Returns:
            float: Lead potential score (0.0-1.0)
        """
        # Base scores
        relevance_score = analysis.get("relevance_score", 0.0)
        
        # Value score - higher value projects score higher
        value_score = 0.0
        project_value = analysis.get("project_value")
        if project_value:
            # Log scale with diminishing returns
            value_score = min(1.0, max(0.0, (
                0.2 +  # Base value score
                0.4 * min(1.0, project_value / 10000000) +  # Up to 0.4 for projects up to $10M
                0.4 * min(1.0, project_value / 50000000)    # Up to 0.4 more for projects up to $50M
            )))
        
        # Location score
        location_score = 0.0
        locations = analysis.get("locations", [])
        if locations:
            # Check if any locations are in priority list
            priority_match = any(
                loc in self.priority_locations or
                any(loc in pl for pl in self.priority_locations)
                for loc in locations
            )
            location_score = 0.8 if priority_match else 0.5
        
        # Market sector score
        sector_score = 0.0
        market_sector = analysis.get("market_sector")
        if market_sector:
            sector_score = 0.8 if market_sector in self.priority_sectors else 0.4
        
        # Keyword score
        keyword_score = 0.0
        for keyword in HIGH_PRIORITY_KEYWORDS:
            if re.search(r'\b' + re.escape(keyword) + r'\b', document_text, re.IGNORECASE):
                keyword_score += 0.1
        keyword_score = min(0.8, keyword_score)
        
        # Project phase score (earlier is better for leads)
        phase_score = 0.0
        project_phase = analysis.get("project_phase")
        if project_phase:
            phase_scores = {
                "pre-bid": 1.0,
                "bidding": 0.9,
                "pre-construction": 0.8,
                "construction": 0.5,
                "completed": 0.2
            }
            phase_score = phase_scores.get(project_phase, 0.4)
        
        # Document type score
        type_score = 0.0
        document_type = analysis.get("document_type")
        if document_type:
            type_scores = {
                "permit": 0.9,
                "contract": 0.8,
                "zoning": 0.7,
                "regulatory": 0.6,
                "unknown": 0.3
            }
            type_score = type_scores.get(document_type, 0.3)
        
        # Combined score with weights
        weights = {
            "relevance": 0.20,
            "value": 0.20,
            "location": 0.15,
            "sector": 0.15,
            "keyword": 0.10,
            "phase": 0.10,
            "type": 0.10
        }
        
        scores = {
            "relevance": relevance_score,
            "value": value_score,
            "location": location_score,
            "sector": sector_score,
            "keyword": keyword_score,
            "phase": phase_score,
            "type": type_score
        }
        
        # Store component scores for transparency
        analysis["potential_score_components"] = scores
        
        # Calculate weighted score
        potential = sum(
            scores[key] * weights[key] for key in weights
        )
        
        return potential
    
    def _passes_value_check(self, analysis: Dict[str, Any]) -> bool:
        """
        Check if the project meets value threshold requirements.
        
        Args:
            analysis: Analysis data from document processing
            
        Returns:
            bool: True if the project meets value requirements
        """
        project_value = analysis.get("project_value")
        if project_value is None:
            # If we can't determine value, use lead potential as proxy
            return analysis.get("lead_potential", 0.0) >= 0.75
        
        return project_value >= self.value_threshold
    
    def _contains_exclusions(self, document_text: str) -> bool:
        """
        Check if the document contains exclusion keywords.
        
        Args:
            document_text: Document text to check
            
        Returns:
            bool: True if exclusion keywords are present
        """
        for keyword in self.exclusion_keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', document_text, re.IGNORECASE):
                return True
        return False
    
    def extract_leads_from_document(self, document_text: str, document_type: Optional[str] = None,
                                  document_source: Optional[str] = None, document_id: Optional[str] = None) -> Optional[Lead]:
        """
        Extract a lead from a document if it meets quality criteria.
        
        Args:
            document_text: The text content of the document
            document_type: Optional hint about the document type
            document_source: Source of the document for tracking
            document_id: Unique identifier for the document
            
        Returns:
            Optional[Lead]: Extracted lead or None if document doesn't qualify
            
        Raises:
            LeadExtractionError: If lead extraction fails
        """
        try:
            # Analyze the document
            analysis = self.analyze_document(
                document_text, document_type, document_source
            )
            
            # Skip if doesn't meet requirements
            if not analysis.get("meets_requirements", False):
                logger.info(f"Document does not meet lead requirements (score: {analysis.get('lead_potential', 0.0):.2f})")
                return None
            
            # Extract metadata for lead
            project_title = None
            project_description = None
            
            # Generate title based on document type
            if analysis.get("document_type") == "permit":
                project_description = analysis.get("work_description")
                if analysis.get("property_address"):
                    project_title = f"Building Permit: {analysis.get('property_address')}"
                else:
                    project_title = "New Building Permit"
            
            elif analysis.get("document_type") == "contract":
                project_title = analysis.get("project_name")
                if not project_title and analysis.get("party_a") and analysis.get("party_b"):
                    project_title = f"Contract between {analysis.get('party_a')} and {analysis.get('party_b')}"
                elif not project_title:
                    project_title = "New Construction Contract"
            
            elif analysis.get("document_type") == "zoning":
                project_description = analysis.get("request_description")
                if analysis.get("property_address"):
                    project_title = f"Zoning Application: {analysis.get('property_address')}"
                else:
                    project_title = "New Zoning Application"
            
            elif analysis.get("document_type") == "regulatory":
                project_title = analysis.get("project_name")
                if not project_title and analysis.get("filing_type"):
                    project_title = f"{analysis.get('filing_type')} Filing"
                else:
                    project_title = "New Regulatory Filing"
            
            # Fallback to NLP-generated title if needed
            if not project_title:
                project_title = self.nlp_processor.summarize_content(document_text, 100)
            
            # Fallback to first 100 chars if still no title
            if not project_title:
                project_title = document_text[:100].strip()
                if len(document_text) > 100:
                    project_title += "..."
            
            # Generate description if none exists
            if not project_description:
                project_description = self.nlp_processor.summarize_content(document_text, 500)
            
            # Create lead object
            source_id = document_id or f"legal_{hashlib.md5(document_text[:500].encode()).hexdigest()}"
            
            lead = Lead(
                title=project_title,
                description=project_description or "",
                source=document_source or "legal_document",
                source_id=source_id,
                url="",  # No URL for document-based leads
                published_date=analysis.get("document_date") or datetime.now().isoformat(),
                location=analysis.get("property_address") or ", ".join(analysis.get("locations", [])),
                project_value=analysis.get("project_value"),
                market_sector=analysis.get("market_sector") or MarketSector.OTHER.value,
                confidence=analysis.get("lead_potential", 0.0),
                metadata={
                    "document_type": analysis.get("document_type", "unknown"),
                    "source": document_source or "document",
                    "processed_at": datetime.now().isoformat(),
                    "lead_category": analysis.get("lead_category"),
                    "lead_potential": analysis.get("lead_potential"),
                    "potential_score_components": analysis.get("potential_score_components"),
                    "document_analysis": {k: v for k, v in analysis.items() if k not in [
                        "potential_score_components", "lead_category", "lead_potential",
                        "meets_requirements", "document_source"
                    ]}
                }
            )
            
            return lead
            
        except Exception as e:
            logger.error(f"Error extracting lead from document: {e}")
            raise LeadExtractionError(f"Lead extraction failed: {str(e)}")
    
    def batch_analyze_documents(self, documents: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Analyze multiple documents in batch.
        
        Args:
            documents: List of dictionaries with 'text', 'type', and optional 'source' keys
            
        Returns:
            List[Dict[str, Any]]: List of analysis results
        """
        results = []
        with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
            futures = []
            for doc in documents:
                future = executor.submit(
                    self.analyze_document,
                    doc.get("text", ""),
                    doc.get("type"),
                    doc.get("source")
                )
                futures.append((future, doc))
            
            for future, doc in futures:
                try:
                    result = future.result()
                    result["document_id"] = doc.get("id")
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error in batch document analysis: {e}")
                    results.append({
                        "document_id": doc.get("id"),
                        "error": str(e),
                        "lead_potential": 0.0,
                        "meets_requirements": False
                    })
        
        return results
    
    def extract_leads_from_local_documents(self, documents_path: Union[str, Path]) -> List[Lead]:
        """
        Extract leads from documents in a local directory.
        
        Args:
            documents_path: Path to directory containing legal documents
            
        Returns:
            List[Lead]: List of extracted leads
            
        Raises:
            LeadExtractionError: If lead extraction fails
        """
        logger.info(f"Extracting leads from local documents in {documents_path}")
        try:
            path = Path(documents_path)
            if not path.exists() or not path.is_dir():
                raise LeadExtractionError(f"Invalid documents path: {documents_path}")
            
            # Find document files
            document_files = []
            for file_path in path.glob("**/*"):
                if file_path.is_file() and self.document_parser.is_supported_format(file_path):
                    document_files.append(file_path)
            
            logger.info(f"Found {len(document_files)} document files")
            
            # Process documents and extract leads
            leads = []
            with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
                futures = []
                for file_path in document_files:
                    future = executor.submit(self._process_local_document, file_path)
                    futures.append(future)
                
                for future in as_completed(futures):
                    try:
                        lead = future.result()
                        if lead:
                            leads.append(lead)
                    except Exception as e:
                        logger.error(f"Error processing document: {e}")
            
            logger.info(f"Extracted {len(leads)} leads from local documents")
            return leads
            
        except Exception as e:
            logger.error(f"Error extracting leads from local documents: {e}")
            raise LeadExtractionError(f"Failed to extract leads from local documents: {str(e)}")
    
    def _process_local_document(self, file_path: Path) -> Optional[Lead]:
        """
        Process a single local document file.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Optional[Lead]: Extracted lead or None if document doesn't qualify
        """
        try:
            # Parse document text
            document_text = self.document_parser.parse_file(file_path)
            
            # Infer document type from file path or content
            document_type = None
            if "permit" in file_path.name.lower() or "permit" in str(file_path).lower():
                document_type = "permit"
            elif "contract" in file_path.name.lower() or "contract" in str(file_path).lower():
                document_type = "contract"
            elif "zoning" in file_path.name.lower() or "zoning" in str(file_path).lower():
                document_type = "zoning"
            elif "regulatory" in file_path.name.lower() or "regulatory" in str(file_path).lower() or "regulation" in str(file_path).lower():
                document_type = "regulatory"
            
            # Extract lead
            return self.extract_leads_from_document(
                document_text,
                document_type,
                f"local_document_{file_path.name}",
                str(file_path)
            )
            
        except Exception as e:
            logger.error(f"Error processing local document {file_path}: {e}")
            return None
    
    def extract_leads_from_api(self, provider: str, document_type: Optional[str] = None,
                             location: Optional[str] = None, days: int = 14,
                             max_results: int = 50) -> List[Lead]:
        """
        Extract leads from a legal document API.
        
        Args:
            provider: API provider name
            document_type: Type of document to search for
            location: Location to filter by
            days: Number of days to look back
            max_results: Maximum number of results
            
        Returns:
            List[Lead]: List of extracted leads
            
        Raises:
            LeadExtractionError: If API lead extraction fails
        """
        logger.info(f"Extracting leads from {provider} API for {location or 'all locations'}")
        
        if not self.api_available:
            raise LeadExtractionError("Legal API client is not available")
        
        try:
            # Generate a search ID for tracking
            search_id = self._generate_search_id(provider, document_type, location, days)
            
            # Check if we've recently performed this search
            if self._is_recent_search(search_id):
                logger.info(f"Skipping recent search: {provider} for {location}")
                return []
            
            # Fetch documents from API
            documents = self.legal_api.fetch_recent_documents(
                provider=provider,
                document_type=document_type,
                location=location,
                days=days,
                max_results=max_results
            )
            
            logger.info(f"Fetched {len(documents)} documents from {provider} API")
            
            # Process documents and extract leads
            leads = []
            with ThreadPoolExecutor(max_workers=self.max_concurrent) as executor:
                futures = []
                for doc in documents:
                    future = executor.submit(self._process_api_document, provider, doc)
                    futures.append(future)
                
                for future in as_completed(futures):
                    try:
                        lead = future.result()
                        if lead:
                            leads.append(lead)
                    except Exception as e:
                        logger.error(f"Error processing API document: {e}")
            
            # Record this search to avoid duplicates
            self._record_search(search_id)
            
            logger.info(f"Extracted {len(leads)} leads from {provider} API")
            return leads
            
        except Exception as e:
            logger.error(f"Error extracting leads from {provider} API: {e}")
            raise LeadExtractionError(f"Failed to extract leads from API: {str(e)}")
    
    def _process_api_document(self, provider: str, document_metadata: Dict[str, Any]) -> Optional[Lead]:
        """
        Process a single document from an API.
        
        Args:
            provider: API provider name
            document_metadata: Document metadata from API
            
        Returns:
            Optional[Lead]: Extracted lead or None if document doesn't qualify
        """
        try:
            # Extract document ID
            doc_id = document_metadata.get("id") or document_metadata.get("document_id")
            if not doc_id:
                logger.warning(f"Document has no ID, skipping")
                return None
            
            # Extract text from the document
            try:
                document_text = self.legal_api.extract_text_from_document(provider, doc_id)
            except Exception as e:
                logger.error(f"Failed to extract text from document {doc_id}: {e}")
                return None
            
            # Get document type from metadata or determine from content
            document_type = document_metadata.get("document_type") or document_metadata.get("type")
            
            # Extract URL if available
            url = document_metadata.get("url", "")
            
            # Extract lead
            source_name = f"api_{provider}"
            return self.extract_leads_from_document(
                document_text,
                document_type,
                source_name,
                doc_id
            )
            
        except Exception as e:
            logger.error(f"Error processing API document: {e}")
            return None
    
    def _generate_search_id(self, provider: str, document_type: Optional[str],
                          location: Optional[str], days: int) -> str:
        """
        Generate a unique ID for a search to avoid duplicates.
        
        Args:
            provider: API provider name
            document_type: Type of document
            location: Location filter
            days: Days to look back
            
        Returns:
            str: Unique search ID
        """
        components = [
            provider,
            document_type or "all",
            location or "all",
            str(days)
        ]
        return hashlib.md5(":".join(components).encode()).hexdigest()
    
    def _is_recent_search(self, search_id: str) -> bool:
        """
        Check if a search has been performed recently.
        
        Args:
            search_id: Search identifier
            
        Returns:
            bool: True if this is a recent search
        """
        if search_id not in self.recent_searches:
            return False
        
        # Check if search is older than cache duration
        timestamp = self.recent_searches[search_id]
        cache_duration = self.config.get('LEGAL_SEARCH_CACHE_HOURS', 24)
        cache_expiry = datetime.now() - timedelta(hours=cache_duration)
        
        search_time = datetime.fromisoformat(timestamp)
        return search_time > cache_expiry
    
    def _record_search(self, search_id: str) -> None:
        """
        Record a search to avoid duplicates.
        
        Args:
            search_id: Search identifier
        """
        self.recent_searches[search_id] = datetime.now().isoformat()
        
        # Save to file
        recent_searches_path = Path(self.config.get('LEGAL_RECENT_SEARCHES_PATH', 'data/legal_recent_searches.json'))
        try:
            # Create directory if it doesn't exist
            recent_searches_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(recent_searches_path, "w") as f:
                json.dump(self.recent_searches, f)
        except Exception as e:
            logger.warning(f"Failed to save recent searches: {e}")
    
    @timeout_handler(timeout_sec=1800)  # 30 minutes timeout
    def discover_leads_from_multiple_sources(self, config_path: Optional[Union[str, Path]] = None) -> List[Lead]:
        """
        Discover leads from multiple configured legal sources.
        
        This method processes both local documents and API sources according to
        the provided configuration.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            List[Lead]: Combined list of leads from all sources
            
        Raises:
            LeadExtractionError: If lead discovery fails
        """
        try:
            # Load configuration
            sources_config = self._load_discovery_config(config_path)
            
            logger.info(f"Discovering leads from {len(sources_config)} legal sources")
            
            # Process all sources
            all_leads = []
            
            # Process local document sources
            for source in [s for s in sources_config if s.get("source_type") == "local"]:
                try:
                    source_path = source.get("path")
                    if not source_path:
                        logger.warning(f"Local source missing path, skipping")
                        continue
                    
                    logger.info(f"Processing local documents from {source_path}")
                    leads = self.extract_leads_from_local_documents(source_path)
                    all_leads.extend(leads)
                    
                except Exception as e:
                    logger.error(f"Error processing local source {source.get('name', 'unknown')}: {e}")
            
            # Process API sources
            for source in [s for s in sources_config if s.get("source_type") == "api"]:
                try:
                    provider = source.get("api_provider")
                    if not provider:
                        logger.warning(f"API source missing provider, skipping")
                        continue
                    
                    logger.info(f"Processing API source {provider}")
                    leads = self.extract_leads_from_api(
                        provider=provider,
                        document_type=source.get("document_type"),
                        location=source.get("location"),
                        days=source.get("days", 14),
                        max_results=source.get("max_results", 50)
                    )
                    all_leads.extend(leads)
                    
                except Exception as e:
                    logger.error(f"Error processing API source {source.get('name', 'unknown')}: {e}")
            
            logger.info(f"Discovered {len(all_leads)} leads from all legal sources")
            return all_leads
            
        except Exception as e:
            logger.error(f"Error discovering leads from multiple sources: {e}")
            raise LeadExtractionError(f"Failed to discover leads: {str(e)}")
    
    def _load_discovery_config(self, config_path: Optional[Union[str, Path]] = None) -> List[Dict[str, Any]]:
        """
        Load lead discovery configuration.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            List[Dict[str, Any]]: List of source configurations
        """
        # Default to main sources file if not specified
        if not config_path:
            config_path = Path(self.config.sources_path)
        else:
            config_path = Path(config_path)
        
        # Check if file exists
        if not config_path.exists():
            logger.warning(f"Sources config file not found: {config_path}")
            return []
        
        try:
            # Load and parse configuration
            with open(config_path, "r") as f:
                config_data = json.load(f)
            
            # Extract legal sources
            all_sources = config_data.get("sources", [])
            legal_sources = [
                source["config"] 
                for source in all_sources 
                if source.get("source_type") == "legal" and source.get("enabled", True)
            ]
            
            logger.info(f"Loaded {len(legal_sources)} legal sources from configuration")
            return legal_sources
            
        except Exception as e:
            logger.error(f"Error loading discovery configuration: {e}")
            return []


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, 
                      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    try:
        # Create analyzer
        analyzer = LegalDocumentAnalyzer()
        
        if len(sys.argv) > 1:
            # Process file or directory specified on command line
            path = Path(sys.argv[1])
            
            if path.is_file():
                # Process single file
                print(f"Analyzing document: {path}")
                document_text = analyzer.document_parser.parse_file(path)
                analysis = analyzer.analyze_document(document_text)
                print(f"Lead potential: {analysis.get('lead_potential', 0.0):.2f}")
                print(f"Meets requirements: {analysis.get('meets_requirements', False)}")
                
                if analysis.get("meets_requirements", False):
                    lead = analyzer.extract_leads_from_document(document_text)
                    if lead:
                        print(f"Lead extracted: {lead.title}")
                        print(f"Confidence: {lead.confidence:.2f}")
                        print(f"Market sector: {lead.market_sector}")
                        if lead.project_value:
                            print(f"Estimated value: ${lead.project_value:,.2f}")
            
            elif path.is_dir():
                # Process directory
                print(f"Processing documents in: {path}")
                leads = analyzer.extract_leads_from_local_documents(path)
                print(f"Extracted {len(leads)} leads")
                
                for lead in leads:
                    print(f"- {lead.title} (Confidence: {lead.confidence:.2f})")
            
            else:
                print(f"Path not found: {path}")
        
        else:
            # Interactive mode
            print("Legal Document Analyzer")
            print("======================")
            print("1. Analyze document file")
            print("2. Process directory of documents")
            print("3. Extract leads from API source")
            print("4. Discover leads from all configured sources")
            print("q. Quit")
            
            choice = input("Enter choice: ")
            
            if choice == "1":
                file_path = input("Enter document file path: ")
                document_text = analyzer.document_parser.parse_file(file_path)
                analysis = analyzer.analyze_document(document_text)
                print(f"Lead potential: {analysis.get('lead_potential', 0.0):.2f}")
                print(f"Meets requirements: {analysis.get('meets_requirements', False)}")
            
            elif choice == "2":
                dir_path = input("Enter document directory path: ")
                leads = analyzer.extract_leads_from_local_documents(dir_path)
                print(f"Extracted {len(leads)} leads")
            
            elif choice == "3":
                provider = input("Enter API provider: ")
                location = input("Enter location (or leave empty): ")
                leads = analyzer.extract_leads_from_api(provider, location=location or None)
                print(f"Extracted {len(leads)} leads")
            
            elif choice == "4":
                leads = analyzer.discover_leads_from_multiple_sources()
                print(f"Discovered {len(leads)} leads from all sources")
            
            elif choice.lower() == "q":
                print("Exiting...")
            
            else:
                print("Invalid choice")
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
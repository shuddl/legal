"""Legal document processor for construction leads.

Provides functionality to analyze and extract relevant information from legal documents
related to construction projects, including permits, contracts, and regulatory filings.
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
from datetime import datetime
import json

from ..config import Config
from ..utils.timeout import timeout_handler
from ..nlp.nlp_processor import NLPProcessor

logger = logging.getLogger(__name__)

class LegalDocumentError(Exception):
    """Base exception for legal document processing errors."""
    pass

class ParseError(LegalDocumentError):
    """Exception raised when a document cannot be parsed."""
    pass

class ValidationError(LegalDocumentError):
    """Exception raised when a document fails validation."""
    pass


class LegalProcessor:
    """Processes legal documents related to construction projects.
    
    This class is responsible for extracting relevant information from various types
    of legal documents, including permits, contracts, zoning approvals, and regulatory 
    filings that might contain valuable lead information.
    """
    
    def __init__(self, config: Optional[Config] = None):
        """Initialize the legal processor.
        
        Args:
            config: Configuration object. If None, will load the default config.
        """
        self.config = config or Config()
        self._load_document_patterns()
        self.nlp_processor = NLPProcessor(config)
        logger.info("Legal processor initialized")
        
    def _load_document_patterns(self) -> None:
        """Load document patterns from configuration."""
        try:
            patterns_path = Path(self.config.get('LEGAL_PATTERNS_PATH', 
                                              'config/legal_patterns.json'))
            if patterns_path.exists():
                with open(patterns_path, 'r') as f:
                    self.patterns = json.load(f)
                logger.info(f"Loaded {len(self.patterns)} legal document patterns")
            else:
                logger.warning(f"Legal patterns file not found at {patterns_path}")
                self.patterns = {}
        except Exception as e:
            logger.error(f"Error loading legal patterns: {e}")
            self.patterns = {}
    
    @timeout_handler(timeout_sec=30)
    def process_document(self, document_text: str, document_type: Optional[str] = None) -> Dict[str, Any]:
        """Process a legal document and extract relevant information.
        
        Args:
            document_text: The text content of the document
            document_type: Optional hint about the document type (permit, contract, etc.)
            
        Returns:
            Dictionary containing extracted information
            
        Raises:
            ParseError: If the document cannot be parsed
            ValidationError: If the extracted data is invalid
        """
        try:
            # Determine document type if not provided
            if not document_type:
                document_type = self._identify_document_type(document_text)
            
            # Apply appropriate extraction based on document type
            if document_type == "permit":
                result = self._extract_permit_info(document_text)
            elif document_type == "contract":
                result = self._extract_contract_info(document_text)
            elif document_type == "zoning":
                result = self._extract_zoning_info(document_text)
            elif document_type == "regulatory":
                result = self._extract_regulatory_info(document_text)
            else:
                # Generic extraction for unknown document types
                result = self._extract_generic_info(document_text)
            
            # Enrich with NLP processing
            nlp_data = self.nlp_processor.process_text(document_text)
            result.update({
                "entities": nlp_data.get("entities", {}),
                "locations": nlp_data.get("locations", []),
                "project_value": nlp_data.get("project_value"),
                "market_sector": nlp_data.get("market_sector"),
                "relevance_score": nlp_data.get("relevance_score"),
            })
            
            # Add metadata
            result["document_type"] = document_type
            result["processed_at"] = datetime.now().isoformat()
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing legal document: {e}")
            raise ParseError(f"Failed to process document: {str(e)}")
    
    def _identify_document_type(self, text: str) -> str:
        """Identify the type of legal document from its content.
        
        Args:
            text: Document text
            
        Returns:
            Identified document type (permit, contract, zoning, regulatory, or unknown)
        """
        # Check for patterns that indicate document type
        for doc_type, pattern_list in self.patterns.get("type_indicators", {}).items():
            for pattern in pattern_list:
                if re.search(pattern, text, re.IGNORECASE):
                    logger.debug(f"Document identified as {doc_type}")
                    return doc_type
        
        # Fallback to NLP classification
        try:
            nlp_data = self.nlp_processor.process_text(text)
            doc_type = nlp_data.get("document_type")
            if doc_type:
                return doc_type
        except Exception as e:
            logger.warning(f"NLP classification failed: {e}")
        
        logger.info("Could not identify document type, using 'unknown'")
        return "unknown"
    
    def _extract_permit_info(self, text: str) -> Dict[str, Any]:
        """Extract information from a building permit document.
        
        Args:
            text: Permit document text
            
        Returns:
            Dictionary of extracted information
        """
        result = {}
        
        # Extract permit number
        permit_patterns = self.patterns.get("permit", {}).get("permit_number", [r"permit\s*#?\s*(\w+-?\w*)"])
        for pattern in permit_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["permit_number"] = match.group(1)
                break
        
        # Extract issue date
        date_patterns = self.patterns.get("permit", {}).get("issue_date", 
                                                       [r"issued?\s*(?:on|date)?\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"])
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["issue_date"] = match.group(1)
                break
        
        # Extract property address
        address_patterns = self.patterns.get("permit", {}).get("property_address", 
                                                           [r"property\s*address\s*:?\s*(.+?(?:\n|$))"])
        for pattern in address_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["property_address"] = match.group(1).strip()
                break
        
        # Extract work description
        desc_patterns = self.patterns.get("permit", {}).get("work_description", 
                                                        [r"description\s*of\s*work\s*:?\s*(.+?(?:\n\s*\n|$))"])
        for pattern in desc_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                result["work_description"] = match.group(1).strip()
                break
        
        # Extract estimated cost/valuation
        value_patterns = self.patterns.get("permit", {}).get("estimated_value", 
                                                         [r"(estimated\s*cost|valuation|job\s*value)\s*:?\s*[$]?\s*(\d[\d,.]*)"])
        for pattern in value_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value_str = match.group(2).replace(',', '')
                    result["estimated_value"] = float(value_str)
                except ValueError:
                    logger.warning(f"Could not convert value to float: {match.group(2)}")
                break
        
        # Extract contractor information
        contractor_patterns = self.patterns.get("permit", {}).get("contractor", 
                                                              [r"contractor\s*:?\s*(.+?(?:\n|$))"])
        for pattern in contractor_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["contractor"] = match.group(1).strip()
                break
        
        return result
    
    def _extract_contract_info(self, text: str) -> Dict[str, Any]:
        """Extract information from a construction contract document.
        
        Args:
            text: Contract document text
            
        Returns:
            Dictionary of extracted information
        """
        result = {}
        
        # Extract contract parties
        party_patterns = self.patterns.get("contract", {}).get("parties", 
                                                          [r"between\s+(.+?)\s+and\s+(.+?)(?:\s+dated|\.|\"|$)"])
        for pattern in party_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                result["party_a"] = match.group(1).strip()
                result["party_b"] = match.group(2).strip()
                break
        
        # Extract contract date
        date_patterns = self.patterns.get("contract", {}).get("date", 
                                                       [r"dated\s*(?:this)?\s*(?:the)?\s*(\d{1,2}(?:st|nd|rd|th)?\s+day\s+of\s+\w+,?\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"])
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["contract_date"] = match.group(1)
                break
        
        # Extract contract amount
        amount_patterns = self.patterns.get("contract", {}).get("amount", 
                                                          [r"(contract\s*(?:sum|amount|price))\s*(?:of|:)?\s*[$]?\s*(\d[\d,.]*)"])
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(2).replace(',', '')
                    result["contract_amount"] = float(amount_str)
                except ValueError:
                    logger.warning(f"Could not convert amount to float: {match.group(2)}")
                break
        
        # Extract project name/description
        project_patterns = self.patterns.get("contract", {}).get("project", 
                                                           [r"project\s*name\s*:?\s*(.+?(?:\n|$))", 
                                                            r"(?:for|regarding)\s+the\s+(.+?)\s+project"])
        for pattern in project_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["project_name"] = match.group(1).strip()
                break
        
        # Extract completion date/timeline
        completion_patterns = self.patterns.get("contract", {}).get("completion", 
                                                              [r"(?:substantial\s*)?completion\s*date\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", 
                                                               r"within\s+(\d+)\s+(days|weeks|months)"])
        for pattern in completion_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 1:  # Date format
                    result["completion_date"] = match.group(1)
                else:  # Duration format
                    result["completion_duration"] = f"{match.group(1)} {match.group(2)}"
                break
        
        return result
    
    def _extract_zoning_info(self, text: str) -> Dict[str, Any]:
        """Extract information from a zoning document.
        
        Args:
            text: Zoning document text
            
        Returns:
            Dictionary of extracted information
        """
        result = {}
        
        # Extract application/case number
        case_patterns = self.patterns.get("zoning", {}).get("case_number", 
                                                       [r"(?:case|application|file)\s*(?:no\.?|number|#)\s*:?\s*(\w+-?\w*)"])
        for pattern in case_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["case_number"] = match.group(1)
                break
        
        # Extract property address
        address_patterns = self.patterns.get("zoning", {}).get("property_address", 
                                                          [r"(?:property|site)\s*address\s*:?\s*(.+?(?:\n|$))"])
        for pattern in address_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["property_address"] = match.group(1).strip()
                break
        
        # Extract current and proposed zoning
        current_patterns = self.patterns.get("zoning", {}).get("current_zoning", 
                                                           [r"current\s*zoning\s*:?\s*([\w-]+)"])
        for pattern in current_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["current_zoning"] = match.group(1)
                break
                
        proposed_patterns = self.patterns.get("zoning", {}).get("proposed_zoning", 
                                                           [r"proposed\s*zoning\s*:?\s*([\w-]+)"])
        for pattern in proposed_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["proposed_zoning"] = match.group(1)
                break
        
        # Extract applicant information
        applicant_patterns = self.patterns.get("zoning", {}).get("applicant", 
                                                            [r"applicant\s*:?\s*(.+?(?:\n|$))"])
        for pattern in applicant_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["applicant"] = match.group(1).strip()
                break
        
        # Extract request/description
        request_patterns = self.patterns.get("zoning", {}).get("request", 
                                                          [r"(?:request|description)\s*:?\s*(.+?(?:\n\s*\n|$))"])
        for pattern in request_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                result["request_description"] = match.group(1).strip()
                break
        
        # Extract hearing date if available
        hearing_patterns = self.patterns.get("zoning", {}).get("hearing_date", 
                                                           [r"hearing\s*date\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"])
        for pattern in hearing_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["hearing_date"] = match.group(1)
                break
        
        return result
    
    def _extract_regulatory_info(self, text: str) -> Dict[str, Any]:
        """Extract information from a regulatory filing document.
        
        Args:
            text: Regulatory document text
            
        Returns:
            Dictionary of extracted information
        """
        result = {}
        
        # Extract filing number
        filing_patterns = self.patterns.get("regulatory", {}).get("filing_number", 
                                                             [r"filing\s*(?:no\.?|number|#)\s*:?\s*(\w+-?\w*)"])
        for pattern in filing_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["filing_number"] = match.group(1)
                break
        
        # Extract filing date
        date_patterns = self.patterns.get("regulatory", {}).get("filing_date", 
                                                           [r"filed\s*(?:on|date)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"])
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["filing_date"] = match.group(1)
                break
        
        # Extract project name
        project_patterns = self.patterns.get("regulatory", {}).get("project_name", 
                                                              [r"project\s*(?:name|title)\s*:?\s*(.+?(?:\n|$))"])
        for pattern in project_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["project_name"] = match.group(1).strip()
                break
        
        # Extract applicant information
        applicant_patterns = self.patterns.get("regulatory", {}).get("applicant", 
                                                               [r"(?:applicant|proponent|submitted by)\s*:?\s*(.+?(?:\n|$))"])
        for pattern in applicant_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["applicant"] = match.group(1).strip()
                break
        
        # Extract regulatory authority
        authority_patterns = self.patterns.get("regulatory", {}).get("authority", 
                                                                [r"(?:submitted to|authority)\s*:?\s*(.+?(?:\n|$))"])
        for pattern in authority_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["authority"] = match.group(1).strip()
                break
        
        # Extract type of filing/application
        type_patterns = self.patterns.get("regulatory", {}).get("filing_type", 
                                                            [r"type\s*of\s*(?:application|filing)\s*:?\s*(.+?(?:\n|$))"])
        for pattern in type_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result["filing_type"] = match.group(1).strip()
                break
        
        return result
    
    def _extract_generic_info(self, text: str) -> Dict[str, Any]:
        """Extract information from an unknown document type.
        
        Args:
            text: Document text
            
        Returns:
            Dictionary of extracted information
        """
        # For generic documents, rely more heavily on NLP processing
        # Just extract some basic fields that might be common across document types
        result = {}
        
        # Try to find any reference numbers
        ref_pattern = r"(?:reference|number|no\.|#)\s*:?\s*(\w+-?\w*)"
        match = re.search(ref_pattern, text, re.IGNORECASE)
        if match:
            result["reference_number"] = match.group(1)
        
        # Try to find dates
        date_pattern = r"(?:dated?|issued|approved)\s*(?:on|:)?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
        match = re.search(date_pattern, text, re.IGNORECASE)
        if match:
            result["document_date"] = match.group(1)
        
        # Try to find addresses
        address_pattern = r"(?:located at|property|address|site)\s*:?\s*(.+?(?:\n|$))"
        match = re.search(address_pattern, text, re.IGNORECASE)
        if match:
            result["address"] = match.group(1).strip()
        
        # Try to find monetary values
        value_pattern = r"(?:amount|value|cost|sum)\s*(?:of|is|:)\s*[$]?\s*(\d[\d,.]*)"
        match = re.search(value_pattern, text, re.IGNORECASE)
        if match:
            try:
                value_str = match.group(1).replace(',', '')
                result["value_amount"] = float(value_str)
            except ValueError:
                pass
        
        return result

    def batch_process(self, documents: List[Tuple[str, Optional[str]]]) -> List[Dict[str, Any]]:
        """Process multiple documents in batch.
        
        Args:
            documents: List of (document_text, document_type) tuples
            
        Returns:
            List of processing results
        """
        results = []
        for i, (doc_text, doc_type) in enumerate(documents):
            try:
                logger.info(f"Processing document {i+1}/{len(documents)}")
                result = self.process_document(doc_text, doc_type)
                results.append(result)
            except Exception as e:
                logger.error(f"Error processing document {i+1}: {e}")
                results.append({"error": str(e)})
        
        return results
    
    def extract_leads_from_documents(self, 
                               documents_path: Union[str, Path, List[Tuple[str, Optional[str]]]],
                               document_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Extract potential construction leads from legal documents.
        
        Args:
            documents_path: Either a path to documents directory, or a list of (document_text, document_type) tuples
            document_type: Optional hint about the document type (permit, contract, etc.)
            
        Returns:
            List of lead dictionaries ready for the lead processor
        """
        leads = []
        
        # Handle different types of input
        if isinstance(documents_path, (str, Path)):
            # Process documents from a directory
            path = Path(documents_path)
            if not path.exists():
                logger.error(f"Documents path does not exist: {path}")
                return []
                
            # Get all document files from the directory
            from .document_parser import DocumentParser
            parser = DocumentParser(self.config)
            
            document_tuples = []
            for file_path in path.glob("**/*"):
                if file_path.is_file() and parser.is_supported_format(file_path):
                    try:
                        text = parser.parse_file(file_path)
                        doc_type = document_type or self._identify_document_type(text)
                        document_tuples.append((text, doc_type))
                    except Exception as e:
                        logger.error(f"Error parsing file {file_path}: {e}")
            
            # Process the document tuples
            processed_docs = self.batch_process(document_tuples)
            
        elif isinstance(documents_path, list):
            # Process document tuples directly
            processed_docs = self.batch_process(documents_path)
            
        else:
            logger.error(f"Invalid documents_path type: {type(documents_path)}")
            return []
        
        # Process each document
        for doc in processed_docs:
            if "error" in doc:
                continue
                
            # Skip documents with low relevance score
            relevance_threshold = self.config.get('LEGAL_RELEVANCE_THRESHOLD', 0.3)
            if doc.get("relevance_score", 0) < relevance_threshold:
                logger.debug(f"Skipping document with low relevance: {doc.get('relevance_score', 0)}")
                continue
                
            # Create lead dictionary
            lead = {
                "title": self._generate_lead_title(doc),
                "description": self._generate_lead_description(doc),
                "source": "legal_document",
                "source_id": doc.get("reference_number", "") or doc.get("permit_number", "") or 
                           doc.get("case_number", "") or doc.get("filing_number", ""),
                "url": doc.get("url", ""),  # URL might be available from API-sourced documents
                "published_date": doc.get("document_date") or doc.get("issue_date") or 
                                doc.get("contract_date") or doc.get("filing_date") or "",
                "location": doc.get("property_address") or doc.get("address") or "",
                "entities": doc.get("entities", {}),
                "project_value": doc.get("estimated_value") or doc.get("contract_amount") or 
                               doc.get("value_amount") or doc.get("project_value"),
                "market_sector": doc.get("market_sector", ""),
                "metadata": {
                    "document_type": doc.get("document_type", "unknown"),
                    "processed_at": doc.get("processed_at", datetime.now().isoformat()),
                    # Include all remaining fields as metadata
                    **{k: v for k, v in doc.items() if k not in [
                        "entities", "locations", "project_value", "market_sector", 
                        "relevance_score", "document_type", "processed_at",
                        "property_address", "address", "estimated_value", "contract_amount", "value_amount",
                        "document_date", "issue_date", "contract_date", "filing_date",
                        "reference_number", "permit_number", "case_number", "filing_number",
                        "url"
                    ]}
                }
            }
            
            leads.append(lead)
            
        return leads
        
    def extract_leads_from_api(self, 
                           provider: str,
                           document_type: Optional[str] = None,
                           location: Optional[str] = None,
                           days: int = 7,
                           max_results: int = 25) -> List[Dict[str, Any]]:
        """Extract potential construction leads from legal document APIs.
        
        Args:
            provider: API provider name (e.g., "public_records", "permit_data")
            document_type: Type of document to search for
            location: Location to search in (e.g., city, county)
            days: Number of days to look back
            max_results: Maximum number of results to return
            
        Returns:
            List of lead dictionaries ready for the lead processor
        """
        try:
            # Import the LegalAPI client
            from .legal_api import LegalAPI
            
            # Initialize the API client
            api_client = LegalAPI(self.config)
            
            # Fetch recent documents
            documents = api_client.fetch_recent_documents(
                provider=provider,
                document_type=document_type,
                location=location,
                days=days,
                max_results=max_results
            )
            
            logger.info(f"Fetched {len(documents)} documents from {provider} API")
            
            # Process the documents
            leads = []
            for doc_meta in documents:
                try:
                    doc_id = doc_meta.get("id") or doc_meta.get("document_id")
                    if not doc_id:
                        logger.warning(f"Skipping document with no ID: {doc_meta}")
                        continue
                    
                    # Get the full document with text
                    text = api_client.extract_text_from_document(provider, doc_id)
                    
                    # Process the document text
                    processed_doc = self.process_document(
                        text, 
                        doc_meta.get("document_type") or document_type
                    )
                    
                    # Merge metadata from API with processed document data
                    processed_doc.update({
                        "url": doc_meta.get("url", ""),
                        "reference_number": doc_meta.get("reference_number") or doc_meta.get("id"),
                        "document_date": doc_meta.get("date") or doc_meta.get("issue_date"),
                        "source_api": provider
                    })
                    
                    # Skip documents with low relevance score
                    relevance_threshold = self.config.get('LEGAL_RELEVANCE_THRESHOLD', 0.3)
                    if processed_doc.get("relevance_score", 0) < relevance_threshold:
                        logger.debug(f"Skipping document with low relevance: {processed_doc.get('relevance_score', 0)}")
                        continue
                    
                    # Create lead dictionary
                    lead = {
                        "title": self._generate_lead_title(processed_doc),
                        "description": self._generate_lead_description(processed_doc),
                        "source": f"legal_api_{provider}",
                        "source_id": processed_doc.get("reference_number", "") or processed_doc.get("permit_number", "") or 
                                   processed_doc.get("case_number", "") or processed_doc.get("filing_number", ""),
                        "url": processed_doc.get("url", ""),
                        "published_date": processed_doc.get("document_date") or processed_doc.get("issue_date") or 
                                        processed_doc.get("contract_date") or processed_doc.get("filing_date") or "",
                        "location": processed_doc.get("property_address") or processed_doc.get("address") or 
                                   doc_meta.get("location", ""),
                        "entities": processed_doc.get("entities", {}),
                        "project_value": processed_doc.get("estimated_value") or processed_doc.get("contract_amount") or 
                                       processed_doc.get("value_amount") or processed_doc.get("project_value") or
                                       doc_meta.get("value"),
                        "market_sector": processed_doc.get("market_sector", ""),
                        "metadata": {
                            "document_type": processed_doc.get("document_type", "unknown"),
                            "processed_at": processed_doc.get("processed_at", datetime.now().isoformat()),
                            "source_api": provider,
                            "api_metadata": doc_meta,
                            # Include all remaining fields as metadata
                            **{k: v for k, v in processed_doc.items() if k not in [
                                "entities", "locations", "project_value", "market_sector", 
                                "relevance_score", "document_type", "processed_at",
                                "property_address", "address", "estimated_value", "contract_amount", "value_amount",
                                "document_date", "issue_date", "contract_date", "filing_date",
                                "reference_number", "permit_number", "case_number", "filing_number",
                                "url"
                            ]}
                        }
                    }
                    
                    leads.append(lead)
                    
                except Exception as e:
                    logger.error(f"Error processing document {doc_meta.get('id')}: {e}")
            
            return leads
            
        except Exception as e:
            logger.error(f"Error extracting leads from API {provider}: {e}")
            return []
    
    def _generate_lead_title(self, doc: Dict[str, Any]) -> str:
        """Generate a title for a lead based on document data.
        
        Args:
            doc: Processed document data
            
        Returns:
            Lead title string
        """
        # Try to use project name if available
        if doc.get("project_name"):
            return doc["project_name"]
            
        # Otherwise construct based on document type and available info
        doc_type = doc.get("document_type", "unknown").capitalize()
        
        if doc_type == "Permit":
            desc = doc.get("work_description", "")
            if len(desc) > 50:
                desc = desc[:47] + "..."
            return f"Building Permit: {desc}" if desc else "New Building Permit"
            
        elif doc_type == "Contract":
            party = doc.get("party_a", "") or doc.get("contractor", "")
            return f"Construction Contract with {party}" if party else "New Construction Contract"
            
        elif doc_type == "Zoning":
            request = doc.get("request_description", "")
            if len(request) > 50:
                request = request[:47] + "..."
            return f"Zoning Application: {request}" if request else "New Zoning Application"
            
        elif doc_type == "Regulatory":
            filing_type = doc.get("filing_type", "")
            return f"{filing_type} Filing" if filing_type else "New Regulatory Filing"
            
        else:
            # Generic title
            return "New Construction Project Document"
    
    def _generate_lead_description(self, doc: Dict[str, Any]) -> str:
        """Generate a description for a lead based on document data.
        
        Args:
            doc: Processed document data
            
        Returns:
            Lead description string
        """
        # Start with document-specific descriptions
        doc_type = doc.get("document_type", "unknown").lower()
        
        if doc_type == "permit":
            desc_parts = []
            if doc.get("work_description"):
                desc_parts.append(f"Work Description: {doc['work_description']}")
            if doc.get("estimated_value"):
                desc_parts.append(f"Estimated Value: ${doc['estimated_value']:,.2f}")
            if doc.get("contractor"):
                desc_parts.append(f"Contractor: {doc['contractor']}")
            if doc.get("property_address") or doc.get("address"):
                address = doc.get("property_address") or doc.get("address")
                desc_parts.append(f"Location: {address}")
            if doc.get("permit_number"):
                desc_parts.append(f"Permit #: {doc['permit_number']}")
            if doc.get("issue_date"):
                desc_parts.append(f"Issued: {doc['issue_date']}")
                
            return "\n".join(desc_parts)
            
        elif doc_type == "contract":
            desc_parts = []
            if doc.get("party_a") and doc.get("party_b"):
                desc_parts.append(f"Contract between {doc['party_a']} and {doc['party_b']}")
            if doc.get("project_name"):
                desc_parts.append(f"Project: {doc['project_name']}")
            if doc.get("contract_amount"):
                desc_parts.append(f"Contract Amount: ${doc['contract_amount']:,.2f}")
            if doc.get("completion_date"):
                desc_parts.append(f"Completion Date: {doc['completion_date']}")
            elif doc.get("completion_duration"):
                desc_parts.append(f"Timeline: {doc['completion_duration']}")
            if doc.get("contract_date"):
                desc_parts.append(f"Contract Date: {doc['contract_date']}")
                
            return "\n".join(desc_parts)
            
        elif doc_type == "zoning":
            desc_parts = []
            if doc.get("request_description"):
                desc_parts.append(f"Request: {doc['request_description']}")
            if doc.get("property_address") or doc.get("address"):
                address = doc.get("property_address") or doc.get("address")
                desc_parts.append(f"Location: {address}")
            if doc.get("current_zoning") and doc.get("proposed_zoning"):
                desc_parts.append(f"Zoning Change: {doc['current_zoning']} to {doc['proposed_zoning']}")
            if doc.get("applicant"):
                desc_parts.append(f"Applicant: {doc['applicant']}")
            if doc.get("hearing_date"):
                desc_parts.append(f"Hearing Date: {doc['hearing_date']}")
            if doc.get("case_number"):
                desc_parts.append(f"Case #: {doc['case_number']}")
                
            return "\n".join(desc_parts)
            
        elif doc_type == "regulatory":
            desc_parts = []
            if doc.get("filing_type"):
                desc_parts.append(f"Filing Type: {doc['filing_type']}")
            if doc.get("project_name"):
                desc_parts.append(f"Project: {doc['project_name']}")
            if doc.get("applicant"):
                desc_parts.append(f"Applicant: {doc['applicant']}")
            if doc.get("authority"):
                desc_parts.append(f"Authority: {doc['authority']}")
            if doc.get("filing_date"):
                desc_parts.append(f"Filed: {doc['filing_date']}")
            if doc.get("filing_number"):
                desc_parts.append(f"Filing #: {doc['filing_number']}")
                
            return "\n".join(desc_parts)
            
        else:
            # For unknown document types, create a generic description
            desc_parts = []
            if doc.get("reference_number"):
                desc_parts.append(f"Reference #: {doc['reference_number']}")
            if doc.get("document_date"):
                desc_parts.append(f"Date: {doc['document_date']}")
            if doc.get("address"):
                desc_parts.append(f"Location: {doc['address']}")
            if doc.get("value_amount"):
                desc_parts.append(f"Value: ${doc['value_amount']:,.2f}")
            if doc.get("market_sector"):
                desc_parts.append(f"Sector: {doc['market_sector']}")
            
            # Add NLP extracted information if available
            if doc.get("entities", {}).get("organizations"):
                orgs = doc["entities"]["organizations"][:3]  # Limit to top 3
                desc_parts.append(f"Organizations: {', '.join(orgs)}")
                
            return "\n".join(desc_parts)

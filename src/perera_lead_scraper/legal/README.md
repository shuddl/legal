# Legal Document Analysis Module

## Overview

The Legal Document Analysis module provides specialized functionality for discovering high-value construction leads from legal documents such as building permits, construction contracts, zoning applications, and regulatory filings. This module builds on the base legal document processing capabilities of the Perera Construction Lead Scraper and adds advanced analysis, classification, and lead extraction features.

## Components

The module consists of the following key components:

### 1. `legal_document_analyzer.py`

The primary component for legal document analysis with the following capabilities:

- Advanced document analysis with multi-factor lead potential scoring
- Configurable thresholds for lead qualification
- Prioritization based on market sector, location, value, and project phase
- Exclusion of non-lead-worthy documents (e.g., minor repairs, signage)
- Batch processing for local document collections
- API integration for retrieving legal documents from external sources
- Automated lead extraction and conversion to standard lead format

### 2. Supporting Components

The Legal Document Analysis module integrates with and extends several existing components:

- `legal_processor.py`: Basic document processing pipeline
- `document_parser.py`: Document format parsing (PDF, DOCX, etc.)
- `document_validator.py`: Data validation and quality checks
- `legal_api.py`: Integration with external legal document APIs
- `nlp_processor.py`: NLP-based text analysis and entity extraction

## Usage Examples

### Analyzing a Single Document

```python
from perera_lead_scraper.legal.legal_document_analyzer import LegalDocumentAnalyzer

# Initialize analyzer
analyzer = LegalDocumentAnalyzer()

# Read and parse a document
document_text = """
BUILDING PERMIT #BP-2023-12345
123 Main St, Los Angeles, CA 90001
Description: New construction of a 5-story office building (50,000 sq ft)
Estimated Value: $25,000,000
"""

# Analyze the document
analysis = analyzer.analyze_document(document_text, document_type="permit")

# Check if the document meets lead requirements
if analysis.get("meets_requirements", False):
    # Extract a lead from the document
    lead = analyzer.extract_leads_from_document(document_text, document_type="permit")
    
    # Use the lead information
    print(f"Lead: {lead.title}")
    print(f"Value: ${lead.project_value:,}")
    print(f"Confidence: {lead.confidence:.2f}")
```

### Processing Local Document Collections

```python
from perera_lead_scraper.legal.legal_document_analyzer import LegalDocumentAnalyzer

# Initialize analyzer
analyzer = LegalDocumentAnalyzer()

# Extract leads from a directory of legal documents
leads = analyzer.extract_leads_from_local_documents("/path/to/legal/documents")

# Process the extracted leads
for lead in leads:
    print(f"Lead: {lead.title}")
    print(f"Location: {lead.location}")
    print(f"Market Sector: {lead.market_sector}")
    print(f"Value: ${lead.project_value:,}")
    print(f"Confidence: {lead.confidence:.2f}")
    print("---")
```

### Retrieving Leads from External APIs

```python
from perera_lead_scraper.legal.legal_document_analyzer import LegalDocumentAnalyzer

# Initialize analyzer
analyzer = LegalDocumentAnalyzer()

# Extract leads from a legal document API
leads = analyzer.extract_leads_from_api(
    provider="public_records",
    document_type="permit",
    location="Los Angeles",
    days=14,
    max_results=50
)

# Process the extracted leads
for lead in leads:
    print(f"Lead: {lead.title}")
    print(f"Source: {lead.source}")
    print(f"Value: ${lead.project_value:,}")
```

### Discovering Leads from Multiple Sources

```python
from perera_lead_scraper.legal.legal_document_analyzer import LegalDocumentAnalyzer

# Initialize analyzer
analyzer = LegalDocumentAnalyzer()

# Discover leads from all configured sources
# Sources are defined in your config/sources.json file
leads = analyzer.discover_leads_from_multiple_sources()

# Process the discovered leads
print(f"Discovered {len(leads)} leads")
for lead in leads:
    print(f"Lead: {lead.title}")
    print(f"Source: {lead.source}")
    print(f"Confidence: {lead.confidence:.2f}")
```

## Configuration

The module's behavior can be customized through the following configuration settings:

### Lead Qualification Settings

- `LEGAL_CONFIDENCE_THRESHOLD`: Minimum lead potential score to qualify (default: 0.6)
- `LEGAL_VALUE_THRESHOLD`: Minimum project value to qualify in dollars (default: $100,000)
- `LEGAL_PRIORITY_SECTORS`: List of priority market sectors
- `LEGAL_PRIORITY_LOCATIONS`: List of priority geographic locations
- `LEGAL_EXCLUSION_KEYWORDS`: List of terms that indicate non-lead-worthy projects

### Source Configuration

Legal document sources are configured in the main `config/sources.json` file:

```json
{
  "sources": [
    {
      "source_id": "la-permits",
      "name": "Los Angeles Building Permits",
      "source_type": "legal",
      "enabled": true,
      "config": {
        "source_type": "api",
        "api_provider": "permit_data",
        "document_type": "building",
        "location": "Los Angeles",
        "days": 14,
        "max_results": 50
      },
      "schedule": {
        "frequency": "daily",
        "time": "08:00"
      }
    },
    {
      "source_id": "contract-documents",
      "name": "Local Contract Documents",
      "source_type": "legal",
      "enabled": true,
      "config": {
        "source_type": "local",
        "path": "/data/legal_documents/contracts"
      },
      "schedule": {
        "frequency": "weekly",
        "day": "Monday",
        "time": "09:00"
      }
    }
  ]
}
```

## Lead Potential Scoring

The module uses a sophisticated multi-factor scoring system to assess lead potential:

1. **Relevance Score** (20%): Relevance to construction domain
2. **Value Score** (20%): Project value with logarithmic scaling
3. **Location Score** (15%): Match to priority locations
4. **Sector Score** (15%): Match to priority market sectors
5. **Keyword Score** (10%): Presence of high-priority construction terms
6. **Phase Score** (10%): Project phase (earlier phases score higher)
7. **Type Score** (10%): Document type relevance

Projects that score above the configured threshold (`LEGAL_CONFIDENCE_THRESHOLD`) and meet minimum value requirements (`LEGAL_VALUE_THRESHOLD`) are converted to leads.

## Integration with Lead Pipeline

The Legal Document Analysis module is designed to integrate with the Lead Extraction Pipeline:

```python
from perera_lead_scraper.legal.legal_document_analyzer import LegalDocumentAnalyzer
from perera_lead_scraper.pipeline.extraction_pipeline import ExtractionPipeline

# Initialize components
analyzer = LegalDocumentAnalyzer()
pipeline = ExtractionPipeline()

# Discover leads from legal documents
leads = analyzer.discover_leads_from_multiple_sources()

# Process the leads through the main pipeline
for lead in leads:
    processed_lead = pipeline.process_lead(lead)
    
    # Store or export the processed lead
    if processed_lead.is_valid:
        pipeline.store_lead(processed_lead)
```

## Testing

The module includes comprehensive unit tests in `tests/unit/test_legal_document_analyzer.py`. Run the tests with:

```bash
pytest tests/unit/test_legal_document_analyzer.py
```

## Command Line Interface

The module can be used via the command line interface:

```bash
# Process all legal sources
lead-scraper run --source-type legal

# Process a specific legal source
lead-scraper run --source la-permits

# Run the legal document analyzer on a specific file
python -m perera_lead_scraper.legal.legal_document_analyzer /path/to/document.pdf

# Run the legal document analyzer on a directory
python -m perera_lead_scraper.legal.legal_document_analyzer /path/to/documents
```
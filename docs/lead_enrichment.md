# Lead Enrichment Module Documentation

The Lead Enrichment module provides functionality to enhance construction lead data with additional company information, contact details, project insights, and other relevant data. This improves the quality and actionability of leads by adding valuable context for sales and business development teams.

## Overview

The `LeadEnricher` class is designed to take basic lead information and enrich it through various methods including:

- Company data lookup from business information providers
- Company website discovery using search engines and directories
- Contact information extraction from company websites and APIs
- Company size estimation
- Project stage determination
- Related project discovery
- Lead scoring

The module makes use of both API integrations and web scraping techniques, with built-in caching to improve performance and reduce API costs.

## Getting Started

### Basic Usage

To enrich a single lead:

```python
from perera_lead_scraper.enrichment.enrichment import LeadEnricher

# Initialize the enricher
enricher = LeadEnricher()

# Sample lead data
lead = {
    "title": "New Office Building Construction",
    "description": "Construction of a 5-story office building in downtown Seattle",
    "organization": "Acme Construction",
    "location": "Seattle, WA",
    "project_type": "Commercial",
    "project_value": "5000000"
}

# Enrich the lead
enriched_lead = enricher.enrich_lead(lead)

# Now you have a lead with additional information
print(f"Company Website: {enriched_lead.get('company_url')}")
print(f"Company Size: {enriched_lead.get('company_size')}")
print(f"Project Stage: {enriched_lead.get('project_stage')}")
print(f"Lead Score: {enriched_lead.get('lead_score', {}).get('total')}/100")
```

To enrich multiple leads in parallel:

```python
# List of leads
leads = [lead1, lead2, lead3, ...]

# Enrich all leads
enriched_leads = enricher.enrich_leads(leads)
```

## Configuration

The LeadEnricher can be configured using the standard AppConfig mechanism or by providing configuration overrides:

```python
from perera_lead_scraper.config import AppConfig
from perera_lead_scraper.enrichment.enrichment import LeadEnricher

# Create custom config
config = AppConfig()
config.set('enable_cache', True)
config.set('cache_ttl', 86400 * 7)  # 7 days
config.set('max_workers', 8)
config.set('target_markets', ['Seattle', 'Portland', 'San Francisco'])
config.set('target_sectors', ['Commercial', 'Healthcare', 'Education'])

# Initialize with custom config
enricher = LeadEnricher(config)
```

### API Credentials

To use external APIs for data enrichment, you'll need to set up API credentials. Create a file at:
`config/enrichment_api_credentials.json` with the following structure:

```json
{
  "company_data": {
    "base_url": "https://api.companydata.example.com/",
    "api_key": "your_api_key_here"
  },
  "contact_finder": {
    "base_url": "https://api.contactfinder.example.com/",
    "api_key": "your_api_key_here"
  },
  "business_directory": {
    "base_url": "https://api.businessdirectory.example.com/",
    "username": "your_username",
    "password": "your_password"
  },
  "project_database": {
    "base_url": "https://api.projectdatabase.example.com/",
    "api_key": "your_api_key_here"
  }
}
```

## Lead Scoring

The LeadEnricher includes a lead scoring system that evaluates leads on multiple factors:

- Company data completeness (15%)
- Contact details availability (20%)
- Project details completeness (15%)
- Project value (15%)
- Project timeliness (20%)
- Market fit (15%)

The score is calculated on a 0-100 scale with quality categories:
- 80-100: Excellent
- 60-79: Good
- 40-59: Average
- 20-39: Fair
- 0-19: Poor

## Web Scraping Considerations

The module includes web scraping capabilities for extracting contact information and other details. To ensure ethical and legal scraping:

1. The default request headers include a descriptive User-Agent
2. Requests are rate-limited and use appropriate timeouts
3. Proxies can be configured to distribute requests
4. Caching is enabled by default to minimize repeat requests

## Performance Optimization

The enrichment module is optimized for performance:

1. Built-in caching with TTL (Time-To-Live) support
2. Parallel processing of multiple leads
3. Timeout handlers to prevent hanging on slow APIs or websites
4. Automatic retry logic with backoff for API requests

## Error Handling

The module implements robust error handling:

1. Exceptions are caught and logged
2. Partial enrichment is returned when possible
3. Rate limit detection and handling
4. Custom exception classes for different error types

## Adding New Data Sources

To add a new data source for enrichment:

1. Add credentials to the `enrichment_api_credentials.json` file
2. Extend the `_get_auth_headers` method with the new provider
3. Implement a provider-specific method in the LeadEnricher class
4. Update the `enrich_lead` method to use the new data source

## Integration with Pipeline

To integrate the LeadEnricher into the extraction pipeline:

```python
from perera_lead_scraper.pipeline.extraction_pipeline import LeadExtractionPipeline
from perera_lead_scraper.enrichment.enrichment import LeadEnricher

# Initialize the enricher
enricher = LeadEnricher()

# Custom enrichment function for the pipeline
def custom_enrich_leads(leads):
    return enricher.enrich_leads(leads)

# Create pipeline with custom enrichment function
pipeline = LeadExtractionPipeline()

# Replace the default enrichment method
pipeline.enrich_leads = custom_enrich_leads

# Process sources with enrichment enabled
pipeline.enable_stage(PipelineStage.ENRICHMENT)
results = pipeline.process_sources(sources)
```
# Legal Document API Integration

This document describes how to use the Legal API module for extracting construction leads from various legal document providers.

## Overview

The Legal API integration allows the Perera Construction Lead Scraper to connect to external legal document APIs and automatically extract construction project leads from:

- Building permits
- Construction contracts
- Zoning applications
- Regulatory filings
- Court records

This functionality provides a valuable source of early-stage project leads directly from authoritative legal sources.

## Supported API Providers

The module currently supports the following types of API providers:

1. **Public Records** (`public_records`): General public records databases containing permits, contracts, and more
2. **Permit Data** (`permit_data`): Building permit-specific APIs from local governments or aggregators
3. **Contract Finder** (`contract_finder`): Construction contract databases and procurement systems
4. **Court Records** (`court_records`): Court filing systems containing construction litigation and contracts
5. **Regulatory Filings** (`regulatory_filings`): Environmental, zoning, and regulatory approval systems

## Configuration

### API Credentials

To set up the API integration, you need to create a credentials file:

1. Copy the example credentials file:
   ```bash
   cp config/legal_api_credentials_example.json config/legal_api_credentials.json
   ```

2. Edit the file to include your specific API credentials:
   ```json
   {
     "public_records": {
       "base_url": "https://api.publicrecords.example.com/",
       "api_key": "your_api_key_here"
     },
     "permit_data": {
       "base_url": "https://permitdata.example.com/",
       "username": "your_username",
       "password": "your_password"
     }
   }
   ```

### Source Configuration

Add API sources to your `config/sources.json` file:

```json
{
  "sources": [
    {
      "source_id": "sf-permit-api",
      "name": "San Francisco Permit API",
      "source_type": "legal",
      "enabled": true,
      "config": {
        "source_type": "api",
        "api_provider": "permit_data",
        "document_type": "building",
        "location": "San Francisco",
        "days": 14,
        "max_results": 50
      },
      "schedule": {
        "frequency": "daily",
        "time": "08:00"
      }
    }
  ]
}
```

## Source Configuration Options

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| source_type | Must be "api" for API-based sources | Yes | - |
| api_provider | One of the supported provider types | Yes | - |
| document_type | Type of document to search for (e.g., "building", "zoning") | No | - |
| location | Location to filter by (e.g., "San Francisco") | No | - |
| days | Number of days to look back | No | 7 |
| max_results | Maximum number of results to return | No | 25 |

## Authentication Methods

Different API providers require different authentication methods:

- **API Key** (`public_records`, `contract_finder`, `regulatory_filings`): Uses a Bearer token or API key header
- **Basic Auth** (`permit_data`): Uses username/password for HTTP Basic authentication
- **OAuth** (`court_records`): Uses client ID and secret for OAuth token-based authentication

## Document Processing

When a legal document is retrieved from an API, the system:

1. Downloads the document content (typically in PDF format)
2. Parses the document into text using the document parser
3. Processes the text to extract structured information
4. Validates the extracted information against rules
5. Transforms the validated information into a lead object
6. Passes the lead to the extraction pipeline for further processing

## Adding a New API Provider

To add support for a new legal document API:

1. Add credentials to your `legal_api_credentials.json` file
2. Update authentication method in `_get_auth_headers()` if needed
3. Add endpoint mapping in `_get_search_endpoint()`, `_get_document_endpoint()`, and `_get_download_endpoint()`
4. Add response parsing logic in `_extract_search_results()`
5. Configure a source in `sources.json` to use the new provider

## Running the Integration

To run the legal API integration:

```bash
# Run all legal sources
lead-scraper run --source-type legal

# Run a specific legal source
lead-scraper run --source sf-permit-api
```

## Troubleshooting

Common issues and their solutions:

- **Authentication errors**: Verify your API credentials and check if they need to be refreshed.
- **Rate limit errors**: Adjust your scraping schedule to stay within API rate limits.
- **Document parsing errors**: Ensure the document format is supported.
- **Empty results**: Check search parameters, especially date ranges and location filters.

For more detailed logging, set `LOG_LEVEL=DEBUG` in your `.env` file.
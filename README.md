# Perera Construction Lead Scraper

A specialized tool for automatically gathering, processing, and managing construction project leads from various sources including city permit databases, industry websites, RSS feeds, and more.

## Overview

The Perera Construction Lead Scraper is designed to automate the process of finding new construction project opportunities in target markets. It can scrape data from:

- RSS feeds from construction industry news sources
- City planning portals and permit databases
- Construction industry news websites
- Legal document APIs (building permits, contracts, zoning applications)
- Local legal document files
- Other industry-specific data sources

The system processes the raw data, standardizes it into a consistent lead format, enriches it with additional information, and can export it to HubSpot CRM or CSV/JSON files.

## Key Features

- **Multi-source data collection**: RSS feeds, websites, city portals, APIs, legal documents
- **Intelligent filtering**: Market sector identification, duplicate detection
- **Location-based targeting**: Focus on specific geographic regions
- **Legal document processing**: Extract leads from permits, contracts, zoning applications
- **Lead enrichment**: Estimate project values, extract contacts
- **NLP processing**: Extract entities, classify documents, analyze sentiment
- **CRM integration**: Direct sync with HubSpot
- **Comprehensive logging**: Detailed activity tracking
- **Configurable scheduling**: Automated data collection

## Installation

### Prerequisites

- Python 3.9 or later
- pip (Python package installer)
- Git

### Installation Steps

1. Clone the repository:
   ```bash
   git clone https://github.com/pereraconstruction/lead-scraper.git
   cd lead-scraper
   ```

2. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```

3. Install the package and dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. Install browser drivers for Playwright:
   ```bash
   playwright install
   ```

5. Create and configure your environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Configuration

Configuration is managed through environment variables (ideally in a `.env` file) and JSON configuration files in the `config/` directory.

### Environment Variables

Key variables to configure:

- `HUBSPOT_API_KEY`: Your HubSpot API key (required for CRM integration)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `SCRAPE_INTERVAL_HOURS`: How often to run the scraper (defaults to 24)
- `MAX_LEADS_PER_RUN`: Maximum number of leads to process per run
- `EXPORT_TO_HUBSPOT`: Whether to export leads to HubSpot (true/false)
- `LOG_FILE_PATH`: Path to the log file

See `.env.example` for a complete list of configuration options.

### Source Configuration

- `config/sources.json`: Main source registry
- `config/rss_sources.json`: RSS feed configurations
- `config/city_portals.json`: City planning portal configurations
- `config/news_sources.json`: News website configurations
- `config/legal_api_credentials.json`: Legal API authentication credentials
- `config/legal_patterns.json`: Regular expression patterns for legal document parsing
- `config/legal_validation_rules.json`: Validation rules for legal documents
- `config/hubspot_config.json`: HubSpot integration configuration

See the `config/` directory for example configuration files.

## Usage

### Command Line Interface

The scraper can be run from the command line with various options:

```bash
# Run all scrapers
lead-scraper run

# Run specific source
lead-scraper run --source construction_dive

# Run only RSS sources
lead-scraper run --source-type rss

# Check source availability
lead-scraper test-sources

# Export leads to CSV
lead-scraper export --format csv --output leads.csv

# Sync validated leads to HubSpot
lead-scraper sync-hubspot

# View application status
lead-scraper status

# List configured sources
lead-scraper list-sources
```

### Scheduled Execution

For regular execution, set up a cron job or scheduled task:

```bash
# Run the scraper daily at 3 AM
0 3 * * * cd /path/to/lead-scraper && /path/to/venv/bin/lead-scraper run >> /path/to/cron.log 2>&1
```

## Development

### Project Structure

```
lead-scraper/
├── config/                 # Configuration files
├── data/                   # Data storage
├── logs/                   # Log files
├── scripts/                # Utility scripts
├── src/                    # Source code
│   └── perera_lead_scraper/
│       ├── scrapers/       # Data source scrapers
│       ├── processors/     # Data processing logic
│       ├── pipeline/       # Lead extraction pipeline
│       ├── integrations/   # External system integrations
│       ├── legal/          # Legal document processing
│       │   ├── legal_api.py           # Legal API client
│       │   ├── legal_processor.py     # Legal document processor
│       │   ├── document_parser.py     # Document parsing utilities
│       │   └── document_validator.py  # Document validation utilities
│       ├── nlp/           # Natural language processing
│       ├── validation/    # Lead validation
│       ├── utils/          # Utility functions
│       ├── models/         # Data models
│       ├── config.py       # Configuration management
│       └── main.py         # Main entry point
├── tests/                  # Test suite
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── test_data/          # Test data files
├── .env.example            # Example environment variables
├── pyproject.toml          # Python project configuration
├── setup.py                # Package setup
└── README.md               # This file
```

### Development Commands

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=src

# Format code
black src tests

# Check code style
ruff src tests

# Type checking
mypy src
```

## Testing

The test suite is organized into unit tests and integration tests:

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run tests with verbose output
pytest -v
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- This project uses the HubSpot API for CRM integration
- Browser automation is powered by Playwright
- Web scraping components use Scrapy and BeautifulSoup
- Document parsing is performed using PyPDF2, pdfplumber, and python-docx
- NLP processing uses spaCy for entity extraction and classification

## Legal Document API Integration

This project includes a module for integrating with various legal document APIs to extract construction-related leads from:

- Building permits
- Construction contracts
- Zoning applications
- Regulatory filings
- Court records

To use the legal API features:

1. Copy `config/legal_api_credentials_example.json` to `config/legal_api_credentials.json`
2. Update the file with your API provider credentials
3. Configure sources in `config/sources.json` to use the legal API providers
4. Run the scraper with `lead-scraper run --source-type legal`

For more details on the API integration, see the documentation in `/docs/legal_api_integration.md`.
# Perera Construction Lead Scraper

A comprehensive system for automatically scraping, processing, and exporting construction project leads from various online sources.

![Perera Lead Scraper](docs/images/perera_lead_scraper_logo.png)

## Overview

The Perera Construction Lead Scraper is a specialized tool designed to help construction companies discover and process new business opportunities. It automatically scrapes construction leads from multiple sources, processes them to extract relevant information, evaluates lead quality, and exports them to your CRM or other business systems.

## Key Features

- **Multi-source Lead Generation**: Scrapes construction leads from various websites, public records, and bid platforms
- **Intelligent Processing**: Uses AI to extract project details, budgets, timelines, and contact information
- **Quality Scoring**: Automatically scores and prioritizes leads based on configurable criteria
- **CRM Integration**: Seamless export to HubSpot and other CRM systems
- **Customizable Filters**: Target specific regions, project types, and value ranges
- **Comprehensive Monitoring**: Built-in monitoring and reliability testing
- **RESTful API**: Full-featured API for integration with other systems
- **Docker Support**: Easy deployment using Docker and Docker Compose
- **Interactive Dashboard**: Visualize, manage, and analyze leads through a user-friendly web interface

## System Requirements

### Standalone Deployment
- Python 3.9+
- 2GB RAM (4GB recommended)
- 10GB disk space
- Internet connectivity

### Docker Deployment
- Docker and Docker Compose
- 2GB RAM (4GB recommended)
- 10GB disk space
- Internet connectivity

## Quick Start

### Docker Installation (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/perera-construction/lead-scraper.git
   cd lead-scraper
   ```

2. Create a `.env` file with your configuration:
   ```
   API_KEY=your_secure_api_key
   HUBSPOT_API_KEY=your_hubspot_api_key
   API_PORT=8000
   ```

3. Start the application:
   ```bash
   docker-compose up -d
   ```

4. Verify it's running:
   ```bash
   curl http://localhost:8000/api/health
   ```

5. Access the API documentation:
   ```
   http://localhost:8000/docs
   ```

### Standard Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/perera-construction/lead-scraper.git
   cd lead-scraper
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   ```bash
   export API_KEY=your_secure_api_key
   export HUBSPOT_API_KEY=your_hubspot_api_key
   ```

5. Run the application:
   ```bash
   python -m src.perera_lead_scraper.api.api
   ```

## Basic Usage

### Command Line Interface

Generate leads from all configured sources:
```bash
python -m src.perera_lead_scraper.cli generate
```

Export leads to CSV:
```bash
python -m src.perera_lead_scraper.cli export --format csv --output leads.csv
```

Run a specific data source:
```bash
python -m src.perera_lead_scraper.cli run-source --source-id SOURCE_ID
```

### Interactive Dashboard

The lead scraper includes a powerful interactive dashboard for visualizing and managing your leads:

1. Start the dashboard:
```bash
streamlit run scripts/lead_dashboard.py
```

2. Open your browser to the URL provided in the terminal (typically http://localhost:8501)

3. Use the dashboard to:
   - View all leads with powerful filtering and sorting
   - Analyze lead quality and distribution by market sector
   - Test lead enrichment and export processes
   - Visualize lead metrics with built-in charts
   - Export selected leads to CSV or HubSpot

### Live Scraping Testing

Test lead scraping in a simulated live environment:

```bash
# List all available sources
python scripts/test_live_scraping.py

# Test a specific source
python scripts/test_live_scraping.py --source SOURCE_ID --verbose

# Test all sources with NLP processing
python scripts/test_live_scraping.py --all --process --limit 3

# Test and store results
python scripts/test_live_scraping.py --all --process --store --output test_results/my_test.json
```

### API

Generate leads:
```bash
curl -X POST http://localhost:8000/api/triggers/generate \
  -H "X-API-Key: your_api_key"
```

Get all leads:
```bash
curl -X GET http://localhost:8000/api/leads \
  -H "X-API-Key: your_api_key"
```

Export leads:
```bash
curl -X POST http://localhost:8000/api/export \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"format": "csv", "filter": {"min_quality": 60}}'
```

## Documentation

- [Architecture](ARCHITECTURE.md) - System design and component overview
- [Deployment](DEPLOYMENT.md) - Detailed deployment instructions
- [API Documentation](API_DOCS.md) - API reference with examples
- [Configuration](CONFIGURATION.md) - Configuration options and formats
- [Customization](CUSTOMIZATION.md) - Extending and customizing the system
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues and solutions
- [Maintenance](MAINTENANCE.md) - Routine maintenance procedures
- [Monitoring](MONITORING.md) - System monitoring and alerting

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
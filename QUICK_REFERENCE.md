# Construction Lead Scraper - Quick Reference Guide

## Quick Start

### Installation
```bash
# Clone the repository
git clone https://github.com/your-org/construction-lead-scraper.git
cd construction-lead-scraper

# Using Docker (recommended)
docker-compose up -d

# Manual installation
pip install -r requirements.txt
python setup.py install
```

### Basic Usage

#### Running a Scraper
```bash
# Run all scrapers
python -m src.perera_lead_scraper.run_orchestrator

# Run a specific scraper
python -m scripts.run_scraper --scraper city_portal

# Schedule scraping
python -m src.perera_lead_scraper.scheduler.scheduler --schedule daily
```

#### Accessing the API
```
API Endpoint: http://localhost:8000/api/v1
Swagger UI: http://localhost:8000/docs
```

## Common Commands

### Container Management
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Restart a specific service
docker-compose restart scraper-api

# Stop all services
docker-compose down
```

### Data Management
```bash
# Export leads to CSV
python -m src.perera_lead_scraper.examples.export_example --format csv --output leads.csv

# Export to HubSpot
python -m src.perera_lead_scraper.hubspot.usage_example --sync-leads

# Generate database migrations
python generate_migration.py "add lead status column"
```

### Monitoring
```bash
# Check system health
bash scripts/healthcheck.sh

# View error logs
tail -f logs/error.log

# Monitor scraper performance
python -m src.perera_lead_scraper.monitoring.monitoring --report daily
```

## Configuration Reference

Key configuration files:

| File | Purpose |
|------|---------|
| `config/sources.json` | Data source definitions |
| `config/keywords.json` | Classification keywords |
| `config/city_portals.json` | City portal scraper config |
| `config/enrichment_api_credentials_example.json` | API credentials template |
| `config/hubspot_config.json` | HubSpot integration config |
| `config/legal_validation_rules.json` | Document validation rules |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/leads` | GET | Retrieve all leads |
| `/api/v1/leads/{id}` | GET | Get lead by ID |
| `/api/v1/leads/search` | POST | Search leads by criteria |
| `/api/v1/leads/export` | GET | Export leads (CSV/JSON) |
| `/api/v1/scraper/run` | POST | Trigger scraper run |
| `/api/v1/health` | GET | System health check |

## Common Patterns

### Adding a New Scraper
1. Create a new class that extends `BaseScraper`
2. Implement `extract()` and `transform()` methods
3. Register in `scrapers/__init__.py`
4. Add configuration in `config/sources.json`

### Adding a New Enrichment Source
1. Extend the `LeadEnricher` class
2. Implement source-specific lookup method
3. Register in the enrichment pipeline
4. Update configuration

### Customizing the Classification System
1. Edit `config/keywords.json` to modify classification criteria
2. Update classification threshold in lead classifier
3. Add or modify rules in the classification pipeline

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Scraper fails with HTTP errors | Check `city_portals.json` for updated selectors |
| API returns authentication error | Verify API credentials in config files |
| HubSpot sync failing | Check HubSpot API key and field mappings |
| Classification accuracy low | Update keywords and classification thresholds |
| Database migration errors | Run `alembic upgrade head` to apply latest migrations |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SCRAPER_LOG_LEVEL` | Logging verbosity | `INFO` |
| `SCRAPER_DB_URI` | Database connection URI | `sqlite:///./leads.db` |
| `SCRAPER_API_HOST` | API host address | `0.0.0.0` |
| `SCRAPER_API_PORT` | API port | `8000` |
| `SCRAPER_API_KEY` | API authentication key | None |
| `HUBSPOT_API_KEY` | HubSpot API key | None |
| `LEGAL_API_KEY` | Legal API authentication | None |

## Additional Resources

- [Complete Documentation](./README.md)
- [API Documentation](./API_DOCS.md)
- [Configuration Guide](./CONFIGURATION.md)
- [Architecture Overview](./ARCHITECTURE.md)
- [Troubleshooting Guide](./TROUBLESHOOTING.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [Customization Guide](./CUSTOMIZATION.md)
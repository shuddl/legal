# Perera Construction Lead Scraper - Handover Documentation

This document provides comprehensive knowledge transfer documentation for the Perera Construction Lead Scraper system. It covers the system architecture, operational procedures, maintenance requirements, and support processes to enable successful ongoing operation and maintenance.

## Table of Contents

- [System Overview](#system-overview)
- [System Architecture](#system-architecture)
- [Component Dependencies](#component-dependencies)
- [Configuration Management](#configuration-management)
- [Operational Procedures](#operational-procedures)
- [Troubleshooting Guide](#troubleshooting-guide)
- [Support Processes](#support-processes)
- [Maintenance Schedule](#maintenance-schedule)
- [Change Management](#change-management)
- [Disaster Recovery](#disaster-recovery)
- [Knowledge Base](#knowledge-base)
- [Contact Information](#contact-information)

## System Overview

The Perera Construction Lead Scraper is a specialized system designed for the automated discovery, processing, and management of construction project leads. The system performs the following key functions:

1. **Lead Extraction**: Automatically extracts construction project leads from multiple configurable sources.
2. **Lead Processing**: Processes raw lead data to extract structured information and enhance with additional context.
3. **Quality Assessment**: Analyzes leads to determine quality and relevance to target market sectors.
4. **Lead Storage**: Securely stores lead information in a structured database.
5. **Lead Export**: Exports processed leads to HubSpot CRM and other configurable formats.
6. **System Monitoring**: Monitors system health, performance, and data quality.

The system is designed to operate either standalone or as a containerized application using Docker.

## System Architecture

The system follows a modular architecture pattern with the following key components:

### Core Components

1. **Orchestrator** (`orchestrator.py`)
   - Central component that coordinates the lead generation process
   - Manages data sources and schedules scraping
   - Initializes and controls other components
   - Implements retry logic and error handling

2. **Data Sources** (`sources/`)
   - Pluggable data source implementations for different lead sources
   - Base class for common functionality (`BaseDataSource`)
   - Specialized implementations for different source types
   - Configuration-driven behavior

3. **Lead Storage** (`storage.py`)
   - Manages persistent storage of lead data
   - Provides CRUD operations for leads
   - Implements efficient querying and filtering
   - Handles data migration and backup

4. **Lead Processor** (`processing/`)
   - Processes raw lead data to extract structured information
   - Enhances leads with additional data
   - Scores lead quality based on configurable criteria
   - Filters leads based on relevance

5. **Export Manager** (`export/`)
   - Handles exporting leads to external systems
   - Support for various export formats (CSV, JSON, Excel)
   - HubSpot CRM integration
   - Email notifications with lead reports

6. **Monitoring System** (`monitoring/`)
   - Collects system performance metrics
   - Detects anomalies and issues
   - Generates alerts for critical problems
   - Creates performance reports

7. **API Server** (`api/`)
   - Provides RESTful API access to system functionality
   - Implements authentication and authorization
   - Provides documentation via Swagger/OpenAPI
   - Handles rate limiting and request validation

### Architecture Diagram

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Data Sources  │────▶│   Orchestrator   │────▶│  Lead Storage   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
       ▲                        │                         │
       │                        ▼                         ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Data Source    │     │  Lead Processor  │     │  Export Manager │
│  Registry       │     │  & Enrichment    │     └─────────────────┘
└─────────────────┘     └──────────────────┘              │
       ▲                        ▲                         ▼
       │                        │                ┌─────────────────┐
┌─────────────────┐     ┌──────────────────┐    │  External       │
│   CLI           │◀───▶│  API Layer       │◀───│  Systems        │
└─────────────────┘     └──────────────────┘    │  (HubSpot, etc) │
                              ▲                 └─────────────────┘
                              │                 
                      ┌──────────────────┐     
                      │   Monitoring &   │     
                      │   Alerting       │     
                      └──────────────────┘     
```

### Data Flow

1. **Acquisition Phase**:
   - Orchestrator triggers data sources to fetch leads
   - Data sources extract raw lead data from websites, APIs, or databases
   - Raw data is normalized to a common format

2. **Processing Phase**:
   - Raw lead data is processed to extract structured information
   - Leads are enriched with additional data
   - Leads are scored for quality and relevance
   - Duplicates are identified and merged

3. **Storage Phase**:
   - Processed leads are stored in the database
   - Existing leads are updated if new information is available
   - Lead history is tracked for changes

4. **Export Phase**:
   - Leads are filtered based on export criteria
   - Formatted for the target system (HubSpot, CSV, etc.)
   - Exported to external systems or sent via email
   - Export results are logged

5. **Monitoring & Feedback**:
   - Metrics are collected throughout the process
   - Anomalies are detected and alerts generated
   - System performance is logged and analyzed

## Component Dependencies

The system has the following key dependencies:

### Internal Dependencies

| Component | Depends On | Description |
|-----------|------------|-------------|
| Orchestrator | Data Sources, Lead Storage, Lead Processor, Export Manager | Coordinates and uses all other components |
| Data Sources | - | Base functionality for accessing lead sources |
| Lead Storage | - | Database operations for lead data |
| Lead Processor | Lead Storage | Processes and scores leads, updates storage |
| Export Manager | Lead Storage | Exports leads from storage to external systems |
| API Layer | Orchestrator, Lead Storage, Export Manager | Provides API access to core functionality |
| Monitoring | All components | Collects metrics from all components |

### External Dependencies

| Dependency | Version | Purpose | Component Using |
|------------|---------|---------|----------------|
| Python | ≥ 3.9 | Core runtime | All |
| SQLite | Built-in | Data storage | Lead Storage |
| FastAPI | 0.68.0 | API framework | API Layer |
| Uvicorn | 0.15.0 | ASGI server | API Layer |
| Requests | 2.26.0 | HTTP client | Data Sources |
| BeautifulSoup4 | 4.10.0 | HTML parsing | Data Sources |
| Pandas | 1.3.3 | Data manipulation | Lead Processor, Export Manager |
| HubSpot Client | 7.3.0 | HubSpot integration | Export Manager |
| Pydantic | 1.8.2 | Data validation | API Layer, Lead Processor |
| APScheduler | 3.8.1 | Task scheduling | Orchestrator |
| Psutil | 5.8.0 | System monitoring | Monitoring |

## Configuration Management

### Configuration Files

The system uses the following configuration files:

1. **`config.yml`** - Main configuration file with the following sections:
   - `storage` - Database configuration
   - `api` - API server settings
   - `sources` - Data source configurations
   - `export` - Export settings
   - `processing` - Lead processing settings
   - `monitoring` - Monitoring and alerting settings
   - `logging` - Logging configuration

Example:
```yaml
# Core configuration
version: "1.0.0"
environment: "production"

# API configuration
api:
  port: 8000
  host: "0.0.0.0"
  api_keys:
    - "your_api_key_here"

# Data sources configuration
sources:
  - name: "Government Bids"
    type: "government_bids"
    url: "https://example.com/bids"
    credentials:
      username: "user123"
      password: "password123"
    schedule: "0 */6 * * *"  # Every 6 hours
    config:
      region: "Northeast"
      project_types:
        - "commercial"
        - "institutional"
    is_active: true

# Export configuration
export:
  hubspot:
    api_key: "your_hubspot_api_key"
    field_mapping:
      name: "dealname"
      email: "email"
      # Additional field mappings...
  schedule: "0 8 * * 1"  # Every Monday at 8 AM
  formats:
    - "csv"
    - "hubspot"
```

2. **Environment Variables** - Can override configuration file settings:
   - `LEAD_SCRAPER_API_KEY` - API authentication key
   - `LEAD_SCRAPER_HUBSPOT_API_KEY` - HubSpot API key
   - `LEAD_SCRAPER_DB_PATH` - Database file path
   - `LEAD_SCRAPER_LOG_LEVEL` - Logging level
   - `LEAD_SCRAPER_PORT` - API server port

### Configuration Management Best Practices

1. **Version Control**
   - Store configuration templates in version control
   - Use environment-specific configuration files
   - Document all configuration changes

2. **Sensitive Information**
   - Never store API keys or passwords in version control
   - Use environment variables for sensitive information
   - Use a secure secrets management solution in production

3. **Configuration Validation**
   - Always validate configuration before deployment
   - Use the built-in configuration validation tool:
     ```bash
     python -m src.perera_lead_scraper.cli validate-config
     ```
   - Document all configuration parameters and valid values

4. **Configuration Changes**
   - Document all configuration changes
   - Test configuration changes in a staging environment
   - Back up configuration before making changes
   - Validate system operation after configuration changes

## Operational Procedures

### Standard Operating Procedures

#### System Startup

1. **Standard Deployment**
   ```bash
   # Start the API server
   python -m src.perera_lead_scraper.api.api &
   
   # Start the orchestrator
   python -m src.perera_lead_scraper.orchestrator &
   ```

2. **Docker Deployment**
   ```bash
   # Start all services
   docker-compose up -d
   
   # Check status
   docker-compose ps
   ```

#### System Shutdown

1. **Standard Deployment**
   ```bash
   # Find the process IDs
   ps aux | grep perera_lead_scraper
   
   # Gracefully terminate processes
   kill -TERM <api_pid> <orchestrator_pid>
   ```

2. **Docker Deployment**
   ```bash
   # Stop all services
   docker-compose down
   ```

#### Manual Operations

1. **Generate Leads Manually**
   ```bash
   # Using CLI
   python -m src.perera_lead_scraper.cli generate
   
   # Using API
   curl -X POST http://localhost:8000/api/triggers/generate \
     -H "X-API-Key: your_api_key"
   ```

2. **Export Leads Manually**
   ```bash
   # Using CLI
   python -m src.perera_lead_scraper.cli export --format csv --output leads.csv
   
   # Using API
   curl -X POST http://localhost:8000/api/export \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your_api_key" \
     -d '{"format": "csv", "filter": {"min_quality": 60}}'
   ```

3. **Add Data Source**
   ```bash
   # Using CLI
   python -m src.perera_lead_scraper.cli add-source --type government_bids --name "New Source" --url "https://example.com"
   
   # Using API
   curl -X POST http://localhost:8000/api/sources \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your_api_key" \
     -d '{
       "name": "New Source",
       "type": "government_bids",
       "url": "https://example.com",
       "credentials": {
         "username": "user123",
         "password": "password123"
       },
       "is_active": true
     }'
   ```

### Scheduled Tasks

The system includes the following scheduled tasks:

1. **Lead Generation**
   - Scheduled based on source configuration
   - Typically runs every 6-24 hours depending on source
   - Configurable via the `schedule` parameter for each source

2. **Lead Export**
   - Scheduled via the `export.schedule` configuration
   - Typically runs daily or weekly
   - Configurable using cron syntax

3. **System Maintenance**
   - Database optimization: Weekly
   - Metrics database cleanup: Monthly
   - Log rotation: Daily

### Monitoring

1. **Health Check**
   ```bash
   # Using API
   curl http://localhost:8000/api/health
   
   # Expected response (healthy system)
   {
     "status": "operational",
     "version": "1.0.0",
     "uptime": 123.45,
     "timestamp": "2023-01-01T00:00:00.000Z",
     "components": {
       "storage": {
         "status": "healthy",
         "lead_count": 100
       },
       "orchestrator": {
         "status": "healthy",
         "active_sources": 5
       },
       "monitor": {
         "status": "healthy",
         "metrics": {
           "cpu_percent": 12.3,
           "memory_percent": 45.6
         }
       }
     }
   }
   ```

2. **Log Monitoring**
   ```bash
   # Check for errors in logs
   grep ERROR logs/app.log
   
   # Follow logs in real-time
   tail -f logs/app.log
   ```

3. **Performance Metrics**
   ```bash
   # Using API
   curl http://localhost:8000/api/stats \
     -H "X-API-Key: your_api_key"
   ```

### Backup & Recovery

1. **Database Backup**
   ```bash
   # Using CLI
   python -m src.perera_lead_scraper.cli backup-db --output backups/leads_$(date +%Y%m%d).db
   
   # Manual SQLite backup
   sqlite3 data/leads.db ".backup backups/leads_$(date +%Y%m%d).db"
   ```

2. **Database Restore**
   ```bash
   # Using CLI
   python -m src.perera_lead_scraper.cli restore-db --backup-file backups/leads_20230101.db
   
   # Manual SQLite restore
   cp backups/leads_20230101.db data/leads.db
   ```

3. **Configuration Backup**
   ```bash
   # Copy configuration to backup location
   cp config.yml backups/config_$(date +%Y%m%d).yml
   ```

## Troubleshooting Guide

### Common Issues and Solutions

#### API Server Issues

1. **API Server Won't Start**

   *Symptoms:*
   - Error when starting API server
   - Port already in use message

   *Solutions:*
   - Check if another process is using the configured port
     ```bash
     netstat -tuln | grep 8000
     ```
   - Verify configuration file is valid
   - Check log for detailed error messages

2. **Authentication Failures**

   *Symptoms:*
   - 401 Unauthorized responses
   - "Invalid API Key" messages

   *Solutions:*
   - Verify API key in request header matches configuration
   - Check if API key is correctly configured
   - Ensure the `X-API-Key` header is correctly formatted

#### Data Source Issues

1. **Source Connection Failures**

   *Symptoms:*
   - Error messages when running sources
   - No leads generated from specific source

   *Solutions:*
   - Test source connection directly
     ```bash
     python -m src.perera_lead_scraper.cli test-source --source-id SOURCE_ID
     ```
   - Verify source URL is accessible
   - Check credentials are correct
   - Verify source website hasn't changed structure

2. **Rate Limiting Issues**

   *Symptoms:*
   - Source failures with 429 status codes
   - "Rate limited" error messages

   *Solutions:*
   - Reduce scraping frequency in configuration
   - Implement backoff strategy in source configuration
   - Split scraping across multiple sources if possible

#### Database Issues

1. **Database Corruption**

   *Symptoms:*
   - SQLite errors when accessing database
   - "database disk image is malformed" messages

   *Solutions:*
   - Run database integrity check
     ```bash
     sqlite3 data/leads.db "PRAGMA integrity_check;"
     ```
   - Restore from backup if necessary
   - If no backup is available, try to recover data
     ```bash
     sqlite3 data/leads.db ".dump" | sqlite3 recovered.db
     ```

2. **Performance Problems**

   *Symptoms:*
   - Slow queries
   - High disk I/O

   *Solutions:*
   - Optimize database with vacuum
     ```bash
     sqlite3 data/leads.db "VACUUM;"
     ```
   - Create indexes for commonly queried fields
   - Consider database migration to PostgreSQL for large datasets

#### Export Issues

1. **HubSpot Export Failures**

   *Symptoms:*
   - Error messages during HubSpot export
   - No leads appear in HubSpot

   *Solutions:*
   - Verify HubSpot API key is valid
   - Check HubSpot API quota/limits
   - Ensure field mapping is correct
   - Verify lead data meets HubSpot requirements

2. **Email Export Issues**

   *Symptoms:*
   - Export emails not being sent
   - SMTP errors in logs

   *Solutions:*
   - Verify SMTP server settings
   - Check email credentials
   - Test SMTP connection
     ```bash
     python -m src.perera_lead_scraper.cli test-smtp-connection
     ```
   - Check for email size limits if sending large exports

### Diagnostic Procedures

1. **System Health Check**
   ```bash
   # Check system health
   curl http://localhost:8000/api/health
   
   # Generate diagnostic report
   python -m src.perera_lead_scraper.cli generate-diagnostic-report
   ```

2. **Log Analysis**
   ```bash
   # Look for ERROR level messages
   grep ERROR logs/app.log
   
   # Look for specific component issues
   grep "data_source" logs/app.log | grep ERROR
   
   # Analyze error patterns
   python -m src.perera_lead_scraper.cli analyze-logs --pattern "ERROR" --days 7
   ```

3. **Database Checks**
   ```bash
   # Check database integrity
   sqlite3 data/leads.db "PRAGMA integrity_check;"
   
   # Check database statistics
   sqlite3 data/leads.db "PRAGMA stats;"
   
   # Get database size and table counts
   python -m src.perera_lead_scraper.cli db-stats
   ```

4. **Network Diagnostics**
   ```bash
   # Test connectivity to data sources
   for url in $(grep url config.yml | cut -d: -f2- | tr -d ' "'); do
     echo "Testing $url"
     curl -I $url
   done
   
   # Test HubSpot API connectivity
   python -m src.perera_lead_scraper.cli test-hubspot-connection
   ```

## Support Processes

### Support Levels

1. **Level 1 Support (Basic)**
   - User access issues
   - Basic configuration changes
   - Routine operational tasks
   - Documentation-guided troubleshooting

2. **Level 2 Support (Advanced)**
   - Complex configuration changes
   - Performance optimization
   - Data source troubleshooting
   - Integration issues

3. **Level 3 Support (Expert)**
   - Code-level issues
   - Database recovery
   - Security incidents
   - Custom development

### Escalation Procedures

1. **When to Escalate**
   - Issue not resolved within 2 hours
   - Issue affects multiple users or critical functionality
   - Issue involves data loss or security concerns
   - Issue requires code changes

2. **Escalation Path**
   - Level 1 → Level 2: After basic troubleshooting steps exhausted
   - Level 2 → Level 3: After advanced diagnostics performed
   - Level 3 → Development Team: For issues requiring code changes

3. **Escalation Information to Provide**
   - Detailed issue description
   - Steps already taken to resolve
   - Relevant log excerpts
   - System configuration
   - Diagnostic reports

### Support Resources

1. **Documentation**
   - System architecture documentation
   - API documentation
   - Troubleshooting guide
   - Configuration guide

2. **Tools**
   - Diagnostic tools in CLI module
   - Log analysis utilities
   - Database management tools
   - Monitoring dashboard

3. **Knowledge Base**
   - Common issues and solutions
   - Configuration examples
   - Performance tuning tips
   - Data source specifics

## Maintenance Schedule

### Daily Maintenance

1. **Health Check**
   - Verify system health status
   - Check for recent errors
   - Verify scheduled tasks are running

2. **Log Review**
   - Check for ERROR messages
   - Verify successful operations
   - Look for unusual patterns

### Weekly Maintenance

1. **Database Optimization**
   ```bash
   # Optimize database
   python -m src.perera_lead_scraper.cli optimize-db
   ```

2. **Backup Verification**
   - Verify backups are being created
   - Test restore procedure periodically
   - Ensure backup storage has sufficient space

3. **Source Verification**
   - Test all data sources
   - Verify connection and data extraction
   - Update source configuration if needed

### Monthly Maintenance

1. **Performance Review**
   - Generate and review performance report
   - Identify trends and potential issues
   - Make optimization recommendations

2. **Data Cleanup**
   - Archive old data according to retention policy
   - Clean up temporary files
   - Remove unnecessary exports

3. **Security Review**
   - Rotate API keys
   - Check for dependency updates
   - Review access logs for suspicious activity

### Quarterly Maintenance

1. **System Update**
   - Apply system updates
   - Update dependencies
   - Implement new features

2. **Full Backup**
   - Create full system backup
   - Verify backup integrity
   - Document backup location and contents

3. **Configuration Review**
   - Review all configuration settings
   - Update documentation
   - Optimize configuration for current usage patterns

## Change Management

### Change Categories

1. **Minor Changes**
   - Configuration adjustments
   - Data source updates
   - Non-disruptive maintenance

2. **Major Changes**
   - System upgrades
   - Database schema changes
   - Integration changes
   - Security-related changes

3. **Emergency Changes**
   - Critical bug fixes
   - Security vulnerability patches
   - Addressing system outages

### Change Process

1. **Change Request**
   - Document change purpose
   - Describe changes to be made
   - Assess impact and risk
   - Define testing requirements
   - Create rollback plan

2. **Change Approval**
   - Review by technical team
   - Sign-off by business stakeholders
   - Schedule change window

3. **Change Implementation**
   - Create backup before change
   - Implement change according to plan
   - Test functionality after change
   - Document actual changes made

4. **Change Review**
   - Verify change effectiveness
   - Document any issues encountered
   - Update documentation
   - Share lessons learned

### Rollback Procedures

1. **Configuration Rollback**
   ```bash
   # Restore previous configuration
   cp backups/config_20230101.yml config.yml
   
   # Restart services
   # For standard deployment
   kill -TERM <api_pid> <orchestrator_pid>
   python -m src.perera_lead_scraper.api.api &
   python -m src.perera_lead_scraper.orchestrator &
   
   # For Docker deployment
   docker-compose down
   docker-compose up -d
   ```

2. **Database Rollback**
   ```bash
   # Restore database from backup
   python -m src.perera_lead_scraper.cli restore-db --backup-file backups/leads_20230101.db
   ```

3. **Code Rollback**
   ```bash
   # Revert to previous version
   git checkout v1.0.0  # Or specific tag/commit
   
   # Reinstall dependencies
   pip install -r requirements.txt
   
   # Restart services
   # ...
   ```

## Disaster Recovery

### Disaster Scenarios

1. **Data Loss**
   - Database corruption
   - Accidental deletion
   - Storage failure

2. **System Failure**
   - Server hardware failure
   - Operating system corruption
   - Critical dependency failure

3. **Security Incident**
   - Unauthorized access
   - Credential compromise
   - Data breach

### Recovery Procedures

1. **Data Recovery**
   - Identify extent of data loss
   - Restore from latest backup
   - Verify data integrity
   - Re-process any data missing since backup

2. **System Recovery**
   - Deploy system to new environment if necessary
   - Restore configuration from backup
   - Restore database from backup
   - Verify system functionality

3. **Security Incident Recovery**
   - Isolate affected components
   - Reset all credentials
   - Deploy from clean source
   - Restore data from verified clean backup
   - Implement additional security measures

### Business Continuity

1. **Manual Procedures**
   - Document manual lead collection process
   - Prepare manual export procedures
   - Train team on manual operations

2. **Alternative Sources**
   - Identify backup data sources
   - Document direct access procedures
   - Prepare alternative export methods

3. **Communication Plan**
   - Define stakeholder notification process
   - Prepare templates for incident communication
   - Document escalation contacts

## Knowledge Base

### Frequently Asked Questions

1. **How do I add a new data source?**
   
   Use the API or CLI to add a new source:
   ```bash
   python -m src.perera_lead_scraper.cli add-source --type government_bids --name "New Source" --url "https://example.com"
   ```
   
   Or use the API:
   ```bash
   curl -X POST http://localhost:8000/api/sources \
     -H "Content-Type: application/json" \
     -H "X-API-Key: your_api_key" \
     -d '{
       "name": "New Source",
       "type": "government_bids",
       "url": "https://example.com",
       "is_active": true
     }'
   ```

2. **How do I customize lead quality scoring?**
   
   Edit the quality scoring configuration in `config.yml`:
   ```yaml
   processing:
     quality:
       weights:
         has_email: 10
         has_phone: 10
         has_project_value: 15
         project_description_length: 0.1  # per character
         project_value_factor: 0.00001  # per dollar
       thresholds:
         minimum_acceptable: 50
         high_quality: 75
   ```

3. **How do I troubleshoot a failing data source?**
   
   Test the source connection directly:
   ```bash
   python -m src.perera_lead_scraper.cli test-source --source-id SOURCE_ID
   ```
   
   Check the logs for specific errors:
   ```bash
   grep "source_name" logs/app.log | grep ERROR
   ```
   
   Update source selectors if the website structure has changed.

4. **How do I customize HubSpot field mapping?**
   
   Edit the HubSpot field mapping in `config.yml`:
   ```yaml
   export:
     hubspot:
       field_mapping:
         name: "dealname"
         email: "email"
         company: "company"
         phone: "phone"
         project_type: "project_type"
         project_value: "amount"
         project_description: "description"
   ```

### Common Customizations

1. **Adding a Custom Data Source**
   
   Create a new source class in the `sources` directory:
   ```python
   # src/perera_lead_scraper/sources/custom_source.py
   from perera_lead_scraper.sources.base import BaseDataSource
   
   class CustomSource(BaseDataSource):
       source_type = "custom_source"
       
       def __init__(self, config=None):
           super().__init__(config or {})
           # Initialize source-specific attributes
           
       def fetch_data(self):
           # Implement data fetching logic
           # Return list of dictionaries with lead data
   ```
   
   Register the source in `sources/__init__.py`:
   ```python
   from perera_lead_scraper.sources.custom_source import CustomSource
   
   AVAILABLE_SOURCES = {
       # ... existing sources ...
       CustomSource.source_type: CustomSource,
   }
   ```

2. **Customizing Lead Processing**
   
   Create a custom processor in the `processing` directory:
   ```python
   # src/perera_lead_scraper/processing/custom_processor.py
   from perera_lead_scraper.processing.base_processor import BaseProcessor
   
   class CustomProcessor(BaseProcessor):
       def process(self, lead):
           # Custom processing logic
           # Modify lead object
           return lead
   ```
   
   Register the processor in `processing/__init__.py`:
   ```python
   from perera_lead_scraper.processing.custom_processor import CustomProcessor
   
   PROCESSORS = [
       # ... existing processors ...
       CustomProcessor,
   ]
   ```

3. **Customizing Export Format**
   
   Create a custom exporter in the `export` directory:
   ```python
   # src/perera_lead_scraper/export/custom_exporter.py
   from perera_lead_scraper.export.base_exporter import BaseExporter
   
   class CustomExporter(BaseExporter):
       format_name = "custom"
       
       def export(self, leads, output_path):
           # Implement custom export logic
           # Write leads to output_path in custom format
           return output_path
   ```
   
   Register the exporter in `export/__init__.py`:
   ```python
   from perera_lead_scraper.export.custom_exporter import CustomExporter
   
   EXPORTERS = {
       # ... existing exporters ...
       "custom": CustomExporter,
   }
   ```

### Performance Optimization Tips

1. **Database Optimization**
   - Add indexes for frequently queried fields
   - Run VACUUM regularly to optimize database
   - Use query parameterization to improve performance

2. **Memory Usage**
   - Process leads in batches for large datasets
   - Implement pagination for large result sets
   - Close database connections when not in use

3. **API Performance**
   - Implement caching for frequently accessed endpoints
   - Use compression for large responses
   - Optimize query patterns to minimize database load

## Contact Information

### Support Contacts

| Role | Name | Email | Phone | Responsibility |
|------|------|-------|-------|----------------|
| Primary Support | Support Team | support@example.com | (555) 123-4567 | Level 1 & 2 Support |
| Technical Lead | Tech Lead | techlead@example.com | (555) 234-5678 | Level 3 Support |
| Project Manager | PM Name | pm@example.com | (555) 345-6789 | Escalation Contact |
| Emergency Contact | On-Call Engineer | oncall@example.com | (555) 456-7890 | 24/7 Emergency Support |

### Developer Contacts

| Component | Responsible Developer | Email | Expertise |
|-----------|----------------------|-------|-----------|
| Data Sources | Dev Name | dev1@example.com | Web scraping, API integration |
| Lead Processing | Dev Name | dev2@example.com | NLP, data enrichment |
| Database | Dev Name | dev3@example.com | Database optimization, data modeling |
| Export System | Dev Name | dev4@example.com | HubSpot integration, reporting |
| API Layer | Dev Name | dev5@example.com | FastAPI, REST APIs |
| Monitoring | Dev Name | dev6@example.com | Metrics, alerting, diagnostics |

### Vendor Contacts

| Service | Vendor | Contact | Account ID | Support URL |
|---------|--------|---------|------------|-------------|
| HubSpot | HubSpot Support | support@hubspot.com | ACCOUNT-ID | https://help.hubspot.com |
| Hosting | Hosting Provider | support@hostingprovider.com | ACCOUNT-ID | https://support.hostingprovider.com |
| Domain | Domain Registrar | support@registrar.com | ACCOUNT-ID | https://support.registrar.com |

---

This handover document provides comprehensive knowledge transfer information for the Perera Construction Lead Scraper system. It should be used as the primary reference for operating and maintaining the system.
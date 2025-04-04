# Perera Construction Lead Scraper - Configuration Guide

This document provides detailed information about configuring the Perera Construction Lead Scraper system.

## Table of Contents

- [Configuration Overview](#configuration-overview)
- [Configuration Methods](#configuration-methods)
- [Core Configuration Options](#core-configuration-options)
- [Data Source Configuration](#data-source-configuration)
- [Export Configuration](#export-configuration)
- [Monitoring Configuration](#monitoring-configuration)
- [API Configuration](#api-configuration)
- [Notification Configuration](#notification-configuration)
- [Scheduling Configuration](#scheduling-configuration)
- [Advanced Configuration](#advanced-configuration)
- [Environment Variables](#environment-variables)
- [Sensitive Configuration](#sensitive-configuration)
- [Configuration Validation](#configuration-validation)

## Configuration Overview

The Perera Construction Lead Scraper can be configured through several methods, with the following precedence (highest to lowest):

1. Command-line arguments
2. Environment variables
3. Configuration file (`config.yml`)
4. Default values

## Configuration Methods

### Configuration File

The primary method for configuring the system is through a YAML configuration file. By default, the system looks for `config.yml` in the root directory of the project.

Example `config.yml`:

```yaml
# Core configuration
version: "1.0.0"
environment: "production"

# API configuration
api:
  port: 8000
  host: "0.0.0.0"
  debug: false
  api_keys:
    - "your_secure_api_key_here"
  cors_allow_origins:
    - "*"

# Data storage configuration
storage:
  type: "sqlite"
  path: "data/leads.db"
  backup_interval: 86400  # 24 hours

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

  - name: "Permit Data"
    type: "permit_data"
    url: "https://permits.example.com/api"
    credentials:
      api_key: "your_api_key_here"
    schedule: "0 0 * * *"  # Daily at midnight
    config:
      regions:
        - "New York"
        - "Massachusetts"
        - "Connecticut"
      min_value: 100000
    is_active: true

# Export configuration
export:
  hubspot:
    api_key: "your_hubspot_api_key"
    field_mapping:
      name: "dealname"
      email: "email"
      # Additional field mappings...
  email:
    enabled: true
    smtp_server: "smtp.example.com"
    smtp_port: 587
    username: "exports@example.com"
    password: "your_smtp_password"
    from_address: "exports@example.com"
    recipients:
      - "manager@example.com"
  schedule: "0 8 * * 1"  # Every Monday at 8 AM
  formats:
    - "csv"
    - "hubspot"

# Monitoring configuration
monitoring:
  metrics_interval: 300  # 5 minutes
  report_interval: 86400  # 24 hours
  thresholds:
    cpu_percent: 80
    memory_percent: 80
    disk_percent: 90
    error_rate: 0.1
  alerting:
    enabled: true
    channels:
      - email
      - webhook
    email:
      recipients:
        - "alerts@example.com"
    webhook:
      url: "https://hooks.example.com/alert"
      headers:
        Authorization: "Bearer your_webhook_token"

# Processing configuration
processing:
  quality_threshold: 50
  max_leads_per_source: 1000
  enrichment:
    enabled: true
    services:
      - "company_lookup"
      - "contact_verification"
  deduplication:
    enabled: true
    match_fields:
      - "name"
      - "company"
      - "address"
    similarity_threshold: 0.8

# Logging configuration
logging:
  level: "INFO"
  file: "logs/app.log"
  max_size: 10485760  # 10 MB
  backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### Environment Variables

You can override configuration options using environment variables. The system converts environment variables to configuration options using the following rules:

1. All environment variables are prefixed with `LEAD_SCRAPER_`
2. Nested configuration uses double underscores (`__`) as separators
3. Lists can be provided as comma-separated values

Example environment variables:

```bash
# Core configuration
LEAD_SCRAPER_ENVIRONMENT=production

# API configuration
LEAD_SCRAPER_API__PORT=8000
LEAD_SCRAPER_API__HOST=0.0.0.0
LEAD_SCRAPER_API__DEBUG=false
LEAD_SCRAPER_API__API_KEYS=your_secure_api_key_here

# Storage configuration
LEAD_SCRAPER_STORAGE__TYPE=sqlite
LEAD_SCRAPER_STORAGE__PATH=data/leads.db

# Export configuration
LEAD_SCRAPER_EXPORT__HUBSPOT__API_KEY=your_hubspot_api_key
LEAD_SCRAPER_EXPORT__EMAIL__ENABLED=true
LEAD_SCRAPER_EXPORT__EMAIL__SMTP_SERVER=smtp.example.com
LEAD_SCRAPER_EXPORT__EMAIL__SMTP_PORT=587
LEAD_SCRAPER_EXPORT__EMAIL__USERNAME=exports@example.com
LEAD_SCRAPER_EXPORT__EMAIL__PASSWORD=your_smtp_password
LEAD_SCRAPER_EXPORT__EMAIL__RECIPIENTS=manager@example.com

# Monitoring configuration
LEAD_SCRAPER_MONITORING__METRICS_INTERVAL=300
LEAD_SCRAPER_MONITORING__ALERTING__ENABLED=true
LEAD_SCRAPER_MONITORING__ALERTING__CHANNELS=email,webhook

# Logging configuration
LEAD_SCRAPER_LOGGING__LEVEL=INFO
LEAD_SCRAPER_LOGGING__FILE=logs/app.log
```

### Command Line Arguments

Some options can be provided as command-line arguments when running the application:

```bash
# Running the API server
python -m src.perera_lead_scraper.api.api --port 8080 --host 0.0.0.0 --log-level DEBUG

# Running the CLI
python -m src.perera_lead_scraper.cli generate --sources government_bids,permit_data
python -m src.perera_lead_scraper.cli export --format csv --output leads.csv --min-quality 70
```

## Core Configuration Options

### General Settings

| Option | Description | Default | Environment Variable |
|--------|-------------|---------|---------------------|
| version | System version | "1.0.0" | LEAD_SCRAPER_VERSION |
| environment | Environment (development, staging, production) | "development" | LEAD_SCRAPER_ENVIRONMENT |
| temp_dir | Directory for temporary files | "temp" | LEAD_SCRAPER_TEMP_DIR |
| data_dir | Directory for data files | "data" | LEAD_SCRAPER_DATA_DIR |
| exports_dir | Directory for export files | "exports" | LEAD_SCRAPER_EXPORTS_DIR |
| logs_dir | Directory for log files | "logs" | LEAD_SCRAPER_LOGS_DIR |

## Data Source Configuration

Data sources are configured in the `sources` section of the configuration file as a list of source objects.

### Common Source Options

| Option | Description | Default | Required |
|--------|-------------|---------|----------|
| name | Human-readable name for the source | | Yes |
| type | Source type identifier | | Yes |
| url | Base URL for the source | | Yes |
| credentials | Authentication credentials | {} | No |
| schedule | Cron expression for scheduling | | Yes |
| config | Source-specific configuration | {} | No |
| is_active | Whether the source is active | true | No |

### Source Type-Specific Configuration

#### Government Bids Source

```yaml
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
      min_value: 100000
      max_results: 200
      selectors:
        bid_items: ".bid-listing .bid-item"
        title: ".bid-title"
        description: ".bid-description"
        value: ".bid-value"
        deadline: ".bid-deadline"
        contact: ".contact-info"
```

#### Permit Data Source

```yaml
sources:
  - name: "Permit Data"
    type: "permit_data"
    url: "https://permits.example.com/api"
    credentials:
      api_key: "your_api_key_here"
    schedule: "0 0 * * *"  # Daily at midnight
    config:
      regions:
        - "New York"
        - "Massachusetts"
        - "Connecticut"
      min_value: 100000
      permit_types:
        - "new_construction"
        - "major_renovation"
      date_range_days: 7
      batch_size: 100
```

## Export Configuration

The export configuration controls how leads are exported to external systems.

### HubSpot Export

```yaml
export:
  hubspot:
    api_key: "your_hubspot_api_key"
    field_mapping:
      email: "email"
      name: "firstname"
      company: "company"
      phone: "phone"
      name: "dealname"
      project_type: "pipeline"
      project_value: "amount"
      project_description: "description"
      address: "address"
      quality_score: "lead_quality_score"
      source: "lead_source"
      source_url: "source_url"
    pipeline_mapping:
      commercial:
        pipeline: "commercial_projects"
        stage: "qualificationready"
      residential:
        pipeline: "residential_projects"
        stage: "appointmentscheduled"
      default:
        pipeline: "default"
        stage: "appointmentscheduled"
```

### Email Export

```yaml
export:
  email:
    enabled: true
    smtp_server: "smtp.example.com"
    smtp_port: 587
    username: "exports@example.com"
    password: "your_smtp_password"
    from_address: "exports@example.com"
    recipients:
      - "manager@example.com"
    subject_template: "Lead Export - {date}"
    body_template: "Please find attached the latest leads export."
    use_tls: true
```

### Export Schedule

```yaml
export:
  schedule: "0 8 * * 1"  # Every Monday at 8 AM
  formats:
    - "csv"
    - "json"
    - "xlsx"
    - "hubspot"
  min_quality: 60
  statuses:
    - "new"
    - "contacted"
```

## Monitoring Configuration

The monitoring configuration controls system monitoring, metrics collection, and alerting.

### Metrics Collection

```yaml
monitoring:
  metrics_interval: 300  # 5 minutes
  report_interval: 86400  # 24 hours
  metrics_database: "data/metrics.db"
  include_metrics:
    - "cpu_percent"
    - "memory_percent"
    - "disk_percent"
    - "lead_count"
    - "processing_time"
    - "success_rate"
    - "error_count"
```

### Threshold Configuration

```yaml
monitoring:
  thresholds:
    cpu_percent: 80
    memory_percent: 80
    disk_percent: 90
    error_rate: 0.1
    processing_time: 10
    success_rate: 0.9
```

### Alerting Configuration

```yaml
monitoring:
  alerting:
    enabled: true
    channels:
      - email
      - webhook
    cooldown_period: 3600  # 1 hour between repeated alerts
    email:
      recipients:
        - "alerts@example.com"
    webhook:
      url: "https://hooks.example.com/alert"
      headers:
        Authorization: "Bearer your_webhook_token"
      template: |
        {
          "text": "{level}: {message}",
          "attachments": [
            {
              "title": "Alert Details",
              "fields": {
                "component": "{component}",
                "timestamp": "{timestamp}",
                "details": "{details}"
              }
            }
          ]
        }
```

## API Configuration

The API configuration controls the FastAPI web server and API functionality.

### Server Configuration

```yaml
api:
  port: 8000
  host: "0.0.0.0"
  debug: false
  workers: 4
  timeout: 60
  cors_allow_origins:
    - "*"
  # or for more restrictive CORS:
  cors_allow_origins:
    - "https://your-app.example.com"
    - "http://localhost:3000"
```

### Authentication Configuration

```yaml
api:
  api_keys:
    - "your_secure_api_key_here"
    - "another_api_key_for_different_user"
  rate_limit:
    enabled: true
    requests_per_minute: 100
    excluded_endpoints:
      - "/api/health"
```

### API Documentation

```yaml
api:
  docs_url: "/docs"
  redoc_url: "/redoc"
  openapi_url: "/openapi.json"
  title: "Perera Construction Lead Scraper API"
  description: "API for managing construction lead generation and processing"
  version: "1.0.0"
  contact:
    name: "Support"
    email: "support@example.com"
```

## Notification Configuration

The notification configuration controls system notifications and alerts.

### Email Notifications

```yaml
notifications:
  channels:
    email:
      enabled: true
      smtp_server: "smtp.example.com"
      smtp_port: 587
      username: "alerts@example.com"
      password: "your_smtp_password"
      from_address: "alerts@example.com"
      use_tls: true
```

### Webhook Notifications

```yaml
notifications:
  channels:
    webhook:
      enabled: true
      url: "https://hooks.example.com/notify"
      headers:
        Content-Type: "application/json"
        Authorization: "Bearer your_webhook_token"
      method: "POST"
      timeout: 10
```

### Alert Types

```yaml
notifications:
  alerts:
    system_error:
      channels:
        - email
      subject: "System Error Alert"
      level: "error"
    critical_error:
      channels:
        - email
        - webhook
      subject: "CRITICAL: System Alert"
      level: "critical"
    data_source_failure:
      channels:
        - email
      subject: "Data Source Failure"
      level: "warning"
    export_success:
      channels:
        - webhook
      subject: "Export Completed Successfully"
      level: "info"
```

## Scheduling Configuration

The scheduling configuration controls when various system tasks are executed.

### Source Check Scheduling

```yaml
scheduling:
  sources_check_interval: 3600  # 1 hour
  max_concurrent_sources: 3
  retry_failed_sources: true
  retry_count: 3
  retry_delay: 300  # 5 minutes
```

### Data Retention

```yaml
scheduling:
  lead_retention:
    enabled: true
    retention_days: 365
    archive_before_delete: true
    archive_path: "data/archives"
  metrics_retention:
    enabled: true
    retention_days: 90
  export_retention:
    enabled: true
    retention_days: 30
    min_files_to_keep: 10
```

### Maintenance Tasks

```yaml
scheduling:
  maintenance:
    database_vacuum: "0 2 * * 0"  # Weekly on Sunday at 2 AM
    database_backup: "0 1 * * *"  # Daily at 1 AM
    log_rotation: "0 0 * * *"     # Daily at midnight
```

## Advanced Configuration

### Processing Configuration

```yaml
processing:
  quality_threshold: 50
  max_leads_per_source: 1000
  enrichment:
    enabled: true
    services:
      - "company_lookup"
      - "contact_verification"
    rate_limits:
      company_lookup: 100  # Max requests per day
      contact_verification: 50  # Max requests per day
  deduplication:
    enabled: true
    match_fields:
      - "name"
      - "company"
      - "address"
    similarity_threshold: 0.8
    check_window_days: 30
  nlp:
    enabled: true
    extract_entities: true
    categorize_description: true
    model: "en_core_web_sm"
```

### Proxy Configuration

```yaml
network:
  proxy:
    enabled: false
    http_proxy: "http://proxy.example.com:8080"
    https_proxy: "http://proxy.example.com:8080"
    no_proxy: "localhost,127.0.0.1"
  timeouts:
    connect: 10
    read: 30
    total: 60
  retries:
    max_retries: 3
    backoff_factor: 0.5
```

### Logging Configuration

```yaml
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
  file: "logs/app.log"
  max_size: 10485760  # 10 MB
  backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  log_to_console: true
  log_to_file: true
  components:
    api: "INFO"
    orchestrator: "INFO"
    storage: "INFO"
    sources: "INFO"
    export: "INFO"
    monitoring: "INFO"
```

## Environment Variables

The system supports configuration via environment variables. Here's a comprehensive list of the supported environment variables and their mappings to configuration options:

| Environment Variable | Configuration Path | Description |
|----------------------|-------------------|-------------|
| LEAD_SCRAPER_VERSION | version | System version |
| LEAD_SCRAPER_ENVIRONMENT | environment | Environment (development, staging, production) |
| LEAD_SCRAPER_DATA_DIR | data_dir | Directory for data files |
| LEAD_SCRAPER_API__PORT | api.port | API server port |
| LEAD_SCRAPER_API__HOST | api.host | API server host |
| LEAD_SCRAPER_API__DEBUG | api.debug | Enable API debug mode |
| LEAD_SCRAPER_API__API_KEYS | api.api_keys | Comma-separated list of API keys |
| LEAD_SCRAPER_STORAGE__TYPE | storage.type | Storage type (sqlite, postgres) |
| LEAD_SCRAPER_STORAGE__PATH | storage.path | Database path (for SQLite) |
| LEAD_SCRAPER_STORAGE__URL | storage.url | Database URL (for PostgreSQL) |
| LEAD_SCRAPER_EXPORT__HUBSPOT__API_KEY | export.hubspot.api_key | HubSpot API key |
| LEAD_SCRAPER_EXPORT__EMAIL__ENABLED | export.email.enabled | Enable email exports |
| LEAD_SCRAPER_EXPORT__EMAIL__SMTP_SERVER | export.email.smtp_server | SMTP server for email exports |
| LEAD_SCRAPER_EXPORT__EMAIL__SMTP_PORT | export.email.smtp_port | SMTP port for email exports |
| LEAD_SCRAPER_EXPORT__EMAIL__USERNAME | export.email.username | SMTP username for email exports |
| LEAD_SCRAPER_EXPORT__EMAIL__PASSWORD | export.email.password | SMTP password for email exports |
| LEAD_SCRAPER_EXPORT__EMAIL__RECIPIENTS | export.email.recipients | Comma-separated list of email recipients |
| LEAD_SCRAPER_MONITORING__METRICS_INTERVAL | monitoring.metrics_interval | Metrics collection interval in seconds |
| LEAD_SCRAPER_MONITORING__ALERTING__ENABLED | monitoring.alerting.enabled | Enable monitoring alerts |
| LEAD_SCRAPER_MONITORING__THRESHOLDS__CPU_PERCENT | monitoring.thresholds.cpu_percent | CPU usage threshold percentage |
| LEAD_SCRAPER_LOGGING__LEVEL | logging.level | Logging level |
| LEAD_SCRAPER_LOGGING__FILE | logging.file | Log file path |
| LEAD_SCRAPER_PROCESSING__QUALITY_THRESHOLD | processing.quality_threshold | Minimum quality score for leads |
| LEAD_SCRAPER_PROCESSING__MAX_LEADS_PER_SOURCE | processing.max_leads_per_source | Maximum leads to process per source |
| LEAD_SCRAPER_SCHEDULING__SOURCES_CHECK_INTERVAL | scheduling.sources_check_interval | Interval to check sources in seconds |
| LEAD_SCRAPER_NETWORK__PROXY__ENABLED | network.proxy.enabled | Enable proxy for network requests |
| LEAD_SCRAPER_NETWORK__PROXY__HTTP_PROXY | network.proxy.http_proxy | HTTP proxy URL |
| LEAD_SCRAPER_NETWORK__PROXY__HTTPS_PROXY | network.proxy.https_proxy | HTTPS proxy URL |

## Sensitive Configuration

Sensitive configuration values like API keys, passwords, and credentials should be handled securely:

### Environment Variables for Secrets

Use environment variables for sensitive values instead of including them in configuration files:

```bash
export LEAD_SCRAPER_API__API_KEYS=your_secure_api_key_here
export LEAD_SCRAPER_EXPORT__HUBSPOT__API_KEY=your_hubspot_api_key
export LEAD_SCRAPER_EXPORT__EMAIL__PASSWORD=your_smtp_password
```

### Secrets File

You can create a separate secrets file (e.g., `secrets.yml`) for sensitive values:

```yaml
# secrets.yml
api:
  api_keys:
    - "your_secure_api_key_here"

export:
  hubspot:
    api_key: "your_hubspot_api_key"
  email:
    password: "your_smtp_password"

sources:
  - name: "Government Bids"
    credentials:
      username: "user123"
      password: "password123"
```

And load it separately:

```python
import yaml

# Load main configuration
with open("config.yml", "r") as f:
    config = yaml.safe_load(f)

# Load secrets and merge with main configuration
try:
    with open("secrets.yml", "r") as f:
        secrets = yaml.safe_load(f)
        # Deep merge secrets into config
        # ...
except FileNotFoundError:
    pass  # No secrets file, use environment variables
```

### Encrypted Configuration

For production environments, consider using encrypted configuration files:

```bash
# Encrypt the secrets file
openssl enc -aes-256-cbc -salt -in secrets.yml -out secrets.yml.enc -pass env:ENCRYPTION_KEY

# Decrypt the secrets file at runtime
openssl enc -d -aes-256-cbc -in secrets.yml.enc -pass env:ENCRYPTION_KEY | python -c "import sys, yaml; config = yaml.safe_load(sys.stdin)"
```

## Configuration Validation

The system validates configuration files to ensure they contain required values and follow the expected format.

### Validation Rules

- Required fields must be present and non-empty
- Field types must match expected types
- Enum values must be one of the allowed values
- Numeric values must be within allowed ranges
- URLs must be properly formatted
- Credentials must be properly structured

### Configuration Schema

The system uses Pydantic models to define and validate configuration:

```python
from pydantic import BaseModel, Field, validator, AnyHttpUrl
from typing import List, Dict, Any, Optional, Union
import re

class SourceConfig(BaseModel):
    name: str
    type: str
    url: AnyHttpUrl
    credentials: Dict[str, Any] = {}
    schedule: str
    config: Dict[str, Any] = {}
    is_active: bool = True
    
    @validator('schedule')
    def validate_cron_format(cls, v):
        # Simple cron format validation
        pattern = r'^(\*|[0-9,\-\*\/]+)\s+(\*|[0-9,\-\*\/]+)\s+(\*|[0-9,\-\*\/]+)\s+(\*|[0-9,\-\*\/]+)\s+(\*|[0-9,\-\*\/]+)$'
        if not re.match(pattern, v):
            raise ValueError('Invalid cron format')
        return v

class ApiConfig(BaseModel):
    port: int = 8000
    host: str = "0.0.0.0"
    debug: bool = False
    api_keys: List[str]
    
    @validator('port')
    def validate_port(cls, v):
        if v < 1 or v > 65535:
            raise ValueError('Port must be between 1 and 65535')
        return v

# Full configuration model
class AppConfig(BaseModel):
    version: str = "1.0.0"
    environment: str = "development"
    data_dir: str = "data"
    api: ApiConfig
    sources: List[SourceConfig]
    # Additional configuration sections...
```

### Validating Configuration Files

```python
import yaml
from pydantic import ValidationError

def load_and_validate_config(config_path):
    try:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
        
        # Validate configuration
        config = AppConfig(**config_data)
        return config
    
    except FileNotFoundError:
        raise Exception(f"Configuration file not found: {config_path}")
    
    except yaml.YAMLError as e:
        raise Exception(f"Invalid YAML in configuration file: {str(e)}")
    
    except ValidationError as e:
        errors = []
        for error in e.errors():
            loc = ".".join(str(loc_part) for loc_part in error["loc"])
            errors.append(f"{loc}: {error['msg']}")
        
        error_message = "Configuration validation failed:\n" + "\n".join(errors)
        raise Exception(error_message)
```
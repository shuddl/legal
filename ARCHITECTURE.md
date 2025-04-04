# Perera Construction Lead Scraper - Architecture

This document provides detailed information about the system architecture, components, data flow, and design decisions of the Perera Construction Lead Scraper.

## Table of Contents

- [System Overview](#system-overview)
- [Architecture Diagram](#architecture-diagram)
- [Core Components](#core-components)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [Integration Points](#integration-points)
- [Design Decisions](#design-decisions)

## System Overview

The Perera Construction Lead Scraper is designed as a modular, extensible system that separates concerns into distinct components. The architecture follows a pipeline pattern where:

1. Data sources are scraped for construction lead information
2. Raw data is processed, normalized, and enriched
3. Leads are scored for quality and relevance
4. Processed leads are stored in a database
5. Leads are exported to external systems (CRM, email, etc.)

The system uses a monitoring layer that tracks performance, detects anomalies, and alerts on issues. It's exposed through both a CLI and RESTful API.

## Architecture Diagram

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

## Core Components

### Data Sources (`sources.py`)

- Responsible for scraping lead data from various websites, APIs, and databases
- Each source is a subclass of `BaseDataSource` with standardized interfaces
- Handles authentication, rate limiting, and error handling for each source
- Extracts raw lead data and normalizes it to a common format

### Orchestrator (`orchestrator.py`)

- Central component that coordinates the lead generation process
- Manages data sources and triggers scraping processes
- Schedules regular scraping based on configured intervals
- Routes data between components in the pipeline
- Implements retry logic and error handling

### Lead Storage (`storage.py`)

- Manages the persistent storage of lead data
- Provides CRUD operations for leads
- Implements efficient querying and filtering
- Handles data migration and backup
- Default implementation uses SQLite, but can be extended to other databases

### Lead Processor (`processor.py`)

- Processes raw lead data to extract structured information
- Enriches leads with additional data from secondary sources
- Scores lead quality based on configurable criteria
- Filters leads based on relevance to configured target markets

### Export Manager (`export.py`)

- Handles exporting leads to external systems
- Supports various export formats: CSV, JSON, Excel
- Integrates with HubSpot CRM
- Implements email notifications with lead reports
- Manages export scheduling and history

### Monitoring (`monitoring.py`)

- Collects performance metrics from all components
- Detects anomalies in system behavior
- Tracks lead quality and volume trends
- Generates performance reports
- Sends alerts for critical issues
- Logs system status and operations

### API (`api.py`)

- Provides RESTful API access to system functionality
- Implements authentication and authorization
- Handles request validation and error responses
- Supports pagination and filtering
- Provides API documentation via Swagger/OpenAPI

### CLI (`cli.py`)

- Command-line interface for system operations
- Supports all core operations: scraping, exporting, configuration
- Provides interactive and scriptable interfaces
- Implements logging and error reporting

## Data Flow

1. **Acquisition Phase**:
   - Orchestrator initiates the scraping process for each data source
   - Data sources fetch raw data from websites, APIs, or databases
   - Raw data is normalized into a common format

2. **Processing Phase**:
   - Raw lead data is processed to extract structured information
   - Leads are enriched with additional data (company details, contact info)
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

## Database Schema

The system uses a relational database (SQLite by default) with the following core tables:

### Leads Table

| Column               | Type      | Description                              |
|----------------------|-----------|------------------------------------------|
| id                   | TEXT      | Unique identifier (UUID)                 |
| name                 | TEXT      | Lead name/title                          |
| company              | TEXT      | Company name                             |
| email                | TEXT      | Contact email                            |
| phone                | TEXT      | Contact phone                            |
| address              | TEXT      | Project address                          |
| project_type         | TEXT      | Type of construction project             |
| project_value        | REAL      | Estimated project value                  |
| project_description  | TEXT      | Detailed project description             |
| source               | TEXT      | Source identifier                        |
| source_url           | TEXT      | Original URL                             |
| timestamp            | DATETIME  | When the lead was discovered             |
| quality_score        | REAL      | Lead quality score (0-100)               |
| status               | TEXT      | Lead status (new, contacted, etc.)       |
| notes                | TEXT      | Additional notes                         |

### Sources Table

| Column               | Type      | Description                              |
|----------------------|-----------|------------------------------------------|
| id                   | TEXT      | Unique identifier                         |
| name                 | TEXT      | Source name                              |
| type                 | TEXT      | Source type                              |
| url                  | TEXT      | Base URL                                 |
| credentials          | TEXT      | Encrypted credentials (JSON)             |
| schedule             | TEXT      | Cron expression for scheduling           |
| config               | TEXT      | Configuration (JSON)                     |
| is_active            | INTEGER   | Whether the source is active             |
| last_run             | DATETIME  | Last execution timestamp                 |
| lead_count           | INTEGER   | Number of leads from this source         |

### Metrics Table

| Column               | Type      | Description                              |
|----------------------|-----------|------------------------------------------|
| id                   | INTEGER   | Auto-incrementing ID                     |
| timestamp            | DATETIME  | When the metric was recorded             |
| metric_name          | TEXT      | Name of the metric                       |
| metric_value         | REAL      | Value of the metric                      |
| component            | TEXT      | Component that generated the metric      |
| tags                 | TEXT      | Additional tags (JSON)                   |

### Exports Table

| Column               | Type      | Description                              |
|----------------------|-----------|------------------------------------------|
| id                   | TEXT      | Unique identifier                         |
| timestamp            | DATETIME  | When the export was performed            |
| format               | TEXT      | Export format (csv, json, hubspot)       |
| lead_count           | INTEGER   | Number of leads exported                 |
| destination          | TEXT      | Export destination                       |
| status               | TEXT      | Export status                            |
| error                | TEXT      | Error message if failed                  |

## Integration Points

### External APIs

1. **HubSpot API**
   - Used for exporting leads to HubSpot CRM
   - Requires API key for authentication
   - Maps lead fields to HubSpot contact/deal properties

2. **Data Source APIs**
   - Various construction data platforms
   - Public records databases
   - Bid management systems

### Email Integration

- SMTP configuration for sending alerts and reports
- Templates for different notification types
- Attachment support for exports

### Monitoring Integration

- Prometheus metrics export (optional)
- Log aggregation support
- Webhook notifications for alerts

## Design Decisions

### Modularity and Extension

The system is designed with a plugin architecture for data sources, allowing new sources to be added without modifying core code. This is implemented through:

- Abstract base classes defining interfaces
- Dynamic loading of source classes
- Configuration-driven behavior

### Storage Strategy

SQLite was chosen as the default database for simplicity and ease of deployment, but the storage layer is abstracted to allow:

- Easy migration to PostgreSQL or other databases
- Swapping storage implementations without affecting other components
- Transparent handling of different storage backends

### Processing Pipeline

The lead processing pipeline is designed as a series of discrete steps that can be:
- Configured individually
- Bypassed if not needed
- Extended with custom processors
- Monitored at each stage

### Security Considerations

- API access is secured with API keys
- Credentials are stored encrypted
- Rate limiting prevents abuse
- IP-based access controls are available
- No PII is stored unless explicitly configured

### Reliability Features

- Each component has retry logic
- Failed operations are logged and can be retried
- The system can recover from partial failures
- Monitoring detects and alerts on anomalies
- Comprehensive testing ensures reliable operation

### Performance Optimizations

- Concurrent scraping of multiple sources
- Efficient database queries with indexing
- Caching of frequently accessed data
- Background processing for non-critical operations
- Resource limiting to prevent overload
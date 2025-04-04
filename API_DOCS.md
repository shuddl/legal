# Perera Construction Lead Scraper - API Documentation

This document provides comprehensive documentation for the RESTful API of the Perera Construction Lead Scraper.

## Table of Contents

- [API Overview](#api-overview)
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
  - [Health Check](#health-check)
  - [Data Sources](#data-sources)
  - [Leads](#leads)
  - [System Stats](#system-stats)
  - [Settings](#settings)
  - [Operations](#operations)
- [Request/Response Examples](#requestresponse-examples)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)

## API Overview

The Perera Construction Lead Scraper API provides programmatic access to all system functionality, including:

- Data source management
- Lead retrieval and filtering
- Lead export
- System configuration
- Monitoring and stats

The API follows REST principles and uses JSON for request and response bodies. All API endpoints are prefixed with `/api`.

## Authentication

All API endpoints (except `/api/health`) require authentication using an API key.

### API Key Authentication

Include your API key in the `X-API-Key` header:

```
X-API-Key: your_api_key_here
```

Example:
```bash
curl -X GET http://localhost:8000/api/leads \
  -H "X-API-Key: your_api_key_here"
```

### Obtaining an API Key

API keys are configured in the system configuration file or through environment variables. See the [Configuration](CONFIGURATION.md) guide for details on setting up API keys.

## API Endpoints

### Health Check

#### GET /api/health

Get the current health status of the system.

**Request**:
```
GET /api/health
```

**Response**:
```json
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

**Status Codes**:
- `200 OK`: System is operational
- `503 Service Unavailable`: System is degraded or unavailable

### Data Sources

#### GET /api/sources

Get a list of all configured data sources.

**Request**:
```
GET /api/sources
```

**Response**:
```json
[
  {
    "id": "src_123456",
    "name": "Government Bids",
    "type": "government_bids",
    "url": "https://example.com/bids",
    "credentials": {
      "username": "user123"
    },
    "schedule": "0 */6 * * *",
    "config": {
      "region": "Northeast",
      "project_types": ["commercial", "institutional"]
    },
    "is_active": true,
    "last_run": "2023-01-01T12:00:00.000Z",
    "next_run": "2023-01-01T18:00:00.000Z",
    "status": "active",
    "lead_count": 250
  }
]
```

**Status Codes**:
- `200 OK`: Successful request
- `401 Unauthorized`: Missing or invalid API key

#### POST /api/sources

Add a new data source.

**Request**:
```
POST /api/sources
Content-Type: application/json

{
  "name": "Government Bids",
  "type": "government_bids",
  "url": "https://example.com/bids",
  "credentials": {
    "username": "user123",
    "password": "pass123"
  },
  "schedule": "0 */6 * * *",
  "config": {
    "region": "Northeast",
    "project_types": ["commercial", "institutional"]
  },
  "is_active": true
}
```

**Response**:
```json
{
  "id": "src_123456",
  "name": "Government Bids",
  "type": "government_bids",
  "url": "https://example.com/bids",
  "credentials": {
    "username": "user123"
  },
  "schedule": "0 */6 * * *",
  "config": {
    "region": "Northeast",
    "project_types": ["commercial", "institutional"]
  },
  "is_active": true,
  "last_run": null,
  "next_run": "2023-01-01T18:00:00.000Z",
  "status": "configured",
  "lead_count": 0
}
```

**Status Codes**:
- `201 Created`: Source created successfully
- `400 Bad Request`: Invalid request body
- `401 Unauthorized`: Missing or invalid API key

#### PUT /api/sources/{source_id}

Update an existing data source.

**Request**:
```
PUT /api/sources/src_123456
Content-Type: application/json

{
  "name": "Updated Government Bids",
  "schedule": "0 */12 * * *",
  "is_active": false
}
```

**Response**:
```json
{
  "id": "src_123456",
  "name": "Updated Government Bids",
  "type": "government_bids",
  "url": "https://example.com/bids",
  "credentials": {
    "username": "user123"
  },
  "schedule": "0 */12 * * *",
  "config": {
    "region": "Northeast",
    "project_types": ["commercial", "institutional"]
  },
  "is_active": false,
  "last_run": "2023-01-01T12:00:00.000Z",
  "next_run": "2023-01-02T00:00:00.000Z",
  "status": "paused",
  "lead_count": 250
}
```

**Status Codes**:
- `200 OK`: Source updated successfully
- `400 Bad Request`: Invalid request body
- `401 Unauthorized`: Missing or invalid API key
- `404 Not Found`: Source not found

#### DELETE /api/sources/{source_id}

Remove a data source.

**Request**:
```
DELETE /api/sources/src_123456
```

**Response**:
```
204 No Content
```

**Status Codes**:
- `204 No Content`: Source deleted successfully
- `401 Unauthorized`: Missing or invalid API key
- `404 Not Found`: Source not found

### Leads

#### GET /api/leads

Get a filtered, paginated list of leads.

**Request Parameters**:
- `page` (optional): Page number (default: 1)
- `size` (optional): Page size (default: 20, max: 100)
- `status` (optional): Filter by status (e.g., "new", "contacted")
- `source` (optional): Filter by source ID
- `min_quality` (optional): Filter by minimum quality score
- `date_from` (optional): Filter by minimum timestamp (ISO format)
- `date_to` (optional): Filter by maximum timestamp (ISO format)
- `search` (optional): Search text in name, company, and description

**Request**:
```
GET /api/leads?page=1&size=10&min_quality=70&status=new
```

**Response**:
```json
{
  "items": [
    {
      "id": "lead_123456",
      "name": "New Office Building",
      "company": "Acme Corp",
      "email": "contact@acmecorp.com",
      "phone": "555-123-4567",
      "address": "123 Main St, Boston, MA",
      "project_type": "commercial",
      "project_value": 2500000,
      "project_description": "New 3-story office building with parking garage",
      "source": "government_bids",
      "source_url": "https://example.com/bids/12345",
      "timestamp": "2023-01-01T12:30:45.000Z",
      "quality_score": 85,
      "status": "new",
      "notes": null
    }
  ],
  "total": 45,
  "page": 1,
  "size": 10,
  "pages": 5
}
```

**Status Codes**:
- `200 OK`: Successful request
- `400 Bad Request`: Invalid parameters
- `401 Unauthorized`: Missing or invalid API key

#### GET /api/leads/{lead_id}

Get detailed information about a specific lead.

**Request**:
```
GET /api/leads/lead_123456
```

**Response**:
```json
{
  "id": "lead_123456",
  "name": "New Office Building",
  "company": "Acme Corp",
  "email": "contact@acmecorp.com",
  "phone": "555-123-4567",
  "address": "123 Main St, Boston, MA",
  "project_type": "commercial",
  "project_value": 2500000,
  "project_description": "New 3-story office building with parking garage",
  "source": "government_bids",
  "source_url": "https://example.com/bids/12345",
  "timestamp": "2023-01-01T12:30:45.000Z",
  "quality_score": 85,
  "status": "new",
  "notes": null
}
```

**Status Codes**:
- `200 OK`: Successful request
- `401 Unauthorized`: Missing or invalid API key
- `404 Not Found`: Lead not found

#### PUT /api/leads/{lead_id}

Update a lead.

**Request**:
```
PUT /api/leads/lead_123456
Content-Type: application/json

{
  "status": "contacted",
  "notes": "Contacted via email on 2023-01-02",
  "quality_score": 90
}
```

**Response**:
```json
{
  "id": "lead_123456",
  "name": "New Office Building",
  "company": "Acme Corp",
  "email": "contact@acmecorp.com",
  "phone": "555-123-4567",
  "address": "123 Main St, Boston, MA",
  "project_type": "commercial",
  "project_value": 2500000,
  "project_description": "New 3-story office building with parking garage",
  "source": "government_bids",
  "source_url": "https://example.com/bids/12345",
  "timestamp": "2023-01-01T12:30:45.000Z",
  "quality_score": 90,
  "status": "contacted",
  "notes": "Contacted via email on 2023-01-02"
}
```

**Status Codes**:
- `200 OK`: Lead updated successfully
- `400 Bad Request`: Invalid request body
- `401 Unauthorized`: Missing or invalid API key
- `404 Not Found`: Lead not found

#### DELETE /api/leads/{lead_id}

Delete a lead.

**Request**:
```
DELETE /api/leads/lead_123456
```

**Response**:
```
204 No Content
```

**Status Codes**:
- `204 No Content`: Lead deleted successfully
- `401 Unauthorized`: Missing or invalid API key
- `404 Not Found`: Lead not found

### System Stats

#### GET /api/stats

Get system performance metrics and statistics.

**Request**:
```
GET /api/stats
```

**Response**:
```json
{
  "cpu_usage": 12.3,
  "memory_usage": 45.6,
  "disk_usage": 32.1,
  "lead_count": 1250,
  "avg_processing_time": 0.75,
  "success_rate": 98.5,
  "active_sources": 5,
  "recent_errors": [
    {
      "timestamp": "2023-01-01T10:15:30.000Z",
      "error": "Connection timeout for source 'bid_platform'",
      "component": "data_source"
    }
  ],
  "last_updated": "2023-01-01T12:30:45.000Z"
}
```

**Status Codes**:
- `200 OK`: Successful request
- `401 Unauthorized`: Missing or invalid API key

### Settings

#### GET /api/settings

Get current system configuration settings.

**Request**:
```
GET /api/settings
```

**Response**:
```json
{
  "sources_check_interval": 3600,
  "export_interval": 86400,
  "hubspot_api_key": "****",
  "export_email": "exports@example.com",
  "quality_threshold": 50.0,
  "enable_automatic_exports": true,
  "monitoring_metrics_interval": 300,
  "notification_email": "alerts@example.com",
  "max_leads_per_source": 1000,
  "retention_days": 365
}
```

**Status Codes**:
- `200 OK`: Successful request
- `401 Unauthorized`: Missing or invalid API key

#### PUT /api/settings

Update system configuration settings.

**Request**:
```
PUT /api/settings
Content-Type: application/json

{
  "quality_threshold": 60.0,
  "enable_automatic_exports": false,
  "monitoring_metrics_interval": 600
}
```

**Response**:
```json
{
  "sources_check_interval": 3600,
  "export_interval": 86400,
  "hubspot_api_key": "****",
  "export_email": "exports@example.com",
  "quality_threshold": 60.0,
  "enable_automatic_exports": false,
  "monitoring_metrics_interval": 600,
  "notification_email": "alerts@example.com",
  "max_leads_per_source": 1000,
  "retention_days": 365
}
```

**Status Codes**:
- `200 OK`: Settings updated successfully
- `400 Bad Request`: Invalid request body
- `401 Unauthorized`: Missing or invalid API key

### Operations

#### POST /api/export

Trigger a manual lead export.

**Request**:
```
POST /api/export
Content-Type: application/json

{
  "format": "csv",
  "filter": {
    "min_quality": 70,
    "status": "new"
  },
  "destination": "exports@example.com"
}
```

**Response**:
```json
{
  "job_id": "job_123456",
  "status": "processing",
  "message": "Export job started with format: csv",
  "timestamp": "2023-01-01T12:30:45.000Z"
}
```

**Status Codes**:
- `200 OK`: Export job started successfully
- `400 Bad Request`: Invalid request body
- `401 Unauthorized`: Missing or invalid API key

#### POST /api/triggers/generate

Manually trigger the lead generation process.

**Request**:
```
POST /api/triggers/generate
```

**Response**:
```json
{
  "status": "processing",
  "message": "Lead generation process started",
  "timestamp": "2023-01-01T12:30:45.000Z"
}
```

**Status Codes**:
- `202 Accepted`: Process started successfully
- `401 Unauthorized`: Missing or invalid API key

#### POST /api/triggers/source/{source_id}

Manually trigger a specific data source.

**Request**:
```
POST /api/triggers/source/src_123456
```

**Response**:
```json
{
  "status": "processing",
  "message": "Source 'Government Bids' processing started",
  "timestamp": "2023-01-01T12:30:45.000Z"
}
```

**Status Codes**:
- `202 Accepted`: Process started successfully
- `401 Unauthorized`: Missing or invalid API key
- `404 Not Found`: Source not found

## Request/Response Examples

### Example: Get Leads with Filtering

**Request**:
```bash
curl -X GET "http://localhost:8000/api/leads?min_quality=70&status=new&page=1&size=10" \
  -H "X-API-Key: your_api_key"
```

**Response**:
```json
{
  "items": [
    {
      "id": "lead_123456",
      "name": "New Office Building",
      "company": "Acme Corp",
      "email": "contact@acmecorp.com",
      "phone": "555-123-4567",
      "address": "123 Main St, Boston, MA",
      "project_type": "commercial",
      "project_value": 2500000,
      "project_description": "New 3-story office building with parking garage",
      "source": "government_bids",
      "source_url": "https://example.com/bids/12345",
      "timestamp": "2023-01-01T12:30:45.000Z",
      "quality_score": 85,
      "status": "new",
      "notes": null
    }
  ],
  "total": 45,
  "page": 1,
  "size": 10,
  "pages": 5
}
```

### Example: Add a New Data Source

**Request**:
```bash
curl -X POST "http://localhost:8000/api/sources" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "name": "Government Bids",
    "type": "government_bids",
    "url": "https://example.com/bids",
    "credentials": {
      "username": "user123",
      "password": "pass123"
    },
    "schedule": "0 */6 * * *",
    "config": {
      "region": "Northeast",
      "project_types": ["commercial", "institutional"]
    },
    "is_active": true
  }'
```

**Response**:
```json
{
  "id": "src_123456",
  "name": "Government Bids",
  "type": "government_bids",
  "url": "https://example.com/bids",
  "credentials": {
    "username": "user123"
  },
  "schedule": "0 */6 * * *",
  "config": {
    "region": "Northeast",
    "project_types": ["commercial", "institutional"]
  },
  "is_active": true,
  "last_run": null,
  "next_run": "2023-01-01T18:00:00.000Z",
  "status": "configured",
  "lead_count": 0
}
```

### Example: Update Lead Status

**Request**:
```bash
curl -X PUT "http://localhost:8000/api/leads/lead_123456" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "status": "contacted",
    "notes": "Contacted via email on 2023-01-02"
  }'
```

**Response**:
```json
{
  "id": "lead_123456",
  "name": "New Office Building",
  "company": "Acme Corp",
  "email": "contact@acmecorp.com",
  "phone": "555-123-4567",
  "address": "123 Main St, Boston, MA",
  "project_type": "commercial",
  "project_value": 2500000,
  "project_description": "New 3-story office building with parking garage",
  "source": "government_bids",
  "source_url": "https://example.com/bids/12345",
  "timestamp": "2023-01-01T12:30:45.000Z",
  "quality_score": 85,
  "status": "contacted",
  "notes": "Contacted via email on 2023-01-02"
}
```

### Example: Trigger Lead Export

**Request**:
```bash
curl -X POST "http://localhost:8000/api/export" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{
    "format": "csv",
    "filter": {
      "min_quality": 70,
      "status": "new"
    },
    "destination": "exports@example.com"
  }'
```

**Response**:
```json
{
  "job_id": "job_123456",
  "status": "processing",
  "message": "Export job started with format: csv",
  "timestamp": "2023-01-01T12:30:45.000Z"
}
```

## Error Handling

The API uses standard HTTP status codes and returns detailed error messages in a consistent format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Error Codes

- `400 Bad Request`: The request was malformed or contained invalid parameters.
- `401 Unauthorized`: Missing or invalid API key.
- `404 Not Found`: The requested resource was not found.
- `429 Too Many Requests`: Rate limit exceeded.
- `500 Internal Server Error`: An unexpected error occurred on the server.

### Error Response Examples

**Invalid request body**:
```json
{
  "detail": "Invalid source type. Must be one of: government_bids, private_bids, permit_data"
}
```

**Missing API key**:
```json
{
  "detail": "API Key header is missing"
}
```

**Invalid API key**:
```json
{
  "detail": "Invalid API Key"
}
```

**Resource not found**:
```json
{
  "detail": "Lead with ID lead_999999 not found"
}
```

**Rate limit exceeded**:
```json
{
  "detail": "Rate limit exceeded. Try again later.",
  "retry_after": 60
}
```

## Rate Limiting

The API implements rate limiting to protect against abuse. Rate limits are based on the client's IP address.

### Default Rate Limits

- 100 requests per minute per IP address
- Health check endpoint (`/api/health`) is not rate-limited

### Rate Limit Headers

When rate limiting is active, the following headers are included in API responses:

- `X-RateLimit-Limit`: Maximum number of requests allowed per time window
- `X-RateLimit-Remaining`: Number of requests remaining in the current time window
- `X-RateLimit-Reset`: Time (in seconds) until the rate limit resets

### Rate Limit Exceeded Response

When a rate limit is exceeded, the API returns a `429 Too Many Requests` status code with a response body:

```json
{
  "detail": "Rate limit exceeded. Try again later.",
  "retry_after": 60
}
```

The `retry_after` value indicates the number of seconds to wait before making another request.
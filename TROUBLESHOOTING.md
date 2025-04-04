# Perera Construction Lead Scraper - Troubleshooting Guide

This document provides guidance for diagnosing and resolving common issues with the Perera Construction Lead Scraper.

## Table of Contents

- [Common Error Scenarios](#common-error-scenarios)
- [Diagnostic Procedures](#diagnostic-procedures)
- [Log Analysis Guide](#log-analysis-guide)
- [Data Source Issues](#data-source-issues)
- [API Issues](#api-issues)
- [Export Issues](#export-issues)
- [Performance Issues](#performance-issues)
- [Database Issues](#database-issues)
- [Recovery Procedures](#recovery-procedures)
- [Support Resources](#support-resources)

## Common Error Scenarios

### Installation and Setup Issues

| Issue | Likely Causes | Resolution |
|-------|---------------|------------|
| **Failed installation** | Missing dependencies, Python version mismatch | Check Python version (3.9+ required), install dependencies with `pip install -r requirements.txt` |
| **Configuration errors** | Invalid YAML format, missing required fields | Validate config file with `python -m src.perera_lead_scraper.cli validate-config` |
| **Permission errors** | Insufficient file permissions | Ensure data, exports, and logs directories are writable |
| **Database initialization fails** | SQLite permissions, path issues | Check database path, ensure parent directory exists and is writable |

### Data Source Issues

| Issue | Likely Causes | Resolution |
|-------|---------------|------------|
| **Connection failures** | Network issues, invalid credentials | Check network connectivity, verify credentials, check if source website is accessible |
| **No leads found** | Wrong configuration, changed website structure | Update selectors, verify URL is correct, check if source website format changed |
| **Rate limiting** | Too many requests to source | Adjust scheduling, implement backoff strategy, check source rate limits |
| **Authentication failures** | Expired credentials, changed auth method | Update credentials, check if source auth method changed |

### API Issues

| Issue | Likely Causes | Resolution |
|-------|---------------|------------|
| **API server won't start** | Port already in use, configuration issues | Check if port is available, verify configuration |
| **Authentication errors** | Invalid API key, missing header | Check API key is correct, ensure X-API-Key header is included |
| **Rate limiting errors** | Too many requests | Reduce request rate, implement client-side throttling |
| **Timeout errors** | Long-running operations | Increase timeout settings, optimize operations |

### Export Issues

| Issue | Likely Causes | Resolution |
|-------|---------------|------------|
| **HubSpot export fails** | Invalid API key, mapping issues | Verify HubSpot API key, check field mapping configuration |
| **Email export fails** | SMTP configuration, email server issues | Test SMTP connection, check credentials, verify recipient addresses |
| **Empty exports** | No leads match filter criteria | Check filter criteria, verify leads exist in database |
| **CSV/Excel format issues** | Character encoding, field mapping | Check file encoding, verify column mapping |

### Monitoring Issues

| Issue | Likely Causes | Resolution |
|-------|---------------|------------|
| **Missing metrics** | Monitoring not enabled, database issues | Check monitoring configuration, verify metrics database |
| **False alerts** | Thresholds too strict | Adjust alert thresholds, implement cooldown periods |
| **No alerts received** | Notification configuration, delivery issues | Check notification configuration, verify recipient addresses |

## Diagnostic Procedures

### System Health Check

Run the system health check to verify all components are operational:

```bash
curl http://localhost:8000/api/health
```

Expected output:
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

Check for any components reporting "unhealthy" status.

### Configuration Validation

Validate the configuration file for errors:

```bash
python -m src.perera_lead_scraper.cli validate-config --config-file config.yml
```

This will report any configuration errors with detailed messages.

### Database Connection Test

Verify database connectivity:

```bash
python -m src.perera_lead_scraper.cli test-db-connection
```

This will attempt to connect to the database and report any issues.

### Source Connection Test

Test connection to a specific data source:

```bash
python -m src.perera_lead_scraper.cli test-source-connection --source-id SOURCE_ID
```

This will attempt to connect to the source and report any issues.

### Generate Diagnostic Report

Generate a comprehensive diagnostic report for troubleshooting:

```bash
python -m src.perera_lead_scraper.cli generate-diagnostic-report
```

This creates a diagnostic report with system information, configuration details, recent logs, and metrics.

## Log Analysis Guide

The system generates logs in the configured log directory (default: `logs/app.log`). Log analysis is a key troubleshooting tool.

### Log Levels

The log contains entries with different severity levels:

- **DEBUG**: Detailed information, typically of interest only when diagnosing problems
- **INFO**: Confirmation that things are working as expected
- **WARNING**: Indication that something unexpected happened, but the application still works
- **ERROR**: Due to a more serious problem, the application has not been able to perform a function
- **CRITICAL**: A serious error, indicating that the application itself may be unable to continue running

### Key Log Patterns

Look for these patterns in the logs to identify common issues:

#### Connection Issues

```
ERROR - Failed to connect to <source_name>: Connection refused
```

This indicates network connectivity issues or the source server is down.

#### Authentication Issues

```
ERROR - Authentication failed for <source_name>: Invalid credentials
```

This indicates the credentials for the source are invalid or expired.

#### Rate Limiting

```
WARNING - Rate limit exceeded for <source_name>. Retrying after 60 seconds
```

This indicates the source is rate-limiting requests.

#### Parsing Errors

```
ERROR - Failed to parse data from <source_name>: <error_details>
```

This usually indicates the source website structure has changed and selectors need updating.

#### Database Errors

```
ERROR - Database error: <error_details>
```

This indicates issues with the database connection or operations.

#### Export Errors

```
ERROR - Failed to export to <destination>: <error_details>
```

This indicates issues with the export process.

### Log Analysis Command

Use the log analysis tool to search for specific patterns:

```bash
python -m src.perera_lead_scraper.cli analyze-logs --pattern "ERROR" --days 3
```

This will search the last 3 days of logs for ERROR messages and summarize them.

## Data Source Issues

### Website Structure Changes

One of the most common issues is when a source website changes its structure, causing selectors to break.

#### Diagnosis

1. Check the logs for parsing errors related to the source
2. Run a source test to see the raw HTML/JSON:

```bash
python -m src.perera_lead_scraper.cli test-source-fetch --source-id SOURCE_ID --raw
```

3. Compare the structure with the configured selectors

#### Resolution

1. Update the selectors in the source configuration:

```yaml
sources:
  - name: "Government Bids"
    type: "government_bids"
    config:
      selectors:
        bid_items: ".updated-bid-list .bid-card"  # Updated selector
        title: ".card-header h3"                  # Updated selector
        # other selectors...
```

2. Test the updated selectors:

```bash
python -m src.perera_lead_scraper.cli test-selectors --source-id SOURCE_ID
```

### Authentication Issues

#### Diagnosis

1. Check logs for authentication errors
2. Verify credentials are still valid by manually logging in
3. Check if the authentication mechanism has changed

#### Resolution

1. Update credentials in the configuration
2. If the authentication method changed, you may need to update the source implementation

### Rate Limiting

#### Diagnosis

1. Check logs for rate limit warnings
2. Look for HTTP 429 errors or other rate limit indicators
3. Check the source website's documented rate limits

#### Resolution

1. Adjust the scraping schedule to be less frequent:

```yaml
sources:
  - name: "Government Bids"
    schedule: "0 */12 * * *"  # Reduced from every 6 hours to every 12 hours
```

2. Implement backoff strategy in the source class:

```python
def fetch_data(self):
    retries = 0
    max_retries = 3
    
    while retries < max_retries:
        try:
            # Attempt to fetch data
            # ...
            return data
        except RateLimitException:
            wait_time = (2 ** retries) * 30  # Exponential backoff
            self.logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
            time.sleep(wait_time)
            retries += 1
    
    # If we get here, all retries failed
    self.logger.error("Failed to fetch data after multiple retries")
    return []
```

## API Issues

### API Server Won't Start

#### Diagnosis

1. Check for error messages during startup
2. Verify port availability:

```bash
netstat -tuln | grep 8000
```

3. Check for permission issues in the logs

#### Resolution

1. If port is in use, choose a different port:

```bash
python -m src.perera_lead_scraper.api.api --port 8001
```

2. Fix permission issues by ensuring the user has appropriate permissions

### Authentication Errors

#### Diagnosis

1. Check that requests include the `X-API-Key` header
2. Verify the API key matches one configured in the system
3. Look for authentication error logs

#### Resolution

1. Ensure API keys are correctly configured:

```yaml
api:
  api_keys:
    - "your_secure_api_key_here"
```

2. Include the header in all requests:

```bash
curl -H "X-API-Key: your_secure_api_key_here" http://localhost:8000/api/leads
```

### Rate Limiting Errors

#### Diagnosis

1. Check for 429 responses from the API
2. Look for rate limiting logs

#### Resolution

1. Adjust client request rate to stay within limits
2. Modify rate limit settings if needed:

```yaml
api:
  rate_limit:
    requests_per_minute: 200  # Increased from default
```

## Export Issues

### HubSpot Export Failures

#### Diagnosis

1. Check logs for HubSpot API errors
2. Verify HubSpot API key is valid
3. Test HubSpot API connection:

```bash
python -m src.perera_lead_scraper.cli test-hubspot-connection
```

#### Resolution

1. Update HubSpot API key if expired
2. Check HubSpot field mapping:

```yaml
export:
  hubspot:
    field_mapping:
      # Ensure these map to existing HubSpot properties
      name: "dealname"
      email: "email"
      project_value: "amount"
```

3. Ensure required fields are present in leads

### Email Export Failures

#### Diagnosis

1. Check logs for SMTP errors
2. Test SMTP connection:

```bash
python -m src.perera_lead_scraper.cli test-smtp-connection
```

3. Verify email configuration

#### Resolution

1. Update SMTP credentials if incorrect
2. Check for email server restrictions
3. Verify recipient email addresses are valid

## Performance Issues

### Slow API Responses

#### Diagnosis

1. Monitor API response times
2. Check system resource usage during API calls
3. Identify slow endpoints

#### Resolution

1. Optimize database queries
2. Implement caching for frequently accessed data:

```python
@app.get("/api/leads")
async def get_leads(request: Request,
                    cache: ResponseCache = Depends(get_cache)):
    """Get leads with caching."""
    cache_key = f"leads:{request.query_params}"
    cached_response = await cache.get(cache_key)
    
    if cached_response:
        return cached_response
    
    # Normal lead retrieval logic
    # ...
    
    await cache.set(cache_key, response, expire=300)  # Cache for 5 minutes
    return response
```

3. Add database indexes for common query patterns

### Memory Usage Growth

#### Diagnosis

1. Monitor memory usage over time
2. Check for memory leaks in logs
3. Use monitoring tools to track memory usage

#### Resolution

1. Implement batch processing for large datasets
2. Add memory limits to prevent excessive usage:

```yaml
resources:
  memory_limit_mb: 1024
  batch_size: 100
```

3. Ensure proper cleanup of resources:

```python
def process_large_dataset(items):
    results = []
    # Process in batches to limit memory usage
    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i:i+BATCH_SIZE]
        results.extend(process_batch(batch))
        # Explicitly run garbage collection after each batch
        gc.collect()
    return results
```

## Database Issues

### Database Corruption

#### Diagnosis

1. Check logs for database errors
2. Run database integrity check:

```bash
python -m src.perera_lead_scraper.cli check-db-integrity
```

#### Resolution

1. Restore from backup:

```bash
python -m src.perera_lead_scraper.cli restore-db --backup-file data/backups/leads.db.bak
```

2. For SQLite, attempt recovery:

```bash
sqlite3 data/leads.db "PRAGMA integrity_check;"
```

If issues are found, you may need to dump and reload the database:

```bash
sqlite3 data/leads.db .dump > dump.sql
rm data/leads.db
sqlite3 data/leads.db < dump.sql
```

### Database Performance

#### Diagnosis

1. Identify slow queries in logs
2. Check database size and growth
3. Analyze query execution plans

#### Resolution

1. Add indexes for common queries:

```python
# In the database initialization code
def create_indexes():
    # Create indexes for common queries
    db.execute("""
    CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source);
    CREATE INDEX IF NOT EXISTS idx_leads_quality_score ON leads(quality_score);
    CREATE INDEX IF NOT EXISTS idx_leads_timestamp ON leads(timestamp);
    """)
```

2. Optimize large queries with pagination and filtering
3. Consider database migration for very large datasets (SQLite to PostgreSQL)

## Recovery Procedures

### Data Recovery

If lead data is corrupted or lost, follow these recovery steps:

1. Stop the application to prevent further data changes
2. Restore the database from the latest backup:

```bash
cp data/backups/leads.db.$(date +%Y%m%d) data/leads.db
```

3. Re-import any leads collected since the backup:

```bash
python -m src.perera_lead_scraper.cli import-leads --file exports/leads_export_recent.json
```

### Configuration Recovery

If the configuration is corrupted:

1. Restore from backup:

```bash
cp config.yml.bak config.yml
```

2. Or restore the default configuration:

```bash
python -m src.perera_lead_scraper.cli generate-default-config > config.yml
```

Then edit the file to add your specific settings.

### Source Recovery

If a specific source is failing consistently:

1. Disable the problematic source temporarily:

```yaml
sources:
  - name: "Problematic Source"
    is_active: false  # Temporarily disable
```

2. Update source configuration with new selectors or settings
3. Test the source:

```bash
python -m src.perera_lead_scraper.cli test-source --source-id SOURCE_ID
```

4. Re-enable the source after fixing the issue

## Support Resources

### Community Support

- GitHub Issues: [github.com/perera-construction/lead-scraper/issues](https://github.com/perera-construction/lead-scraper/issues)
- Stack Overflow: Tag questions with `perera-lead-scraper`

### Commercial Support

For commercial support options, contact:

- Email: support@example.com
- Phone: (123) 456-7890

### Reporting Bugs

When reporting bugs, please include:

1. System information:
   - Operating system
   - Python version
   - Lead Scraper version

2. Steps to reproduce the issue

3. Relevant logs (with sensitive information redacted)

4. Configuration file (with sensitive information redacted)

5. Expected vs. actual behavior

Use the bug report template on GitHub for structured reports.
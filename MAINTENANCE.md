# Perera Construction Lead Scraper - Maintenance Guide

This document provides guidance for routine maintenance tasks, backup procedures, and performance tuning for the Perera Construction Lead Scraper.

## Table of Contents

- [Routine Maintenance Tasks](#routine-maintenance-tasks)
- [Backup Procedures](#backup-procedures)
- [Database Maintenance](#database-maintenance)
- [Log Management](#log-management)
- [Update Procedures](#update-procedures)
- [Performance Tuning](#performance-tuning)
- [Security Maintenance](#security-maintenance)
- [Health Checks](#health-checks)
- [Maintenance Schedule](#maintenance-schedule)

## Routine Maintenance Tasks

### Daily Tasks

1. **Monitor System Health**

   Check the system health endpoint to ensure all components are operational:

   ```bash
   curl http://localhost:8000/api/health
   ```

   Verify that the status is "operational" and all components report "healthy".

2. **Review Logs**

   Check logs for errors or warnings:

   ```bash
   # View recent errors
   grep "ERROR" logs/app.log | tail -n 50

   # View recent warnings
   grep "WARNING" logs/app.log | tail -n 50
   ```

3. **Verify Successful Exports**

   Check that exports have been completed successfully:

   ```bash
   ls -la exports/
   ```

   Verify that export files have been created with non-zero sizes.

### Weekly Tasks

1. **Update Data Source Configurations**

   Review and update data source configurations if websites or APIs have changed:

   ```bash
   # Test all sources to identify any failing ones
   python -m src.perera_lead_scraper.cli test-all-sources
   ```

   Update any failing sources in the configuration file.

2. **Prune Old Exports**

   Remove old export files to free up disk space:

   ```bash
   # Remove exports older than 30 days
   find exports/ -type f -name "*.csv" -mtime +30 -delete
   find exports/ -type f -name "*.xlsx" -mtime +30 -delete
   find exports/ -type f -name "*.json" -mtime +30 -delete
   ```

3. **Verify Database Integrity**

   Check database integrity:

   ```bash
   python -m src.perera_lead_scraper.cli check-db-integrity
   ```

### Monthly Tasks

1. **Database Optimization**

   Optimize the database to improve performance:

   ```bash
   python -m src.perera_lead_scraper.cli optimize-db
   ```

2. **Review and Update API Keys**

   Check expiration dates on API keys and update if necessary:

   ```bash
   python -m src.perera_lead_scraper.cli check-api-keys
   ```

   Update any expiring or expired keys in the configuration.

3. **Review System Metrics**

   Generate and review a system performance report:

   ```bash
   python -m src.perera_lead_scraper.cli generate-performance-report
   ```

   Look for trends in resource usage, processing times, and lead quality.

### Quarterly Tasks

1. **Data Purging**

   Archive and purge old leads according to retention policy:

   ```bash
   # Archive leads older than 1 year
   python -m src.perera_lead_scraper.cli archive-leads --older-than 365

   # Purge archived leads older than 2 years
   python -m src.perera_lead_scraper.cli purge-archived-leads --older-than 730
   ```

2. **Configuration Review**

   Review the entire configuration for optimization opportunities:

   ```bash
   python -m src.perera_lead_scraper.cli analyze-config
   ```

   Implement suggested optimizations as needed.

3. **Security Audit**

   Review access logs and security settings:

   ```bash
   # Generate security audit report
   python -m src.perera_lead_scraper.cli security-audit
   ```

   Address any security issues identified.

## Backup Procedures

### Database Backup

1. **Automated Backups**

   Configure automated database backups in the configuration file:

   ```yaml
   backup:
     enabled: true
     schedule: "0 1 * * *"  # Daily at 1 AM
     retention_days: 30
     backup_dir: "data/backups"
   ```

2. **Manual Backup**

   Perform a manual backup:

   ```bash
   # For SQLite
   python -m src.perera_lead_scraper.cli backup-db --output data/backups/leads.db.$(date +%Y%m%d)

   # For PostgreSQL
   pg_dump -U username -d leaddb -f data/backups/leads_$(date +%Y%m%d).sql
   ```

3. **Backup Verification**

   Verify backup integrity:

   ```bash
   # For SQLite
   sqlite3 data/backups/leads.db.$(date +%Y%m%d) "PRAGMA integrity_check;"

   # For PostgreSQL
   psql -U username -d postgres -c "SELECT 1;" < data/backups/leads_$(date +%Y%m%d).sql
   ```

### Configuration Backup

1. **Version Control**

   Store configuration files in version control:

   ```bash
   git add config.yml
   git commit -m "Update configuration with new data sources"
   ```

2. **Manual Backups**

   Create backup copies before significant changes:

   ```bash
   cp config.yml config.yml.$(date +%Y%m%d)
   ```

### Export Backup

1. **Archive Important Exports**

   Archive important exports to secure storage:

   ```bash
   # Archive to a backup directory
   mkdir -p archives/exports/$(date +%Y%m)
   cp exports/important_export.xlsx archives/exports/$(date +%Y%m)/
   ```

2. **Cloud Backup**

   Upload critical exports to cloud storage:

   ```bash
   # Using AWS CLI
   aws s3 cp exports/important_export.xlsx s3://your-backup-bucket/exports/

   # Using Google Cloud Storage
   gsutil cp exports/important_export.xlsx gs://your-backup-bucket/exports/
   ```

## Database Maintenance

### SQLite Maintenance

1. **Database Vacuuming**

   Reclaim unused space and optimize the database:

   ```bash
   sqlite3 data/leads.db "VACUUM;"
   ```

   This can be automated in the configuration:

   ```yaml
   maintenance:
     sqlite_vacuum: "0 2 * * 0"  # Weekly on Sunday at 2 AM
   ```

2. **Analyze Tables**

   Update table statistics for the query optimizer:

   ```bash
   sqlite3 data/leads.db "ANALYZE;"
   ```

3. **Index Optimization**

   Create and maintain indexes for commonly queried fields:

   ```bash
   sqlite3 data/leads.db <<EOF
   CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source);
   CREATE INDEX IF NOT EXISTS idx_leads_quality_score ON leads(quality_score);
   CREATE INDEX IF NOT EXISTS idx_leads_timestamp ON leads(timestamp);
   EOF
   ```

### PostgreSQL Maintenance

If using PostgreSQL instead of SQLite:

1. **Vacuum and Analyze**

   Reclaim space and update statistics:

   ```bash
   psql -U username -d leaddb -c "VACUUM ANALYZE;"
   ```

2. **Index Maintenance**

   Rebuild indexes to eliminate fragmentation:

   ```bash
   psql -U username -d leaddb -c "REINDEX TABLE leads;"
   ```

3. **Table Statistics**

   Update statistics for the query planner:

   ```bash
   psql -U username -d leaddb -c "ANALYZE;"
   ```

## Log Management

### Log Rotation

1. **Configure Log Rotation**

   Set up log rotation in the configuration:

   ```yaml
   logging:
     file: "logs/app.log"
     max_size: 10485760  # 10 MB
     backup_count: 5
   ```

   This will keep 5 rotated log files of up to 10 MB each.

2. **Manual Log Rotation**

   Manually rotate logs when needed:

   ```bash
   mv logs/app.log logs/app.log.$(date +%Y%m%d)
   touch logs/app.log
   ```

3. **System Log Rotation**

   For production systems, configure logrotate:

   ```
   # /etc/logrotate.d/perera-lead-scraper
   /path/to/logs/app.log {
       daily
       missingok
       rotate 14
       compress
       delaycompress
       notifempty
       create 0640 scraper scraper
       postrotate
           kill -USR1 $(cat /path/to/app.pid 2>/dev/null) 2>/dev/null || true
       endscript
   }
   ```

### Log Analysis

1. **Error Trend Analysis**

   Analyze error trends:

   ```bash
   python -m src.perera_lead_scraper.cli analyze-logs --pattern "ERROR" --group-by day
   ```

2. **Log Filtering**

   Filter logs for specific components:

   ```bash
   grep "data_source:government_bids" logs/app.log | grep "ERROR"
   ```

3. **Log Archival**

   Archive old logs:

   ```bash
   # Compress logs older than 30 days
   find logs/ -type f -name "app.log.*" -mtime +30 -exec gzip {} \;

   # Move compressed logs older than 90 days to archive
   find logs/ -type f -name "app.log.*.gz" -mtime +90 -exec mv {} logs/archive/ \;
   ```

## Update Procedures

### Software Updates

1. **Check for Updates**

   Check for available updates:

   ```bash
   git fetch origin
   git log HEAD..origin/main --oneline
   ```

2. **Backup Before Update**

   Always backup before updating:

   ```bash
   # Backup database
   python -m src.perera_lead_scraper.cli backup-db

   # Backup configuration
   cp config.yml config.yml.bak
   ```

3. **Update Process**

   Standard update process:

   ```bash
   # Stop the application
   sudo systemctl stop perera-lead-scraper-api
   sudo systemctl stop perera-lead-scraper-orchestrator

   # Pull latest code
   git pull origin main

   # Update dependencies
   pip install -r requirements.txt

   # Run database migrations
   python -m src.perera_lead_scraper.cli migrate

   # Start the application
   sudo systemctl start perera-lead-scraper-api
   sudo systemctl start perera-lead-scraper-orchestrator
   ```

4. **Verify Update**

   Verify the update was successful:

   ```bash
   # Check version
   python -m src.perera_lead_scraper.cli version

   # Check health
   curl http://localhost:8000/api/health
   ```

### Docker Updates

If using Docker deployment:

1. **Pull Latest Images**

   ```bash
   docker-compose pull
   ```

2. **Update and Restart Services**

   ```bash
   docker-compose down
   docker-compose up -d
   ```

3. **Verify Update**

   ```bash
   docker-compose ps
   docker-compose logs --tail 100
   ```

## Performance Tuning

### Database Optimization

1. **Identify Slow Queries**

   Enable query logging to identify slow queries:

   ```yaml
   database:
     log_queries: true
     slow_query_threshold: 1.0  # Log queries taking more than 1 second
   ```

2. **Index Optimization**

   Add indexes for frequently queried fields:

   ```python
   def optimize_indexes():
       """Add optimal indexes based on query patterns."""
       db.execute("""
       CREATE INDEX IF NOT EXISTS idx_leads_combined ON leads(source, quality_score, status);
       """)
   ```

3. **Connection Pooling**

   Configure connection pooling for better performance:

   ```yaml
   database:
     pool_size: 10
     max_overflow: 20
     pool_timeout: 30
     pool_recycle: 1800
   ```

### API Performance

1. **Response Caching**

   Implement caching for frequently accessed endpoints:

   ```python
   @app.get("/api/stats")
   @cache(expire=300)  # Cache for 5 minutes
   async def get_system_stats():
       # Expensive operation to generate stats
       return stats
   ```

2. **Pagination Optimization**

   Optimize pagination for large result sets:

   ```python
   def get_leads_optimized(page, size, filters):
       """Optimized lead retrieval with keyset pagination."""
       # Instead of OFFSET/LIMIT, use keyset pagination
       if "last_id" in filters:
           query = "SELECT * FROM leads WHERE id > :last_id ORDER BY id LIMIT :limit"
       else:
           query = "SELECT * FROM leads ORDER BY id LIMIT :limit"
           
       return db.execute(query, {"last_id": filters.get("last_id"), "limit": size}).fetchall()
   ```

3. **Background Processing**

   Move expensive operations to background tasks:

   ```python
   @app.post("/api/export")
   async def export_leads(request: ExportRequest, background_tasks: BackgroundTasks):
       # Instead of processing immediately, schedule as background task
       job_id = str(uuid.uuid4())
       background_tasks.add_task(process_export, job_id, request)
       return {"job_id": job_id, "status": "processing"}
   ```

### Resource Allocation

1. **Worker Scaling**

   Adjust worker count based on system resources:

   ```yaml
   workers:
     api_workers: 4  # Number of Uvicorn workers
     processing_workers: 2  # Number of processing workers
   ```

2. **Memory Management**

   Configure memory limits to prevent excessive usage:

   ```yaml
   resources:
     memory_limit_mb: 1024
     enable_garbage_collection: true
     gc_threshold: 100  # Trigger GC after processing 100 leads
   ```

3. **Batch Processing**

   Implement batch processing for large datasets:

   ```python
   def process_large_dataset(items):
       """Process large dataset in batches to limit memory usage."""
       results = []
       for i in range(0, len(items), BATCH_SIZE):
           batch = items[i:i+BATCH_SIZE]
           results.extend(process_batch(batch))
           # Explicitly run garbage collection after each batch
           if config.resources.enable_garbage_collection:
               gc.collect()
       return results
   ```

## Security Maintenance

### API Key Rotation

1. **Generate New API Keys**

   Generate new API keys:

   ```bash
   python -m src.perera_lead_scraper.cli generate-api-key
   ```

2. **Update Configuration**

   Add the new key to the configuration before removing the old one:

   ```yaml
   api:
     api_keys:
       - "new_api_key_here"
       - "old_api_key_here"  # Will be removed after clients migrate
   ```

3. **Update Clients**

   Update all clients to use the new API key, then remove the old key from configuration.

### Credential Management

1. **Encrypt Sensitive Configuration**

   Encrypt sensitive parts of the configuration:

   ```bash
   python -m src.perera_lead_scraper.cli encrypt-config --fields "sources[0].credentials.password,export.hubspot.api_key"
   ```

2. **Rotate Source Credentials**

   Regularly update credentials for external services:

   ```bash
   # Update credentials for a specific source
   python -m src.perera_lead_scraper.cli update-source-credentials --source-id SOURCE_ID
   ```

### Security Scanning

1. **Dependency Scanning**

   Scan dependencies for vulnerabilities:

   ```bash
   pip install safety
   safety check
   ```

2. **Code Scanning**

   Scan code for security issues:

   ```bash
   pip install bandit
   bandit -r src/
   ```

## Health Checks

### System Health Verification

1. **API Health Check**

   Verify API health:

   ```bash
   curl http://localhost:8000/api/health
   ```

2. **Component Health Check**

   Check individual components:

   ```bash
   # Check orchestrator
   python -m src.perera_lead_scraper.cli check-component --component orchestrator

   # Check storage
   python -m src.perera_lead_scraper.cli check-component --component storage

   # Check monitoring
   python -m src.perera_lead_scraper.cli check-component --component monitoring
   ```

3. **Automated Health Monitoring**

   Set up a cron job to regularly check system health:

   ```
   # /etc/cron.d/lead-scraper-health
   */10 * * * * scraper /usr/bin/curl -s http://localhost:8000/api/health | grep -q '"status":"operational"' || /usr/bin/mail -s "Lead Scraper Health Alert" admin@example.com
   ```

### Data Quality Monitoring

1. **Lead Quality Check**

   Monitor lead quality metrics:

   ```bash
   python -m src.perera_lead_scraper.cli analyze-lead-quality
   ```

2. **Duplicate Detection**

   Check for and resolve duplicate leads:

   ```bash
   python -m src.perera_lead_scraper.cli detect-duplicates
   ```

3. **Data Validation**

   Validate lead data against expected format:

   ```bash
   python -m src.perera_lead_scraper.cli validate-leads
   ```

## Maintenance Schedule

Below is a recommended maintenance schedule:

### Daily

| Task | Description | Command/Action |
|------|-------------|----------------|
| Health check | Verify system health | `curl http://localhost:8000/api/health` |
| Log review | Check for errors or warnings | `grep "ERROR\|WARNING" logs/app.log | tail -n 100` |
| Backup verification | Verify backups were created | Check presence of latest backup files |

### Weekly

| Task | Description | Command/Action |
|------|-------------|----------------|
| Source testing | Test all data sources | `python -m src.perera_lead_scraper.cli test-all-sources` |
| Export cleanup | Remove old exports | `find exports/ -type f -mtime +30 -delete` |
| Performance review | Check system performance | `python -m src.perera_lead_scraper.cli generate-performance-report` |

### Monthly

| Task | Description | Command/Action |
|------|-------------|----------------|
| Database optimization | Optimize database | `python -m src.perera_lead_scraper.cli optimize-db` |
| API key review | Check API key security | `python -m src.perera_lead_scraper.cli check-api-keys` |
| Log rotation | Archive old logs | `find logs/ -type f -name "app.log.*" -mtime +30 -exec gzip {} \;` |

### Quarterly

| Task | Description | Command/Action |
|------|-------------|----------------|
| Security audit | Complete security review | `python -m src.perera_lead_scraper.cli security-audit` |
| Data purging | Archive old leads | `python -m src.perera_lead_scraper.cli archive-leads --older-than 365` |
| Config review | Review entire configuration | `python -m src.perera_lead_scraper.cli analyze-config` |

### As Needed

| Task | Description | Command/Action |
|------|-------------|----------------|
| Software updates | Update to latest version | Follow [Update Procedures](#update-procedures) |
| API key rotation | Rotate API keys | Follow [API Key Rotation](#api-key-rotation) |
| Source updates | Update source configuration | Update when source websites change |
# Perera Construction Lead Scraper - Monitoring Guide

This document provides detailed information about monitoring the Perera Construction Lead Scraper system, including available metrics, monitoring setup, alerting configuration, and performance baselines.

## Table of Contents

- [Available Metrics](#available-metrics)
- [Monitoring Setup](#monitoring-setup)
- [Alert Configuration](#alert-configuration)
- [Dashboard Setup](#dashboard-setup)
- [Performance Baselines](#performance-baselines)
- [Capacity Planning](#capacity-planning)
- [Log Monitoring](#log-monitoring)
- [Health Checks](#health-checks)
- [Custom Monitoring](#custom-monitoring)

## Available Metrics

The Lead Scraper system collects a wide range of metrics that can be used for monitoring and alerting.

### System Metrics

| Metric | Description | Unit | Collection Method |
|--------|-------------|------|------------------|
| cpu_percent | CPU usage percentage | % | Direct OS monitoring via psutil |
| memory_percent | Memory usage percentage | % | Direct OS monitoring via psutil |
| disk_percent | Disk usage percentage | % | Direct OS monitoring via psutil |
| network_tx_bytes | Network bytes transmitted | Bytes | Direct OS monitoring via psutil |
| network_rx_bytes | Network bytes received | Bytes | Direct OS monitoring via psutil |

### Application Metrics

| Metric | Description | Unit | Collection Method |
|--------|-------------|------|------------------|
| lead_count | Total lead count in system | Count | Database query |
| active_sources | Number of active data sources | Count | Configuration check |
| processing_time | Average lead processing time | Seconds | Timing of lead processing |
| source_success_rate | Success rate of source scraping | % | Success vs. failure tracking |
| lead_quality_average | Average lead quality score | Score (0-100) | Calculation from lead data |

### Pipeline Metrics

| Metric | Description | Unit | Collection Method |
|--------|-------------|------|------------------|
| extraction_time | Time to extract data from sources | Seconds | Pipeline timing |
| processing_time | Time to process extracted data | Seconds | Pipeline timing |
| storage_time | Time to store processed leads | Seconds | Pipeline timing |
| export_time | Time to export leads | Seconds | Pipeline timing |
| pipeline_throughput | Leads processed per minute | Leads/min | Pipeline tracking |

### Data Source Metrics

| Metric | Description | Unit | Collection Method |
|--------|-------------|------|------------------|
| source_request_count | Number of requests to source | Count | Source tracking |
| source_request_time | Average request time for source | Seconds | Source timing |
| source_lead_count | Number of leads from source | Count | Source tracking |
| source_error_count | Number of errors from source | Count | Source tracking |
| source_throttled_count | Number of throttled requests | Count | Source tracking |

### Export Metrics

| Metric | Description | Unit | Collection Method |
|--------|-------------|------|------------------|
| export_count | Number of exports performed | Count | Export tracking |
| export_lead_count | Number of leads exported | Count | Export tracking |
| export_time | Time to complete export | Seconds | Export timing |
| export_success_rate | Success rate of exports | % | Export tracking |
| hubspot_sync_time | Time to sync with HubSpot | Seconds | HubSpot export timing |

### Error Metrics

| Metric | Description | Unit | Collection Method |
|--------|-------------|------|------------------|
| error_count | Total error count | Count | Error tracking |
| error_rate | Errors per operation | Rate | Error tracking |
| warning_count | Total warning count | Count | Warning tracking |
| critical_error_count | Critical error count | Count | Error tracking |
| recovery_count | Number of automatic recoveries | Count | Recovery tracking |

## Monitoring Setup

### Built-in Monitoring

The Lead Scraper includes a built-in monitoring system that collects metrics and provides access to them via the API.

#### Accessing Metrics via API

```bash
curl -H "X-API-Key: your_api_key" http://localhost:8000/api/stats
```

This returns current system metrics:

```json
{
  "cpu_usage": 12.3,
  "memory_usage": 45.6,
  "disk_usage": 32.1,
  "lead_count": 1250,
  "avg_processing_time": 0.75,
  "success_rate": 98.5,
  "active_sources": 5,
  "recent_errors": [],
  "last_updated": "2023-01-01T12:30:45.000Z"
}
```

#### Configuring Built-in Monitoring

Edit the monitoring section in the configuration file:

```yaml
monitoring:
  metrics_interval: 300  # Collect metrics every 5 minutes
  report_interval: 86400  # Generate daily report
  metrics_database: "data/metrics.db"  # SQLite metrics storage
  metrics_retention_days: 90  # Keep metrics for 90 days
  include_metrics:
    - "cpu_percent"
    - "memory_percent"
    - "disk_percent"
    - "lead_count"
    - "processing_time"
    - "source_success_rate"
    - "export_success_rate"
  thresholds:
    cpu_percent: 80
    memory_percent: 80
    disk_percent: 90
    error_rate: 0.1
```

### Prometheus Integration

The Lead Scraper can export metrics in Prometheus format for integration with Prometheus monitoring system.

#### Enabling Prometheus Endpoint

Enable the Prometheus endpoint in the configuration:

```yaml
monitoring:
  prometheus:
    enabled: true
    endpoint: "/metrics"
    export_labels:
      environment: "production"
      service: "lead-scraper"
```

#### Prometheus Scrape Configuration

Configure Prometheus to scrape metrics from the Lead Scraper:

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'lead-scraper'
    scrape_interval: 30s
    metrics_path: '/metrics'
    basic_auth:
      username: 'prometheus'
      password: 'your_prometheus_password'
    static_configs:
      - targets: ['lead-scraper:8000']
```

### Grafana Integration

Setup Grafana to visualize metrics from Prometheus or directly from the Lead Scraper's database.

#### Grafana Datasource Configuration

1. Add Prometheus as a datasource:
   - Name: Lead Scraper Prometheus
   - Type: Prometheus
   - URL: http://prometheus:9090
   - Access: Server

2. Or add direct database connection:
   - Name: Lead Scraper Metrics
   - Type: SQLite
   - Path: /path/to/data/metrics.db

### ELK Stack Integration

For log monitoring, you can integrate with the ELK stack (Elasticsearch, Logstash, Kibana).

#### Logstash Configuration

```
# logstash.conf
input {
  file {
    path => "/path/to/logs/app.log"
    start_position => "beginning"
    type => "lead-scraper-logs"
  }
}

filter {
  grok {
    match => { "message" => "%{TIMESTAMP_ISO8601:timestamp} - %{DATA:component} - %{LOGLEVEL:level} - %{GREEDYDATA:msg}" }
  }
  
  date {
    match => [ "timestamp", "ISO8601" ]
    target => "@timestamp"
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "lead-scraper-logs-%{+YYYY.MM.dd}"
  }
}
```

## Alert Configuration

### Built-in Alerting

The Lead Scraper includes a built-in alerting system that can send notifications through various channels.

#### Email Alerts

Configure email alerts:

```yaml
monitoring:
  alerting:
    enabled: true
    channels:
      email:
        enabled: true
        smtp_server: "smtp.example.com"
        smtp_port: 587
        username: "alerts@example.com"
        password: "your_smtp_password"
        from_address: "alerts@example.com"
        recipients:
          - "admin@example.com"
          - "manager@example.com"
        use_tls: true
```

#### Webhook Alerts

Configure webhook alerts for integration with chat platforms or custom systems:

```yaml
monitoring:
  alerting:
    enabled: true
    channels:
      webhook:
        enabled: true
        url: "https://hooks.slack.com/services/your/webhook/url"
        headers:
          Content-Type: "application/json"
        method: "POST"
        template: |
          {
            "text": "[{{ level | upper }}] {{ subject }}",
            "attachments": [
              {
                "color": "{{ color }}",
                "fields": [
                  {
                    "title": "Message",
                    "value": "{{ message }}",
                    "short": false
                  },
                  {
                    "title": "System",
                    "value": "Lead Scraper",
                    "short": true
                  },
                  {
                    "title": "Timestamp",
                    "value": "{{ timestamp }}",
                    "short": true
                  }
                ]
              }
            ]
          }
```

### Alert Types

Configure different alert types:

```yaml
monitoring:
  alerting:
    alert_types:
      system_resources:
        threshold: "cpu_percent > 80 OR memory_percent > 80 OR disk_percent > 90"
        subject: "System Resource Alert"
        message: "System resources are running high: CPU: {{ cpu_percent }}%, Memory: {{ memory_percent }}%, Disk: {{ disk_percent }}%"
        level: "warning"
        cooldown: 3600  # 1 hour between alerts
        
      data_source_failure:
        threshold: "source_success_rate < 50"
        subject: "Data Source Failure"
        message: "Data source {{ source_name }} is failing with success rate {{ source_success_rate }}%"
        level: "error"
        cooldown: 1800  # 30 minutes between alerts
        
      lead_quality:
        threshold: "lead_quality_average < 40"
        subject: "Low Lead Quality Alert"
        message: "Average lead quality has dropped to {{ lead_quality_average }}"
        level: "warning"
        cooldown: 86400  # 1 day between alerts
        
      critical_error:
        threshold: "critical_error_count > 0"
        subject: "Critical Error Detected"
        message: "{{ critical_error_count }} critical errors detected in the system"
        level: "critical"
        cooldown: 300  # 5 minutes between alerts
```

### Alert Throttling

Configure alert throttling to prevent alert storms:

```yaml
monitoring:
  alerting:
    throttling:
      max_alerts_per_hour: 10
      cooldown_period: 300  # 5 minutes global cooldown
      grouped_alerts: true  # Group similar alerts
      summary_interval: 3600  # Send summary every hour if throttled
```

## Dashboard Setup

### Grafana Dashboard

Here's a sample Grafana dashboard configuration for the Lead Scraper:

#### System Overview Dashboard

```json
{
  "title": "Lead Scraper - System Overview",
  "panels": [
    {
      "title": "CPU Usage",
      "type": "graph",
      "datasource": "Lead Scraper Prometheus",
      "targets": [
        {
          "expr": "lead_scraper_cpu_percent",
          "legendFormat": "CPU %"
        }
      ],
      "thresholds": [
        {
          "value": 70,
          "op": "gt",
          "fillColor": "rgba(255, 255, 0, 0.2)",
          "line": true,
          "lineColor": "rgba(255, 255, 0, 0.6)"
        },
        {
          "value": 85,
          "op": "gt",
          "fillColor": "rgba(255, 0, 0, 0.2)",
          "line": true,
          "lineColor": "rgba(255, 0, 0, 0.6)"
        }
      ]
    },
    {
      "title": "Memory Usage",
      "type": "graph",
      "datasource": "Lead Scraper Prometheus",
      "targets": [
        {
          "expr": "lead_scraper_memory_percent",
          "legendFormat": "Memory %"
        }
      ]
    },
    {
      "title": "Disk Usage",
      "type": "gauge",
      "datasource": "Lead Scraper Prometheus",
      "targets": [
        {
          "expr": "lead_scraper_disk_percent",
          "legendFormat": "Disk %"
        }
      ],
      "thresholds": "70,85"
    },
    {
      "title": "Lead Count",
      "type": "stat",
      "datasource": "Lead Scraper Prometheus",
      "targets": [
        {
          "expr": "lead_scraper_lead_count",
          "legendFormat": "Leads"
        }
      ]
    },
    {
      "title": "Error Rate",
      "type": "graph",
      "datasource": "Lead Scraper Prometheus",
      "targets": [
        {
          "expr": "lead_scraper_error_rate",
          "legendFormat": "Error Rate"
        }
      ]
    }
  ]
}
```

#### Lead Quality Dashboard

```json
{
  "title": "Lead Scraper - Lead Quality",
  "panels": [
    {
      "title": "Average Lead Quality",
      "type": "graph",
      "datasource": "Lead Scraper Prometheus",
      "targets": [
        {
          "expr": "lead_scraper_lead_quality_average",
          "legendFormat": "Avg Quality"
        }
      ]
    },
    {
      "title": "Leads by Quality Range",
      "type": "bar",
      "datasource": "Lead Scraper Prometheus",
      "targets": [
        {
          "expr": "lead_scraper_lead_quality_range{range='0-20'}",
          "legendFormat": "0-20"
        },
        {
          "expr": "lead_scraper_lead_quality_range{range='21-40'}",
          "legendFormat": "21-40"
        },
        {
          "expr": "lead_scraper_lead_quality_range{range='41-60'}",
          "legendFormat": "41-60"
        },
        {
          "expr": "lead_scraper_lead_quality_range{range='61-80'}",
          "legendFormat": "61-80"
        },
        {
          "expr": "lead_scraper_lead_quality_range{range='81-100'}",
          "legendFormat": "81-100"
        }
      ]
    },
    {
      "title": "Lead Quality by Source",
      "type": "graph",
      "datasource": "Lead Scraper Prometheus",
      "targets": [
        {
          "expr": "lead_scraper_lead_quality_by_source",
          "legendFormat": "{{source}}"
        }
      ]
    }
  ]
}
```

### Custom HTML Dashboard

If you prefer a simpler solution, you can create a custom HTML dashboard that fetches data from the API:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lead Scraper Dashboard</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="container mt-4">
        <h1>Lead Scraper Dashboard</h1>
        
        <div class="row mt-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">System Resources</div>
                    <div class="card-body">
                        <canvas id="resourcesChart"></canvas>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">Lead Count</div>
                    <div class="card-body">
                        <canvas id="leadCountChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mt-4">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header">Lead Quality</div>
                    <div class="card-body">
                        <canvas id="leadQualityChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row mt-4">
            <div class="col-md-12">
                <div class="card">
                    <div class="card-header">Recent Errors</div>
                    <div class="card-body">
                        <table class="table" id="errorsTable">
                            <thead>
                                <tr>
                                    <th>Timestamp</th>
                                    <th>Component</th>
                                    <th>Error</th>
                                </tr>
                            </thead>
                            <tbody></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        const API_KEY = 'your_api_key_here';
        const API_BASE = 'http://localhost:8000/api';
        
        // Fetch stats every 30 seconds
        function fetchStats() {
            fetch(`${API_BASE}/stats`, {
                headers: {
                    'X-API-Key': API_KEY
                }
            })
            .then(response => response.json())
            .then(data => {
                updateResourcesChart(data);
                updateErrorsTable(data.recent_errors);
            })
            .catch(error => console.error('Error fetching stats:', error));
        }
        
        // Initialize charts and start fetching data
        document.addEventListener('DOMContentLoaded', function() {
            initializeCharts();
            fetchStats();
            setInterval(fetchStats, 30000);
        });
        
        // Initialize chart objects
        function initializeCharts() {
            // Resources chart
            window.resourcesChart = new Chart(
                document.getElementById('resourcesChart'),
                {
                    type: 'bar',
                    data: {
                        labels: ['CPU', 'Memory', 'Disk'],
                        datasets: [{
                            label: 'Usage %',
                            data: [0, 0, 0],
                            backgroundColor: [
                                'rgba(255, 99, 132, 0.2)',
                                'rgba(54, 162, 235, 0.2)',
                                'rgba(255, 206, 86, 0.2)'
                            ],
                            borderColor: [
                                'rgba(255, 99, 132, 1)',
                                'rgba(54, 162, 235, 1)',
                                'rgba(255, 206, 86, 1)'
                            ],
                            borderWidth: 1
                        }]
                    },
                    options: {
                        scales: {
                            y: {
                                beginAtZero: true,
                                max: 100
                            }
                        }
                    }
                }
            );
            
            // Lead count chart and other charts initialization...
        }
        
        // Update resources chart with new data
        function updateResourcesChart(data) {
            window.resourcesChart.data.datasets[0].data = [
                data.cpu_usage,
                data.memory_usage,
                data.disk_usage
            ];
            window.resourcesChart.update();
            
            // Update other charts...
        }
        
        // Update errors table
        function updateErrorsTable(errors) {
            const tbody = document.querySelector('#errorsTable tbody');
            tbody.innerHTML = '';
            
            errors.forEach(error => {
                const row = document.createElement('tr');
                
                const timestampCell = document.createElement('td');
                timestampCell.textContent = new Date(error.timestamp).toLocaleString();
                
                const componentCell = document.createElement('td');
                componentCell.textContent = error.component;
                
                const errorCell = document.createElement('td');
                errorCell.textContent = error.error;
                
                row.appendChild(timestampCell);
                row.appendChild(componentCell);
                row.appendChild(errorCell);
                
                tbody.appendChild(row);
            });
        }
    </script>
</body>
</html>
```

## Performance Baselines

Understanding normal system behavior is crucial for effective monitoring. Here are baseline metrics for the Lead Scraper:

### System Resource Baselines

| Metric | Normal Range | Warning Threshold | Critical Threshold |
|--------|--------------|-------------------|-------------------|
| CPU Usage | 10-30% | >70% | >85% |
| Memory Usage | 20-40% | >70% | >85% |
| Disk Usage | 30-60% | >80% | >90% |
| Network RX | 1-10 MB/s | >50 MB/s | >100 MB/s |
| Network TX | 0.1-5 MB/s | >20 MB/s | >50 MB/s |

### Application Performance Baselines

| Metric | Normal Range | Warning Threshold | Critical Threshold |
|--------|--------------|-------------------|-------------------|
| Lead Processing Time | 0.1-1.0s | >5s | >10s |
| API Response Time | 50-200ms | >1s | >3s |
| Source Request Time | 0.5-3.0s | >10s | >30s |
| Export Time | 1-30s | >120s | >300s |
| Database Query Time | 10-100ms | >500ms | >2s |

### Operational Baselines

| Metric | Normal Range | Warning Threshold | Critical Threshold |
|--------|--------------|-------------------|-------------------|
| Error Rate | 0-1% | >5% | >10% |
| Source Success Rate | 95-100% | <90% | <70% |
| Lead Quality Score | 60-80 | <50 | <30 |
| Export Success Rate | 98-100% | <95% | <90% |
| Duplicate Lead Rate | 0-2% | >5% | >10% |

### Establishing Your Own Baselines

Run the system for at least a week during normal operation to establish your own baselines:

```bash
# Generate baseline report
python -m src.perera_lead_scraper.cli generate-baseline-report --days 7
```

This will analyze a week of metrics data and generate a baseline report with recommended thresholds.

## Capacity Planning

### Current Capacity Metrics

Understand the current capacity of your Lead Scraper system:

| Metric | Typical Value | Maximum Tested |
|--------|---------------|----------------|
| Leads processed per day | 1,000-5,000 | 20,000 |
| Sources supported | 5-10 | 50 |
| Concurrent API requests | 10-20 | 100 |
| Database size per 1,000 leads | 5-10 MB | N/A |
| Memory usage per 1,000 leads | 50-100 MB | N/A |

### Scaling Guidelines

| Component | Scaling Indicator | Scaling Action |
|-----------|-------------------|----------------|
| API Server | >70% CPU usage, >1s response time | Increase worker count or instance size |
| Database | >500ms query time, >70% disk usage | Migrate to larger DB, add indexes, consider PostgreSQL |
| Worker Processes | Processing backlog >1 hour | Increase worker count or add worker instances |
| Memory | >80% memory usage | Increase memory allocation, implement batch processing |

### Growth Planning

To plan for system growth:

1. **Monitor Growth Trends**:
   ```bash
   python -m src.perera_lead_scraper.cli analyze-growth-trends --months 3
   ```

2. **Estimate Resource Needs**:
   - Each additional 10,000 leads requires approximately:
     - 50-100 MB additional database space
     - 200-500 MB additional memory during processing
     - 10-20% additional CPU capacity

3. **Scale Recommendations**:
   - <5,000 leads/month: Single instance setup
   - 5,000-20,000 leads/month: Increase instance resources
   - >20,000 leads/month: Consider distributed setup with separate API and worker instances

## Log Monitoring

### Key Log Patterns to Monitor

| Pattern | Severity | Action |
|---------|----------|--------|
| `ERROR - Database connection failed` | Critical | Investigate database connection, restart if needed |
| `ERROR - Failed to fetch data from source` | High | Check source configuration and availability |
| `ERROR - Export failed` | High | Verify export configuration and connectivity |
| `WARNING - Rate limited by source` | Medium | Adjust source scheduling or implement backoff |
| `WARNING - High memory usage` | Medium | Investigate memory usage patterns, consider scaling |
| `WARNING - Duplicate lead detected` | Low | Review deduplication settings if rate increases |

### Log Monitoring with ELK

If using the ELK stack, set up alerts for important log patterns:

1. **Create Saved Searches**:
   - Critical Errors: `level:ERROR AND NOT message:retry`
   - Data Source Failures: `level:ERROR AND component:data_source`
   - Export Failures: `level:ERROR AND component:export`

2. **Configure Watcher Alerts**:
   ```json
   {
     "trigger": {
       "schedule": {
         "interval": "5m"
       }
     },
     "input": {
       "search": {
         "request": {
           "search_type": "query_then_fetch",
           "indices": ["lead-scraper-logs-*"],
           "body": {
             "query": {
               "bool": {
                 "must": [
                   { "match": { "level": "ERROR" } },
                   { "match": { "component": "data_source" } }
                 ],
                 "filter": {
                   "range": {
                     "@timestamp": {
                       "gte": "now-5m"
                     }
                   }
                 }
               }
             }
           }
         }
       }
     },
     "condition": {
       "compare": {
         "ctx.payload.hits.total": {
           "gt": 5
         }
       }
     },
     "actions": {
       "email_admin": {
         "email": {
           "to": "admin@example.com",
           "subject": "Lead Scraper - Data Source Failures",
           "body": {
             "html": "There have been {{ctx.payload.hits.total}} data source failures in the last 5 minutes. Please investigate."
           }
         }
       }
     }
   }
   ```

### Log Aggregation

For multi-instance deployments, set up centralized logging:

- Use Filebeat to ship logs to Logstash
- Configure log forwarding in the Lead Scraper:

```yaml
logging:
  centralized:
    enabled: true
    method: "syslog"  # or "tcp", "http", etc.
    host: "logstash.example.com"
    port: 5140
    format: "json"
```

## Health Checks

### API Health Check

The system provides a health check endpoint that returns system status:

```bash
curl http://localhost:8000/api/health
```

Expected response:
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

### Docker Health Check

If using Docker, the container includes a health check:

```bash
docker inspect --format "{{.State.Health.Status}}" perera-lead-scraper
```

### Automated Health Monitoring

Set up automated health checks with your monitoring system:

#### Prometheus Alerting Rule

```yaml
groups:
- name: lead-scraper
  rules:
  - alert: LeadScraperDown
    expr: up{job="lead-scraper"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Lead Scraper is down"
      description: "The Lead Scraper instance has been down for more than 1 minute."
      
  - alert: LeadScraperHighCpu
    expr: lead_scraper_cpu_percent > 80
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "Lead Scraper high CPU usage"
      description: "CPU usage has been above 80% for more than 5 minutes: {{ $value }}%"
```

#### Monitoring Script

Create a simple monitoring script:

```bash
#!/bin/bash
# lead-scraper-monitor.sh

API_URL="http://localhost:8000/api/health"
API_KEY="your_api_key_here"
ALERT_EMAIL="admin@example.com"

# Function to send email alert
send_alert() {
    echo "ALERT: $1" | mail -s "Lead Scraper Alert: $2" $ALERT_EMAIL
}

# Check if API is responding
response=$(curl -s -o /dev/null -w "%{http_code}" -H "X-API-Key: $API_KEY" $API_URL)
if [ "$response" != "200" ]; then
    send_alert "API is not responding. HTTP code: $response" "API Down"
    exit 1
fi

# Check component health
health=$(curl -s -H "X-API-Key: $API_KEY" $API_URL)
status=$(echo $health | jq -r '.status')
if [ "$status" != "operational" ]; then
    send_alert "System status is not operational: $status" "System Degraded"
    exit 1
fi

# Check storage component
storage_status=$(echo $health | jq -r '.components.storage.status')
if [ "$storage_status" != "healthy" ]; then
    send_alert "Storage component is not healthy: $storage_status" "Storage Issue"
    exit 1
fi

# Check orchestrator component
orchestrator_status=$(echo $health | jq -r '.components.orchestrator.status')
if [ "$orchestrator_status" != "healthy" ]; then
    send_alert "Orchestrator component is not healthy: $orchestrator_status" "Orchestrator Issue"
    exit 1
fi

# Check resource usage
cpu_percent=$(echo $health | jq -r '.components.monitor.metrics.cpu_percent')
if (( $(echo "$cpu_percent > 80" | bc -l) )); then
    send_alert "High CPU usage: $cpu_percent%" "Resource Warning"
    exit 1
fi

echo "All checks passed. System is healthy."
exit 0
```

Set up a cron job to run this script regularly:

```
*/5 * * * * /path/to/lead-scraper-monitor.sh >> /var/log/lead-scraper-monitor.log 2>&1
```

## Custom Monitoring

### Creating Custom Metrics

You can extend the monitoring system with custom metrics:

1. **Define Custom Metrics in Code**:

```python
from perera_lead_scraper.monitoring.metrics import register_metric, update_metric

# Register a custom metric
register_metric(
    name="lead_conversion_rate",
    description="Percentage of leads that converted to deals",
    metric_type="gauge"
)

# Update the metric value
def calculate_conversion_rate():
    converted = db.execute("SELECT COUNT(*) FROM leads WHERE status = 'converted'").fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    rate = (converted / total * 100) if total > 0 else 0
    update_metric("lead_conversion_rate", rate)
    return rate
```

2. **Configure Custom Metrics Collection**:

```yaml
monitoring:
  custom_metrics:
    - name: "lead_conversion_rate"
      enabled: true
      collection_interval: 3600  # 1 hour
      alert_threshold: 10  # Alert if conversion rate drops below 10%
```

### Custom Dashboard Widgets

Add custom widgets to your monitoring dashboard:

```javascript
// Custom Conversion Rate Widget
function createConversionWidget(containerId) {
    const container = document.getElementById(containerId);
    
    // Create gauge element
    const gauge = document.createElement('div');
    gauge.className = 'gauge-container';
    container.appendChild(gauge);
    
    // Initialize gauge
    const gaugeChart = new GaugeChart(gauge, {
        min: 0,
        max: 100,
        label: 'Conversion Rate',
        units: '%'
    });
    
    // Update function
    async function updateGauge() {
        const response = await fetch(`${API_BASE}/custom-metrics/lead_conversion_rate`, {
            headers: {
                'X-API-Key': API_KEY
            }
        });
        const data = await response.json();
        gaugeChart.update(data.value);
    }
    
    // Initial update and set interval
    updateGauge();
    setInterval(updateGauge, 60000);
    
    return gaugeChart;
}
```

### Custom Monitoring Plugins

Create custom monitoring plugins for specific business needs:

1. **Create a Plugin File**:

```python
# plugins/competitor_monitor.py
import requests
from bs4 import BeautifulSoup
from perera_lead_scraper.monitoring.plugin import MonitoringPlugin

class CompetitorMonitor(MonitoringPlugin):
    """Monitor competitor websites for changes."""
    
    plugin_name = "competitor_monitor"
    
    def __init__(self, config):
        super().__init__(config)
        self.competitors = config.get("competitors", [])
        self.check_interval = config.get("check_interval", 86400)  # Daily
        self.last_check = 0
        self.last_data = {}
    
    def check(self):
        """Check competitor websites for changes."""
        current_time = time.time()
        
        # Only check if interval has passed
        if current_time - self.last_check < self.check_interval:
            return
        
        self.last_check = current_time
        changes = []
        
        for competitor in self.competitors:
            try:
                response = requests.get(competitor["url"], timeout=10)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract data using selector
                element = soup.select_one(competitor["selector"])
                current_data = element.text.strip() if element else ""
                
                # Compare with last data
                if competitor["url"] in self.last_data and self.last_data[competitor["url"]] != current_data:
                    changes.append({
                        "competitor": competitor["name"],
                        "url": competitor["url"],
                        "old_data": self.last_data[competitor["url"]],
                        "new_data": current_data
                    })
                
                # Update last data
                self.last_data[competitor["url"]] = current_data
                
            except Exception as e:
                self.logger.error(f"Error checking competitor {competitor['name']}: {str(e)}")
        
        # Report any changes
        if changes:
            subject = f"Competitor Changes Detected: {len(changes)} changes"
            message = "The following competitor changes were detected:\n\n"
            for change in changes:
                message += f"Competitor: {change['competitor']}\n"
                message += f"URL: {change['url']}\n"
                message += f"Old: {change['old_data']}\n"
                message += f"New: {change['new_data']}\n\n"
            
            self.send_alert(subject, message, level="info")
        
        return changes
```

2. **Configure the Plugin**:

```yaml
monitoring:
  plugins:
    competitor_monitor:
      enabled: true
      competitors:
        - name: "Competitor A"
          url: "https://www.competitora.com/pricing"
          selector: ".pricing-table"
        - name: "Competitor B"
          url: "https://www.competitorb.com/services"
          selector: ".services-list"
      check_interval: 86400  # Daily
```
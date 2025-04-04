# System Monitoring Module

This module provides comprehensive monitoring, metrics collection, anomaly detection, and alerting for the Perera Construction Lead Scraper system.

## Features

- Real-time metrics collection and storage
- Component health monitoring
- Data source quality tracking
- Processing pipeline metrics
- Export pipeline performance monitoring
- Anomaly detection
- Alerting system with configurable notification channels
- Performance reporting

## Architecture

The monitoring system consists of the following components:

1. **SystemMonitor**: Central monitoring class that coordinates metrics collection and analysis
2. **MetricsDatabase**: Storage for time-series metrics data
3. **Alert**: Representation of system alerts
4. **Alert levels**: INFO, WARNING, ERROR, CRITICAL

## Metrics Collection

The monitoring system collects the following types of metrics:

- **System metrics**: CPU, memory, disk, network usage
- **Source metrics**: Success rates, lead yields, error rates
- **Pipeline metrics**: Processing times, validation rates, enrichment rates
- **Export metrics**: Export rates, error rates, backlogs
- **Lead quality metrics**: Quality scores, validation rates, market sector distribution

## Anomaly Detection

The system uses both threshold-based and statistical anomaly detection:

- Threshold-based detection for resource usage (CPU, memory, disk)
- Threshold-based detection for error rates and success rates
- Statistical detection (z-score) for performance metrics
- Trend analysis for lead quality

## Alerting System

Alerts can be delivered through:

- Email notifications (SMTP)
- Webhook integrations
- Database storage for UI display

Alert levels are configurable and include rate limiting to prevent alert storms.

## Configuration

The following configuration options are available:

```python
# Monitoring intervals
MONITORING_METRICS_INTERVAL=60  # seconds
MONITORING_REPORT_INTERVAL=3600  # seconds

# Alert settings
MONITORING_ALERT_COOLDOWN=300  # seconds
MONITORING_EMAIL_ALERTS_ENABLED=false
MONITORING_EMAIL_FROM=alerts@example.com
MONITORING_EMAIL_TO=admin@example.com
MONITORING_EMAIL_SMTP_SERVER=smtp.example.com
MONITORING_EMAIL_SMTP_PORT=587
MONITORING_EMAIL_SMTP_USERNAME=user
MONITORING_EMAIL_SMTP_PASSWORD=password
MONITORING_EMAIL_USE_TLS=true

# Webhook alerts
MONITORING_WEBHOOK_ALERTS_ENABLED=false
MONITORING_WEBHOOK_URL=https://example.com/webhook

# Thresholds
MONITORING_THRESHOLD_CPU_USAGE=80
MONITORING_THRESHOLD_MEMORY_USAGE=80
MONITORING_THRESHOLD_DISK_USAGE=85
MONITORING_THRESHOLD_SOURCE_ERROR_RATE=0.3
MONITORING_THRESHOLD_EXPORT_ERROR_RATE=0.2
MONITORING_THRESHOLD_LEAD_VALIDATION_RATE=0.5

# Warning levels
MONITORING_WARNING_CPU_USAGE=70
MONITORING_WARNING_MEMORY_USAGE=70
MONITORING_WARNING_DISK_USAGE=75
MONITORING_WARNING_SOURCE_ERROR_RATE=0.2
MONITORING_WARNING_EXPORT_ERROR_RATE=0.1
MONITORING_WARNING_LEAD_VALIDATION_RATE=0.6
```

## Usage

### Basic Usage

```python
from src.perera_lead_scraper.monitoring.monitoring import SystemMonitor

# Create monitor
monitor = SystemMonitor()

# Start monitoring
monitor.start_monitoring()

# Generate performance report
report = monitor.generate_performance_report()

# Stop monitoring
monitor.stop_monitoring()
```

### Command-line Usage

The monitoring module can also be run as a standalone tool:

```bash
python -m src.perera_lead_scraper.monitoring.monitoring --report
```

## Metrics Database

The monitoring system uses a SQLite database to store metrics. The database schema includes:

- `metrics` table: Stores all system metrics
- `alerts` table: Stores system alerts

## Troubleshooting

Common issues:

1. **High CPU/Memory Usage**: Check resource-intensive components like scrapers
2. **Source Failures**: Validate source configurations and credentials
3. **Pipeline Performance Issues**: Look for bottlenecks in processing stages
4. **Export Failures**: Check API keys and rate limits

## Performance Considerations

- Metrics are collected at configurable intervals (default: 60 seconds)
- Old metrics are purged automatically (default retention: 24 hours)
- Alerts use cooldown periods to prevent flooding
- Resource usage is monitored to ensure the monitoring itself doesn't impact system performance
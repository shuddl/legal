#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
System Monitoring Module

Provides comprehensive monitoring, metrics collection, anomaly detection,
and alerting for the Perera Construction Lead Scraper system.
"""

import os
import time
import json
import logging
import uuid
import statistics
import threading
import datetime
import sqlite3
import smtplib
import socket
import psutil
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Any, Optional, Union, Tuple, Set, Callable
from collections import defaultdict, deque
from pathlib import Path
import numpy as np
from enum import Enum
import platform
import traceback

# Application imports
from perera_lead_scraper.models.lead import Lead, LeadStatus, MarketSector
from perera_lead_scraper.utils.storage import LeadStorage
from perera_lead_scraper.config import config

# Configure logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_METRICS_INTERVAL = 60  # seconds
DEFAULT_METRICS_RETENTION = 24 * 60 * 60  # 24 hours in seconds
DEFAULT_ALERT_COOLDOWN = 300  # 5 minutes in seconds
DEFAULT_ANOMALY_DETECTION_WINDOW = 60  # data points for anomaly detection
DEFAULT_METRICS_DB_PATH = "metrics.db"
DEFAULT_REPORT_INTERVAL = 3600  # 1 hour in seconds
DEFAULT_SOURCE_HEALTH_THRESHOLD = 0.6  # 60% success rate for source health


class MetricType(str, Enum):
    """Types of metrics collected by the system monitor."""
    SYSTEM = "system"
    SOURCE = "source"
    PIPELINE = "pipeline"
    EXPORT = "export"
    LEAD = "lead"
    COMPONENT = "component"
    CUSTOM = "custom"


class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Alert:
    """System alert representation."""
    
    def __init__(self, 
                level: AlertLevel,
                message: str,
                component: str,
                metric: Optional[str] = None,
                value: Optional[float] = None,
                threshold: Optional[float] = None,
                context: Optional[Dict[str, Any]] = None,
                timestamp: Optional[datetime.datetime] = None):
        """
        Initialize a system alert.
        
        Args:
            level: Alert severity level
            message: Alert message
            component: Component that generated the alert
            metric: Related metric name (if applicable)
            value: Current metric value (if applicable)
            threshold: Alert threshold value (if applicable)
            context: Additional context information
            timestamp: Alert timestamp (defaults to now)
        """
        self.id = str(uuid.uuid4())
        self.level = level
        self.message = message
        self.component = component
        self.metric = metric
        self.value = value
        self.threshold = threshold
        self.context = context or {}
        self.timestamp = timestamp or datetime.datetime.now()
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "id": self.id,
            "level": self.level,
            "message": self.message,
            "component": self.component,
            "metric": self.metric,
            "value": self.value,
            "threshold": self.threshold,
            "context": self.context,
            "timestamp": self.timestamp.isoformat()
        }


class MetricsDatabase:
    """Database for storing and retrieving system metrics."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the metrics database.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            DEFAULT_METRICS_DB_PATH
        )
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize database
        self._initialize_db()
        
    def _initialize_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create metrics table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL,
                metric_type TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                value REAL,
                component TEXT,
                source_id TEXT,
                tags TEXT,
                metadata TEXT
            )
            ''')
            
            # Create alerts table
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                timestamp DATETIME NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                component TEXT NOT NULL,
                metric TEXT,
                value REAL,
                threshold REAL,
                context TEXT,
                acknowledged BOOLEAN DEFAULT 0,
                resolved BOOLEAN DEFAULT 0
            )
            ''')
            
            # Create indexes
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics(metric_name)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_component ON metrics(component)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_type ON metrics(metric_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_source ON metrics(source_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_level ON alerts(level)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_component ON alerts(component)')
            
            conn.commit()
    
    def store_metric(self, 
                    metric_type: MetricType,
                    metric_name: str,
                    value: Union[float, int, str],
                    component: Optional[str] = None,
                    source_id: Optional[str] = None,
                    tags: Optional[List[str]] = None,
                    metadata: Optional[Dict[str, Any]] = None,
                    timestamp: Optional[datetime.datetime] = None) -> None:
        """
        Store a metric in the database.
        
        Args:
            metric_type: Type of metric
            metric_name: Name of the metric
            value: Metric value
            component: Component associated with the metric
            source_id: Data source ID (if applicable)
            tags: Tags associated with the metric
            metadata: Additional metadata
            timestamp: Metric timestamp (defaults to now)
        """
        # Prepare values
        metric_timestamp = timestamp or datetime.datetime.now()
        tags_str = json.dumps(tags) if tags else None
        metadata_str = json.dumps(metadata) if metadata else None
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT INTO metrics 
                    (timestamp, metric_type, metric_name, value, component, source_id, tags, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        metric_timestamp.isoformat(),
                        metric_type,
                        metric_name,
                        value,
                        component,
                        source_id,
                        tags_str,
                        metadata_str
                    )
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error storing metric {metric_name}: {str(e)}")
    
    def store_alert(self, alert: Alert) -> None:
        """
        Store an alert in the database.
        
        Args:
            alert: Alert to store
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT INTO alerts 
                    (id, timestamp, level, message, component, metric, value, threshold, context)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        alert.id,
                        alert.timestamp.isoformat(),
                        alert.level,
                        alert.message,
                        alert.component,
                        alert.metric,
                        alert.value,
                        alert.threshold,
                        json.dumps(alert.context) if alert.context else None
                    )
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error storing alert {alert.id}: {str(e)}")
    
    def get_metrics(self, 
                   metric_type: Optional[MetricType] = None,
                   metric_name: Optional[str] = None,
                   component: Optional[str] = None,
                   source_id: Optional[str] = None,
                   start_time: Optional[datetime.datetime] = None,
                   end_time: Optional[datetime.datetime] = None,
                   limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get metrics from the database.
        
        Args:
            metric_type: Filter by metric type
            metric_name: Filter by metric name
            component: Filter by component
            source_id: Filter by source ID
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum number of results
        
        Returns:
            List of metrics as dictionaries
        """
        query = "SELECT * FROM metrics WHERE 1=1"
        params = []
        
        # Apply filters
        if metric_type:
            query += " AND metric_type = ?"
            params.append(metric_type)
        
        if metric_name:
            query += " AND metric_name = ?"
            params.append(metric_name)
        
        if component:
            query += " AND component = ?"
            params.append(component)
        
        if source_id:
            query += " AND source_id = ?"
            params.append(source_id)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())
        
        # Add ordering and limit
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                results = []
                for row in cursor.fetchall():
                    result = dict(row)
                    
                    # Parse JSON fields
                    if result.get('tags'):
                        result['tags'] = json.loads(result['tags'])
                    
                    if result.get('metadata'):
                        result['metadata'] = json.loads(result['metadata'])
                    
                    results.append(result)
                
                return results
        except Exception as e:
            logger.error(f"Error retrieving metrics: {str(e)}")
            return []
    
    def get_recent_alerts(self, 
                         level: Optional[AlertLevel] = None,
                         component: Optional[str] = None,
                         hours: int = 24,
                         limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent alerts from the database.
        
        Args:
            level: Filter by alert level
            component: Filter by component
            hours: Number of hours to look back
            limit: Maximum number of results
        
        Returns:
            List of alerts as dictionaries
        """
        query = "SELECT * FROM alerts WHERE 1=1"
        params = []
        
        # Apply filters
        if level:
            query += " AND level = ?"
            params.append(level)
        
        if component:
            query += " AND component = ?"
            params.append(component)
        
        # Apply time filter
        if hours > 0:
            start_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        
        # Add ordering and limit
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                results = []
                for row in cursor.fetchall():
                    result = dict(row)
                    
                    # Parse JSON fields
                    if result.get('context'):
                        result['context'] = json.loads(result['context'])
                    
                    results.append(result)
                
                return results
        except Exception as e:
            logger.error(f"Error retrieving alerts: {str(e)}")
            return []
    
    def clear_old_metrics(self, retention_seconds: int = DEFAULT_METRICS_RETENTION) -> int:
        """
        Remove metrics older than the retention period.
        
        Args:
            retention_seconds: Retention period in seconds
        
        Returns:
            Number of metrics deleted
        """
        cutoff_time = datetime.datetime.now() - datetime.timedelta(seconds=retention_seconds)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM metrics WHERE timestamp < ?",
                    (cutoff_time.isoformat(),)
                )
                rows_deleted = cursor.rowcount
                conn.commit()
                return rows_deleted
        except Exception as e:
            logger.error(f"Error clearing old metrics: {str(e)}")
            return 0
    
    def get_metric_statistics(self, 
                             metric_name: str,
                             component: Optional[str] = None,
                             hours: int = 24) -> Dict[str, Any]:
        """
        Calculate statistics for a metric.
        
        Args:
            metric_name: Metric name
            component: Filter by component
            hours: Number of hours to analyze
        
        Returns:
            Dictionary with statistics
        """
        start_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
        
        query = "SELECT value FROM metrics WHERE metric_name = ? AND timestamp >= ?"
        params = [metric_name, start_time.isoformat()]
        
        if component:
            query += " AND component = ?"
            params.append(component)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                
                values = [row[0] for row in cursor.fetchall() if row[0] is not None]
                
                if not values:
                    return {
                        "metric": metric_name,
                        "component": component,
                        "hours": hours,
                        "count": 0,
                        "statistics": None
                    }
                
                return {
                    "metric": metric_name,
                    "component": component,
                    "hours": hours,
                    "count": len(values),
                    "statistics": {
                        "min": min(values),
                        "max": max(values),
                        "mean": statistics.mean(values),
                        "median": statistics.median(values),
                        "stddev": statistics.stdev(values) if len(values) > 1 else 0,
                        "latest": values[0] if values else None
                    }
                }
                
        except Exception as e:
            logger.error(f"Error calculating metric statistics: {str(e)}")
            return {
                "metric": metric_name,
                "component": component,
                "hours": hours,
                "count": 0,
                "error": str(e),
                "statistics": None
            }


class SystemMonitor:
    """
    System monitoring, metrics collection, and alerting.
    
    Monitors all aspects of the lead generation system, collects metrics,
    detects anomalies, and triggers alerts for potential issues.
    """
    
    def __init__(self, metrics_db_path: Optional[str] = None):
        """
        Initialize the system monitor.
        
        Args:
            metrics_db_path: Path to the metrics database
        """
        # Initialize metrics database
        self.metrics_db = MetricsDatabase(metrics_db_path)
        
        # Initialize component references
        self.storage = LeadStorage()
        
        # Initialize metric collection
        self.metrics_interval = getattr(config, 'monitoring_metrics_interval', DEFAULT_METRICS_INTERVAL)
        self.report_interval = getattr(config, 'monitoring_report_interval', DEFAULT_REPORT_INTERVAL)
        
        # Initialize alerting
        self.alert_cooldown = getattr(config, 'monitoring_alert_cooldown', DEFAULT_ALERT_COOLDOWN)
        self.alert_cooldowns = {}  # Track alert cooldowns
        self.alert_history = deque(maxlen=100)  # Recent alerts
        
        # Initialize metric history for anomaly detection
        self.metric_history = defaultdict(lambda: deque(maxlen=DEFAULT_ANOMALY_DETECTION_WINDOW))
        
        # Initialize monitoring state
        self.is_running = False
        self.monitor_thread = None
        self._shutdown_requested = False
        self._shutdown_event = threading.Event()
        
        # Get alert configuration
        self.alert_config = {
            "email": {
                "enabled": getattr(config, 'monitoring_email_alerts_enabled', False),
                "from_address": getattr(config, 'monitoring_email_from', None),
                "to_addresses": getattr(config, 'monitoring_email_to', "").split(","),
                "smtp_server": getattr(config, 'monitoring_email_smtp_server', None),
                "smtp_port": getattr(config, 'monitoring_email_smtp_port', 587),
                "smtp_username": getattr(config, 'monitoring_email_smtp_username', None),
                "smtp_password": getattr(config, 'monitoring_email_smtp_password', None),
                "use_tls": getattr(config, 'monitoring_email_use_tls', True)
            },
            "webhook": {
                "enabled": getattr(config, 'monitoring_webhook_alerts_enabled', False),
                "url": getattr(config, 'monitoring_webhook_url', None)
            },
            "thresholds": {
                "cpu_usage": getattr(config, 'monitoring_threshold_cpu_usage', 80),
                "memory_usage": getattr(config, 'monitoring_threshold_memory_usage', 80),
                "disk_usage": getattr(config, 'monitoring_threshold_disk_usage', 85),
                "source_error_rate": getattr(config, 'monitoring_threshold_source_error_rate', 0.3),
                "export_error_rate": getattr(config, 'monitoring_threshold_export_error_rate', 0.2),
                "lead_validation_rate": getattr(config, 'monitoring_threshold_lead_validation_rate', 0.5)
            },
            "levels": {
                "warning": {
                    "cpu_usage": getattr(config, 'monitoring_warning_cpu_usage', 70),
                    "memory_usage": getattr(config, 'monitoring_warning_memory_usage', 70),
                    "disk_usage": getattr(config, 'monitoring_warning_disk_usage', 75),
                    "source_error_rate": getattr(config, 'monitoring_warning_source_error_rate', 0.2),
                    "export_error_rate": getattr(config, 'monitoring_warning_export_error_rate', 0.1),
                    "lead_validation_rate": getattr(config, 'monitoring_warning_lead_validation_rate', 0.6)
                }
            }
        }
        
        logger.info("System monitor initialized")
    
    def start_monitoring(self) -> None:
        """Start the monitoring process."""
        if self.is_running:
            logger.warning("Monitoring is already running")
            return
        
        logger.info("Starting system monitoring")
        self.is_running = True
        self._shutdown_requested = False
        self._shutdown_event.clear()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True,
            name="SystemMonitorThread"
        )
        self.monitor_thread.start()
        
        logger.info("System monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop the monitoring process."""
        if not self.is_running:
            logger.warning("Monitoring is not running")
            return
        
        logger.info("Stopping system monitoring")
        self._shutdown_requested = True
        self._shutdown_event.set()
        
        # Wait for monitoring thread to finish
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=10.0)
        
        self.is_running = False
        logger.info("System monitoring stopped")
    
    def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        logger.info("Monitoring loop started")
        
        last_metrics_time = 0
        last_report_time = 0
        
        try:
            while not self._shutdown_requested:
                current_time = time.time()
                
                # Collect metrics periodically
                if current_time - last_metrics_time >= self.metrics_interval:
                    self.track_metrics()
                    last_metrics_time = current_time
                
                # Generate performance report periodically
                if current_time - last_report_time >= self.report_interval:
                    self.generate_performance_report()
                    last_report_time = current_time
                
                # Check for anomalies
                issues = self.detect_anomalies()
                if issues:
                    self.alert_on_critical_issues(issues)
                
                # Sleep briefly
                self._shutdown_event.wait(1.0)
                
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}", exc_info=True)
        
        logger.info("Monitoring loop ended")
    
    def track_metrics(self) -> None:
        """
        Collect and record system metrics.
        
        This method collects metrics from various system components and stores them
        in the metrics database for analysis and monitoring.
        """
        logger.debug("Collecting system metrics")
        
        try:
            # Track system resource metrics
            self._track_system_resources()
            
            # Track component metrics
            self._track_component_metrics()
            
            # Track storage metrics
            self._track_storage_metrics()
            
            # Track pipeline metrics
            pipeline_metrics = self.monitor_processing_pipeline()
            for name, value in pipeline_metrics.items():
                self.metrics_db.store_metric(
                    metric_type=MetricType.PIPELINE,
                    metric_name=name,
                    value=value,
                    component="processing_pipeline"
                )
            
            # Track export metrics
            export_metrics = self.monitor_export_pipeline()
            for name, value in export_metrics.items():
                self.metrics_db.store_metric(
                    metric_type=MetricType.EXPORT,
                    metric_name=name,
                    value=value,
                    component="export_pipeline"
                )
            
            # Track lead metrics
            lead_metrics = self.track_lead_quality()
            for name, value in lead_metrics.items():
                self.metrics_db.store_metric(
                    metric_type=MetricType.LEAD,
                    metric_name=name,
                    value=value,
                    component="lead_quality"
                )
            
            # Track data source metrics
            source_metrics = self.monitor_data_sources()
            for source_id, metrics in source_metrics.items():
                for name, value in metrics.items():
                    if isinstance(value, (int, float)):
                        self.metrics_db.store_metric(
                            metric_type=MetricType.SOURCE,
                            metric_name=name,
                            value=value,
                            component="data_sources",
                            source_id=source_id
                        )
            
            # Log system status
            self.log_system_status()
            
            # Clean up old metrics
            self.metrics_db.clear_old_metrics()
            
        except Exception as e:
            logger.error(f"Error tracking metrics: {str(e)}", exc_info=True)
    
    def _track_system_resources(self) -> None:
        """Track system resource usage."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.metrics_db.store_metric(
                metric_type=MetricType.SYSTEM,
                metric_name="cpu_usage_percent",
                value=cpu_percent,
                component="system"
            )
            
            # Memory usage
            memory = psutil.virtual_memory()
            self.metrics_db.store_metric(
                metric_type=MetricType.SYSTEM,
                metric_name="memory_usage_percent",
                value=memory.percent,
                component="system"
            )
            self.metrics_db.store_metric(
                metric_type=MetricType.SYSTEM,
                metric_name="memory_available_mb",
                value=memory.available / (1024 * 1024),
                component="system"
            )
            
            # Disk usage
            disk = psutil.disk_usage('/')
            self.metrics_db.store_metric(
                metric_type=MetricType.SYSTEM,
                metric_name="disk_usage_percent",
                value=disk.percent,
                component="system"
            )
            self.metrics_db.store_metric(
                metric_type=MetricType.SYSTEM,
                metric_name="disk_free_gb",
                value=disk.free / (1024 * 1024 * 1024),
                component="system"
            )
            
            # Network stats
            net_io = psutil.net_io_counters()
            self.metrics_db.store_metric(
                metric_type=MetricType.SYSTEM,
                metric_name="network_bytes_sent",
                value=net_io.bytes_sent,
                component="system"
            )
            self.metrics_db.store_metric(
                metric_type=MetricType.SYSTEM,
                metric_name="network_bytes_recv",
                value=net_io.bytes_recv,
                component="system"
            )
            
            # Process info
            process = psutil.Process()
            self.metrics_db.store_metric(
                metric_type=MetricType.SYSTEM,
                metric_name="process_cpu_percent",
                value=process.cpu_percent(interval=0.1),
                component="system"
            )
            self.metrics_db.store_metric(
                metric_type=MetricType.SYSTEM,
                metric_name="process_memory_mb",
                value=process.memory_info().rss / (1024 * 1024),
                component="system"
            )
            self.metrics_db.store_metric(
                metric_type=MetricType.SYSTEM,
                metric_name="process_threads",
                value=process.num_threads(),
                component="system"
            )
            
        except Exception as e:
            logger.error(f"Error tracking system resources: {str(e)}")
    
    def _track_component_metrics(self) -> None:
        """Track component-specific metrics."""
        try:
            # Get reference to orchestrator if available
            orchestrator = None
            try:
                from perera_lead_scraper.orchestration.orchestrator import LeadGenerationOrchestrator
                # This is just a simple check to see if the orchestrator is in the current process
                # In a real implementation, you might get this from a registry or service locator
                for thread in threading.enumerate():
                    if hasattr(thread, "orchestrator") and isinstance(thread.orchestrator, LeadGenerationOrchestrator):
                        orchestrator = thread.orchestrator
                        break
            except ImportError:
                logger.debug("Orchestrator module not available")
            
            if orchestrator:
                # Get orchestrator metrics
                metrics = orchestrator.get_system_metrics()
                
                # Store relevant metrics
                self.metrics_db.store_metric(
                    metric_type=MetricType.COMPONENT,
                    metric_name="active_sources",
                    value=metrics.get("active_sources", 0),
                    component="orchestrator"
                )
                self.metrics_db.store_metric(
                    metric_type=MetricType.COMPONENT,
                    metric_name="source_executions",
                    value=metrics.get("source_executions", 0),
                    component="orchestrator"
                )
                self.metrics_db.store_metric(
                    metric_type=MetricType.COMPONENT,
                    metric_name="total_leads_processed",
                    value=metrics.get("total_leads_processed", 0),
                    component="orchestrator"
                )
                self.metrics_db.store_metric(
                    metric_type=MetricType.COMPONENT,
                    metric_name="leads_exported",
                    value=metrics.get("leads_exported", 0),
                    component="orchestrator"
                )
                self.metrics_db.store_metric(
                    metric_type=MetricType.COMPONENT,
                    metric_name="total_errors",
                    value=metrics.get("total_errors", 0),
                    component="orchestrator"
                )
            
        except Exception as e:
            logger.error(f"Error tracking component metrics: {str(e)}")
    
    def _track_storage_metrics(self) -> None:
        """Track storage-related metrics."""
        try:
            # Get storage metrics
            lead_counts = self.storage.count_leads_by_status()
            source_counts = self.storage.count_leads_by_source()
            sector_counts = self.storage.count_leads_by_market_sector()
            
            # Store lead status counts
            for status, count in lead_counts.items():
                self.metrics_db.store_metric(
                    metric_type=MetricType.COMPONENT,
                    metric_name=f"lead_count_{status}",
                    value=count,
                    component="storage"
                )
            
            # Store total lead count
            total_leads = sum(lead_counts.values())
            self.metrics_db.store_metric(
                metric_type=MetricType.COMPONENT,
                metric_name="total_leads",
                value=total_leads,
                component="storage"
            )
            
            # Store top sources by lead count
            for source, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                self.metrics_db.store_metric(
                    metric_type=MetricType.COMPONENT,
                    metric_name=f"source_lead_count",
                    value=count,
                    component="storage",
                    source_id=source
                )
            
            # Store market sector distribution
            for sector, count in sector_counts.items():
                self.metrics_db.store_metric(
                    metric_type=MetricType.COMPONENT,
                    metric_name=f"sector_lead_count_{sector}",
                    value=count,
                    component="storage"
                )
            
        except Exception as e:
            logger.error(f"Error tracking storage metrics: {str(e)}")
    
    def monitor_data_sources(self) -> Dict[str, Dict[str, Any]]:
        """
        Check health and performance of data sources.
        
        Returns:
            Dict: Source metrics indexed by source ID
        """
        logger.debug("Monitoring data sources")
        result = {}
        
        try:
            # Try to get orchestrator if available
            orchestrator = None
            try:
                from perera_lead_scraper.orchestration.orchestrator import LeadGenerationOrchestrator
                for thread in threading.enumerate():
                    if hasattr(thread, "orchestrator") and isinstance(thread.orchestrator, LeadGenerationOrchestrator):
                        orchestrator = thread.orchestrator
                        break
            except ImportError:
                logger.debug("Orchestrator module not available")
            
            # If orchestrator is available, get source metrics
            if orchestrator:
                source_performance = orchestrator.track_source_performance()
                for source_id, metrics in source_performance.items():
                    # Store relevant metrics
                    source_metrics = {
                        "success_rate": metrics.get("success_rate", 0.0),
                        "quality_score": metrics.get("quality_score", 0.0),
                        "priority_score": metrics.get("priority_score", 0.0),
                        "error_count": metrics.get("error_count", 0),
                        "consecutive_errors": metrics.get("consecutive_errors", 0),
                        "total_leads_found": metrics.get("total_leads_found", 0),
                        "valid_leads_found": metrics.get("valid_leads_found", 0),
                        "health": 1.0 if metrics.get("success_rate", 0.0) > DEFAULT_SOURCE_HEALTH_THRESHOLD else 0.0
                    }
                    
                    result[source_id] = source_metrics
            
            # Get lead counts by source from storage
            source_counts = self.storage.count_leads_by_source()
            
            # Add lead counts to source metrics
            for source_id, count in source_counts.items():
                if source_id not in result:
                    result[source_id] = {}
                
                result[source_id]["total_stored_leads"] = count
            
            return result
            
        except Exception as e:
            logger.error(f"Error monitoring data sources: {str(e)}")
            return result
    
    def monitor_processing_pipeline(self) -> Dict[str, Any]:
        """
        Track extraction pipeline metrics.
        
        Returns:
            Dict: Pipeline metrics
        """
        logger.debug("Monitoring processing pipeline")
        result = {}
        
        try:
            # Get lead status counts
            lead_counts = self.storage.count_leads_by_status()
            
            # Calculate key metrics
            total_leads = sum(lead_counts.values())
            result["total_leads"] = total_leads
            
            # Calculate validation rate
            new_count = lead_counts.get("new", 0)
            validated_count = lead_counts.get("validated", 0)
            enriched_count = lead_counts.get("enriched", 0)
            rejected_count = lead_counts.get("rejected", 0)
            
            # Calculate processing rates
            processed_count = validated_count + enriched_count + rejected_count
            if processed_count > 0:
                result["validation_rate"] = (validated_count + enriched_count) / processed_count
            else:
                result["validation_rate"] = 0.0
            
            # Calculate enrichment rate
            if validated_count > 0:
                result["enrichment_rate"] = enriched_count / validated_count
            else:
                result["enrichment_rate"] = 0.0
            
            # Calculate rejection rate
            if processed_count > 0:
                result["rejection_rate"] = rejected_count / processed_count
            else:
                result["rejection_rate"] = 0.0
            
            # Calculate pipeline throughput and efficiency
            # This would normally come from real pipeline metrics
            # Here we're just using placeholder calculations
            result["pipeline_throughput"] = total_leads / 10  # Assuming 10 hours of operation
            result["pipeline_efficiency"] = result["validation_rate"] * result["enrichment_rate"]
            
            return result
            
        except Exception as e:
            logger.error(f"Error monitoring processing pipeline: {str(e)}")
            return result
    
    def monitor_export_pipeline(self) -> Dict[str, Any]:
        """
        Monitor HubSpot export performance.
        
        Returns:
            Dict: Export metrics
        """
        logger.debug("Monitoring export pipeline")
        result = {}
        
        try:
            # Get relevant status counts
            lead_counts = self.storage.count_leads_by_status()
            
            enriched_count = lead_counts.get("enriched", 0)
            exported_count = lead_counts.get("exported", 0)
            
            # Calculate export rate
            exportable_count = enriched_count + exported_count
            if exportable_count > 0:
                result["export_rate"] = exported_count / exportable_count
            else:
                result["export_rate"] = 0.0
            
            # Export backlog
            result["export_backlog"] = enriched_count
            
            # Export success/failure cannot be directly measured from storage
            # In a real implementation, you would get these from the export pipeline
            # For now, we'll use placeholder values
            result["export_success_rate"] = 0.95  # Placeholder
            result["export_error_rate"] = 0.05    # Placeholder
            
            # Get export pipeline metrics from recent metrics history
            recent_metrics = self.metrics_db.get_metrics(
                metric_type=MetricType.COMPONENT,
                metric_name="leads_exported",
                component="orchestrator",
                limit=10
            )
            
            if len(recent_metrics) >= 2:
                oldest_value = recent_metrics[-1].get('value', 0)
                newest_value = recent_metrics[0].get('value', 0)
                time_diff = (datetime.datetime.fromisoformat(recent_metrics[0].get('timestamp')) - 
                           datetime.datetime.fromisoformat(recent_metrics[-1].get('timestamp')))
                
                # Calculate export rate per hour
                hours = time_diff.total_seconds() / 3600
                if hours > 0:
                    export_rate_per_hour = (newest_value - oldest_value) / hours
                    result["export_rate_per_hour"] = export_rate_per_hour
            
            return result
            
        except Exception as e:
            logger.error(f"Error monitoring export pipeline: {str(e)}")
            return result
    
    def track_lead_quality(self) -> Dict[str, Any]:
        """
        Analyze lead quality trends.
        
        Returns:
            Dict: Lead quality metrics
        """
        logger.debug("Tracking lead quality")
        result = {}
        
        try:
            # Get lead counts by status
            lead_counts = self.storage.count_leads_by_status()
            
            # Get market sector distribution
            sector_counts = self.storage.count_leads_by_market_sector()
            
            # Calculate overall quality metrics
            total_leads = sum(lead_counts.values())
            if total_leads > 0:
                # Quality ratio based on progression through pipeline
                validated_count = lead_counts.get("validated", 0)
                enriched_count = lead_counts.get("enriched", 0)
                exported_count = lead_counts.get("exported", 0)
                rejected_count = lead_counts.get("rejected", 0)
                
                # Calculate quality score
                processed_count = validated_count + enriched_count + exported_count + rejected_count
                if processed_count > 0:
                    quality_score = (validated_count + enriched_count + exported_count) / processed_count
                    result["overall_quality_score"] = quality_score
                
                # Calculate lead status distribution
                for status, count in lead_counts.items():
                    result[f"status_ratio_{status}"] = count / total_leads
                
                # Calculate sector distribution
                for sector, count in sector_counts.items():
                    if sector:  # Skip None/unknown sectors
                        result[f"sector_ratio_{sector}"] = count / total_leads
            
            # In a real implementation, you would include more quality metrics:
            # - Lead value distribution
            # - Confidence score distribution
            # - Geographic distribution
            # - Lead age distribution
            
            return result
            
        except Exception as e:
            logger.error(f"Error tracking lead quality: {str(e)}")
            return result
    
    def detect_anomalies(self) -> List[str]:
        """
        Identify potential issues using anomaly detection.
        
        Returns:
            List[str]: Detected issues
        """
        logger.debug("Detecting anomalies")
        issues = []
        
        try:
            # Get recent system metrics
            cpu_metrics = self.metrics_db.get_metrics(
                metric_type=MetricType.SYSTEM,
                metric_name="cpu_usage_percent",
                limit=DEFAULT_ANOMALY_DETECTION_WINDOW
            )
            
            memory_metrics = self.metrics_db.get_metrics(
                metric_type=MetricType.SYSTEM,
                metric_name="memory_usage_percent",
                limit=DEFAULT_ANOMALY_DETECTION_WINDOW
            )
            
            disk_metrics = self.metrics_db.get_metrics(
                metric_type=MetricType.SYSTEM,
                metric_name="disk_usage_percent",
                limit=DEFAULT_ANOMALY_DETECTION_WINDOW
            )
            
            # Check CPU usage
            if cpu_metrics and cpu_metrics[0].get('value', 0) > self.alert_config['thresholds']['cpu_usage']:
                issues.append(f"High CPU usage: {cpu_metrics[0].get('value')}%")
                
                # Create alert
                self._create_alert(
                    level=AlertLevel.WARNING if cpu_metrics[0].get('value', 0) < 90 else AlertLevel.ERROR,
                    message=f"High CPU usage detected: {cpu_metrics[0].get('value')}%",
                    component="system",
                    metric="cpu_usage_percent",
                    value=cpu_metrics[0].get('value'),
                    threshold=self.alert_config['thresholds']['cpu_usage']
                )
            
            # Check memory usage
            if memory_metrics and memory_metrics[0].get('value', 0) > self.alert_config['thresholds']['memory_usage']:
                issues.append(f"High memory usage: {memory_metrics[0].get('value')}%")
                
                # Create alert
                self._create_alert(
                    level=AlertLevel.WARNING if memory_metrics[0].get('value', 0) < 95 else AlertLevel.ERROR,
                    message=f"High memory usage detected: {memory_metrics[0].get('value')}%",
                    component="system",
                    metric="memory_usage_percent",
                    value=memory_metrics[0].get('value'),
                    threshold=self.alert_config['thresholds']['memory_usage']
                )
            
            # Check disk usage
            if disk_metrics and disk_metrics[0].get('value', 0) > self.alert_config['thresholds']['disk_usage']:
                issues.append(f"High disk usage: {disk_metrics[0].get('value')}%")
                
                # Create alert
                self._create_alert(
                    level=AlertLevel.WARNING if disk_metrics[0].get('value', 0) < 95 else AlertLevel.ERROR,
                    message=f"High disk usage detected: {disk_metrics[0].get('value')}%",
                    component="system",
                    metric="disk_usage_percent",
                    value=disk_metrics[0].get('value'),
                    threshold=self.alert_config['thresholds']['disk_usage']
                )
            
            # Check source health
            source_metrics = self.monitor_data_sources()
            for source_id, metrics in source_metrics.items():
                # Check error rate
                error_rate = 1.0 - metrics.get("success_rate", 1.0)
                if error_rate > self.alert_config['thresholds']['source_error_rate']:
                    source_name = metrics.get('source_name', source_id)
                    issues.append(f"High error rate for source {source_name}: {error_rate:.2f}")
                    
                    # Create alert
                    self._create_alert(
                        level=AlertLevel.WARNING if error_rate < 0.5 else AlertLevel.ERROR,
                        message=f"High error rate for source {source_name}: {error_rate:.2f}",
                        component="data_sources",
                        metric="error_rate",
                        value=error_rate,
                        threshold=self.alert_config['thresholds']['source_error_rate'],
                        context={"source_id": source_id}
                    )
                
                # Check consecutive errors
                consecutive_errors = metrics.get("consecutive_errors", 0)
                if consecutive_errors >= 3:
                    source_name = metrics.get('source_name', source_id)
                    issues.append(f"Source {source_name} has {consecutive_errors} consecutive errors")
                    
                    # Create alert
                    self._create_alert(
                        level=AlertLevel.ERROR,
                        message=f"Source {source_name} has {consecutive_errors} consecutive errors",
                        component="data_sources",
                        metric="consecutive_errors",
                        value=consecutive_errors,
                        threshold=3,
                        context={"source_id": source_id}
                    )
            
            # Check export pipeline
            export_metrics = self.monitor_export_pipeline()
            export_error_rate = export_metrics.get("export_error_rate", 0)
            if export_error_rate > self.alert_config['thresholds']['export_error_rate']:
                issues.append(f"High export error rate: {export_error_rate:.2f}")
                
                # Create alert
                self._create_alert(
                    level=AlertLevel.WARNING if export_error_rate < 0.3 else AlertLevel.ERROR,
                    message=f"High export error rate: {export_error_rate:.2f}",
                    component="export_pipeline",
                    metric="export_error_rate",
                    value=export_error_rate,
                    threshold=self.alert_config['thresholds']['export_error_rate']
                )
            
            # Check processing pipeline
            pipeline_metrics = self.monitor_processing_pipeline()
            validation_rate = pipeline_metrics.get("validation_rate", 1.0)
            if validation_rate < self.alert_config['thresholds']['lead_validation_rate']:
                issues.append(f"Low lead validation rate: {validation_rate:.2f}")
                
                # Create alert
                self._create_alert(
                    level=AlertLevel.WARNING if validation_rate > 0.3 else AlertLevel.ERROR,
                    message=f"Low lead validation rate: {validation_rate:.2f}",
                    component="processing_pipeline",
                    metric="validation_rate",
                    value=validation_rate,
                    threshold=self.alert_config['thresholds']['lead_validation_rate']
                )
            
            # Advanced anomaly detection using statistical methods
            self._detect_statistical_anomalies(issues)
            
            return issues
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {str(e)}", exc_info=True)
            return issues
    
    def _detect_statistical_anomalies(self, issues: List[str]) -> None:
        """
        Perform statistical anomaly detection on metrics.
        
        Args:
            issues: List to append detected issues to
        """
        try:
            # Get key metrics for statistical analysis
            key_metrics = [
                ("system", "cpu_usage_percent"),
                ("system", "memory_usage_percent"),
                ("processing_pipeline", "validation_rate"),
                ("export_pipeline", "export_rate"),
                ("storage", "total_leads")
            ]
            
            for component, metric_name in key_metrics:
                # Get recent values
                metrics = self.metrics_db.get_metrics(
                    component=component,
                    metric_name=metric_name,
                    limit=DEFAULT_ANOMALY_DETECTION_WINDOW
                )
                
                if len(metrics) < 5:  # Need enough data for statistical analysis
                    continue
                
                values = [m.get('value') for m in metrics if m.get('value') is not None]
                if not values:
                    continue
                
                # Update metric history
                key = f"{component}_{metric_name}"
                self.metric_history[key].extend(values)
                
                # Only proceed if we have enough history
                if len(self.metric_history[key]) < 10:
                    continue
                
                # Calculate statistics
                mean = statistics.mean(self.metric_history[key])
                stdev = statistics.stdev(self.metric_history[key]) if len(self.metric_history[key]) > 1 else 0
                
                if stdev == 0:  # Avoid division by zero
                    continue
                
                # Get latest value
                latest_value = values[0]
                
                # Calculate z-score
                z_score = abs(latest_value - mean) / stdev
                
                # Check for anomaly (z-score > 3 indicates outlier)
                if z_score > 3:
                    direction = "high" if latest_value > mean else "low"
                    issue = f"Anomalous {direction} value for {component} {metric_name}: {latest_value:.2f} (z-score: {z_score:.2f})"
                    issues.append(issue)
                    
                    # Create alert
                    self._create_alert(
                        level=AlertLevel.WARNING,
                        message=issue,
                        component=component,
                        metric=metric_name,
                        value=latest_value,
                        context={"z_score": z_score, "mean": mean, "stdev": stdev}
                    )
        
        except Exception as e:
            logger.error(f"Error during statistical anomaly detection: {str(e)}")
    
    def _create_alert(self, 
                     level: AlertLevel,
                     message: str,
                     component: str,
                     metric: Optional[str] = None,
                     value: Optional[float] = None,
                     threshold: Optional[float] = None,
                     context: Optional[Dict[str, Any]] = None) -> Optional[Alert]:
        """
        Create and store an alert.
        
        Args:
            level: Alert severity level
            message: Alert message
            component: Component that generated the alert
            metric: Related metric name
            value: Current metric value
            threshold: Alert threshold value
            context: Additional context information
        
        Returns:
            Optional[Alert]: Created alert or None if throttled
        """
        # Check for alert cooldown
        cooldown_key = f"{component}_{metric}_{level}"
        if cooldown_key in self.alert_cooldowns:
            last_alert_time = self.alert_cooldowns[cooldown_key]
            if time.time() - last_alert_time < self.alert_cooldown:
                logger.debug(f"Alert throttled: {message}")
                return None
        
        # Create alert
        alert = Alert(
            level=level,
            message=message,
            component=component,
            metric=metric,
            value=value,
            threshold=threshold,
            context=context
        )
        
        # Store alert
        self.metrics_db.store_alert(alert)
        
        # Add to history
        self.alert_history.append(alert)
        
        # Update cooldown
        self.alert_cooldowns[cooldown_key] = time.time()
        
        # Log alert
        log_method = logger.info if level == AlertLevel.INFO else (
            logger.warning if level == AlertLevel.WARNING else logger.error
        )
        log_method(f"ALERT [{level}]: {message}")
        
        return alert
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """
        Create comprehensive system performance report.
        
        Returns:
            Dict: Performance report
        """
        logger.info("Generating performance report")
        report = {
            "timestamp": datetime.datetime.now().isoformat(),
            "system": {},
            "data_sources": {},
            "processing_pipeline": {},
            "export_pipeline": {},
            "lead_quality": {},
            "alerts": [],
            "recommendations": []
        }
        
        try:
            # System metrics
            system_stats = self._get_system_stats()
            report["system"] = system_stats
            
            # Data source metrics
            source_metrics = self.monitor_data_sources()
            report["data_sources"] = source_metrics
            
            # Processing pipeline metrics
            pipeline_metrics = self.monitor_processing_pipeline()
            report["processing_pipeline"] = pipeline_metrics
            
            # Export pipeline metrics
            export_metrics = self.monitor_export_pipeline()
            report["export_pipeline"] = export_metrics
            
            # Lead quality metrics
            lead_quality = self.track_lead_quality()
            report["lead_quality"] = lead_quality
            
            # Recent alerts
            recent_alerts = self.metrics_db.get_recent_alerts(hours=24)
            report["alerts"] = recent_alerts
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                system_stats, source_metrics, pipeline_metrics, export_metrics, lead_quality, recent_alerts
            )
            report["recommendations"] = recommendations
            
            # Store report in metrics database
            self.metrics_db.store_metric(
                metric_type=MetricType.CUSTOM,
                metric_name="performance_report",
                value=1.0,  # Placeholder value
                component="monitoring",
                metadata=report
            )
            
            # Log report summary
            logger.info(f"Performance report generated with {len(recommendations)} recommendations")
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating performance report: {str(e)}", exc_info=True)
            report["error"] = str(e)
            return report
    
    def _get_system_stats(self) -> Dict[str, Any]:
        """
        Get system statistics for the report.
        
        Returns:
            Dict: System statistics
        """
        stats = {
            "cpu": {
                "usage_percent": psutil.cpu_percent(interval=0.1),
                "cores": psutil.cpu_count(logical=True),
                "physical_cores": psutil.cpu_count(logical=False)
            },
            "memory": {
                "total_mb": psutil.virtual_memory().total / (1024 * 1024),
                "available_mb": psutil.virtual_memory().available / (1024 * 1024),
                "usage_percent": psutil.virtual_memory().percent
            },
            "disk": {
                "total_gb": psutil.disk_usage('/').total / (1024 * 1024 * 1024),
                "free_gb": psutil.disk_usage('/').free / (1024 * 1024 * 1024),
                "usage_percent": psutil.disk_usage('/').percent
            },
            "network": {
                "hostname": socket.gethostname(),
                "ip_address": socket.gethostbyname(socket.gethostname()),
                "bytes_sent": psutil.net_io_counters().bytes_sent,
                "bytes_recv": psutil.net_io_counters().bytes_recv
            },
            "process": {
                "pid": os.getpid(),
                "memory_mb": psutil.Process().memory_info().rss / (1024 * 1024),
                "cpu_percent": psutil.Process().cpu_percent(interval=0.1),
                "threads": psutil.Process().num_threads(),
                "open_files": len(psutil.Process().open_files()),
                "connections": len(psutil.Process().connections())
            },
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "python_version": platform.python_version()
            },
            "uptime": {
                "system_seconds": time.time() - psutil.boot_time(),
                "process_seconds": time.time() - psutil.Process().create_time()
            }
        }
        
        return stats
    
    def _generate_recommendations(self,
                                 system_stats: Dict[str, Any],
                                 source_metrics: Dict[str, Dict[str, Any]],
                                 pipeline_metrics: Dict[str, Any],
                                 export_metrics: Dict[str, Any],
                                 lead_quality: Dict[str, Any],
                                 alerts: List[Dict[str, Any]]) -> List[str]:
        """
        Generate recommendations based on performance metrics.
        
        Args:
            system_stats: System statistics
            source_metrics: Data source metrics
            pipeline_metrics: Processing pipeline metrics
            export_metrics: Export pipeline metrics
            lead_quality: Lead quality metrics
            alerts: Recent alerts
        
        Returns:
            List[str]: Recommendations
        """
        recommendations = []
        
        # System recommendations
        if system_stats.get('cpu', {}).get('usage_percent', 0) > 70:
            recommendations.append("Consider scaling up CPU resources or optimizing resource usage")
        
        if system_stats.get('memory', {}).get('usage_percent', 0) > 70:
            recommendations.append("Consider increasing available memory or optimizing memory usage")
        
        if system_stats.get('disk', {}).get('usage_percent', 0) > 70:
            recommendations.append("Consider increasing disk space or cleaning up unnecessary files")
        
        # Source recommendations
        problematic_sources = []
        for source_id, metrics in source_metrics.items():
            if metrics.get('success_rate', 1.0) < 0.7:
                problematic_sources.append(source_id)
        
        if problematic_sources:
            recommendations.append(f"Review {len(problematic_sources)} problematic data sources with low success rates")
        
        # Pipeline recommendations
        if pipeline_metrics.get('validation_rate', 1.0) < 0.7:
            recommendations.append("Review lead validation logic - current validation rate is below target")
        
        if pipeline_metrics.get('enrichment_rate', 1.0) < 0.7:
            recommendations.append("Investigate enrichment pipeline performance - current enrichment rate is below target")
        
        # Export recommendations
        if export_metrics.get('export_rate', 1.0) < 0.7:
            recommendations.append("Review export pipeline performance - current export rate is below target")
        
        if export_metrics.get('export_backlog', 0) > 100:
            recommendations.append(f"Clear export backlog of {export_metrics.get('export_backlog')} leads")
        
        # Alert-based recommendations
        error_alerts = [a for a in alerts if a.get('level') == 'error' or a.get('level') == 'critical']
        if len(error_alerts) > 10:
            recommendations.append(f"Address {len(error_alerts)} error-level alerts in the system")
        
        # Lead quality recommendations
        if lead_quality.get('overall_quality_score', 1.0) < 0.7:
            recommendations.append("Review lead quality metrics and improve source targeting")
        
        return recommendations
    
    def alert_on_critical_issues(self, issues: List[str]) -> bool:
        """
        Trigger notifications for critical issues.
        
        Args:
            issues: List of detected issues
        
        Returns:
            bool: True if alerts were sent successfully
        """
        if not issues:
            return True
        
        logger.info(f"Alerting on {len(issues)} issues")
        
        critical_issues = []
        warning_issues = []
        
        # Categorize issues by severity
        for issue in issues:
            if "critical" in issue.lower() or "error" in issue.lower() or "high" in issue.lower():
                critical_issues.append(issue)
            else:
                warning_issues.append(issue)
        
        # Only alert on critical issues unless there are too many warnings
        issues_to_alert = critical_issues
        if len(warning_issues) > 5:
            issues_to_alert.append(f"There are {len(warning_issues)} warning issues")
        
        if not issues_to_alert:
            return True
        
        # Trigger email alerts if configured
        email_sent = False
        if self.alert_config["email"]["enabled"] and self.alert_config["email"]["smtp_server"]:
            email_sent = self._send_email_alert(issues_to_alert)
        
        # Trigger webhook alerts if configured
        webhook_sent = False
        if self.alert_config["webhook"]["enabled"] and self.alert_config["webhook"]["url"]:
            webhook_sent = self._send_webhook_alert(issues_to_alert)
        
        return email_sent or webhook_sent
    
    def _send_email_alert(self, issues: List[str]) -> bool:
        """
        Send email alert.
        
        Args:
            issues: List of issues to report
        
        Returns:
            bool: True if email was sent successfully
        """
        try:
            # Prepare email
            msg = MIMEMultipart()
            msg["From"] = self.alert_config["email"]["from_address"]
            msg["To"] = ", ".join(self.alert_config["email"]["to_addresses"])
            msg["Subject"] = f"ALERT: Perera Lead Scraper - {len(issues)} Issues Detected"
            
            # Create email body
            body = f"The following issues were detected at {datetime.datetime.now().isoformat()}:\n\n"
            for i, issue in enumerate(issues, 1):
                body += f"{i}. {issue}\n"
            
            body += "\n\nPlease check the system monitor for more details."
            
            msg.attach(MIMEText(body, "plain"))
            
            # Connect to SMTP server
            smtp_server = self.alert_config["email"]["smtp_server"]
            smtp_port = self.alert_config["email"]["smtp_port"]
            smtp_user = self.alert_config["email"]["smtp_username"]
            smtp_pass = self.alert_config["email"]["smtp_password"]
            use_tls = self.alert_config["email"]["use_tls"]
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                if use_tls:
                    server.starttls()
                
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                
                server.send_message(msg)
            
            logger.info(f"Email alert sent to {len(self.alert_config['email']['to_addresses'])} recipients")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email alert: {str(e)}", exc_info=True)
            return False
    
    def _send_webhook_alert(self, issues: List[str]) -> bool:
        """
        Send webhook alert.
        
        Args:
            issues: List of issues to report
        
        Returns:
            bool: True if webhook request was successful
        """
        try:
            # Prepare payload
            payload = {
                "timestamp": datetime.datetime.now().isoformat(),
                "system": "Perera Lead Scraper",
                "alert_count": len(issues),
                "issues": issues,
                "hostname": socket.gethostname()
            }
            
            # Send webhook request
            webhook_url = self.alert_config["webhook"]["url"]
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            # Check response
            if response.status_code < 400:
                logger.info(f"Webhook alert sent successfully: {response.status_code}")
                return True
            else:
                logger.error(f"Webhook alert failed: {response.status_code} - {response.text}")
                return False
            
        except Exception as e:
            logger.error(f"Error sending webhook alert: {str(e)}", exc_info=True)
            return False
    
    def log_system_status(self) -> None:
        """Record current system state."""
        try:
            # Get system status
            status = {
                "timestamp": datetime.datetime.now().isoformat(),
                "cpu_usage": psutil.cpu_percent(interval=0.1),
                "memory_usage": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/').percent,
                "thread_count": threading.active_count(),
                "monitoring_active": self.is_running
            }
            
            # Log system status
            logger.debug(f"System status: CPU {status['cpu_usage']}%, Mem {status['memory_usage']}%, Disk {status['disk_usage']}%")
            
            # Store in metrics database
            self.metrics_db.store_metric(
                metric_type=MetricType.SYSTEM,
                metric_name="system_status",
                value=1.0,  # Placeholder value
                component="monitoring",
                metadata=status
            )
            
        except Exception as e:
            logger.error(f"Error logging system status: {str(e)}")


# Simple CLI for testing
def main():
    """CLI entry point for system monitoring."""
    import argparse
    
    # Parse arguments
    parser = argparse.ArgumentParser(description="System Monitoring Tool")
    parser.add_argument("--db-path", help="Path to metrics database")
    parser.add_argument("--report", action="store_true", help="Generate performance report and exit")
    args = parser.parse_args()
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create monitor
    monitor = SystemMonitor(metrics_db_path=args.db_path)
    
    # Generate report if requested
    if args.report:
        report = monitor.generate_performance_report()
        print(json.dumps(report, indent=2))
        return
    
    # Start monitoring
    try:
        monitor.start_monitoring()
        
        # Keep running until interrupted
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
    finally:
        monitor.stop_monitoring()


if __name__ == "__main__":
    main()
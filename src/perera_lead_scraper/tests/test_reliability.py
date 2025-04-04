#!/usr/bin/env python3
"""
Reliability testing module for the Perera Construction Lead Scraper.

This module provides a framework for conducting long-running reliability tests,
simulating failures, measuring recovery times, and evaluating system performance
under various conditions.
"""

import unittest
import pytest
import time
import random
import threading
import logging
import json
import csv
import os
import sys
import signal
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Set, Any
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field

# Add parent directory to sys.path to import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import project modules
from perera_lead_scraper.orchestrator import LeadGenerationOrchestrator
from perera_lead_scraper.storage import LeadStorage
from perera_lead_scraper.sources import BaseDataSource
from perera_lead_scraper.export import ExportManager
from perera_lead_scraper.config import config
from perera_lead_scraper.monitoring.monitoring import SystemMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('reliability_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ReliabilityTest")

# Constants
TEST_DURATION_HOURS = 24
CHECK_INTERVAL_SECONDS = 300  # 5 minutes
FAILURE_PROBABILITY = 0.1  # 10% chance of failure during each check interval
MAX_CONCURRENT_RUNS = 5
DATA_SAMPLE_SIZE = 100  # Number of leads to sample for data integrity checks
RESOURCE_LIMIT_CPU_PERCENT = 80
RESOURCE_LIMIT_MEMORY_PERCENT = 80
RESOURCE_LIMIT_DISK_PERCENT = 90

# Failure types
FAILURE_TYPES = [
    "network_failure",
    "data_source_failure",
    "database_failure",
    "export_failure",
    "resource_limit",
    "component_crash"
]


@dataclass
class TestMetric:
    """Class for storing individual test metrics."""
    timestamp: datetime
    metric_type: str
    value: float
    related_component: Optional[str] = None
    failure_type: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestState:
    """Class for tracking the state of a reliability test run."""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    is_running: bool = True
    metrics: List[TestMetric] = field(default_factory=list)
    failures_introduced: List[Dict[str, Any]] = field(default_factory=list)
    recovery_times: List[Dict[str, Any]] = field(default_factory=list)
    data_integrity_checks: List[Dict[str, Any]] = field(default_factory=list)
    concurrent_operations: List[Dict[str, Any]] = field(default_factory=list)
    resource_usage: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_metric(self, metric_type: str, value: float, 
                  related_component: Optional[str] = None,
                  failure_type: Optional[str] = None, 
                  details: Optional[Dict[str, Any]] = None) -> None:
        """Add a new metric to the test state."""
        self.metrics.append(TestMetric(
            timestamp=datetime.now(),
            metric_type=metric_type,
            value=value,
            related_component=related_component,
            failure_type=failure_type,
            details=details or {}
        ))
    
    def record_failure(self, failure_type: str, component: str, 
                     details: Optional[Dict[str, Any]] = None) -> None:
        """Record a simulated failure."""
        failure_record = {
            "timestamp": datetime.now(),
            "failure_type": failure_type,
            "component": component,
            "details": details or {}
        }
        self.failures_introduced.append(failure_record)
        logger.info(f"Failure introduced: {failure_type} in {component}")
    
    def record_recovery(self, failure_type: str, component: str, 
                      recovery_time_seconds: float,
                      details: Optional[Dict[str, Any]] = None) -> None:
        """Record a system recovery from failure."""
        recovery_record = {
            "timestamp": datetime.now(),
            "failure_type": failure_type,
            "component": component,
            "recovery_time_seconds": recovery_time_seconds,
            "details": details or {}
        }
        self.recovery_times.append(recovery_record)
        self.add_metric("recovery_time", recovery_time_seconds, 
                       related_component=component, failure_type=failure_type)
        logger.info(f"System recovered from {failure_type} in {component} "
                   f"after {recovery_time_seconds:.2f} seconds")
    
    def record_data_integrity(self, check_result: bool, sample_size: int,
                             error_count: int, 
                             details: Optional[Dict[str, Any]] = None) -> None:
        """Record results of a data integrity check."""
        integrity_record = {
            "timestamp": datetime.now(),
            "passed": check_result,
            "sample_size": sample_size,
            "error_count": error_count,
            "error_rate": error_count / sample_size if sample_size > 0 else 0,
            "details": details or {}
        }
        self.data_integrity_checks.append(integrity_record)
        logger.info(f"Data integrity check: {'PASSED' if check_result else 'FAILED'} "
                   f"with {error_count}/{sample_size} errors")
    
    def record_concurrent_operation(self, operation_count: int, success_count: int,
                                  avg_response_time: float,
                                  details: Optional[Dict[str, Any]] = None) -> None:
        """Record results of concurrent operations test."""
        concurrency_record = {
            "timestamp": datetime.now(),
            "operation_count": operation_count,
            "success_count": success_count,
            "success_rate": success_count / operation_count if operation_count > 0 else 0,
            "avg_response_time": avg_response_time,
            "details": details or {}
        }
        self.concurrent_operations.append(concurrency_record)
        logger.info(f"Concurrent operations test: {success_count}/{operation_count} "
                   f"successful, avg response time: {avg_response_time:.2f}s")
    
    def record_resource_usage(self, cpu_percent: float, memory_percent: float,
                           disk_percent: float, network_tx_bytes: int, 
                           network_rx_bytes: int) -> None:
        """Record system resource usage."""
        resource_record = {
            "timestamp": datetime.now(),
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "disk_percent": disk_percent,
            "network_tx_bytes": network_tx_bytes,
            "network_rx_bytes": network_rx_bytes
        }
        self.resource_usage.append(resource_record)
        self.add_metric("cpu_usage", cpu_percent)
        self.add_metric("memory_usage", memory_percent)
        self.add_metric("disk_usage", disk_percent)
    
    def finish(self) -> None:
        """Mark the test as finished and record the end time."""
        self.is_running = False
        self.end_time = datetime.now()
    
    def generate_report(self, output_path: str = "reliability_report") -> str:
        """Generate a comprehensive reliability test report."""
        if not self.end_time:
            self.end_time = datetime.now()
        
        # Create output directory if it doesn't exist
        os.makedirs(output_path, exist_ok=True)
        
        # Calculate test duration
        duration = (self.end_time - self.start_time).total_seconds()
        duration_hours = duration / 3600
        
        # Calculate summary statistics
        total_failures = len(self.failures_introduced)
        avg_recovery_time = (sum(r["recovery_time_seconds"] for r in self.recovery_times) / 
                          len(self.recovery_times) if self.recovery_times else 0)
        
        data_integrity_success_rate = (
            sum(1 for check in self.data_integrity_checks if check["passed"]) / 
            len(self.data_integrity_checks) if self.data_integrity_checks else 0
        )
        
        concurrency_success_rate = (
            sum(op["success_rate"] for op in self.concurrent_operations) / 
            len(self.concurrent_operations) if self.concurrent_operations else 0
        )
        
        avg_cpu = (sum(r["cpu_percent"] for r in self.resource_usage) / 
                len(self.resource_usage) if self.resource_usage else 0)
        
        avg_memory = (sum(r["memory_percent"] for r in self.resource_usage) / 
                   len(self.resource_usage) if self.resource_usage else 0)
        
        # Create summary report
        report = {
            "test_summary": {
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "duration_hours": duration_hours,
                "total_failures_introduced": total_failures,
                "failures_per_hour": total_failures / duration_hours if duration_hours > 0 else 0,
                "average_recovery_time_seconds": avg_recovery_time,
                "data_integrity_success_rate": data_integrity_success_rate,
                "concurrency_success_rate": concurrency_success_rate,
                "average_cpu_usage": avg_cpu,
                "average_memory_usage": avg_memory
            },
            "failure_summary": {
                failure_type: len([f for f in self.failures_introduced 
                                if f["failure_type"] == failure_type])
                for failure_type in FAILURE_TYPES
            },
            "recovery_time_by_failure": {
                failure_type: {
                    "count": len([r for r in self.recovery_times 
                               if r["failure_type"] == failure_type]),
                    "avg_seconds": (
                        sum(r["recovery_time_seconds"] for r in self.recovery_times 
                          if r["failure_type"] == failure_type) / 
                        len([r for r in self.recovery_times 
                           if r["failure_type"] == failure_type])
                        if len([r for r in self.recovery_times 
                             if r["failure_type"] == failure_type]) > 0 else 0
                    )
                }
                for failure_type in FAILURE_TYPES
            }
        }
        
        # Write summary report to JSON
        report_path = os.path.join(output_path, "summary_report.json")
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Write detailed metrics to CSV
        metrics_path = os.path.join(output_path, "metrics.csv")
        with open(metrics_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "metric_type", "value", 
                           "component", "failure_type"])
            for metric in self.metrics:
                writer.writerow([
                    metric.timestamp.isoformat(),
                    metric.metric_type,
                    metric.value,
                    metric.related_component or "",
                    metric.failure_type or ""
                ])
        
        # Create summary text report
        summary_text = f"""
Reliability Test Report
======================
Test Duration: {duration_hours:.2f} hours
Start Time: {self.start_time.isoformat()}
End Time: {self.end_time.isoformat()}

System Reliability Metrics
-------------------------
Total Failures Introduced: {total_failures}
Failures Per Hour: {total_failures / duration_hours if duration_hours > 0 else 0:.2f}
Average Recovery Time: {avg_recovery_time:.2f} seconds
Data Integrity Success Rate: {data_integrity_success_rate * 100:.2f}%
Concurrency Success Rate: {concurrency_success_rate * 100:.2f}%

Resource Usage
-------------
Average CPU Usage: {avg_cpu:.2f}%
Average Memory Usage: {avg_memory:.2f}%

Recovery Time by Failure Type
---------------------------
{chr(10).join(f"{failure_type}: {report['recovery_time_by_failure'][failure_type]['avg_seconds']:.2f}s" 
             for failure_type in FAILURE_TYPES 
             if report['recovery_time_by_failure'][failure_type]['count'] > 0)}

Detailed reports and metrics available in: {output_path}
"""
        
        # Write summary text report
        summary_path = os.path.join(output_path, "summary_report.txt")
        with open(summary_path, 'w') as f:
            f.write(summary_text)
        
        logger.info(f"Reliability test report generated at {output_path}")
        return summary_path


class ReliabilityTester:
    """
    Class for conducting reliability tests on the Lead Generation system.
    """
    
    def __init__(self, test_duration_hours: int = TEST_DURATION_HOURS):
        """Initialize the reliability tester."""
        self.test_duration_hours = test_duration_hours
        self.state = TestState()
        self.orchestrator = LeadGenerationOrchestrator()
        self.storage = LeadStorage()
        self.monitor = SystemMonitor()
        self.export_manager = ExportManager()
        
        # Store original implementations for restoring after simulated failures
        self._original_methods = {}
        self._failure_locks = {failure_type: threading.Lock() 
                            for failure_type in FAILURE_TYPES}
        self._active_failures = set()
        
        # Thread control
        self._stop_event = threading.Event()
        self._background_threads = []
    
    def run_test(self) -> TestState:
        """Run the complete reliability test suite."""
        logger.info(f"Starting reliability test for {self.test_duration_hours} hours")
        
        # Set test end time
        end_time = datetime.now() + timedelta(hours=self.test_duration_hours)
        
        try:
            # Start background monitoring thread
            self._start_background_monitoring()
            
            # Main test loop
            while datetime.now() < end_time and not self._stop_event.is_set():
                # Run a test cycle
                self._run_test_cycle()
                
                # Check if we should introduce a failure
                if random.random() < FAILURE_PROBABILITY:
                    self._introduce_random_failure()
                
                # Sleep until next check interval
                time.sleep(CHECK_INTERVAL_SECONDS)
            
        except KeyboardInterrupt:
            logger.info("Test interrupted by user")
        except Exception as e:
            logger.error(f"Test encountered an unexpected error: {str(e)}", 
                        exc_info=True)
        finally:
            # Cleanup and generate report
            self._cleanup()
            self.state.finish()
            report_path = self.state.generate_report()
            logger.info(f"Test completed. Report available at: {report_path}")
        
        return self.state
    
    def _start_background_monitoring(self) -> None:
        """Start background threads for monitoring system state."""
        # Resource monitoring thread
        resource_thread = threading.Thread(
            target=self._monitor_resources,
            daemon=True
        )
        resource_thread.start()
        self._background_threads.append(resource_thread)
        
        # Recovery monitoring thread  
        recovery_thread = threading.Thread(
            target=self._monitor_failures,
            daemon=True
        )
        recovery_thread.start()
        self._background_threads.append(recovery_thread)
    
    def _run_test_cycle(self) -> None:
        """Run a single test cycle with all test types."""
        logger.info("Running test cycle")
        
        # Test data integrity
        self._test_data_integrity()
        
        # Test concurrency
        self._test_concurrency()
        
        # Collect metrics from system monitor
        self._collect_system_metrics()
    
    def _introduce_random_failure(self) -> None:
        """Introduce a random failure into the system."""
        # Don't introduce a new failure if too many active failures
        if len(self._active_failures) >= 2:
            return
        
        # Choose a random failure type that's not already active
        available_failures = [f for f in FAILURE_TYPES 
                             if f not in self._active_failures]
        if not available_failures:
            return
        
        failure_type = random.choice(available_failures)
        
        # Introduce the selected failure
        with self._failure_locks[failure_type]:
            if failure_type in self._active_failures:
                return
            
            getattr(self, f"_simulate_{failure_type}")()
            self._active_failures.add(failure_type)
    
    def _simulate_network_failure(self) -> None:
        """Simulate network connectivity issues."""
        def failed_request(*args, **kwargs):
            time.sleep(random.uniform(5, 15))  # Simulate timeout
            raise ConnectionError("Simulated network failure")
        
        # Find network-related methods in data sources and export manager
        for datasource in self.orchestrator.data_sources:
            if hasattr(datasource, 'fetch_data'):
                self._patch_method(datasource, 'fetch_data', failed_request)
        
        if hasattr(self.export_manager, 'export_leads'):
            self._patch_method(self.export_manager, 'export_leads', failed_request)
        
        self.state.record_failure("network_failure", "network", {
            "affected_components": ["data_sources", "export_manager"]
        })
    
    def _simulate_data_source_failure(self) -> None:
        """Simulate data source failures."""
        if not self.orchestrator.data_sources:
            return
        
        # Choose a random data source to fail
        datasource = random.choice(self.orchestrator.data_sources)
        source_name = datasource.__class__.__name__
        
        # Patch its fetch_data method to fail
        def failed_fetch(*args, **kwargs):
            raise Exception(f"Simulated {source_name} failure")
        
        self._patch_method(datasource, 'fetch_data', failed_fetch)
        
        self.state.record_failure("data_source_failure", source_name)
    
    def _simulate_database_failure(self) -> None:
        """Simulate database connectivity or corruption issues."""
        # Patch storage methods to simulate database failure
        def failed_storage_op(*args, **kwargs):
            time.sleep(random.uniform(0.5, 2))  # Simulate lag
            raise Exception("Simulated database failure")
        
        for method_name in ['store_lead', 'get_lead', 'update_lead', 
                          'get_all_leads', 'delete_lead']:
            if hasattr(self.storage, method_name):
                self._patch_method(self.storage, method_name, failed_storage_op)
        
        self.state.record_failure("database_failure", "storage")
    
    def _simulate_export_failure(self) -> None:
        """Simulate failures in the export process."""
        if not hasattr(self.export_manager, 'export_leads'):
            return
        
        def failed_export(*args, **kwargs):
            raise Exception("Simulated export failure")
        
        self._patch_method(self.export_manager, 'export_leads', failed_export)
        
        self.state.record_failure("export_failure", "export_manager")
    
    def _simulate_resource_limit(self) -> None:
        """Simulate system resource limitations."""
        # Create a resource-intensive operation
        def consume_resources():
            # Consume CPU
            end_time = time.time() + 30  # Run for 30 seconds
            while time.time() < end_time:
                _ = [i**2 for i in range(10000)]
                time.sleep(0.01)  # Allow other threads to run
        
        # Start resource-consuming threads
        threads = []
        for _ in range(4):  # Use 4 threads to consume resources
            t = threading.Thread(target=consume_resources)
            t.daemon = True
            t.start()
            threads.append(t)
        
        self.state.record_failure("resource_limit", "system", {
            "resource_type": "cpu",
            "threads": len(threads)
        })
    
    def _simulate_component_crash(self) -> None:
        """Simulate a component crash by disabling core functionality."""
        if not hasattr(self.orchestrator, 'generate_leads'):
            return
        
        def crashed_component(*args, **kwargs):
            raise RuntimeError("Simulated component crash")
        
        self._patch_method(self.orchestrator, 'generate_leads', crashed_component)
        
        self.state.record_failure("component_crash", "orchestrator")
    
    def _patch_method(self, obj: Any, method_name: str, 
                    replacement_func: callable) -> None:
        """
        Patch an object's method with a replacement function and store original.
        """
        if not hasattr(obj, method_name):
            return
        
        # Store original method if not already stored
        obj_id = id(obj)
        method_key = f"{obj_id}_{method_name}"
        
        if method_key not in self._original_methods:
            self._original_methods[method_key] = getattr(obj, method_name)
        
        # Replace with failure simulation
        setattr(obj, method_name, replacement_func)
    
    def _restore_method(self, obj: Any, method_name: str) -> bool:
        """Restore an object's original method if it was patched."""
        obj_id = id(obj)
        method_key = f"{obj_id}_{method_name}"
        
        if method_key in self._original_methods:
            setattr(obj, method_name, self._original_methods[method_key])
            return True
        return False
    
    def _monitor_failures(self) -> None:
        """
        Background thread to monitor active failures and restore functionality
        after a random time to simulate recovery.
        """
        while not self._stop_event.is_set():
            # Check all active failures
            for failure_type in list(self._active_failures):
                # 10% chance to recover from this failure on each check
                if random.random() < 0.1:
                    with self._failure_locks[failure_type]:
                        # Measure recovery time
                        start_time = time.time()
                        
                        # Call the specific recovery method
                        recovery_method = f"_recover_from_{failure_type}"
                        if hasattr(self, recovery_method):
                            getattr(self, recovery_method)()
                        
                        recovery_time = time.time() - start_time
                        
                        # Record the recovery
                        component = self._get_component_for_failure(failure_type)
                        self.state.record_recovery(
                            failure_type, component, recovery_time)
                        
                        # Remove from active failures
                        self._active_failures.remove(failure_type)
            
            # Check every few seconds
            time.sleep(5)
    
    def _recover_from_network_failure(self) -> None:
        """Recover from simulated network failure."""
        # Restore network-related methods
        for datasource in self.orchestrator.data_sources:
            self._restore_method(datasource, 'fetch_data')
        
        self._restore_method(self.export_manager, 'export_leads')
    
    def _recover_from_data_source_failure(self) -> None:
        """Recover from simulated data source failure."""
        for datasource in self.orchestrator.data_sources:
            self._restore_method(datasource, 'fetch_data')
    
    def _recover_from_database_failure(self) -> None:
        """Recover from simulated database failure."""
        for method_name in ['store_lead', 'get_lead', 'update_lead', 
                          'get_all_leads', 'delete_lead']:
            self._restore_method(self.storage, method_name)
    
    def _recover_from_export_failure(self) -> None:
        """Recover from simulated export failure."""
        self._restore_method(self.export_manager, 'export_leads')
    
    def _recover_from_resource_limit(self) -> None:
        """Recover from simulated resource limitations."""
        # Resource limitation is temporary, just wait for consuming threads to finish
        pass
    
    def _recover_from_component_crash(self) -> None:
        """Recover from simulated component crash."""
        self._restore_method(self.orchestrator, 'generate_leads')
    
    def _get_component_for_failure(self, failure_type: str) -> str:
        """Get the component name associated with a failure type."""
        component_map = {
            "network_failure": "network",
            "data_source_failure": "data_source",
            "database_failure": "database",
            "export_failure": "export_manager",
            "resource_limit": "system_resources",
            "component_crash": "orchestrator"
        }
        return component_map.get(failure_type, "unknown")
    
    def _test_data_integrity(self) -> None:
        """Test data integrity during/after failures."""
        try:
            # Get a sample of leads
            leads = self.storage.get_all_leads()
            if not leads:
                return
            
            sample_size = min(len(leads), DATA_SAMPLE_SIZE)
            lead_sample = random.sample(leads, sample_size)
            
            # Validate each lead's integrity
            errors = 0
            error_details = []
            
            for lead in lead_sample:
                # Check for required fields
                missing_fields = []
                for field in ['name', 'email', 'phone', 'source', 'timestamp']:
                    if not hasattr(lead, field) or getattr(lead, field) is None:
                        missing_fields.append(field)
                
                # Check for data consistency
                consistency_errors = []
                if hasattr(lead, 'email') and lead.email:
                    if '@' not in lead.email:
                        consistency_errors.append('invalid_email')
                
                if hasattr(lead, 'phone') and lead.phone:
                    if not any(c.isdigit() for c in lead.phone):
                        consistency_errors.append('invalid_phone')
                
                # Record any errors found
                if missing_fields or consistency_errors:
                    errors += 1
                    error_details.append({
                        "lead_id": getattr(lead, 'id', 'unknown'),
                        "missing_fields": missing_fields,
                        "consistency_errors": consistency_errors
                    })
            
            # Record the integrity check results
            check_passed = errors == 0
            self.state.record_data_integrity(check_passed, sample_size, errors, {
                "error_details": error_details
            })
            
        except Exception as e:
            logger.error(f"Data integrity check failed: {str(e)}", exc_info=True)
            self.state.record_data_integrity(False, 0, 0, {
                "error": str(e)
            })
    
    def _test_concurrency(self) -> None:
        """Test system performance under concurrent operations."""
        try:
            # Define operations to run concurrently
            operations = [
                self._concurrent_lead_generation,
                self._concurrent_lead_retrieval,
                self._concurrent_lead_update,
                self._concurrent_lead_export
            ]
            
            # Randomly select operations and concurrency level
            num_operations = random.randint(2, len(operations))
            selected_operations = random.sample(operations, num_operations)
            concurrency_level = random.randint(2, MAX_CONCURRENT_RUNS)
            
            # Execute concurrent operations
            start_time = time.time()
            results = []
            
            with ThreadPoolExecutor(max_workers=concurrency_level) as executor:
                futures = []
                
                # Submit operations to the executor
                for _ in range(concurrency_level):
                    op = random.choice(selected_operations)
                    futures.append(executor.submit(op))
                
                # Collect results
                for future in futures:
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        results.append({"success": False, "error": str(e)})
            
            end_time = time.time()
            
            # Calculate metrics
            total_operations = len(results)
            successful_operations = sum(1 for r in results if r.get("success", False))
            avg_response_time = (end_time - start_time) / total_operations
            
            # Record results
            self.state.record_concurrent_operation(
                total_operations, successful_operations, avg_response_time, {
                    "concurrency_level": concurrency_level,
                    "operation_details": results
                }
            )
            
        except Exception as e:
            logger.error(f"Concurrency test failed: {str(e)}", exc_info=True)
            self.state.record_concurrent_operation(0, 0, 0, {
                "error": str(e)
            })
    
    def _concurrent_lead_generation(self) -> Dict[str, Any]:
        """Concurrent operation: Generate leads."""
        try:
            start_time = time.time()
            result = self.orchestrator.generate_leads(1)  # Generate a single lead
            end_time = time.time()
            
            return {
                "operation": "lead_generation",
                "success": True,
                "lead_count": len(result) if isinstance(result, list) else 1,
                "response_time": end_time - start_time
            }
        except Exception as e:
            return {
                "operation": "lead_generation",
                "success": False,
                "error": str(e)
            }
    
    def _concurrent_lead_retrieval(self) -> Dict[str, Any]:
        """Concurrent operation: Retrieve leads."""
        try:
            start_time = time.time()
            leads = self.storage.get_all_leads()
            end_time = time.time()
            
            return {
                "operation": "lead_retrieval",
                "success": True,
                "lead_count": len(leads) if leads else 0,
                "response_time": end_time - start_time
            }
        except Exception as e:
            return {
                "operation": "lead_retrieval",
                "success": False,
                "error": str(e)
            }
    
    def _concurrent_lead_update(self) -> Dict[str, Any]:
        """Concurrent operation: Update leads."""
        try:
            # Get a lead to update
            leads = self.storage.get_all_leads()
            if not leads:
                return {
                    "operation": "lead_update",
                    "success": False,
                    "error": "No leads available to update"
                }
            
            lead = random.choice(leads)
            
            # Update the lead
            start_time = time.time()
            lead.quality_score = random.uniform(0, 100)
            self.storage.update_lead(lead)
            end_time = time.time()
            
            return {
                "operation": "lead_update",
                "success": True,
                "lead_id": getattr(lead, 'id', 'unknown'),
                "response_time": end_time - start_time
            }
        except Exception as e:
            return {
                "operation": "lead_update",
                "success": False,
                "error": str(e)
            }
    
    def _concurrent_lead_export(self) -> Dict[str, Any]:
        """Concurrent operation: Export leads."""
        try:
            # Get leads to export
            leads = self.storage.get_all_leads()
            if not leads:
                return {
                    "operation": "lead_export",
                    "success": False,
                    "error": "No leads available to export"
                }
            
            # Select a random subset
            export_count = min(10, len(leads))
            export_leads = random.sample(leads, export_count)
            
            # Export the leads
            start_time = time.time()
            self.export_manager.export_leads(export_leads)
            end_time = time.time()
            
            return {
                "operation": "lead_export",
                "success": True,
                "lead_count": export_count,
                "response_time": end_time - start_time
            }
        except Exception as e:
            return {
                "operation": "lead_export",
                "success": False,
                "error": str(e)
            }
    
    def _monitor_resources(self) -> None:
        """
        Background thread to monitor system resource usage during the test.
        """
        while not self._stop_event.is_set():
            try:
                # Collect system resource metrics
                cpu_percent = psutil.cpu_percent(interval=1)
                memory_percent = psutil.virtual_memory().percent
                disk_percent = psutil.disk_usage('/').percent
                
                # Get network stats
                net_io = psutil.net_io_counters()
                net_tx = net_io.bytes_sent
                net_rx = net_io.bytes_recv
                
                # Record resource usage
                self.state.record_resource_usage(
                    cpu_percent, memory_percent, disk_percent, net_tx, net_rx)
                
            except Exception as e:
                logger.error(f"Resource monitoring error: {str(e)}")
            
            # Check every 30 seconds
            time.sleep(30)
    
    def _collect_system_metrics(self) -> None:
        """Collect metrics from the system monitor."""
        try:
            # Collect metrics from the monitoring system
            metrics = self.monitor.track_metrics()
            
            # Add metrics to test state
            for metric_name, value in metrics.items():
                self.state.add_metric(metric_name, value)
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {str(e)}")
    
    def _cleanup(self) -> None:
        """Clean up resources and stop background threads."""
        logger.info("Cleaning up resources")
        
        # Signal threads to stop
        self._stop_event.set()
        
        # Restore any patched methods
        for obj_method, original in self._original_methods.items():
            obj_id, method_name = obj_method.split('_', 1)
            
            # Find the object by its id in known objects
            for obj in [self.orchestrator, self.storage, self.export_manager] + \
                    self.orchestrator.data_sources:
                if id(obj) == int(obj_id) and hasattr(obj, method_name):
                    setattr(obj, method_name, original)
                    break
        
        # Wait for background threads to finish
        for thread in self._background_threads:
            if thread.is_alive():
                thread.join(timeout=1)


class TestReliability(unittest.TestCase):
    """
    Test suite for reliability testing of the Lead Generation system.
    Uses pytest for parametrization and fixtures.
    """
    
    @pytest.mark.reliability
    @pytest.mark.slow
    def test_short_reliability(self):
        """
        Run a short reliability test (1 hour) to validate system stability.
        """
        tester = ReliabilityTester(test_duration_hours=1)
        state = tester.run_test()
        
        # Assert basic reliability metrics
        failure_count = len(state.failures_introduced)
        recovery_count = len(state.recovery_times)
        
        self.assertEqual(recovery_count, failure_count, 
                        "Not all failures were recovered from")
        
        # Check data integrity
        integrity_checks = state.data_integrity_checks
        if integrity_checks:
            success_rate = sum(1 for check in integrity_checks if check["passed"]) / len(integrity_checks)
            self.assertGreaterEqual(success_rate, 0.9, 
                                  "Data integrity success rate below 90%")
    
    @pytest.mark.reliability
    @pytest.mark.slow
    def test_component_failures(self):
        """
        Test that each component can handle and recover from failures.
        """
        for failure_type in FAILURE_TYPES:
            with self.subTest(failure_type=failure_type):
                # Create a tester instance for each failure type
                tester = ReliabilityTester(test_duration_hours=0.1)  # 6 minutes
                
                # Manually introduce the specific failure
                getattr(tester, f"_simulate_{failure_type}")()
                tester._active_failures.add(failure_type)
                
                # Wait for recovery detection and handling
                time.sleep(60)
                
                # Manually trigger recovery
                recovery_method = f"_recover_from_{failure_type}"
                if hasattr(tester, recovery_method):
                    getattr(tester, recovery_method)()
                
                # Verify component functionality after recovery
                try:
                    # Test basic operations after recovery
                    if failure_type == "data_source_failure":
                        # Verify data source works after recovery
                        for source in tester.orchestrator.data_sources:
                            if hasattr(source, 'fetch_data'):
                                result = source.fetch_data()
                                self.assertIsNotNone(result)
                    
                    elif failure_type == "database_failure":
                        # Verify storage operations work after recovery
                        leads = tester.storage.get_all_leads()
                        self.assertIsNotNone(leads)
                    
                    elif failure_type == "export_failure":
                        # Verify export works after recovery
                        leads = tester.storage.get_all_leads()
                        if leads:
                            result = tester.export_manager.export_leads([leads[0]])
                            self.assertTrue(result)
                    
                    # Cleanup
                    tester._cleanup()
                
                except Exception as e:
                    self.fail(f"Failed to recover from {failure_type}: {str(e)}")
    
    @pytest.mark.reliability
    @pytest.mark.slow
    def test_concurrent_operations(self):
        """
        Test that the system handles concurrent operations correctly.
        """
        tester = ReliabilityTester(test_duration_hours=0.1)  # 6 minutes
        
        # Run concurrency test
        tester._test_concurrency()
        
        # Check results
        concurrent_ops = tester.state.concurrent_operations
        self.assertTrue(len(concurrent_ops) > 0, "No concurrent operations were recorded")
        
        # At least 80% of operations should succeed
        if concurrent_ops:
            total_ops = concurrent_ops[0]["operation_count"]
            success_ops = concurrent_ops[0]["success_count"]
            success_rate = success_ops / total_ops if total_ops > 0 else 0
            
            self.assertGreaterEqual(success_rate, 0.8, 
                                  "Concurrent operation success rate below 80%")
        
        # Cleanup
        tester._cleanup()
    
    @pytest.mark.reliability
    @pytest.mark.slow
    def test_data_integrity(self):
        """
        Test that the system maintains data integrity during stress.
        """
        tester = ReliabilityTester(test_duration_hours=0.1)  # 6 minutes
        
        # First introduce database failure
        tester._simulate_database_failure()
        tester._active_failures.add("database_failure")
        
        # Wait briefly
        time.sleep(30)
        
        # Recover from failure
        tester._recover_from_database_failure()
        
        # Now check data integrity
        tester._test_data_integrity()
        
        # Verify integrity check results
        integrity_checks = tester.state.data_integrity_checks
        self.assertTrue(len(integrity_checks) > 0, "No data integrity checks were recorded")
        
        # Check if any integrity checks passed
        if integrity_checks:
            passed = integrity_checks[-1]["passed"]
            # We should eventually pass the integrity check after recovery
            self.assertTrue(passed, "Data integrity check failed after recovery")
        
        # Cleanup
        tester._cleanup()


if __name__ == "__main__":
    # Run the reliability test directly when script is executed
    test_duration = float(sys.argv[1]) if len(sys.argv) > 1 else TEST_DURATION_HOURS
    
    print(f"Starting reliability test for {test_duration} hours")
    tester = ReliabilityTester(test_duration_hours=test_duration)
    state = tester.run_test()
    
    # Generate and print report path
    report_path = state.generate_report()
    print(f"Test completed. Report available at: {report_path}")
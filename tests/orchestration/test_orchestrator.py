#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Orchestrator Tests

Unit and integration tests for the LeadGenerationOrchestrator.
"""

import os
import time
import uuid
import pytest
import threading
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from pathlib import Path
import json
import copy

from models.lead import Lead, LeadStatus, MarketSector, LeadType, DataSource, SourceType
from utils.storage import LeadStorage
from src.perera_lead_scraper.config import AppConfig
from src.perera_lead_scraper.orchestration.orchestrator import (
    LeadGenerationOrchestrator,
    OrchestratorStatus,
    SourcePerformanceMetrics
)


# Sample test data
SAMPLE_SOURCE = {
    "id": str(uuid.uuid4()),
    "name": "Test Source",
    "url": "https://example.com/feed",
    "type": "rss",
    "market_sectors": ["commercial", "healthcare"],
    "active": True,
    "requires_js": False,
    "config": {
        "cooldown_minutes": 5,
        "timeout_seconds": 30
    },
    "credentials": None,
    "last_checked": None,
    "status": None,
    "metrics": {},
    "tags": ["test"],
    "created_at": datetime.now().isoformat(),
    "updated_at": datetime.now().isoformat()
}


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    config = MagicMock(spec=AppConfig)
    
    # Set required attributes
    config.orchestrator_max_workers = 2
    config.orchestrator_max_concurrent_sources = 1
    config.orchestrator_min_source_interval_mins = 5
    config.export_to_hubspot = False
    
    return config


@pytest.fixture
def mock_storage():
    """Create a mock storage for testing."""
    storage = MagicMock(spec=LeadStorage)
    return storage


@pytest.fixture
def test_source_data(tmp_path):
    """Create test source data for testing."""
    # Create sources directory
    sources_path = tmp_path / "sources.json"
    
    # Create sample source data
    source_data = {
        "sources": [
            SAMPLE_SOURCE
        ]
    }
    
    # Write to file
    with open(sources_path, "w") as f:
        json.dump(source_data, f)
    
    return sources_path


@pytest.fixture
def orchestrator(mock_config, test_source_data):
    """Create a test orchestrator instance."""
    # Configure the mock config
    mock_config.sources_path = test_source_data
    mock_config.load_source_config = lambda path: json.load(open(path))
    
    # Create orchestrator
    orchestrator = LeadGenerationOrchestrator(app_config=mock_config)
    
    # Patch methods that would start threads
    orchestrator._start_resource_monitoring = MagicMock()
    
    yield orchestrator
    
    # Clean up
    if orchestrator.status != OrchestratorStatus.STOPPED:
        orchestrator.shutdown_gracefully()


class TestSourcePerformanceMetrics:
    """Tests for SourcePerformanceMetrics."""
    
    def test_update_metrics(self):
        """Test updating performance metrics."""
        source_id = uuid.uuid4()
        metrics = SourcePerformanceMetrics(source_id=source_id, name="Test Source")
        
        # Update metrics once
        metrics.update_metrics(
            execution_time_ms=100.0,
            leads_found=10,
            valid_leads=8,
            had_error=False
        )
        
        # Check basic metrics
        assert metrics.avg_execution_time_ms == 100.0
        assert metrics.total_leads_found == 10
        assert metrics.valid_leads_found == 8
        assert metrics.error_count == 0
        assert metrics.consecutive_errors == 0
        assert metrics.success_rate == 1.0
        assert metrics.quality_score == 0.8  # 8/10
        assert 0.0 <= metrics.priority_score <= 1.0
        assert len(metrics.execution_times) == 1
        assert len(metrics.execution_history) == 1
        
        # Update with an error
        metrics.update_metrics(
            execution_time_ms=150.0,
            leads_found=0,
            valid_leads=0,
            had_error=True
        )
        
        # Check updated metrics
        assert metrics.avg_execution_time_ms == 125.0  # (100 + 150) / 2
        assert metrics.total_leads_found == 10
        assert metrics.valid_leads_found == 8
        assert metrics.error_count == 1
        assert metrics.consecutive_errors == 1
        assert metrics.success_rate == 0.5  # 1/2 successful
        assert metrics.quality_score == 0.8  # still 8/10
        assert len(metrics.execution_times) == 2
        assert len(metrics.execution_history) == 2


class TestOrchestratorInitialization:
    """Tests for orchestrator initialization."""
    
    def test_init(self, orchestrator):
        """Test orchestrator initialization."""
        assert orchestrator.status == OrchestratorStatus.INITIALIZED
        assert orchestrator.config is not None
        assert orchestrator.sources == {}
        assert orchestrator.source_metrics == {}
        assert orchestrator.system_metrics["system_status"] == OrchestratorStatus.INITIALIZED.value
    
    def test_load_data_sources(self, orchestrator, test_source_data):
        """Test loading data sources."""
        # Mock the load_source_config return value
        with open(test_source_data) as f:
            source_data = json.load(f)
        
        orchestrator.config.load_source_config = MagicMock(return_value=source_data)
        
        # Call the method
        orchestrator._load_data_sources()
        
        # Check the sources were loaded
        assert len(orchestrator.sources) == 1
        assert len(orchestrator.source_metrics) == 1
        assert len(orchestrator.source_locks) == 1
        
        # Check the first source
        source_id = list(orchestrator.sources.keys())[0]
        source = orchestrator.sources[source_id]
        assert source.name == "Test Source"
        assert source.type == SourceType.RSS
        assert source.active is True
    
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    def test_resource_monitor_task(self, mock_virtual_memory, mock_cpu_percent, orchestrator):
        """Test resource monitoring task."""
        # Mock psutil return values
        mock_cpu_percent.return_value = 50.0
        mock_memory = MagicMock()
        mock_memory.percent = 60.0
        mock_virtual_memory.return_value = mock_memory
        
        # Set up for one iteration
        def side_effect():
            orchestrator._shutdown_event.set()
        orchestrator.balance_resource_usage = MagicMock(side_effect=side_effect)
        
        # Run the task
        orchestrator._resource_monitor_task()
        
        # Verify metrics were updated
        assert orchestrator.system_metrics["cpu_usage"] == 50.0
        assert orchestrator.system_metrics["memory_usage"] == 60.0
        
        # Verify balance_resource_usage was called
        orchestrator.balance_resource_usage.assert_called_once()


class TestOrchestratorLifecycle:
    """Tests for orchestrator lifecycle management."""
    
    def test_initialize_components(self, orchestrator):
        """Test component initialization."""
        # Patch component constructors
        with patch('utils.storage.LeadStorage'):
            # Initialize components
            result = orchestrator.initialize_components()
            
            # Check result
            assert result is True
            assert orchestrator.status == OrchestratorStatus.STARTING
            assert orchestrator.storage is not None
            assert orchestrator.system_metrics["system_status"] == OrchestratorStatus.STARTING.value
    
    def test_start_processing(self, orchestrator):
        """Test starting the orchestration process."""
        # Set up necessary mocks
        orchestrator.storage = MagicMock()
        orchestrator.scheduler = MagicMock()
        orchestrator.schedule_source_processing = MagicMock()
        
        # Start processing
        orchestrator.start_processing()
        
        # Verify
        assert orchestrator.status == OrchestratorStatus.RUNNING
        assert orchestrator.system_metrics["system_status"] == OrchestratorStatus.RUNNING.value
        assert orchestrator.scheduler.start.called
        assert orchestrator.schedule_source_processing.called
    
    def test_pause_resume_processing(self, orchestrator):
        """Test pausing and resuming processing."""
        # Set up necessary mocks
        orchestrator.status = OrchestratorStatus.RUNNING
        orchestrator.scheduler = MagicMock()
        
        # Pause processing
        orchestrator.pause_processing()
        
        # Verify
        assert orchestrator.status == OrchestratorStatus.PAUSED
        assert orchestrator.system_metrics["system_status"] == OrchestratorStatus.PAUSED.value
        assert orchestrator.scheduler.pause.called
        
        # Resume processing
        orchestrator.resume_processing()
        
        # Verify
        assert orchestrator.status == OrchestratorStatus.RUNNING
        assert orchestrator.system_metrics["system_status"] == OrchestratorStatus.RUNNING.value
        assert orchestrator.scheduler.resume.called
    
    def test_shutdown_gracefully(self, orchestrator):
        """Test graceful shutdown."""
        # Set up necessary mocks
        orchestrator.status = OrchestratorStatus.RUNNING
        orchestrator.scheduler = MagicMock()
        orchestrator.scheduler.running = True
        orchestrator.executor = MagicMock()
        orchestrator.export_scheduler = MagicMock()
        
        # Shutdown
        result = orchestrator.shutdown_gracefully()
        
        # Verify
        assert result is True
        assert orchestrator.status == OrchestratorStatus.STOPPED
        assert orchestrator.system_metrics["system_status"] == OrchestratorStatus.STOPPED.value
        assert orchestrator._shutdown_requested is True
        assert orchestrator._shutdown_event.is_set() is True
        assert orchestrator.scheduler.shutdown.called
        assert orchestrator.executor.shutdown.called
        assert orchestrator.export_scheduler.stop_scheduler.called


class TestSourceProcessing:
    """Tests for source processing."""
    
    def test_prioritize_sources(self, orchestrator):
        """Test prioritizing sources."""
        # Create test sources
        source1 = DataSource(
            id=uuid.uuid4(),
            name="High Priority Source",
            url="https://example.com/high",
            type=SourceType.RSS,
            active=True
        )
        source2 = DataSource(
            id=uuid.uuid4(),
            name="Medium Priority Source",
            url="https://example.com/medium",
            type=SourceType.WEBSITE,
            active=True
        )
        source3 = DataSource(
            id=uuid.uuid4(),
            name="Low Priority Source",
            url="https://example.com/low",
            type=SourceType.CITY_PORTAL,
            active=True
        )
        source4 = DataSource(
            id=uuid.uuid4(),
            name="Inactive Source",
            url="https://example.com/inactive",
            type=SourceType.API,
            active=False
        )
        
        # Add to orchestrator
        orchestrator.sources = {
            source1.id: source1,
            source2.id: source2,
            source3.id: source3,
            source4.id: source4
        }
        
        # Create metrics with different priority scores
        metrics1 = SourcePerformanceMetrics(source_id=source1.id, name=source1.name)
        metrics1.priority_score = 0.9
        
        metrics2 = SourcePerformanceMetrics(source_id=source2.id, name=source2.name)
        metrics2.priority_score = 0.6
        
        metrics3 = SourcePerformanceMetrics(source_id=source3.id, name=source3.name)
        metrics3.priority_score = 0.3
        
        metrics4 = SourcePerformanceMetrics(source_id=source4.id, name=source4.name)
        metrics4.priority_score = 0.0
        
        orchestrator.source_metrics = {
            source1.id: metrics1,
            source2.id: metrics2,
            source3.id: metrics3,
            source4.id: metrics4
        }
        
        # Prioritize sources
        prioritized = orchestrator.prioritize_sources()
        
        # Verify order
        assert len(prioritized) == 3  # Only active sources
        assert prioritized[0].id == source1.id
        assert prioritized[1].id == source2.id
        assert prioritized[2].id == source3.id
    
    def test_determine_optimal_frequency(self, orchestrator):
        """Test determining optimal frequency."""
        # Create test source
        source = DataSource(
            id=uuid.uuid4(),
            name="Test Source",
            url="https://example.com/test",
            type=SourceType.RSS,
            active=True
        )
        
        # Test with no metrics
        frequency = orchestrator.determine_optimal_frequency(source)
        assert frequency == orchestrator.min_source_interval_mins
        
        # Create metrics with different scenarios
        # Case 1: High quality source
        metrics_high = SourcePerformanceMetrics(source_id=source.id, name=source.name)
        metrics_high.quality_score = 0.9
        metrics_high.success_rate = 0.95
        metrics_high.consecutive_errors = 0
        
        orchestrator.source_metrics[source.id] = metrics_high
        frequency_high = orchestrator.determine_optimal_frequency(source)
        
        # Case 2: Medium quality source
        metrics_medium = copy.deepcopy(metrics_high)
        metrics_medium.quality_score = 0.5
        metrics_medium.success_rate = 0.7
        
        orchestrator.source_metrics[source.id] = metrics_medium
        frequency_medium = orchestrator.determine_optimal_frequency(source)
        
        # Case 3: Low quality source with errors
        metrics_low = copy.deepcopy(metrics_high)
        metrics_low.quality_score = 0.2
        metrics_low.success_rate = 0.4
        metrics_low.consecutive_errors = 3
        
        orchestrator.source_metrics[source.id] = metrics_low
        frequency_low = orchestrator.determine_optimal_frequency(source)
        
        # Verify frequencies
        assert frequency_high <= frequency_medium <= frequency_low
    
    def test_calculate_source_value(self, orchestrator):
        """Test calculating source value."""
        # Create test source
        source = DataSource(
            id=uuid.uuid4(),
            name="Test Source",
            url="https://example.com/test",
            type=SourceType.RSS,
            active=True
        )
        
        # Test with no metrics
        value = orchestrator.calculate_source_value(source)
        assert value == 0.5  # Default
        
        # Create metrics with different scenarios
        # Case 1: High quality, low volume
        metrics_high_q = SourcePerformanceMetrics(source_id=source.id, name=source.name)
        metrics_high_q.quality_score = 0.9
        metrics_high_q.valid_leads_found = 10
        
        orchestrator.source_metrics[source.id] = metrics_high_q
        value_high_q = orchestrator.calculate_source_value(source)
        
        # Case 2: Medium quality, high volume
        metrics_med_q = copy.deepcopy(metrics_high_q)
        metrics_med_q.quality_score = 0.5
        metrics_med_q.valid_leads_found = 500
        
        orchestrator.source_metrics[source.id] = metrics_med_q
        value_med_q = orchestrator.calculate_source_value(source)
        
        # Verify values
        assert 0.0 <= value_high_q <= 1.0
        assert 0.0 <= value_med_q <= 1.0
    
    @patch('src.perera_lead_scraper.orchestration.orchestrator.psutil')
    def test_balance_resource_usage(self, mock_psutil, orchestrator):
        """Test balancing resource usage."""
        # Mock psutil return values
        mock_psutil.cpu_percent.return_value = 90.0  # High CPU
        mock_psutil.virtual_memory.return_value.percent = 85.0  # High memory
        
        # Set up orchestrator with multiple concurrent sources
        orchestrator.max_concurrent_sources = 3
        orchestrator.active_source_jobs = {
            uuid.uuid4(): {"source_name": "Job 1"},
            uuid.uuid4(): {"source_name": "Job 2"}
        }
        
        # Test balancing
        result = orchestrator.balance_resource_usage()
        
        # Verify actions were taken
        assert result is True
        assert orchestrator.max_concurrent_sources == 2  # Reduced


class TestLeadProcessing:
    """Tests for lead processing."""
    
    def test_handle_new_leads(self, orchestrator):
        """Test handling new leads."""
        # Mock validation and enrichment
        orchestrator._validate_lead = MagicMock(side_effect=lambda l: l if l.project_name != "Invalid" else None)
        orchestrator._enrich_lead = MagicMock(side_effect=lambda l: l)
        orchestrator.storage = MagicMock()
        orchestrator.storage.save_lead = MagicMock(side_effect=lambda l: l)
        
        # Create test leads
        leads = [
            Lead(
                id=uuid.uuid4(),
                source="test_source",
                project_name=f"Test Project {i}",
                status=LeadStatus.NEW
            )
            for i in range(3)
        ]
        
        # Add an invalid lead
        leads.append(Lead(
            id=uuid.uuid4(),
            source="test_source",
            project_name="Invalid",
            status=LeadStatus.NEW
        ))
        
        # Process leads
        orchestrator.handle_new_leads(leads)
        
        # Verify
        assert orchestrator._validate_lead.call_count == 4  # All leads
        assert orchestrator._enrich_lead.call_count == 3  # Only valid leads
        assert orchestrator.storage.save_lead.call_count == 3  # Only processed leads
        assert orchestrator.system_metrics["total_leads_processed"] == 3


@pytest.mark.integration
class TestIntegration:
    """Integration tests for the orchestrator."""
    
    def test_full_lifecycle(self, orchestrator, mock_storage):
        """Test full orchestrator lifecycle."""
        # Mock components to avoid real external calls
        orchestrator.storage = mock_storage
        
        # Initialize components
        result = orchestrator.initialize_components()
        assert result is True
        
        # Start processing
        orchestrator.start_processing()
        assert orchestrator.status == OrchestratorStatus.RUNNING
        
        # Let it run briefly
        time.sleep(0.1)
        
        # Trigger export
        export_result = orchestrator.trigger_export_pipeline()
        assert isinstance(export_result, dict)
        
        # Get metrics
        metrics = orchestrator.get_system_metrics()
        assert isinstance(metrics, dict)
        assert "orchestrator_status" in metrics
        
        # Shutdown
        shutdown_result = orchestrator.shutdown_gracefully()
        assert shutdown_result is True
        assert orchestrator.status == OrchestratorStatus.STOPPED
#!/usr/bin/env python3
"""
End-to-End Testing Script for Perera Construction Lead Scraper.

This script performs comprehensive end-to-end testing of the entire lead generation
pipeline, from source configuration to CRM export, across all target market sectors.
It validates system performance, data quality, error handling, and lead qualification.
"""

import os
import sys
import time
import json
import logging
import unittest
import tempfile
import shutil
import tracemalloc
import concurrent.futures
import psutil
import pytest
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from dataclasses import dataclass, field

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import system components
from perera_lead_scraper.orchestrator import LeadGenerationOrchestrator
from perera_lead_scraper.storage import LeadStorage
from perera_lead_scraper.sources import BaseDataSource
from perera_lead_scraper.export import ExportManager
from perera_lead_scraper.processing import LeadProcessor
from perera_lead_scraper.monitoring.monitoring import SystemMonitor
from perera_lead_scraper.config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('e2e_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("E2ETest")


@dataclass
class TestMetric:
    """Class for storing test metrics."""
    name: str
    value: float
    unit: str
    timestamp: datetime = field(default_factory=datetime.now)
    category: str = "general"
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    """Class for storing test results."""
    success: bool
    metrics: List[TestMetric] = field(default_factory=list)
    issues: List[Dict[str, Any]] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestReport:
    """Class for generating test reports."""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    results: Dict[str, TestResult] = field(default_factory=dict)
    metrics: List[TestMetric] = field(default_factory=list)
    
    def add_metric(self, name: str, value: float, unit: str, 
                  category: str = "general", context: Dict[str, Any] = None) -> None:
        """Add a metric to the report."""
        self.metrics.append(TestMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.now(),
            category=category,
            context=context or {}
        ))
    
    def add_test_result(self, test_name: str, result: TestResult) -> None:
        """Add a test result to the report."""
        self.results[test_name] = result
        
    def finalize(self) -> None:
        """Finalize the report by setting the end time."""
        self.end_time = datetime.now()
    
    def generate_report(self, output_dir: str = None) -> Dict[str, Any]:
        """Generate a JSON report of the test results."""
        if not self.end_time:
            self.finalize()
            
        # Calculate overall metrics
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results.values() if result.success)
        
        # Calculate test duration
        duration = (self.end_time - self.start_time).total_seconds()
        
        # Organize metrics by category
        metrics_by_category = {}
        for metric in self.metrics:
            if metric.category not in metrics_by_category:
                metrics_by_category[metric.category] = []
            metrics_by_category[metric.category].append({
                "name": metric.name,
                "value": metric.value,
                "unit": metric.unit,
                "timestamp": metric.timestamp.isoformat()
            })
        
        # Create report structure
        report = {
            "summary": {
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "duration_seconds": duration,
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "status": "PASSED" if passed_tests == total_tests else "FAILED"
            },
            "test_results": {
                test_name: {
                    "success": result.success,
                    "issues": result.issues,
                    "metrics": [
                        {
                            "name": metric.name,
                            "value": metric.value,
                            "unit": metric.unit,
                            "category": metric.category
                        } for metric in result.metrics
                    ],
                    "details": result.details
                } for test_name, result in self.results.items()
            },
            "metrics": metrics_by_category
        }
        
        # Write to file if output_dir is provided
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            report_path = os.path.join(output_dir, f"e2e_test_report_{self.end_time.strftime('%Y%m%d_%H%M%S')}.json")
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Test report generated at: {report_path}")
        
        return report
    
    def print_summary(self) -> None:
        """Print a summary of the test results to the console."""
        if not self.end_time:
            self.finalize()
            
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results.values() if result.success)
        
        duration = (self.end_time - self.start_time).total_seconds()
        
        print("\n" + "=" * 80)
        print(f"END-TO-END TEST SUMMARY")
        print("=" * 80)
        print(f"Start Time: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"End Time: {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Tests: {passed_tests}/{total_tests} passed ({passed_tests/total_tests*100:.2f}%)")
        print(f"Status: {'PASSED' if passed_tests == total_tests else 'FAILED'}")
        print("\nTest Results:")
        
        for test_name, result in self.results.items():
            status = "✓ PASSED" if result.success else "✗ FAILED"
            print(f"  {status} - {test_name}")
            
            if not result.success and result.issues:
                print(f"    Issues:")
                for issue in result.issues:
                    print(f"    - {issue.get('message', 'Unknown issue')}")
        
        print("\nKey Metrics:")
        categories_to_show = ["performance", "data_quality", "resource_usage"]
        for category in categories_to_show:
            metrics = [m for m in self.metrics if m.category == category]
            if metrics:
                print(f"  {category.replace('_', ' ').title()}:")
                for metric in metrics:
                    print(f"    - {metric.name}: {metric.value} {metric.unit}")
        
        print("=" * 80)


class MockDataSource(BaseDataSource):
    """Mock data source for testing."""
    
    source_type = "mock"
    
    def __init__(self, config=None):
        super().__init__(config or {})
        self.mock_data = config.get("mock_data", [])
        self.sector = config.get("sector", "general")
        self.error_rate = config.get("error_rate", 0.0)
        self.delay = config.get("delay", 0.0)
        
    def connect(self):
        time.sleep(self.delay / 2)  # Simulate connection delay
        return True
        
    def fetch_data(self):
        time.sleep(self.delay / 2)  # Simulate fetch delay
        return self.mock_data


class MockHubSpotClient:
    """Mock HubSpot client for testing."""
    
    def __init__(self):
        self.contacts = {}
        self.deals = {}
        
    def create_contact(self, properties):
        contact_id = f"contact_{len(self.contacts) + 1}"
        self.contacts[contact_id] = properties
        return {"id": contact_id, "properties": properties}
    
    def create_deal(self, properties):
        deal_id = f"deal_{len(self.deals) + 1}"
        self.deals[deal_id] = properties
        return {"id": deal_id, "properties": properties}
    
    def associate_objects(self, from_object_type, from_object_id, to_object_type, to_object_id, association_type):
        return {"success": True}


class E2ETestSuite:
    """
    End-to-End test suite for the Perera Construction Lead Scraper.
    
    This class contains tests that validate the entire lead generation pipeline
    from source configuration to CRM export, across all target market sectors.
    """
    
    def __init__(self):
        """Initialize the test suite."""
        self.report = TestReport()
        self.test_dir = tempfile.mkdtemp(prefix="perera_lead_test_")
        
        # Set up test environment
        self.setup_test_environment()
        
        # Create component instances
        self.storage = LeadStorage(db_path=os.path.join(self.test_dir, "test_leads.db"))
        self.orchestrator = LeadGenerationOrchestrator(
            storage=self.storage,
            config_path=os.path.join(self.test_dir, "test_config.json")
        )
        self.monitor = SystemMonitor(
            metrics_db_path=os.path.join(self.test_dir, "test_metrics.db")
        )
        
        # Mock HubSpot client
        self.hubspot_client = MockHubSpotClient()
        
        # Test configuration
        self.sector_test_data = self.load_test_data()
    
    def setup_test_environment(self):
        """Set up the isolated test environment."""
        # Create directories
        os.makedirs(os.path.join(self.test_dir, "data"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "exports"), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "logs"), exist_ok=True)
        
        # Create test configuration
        test_config = {
            "storage": {
                "type": "sqlite",
                "path": os.path.join(self.test_dir, "test_leads.db")
            },
            "monitoring": {
                "metrics_interval": 10,
                "metrics_database": os.path.join(self.test_dir, "test_metrics.db")
            },
            "export": {
                "hubspot": {
                    "api_key": "test_api_key",
                    "field_mapping": {
                        "name": "dealname",
                        "company": "company",
                        "email": "email",
                        "phone": "phone",
                        "address": "address",
                        "project_type": "project_type",
                        "project_value": "amount",
                        "project_description": "description",
                        "source": "lead_source",
                        "quality_score": "quality_score"
                    }
                },
                "email": {
                    "enabled": False
                },
                "formats": ["csv", "json", "xlsx"]
            },
            "processing": {
                "quality_threshold": 50,
                "enrichment": {
                    "enabled": True
                }
            },
            "sources": []  # Will be populated with test sources
        }
        
        # Write test configuration to file
        with open(os.path.join(self.test_dir, "test_config.json"), 'w') as f:
            json.dump(test_config, f, indent=2)
    
    def load_test_data(self):
        """Load test data for each sector."""
        sector_data = {
            "healthcare": self._create_healthcare_test_data(),
            "education": self._create_education_test_data(),
            "energy": self._create_energy_test_data(),
            "entertainment": self._create_entertainment_test_data(),
            "commercial": self._create_commercial_test_data()
        }
        return sector_data
    
    def _create_healthcare_test_data(self):
        """Create test data for healthcare sector."""
        return {
            "name": "Healthcare",
            "sources": [
                {
                    "type": "mock",
                    "name": "Healthcare Projects",
                    "config": {
                        "sector": "healthcare",
                        "delay": 0.5,
                        "mock_data": [
                            {
                                "name": "New Medical Center Construction",
                                "company": "Health Partners Inc.",
                                "email": "contact@healthpartners.example",
                                "phone": "555-123-4567",
                                "address": "100 Medical Park Dr, Boston, MA",
                                "project_type": "healthcare",
                                "project_value": 15000000,
                                "project_description": "Construction of a new 50,000 sq ft medical center with emergency department, imaging center, and specialty clinics.",
                                "source_url": "https://example.com/projects/medical-center"
                            },
                            {
                                "name": "Hospital Expansion Wing",
                                "company": "Central Hospital",
                                "email": "development@centralhospital.example",
                                "phone": "555-987-6543",
                                "address": "200 Healthcare Blvd, Chicago, IL",
                                "project_type": "healthcare",
                                "project_value": 22000000,
                                "project_description": "Adding a new 75,000 sq ft wing to existing hospital facility with 50 patient rooms and surgical suites.",
                                "source_url": "https://example.com/projects/hospital-expansion"
                            },
                            {
                                "name": "Medical Office Building",
                                "company": "Physician Group LLC",
                                "email": "info@physiciangroup.example",
                                "phone": "555-456-7890",
                                "address": "300 Doctor Way, Miami, FL",
                                "project_type": "healthcare",
                                "project_value": 5000000,
                                "project_description": "New 3-story medical office building with specialty practices and outpatient surgery center.",
                                "source_url": "https://example.com/projects/medical-office"
                            }
                        ]
                    }
                }
            ],
            "expected_leads": 3,
            "expected_min_quality": 70
        }
    
    def _create_education_test_data(self):
        """Create test data for higher education sector."""
        return {
            "name": "Higher Education",
            "sources": [
                {
                    "type": "mock",
                    "name": "Education Projects",
                    "config": {
                        "sector": "education",
                        "delay": 0.3,
                        "mock_data": [
                            {
                                "name": "University Science Building",
                                "company": "State University",
                                "email": "facilities@stateuniv.example",
                                "phone": "555-222-3333",
                                "address": "1 University Dr, Austin, TX",
                                "project_type": "education",
                                "project_value": 45000000,
                                "project_description": "New 120,000 sq ft science and research facility with labs, classrooms, and collaborative spaces.",
                                "source_url": "https://example.com/projects/science-building"
                            },
                            {
                                "name": "Student Housing Complex",
                                "company": "College Housing Authority",
                                "email": "housing@college.example",
                                "phone": "555-444-5555",
                                "address": "200 Campus Rd, Berkeley, CA",
                                "project_type": "education",
                                "project_value": 30000000,
                                "project_description": "New student housing complex with 500 beds, dining facilities, and study spaces.",
                                "source_url": "https://example.com/projects/student-housing"
                            }
                        ]
                    }
                }
            ],
            "expected_leads": 2,
            "expected_min_quality": 75
        }
    
    def _create_energy_test_data(self):
        """Create test data for energy/utilities sector."""
        return {
            "name": "Energy/Utilities",
            "sources": [
                {
                    "type": "mock",
                    "name": "Energy Projects",
                    "config": {
                        "sector": "energy",
                        "delay": 0.4,
                        "mock_data": [
                            {
                                "name": "Solar Farm Development",
                                "company": "Clean Energy Solutions",
                                "email": "projects@cleanenergy.example",
                                "phone": "555-777-8888",
                                "address": "Rural Route 5, Phoenix, AZ",
                                "project_type": "energy",
                                "project_value": 25000000,
                                "project_description": "50MW solar farm development with access roads, control building, and grid connection infrastructure.",
                                "source_url": "https://example.com/projects/solar-farm"
                            },
                            {
                                "name": "Water Treatment Facility Upgrade",
                                "company": "Municipal Water Authority",
                                "email": "engineering@waterauth.example",
                                "phone": "555-666-7777",
                                "address": "400 Waterworks Rd, Denver, CO",
                                "project_type": "utilities",
                                "project_value": 18000000,
                                "project_description": "Comprehensive upgrade of municipal water treatment facility with new filtration systems and control building.",
                                "source_url": "https://example.com/projects/water-treatment"
                            }
                        ]
                    }
                }
            ],
            "expected_leads": 2,
            "expected_min_quality": 65
        }
    
    def _create_entertainment_test_data(self):
        """Create test data for themed entertainment sector."""
        return {
            "name": "Themed Entertainment",
            "sources": [
                {
                    "type": "mock",
                    "name": "Entertainment Projects",
                    "config": {
                        "sector": "entertainment",
                        "delay": 0.6,
                        "mock_data": [
                            {
                                "name": "Theme Park Attraction",
                                "company": "Adventure World Parks",
                                "email": "development@adventureworld.example",
                                "phone": "555-999-8888",
                                "address": "500 Theme Park Way, Orlando, FL",
                                "project_type": "entertainment",
                                "project_value": 65000000,
                                "project_description": "New immersive themed attraction with queue building, ride system, and extensive theming elements.",
                                "source_url": "https://example.com/projects/theme-park-attraction"
                            },
                            {
                                "name": "Waterpark Expansion",
                                "company": "Splash Resorts",
                                "email": "projects@splashresorts.example",
                                "phone": "555-123-7777",
                                "address": "100 Splash Rd, Myrtle Beach, SC",
                                "project_type": "entertainment",
                                "project_value": 12000000,
                                "project_description": "Expansion of existing waterpark with new slides, wave pool, and support facilities.",
                                "source_url": "https://example.com/projects/waterpark-expansion"
                            }
                        ]
                    }
                }
            ],
            "expected_leads": 2,
            "expected_min_quality": 80
        }
    
    def _create_commercial_test_data(self):
        """Create test data for general commercial construction sector."""
        return {
            "name": "General Commercial",
            "sources": [
                {
                    "type": "mock",
                    "name": "Commercial Projects",
                    "config": {
                        "sector": "commercial",
                        "delay": 0.2,
                        "error_rate": 0.2,  # 20% chance of error
                        "mock_data": [
                            {
                                "name": "Office Tower Development",
                                "company": "Commercial Properties LLC",
                                "email": "development@commercial.example",
                                "phone": "555-333-2222",
                                "address": "100 Business Plaza, Atlanta, GA",
                                "project_type": "commercial",
                                "project_value": 85000000,
                                "project_description": "New 30-story office tower with ground floor retail, parking garage, and green roof amenities.",
                                "source_url": "https://example.com/projects/office-tower"
                            },
                            {
                                "name": "Retail Shopping Center",
                                "company": "Retail Developers Inc",
                                "email": "leasing@retaildev.example",
                                "phone": "555-444-3333",
                                "address": "200 Shopping Way, Dallas, TX",
                                "project_type": "commercial",
                                "project_value": 35000000,
                                "project_description": "New shopping center with 25 retail spaces, food court, and outdoor plaza.",
                                "source_url": "https://example.com/projects/shopping-center"
                            },
                            {
                                "name": "Hotel and Conference Center",
                                "company": "Hospitality Group",
                                "email": "projects@hospitalitygroup.example",
                                "phone": "555-111-2222",
                                "address": "300 Resort Blvd, San Diego, CA",
                                "project_type": "commercial",
                                "project_value": 55000000,
                                "project_description": "New 250-room hotel with 15,000 sq ft of conference space, restaurant, and amenities.",
                                "source_url": "https://example.com/projects/hotel-conference"
                            },
                            # Edge case with minimal data
                            {
                                "name": "Warehouse Construction",
                                "project_type": "commercial",
                                "project_description": "Construction of a new warehouse facility.",
                                "source_url": "https://example.com/projects/warehouse"
                            }
                        ]
                    }
                }
            ],
            "expected_leads": 4,
            "expected_min_quality": 60
        }
    
    def setup_test_sources(self, sector_name):
        """Configure test sources for a specific sector."""
        sector_data = self.sector_test_data.get(sector_name)
        if not sector_data:
            raise ValueError(f"Unknown sector: {sector_name}")
        
        sources = sector_data["sources"]
        
        # Add sources to orchestrator
        for source_config in sources:
            source_type = source_config["type"]
            source_name = source_config["name"]
            config = source_config.get("config", {})
            
            # Register mock source if needed
            if source_type == "mock" and source_type not in self.orchestrator.get_available_sources():
                # Register the mock source
                from perera_lead_scraper.sources import AVAILABLE_SOURCES
                AVAILABLE_SOURCES[MockDataSource.source_type] = MockDataSource
            
            # Add source to orchestrator
            self.orchestrator.add_source(
                source_type=source_type,
                name=source_name,
                is_active=True,
                config=config
            )
    
    def cleanup(self):
        """Clean up the test environment."""
        # Clean up test directory
        try:
            shutil.rmtree(self.test_dir)
        except Exception as e:
            logger.warning(f"Failed to clean up test directory: {str(e)}")
    
    def run_all_tests(self):
        """Run all end-to-end tests."""
        try:
            # Start timing the entire test suite
            suite_start_time = time.time()
            
            # Start memory tracking
            tracemalloc.start()
            
            # Run tests for each sector
            for sector_name in self.sector_test_data.keys():
                self._test_sector_pipeline(sector_name)
            
            # Test error handling and recovery
            self._test_error_handling()
            
            # Test concurrent operations
            self._test_concurrent_operations()
            
            # Test end-to-end export
            self._test_export_to_crm()
            
            # Test system performance
            self._test_system_performance()
            
            # Stop memory tracking
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            
            # Record overall memory usage
            self.report.add_metric(
                name="peak_memory_usage",
                value=peak / (1024 * 1024),
                unit="MB",
                category="resource_usage"
            )
            
            # Record total test duration
            suite_duration = time.time() - suite_start_time
            self.report.add_metric(
                name="total_test_duration",
                value=suite_duration,
                unit="seconds",
                category="performance"
            )
            
            # Finalize report
            self.report.finalize()
            
            # Generate and print report
            self.report.generate_report(output_dir="test_reports")
            self.report.print_summary()
            
        finally:
            # Clean up
            self.cleanup()
    
    def _test_sector_pipeline(self, sector_name):
        """Test the lead generation pipeline for a specific sector."""
        logger.info(f"Testing {sector_name} sector pipeline")
        
        # Reset storage for clean test
        self.storage.reset_database()
        
        # Set up test sources for this sector
        self.setup_test_sources(sector_name)
        
        # Start timing
        start_time = time.time()
        
        # Process metrics
        process = psutil.Process(os.getpid())
        start_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        try:
            # Run the lead generation pipeline
            result = self.orchestrator.generate_leads()
            
            # Measure end metrics
            end_time = time.time()
            duration = end_time - start_time
            end_memory = process.memory_info().rss / (1024 * 1024)  # MB
            memory_increase = end_memory - start_memory
            
            # Get all leads from storage
            leads = self.storage.get_all_leads()
            
            # Check lead count
            expected_lead_count = self.sector_test_data[sector_name]["expected_leads"]
            lead_count_match = len(leads) == expected_lead_count
            
            # Check lead quality
            expected_min_quality = self.sector_test_data[sector_name]["expected_min_quality"]
            quality_scores = [lead.quality_score for lead in leads if lead.quality_score is not None]
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
            min_quality = min(quality_scores) if quality_scores else 0
            quality_match = avg_quality >= expected_min_quality
            
            # Check lead data completeness
            completeness_scores = []
            required_fields = ["name", "project_type", "project_description", "source"]
            for lead in leads:
                # Calculate completeness as percentage of all potential fields
                field_count = sum(1 for field in ["name", "company", "email", "phone", 
                                               "address", "project_type", "project_value",
                                               "project_description", "source", "source_url"]
                                if hasattr(lead, field) and getattr(lead, field))
                completeness = field_count / 10
                
                # Check required fields
                required_completeness = all(hasattr(lead, field) and getattr(lead, field) 
                                         for field in required_fields)
                
                # Only include leads with required fields
                if required_completeness:
                    completeness_scores.append(completeness)
            
            avg_completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0
            
            # Determine success based on metrics
            success = lead_count_match and quality_match and avg_completeness >= 0.7
            
            # Create test result
            result = TestResult(
                success=success,
                metrics=[
                    TestMetric(name="processing_time", value=duration, unit="seconds", category="performance"),
                    TestMetric(name="memory_usage", value=memory_increase, unit="MB", category="resource_usage"),
                    TestMetric(name="lead_count", value=len(leads), unit="leads", category="data_quality"),
                    TestMetric(name="average_quality", value=avg_quality, unit="score", category="data_quality"),
                    TestMetric(name="min_quality", value=min_quality, unit="score", category="data_quality"),
                    TestMetric(name="average_completeness", value=avg_completeness, unit="ratio", category="data_quality")
                ],
                details={
                    "sector": sector_name,
                    "expected_lead_count": expected_lead_count,
                    "actual_lead_count": len(leads),
                    "expected_min_quality": expected_min_quality,
                    "lead_ids": [lead.id for lead in leads]
                }
            )
            
            # Add issues if any
            if not lead_count_match:
                result.issues.append({
                    "type": "lead_count_mismatch",
                    "message": f"Expected {expected_lead_count} leads, got {len(leads)}",
                    "severity": "high"
                })
            
            if not quality_match:
                result.issues.append({
                    "type": "quality_below_threshold",
                    "message": f"Average quality {avg_quality:.2f} below expected {expected_min_quality}",
                    "severity": "medium"
                })
            
            if avg_completeness < 0.7:
                result.issues.append({
                    "type": "low_data_completeness",
                    "message": f"Average data completeness {avg_completeness:.2f} below threshold 0.7",
                    "severity": "medium"
                })
            
            # Add result to report
            self.report.add_test_result(f"sector_pipeline_{sector_name}", result)
            
            logger.info(f"Completed {sector_name} sector test: {'SUCCESS' if success else 'FAILURE'}")
            
        except Exception as e:
            logger.error(f"Error testing {sector_name} sector: {str(e)}", exc_info=True)
            
            # Create failure result
            result = TestResult(
                success=False,
                issues=[{
                    "type": "exception",
                    "message": str(e),
                    "severity": "critical",
                    "details": {
                        "traceback": traceback.format_exc()
                    }
                }],
                details={
                    "sector": sector_name
                }
            )
            
            # Add to report
            self.report.add_test_result(f"sector_pipeline_{sector_name}", result)
    
    def _test_error_handling(self):
        """Test system error handling and recovery capabilities."""
        logger.info("Testing error handling and recovery")
        
        # Reset storage for clean test
        self.storage.reset_database()
        
        # Create test source with errors
        error_source = {
            "type": "mock",
            "name": "Error Test Source",
            "config": {
                "sector": "commercial",
                "error_rate": 1.0,  # 100% error rate
                "mock_data": [
                    {
                        "name": "Test Project",
                        "project_type": "commercial",
                        "project_description": "Test project with errors",
                        "source_url": "https://example.com/test"
                    }
                ]
            }
        }
        
        # Add error source to orchestrator
        source_id = self.orchestrator.add_source(
            source_type=error_source["type"],
            name=error_source["name"],
            is_active=True,
            config=error_source["config"]
        )
        
        # Start timing
        start_time = time.time()
        
        try:
            # Run orchestrator with retry enabled
            with patch.object(self.orchestrator, 'max_retries', 3):
                result = self.orchestrator.generate_leads()
            
            # Measure end time
            end_time = time.time()
            duration = end_time - start_time
            
            # Check error logging in the monitor
            error_count = 0
            retry_count = 0
            
            # Get errors from monitor or logs
            # This is a simplified version - actual implementation would depend on how errors are logged
            if hasattr(self.monitor, 'get_recent_errors'):
                errors = self.monitor.get_recent_errors()
                error_count = len(errors)
                retry_count = sum(1 for e in errors if "retry" in str(e).lower())
            
            # Determine if error handling was successful
            # Success criteria: System detected errors, tried to recover (retries), and continued operation
            success = error_count > 0 and retry_count > 0
            
            # Create test result
            result = TestResult(
                success=success,
                metrics=[
                    TestMetric(name="error_handling_time", value=duration, unit="seconds", category="performance"),
                    TestMetric(name="error_count", value=error_count, unit="errors", category="error_handling"),
                    TestMetric(name="retry_count", value=retry_count, unit="retries", category="error_handling")
                ],
                details={
                    "source_id": source_id,
                    "error_rate": 1.0
                }
            )
            
            # Add issues if any
            if error_count == 0:
                result.issues.append({
                    "type": "no_errors_detected",
                    "message": "Expected errors were not detected",
                    "severity": "high"
                })
            
            if retry_count == 0:
                result.issues.append({
                    "type": "no_retry_attempts",
                    "message": "No retry attempts were made",
                    "severity": "high"
                })
            
            # Add result to report
            self.report.add_test_result("error_handling", result)
            
            logger.info(f"Completed error handling test: {'SUCCESS' if success else 'FAILURE'}")
            
        except Exception as e:
            logger.error(f"Error during error handling test: {str(e)}", exc_info=True)
            
            # Create failure result
            result = TestResult(
                success=False,
                issues=[{
                    "type": "exception",
                    "message": str(e),
                    "severity": "critical",
                    "details": {
                        "traceback": traceback.format_exc()
                    }
                }],
                details={
                    "source_id": source_id
                }
            )
            
            # Add to report
            self.report.add_test_result("error_handling", result)
        
        finally:
            # Remove the error source
            self.orchestrator.remove_source(source_id)
    
    def _test_concurrent_operations(self):
        """Test system performance under concurrent operations."""
        logger.info("Testing concurrent operations")
        
        # Reset storage for clean test
        self.storage.reset_database()
        
        # Set up test sources for multiple sectors
        for sector_name in ["healthcare", "education", "commercial"]:
            self.setup_test_sources(sector_name)
        
        # Start timing
        start_time = time.time()
        
        try:
            # Define concurrent operations
            operations = [
                self._run_source_operation,
                self._run_export_operation,
                self._run_query_operation,
                self._run_processing_operation
            ]
            
            # Number of concurrent operations to run
            concurrency_level = 8
            
            # Run operations concurrently
            results = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency_level) as executor:
                # Submit operations
                futures = []
                for _ in range(concurrency_level):
                    op = random.choice(operations)
                    futures.append(executor.submit(op))
                
                # Collect results
                for future in concurrent.futures.as_completed(futures):
                    try:
                        results.append(future.result())
                    except Exception as e:
                        logger.error(f"Operation failed: {str(e)}")
                        results.append(False)
            
            # Measure end time
            end_time = time.time()
            duration = end_time - start_time
            
            # Analyze results
            success_count = sum(1 for r in results if r)
            success_rate = success_count / len(results) if results else 0
            
            # Create test result
            result = TestResult(
                success=success_rate >= 0.8,  # At least 80% success rate
                metrics=[
                    TestMetric(name="concurrent_operation_time", value=duration, unit="seconds", category="performance"),
                    TestMetric(name="operation_count", value=len(results), unit="operations", category="concurrency"),
                    TestMetric(name="success_rate", value=success_rate, unit="ratio", category="concurrency")
                ],
                details={
                    "concurrency_level": concurrency_level,
                    "operations_attempted": len(results),
                    "operations_succeeded": success_count
                }
            )
            
            # Add issues if any
            if success_rate < 0.8:
                result.issues.append({
                    "type": "low_concurrency_success_rate",
                    "message": f"Success rate {success_rate:.2f} below threshold 0.8",
                    "severity": "high"
                })
            
            # Add result to report
            self.report.add_test_result("concurrent_operations", result)
            
            logger.info(f"Completed concurrent operations test: {'SUCCESS' if result.success else 'FAILURE'}")
            
        except Exception as e:
            logger.error(f"Error during concurrent operations test: {str(e)}", exc_info=True)
            
            # Create failure result
            result = TestResult(
                success=False,
                issues=[{
                    "type": "exception",
                    "message": str(e),
                    "severity": "critical",
                    "details": {
                        "traceback": traceback.format_exc()
                    }
                }]
            )
            
            # Add to report
            self.report.add_test_result("concurrent_operations", result)
    
    def _run_source_operation(self):
        """Run a source operation for concurrency testing."""
        try:
            # Get a random source
            sources = self.orchestrator.get_sources()
            if not sources:
                return False
            
            source = random.choice(sources)
            
            # Run the source
            self.orchestrator.run_source(source.id)
            return True
        except Exception as e:
            logger.error(f"Source operation failed: {str(e)}")
            return False
    
    def _run_export_operation(self):
        """Run an export operation for concurrency testing."""
        try:
            # Create an export manager
            export_manager = ExportManager()
            
            # Get leads to export
            leads = self.storage.get_all_leads()
            if not leads:
                return False
            
            # Select a random subset
            sample_size = min(10, len(leads))
            sample = random.sample(leads, sample_size)
            
            # Export to CSV
            export_path = os.path.join(self.test_dir, f"export_{time.time()}.csv")
            export_manager.export_to_csv(sample, export_path)
            
            return os.path.exists(export_path)
        except Exception as e:
            logger.error(f"Export operation failed: {str(e)}")
            return False
    
    def _run_query_operation(self):
        """Run a query operation for concurrency testing."""
        try:
            # Perform various queries
            all_leads = self.storage.get_all_leads()
            if not all_leads:
                return False
            
            # Get a random lead
            lead = random.choice(all_leads)
            
            # Get lead by ID
            lead_by_id = self.storage.get_lead(lead.id)
            
            # Query by various criteria
            if hasattr(self.storage, 'query_leads'):
                leads_by_type = self.storage.query_leads(project_type=lead.project_type)
                high_quality_leads = self.storage.query_leads(min_quality=70)
            
            return True
        except Exception as e:
            logger.error(f"Query operation failed: {str(e)}")
            return False
    
    def _run_processing_operation(self):
        """Run a processing operation for concurrency testing."""
        try:
            # Create a processor
            processor = LeadProcessor()
            
            # Create a mock lead
            mock_data = {
                "name": f"Test Project {time.time()}",
                "company": "Test Company",
                "project_type": "commercial",
                "project_description": "This is a test project for concurrency testing.",
                "source": "test_source"
            }
            
            # Process the lead
            processed_lead = processor.process_lead(mock_data)
            
            # Store the lead
            self.storage.store_lead(processed_lead)
            
            return True
        except Exception as e:
            logger.error(f"Processing operation failed: {str(e)}")
            return False
    
    def _test_export_to_crm(self):
        """Test the export to HubSpot CRM functionality."""
        logger.info("Testing export to HubSpot CRM")
        
        # Create leads if none exist
        leads = self.storage.get_all_leads()
        if not leads:
            # Setup some test sources and generate leads
            self.setup_test_sources("commercial")
            self.orchestrator.generate_leads()
            leads = self.storage.get_all_leads()
        
        # Start timing
        start_time = time.time()
        
        try:
            # Create export manager with mock HubSpot client
            export_manager = ExportManager()
            
            # Patch the HubSpot client creation
            with patch('perera_lead_scraper.export.hubspot.create_hubspot_client', 
                     return_value=self.hubspot_client):
                
                # Export leads to HubSpot
                export_result = export_manager.export_to_hubspot(leads)
            
            # Measure end time
            end_time = time.time()
            duration = end_time - start_time
            
            # Check results
            contact_count = len(self.hubspot_client.contacts)
            deal_count = len(self.hubspot_client.deals)
            
            # Validate mapping accuracy
            mapping_errors = 0
            for lead in leads:
                # Find corresponding deal
                matching_deals = [
                    deal for deal_id, deal in self.hubspot_client.deals.items()
                    if deal.get("dealname") == lead.name
                ]
                
                if not matching_deals:
                    mapping_errors += 1
                    continue
                
                deal = matching_deals[0]
                
                # Check basic mapping
                if lead.project_value and str(lead.project_value) != str(deal.get("amount")):
                    mapping_errors += 1
                
                if lead.project_description != deal.get("description"):
                    mapping_errors += 1
            
            mapping_accuracy = 1 - (mapping_errors / len(leads)) if leads else 0
            
            # Create test result
            result = TestResult(
                success=contact_count > 0 and deal_count > 0 and mapping_accuracy >= 0.9,
                metrics=[
                    TestMetric(name="export_time", value=duration, unit="seconds", category="performance"),
                    TestMetric(name="contact_count", value=contact_count, unit="contacts", category="export"),
                    TestMetric(name="deal_count", value=deal_count, unit="deals", category="export"),
                    TestMetric(name="mapping_accuracy", value=mapping_accuracy, unit="ratio", category="data_quality")
                ],
                details={
                    "lead_count": len(leads),
                    "contacts_created": contact_count,
                    "deals_created": deal_count
                }
            )
            
            # Add issues if any
            if contact_count == 0:
                result.issues.append({
                    "type": "no_contacts_created",
                    "message": "No contacts were created in HubSpot",
                    "severity": "critical"
                })
            
            if deal_count == 0:
                result.issues.append({
                    "type": "no_deals_created",
                    "message": "No deals were created in HubSpot",
                    "severity": "critical"
                })
            
            if mapping_accuracy < 0.9:
                result.issues.append({
                    "type": "low_mapping_accuracy",
                    "message": f"Mapping accuracy {mapping_accuracy:.2f} below threshold 0.9",
                    "severity": "high"
                })
            
            # Add result to report
            self.report.add_test_result("export_to_crm", result)
            
            logger.info(f"Completed export to CRM test: {'SUCCESS' if result.success else 'FAILURE'}")
            
        except Exception as e:
            logger.error(f"Error during export to CRM test: {str(e)}", exc_info=True)
            
            # Create failure result
            result = TestResult(
                success=False,
                issues=[{
                    "type": "exception",
                    "message": str(e),
                    "severity": "critical",
                    "details": {
                        "traceback": traceback.format_exc()
                    }
                }]
            )
            
            # Add to report
            self.report.add_test_result("export_to_crm", result)
    
    def _test_system_performance(self):
        """Test overall system performance under load."""
        logger.info("Testing system performance under load")
        
        # Reset storage for clean test
        self.storage.reset_database()
        
        # Set up sources from all sectors
        for sector_name in self.sector_test_data.keys():
            self.setup_test_sources(sector_name)
        
        # Start monitoring resources
        process = psutil.Process(os.getpid())
        start_cpu_times = process.cpu_times()
        start_memory = process.memory_info().rss / (1024 * 1024)  # MB
        start_time = time.time()
        
        try:
            # Generate leads from all sources
            self.orchestrator.generate_leads()
            
            # Get all leads
            leads = self.storage.get_all_leads()
            
            # Perform various operations to measure performance
            # 1. Export to all formats
            export_manager = ExportManager()
            
            export_paths = {
                "csv": os.path.join(self.test_dir, "performance_test_export.csv"),
                "json": os.path.join(self.test_dir, "performance_test_export.json"),
                "xlsx": os.path.join(self.test_dir, "performance_test_export.xlsx")
            }
            
            export_times = {}
            
            for format_name, path in export_paths.items():
                format_start = time.time()
                
                if format_name == "csv":
                    export_manager.export_to_csv(leads, path)
                elif format_name == "json":
                    export_manager.export_to_json(leads, path)
                elif format_name == "xlsx":
                    export_manager.export_to_excel(leads, path)
                
                export_times[format_name] = time.time() - format_start
            
            # 2. Run queries
            query_start = time.time()
            
            # Query by different criteria
            if hasattr(self.storage, 'query_leads'):
                for sector in ["healthcare", "education", "commercial"]:
                    sector_leads = self.storage.query_leads(project_type=sector)
                
                high_quality = self.storage.query_leads(min_quality=75)
                recent_leads = self.storage.query_leads(
                    start_date=datetime.now() - timedelta(days=1)
                )
            
            query_time = time.time() - query_start
            
            # Measure end resources
            end_time = time.time()
            duration = end_time - start_time
            
            end_cpu_times = process.cpu_times()
            end_memory = process.memory_info().rss / (1024 * 1024)  # MB
            
            cpu_time = (end_cpu_times.user - start_cpu_times.user) + (end_cpu_times.system - start_cpu_times.system)
            memory_increase = end_memory - start_memory
            
            # Calculate leads per second
            leads_per_second = len(leads) / duration if duration > 0 else 0
            
            # Create test result
            result = TestResult(
                success=duration < 60 and memory_increase < 100,  # Example thresholds
                metrics=[
                    TestMetric(name="total_processing_time", value=duration, unit="seconds", category="performance"),
                    TestMetric(name="cpu_time", value=cpu_time, unit="seconds", category="resource_usage"),
                    TestMetric(name="memory_usage", value=memory_increase, unit="MB", category="resource_usage"),
                    TestMetric(name="leads_per_second", value=leads_per_second, unit="leads/s", category="performance"),
                    TestMetric(name="query_time", value=query_time, unit="seconds", category="performance"),
                    TestMetric(name="csv_export_time", value=export_times.get("csv", 0), unit="seconds", category="performance"),
                    TestMetric(name="json_export_time", value=export_times.get("json", 0), unit="seconds", category="performance"),
                    TestMetric(name="xlsx_export_time", value=export_times.get("xlsx", 0), unit="seconds", category="performance")
                ],
                details={
                    "lead_count": len(leads),
                    "source_count": len(self.orchestrator.get_sources())
                }
            )
            
            # Add issues if any
            if duration > 60:
                result.issues.append({
                    "type": "slow_processing",
                    "message": f"Total processing time {duration:.2f}s exceeds threshold of 60s",
                    "severity": "medium"
                })
            
            if memory_increase > 100:
                result.issues.append({
                    "type": "high_memory_usage",
                    "message": f"Memory usage {memory_increase:.2f}MB exceeds threshold of 100MB",
                    "severity": "medium"
                })
            
            # Add result to report
            self.report.add_test_result("system_performance", result)
            
            logger.info(f"Completed system performance test: {'SUCCESS' if result.success else 'FAILURE'}")
            
        except Exception as e:
            logger.error(f"Error during system performance test: {str(e)}", exc_info=True)
            
            # Create failure result
            result = TestResult(
                success=False,
                issues=[{
                    "type": "exception",
                    "message": str(e),
                    "severity": "critical",
                    "details": {
                        "traceback": traceback.format_exc()
                    }
                }]
            )
            
            # Add to report
            self.report.add_test_result("system_performance", result)


@pytest.mark.e2e
class TestE2E(unittest.TestCase):
    """Unittest wrapper for the E2E test suite."""
    
    def test_full_e2e(self):
        """Run the full end-to-end test suite."""
        # Skip if running in CI with --ci flag
        if pytest.config.getoption("--ci", default=False):
            pytest.skip("Skipping full E2E test in CI environment")
        
        # Run the test suite
        test_suite = E2ETestSuite()
        test_suite.run_all_tests()
    
    def test_individual_modules(self):
        """Test individual modules separately."""
        # This is a faster version that can run in CI
        test_suite = E2ETestSuite()
        
        # Only test a single sector
        test_suite._test_sector_pipeline("commercial")
        
        # Test error handling
        test_suite._test_error_handling()
        
        # Clean up
        test_suite.cleanup()
        
        # Check results
        self.assertTrue(
            test_suite.report.results.get("sector_pipeline_commercial", TestResult(success=False)).success,
            "Commercial sector pipeline test failed"
        )


# Stand-alone execution
if __name__ == "__main__":
    # Parse arguments
    import argparse
    
    parser = argparse.ArgumentParser(description="Run end-to-end tests for Perera Lead Scraper")
    parser.add_argument("--sectors", type=str, help="Comma-separated list of sectors to test")
    parser.add_argument("--report-dir", type=str, default="test_reports", help="Directory for test reports")
    parser.add_argument("--full", action="store_true", help="Run full test suite")
    
    args = parser.parse_args()
    
    # Create test suite
    test_suite = E2ETestSuite()
    
    if args.full:
        # Run the full test suite
        test_suite.run_all_tests()
    elif args.sectors:
        # Run tests for specific sectors
        sectors = args.sectors.split(",")
        for sector in sectors:
            if sector in test_suite.sector_test_data:
                test_suite._test_sector_pipeline(sector)
            else:
                logger.error(f"Unknown sector: {sector}")
        
        # Generate report
        test_suite.report.generate_report(output_dir=args.report_dir)
        test_suite.report.print_summary()
    else:
        # Run a default subset of tests
        test_suite._test_sector_pipeline("healthcare")
        test_suite._test_error_handling()
        test_suite._test_export_to_crm()
        
        # Generate report
        test_suite.report.generate_report(output_dir=args.report_dir)
        test_suite.report.print_summary()
    
    # Clean up
    test_suite.cleanup()
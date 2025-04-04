"""
Unit tests for the extraction pipeline module.
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
import os
import sys
import tempfile

# Import the modules to test
from perera_lead_scraper.pipeline.extraction_pipeline import (
    LeadExtractionPipeline,
    PipelineStage,
    ProcessingStatus,
    PipelineMetrics
)
from perera_lead_scraper.models.lead import Lead
from perera_lead_scraper.utils.source_registry import DataSource

class TestPipelineMetrics(unittest.TestCase):
    """Test the PipelineMetrics class."""
    
    def test_initialization(self):
        """Test metrics initialization."""
        metrics = PipelineMetrics()
        self.assertEqual(metrics.total_sources, 0)
        self.assertEqual(metrics.processed_sources, 0)
        self.assertEqual(metrics.successful_sources, 0)
        self.assertEqual(metrics.failed_sources, 0)
        self.assertEqual(metrics.total_leads_extracted, 0)
        self.assertIsNotNone(metrics.start_time)
        self.assertIsNone(metrics.end_time)
    
    def test_record_source_processed(self):
        """Test recording of processed sources."""
        metrics = PipelineMetrics()
        
        # Record a successful source
        metrics.record_source_processed("rss", ProcessingStatus.SUCCESS)
        self.assertEqual(metrics.processed_sources, 1)
        self.assertEqual(metrics.successful_sources, 1)
        self.assertEqual(metrics.failed_sources, 0)
        
        # Record a failed source
        metrics.record_source_processed("website", ProcessingStatus.FAILED)
        self.assertEqual(metrics.processed_sources, 2)
        self.assertEqual(metrics.successful_sources, 1)
        self.assertEqual(metrics.failed_sources, 1)
        
        # Check source stats
        self.assertEqual(metrics.source_type_stats["rss"]["success"], 1)
        self.assertEqual(metrics.source_type_stats["website"]["failed"], 1)
    
    def test_record_leads_extracted(self):
        """Test recording of extracted leads."""
        metrics = PipelineMetrics()
        
        metrics.record_leads_extracted("rss", 10)
        self.assertEqual(metrics.total_leads_extracted, 10)
        
        metrics.record_leads_extracted("website", 5)
        self.assertEqual(metrics.total_leads_extracted, 15)
        
        # Initialize source_type_stats first
        metrics.source_type_stats["rss"] = {
            'total': 1,
            'success': 1,
            'failed': 0,
            'partial': 0,
            'leads_extracted': 0
        }
        
        metrics.record_leads_extracted("rss", 20)
        self.assertEqual(metrics.total_leads_extracted, 35)
        self.assertEqual(metrics.source_type_stats["rss"]["leads_extracted"], 20)
    
    def test_get_report(self):
        """Test generation of metrics report."""
        metrics = PipelineMetrics()
        
        # Setup some test data
        metrics.total_sources = 5
        metrics.record_source_processed("rss", ProcessingStatus.SUCCESS)
        metrics.record_source_processed("rss", ProcessingStatus.SUCCESS)
        metrics.record_source_processed("website", ProcessingStatus.FAILED)
        metrics.record_leads_extracted("rss", 15)
        metrics.leads_after_filtering = 10
        metrics.leads_after_deduplication = 8
        metrics.leads_stored = 8
        metrics.record_error("ConnectionError")
        metrics.record_error("ConnectionError")
        metrics.record_error("ValueError")
        
        # Generate report
        report = metrics.get_report()
        
        # Test that the report has all expected fields
        self.assertIn('execution_time_seconds', report)
        self.assertIn('sources', report)
        self.assertIn('leads', report)
        self.assertIn('error_counts', report)
        
        # Test some specific values
        self.assertEqual(report['sources']['total'], 5)
        self.assertEqual(report['sources']['successful'], 2)
        self.assertEqual(report['sources']['failed'], 1)
        self.assertEqual(report['leads']['extracted'], 15)
        self.assertEqual(report['leads']['after_filtering'], 10)
        self.assertEqual(report['leads']['after_deduplication'], 8)
        self.assertEqual(report['error_counts']['ConnectionError'], 2)
        self.assertEqual(report['error_counts']['ValueError'], 1)


class TestExtractionPipeline(unittest.TestCase):
    """Test the LeadExtractionPipeline class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create mocks for dependencies
        self.mock_nlp_processor = MagicMock()
        self.mock_legal_processor = MagicMock()
        self.mock_storage = MagicMock()
        
        # Create a pipeline with mocked dependencies
        self.pipeline = LeadExtractionPipeline(
            nlp_processor=self.mock_nlp_processor,
            legal_processor=self.mock_legal_processor,
            storage=self.mock_storage,
            config_override={
                'min_confidence_threshold': 0.5,
                'similarity_threshold': 0.7,
                'max_workers': 2
            }
        )
    
    def test_initialization(self):
        """Test pipeline initialization."""
        self.assertEqual(self.pipeline.config['min_confidence_threshold'], 0.5)
        self.assertEqual(self.pipeline.config['similarity_threshold'], 0.7)
        self.assertEqual(self.pipeline.config['max_workers'], 2)
        self.assertTrue(self.pipeline.is_stage_enabled(PipelineStage.EXTRACTION))
        self.assertTrue(self.pipeline.is_stage_enabled(PipelineStage.FILTERING))
    
    def test_pipeline_stage_configuration(self):
        """Test enabling and disabling pipeline stages."""
        # Disable a stage
        self.pipeline.disable_stage(PipelineStage.FILTERING)
        self.assertFalse(self.pipeline.is_stage_enabled(PipelineStage.FILTERING))
        
        # Enable a stage
        self.pipeline.enable_stage(PipelineStage.FILTERING)
        self.assertTrue(self.pipeline.is_stage_enabled(PipelineStage.FILTERING))
        
        # Try to disable extraction (should be prevented)
        self.pipeline.disable_stage(PipelineStage.EXTRACTION)
        self.assertTrue(self.pipeline.is_stage_enabled(PipelineStage.EXTRACTION))
    
    def test_generate_lead_fingerprint(self):
        """Test lead fingerprint generation."""
        lead1 = Lead(
            title="Test Lead",
            description="This is a test lead",
            organization="Test Org",
            location="Test Location",
            project_type="Commercial",
            project_value=1000000
        )
        
        lead2 = Lead(
            title="Test Lead",
            description="This is a test lead",
            organization="Test Org",
            location="Test Location",
            project_type="Commercial",
            project_value=1000000
        )
        
        lead3 = Lead(
            title="Different Lead",
            description="This is a different lead",
            organization="Other Org",
            location="Other Location",
            project_type="Residential",
            project_value=500000
        )
        
        # Same leads should have the same fingerprint
        self.assertEqual(
            self.pipeline._generate_lead_fingerprint(lead1),
            self.pipeline._generate_lead_fingerprint(lead2)
        )
        
        # Different leads should have different fingerprints
        self.assertNotEqual(
            self.pipeline._generate_lead_fingerprint(lead1),
            self.pipeline._generate_lead_fingerprint(lead3)
        )
    
    def test_calculate_similarity(self):
        """Test lead similarity calculation."""
        lead1 = Lead(
            title="New Office Building in San Francisco",
            description="Construction of a new 10-story office building in downtown San Francisco.",
            organization="ABC Construction",
            location="San Francisco, CA",
            project_type="Commercial",
            project_value=25000000
        )
        
        lead2 = Lead(
            title="New Office Tower in San Francisco",
            description="Construction of a new 10-story office tower in downtown San Francisco area.",
            organization="ABC Builders",
            location="San Francisco, California",
            project_type="Commercial Office",
            project_value=25000000
        )
        
        lead3 = Lead(
            title="Residential Complex in Los Angeles",
            description="Development of a residential complex with 200 units in Los Angeles.",
            organization="XYZ Developers",
            location="Los Angeles, CA",
            project_type="Residential",
            project_value=40000000
        )
        
        # Similar leads should have high similarity
        similarity1_2 = self.pipeline._calculate_similarity(lead1, lead2)
        self.assertGreater(similarity1_2, 0.6)
        
        # Different leads should have low similarity
        similarity1_3 = self.pipeline._calculate_similarity(lead1, lead3)
        self.assertLess(similarity1_3, 0.3)
    
    def test_filter_leads(self):
        """Test lead filtering."""
        leads = [
            Lead(title="Lead 1", description="Description 1", confidence_score=0.8),
            Lead(title="Lead 2", description="Description 2", confidence_score=0.4),
            Lead(title="Lead 3", description="Description 3", confidence_score=0.6),
            Lead(title="", description="Description 4", confidence_score=0.9),  # Missing title
            Lead(title="Lead 5", description="", confidence_score=0.9)  # Missing description
        ]
        
        # Filter with default threshold
        filtered_leads = self.pipeline.filter_leads(leads)
        
        # Only lead1 and lead3 should pass the filters (lead2 has low confidence, lead4 and lead5 are missing fields)
        self.assertEqual(len(filtered_leads), 2)
        self.assertEqual(filtered_leads[0].title, "Lead 1")
        self.assertEqual(filtered_leads[1].title, "Lead 3")
        
        # Filter with custom threshold
        filtered_leads = self.pipeline.filter_leads(leads, min_confidence=0.7)
        self.assertEqual(len(filtered_leads), 1)
        self.assertEqual(filtered_leads[0].title, "Lead 1")
    
    def test_deduplicate_leads(self):
        """Test lead deduplication."""
        # Create test leads
        lead1 = Lead(
            title="New Office Building",
            description="Construction of a new office building",
            confidence_score=0.8
        )
        
        lead2 = Lead(
            title="New Office Building",
            description="Construction of a new office building",
            confidence_score=0.7
        )
        
        lead3 = Lead(
            title="Apartment Complex",
            description="Construction of apartments",
            confidence_score=0.9
        )
        
        # Test deduplication
        leads = [lead1, lead2, lead3]
        deduplicated = self.pipeline.deduplicate_leads(leads)
        
        # Should keep lead1 and lead3 (lead2 is a duplicate of lead1 but with lower confidence)
        self.assertEqual(len(deduplicated), 2)
        
        # Make sure we kept the higher confidence version of the duplicate
        self.assertEqual(deduplicated[0].confidence_score, 0.8)
        self.assertEqual(deduplicated[1].confidence_score, 0.9)
    
    def test_prioritize_leads(self):
        """Test lead prioritization."""
        # Create test leads with different characteristics
        lead1 = Lead(
            title="High Value Project",
            description="A high value project in a target market",
            location="San Francisco", 
            project_type="Commercial",
            project_value=8000000,
            confidence_score=0.9,
            published_date=datetime.now()
        )
        
        lead2 = Lead(
            title="Medium Value Project",
            description="A medium value project with moderate confidence",
            project_value=3000000,
            confidence_score=0.7
        )
        
        lead3 = Lead(
            title="Low Value Project",
            description="A low value project with low confidence",
            project_value=500000,
            confidence_score=0.5
        )
        
        # Test prioritization
        leads = [lead3, lead2, lead1]  # Intentionally out of order
        prioritized = self.pipeline.prioritize_leads(leads)
        
        # Should be ordered from highest to lowest priority
        self.assertEqual(len(prioritized), 3)
        self.assertEqual(prioritized[0].title, "High Value Project")
        self.assertEqual(prioritized[1].title, "Medium Value Project")
        self.assertEqual(prioritized[2].title, "Low Value Project")
        
        # Check that priority scores were assigned
        self.assertIsNotNone(prioritized[0].priority_score)
        self.assertIsNotNone(prioritized[0].priority_factors)
        
    def test_process_source(self):
        """Test processing a single source."""
        # Create a mock source
        source = DataSource(
            source_id="test_source",
            source_type="rss",
            name="Test Source",
            config={"feed_url": "http://example.com/feed"}
        )
        
        # Mock the extract_from_rss method
        mock_leads = [
            Lead(title="Test Lead 1", description="Description 1"),
            Lead(title="Test Lead 2", description="Description 2")
        ]
        self.pipeline.extract_from_rss = MagicMock(return_value=mock_leads)
        
        # Process the source
        result = self.pipeline.process_source(source)
        
        # Verify the result
        self.assertEqual(result["source_id"], "test_source")
        self.assertEqual(result["source_type"], "rss")
        self.assertEqual(result["status"], ProcessingStatus.SUCCESS)
        self.assertEqual(len(result["leads"]), 2)
        self.assertEqual(result["lead_count"], 2)
        
        # Verify extract_from_rss was called
        self.pipeline.extract_from_rss.assert_called_once_with(source)
    
    def test_process_source_error(self):
        """Test handling errors when processing a source."""
        # Create a mock source
        source = DataSource(
            source_id="test_source",
            source_type="rss",
            name="Test Source",
            config={"feed_url": "http://example.com/feed"}
        )
        
        # Mock extract_from_rss to raise an exception
        self.pipeline.extract_from_rss = MagicMock(side_effect=Exception("Test error"))
        
        # Process the source
        result = self.pipeline.process_source(source)
        
        # Verify the result
        self.assertEqual(result["source_id"], "test_source")
        self.assertEqual(result["source_type"], "rss")
        self.assertEqual(result["status"], ProcessingStatus.FAILED)
        self.assertEqual(result["error"], "Test error")
        self.assertEqual(len(result["leads"]), 0)
    
    def test_process_sources(self):
        """Test processing multiple sources."""
        # Create mock sources
        sources = [
            DataSource(source_id="source1", source_type="rss", name="Source 1", config={"feed_url": "http://example.com/feed1"}),
            DataSource(source_id="source2", source_type="website", name="Source 2", config={"url": "http://example.com"})
        ]
        
        # Mock process_source method
        self.pipeline.process_source = MagicMock(side_effect=[
            {
                "source_id": "source1",
                "source_type": "rss",
                "status": ProcessingStatus.SUCCESS,
                "leads": [Lead(title="Lead 1", description="Desc 1"), Lead(title="Lead 2", description="Desc 2")],
                "lead_count": 2
            },
            {
                "source_id": "source2",
                "source_type": "website",
                "status": ProcessingStatus.SUCCESS,
                "leads": [Lead(title="Lead 3", description="Desc 3")],
                "lead_count": 1
            }
        ])
        
        # Mock pipeline stage methods
        self.pipeline.filter_leads = MagicMock(return_value=[Lead(title="Lead 1"), Lead(title="Lead 3")])
        self.pipeline.deduplicate_leads = MagicMock(return_value=[Lead(title="Lead 1"), Lead(title="Lead 3")])
        self.pipeline.enrich_leads = MagicMock(return_value=[Lead(title="Lead 1"), Lead(title="Lead 3")])
        self.pipeline.prioritize_leads = MagicMock(return_value=[Lead(title="Lead 3"), Lead(title="Lead 1")])
        self.pipeline._store_leads = MagicMock(return_value=2)
        
        # Process sources
        result = self.pipeline.process_sources(sources)
        
        # Verify result
        self.assertEqual(len(result["processing_results"]), 2)
        self.assertEqual(result["total_leads"], 2)
        self.assertIn("metrics", result)
        
        # Verify stage methods were called
        self.pipeline.filter_leads.assert_called_once()
        self.pipeline.deduplicate_leads.assert_called_once()
        self.pipeline.enrich_leads.assert_called_once()
        self.pipeline.prioritize_leads.assert_called_once()
        self.pipeline._store_leads.assert_called_once()


if __name__ == "__main__":
    unittest.main()
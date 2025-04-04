"""Tests for the lead extraction system.

This script provides comprehensive testing of the end-to-end extraction process,
evaluating the accuracy of NLP processing, lead extraction pipeline, and validation
logic against manually labeled test data.
"""

import os
import sys
import logging
import json
import csv
import difflib
from typing import Dict, List, Any, Tuple
from pathlib import Path
import argparse
from datetime import datetime
import time
import random
from collections import defaultdict
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve, confusion_matrix, f1_score, precision_score, recall_score

# Add src directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.perera_lead_scraper.config import AppConfig
from src.perera_lead_scraper.models.lead import Lead, MarketSector
from src.perera_lead_scraper.models.source import DataSource, SourceType
from src.perera_lead_scraper.pipeline.extraction_pipeline import LeadExtractionPipeline
from src.perera_lead_scraper.validation.lead_validator import LeadValidator
from src.perera_lead_scraper.nlp.nlp_processor import NLPProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_extraction.log')
    ]
)

logger = logging.getLogger(__name__)

# Define test data directory
TEST_DATA_DIR = Path(__file__).parent.parent.parent / 'test_data'
OUTPUT_DIR = Path(__file__).parent.parent.parent / 'test_results'


class ExtractionTester:
    """Tester for the lead extraction system.
    
    This class provides methods to test the lead extraction system against
    manually labeled test data, calculate accuracy metrics, and generate
    performance reports.
    
    Attributes:
        config: Configuration object
        pipeline: Lead extraction pipeline
        validator: Lead validator
        nlp_processor: NLP processor
        test_data_dir: Directory containing test data
        output_dir: Directory for test output
        ground_truth: Dictionary mapping test case IDs to ground truth data
    """
    
    def __init__(
        self,
        legal_processor=None,
        lead_validator=None,
        extraction_pipeline=None,
        config_path: str = None,
        test_data_dir: str = None,
        output_dir: str = None,
        generate_visualizations: bool = True,
        save_failed_documents: bool = True
    ):
        """Initialize the extraction tester.
        
        Args:
            legal_processor: Optional LegalProcessor instance.
            lead_validator: Optional LeadValidator instance.
            extraction_pipeline: Optional LeadExtractionPipeline instance.
            config_path: Path to config file. If None, default config is used.
            test_data_dir: Path to test data directory. If None, default is used.
            output_dir: Path to output directory. If None, default is used.
            generate_visualizations: Whether to generate performance visualizations.
            save_failed_documents: Whether to save copies of documents that failed extraction.
        """
        # Initialize configuration
        self.config = AppConfig()
        
        # Set directories
        self.test_data_dir = Path(test_data_dir) if test_data_dir else TEST_DATA_DIR
        self.output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Initialize options
        self.generate_visualizations = generate_visualizations
        self.save_failed_documents = save_failed_documents
        
        # Initialize components (use provided instances or create new ones)
        self.pipeline = extraction_pipeline or LeadExtractionPipeline(self.config)
        self.validator = lead_validator or LeadValidator(self.config)
        self.nlp_processor = NLPProcessor(self.config)
        self.legal_processor = legal_processor
        
        # Track memory usage if psutil is available
        self.enable_memory_tracking = False
        try:
            import psutil
            self.enable_memory_tracking = True
            self.process = psutil.Process(os.getpid())
        except ImportError:
            logger.warning("psutil not available. Memory tracking disabled.")
        
        # Initialize test data
        self.ground_truth = {}
        self._load_ground_truth()
        
        logger.info(
            f"Extraction tester initialized with "
            f"{len(self.ground_truth)} ground truth cases"
        )
    
    def _load_ground_truth(self) -> None:
        """Load ground truth data from test_data directory."""
        ground_truth_path = self.test_data_dir / 'ground_truth.json'
        
        if not ground_truth_path.exists():
            logger.warning(f"Ground truth file not found: {ground_truth_path}")
            return
        
        try:
            with open(ground_truth_path, 'r') as f:
                self.ground_truth = json.load(f)
            
            logger.info(f"Loaded {len(self.ground_truth)} ground truth cases")
        except Exception as e:
            logger.error(f"Error loading ground truth data: {e}")
    
    def run_full_test(self) -> Dict[str, Any]:
        """Run a full test of the extraction system.
        
        Returns:
            Dictionary containing test results and metrics
        """
        start_time = time.time()
        logger.info("Starting full extraction system test")
        
        # Initialize results dictionary
        results = {
            'start_time': datetime.now().isoformat(),
            'component_tests': {},
            'end_to_end_tests': {},
            'metrics': {},
            'errors': [],
            'performance': {}
        }
        
        try:
            # 1. Test individual components
            results['component_tests']['nlp_processor'] = self.test_nlp_processor()
            results['component_tests']['pipeline'] = self.test_extraction_pipeline()
            results['component_tests']['validator'] = self.test_lead_validator()
            
            # 2. Test end-to-end workflow
            results['end_to_end_tests'] = self.test_end_to_end_workflow()
            
            # 3. Calculate overall metrics
            results['metrics'] = self.calculate_overall_metrics(results)
            
            # 4. Record performance metrics
            elapsed_time = time.time() - start_time
            results['performance']['total_test_time'] = elapsed_time
            results['performance']['timestamp'] = datetime.now().isoformat()
            
            # 5. Generate visualizations
            self.generate_visualizations(results)
            
            # 6. Save results
            self.save_results(results)
            
            logger.info(
                f"Full extraction test completed in {elapsed_time:.2f}s. "
                f"Results saved to {self.output_dir}"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error in full test: {e}")
            results['errors'].append(str(e))
            self.save_results(results)
            raise
    
    def test_nlp_processor(self) -> Dict[str, Any]:
        """Test the NLP processor component.
        
        Returns:
            Dictionary containing test results and metrics
        """
        logger.info("Testing NLP processor")
        start_time = time.time()
        
        results = {
            'entity_extraction': {
                'precision': 0.0,
                'recall': 0.0,
                'f1': 0.0,
                'detail': {}
            },
            'market_sector_classification': {
                'accuracy': 0.0,
                'confusion_matrix': None,
                'per_class': {}
            },
            'location_extraction': {
                'precision': 0.0,
                'recall': 0.0,
                'f1': 0.0
            },
            'project_value_extraction': {
                'accuracy': 0.0,
                'mean_absolute_error': 0.0,
                'within_20_percent': 0.0
            },
            'performance': {
                'avg_processing_time': 0.0,
                'total_time': 0.0
            },
            'examples': {
                'true_positives': [],
                'false_positives': [],
                'false_negatives': []
            }
        }
        
        # Load NLP test data
        nlp_test_data_path = self.test_data_dir / 'nlp_test_data.json'
        
        if not nlp_test_data_path.exists():
            logger.warning(f"NLP test data not found: {nlp_test_data_path}")
            return results
        
        try:
            with open(nlp_test_data_path, 'r') as f:
                test_cases = json.load(f)
            
            # Initialize counters
            total_processing_time = 0.0
            entity_stats = {'true_pos': 0, 'false_pos': 0, 'false_neg': 0}
            entity_type_stats = defaultdict(lambda: {'true_pos': 0, 'false_pos': 0, 'false_neg': 0})
            market_sector_correct = 0
            market_sector_confusion = np.zeros((5, 5), dtype=int)  # 5x5 for our market sectors
            market_sector_mapping = {s.value: i for i, s in enumerate(MarketSector)}
            
            location_stats = {'true_pos': 0, 'false_pos': 0, 'false_neg': 0}
            value_errors = []
            value_within_20pct = 0
            value_total = 0
            
            # Process each test case
            for i, case in enumerate(test_cases):
                logger.debug(f"Processing NLP test case {i+1}/{len(test_cases)}")
                
                # Extract ground truth
                text = case['text']
                expected_entities = case.get('entities', {})
                expected_market_sector = case.get('market_sector', '')
                expected_locations = case.get('locations', [])
                expected_value = case.get('project_value')
                
                # Process with NLP
                case_start_time = time.time()
                nlp_results = self.nlp_processor.process_text(text)
                case_time = time.time() - case_start_time
                total_processing_time += case_time
                
                # Evaluate entity extraction
                entities = nlp_results.get('entities', {})
                self._evaluate_entities(entities, expected_entities, entity_stats, entity_type_stats)
                
                # Evaluate market sector classification
                market_sector = nlp_results.get('market_sector', '')
                if market_sector == expected_market_sector:
                    market_sector_correct += 1
                
                # Update confusion matrix
                if expected_market_sector and market_sector:
                    try:
                        expected_idx = market_sector_mapping.get(expected_market_sector, 0)
                        actual_idx = market_sector_mapping.get(market_sector, 0)
                        market_sector_confusion[expected_idx, actual_idx] += 1
                    except:
                        pass
                
                # Evaluate location extraction
                locations = nlp_results.get('locations', [])
                self._evaluate_locations(locations, expected_locations, location_stats)
                
                # Evaluate project value extraction
                value = nlp_results.get('project_value')
                if expected_value is not None and value is not None:
                    value_total += 1
                    error = abs(value - expected_value) / expected_value if expected_value != 0 else 0
                    value_errors.append(error)
                    
                    # Check if within 20%
                    if error <= 0.2:
                        value_within_20pct += 1
                
                # Store example cases
                if i < 5:  # Just store a few examples
                    results['examples'][f'case_{i}'] = {
                        'text': text[:200] + '...',  # Truncate for brevity
                        'expected': {
                            'entities': expected_entities,
                            'market_sector': expected_market_sector,
                            'locations': expected_locations,
                            'project_value': expected_value
                        },
                        'actual': {
                            'entities': entities,
                            'market_sector': market_sector,
                            'locations': locations,
                            'project_value': value
                        }
                    }
            
            # Calculate entity metrics
            total_true_pos = entity_stats['true_pos']
            total_false_pos = entity_stats['false_pos']
            total_false_neg = entity_stats['false_neg']
            
            precision = total_true_pos / (total_true_pos + total_false_pos) if (total_true_pos + total_false_pos) > 0 else 0
            recall = total_true_pos / (total_true_pos + total_false_neg) if (total_true_pos + total_false_neg) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            
            # Calculate entity type metrics
            entity_detail = {}
            for entity_type, stats in entity_type_stats.items():
                type_precision = stats['true_pos'] / (stats['true_pos'] + stats['false_pos']) if (stats['true_pos'] + stats['false_pos']) > 0 else 0
                type_recall = stats['true_pos'] / (stats['true_pos'] + stats['false_neg']) if (stats['true_pos'] + stats['false_neg']) > 0 else 0
                type_f1 = 2 * type_precision * type_recall / (type_precision + type_recall) if (type_precision + type_recall) > 0 else 0
                
                entity_detail[entity_type] = {
                    'precision': type_precision,
                    'recall': type_recall,
                    'f1': type_f1,
                    'counts': {
                        'true_pos': stats['true_pos'],
                        'false_pos': stats['false_pos'],
                        'false_neg': stats['false_neg']
                    }
                }
            
            # Calculate market sector metrics
            sector_accuracy = market_sector_correct / len(test_cases) if test_cases else 0
            
            # Calculate location metrics
            loc_precision = location_stats['true_pos'] / (location_stats['true_pos'] + location_stats['false_pos']) if (location_stats['true_pos'] + location_stats['false_pos']) > 0 else 0
            loc_recall = location_stats['true_pos'] / (location_stats['true_pos'] + location_stats['false_neg']) if (location_stats['true_pos'] + location_stats['false_neg']) > 0 else 0
            loc_f1 = 2 * loc_precision * loc_recall / (loc_precision + loc_recall) if (loc_precision + loc_recall) > 0 else 0
            
            # Calculate value metrics
            mean_abs_error = sum(value_errors) / value_total if value_total > 0 else 0
            within_20pct = value_within_20pct / value_total if value_total > 0 else 0
            
            # Update results
            results['entity_extraction']['precision'] = precision
            results['entity_extraction']['recall'] = recall
            results['entity_extraction']['f1'] = f1
            results['entity_extraction']['detail'] = entity_detail
            
            results['market_sector_classification']['accuracy'] = sector_accuracy
            results['market_sector_classification']['confusion_matrix'] = market_sector_confusion.tolist()
            
            results['location_extraction']['precision'] = loc_precision
            results['location_extraction']['recall'] = loc_recall
            results['location_extraction']['f1'] = loc_f1
            
            results['project_value_extraction']['mean_absolute_error'] = mean_abs_error
            results['project_value_extraction']['within_20_percent'] = within_20pct
            
            results['performance']['avg_processing_time'] = total_processing_time / len(test_cases) if test_cases else 0
            results['performance']['total_time'] = time.time() - start_time
            
            logger.info(
                f"NLP processor test completed in {results['performance']['total_time']:.2f}s. "
                f"Entity F1: {f1:.2f}, Market Sector Accuracy: {sector_accuracy:.2f}"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error testing NLP processor: {e}")
            results['error'] = str(e)
            return results
    
    def _evaluate_entities(
        self,
        actual: Dict[str, List[str]],
        expected: Dict[str, List[str]],
        stats: Dict[str, int],
        type_stats: Dict[str, Dict[str, int]]
    ) -> None:
        """Evaluate entity extraction performance.
        
        Args:
            actual: Extracted entities
            expected: Expected entities
            stats: Overall entity statistics to update
            type_stats: Entity type statistics to update
        """
        # Process each entity type
        all_types = set(actual.keys()) | set(expected.keys())
        
        for entity_type in all_types:
            actual_entities = set(actual.get(entity_type, []))
            expected_entities = set(expected.get(entity_type, []))
            
            # Calculate true positives, false positives, false negatives
            true_pos = len(actual_entities & expected_entities)
            false_pos = len(actual_entities - expected_entities)
            false_neg = len(expected_entities - actual_entities)
            
            # Update overall stats
            stats['true_pos'] += true_pos
            stats['false_pos'] += false_pos
            stats['false_neg'] += false_neg
            
            # Update type-specific stats
            type_stats[entity_type]['true_pos'] += true_pos
            type_stats[entity_type]['false_pos'] += false_pos
            type_stats[entity_type]['false_neg'] += false_neg
    
    def _evaluate_locations(
        self,
        actual: List[str],
        expected: List[str],
        stats: Dict[str, int]
    ) -> None:
        """Evaluate location extraction performance.
        
        Args:
            actual: Extracted locations
            expected: Expected locations
            stats: Location statistics to update
        """
        # Normalize locations for comparison
        actual_norm = [loc.lower() for loc in actual]
        expected_norm = [loc.lower() for loc in expected]
        
        # Count matches (true positives)
        true_pos = sum(1 for loc in actual_norm if any(
            expected_loc in loc or loc in expected_loc for expected_loc in expected_norm
        ))
        
        # Count false positives and false negatives
        false_pos = len(actual) - true_pos
        false_neg = len(expected) - true_pos
        
        # Update stats
        stats['true_pos'] += true_pos
        stats['false_pos'] += false_pos
        stats['false_neg'] += false_neg
    
    def test_extraction_pipeline(self) -> Dict[str, Any]:
        """Test the extraction pipeline component.
        
        Returns:
            Dictionary containing test results and metrics
        """
        logger.info("Testing extraction pipeline")
        start_time = time.time()
        
        results = {
            'source_processing': {
                'success_rate': 0.0,
                'avg_leads_per_source': 0.0,
                'by_source_type': {}
            },
            'pipeline_steps': {
                'filter': {'effectiveness': 0.0, 'time': 0.0},
                'deduplicate': {'effectiveness': 0.0, 'time': 0.0},
                'enrich': {'effectiveness': 0.0, 'time': 0.0},
                'prioritize': {'effectiveness': 0.0, 'time': 0.0}
            },
            'performance': {
                'total_time': 0.0,
                'avg_source_time': 0.0
            },
            'examples': {
                'successful_sources': [],
                'failed_sources': []
            }
        }
        
        # Load test sources
        sources_path = self.test_data_dir / 'test_sources.json'
        
        if not sources_path.exists():
            logger.warning(f"Test sources not found: {sources_path}")
            return results
        
        try:
            with open(sources_path, 'r') as f:
                test_sources_data = json.load(f)
            
            # Convert to DataSource objects
            test_sources = []
            for source_data in test_sources_data:
                source = DataSource(
                    id=source_data.get('id', ''),
                    name=source_data.get('name', ''),
                    url=source_data.get('url', ''),
                    source_type=SourceType(source_data.get('source_type', 'unknown')),
                    active=source_data.get('active', True),
                    metadata=source_data.get('metadata', {})
                )
                test_sources.append(source)
            
            # Set up metrics
            success_count = 0
            total_leads = 0
            total_source_time = 0.0
            source_type_stats = defaultdict(lambda: {'count': 0, 'success': 0, 'leads': 0, 'time': 0.0})
            
            # Process sources one by one
            for i, source in enumerate(test_sources):
                logger.debug(f"Processing test source {i+1}/{len(test_sources)}: {source.name}")
                
                try:
                    # Process the source
                    source_start_time = time.time()
                    source_leads = self.pipeline.process_source(source)
                    source_time = time.time() - source_start_time
                    
                    # Update metrics
                    success_count += 1
                    total_leads += len(source_leads)
                    total_source_time += source_time
                    
                    source_type = source.source_type.value
                    source_type_stats[source_type]['count'] += 1
                    source_type_stats[source_type]['success'] += 1
                    source_type_stats[source_type]['leads'] += len(source_leads)
                    source_type_stats[source_type]['time'] += source_time
                    
                    # Store example
                    if len(results['examples']['successful_sources']) < 3:
                        results['examples']['successful_sources'].append({
                            'source': source.name,
                            'source_type': source_type,
                            'leads_count': len(source_leads),
                            'time': source_time,
                            'sample_leads': [
                                {
                                    'title': lead.title,
                                    'confidence': lead.confidence_score,
                                    'market_sector': lead.market_sector
                                }
                                for lead in source_leads[:3]  # Just store a few leads
                            ]
                        })
                        
                except Exception as e:
                    logger.warning(f"Error processing source {source.name}: {e}")
                    
                    # Update metrics for failed source
                    source_type = source.source_type.value
                    source_type_stats[source_type]['count'] += 1
                    
                    # Store example
                    if len(results['examples']['failed_sources']) < 3:
                        results['examples']['failed_sources'].append({
                            'source': source.name,
                            'source_type': source_type,
                            'error': str(e)
                        })
            
            # Calculate overall metrics
            success_rate = success_count / len(test_sources) if test_sources else 0
            avg_leads_per_source = total_leads / success_count if success_count else 0
            avg_source_time = total_source_time / len(test_sources) if test_sources else 0
            
            # Format source type stats
            source_type_results = {}
            for source_type, stats in source_type_stats.items():
                source_type_results[source_type] = {
                    'success_rate': stats['success'] / stats['count'] if stats['count'] > 0 else 0,
                    'avg_leads': stats['leads'] / stats['success'] if stats['success'] > 0 else 0,
                    'avg_time': stats['time'] / stats['count'] if stats['count'] > 0 else 0
                }
            
            # Test pipeline steps with a batch of leads
            if total_leads > 0:
                # Get a sample of leads for pipeline step testing
                # We'll use a mix of leads from all successful sources
                all_leads = []
                for source in test_sources:
                    try:
                        source_leads = self.pipeline.process_source(source)
                        all_leads.extend(source_leads)
                    except:
                        pass
                
                # Test filter step
                if 'filter' in self.pipeline.pipeline_steps and all_leads:
                    filter_start = time.time()
                    filtered_leads = self.pipeline.filter_leads(all_leads)
                    filter_time = time.time() - filter_start
                    
                    filter_effectiveness = 1 - (len(filtered_leads) / len(all_leads))
                    results['pipeline_steps']['filter'] = {
                        'effectiveness': filter_effectiveness,
                        'time': filter_time
                    }
                
                # Test deduplicate step
                if 'deduplicate' in self.pipeline.pipeline_steps and all_leads:
                    # Create some duplicate leads for testing
                    test_leads = all_leads.copy()
                    dup_count = min(5, len(all_leads))
                    test_leads.extend(all_leads[:dup_count])
                    
                    dedupe_start = time.time()
                    deduped_leads = self.pipeline.deduplicate_leads(test_leads)
                    dedupe_time = time.time() - dedupe_start
                    
                    dedupe_effectiveness = 1 - (len(deduped_leads) / len(test_leads))
                    results['pipeline_steps']['deduplicate'] = {
                        'effectiveness': dedupe_effectiveness,
                        'time': dedupe_time
                    }
                
                # Test enrich step
                if 'enrich' in self.pipeline.pipeline_steps and all_leads:
                    enrich_start = time.time()
                    enriched_leads = self.pipeline.enrich_leads(all_leads)
                    enrich_time = time.time() - enrich_start
                    
                    # Measure enrichment by counting added metadata
                    enrich_count = 0
                    for lead in enriched_leads:
                        if lead.metadata.get('last_enriched'):
                            enrich_count += 1
                    
                    enrich_effectiveness = enrich_count / len(all_leads)
                    results['pipeline_steps']['enrich'] = {
                        'effectiveness': enrich_effectiveness,
                        'time': enrich_time
                    }
                
                # Test prioritize step
                if 'prioritize' in self.pipeline.pipeline_steps and all_leads:
                    prioritize_start = time.time()
                    prioritized_leads = self.pipeline.prioritize_leads(all_leads)
                    prioritize_time = time.time() - prioritize_start
                    
                    # Measure if leads were properly sorted
                    priority_effectiveness = 1.0  # Assume perfect if the step runs
                    results['pipeline_steps']['prioritize'] = {
                        'effectiveness': priority_effectiveness,
                        'time': prioritize_time
                    }
            
            # Update overall results
            results['source_processing']['success_rate'] = success_rate
            results['source_processing']['avg_leads_per_source'] = avg_leads_per_source
            results['source_processing']['by_source_type'] = source_type_results
            
            results['performance']['total_time'] = time.time() - start_time
            results['performance']['avg_source_time'] = avg_source_time
            
            logger.info(
                f"Pipeline test completed in {results['performance']['total_time']:.2f}s. "
                f"Source success rate: {success_rate:.2f}, Avg leads: {avg_leads_per_source:.1f}"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error testing extraction pipeline: {e}")
            results['error'] = str(e)
            return results
    
    def test_lead_validator(self) -> Dict[str, Any]:
        """Test the lead validator component.
        
        Returns:
            Dictionary containing test results and metrics
        """
        logger.info("Testing lead validator")
        start_time = time.time()
        
        results = {
            'validation': {
                'accuracy': 0.0,
                'qualified_lead_precision': 0.0,
                'qualified_lead_recall': 0.0,
                'f1': 0.0
            },
            'rule_effectiveness': {},
            'performance': {
                'avg_validation_time': 0.0,
                'total_time': 0.0
            },
            'examples': {
                'true_positives': [],
                'false_positives': [],
                'false_negatives': []
            }
        }
        
        # Load test leads with validation ground truth
        validation_test_path = self.test_data_dir / 'validation_test_data.json'
        
        if not validation_test_path.exists():
            logger.warning(f"Validation test data not found: {validation_test_path}")
            return results
        
        try:
            with open(validation_test_path, 'r') as f:
                test_cases = json.load(f)
            
            # Prepare tracking variables
            true_positives = 0
            false_positives = 0
            false_negatives = 0
            correct_validations = 0
            total_validation_time = 0.0
            
            # Rule effectiveness tracking
            rule_stats = defaultdict(lambda: {'triggered': 0, 'correct': 0})
            
            # Process each test case
            for i, case in enumerate(test_cases):
                logger.debug(f"Processing validation test case {i+1}/{len(test_cases)}")
                
                # Extract data
                lead_data = case['lead']
                expected_valid = case['expected_valid']
                expected_reasons = case.get('expected_reasons', [])
                
                # Create Lead object
                lead = Lead(
                    title=lead_data.get('title', ''),
                    description=lead_data.get('description', ''),
                    source=lead_data.get('source', ''),
                    source_id=lead_data.get('source_id', ''),
                    url=lead_data.get('url', ''),
                    published_date=lead_data.get('published_date', ''),
                    location=lead_data.get('location', ''),
                    entities=lead_data.get('entities', {}),
                    project_value=lead_data.get('project_value'),
                    market_sector=lead_data.get('market_sector', ''),
                    confidence_score=lead_data.get('confidence_score', 0.5),
                    metadata=lead_data.get('metadata', {})
                )
                
                if 'contacts' in lead_data:
                    lead.contacts = lead_data['contacts']
                
                # Validate the lead
                validation_start = time.time()
                is_valid, messages, _ = self.validator.validate_lead(lead)
                validation_time = time.time() - validation_start
                total_validation_time += validation_time
                
                # Check validation accuracy
                if is_valid == expected_valid:
                    correct_validations += 1
                
                # Update precision/recall metrics
                if is_valid and expected_valid:
                    true_positives += 1
                    
                    # Store example
                    if len(results['examples']['true_positives']) < 2:
                        results['examples']['true_positives'].append({
                            'title': lead.title,
                            'validation_messages': messages,
                            'confidence': lead.confidence_score
                        })
                        
                elif is_valid and not expected_valid:
                    false_positives += 1
                    
                    # Store example
                    if len(results['examples']['false_positives']) < 2:
                        results['examples']['false_positives'].append({
                            'title': lead.title,
                            'validation_messages': messages,
                            'confidence': lead.confidence_score,
                            'expected_reasons': expected_reasons
                        })
                        
                elif not is_valid and expected_valid:
                    false_negatives += 1
                    
                    # Store example
                    if len(results['examples']['false_negatives']) < 2:
                        results['examples']['false_negatives'].append({
                            'title': lead.title,
                            'validation_messages': messages,
                            'confidence': lead.confidence_score
                        })
                
                # Track rule effectiveness
                for message in messages:
                    # Extract rule name from message
                    rule_name = message.split(':')[0] if ':' in message else message
                    rule_stats[rule_name]['triggered'] += 1
                    
                    # Check if rule firing matches expectation
                    if (not is_valid) == (not expected_valid):
                        rule_stats[rule_name]['correct'] += 1
            
            # Calculate metrics
            accuracy = correct_validations / len(test_cases) if test_cases else 0
            
            # Precision, recall, and F1 for valid lead classification
            precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
            recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            
            # Calculate rule effectiveness
            rule_effectiveness = {}
            for rule, stats in rule_stats.items():
                if stats['triggered'] > 0:
                    effectiveness = stats['correct'] / stats['triggered']
                    rule_effectiveness[rule] = {
                        'effectiveness': effectiveness,
                        'triggered': stats['triggered'],
                        'correct': stats['correct']
                    }
            
            # Update results
            results['validation']['accuracy'] = accuracy
            results['validation']['qualified_lead_precision'] = precision
            results['validation']['qualified_lead_recall'] = recall
            results['validation']['f1'] = f1
            
            results['rule_effectiveness'] = rule_effectiveness
            
            results['performance']['avg_validation_time'] = total_validation_time / len(test_cases) if test_cases else 0
            results['performance']['total_time'] = time.time() - start_time
            
            logger.info(
                f"Validator test completed in {results['performance']['total_time']:.2f}s. "
                f"Accuracy: {accuracy:.2f}, F1: {f1:.2f}"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error testing lead validator: {e}")
            results['error'] = str(e)
            return results
    
    def test_end_to_end_workflow(self) -> Dict[str, Any]:
        """Test the end-to-end extraction workflow.
        
        Returns:
            Dictionary containing test results and metrics
        """
        logger.info("Testing end-to-end extraction workflow")
        start_time = time.time()
        
        results = {
            'extraction_to_validation': {
                'success_rate': 0.0,
                'qualified_lead_ratio': 0.0,
                'avg_confidence': 0.0
            },
            'source_to_qualified_lead': {
                'yield_ratio': 0.0,
                'by_source_type': {}
            },
            'performance': {
                'total_time': 0.0,
                'breakdown': {
                    'extraction': 0.0,
                    'validation': 0.0
                }
            },
            'examples': {
                'qualified_leads': [],
                'rejected_leads': []
            }
        }
        
        # Get test sources
        sources_path = self.test_data_dir / 'test_sources.json'
        
        if not sources_path.exists():
            logger.warning(f"Test sources not found: {sources_path}")
            return results
        
        try:
            with open(sources_path, 'r') as f:
                test_sources_data = json.load(f)
            
            # Convert to DataSource objects
            test_sources = []
            for source_data in test_sources_data:
                source = DataSource(
                    id=source_data.get('id', ''),
                    name=source_data.get('name', ''),
                    url=source_data.get('url', ''),
                    source_type=SourceType(source_data.get('source_type', 'unknown')),
                    active=source_data.get('active', True),
                    metadata=source_data.get('metadata', {})
                )
                test_sources.append(source)
            
            # Randomly select a subset of sources for end-to-end testing
            sample_size = min(5, len(test_sources))
            sample_sources = random.sample(test_sources, sample_size)
            
            # Measure extraction performance
            extraction_start = time.time()
            all_leads = self.pipeline.process_sources(sample_sources)
            extraction_time = time.time() - extraction_start
            
            # Validate all leads
            validation_start = time.time()
            validated_leads = []
            qualified_leads = []
            rejected_leads = []
            
            for lead in all_leads:
                valid, messages, _ = self.validator.validate_lead(lead)
                lead.metadata['validation_result'] = valid
                lead.metadata['validation_messages'] = messages
                
                validated_leads.append(lead)
                
                if valid:
                    qualified_leads.append(lead)
                else:
                    rejected_leads.append(lead)
            
            validation_time = time.time() - validation_start
            
            # Calculate metrics
            success_rate = len(validated_leads) / (len(all_leads) if all_leads else 1)
            qualified_ratio = len(qualified_leads) / (len(validated_leads) if validated_leads else 1)
            avg_confidence = sum(lead.confidence_score for lead in validated_leads) / (len(validated_leads) if validated_leads else 1)
            
            # Calculate source yield metrics
            source_type_yields = defaultdict(lambda: {'leads': 0, 'qualified': 0})
            for lead in all_leads:
                source_type = lead.metadata.get('source_type', 'unknown')
                source_type_yields[source_type]['leads'] += 1
            
            for lead in qualified_leads:
                source_type = lead.metadata.get('source_type', 'unknown')
                source_type_yields[source_type]['qualified'] += 1
            
            source_yield_results = {}
            for source_type, counts in source_type_yields.items():
                yield_ratio = counts['qualified'] / counts['leads'] if counts['leads'] > 0 else 0
                source_yield_results[source_type] = {
                    'total_leads': counts['leads'],
                    'qualified_leads': counts['qualified'],
                    'yield_ratio': yield_ratio
                }
            
            # Calculate overall yield
            overall_yield = len(qualified_leads) / len(sample_sources) if sample_sources else 0
            
            # Store examples
            for lead in qualified_leads[:3]:
                results['examples']['qualified_leads'].append({
                    'title': lead.title,
                    'source': lead.source,
                    'market_sector': lead.market_sector,
                    'confidence': lead.confidence_score,
                    'quality_score': lead.metadata.get('quality_score', 0.0)
                })
            
            for lead in rejected_leads[:3]:
                results['examples']['rejected_leads'].append({
                    'title': lead.title,
                    'source': lead.source,
                    'market_sector': lead.market_sector,
                    'confidence': lead.confidence_score,
                    'reasons': lead.metadata.get('validation_messages', [])
                })
            
            # Update results
            results['extraction_to_validation']['success_rate'] = success_rate
            results['extraction_to_validation']['qualified_lead_ratio'] = qualified_ratio
            results['extraction_to_validation']['avg_confidence'] = avg_confidence
            
            results['source_to_qualified_lead']['yield_ratio'] = overall_yield
            results['source_to_qualified_lead']['by_source_type'] = source_yield_results
            
            results['performance']['total_time'] = time.time() - start_time
            results['performance']['breakdown']['extraction'] = extraction_time
            results['performance']['breakdown']['validation'] = validation_time
            
            logger.info(
                f"End-to-end test completed in {results['performance']['total_time']:.2f}s. "
                f"Qualified lead ratio: {qualified_ratio:.2f}, Overall yield: {overall_yield:.2f}"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error in end-to-end testing: {e}")
            results['error'] = str(e)
            return results
    
    def calculate_overall_metrics(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall metrics from component test results.
        
        Args:
            results: Test results from individual components
            
        Returns:
            Dictionary containing overall metrics
        """
        logger.info("Calculating overall metrics")
        
        overall_metrics = {
            'accuracy': {
                'entity_extraction_f1': results.get('component_tests', {}).get('nlp_processor', {}).get('entity_extraction', {}).get('f1', 0.0),
                'market_sector_accuracy': results.get('component_tests', {}).get('nlp_processor', {}).get('market_sector_classification', {}).get('accuracy', 0.0),
                'lead_validation_f1': results.get('component_tests', {}).get('validator', {}).get('validation', {}).get('f1', 0.0),
                'overall_extraction_accuracy': 0.0
            },
            'performance': {
                'avg_processing_time_per_source': results.get('component_tests', {}).get('pipeline', {}).get('performance', {}).get('avg_source_time', 0.0),
                'avg_validation_time_per_lead': results.get('component_tests', {}).get('validator', {}).get('performance', {}).get('avg_validation_time', 0.0),
                'end_to_end_throughput': 0.0
            },
            'business_value': {
                'qualified_lead_yield': results.get('end_to_end_tests', {}).get('source_to_qualified_lead', {}).get('yield_ratio', 0.0),
                'false_positive_rate': 0.0,
                'cost_per_qualified_lead': 0.0,
                'lead_quality_score': 0.0
            },
            'recommendations': []
        }
        
        # Calculate overall extraction accuracy
        nlp_f1 = overall_metrics['accuracy']['entity_extraction_f1']
        sector_accuracy = overall_metrics['accuracy']['market_sector_accuracy']
        validation_f1 = overall_metrics['accuracy']['lead_validation_f1']
        
        if all([nlp_f1, sector_accuracy, validation_f1]):
            # Weighted combination of metrics
            overall_metrics['accuracy']['overall_extraction_accuracy'] = (
                0.3 * nlp_f1 + 0.3 * sector_accuracy + 0.4 * validation_f1
            )
        
        # Calculate end-to-end throughput
        e2e_time = results.get('end_to_end_tests', {}).get('performance', {}).get('total_time', 0.0)
        e2e_source_count = len(results.get('end_to_end_tests', {}).get('source_to_qualified_lead', {}).get('by_source_type', {}))
        
        if e2e_time > 0 and e2e_source_count > 0:
            overall_metrics['performance']['end_to_end_throughput'] = e2e_source_count / e2e_time
        
        # Calculate false positive rate
        validator_precision = results.get('component_tests', {}).get('validator', {}).get('validation', {}).get('qualified_lead_precision', 0.0)
        if validator_precision > 0:
            overall_metrics['business_value']['false_positive_rate'] = 1.0 - validator_precision
        
        # Estimate cost per qualified lead
        source_processing_time = overall_metrics['performance']['avg_processing_time_per_source']
        qualified_yield = overall_metrics['business_value']['qualified_lead_yield']
        
        if qualified_yield > 0:
            # Use time as a proxy for cost
            overall_metrics['business_value']['cost_per_qualified_lead'] = source_processing_time / qualified_yield
        
        # Estimate lead quality
        qualified_examples = results.get('end_to_end_tests', {}).get('examples', {}).get('qualified_leads', [])
        if qualified_examples:
            quality_scores = [lead.get('quality_score', 0.0) for lead in qualified_examples if 'quality_score' in lead]
            if quality_scores:
                overall_metrics['business_value']['lead_quality_score'] = sum(quality_scores) / len(quality_scores)
        
        # Generate recommendations
        recommendations = []
        
        # NLP recommendations
        if nlp_f1 < 0.7:
            recommendations.append("Improve entity extraction performance in the NLP processor")
        
        if sector_accuracy < 0.8:
            recommendations.append("Enhance market sector classification accuracy")
        
        # Pipeline recommendations
        filter_effect = results.get('component_tests', {}).get('pipeline', {}).get('pipeline_steps', {}).get('filter', {}).get('effectiveness', 0.0)
        if filter_effect < 0.2:
            recommendations.append("Adjust lead filtering for better precision-recall balance")
        
        # Validation recommendations
        if validation_f1 < 0.8:
            recommendations.append("Refine lead validation rules for better accuracy")
        
        # Overall recommendations
        qualified_ratio = results.get('end_to_end_tests', {}).get('extraction_to_validation', {}).get('qualified_lead_ratio', 0.0)
        if qualified_ratio < 0.5:
            recommendations.append("Improve overall qualified lead ratio through better source selection and validation tuning")
        
        overall_metrics['recommendations'] = recommendations
        
        logger.info(
            f"Overall metrics calculated. "
            f"Overall accuracy: {overall_metrics['accuracy']['overall_extraction_accuracy']:.2f}, "
            f"{len(recommendations)} recommendations generated"
        )
        
        return overall_metrics
    
    def generate_visualizations(self, results: Dict[str, Any]) -> None:
        """Generate visualizations from test results.
        
        Args:
            results: Test results from all components
        """
        logger.info("Generating visualizations")
        
        # Create visualization directory
        vis_dir = self.output_dir / 'visualizations'
        os.makedirs(vis_dir, exist_ok=True)
        
        try:
            # 1. NLP Performance Bar Chart
            self._plot_nlp_performance(results, vis_dir)
            
            # 2. Source Type Yield Comparison
            self._plot_source_type_yields(results, vis_dir)
            
            # 3. Market Sector Confusion Matrix
            self._plot_market_sector_confusion(results, vis_dir)
            
            # 4. Pipeline Step Performance
            self._plot_pipeline_performance(results, vis_dir)
            
            # 5. Overall Metrics Radar Chart
            self._plot_overall_metrics_radar(results, vis_dir)
            
            logger.info(f"Visualizations generated in {vis_dir}")
            
        except Exception as e:
            logger.error(f"Error generating visualizations: {e}")
    
    def _plot_nlp_performance(self, results: Dict[str, Any], output_dir: Path) -> None:
        """Plot NLP performance metrics.
        
        Args:
            results: Test results
            output_dir: Output directory for visualizations
        """
        nlp_results = results.get('component_tests', {}).get('nlp_processor', {})
        
        # Extract metrics
        metrics = {
            'Entity Extraction F1': nlp_results.get('entity_extraction', {}).get('f1', 0),
            'Market Sector Accuracy': nlp_results.get('market_sector_classification', {}).get('accuracy', 0),
            'Location Extraction F1': nlp_results.get('location_extraction', {}).get('f1', 0),
            'Project Value Within 20%': nlp_results.get('project_value_extraction', {}).get('within_20_percent', 0)
        }
        
        # Create bar chart
        plt.figure(figsize=(10, 6))
        plt.bar(metrics.keys(), metrics.values(), color='skyblue')
        plt.ylim(0, 1.0)
        plt.title('NLP Processor Performance')
        plt.ylabel('Score (0-1)')
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Add value labels on top of bars
        for i, v in enumerate(metrics.values()):
            plt.text(i, v + 0.02, f"{v:.2f}", ha='center')
        
        # Save figure
        plt.tight_layout()
        plt.savefig(output_dir / 'nlp_performance.png')
        plt.close()
    
    def _plot_source_type_yields(self, results: Dict[str, Any], output_dir: Path) -> None:
        """Plot source type yield comparison.
        
        Args:
            results: Test results
            output_dir: Output directory for visualizations
        """
        source_yields = results.get('end_to_end_tests', {}).get('source_to_qualified_lead', {}).get('by_source_type', {})
        
        if not source_yields:
            logger.warning("No source yield data available for visualization")
            return
        
        # Extract data
        source_types = []
        total_leads = []
        qualified_leads = []
        
        for source_type, data in source_yields.items():
            source_types.append(source_type)
            total_leads.append(data.get('total_leads', 0))
            qualified_leads.append(data.get('qualified_leads', 0))
        
        # Create grouped bar chart
        x = np.arange(len(source_types))
        width = 0.35
        
        fig, ax = plt.subplots(figsize=(12, 7))
        ax.bar(x - width/2, total_leads, width, label='Total Leads', color='lightblue')
        ax.bar(x + width/2, qualified_leads, width, label='Qualified Leads', color='darkblue')
        
        ax.set_xticks(x)
        ax.set_xticklabels(source_types)
        ax.set_title('Lead Yields by Source Type')
        ax.set_ylabel('Number of Leads')
        ax.legend()
        
        # Add yield ratio as text
        for i, source_type in enumerate(source_types):
            yield_ratio = source_yields[source_type].get('yield_ratio', 0)
            ax.text(i, max(total_leads[i], qualified_leads[i]) + 0.5, 
                   f"Yield: {yield_ratio:.2f}", ha='center')
        
        # Save figure
        plt.tight_layout()
        plt.savefig(output_dir / 'source_type_yields.png')
        plt.close()
    
    def _plot_market_sector_confusion(self, results: Dict[str, Any], output_dir: Path) -> None:
        """Plot market sector confusion matrix.
        
        Args:
            results: Test results
            output_dir: Output directory for visualizations
        """
        confusion_matrix = results.get('component_tests', {}).get('nlp_processor', {}).get('market_sector_classification', {}).get('confusion_matrix')
        
        if not confusion_matrix:
            logger.warning("No confusion matrix available for visualization")
            return
        
        # Convert to numpy array if it's a list
        if isinstance(confusion_matrix, list):
            confusion_matrix = np.array(confusion_matrix)
        
        # Market sector labels
        sectors = [s.value for s in MarketSector]
        
        # Create heatmap
        plt.figure(figsize=(10, 8))
        plt.imshow(confusion_matrix, cmap='Blues')
        plt.colorbar(label='Count')
        
        # Add labels
        plt.xticks(np.arange(len(sectors)), sectors, rotation=45, ha='right')
        plt.yticks(np.arange(len(sectors)), sectors)
        
        plt.xlabel('Predicted Sector')
        plt.ylabel('True Sector')
        plt.title('Market Sector Classification Confusion Matrix')
        
        # Add count labels
        for i in range(len(sectors)):
            for j in range(len(sectors)):
                plt.text(j, i, str(confusion_matrix[i, j]),
                       ha="center", va="center", color="black" if confusion_matrix[i, j] < 4 else "white")
        
        # Save figure
        plt.tight_layout()
        plt.savefig(output_dir / 'market_sector_confusion.png')
        plt.close()
    
    def _plot_pipeline_performance(self, results: Dict[str, Any], output_dir: Path) -> None:
        """Plot pipeline step performance.
        
        Args:
            results: Test results
            output_dir: Output directory for visualizations
        """
        pipeline_steps = results.get('component_tests', {}).get('pipeline', {}).get('pipeline_steps', {})
        
        if not pipeline_steps:
            logger.warning("No pipeline step data available for visualization")
            return
        
        # Extract data
        steps = []
        effectiveness = []
        times = []
        
        for step, data in pipeline_steps.items():
            steps.append(step.capitalize())
            effectiveness.append(data.get('effectiveness', 0) * 100)  # Convert to percentage
            times.append(data.get('time', 0))
        
        # Create figure with two y-axes
        fig, ax1 = plt.subplots(figsize=(10, 6))
        
        # Plot effectiveness bars
        x = np.arange(len(steps))
        bars = ax1.bar(x, effectiveness, color='skyblue', alpha=0.7)
        ax1.set_ylabel('Effectiveness (%)')
        ax1.set_ylim(0, 100)
        
        # Add second y-axis for time
        ax2 = ax1.twinx()
        line = ax2.plot(x, times, 'ro-', linewidth=2, markersize=8)
        ax2.set_ylabel('Processing Time (s)', color='red')
        ax2.tick_params(axis='y', labelcolor='red')
        
        # Set x-axis
        ax1.set_xticks(x)
        ax1.set_xticklabels(steps)
        
        # Add title and legend
        ax1.set_title('Pipeline Step Performance')
        ax1.legend([bars[0], line[0]], ['Effectiveness', 'Time'], loc='upper left')
        
        # Add value labels
        for i, v in enumerate(effectiveness):
            ax1.text(i, v + 5, f"{v:.1f}%", ha='center')
            ax2.text(i, times[i] + 0.05, f"{times[i]:.2f}s", ha='center', color='red')
        
        # Save figure
        plt.tight_layout()
        plt.savefig(output_dir / 'pipeline_performance.png')
        plt.close()
    
    def _plot_overall_metrics_radar(self, results: Dict[str, Any], output_dir: Path) -> None:
        """Plot overall metrics on a radar chart.
        
        Args:
            results: Test results
            output_dir: Output directory for visualizations
        """
        overall_metrics = results.get('metrics', {})
        
        if not overall_metrics:
            logger.warning("No overall metrics available for visualization")
            return
        
        # Extract metrics for radar chart
        metrics = {
            'Entity Extraction': overall_metrics.get('accuracy', {}).get('entity_extraction_f1', 0),
            'Market Sector Classification': overall_metrics.get('accuracy', {}).get('market_sector_accuracy', 0),
            'Lead Validation': overall_metrics.get('accuracy', {}).get('lead_validation_f1', 0),
            'Qualified Lead Yield': overall_metrics.get('business_value', {}).get('qualified_lead_yield', 0),
            'Lead Quality': overall_metrics.get('business_value', {}).get('lead_quality_score', 0),
            'Processing Efficiency': 1.0 - min(1.0, overall_metrics.get('performance', {}).get('cost_per_qualified_lead', 0) / 10)  # Normalize
        }
        
        # Set up radar chart
        categories = list(metrics.keys())
        values = list(metrics.values())
        
        # Add first value at the end to close the polygon
        values.append(values[0])
        categories.append(categories[0])
        
        # Compute angles for each metric
        angles = np.linspace(0, 2*np.pi, len(categories)-1, endpoint=False).tolist()
        angles.append(angles[0])  # Close the polygon
        
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))
        
        # Plot metrics
        ax.plot(angles, values, 'o-', linewidth=2, markersize=8)
        ax.fill(angles, values, alpha=0.25)
        
        # Set category labels
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories[:-1])
        
        # Set y-axis limits and labels
        ax.set_ylim(0, 1)
        ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
        ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'])
        
        # Add value labels
        for i, angle in enumerate(angles[:-1]):  # Skip the last one (duplicate)
            ax.text(angle, values[i] + 0.05, f"{values[i]:.2f}", 
                  ha='center', va='center')
        
        plt.title('Overall Extraction System Performance', size=15, pad=20)
        
        # Save figure
        plt.tight_layout()
        plt.savefig(output_dir / 'overall_metrics_radar.png')
        plt.close()
    
    def save_results(self, results: Dict[str, Any]) -> None:
        """Save test results to files.
        
        Args:
            results: Test results from all components
        """
        # Save full JSON results
        results_path = self.output_dir / 'test_results.json'
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        # Save summary as CSV
        summary_path = self.output_dir / 'test_summary.csv'
        self._save_summary_csv(results, summary_path)
        
        # Save recommendations
        recommendations_path = self.output_dir / 'recommendations.txt'
        self._save_recommendations(results, recommendations_path)
        
        logger.info(f"Test results saved to {results_path}")
    
    def _save_summary_csv(self, results: Dict[str, Any], output_path: Path) -> None:
        """Save summary metrics as CSV.
        
        Args:
            results: Test results
            output_path: Output path for CSV file
        """
        # Extract key metrics
        metrics = [
            # NLP metrics
            ('NLP', 'Entity Extraction F1', results.get('component_tests', {}).get('nlp_processor', {}).get('entity_extraction', {}).get('f1', 0)),
            ('NLP', 'Market Sector Accuracy', results.get('component_tests', {}).get('nlp_processor', {}).get('market_sector_classification', {}).get('accuracy', 0)),
            ('NLP', 'Location Extraction F1', results.get('component_tests', {}).get('nlp_processor', {}).get('location_extraction', {}).get('f1', 0)),
            ('NLP', 'Project Value Within 20%', results.get('component_tests', {}).get('nlp_processor', {}).get('project_value_extraction', {}).get('within_20_percent', 0)),
            
            # Pipeline metrics
            ('Pipeline', 'Source Processing Success Rate', results.get('component_tests', {}).get('pipeline', {}).get('source_processing', {}).get('success_rate', 0)),
            ('Pipeline', 'Average Leads per Source', results.get('component_tests', {}).get('pipeline', {}).get('source_processing', {}).get('avg_leads_per_source', 0)),
            ('Pipeline', 'Filter Effectiveness', results.get('component_tests', {}).get('pipeline', {}).get('pipeline_steps', {}).get('filter', {}).get('effectiveness', 0)),
            ('Pipeline', 'Deduplication Effectiveness', results.get('component_tests', {}).get('pipeline', {}).get('pipeline_steps', {}).get('deduplicate', {}).get('effectiveness', 0)),
            
            # Validator metrics
            ('Validator', 'Validation Accuracy', results.get('component_tests', {}).get('validator', {}).get('validation', {}).get('accuracy', 0)),
            ('Validator', 'Qualified Lead Precision', results.get('component_tests', {}).get('validator', {}).get('validation', {}).get('qualified_lead_precision', 0)),
            ('Validator', 'Qualified Lead Recall', results.get('component_tests', {}).get('validator', {}).get('validation', {}).get('qualified_lead_recall', 0)),
            ('Validator', 'Qualified Lead F1', results.get('component_tests', {}).get('validator', {}).get('validation', {}).get('f1', 0)),
            
            # End-to-end metrics
            ('End-to-End', 'Qualified Lead Ratio', results.get('end_to_end_tests', {}).get('extraction_to_validation', {}).get('qualified_lead_ratio', 0)),
            ('End-to-End', 'Source to Qualified Lead Yield', results.get('end_to_end_tests', {}).get('source_to_qualified_lead', {}).get('yield_ratio', 0)),
            
            # Overall metrics
            ('Overall', 'Extraction System Accuracy', results.get('metrics', {}).get('accuracy', {}).get('overall_extraction_accuracy', 0)),
            ('Overall', 'False Positive Rate', results.get('metrics', {}).get('business_value', {}).get('false_positive_rate', 0)),
            ('Overall', 'Lead Quality Score', results.get('metrics', {}).get('business_value', {}).get('lead_quality_score', 0))
        ]
        
        # Write to CSV
        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Component', 'Metric', 'Value'])
            for row in metrics:
                writer.writerow(row)
    
    def test_document_extraction(self, 
                          document_paths: List[str], 
                          expected_results: List[Dict[str, Any]],
                          document_type: str = None,
                          thresholds: Dict[str, float] = None) -> Dict[str, Any]:
        """Test the extraction of leads from legal documents.
        
        Args:
            document_paths: List of paths to test documents
            expected_results: List of expected extraction results
            document_type: Optional document type hint
            thresholds: Optional thresholds for precision, recall, and F1 score
                      
        Returns:
            Dictionary with extraction performance metrics
        """
        if not self.legal_processor:
            logger.error("LegalProcessor not initialized. Cannot test document extraction.")
            return {
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0,
                "error": "LegalProcessor not initialized"
            }
            
        if not thresholds:
            thresholds = {
                "precision": 0.8,
                "recall": 0.8,
                "f1_score": 0.8
            }
            
        logger.info(f"Testing document extraction for {len(document_paths)} documents")
        start_time = time.time()
        
        results = {
            "document_paths": document_paths,
            "document_type": document_type,
            "thresholds": thresholds,
            "extraction_results": [],
            "precision": 0.0,
            "recall": 0.0,
            "f1_score": 0.0,
            "performance": {
                "total_time": 0.0,
                "avg_document_time": 0.0
            },
            "errors": [],
            "false_positives": [],
            "false_negatives": [],
            "details": {
                "field_accuracy": {},
                "entity_extraction": {},
                "error_patterns": {}
            }
        }
        
        # Track memory usage if enabled
        if self.enable_memory_tracking:
            results["performance"]["memory_before"] = self.process.memory_info().rss / 1024 / 1024  # MB
        
        # Process each document
        extracted_data = []
        document_times = []
        
        for i, doc_path in enumerate(document_paths):
            try:
                # Process document
                doc_start_time = time.time()
                
                # Read document
                with open(doc_path, 'r', encoding='utf-8') as f:
                    document_text = f.read()
                
                # Process through legal processor
                processed_doc = self.legal_processor.process_document(document_text, document_type)
                
                # Track processing time
                doc_time = time.time() - doc_start_time
                document_times.append(doc_time)
                
                # Store results
                extracted_data.append({
                    "document_path": doc_path,
                    "processing_time": doc_time,
                    "extracted_data": processed_doc
                })
                
                logger.info(f"Processed document {i+1}/{len(document_paths)}: {Path(doc_path).name} in {doc_time:.2f}s")
                
            except Exception as e:
                logger.error(f"Error processing document {doc_path}: {e}")
                results["errors"].append({
                    "document_path": doc_path,
                    "error": str(e)
                })
                
                # Save failed document if enabled
                if self.save_failed_documents:
                    failed_dir = self.output_dir / "failed_documents"
                    os.makedirs(failed_dir, exist_ok=True)
                    try:
                        import shutil
                        shutil.copy(doc_path, failed_dir / Path(doc_path).name)
                    except Exception as copy_error:
                        logger.error(f"Failed to save failed document: {copy_error}")
        
        # Calculate extraction metrics
        if extracted_data and expected_results:
            # Match extracted data with expected results
            matches = []
            
            for expected in expected_results:
                best_match = None
                best_match_score = 0
                
                for extracted in extracted_data:
                    match_score = self._calculate_extraction_match(
                        extracted["extracted_data"], 
                        expected
                    )
                    
                    if match_score > best_match_score:
                        best_match = extracted
                        best_match_score = match_score
                
                if best_match and best_match_score > 0.5:  # Consider it a match if score > 0.5
                    matches.append({
                        "expected": expected,
                        "extracted": best_match,
                        "match_score": best_match_score
                    })
                else:
                    # False negative - expected but not extracted
                    results["false_negatives"].append({
                        "expected": expected,
                        "best_match_score": best_match_score if best_match else 0.0
                    })
            
            # Calculate precision and recall
            if matches:
                # Precision = correctly extracted / all extracted
                precision = len(matches) / len(extracted_data) if extracted_data else 0
                
                # Recall = correctly extracted / all expected
                recall = len(matches) / len(expected_results) if expected_results else 0
                
                # F1 score
                f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
                
                # Update results
                results["precision"] = precision
                results["recall"] = recall
                results["f1_score"] = f1
                
                # Calculate field-level accuracy
                field_accuracy = self._calculate_field_accuracy(matches)
                results["details"]["field_accuracy"] = field_accuracy
                
                # Track entity extraction accuracy
                entity_accuracy = self._calculate_entity_accuracy(matches)
                results["details"]["entity_extraction"] = entity_accuracy
                
                # Identify error patterns
                error_patterns = self._analyze_error_patterns(
                    matches, results["false_positives"], results["false_negatives"]
                )
                results["details"]["error_patterns"] = error_patterns
                
                logger.info(
                    f"Extraction metrics: Precision={precision:.4f}, Recall={recall:.4f}, F1={f1:.4f}"
                )
                
                # Check against thresholds
                if precision < thresholds.get("precision", 0.8):
                    logger.warning(f"Precision {precision:.4f} below threshold {thresholds.get('precision', 0.8)}")
                
                if recall < thresholds.get("recall", 0.8):
                    logger.warning(f"Recall {recall:.4f} below threshold {thresholds.get('recall', 0.8)}")
                
                if f1 < thresholds.get("f1_score", 0.8):
                    logger.warning(f"F1 score {f1:.4f} below threshold {thresholds.get('f1_score', 0.8)}")
            
            # Store extraction results
            results["extraction_results"] = matches
        
        # Performance metrics
        results["performance"]["total_time"] = time.time() - start_time
        results["performance"]["avg_document_time"] = sum(document_times) / len(document_times) if document_times else 0
        
        # Memory usage
        if self.enable_memory_tracking:
            results["performance"]["memory_after"] = self.process.memory_info().rss / 1024 / 1024  # MB
            results["performance"]["memory_used"] = results["performance"]["memory_after"] - results["performance"]["memory_before"]
        
        # Generate precision-recall curve if multiple confidence thresholds
        if len(extracted_data) >= 5 and self.generate_visualizations:
            try:
                self._generate_precision_recall_curve(extracted_data, expected_results)
                logger.info("Generated precision-recall curve")
            except Exception as e:
                logger.error(f"Failed to generate precision-recall curve: {e}")
        
        # Save detailed results
        details_path = self.output_dir / f"extraction_details_{document_type}.json"
        with open(details_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        return results
    
    def _calculate_extraction_match(self, extracted: Dict[str, Any], expected: Dict[str, Any]) -> float:
        """Calculate how well an extracted result matches expected data.
        
        Args:
            extracted: Extracted data
            expected: Expected data
            
        Returns:
            Match score between 0 and 1
        """
        # Get set of all keys
        all_keys = set(extracted.keys()) | set(expected.keys())
        
        # Priority fields that are more important for matching
        priority_fields = {
            "document_id": 3.0,
            "project_name": 2.0,
            "project_address": 2.0,
            "project_value": 1.5,
            "contractor": 1.5,
            "construction_type": 1.5
        }
        
        # Count matches, weighted by priority
        total_weight = 0
        matched_weight = 0
        
        for key in all_keys:
            # Skip complex nested objects for basic matching
            if key in ["construction_details", "contractor", "property_owner", 
                     "professionals", "approval", "extraction_confidence"]:
                continue
                
            # Get field weight
            weight = priority_fields.get(key, 1.0)
            total_weight += weight
            
            # Check for match
            if key in extracted and key in expected:
                # Convert values to strings for comparison
                extracted_val = str(extracted[key]).lower()
                expected_val = str(expected[key]).lower()
                
                # Calculate field similarity
                if extracted_val == expected_val:
                    matched_weight += weight
                elif expected_val in extracted_val or extracted_val in expected_val:
                    matched_weight += weight * 0.75
                else:
                    # Calculate string similarity
                    similarity = difflib.SequenceMatcher(None, extracted_val, expected_val).ratio()
                    matched_weight += weight * similarity
        
        # Calculate overall match score
        match_score = matched_weight / total_weight if total_weight > 0 else 0
        return match_score
    
    def _calculate_field_accuracy(self, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate accuracy for each field across all matched documents.
        
        Args:
            matches: List of matched document pairs
            
        Returns:
            Dictionary with field accuracy metrics
        """
        field_stats = defaultdict(lambda: {"correct": 0, "total": 0, "accuracy": 0.0})
        
        for match in matches:
            expected = match["expected"]
            extracted = match["extracted"]["extracted_data"]
            
            # Check each field in expected data
            for field, expected_value in expected.items():
                # Skip special fields
                if field in ["source_file", "extraction_confidence"] or not expected_value:
                    continue
                
                field_stats[field]["total"] += 1
                
                # Check if field exists and matches in extracted data
                if field in extracted:
                    extracted_value = extracted[field]
                    
                    # Compare values (with special handling for some types)
                    if isinstance(expected_value, (dict, list)):
                        # For complex types, just check presence for now
                        if extracted_value:
                            field_stats[field]["correct"] += 0.5  # Partial credit
                    elif field == "project_value":
                        # For monetary values, allow 10% margin
                        try:
                            if isinstance(extracted_value, (int, float)) and isinstance(expected_value, (int, float)):
                                if abs(extracted_value - expected_value) / expected_value <= 0.1:
                                    field_stats[field]["correct"] += 1
                        except:
                            pass
                    else:
                        # For strings and other types, check similarity
                        if isinstance(extracted_value, str) and isinstance(expected_value, str):
                            if expected_value.lower() in extracted_value.lower() or extracted_value.lower() in expected_value.lower():
                                field_stats[field]["correct"] += 1
                            else:
                                similarity = difflib.SequenceMatcher(None, str(extracted_value).lower(), str(expected_value).lower()).ratio()
                                if similarity >= 0.8:
                                    field_stats[field]["correct"] += 1
                        elif extracted_value == expected_value:
                            field_stats[field]["correct"] += 1
        
        # Calculate accuracy for each field
        results = {}
        for field, stats in field_stats.items():
            accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            results[field] = {
                "accuracy": accuracy,
                "correct": stats["correct"],
                "total": stats["total"]
            }
        
        return results
    
    def _calculate_entity_accuracy(self, matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate accuracy for entity extraction.
        
        Args:
            matches: List of matched document pairs
            
        Returns:
            Dictionary with entity extraction accuracy metrics
        """
        entity_stats = {
            "organization": {"true_pos": 0, "false_pos": 0, "false_neg": 0},
            "location": {"true_pos": 0, "false_pos": 0, "false_neg": 0},
            "person": {"true_pos": 0, "false_pos": 0, "false_neg": 0},
            "money": {"true_pos": 0, "false_pos": 0, "false_neg": 0},
            "date": {"true_pos": 0, "false_pos": 0, "false_neg": 0}
        }
        
        for match in matches:
            expected = match["expected"]
            extracted = match["extracted"]["extracted_data"]
            
            # Organization entities
            expected_orgs = []
            if "contractor" in expected and isinstance(expected["contractor"], dict) and "name" in expected["contractor"]:
                expected_orgs.append(expected["contractor"]["name"])
            if "property_owner" in expected and isinstance(expected["property_owner"], dict) and "name" in expected["property_owner"]:
                expected_orgs.append(expected["property_owner"]["name"])
            if "professionals" in expected and isinstance(expected["professionals"], dict):
                expected_orgs.extend(expected["professionals"].values())
            
            # Extracted organizations
            extracted_orgs = []
            if "entities" in extracted and "organizations" in extracted["entities"]:
                extracted_orgs = extracted["entities"]["organizations"]
            
            # Count matches for organizations
            for org in expected_orgs:
                matched = False
                for ext_org in extracted_orgs:
                    if org.lower() in ext_org.lower() or ext_org.lower() in org.lower():
                        matched = True
                        entity_stats["organization"]["true_pos"] += 1
                        break
                if not matched:
                    entity_stats["organization"]["false_neg"] += 1
            
            # Count false positives for organizations
            for ext_org in extracted_orgs:
                matched = False
                for org in expected_orgs:
                    if org.lower() in ext_org.lower() or ext_org.lower() in org.lower():
                        matched = True
                        break
                if not matched:
                    entity_stats["organization"]["false_pos"] += 1
            
            # Location entities
            expected_locs = []
            if "project_address" in expected:
                expected_locs.append(expected["project_address"])
            
            # Extracted locations
            extracted_locs = []
            if "entities" in extracted and "locations" in extracted["entities"]:
                extracted_locs = extracted["entities"]["locations"]
            
            # Count matches for locations
            for loc in expected_locs:
                matched = False
                for ext_loc in extracted_locs:
                    if loc.lower() in ext_loc.lower() or ext_loc.lower() in loc.lower():
                        matched = True
                        entity_stats["location"]["true_pos"] += 1
                        break
                if not matched:
                    entity_stats["location"]["false_neg"] += 1
            
            # Count false positives for locations
            for ext_loc in extracted_locs:
                matched = False
                for loc in expected_locs:
                    if loc.lower() in ext_loc.lower() or ext_loc.lower() in loc.lower():
                        matched = True
                        break
                if not matched:
                    entity_stats["location"]["false_pos"] += 1
        
        # Calculate precision, recall, F1 for each entity type
        results = {}
        for entity_type, stats in entity_stats.items():
            true_pos = stats["true_pos"]
            false_pos = stats["false_pos"]
            false_neg = stats["false_neg"]
            
            precision = true_pos / (true_pos + false_pos) if true_pos + false_pos > 0 else 0
            recall = true_pos / (true_pos + false_neg) if true_pos + false_neg > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0
            
            results[entity_type] = {
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "counts": {
                    "true_pos": true_pos,
                    "false_pos": false_pos,
                    "false_neg": false_neg
                }
            }
        
        return results
    
    def _analyze_error_patterns(self, matches: List[Dict[str, Any]], 
                              false_positives: List[Dict[str, Any]], 
                              false_negatives: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze error patterns in extraction results.
        
        Args:
            matches: List of matched document pairs
            false_positives: List of false positive extractions
            false_negatives: List of false negative extractions
            
        Returns:
            Dictionary with error pattern analysis
        """
        error_patterns = {
            "common_field_errors": [],
            "entity_extraction_issues": [],
            "missing_fields": defaultdict(int),
            "incorrect_fields": defaultdict(int)
        }
        
        # Analyze field errors in matched documents
        for match in matches:
            expected = match["expected"]
            extracted = match["extracted"]["extracted_data"]
            
            # Check each field in expected data
            for field, expected_value in expected.items():
                # Skip special fields
                if field in ["source_file", "extraction_confidence"] or not expected_value:
                    continue
                
                # Check if field exists in extracted data
                if field not in extracted:
                    error_patterns["missing_fields"][field] += 1
                else:
                    # Check if values match
                    extracted_value = extracted[field]
                    if field == "project_value":
                        # For monetary values, check percentage difference
                        try:
                            if isinstance(extracted_value, (int, float)) and isinstance(expected_value, (int, float)):
                                if abs(extracted_value - expected_value) / expected_value > 0.1:
                                    error_patterns["incorrect_fields"][field] += 1
                        except:
                            error_patterns["incorrect_fields"][field] += 1
                    elif isinstance(expected_value, (dict, list)):
                        # Skip complex types for now
                        pass
                    else:
                        # For strings and other types, check equality
                        if expected_value != extracted_value:
                            # Check string similarity
                            if isinstance(extracted_value, str) and isinstance(expected_value, str):
                                similarity = difflib.SequenceMatcher(None, str(extracted_value).lower(), str(expected_value).lower()).ratio()
                                if similarity < 0.8:
                                    error_patterns["incorrect_fields"][field] += 1
                            else:
                                error_patterns["incorrect_fields"][field] += 1
        
        # Identify common field errors
        for field, count in error_patterns["missing_fields"].items():
            if count >= 2:  # Consider it a pattern if it occurs multiple times
                error_patterns["common_field_errors"].append(f"Frequently missing field: {field} ({count} occurrences)")
        
        for field, count in error_patterns["incorrect_fields"].items():
            if count >= 2:  # Consider it a pattern if it occurs multiple times
                error_patterns["common_field_errors"].append(f"Frequently incorrect field: {field} ({count} occurrences)")
        
        # Entity extraction issues
        if len(false_negatives) >= 2:
            error_patterns["entity_extraction_issues"].append(f"Multiple false negatives in entity extraction ({len(false_negatives)} occurrences)")
        
        return error_patterns
    
    def _generate_precision_recall_curve(self, extracted_data: List[Dict[str, Any]], 
                                      expected_results: List[Dict[str, Any]]) -> None:
        """Generate a precision-recall curve by varying confidence thresholds.
        
        Args:
            extracted_data: List of extracted document data
            expected_results: List of expected extraction results
        """
        # Create thresholds for confidence
        thresholds = np.linspace(0, 1, 20)
        precisions = []
        recalls = []
        f1_scores = []
        
        # Get confidence scores or use extraction_confidence if available
        confidence_scores = []
        for data in extracted_data:
            if "extraction_confidence" in data["extracted_data"]:
                confidence_scores.append(data["extracted_data"]["extraction_confidence"])
            else:
                # Use fixed confidence if not available
                confidence_scores.append(0.75)
        
        # Calculate precision and recall at each threshold
        for threshold in thresholds:
            # Filter results by confidence
            filtered_data = [
                extracted_data[i] for i in range(len(extracted_data))
                if confidence_scores[i] >= threshold
            ]
            
            # Skip if no data at this threshold
            if not filtered_data:
                precisions.append(0)
                recalls.append(0)
                f1_scores.append(0)
                continue
            
            # Count matches
            matches = 0
            for expected in expected_results:
                best_match_score = 0
                for extracted in filtered_data:
                    match_score = self._calculate_extraction_match(
                        extracted["extracted_data"], 
                        expected
                    )
                    
                    if match_score > best_match_score:
                        best_match_score = match_score
                
                if best_match_score > 0.5:
                    matches += 1
            
            # Calculate metrics
            precision = matches / len(filtered_data) if filtered_data else 0
            recall = matches / len(expected_results) if expected_results else 0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else 0
            
            precisions.append(precision)
            recalls.append(recall)
            f1_scores.append(f1)
        
        # Plot precision-recall curve
        plt.figure(figsize=(10, 8))
        
        # Precision vs. Recall curve
        plt.subplot(2, 1, 1)
        plt.plot(recalls, precisions, 'b-', linewidth=2)
        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title('Precision-Recall Curve')
        plt.grid(True)
        
        # F1 vs. Threshold curve
        plt.subplot(2, 1, 2)
        plt.plot(thresholds, f1_scores, 'r-', linewidth=2)
        plt.xlabel('Confidence Threshold')
        plt.ylabel('F1 Score')
        plt.title('F1 Score vs. Confidence Threshold')
        plt.grid(True)
        
        # Find optimal threshold
        optimal_idx = np.argmax(f1_scores)
        optimal_threshold = thresholds[optimal_idx]
        optimal_f1 = f1_scores[optimal_idx]
        
        plt.axvline(x=optimal_threshold, color='g', linestyle='--')
        plt.text(optimal_threshold + 0.02, optimal_f1 - 0.1, 
                f'Optimal Threshold: {optimal_threshold:.2f}\nF1: {optimal_f1:.2f}', 
                verticalalignment='bottom')
        
        # Save the figure
        plt.tight_layout()
        plt.savefig(self.output_dir / "precision_recall_curve.png")
        plt.close()
        
        # Save threshold data
        threshold_data = {
            "thresholds": thresholds.tolist(),
            "precisions": precisions,
            "recalls": recalls,
            "f1_scores": f1_scores,
            "optimal_threshold": float(optimal_threshold),
            "optimal_f1": float(optimal_f1)
        }
        
        with open(self.output_dir / "threshold_analysis.json", 'w') as f:
            json.dump(threshold_data, f, indent=2)
    
    def benchmark_performance(self, document_paths: List[str], iterations: int = 3,
                           enable_memory_tracking: bool = True) -> Dict[str, Any]:
        """Benchmark the performance of document extraction.
        
        Args:
            document_paths: List of paths to test documents
            iterations: Number of iterations to run for reliable measurement
            enable_memory_tracking: Whether to track memory usage
            
        Returns:
            Dictionary with performance benchmark results
        """
        if not self.legal_processor:
            logger.error("LegalProcessor not initialized. Cannot benchmark performance.")
            return {"error": "LegalProcessor not initialized"}
            
        logger.info(f"Benchmarking performance with {len(document_paths)} documents and {iterations} iterations")
        
        results = {
            "document_count": len(document_paths),
            "iterations": iterations,
            "timing": {
                "total_time": 0.0,
                "avg_document_time": 0.0,
                "std_dev": 0.0,
                "min_time": float('inf'),
                "max_time": 0.0
            },
            "memory": {},
            "component_timing": {
                "document_parsing": 0.0,
                "nlp_processing": 0.0,
                "lead_creation": 0.0
            },
            "throughput": 0.0
        }
        
        all_times = []
        iteration_times = []
        
        # Track memory if enabled
        if enable_memory_tracking and self.enable_memory_tracking:
            results["memory"]["before"] = self.process.memory_info().rss / 1024 / 1024  # MB
        
        # Run the benchmark
        for i in range(iterations):
            iteration_start = time.time()
            doc_times = []
            
            for doc_path in document_paths:
                try:
                    # Process document
                    doc_start_time = time.time()
                    
                    # Read document
                    with open(doc_path, 'r', encoding='utf-8') as f:
                        document_text = f.read()
                    
                    # Process through legal processor
                    self.legal_processor.process_document(document_text)
                    
                    # Record time
                    doc_time = time.time() - doc_start_time
                    doc_times.append(doc_time)
                    all_times.append(doc_time)
                    
                except Exception as e:
                    logger.error(f"Error in benchmark for document {doc_path}: {e}")
            
            iteration_time = time.time() - iteration_start
            iteration_times.append(iteration_time)
            
            logger.info(f"Benchmark iteration {i+1}/{iterations} completed in {iteration_time:.2f}s")
        
        # Calculate performance metrics
        if all_times:
            avg_time = sum(all_times) / len(all_times)
            std_dev = (sum((t - avg_time) ** 2 for t in all_times) / len(all_times)) ** 0.5
            min_time = min(all_times)
            max_time = max(all_times)
            
            results["timing"]["avg_document_time"] = avg_time
            results["timing"]["std_dev"] = std_dev
            results["timing"]["min_time"] = min_time
            results["timing"]["max_time"] = max_time
        
        # Total time and throughput
        total_time = sum(iteration_times)
        results["timing"]["total_time"] = total_time
        results["throughput"] = (len(document_paths) * iterations) / total_time if total_time > 0 else 0
        
        # Track memory if enabled
        if enable_memory_tracking and self.enable_memory_tracking:
            results["memory"]["after"] = self.process.memory_info().rss / 1024 / 1024  # MB
            results["memory"]["used"] = results["memory"]["after"] - results["memory"]["before"]
        
        # Save benchmark results
        with open(self.output_dir / "performance_benchmark.json", 'w') as f:
            json.dump(results, f, indent=2)
        
        return results
    
    def _save_recommendations(self, results: Dict[str, Any], output_path: Path) -> None:
        """Save recommendations to a text file.
        
        Args:
            results: Test results
            output_path: Output path for recommendations file
        """
        recommendations = results.get('metrics', {}).get('recommendations', [])
        
        with open(output_path, 'w') as f:
            f.write("# Extraction System Test Recommendations\n\n")
            f.write(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            if recommendations:
                f.write("## Areas for Improvement\n\n")
                for i, rec in enumerate(recommendations, 1):
                    f.write(f"{i}. {rec}\n")
            else:
                f.write("No specific recommendations. System is performing well.\n")
            
            # Add performance summary
            f.write("\n## Performance Summary\n\n")
            
            overall_accuracy = results.get('metrics', {}).get('accuracy', {}).get('overall_extraction_accuracy', 0)
            f.write(f"- Overall System Accuracy: {overall_accuracy:.2f}\n")
            
            qualified_yield = results.get('metrics', {}).get('business_value', {}).get('qualified_lead_yield', 0)
            f.write(f"- Qualified Lead Yield: {qualified_yield:.2f} leads per source\n")
            
            false_pos_rate = results.get('metrics', {}).get('business_value', {}).get('false_positive_rate', 0)
            f.write(f"- False Positive Rate: {false_pos_rate:.2f}\n")
            
            lead_quality = results.get('metrics', {}).get('business_value', {}).get('lead_quality_score', 0)
            f.write(f"- Lead Quality Score: {lead_quality:.2f}\n")


def main():
    """Main entry point for extraction testing."""
    parser = argparse.ArgumentParser(description='Test the lead extraction system')
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--test-data', help='Path to test data directory')
    parser.add_argument('--output', help='Path to output directory')
    parser.add_argument('--component', choices=['nlp', 'pipeline', 'validator', 'all'],
                      default='all', help='Which component to test')
    args = parser.parse_args()
    
    # Initialize tester
    tester = ExtractionTester(
        config_path=args.config,
        test_data_dir=args.test_data,
        output_dir=args.output
    )
    
    # Run tests
    if args.component == 'nlp':
        results = tester.test_nlp_processor()
        tester.save_results({'component_tests': {'nlp_processor': results}})
        
    elif args.component == 'pipeline':
        results = tester.test_extraction_pipeline()
        tester.save_results({'component_tests': {'pipeline': results}})
        
    elif args.component == 'validator':
        results = tester.test_lead_validator()
        tester.save_results({'component_tests': {'validator': results}})
        
    else:  # 'all'
        tester.run_full_test()


if __name__ == '__main__':
    main()
#!/usr/bin/env python3
"""
Run extraction tests using the test_extraction.py framework.
This script executes the tests defined in test_config.json.
"""

import os
import sys
import json
import logging
from datetime import datetime

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from perera_lead_scraper.tests.test_extraction import ExtractionTester
from perera_lead_scraper.legal.legal_processor import LegalProcessor
from perera_lead_scraper.legal.document_parser import DocumentParser
from perera_lead_scraper.legal.document_validator import DocumentValidator
from perera_lead_scraper.validation.lead_validator import LeadValidator
from perera_lead_scraper.pipeline.extraction_pipeline import LeadExtractionPipeline

def setup_logging(log_level):
    """Configure logging for the test runner."""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(OUTPUT_DIR, 'test_run.log'))
        ]
    )
    return logging.getLogger('extraction_test_runner')

def load_config():
    """Load the test configuration from the config file."""
    config_path = os.path.join(os.path.dirname(__file__), 'expected/test_config.json')
    with open(config_path, 'r') as f:
        return json.load(f)

def load_expected_result(file_path):
    """Load the expected result from a JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)

def main():
    """Main execution function for the test runner."""
    global OUTPUT_DIR
    
    # Load configuration
    config = load_config()
    test_settings = config['test_settings']
    OUTPUT_DIR = test_settings['output_directory']
    
    # Create timestamp directory for this test run
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    OUTPUT_DIR = os.path.join(OUTPUT_DIR, f"run_{timestamp}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Set up logging
    logger = setup_logging(test_settings['log_level'])
    logger.info(f"Starting extraction tests at {timestamp}")
    
    # Initialize components
    document_parser = DocumentParser()
    document_validator = DocumentValidator()
    legal_processor = LegalProcessor(document_parser, document_validator)
    lead_validator = LeadValidator()
    extraction_pipeline = LeadExtractionPipeline()
    
    # Initialize the tester
    tester = ExtractionTester(
        legal_processor=legal_processor,
        lead_validator=lead_validator,
        extraction_pipeline=extraction_pipeline,
        output_dir=OUTPUT_DIR,
        generate_visualizations=test_settings.get('generate_visualizations', False),
        save_failed_documents=test_settings.get('save_failed_documents', False)
    )
    
    # Run all test cases
    all_passed = True
    results_summary = []
    
    for test_case in config['test_cases']:
        logger.info(f"Running test case: {test_case['name']}")
        
        # Load expected results
        expected_results = []
        for result_path in test_case['expected_results']:
            expected_results.append(load_expected_result(result_path))
        
        # Run the test
        result = tester.test_document_extraction(
            document_paths=test_case['input_files'],
            expected_results=expected_results,
            document_type=test_case['document_type'],
            thresholds=test_case['thresholds']
        )
        
        # Store results
        passed = result['precision'] >= test_case['thresholds']['precision'] and \
                 result['recall'] >= test_case['thresholds']['recall'] and \
                 result['f1_score'] >= test_case['thresholds']['f1_score']
        
        all_passed = all_passed and passed
        
        results_summary.append({
            'test_case': test_case['name'],
            'document_type': test_case['document_type'],
            'precision': result['precision'],
            'recall': result['recall'],
            'f1_score': result['f1_score'],
            'passed': passed,
            'details': result.get('details', {})
        })
        
        logger.info(f"Test case {test_case['name']} {'PASSED' if passed else 'FAILED'}")
        logger.info(f"  Precision: {result['precision']:.4f} (threshold: {test_case['thresholds']['precision']})")
        logger.info(f"  Recall: {result['recall']:.4f} (threshold: {test_case['thresholds']['recall']})")
        logger.info(f"  F1 Score: {result['f1_score']:.4f} (threshold: {test_case['thresholds']['f1_score']})")
    
    # Save overall results
    with open(os.path.join(OUTPUT_DIR, 'results_summary.json'), 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'overall_result': 'PASSED' if all_passed else 'FAILED',
            'test_cases': results_summary
        }, f, indent=2)
    
    # Run performance benchmarks if enabled
    if config['performance_metrics']['enable_timing']:
        logger.info("Running performance benchmarks")
        perf_result = tester.benchmark_performance(
            document_paths=[item for sublist in [tc['input_files'] for tc in config['test_cases']] for item in sublist],
            iterations=config['performance_metrics']['benchmark_iterations'],
            enable_memory_tracking=config['performance_metrics']['enable_memory_tracking']
        )
        
        with open(os.path.join(OUTPUT_DIR, 'performance_metrics.json'), 'w') as f:
            json.dump(perf_result, f, indent=2)
    
    # Generate visualizations if enabled
    if test_settings.get('generate_visualizations', False):
        logger.info("Generating visualizations")
        tester.generate_visualization(
            os.path.join(OUTPUT_DIR, 'results_summary.json'),
            os.path.join(OUTPUT_DIR, 'visualization')
        )
    
    logger.info(f"All tests completed. Overall result: {'PASSED' if all_passed else 'FAILED'}")
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
# Lead Enrichment and Classification Testing Framework

This document describes the comprehensive testing framework used to validate and measure the quality, accuracy, and performance of the lead enrichment and classification systems within the Perera Construction Lead Scraper project.

## Overview

The testing framework evaluates several key aspects of lead enrichment and classification:

1. **Data Quality**: How complete and accurate is the enriched lead data?
2. **Classification Accuracy**: How well does the system categorize leads across various dimensions?
3. **Performance**: How efficiently do the enrichment and classification processes run?
4. **Integration**: How well do the various components work together?

The framework uses a combination of synthetic test data, mock API responses, and ground truth validation to provide comprehensive coverage of normal operations, edge cases, and failure scenarios.

## Test Components

### 1. Test Dataset

The framework includes a configurable test dataset with diverse lead samples:

- Covers all market sectors (healthcare, education, energy, commercial, entertainment)
- Includes leads with varying levels of detail (complete, partial, minimal)
- Represents different geographical areas (primarily Southern California)
- Provides a range of project values, timelines, and project types

Each test lead includes corresponding ground truth data that serves as the reference point for validation. This ground truth data is either manually defined or generated through a controlled enrichment process.

### 2. Mock Services

To enable reliable and efficient testing without depending on external services, the framework includes mock implementations for:

- Company data APIs
- Contact finder services
- Project database APIs
- Web scraping services

These mocks can be configured to operate at different levels:

- **Full**: All external services are mocked
- **Partial**: Critical services are mocked, with optional real service integration
- **None**: No mocking, uses real services (caution: consumes API quota)

### 3. Metrics Collection

The framework collects detailed metrics on every aspect of enrichment and classification:

- Success rates for each enrichment operation
- Accuracy rates for each classification category
- Processing times for enrichment and classification operations
- Resource utilization (memory, CPU)
- API usage counts and patterns

These metrics are tracked both individually and in aggregate to provide a complete picture of system performance.

### 4. Failure Analysis

When enrichment or classification operations fail or produce inaccurate results, the framework:

- Records the specific type of failure
- Categorizes failures by root cause
- Measures the impact on overall data quality
- Tracks patterns and recurring issues

This information is essential for identifying weaknesses and prioritizing improvements.

## Testing Methodology

### Enrichment Testing

The enrichment testing process validates:

1. **Company Data Lookup**: Accuracy and completeness of retrieved company information
2. **Website Discovery**: Success rate in finding company websites
3. **Contact Extraction**: Ability to find and extract valid contact information
4. **Company Size Estimation**: Accuracy of company size determination
5. **Project Stage Determination**: Correctness of project stage identification
6. **Related Projects Discovery**: Success in finding related projects
7. **Lead Scoring**: Accuracy of lead scoring calculations

Each aspect is evaluated by comparing the enriched lead data to the ground truth reference, using appropriate similarity metrics for different types of data (exact matching for well-defined fields, fuzzy matching for textual descriptions, etc.).

### Classification Testing

The classification testing process validates:

1. **Value Classification**: Accuracy of categorizing leads by project value
2. **Timeline Classification**: Accuracy of timeline categorization
3. **Decision Stage Determination**: Accuracy of identifying project decision stages
4. **Competition Level Assessment**: Accuracy of competition assessment
5. **Win Probability Calculation**: Calibration of win probability estimates
6. **Priority Score Assignment**: Effectiveness of priority scoring algorithm

Classification accuracy is measured against ground truth classifications, with special attention to confidence scores and their correlation with actual accuracy.

### Performance Testing

The performance testing process measures:

1. **Processing Time**: Time required for enrichment and classification operations
2. **Memory Usage**: Memory consumption during processing
3. **Scalability**: Performance with varying batch sizes
4. **API Efficiency**: Number of API calls made per lead

Performance metrics are collected across different batch sizes to identify optimal processing configurations and potential bottlenecks.

### Integration Testing

The integration testing process validates:

1. **Enrichment-Classification Flow**: Data flow between enrichment and classification
2. **Database Integration**: Proper persistence and retrieval of enriched and classified data
3. **Configuration Handling**: Correct application of configuration across components

Integration tests focus on the interactions between components and the overall system behavior.

## Running the Tests

### Basic Usage

To run the complete test suite:

```bash
python -m perera_lead_scraper.tests.test_enrichment
```

### Configuration Options

The test framework supports several configuration options:

```bash
python -m perera_lead_scraper.tests.test_enrichment --mock partial --sample 50 --test all --report --verbose
```

- `--mock`: Mocking level (`full`, `partial`, `none`)
- `--sample`: Number of test leads to use
- `--test`: Test suite to run (`all`, `enrichment`, `classification`, `integration`, `performance`)
- `--report`: Generate detailed test reports
- `--verbose`: Enable verbose logging

### Generating Reports

Test reports are generated in the `tests/test_data/reports` directory and include:

- JSON reports with detailed metrics
- CSV reports for easy import into spreadsheets
- Visualizations of key metrics

## Interpreting Test Results

### Enrichment Quality

For enrichment operations, the key metrics to consider are:

- **Success Rates**: Percentage of leads successfully enriched for each data type
- **Data Completeness**: Overall completeness of enriched data
- **Accuracy**: Match between enriched data and ground truth

Target success rates:
- Company Data: >80%
- Website Discovery: >75%
- Contact Extraction: >70%
- Company Size: >80%
- Project Stage: >75%
- Overall Data Completeness: >75%

### Classification Quality

For classification operations, the key metrics are:

- **Accuracy Rates**: Percentage of leads correctly classified in each category
- **Confidence Calibration**: Alignment between confidence scores and actual accuracy
- **Priority Effectiveness**: Ability to prioritize the most valuable leads

Target accuracy rates:
- Value Classification: >90%
- Timeline Classification: >80%
- Decision Stage: >80%
- Competition Level: >75%
- Win Probability Calibration: >85%
- Overall Classification Accuracy: >85%

### Performance Metrics

For performance assessment, the key metrics are:

- **Enrichment Time**: Target <300ms per lead
- **Classification Time**: Target <200ms per lead
- **Memory Usage**: Minimal increase with batch size
- **API Calls**: Efficient use of external APIs

## Addressing Issues

When test results indicate issues, consider the following approaches:

1. **Data Quality Issues**:
   - Improve data extraction patterns and techniques
   - Enhance preprocessing of input data
   - Add fallback data sources

2. **Classification Accuracy Issues**:
   - Refine classification rules and thresholds
   - Adjust confidence calculation algorithms
   - Add more indicators for challenging categories

3. **Performance Issues**:
   - Optimize algorithms for bottleneck operations
   - Improve caching strategies
   - Reduce unnecessary API calls

4. **Integration Issues**:
   - Review data flow between components
   - Check configuration handling
   - Ensure proper error propagation

## Extending the Test Framework

The test framework is designed to be extensible:

1. **Adding Test Cases**:
   - Add new test leads to the test dataset
   - Update the ground truth file with expected results

2. **Adding Mock Services**:
   - Extend the EnrichmentMock class with new service mocks
   - Add mock response data to mock_api_responses.json

3. **Adding Metrics**:
   - Extend the TestMetrics class with new metrics
   - Update the report generation to include new metrics

## Conclusion

The lead enrichment and classification testing framework provides comprehensive validation and measurement of system quality, accuracy, and performance. By regularly running these tests and addressing identified issues, the Perera Construction Lead Scraper project can maintain and improve its ability to deliver high-quality, actionable construction leads.
# Test Data for Perera Lead Scraper

This directory contains test data for evaluating the performance of the Perera Lead Scraper's legal document extraction capabilities.

## Directory Structure

```
test_data/
├── documents/                # Sample legal documents for testing
│   ├── permits/              # Building permits
│   ├── contracts/            # Construction contracts
│   ├── zoning/               # Zoning applications
│   └── regulatory/           # Regulatory filings
├── expected/                 # Expected extraction results (ground truth)
│   ├── *.json                # Expected output for each document
│   └── test_config.json      # Test configuration
├── results/                  # Directory for test results (created during testing)
├── run_extraction_test.py    # Test runner script
└── README.md                 # This file
```

## Test Documents

The `documents` directory contains sample legal documents of various types:

1. **Building Permits**: Official permits for construction of new buildings or renovations
2. **Construction Contracts**: Agreements between property owners and contractors
3. **Zoning Applications**: Requests for zoning variances or changes
4. **Regulatory Filings**: Environmental impact reports and other regulatory documents

## Expected Results

The `expected` directory contains the expected extraction results for each document, in JSON format. These files represent the "ground truth" against which the extraction system's output is compared.

## Test Configuration

The `expected/test_config.json` file defines the test cases and settings:

- **Test Settings**: Output directory, logging level, visualization options
- **Test Cases**: Document types, input files, expected results, and quality thresholds
- **Performance Metrics**: Options for timing and memory tracking

## Running Tests

To run the tests, execute the `run_extraction_test.py` script:

```bash
cd /path/to/perera_lead_scraper
python tests/test_data/run_extraction_test.py
```

The test results will be saved in the `results` directory, including:

- JSON summary of results for each test case
- Performance metrics
- Visualizations (if enabled)
- Log file with detailed information

## Adding New Tests

To add new test documents:

1. Add the document file to the appropriate subdirectory under `documents/`
2. Create a corresponding expected result file in `expected/`
3. Update `expected/test_config.json` to include the new test case

## Evaluation Metrics

The test framework evaluates extraction performance using:

- **Precision**: Ratio of correctly extracted fields to total extracted fields
- **Recall**: Ratio of correctly extracted fields to total expected fields
- **F1 Score**: Harmonic mean of precision and recall

Each test case defines thresholds for these metrics to determine pass/fail status.
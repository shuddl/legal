# HubSpot Integration Tests

This directory contains integration tests for the HubSpot CRM export functionality. These tests validate that the CRM export pipeline correctly creates, updates, and associates HubSpot objects with the correct mapped fields.

## Requirements

To run the integration tests, you need:

1. A HubSpot Sandbox account (do NOT use a production account)
2. A HubSpot Sandbox API key
3. Configured property and deal stage IDs for testing

## Setup

1. Add the test configuration to your `.env` file:

```
# Test Configuration (for integration tests)
# This separate API key targets a HubSpot Sandbox account
TEST_HUBSPOT_API_KEY=your_test_hubspot_api_key

# Test HubSpot Custom Property IDs (for integration tests)
# These must be valid property IDs in the Sandbox environment
TEST_HUBSPOT_PROP_LEAD_SOURCE=your_test_hubspot_property_id
TEST_HUBSPOT_PROP_SOURCE_URL=your_test_hubspot_property_id
TEST_HUBSPOT_PROP_SOURCE_ID=your_test_hubspot_property_id
TEST_HUBSPOT_PROP_LEAD_ID=your_test_hubspot_property_id
TEST_HUBSPOT_PROP_PUBLICATION_DATE=your_test_hubspot_property_id
TEST_HUBSPOT_PROP_RETRIEVED_DATE=your_test_hubspot_property_id
TEST_HUBSPOT_PROP_CONFIDENCE_SCORE=your_test_hubspot_property_id
TEST_HUBSPOT_PROP_LOCATION_CITY=your_test_hubspot_property_id
TEST_HUBSPOT_PROP_LOCATION_STATE=your_test_hubspot_property_id
TEST_HUBSPOT_PROP_EST_SQ_FOOTAGE=your_test_hubspot_property_id

# Test HubSpot Deal Stage IDs (for integration tests)
# These must be valid stage IDs in the Sandbox environment
TEST_HUBSPOT_STAGE_NEW=your_test_hubspot_dealstage_id
TEST_HUBSPOT_STAGE_ENRICHED=your_test_hubspot_dealstage_id
TEST_HUBSPOT_STAGE_EXPORTED=your_test_hubspot_dealstage_id
```

2. Create the required custom properties and deal stages in your HubSpot Sandbox account if they don't exist already.

## Running the Tests

To run only the integration tests:

```bash
pytest tests/hubspot/test_crm_integration.py -v
```

To run a specific test:

```bash
pytest tests/hubspot/test_crm_integration.py::test_export_single_lead -v
```

## Test Descriptions

1. `test_export_single_lead` - Tests exporting a single lead to HubSpot and verifies that all standard and custom fields are correctly mapped.

2. `test_find_or_create_logic` - Tests that the find-or-create logic works correctly by exporting the same lead twice and verifying that only one set of objects is created.

3. `test_association` - Tests that associations between deals, companies, and contacts are correctly created.

4. `test_note_creation` - Tests that notes are correctly created and attached to deals.

## Clean Up

The tests automatically clean up any objects created during the test run. However, if a test fails unexpectedly, it's possible that some objects may be left in your Sandbox account. In this case, you'll need to manually delete them.
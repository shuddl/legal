#!/bin/bash
set -e

# Health check script for the Perera Lead Scraper container
# This script is used by Docker's HEALTHCHECK instruction

# Environment variables
API_PORT=${PORT:-8000}
TIMEOUT=5

# Check API health endpoint
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT http://localhost:$API_PORT/api/health || echo "failed")

if [ "$API_STATUS" = "200" ]; then
    echo "API service is healthy"
    exit 0
else
    echo "API service is unhealthy: HTTP status $API_STATUS"
    exit 1
fi
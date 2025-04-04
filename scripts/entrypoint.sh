#!/bin/bash
set -e

# Configure timezone if provided
if [ ! -z "$TZ" ]; then
    echo "Setting timezone to $TZ"
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime
    echo $TZ > /etc/timezone
fi

# Ensure directories exist and have correct permissions
mkdir -p /app/data /app/exports /app/logs

# Wait for any database dependency (if needed in the future)
# Currently using SQLite which doesn't need a wait

# Check for command argument
if [ "$1" = "api" ]; then
    echo "Starting API server"
    exec python -m uvicorn src.perera_lead_scraper.api.api:app --host 0.0.0.0 --port ${PORT:-8000}
elif [ "$1" = "worker" ]; then
    echo "Starting background worker"
    exec python -m src.perera_lead_scraper.worker
elif [ "$1" = "shell" ]; then
    echo "Starting interactive shell"
    exec /bin/bash
else
    # Default: Start both API and orchestrator in the same container
    echo "Starting Perera Lead Scraper"
    echo "Starting API server at port ${PORT:-8000}"
    
    # Start the API server in the background
    python -m uvicorn src.perera_lead_scraper.api.api:app --host 0.0.0.0 --port ${PORT:-8000} &
    API_PID=$!
    
    # Start the orchestrator (which will start scheduled tasks)
    python -m src.perera_lead_scraper.orchestrator &
    ORCHESTRATOR_PID=$!
    
    # Handle graceful shutdown
    function handle_sigterm() {
        echo "Received SIGTERM, shutting down..."
        kill -TERM $API_PID 2>/dev/null || true
        kill -TERM $ORCHESTRATOR_PID 2>/dev/null || true
        wait $API_PID 2>/dev/null || true
        wait $ORCHESTRATOR_PID 2>/dev/null || true
        echo "Shutdown complete"
        exit 0
    }
    
    trap handle_sigterm SIGTERM
    
    # Wait for processes to exit
    wait $API_PID || true
    wait $ORCHESTRATOR_PID || true
fi
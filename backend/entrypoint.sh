#!/bin/bash
# Backend entrypoint script
# Runs Alembic migrations before starting the uvicorn server
#
# This script ensures:
# 1. Database schema is up-to-date via Alembic migrations
# 2. Migrations complete before FastAPI app starts
# 3. The logs table exists before database logging is enabled
#
# Usage: This script is called by the Dockerfile CMD

set -e

echo "Running Alembic migrations..."

# Change to backend directory where alembic.ini is located
cd /app/backend

# Run migrations with retry logic for database startup race conditions
MAX_RETRIES=30
RETRY_INTERVAL=2
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if alembic upgrade head 2>&1; then
        echo "Alembic migrations completed successfully"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo "Migration failed (attempt $RETRY_COUNT/$MAX_RETRIES), retrying in ${RETRY_INTERVAL}s..."
            sleep $RETRY_INTERVAL
        else
            echo "ERROR: Alembic migrations failed after $MAX_RETRIES attempts"
            exit 1
        fi
    fi
done

# Return to app directory
cd /app

echo "Starting uvicorn server..."

# Execute the uvicorn command passed as arguments
exec "$@"

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

# Set PYTHONPATH so alembic can find the backend module
export PYTHONPATH=/app:${PYTHONPATH:-}

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

# Start Pyroscope profiler in background if PYROSCOPE_ENABLED is set (default: true)
if [ "${PYROSCOPE_ENABLED:-true}" = "true" ]; then
    echo "Starting Pyroscope profiler in background..."
    nohup /usr/local/bin/pyroscope-profiler.sh "backend" "${PYROSCOPE_URL:-http://pyroscope:4040}" "${PROFILE_INTERVAL:-30}" \
        >> /app/data/logs/profiler.log 2>&1 &
fi

echo "Starting uvicorn server..."

# Execute the uvicorn command passed as arguments
exec "$@"

#!/bin/bash
# Backend entrypoint script
# Waits for database to be ready before starting the uvicorn server
# Schema is created via SQLAlchemy's create_all() in init_db()
#
# This script ensures:
# 1. Database is reachable before app starts
# 2. Schema creation happens via create_all() in the app
#
# Usage: This script is called by the Dockerfile CMD

set -e

echo "Waiting for database to be ready..."

# Set PYTHONPATH so Python can find the backend module
export PYTHONPATH=/app:${PYTHONPATH:-}

# Wait for database to be ready with retry logic
MAX_RETRIES=30
RETRY_INTERVAL=2
RETRY_COUNT=0

# Extract host and port from DATABASE_URL
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:/]*\).*|\1|p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
DB_PORT=${DB_PORT:-5432}

echo "Checking database at $DB_HOST:$DB_PORT..."

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('$DB_HOST', $DB_PORT)); s.close()" 2>/dev/null; then
        echo "Database is reachable"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo "Database not ready (attempt $RETRY_COUNT/$MAX_RETRIES), retrying in ${RETRY_INTERVAL}s..."
            sleep $RETRY_INTERVAL
        else
            echo "ERROR: Database not reachable after $MAX_RETRIES attempts"
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

#!/bin/bash
# Generic entrypoint for AI service containers with optional Pyroscope profiling
#
# Environment variables:
#   SERVICE_NAME:      Name for this service in Pyroscope (required for profiling)
#   PYROSCOPE_ENABLED: Set to "true" to enable profiling (default: false)
#   PYROSCOPE_URL:     Pyroscope server URL (default: http://pyroscope:4040)
#   PROFILE_INTERVAL:  Profile duration in seconds (default: 30)

set -e

# Start Pyroscope profiler in background if enabled
if [ "${PYROSCOPE_ENABLED:-false}" = "true" ] && [ -n "$SERVICE_NAME" ]; then
    echo "[entrypoint] Starting Pyroscope profiler for $SERVICE_NAME..."
    nohup /usr/local/bin/pyroscope-profiler.sh "$SERVICE_NAME" "${PYROSCOPE_URL:-http://pyroscope:4040}" "${PROFILE_INTERVAL:-30}" \
        >> /tmp/profiler.log 2>&1 &
fi

echo "[entrypoint] Starting $SERVICE_NAME..."

# Execute the main command
exec "$@"

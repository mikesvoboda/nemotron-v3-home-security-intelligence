#!/bin/bash
# Self-profiling script using py-spy that pushes profiles to Pyroscope
# Run this in the background alongside your Python application
#
# Usage: ./pyroscope-profiler.sh <service_name> [pyroscope_url] [interval]
#   service_name:   Name for this service in Pyroscope (e.g., "backend", "clip")
#   pyroscope_url:  Pyroscope server URL (default: http://pyroscope:4040)
#   interval:       Profile duration in seconds (default: 30)

SERVICE_NAME="${1:-unknown}"
PYROSCOPE_SERVER="${2:-http://pyroscope:4040}"
PROFILE_INTERVAL="${3:-30}"

log() {
    echo "[pyroscope-profiler] [$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Wait for the main process to start
sleep 10

log "Starting profiler for $SERVICE_NAME"
log "  Pyroscope server: $PYROSCOPE_SERVER"
log "  Profile interval: ${PROFILE_INTERVAL}s"

# Find our own Python process (the main application)
find_python_pid() {
    # Find Python processes, exclude this script's subprocesses
    pgrep -f "python|uvicorn" | while read pid; do
        # Skip if it's a py-spy process
        if ! grep -q "py-spy" /proc/$pid/cmdline 2>/dev/null; then
            echo "$pid"
            return
        fi
    done
}

while true; do
    PID=$(find_python_pid)

    if [ -z "$PID" ]; then
        log "No Python process found, waiting..."
        sleep 10
        continue
    fi

    log "Profiling PID $PID for ${PROFILE_INTERVAL}s..."

    PROFILE_FILE="/tmp/profile_${SERVICE_NAME}_$(date +%s).json"

    # Run py-spy with nonblocking mode to minimize impact
    if py-spy record \
        --pid "$PID" \
        --duration "$PROFILE_INTERVAL" \
        --format speedscope \
        --output "$PROFILE_FILE" \
        --nonblocking \
        2>/tmp/pyspy_error.log; then

        if [ -f "$PROFILE_FILE" ] && [ -s "$PROFILE_FILE" ]; then
            FROM_TS=$(($(date +%s) - PROFILE_INTERVAL))
            UNTIL_TS=$(date +%s)

            # Push to Pyroscope
            HTTP_CODE=$(curl -s -w "%{http_code}" -o /tmp/pyroscope_response.txt \
                -X POST "${PYROSCOPE_SERVER}/ingest?name=${SERVICE_NAME}&from=${FROM_TS}&until=${UNTIL_TS}&spyName=pyspy&format=speedscope" \
                --data-binary "@${PROFILE_FILE}" \
                -H "Content-Type: application/json")

            if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "204" ]; then
                log "Profile pushed successfully"
            else
                log "Failed to push profile: HTTP $HTTP_CODE"
            fi

            rm -f "$PROFILE_FILE"
        else
            log "Profile file empty or missing"
        fi
    else
        ERROR=$(cat /tmp/pyspy_error.log 2>/dev/null)
        log "Profiling failed: $ERROR"
    fi

    # Short sleep between profiling cycles
    sleep 5
done

#!/bin/bash
# py-spy profiler script for Python process profiling
# Discovers Python processes and pushes profiles to Pyroscope

PYROSCOPE_SERVER="http://localhost:4040"
PROFILE_INTERVAL="${PROFILE_INTERVAL:-30}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "py-spy profiler starting..."
log "  Profile interval: ${PROFILE_INTERVAL}s"

# Wait for Pyroscope to be ready
sleep 15

# Service patterns to profile
declare -A SERVICES=(
    ["Backend"]="uvicorn.*backend.main"
    ["RT-DETR"]="python.*rtdetr"
    ["Florence"]="python.*florence"
    ["CLIP"]="python.*clip"
    ["Enrichment"]="python.*enrichment"
)

profile_service() {
    local service_name="$1"
    local pattern="$2"

    # Find matching PID
    local pid=$(pgrep -f "$pattern" 2>/dev/null | head -1)

    if [ -z "$pid" ]; then
        return 1
    fi

    log "Profiling $service_name (PID: $pid)..."

    local profile_file="/tmp/profile_${service_name}_$(date +%s).json"

    # Run py-spy
    if py-spy record \
        --pid "$pid" \
        --duration "$PROFILE_INTERVAL" \
        --format speedscope \
        --output "$profile_file" \
        --nonblocking \
        2>/dev/null; then

        # Push to Pyroscope
        if [ -f "$profile_file" ]; then
            local from_ts=$(($(date +%s) - PROFILE_INTERVAL))
            local until_ts=$(date +%s)

            curl -s -X POST "${PYROSCOPE_SERVER}/ingest?name=${service_name}&from=${from_ts}&until=${until_ts}&spyName=pyspy&format=speedscope" \
                --data-binary "@${profile_file}" \
                -H "Content-Type: application/json" \
                >/dev/null 2>&1

            rm -f "$profile_file"
            log "  $service_name profile pushed successfully"
        fi
    else
        log "  $service_name profiling failed"
    fi
}

# Main loop
while true; do
    for service_name in "${!SERVICES[@]}"; do
        profile_service "$service_name" "${SERVICES[$service_name]}" &
    done

    # Wait for all profiling jobs
    wait

    log "Profile cycle complete, sleeping..."
    sleep 5
done

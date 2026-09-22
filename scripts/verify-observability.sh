#!/bin/bash
# =============================================================================
# Observability Stack Verification Script
# =============================================================================
# Verifies that Loki, Pyroscope, Alloy, and existing monitoring services
# are healthy and ingesting data.
#
# Usage: ./scripts/verify-observability.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load .env for port configuration
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "=== Observability Stack Verification ==="
echo ""

# Service ports (use .env values or defaults)
LOKI_PORT="${LOKI_PORT:-3100}"
PYROSCOPE_PORT="${PYROSCOPE_PORT:-4040}"
# Alloy's host port is published as ALLOY_UI_PORT in .env (12345); ALLOY_PORT is
# kept as a fallback for older .env files.
ALLOY_PORT="${ALLOY_UI_PORT:-${ALLOY_PORT:-12345}}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
TEMPO_PORT="${TEMPO_PORT:-3200}"
GRAFANA_PORT="${GRAFANA_PORT:-3002}"

# OTLP ingest chain: services export to Alloy :4317, Alloy forwards to Tempo :4317.
# Host-side the OTLP gRPC port is published via TEMPO_OTLP_GRPC in .env (4317).
TEMPO_OTLP_GRPC="${TEMPO_OTLP_GRPC:-4317}"

declare -A SERVICES=(
    ["loki"]="$LOKI_PORT|/ready"
    ["pyroscope"]="$PYROSCOPE_PORT|/ready"
    ["prometheus"]="$PROMETHEUS_PORT|/-/ready"
    ["tempo"]="$TEMPO_PORT|/ready"
    ["grafana"]="$GRAFANA_PORT|/api/health"
)

echo "Checking service health..."
echo ""

failed=0

# Alloy doesn't expose HTTP health endpoint externally - check container status instead
printf "  %-12s ... " "alloy"
if podman ps --format "{{.Names}} {{.Status}}" 2>/dev/null | grep -q "alloy.*Up"; then
    echo -e "${GREEN}OK (container running)${NC}"
else
    echo -e "${RED}FAIL${NC}"
    ((failed++)) || true
fi
for svc in "${!SERVICES[@]}"; do
    IFS='|' read -r port endpoint <<< "${SERVICES[$svc]}"
    printf "  %-12s (port %s)... " "$svc" "$port"

    if curl -sf --max-time 5 "http://localhost:$port$endpoint" > /dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAIL${NC}"
        ((failed++)) || true
    fi
done

echo ""
echo "Checking data ingestion..."
echo ""

# Verify log ingestion (Loki)
printf "  Loki log labels:     "
loki_labels=$(curl -s --max-time 5 "http://localhost:$LOKI_PORT/loki/api/v1/labels" 2>/dev/null | jq -r '.data | length' 2>/dev/null || echo "0")
if [ "$loki_labels" -gt 0 ] 2>/dev/null; then
    echo -e "${GREEN}$loki_labels labels found${NC}"
else
    echo -e "${YELLOW}no labels (logs may not be flowing yet)${NC}"
fi

# Verify profile ingestion (Pyroscope)
printf "  Pyroscope profiles:  "
pyroscope_ready=$(curl -sf --max-time 5 "http://localhost:$PYROSCOPE_PORT/ready" 2>/dev/null || true)
if [ "$pyroscope_ready" = "ready" ]; then
    echo -e "${GREEN}ready${NC}"
else
    echo -e "${YELLOW}not ready${NC}"
fi

# Verify trace ingestion (Tempo, fed by Alloy's OTLP receiver)
printf "  Tempo trace search:  "
# Tempo's search API needs at least one tag matcher; {duration>0} matches every span.
tempo_traces=$(curl -s --max-time 5 "http://localhost:$TEMPO_PORT/api/search?q=%7Bduration%3E0%7D&limit=20" 2>/dev/null | jq -r '.traces | length' 2>/dev/null || echo "0")
if [ "$tempo_traces" -gt 0 ] 2>/dev/null; then
    echo -e "${GREEN}$tempo_traces recent traces found${NC}"
else
    echo -e "${YELLOW}no traces (traces may not be flowing yet)${NC}"
fi

# Verify OTLP ingest. Services export to alloy:4317 on the internal network
# (Alloy forwards to tempo:4317); Alloy's 4317 has no fixed host mapping, so
# host-side :4317 is Tempo's OTLP gRPC listener — the end of that chain. TCP
# probe only: OTLP is gRPC, so there is no HTTP endpoint to curl here.
printf "  OTLP ingest:         "
if timeout 5 bash -c "cat < /dev/null > /dev/tcp/localhost/$TEMPO_OTLP_GRPC" 2>/dev/null; then
    echo -e "${GREEN}accepting on :$TEMPO_OTLP_GRPC${NC}"
else
    echo -e "${RED}FAIL (nothing on :$TEMPO_OTLP_GRPC)${NC}"
    # `|| true` — failed is 0 here if every service above passed, and a bare
    # ((failed++)) would return 1 and abort the script under `set -e`.
    ((failed++)) || true
fi

echo ""
echo "=== Verification Complete ==="
echo ""

if [ $failed -gt 0 ]; then
    echo -e "${RED}$failed service(s) failed health check${NC}"
    exit 1
else
    echo -e "${GREEN}All services healthy${NC}"
fi

# Show useful URLs
echo ""
echo "Useful URLs:"
echo "  Grafana:    http://localhost:$GRAFANA_PORT"
echo "  Prometheus: http://localhost:$PROMETHEUS_PORT"
echo "  Tempo:      http://localhost:$TEMPO_PORT (traces via Grafana Explore)"
echo "  Loki:       http://localhost:$LOKI_PORT (via Grafana Explore)"
echo "  Pyroscope:  http://localhost:$PYROSCOPE_PORT (via Grafana Explore)"
echo "  Alloy:      http://localhost:$ALLOY_PORT"
echo ""

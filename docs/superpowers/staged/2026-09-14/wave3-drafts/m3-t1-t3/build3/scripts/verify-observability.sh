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
ALLOY_PORT="${ALLOY_PORT:-12345}"
PROMETHEUS_PORT="${PROMETHEUS_PORT:-9090}"
JAEGER_PORT="${JAEGER_PORT:-16686}"
GRAFANA_PORT="${GRAFANA_PORT:-3002}"

declare -A SERVICES=(
    ["loki"]="$LOKI_PORT|/ready"
    ["pyroscope"]="$PYROSCOPE_PORT|/ready"
    ["prometheus"]="$PROMETHEUS_PORT|/-/ready"
    ["jaeger"]="$JAEGER_PORT|/"
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
    ((failed++))
fi
for svc in "${!SERVICES[@]}"; do
    IFS='|' read -r port endpoint <<< "${SERVICES[$svc]}"
    printf "  %-12s (port %s)... " "$svc" "$port"

    if curl -sf --max-time 5 "http://localhost:$port$endpoint" > /dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}FAIL${NC}"
        ((failed++))
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
pyroscope_ready=$(curl -sf --max-time 5 "http://localhost:$PYROSCOPE_PORT/ready" 2>/dev/null)
if [ "$pyroscope_ready" = "ready" ]; then
    echo -e "${GREEN}ready${NC}"
else
    echo -e "${YELLOW}not ready${NC}"
fi

# Verify trace ingestion (Jaeger)
printf "  Jaeger services:     "
jaeger_services=$(curl -s --max-time 5 "http://localhost:$JAEGER_PORT/api/services" 2>/dev/null | jq -r '.data | length' 2>/dev/null || echo "0")
if [ "$jaeger_services" -gt 0 ] 2>/dev/null; then
    echo -e "${GREEN}$jaeger_services services found${NC}"
else
    echo -e "${YELLOW}no services (traces may not be flowing yet)${NC}"
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
echo "  Jaeger:     http://localhost:$JAEGER_PORT"
echo "  Loki:       http://localhost:$LOKI_PORT (via Grafana Explore)"
echo "  Pyroscope:  http://localhost:$PYROSCOPE_PORT (via Grafana Explore)"
echo "  Alloy:      http://localhost:$ALLOY_PORT"
echo ""

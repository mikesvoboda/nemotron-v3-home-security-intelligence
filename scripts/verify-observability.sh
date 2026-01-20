#!/bin/bash
set -e

echo "=== Observability Stack Verification ==="

# Check all services healthy
declare -A PORTS=(
  ["loki"]=3100
  ["pyroscope"]=4040
  ["alloy"]=12345
  ["prometheus"]=9090
  ["jaeger"]=16686
  ["grafana"]=3000
)

for svc in "${!PORTS[@]}"; do
  port=${PORTS[$svc]}
  echo -n "Checking $svc:$port... "
  if curl -sf "http://localhost:$port/ready" > /dev/null 2>&1 || \
     curl -sf "http://localhost:$port/-/ready" > /dev/null 2>&1 || \
     curl -sf "http://localhost:$port/api/health" > /dev/null 2>&1; then
    echo "OK"
  else
    echo "FAIL"
  fi
done

# Verify log ingestion
echo -n "Loki log streams: "
curl -s 'http://localhost:3100/loki/api/v1/labels' | jq -r '.data | length'

# Verify profile ingestion
echo -n "Pyroscope apps: "
curl -s http://localhost:4040/api/v1/apps | jq -r 'length'

# Verify trace ingestion
echo -n "Jaeger services: "
curl -s http://localhost:16686/api/services | jq -r '.data | length'

echo "=== Verification Complete ==="

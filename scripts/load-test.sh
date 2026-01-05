#!/usr/bin/env bash
#
# k6 Load Test Runner Script
#
# Runs k6 load tests against the security dashboard API.
# Supports multiple test scenarios and configurable load profiles.
#
# Prerequisites:
#   - k6 must be installed: https://k6.io/docs/getting-started/installation/
#   - Backend must be running at BASE_URL (default: http://localhost:8000)
#
# Usage:
#   ./scripts/load-test.sh                    # Run all tests with average load
#   ./scripts/load-test.sh events             # Run events API tests only
#   ./scripts/load-test.sh cameras stress     # Run cameras tests with stress profile
#   ./scripts/load-test.sh all spike          # Run all tests with spike profile
#   ./scripts/load-test.sh websocket smoke    # Quick smoke test for WebSockets
#
# Environment Variables:
#   BASE_URL       - API base URL (default: http://localhost:8000)
#   WS_URL         - WebSocket URL (default: ws://localhost:8000)
#   API_KEY        - API key for authenticated endpoints (optional)
#   ADMIN_API_KEY  - Admin API key for seed endpoints (optional)
#   K6_OUT         - Output format (default: json=results/k6-results.json)
#
# Load Profiles:
#   smoke   - Quick validation (1 VU, 10 seconds)
#   average - Normal load (10 VUs, 2 minutes)
#   stress  - Heavy load (up to 100 VUs, 5 minutes)
#   spike   - Sudden traffic spikes (5->100->5 VUs)
#   soak    - Extended duration (30 VUs, 10+ minutes)
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
LOAD_TEST_DIR="$PROJECT_ROOT/tests/load"
RESULTS_DIR="$PROJECT_ROOT/results"

# Default configuration
DEFAULT_BASE_URL="http://localhost:8000"
DEFAULT_WS_URL="ws://localhost:8000"
DEFAULT_LOAD_PROFILE="average"

# Parse arguments
TEST_SUITE="${1:-all}"
LOAD_PROFILE="${2:-$DEFAULT_LOAD_PROFILE}"

# Available test suites
AVAILABLE_SUITES="all events cameras websocket mutations"

# Validate test suite
if ! echo "$AVAILABLE_SUITES" | grep -qw "$TEST_SUITE"; then
    echo -e "${RED}Error: Invalid test suite '$TEST_SUITE'${NC}"
    echo "Available suites: $AVAILABLE_SUITES"
    exit 1
fi

# Validate load profile
AVAILABLE_PROFILES="smoke average stress spike soak"
if ! echo "$AVAILABLE_PROFILES" | grep -qw "$LOAD_PROFILE"; then
    echo -e "${RED}Error: Invalid load profile '$LOAD_PROFILE'${NC}"
    echo "Available profiles: $AVAILABLE_PROFILES"
    exit 1
fi

# Check k6 is installed
if ! command -v k6 &> /dev/null; then
    echo -e "${RED}Error: k6 is not installed${NC}"
    echo "Install k6 from: https://k6.io/docs/getting-started/installation/"
    echo ""
    echo "Quick install options:"
    echo "  macOS:   brew install k6"
    echo "  Linux:   sudo apt-get install k6"
    echo "  Docker:  docker run -i grafana/k6 run -"
    exit 1
fi

# Set environment variables with defaults
export BASE_URL="${BASE_URL:-$DEFAULT_BASE_URL}"
export WS_URL="${WS_URL:-$DEFAULT_WS_URL}"
export LOAD_PROFILE="$LOAD_PROFILE"

# Create results directory
mkdir -p "$RESULTS_DIR"

# Generate timestamp for results
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_FILE="$RESULTS_DIR/k6-${TEST_SUITE}-${LOAD_PROFILE}-${TIMESTAMP}.json"
SUMMARY_FILE="$RESULTS_DIR/k6-${TEST_SUITE}-${LOAD_PROFILE}-${TIMESTAMP}.txt"

# Header
echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}   k6 Load Test Runner${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo -e "Test Suite:    ${GREEN}$TEST_SUITE${NC}"
echo -e "Load Profile:  ${GREEN}$LOAD_PROFILE${NC}"
echo -e "Base URL:      ${GREEN}$BASE_URL${NC}"
echo -e "WebSocket URL: ${GREEN}$WS_URL${NC}"
echo -e "Results File:  ${GREEN}$RESULTS_FILE${NC}"
echo ""

# Check API availability
echo -e "${YELLOW}Checking API availability...${NC}"
if curl -s --connect-timeout 5 "$BASE_URL/api/system/health/ready" > /dev/null 2>&1; then
    echo -e "${GREEN}API is reachable${NC}"
else
    echo -e "${RED}Warning: API at $BASE_URL may not be available${NC}"
    echo "Tests will proceed but may fail if the API is not running."
    echo ""
fi

# Select test file
case "$TEST_SUITE" in
    all)
        TEST_FILE="$LOAD_TEST_DIR/all.js"
        ;;
    events)
        TEST_FILE="$LOAD_TEST_DIR/events.js"
        ;;
    cameras)
        TEST_FILE="$LOAD_TEST_DIR/cameras.js"
        ;;
    websocket)
        TEST_FILE="$LOAD_TEST_DIR/websocket.js"
        ;;
    mutations)
        TEST_FILE="$LOAD_TEST_DIR/mutations.js"
        ;;
esac

# Verify test file exists
if [ ! -f "$TEST_FILE" ]; then
    echo -e "${RED}Error: Test file not found: $TEST_FILE${NC}"
    exit 1
fi

echo -e "${YELLOW}Running k6 load tests...${NC}"
echo ""

# Run k6 with JSON output and summary
set +e  # Don't exit on test failure
k6 run \
    --out "json=$RESULTS_FILE" \
    --summary-export="$SUMMARY_FILE" \
    --env "BASE_URL=$BASE_URL" \
    --env "WS_URL=$WS_URL" \
    --env "LOAD_PROFILE=$LOAD_PROFILE" \
    ${API_KEY:+--env "API_KEY=$API_KEY"} \
    ${ADMIN_API_KEY:+--env "ADMIN_API_KEY=$ADMIN_API_KEY"} \
    "$TEST_FILE"

EXIT_CODE=$?
set -e

echo ""
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}   Test Results${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}All thresholds passed!${NC}"
else
    echo -e "${RED}Some thresholds failed!${NC}"
    echo "Review the results above for details."
fi

echo ""
echo -e "Results saved to:"
echo -e "  JSON: ${GREEN}$RESULTS_FILE${NC}"
echo -e "  Summary: ${GREEN}$SUMMARY_FILE${NC}"
echo ""

# Show quick summary if jq is available
if command -v jq &> /dev/null && [ -f "$SUMMARY_FILE" ]; then
    echo -e "${YELLOW}Quick Summary:${NC}"
    echo ""

    # Extract key metrics from summary
    if [ -s "$SUMMARY_FILE" ]; then
        # Try to parse summary with jq
        HTTP_REQS=$(jq -r '.metrics.http_reqs.values.count // "N/A"' "$SUMMARY_FILE" 2>/dev/null || echo "N/A")
        HTTP_DURATION_P95=$(jq -r '.metrics.http_req_duration.values["p(95)"] // "N/A"' "$SUMMARY_FILE" 2>/dev/null || echo "N/A")
        HTTP_FAILED=$(jq -r '.metrics.http_req_failed.values.rate // "N/A"' "$SUMMARY_FILE" 2>/dev/null || echo "N/A")

        if [ "$HTTP_REQS" != "N/A" ]; then
            echo "  Total Requests:    $HTTP_REQS"
        fi
        if [ "$HTTP_DURATION_P95" != "N/A" ]; then
            printf "  Response Time (p95): %.2f ms\n" "$HTTP_DURATION_P95"
        fi
        if [ "$HTTP_FAILED" != "N/A" ]; then
            printf "  Error Rate:        %.4f%%\n" "$(echo "$HTTP_FAILED * 100" | bc -l 2>/dev/null || echo "N/A")"
        fi
        echo ""
    fi
fi

# Provide next steps
echo -e "${YELLOW}Next Steps:${NC}"
echo "  - View detailed results in the JSON file"
echo "  - Import to Grafana for visualization"
echo "  - Run with different profiles: smoke, stress, spike, soak"
echo ""

exit $EXIT_CODE

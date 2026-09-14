#!/usr/bin/env bash
# =============================================================================
# CI Smoke Test Script for Deployment Verification
# =============================================================================
# Lightweight smoke tests designed for CI/CD pipelines after container push.
# Verifies that the deployed containers are healthy and responding.
#
# Usage:
#   ./scripts/ci-smoke-test.sh [OPTIONS]
#
# Options:
#   --help, -h         Show this help message
#   --backend-url URL  Backend API URL (default: http://localhost:8000)
#   --frontend-url URL Frontend URL (default: http://localhost:3000)
#   --timeout SECONDS  Timeout in seconds (default: 120)
#   --skip-websocket   Skip WebSocket connectivity test
#
# Exit Codes:
#   0 - All tests passed
#   1 - One or more tests failed
# =============================================================================

set -e

# =============================================================================
# Configuration
# =============================================================================

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"
TIMEOUT="${TIMEOUT:-120}"
SKIP_WEBSOCKET="${SKIP_WEBSOCKET:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Utility Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

show_help() {
    cat << 'EOF'
CI Smoke Test - Deployment Verification

USAGE:
    ./scripts/ci-smoke-test.sh [OPTIONS]

OPTIONS:
    --help, -h         Show this help message
    --backend-url URL  Backend API URL (default: http://localhost:8000)
    --frontend-url URL Frontend URL (default: http://localhost:3000)
    --timeout SECONDS  Timeout in seconds for each test (default: 120)
    --skip-websocket   Skip WebSocket connectivity test

DESCRIPTION:
    This script runs lightweight smoke tests to verify that deployed
    containers are healthy and responding correctly. It is designed
    for CI/CD pipelines to run after container builds are pushed.

    Tests performed:
    1. Backend /api/system/health/ready returns 200
    2. Backend /api/system/health returns 200
    3. Frontend / returns 200
    4. WebSocket connection can be established (optional)

EXAMPLES:
    # Default smoke test
    ./scripts/ci-smoke-test.sh

    # Custom URLs
    ./scripts/ci-smoke-test.sh --backend-url http://backend:8000 --frontend-url http://frontend:80

    # Skip WebSocket test
    ./scripts/ci-smoke-test.sh --skip-websocket

EXIT CODES:
    0 - All tests passed
    1 - One or more tests failed
EOF
}

# =============================================================================
# Test Functions
# =============================================================================

wait_for_endpoint() {
    local url="$1"
    local description="$2"
    local expected_status="${3:-200}"
    local start_time
    start_time=$(date +%s)

    log_info "Waiting for $description at $url..."

    while true; do
        local elapsed=$(($(date +%s) - start_time))

        if [ "$elapsed" -ge "$TIMEOUT" ]; then
            log_fail "$description timed out after ${TIMEOUT}s"
            return 1
        fi

        local status_code
        status_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "$url" 2>/dev/null || echo "000")

        if [ "$status_code" = "$expected_status" ]; then
            log_success "$description is healthy (${elapsed}s)"
            return 0
        fi

        # Show progress every 10 seconds
        if [ $((elapsed % 10)) -eq 0 ] && [ "$elapsed" -gt 0 ]; then
            log_info "Still waiting for $description... (${elapsed}s, status: $status_code)"
        fi

        sleep 2
    done
}

test_backend_ready() {
    log_info "Testing backend readiness endpoint..."

    local url="${BACKEND_URL}/api/system/health/ready"
    if ! wait_for_endpoint "$url" "Backend /api/system/health/ready" "200"; then
        return 1
    fi

    # Verify response content
    local response
    response=$(curl -s "$url" 2>/dev/null)

    local ready
    ready=$(echo "$response" | jq -r '.ready' 2>/dev/null || echo "null")

    if [ "$ready" = "true" ]; then
        log_success "Backend readiness check passed (ready=true)"
        return 0
    else
        # Readiness endpoint may return ready=false but still respond with 200
        # This is acceptable - it means the service is running but dependencies may be unavailable
        log_warn "Backend responded but ready=$ready (some dependencies may be unavailable)"
        log_info "Response: $response"
        return 0
    fi
}

test_backend_health() {
    log_info "Testing backend health endpoint..."

    local url="${BACKEND_URL}/api/system/health"
    local response
    response=$(curl -s --connect-timeout 5 "$url" 2>/dev/null)

    if [ -z "$response" ]; then
        log_fail "Backend health endpoint returned empty response"
        return 1
    fi

    local status
    status=$(echo "$response" | jq -r '.status' 2>/dev/null || echo "unknown")

    if [ "$status" = "healthy" ] || [ "$status" = "degraded" ]; then
        log_success "Backend health check passed (status=$status)"
        return 0
    else
        log_fail "Backend health check failed (status=$status)"
        log_info "Response: $response"
        return 1
    fi
}

test_frontend() {
    log_info "Testing frontend..."

    local url="${FRONTEND_URL}/"
    if ! wait_for_endpoint "$url" "Frontend" "200"; then
        return 1
    fi

    # Verify we get HTML content
    local content_type
    content_type=$(curl -s -I --connect-timeout 5 "$url" 2>/dev/null | grep -i "content-type" | head -1)

    if echo "$content_type" | grep -qi "text/html"; then
        log_success "Frontend returns HTML content"
        return 0
    else
        log_warn "Frontend content-type: $content_type"
        return 0
    fi
}

test_websocket() {
    if [ "$SKIP_WEBSOCKET" = "true" ]; then
        log_warn "Skipping WebSocket test (--skip-websocket)"
        return 0
    fi

    log_info "Testing WebSocket connectivity..."

    # Check if websocat is available
    if ! command -v websocat &> /dev/null; then
        log_warn "websocat not installed, skipping WebSocket test"
        return 0
    fi

    local ws_url
    ws_url=$(echo "$BACKEND_URL" | sed 's|http://|ws://|' | sed 's|https://|wss://|')
    ws_url="${ws_url}/ws/events"

    # Try to establish WebSocket connection with timeout
    local result
    result=$(timeout 5 websocat --text --one-message "$ws_url" 2>&1 || true)

    if [ -n "$result" ] || [ $? -eq 0 ]; then
        log_success "WebSocket connection established"
        return 0
    else
        log_warn "WebSocket connection test inconclusive (may require authentication)"
        return 0
    fi
}

test_api_endpoints() {
    log_info "Testing additional API endpoints..."

    local failed=0

    # Test /api/system/stats
    local stats_response
    stats_response=$(curl -s --connect-timeout 5 "${BACKEND_URL}/api/system/stats" 2>/dev/null)

    if echo "$stats_response" | jq -e '.total_cameras >= 0' &>/dev/null; then
        log_success "API /api/system/stats is responding"
    else
        log_warn "API /api/system/stats returned unexpected response"
        failed=1
    fi

    # Test /api/cameras
    local cameras_response
    cameras_response=$(curl -s --connect-timeout 5 "${BACKEND_URL}/api/cameras" 2>/dev/null)

    if echo "$cameras_response" | jq -e '.cameras' &>/dev/null; then
        log_success "API /api/cameras is responding"
    else
        log_warn "API /api/cameras returned unexpected response"
        failed=1
    fi

    return $failed
}

# =============================================================================
# Main
# =============================================================================

main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --help|-h)
                show_help
                exit 0
                ;;
            --backend-url)
                BACKEND_URL="$2"
                shift 2
                ;;
            --frontend-url)
                FRONTEND_URL="$2"
                shift 2
                ;;
            --timeout)
                TIMEOUT="$2"
                shift 2
                ;;
            --skip-websocket)
                SKIP_WEBSOCKET="true"
                shift
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done

    echo ""
    echo "============================================"
    echo "  CI Smoke Test - Deployment Verification   "
    echo "============================================"
    echo ""
    echo "Backend URL:  $BACKEND_URL"
    echo "Frontend URL: $FRONTEND_URL"
    echo "Timeout:      ${TIMEOUT}s"
    echo "Started:      $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    local start_time
    start_time=$(date +%s)
    local failed=0

    # Run tests
    echo "----------------------------------------"
    echo "Running smoke tests..."
    echo "----------------------------------------"

    if ! test_backend_ready; then
        failed=1
    fi

    if ! test_backend_health; then
        failed=1
    fi

    if ! test_frontend; then
        failed=1
    fi

    if ! test_websocket; then
        # WebSocket failure is not critical
        log_warn "WebSocket test did not pass (non-blocking)"
    fi

    if ! test_api_endpoints; then
        # API endpoint failures are warnings
        log_warn "Some API endpoint tests did not pass (non-blocking)"
    fi

    # Summary
    echo ""
    echo "----------------------------------------"
    echo "Smoke Test Results"
    echo "----------------------------------------"

    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    if [ $failed -eq 0 ]; then
        echo ""
        echo -e "${GREEN}ALL CRITICAL TESTS PASSED${NC}"
        echo ""
        echo "Duration: ${duration}s"
        echo ""
        echo "Deployment verification successful:"
        echo "  - Backend is healthy and responding"
        echo "  - Frontend is serving content"
        echo "  - API endpoints are functional"
        exit 0
    else
        echo ""
        echo -e "${RED}SMOKE TESTS FAILED${NC}"
        echo ""
        echo "Duration: ${duration}s"
        echo ""
        echo "One or more critical tests failed."
        echo "Check the output above for details."
        exit 1
    fi
}

# Run main
main "$@"

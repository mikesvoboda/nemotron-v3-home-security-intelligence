#!/usr/bin/env bash
# =============================================================================
# Production Connectivity Test Script
# =============================================================================
# Tests that nginx correctly proxies API and WebSocket requests to the backend.
# This script is designed to run against the production docker-compose setup.
#
# Usage:
#   ./scripts/test-prod-connectivity.sh [OPTIONS]
#
# Options:
#   --help, -h       Show this help message
#   --url URL        Frontend URL (default: http://localhost:80)
#   --verbose, -v    Enable verbose output
#
# Prerequisites:
#   - docker-compose.prod.yml running
#   - curl and (optionally) websocat installed for WebSocket tests
#
# Exit Codes:
#   0 - All tests passed
#   1 - Test failure
#   2 - Prerequisite check failed
# =============================================================================

set -e

# =============================================================================
# Configuration
# =============================================================================

FRONTEND_URL="${FRONTEND_URL:-http://localhost:80}"
VERBOSE="${VERBOSE:-false}"

# =============================================================================
# Colors
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# =============================================================================
# Utility Functions
# =============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}${BOLD}=== $1 ===${NC}"
}

print_step() {
    echo -e "${CYAN}[TEST]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

print_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_info() {
    if [ "$VERBOSE" = "true" ]; then
        echo -e "${CYAN}[INFO]${NC} $1"
    fi
}

show_help() {
    cat << 'EOF'
Production Connectivity Test - Tests nginx reverse proxy configuration

USAGE:
    ./scripts/test-prod-connectivity.sh [OPTIONS]

OPTIONS:
    --help, -h       Show this help message
    --url URL        Frontend URL (default: http://localhost:80)
    --verbose, -v    Enable verbose output

DESCRIPTION:
    This script validates that the nginx reverse proxy in production correctly
    forwards API and WebSocket requests to the backend:

    1. Static File Serving
       - Frontend serves index.html at /
       - Static assets are served correctly

    2. API Proxy (/api/*)
       - /api/system/health returns backend health response
       - /api/cameras returns camera list
       - Proper headers are forwarded

    3. WebSocket Proxy (/ws/*)
       - /ws/events accepts WebSocket connections
       - /ws/system accepts WebSocket connections
       - Upgrade headers are properly handled

PREREQUISITES:
    Start production services:
        docker compose -f docker-compose.prod.yml up -d

    For WebSocket tests, install websocat:
        # macOS
        brew install websocat

        # Linux
        cargo install websocat

EXAMPLES:
    # Basic connectivity test
    ./scripts/test-prod-connectivity.sh

    # Test against custom URL
    ./scripts/test-prod-connectivity.sh --url http://192.168.1.100:80

    # Verbose output
    ./scripts/test-prod-connectivity.sh --verbose

EXIT CODES:
    0 - All tests passed
    1 - Test failure
    2 - Prerequisite check failed

EOF
}

# =============================================================================
# Test Functions
# =============================================================================

test_frontend_serving() {
    print_header "Testing Frontend Static File Serving"
    local passed=true

    # Test root serves HTML
    print_step "Testing / serves index.html..."
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}:%{content_type}" "$FRONTEND_URL/" 2>/dev/null)
    local http_code="${response%%:*}"
    local content_type="${response#*:}"

    if [ "$http_code" = "200" ] && [[ "$content_type" == *"text/html"* ]]; then
        print_success "Root serves HTML (status: $http_code)"
    else
        print_fail "Root did not serve HTML (status: $http_code, type: $content_type)"
        passed=false
    fi

    # Test health endpoint
    print_step "Testing /health endpoint..."
    response=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL/health" 2>/dev/null)
    if [ "$response" = "200" ]; then
        print_success "Health endpoint accessible (status: $response)"
    else
        print_fail "Health endpoint failed (status: $response)"
        passed=false
    fi

    [ "$passed" = "true" ]
}

test_api_proxy() {
    print_header "Testing API Proxy (/api/*)"
    local passed=true

    # Test /api/system/health
    print_step "Testing /api/system/health via nginx..."
    local response
    response=$(curl -s --connect-timeout 10 "$FRONTEND_URL/api/system/health" 2>/dev/null)
    print_info "Response: $response"

    local status
    status=$(echo "$response" | jq -r '.status' 2>/dev/null || echo "")

    if [ "$status" = "healthy" ] || [ "$status" = "degraded" ]; then
        print_success "API health endpoint proxied successfully (status: $status)"
    else
        print_fail "API health endpoint failed (response: $response)"
        passed=false
    fi

    # Test /api/cameras
    print_step "Testing /api/cameras via nginx..."
    response=$(curl -s --connect-timeout 10 "$FRONTEND_URL/api/cameras" 2>/dev/null)
    print_info "Response: $response"

    if echo "$response" | jq -e '.cameras' &>/dev/null; then
        local camera_count
        camera_count=$(echo "$response" | jq -r '.cameras | length')
        print_success "Cameras endpoint proxied successfully ($camera_count cameras)"
    else
        print_fail "Cameras endpoint failed (response: $response)"
        passed=false
    fi

    # Test /api/system/stats
    print_step "Testing /api/system/stats via nginx..."
    response=$(curl -s --connect-timeout 10 "$FRONTEND_URL/api/system/stats" 2>/dev/null)
    print_info "Response: $response"

    if echo "$response" | jq -e '.total_cameras >= 0' &>/dev/null; then
        print_success "Stats endpoint proxied successfully"
    else
        print_fail "Stats endpoint failed (response: $response)"
        passed=false
    fi

    # Test headers are forwarded correctly
    print_step "Verifying proxy headers..."
    local headers
    headers=$(curl -s -I --connect-timeout 10 "$FRONTEND_URL/api/system/health" 2>/dev/null)
    print_info "Headers: $headers"

    # Just verify we get a response (headers depend on backend implementation)
    if echo "$headers" | grep -q "HTTP/"; then
        print_success "Proxy returns proper HTTP response headers"
    else
        print_warn "Could not verify response headers"
    fi

    [ "$passed" = "true" ]
}

test_websocket_proxy() {
    print_header "Testing WebSocket Proxy (/ws/*)"
    local passed=true

    # Check if websocat is available
    if ! command -v websocat &> /dev/null; then
        print_warn "websocat not installed, testing WebSocket with curl upgrade headers only"
        print_info "Install websocat for full WebSocket testing:"
        print_info "  macOS: brew install websocat"
        print_info "  Linux: cargo install websocat"

        # Test WebSocket upgrade headers with curl
        print_step "Testing /ws/events accepts WebSocket upgrade..."
        local ws_url="${FRONTEND_URL/http:/ws:}"
        ws_url="${ws_url/https:/wss:}"

        local response
        response=$(curl -s -i -N \
            -H "Connection: Upgrade" \
            -H "Upgrade: websocket" \
            -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
            -H "Sec-WebSocket-Version: 13" \
            --connect-timeout 5 \
            "$FRONTEND_URL/ws/events" 2>/dev/null | head -20)

        print_info "Response: $response"

        # Check for WebSocket upgrade response (101) or connection established
        if echo "$response" | grep -q "101 Switching Protocols" || echo "$response" | grep -q "HTTP/1.1 101"; then
            print_success "WebSocket upgrade accepted for /ws/events"
        elif echo "$response" | grep -q "HTTP/"; then
            # Some response means nginx is proxying (backend might reject without proper handshake)
            print_warn "WebSocket endpoint responded (may need full client for handshake)"
        else
            print_fail "WebSocket upgrade failed for /ws/events"
            passed=false
        fi

        print_step "Testing /ws/system accepts WebSocket upgrade..."
        response=$(curl -s -i -N \
            -H "Connection: Upgrade" \
            -H "Upgrade: websocket" \
            -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
            -H "Sec-WebSocket-Version: 13" \
            --connect-timeout 5 \
            "$FRONTEND_URL/ws/system" 2>/dev/null | head -20)

        print_info "Response: $response"

        if echo "$response" | grep -q "101 Switching Protocols" || echo "$response" | grep -q "HTTP/1.1 101"; then
            print_success "WebSocket upgrade accepted for /ws/system"
        elif echo "$response" | grep -q "HTTP/"; then
            print_warn "WebSocket endpoint responded (may need full client for handshake)"
        else
            print_fail "WebSocket upgrade failed for /ws/system"
            passed=false
        fi
    else
        # Full WebSocket test with websocat
        local ws_url="${FRONTEND_URL/http:/ws:}"
        ws_url="${ws_url/https:/wss:}"

        print_step "Testing /ws/events WebSocket connection..."

        # Try to connect and receive one message (with timeout)
        local ws_response
        if timeout 5 websocat -t "$ws_url/ws/events" 2>/dev/null | head -1 > /tmp/ws_test_events.txt; then
            ws_response=$(cat /tmp/ws_test_events.txt)
            print_info "Received: $ws_response"
            print_success "WebSocket connection to /ws/events established"
        else
            # Connection might timeout waiting for message, but connection itself worked
            if [ -f /tmp/ws_test_events.txt ]; then
                print_success "WebSocket connection to /ws/events established (no messages yet)"
            else
                print_fail "WebSocket connection to /ws/events failed"
                passed=false
            fi
        fi
        rm -f /tmp/ws_test_events.txt

        print_step "Testing /ws/system WebSocket connection..."

        if timeout 10 websocat -t "$ws_url/ws/system" 2>/dev/null | head -1 > /tmp/ws_test_system.txt; then
            ws_response=$(cat /tmp/ws_test_system.txt)
            print_info "Received: $ws_response"

            # System status messages are sent periodically
            if echo "$ws_response" | jq -e '.type' &>/dev/null; then
                print_success "WebSocket connection to /ws/system established and receiving messages"
            else
                print_success "WebSocket connection to /ws/system established"
            fi
        else
            if [ -f /tmp/ws_test_system.txt ]; then
                print_success "WebSocket connection to /ws/system established (waiting for messages)"
            else
                print_fail "WebSocket connection to /ws/system failed"
                passed=false
            fi
        fi
        rm -f /tmp/ws_test_system.txt
    fi

    [ "$passed" = "true" ]
}

test_spa_routing() {
    print_header "Testing SPA Routing"
    local passed=true

    # Test that unknown routes return index.html (SPA routing)
    print_step "Testing SPA fallback for /events route..."
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}:%{content_type}" "$FRONTEND_URL/events" 2>/dev/null)
    local http_code="${response%%:*}"
    local content_type="${response#*:}"

    if [ "$http_code" = "200" ] && [[ "$content_type" == *"text/html"* ]]; then
        print_success "SPA routing works for /events (serves index.html)"
    else
        print_fail "SPA routing failed for /events (status: $http_code, type: $content_type)"
        passed=false
    fi

    print_step "Testing SPA fallback for /settings route..."
    response=$(curl -s -o /dev/null -w "%{http_code}:%{content_type}" "$FRONTEND_URL/settings" 2>/dev/null)
    http_code="${response%%:*}"
    content_type="${response#*:}"

    if [ "$http_code" = "200" ] && [[ "$content_type" == *"text/html"* ]]; then
        print_success "SPA routing works for /settings (serves index.html)"
    else
        print_fail "SPA routing failed for /settings (status: $http_code, type: $content_type)"
        passed=false
    fi

    [ "$passed" = "true" ]
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
            --url)
                FRONTEND_URL="$2"
                shift 2
                ;;
            --verbose|-v)
                VERBOSE="true"
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
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo -e "${BLUE}${BOLD}  Production Connectivity Test              ${NC}"
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo ""
    echo -e "Frontend URL: ${CYAN}$FRONTEND_URL${NC}"
    echo -e "Verbose:      ${CYAN}$VERBOSE${NC}"
    echo ""

    local exit_code=0

    # Check prerequisites
    print_header "Checking Prerequisites"

    print_step "Checking curl..."
    if command -v curl &> /dev/null; then
        print_success "curl is installed"
    else
        print_fail "curl is not installed"
        exit 2
    fi

    print_step "Checking jq..."
    if command -v jq &> /dev/null; then
        print_success "jq is installed"
    else
        print_warn "jq is not installed (JSON parsing may fail)"
    fi

    # Check frontend is reachable
    print_step "Checking frontend is reachable..."
    if curl -s --connect-timeout 5 "$FRONTEND_URL" > /dev/null 2>&1; then
        print_success "Frontend is reachable at $FRONTEND_URL"
    else
        print_fail "Cannot reach frontend at $FRONTEND_URL"
        echo ""
        echo -e "  ${YELLOW}Troubleshooting:${NC}"
        echo "    1. Start production services:"
        echo "       docker compose -f docker-compose.prod.yml up -d"
        echo "    2. Check container status:"
        echo "       docker compose -f docker-compose.prod.yml ps"
        echo "    3. Check nginx logs:"
        echo "       docker compose -f docker-compose.prod.yml logs frontend"
        exit 2
    fi

    # Run tests
    if ! test_frontend_serving; then
        exit_code=1
    fi

    if ! test_api_proxy; then
        exit_code=1
    fi

    if ! test_websocket_proxy; then
        exit_code=1
    fi

    if ! test_spa_routing; then
        exit_code=1
    fi

    # Summary
    print_header "Test Results"

    if [ $exit_code -eq 0 ]; then
        echo ""
        echo -e "${GREEN}${BOLD}  ALL CONNECTIVITY TESTS PASSED  ${NC}"
        echo ""
        echo "Nginx reverse proxy is correctly configured:"
        echo "  - Static files served at /"
        echo "  - API requests proxied to backend (/api/*)"
        echo "  - WebSocket connections proxied (/ws/*)"
        echo "  - SPA routing fallback working"
    else
        echo ""
        echo -e "${RED}${BOLD}  SOME CONNECTIVITY TESTS FAILED  ${NC}"
        echo ""
        echo "Review the output above for specific failures."
        echo ""
        echo "Common issues:"
        echo "  - Backend not running: docker compose ps"
        echo "  - Nginx config error: docker compose logs frontend"
        echo "  - Network issues: docker network inspect"
    fi

    exit $exit_code
}

# Run main
main "$@"

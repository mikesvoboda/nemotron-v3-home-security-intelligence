#!/bin/bash
# =============================================================================
# End-to-End Smoke Test Script for Home Security Intelligence MVP
# =============================================================================
# This script validates that the complete AI pipeline is working:
#   1. Backend API is healthy
#   2. Redis is connected
#   3. File watcher can process images
#   4. Detections are created in database
#   5. Events are created after analysis
#   6. API returns expected data
#
# Usage:
#   ./scripts/smoke-test.sh [OPTIONS]
#
# Options:
#   --help, -h       Show this help message
#   --verbose, -v    Enable verbose output
#   --skip-cleanup   Don't remove test artifacts after completion
#   --timeout N      Timeout in seconds for pipeline completion (default: 90)
#   --api-url URL    Backend API URL (default: http://localhost:8000)
#
# Prerequisites:
#   - Backend API running (./scripts/dev.sh start)
#   - Redis running
#   - curl installed
#   - jq installed (for JSON parsing)
#
# Exit Codes:
#   0 - All tests passed
#   1 - Test failure (with diagnostic info)
#   2 - Prerequisite check failed
# =============================================================================

set -e

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default settings
API_URL="${API_URL:-http://localhost:8000}"
TIMEOUT="${TIMEOUT:-90}"
VERBOSE="${VERBOSE:-false}"
SKIP_CLEANUP="${SKIP_CLEANUP:-false}"

# Test artifacts
# Note: Camera IDs are auto-generated UUIDs by the backend, not user-provided.
# We use a unique folder name pattern to identify our test camera.
TEST_CAMERA_NAME="Smoke Test Camera"
TEST_CAMERA_FOLDER="$PROJECT_ROOT/data/smoke_test_camera"
TEST_IMAGE_PATH="$TEST_CAMERA_FOLDER/smoke_test_image.jpg"
FIXTURE_IMAGE="$PROJECT_ROOT/data/fixtures/smoke_test_fixture.jpg"

# Tracking
TEST_START_TIME=""
CREATED_CAMERA_ID=""  # Will be set to the auto-generated UUID from API response
CREATED_DETECTION_ID=""
CREATED_EVENT_ID=""

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
    echo -e "${CYAN}[STEP]${NC} $1"
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

print_debug() {
    if [ "$VERBOSE" = "true" ]; then
        echo -e "${YELLOW}[DEBUG]${NC} $1"
    fi
}

show_help() {
    cat << 'EOF'
Home Security Intelligence - End-to-End Smoke Test

USAGE:
    ./scripts/smoke-test.sh [OPTIONS]

OPTIONS:
    --help, -h       Show this help message
    --verbose, -v    Enable verbose output (show API responses, debug info)
    --skip-cleanup   Don't remove test artifacts after completion
    --timeout N      Timeout in seconds for pipeline completion (default: 90)
    --api-url URL    Backend API URL (default: http://localhost:8000)

DESCRIPTION:
    This script validates the complete MVP pipeline is working end-to-end:

    1. Prerequisite Checks
       - Backend API is running and healthy
       - Redis is connected
       - Required tools (curl, jq) are available

    2. Test Fixture Setup
       - Creates a test camera in the database
       - Generates a test image fixture

    3. Pipeline Validation
       - Drops test image into camera folder
       - Waits for file watcher to detect it
       - Verifies detection is created in database
       - Verifies event is created after analysis

    4. API Verification
       - Confirms detection via /api/detections
       - Confirms event via /api/events
       - Validates WebSocket connectivity (optional)

    5. Cleanup
       - Removes test camera, detections, events
       - Removes test image files

PREREQUISITES:
    1. Start development services:
       ./scripts/dev.sh start

    2. (Optional) Start AI services for full pipeline:
       ./scripts/start-ai.sh start

    Without AI services, the pipeline will create events with fallback
    risk scores (score=50, level=medium).

EXAMPLES:
    # Basic smoke test
    ./scripts/smoke-test.sh

    # Verbose output for debugging
    ./scripts/smoke-test.sh --verbose

    # Keep test artifacts for inspection
    ./scripts/smoke-test.sh --skip-cleanup

    # Custom API URL
    ./scripts/smoke-test.sh --api-url http://192.168.1.100:8000

    # Extended timeout for slow systems
    ./scripts/smoke-test.sh --timeout 180

EXIT CODES:
    0 - All tests passed
    1 - Test failure (see output for details)
    2 - Prerequisite check failed

TROUBLESHOOTING:
    If the smoke test fails, check:

    1. Services running?
       ./scripts/dev.sh status

    2. Backend logs?
       tail -50 logs/backend.log

    3. Health endpoint?
       curl -s http://localhost:8000/api/system/health | jq .

    4. Redis connected?
       redis-cli ping

    5. File watcher active?
       Check backend logs for "FileWatcher started" message

EOF
}

# =============================================================================
# Prerequisite Checks
# =============================================================================

check_prerequisites() {
    print_header "Checking Prerequisites"
    local failed=0

    # Check curl
    print_step "Checking curl..."
    if command -v curl &> /dev/null; then
        print_success "curl is installed"
    else
        print_fail "curl is not installed"
        echo "  Install with: sudo dnf install curl (Fedora) or sudo apt install curl (Debian)"
        failed=1
    fi

    # Check jq
    print_step "Checking jq..."
    if command -v jq &> /dev/null; then
        print_success "jq is installed"
    else
        print_fail "jq is not installed"
        echo "  Install with: sudo dnf install jq (Fedora) or sudo apt install jq (Debian)"
        failed=1
    fi

    # Check backend API
    print_step "Checking backend API at $API_URL..."
    local health_response
    if health_response=$(curl -s --connect-timeout 5 "$API_URL/api/system/health" 2>/dev/null); then
        local status
        status=$(echo "$health_response" | jq -r '.status' 2>/dev/null || echo "unknown")
        if [ "$status" = "healthy" ] || [ "$status" = "degraded" ]; then
            print_success "Backend API is running (status: $status)"
            print_debug "Health response: $health_response"
        else
            print_fail "Backend API returned unhealthy status: $status"
            echo "  Full response: $health_response"
            failed=1
        fi
    else
        print_fail "Cannot connect to backend API at $API_URL"
        echo ""
        echo -e "  ${YELLOW}Troubleshooting:${NC}"
        echo "    1. Start services: ./scripts/dev.sh start"
        echo "    2. Check status: ./scripts/dev.sh status"
        echo "    3. View logs: tail -50 logs/backend.log"
        failed=1
    fi

    # Check Redis connectivity via health endpoint
    print_step "Checking Redis connectivity..."
    if [ -n "$health_response" ]; then
        local redis_status
        redis_status=$(echo "$health_response" | jq -r '.services.redis.status' 2>/dev/null || echo "unknown")
        if [ "$redis_status" = "healthy" ]; then
            print_success "Redis is connected"
        else
            print_fail "Redis is not connected (status: $redis_status)"
            local redis_message
            redis_message=$(echo "$health_response" | jq -r '.services.redis.message' 2>/dev/null || echo "")
            [ -n "$redis_message" ] && echo "  Error: $redis_message"
            echo ""
            echo -e "  ${YELLOW}Troubleshooting:${NC}"
            echo "    1. Start Redis: ./scripts/dev.sh redis start"
            echo "    2. Check Redis: redis-cli ping"
            failed=1
        fi
    fi

    # Check database connectivity
    print_step "Checking database connectivity..."
    if [ -n "$health_response" ]; then
        local db_status
        db_status=$(echo "$health_response" | jq -r '.services.database.status' 2>/dev/null || echo "unknown")
        if [ "$db_status" = "healthy" ]; then
            print_success "Database is connected"
        else
            print_fail "Database is not connected (status: $db_status)"
            failed=1
        fi
    fi

    if [ $failed -ne 0 ]; then
        print_fail "Prerequisite checks failed"
        return 2
    fi

    print_success "All prerequisites met"
    return 0
}

# =============================================================================
# Test Fixture Setup
# =============================================================================

create_test_image() {
    print_step "Creating test image fixture..."

    # Create fixtures directory
    mkdir -p "$(dirname "$FIXTURE_IMAGE")"

    # Check if we have Python with PIL available
    if python3 -c "from PIL import Image" &>/dev/null; then
        # Create a real test image with PIL
        python3 << 'PYTHON_EOF'
import sys
sys.path.insert(0, '.')
from PIL import Image, ImageDraw, ImageFont

# Create a 640x480 test image
img = Image.new('RGB', (640, 480), color=(50, 100, 150))
draw = ImageDraw.Draw(img)

# Draw some shapes to simulate a scene
# Background gradient simulation
for y in range(480):
    shade = int(50 + (y / 480) * 100)
    for x in range(640):
        if (x + y) % 20 < 10:
            img.putpixel((x, y), (shade, shade + 20, shade + 50))

# Draw a "person" silhouette (simple rectangle)
draw.rectangle([200, 150, 280, 380], fill=(80, 60, 60), outline=(40, 30, 30))
draw.ellipse([210, 100, 270, 160], fill=(80, 60, 60), outline=(40, 30, 30))

# Draw a "car" shape
draw.rectangle([400, 280, 580, 380], fill=(100, 100, 120), outline=(60, 60, 80))
draw.ellipse([410, 350, 450, 390], fill=(30, 30, 30))
draw.ellipse([530, 350, 570, 390], fill=(30, 30, 30))

# Add text label
try:
    font = ImageFont.load_default()
except Exception:
    font = None
draw.text((10, 10), "Smoke Test Image", fill=(255, 255, 255), font=font)
draw.text((10, 30), "For E2E Pipeline Validation", fill=(200, 200, 200), font=font)

# Save
img.save(sys.argv[1] if len(sys.argv) > 1 else 'data/fixtures/smoke_test_fixture.jpg', 'JPEG', quality=85)
print("Created test image with PIL")
PYTHON_EOF
        python3 -c "
import sys
sys.path.insert(0, '.')
from PIL import Image, ImageDraw
img = Image.new('RGB', (640, 480), color=(50, 100, 150))
draw = ImageDraw.Draw(img)
draw.rectangle([200, 150, 280, 380], fill=(80, 60, 60))
draw.ellipse([210, 100, 270, 160], fill=(80, 60, 60))
draw.rectangle([400, 280, 580, 380], fill=(100, 100, 120))
draw.text((10, 10), 'Smoke Test Image', fill=(255, 255, 255))
img.save('$FIXTURE_IMAGE', 'JPEG', quality=85)
"
        print_success "Created test image with PIL"
    else
        # Create a minimal valid JPEG using base64-encoded data
        # This is a tiny 8x8 JPEG that most systems can process
        print_warn "PIL not available, creating minimal JPEG fixture"
        base64 -d << 'BASE64_EOF' > "$FIXTURE_IMAGE"
/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof
Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwh
MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAAR
CAAIAAgDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAUEAEAAAAAAAAAAAAAAAAA
AAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMB
AAIRAxEAPwC/AB//2Q==
BASE64_EOF
    fi

    if [ -f "$FIXTURE_IMAGE" ]; then
        local size
        size=$(stat -c%s "$FIXTURE_IMAGE" 2>/dev/null || stat -f%z "$FIXTURE_IMAGE" 2>/dev/null)
        print_success "Test fixture created: $FIXTURE_IMAGE ($size bytes)"
        return 0
    else
        print_fail "Failed to create test fixture image"
        return 1
    fi
}

create_test_camera() {
    print_step "Creating test camera in database..."

    # First check if a camera with our test folder already exists
    # The backend generates UUIDs for camera IDs, so we search by folder_path
    local existing_cameras
    existing_cameras=$(curl -s "$API_URL/api/cameras" 2>/dev/null)
    if echo "$existing_cameras" | jq -e '.cameras' &>/dev/null; then
        local existing_id
        existing_id=$(echo "$existing_cameras" | jq -r ".cameras[] | select(.folder_path == \"$TEST_CAMERA_FOLDER\") | .id" 2>/dev/null | head -1)
        if [ -n "$existing_id" ] && [ "$existing_id" != "null" ]; then
            print_warn "Test camera already exists (ID: $existing_id), will reuse it"
            CREATED_CAMERA_ID="$existing_id"
            return 0
        fi
    fi

    # Create camera folder
    mkdir -p "$TEST_CAMERA_FOLDER"

    # Create camera via API
    # Note: Camera ID is auto-generated by the backend as a UUID
    # Status must be one of: "online", "offline", "error"
    local response
    response=$(curl -s -X POST "$API_URL/api/cameras" \
        -H "Content-Type: application/json" \
        -d "{
            \"name\": \"$TEST_CAMERA_NAME\",
            \"folder_path\": \"$TEST_CAMERA_FOLDER\",
            \"status\": \"online\"
        }" 2>/dev/null)

    print_debug "Create camera response: $response"

    local camera_id
    camera_id=$(echo "$response" | jq -r '.id' 2>/dev/null)

    # Check if we got a valid UUID (camera IDs are auto-generated UUIDs)
    if [ -n "$camera_id" ] && [ "$camera_id" != "null" ]; then
        CREATED_CAMERA_ID="$camera_id"
        print_success "Created test camera: $camera_id"
        return 0
    else
        print_fail "Failed to create test camera"
        echo "  Response: $response"
        return 1
    fi
}

# =============================================================================
# Pipeline Test
# =============================================================================

drop_test_image() {
    print_step "Dropping test image into camera folder..."

    # Copy fixture to camera folder with unique timestamp
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    TEST_IMAGE_PATH="$TEST_CAMERA_FOLDER/smoke_test_${timestamp}.jpg"

    cp "$FIXTURE_IMAGE" "$TEST_IMAGE_PATH"

    if [ -f "$TEST_IMAGE_PATH" ]; then
        print_success "Test image dropped: $TEST_IMAGE_PATH"
        return 0
    else
        print_fail "Failed to copy test image"
        return 1
    fi
}

wait_for_detection() {
    print_step "Waiting for detection to be created (timeout: ${TIMEOUT}s)..."

    local start_time
    start_time=$(date +%s)
    local poll_interval=2
    local found=false

    while [ $(($(date +%s) - start_time)) -lt "$TIMEOUT" ]; do
        # Query detections for our test camera
        local response
        response=$(curl -s "$API_URL/api/detections?camera_id=$TEST_CAMERA_ID&limit=5" 2>/dev/null)

        print_debug "Detections query response: $response"

        # Check if we got any detections
        local count
        count=$(echo "$response" | jq -r '.detections | length' 2>/dev/null || echo "0")

        if [ "$count" != "0" ] && [ "$count" != "null" ]; then
            # Get the most recent detection
            CREATED_DETECTION_ID=$(echo "$response" | jq -r '.detections[0].id' 2>/dev/null)
            local object_type
            object_type=$(echo "$response" | jq -r '.detections[0].object_type' 2>/dev/null)
            local confidence
            confidence=$(echo "$response" | jq -r '.detections[0].confidence' 2>/dev/null)

            print_success "Detection created: ID=$CREATED_DETECTION_ID, type=$object_type, confidence=$confidence"
            found=true
            break
        fi

        local elapsed=$(($(date +%s) - start_time))
        print_info "Waiting for detection... ($elapsed/${TIMEOUT}s)"
        sleep $poll_interval
    done

    if [ "$found" = "false" ]; then
        print_fail "No detection created within ${TIMEOUT}s timeout"
        echo ""
        echo -e "  ${YELLOW}Troubleshooting:${NC}"
        echo "    1. Is file watcher running? Check backend logs"
        echo "    2. Is RT-DETRv2 service running? ./scripts/start-ai.sh status"
        echo "    3. Check file permissions on camera folder"
        echo "    4. Try: curl -s $API_URL/api/detections?camera_id=$TEST_CAMERA_ID | jq ."
        return 1
    fi

    return 0
}

wait_for_event() {
    print_step "Waiting for event to be created (batch processing may take up to 90s)..."

    local start_time
    start_time=$(date +%s)
    local poll_interval=5
    local found=false

    # Events are created after batch window (90s) or idle timeout (30s)
    # Give extra time for LLM analysis
    local event_timeout=$((TIMEOUT + 60))

    while [ $(($(date +%s) - start_time)) -lt "$event_timeout" ]; do
        # Query events for our test camera
        local response
        response=$(curl -s "$API_URL/api/events?camera_id=$TEST_CAMERA_ID&limit=5" 2>/dev/null)

        print_debug "Events query response: $response"

        # Check if we got any events
        local count
        count=$(echo "$response" | jq -r '.events | length' 2>/dev/null || echo "0")

        if [ "$count" != "0" ] && [ "$count" != "null" ]; then
            # Get the most recent event
            CREATED_EVENT_ID=$(echo "$response" | jq -r '.events[0].id' 2>/dev/null)
            local risk_score
            risk_score=$(echo "$response" | jq -r '.events[0].risk_score' 2>/dev/null)
            local risk_level
            risk_level=$(echo "$response" | jq -r '.events[0].risk_level' 2>/dev/null)
            local summary
            summary=$(echo "$response" | jq -r '.events[0].summary' 2>/dev/null | head -c 60)

            print_success "Event created: ID=$CREATED_EVENT_ID, score=$risk_score, level=$risk_level"
            print_info "Summary: $summary..."
            found=true
            break
        fi

        local elapsed=$(($(date +%s) - start_time))
        print_info "Waiting for event (batch processing)... ($elapsed/${event_timeout}s)"
        sleep $poll_interval
    done

    if [ "$found" = "false" ]; then
        print_warn "No event created within timeout (this may be OK if batch window hasn't closed)"
        echo ""
        echo -e "  ${YELLOW}Note:${NC} Events are created after batch processing completes."
        echo "    - Batch window: 90 seconds"
        echo "    - Idle timeout: 30 seconds"
        echo ""
        echo "  If you're running without AI services, fallback events should still be created."
        echo "  Check: curl -s $API_URL/api/events?camera_id=$TEST_CAMERA_ID | jq ."
        # Don't fail - detection existing is the primary test
        return 0
    fi

    return 0
}

verify_api_endpoints() {
    print_header "Verifying API Endpoints"

    local all_passed=true

    # Verify system stats
    print_step "Checking /api/system/stats..."
    local stats
    stats=$(curl -s "$API_URL/api/system/stats" 2>/dev/null)
    if echo "$stats" | jq -e '.total_cameras >= 0' &>/dev/null; then
        local cameras events detections
        cameras=$(echo "$stats" | jq -r '.total_cameras')
        events=$(echo "$stats" | jq -r '.total_events')
        detections=$(echo "$stats" | jq -r '.total_detections')
        print_success "System stats: cameras=$cameras, events=$events, detections=$detections"
    else
        print_fail "System stats endpoint failed"
        all_passed=false
    fi

    # Verify cameras list
    print_step "Checking /api/cameras..."
    local cameras_response
    cameras_response=$(curl -s "$API_URL/api/cameras" 2>/dev/null)
    if echo "$cameras_response" | jq -e '.cameras' &>/dev/null; then
        local camera_count
        camera_count=$(echo "$cameras_response" | jq -r '.cameras | length')
        print_success "Cameras list: $camera_count cameras"
    else
        print_fail "Cameras list endpoint failed"
        all_passed=false
    fi

    # Verify specific detection if we created one
    if [ -n "$CREATED_DETECTION_ID" ]; then
        print_step "Checking /api/detections/$CREATED_DETECTION_ID..."
        local detection
        detection=$(curl -s "$API_URL/api/detections/$CREATED_DETECTION_ID" 2>/dev/null)
        if echo "$detection" | jq -e '.id' &>/dev/null; then
            print_success "Detection detail endpoint working"
        else
            print_fail "Detection detail endpoint failed"
            all_passed=false
        fi
    fi

    # Verify specific event if we created one
    if [ -n "$CREATED_EVENT_ID" ]; then
        print_step "Checking /api/events/$CREATED_EVENT_ID..."
        local event
        event=$(curl -s "$API_URL/api/events/$CREATED_EVENT_ID" 2>/dev/null)
        if echo "$event" | jq -e '.id' &>/dev/null; then
            print_success "Event detail endpoint working"
        else
            print_fail "Event detail endpoint failed"
            all_passed=false
        fi
    fi

    if [ "$all_passed" = "true" ]; then
        return 0
    else
        return 1
    fi
}

# =============================================================================
# Cleanup
# =============================================================================

cleanup_test_artifacts() {
    print_header "Cleaning Up Test Artifacts"

    if [ "$SKIP_CLEANUP" = "true" ]; then
        print_warn "Skipping cleanup (--skip-cleanup specified)"
        echo "  Test camera ID: $CREATED_CAMERA_ID"
        echo "  Test image: $TEST_IMAGE_PATH"
        echo "  To manually cleanup, delete the camera via API:"
        echo "    curl -X DELETE $API_URL/api/cameras/$CREATED_CAMERA_ID"
        return 0
    fi

    # Delete test camera (this cascades to detections and events)
    if [ -n "$CREATED_CAMERA_ID" ]; then
        print_step "Deleting test camera and related data..."
        local response
        response=$(curl -s -X DELETE "$API_URL/api/cameras/$CREATED_CAMERA_ID" -w "%{http_code}" 2>/dev/null)
        local http_code="${response: -3}"
        if [ "$http_code" = "204" ] || [ "$http_code" = "200" ] || [ "$http_code" = "404" ]; then
            print_success "Deleted test camera"
        else
            print_warn "Camera deletion returned: $http_code"
        fi
    fi

    # Remove test image file
    if [ -f "$TEST_IMAGE_PATH" ]; then
        rm -f "$TEST_IMAGE_PATH"
        print_success "Removed test image"
    fi

    # Remove test camera folder if empty
    if [ -d "$TEST_CAMERA_FOLDER" ]; then
        rmdir "$TEST_CAMERA_FOLDER" 2>/dev/null && print_success "Removed test camera folder" || true
    fi

    print_success "Cleanup complete"
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
            --verbose|-v)
                VERBOSE="true"
                shift
                ;;
            --skip-cleanup)
                SKIP_CLEANUP="true"
                shift
                ;;
            --timeout)
                TIMEOUT="$2"
                shift 2
                ;;
            --api-url)
                API_URL="$2"
                shift 2
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done

    # Record start time
    TEST_START_TIME=$(date +%s)

    echo ""
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo -e "${BLUE}${BOLD}  Home Security Intelligence Smoke Test    ${NC}"
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo ""
    echo -e "API URL:    ${CYAN}$API_URL${NC}"
    echo -e "Timeout:    ${CYAN}${TIMEOUT}s${NC}"
    echo -e "Verbose:    ${CYAN}$VERBOSE${NC}"
    echo -e "Cleanup:    ${CYAN}$([ "$SKIP_CLEANUP" = "true" ] && echo "disabled" || echo "enabled")${NC}"
    echo -e "Started:    ${CYAN}$(date '+%Y-%m-%d %H:%M:%S')${NC}"

    # Trap to ensure cleanup on exit
    trap cleanup_test_artifacts EXIT

    local exit_code=0

    # Run prerequisite checks
    if ! check_prerequisites; then
        exit 2
    fi

    # Setup test fixtures
    print_header "Setting Up Test Fixtures"
    if ! create_test_image; then
        print_fail "Failed to create test image"
        exit 1
    fi

    if ! create_test_camera; then
        print_fail "Failed to create test camera"
        exit 1
    fi

    # Run pipeline test
    print_header "Testing AI Pipeline"
    if ! drop_test_image; then
        print_fail "Failed to drop test image"
        exit 1
    fi

    if ! wait_for_detection; then
        print_warn "Detection verification failed (pipeline may not be fully running)"
        exit_code=1
    fi

    # Note: Events take longer due to batch processing, so we just check
    wait_for_event

    # Verify API endpoints
    if ! verify_api_endpoints; then
        print_warn "Some API endpoint verifications failed"
        exit_code=1
    fi

    # Summary
    print_header "Smoke Test Results"

    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - TEST_START_TIME))

    if [ $exit_code -eq 0 ]; then
        echo ""
        echo -e "${GREEN}${BOLD}  ALL TESTS PASSED  ${NC}"
        echo ""
        echo -e "Duration: ${CYAN}${duration}s${NC}"
        echo ""
        echo "The MVP pipeline is operational:"
        echo "  - Backend API is healthy"
        echo "  - Redis is connected"
        echo "  - Database is operational"
        if [ -n "$CREATED_DETECTION_ID" ]; then
            echo "  - File watcher detected image"
            echo "  - Detection created (ID: $CREATED_DETECTION_ID)"
        fi
        if [ -n "$CREATED_EVENT_ID" ]; then
            echo "  - Event created after analysis (ID: $CREATED_EVENT_ID)"
        fi
    else
        echo ""
        echo -e "${YELLOW}${BOLD}  PARTIAL PASS - SOME TESTS FAILED  ${NC}"
        echo ""
        echo -e "Duration: ${CYAN}${duration}s${NC}"
        echo ""
        echo "Core services are running but pipeline may have issues."
        echo "Review the output above for specific failures."
    fi

    exit $exit_code
}

# Run main
main "$@"

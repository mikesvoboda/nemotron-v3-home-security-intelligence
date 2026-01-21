#!/bin/bash
# Pre-push parallel test runner
# Runs backend unit/integration tests, frontend unit tests, E2E+a11y tests, and API type checks concurrently
#
# Parallelization strategy:
#   - Backend unit tests (pytest) - ~2-3 minutes
#   - E2E + Accessibility tests (Playwright) - ~30-60 seconds
#   - API types contract check (openapi-typescript) - ~10-20 seconds
#   - Backend integration tests (subset for speed) - ~30-60 seconds
#   - Frontend unit tests (vitest) - ~10-30 seconds
#
# Total time: max(all_jobs) instead of sum (~60-70% faster)
#
# Usage: ./scripts/pre-push-tests.sh
# Skip: SKIP=parallel-tests git push

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Temporary files for capturing exit codes and logs
UNIT_EXIT_FILE=$(mktemp)
E2E_EXIT_FILE=$(mktemp)
API_EXIT_FILE=$(mktemp)
INTEGRATION_EXIT_FILE=$(mktemp)
FRONTEND_EXIT_FILE=$(mktemp)
UNIT_LOG=$(mktemp)
E2E_LOG=$(mktemp)
API_LOG=$(mktemp)
INTEGRATION_LOG=$(mktemp)
FRONTEND_LOG=$(mktemp)

# Cleanup on exit
cleanup() {
    rm -f "$UNIT_EXIT_FILE" "$E2E_EXIT_FILE" "$API_EXIT_FILE" "$INTEGRATION_EXIT_FILE" "$FRONTEND_EXIT_FILE"
    rm -f "$UNIT_LOG" "$E2E_LOG" "$API_LOG" "$INTEGRATION_LOG" "$FRONTEND_LOG"
}
trap cleanup EXIT

cd "$PROJECT_ROOT"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}        PARALLEL PRE-PUSH VALIDATION (5 concurrent jobs)       ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Job 1: Backend unit tests
(
    redis-cli -n 15 FLUSHDB > /dev/null 2>&1 || true
    if uv run pytest backend/tests/unit/ -m "not slow and not integration" \
        --cov=backend --cov-report=term-missing:skip-covered --cov-fail-under=85 \
        -q --tb=short -n auto --dist=worksteal > "$UNIT_LOG" 2>&1; then
        echo "0" > "$UNIT_EXIT_FILE"
    else
        echo "1" > "$UNIT_EXIT_FILE"
    fi
) &
UNIT_PID=$!

# Job 2: E2E + Accessibility tests (Playwright - Chromium only)
# Includes accessibility.spec.ts for WCAG validation
(
    cd "$PROJECT_ROOT/frontend"
    # Backup storage-state.json to prevent pre-commit file modification detection
    STORAGE_STATE="tests/e2e/.auth/storage-state.json"
    STORAGE_STATE_BAK="/tmp/storage-state.json.bak.$$"
    if [ -f "$STORAGE_STATE" ]; then
        cp "$STORAGE_STATE" "$STORAGE_STATE_BAK"
    fi

    # Run all E2E tests including accessibility specs
    if npm run test:e2e -- --project=chromium --reporter=dot > "$E2E_LOG" 2>&1; then
        EXIT_CODE=0
    else
        EXIT_CODE=1
    fi

    # Restore storage-state.json
    if [ -f "$STORAGE_STATE_BAK" ]; then
        cp "$STORAGE_STATE_BAK" "$STORAGE_STATE"
        rm -f "$STORAGE_STATE_BAK"
    fi

    echo "$EXIT_CODE" > "$E2E_EXIT_FILE"
) &
E2E_PID=$!

# Job 3: API types contract check
(
    if "$PROJECT_ROOT/scripts/generate-types.sh" --check > "$API_LOG" 2>&1; then
        echo "0" > "$API_EXIT_FILE"
    else
        echo "1" > "$API_EXIT_FILE"
    fi
) &
API_PID=$!

# Job 4: Backend integration tests (subset for speed)
(
    redis-cli -n 15 FLUSHDB > /dev/null 2>&1 || true
    if uv run pytest backend/tests/integration/ -n0 --tb=short -q -x --timeout=60 > "$INTEGRATION_LOG" 2>&1; then
        echo "0" > "$INTEGRATION_EXIT_FILE"
    else
        echo "1" > "$INTEGRATION_EXIT_FILE"
    fi
) &
INTEGRATION_PID=$!

# Job 5: Frontend unit tests with coverage
(
    cd "$PROJECT_ROOT/frontend"
    if npm test -- --coverage --run > "$FRONTEND_LOG" 2>&1; then
        echo "0" > "$FRONTEND_EXIT_FILE"
    else
        echo "1" > "$FRONTEND_EXIT_FILE"
    fi
) &
FRONTEND_PID=$!

# Show running jobs
echo -e "${YELLOW}Running 5 jobs in parallel:${NC}"
echo "  [1] Backend unit tests (pytest, 85% coverage)"
echo "  [2] E2E + Accessibility tests (Playwright Chromium)"
echo "  [3] API types contract check (openapi-typescript)"
echo "  [4] Backend integration tests (subset for speed)"
echo "  [5] Frontend unit tests (vitest with coverage)"
echo ""
echo -e "${BLUE}Waiting for all jobs to complete...${NC}"

# Wait for all jobs
wait $UNIT_PID 2>/dev/null || true
wait $E2E_PID 2>/dev/null || true
wait $API_PID 2>/dev/null || true
wait $INTEGRATION_PID 2>/dev/null || true
wait $FRONTEND_PID 2>/dev/null || true

# Read exit codes
UNIT_EXIT=$(cat "$UNIT_EXIT_FILE" 2>/dev/null || echo "1")
E2E_EXIT=$(cat "$E2E_EXIT_FILE" 2>/dev/null || echo "1")
API_EXIT=$(cat "$API_EXIT_FILE" 2>/dev/null || echo "1")
INTEGRATION_EXIT=$(cat "$INTEGRATION_EXIT_FILE" 2>/dev/null || echo "1")
FRONTEND_EXIT=$(cat "$FRONTEND_EXIT_FILE" 2>/dev/null || echo "1")

# Report results
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}                       RESULTS SUMMARY                          ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Unit test results
if [ "$UNIT_EXIT" = "0" ]; then
    echo -e "${GREEN}✓ [1] Backend Unit Tests: PASSED${NC}"
else
    echo -e "${RED}✗ [1] Backend Unit Tests: FAILED${NC}"
fi

# E2E test results
if [ "$E2E_EXIT" = "0" ]; then
    echo -e "${GREEN}✓ [2] E2E + Accessibility Tests: PASSED${NC}"
else
    echo -e "${RED}✗ [2] E2E + Accessibility Tests: FAILED${NC}"
fi

# API types results
if [ "$API_EXIT" = "0" ]; then
    echo -e "${GREEN}✓ [3] API Types Contract: PASSED${NC}"
else
    echo -e "${RED}✗ [3] API Types Contract: FAILED${NC}"
fi

# Integration test results
if [ "$INTEGRATION_EXIT" = "0" ]; then
    echo -e "${GREEN}✓ [4] Backend Integration Tests: PASSED${NC}"
else
    echo -e "${RED}✗ [4] Backend Integration Tests: FAILED${NC}"
fi

# Frontend unit test results
if [ "$FRONTEND_EXIT" = "0" ]; then
    echo -e "${GREEN}✓ [5] Frontend Unit Tests: PASSED${NC}"
else
    echo -e "${RED}✗ [5] Frontend Unit Tests: FAILED${NC}"
fi

echo ""

# Show failure details
SHOW_DETAILS=false

if [ "$UNIT_EXIT" != "0" ]; then
    SHOW_DETAILS=true
    echo -e "${RED}─────────────────────────────────────────────────────────────────${NC}"
    echo -e "${RED}Backend Unit Test Failures:${NC}"
    echo -e "${RED}─────────────────────────────────────────────────────────────────${NC}"
    cat "$UNIT_LOG"
    echo ""
fi

if [ "$E2E_EXIT" != "0" ]; then
    SHOW_DETAILS=true
    echo -e "${RED}─────────────────────────────────────────────────────────────────${NC}"
    echo -e "${RED}E2E + Accessibility Test Failures:${NC}"
    echo -e "${RED}─────────────────────────────────────────────────────────────────${NC}"
    cat "$E2E_LOG"
    echo ""
fi

if [ "$API_EXIT" != "0" ]; then
    SHOW_DETAILS=true
    echo -e "${RED}─────────────────────────────────────────────────────────────────${NC}"
    echo -e "${RED}API Types Contract Failures:${NC}"
    echo -e "${RED}─────────────────────────────────────────────────────────────────${NC}"
    cat "$API_LOG"
    echo ""
fi

if [ "$INTEGRATION_EXIT" != "0" ]; then
    SHOW_DETAILS=true
    echo -e "${RED}─────────────────────────────────────────────────────────────────${NC}"
    echo -e "${RED}Backend Integration Test Failures:${NC}"
    echo -e "${RED}─────────────────────────────────────────────────────────────────${NC}"
    cat "$INTEGRATION_LOG"
    echo ""
fi

if [ "$FRONTEND_EXIT" != "0" ]; then
    SHOW_DETAILS=true
    echo -e "${RED}─────────────────────────────────────────────────────────────────${NC}"
    echo -e "${RED}Frontend Unit Test Failures:${NC}"
    echo -e "${RED}─────────────────────────────────────────────────────────────────${NC}"
    cat "$FRONTEND_LOG"
    echo ""
fi

# Final result
if [ "$UNIT_EXIT" = "0" ] && [ "$E2E_EXIT" = "0" ] && [ "$API_EXIT" = "0" ] && [ "$INTEGRATION_EXIT" = "0" ] && [ "$FRONTEND_EXIT" = "0" ]; then
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}              ALL PARALLEL VALIDATIONS PASSED                  ${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    exit 0
else
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}            VALIDATION FAILED - PUSH BLOCKED                    ${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    exit 1
fi

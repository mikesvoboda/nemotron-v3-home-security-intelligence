#!/bin/bash
#
# Unified Test Runner
# Runs all tests with 95% code coverage enforcement
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Coverage threshold
COVERAGE_THRESHOLD=95

# Track results
BACKEND_RESULT=0
FRONTEND_RESULT=0
BACKEND_COVERAGE=0
FRONTEND_COVERAGE=0

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Home Security Intelligence - Test Runner${NC}"
echo -e "${BLUE}  Coverage Threshold: ${COVERAGE_THRESHOLD}%${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Function to print section header
print_section() {
    echo -e "${YELLOW}───────────────────────────────────────────────────────────────${NC}"
    echo -e "${YELLOW}  $1${NC}"
    echo -e "${YELLOW}───────────────────────────────────────────────────────────────${NC}"
}

# Function to print success
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

# Function to print failure
print_failure() {
    echo -e "${RED}✗ $1${NC}"
}

# ─────────────────────────────────────────────────────────────────────────────
# Backend Tests
# ─────────────────────────────────────────────────────────────────────────────

print_section "Backend Tests (Python/pytest)"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    if command -v uv &> /dev/null; then
        uv venv .venv
    else
        python3 -m venv .venv
    fi
fi

# Activate virtual environment and install dependencies
source .venv/bin/activate

# Install dependencies if needed
if ! python -c "import pytest" 2>/dev/null; then
    echo "Installing backend dependencies..."
    if command -v uv &> /dev/null; then
        uv pip install -r backend/requirements.txt
    else
        pip install -r backend/requirements.txt
    fi
fi

# Run backend tests with coverage
echo ""
echo "Running backend tests with coverage..."
echo ""

if python -m pytest backend/tests/ \
    --cov=backend \
    --cov-report=term-missing \
    --cov-report=html:coverage/backend \
    --cov-report=json:coverage/backend/coverage.json \
    --cov-fail-under=$COVERAGE_THRESHOLD \
    -v; then
    BACKEND_RESULT=0
    print_success "Backend tests passed"
else
    BACKEND_RESULT=$?
    print_failure "Backend tests failed"
fi

# Extract backend coverage percentage
if [ -f "coverage/backend/coverage.json" ]; then
    BACKEND_COVERAGE=$(python -c "import json; print(round(json.load(open('coverage/backend/coverage.json'))['totals']['percent_covered'], 2))")
    echo -e "Backend coverage: ${BLUE}${BACKEND_COVERAGE}%${NC}"
fi

deactivate

# ─────────────────────────────────────────────────────────────────────────────
# Frontend Tests
# ─────────────────────────────────────────────────────────────────────────────

echo ""
print_section "Frontend Tests (React/Vitest)"

cd "$PROJECT_ROOT/frontend"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

# Run frontend tests with coverage
echo ""
echo "Running frontend tests with coverage..."
echo ""

if npm run test:coverage -- --run; then
    FRONTEND_RESULT=0
    print_success "Frontend tests passed"
else
    FRONTEND_RESULT=$?
    print_failure "Frontend tests failed"
fi

# Extract frontend coverage percentage
if [ -f "coverage/coverage-summary.json" ]; then
    FRONTEND_COVERAGE=$(node -e "console.log(require('./coverage/coverage-summary.json').total.lines.pct)")
    echo -e "Frontend coverage: ${BLUE}${FRONTEND_COVERAGE}%${NC}"
fi

cd "$PROJECT_ROOT"

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Backend status
if [ $BACKEND_RESULT -eq 0 ]; then
    print_success "Backend:  PASSED (${BACKEND_COVERAGE:-N/A}% coverage)"
else
    print_failure "Backend:  FAILED"
fi

# Frontend status
if [ $FRONTEND_RESULT -eq 0 ]; then
    print_success "Frontend: PASSED (${FRONTEND_COVERAGE:-N/A}% coverage)"
else
    print_failure "Frontend: FAILED"
fi

echo ""

# Coverage reports location
echo -e "${YELLOW}Coverage Reports:${NC}"
echo "  Backend:  coverage/backend/index.html"
echo "  Frontend: frontend/coverage/index.html"
echo ""

# Final result
if [ $BACKEND_RESULT -eq 0 ] && [ $FRONTEND_RESULT -eq 0 ]; then
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  All tests passed with ${COVERAGE_THRESHOLD}%+ coverage!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    exit 0
else
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${RED}  Some tests failed or coverage below ${COVERAGE_THRESHOLD}%${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    exit 1
fi

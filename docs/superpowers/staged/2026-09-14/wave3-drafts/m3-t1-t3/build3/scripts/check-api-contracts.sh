#!/bin/bash
# =============================================================================
# API Contract Verification Script
# =============================================================================
#
# NEM-1684: Contract Tests for Backend-Frontend API Parity
#
# This script runs contract tests to verify that backend API responses match
# frontend TypeScript type expectations. It ensures API compatibility is
# maintained across changes.
#
# Usage:
#   ./scripts/check-api-contracts.sh [options]
#
# Options:
#   --backend     Run only backend contract tests
#   --frontend    Run only frontend contract tests
#   --verbose     Show verbose output
#   --help        Show this help message
#
# Exit codes:
#   0 - All contract tests passed
#   1 - Some tests failed
#   2 - Script error (missing dependencies, etc.)
#
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
BACKEND_PASSED=0
FRONTEND_PASSED=0
BACKEND_FAILED=0
FRONTEND_FAILED=0

# Options
RUN_BACKEND=true
RUN_FRONTEND=true
VERBOSE=false

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# -----------------------------------------------------------------------------
# Functions
# -----------------------------------------------------------------------------

show_help() {
    head -30 "$0" | tail -28 | sed 's/^# //' | sed 's/^#//'
    exit 0
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $1"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

check_dependencies() {
    local missing=()

    if ! command -v uv &> /dev/null; then
        missing+=("uv (Python package manager)")
    fi

    if ! command -v npm &> /dev/null; then
        missing+=("npm (Node package manager)")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        log_error "Missing dependencies:"
        for dep in "${missing[@]}"; do
            echo "  - $dep"
        done
        exit 2
    fi
}

run_backend_contracts() {
    log_info "Running backend contract tests..."

    cd "$PROJECT_ROOT"

    if $VERBOSE; then
        if uv run pytest backend/tests/contracts/ -v --tb=short 2>&1; then
            BACKEND_PASSED=1
            log_success "Backend contract tests passed"
        else
            BACKEND_FAILED=1
            log_error "Backend contract tests failed"
        fi
    else
        if uv run pytest backend/tests/contracts/ -q --tb=line 2>&1; then
            BACKEND_PASSED=1
            log_success "Backend contract tests passed"
        else
            BACKEND_FAILED=1
            log_error "Backend contract tests failed"
        fi
    fi
}

run_frontend_contracts() {
    log_info "Running frontend contract tests..."

    cd "$PROJECT_ROOT/frontend"

    if $VERBOSE; then
        if npm test -- --run api-contracts 2>&1; then
            FRONTEND_PASSED=1
            log_success "Frontend contract tests passed"
        else
            FRONTEND_FAILED=1
            log_error "Frontend contract tests failed"
        fi
    else
        if npm test -- --run api-contracts --reporter=dot 2>&1; then
            FRONTEND_PASSED=1
            log_success "Frontend contract tests passed"
        else
            FRONTEND_FAILED=1
            log_error "Frontend contract tests failed"
        fi
    fi

    cd "$PROJECT_ROOT"
}

print_summary() {
    echo ""
    echo "=============================================="
    echo "           Contract Test Summary              "
    echo "=============================================="
    echo ""

    local total_passed=0
    local total_failed=0

    if $RUN_BACKEND; then
        if [ $BACKEND_PASSED -eq 1 ]; then
            echo -e "Backend:  ${GREEN}PASSED${NC}"
            total_passed=$((total_passed + 1))
        elif [ $BACKEND_FAILED -eq 1 ]; then
            echo -e "Backend:  ${RED}FAILED${NC}"
            total_failed=$((total_failed + 1))
        else
            echo -e "Backend:  ${YELLOW}SKIPPED${NC}"
        fi
    fi

    if $RUN_FRONTEND; then
        if [ $FRONTEND_PASSED -eq 1 ]; then
            echo -e "Frontend: ${GREEN}PASSED${NC}"
            total_passed=$((total_passed + 1))
        elif [ $FRONTEND_FAILED -eq 1 ]; then
            echo -e "Frontend: ${RED}FAILED${NC}"
            total_failed=$((total_failed + 1))
        else
            echo -e "Frontend: ${YELLOW}SKIPPED${NC}"
        fi
    fi

    echo ""
    echo "----------------------------------------------"
    echo -e "Total: ${GREEN}$total_passed passed${NC}, ${RED}$total_failed failed${NC}"
    echo "=============================================="

    if [ $total_failed -gt 0 ]; then
        return 1
    fi
    return 0
}

# -----------------------------------------------------------------------------
# Parse arguments
# -----------------------------------------------------------------------------

while [[ $# -gt 0 ]]; do
    case $1 in
        --backend)
            RUN_BACKEND=true
            RUN_FRONTEND=false
            shift
            ;;
        --frontend)
            RUN_BACKEND=false
            RUN_FRONTEND=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            show_help
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 2
            ;;
    esac
done

# -----------------------------------------------------------------------------
# Main execution
# -----------------------------------------------------------------------------

echo ""
echo "=============================================="
echo "     API Contract Verification (NEM-1684)     "
echo "=============================================="
echo ""

check_dependencies

if $RUN_BACKEND; then
    run_backend_contracts
    echo ""
fi

if $RUN_FRONTEND; then
    run_frontend_contracts
    echo ""
fi

if print_summary; then
    echo ""
    log_success "All contract tests passed - API parity verified!"
    exit 0
else
    echo ""
    log_error "Some contract tests failed - review above for details"
    exit 1
fi

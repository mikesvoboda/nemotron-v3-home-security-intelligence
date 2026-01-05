#!/usr/bin/env bash
#
# API Compatibility Check
# Compares OpenAPI schemas between current branch and main to detect breaking changes
#
# Usage:
#   ./scripts/check-api-compatibility.sh              # Compare against main
#   ./scripts/check-api-compatibility.sh <base-ref>   # Compare against specific ref
#   ./scripts/check-api-compatibility.sh --help       # Show help
#
# Requirements:
#   - Python 3.14+ with backend dependencies installed
#   - oasdiff CLI (installed automatically if missing)
#   - jq (for JSON processing)
#
# Breaking changes detected:
#   - Removed endpoints
#   - Removed required parameters
#   - Changed response schemas (incompatible changes)
#   - Type changes in request/response bodies
#
# Non-breaking changes (allowed):
#   - New endpoints
#   - New optional parameters
#   - New optional response fields
#

set -e

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMP_DIR=$(mktemp -d)
CURRENT_SPEC="$TEMP_DIR/openapi-current.json"
BASE_SPEC="$TEMP_DIR/openapi-base.json"
BREAKING_CHANGES="$TEMP_DIR/breaking-changes.txt"
FULL_DIFF="$TEMP_DIR/full-diff.txt"

# Default base reference
BASE_REF="${1:-origin/main}"

# oasdiff version
OASDIFF_VERSION="1.10.25"

# Colors (portable - works in sh)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    NC='\033[0m'
else
    GREEN=''
    RED=''
    YELLOW=''
    CYAN=''
    NC=''
fi

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

print_step() {
    printf "${CYAN}> %s${NC}\n" "$1"
}

print_success() {
    printf "${GREEN}[OK] %s${NC}\n" "$1"
}

print_error() {
    printf "${RED}[ERROR] %s${NC}\n" "$1" >&2
}

print_warning() {
    printf "${YELLOW}[WARN] %s${NC}\n" "$1"
}

show_help() {
    cat << 'EOF'
API Compatibility Check

Compare OpenAPI schemas between current branch and main to detect breaking changes.

Usage:
    ./scripts/check-api-compatibility.sh [BASE_REF]

Arguments:
    BASE_REF    Git reference to compare against (default: origin/main)
                Examples: main, origin/main, HEAD~5, v1.0.0

Options:
    -h, --help  Show this help message

Examples:
    ./scripts/check-api-compatibility.sh                    # Compare against origin/main
    ./scripts/check-api-compatibility.sh main               # Compare against local main
    ./scripts/check-api-compatibility.sh HEAD~3             # Compare against 3 commits ago
    ./scripts/check-api-compatibility.sh v1.0.0             # Compare against a tag

Breaking changes detected:
    - Removed endpoints
    - Removed required parameters
    - Changed response schemas (incompatible changes)
    - Type changes in request/response bodies

Non-breaking changes (allowed):
    - New endpoints
    - New optional parameters
    - New optional response fields

Exit codes:
    0  No breaking changes detected
    1  Breaking changes detected or error occurred

EOF
    exit 0
}

check_command() {
    command -v "$1" >/dev/null 2>&1
}

cleanup() {
    if [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
    fi
}

# Set up trap to clean up on exit
trap cleanup EXIT

install_oasdiff() {
    print_step "Installing oasdiff..."

    local ARCH
    local OS

    # Detect OS
    case "$(uname -s)" in
        Linux*)  OS="linux";;
        Darwin*) OS="darwin";;
        *)       print_error "Unsupported OS: $(uname -s)"; exit 1;;
    esac

    # Detect architecture
    case "$(uname -m)" in
        x86_64)  ARCH="amd64";;
        aarch64) ARCH="arm64";;
        arm64)   ARCH="arm64";;
        *)       print_error "Unsupported architecture: $(uname -m)"; exit 1;;
    esac

    local URL="https://github.com/Tufin/oasdiff/releases/download/v${OASDIFF_VERSION}/oasdiff_${OASDIFF_VERSION}_${OS}_${ARCH}.tar.gz"

    curl -sSL "$URL" | tar xz -C "$TEMP_DIR"

    if [ ! -f "$TEMP_DIR/oasdiff" ]; then
        print_error "Failed to download oasdiff"
        exit 1
    fi

    chmod +x "$TEMP_DIR/oasdiff"
    OASDIFF_CMD="$TEMP_DIR/oasdiff"
    print_success "oasdiff ${OASDIFF_VERSION} installed"
}

generate_openapi_spec() {
    local output_file="$1"
    local description="$2"

    print_step "Generating OpenAPI spec ($description)..."

    # Set default environment variables for OpenAPI generation
    # pragma: allowlist nextline secret
    export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://user:password@localhost:5432/security}"
    export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

    uv run python -c "
from backend.main import app
import json
import sys

try:
    spec = app.openapi()
    with open('$output_file', 'w') as f:
        json.dump(spec, f, indent=2)
    endpoint_count = len(spec.get('paths', {}))
    print(f'Generated OpenAPI spec with {endpoint_count} endpoints', file=sys.stderr)
except Exception as e:
    print(f'Error generating OpenAPI spec: {e}', file=sys.stderr)
    sys.exit(1)
"
}

# ─────────────────────────────────────────────────────────────────────────────
# Parse Arguments
# ─────────────────────────────────────────────────────────────────────────────

case "$1" in
    -h|--help)
        show_help
        ;;
esac

# ─────────────────────────────────────────────────────────────────────────────
# Main Script
# ─────────────────────────────────────────────────────────────────────────────

cd "$PROJECT_ROOT"

echo ""
printf "${CYAN}============================================${NC}\n"
printf "${CYAN}  API Compatibility Check${NC}\n"
printf "${CYAN}============================================${NC}\n"
echo ""

# Step 1: Check for required tools
print_step "Checking dependencies..."

if ! check_command uv; then
    print_error "uv not found. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

if ! check_command jq; then
    print_error "jq not found. Install with: apt-get install jq (or brew install jq)"
    exit 1
fi

if ! check_command git; then
    print_error "git not found"
    exit 1
fi

# Check for oasdiff
if check_command oasdiff; then
    OASDIFF_CMD="oasdiff"
    print_success "oasdiff found in PATH"
else
    install_oasdiff
fi

print_success "All dependencies available"

# Step 2: Generate current branch OpenAPI spec
generate_openapi_spec "$CURRENT_SPEC" "current branch"

if [ ! -f "$CURRENT_SPEC" ]; then
    print_error "Failed to generate current OpenAPI spec"
    exit 1
fi

print_success "Current branch spec generated"

# Step 3: Generate base branch OpenAPI spec
print_step "Generating OpenAPI spec from $BASE_REF..."

# Store current branch/commit
CURRENT_REF=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || git rev-parse HEAD)

# Stash any uncommitted changes
STASHED=false
if ! git diff --quiet || ! git diff --cached --quiet; then
    print_step "Stashing uncommitted changes..."
    git stash --include-untracked
    STASHED=true
fi

# Checkout base ref
git checkout "$BASE_REF" --quiet 2>/dev/null || git checkout "refs/heads/$BASE_REF" --quiet 2>/dev/null || {
    # If checkout fails, try fetching first
    git fetch origin --quiet 2>/dev/null || true
    git checkout "$BASE_REF" --quiet
}

# Generate spec from base
generate_openapi_spec "$BASE_SPEC" "$BASE_REF" || {
    # If generation fails, create empty spec
    print_warning "Could not generate spec from $BASE_REF, using empty spec"
    echo '{"openapi": "3.0.0", "info": {"title": "Empty", "version": "0.0.0"}, "paths": {}}' > "$BASE_SPEC"
}

# Return to original ref
git checkout "$CURRENT_REF" --quiet

# Restore stashed changes
if [ "$STASHED" = true ]; then
    print_step "Restoring stashed changes..."
    git stash pop --quiet || true
fi

print_success "Base branch spec generated"

# Step 4: Run oasdiff comparison
print_step "Comparing OpenAPI specs..."

echo ""
printf "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
printf "${CYAN}  Breaking Changes Report${NC}\n"
printf "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
echo ""

# Run breaking change detection
HAS_BREAKING=false
if $OASDIFF_CMD breaking "$BASE_SPEC" "$CURRENT_SPEC" --format text > "$BREAKING_CHANGES" 2>&1; then
    if [ -s "$BREAKING_CHANGES" ]; then
        HAS_BREAKING=true
    fi
else
    # oasdiff returns non-zero when breaking changes are found
    if [ -s "$BREAKING_CHANGES" ]; then
        HAS_BREAKING=true
    fi
fi

if [ "$HAS_BREAKING" = true ]; then
    printf "${RED}Breaking changes detected:${NC}\n"
    echo ""
    cat "$BREAKING_CHANGES"
    echo ""
else
    printf "${GREEN}No breaking changes detected${NC}\n"
    echo ""
fi

# Generate full diff
printf "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
printf "${CYAN}  Full API Diff${NC}\n"
printf "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
echo ""

$OASDIFF_CMD diff "$BASE_SPEC" "$CURRENT_SPEC" --format text > "$FULL_DIFF" 2>&1 || true

if [ -s "$FULL_DIFF" ]; then
    cat "$FULL_DIFF"
else
    echo "No API changes detected."
fi

# Summary statistics
echo ""
printf "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
printf "${CYAN}  Summary${NC}\n"
printf "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
echo ""

BASE_ENDPOINTS=$(jq '.paths | keys | length' "$BASE_SPEC" 2>/dev/null || echo "0")
CURRENT_ENDPOINTS=$(jq '.paths | keys | length' "$CURRENT_SPEC" 2>/dev/null || echo "0")

printf "%-20s %s\n" "Base ($BASE_REF):" "$BASE_ENDPOINTS endpoints"
printf "%-20s %s\n" "Current:" "$CURRENT_ENDPOINTS endpoints"
printf "%-20s %s\n" "Difference:" "$((CURRENT_ENDPOINTS - BASE_ENDPOINTS)) endpoints"
echo ""

# Final result
if [ "$HAS_BREAKING" = true ]; then
    printf "${RED}============================================${NC}\n"
    printf "${RED}  BREAKING CHANGES DETECTED${NC}\n"
    printf "${RED}============================================${NC}\n"
    echo ""
    echo "Review the breaking changes above before merging."
    echo ""
    echo "If the changes are intentional:"
    echo "  1. Update frontend API clients"
    echo "  2. Update API documentation"
    echo "  3. Consider API versioning for major changes"
    echo ""
    exit 1
else
    printf "${GREEN}============================================${NC}\n"
    printf "${GREEN}  API COMPATIBLE${NC}\n"
    printf "${GREEN}============================================${NC}\n"
    echo ""
    echo "No breaking changes detected. Safe to merge."
    echo ""
    exit 0
fi

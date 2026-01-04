#!/bin/sh
#
# Generate TypeScript Types from Backend OpenAPI Schema
#
# This script extracts the OpenAPI specification from the FastAPI backend
# and generates TypeScript types using openapi-typescript.
#
# Usage:
#   ./scripts/generate-types.sh              # Generate types
#   ./scripts/generate-types.sh --check      # Check if types are current (for CI)
#   ./scripts/generate-types.sh --help       # Show help
#
# Requirements:
#   - Python 3.14+ with backend dependencies installed
#   - Node.js 20.19+ or 22.12+ with frontend dependencies installed
#   - Virtual environment at .venv/
#

set -e

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPENAPI_SPEC_FILE="/tmp/openapi-$$.json"
GENERATED_TYPES_DIR="$PROJECT_ROOT/frontend/src/types/generated"
GENERATED_TYPES_FILE="$GENERATED_TYPES_DIR/api.ts"

# Flags
CHECK_MODE=false

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
Generate TypeScript Types from Backend OpenAPI Schema

Usage:
    ./scripts/generate-types.sh [OPTIONS]

Options:
    -h, --help    Show this help message
    --check       Check if generated types are current (for CI)
                  Exits with code 1 if types need regeneration

Examples:
    ./scripts/generate-types.sh           # Generate types
    ./scripts/generate-types.sh --check   # CI mode - check types are current

The script will:
1. Extract OpenAPI spec from the FastAPI backend
2. Generate TypeScript types to frontend/src/types/generated/api.ts
3. Optionally check if types are current (--check mode for CI)

Requirements:
    Backend:  Python 3.14+, .venv with backend dependencies
    Frontend: Node.js 20.19+/22.12+, npm with openapi-typescript installed

EOF
    exit 0
}

check_command() {
    command -v "$1" >/dev/null 2>&1
}

cleanup() {
    # Clean up temporary OpenAPI spec file
    if [ -f "$OPENAPI_SPEC_FILE" ]; then
        rm -f "$OPENAPI_SPEC_FILE"
    fi
}

# Set up trap to clean up on exit
trap cleanup EXIT

# ─────────────────────────────────────────────────────────────────────────────
# Parse Arguments
# ─────────────────────────────────────────────────────────────────────────────

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            show_help
            ;;
        --check)
            CHECK_MODE=true
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────────────
# Main Script
# ─────────────────────────────────────────────────────────────────────────────

cd "$PROJECT_ROOT"

# Step 1: Check for Python environment
print_step "Checking for Python environment..."
VENV_DIR="$PROJECT_ROOT/.venv"

# Determine the Python command to use
# In CI with uv, we need to use "uv run python" to access dependencies
if [ -n "$GITHUB_ACTIONS" ] || [ -n "$CI" ]; then
    if check_command uv; then
        PYTHON_CMD="uv run python"
        print_success "Running in CI environment - using uv run python"
    else
        PYTHON_CMD="python"
        print_success "Running in CI environment - using system Python"
    fi
elif [ -d "$VENV_DIR" ]; then
    # Local development - activate virtual environment
    if [ -f "$VENV_DIR/bin/activate" ]; then
        # shellcheck disable=SC1091
        . "$VENV_DIR/bin/activate"
        PYTHON_CMD="python"
        print_success "Virtual environment activated"
    else
        print_error "Could not find $VENV_DIR/bin/activate"
        exit 1
    fi
else
    print_error "Virtual environment not found at $VENV_DIR"
    echo "Run ./scripts/setup.sh first"
    exit 1
fi

# Step 2: Check for Node.js and frontend dependencies
print_step "Checking Node.js and frontend dependencies..."
if ! check_command node; then
    print_error "Node.js not found. Install Node.js 20.19+ or 22.12+."
    exit 1
fi

if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
    print_error "Frontend dependencies not installed. Run: cd frontend && npm install"
    exit 1
fi

if [ ! -d "$PROJECT_ROOT/frontend/node_modules/openapi-typescript" ]; then
    print_error "openapi-typescript not installed. Run: cd frontend && npm install"
    exit 1
fi
print_success "Node.js and dependencies available"

# Step 3: Generate OpenAPI spec from backend
print_step "Generating OpenAPI specification from backend..."

# Set default environment variables for OpenAPI generation
# These are only needed for Settings validation during import, not for actual functionality
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://user:password@localhost:5432/security}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

$PYTHON_CMD -c "
from backend.main import app
import json
import sys

spec = app.openapi()
with open('$OPENAPI_SPEC_FILE', 'w') as f:
    json.dump(spec, f, indent=2)
print('OpenAPI spec written to $OPENAPI_SPEC_FILE', file=sys.stderr)
" 2>&1

if [ ! -f "$OPENAPI_SPEC_FILE" ]; then
    print_error "Failed to generate OpenAPI specification"
    exit 1
fi
print_success "OpenAPI specification generated"

# Step 4: Create output directory if it doesn't exist
mkdir -p "$GENERATED_TYPES_DIR"

# Step 5: Generate TypeScript types
print_step "Generating TypeScript types..."

if [ "$CHECK_MODE" = true ]; then
    # In check mode, generate to a temp file and compare
    TEMP_FILE=$(mktemp)

    npx --prefix "$PROJECT_ROOT/frontend" openapi-typescript "$OPENAPI_SPEC_FILE" -o "$TEMP_FILE" 2>/dev/null

    if [ ! -f "$GENERATED_TYPES_FILE" ]; then
        print_error "Generated types file does not exist: $GENERATED_TYPES_FILE"
        echo "Run './scripts/generate-types.sh' to generate types"
        rm -f "$TEMP_FILE"
        exit 1
    fi

    if ! diff -q "$TEMP_FILE" "$GENERATED_TYPES_FILE" > /dev/null 2>&1; then
        print_error "Generated types are out of date!"
        echo ""
        echo "The OpenAPI schema has changed. Please regenerate types:"
        echo "  ./scripts/generate-types.sh"
        echo ""
        echo "Then commit the updated types file."
        rm -f "$TEMP_FILE"
        exit 1
    fi

    rm -f "$TEMP_FILE"
    print_success "Generated types are current"
else
    # Normal generation mode
    npx --prefix "$PROJECT_ROOT/frontend" openapi-typescript "$OPENAPI_SPEC_FILE" -o "$GENERATED_TYPES_FILE"

    if [ ! -f "$GENERATED_TYPES_FILE" ]; then
        print_error "Failed to generate TypeScript types"
        exit 1
    fi
    print_success "TypeScript types generated: $GENERATED_TYPES_FILE"
fi

# Step 6: Cleanup (handled by trap)
echo ""
printf "${GREEN}============================================${NC}\n"
if [ "$CHECK_MODE" = true ]; then
    printf "${GREEN}  API types are synchronized!${NC}\n"
else
    printf "${GREEN}  TypeScript types generated successfully!${NC}\n"
fi
printf "${GREEN}============================================${NC}\n"

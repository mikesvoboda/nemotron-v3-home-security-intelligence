#!/bin/sh
#
# Full Project Validation Script
# Runs linting, type checking, and tests for both backend and frontend
#
# This script is self-contained and will:
# - Auto-activate .venv for backend tools
# - Check for uv and use it if available
# - Fail fast with actionable error messages
#
# Usage:
#   ./scripts/validate.sh              # Full validation
#   ./scripts/validate.sh --backend    # Backend only
#   ./scripts/validate.sh --frontend   # Frontend only
#   ./scripts/validate.sh --help       # Show help
#

set -e

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Determine script and project root directories
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Flags
RUN_BACKEND=true
RUN_FRONTEND=true

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

print_header() {
    printf "\n${GREEN}=== %s ===${NC}\n" "$1"
}

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
Full Project Validation Script

Usage:
    ./scripts/validate.sh [OPTIONS]

Options:
    -h, --help      Show this help message
    --backend       Run backend validation only
    --frontend      Run frontend validation only

Examples:
    ./scripts/validate.sh               # Full validation
    ./scripts/validate.sh --backend     # Backend only
    ./scripts/validate.sh --frontend    # Frontend only

Requirements:
    Backend:  Python 3.14+, .venv with ruff/mypy/pytest installed
    Frontend: Node.js 18+, npm, node_modules installed

Setup:
    Run ./scripts/setup.sh first to install all dependencies.

EOF
    exit 0
}

check_command() {
    command -v "$1" >/dev/null 2>&1
}

# ─────────────────────────────────────────────────────────────────────────────
# Parse Arguments
# ─────────────────────────────────────────────────────────────────────────────

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            show_help
            ;;
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
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────────────
# Backend Validation
# ─────────────────────────────────────────────────────────────────────────────

run_backend_validation() {
    print_header "Backend Validation"

    # Check for virtual environment
    VENV_DIR="$PROJECT_ROOT/.venv"
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Virtual environment not found at $VENV_DIR"
        echo ""
        echo "To fix this, run:"
        echo "  ./scripts/setup.sh"
        echo ""
        echo "Or create manually:"
        if check_command uv; then
            echo "  cd $PROJECT_ROOT && uv venv .venv && source .venv/bin/activate && uv pip install -r backend/requirements.txt"
        else
            echo "  cd $PROJECT_ROOT && python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt"
        fi
        exit 1
    fi

    # Activate virtual environment
    print_step "Activating virtual environment..."
    if [ -f "$VENV_DIR/bin/activate" ]; then
        # shellcheck disable=SC1091
        . "$VENV_DIR/bin/activate"
        print_success "Virtual environment activated"
    else
        print_error "Could not find $VENV_DIR/bin/activate"
        echo "The virtual environment may be corrupted. Try:"
        echo "  rm -rf $VENV_DIR && ./scripts/setup.sh"
        exit 1
    fi

    # Verify required tools are installed in venv
    print_step "Checking backend dependencies..."

    MISSING_DEPS=""

    if ! check_command ruff; then
        MISSING_DEPS="$MISSING_DEPS ruff"
    fi

    if ! check_command mypy; then
        MISSING_DEPS="$MISSING_DEPS mypy"
    fi

    if ! check_command pytest; then
        MISSING_DEPS="$MISSING_DEPS pytest"
    fi

    if [ -n "$MISSING_DEPS" ]; then
        print_error "Missing backend dependencies:$MISSING_DEPS"
        echo ""
        echo "To fix this, install the missing packages:"
        if check_command uv; then
            echo "  source $VENV_DIR/bin/activate && uv pip install$MISSING_DEPS"
        else
            echo "  source $VENV_DIR/bin/activate && pip install$MISSING_DEPS"
        fi
        echo ""
        echo "Or reinstall all backend dependencies:"
        if check_command uv; then
            echo "  source $VENV_DIR/bin/activate && uv pip install -r backend/requirements.txt"
        else
            echo "  source $VENV_DIR/bin/activate && pip install -r backend/requirements.txt"
        fi
        exit 1
    fi

    print_success "All backend dependencies available"

    # Run linting
    print_step "Running Ruff (Linting)..."
    if ! ruff check "$PROJECT_ROOT/backend"; then
        print_error "Ruff linting failed"
        echo ""
        echo "To auto-fix some issues, run:"
        echo "  source $VENV_DIR/bin/activate && ruff check --fix $PROJECT_ROOT/backend"
        exit 1
    fi
    print_success "Ruff linting passed"

    # Run formatting check
    print_step "Running Ruff (Format Check)..."
    if ! ruff format --check "$PROJECT_ROOT/backend"; then
        print_error "Ruff format check failed"
        echo ""
        echo "To auto-format, run:"
        echo "  source $VENV_DIR/bin/activate && ruff format $PROJECT_ROOT/backend"
        exit 1
    fi
    print_success "Ruff format check passed"

    # Run type checking
    print_step "Running MyPy (Type Checking)..."
    if ! mypy "$PROJECT_ROOT/backend"; then
        print_error "MyPy type checking failed"
        echo ""
        echo "Fix the type errors shown above, then re-run validation."
        exit 1
    fi
    print_success "MyPy type checking passed"

    # Run tests
    # Coverage threshold: 95% combined (unit + integration)
    # This aligns with CI which enforces 95% coverage (per CLAUDE.md).
    # The combined threshold applies to all tests run together, ensuring
    # comprehensive test coverage across unit and integration tests.
    print_step "Running pytest (Tests & Coverage)..."
    if ! pytest "$PROJECT_ROOT/backend" --cov="$PROJECT_ROOT/backend" --cov-report=term-missing --cov-fail-under=95; then
        print_error "Backend tests failed or coverage below 95%"
        echo ""
        echo "Fix failing tests, then re-run validation."
        exit 1
    fi
    print_success "Backend tests passed with sufficient coverage"
}

# ─────────────────────────────────────────────────────────────────────────────
# Frontend Validation
# ─────────────────────────────────────────────────────────────────────────────

run_frontend_validation() {
    print_header "Frontend Validation"

    FRONTEND_DIR="$PROJECT_ROOT/frontend"

    # Check Node.js
    print_step "Checking Node.js..."
    if ! check_command node; then
        print_error "Node.js not found"
        echo ""
        echo "Please install Node.js 18+ from https://nodejs.org/"
        echo "Or use nvm: nvm install 18 && nvm use 18"
        exit 1
    fi

    NODE_VERSION=$(node --version | sed 's/v//' | cut -d. -f1)
    if [ "$NODE_VERSION" -lt 18 ]; then
        print_error "Node.js 18+ required, found v$NODE_VERSION"
        echo ""
        echo "Please upgrade Node.js to version 18 or later."
        exit 1
    fi
    print_success "Node.js $(node --version) found"

    # Check npm
    print_step "Checking npm..."
    if ! check_command npm; then
        print_error "npm not found"
        echo ""
        echo "npm should come with Node.js. Try reinstalling Node.js."
        exit 1
    fi
    print_success "npm $(npm --version) found"

    # Check for node_modules
    print_step "Checking frontend dependencies..."
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        print_error "Frontend dependencies not installed (node_modules missing)"
        echo ""
        echo "To fix this, run:"
        echo "  cd $FRONTEND_DIR && npm install"
        echo ""
        echo "Or run the setup script:"
        echo "  ./scripts/setup.sh"
        exit 1
    fi

    # Verify key packages are installed
    if [ ! -d "$FRONTEND_DIR/node_modules/eslint" ]; then
        print_warning "eslint not found in node_modules, may need to reinstall"
        echo "  cd $FRONTEND_DIR && npm install"
    fi

    if [ ! -d "$FRONTEND_DIR/node_modules/vitest" ]; then
        print_warning "vitest not found in node_modules, may need to reinstall"
        echo "  cd $FRONTEND_DIR && npm install"
    fi

    print_success "Frontend dependencies available"

    # Run ESLint
    print_step "Running ESLint..."
    if ! npm run lint --prefix "$FRONTEND_DIR"; then
        print_error "ESLint failed"
        echo ""
        echo "To auto-fix some issues, run:"
        echo "  cd $FRONTEND_DIR && npm run lint:fix"
        exit 1
    fi
    print_success "ESLint passed"

    # Run TypeScript type checking
    print_step "Running TypeScript type check..."
    if ! npm run typecheck --prefix "$FRONTEND_DIR"; then
        print_error "TypeScript type checking failed"
        echo ""
        echo "Fix the type errors shown above, then re-run validation."
        exit 1
    fi
    print_success "TypeScript type check passed"

    # Run Prettier check
    print_step "Running Prettier check..."
    # NOTE: Use the frontend npm script so Prettier loads plugins (e.g. prettier-plugin-tailwindcss)
    # from frontend/node_modules correctly. `npx --prefix` can fail to resolve plugins on some setups.
    if ! npm run format:check --prefix "$FRONTEND_DIR"; then
        print_error "Prettier check failed"
        echo ""
        echo "To auto-format, run:"
        echo "  cd $FRONTEND_DIR && npm run format"
        exit 1
    fi
    print_success "Prettier check passed"

    # Run tests
    print_step "Running Vitest (Tests)..."
    if ! npm run test --prefix "$FRONTEND_DIR" -- --run; then
        print_error "Frontend tests failed"
        echo ""
        echo "Fix failing tests, then re-run validation."
        exit 1
    fi
    print_success "Frontend tests passed"
}

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

printf "${GREEN}Starting project validation...${NC}\n"
printf "Project root: ${CYAN}%s${NC}\n" "$PROJECT_ROOT"

cd "$PROJECT_ROOT"

if [ "$RUN_BACKEND" = true ]; then
    run_backend_validation
fi

if [ "$RUN_FRONTEND" = true ]; then
    run_frontend_validation
fi

echo ""
printf "${GREEN}============================================${NC}\n"
printf "${GREEN}  VALIDATION SUCCESSFUL: codebase is healthy!${NC}\n"
printf "${GREEN}============================================${NC}\n"

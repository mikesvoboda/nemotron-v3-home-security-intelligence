#!/usr/bin/env bash
#
# Development Environment Setup Script
# For Nemotron v3 Home Security Intelligence Dashboard
#
# This script automates the setup of the development environment including:
# - Prerequisite checks (Python, Node.js, Docker, NVIDIA drivers)
# - Backend setup (virtualenv, dependencies, database)
# - Frontend setup (npm dependencies)
# - Pre-commit hooks installation
# - Verification tests
#
# Usage:
#   ./scripts/setup.sh              # Full setup
#   ./scripts/setup.sh --help       # Show help
#   ./scripts/setup.sh --skip-gpu   # Skip GPU checks
#

set -e  # Exit on error

# ─────────────────────────────────────────────────────────────────────────────
# Color Definitions
# ─────────────────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'  # No Color

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKIP_GPU=false
SKIP_TESTS=false

# Required versions
REQUIRED_PYTHON_MAJOR=3
REQUIRED_PYTHON_MINOR=14
REQUIRED_NODE_MAJOR=18

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${CYAN}▶ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${MAGENTA}ℹ $1${NC}"
}

show_help() {
    cat << EOF
Development Environment Setup Script

Usage:
    ./scripts/setup.sh [OPTIONS]

Options:
    -h, --help          Show this help message
    --skip-gpu          Skip GPU/NVIDIA driver checks
    --skip-tests        Skip verification tests
    --clean             Clean existing setup before reinstalling

Examples:
    ./scripts/setup.sh                  # Full setup with all checks
    ./scripts/setup.sh --skip-gpu       # Setup without GPU requirements
    ./scripts/setup.sh --clean          # Clean and reinstall everything

EOF
    exit 0
}

check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

version_compare() {
    # Compare version strings
    # Returns 0 if $1 >= $2, 1 otherwise
    local version1=$1
    local version2=$2

    if [ "$(printf '%s\n' "$version1" "$version2" | sort -V | head -n1)" = "$version2" ]; then
        return 0
    else
        return 1
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Parse Command Line Arguments
# ─────────────────────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        --skip-gpu)
            SKIP_GPU=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --clean)
            print_warning "Cleaning existing setup..."
            rm -rf "$PROJECT_ROOT/.venv"
            rm -rf "$PROJECT_ROOT/frontend/node_modules"
            rm -f "$PROJECT_ROOT/data/security.db"
            print_success "Cleanup complete"
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
# Start Setup
# ─────────────────────────────────────────────────────────────────────────────

print_header "Nemotron v3 Home Security Intelligence - Development Setup"

echo -e "Project root: ${CYAN}${PROJECT_ROOT}${NC}"
echo ""

cd "$PROJECT_ROOT"

# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Check Prerequisites
# ─────────────────────────────────────────────────────────────────────────────

print_header "Step 1: Checking Prerequisites"

# Check Python
print_step "Checking Python installation..."
if check_command python3; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -ge "$REQUIRED_PYTHON_MAJOR" ] && [ "$PYTHON_MINOR" -ge "$REQUIRED_PYTHON_MINOR" ]; then
        print_success "Python $PYTHON_VERSION found"
    else
        print_error "Python $REQUIRED_PYTHON_MAJOR.$REQUIRED_PYTHON_MINOR+ required, found $PYTHON_VERSION"
        exit 1
    fi
else
    print_error "Python 3 not found. Please install Python $REQUIRED_PYTHON_MAJOR.$REQUIRED_PYTHON_MINOR+"
    exit 1
fi

# Check Node.js
print_step "Checking Node.js installation..."
if check_command node; then
    NODE_VERSION=$(node --version | sed 's/v//')
    NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)

    if [ "$NODE_MAJOR" -ge "$REQUIRED_NODE_MAJOR" ]; then
        print_success "Node.js $NODE_VERSION found"
    else
        print_error "Node.js $REQUIRED_NODE_MAJOR+ required, found $NODE_VERSION"
        exit 1
    fi
else
    print_error "Node.js not found. Please install Node.js $REQUIRED_NODE_MAJOR+"
    exit 1
fi

# Check npm
print_step "Checking npm installation..."
if check_command npm; then
    NPM_VERSION=$(npm --version)
    print_success "npm $NPM_VERSION found"
else
    print_error "npm not found. Please install npm"
    exit 1
fi

# Check Docker (optional)
print_step "Checking Docker installation (optional)..."
if check_command docker; then
    DOCKER_VERSION=$(docker --version | awk '{print $3}' | sed 's/,//')
    print_success "Docker $DOCKER_VERSION found"
else
    print_warning "Docker not found (optional for development)"
fi

# Check NVIDIA drivers (optional for GPU)
if [ "$SKIP_GPU" = false ]; then
    print_step "Checking NVIDIA GPU support (optional)..."
    if check_command nvidia-smi; then
        NVIDIA_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -n1)
        print_success "NVIDIA driver $NVIDIA_VERSION found"

        # Show GPU info
        GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n1)
        print_info "GPU: $GPU_NAME"
    else
        print_warning "nvidia-smi not found (GPU features will be limited)"
    fi
else
    print_info "Skipping GPU checks (--skip-gpu flag)"
fi

# Check git
print_step "Checking git installation..."
if check_command git; then
    GIT_VERSION=$(git --version | awk '{print $3}')
    print_success "git $GIT_VERSION found"
else
    print_error "git not found. Please install git"
    exit 1
fi

print_success "All required prerequisites are installed"

# ─────────────────────────────────────────────────────────────────────────────
# Step 2: Backend Setup
# ─────────────────────────────────────────────────────────────────────────────

print_header "Step 2: Setting Up Backend"

# Create virtual environment
print_step "Creating Python virtual environment..."
if [ ! -d ".venv" ]; then
    if check_command uv; then
        print_info "Using uv for faster installation"
        uv venv .venv
    else
        python3 -m venv .venv
    fi
    print_success "Virtual environment created"
else
    print_info "Virtual environment already exists"
fi

# Activate virtual environment
print_step "Activating virtual environment..."
source .venv/bin/activate
print_success "Virtual environment activated"

# Upgrade pip
print_step "Upgrading pip..."
if check_command uv; then
    uv pip install --upgrade pip
else
    python -m pip install --upgrade pip --quiet
fi
print_success "pip upgraded"

# Install backend dependencies
print_step "Installing backend dependencies..."
if [ -f "backend/requirements.txt" ]; then
    if check_command uv; then
        uv pip install -r backend/requirements.txt
    else
        pip install -r backend/requirements.txt --quiet
    fi
    print_success "Backend dependencies installed"
else
    print_error "backend/requirements.txt not found"
    exit 1
fi

# Install development tools
print_step "Installing development tools (pre-commit, ruff, mypy)..."
if check_command uv; then
    uv pip install pre-commit ruff mypy
else
    pip install pre-commit ruff mypy --quiet
fi
print_success "Development tools installed"

# Create .env file if it doesn't exist
print_step "Setting up environment configuration..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success ".env file created from .env.example"
        print_warning "Please review and update .env with your configuration"
    else
        print_warning ".env.example not found, skipping .env creation"
    fi
else
    print_info ".env file already exists"
fi

# Create data directory for database
print_step "Creating data directory..."
mkdir -p data
print_success "Data directory ready"

# Initialize database
print_step "Initializing database..."
if [ -f "backend/main.py" ]; then
    print_info "Database will be initialized on first run"
    print_success "Database setup ready"
else
    print_warning "backend/main.py not found, skipping database initialization"
fi

print_success "Backend setup complete"

# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Frontend Setup
# ─────────────────────────────────────────────────────────────────────────────

print_header "Step 3: Setting Up Frontend"

cd "$PROJECT_ROOT/frontend"

# Install frontend dependencies
print_step "Installing frontend dependencies..."
if [ -f "package.json" ]; then
    npm install
    print_success "Frontend dependencies installed"
else
    print_error "frontend/package.json not found"
    exit 1
fi

# Create frontend .env if needed
print_step "Checking frontend environment configuration..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_success "Frontend .env file created"
    else
        print_info "No frontend .env.example found (may not be required)"
    fi
else
    print_info "Frontend .env already exists"
fi

cd "$PROJECT_ROOT"
print_success "Frontend setup complete"

# ─────────────────────────────────────────────────────────────────────────────
# Step 4: Pre-commit Hooks
# ─────────────────────────────────────────────────────────────────────────────

print_header "Step 4: Setting Up Pre-commit Hooks"

# Install pre-commit hooks
print_step "Installing pre-commit hooks..."
if [ -f ".pre-commit-config.yaml" ]; then
    pre-commit install
    pre-commit install --hook-type commit-msg
    print_success "Pre-commit hooks installed"

    print_step "Pre-commit hooks will run on every commit to ensure code quality"
    print_info "Hooks include: ruff (linting), mypy (type checking), pytest (tests)"
else
    print_warning ".pre-commit-config.yaml not found, skipping pre-commit setup"
fi

print_success "Pre-commit setup complete"

# ─────────────────────────────────────────────────────────────────────────────
# Step 5: Verification
# ─────────────────────────────────────────────────────────────────────────────

print_header "Step 5: Verifying Installation"

# Verify Python tools
print_step "Verifying Python tools..."

echo -n "  ruff: "
if check_command ruff; then
    ruff --version
else
    python -m ruff --version
fi

echo -n "  mypy: "
python -m mypy --version 2>/dev/null || echo "not found"

echo -n "  pytest: "
python -m pytest --version 2>/dev/null | head -1 || echo "not found"

print_success "Python tools verified"

# Verify Node.js tools
print_step "Verifying Node.js tools..."

cd "$PROJECT_ROOT/frontend"

echo -n "  eslint: "
npx eslint --version 2>/dev/null || echo "not found"

echo -n "  prettier: "
npx prettier --version 2>/dev/null || echo "not found"

echo -n "  vitest: "
npx vitest --version 2>/dev/null || echo "not found"

echo -n "  typescript: "
npx tsc --version 2>/dev/null || echo "not found"

cd "$PROJECT_ROOT"

print_success "Node.js tools verified"

# Run quick tests (optional)
if [ "$SKIP_TESTS" = false ]; then
    print_step "Running quick verification tests..."

    # Test Python import
    if python -c "import fastapi, sqlalchemy, redis; print('Backend imports OK')" 2>/dev/null; then
        print_success "Backend imports verified"
    else
        print_warning "Some backend imports failed (this may be normal for optional dependencies)"
    fi

    # Test frontend build
    cd "$PROJECT_ROOT/frontend"
    if npx tsc --noEmit 2>/dev/null; then
        print_success "Frontend TypeScript compilation verified"
    else
        print_warning "TypeScript compilation has errors (fix before running)"
    fi

    cd "$PROJECT_ROOT"
else
    print_info "Skipping verification tests (--skip-tests flag)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Setup Complete
# ─────────────────────────────────────────────────────────────────────────────

print_header "Setup Complete!"

echo -e "${GREEN}Your development environment is ready!${NC}"
echo ""
echo -e "${CYAN}Next Steps:${NC}"
echo ""
echo "  1. Review and update .env file with your configuration:"
echo -e "     ${YELLOW}nano .env${NC}"
echo ""
echo "  2. Start the backend server:"
echo -e "     ${YELLOW}source .venv/bin/activate${NC}"
echo -e "     ${YELLOW}cd backend && uvicorn main:app --reload${NC}"
echo ""
echo "  3. Start the frontend development server (in another terminal):"
echo -e "     ${YELLOW}cd frontend && npm run dev${NC}"
echo ""
echo -e "${CYAN}Available Commands:${NC}"
echo ""
echo "  Backend:"
echo -e "    ${YELLOW}source .venv/bin/activate${NC}          Activate Python virtual environment"
echo -e "    ${YELLOW}cd backend && pytest${NC}               Run backend tests"
echo -e "    ${YELLOW}ruff check backend/${NC}                Run Python linting"
echo -e "    ${YELLOW}mypy backend/${NC}                      Run type checking"
echo ""
echo "  Frontend:"
echo -e "    ${YELLOW}cd frontend && npm run dev${NC}         Start development server"
echo -e "    ${YELLOW}cd frontend && npm test${NC}            Run frontend tests"
echo -e "    ${YELLOW}cd frontend && npm run lint${NC}        Run ESLint"
echo -e "    ${YELLOW}cd frontend && npm run build${NC}       Build for production"
echo ""
echo "  Development:"
echo -e "    ${YELLOW}pre-commit run --all-files${NC}        Run all pre-commit hooks"
echo -e "    ${YELLOW}./scripts/test-runner.sh${NC}          Run full test suite"
echo -e "    ${YELLOW}./scripts/dev.sh${NC}                  Start all services"
echo ""
echo -e "${CYAN}Documentation:${NC}"
echo "  - Project README: README.md"
echo "  - Agent navigation: AGENTS.md files in each directory"
echo "  - Roadmap: docs/ROADMAP.md"
echo ""
echo -e "${GREEN}Happy coding!${NC}"
echo ""

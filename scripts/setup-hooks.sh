#!/bin/bash
#
# Setup script for pre-commit hooks and development environment
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Setting up development environment${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Python Environment
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${YELLOW}Setting up Python environment...${NC}"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    if command -v uv &> /dev/null; then
        uv venv .venv
    else
        python3 -m venv .venv
    fi
fi

# Activate virtual environment
source .venv/bin/activate

# Install backend dependencies
echo "Installing backend dependencies..."
if command -v uv &> /dev/null; then
    uv pip install -r backend/requirements.txt
    uv pip install pre-commit ruff mypy
else
    pip install -r backend/requirements.txt
    pip install pre-commit ruff mypy
fi

echo -e "${GREEN}✓ Python environment ready${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Node.js Environment
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${YELLOW}Setting up Node.js environment...${NC}"

cd "$PROJECT_ROOT/frontend"

# Install frontend dependencies
echo "Installing frontend dependencies..."
npm install

echo -e "${GREEN}✓ Node.js environment ready${NC}"
echo ""

cd "$PROJECT_ROOT"

# ─────────────────────────────────────────────────────────────────────────────
# Pre-commit Hooks
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${YELLOW}Setting up pre-commit hooks...${NC}"

# Install pre-commit hooks
pre-commit install
pre-commit install --hook-type commit-msg

echo -e "${GREEN}✓ Pre-commit hooks installed${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Verify Installation
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${YELLOW}Verifying installation...${NC}"

# Check Python tools
echo -n "  ruff: "
if command -v ruff &> /dev/null; then
    echo -e "${GREEN}$(ruff --version)${NC}"
else
    echo -e "${GREEN}$(python -m ruff --version)${NC}"
fi

echo -n "  mypy: "
python -m mypy --version 2>/dev/null || echo "not found"

echo -n "  pytest: "
python -m pytest --version 2>/dev/null | head -1 || echo "not found"

# Check Node tools
cd "$PROJECT_ROOT/frontend"
echo -n "  eslint: "
npx eslint --version 2>/dev/null || echo "not found"

echo -n "  prettier: "
npx prettier --version 2>/dev/null || echo "not found"

echo -n "  vitest: "
npx vitest --version 2>/dev/null || echo "not found"

cd "$PROJECT_ROOT"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Available commands:"
echo "  ./scripts/test-runner.sh      Run all tests with coverage"
echo "  pre-commit run --all-files    Run all pre-commit hooks"
echo "  cd frontend && npm run lint   Run frontend linting"
echo "  ruff check backend/           Run Python linting"
echo ""

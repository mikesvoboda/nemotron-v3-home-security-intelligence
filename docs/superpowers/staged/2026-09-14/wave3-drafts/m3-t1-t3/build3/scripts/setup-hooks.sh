#!/usr/bin/env bash
#
# Git Hooks Setup Script
#
# This script installs and configures all Git hooks for the development environment:
# - pre-commit: Linting, formatting, type checking (~10-30 seconds)
# - commit-msg: Conventional commit message validation (commitlint)
# - pre-push: Branch name validation, fast tests, API contract check
#
# Usage:
#   ./scripts/setup-hooks.sh           # Full setup
#   ./scripts/setup-hooks.sh --check   # Check installation status only
#   ./scripts/setup-hooks.sh --help    # Show this help message
#
# Requirements:
#   - Python 3.13+ with pre-commit installed
#   - Node.js 20+ with npm
#   - Git 2.5+ (for worktrees support)
#
# The script will:
#   1. Verify prerequisites are installed
#   2. Create Python virtual environment if needed
#   3. Install backend dependencies (uv sync)
#   4. Install frontend dependencies (npm ci)
#   5. Install pre-commit hooks (pre-commit, commit-msg, pre-push)
#   6. Verify installation succeeded
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Parse arguments
CHECK_ONLY=false
SHOW_HELP=false

for arg in "$@"; do
    case $arg in
        --check)
            CHECK_ONLY=true
            ;;
        --help|-h)
            SHOW_HELP=true
            ;;
    esac
done

if [ "$SHOW_HELP" = true ]; then
    cat << 'EOF'
Git Hooks Setup Script

This script installs and configures all Git hooks for development.

Usage:
  ./scripts/setup-hooks.sh           # Full setup
  ./scripts/setup-hooks.sh --check   # Check installation status only
  ./scripts/setup-hooks.sh --help    # Show this help

Hooks Installed:
  pre-commit  - Runs on 'git commit' before the commit is created
                Checks: ruff, mypy, eslint, prettier, hadolint, semgrep

  commit-msg  - Runs on 'git commit' to validate the commit message
                Checks: commitlint (conventional commits)

  pre-push    - Runs on 'git push' before pushing to remote
                Checks: branch naming, fast tests, API types contract

Hook Stages:
  ┌─────────────────────────────────────────────────────────────────────┐
  │ git commit                                                          │
  │   └─> pre-commit hooks (~10-30s)                                    │
  │         • trailing-whitespace, end-of-file-fixer                    │
  │         • check-yaml, check-json, check-merge-conflict              │
  │         • detect-secrets, detect-private-key                        │
  │         • hadolint (Dockerfile), semgrep (security)                 │
  │         • ruff check + format (Python)                              │
  │         • mypy (Python types)                                       │
  │         • prettier, eslint, typescript (Frontend)                   │
  │   └─> commit-msg hook (<1s)                                         │
  │         • commitlint (conventional commit format)                   │
  └─────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────┐
  │ git push                                                            │
  │   └─> pre-push hooks (~2-5min)                                      │
  │         • branch-name-check (naming convention)                     │
  │         • auto-rebase (keep up-to-date with main)                   │
  │         • fast-test (backend unit tests)                            │
  │         • api-types-contract (frontend/backend sync)                │
  └─────────────────────────────────────────────────────────────────────┘

Skipping Hooks (emergencies only):
  SKIP=hook-name git commit    # Skip specific hook
  git commit --no-verify       # Skip ALL hooks (use sparingly!)
  SKIP=fast-test git push      # Skip specific pre-push hook

Examples:
  # Normal commit (hooks run automatically)
  git commit -m "feat(api): add camera streaming endpoint"

  # Skip a slow hook temporarily
  SKIP=fast-test git push

  # Check hook status
  ./scripts/setup-hooks.sh --check

For more information, see:
  - docs/development/git-worktree-workflow.md
  - .pre-commit-config.yaml
  - commitlint.config.js
EOF
    exit 0
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Function to check hook installation status
check_hooks() {
    echo -e "${BLUE}Checking Git hooks installation status...${NC}"
    echo ""

    local all_ok=true

    # Check pre-commit hook
    if [ -f ".git/hooks/pre-commit" ] && grep -q "pre-commit" ".git/hooks/pre-commit" 2>/dev/null; then
        echo -e "${GREEN}[OK]${NC} pre-commit hook installed"
    else
        echo -e "${RED}[MISSING]${NC} pre-commit hook"
        all_ok=false
    fi

    # Check commit-msg hook
    if [ -f ".git/hooks/commit-msg" ] && grep -q "pre-commit\|commitlint" ".git/hooks/commit-msg" 2>/dev/null; then
        echo -e "${GREEN}[OK]${NC} commit-msg hook installed"
    else
        echo -e "${RED}[MISSING]${NC} commit-msg hook"
        all_ok=false
    fi

    # Check pre-push hook
    if [ -f ".git/hooks/pre-push" ] && grep -q "pre-commit" ".git/hooks/pre-push" 2>/dev/null; then
        echo -e "${GREEN}[OK]${NC} pre-push hook installed"
    else
        echo -e "${RED}[MISSING]${NC} pre-push hook"
        all_ok=false
    fi

    echo ""

    # Check prerequisites
    echo -e "${BLUE}Checking prerequisites...${NC}"
    echo ""

    if command_exists python3; then
        local py_version=$(python3 --version 2>&1 | cut -d' ' -f2)
        echo -e "${GREEN}[OK]${NC} Python: $py_version"
    else
        echo -e "${RED}[MISSING]${NC} Python 3"
        all_ok=false
    fi

    if command_exists uv; then
        local uv_version=$(uv --version 2>&1 | head -1)
        echo -e "${GREEN}[OK]${NC} uv: $uv_version"
    else
        echo -e "${RED}[MISSING]${NC} uv (required)"
        all_ok=false
    fi

    if command_exists node; then
        local node_version=$(node --version 2>&1)
        echo -e "${GREEN}[OK]${NC} Node.js: $node_version"
    else
        echo -e "${RED}[MISSING]${NC} Node.js"
        all_ok=false
    fi

    if command_exists npm; then
        local npm_version=$(npm --version 2>&1)
        echo -e "${GREEN}[OK]${NC} npm: $npm_version"
    else
        echo -e "${RED}[MISSING]${NC} npm"
        all_ok=false
    fi

    if command_exists pre-commit; then
        local pc_version=$(pre-commit --version 2>&1)
        echo -e "${GREEN}[OK]${NC} pre-commit: $pc_version"
    else
        echo -e "${RED}[MISSING]${NC} pre-commit"
        all_ok=false
    fi

    if command_exists hadolint; then
        echo -e "${GREEN}[OK]${NC} hadolint installed"
    else
        echo -e "${YELLOW}[WARN]${NC} hadolint not installed (Dockerfile linting disabled)"
    fi

    echo ""

    if [ "$all_ok" = true ]; then
        echo -e "${GREEN}All hooks are properly installed!${NC}"
        return 0
    else
        echo -e "${YELLOW}Some hooks or prerequisites are missing.${NC}"
        echo "Run './scripts/setup-hooks.sh' to install."
        return 1
    fi
}

# If check-only mode, just check and exit
if [ "$CHECK_ONLY" = true ]; then
    check_hooks
    exit $?
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Git Hooks Setup${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Check Prerequisites
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command_exists python3; then
    echo -e "${RED}Error: Python 3 is required but not installed.${NC}"
    exit 1
fi

if ! command_exists node; then
    echo -e "${RED}Error: Node.js is required but not installed.${NC}"
    echo "Install: https://nodejs.org/"
    exit 1
fi

if ! command_exists npm; then
    echo -e "${RED}Error: npm is required but not installed.${NC}"
    exit 1
fi

echo -e "${GREEN}Prerequisites OK${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Python Environment
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${YELLOW}Setting up Python environment...${NC}"

# Check for uv (mandatory)
if ! command_exists uv; then
    echo -e "${RED}Error: uv is required but not installed.${NC}"
    echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "Or with Homebrew: brew install uv"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating Python virtual environment..."
    uv venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install backend dependencies using uv sync
echo "Installing backend dependencies..."
uv sync --extra dev

echo -e "${GREEN}Python environment ready${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Node.js Environment
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${YELLOW}Setting up Node.js environment...${NC}"

# Install root-level dependencies (commitlint)
echo "Installing root dependencies (commitlint)..."
npm install

# Install frontend dependencies
if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
    echo "Installing frontend dependencies..."
    cd frontend
    npm ci
    cd "$PROJECT_ROOT"
fi

echo -e "${GREEN}Node.js environment ready${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Pre-commit Hooks Installation
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${YELLOW}Installing pre-commit hooks...${NC}"

# Install all hook types
pre-commit install
pre-commit install --hook-type commit-msg
pre-commit install --hook-type pre-push

echo -e "${GREEN}Pre-commit hooks installed${NC}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Git LFS Setup (if available)
# ─────────────────────────────────────────────────────────────────────────────

if command_exists git-lfs; then
    echo -e "${YELLOW}Setting up Git LFS...${NC}"
    git lfs install
    echo -e "${GREEN}Git LFS configured${NC}"
    echo ""
else
    echo -e "${YELLOW}Note: Git LFS not installed. Large AI model files won't be tracked.${NC}"
    echo "Install: https://git-lfs.github.io/"
    echo ""
fi

# ─────────────────────────────────────────────────────────────────────────────
# Verify Installation
# ─────────────────────────────────────────────────────────────────────────────

echo -e "${YELLOW}Verifying installation...${NC}"
echo ""

check_hooks

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo "Hooks will automatically run on:"
echo "  - git commit  -> pre-commit + commit-msg hooks"
echo "  - git push    -> pre-push hooks"
echo ""
echo "Useful commands:"
echo "  pre-commit run --all-files    # Run all hooks on all files"
echo "  ./scripts/setup-hooks.sh --check    # Check hook status"
echo "  ./scripts/validate.sh         # Full validation before PRs"
echo ""
echo "For commit message format, see: commitlint.config.js"
echo "Example: feat(api): add camera streaming endpoint (NEM-123)"
echo ""

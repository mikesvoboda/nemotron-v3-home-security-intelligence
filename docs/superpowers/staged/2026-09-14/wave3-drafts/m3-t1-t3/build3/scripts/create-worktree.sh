#!/usr/bin/env bash
#
# Create Git Worktree with Development Environment Setup
#
# This script creates a new git worktree and sets up the development environment
# including Python dependencies, Node dependencies, and pre-commit hooks.
#
# Usage:
#   ./scripts/create-worktree.sh <branch-name> [worktree-path]
#
# Arguments:
#   branch-name:   The branch to checkout (creates if doesn't exist)
#   worktree-path: Optional custom path for the worktree
#                  Default: ../<repo-name>-<sanitized-branch>
#
# Examples:
#   ./scripts/create-worktree.sh feat/new-camera-api
#   ./scripts/create-worktree.sh fix/NEM-123-websocket ../my-custom-path
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_NAME=$(basename "$PROJECT_ROOT")

# Parse arguments
BRANCH_NAME="${1:-}"
WORKTREE_PATH="${2:-}"

usage() {
    echo "Usage: $0 <branch-name> [worktree-path]"
    echo ""
    echo "Creates a new git worktree with full development environment setup."
    echo ""
    echo "Arguments:"
    echo "  branch-name   The branch to checkout (creates if doesn't exist)"
    echo "  worktree-path Optional custom path (default: ../<repo>-<branch>)"
    echo ""
    echo "Examples:"
    echo "  $0 feat/camera-api"
    echo "  $0 fix/NEM-123-bug ../custom-path"
    exit 1
}

# Validate arguments
if [ -z "$BRANCH_NAME" ]; then
    echo -e "${RED}Error: branch-name is required${NC}"
    usage
fi

# Generate worktree path if not provided
if [ -z "$WORKTREE_PATH" ]; then
    # Sanitize branch name for use in path (replace / with -)
    SANITIZED_BRANCH=$(echo "$BRANCH_NAME" | tr '/' '-')
    WORKTREE_PATH="$(dirname "$PROJECT_ROOT")/${REPO_NAME}-${SANITIZED_BRANCH}"
fi

# Convert to absolute path
WORKTREE_PATH=$(cd "$(dirname "$WORKTREE_PATH")" 2>/dev/null && pwd)/$(basename "$WORKTREE_PATH") || WORKTREE_PATH="$WORKTREE_PATH"

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Git Worktree Creator${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo -e "${YELLOW}Branch:${NC}    $BRANCH_NAME"
echo -e "${YELLOW}Path:${NC}      $WORKTREE_PATH"
echo ""

# Check if worktree path already exists
if [ -d "$WORKTREE_PATH" ]; then
    echo -e "${RED}Error: Path already exists: $WORKTREE_PATH${NC}"
    echo "Either remove it or specify a different path."
    exit 1
fi

# Check if branch exists locally or remotely
cd "$PROJECT_ROOT"
BRANCH_EXISTS=false
if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME"; then
    BRANCH_EXISTS=true
    echo -e "${GREEN}Branch exists locally: $BRANCH_NAME${NC}"
elif git show-ref --verify --quiet "refs/remotes/origin/$BRANCH_NAME"; then
    BRANCH_EXISTS=true
    echo -e "${GREEN}Branch exists on remote: $BRANCH_NAME${NC}"
else
    echo -e "${YELLOW}Branch does not exist, will create: $BRANCH_NAME${NC}"
fi

# Create the worktree
echo ""
echo -e "${BLUE}Creating worktree...${NC}"
if [ "$BRANCH_EXISTS" = true ]; then
    git worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
else
    # Create new branch from current HEAD
    git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME"
fi

echo -e "${GREEN}Worktree created successfully!${NC}"

# Change to worktree directory
cd "$WORKTREE_PATH"

# Setup Python environment
echo ""
echo -e "${BLUE}Setting up Python environment...${NC}"
if command -v uv &> /dev/null; then
    uv sync --extra dev
    echo -e "${GREEN}Python dependencies installed with uv${NC}"
else
    echo -e "${YELLOW}Warning: uv not found, skipping Python setup${NC}"
    echo "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
fi

# Setup Node.js environment
echo ""
echo -e "${BLUE}Setting up Node.js environment...${NC}"
if [ -d "frontend" ] && [ -f "frontend/package.json" ]; then
    if command -v npm &> /dev/null; then
        cd frontend
        npm ci
        cd "$WORKTREE_PATH"
        echo -e "${GREEN}Frontend dependencies installed with npm${NC}"
    else
        echo -e "${YELLOW}Warning: npm not found, skipping frontend setup${NC}"
    fi
else
    echo -e "${YELLOW}No frontend directory found, skipping${NC}"
fi

# Install pre-commit hooks
echo ""
echo -e "${BLUE}Installing pre-commit hooks...${NC}"
if command -v pre-commit &> /dev/null; then
    pre-commit install
    pre-commit install --hook-type commit-msg
    pre-commit install --hook-type pre-push
    echo -e "${GREEN}Pre-commit hooks installed${NC}"
else
    echo -e "${YELLOW}Warning: pre-commit not found, skipping hook installation${NC}"
    echo "Install: pip install pre-commit"
fi

# Summary
echo ""
echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}  Worktree Ready!${NC}"
echo -e "${GREEN}======================================${NC}"
echo ""
echo "Worktree location: $WORKTREE_PATH"
echo ""
echo "To start working:"
echo -e "  ${BLUE}cd $WORKTREE_PATH${NC}"
echo ""
echo "When done with this worktree:"
echo -e "  ${BLUE}git worktree remove $WORKTREE_PATH${NC}"
echo ""
echo "To list all worktrees:"
echo -e "  ${BLUE}git worktree list${NC}"

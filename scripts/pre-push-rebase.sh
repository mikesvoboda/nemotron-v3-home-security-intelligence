#!/bin/bash
# Pre-push hook: Auto-rebase on origin/main before pushing
#
# This hook fetches origin/main and rebases the current branch if needed.
# If rebase fails due to conflicts, it aborts and exits with error.
#
# Skip with: SKIP=auto-rebase git push

set -e

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Skip if pushing to main directly
if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
    echo "[auto-rebase] On main branch, skipping rebase"
    exit 0
fi

# Skip if detached HEAD
if [ "$CURRENT_BRANCH" = "HEAD" ]; then
    echo "[auto-rebase] Detached HEAD, skipping rebase"
    exit 0
fi

# Fetch latest main
echo "[auto-rebase] Fetching origin/main..."
git fetch origin main --quiet 2>/dev/null || {
    echo "[auto-rebase] Warning: Could not fetch origin/main, continuing without rebase"
    exit 0
}

# Check if we're behind origin/main
BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")

if [ "$BEHIND" = "0" ]; then
    echo "[auto-rebase] Branch is up-to-date with origin/main"
    exit 0
fi

echo "[auto-rebase] Branch is $BEHIND commit(s) behind origin/main, rebasing..."

# Check for uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "[auto-rebase] Error: You have uncommitted changes. Commit or stash them first."
    exit 1
fi

# Attempt rebase
if git rebase origin/main --quiet; then
    echo "[auto-rebase] Rebase successful!"

    # Show what changed
    AHEAD=$(git rev-list --count origin/main..HEAD)
    echo "[auto-rebase] Branch is now $AHEAD commit(s) ahead of origin/main"
else
    echo ""
    echo "[auto-rebase] Rebase failed due to conflicts!"
    echo ""
    echo "To resolve:"
    echo "  1. Run: git rebase --abort"
    echo "  2. Manually rebase: git fetch origin main && git rebase origin/main"
    echo "  3. Fix conflicts, then: git rebase --continue"
    echo "  4. Push again"
    echo ""

    # Abort the failed rebase
    git rebase --abort 2>/dev/null || true
    exit 1
fi

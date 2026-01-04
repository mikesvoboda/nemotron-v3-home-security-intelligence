#!/bin/bash
# Pre-push hook: Auto-rebase on origin's default branch before pushing
#
# This hook fetches the default branch and rebases the current branch if needed.
# If rebase fails due to conflicts, it aborts and exits with error.
#
# Skip with: SKIP=auto-rebase git push

set -e

# Detect the default branch dynamically
# First try symbolic-ref, fall back to common defaults if that fails
get_default_branch() {
    local default_branch

    # Try to get the default branch from origin/HEAD symbolic ref
    default_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')

    if [ -n "$default_branch" ]; then
        echo "$default_branch"
        return 0
    fi

    # If symbolic-ref fails, try to detect from remote
    # This handles cases where origin/HEAD hasn't been set
    git remote set-head origin --auto >/dev/null 2>&1 || true
    default_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')

    if [ -n "$default_branch" ]; then
        echo "$default_branch"
        return 0
    fi

    # Fall back to checking if main or master exists
    if git show-ref --verify --quiet refs/remotes/origin/main 2>/dev/null; then
        echo "main"
        return 0
    fi

    if git show-ref --verify --quiet refs/remotes/origin/master 2>/dev/null; then
        echo "master"
        return 0
    fi

    # Default to main if nothing else works
    echo "main"
}

DEFAULT_BRANCH=$(get_default_branch)

# Get current branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Skip if pushing to the default branch directly
if [ "$CURRENT_BRANCH" = "$DEFAULT_BRANCH" ]; then
    echo "[auto-rebase] On $DEFAULT_BRANCH branch, skipping rebase"
    exit 0
fi

# Skip if detached HEAD
if [ "$CURRENT_BRANCH" = "HEAD" ]; then
    echo "[auto-rebase] Detached HEAD, skipping rebase"
    exit 0
fi

# Fetch latest default branch
echo "[auto-rebase] Fetching origin/$DEFAULT_BRANCH..."
git fetch origin "$DEFAULT_BRANCH" --quiet 2>/dev/null || {
    echo "[auto-rebase] Warning: Could not fetch origin/$DEFAULT_BRANCH, continuing without rebase"
    exit 0
}

# Check if we're behind origin's default branch
BEHIND=$(git rev-list --count "HEAD..origin/$DEFAULT_BRANCH" 2>/dev/null || echo "0")

if [ "$BEHIND" = "0" ]; then
    echo "[auto-rebase] Branch is up-to-date with origin/$DEFAULT_BRANCH"
    exit 0
fi

echo "[auto-rebase] Branch is $BEHIND commit(s) behind origin/$DEFAULT_BRANCH, rebasing..."

# Check for uncommitted changes
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "[auto-rebase] Error: You have uncommitted changes. Commit or stash them first."
    exit 1
fi

# Attempt rebase
if git rebase "origin/$DEFAULT_BRANCH" --quiet; then
    echo "[auto-rebase] Rebase successful!"

    # Show what changed
    AHEAD=$(git rev-list --count "origin/$DEFAULT_BRANCH..HEAD")
    echo "[auto-rebase] Branch is now $AHEAD commit(s) ahead of origin/$DEFAULT_BRANCH"
else
    echo ""
    echo "[auto-rebase] Rebase failed due to conflicts!"
    echo ""
    echo "To resolve:"
    echo "  1. Run: git rebase --abort"
    echo "  2. Manually rebase: git fetch origin $DEFAULT_BRANCH && git rebase origin/$DEFAULT_BRANCH"
    echo "  3. Fix conflicts, then: git rebase --continue"
    echo "  4. Push again"
    echo ""

    # Abort the failed rebase
    git rebase --abort 2>/dev/null || true
    exit 1
fi

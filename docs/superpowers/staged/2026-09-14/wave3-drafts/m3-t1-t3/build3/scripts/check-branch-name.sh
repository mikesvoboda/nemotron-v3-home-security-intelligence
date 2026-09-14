#!/usr/bin/env bash
#
# Branch Name Convention Check
#
# Validates that the current branch follows naming conventions:
#
# Allowed patterns:
#   - main, master, develop (protected branches)
#   - <type>/<description> (e.g., feat/add-camera-api)
#   - <username>/<type>/<description> (e.g., msvoboda/fix/websocket-bug)
#   - dependabot/* (automated dependency updates)
#   - release/* (release branches)
#   - hotfix/* (urgent fixes)
#
# Types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert, security
#
# Examples:
#   Good: feat/add-camera-streaming, msvoboda/fix/NEM-123-websocket-reconnection
#   Bad:  my-feature, new_changes, Feature/AddCamera
#

set -e

# Get current branch name
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Skip check if we're in detached HEAD state
if [ "$BRANCH" = "HEAD" ]; then
    echo "Skipping branch name check (detached HEAD state)"
    exit 0
fi

# Define allowed branch types
TYPES="feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert|security"

# Define regex patterns for valid branch names
# Pattern 1: Protected branches
PROTECTED_PATTERN="^(main|master|develop)$"

# Pattern 2: Type/description (e.g., feat/add-camera-api)
TYPE_PATTERN="^($TYPES)/[a-z0-9][a-z0-9._-]*$"

# Pattern 3: Username/type/description (e.g., msvoboda/fix/websocket-bug)
USER_TYPE_PATTERN="^[a-z0-9_-]+/($TYPES)/[a-z0-9][a-z0-9._-]*$"

# Pattern 4: Username/simple-name (e.g., msvoboda/skill3 - for CI agents and quick branches)
USER_SIMPLE_PATTERN="^[a-z0-9_-]+/[a-z0-9][a-z0-9._-]*$"

# Pattern 5: Dependabot branches
DEPENDABOT_PATTERN="^dependabot/.*$"

# Pattern 6: Release branches (e.g., release/v1.0.0)
RELEASE_PATTERN="^release/v?[0-9]+\.[0-9]+.*$"

# Pattern 7: Hotfix branches (e.g., hotfix/critical-security-fix)
HOTFIX_PATTERN="^hotfix/[a-z0-9][a-z0-9._-]*$"

# Check if branch matches any allowed pattern
if [[ $BRANCH =~ $PROTECTED_PATTERN ]]; then
    exit 0
fi

if [[ $BRANCH =~ $TYPE_PATTERN ]]; then
    exit 0
fi

if [[ $BRANCH =~ $USER_TYPE_PATTERN ]]; then
    exit 0
fi

if [[ $BRANCH =~ $USER_SIMPLE_PATTERN ]]; then
    exit 0
fi

if [[ $BRANCH =~ $DEPENDABOT_PATTERN ]]; then
    exit 0
fi

if [[ $BRANCH =~ $RELEASE_PATTERN ]]; then
    exit 0
fi

if [[ $BRANCH =~ $HOTFIX_PATTERN ]]; then
    exit 0
fi

# Branch name doesn't match any pattern
echo ""
echo "ERROR: Invalid branch name: '$BRANCH'"
echo ""
echo "Branch names must follow one of these patterns:"
echo ""
echo "  1. Protected branches: main, master, develop"
echo ""
echo "  2. Type/description:"
echo "     <type>/<description>"
echo "     Examples: feat/add-camera-api, fix/NEM-123-websocket-bug"
echo ""
echo "  3. Username/type/description:"
echo "     <username>/<type>/<description>"
echo "     Examples: msvoboda/feat/camera-streaming, john/fix/memory-leak"
echo ""
echo "  4. Username/simple-name (for CI agents or quick branches):"
echo "     <username>/<description>"
echo "     Examples: msvoboda/skill3, ci/cleanup-task"
echo ""
echo "  5. Special branches:"
echo "     dependabot/*, release/v*, hotfix/*"
echo ""
echo "Allowed types: feat, fix, docs, style, refactor, perf, test, build, ci, chore, revert, security"
echo ""
echo "Rules:"
echo "  - Use lowercase letters, numbers, hyphens, dots, and underscores only"
echo "  - Start description with a letter or number"
echo "  - Include Linear issue ID in description when applicable (e.g., NEM-123-description)"
echo ""
echo "To rename your branch:"
echo "  git branch -m <new-branch-name>"
echo ""
exit 1

#!/usr/bin/env bash
#
# Git Bisect Helper Script
#
# This script helps identify which commit introduced a regression by
# automating the binary search process with project-specific test commands.
#
# Usage:
#   ./scripts/git-bisect-helper.sh <good-commit> <bad-commit> [test-type]
#
# Arguments:
#   good-commit: A known good commit (SHA, tag, or branch)
#   bad-commit:  A known bad commit (SHA, tag, or branch), defaults to HEAD
#   test-type:   Type of test to run (see options below)
#
# Test Types:
#   backend-unit      Run backend unit tests (default)
#   backend-int       Run backend integration tests
#   frontend-unit     Run frontend unit tests
#   frontend-e2e      Run frontend E2E tests
#   custom            Run a custom command from BISECT_CMD environment variable
#
# Examples:
#   # Find which commit broke backend unit tests
#   ./scripts/git-bisect-helper.sh v1.0.0 HEAD backend-unit
#
#   # Find which commit broke a specific test
#   BISECT_CMD="uv run pytest backend/tests/unit/test_cameras.py -v" \
#     ./scripts/git-bisect-helper.sh abc123 HEAD custom
#
#   # Find which commit broke the build
#   BISECT_CMD="cd frontend && npm run build" \
#     ./scripts/git-bisect-helper.sh v0.9.0 HEAD custom
#
# Tips:
#   - Use `git bisect log` to see the bisect history
#   - Use `git bisect visualize` to see a graphical representation
#   - Use `git bisect reset` to stop bisecting and return to original branch
#   - For flaky tests, consider running the test multiple times in BISECT_CMD
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

# Parse arguments
GOOD_COMMIT="${1:-}"
BAD_COMMIT="${2:-HEAD}"
TEST_TYPE="${3:-backend-unit}"

usage() {
    echo "Usage: $0 <good-commit> <bad-commit> [test-type]"
    echo ""
    echo "Test types:"
    echo "  backend-unit   Run backend unit tests (default)"
    echo "  backend-int    Run backend integration tests"
    echo "  frontend-unit  Run frontend unit tests"
    echo "  frontend-e2e   Run frontend E2E tests (Chromium)"
    echo "  custom         Run BISECT_CMD environment variable"
    echo ""
    echo "Examples:"
    echo "  $0 v1.0.0 HEAD backend-unit"
    echo "  $0 abc123 def456 frontend-unit"
    echo "  BISECT_CMD='uv run pytest -k test_camera' $0 v1.0.0 HEAD custom"
    exit 1
}

# Validate arguments
if [ -z "$GOOD_COMMIT" ]; then
    echo -e "${RED}Error: good-commit is required${NC}"
    usage
fi

# Verify commits exist
if ! git rev-parse "$GOOD_COMMIT" > /dev/null 2>&1; then
    echo -e "${RED}Error: good-commit '$GOOD_COMMIT' not found${NC}"
    exit 1
fi

if ! git rev-parse "$BAD_COMMIT" > /dev/null 2>&1; then
    echo -e "${RED}Error: bad-commit '$BAD_COMMIT' not found${NC}"
    exit 1
fi

# Define test commands based on test type
get_test_command() {
    case "$TEST_TYPE" in
        backend-unit)
            echo "cd '$PROJECT_ROOT' && uv run pytest backend/tests/unit/ -x -q --tb=no -n0"
            ;;
        backend-int)
            echo "cd '$PROJECT_ROOT' && uv run pytest backend/tests/integration/ -x -q --tb=no -n0"
            ;;
        frontend-unit)
            echo "cd '$PROJECT_ROOT/frontend' && npm run test -- --run"
            ;;
        frontend-e2e)
            echo "cd '$PROJECT_ROOT/frontend' && npx playwright test --project=chromium"
            ;;
        custom)
            if [ -z "$BISECT_CMD" ]; then
                echo -e "${RED}Error: BISECT_CMD environment variable is required for custom test type${NC}" >&2
                exit 1
            fi
            echo "$BISECT_CMD"
            ;;
        *)
            echo -e "${RED}Error: Unknown test type '$TEST_TYPE'${NC}" >&2
            usage
            ;;
    esac
}

TEST_CMD=$(get_test_command)

echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  Git Bisect Helper${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""
echo -e "${YELLOW}Good commit:${NC} $GOOD_COMMIT"
echo -e "${YELLOW}Bad commit:${NC}  $BAD_COMMIT"
echo -e "${YELLOW}Test type:${NC}   $TEST_TYPE"
echo -e "${YELLOW}Test command:${NC}"
echo "  $TEST_CMD"
echo ""

# Create a temporary script for git bisect run
BISECT_SCRIPT=$(mktemp)
cat > "$BISECT_SCRIPT" << EOF
#!/usr/bin/env bash
set -e
cd "$PROJECT_ROOT"

# Setup environment if needed
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate 2>/dev/null || true
fi

# Run the test command
$TEST_CMD
EOF
chmod +x "$BISECT_SCRIPT"

# Cleanup function
cleanup() {
    rm -f "$BISECT_SCRIPT"
    # Only reset if we're still in bisect state
    if git bisect log > /dev/null 2>&1; then
        echo ""
        echo -e "${YELLOW}Cleaning up bisect state...${NC}"
        git bisect reset
    fi
}
trap cleanup EXIT

# Start bisecting
echo -e "${BLUE}Starting git bisect...${NC}"
echo ""

cd "$PROJECT_ROOT"

# Initialize bisect
git bisect start
git bisect bad "$BAD_COMMIT"
git bisect good "$GOOD_COMMIT"

# Calculate approximate number of steps
TOTAL_COMMITS=$(git rev-list --count "$GOOD_COMMIT".."$BAD_COMMIT")
STEPS=$(echo "l($TOTAL_COMMITS)/l(2)" | bc -l | cut -d. -f1)
echo ""
echo -e "${YELLOW}Total commits to search:${NC} $TOTAL_COMMITS"
echo -e "${YELLOW}Estimated bisect steps:${NC} ~$STEPS"
echo ""

# Run the bisect
echo -e "${BLUE}Running automated bisect...${NC}"
echo ""

if git bisect run "$BISECT_SCRIPT"; then
    echo ""
    echo -e "${GREEN}======================================${NC}"
    echo -e "${GREEN}  Bisect Complete!${NC}"
    echo -e "${GREEN}======================================${NC}"
    echo ""
    echo "The first bad commit has been identified above."
    echo ""
    echo "Useful commands:"
    echo "  git show <commit>          Show the commit details"
    echo "  git log -p <commit>        Show commit with diff"
    echo "  git blame <file>           See line-by-line history"
    echo ""
else
    echo ""
    echo -e "${RED}======================================${NC}"
    echo -e "${RED}  Bisect Failed${NC}"
    echo -e "${RED}======================================${NC}"
    echo ""
    echo "The bisect could not complete. Possible reasons:"
    echo "  - The test command failed on both good and bad commits"
    echo "  - The regression is not reproducible with the given test"
    echo "  - There are commits that cannot be tested (e.g., broken builds)"
    echo ""
    echo "Try running the test manually on specific commits to debug."
    exit 1
fi

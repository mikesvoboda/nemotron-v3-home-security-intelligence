#!/usr/bin/env bash
# Fast parallel test runner with timing report
#
# Usage:
#   ./scripts/test-fast.sh                    # Run all unit tests
#   ./scripts/test-fast.sh backend/tests/     # Run specific path
#   ./scripts/test-fast.sh unit 8             # Run unit tests with 8 workers
#   ./scripts/test-fast.sh integration        # Run integration tests
#
set -e

# Parse arguments
TARGET="${1:-unit}"
WORKERS="${2:-auto}"

# Map shorthand to full paths
case "$TARGET" in
    unit)
        TARGET_PATH="backend/tests/unit/"
        ;;
    integration)
        TARGET_PATH="backend/tests/integration/"
        ;;
    all)
        TARGET_PATH="backend/tests/"
        ;;
    *)
        TARGET_PATH="$TARGET"
        ;;
esac

echo "========================================"
echo "Fast Parallel Test Runner"
echo "========================================"
echo "Target: $TARGET_PATH"
echo "Workers: $WORKERS"
echo "========================================"
echo

# Activate virtual environment if not already active
if [[ -z "$VIRTUAL_ENV" ]]; then
    if [[ -f ".venv/bin/activate" ]]; then
        source .venv/bin/activate
    fi
fi

# Run tests with parallel execution and timing
pytest "$TARGET_PATH" \
    -n "$WORKERS" \
    --dist=loadgroup \
    --durations=20 \
    -v \
    "${@:3}"

echo
echo "========================================"
echo "Test run complete"
echo "========================================"

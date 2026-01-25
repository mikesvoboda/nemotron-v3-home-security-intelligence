#!/bin/bash
# Full pre-push test runner - comprehensive validation
# Called when FULL_TESTS=1 git push
# Normal pushes use fast smoke tests in pre-push-tests.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "Running FULL test suite (this may take several minutes)..."

# Run validate.sh which does comprehensive testing
exec ./scripts/validate.sh

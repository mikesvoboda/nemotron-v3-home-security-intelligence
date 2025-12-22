#!/bin/bash
# Test runner script for database tests

set -e

cd "$(dirname "$0")/../.."

echo "Running database unit tests..."
python3 -m pytest backend/tests/unit/test_database.py -v --tb=short

echo ""
echo "All tests passed successfully!"

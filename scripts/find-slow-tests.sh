#!/bin/bash
# Find tests that hang or take too long

source .venv/bin/activate

echo "=== UNIT TESTS ==="
for f in backend/tests/unit/test_*.py; do
  name=$(basename "$f")
  result=$(timeout 15 pytest "$f" -q --tb=no 2>&1 | tail -1)
  exit_code=$?
  if [ $exit_code -eq 124 ]; then
    echo "TIMEOUT: $name"
  elif [ $exit_code -ne 0 ]; then
    echo "FAILED: $name - $result"
  else
    echo "OK: $name - $result"
  fi
done

echo ""
echo "=== INTEGRATION TESTS ==="
for f in backend/tests/integration/test_*.py; do
  name=$(basename "$f")
  result=$(timeout 30 pytest "$f" -q --tb=no 2>&1 | tail -1)
  exit_code=$?
  if [ $exit_code -eq 124 ]; then
    echo "TIMEOUT: $name"
  elif [ $exit_code -ne 0 ]; then
    echo "FAILED: $name - $result"
  else
    echo "OK: $name - $result"
  fi
done

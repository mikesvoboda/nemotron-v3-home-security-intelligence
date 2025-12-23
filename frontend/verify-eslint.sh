#!/bin/bash
# Verify ESLint configuration

cd "$(dirname "$0")"

echo "Verifying ESLint configuration..."
echo "=================================="
echo ""

# Test ESLint can parse config
echo "1. Testing ESLint configuration parsing..."
npx eslint --print-config src/main.tsx > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✓ ESLint configuration is valid"
else
    echo "   ✗ ESLint configuration has errors"
    exit 1
fi

echo ""
echo "2. Running ESLint on src directory..."
npm run lint
LINT_EXIT=$?

echo ""
if [ $LINT_EXIT -eq 0 ]; then
    echo "=================================="
    echo "✓ ESLint verification complete - all checks passed!"
else
    echo "=================================="
    echo "✗ ESLint found issues (exit code: $LINT_EXIT)"
    echo "Run 'npm run lint:fix' to auto-fix some issues"
    exit $LINT_EXIT
fi

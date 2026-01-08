#!/usr/bin/env bash
# Accessibility Smoke Test - Pre-push Hook
#
# Runs a fast subset of E2E accessibility tests to catch WCAG violations
# (especially color contrast issues) before they reach CI/CD.
#
# Usage:
#   ./scripts/a11y-smoke-test.sh          # Run a11y tests
#   SKIP=a11y-smoke-test git push         # Skip this check
#
# Performance:
#   - Runs ~30-60 seconds
#   - Tests key pages for color contrast and ARIA violations
#   - Uses Playwright with axe-core
#
# What it catches:
#   - Color contrast violations (WCAG 2 AA 4.5:1 ratio)
#   - Missing ARIA labels
#   - Form accessibility issues
#   - Focus management problems

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}[a11y-smoke-test]${NC} Running accessibility smoke tests..."

cd "$PROJECT_ROOT/frontend"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${RED}[a11y-smoke-test]${NC} node_modules not found. Run 'npm install' first."
    exit 1
fi

# Check if Playwright is installed
if [ ! -d "node_modules/@playwright" ]; then
    echo -e "${RED}[a11y-smoke-test]${NC} Playwright not installed. Run 'npx playwright install' first."
    exit 1
fi

# Run accessibility tests - focus on pages with known color contrast patterns
# Uses grep to select specific accessibility test patterns
# Runs only chromium for speed (cross-browser a11y is consistent)
echo -e "${YELLOW}[a11y-smoke-test]${NC} Testing key pages for WCAG violations..."

# Run a subset of accessibility tests (pages most likely to have color issues)
# These tests use axe-core which checks for color contrast automatically
if npx playwright test tests/e2e/specs/accessibility.spec.ts \
    --project=chromium \
    --grep "has no accessibility violations" \
    --reporter=line \
    --timeout=30000 \
    --retries=0 2>&1 | tee /tmp/a11y-smoke-test.log; then
    echo -e "${GREEN}[a11y-smoke-test]${NC} All accessibility tests passed!"
    exit 0
else
    echo -e "${RED}[a11y-smoke-test]${NC} Accessibility violations detected!"
    echo ""
    echo -e "${YELLOW}Common fixes:${NC}"
    echo "  - Color contrast: Change text-red-500 to text-red-400 on dark backgrounds"
    echo "  - Color contrast: Change text-green-600 to emerald for badges"
    echo "  - Missing labels: Add aria-label or htmlFor attributes"
    echo ""
    echo -e "${YELLOW}To see full details:${NC}"
    echo "  cat /tmp/a11y-smoke-test.log"
    echo ""
    echo -e "${YELLOW}To skip this check (not recommended):${NC}"
    echo "  SKIP=a11y-smoke-test git push"
    exit 1
fi

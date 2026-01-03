#!/bin/bash
# Run all audits locally and generate summary
# Usage: ./scripts/audit-summary.sh
#
# This script runs the same audits as the weekly-audit.yml workflow
# locally, allowing you to preview findings before they appear in CI.

set -e

# Determine script and project root directories
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    RED='\033[0;31m'
    YELLOW='\033[1;33m'
    CYAN='\033[0;36m'
    NC='\033[0m'
else
    GREEN=''
    RED=''
    YELLOW=''
    CYAN=''
    NC=''
fi

cd "$PROJECT_ROOT"

echo ""
printf "${GREEN}============================================${NC}\n"
printf "${GREEN}       LOCAL AUDIT SUMMARY${NC}\n"
printf "${GREEN}============================================${NC}\n"
echo ""

# Security Scan (Semgrep)
printf "${CYAN}=== Security Scan (Semgrep) ===${NC}\n"
if command -v semgrep &> /dev/null; then
    semgrep --config=auto backend/ frontend/src/ 2>&1 | head -50 || true
else
    printf "${YELLOW}Semgrep not installed. Run: pip install semgrep${NC}\n"
    echo "Or: uv tool install semgrep"
fi
echo ""

# Python Dependency Audit
printf "${CYAN}=== Python Dependency Audit (pip-audit) ===${NC}\n"
if command -v pip-audit &> /dev/null; then
    uv export --no-hashes > /tmp/requirements-audit.txt 2>/dev/null
    pip-audit -r /tmp/requirements-audit.txt --desc 2>&1 | head -30 || true
    rm -f /tmp/requirements-audit.txt
else
    printf "${YELLOW}pip-audit not installed. Run: uv tool install pip-audit${NC}\n"
fi
echo ""

# Dead Code (Vulture)
printf "${CYAN}=== Dead Code (Vulture) ===${NC}\n"
if [ -f "$PROJECT_ROOT/vulture_whitelist.py" ]; then
    uv run vulture backend/ vulture_whitelist.py --min-confidence 80 2>&1 | head -30 || true
else
    uv run vulture backend/ --min-confidence 80 2>&1 | head -30 || true
fi
echo ""

# Complexity (Radon)
printf "${CYAN}=== Complexity (Radon) ===${NC}\n"
echo "Functions with complexity C or higher:"
uv run radon cc backend/ -a -nc 2>&1 | head -30 || true
echo ""
echo "Maintainability Index:"
uv run radon mi backend/ -nc 2>&1 | head -30 || true
echo ""

# Frontend Dead Code (Knip)
printf "${CYAN}=== Frontend Dead Code (Knip) ===${NC}\n"
if [ -d "$PROJECT_ROOT/frontend/node_modules" ]; then
    cd "$PROJECT_ROOT/frontend" && npx knip 2>&1 | head -30 || true
    cd "$PROJECT_ROOT"
else
    printf "${YELLOW}Frontend dependencies not installed. Run: cd frontend && npm install${NC}\n"
fi
echo ""

echo ""
printf "${GREEN}============================================${NC}\n"
printf "${GREEN}Audit complete. Review findings above.${NC}\n"
printf "${GREEN}Create beads for issues with: bd create '<title>' --labels weekly-audit${NC}\n"
printf "${GREEN}============================================${NC}\n"

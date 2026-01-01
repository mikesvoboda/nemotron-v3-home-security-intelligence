#!/bin/bash
#
# API Coverage Check
# Finds backend API endpoints with no frontend consumers
#
# Usage: ./scripts/check-api-coverage.sh
#

set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Colors
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    NC='\033[0m'
else
    RED=''
    GREEN=''
    NC=''
fi

echo "Checking API endpoint coverage..."

# Extract all route paths from backend
BACKEND_ROUTES=$(grep -rh "@router\.\(get\|post\|put\|delete\|patch\)" "$PROJECT_ROOT/backend/api/routes/" \
  | sed -n 's/.*"\([^"]*\)".*/\1/p' | sort -u)

# Search frontend for each route
UNUSED=()
for route in $BACKEND_ROUTES; do
  # Normalize route (remove path params for matching)
  normalized=$(echo "$route" | sed 's/{[^}]*}/<param>/g')
  if ! grep -rq "$normalized\|$route" "$PROJECT_ROOT/frontend/src/"; then
    UNUSED+=("$route")
  fi
done

if [ ${#UNUSED[@]} -gt 0 ]; then
  printf "${RED}Unused backend endpoints (no frontend consumer found):${NC}\n"
  printf '  - %s\n' "${UNUSED[@]}"
  echo ""
  echo "Consider: Are these endpoints needed? Should frontend use them?"
  exit 1
fi

printf "${GREEN}All backend endpoints have frontend consumers${NC}\n"

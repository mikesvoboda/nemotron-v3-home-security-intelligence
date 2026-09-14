#!/usr/bin/env bash
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

# Allowlisted endpoints that are intentionally not consumed by frontend
# These are admin/internal endpoints that may be used via API directly or planned for future use
ALLOWLIST=(
  # Prompt management admin endpoints - for managing prompt versions and importing prompts
  # These endpoints enable:
  # - /history/{version_id}: View historical prompt versions
  # - /import/preview: Preview prompt import before applying
  # - /{model}: Get prompts for a specific model (admin use)
  "/history/{version_id}"
  "/import/preview"
  "/{model}"
)

# Extract all route paths from backend
BACKEND_ROUTES=$(grep -rh "@router\.\(get\|post\|put\|delete\|patch\)" "$PROJECT_ROOT/backend/api/routes/" \
  | sed -n 's/.*"\([^"]*\)".*/\1/p' | sort -u)

# Check if a route is in the allowlist
is_allowlisted() {
  local route="$1"
  for allowed in "${ALLOWLIST[@]}"; do
    if [ "$route" = "$allowed" ]; then
      return 0
    fi
  done
  return 1
}

# Search frontend for each route
UNUSED=()
for route in $BACKEND_ROUTES; do
  # Skip allowlisted endpoints
  if is_allowlisted "$route"; then
    continue
  fi
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

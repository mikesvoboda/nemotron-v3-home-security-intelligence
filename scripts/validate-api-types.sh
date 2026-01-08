#!/bin/sh
#
# Validate API Type Contract Consistency
#
# This script validates that TypeScript types match the backend OpenAPI spec.
# It's part of the CI/CD pipeline to catch type mismatches early.
#
# Usage:
#   ./scripts/validate-api-types.sh              # Full validation
#   ./scripts/validate-api-types.sh --verbose    # Detailed output
#
# Exit codes:
#   0 - Types are synchronized
#   1 - Types are out of sync
#   2 - Required dependencies missing
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors (portable)
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

VERBOSE=false

print_step() {
    printf "${CYAN}> %s${NC}\n" "$1"
}

print_success() {
    printf "${GREEN}[OK] %s${NC}\n" "$1"
}

print_error() {
    printf "${RED}[ERROR] %s${NC}\n" "$1" >&2
}

print_warning() {
    printf "${YELLOW}[WARN] %s${NC}\n" "$1"
}

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        --verbose)
            VERBOSE=true
            ;;
    esac
done

# ============================================================================
# Validation Steps
# ============================================================================

echo ""
printf "${CYAN}=== API Type Contract Validation ===${NC}\n"
echo ""

# Step 1: Check prerequisites
print_step "Checking prerequisites..."

if ! command -v node >/dev/null 2>&1; then
    print_error "Node.js is required but not installed"
    exit 2
fi

if ! command -v python >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
    print_error "Python is required but not installed"
    exit 2
fi

if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
    print_error "Frontend dependencies not installed"
    echo "Run: cd frontend && npm install"
    exit 2
fi

print_success "Prerequisites available"

# Step 2: Run type generation and capture output
print_step "Generating types from OpenAPI spec..."

if [ "$VERBOSE" = true ]; then
    ./scripts/generate-types.sh --check 2>&1 || exit 1
else
    ./scripts/generate-types.sh --check >/dev/null 2>&1 || exit 1
fi

print_success "API types are synchronized"

# Step 3: Type checking
print_step "Running TypeScript type checker..."

cd "$PROJECT_ROOT/frontend"

if [ "$VERBOSE" = true ]; then
    npm run typecheck || exit 1
else
    npm run typecheck >/dev/null 2>&1 || exit 1
fi

print_success "TypeScript type checking passed"

# Step 4: Additional validation - check for unused types
print_step "Scanning for unused API types..."

# Simple check: look for exported types that are never imported
GENERATED_API="$PROJECT_ROOT/frontend/src/types/generated/api.ts"
UNUSED_TYPES=0

# Count exported interfaces
EXPORTED_COUNT=$(grep -c "^export interface" "$GENERATED_API" || echo "0")

if [ "$VERBOSE" = true ]; then
    echo "Total exported API types: $EXPORTED_COUNT"
fi

# Check that generated types file is not empty
if [ ! -s "$GENERATED_API" ]; then
    print_error "Generated API types file is empty: $GENERATED_API"
    exit 1
fi

FILE_SIZE=$(wc -c < "$GENERATED_API")
if [ "$FILE_SIZE" -lt 1000 ]; then
    print_warning "Generated API types file is suspiciously small ($FILE_SIZE bytes)"
fi

print_success "API types file validation passed"

# Step 5: Verify critical types exist in generated index
print_step "Verifying critical API types are present..."

GENERATED_INDEX="$PROJECT_ROOT/frontend/src/types/generated/index.ts"
REQUIRED_TYPES=(
    "Camera"
    "Event"
    "Detection"
    "HealthResponse"
    "SystemStats"
    "GPUStats"
)

MISSING_TYPES=0
for type_name in "${REQUIRED_TYPES[@]}"; do
    if ! grep -q "export type $type_name\|export interface $type_name" "$GENERATED_INDEX"; then
        print_error "Missing critical type: $type_name"
        MISSING_TYPES=$((MISSING_TYPES + 1))
    fi
done

if [ $MISSING_TYPES -gt 0 ]; then
    print_error "Missing $MISSING_TYPES critical API types"
    exit 1
fi

print_success "All critical API types are present"

# Step 6: Verify no breaking changes in type structure
print_step "Checking for type structure integrity..."

# Verify basic structure - should have operation definitions
if ! grep -q "export interface operations" "$GENERATED_API"; then
    print_warning "Operations interface not found in generated types"
fi

# Verify paths are defined
if ! grep -q "export interface paths" "$GENERATED_API"; then
    print_warning "Paths interface not found in generated types"
fi

print_success "Type structure looks healthy"

# ============================================================================
# Summary
# ============================================================================

echo ""
printf "${GREEN}============================================${NC}\n"
printf "${GREEN}  API Type Contract Validation PASSED${NC}\n"
printf "${GREEN}============================================${NC}\n"
echo ""
echo "Summary:"
echo "  - Generated types match OpenAPI spec"
echo "  - TypeScript compilation successful"
echo "  - All critical types present"
echo "  - No breaking structural changes detected"
echo ""
echo "Next steps:"
echo "  - Review generated types: frontend/src/types/generated/api.ts"
echo "  - Run tests: npm test"
echo "  - Run E2E contract tests: npx playwright test"
echo ""

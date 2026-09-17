#!/bin/sh
#
# Mutation Testing Script
# Runs mutation tests for backend (mutmut) and/or frontend (Stryker)
#
# Usage:
#   ./scripts/mutation-test.sh              # Run both backend and frontend
#   ./scripts/mutation-test.sh --backend    # Backend only
#   ./scripts/mutation-test.sh --frontend   # Frontend only
#   ./scripts/mutation-test.sh --module <path>  # Backend specific module
#   ./scripts/mutation-test.sh --help       # Show help
#
# Mutation testing verifies test effectiveness by making small changes (mutants)
# to source code and checking if tests catch them.
#
# See docs/developer/patterns/mutation-testing.md for detailed guidance.

set -e

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Flags
RUN_BACKEND=true
RUN_FRONTEND=true
BACKEND_MODULE=""

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

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

print_header() {
    printf "\n${GREEN}=== %s ===${NC}\n" "$1"
}

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

show_help() {
    cat << 'EOF'
Mutation Testing Script

Usage:
    ./scripts/mutation-test.sh [OPTIONS]

Options:
    -h, --help          Show this help message
    --backend           Run backend mutation tests only (mutmut)
    --frontend          Run frontend mutation tests only (Stryker)
    --module <name>     Mutate one backend module by bare name (e.g. severity).
                        mutmut 3 filters by fnmatch over mutant keys, so the
                        WP4.3 runner takes the name, not a path.

Examples:
    ./scripts/mutation-test.sh                   # Run all mutation tests
    ./scripts/mutation-test.sh --backend         # Backend only
    ./scripts/mutation-test.sh --frontend        # Frontend only
    ./scripts/mutation-test.sh --module severity

Default Target Modules:
    Backend:  the widened WP4.3 set -- everything under backend/services/ and
              backend/api/routes/ ([tool.mutmut] source_paths)
    Frontend: src/utils/risk.ts, src/utils/time.ts, src/utils/confidence.ts

Mutation Score Interpretation:
    90-100%  Excellent - Tests are highly effective
    80-89%   Good - Tests catch most mutations
    60-79%   Fair - Some test gaps exist
    <60%     Poor - Tests need improvement

See docs/developer/patterns/mutation-testing.md for detailed guidance on improving mutation scores.

EOF
    exit 0
}

# ─────────────────────────────────────────────────────────────────────────────
# Parse Arguments
# ─────────────────────────────────────────────────────────────────────────────

while [ $# -gt 0 ]; do
    case "$1" in
        -h|--help)
            show_help
            ;;
        --backend)
            RUN_BACKEND=true
            RUN_FRONTEND=false
            shift
            ;;
        --frontend)
            RUN_BACKEND=false
            RUN_FRONTEND=true
            shift
            ;;
        --module)
            BACKEND_MODULE="$2"
            RUN_BACKEND=true
            RUN_FRONTEND=false
            shift 2
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────────────
# Backend Mutation Testing (mutmut) -- DELEGATES to scripts/mutation-run.sh
# ─────────────────────────────────────────────────────────────────────────────

run_backend_mutation() {
    # WP4.3: the 2.x-era inline mutmut calls (--paths-to-mutate/--tests-dir/
    # --runner) are dead flags under mutmut 3.8 -- they errored into a
    # `|| true` and produced nothing. mutmut 3 is config-driven
    # ([tool.mutmut]); mutation-run.sh is the ONE runner (workflow included),
    # so call sites cannot rot independently again.
    print_header "Backend Mutation Testing (mutmut)"
    "$SCRIPT_DIR/mutation-run.sh" ${BACKEND_MODULE:+"$BACKEND_MODULE"}
}

# ─────────────────────────────────────────────────────────────────────────────
# Frontend Mutation Testing (Stryker)
# ─────────────────────────────────────────────────────────────────────────────

run_frontend_mutation() {
    print_header "Frontend Mutation Testing (Stryker)"

    cd "$PROJECT_ROOT/frontend"

    # Check for npm
    if ! command -v npm >/dev/null 2>&1; then
        print_error "npm not found. Install Node.js from https://nodejs.org/"
        exit 1
    fi

    # Check for node_modules
    if [ ! -d "node_modules" ]; then
        print_step "Installing dependencies..."
        npm ci
    fi

    # Check if Stryker is installed
    if [ ! -f "node_modules/@stryker-mutator/core/package.json" ]; then
        print_step "Installing Stryker dependencies..."
        npm install @stryker-mutator/core @stryker-mutator/typescript-checker @stryker-mutator/vitest-runner --save-dev
    fi

    # Run Stryker
    print_step "Running mutation tests (this may take several minutes)..."
    npm run test:mutation || true

    print_success "Frontend mutation testing complete"
    echo ""
    echo "Mutation report generated at: frontend/reports/mutation/mutation-report.html"
}

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

printf "${GREEN}Starting mutation testing...${NC}\n"
printf "Project root: ${CYAN}%s${NC}\n" "$PROJECT_ROOT"

if [ "$RUN_BACKEND" = true ]; then
    run_backend_mutation
fi

if [ "$RUN_FRONTEND" = true ]; then
    run_frontend_mutation
fi

echo ""
printf "${GREEN}============================================${NC}\n"
printf "${GREEN}  MUTATION TESTING COMPLETE${NC}\n"
printf "${GREEN}============================================${NC}\n"
echo ""
echo "Next steps:"
echo "1. Review surviving mutants to identify test gaps"
echo "2. Add targeted tests to kill surviving mutants"
echo "3. Re-run mutation tests to verify improvements"
echo ""
echo "For detailed guidance, see: docs/developer/patterns/mutation-testing.md"

#!/bin/sh
#
# Full Project Validation Script
# Runs linting, type checking, and tests for both backend and frontend
#
# This script is self-contained and will:
# - Use uv for Python dependency management (10-100x faster than pip)
# - Fail fast with actionable error messages
#
# Usage:
#   ./scripts/validate.sh              # Full validation
#   ./scripts/validate.sh --backend    # Backend only
#   ./scripts/validate.sh --frontend   # Frontend only
#   ./scripts/validate.sh --fast       # Change-scoped advisory tier (<=10 min, no coverage)
#   ./scripts/validate.sh --help       # Show help
#

set -e

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Determine script and project root directories
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Required Node.js major version — keep in sync with .github/workflows/ci.yml
# (env.NODE_VERSION) and frontend/.nvmrc. Node 24 = Latest LTS; Node 20 is EOL.
REQUIRED_NODE_MAJOR=24

# Flags
RUN_BACKEND=true
RUN_FRONTEND=true
RUN_FAST=false

# Colors (portable - works in sh)
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
Full Project Validation Script

Usage:
    ./scripts/validate.sh [OPTIONS]

Options:
    -h, --help      Show this help message
    --backend       Run backend validation only
    --frontend      Run frontend validation only
    --fast          Change-scoped advisory tier (<=10 min, no coverage proof;
                    base ref via VALIDATE_BASE=<ref>, per-file reasons via
                    VALIDATE_WHY=1). Never prints the full gate's success
                    banner - the full gate stays required before merge.

Examples:
    ./scripts/validate.sh               # Full validation
    ./scripts/validate.sh --backend     # Backend only
    ./scripts/validate.sh --frontend    # Frontend only
    ./scripts/validate.sh --fast        # Advisory tier on the change set

Requirements:
    Backend:  Python 3.14+, uv (https://docs.astral.sh/uv/)
    Frontend: Node.js 24+ (22.12+ accepted), npm, node_modules installed

Setup:
    Run ./scripts/setup.sh first to install all dependencies.

EOF
    exit 0
}

check_command() {
    command -v "$1" >/dev/null 2>&1
}

# ─────────────────────────────────────────────────────────────────────────────
# Container Discovery (Worktree-Aware)
# ─────────────────────────────────────────────────────────────────────────────
# Discovers running PostgreSQL/Redis containers from any worktree and configures
# environment variables for integration tests.

discover_containers() {
    print_step "Discovering running containers..."

    # Determine container runtime (podman or docker)
    if check_command podman; then
        CONTAINER_CMD="podman"
    elif check_command docker; then
        CONTAINER_CMD="docker"
    else
        print_warning "No container runtime found (podman/docker)"
        print_warning "Integration tests will be skipped if DATABASE_URL is not set"
        return 1
    fi

    # Find PostgreSQL container (may be from any worktree)
    # Matches legacy underscore naming (..._postgres_ / ..._postgres_1) and
    # compose-v2 provider naming (<project>-postgres-1). The end anchor keeps
    # sibling services such as redis-exporter from matching.
    POSTGRES_CONTAINER=$($CONTAINER_CMD ps --format '{{.Names}}' 2>/dev/null | grep -E '[_-]postgres[-_]?[0-9]?$' | head -1)

    if [ -z "$POSTGRES_CONTAINER" ]; then
        print_warning "No PostgreSQL container found running"
        print_warning "Integration tests will be skipped"
        return 1
    fi

    print_success "Found PostgreSQL container: $POSTGRES_CONTAINER"

    # Extract credentials from the running container
    POSTGRES_USER=$($CONTAINER_CMD exec "$POSTGRES_CONTAINER" printenv POSTGRES_USER 2>/dev/null)
    POSTGRES_PASSWORD=$($CONTAINER_CMD exec "$POSTGRES_CONTAINER" printenv POSTGRES_PASSWORD 2>/dev/null)
    POSTGRES_DB=$($CONTAINER_CMD exec "$POSTGRES_CONTAINER" printenv POSTGRES_DB 2>/dev/null)

    if [ -z "$POSTGRES_USER" ] || [ -z "$POSTGRES_PASSWORD" ]; then
        print_warning "Could not extract PostgreSQL credentials from container"
        return 1
    fi

    # Set TEST_DATABASE_URL for integration tests (conftest.py checks this first)
    if [ -z "$TEST_DATABASE_URL" ]; then
        export TEST_DATABASE_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB:-$POSTGRES_USER}"
        print_success "Configured TEST_DATABASE_URL from container"
    else
        print_success "Using existing TEST_DATABASE_URL"
    fi

    # Also set DATABASE_URL for other tools that may use it
    if [ -z "$DATABASE_URL" ]; then
        export DATABASE_URL="postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB:-$POSTGRES_USER}"
    fi

    # Find Redis container (same legacy + compose-v2 provider naming, end-anchored
    # so redis-exporter does not match)
    REDIS_CONTAINER=$($CONTAINER_CMD ps --format '{{.Names}}' 2>/dev/null | grep -E '[_-]redis[-_]?[0-9]?$' | head -1)

    if [ -n "$REDIS_CONTAINER" ]; then
        if [ -z "$REDIS_URL" ]; then
            export REDIS_URL="redis://localhost:6379/0"
            print_success "Found Redis container: $REDIS_CONTAINER"
        fi
    else
        print_warning "No Redis container found - some tests may be skipped"
    fi

    return 0
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
        --fast)
            RUN_FAST=true
            RUN_BACKEND=false
            RUN_FRONTEND=false
            shift
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────────────
# Backend Validation
# ─────────────────────────────────────────────────────────────────────────────

run_backend_validation() {
    print_header "Backend Validation"

    # Check for uv
    print_step "Checking for uv..."
    if ! check_command uv; then
        print_error "uv not found"
        echo ""
        echo "To install uv, run:"
        echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
        echo ""
        echo "Or with Homebrew:"
        echo "  brew install uv"
        exit 1
    fi
    print_success "uv $(uv --version | cut -d' ' -f2) found"

    # Sync dependencies (creates venv if needed)
    print_step "Syncing dependencies with uv..."
    if ! uv sync --extra dev --frozen; then
        print_error "Failed to sync dependencies"
        echo ""
        echo "Try regenerating the lock file:"
        echo "  uv lock && uv sync --extra dev"
        exit 1
    fi
    print_success "Dependencies synced"

    # Run linting
    print_step "Running Ruff (Linting)..."
    if ! uv run ruff check "$PROJECT_ROOT/backend"; then
        print_error "Ruff linting failed"
        echo ""
        echo "To auto-fix some issues, run:"
        echo "  uv run ruff check --fix $PROJECT_ROOT/backend"
        exit 1
    fi
    print_success "Ruff linting passed"

    # Run formatting check
    print_step "Running Ruff (Format Check)..."
    if ! uv run ruff format --check "$PROJECT_ROOT/backend"; then
        print_error "Ruff format check failed"
        echo ""
        echo "To auto-format, run:"
        echo "  uv run ruff format $PROJECT_ROOT/backend"
        exit 1
    fi
    print_success "Ruff format check passed"

    # Run type checking
    print_step "Running MyPy (Type Checking)..."
    if ! uv run mypy "$PROJECT_ROOT/backend"; then
        print_error "MyPy type checking failed"
        echo ""
        echo "Fix the type errors shown above, then re-run validation."
        exit 1
    fi
    print_success "MyPy type checking passed"

    # Discover running containers for integration tests
    # This is worktree-aware - finds containers from any worktree
    if discover_containers; then
        print_success "Container environment configured for integration tests"
    else
        print_warning "Running without containers - integration tests may be skipped"
    fi

    # Run tests
    # Local validation uses 80% combined coverage (unit + integration)
    # CI enforces per-test-type thresholds: unit=85%, integration=50%
    # backend/tests/load and backend/tests/benchmarks are out of the PR-gate contract:
    # CI runs them only from their own path-scoped workflows (benchmarks.yml,
    # load-tests.yml), never from the unit+integration gate. backend/tests/e2e is out
    # for the same reason (R-T7-BACKEND-SCOPE: PR pytest jobs collect only
    # contracts/integration/security/unit; its :680 '-k' name-list does not match the
    # e2e test_pipeline_integration names). backend/tests/chaos is out per the
    # pre-approved conditional in R-T7-POISON-CASCADE + AMENDMENT-RESOLUTION
    # (SDD ledger 2026-09-12, progress.md :1203+/:1272+): its solo -n0 arbiter rerun
    # HUNG (pytest-timeout fired, RC=1 stack dump — not SIGSEGV 139/137), and in the
    # full lane its test_worker_chaos.py dispatch bracket exactly matches an 11-worker
    # node-down cascade (lane 2: lines 26414-27010; lane 3: 12742-13415) — the suite
    # is xdist-unsafe by its own conftest "deadlock" docs. CI strictness is unchanged:
    # grep of .github/workflows shows zero references to tests/chaos (path-scoped
    # pytest jobs collect only contracts/integration/security/unit), so CI never
    # collected it — same convention class as load/benchmarks/e2e. Chaos deserves
    # its own xdist-unsafe workflow someday; NOT this milestone. No CLI '-m' is
    # passed here because it would replace pyproject.toml's addopts expression
    # (which carries "-m 'not gpu'").
    print_step "Running pytest (Tests & Coverage)..."
    # D14 split (M1 Task 7 pre-authorized fix, applied 2026-09-13): mirror
    # CI's shape — unit suite in one pytest process, integration suites in
    # another. The single combined process OOM-killed xdist workers at
    # 30-50GB RSS (R-T7-OTEL-OOM class; workers running TestClient
    # lifespans accumulate ML-stack Rust state — tokenizers
    # pretty_env_logger init aborts on the second SetLoggerError) and the
    # controller died with them, cascading 377-1398 setup ERRORs. The split
    # is what CI already does (ci.yml unit job 85% gate; integration jobs
    # separate with --cov-fail-under=0).
    #
    # Coverage semantics PRESERVED — the 80% gate stays COMBINED
    # (unit+integration, as the pre-split single run measured it; run-4's
    # 85.17% and run-5's crash-collapsed 25.26% were both that number).
    # Mechanics: each pytest-cov invocation writes its own data file via the
    # COVERAGE_FILE env var (pytest-cov has no --cov-data-file flag — the
    # first draft of this split used one and died on "unrecognized
    # arguments"), then `coverage combine` merges them and the report is
    # gated at 80 against the merged file. Both runs pass --cov-fail-under=0
    # so pyproject's [tool.coverage.report] fail_under=85 cannot fire early.
    # Suite scope unchanged: the four --ignore exclusions in both runs, and
    # the split collects the identical 32000 items as the whole-tree path
    # did (verified by --co -q diff, zero delta). No `| tee`: this is /bin/sh
    # with `set -e` but no pipefail, so a pipe would test tee's status and
    # mask pytest failures — output goes to a log file that is cat'd on
    # failure instead. Environment note (run-5, 2026-09-13): when no
    # postgres container is discoverable the integration tier silently falls
    # back to spawning a testcontainer per worker DB — that run filled its
    # 9.8GB docker disk with ~800MB WAL and DiskFull-cascaded 377 setup
    # ERRORs. Pre-export TEST_DATABASE_URL/TEST_REDIS_URL to point at a
    # real server before running this gate.
    _VALIDATE_COV_DATA_DIR=$(mktemp -d)
    print_step "Running backend unit tests (coverage)..."
    if ! COVERAGE_FILE="$_VALIDATE_COV_DATA_DIR/.coverage.unit" \
        uv run pytest "$PROJECT_ROOT/backend/tests/unit" "$PROJECT_ROOT/backend/tests/contracts" "$PROJECT_ROOT/backend/tests/security" \
        --cov="$PROJECT_ROOT/backend" --cov-report= --cov-fail-under=0 \
        --ignore="$PROJECT_ROOT/backend/tests/load" --ignore="$PROJECT_ROOT/backend/tests/benchmarks" --ignore="$PROJECT_ROOT/backend/tests/e2e" --ignore="$PROJECT_ROOT/backend/tests/chaos" \
        > /tmp/validate-backend-unit.log 2>&1; then
        print_error "Backend unit tests failed (full log: /tmp/validate-backend-unit.log)"
        tail -60 /tmp/validate-backend-unit.log
        rm -rf "$_VALIDATE_COV_DATA_DIR"
        echo ""
        echo "Fix failing tests, then re-run validation."
        exit 1
    fi
    print_success "Backend unit tests passed"
    print_step "Running backend integration tests (coverage)..."
    if ! COVERAGE_FILE="$_VALIDATE_COV_DATA_DIR/.coverage.integration" \
        uv run pytest "$PROJECT_ROOT/backend/tests/integration" \
        --cov="$PROJECT_ROOT/backend" --cov-report= --cov-fail-under=0 \
        --ignore="$PROJECT_ROOT/backend/tests/load" --ignore="$PROJECT_ROOT/backend/tests/benchmarks" --ignore="$PROJECT_ROOT/backend/tests/e2e" --ignore="$PROJECT_ROOT/backend/tests/chaos" \
        --timeout=30 > /tmp/validate-backend-integration.log 2>&1; then
        print_error "Backend integration tests failed (full log: /tmp/validate-backend-integration.log)"
        tail -60 /tmp/validate-backend-integration.log
        rm -rf "$_VALIDATE_COV_DATA_DIR"
        echo ""
        echo "Fix failing tests, then re-run validation."
        exit 1
    fi
    print_success "Backend integration tests passed"
    print_step "Combining coverage (unit + integration) and checking the 80% gate..."
    uv run python -m coverage combine --data-file="$_VALIDATE_COV_DATA_DIR/.coverage" \
        "$_VALIDATE_COV_DATA_DIR/.coverage.unit" "$_VALIDATE_COV_DATA_DIR/.coverage.integration" >/dev/null
    if ! uv run python -m coverage report --data-file="$_VALIDATE_COV_DATA_DIR/.coverage" --fail-under=80 --show-missing > /tmp/validate-coverage-report.log 2>&1; then
        print_error "Combined unit+integration coverage below 80% (report: /tmp/validate-coverage-report.log)"
        tail -20 /tmp/validate-coverage-report.log
        rm -rf "$_VALIDATE_COV_DATA_DIR"
        echo ""
        echo "Fix failing tests, then re-run validation."
        exit 1
    fi
    tail -2 /tmp/validate-coverage-report.log
    rm -rf "$_VALIDATE_COV_DATA_DIR"
    print_success "Backend tests passed with sufficient coverage"

    # Optional: Run prompt evaluation (commented out by default)
    # Requires Nemotron service or uses mock mode
    # print_step "Running prompt evaluation (optional)..."
    # if ! uv run python -m backend.evaluation.harness --mock --output reports/evaluation.json; then
    #     print_warning "Prompt evaluation failed (not blocking validation)"
    # else
    #     print_success "Prompt evaluation completed"
    # fi
}

# ─────────────────────────────────────────────────────────────────────────────
# Frontend Validation
# ─────────────────────────────────────────────────────────────────────────────

run_frontend_validation() {
    print_header "Frontend Validation"

    FRONTEND_DIR="$PROJECT_ROOT/frontend"

    # Check Node.js
    print_step "Checking Node.js..."
    if ! check_command node; then
        print_error "Node.js not found"
        echo ""
        echo "Please install Node.js $REQUIRED_NODE_MAJOR+ (22.12+ accepted) from https://nodejs.org/"
        echo "Or use nvm: nvm install $REQUIRED_NODE_MAJOR && nvm use $REQUIRED_NODE_MAJOR"
        exit 1
    fi

    # CI runs Node $REQUIRED_NODE_MAJOR (Latest LTS); 22.12+ is accepted as a
    # maintenance-LTS floor (Vite 7 needs 20.19+/22.12+, and Node 20 is EOL).
    NODE_FULL_VERSION=$(node --version | sed 's/^v//')
    NODE_MAJOR=$(echo "$NODE_FULL_VERSION" | cut -d. -f1)
    NODE_MINOR=$(echo "$NODE_FULL_VERSION" | cut -d. -f2)
    if [ "$NODE_MAJOR" -lt "$REQUIRED_NODE_MAJOR" ]; then
        if [ "$NODE_MAJOR" -eq 22 ] && [ "$NODE_MINOR" -ge 12 ]; then
            print_warning "Node.js $(node --version) is older than CI's Node $REQUIRED_NODE_MAJOR — results may diverge from CI."
        else
            print_error "Node.js $REQUIRED_NODE_MAJOR+ (or 22.12+) required, found v$NODE_FULL_VERSION"
            echo ""
            echo "Please upgrade Node.js to version $REQUIRED_NODE_MAJOR+ (Latest LTS; Vite 7 floor is 22.12+)."
            exit 1
        fi
    fi
    print_success "Node.js $(node --version) found"

    # Check npm
    print_step "Checking npm..."
    if ! check_command npm; then
        print_error "npm not found"
        echo ""
        echo "npm should come with Node.js. Try reinstalling Node.js."
        exit 1
    fi
    print_success "npm $(npm --version) found"

    # Check for node_modules
    print_step "Checking frontend dependencies..."
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        print_error "Frontend dependencies not installed (node_modules missing)"
        echo ""
        echo "To fix this, run:"
        echo "  cd $FRONTEND_DIR && npm install"
        echo ""
        echo "Or run the setup script:"
        echo "  ./scripts/setup.sh"
        exit 1
    fi

    # Verify key packages are installed
    if [ ! -d "$FRONTEND_DIR/node_modules/eslint" ]; then
        print_warning "eslint not found in node_modules, may need to reinstall"
        echo "  cd $FRONTEND_DIR && npm install"
    fi

    if [ ! -d "$FRONTEND_DIR/node_modules/vitest" ]; then
        print_warning "vitest not found in node_modules, may need to reinstall"
        echo "  cd $FRONTEND_DIR && npm install"
    fi

    print_success "Frontend dependencies available"

    # Run ESLint
    print_step "Running ESLint..."
    if ! npm run lint --prefix "$FRONTEND_DIR"; then
        print_error "ESLint failed"
        echo ""
        echo "To auto-fix some issues, run:"
        echo "  cd $FRONTEND_DIR && npm run lint:fix"
        exit 1
    fi
    print_success "ESLint passed"

    # Run TypeScript type checking
    print_step "Running TypeScript type check..."
    if ! npm run typecheck --prefix "$FRONTEND_DIR"; then
        print_error "TypeScript type checking failed"
        echo ""
        echo "Fix the type errors shown above, then re-run validation."
        exit 1
    fi
    print_success "TypeScript type check passed"

    # Run Prettier check
    print_step "Running Prettier check..."
    # NOTE: Use the frontend npm script so Prettier loads plugins (e.g. prettier-plugin-tailwindcss)
    # from frontend/node_modules correctly. `npx --prefix` can fail to resolve plugins on some setups.
    if ! npm run format:check --prefix "$FRONTEND_DIR"; then
        print_error "Prettier check failed"
        echo ""
        echo "To auto-format, run:"
        echo "  cd $FRONTEND_DIR && npm run format"
        exit 1
    fi
    print_success "Prettier check passed"

    # Run tests
    print_step "Running Vitest (Tests)..."
    # Machine-aware test execution (fast-confidence-loop spec SS3.3): boxes with
    # >=64 GB RAM run files in parallel with a bigger heap; small boxes and CI
    # runners keep the inherited sequential + 8 GB settings byte-identically.
    # /proc/meminfo is Linux-only: its absence (macOS) falls to 0 -> sequential.
    MEM_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
    MEM_KB="${MEM_KB:-0}"
    if [ "${VITEST_PARALLEL:-}" != "0" ] && [ "$MEM_KB" -ge 67108864 ]; then
        export VITEST_PARALLEL=1
        export VITEST_MAX_WORKERS="${VITEST_MAX_WORKERS:-8}"
        export VITEST_HEAP_MB="${VITEST_HEAP_MB:-16384}"
        print_step "Parallel vitest: ${VITEST_MAX_WORKERS} workers, ${VITEST_HEAP_MB} MB heap (RAM $((MEM_KB / 1048576)) GB)"
    fi
    if ! VITEST_HEAP_MB="${VITEST_HEAP_MB:-8192}" npm run test --prefix "$FRONTEND_DIR" -- --run; then
        print_error "Frontend tests failed"
        echo ""
        echo "Fix failing tests, then re-run validation."
        exit 1
    fi
    print_success "Frontend tests passed"

    # Build and validate chunks for circular dependencies (NEM-3494)
    print_step "Building frontend and validating chunks..."
    if ! npm run build --prefix "$FRONTEND_DIR"; then
        print_error "Frontend build failed"
        exit 1
    fi
    print_success "Frontend build completed"

    print_step "Analyzing build chunks for circular dependencies..."
    if ! npm run validate:build-chunks --prefix "$FRONTEND_DIR"; then
        print_error "Build chunk validation failed - circular dependencies detected"
        echo ""
        echo "Review vite.config.ts rollupOptions.output.manualChunks configuration."
        exit 1
    fi
    print_success "Build chunk validation passed"

    # Note: Runtime E2E validation tests are available but not run by default
    # To run full build validation with Playwright (runtime TDZ detection):
    #   cd frontend && npx playwright test --config playwright.config.build-validation.ts
}

# ─────────────────────────────────────────────────────────────────────────────
# Fast Tier (change-scoped advisory gate - fast-confidence-loop spec SS4.1)
# ─────────────────────────────────────────────────────────────────────────────

# [M1 §6 GATE] This ENTIRE function is reachable only via the `--fast` case
# added to the arg parser above (RUN_FAST=true). With no --fast flag,
# RUN_FAST stays false and nothing here ever executes, so the default
# (no-flag / --backend / --frontend) path is unchanged — the M1 spec §9
# freeze on scripts/validate.sh behavior holds while M1's final no-flag
# validate.sh run is outstanding (the §6 "exit criteria" record). It may
# APPLY only once the M1 §6 record is in the ledger.

run_fast_validation() {
    # Base ref: default = merge-base with main (fallback origin/main on clones
    # without a local main; a bare `git merge-base HEAD main` dies there).
    _FCL_MAIN=$(git rev-parse --verify -q main || echo origin/main)
    VALIDATE_BASE="${VALIDATE_BASE:-$(git merge-base HEAD "$_FCL_MAIN")}"
    print_step "Fast tier: change set against ${VALIDATE_BASE}"

    SEL_LIST=$(mktemp)
    FE_LOG=$(mktemp)
    # One accumulated EXIT trap: POSIX sh replaces (does not stack) prior traps.
    trap 'rm -f "$SEL_LIST" "$FE_LOG"' EXIT

    print_step "Backend selection (import-truth selector)..."
    # `if ! VAR=$(...)` form: with set -e a bare VAR=$(cmd) propagates failure
    # at the assignment without letting us print context; and NO pipe here —
    # validate.sh is /bin/sh without pipefail, so `cmd | tee` would test tee's
    # status and mask the runner's verdict (the ci.yml retry-mask class).
    if ! BACKEND_OUT=$(uv run python "$SCRIPT_DIR/fast_select.py" \
        --base "$VALIDATE_BASE" --list-out "$SEL_LIST" ${VALIDATE_WHY:+--why}); then
        print_error "Backend selector (fast_select.py) failed"
        exit 1
    fi
    printf '%s\n' "$BACKEND_OUT"

    print_step "Backend: selected tests (no coverage, deterministic)..."
    if ! BACKEND_RUN=$(sh "$SCRIPT_DIR/fast-backend-runner.sh" "$SEL_LIST"); then
        printf '%s\n' "$BACKEND_RUN"
        print_error "Fast backend tests failed"
        exit 1
    fi
    printf '%s\n' "$BACKEND_RUN"

    print_step "Frontend: vitest related..."
    if ! FE_OUT=$(sh "$SCRIPT_DIR/fast-frontend-runner.sh" "$VALIDATE_BASE" 2>&1); then
        printf '%s\n' "$FE_OUT"
        print_error "Fast frontend tests failed"
        exit 1
    fi
    printf '%s\n' "$FE_OUT"
    printf '%s\n' "$FE_OUT" > "$FE_LOG"

    BE_N=$(printf '%s\n' "$BACKEND_OUT" "$BACKEND_RUN" \
        | sed -n 's/^SELECTED-BACKEND-FILES: //p' | tail -1)
    FE_N=$(sed -n 's/^SELECTED-FRONTEND-FILES: //p' "$FE_LOG" | tail -1)
    printf '\nSELECTED: %s files total (backend: %s via import-truth, frontend: %s via related, smoke: contracts-included-when-api-changed)\n' \
        "$(( ${BE_N:-0} + ${FE_N:-0} ))" "${BE_N:-0}" "${FE_N:-0}"
    printf '%s\n' "FAST TIER — no coverage proof; full gate still required before merge."
    # Deliberately NO "VALIDATION SUCCESSFUL" banner: that string belongs to
    # the full gate alone (spec SS4.1 output contract).
}

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

printf "${GREEN}Starting project validation...${NC}\n"
printf "Project root: ${CYAN}%s${NC}\n" "$PROJECT_ROOT"

cd "$PROJECT_ROOT"

# [M1 §6 GATE] Fast-tier dispatch. Reachable ONLY when --fast set
# RUN_FAST=true; the no-flag path never enters this branch, so the default
# behavior freeze (M1 spec §9, pending M1's §6 green record) is preserved.
if [ "$RUN_FAST" = true ]; then
    run_fast_validation
    exit 0   # fast tier never falls through to the full-gate banner
fi

if [ "$RUN_BACKEND" = true ]; then
    run_backend_validation
fi

if [ "$RUN_FRONTEND" = true ]; then
    run_frontend_validation
fi

echo ""
printf "${GREEN}============================================${NC}\n"
printf "${GREEN}  VALIDATION SUCCESSFUL: codebase is healthy!${NC}\n"
printf "${GREEN}============================================${NC}\n"

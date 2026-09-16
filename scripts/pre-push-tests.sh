#!/bin/bash
# Pre-push smoke test runner - FAST validation before push
# Full test suite runs in CI/CD, this is just a quick sanity check
#
# Strategy:
#   - API types contract check (~10s) - catches schema drift
#   - Backend smoke tests (~20s) - 10 critical path tests
#   - Frontend smoke tests (~15s) - component render tests
#   - Total: ~45 seconds max (with 60s timeout failsafe)
#
# Full validation: ./scripts/validate.sh (before PRs)
# Skip: SKIP=parallel-tests git push
# Force full tests: FULL_TESTS=1 git push

# WP0.1: pipefail is the fix for `if cmd | head -N`, which tested head's exit status
# and let jobs 2+3 report success unconditionally. Every other pipe in this script
# already carries `|| true`, so pipefail cannot break tolerated failures. Same
# pattern as ci.yml's vitest shards (ci.yml:1344-1352).
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if full tests requested
if [ "${FULL_TESTS:-0}" = "1" ]; then
    echo -e "${YELLOW}FULL_TESTS=1 detected - running complete test suite${NC}"
    exec "$SCRIPT_DIR/pre-push-tests-full.sh"
fi

# Temporary files for capturing exit codes
API_EXIT_FILE=$(mktemp)
BACKEND_EXIT_FILE=$(mktemp)
FRONTEND_EXIT_FILE=$(mktemp)
API_LOG=$(mktemp)
BACKEND_LOG=$(mktemp)
FRONTEND_LOG=$(mktemp)

# Cleanup on exit
cleanup() {
    rm -f "$API_EXIT_FILE" "$BACKEND_EXIT_FILE" "$FRONTEND_EXIT_FILE"
    rm -f "$API_LOG" "$BACKEND_LOG" "$FRONTEND_LOG"
}
trap cleanup EXIT

cd "$PROJECT_ROOT"

# Global failsafe: a hung runner must FAIL the push (exit 124), not hang it.
# WP0.1: the old form was a background `( sleep 60; … ) &` watcher, and it leaked:
# for `( … ) &` bash returns a transient WRAPPER pid in $!, the real subshell
# reparents to init almost immediately, and cleanup therefore can neither reap the
# sleep nor kill the watcher (measured: EVERY run left a `sleep 60` behind; when
# that sleep inherited the hook's stdout, git's output capture blocked 60s on EOF
# after the hook had already exited — every push paid the toll). A self-exec under
# `timeout` has no watcher, no sleep, and nothing to reap; on expiry there are no
# exit-code files, so even the legacy default-to-fail path agrees it is red.
# (Known limitation, unchanged from the old watcher: on real expiry the pytest/node
# grandchildren are orphaned to completion — the old pkill -P only reached the
# three job subshells too. Widening that is WP2.4's wiring job, not WP0.1's.)
if [ -z "${PREPUSH_TIMEOUT_ARMED:-}" ] && command -v timeout >/dev/null 2>&1; then
    export PREPUSH_TIMEOUT_ARMED=1
    exec timeout --kill-after=10s 60s "$SCRIPT_DIR/pre-push-tests.sh" "$@"
fi

trap cleanup EXIT

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}          FAST PRE-PUSH SMOKE TESTS (~45 seconds)              ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Full tests run in CI/CD. Use FULL_TESTS=1 for complete suite.${NC}"
echo ""

# Job 1: API types contract check (fast, catches schema drift)
(
    if "$PROJECT_ROOT/scripts/generate-types.sh" --check > "$API_LOG" 2>&1; then
        echo "0" > "$API_EXIT_FILE"
    else
        echo "1" > "$API_EXIT_FILE"
    fi
) &
API_PID=$!

# Job 2: Backend smoke tests - just critical path, no coverage
# WP0.1: the old `pytest ... | head -50` tested head's exit status, so a failing
# suite still wrote "0" to the exit file. The full output now goes to the log and
# the DISPLAYED tail is truncated separately — piping the runner into head also
# kills it via SIGPIPE once output exceeds the cap (head exits, pipefail reports
# 141 on a green run). The import-check fallback fires ONLY on pytest rc 5
# ("no tests collected") — a genuine test failure (rc 1) can never be excused
# by a passing `import backend.main` again.
(
    set +e   # verdicts are read explicitly via RC below
    redis-cli -n 15 FLUSHDB > /dev/null 2>&1 || true
    uv run pytest backend/tests/unit/api/ -q --tb=line -x \
        --ignore=backend/tests/unit/api/schemas/ \
        -k "test_health or test_root or test_cameras_list or test_events_list" \
        --timeout=30 -n 8 > "$BACKEND_LOG" 2>&1
    BE_RC=$?
    if [ "$BE_RC" -eq 5 ]; then
        echo "[pre-push] smoke selection collected no tests (pytest rc 5); falling back to import check" >> "$BACKEND_LOG"
        if uv run python -c "from backend.main import app; print('Backend imports OK')" >> "$BACKEND_LOG" 2>&1; then
            echo "0" > "$BACKEND_EXIT_FILE"
        else
            echo "1" > "$BACKEND_EXIT_FILE"
        fi
    elif [ "$BE_RC" -eq 0 ]; then
        echo "0" > "$BACKEND_EXIT_FILE"
    else
        echo "1" > "$BACKEND_EXIT_FILE"
    fi
) &
BACKEND_PID=$!

# Job 3: Frontend smoke tests - App render suite via vitest positional filter.
# WP0.1: the old call passed jest-only flags (--testPathPattern/--passWithNoTests)
# that vitest 4 rejects at CLI parse time — it exited non-zero WITHOUT running any
# test, every run fell into the tsc fallback, and a compile check pretended to be
# component smoke tests. (npm test already runs `vitest run`; --run here is
# belt-and-braces for a watch-mode hang.) tsc remains ONLY as the launch-failure
# fallback (npm rc 127); a real test failure can never be excused by tsc.
# The filter is an exact path because vitest 4 positionals are substring matchers:
# a regex arrives through npm mangled (`App\.(test|spec)` reaches vitest as the
# literal `App/.(test|spec)`) and silently selects zero files. If this file is
# ever renamed the smoke MUST fail loudly, not pass vacuously.
(
    set +e   # verdicts are read explicitly via RC below
    cd "$PROJECT_ROOT/frontend"
    npm test -- --run --reporter=dot src/App.test.tsx > "$FRONTEND_LOG" 2>&1
    FE_RC=$?
    if [ "$FE_RC" -eq 127 ]; then
        echo "[pre-push] vitest could not launch (npm rc 127); falling back to tsc" >> "$FRONTEND_LOG"
        if npx tsc --noEmit --skipLibCheck >> "$FRONTEND_LOG" 2>&1; then
            echo "0" > "$FRONTEND_EXIT_FILE"
        else
            echo "1" > "$FRONTEND_EXIT_FILE"
        fi
    elif [ "$FE_RC" -eq 0 ]; then
        echo "0" > "$FRONTEND_EXIT_FILE"
    else
        echo "1" > "$FRONTEND_EXIT_FILE"
    fi
) &
FRONTEND_PID=$!

# Show running jobs
echo -e "${YELLOW}Running 3 smoke tests in parallel:${NC}"
echo "  [1] API types contract check"
echo "  [2] Backend smoke tests (critical endpoints)"
echo "  [3] Frontend smoke tests (App renders)"
echo ""

# Wait for all jobs. No timeout bookkeeping anymore: the self-exec above runs the
# whole script under `timeout`, so a hung run dies 124 and the push is blocked.
# Missing exit-code files below default a job to FAILED (legacy safety net, now
# load-bearing for the case where the OOM killer takes a single job subshell).
wait $API_PID 2>/dev/null || true
wait $BACKEND_PID 2>/dev/null || true
wait $FRONTEND_PID 2>/dev/null || true

# Read exit codes
API_EXIT=$(cat "$API_EXIT_FILE" 2>/dev/null || echo "1")
BACKEND_EXIT=$(cat "$BACKEND_EXIT_FILE" 2>/dev/null || echo "1")
FRONTEND_EXIT=$(cat "$FRONTEND_EXIT_FILE" 2>/dev/null || echo "1")

# Report results
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# API types results
if [ "$API_EXIT" = "0" ]; then
    echo -e "${GREEN}✓ [1] API Types Contract: PASSED${NC}"
else
    echo -e "${RED}✗ [1] API Types Contract: FAILED${NC}"
fi

# Backend results
if [ "$BACKEND_EXIT" = "0" ]; then
    echo -e "${GREEN}✓ [2] Backend Smoke Tests: PASSED${NC}"
else
    echo -e "${RED}✗ [2] Backend Smoke Tests: FAILED${NC}"
fi

# Frontend results
if [ "$FRONTEND_EXIT" = "0" ]; then
    echo -e "${GREEN}✓ [3] Frontend Smoke Tests: PASSED${NC}"
else
    echo -e "${RED}✗ [3] Frontend Smoke Tests: FAILED${NC}"
fi

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"

# Show failure details if any
if [ "$API_EXIT" != "0" ]; then
    echo -e "${RED}API Types Failures:${NC}"
    cat "$API_LOG"
    echo ""
fi

if [ "$BACKEND_EXIT" != "0" ]; then
    echo -e "${RED}Backend Failures:${NC}"
    cat "$BACKEND_LOG"
    echo ""
fi

if [ "$FRONTEND_EXIT" != "0" ]; then
    echo -e "${RED}Frontend Failures:${NC}"
    cat "$FRONTEND_LOG"
    echo ""
fi

# Final result
if [ "$API_EXIT" = "0" ] && [ "$BACKEND_EXIT" = "0" ] && [ "$FRONTEND_EXIT" = "0" ]; then
    echo -e "${GREEN}✓ Smoke tests passed - CI/CD will run full suite${NC}"
    exit 0
else
    echo -e "${RED}✗ Smoke tests failed - fix before pushing${NC}"
    echo -e "${YELLOW}Run ./scripts/validate.sh for detailed errors${NC}"
    exit 1
fi

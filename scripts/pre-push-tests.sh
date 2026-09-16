#!/bin/bash
# Pre-push FAST-tier runner - WP2.4 wiring (plan: selection-driven, budgeted).
# Full test suite runs in CI/CD; this hook runs the SELECTED tier for the
# exact diff being pushed.
#
# Strategy:
#   - API types contract check (~10s) - catches schema drift (unchanged job)
#   - Backend: fast_select --base <remote sha> -> unit+contracts tier ->
#     fast-backend-runner.sh (WP2.3 manifest: not-selected vs cannot-run)
#   - Frontend: fast-frontend-runner.sh <remote sha> (vitest --related)
#   - Budget: FAST_PREPUSH_BUDGET seconds (default 900). MEASURED p50/p95 of
#     this wired shape lives in the ledger + the WP2.4 commit body: hub-diff
#     p95 ~513s, so 300 (plan target) RAISED to 900 = ~75% margin (owner
#     ruling 2026-09-16: tiered). MEGA diffs (hundreds of frontend/backend
#     files, e.g. the 978bb04c class) exceed any sane budget - they hit the
#     timeout and get a LOUD handoff notice naming the wide-diff cause; CI
#     remains the full-suite authority. Selection NEVER narrows to hit time:
#     the timeout bounds wall time only.
#
# Base resolution (what "this diff" means at push time), first hit wins:
#   1. PRE_COMMIT_FROM_REF — the live path under the real harness: pre-commit
#      consumes git's pre-push stdin itself (hook_impl.py:32) and spawns this
#      hook with stdin=/dev/null (util.py:178), so the stdin read below NEVER
#      fires when pre-commit drives the push. Pre-commit re-exports the true
#      range as PRE_COMMIT_FROM_REF/TO_REF (run.py:386-392) - use it.
#   2. pre-push stdin remote_sha for the pushed ref — only answers when git
#      runs this script directly (no pre-commit installed).
#   3. merge-base with @{upstream}, else origin/main. On the FIRST push of a
#      branch this is the origin/main merge-base: honest, wide, slow — the
#      trade recorded in the ledger WP2.4 row (budgets rise, selection never
#      narrows).
#   4. nothing usable (fresh clone, rewritten remote) -> LOUD NOTICE, fall
#      back to the legacy fixed-smoke jobs. Loud, never silently-empty.
#
# Full validation: ./scripts/validate.sh (before PRs)
# Skip: SKIP=parallel-tests git push   (forbidden by repo rule; documented only)
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
# WP2.4: budget is the plan's Phase-2 target (300s), env-overridable. The
# MEASURED p50/p95 of this wired shape (ledger, WP2.4 commit) is what decides
# whether 300 stands; if measurement says raise, the budget RAISES — the
# timeout only ever bounds wall time, selection never narrows to fit it.
FAST_PREPUSH_BUDGET="${FAST_PREPUSH_BUDGET:-900}"
case "$FAST_PREPUSH_BUDGET" in
    ''|*[!0-9]*)
        # f7 (review 2026-09-16): FAST_PREPUSH_BUDGET=5m/typo made timeout die
        # rc 125 and brick EVERY push with a message nobody could attribute to
        # this hook. Digits-only or default loudly; never a mystery 125.
        echo -e "${YELLOW}NOTICE: FAST_PREPUSH_BUDGET='$FAST_PREPUSH_BUDGET' is not a plain${NC}"
        echo -e "${YELLOW}integer of seconds — using 900. Set e.g. FAST_PREPUSH_BUDGET=600.${NC}"
        FAST_PREPUSH_BUDGET=900
        ;;
esac
if [ -z "${PREPUSH_TIMEOUT_ARMED:-}" ] && command -v timeout >/dev/null 2>&1; then
    export PREPUSH_TIMEOUT_ARMED=1
    # Owner ruling 2026-09-16 (tiered budget): expiry must be an ATTRIBUTABLE
    # handoff, not a bare rc-124. bash -c wraps the timeout so the notice can
    # print AFTER the kill (a plain exec past this point prints nothing);
    # stdin passes through untouched for the inner instance's base resolution.
    exec bash -c '
        timeout --kill-after=10s "${1}s" "$2" "${@:3}"
        RC=$?
        if [ "$RC" -eq 124 ]; then
            echo "NOTICE: the fast tier hit its ${1}s budget — push blocked." >&2
            echo "If the selection scope above was huge, this is a MEGA diff the fast" >&2
            echo "tier cannot certify in budget (the recorded trade: budgets bound" >&2
            echo "wall time; selection NEVER narrows). Options: split the push, raise" >&2
            echo "FAST_PREPUSH_BUDGET for this push, or FULL_TESTS=1 git push." >&2
        fi
        exit "$RC"' pre-push-budget "$FAST_PREPUSH_BUDGET" "$SCRIPT_DIR/pre-push-tests.sh" "$@"
fi

# f1 (review 2026-09-16): the six temps used to be created ABOVE the self-exec,
# and `exec` replaces the process image WITHOUT running the EXIT trap (verified
# on bash 5.3.9: /tmp probe leaked on every shape) — six leaked files per push,
# forever. They now live in one directory created AFTER the exec: the outer
# instance creates nothing, the inner instance owns everything, cleanup has one
# target, and SEL_LIST (job 2's f6a leak) joins the same sweep.
TMPD=$(mktemp -d "${TMPDIR:-/tmp}/prepush-tier.XXXXXX")
API_EXIT_FILE="$TMPD/api.exit"
BACKEND_EXIT_FILE="$TMPD/backend.exit"
FRONTEND_EXIT_FILE="$TMPD/frontend.exit"
API_LOG="$TMPD/api.log"
BACKEND_LOG="$TMPD/backend.log"
FRONTEND_LOG="$TMPD/frontend.log"
cleanup() {
    rm -rf "$TMPD"
}
trap cleanup EXIT

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}      FAST PRE-PUSH TIER — selected for THIS diff (budget ${FAST_PREPUSH_BUDGET}s)${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}Full tests run in CI/CD. Use FULL_TESTS=1 for complete suite.${NC}"
echo ""

# --- WP2.4 base resolution: read pre-push stdin BEFORE any job forks it. ---
# Lines are: local_ref local_sha remote_ref remote_sha. Our pushed sha is
# local_sha; the BASE is remote_sha (what the remote already has).
FAST_TIER_BASE=""
LEGACY_SMOKE=""
if [ ! -t 0 ]; then
    read -r PP_LOCAL_REF PP_LOCAL_SHA PP_REMOTE_REF PP_REMOTE_SHA </dev/stdin 2>/dev/null || true
fi
ZERO40=0000000000000000000000000000000000000000
if [ -n "${PRE_COMMIT_FROM_REF:-}" ] \
   && [ "$PRE_COMMIT_FROM_REF" != "$ZERO40" ] \
   && git cat-file -e "${PRE_COMMIT_FROM_REF}^{commit}" 2>/dev/null; then
    # THE live path under pre-commit (see header): it re-exports git's real
    # pre-push range (run.py:386-392). New-branch pushes carry Z40 here and
    # fall through to merge-base, exactly as intended.
    FAST_TIER_BASE="$PRE_COMMIT_FROM_REF"
elif [ -n "${PP_REMOTE_SHA:-}" ] && [ "$PP_REMOTE_SHA" != "$ZERO40" ] \
   && git cat-file -e "${PP_REMOTE_SHA}^{commit}" 2>/dev/null; then
    FAST_TIER_BASE="$PP_REMOTE_SHA"
elif mb=$(git merge-base @{upstream} HEAD 2>/dev/null || git merge-base origin/main HEAD 2>/dev/null); then
    FAST_TIER_BASE="$mb"
else
    LEGACY_SMOKE=1
    echo -e "${YELLOW}NOTICE: no usable diff base (fresh clone / rewritten remote).${NC}"
    echo -e "${YELLOW}Falling back to the LEGACY fixed-smoke jobs for this push only —${NC}"
    echo -e "${YELLOW}the selected tier needs a reachable base. Force-full: FULL_TESTS=1 git push${NC}"
fi
export FAST_TIER_BASE

# f3 honesty (review 2026-09-16): the tier tests the WORKING TREE — both the
# selector diff and the pytest run read the tree, and pre-commit force-sets
# it to the index for the hook's duration (run.py:344). If the index holds
# staged-but-uncommitted edits, the tree being certified is AHEAD of what
# this push ships (HEAD): a red commit hidden by an uncommitted fix. Loud
# notice; CI remains the authority on the pushed tree.
if ! git diff --cached --quiet 2>/dev/null; then
    echo -e "${YELLOW}NOTICE: staged-but-uncommitted changes exist — the fast tier tested the${NC}"
    echo -e "${YELLOW}working tree, which is NOT exactly the tree this push ships (HEAD). Commit${NC}"
    echo -e "${YELLOW}or unstage them for an honest local verdict.${NC}"
fi

# Job 2: SELECTED backend tier. fast_select answers for the real base, the
# tier filter keeps integration OUT (it has its own -n0 gate; tier identity,
# printed OUT-OF-TIER-EXCLUDED count — this is tier definition, never
# narrowing to hit a clock), and fast-backend-runner enforces the WP2.3
# manifest contract. Empty selection is GREEN WITH ITS MANIFEST.
(
    set +e   # verdicts are read explicitly via RC below
    redis-cli -n 15 FLUSHDB > /dev/null 2>&1 || true
    if [ -n "$LEGACY_SMOKE" ]; then
        # Loud fallback path (WP2.4 base resolution step 4): pre-WP2.4 smoke.
        uv run pytest backend/tests/unit/api/ -q --tb=line -x \
            --ignore=backend/tests/unit/api/schemas/ \
            -k "test_health or test_root or test_cameras_list or test_events_list" \
            --timeout=30 -n 8 > "$BACKEND_LOG" 2>&1
        [ "$?" -eq 0 ] && echo "0" > "$BACKEND_EXIT_FILE" || echo "1" > "$BACKEND_EXIT_FILE"
    else
        SEL_LIST="$TMPD/sel.txt"
        uv run python scripts/fast_select.py --base "$FAST_TIER_BASE" \
            --list-out "$SEL_LIST" > "$BACKEND_LOG" 2>&1
        FS_RC=$?
        # Tier filter: unit + contracts + UNMARKED top-level test files (f4,
        # review 2026-09-16: fast_select's changed-test self-selection would
        # otherwise be silently dropped for backend/tests/test_utils.py —
        # a gate that won't run the tests the diff rewrote breaks the tier's
        # own promise; those files carry no tier marker, so they are unit-like).
        # integration/security/chaos stay out by tier definition — they have
        # their own -n0 gate. Dropped files are COUNTED and named below, and
        # the count prints on green runs too (WP2.3: named, never silence).
        grep -E '^backend/tests/(unit|contracts)/|^backend/tests/test_[^/]*\.py$' \
            "$SEL_LIST" > "${SEL_LIST}.tier" 2>/dev/null
        OOT=$(( $(wc -l < "$SEL_LIST" 2>/dev/null || echo 0) - $(wc -l < "${SEL_LIST}.tier") ))
        echo "OUT-OF-TIER-EXCLUDED: $OOT (integration has its own -n0 gate)" >> "$BACKEND_LOG"
        comm -23 <(sort "$SEL_LIST") <(sort "${SEL_LIST}.tier") \
            | head -20 | sed 's/^/OUT-OF-TIER-FILE: /' >> "$BACKEND_LOG" || true
        if [ "$FS_RC" -ne 0 ]; then
            echo "MANIFEST CANNOT-RUN: fast_select failed rc=$FS_RC (git base?)" >> "$BACKEND_LOG"
            echo "1" > "$BACKEND_EXIT_FILE"
        elif [ -s "${SEL_LIST}.tier" ]; then
            sh scripts/fast-backend-runner.sh "${SEL_LIST}.tier" >> "$BACKEND_LOG" 2>&1
            [ "$?" -eq 0 ] && echo "0" > "$BACKEND_EXIT_FILE" || echo "1" > "$BACKEND_EXIT_FILE"
        else
            # Empty in-tier selection: green, but SAY SO with the manifest
            # lines fast_select already printed (NOT-SELECTED-FILE proof the
            # tier ran and honestly found nothing).
            echo "0" > "$BACKEND_EXIT_FILE"
        fi
        rm -f "$SEL_LIST" "${SEL_LIST}.tier"
    fi
) &
BACKEND_PID=$!

# Job 3: SELECTED frontend tier — vitest --related against the same base
# (WP2.3 manifest contract inside the runner). A backend-only commit is
# legitimately ZERO-RELATED green; that is the runner's named category,
# not a vacuous pass.
(
    set +e   # verdicts are read explicitly via RC below
    if [ -n "$LEGACY_SMOKE" ]; then
        cd "$PROJECT_ROOT/frontend"
        npm test -- --run --reporter=dot src/App.test.tsx > "$FRONTEND_LOG" 2>&1
        [ "$?" -eq 0 ] && echo "0" > "$FRONTEND_EXIT_FILE" || echo "1" > "$FRONTEND_EXIT_FILE"
    else
        sh scripts/fast-frontend-runner.sh "$FAST_TIER_BASE" > "$FRONTEND_LOG" 2>&1
        [ "$?" -eq 0 ] && echo "0" > "$FRONTEND_EXIT_FILE" || echo "1" > "$FRONTEND_EXIT_FILE"
    fi
) &
FRONTEND_PID=$!

# Show running jobs
echo -e "${YELLOW}Running 3 jobs in parallel:${NC}"
echo "  [1] API types contract check"
echo "  [2] Backend SELECTED tier (unit+contracts for this diff)"
echo "  [3] Frontend SELECTED tier (vitest --related for this diff)"
(
    if "$PROJECT_ROOT/scripts/generate-types.sh" --check > "$API_LOG" 2>&1; then
        echo "0" > "$API_EXIT_FILE"
    else
        echo "1" > "$API_EXIT_FILE"
    fi
) &
API_PID=$!

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
    echo -e "${GREEN}✓ [2] Backend Selected Tier: PASSED${NC}"
else
    echo -e "${RED}✗ [2] Backend Selected Tier: FAILED${NC}"
fi

# Frontend results
if [ "$FRONTEND_EXIT" = "0" ]; then
    echo -e "${GREEN}✓ [3] Frontend Selected Tier: PASSED${NC}"
else
    echo -e "${RED}✗ [3] Frontend Selected Tier: FAILED${NC}"
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

# f4 (review 2026-09-16): the WP2.3 manifest contract is "named, never
# silence" on EVERY run, green included — surface the out-of-tier count even
# when everything passed (it lives in the log, which the failure branch prints
# and this branch would otherwise swallow).
OOT_GREEN=$(grep -m1 '^OUT-OF-TIER-EXCLUDED:' "$BACKEND_LOG" 2>/dev/null || true)
[ -n "$OOT_GREEN" ] && echo -e "${YELLOW}▸ $OOT_GREEN — files above print with names on failure${NC}"

# Final result
if [ "$API_EXIT" = "0" ] && [ "$BACKEND_EXIT" = "0" ] && [ "$FRONTEND_EXIT" = "0" ]; then
    echo -e "${GREEN}✓ Fast tier passed - CI/CD will run full suite${NC}"
    exit 0
else
    echo -e "${RED}✗ Fast tier failed - fix before pushing${NC}"
    echo -e "${YELLOW}Run ./scripts/validate.sh for detailed errors${NC}"
    exit 1
fi

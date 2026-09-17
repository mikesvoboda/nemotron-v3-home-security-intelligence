#!/bin/sh
# Spec 6.3 verification playbook: 5 scripted small changes, each timed against
# the fast tier, with per-change wall assertions. Each case: append a comment
# line (behavior-neutral), run the applicable runner, record seconds, revert.
# Usage: scripts/fast-validation-playbook.sh [BASE_REF]
#        (default: merge-base HEAD main, or origin/main when no local main —
#         same fallback T13's base-ref default uses; this repo has NO local
#         main branch: only remotes/origin/main exists at landing time)
# Exit: 0 every case within the wall AND every selection assertion holds;
#       1 on breach or failed assertion; 2 setup failure.
#
# WP2.5: seven TRANSITIVE cases were added (5 original + 7 = 12 total) and
# the wall was retargeted from the 600s plan-era guess to the WP2.4 MEASURED
# figure. Wall time alone cannot tell a closure from a full run, so cases 6+
# additionally assert WHICH files the selector put in its list (REQUIRED /
# FORBIDDEN / exact TOTAL) — a case whose selection is not what the closure
# mechanism promises is a failure even when it runs fast.
#
# [RECONCILIATION - loud] Plan Task 12 Step 1's listing invoked
# `sh "$RUNNER" "$BASE"` uniformly, then its own GOTCHA text corrects the
# backend side: fast-backend-runner.sh takes a LISTFILE, not a BASE (Task 10's
# contract), so selection must be generated first via fast_select.py. This file
# ships the CORRECTED shape the plan mandates: the third parameter is a
# command string executed through `sh -c`. fast_select.py's SELECTED-BACKEND-
# FILES stdout line is NOT suppressed (the plan draft's >/dev/null would hide
# the very selection table spec 6.3 requires); it is teed to the per-case log
# and counted from there.
set -eu
cd "$(git rev-parse --show-toplevel)"
if [ "$#" -ge 1 ]; then
    BASE="$1"
elif git rev-parse --verify -q main >/dev/null 2>&1; then
    BASE=$(git merge-base HEAD main)
else
    BASE=$(git merge-base HEAD origin/main)
fi
# WP2.5 retarget 600 -> 900: WP2.4 measured the wired fast tier at p50 428s /
# p95 513s (n=20, ledger WP2.4 row) and the owner ruling set FAST_PREPUSH_BUDGET
# to 900s. The playbook certifies the same tier the pre-push hook ships, so it
# shares that budget exactly; the 600s spec-era guess predates any measurement.
# Selection NEVER narrows to fit the wall — the wall only bounds it.
WALL_LIMIT_S=900

# Setup guard FIRST — before any revert-capable trap is armed: a dirty tracked
# tree would have its (user's) edits reverted by the EXIT trap's
# `git checkout -- .` and would pollute selection. Exit 2 here runs with no
# destructive trap installed.
if ! git diff --quiet HEAD --; then
    echo "[SETUP-FAIL] tracked tree is dirty; playbook reverts files on exit — refusing to run" >&2
    exit 2
fi

LOGDIR="${TMPDIR:-/tmp}/fcl-playbook.$$"
mkdir -p "$LOGDIR"
RESULTS=$(mktemp)
trap 'rm -f "$RESULTS"; rm -rf "$LOGDIR"; git checkout -- . 2>/dev/null || true' EXIT

probe_line() {
    # [RECONCILIATION - loud] Run 1 (2026-09-14) exposed the plan listing's
    # C-style probe comment as Python-invalid: `/* ... */` appended to
    # alerts.py SyntaxErrors every importing test (114 files' collection died
    # in 4.65s, rc=123 from xargs). Extension-dependent comment now.
    case "$1" in
        *.py) printf '\n# fcl playbook probe\n' ;;
        *)    printf '\n/* fcl playbook probe */\n' ;;
    esac
}

run_case() {
    # WP2.5 selection assertions: wall time alone cannot tell a closure
    # selection from an accidental full run, so backend cases may additionally
    # pin WHICH files the selector put in its list. Assertions read the raw
    # selector list-out (sel.txt, un-tier-filtered) — not the tier-filtered
    # run list — so integration-tier proofs (x2, x4) assert cleanly while the
    # RUN stays in-tier (pre-push's contract). A frontend case declaring one
    # is a wiring mistake: ASSERT=no-sel-file makes that loud, never skipped.
    #   $4 REQUIRED  space-separated exact paths, each must be selected
    #   $5 FORBIDDEN space-separated prefixes, none may be selected
    #   $6 TOTAL     exact raw selection count (T3: self-select is exactly 1)
    NAME="$1"; FILE="$2"; RUNNER="$3"; REQUIRED="${4:-}"; FORBIDDEN="${5:-}"; TOTAL="${6:-}"
    # NAME is PATH-INVARIANT ONLY AFTER tr: it feeds a log PATH, so a slash
    # in a case name makes the redirect target a nonexistent directory and
    # dash dies rc=2 WITHOUT RUNNING THE RUNNER (no log file at all — zero
    # signal). Run 2 proof: "x4-depth2(schemas/queue)" ->
    # `cannot create .../x4-depth2(schemas/queue).log: Directory nonexistent`;
    # the identical Run 1 death I misread as a pkill artifact; and the
    # rc-blind Run 1 verdict printed that non-run as "OK" (the verdict fold
    # now prints FAILED-rc2). The human table keeps NAME; the log gets SAFE.
    SAFE=$(printf '%s' "$NAME" | tr / _)
    # per-case sel.txt: without this wipe, a frontend case (whose runner
    # writes no sel.txt) declaring an assertion would silently grade against
    # the PREVIOUS backend case's list — stale file, false verdict.
    rm -f "$LOGDIR/sel.txt" "$LOGDIR/sel.tier"
    START=$(date +%s)
    # SC2094 false positive: probe_line reads only the NAME string, not the
    # file's contents — nothing reads while appending.
    # shellcheck disable=SC2094
    probe_line "$FILE" >> "$FILE"
    # shellcheck disable=SC2086
    if sh -c "$RUNNER" > "$LOGDIR/$SAFE.log" 2>&1; then RC=0; else RC=$?; fi
    # revert this probe before timing bookkeeping so the next case sees a clean tree
    git checkout -- "$FILE"
    END=$(date +%s); DUR=$((END - START))
    SEL=$(grep -hE 'SELECTED-(BACKEND|FRONTEND)-FILES:' "$LOGDIR/$SAFE.log" | tail -1)
    ASSERT=none
    if [ -n "$REQUIRED$FORBIDDEN$TOTAL" ]; then
        ASSERT=ok
        if [ -f "$LOGDIR/sel.txt" ]; then
            for f in $REQUIRED; do
                if ! grep -qxF "$f" "$LOGDIR/sel.txt"; then ASSERT="missing:$f"; break; fi
            done
            if [ "$ASSERT" = ok ]; then
                for p in $FORBIDDEN; do
                    if grep -qF "$p" "$LOGDIR/sel.txt"; then ASSERT="forbidden:$p"; break; fi
                done
            fi
            if [ "$ASSERT" = ok ] && [ -n "$TOTAL" ]; then
                if [ "$(grep -c . "$LOGDIR/sel.txt")" != "$TOTAL" ]; then ASSERT="total:want-$TOTAL"; fi
            fi
        else
            ASSERT=no-sel-file
        fi
    fi
    # rc rides the verdict: a case whose selected tier FAILED is not OK no
    # matter how fast or well-selected it was (Run 1 proof: route(alerts)
    # printed 78s/OK while rc=1 — the manifest CANNOT-RUN that exposed the
    # schemathesis stub rode exactly this blind spot in my first draft).
    VERDICT=OK
    [ "$RC" -eq 0 ] || VERDICT="FAILED-rc$RC"
    [ "$DUR" -le "$WALL_LIMIT_S" ] || VERDICT="$VERDICT/OVER-WALL"
    [ "$ASSERT" = ok ] || [ "$ASSERT" = none ] || VERDICT="$VERDICT/assert:$ASSERT"
    printf '%-28s %6ss rc=%s %-40s %s\n' "$NAME" "$DUR" "$RC" \
        "${SEL:-no-selection-line}" "$VERDICT" | tee -a "$RESULTS"
    [ "$VERDICT" = OK ]
}

# SC2016 deliberate: single quotes are the DEFERRED-expansion mechanism —
# "$BASE"/"$LOGDIR" resolve inside `sh -c "$RUNNER"`, not at assignment.
# WP2.5: the RUN list is the WP2.4 f4 tier filter applied to the selection
# (same grep as scripts/pre-push-tests.sh job 2) — the playbook certifies the
# tier the hook ships. The selector's raw list-out stays UNFILTERED as
# $LOGDIR/sel.txt: selection assertions are about what fast_select CHOSE, and
# integration-tier proofs (x2/x4) live in that raw list by design; the filter
# is what keeps their RUN in-tier (serial -n0 integration is never this
# tier's — running 191 integration files here would blow the wall for the
# wrong reason). `&&` before grep keeps SELECTOR DEATH loud (rc = fast_select's);
# `|| true` after grep tolerates ONLY the no-match case — an empty in-tier list
# is pre-push's empty-tier contract (green-with-manifest), and the runner reads
# a real file ([ -s ] is false for a pipe, so /dev/stdin would silently empty
# every run).
# shellcheck disable=SC2016
BACKEND_CMD='uv run python scripts/fast_select.py --base "$BASE" --list-out "$LOGDIR/sel.txt" && { grep -E "^backend/tests/(unit|contracts)/|^backend/tests/test_[^/]*\.py$" "$LOGDIR/sel.txt" > "$LOGDIR/sel.tier" || true; } && sh scripts/fast-backend-runner.sh "$LOGDIR/sel.tier"'
# shellcheck disable=SC2016
FRONTEND_CMD='sh scripts/fast-frontend-runner.sh "$BASE"'
export BASE LOGDIR

# WP0-era baseline cases (assertion-free: their proof is the wall + guard
# behavior; sel.txt assertions start at x1). probe files reverted between cases,
# so each sees a one-file diff against BASE.
run_case "route(alerts)"              backend/api/routes/alerts.py               "$BACKEND_CMD"   || OVERALL=1
run_case "service(alert_service)"     backend/services/alert_service.py          "$BACKEND_CMD"   || OVERALL=1
run_case "component(ActionableInsig)" frontend/src/components/dashboard/ActionableInsights.tsx "$FRONTEND_CMD" || OVERALL=1
run_case "hook(useAlertsQuery)"       frontend/src/hooks/useAlertsQuery.ts       "$FRONTEND_CMD"  || OVERALL=1
# config case EXPECTS the guard notice (positional config trips
# forceRerunTriggers -> runner reports the full-suite guard, spec Tier-0
# fallback + notice); only the wall bound is asserted:
run_case "config(vite.config)"        frontend/vite.config.ts                    "$FRONTEND_CMD"  || OVERALL=1

# WP2.5 TRANSITIVE cases (plan: >=3; shipped 7). Every REQUIRED/FORBIDDEN/TOTAL
# below was probe-verified against the shipped selector at 515a4810 with a
# one-file diff (method: append one behavior-neutral comment, fast_select
# --base HEAD, read why-lines; /tmp/wp25/verified-cases.md carries the evidence).
# The shipped CLI has no --closure-depth flag (depth=4 hardcoded at the
# closure() call-site), so the closure is pinned by ASSERTING the selection the
# depth-annotated why-lines produced, never by a flag.

# x1: untouched-intermediate closure — test_alerts.py does NOT import
# event_broadcaster; it rides the route that does ("transitive (depth 1):
# backend.api.routes.alerts imports backend.services.event_broadcaster").
# [RECONCILIATION - loud] the plan-era draft probed services/alert_service.py
# for THIS claim; that file's only hop to test_alerts.py is the routes-package
# __init__ hub — it would pass for the wrong reason, so the drafted probe is
# kept, but as x1b labelled for what it actually proves.
run_case "x1-intm(event_broadcaster)" backend/services/event_broadcaster.py "$BACKEND_CMD" \
    "backend/tests/unit/api/routes/test_alerts.py" || OVERALL=1
# x1b: package-hub transitive — depth 2 via routes/__init__.py's re-export
# ("transitive (depth 2): backend.api.routes imports backend.services.alert_service").
run_case "x1b-pkghub(alert_service)"  backend/services/alert_service.py "$BACKEND_CMD" \
    "backend/tests/unit/api/routes/test_alerts.py" || OVERALL=1
# x2: package RE-EXPORT — test_alert_repository.py references bare
# backend.models + the repository module ONLY; it reaches models.alert solely
# through models/__init__.py's re-export ("transitive (depth 1): backend.models
# imports backend.models.alert"). REQUIRED file is INTEGRATION tier: asserted on
# the raw selection, EXCLUDED from the in-tier run by the f4 filter by design —
# do not "fix" this into the tier; that is WP2.4's contract, not a bug here.
run_case "x2-reexport(models/alert)"  backend/models/alert.py "$BACKEND_CMD" \
    "backend/tests/integration/repositories/test_alert_repository.py" || OVERALL=1
# x3: changed-TEST self-selection — probing a test file must select EXACTLY
# that file, one, via "changed test file" (bake-off 18984662 class). TOTAL=1
# is the assertion; a closure that fans out from a test edit is a defect.
run_case "x3-selfselect(test_alerts)" backend/tests/unit/api/routes/test_alerts.py "$BACKEND_CMD" \
    "backend/tests/unit/api/routes/test_alerts.py" "" 1 || OVERALL=1
# x4: real depth-2 CHAIN through two untouched intermediates —
# schemas/queue <- services/pipeline_workers.py:44 <- api/routes/system.py:749
# <- test refs routes.system ("transitive (depth 2): backend.api.routes.system
# imports backend.api.schemas.queue"). Integration-tier REQUIRED, same
# assert-on-selection note as x2. A "narrower" alternative (schemas/jobs) was
# probe-rejected: test_jobs.py references schemas.jobs DIRECTLY — a depth-0
# case masquerading as the chain proof.
run_case "x4-depth2(schemas/queue)"   backend/api/schemas/queue.py "$BACKEND_CMD" \
    "backend/tests/integration/test_api_error_scenarios.py" || OVERALL=1
# x5: FIXTURE-INDIRECT conftest hop — test_rum.py has ZERO production refs;
# its only edge is backend.tests.unit.conftest, whose authenticated_async_client
# fixture does `from backend.main import app` (unit/conftest.py:136). Probing
# main.py must reach it ("transitive (depth 1): backend.tests.unit.conftest
# imports backend.main"). Bake-off 15d7b5a2 fault class. Selection tight (68).
run_case "x5-fixtureind(main.py)"     backend/main.py "$BACKEND_CMD" \
    "backend/tests/unit/api/routes/test_rum.py" || OVERALL=1
# x6: conftest-TREE scoping — the rule is not graph-derivable (conftest is
# neither seed nor test). Probing unit/conftest.py must select the UNIT tree
# and NOTHING from contracts/ or integration/ (674 files, verified 0/0).
run_case "x6-conftest-tree"           backend/tests/unit/conftest.py "$BACKEND_CMD" \
    "backend/tests/unit/api/middleware/test_accept_header.py" \
    "backend/tests/contracts/ backend/tests/integration/" || OVERALL=1

echo "--- playbook summary ---"; cat "$RESULTS"
exit "${OVERALL:-0}"

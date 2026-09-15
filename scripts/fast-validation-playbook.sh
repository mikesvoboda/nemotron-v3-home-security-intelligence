#!/bin/sh
# Spec 6.3 verification playbook: 5 scripted small changes, each timed against
# the fast tier, with per-change wall assertions. Each case: append a comment
# line (behavior-neutral), run the applicable runner, record seconds, revert.
# Usage: scripts/fast-validation-playbook.sh [BASE_REF]
#        (default: merge-base HEAD main, or origin/main when no local main —
#         same fallback T13's base-ref default uses; this repo has NO local
#         main branch: only remotes/origin/main exists at landing time)
# Exit: 0 all five within the 10-minute wall; 1 on breach; 2 setup failure.
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
WALL_LIMIT_S=600

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
    NAME="$1"; FILE="$2"; RUNNER="$3"
    START=$(date +%s)
    # SC2094 false positive: probe_line reads only the NAME string, not the
    # file's contents — nothing reads while appending.
    # shellcheck disable=SC2094
    probe_line "$FILE" >> "$FILE"
    # shellcheck disable=SC2086
    if sh -c "$RUNNER" > "$LOGDIR/$NAME.log" 2>&1; then RC=0; else RC=$?; fi
    # revert this probe before timing bookkeeping so the next case sees a clean tree
    git checkout -- "$FILE"
    END=$(date +%s); DUR=$((END - START))
    SEL=$(grep -hE 'SELECTED-(BACKEND|FRONTEND)-FILES:' "$LOGDIR/$NAME.log" | tail -1)
    printf '%-28s %6ss rc=%s %-40s %s\n' "$NAME" "$DUR" "$RC" \
        "${SEL:-no-selection-line}" \
        "$([ "$DUR" -le "$WALL_LIMIT_S" ] && echo OK || echo OVER-WALL)" | tee -a "$RESULTS"
    [ "$DUR" -le "$WALL_LIMIT_S" ]
}

# SC2016 deliberate: single quotes are the DEFERRED-expansion mechanism —
# "$BASE"/"$LOGDIR" resolve inside `sh -c "$RUNNER"`, not at assignment.
# shellcheck disable=SC2016
BACKEND_CMD='uv run python scripts/fast_select.py --base "$BASE" --list-out "$LOGDIR/sel.txt" && sh scripts/fast-backend-runner.sh "$LOGDIR/sel.txt"'
# shellcheck disable=SC2016
FRONTEND_CMD='sh scripts/fast-frontend-runner.sh "$BASE"'
export BASE LOGDIR

run_case "route(alerts)"              backend/api/routes/alerts.py               "$BACKEND_CMD"   || OVERALL=1
run_case "service(alert_service)"     backend/services/alert_service.py          "$BACKEND_CMD"   || OVERALL=1
run_case "component(ActionableInsig)" frontend/src/components/dashboard/ActionableInsights.tsx "$FRONTEND_CMD" || OVERALL=1
run_case "hook(useAlertsQuery)"       frontend/src/hooks/useAlertsQuery.ts       "$FRONTEND_CMD"  || OVERALL=1
# config case EXPECTS the guard notice (positional config trips
# forceRerunTriggers -> runner reports the full-suite guard, spec Tier-0
# fallback + notice); only the wall bound is asserted:
run_case "config(vite.config)"        frontend/vite.config.ts                    "$FRONTEND_CMD"  || OVERALL=1

echo "--- playbook summary ---"; cat "$RESULTS"
exit "${OVERALL:-0}"

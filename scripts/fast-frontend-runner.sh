#!/bin/sh
# Fast-tier frontend selection (spec 4.1): vitest's own import-graph selector.
# Guards encoded from the vitest 4.0.18 source sweep (plan Task 11):
#  - related + --run is mandatory (without --run it is WATCH MODE on a TTY).
#  - a zero-selection related run exits 0 (passWithNoTests is forced) - the
#    SELECTED-FRONTEND-FILES count line below is what distinguishes 'nothing
#    affected' from 'all green'; exit code alone cannot tell them apart.
#  - positional config/package.json files trip forceRerunTriggers and silently
#    select the FULL suite (Tier 0 territory) - excluded from the arg list
#    here and reported as a notice instead ("run the full gate").
#  - direct npx bypasses the package.json "test" script's NODE_OPTIONS heap
#    wrapper - replicated below (8 GB floor, VITEST_HEAP_MB override; matches
#    the npm-script wrapper the t3-draft package.json makes env-driven).
# Unquoted $SELECTABLE/$CONFIGY word-splitting is deliberate-POSIX (repo file
# names contain no spaces - verified: git ls-files frontend/src | grep ' ' is
# empty); shellcheck SC2086 disables at each site record the intent.
# shellcheck disable=SC2086
# related follows the full transitive import graph, so a shared-module edit
# selecting most of the suite is honest behavior, not a bug (the count line
# tells the developer why today's --fast wasn't fast).
#
# WP2.3 MANIFEST CONTRACT (spec §Phase 2, "non-negotiable") — same categories
# as fast-backend-runner.sh, same names, emitted on EVERY exit path:
#   MANIFEST NOT-SELECTED   "not selected for this diff" — NORMAL, visible
#   MANIFEST ZERO-RELATED   green run that ran 0 test files (vitest
#                           semantics) — named, never silence
#   MANIFEST CANNOT-RUN     vitest exited non-zero WITHOUT ever printing its
#                           'Test Files' summary: a crash/uncollectable file,
#                           not a failing test. Forces non-zero.
# A run that printed the summary keeps vitest's own exit (a failing test is a
# FAILURE under its own name, not a selection defect).
# VITEST_CMD env overrides the vitest binary (default local
# node_modules/.bin/vitest) — the seam scripts/test_fast_runners_manifest.py
# drives with canned fakes.
set -eu

BASE="${1:?usage: fast-frontend-runner.sh BASE_REF}"
# No self-cd (WP2.3 contract, same as fast-backend-runner.sh): callers run
# with cwd = repo root; the git checks below fail loudly for any other cwd,
# and the `cd frontend` further down catches a repo without a frontend/.

# Loud failure over silent-empty selection — same rule fast_select encodes as
# exit 2, and a defect the draft smoke caught in the plan's listing: an
# unreachable BASE (or a non-repo cwd) makes `git diff` fail INSIDE a pipe,
# where the pipeline exit code is sed's (0), so the run would print "nothing
# affected" and exit 0 — a green --fast that ran zero frontend tests. Verify
# the repo and the ref up front instead.
git rev-parse --git-dir >/dev/null 2>&1 || {
    echo "fast(frontend): $(pwd) is not a git repository" >&2; exit 2; }
git rev-parse --verify --quiet "${BASE}^{commit}" >/dev/null || {
    echo "fast(frontend): base ref '$BASE' not found (fast tier needs a reachable base - run the full gate)" >&2; exit 2; }

CHANGED=$(git diff --name-only "$BASE" | sed -n 's|^frontend/||p')
UNTRACKED=$(git ls-files --others --exclude-standard | sed -n 's|^frontend/||p')
ALL=$(printf '%s\n%s\n' "$CHANGED" "$UNTRACKED" | grep -v '^$' | sort -u || true)

# Partition: selectable sources vs config-class files (full-gate territory)
SELECTABLE=$(printf '%s\n' "$ALL" | grep -E '^src/.*\.(ts|tsx|js|jsx)$' || true)
CONFIGY=$(printf '%s\n' "$ALL" | grep -E '^(package\.json|vite\.config|tsconfig|.*\.config\.ts$)' || true)

# Universe for the manifest: tracked frontend test files, frontend/-stripped
# (the reporter names files frontend/-relative; the manifest matches that).
UNIVERSE_REL=$(git ls-files "frontend/src" | sed -n 's|^frontend/||p' \
    | grep -E '\.(test|spec)\.(ts|tsx|js|jsx)$' | sort -u || true)

# emit_manifest NOT_SELECTED_LIST RUN_COUNT CRASH_REASON LOG
#   not-selected = universe files the reporter never mentioned. Matching on
#   the log by path substring (fixed-string) is the honest run/route split:
#   the default reporter prints each run file's path.
emit_manifest() {
    NOT_SEL="$1"; RUN="$2"; CRASH="$3"; MLOG="$4"
    NS=$(printf '%s\n' "$NOT_SEL" | grep -c . || true)
    printf 'MANIFEST NOT-SELECTED: %s (not selected for this diff)\n' "$NS"
    if [ "$NS" -gt 0 ]; then
        # names on MANIFEST-prefixed lines: a parser filtering MANIFEST* must
        # see WHICH files didn't run (see fast-backend-runner.sh, same fix).
        printf '%s\n' "$NOT_SEL" | head -20 | sed 's/^/MANIFEST NOT-SELECTED-FILE: /'
        [ "$NS" -gt 20 ] && printf 'MANIFEST NOT-SELECTED-MORE: %s\n' "$((NS - 20))"
    fi
    # A crash is its own category — never ALSO "normal zero-selection" (the
    # probe caught both lines printing together; the contract forbids the two
    # rendering alike, including simultaneously).
    if [ "$RUN" = "0" ] && [ -z "$CRASH" ] && [ -n "${EMIT_ZERO_RELATED:-}" ]; then
        echo "MANIFEST ZERO-RELATED: a source change selected 0 test files (normal under vitest semantics - related found no importers)"
    fi
    [ -n "$CRASH" ] && printf 'MANIFEST CANNOT-RUN: %s\n' "$CRASH"
    return 0
}

universe_not_selected() {
    MLOG="$1"
    OUT=""
    for u in $UNIVERSE_REL; do
        [ -n "$MLOG" ] && grep -qF -- "$u" "$MLOG" 2>/dev/null && continue
        OUT="${OUT}${u}
"
    done
    printf '%s' "$OUT" | grep -v '^$' || true
}

if [ -n "$CONFIGY" ]; then
    echo "fast(frontend): config-class changes detected - vitest related would" \
         "run the full suite (forceRerunTriggers). Run the full gate for:"
    printf '  %s\n' $CONFIGY
fi

if [ -z "$SELECTABLE" ]; then
    echo "SELECTED-FRONTEND-FILES: 0"
    echo "fast(frontend): 0 frontend source files changed - nothing affected"
    emit_manifest "$(printf '%s\n' "$UNIVERSE_REL")" 0 "" ""
    exit 0
fi

# [RECONCILIATION - loud] Playbook run 1 (2026-09-14) executed this runner for
# the first time and exposed two landed bugs, both fixed here:
#  (1) VERSION/ROOT: `npx vitest` from the REPO ROOT found no local vitest
#      (frontend/node_modules is one level down) and downloaded the registry
#      LATEST — v5.0.0 — running with root as vitest-root. v5's mock-hoisting
#      plugin then hard-errored ('call ... defined outside top level scope')
#      on files v4 runs green in the gate. Fix: cd into frontend/ and exec
#      the LOCAL node_modules/.bin/vitest (4.0.18, the version the plan's
#      source sweep and the gate both pin) — same proven invocation as the
#      measurement-plan Step-3 related census.
#  (2) RC MASK: `vitest | tee LOG; RC=$?` captured TEE's exit, not vitest's —
#      a crashed run reported rc=0 and the case still printed OK. That is
#      exactly the spec §5 mask class this milestone exists to kill. Fix:
#      redirect to LOG, take vitest's own exit, then emit the log.
# 8 GB heap floor matches the npm-script wrapper direct invocation bypasses.
cd frontend || { echo "fast(frontend): frontend/ directory missing" >&2; exit 2; }
VITEST="${VITEST_CMD:-node_modules/.bin/vitest}"
if [ -z "${VITEST_CMD:-}" ] && [ ! -x node_modules/.bin/vitest ]; then
    echo "fast(frontend): frontend/node_modules/vitest missing - run npm ci in frontend/" >&2
    exit 2
fi
export NODE_OPTIONS="${NODE_OPTIONS:-} --max-old-space-size=${VITEST_HEAP_MB:-8192}"
echo "fast(frontend): related over:"
printf '  %s\n' $SELECTABLE
LOG=$(mktemp)
EMIT_ZERO_RELATED=1; export EMIT_ZERO_RELATED
trap 'rm -f "$LOG"' EXIT
set +e
"$VITEST" related --run $SELECTABLE --reporter=default > "$LOG" 2>&1
RC=$?
set -e
cat "$LOG"
# Count of test files the default reporter actually ran. CALIBRATED against
# 4.0.18's real output (playbook run 1 + control arm): the summary line is
# 'Test Files  A passed | B skipped (TOTAL)' or 'Test Files  F failed | P
# passed (TOTAL)' — the TOTAL that matters lives in the LAST parentheses.
# The draft's "first number" regex would report the FAILED count on a red
# run — fixed as part of this calibration (plan Task 11 pre-authorized
# adjusting the regex at live calibration and recording it here).
RUN_COUNT=$(grep -E 'Test Files' "$LOG" | tail -1 | grep -oE '\(([0-9]+)\)' | tail -1 | tr -d '()' || true)
RUN_COUNT=${RUN_COUNT:-0}
echo "SELECTED-FRONTEND-FILES: $RUN_COUNT"

# cannot-run: non-zero exit AND no 'Test Files' summary ever printed —
# vitest died before evaluating anything (uncollectable parse/import crash,
# or a bad-invocation error). A run WITH a summary is a verdict, not a crash.
CRASH=""
if [ "$RC" -ne 0 ] && ! grep -qE 'Test Files' "$LOG"; then
    CRASH="vitest exited $RC without printing a test summary (uncollectable/crash) over changed files: $(printf '%s ' $SELECTABLE)"
fi

emit_manifest "$(universe_not_selected "$LOG")" "$RUN_COUNT" "$CRASH" "$LOG"
if [ -n "$CRASH" ]; then
    exit 1
fi
exit "$RC"

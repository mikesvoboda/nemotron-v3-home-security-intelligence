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
# Unquoted $SELECTABLE word-splitting is deliberate-POSIX (repo file names
# contain no spaces - verified: git ls-files frontend/src | grep ' ' is empty).
# related follows the full transitive import graph, so a shared-module edit
# selecting most of the suite is honest behavior, not a bug (the count line
# tells the developer why today's --fast wasn't fast).
set -eu

BASE="${1:?usage: fast-frontend-runner.sh BASE_REF}"
cd "$(dirname "$0")/.."

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

if [ -n "$CONFIGY" ]; then
    echo "fast(frontend): config-class changes detected - vitest related would" \
         "run the full suite (forceRerunTriggers). Run the full gate for:"
    printf '  %s\n' $CONFIGY
fi

if [ -z "$SELECTABLE" ]; then
    echo "SELECTED-FRONTEND-FILES: 0"
    echo "fast(frontend): 0 frontend source files changed - nothing affected"
    exit 0
fi

# 8 GB heap floor matches the npm-script wrapper direct-npx would bypass.
export NODE_OPTIONS="${NODE_OPTIONS:-} --max-old-space-size=${VITEST_HEAP_MB:-8192}"
echo "fast(frontend): related over:"
printf '  %s\n' $SELECTABLE
LOG=$(mktemp)
trap 'rm -f "$LOG"' EXIT
set +e
npx vitest related --run $SELECTABLE --reporter=default 2>&1 | tee "$LOG"
RC=$?
set -e
# Count the test files the default reporter actually ran. The summary line
# shape is 'Test Files  N passed (N)' - the count FOLLOWS the label, so the
# label anchors the grep and the first number on that line is the count (a
# digits-before-label regex would miss it; caught in draft review). Plan Task
# 11 Step 2 is the live calibration of this against 4.0.18's real reporter
# output on the leased box - adjust there if the shape differs and record the
# final regex in that commit. [UNVERIFIED until that calibration.]
RUN_COUNT=$(grep -E 'Test Files' "$LOG" | grep -oE '[0-9]+' | head -1 || true)
echo "SELECTED-FRONTEND-FILES: ${RUN_COUNT:-0}"
exit $RC

#!/usr/bin/env bash
# Gate test for ci.yml's verdict machinery (WP1.4) — run explicitly; like the
# other scripts/test_* gate tests it sits outside testpaths on purpose.
#
#   bash scripts/test_summary_verdicts.sh
#
# Two compounding defects this pins:
#   1. THE REQUIRED UNIT TIER WAS BLIND TO TIMEOUTS — it passed --timeout=0,
#      which backend/tests/conftest.py honors by disabling EVERY per-test
#      timeout (the M3 T5 CLI-governs ruling). A hung test then waits out the
#      15-min job cap -> the shard ends `cancelled` -> defect 2 forgives it.
#      Measured (WP1.4): 447,391 unit rows across 17 TPA-red run corpora +
#      green main run 35486259345 — max duration 19.02s, ZERO rows > 20s —
#      so --timeout=30 (validate.sh's own value, same as every integration
#      job) never fires on a legitimately slow test; it only converts a hang
#      into a per-test FAILURE at 30s instead of a job-cap cancellation.
#   2. SUMMARIES FORGAVE `cancelled` — a shard killed at the job cap fell
#      through the "== failure" tests to "All ... shards passed" (the class
#      WP0.5 already fixed for the API shard: run 35353201418 attempt 4, CI
#      Gate green with the tier dead). unit/frontend/e2e summaries never got
#      the fix, and integration-tests-summary still forgives cancelled for
#      its three NON-API shards (its retry exception covers api only).
#
# The verdict step of each summary job is EXTRACTED FROM ci.yml and executed —
# `${{ }}` expressions fed through bash the way the runner does: a result
# string substituted inside an already-double-quoted argument (word-splitting
# stays impossible), names normalized to env vars the test then fills.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CI="$SCRIPT_DIR/../.github/workflows/ci.yml"
PY="${PYTHON:-uv run python}"
[ -f "$CI" ] || { echo "missing $CI" >&2; exit 2; }

FAILURES=0
bad() { printf '  FAIL: %s\n' "$*" >&2; FAILURES=$((FAILURES + 1)); }

ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
export GITHUB_STEP_SUMMARY="$ROOT/summary.md"

# step_script JOB STEP_NAME OUT — extract one step's run block, expressions ->
# "$NEEDS_A_B_RESULT"-style expansions.
step_script() {
  $PY - "$CI" "$1" "$2" >"$3" <<'PY'
import re
import sys

import yaml

ci, job, step_name = sys.argv[1], sys.argv[2], sys.argv[3]
with open(ci) as f:
    data = yaml.safe_load(f)
steps = data["jobs"][job]["steps"]
block = next(s["run"] for s in steps if s.get("name") == step_name)


def sub(m):
    name = m.group(1).strip().replace("-", "_").replace(".", "_").upper()
    return '"${' + name + '}"'


sys.stdout.write(re.sub(r"\$\{\{([^}]*)\}\}", sub, block))
PY
}

run_verdict() { # $1 = step file; sets RC
  bash "$1" >"$ROOT/out.log" 2>&1
  RC=$?
}

# ---------------------------------------------------------------------------
# Defect 1: the required unit tier must be able to SEE a timeout.
# ---------------------------------------------------------------------------
echo "[1] required unit tier runs with a real per-test timeout (not --timeout=0)"
# the shard step's name carries ${{ matrix.shard }}, so locate it by content
$PY - "$CI" >"$ROOT/unit-run.sh" <<'PY'
import sys

import yaml

with open(sys.argv[1]) as f:
    data = yaml.safe_load(f)
steps = data["jobs"]["unit-tests"]["steps"]
block = next(s["run"] for s in steps if "pytest backend/tests/unit/" in (s.get("run") or ""))
sys.stdout.write(block)
PY
grep -q -- '--timeout=0' "$ROOT/unit-run.sh" &&
  bad "unit tier still passes --timeout=0 (conftest.py disables ALL per-test timeouts on that flag — required tier cannot see a hang)"
grep -Eq -- '--timeout=[1-9][0-9]*' "$ROOT/unit-run.sh" ||
  bad "unit tier has no positive --timeout — the required tier is blind to timeout flakes"
grep -Eq -- '--cov-fail-under=[1-9]' "$ROOT/unit-run.sh" &&
  bad "unit shard raised its coverage threshold (WP1.4 scope is the timeout; coverage floors are WP2.3)"

# ---------------------------------------------------------------------------
# Defect 2: every summary treats a cancelled shard as not-success.
# skipped stays forgiven (a never-run shard is not a verdict — same stance as
# ci-gate's check_job). An ABSENT need yields an empty result: inert in the
# runner's literal substitution, and the summary must not crash on it.
# ---------------------------------------------------------------------------
export NEEDS_DETECT_CHANGES_OUTPUTS_SHOULD_RUN_ALL="true"
export NEEDS_DETECT_CHANGES_OUTPUTS_BACKEND="true"
export NEEDS_DETECT_CHANGES_OUTPUTS_FRONTEND="true"

check_summary() { # $1 job  $2 step name  $3 env var for the shard need
  local job="$1" step="$2" var="$3" label="$4"
  local f="$ROOT/$label.sh"
  step_script "$job" "$step" "$f"

  export NEEDS_INTEGRATION_TESTS_API_RETRY_RESULT=""

  export "$var"="cancelled"
  run_verdict "$f"
  [ "$RC" -ne 0 ] || bad "$label: a cancelled shard exited 0 — the summary FORGIVES cancellation"

  export "$var"="skipped"
  run_verdict "$f"
  [ "$RC" -eq 0 ] || bad "$label: skipped shard must stay forgiven (a never-run shard is not a verdict)"

  export "$var"=""
  run_verdict "$f"
  [ "$RC" -eq 0 ] || bad "$label: absent need (empty result) crashed or reddened the summary"

  export "$var"="failure"
  run_verdict "$f"
  [ "$RC" -ne 0 ] || bad "$label: a failed shard must be red"

  export "$var"="success"
  run_verdict "$f"
  [ "$RC" -eq 0 ] || bad "$label: all-success must be green"
}

echo "[2] unit-tests-summary: cancelled shard is not-success"
check_summary unit-tests-summary "Check unit test shard results" NEEDS_UNIT_TESTS_RESULT "unit"

echo "[3] frontend-tests-summary: cancelled shard is not-success"
check_summary frontend-tests-summary "Check shard results" NEEDS_FRONTEND_TESTS_RESULT "vitest"

echo "[4] frontend-e2e-summary: cancelled shard is not-success"
check_summary frontend-e2e-summary "Check shard results" NEEDS_FRONTEND_E2E_RESULT "e2e"

echo "[5] integration-tests-summary: cancelled NON-API shard is not-success; API cancelled + retry success stays green (WP0.5 exception preserved)"
f="$ROOT/integration.sh"
step_script integration-tests-summary "Check integration test results" "$f"
export NEEDS_INTEGRATION_TESTS_API_RESULT="success"
export NEEDS_INTEGRATION_TESTS_WEBSOCKET_RESULT="success"
export NEEDS_INTEGRATION_TESTS_SERVICES_RESULT="success"
export NEEDS_INTEGRATION_TESTS_MODELS_RESULT="success"
export NEEDS_INTEGRATION_TESTS_API_RETRY_RESULT=""

for V in WEBSOCKET SERVICES MODELS; do
  export "NEEDS_INTEGRATION_TESTS_${V}_RESULT"="cancelled"
  run_verdict "$f"
  [ "$RC" -ne 0 ] || bad "integration: cancelled $V shard exited 0 — non-API shards still forgive cancellation"
  export "NEEDS_INTEGRATION_TESTS_${V}_RESULT"="success"
done

export NEEDS_INTEGRATION_TESTS_API_RESULT="cancelled"
export NEEDS_INTEGRATION_TESTS_API_RETRY_RESULT="success"
run_verdict "$f"
[ "$RC" -eq 0 ] || bad "integration: API cancelled + retry SUCCESS must stay green (WP0.5 slow-runner exception)"
export NEEDS_INTEGRATION_TESTS_API_RETRY_RESULT=""
run_verdict "$f"
[ "$RC" -ne 0 ] || bad "integration: API cancelled with no passing retry must be red"
export NEEDS_INTEGRATION_TESTS_API_RESULT="skipped"
run_verdict "$f"
[ "$RC" -eq 0 ] || bad "integration: skipped API shard must stay forgiven"

if [ "$FAILURES" -eq 0 ]; then
  echo "OK: summary verdicts are honest — no cancelled shard passes a tier (WP1.4)"
  exit 0
else
  echo "FAILED: $FAILURES assertion(s) against $CI" >&2
  exit 1
fi

#!/usr/bin/env bash
# Gate test for scripts/audit-test-durations.py (WP0.5) — run explicitly; like the
# other scripts/test_* gate tests it sits outside testpaths on purpose.
#
#   bash scripts/test_audit_gate.sh
#
# Proves the Test Performance Audit is an honest GATE at the owner-ruled raised
# thresholds (WP0.5 RULING 2026-09-16: "gate at raised thresholds"), not the
# red-and-advisory signal it was. Historical lies this pins against:
#   1. an EMPTY results dir printed a warning and exited 0 — a job with zero
#      test data "passed" vacuously (same class as the pre-push head|-lies);
#   2. thresholds (unit 1.0s) sat below the honest baseline (46 rows), so the
#      job could never gate anything — it only announced its own red;
#   3. raising thresholds silently launders known-slow tests: the ruling's
#      fix is a TRACKED-SLOW list (extended 60s cap, visible in every report),
#      and a tracked test that blows even the slow cap must still bite.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUDIT="$SCRIPT_DIR/audit-test-durations.py"
[ -f "$AUDIT" ] || { echo "missing $AUDIT" >&2; exit 2; }

ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

# Raised-threshold environment — must match ci.yml's step env (WP0.5).
export UNIT_TEST_THRESHOLD=4.0
export INTEGRATION_TEST_THRESHOLD=10.0
export E2E_TEST_THRESHOLD=10.0
export SLOW_TEST_THRESHOLD=60.0
export WARN_THRESHOLD_PERCENT=80

# junit fixture builder: $1=file $2=classname $3=name $4=seconds
mk_xml() {
  cat >"$1" <<EOF
<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="s" tests="1" time="$4">
  <testcase classname="$2" name="$3" time="$4"/>
</testsuite></testsuites>
EOF
}

FAILURES=0
bad() { printf '  FAIL: %s\n' "$*" >&2; FAILURES=$((FAILURES + 1)); }

run_audit() { # $1 = results dir; sets RC
  uv run python "$AUDIT" "$1" >"$ROOT/out.log" 2>&1
  RC=$?
}

expect_zero()    { [ "$RC" -eq 0 ] || bad "$1: expected exit 0, got $RC — $(tail -1 "$ROOT/out.log")"; }
expect_nonzero() { [ "$RC" -ne 0 ] || bad "$1: expected non-zero exit, got 0 — the GATE LIES"; }
expect_line()    { case "$(cat "$ROOT/out.log")" in *"$2"*) : ;; *) bad "$1: output missing '$2'"; ;; esac; }

U="backend.tests.unit.example.test_thing.TestThing"
I="backend.tests.integration.test_thing.TestThing"

echo "[1] a NEW test at 4.5s unit bites the raised gate"
rm -rf "$ROOT/d"; mkdir -p "$ROOT/d"
mk_xml "$ROOT/d/a.xml" "$U" "test_newly_slow" 4.5
run_audit "$ROOT/d"; expect_nonzero "new-slow-unit"
expect_line "new-slow-unit" "RESULT: FAIL"

echo "[2] the old 3.xs cluster the 1.0s gate failed now passes the 4.0s gate"
rm -rf "$ROOT/d"; mkdir -p "$ROOT/d"
mk_xml "$ROOT/d/a.xml" "$U" "test_fits_under_raised" 3.5
run_audit "$ROOT/d"; expect_zero "under-raised"

echo "[3] integration 9.5s passes the 10.0s gate; 12s bites"
rm -rf "$ROOT/d"; mkdir -p "$ROOT/d"
mk_xml "$ROOT/d/a.xml" "$I" "test_ok" 9.5
run_audit "$ROOT/d"; expect_zero "int-under"
mk_xml "$ROOT/d/a.xml" "$I" "test_bad" 12.0
run_audit "$ROOT/d"; expect_nonzero "int-over"

echo "[4] WP0.5-tracked slow test at 16s PASSES on the 60s slow cap"
rm -rf "$ROOT/d"; mkdir -p "$ROOT/d"
mk_xml "$ROOT/d/a.xml" \
  "backend.tests.unit.api.middleware.test_error_handler.TestErrorResponse" \
  "test_timestamp_auto_generated" 16.0
run_audit "$ROOT/d"; expect_zero "tracked-slow"
expect_line "tracked-slow" "KNOWN SLOW TESTS"

echo "[5] a tracked-slow test at 61s blows the slow cap and BITES"
mk_xml "$ROOT/d/a.xml" \
  "backend.tests.unit.api.middleware.test_error_handler.TestErrorResponse" \
  "test_timestamp_auto_generated" 61.0
run_audit "$ROOT/d"; expect_nonzero "tracked-over-slow-cap"

echo "[6] EMPTY results dir must FAIL the job, not 'pass' vacuously"
rm -rf "$ROOT/d"; mkdir -p "$ROOT/d"
run_audit "$ROOT/d"; expect_nonzero "empty-dir"

echo "[7] benchmarks stay excluded at the raised gate (no laundering regression)"
rm -rf "$ROOT/d"; mkdir -p "$ROOT/d"
mk_xml "$ROOT/d/a.xml" "backend.tests.benchmarks.test_api.TestAPIBenchmarks" "test_heavy" 200.0
run_audit "$ROOT/d"; expect_zero "benchmark-excluded"

if [ "$FAILURES" -eq 0 ]; then
    echo "OK: audit-test-durations gate verdicts are honest (7 cases)"
    exit 0
else
    echo "FAILED: $FAILURES assertion(s) against $AUDIT" >&2
    exit 1
fi

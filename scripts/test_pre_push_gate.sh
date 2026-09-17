#!/usr/bin/env bash
# Gate test for scripts/pre-push-tests.sh (WP0.1) — run explicitly; like the other
# scripts/test_*.py gate tests it sits outside testpaths on purpose.
#
#   bash scripts/test_pre_push_gate.sh
#
# Proves the hook's Done-when property: a deliberately failing backend smoke test
# AND a deliberately failing frontend smoke test each make the hook exit non-zero and
# block a real `git push` (hook installed normally in a throwaway repo — never
# --no-verify). Historical lies it pins against:
#   1. `if cmd | head -N` tests head's exit status, so jobs 2+3 passed unconditionally;
#   2. a pytest failure fell through to a `python -c` import fallback which then passed;
#   3. a jest-only flag (--testPathPattern) made vitest exit non-zero BEFORE running
#      any test, so the always-green tsc fallback silently substituted for frontend
#      smoke tests. npx is shimmed always-clean to catch exactly that substitution.
# External commands are PATH shims that log every invocation, so the test can also
# assert WHICH commands ran.
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_HOOK="$SCRIPT_DIR/pre-push-tests.sh"
[ -f "$SRC_HOOK" ] || { echo "missing $SRC_HOOK" >&2; exit 2; }

ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT
BIN="$ROOT/bin"
LOGS="$ROOT/logs"
mkdir -p "$BIN" "$LOGS" "$ROOT/scripts" "$ROOT/frontend"
cp "$SRC_HOOK" "$ROOT/scripts/pre-push-tests.sh"

# --- sandbox stubs ---------------------------------------------------------------
# Job 1 invokes generate-types.sh by absolute path, so it lives in sandbox scripts/.
cat >"$ROOT/scripts/generate-types.sh" <<EOF
#!/bin/sh
echo "generate-types \$*" >> "$LOGS/calls"
if [ -f "$ROOT/broken_types" ]; then echo "types drift detected"; exit 1; fi
echo "types current"
exit 0
EOF
chmod +x "$ROOT/scripts/generate-types.sh"

# uv: pytest invocations fail iff broken_backend; rc=5 iff broken_nocollect.
# Import fallback fails iff broken_import (so its verdict can itself bite).
# uv: pytest runs emit 60 lines then the honest verdict — a runner whose successful
# output exceeds the 50-line display cap pins the SIGPIPE hazard (pytest|head +
# pipefail would report 141 on a GREEN run; the fix writes a full log and truncates
# the display instead).
cat >"$BIN/uv" <<EOF
#!/bin/sh
echo "uv \$*" >> "$LOGS/calls"
case "\$*" in
  *pytest*)
    i=0; while [ \$i -lt 60 ]; do echo "progress line \$i"; i=\$((i+1)); done
    if [ -f "$ROOT/broken_nocollect" ]; then echo "no tests ran"; exit 5; fi
    if [ -f "$ROOT/broken_backend" ]; then echo "FAILED 1 failed"; exit 1; fi
    echo "smoke passed"; exit 0 ;;
  *)
    if [ -f "$ROOT/broken_import" ]; then echo "ImportError"; exit 1; fi
    echo "Backend imports OK"; exit 0 ;;
esac
EOF
# npm == the vitest runner: honest rc for the frontend smoke tests. rc=127 models
# the runner being un-launchable — the ONE condition under which the tsc fallback
# is legitimate. "Ran but no files matched" is a smoke FAILURE (a silent smoke test
# is how the jest-flag lie hid for a year), never a fallback.
cat >"$BIN/npm" <<EOF
#!/bin/sh
echo "npm \$*" >> "$LOGS/calls"
if [ -f "$ROOT/broken_npmabsent" ]; then echo "npm: command not found"; exit 127; fi
if [ -f "$ROOT/broken_frontend" ]; then echo "FAIL App renders: 1 failed"; exit 1; fi
if [ -f "$ROOT/broken_testsmissing" ]; then echo "No test files found"; exit 1; fi
echo "App: 6 passed"; exit 0
EOF
# npx == tsc only, deliberately ALWAYS clean: if a failed frontend test ever routes
# through the tsc fallback, the hook prints PASSED and these tests catch it.
cat >"$BIN/npx" <<EOF
#!/bin/sh
echo "npx \$*" >> "$LOGS/calls"
if [ -f "$ROOT/broken_tsckey" ]; then echo "App.tsx:1 - error TS1005"; exit 2; fi
echo "tsc clean"; exit 0
EOF
chmod +x "$BIN"/*

# --- throwaway repo with the hook installed normally ------------------------------
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null GIT_TERMINAL_PROMPT=0
git init -q --bare -b main "$ROOT/remote.git"
git init -q -b main "$ROOT/repo"
cat >"$ROOT/repo/.git/hooks/pre-push" <<EOF
#!/bin/sh
echo "pre-push \$*" >> "$LOGS/calls"
exec "$ROOT/scripts/pre-push-tests.sh" "\$@"
EOF
chmod +x "$ROOT/repo/.git/hooks/pre-push"
git -C "$ROOT/repo" remote add origin "$ROOT/remote.git"
git -C "$ROOT/repo" -c user.email=gate@test.invalid -c user.name=gate commit -q --allow-empty -m seed

# --- assertions -------------------------------------------------------------------
FAILURES=0
bad() { printf '  FAIL: %s\n' "$*" >&2; FAILURES=$((FAILURES + 1)); }

# Capture to FILES, never $(...): the hook's 60s timeout watcher can leave an orphaned
# `sleep` holding an inherited fd, and a command substitution waits for that EOF.
OUTF="$ROOT/out.log"
run_direct() {
  ( cd "$ROOT" && env PATH="$BIN:/usr/bin:/bin" timeout 120 bash scripts/pre-push-tests.sh ) >"$OUTF" 2>&1
  RC=$?; OUT="$(cat "$OUTF")"
}
run_push() {
  env PATH="$BIN:/usr/bin:/bin" timeout 120 git -C "$ROOT/repo" push origin HEAD:refs/heads/main >"$OUTF" 2>&1
  RC=$?; OUT="$(cat "$OUTF")"
}

reset_sandbox() { rm -f "$ROOT"/broken_* "$LOGS/calls"; }

expect_zero()    { [ "$RC" -eq 0 ]  || bad "$1: expected exit 0, got $RC"; }
expect_nonzero() { [ "$RC" -ne 0 ]  || bad "$1: expected non-zero exit, got 0 — the hook LIES"; }
expect_line()    { case "$OUT" in *"$2"*) : ;; *) bad "$1: output missing '$2'"; ;; esac; }
expect_call()    { grep -q "$2" "$LOGS/calls" 2>/dev/null || bad "$1: expected a call matching '$2'"; }
expect_no_call() { grep -q "$2" "$LOGS/calls" 2>/dev/null && bad "$1: command matching '$2' ran, must not"; }

echo "[1] healthy sandbox: hook passes on the real commands, no fallback substitutes"
reset_sandbox
run_direct
expect_zero "healthy"
expect_line "healthy" "[1] API Types Contract: PASSED"
expect_line "healthy" "[2] Backend Selected Tier: PASSED"
expect_line "healthy" "[3] Frontend Selected Tier: PASSED"
expect_no_call "healthy" "npx tsc"        # healthy path must not hide behind a compile check
expect_no_call "healthy" "from backend.main import"

echo "[2] broken backend test: hook fails and never excuses itself via the import fallback"
reset_sandbox
touch "$ROOT/broken_backend"
run_direct
expect_nonzero "broken-backend"
expect_line "broken-backend" "[2] Backend Selected Tier: FAILED"
expect_no_call "broken-backend" "from backend.main import"

echo "[3] broken frontend test: hook fails even though tsc is clean"
reset_sandbox
touch "$ROOT/broken_frontend"
run_direct
expect_nonzero "broken-frontend"
expect_line "broken-frontend" "[3] Frontend Selected Tier: FAILED"

echo "[4] broken types contract: hook fails (pins job 1, which never lied)"
reset_sandbox
touch "$ROOT/broken_types"
run_direct
expect_nonzero "broken-types"
expect_line "broken-types" "[1] API Types Contract: FAILED"

echo "[5] pytest rc=5 with clean import: author's no-tests fallback stays legitimate"
reset_sandbox
touch "$ROOT/broken_nocollect"
run_direct
expect_zero "no-collect"
expect_call "no-collect" "from backend.main import"

echo "[6] pytest rc=5 with broken import: the fallback must bite"
reset_sandbox
touch "$ROOT/broken_nocollect" "$ROOT/broken_import"
run_direct
expect_nonzero "no-collect+bad-import"

echo "[7] vitest un-launchable (rc=127): tsc fallback is legitimate; tsc dirty must bite"
reset_sandbox
touch "$ROOT/broken_npmabsent"
run_direct
expect_zero "runner-absent"
expect_call "runner-absent" "npx tsc"
reset_sandbox
touch "$ROOT/broken_npmabsent" "$ROOT/broken_tsckey"
run_direct
expect_nonzero "runner-absent+tsc-dirty"

echo "[8] vitest ran but matched no files: smoke FAILURE, never a tsc fallback"
reset_sandbox
touch "$ROOT/broken_testsmissing"
run_direct
expect_nonzero "tests-missing"
expect_no_call "tests-missing" "npx tsc"

echo "[9] git push blocked by a broken backend test (hook installed normally)"
reset_sandbox
touch "$ROOT/broken_backend"
run_push
expect_nonzero "push-backend"
expect_call "push-backend" "pre-push"

echo "[10] git push blocked by a broken frontend test"
reset_sandbox
touch "$ROOT/broken_frontend"
run_push
expect_nonzero "push-frontend"
expect_call "push-frontend" "pre-push"

echo "[11] healthy push still succeeds end-to-end"
reset_sandbox
run_push
expect_zero "push-healthy"
expect_call "push-healthy" "pre-push origin"

if [ "$FAILURES" -eq 0 ]; then
    echo "OK: pre-push gate verdicts are honest (11 cases)"
    exit 0
else
    echo "FAILED: $FAILURES assertion(s) against $SRC_HOOK" >&2
    exit 1
fi

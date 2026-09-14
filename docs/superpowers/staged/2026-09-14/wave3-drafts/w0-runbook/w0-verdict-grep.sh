#!/usr/bin/env bash
# w0-verdict-grep.sh — READ-ONLY verdict extractor for gate 14 (W0 runbook STEP 1).
# Touches NOTHING but reads. Safe while any gate is live. No pytest/vitest/npm/compose.
# Usage: bash /tmp/wave3-drafts/w0-runbook/w0-verdict-grep.sh [logfile]   (default /tmp/validate-full-14.log)
set -uo pipefail   # deliberately NOT -e: we want every section to print even when a grep finds nothing

LOG="${1:-/tmp/validate-full-14.log}"
BANNER='  VALIDATION SUCCESSFUL: codebase is healthy!'   # validate.sh:529, two leading spaces

echo "=== gate-14 verdict readout — $(date -Is) ==="
pid="$(cat /tmp/gate14.pid 2>/dev/null || true)"
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
  echo "PROCESS: pid $pid STILL RUNNING — verdict is NOT final yet; re-run after it exits."
else
  echo "PROCESS: pid '${pid:-unknown}' not alive — log is final (verdict may be read)."
fi
[ -r "$LOG" ] || { echo "LOG: $LOG unreadable — ABORT readout."; exit 2; }
echo "LOG: $LOG  size=$(wc -c <"$LOG")  lines=$(wc -l <"$LOG")  mtime=$(stat -c %y "$LOG")"

echo; echo "--- [1] success banner, exact whole-line, with '=' rules (paste this block to the ledger) ---"
grep -FxC 1 "$BANNER" "$LOG" || echo "(no banner — NOT green as of this readout)"

echo; echo "--- [2] banner line number for citation ---"
grep -Fxn "$BANNER" "$LOG" || echo "(none)"

echo; echo "--- [3] banner count (must be exactly 1) ---"
grep -cF "$BANNER" "$LOG"

echo; echo "--- [4] validate.sh stage-failure lines ('^[ERROR] ', anchored — must be 0) ---"
grep -cE '^\[ERROR\] ' "$LOG"

echo; echo "--- [5] combined coverage TOTAL row (gate: >=80) + side-log binding ---"
grep -n '^TOTAL' "$LOG" | tail -1
ls -l --time-style=full-iso /tmp/validate-backend-unit.log /tmp/validate-backend-integration.log /tmp/validate-coverage-report.log 2>/dev/null
tail -2 /tmp/validate-coverage-report.log 2>/dev/null

echo; echo "--- [6] backend pytest summaries (side logs; verify mtime is TODAY/post-launch) ---"
for f in /tmp/validate-backend-unit.log /tmp/validate-backend-integration.log; do
  [ -r "$f" ] && { echo "## $f"; grep -E '[0-9]+ (passed|failed|error)' "$f" | tail -2; }
done

echo; echo "--- [7] vitest summaries (color-strip first — vitest stderr keeps ANSI) ---"
sed -r 's/\x1b\[[0-9;]*m//g' "$LOG" > /tmp/validate-full-14.clean.log
grep -E 'Test Files|Tests  |Duration' /tmp/validate-full-14.clean.log | tail -5

echo; echo "--- [8] negative control: gate 12 (died) must show banner-count 0 ---"
[ -r /tmp/validate-full-12.log ] \
  && echo "gate-12 banner count: $(grep -cF "$BANNER" /tmp/validate-full-12.log)" \
  || echo "gate-12: log absent — note '[control unrunnable: no /tmp/validate-full-12.log]' in the ledger"

echo; echo "=== readout done. GREEN ⇔ [process exited] AND [3]=1 AND [4]=0. All three, or hand back. ==="

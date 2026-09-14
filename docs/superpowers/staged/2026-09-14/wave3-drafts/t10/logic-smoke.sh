#!/usr/bin/env bash
# Logic smoke for fast_select.py — stdlib-only python3 + throwaway git repos
# under /tmp (NEVER git init inside the real repo). Mirrors, case for case,
# the six pytest self-tests in scripts/test_fast_select.py plus four extra
# operational cases ( --why, bad base rc=2, POLICY-SKIP partition, untracked
# new module). Run: bash /tmp/wave3-drafts/t10/logic-smoke.sh
set -u

SELECT=/tmp/wave3-drafts/t10/new-files/scripts/fast_select.py
TESTFILE=/tmp/wave3-drafts/t10/new-files/scripts/test_fast_select.py
RUNNER=/tmp/wave3-drafts/t10/new-files/scripts/fast-frontend-runner.sh
FAIL=0
pass() { echo "  ok: $*"; }
fail() { echo "  FAIL: $*"; FAIL=1; }

# ---------- static checks (no execution of tests) ----------
echo "[static] python3 -m py_compile on both python files"
for f in "$SELECT" "$TESTFILE"; do
  if python3 -m py_compile "$f" 2>/tmp/wave3-drafts/t10/compile.err; then
    pass "compiles: $(basename "$f")"
  else
    fail "compile: $(basename "$f"): $(cat /tmp/wave3-drafts/t10/compile.err)"
  fi
done
echo "[static] bash -n on both runners"
for s in "$RUNNER" /tmp/wave3-drafts/t10/new-files/scripts/fast-backend-runner.sh; do
  if bash -n "$s"; then pass "bash -n $(basename "$s")"; else fail "bash -n $(basename "$s")"; fi
done
if command -v shellcheck >/dev/null 2>&1; then
  shellcheck -s sh "$RUNNER" /tmp/wave3-drafts/t10/new-files/scripts/fast-backend-runner.sh \
    && pass shellcheck || fail shellcheck
else
  echo "  (shellcheck ABSENT on this box — recorded in report)"
fi

# ---------- fixture repo (mirrors the pytest fixture exactly) ----------
R=$(mktemp -d /tmp/wave3-fixture.XXXX)
cd "$R" || exit 1
git init -q . && git config user.email t@t && git config user.name t
mkdir -p backend/api/routes backend/services \
         backend/tests/unit/api/routes backend/tests/unit/services backend/tests/contracts
echo 'def list_alerts(): ...' > backend/api/routes/alerts.py
echo 'class AlertService: ...' > backend/services/alert_service.py
printf 'def test_x():\n    from backend.api.routes.alerts import list_alerts\n' \
  > backend/tests/unit/api/routes/test_alerts.py
echo 'from backend.services.alert_service import AlertService' \
  > backend/tests/unit/services/test_alert_service.py
printf 'def test_y(mocker):\n    mocker.patch("backend.api.routes.metrics.get_x")\n' \
  > backend/tests/unit/services/test_metrics.py
echo 'def test_c(): ...' > backend/tests/contracts/test_api_contracts.py
for p in backend backend/api backend/api/routes backend/services backend/tests \
         backend/tests/unit backend/tests/unit/api backend/tests/unit/api/routes \
         backend/tests/unit/services backend/tests/contracts; do
  touch "$p/__init__.py"
done
echo 'def get_x(): ...' > backend/api/routes/metrics.py
git add -A && git commit -qm base

run() { python3 "$SELECT" "$@" 2>/tmp/wave3-drafts/t10/stderr.txt; }
reset_tree() { git checkout -q -- backend; git clean -qfd backend; }

# ---------- case 1: route change (lazy import) selects its test + smoke tier ----------
echo "[case 1] route lazy-import + directory policy (pytest: test_route_change_selects_lazy_import_test)"
printf 'def list_alerts():\n    return []  # touched\n' > backend/api/routes/alerts.py
OUT=$(run --base HEAD)
grep -q 'backend/tests/unit/api/routes/test_alerts.py' <<<"$OUT" \
  && pass "lazy-import test selected" || fail "lazy-import test missing: $OUT"
grep -q 'backend/tests/contracts/test_api_contracts.py' <<<"$OUT" \
  && pass "contracts smoke pulled by api/** policy" || fail "smoke tier missing"
reset_tree

# ---------- case 2: patch-string reference counts ----------
echo "[case 2] patch-string reference (pytest: test_patch_string_reference_counts)"
printf 'def get_x():\n    return 1  # touched\n' > backend/api/routes/metrics.py
OUT=$(run --base HEAD)
grep -q 'backend/tests/unit/services/test_metrics.py' <<<"$OUT" \
  && pass "mocker.patch() dotted string counts as a reference" \
  || fail "patch-string test missing: $OUT"
reset_tree

# ---------- case 3: service change selects importer only ----------
echo "[case 3] service importer-only (pytest: test_service_change_selects_importer_only)"
printf 'class AlertService:  # touched\n    pass\n' > backend/services/alert_service.py
OUT=$(run --base HEAD)
grep -q 'backend/tests/unit/services/test_alert_service.py' <<<"$OUT" \
  && pass "importer selected" || fail "importer missing: $OUT"
grep -q 'test_alerts.py' <<<"$OUT" \
  && fail "unrelated route test rode along" || pass "route test NOT selected"
reset_tree

# ---------- case 4: unmapped is loud ----------
echo "[case 4] unmapped loud (pytest: test_unmapped_is_loud)"
printf 'def f():\n    return 1\n' > backend/services/orphan.py
OUT=$(run --base HEAD)
grep -q 'UNMAPPED: backend/services/orphan.py' <<<"$OUT" \
  && pass "UNMAPPED printed" || fail "UNMAPPED missing: $OUT"
reset_tree

# ---------- case 5: --list-out exact contents ----------
echo "[case 5] list-out (pytest: test_list_out_file)"
printf 'class AlertService:  # x\n    pass\n' > backend/services/alert_service.py
run --base HEAD --list-out "$R/sel.txt" >/dev/null
if [ "$(cat "$R/sel.txt")" = "backend/tests/unit/services/test_alert_service.py" ]; then
  pass "list-out is exactly the selection, newline-terminated"
else
  fail "list-out content: $(od -c "$R/sel.txt" | head -3)"
fi
reset_tree

# ---------- case 6: no changes -> empty selection, rc 0 ----------
echo "[case 6] no changes (pytest: test_no_changes_empty_selection)"
OUT=$(run --base HEAD); RC=$?
[ "$RC" -eq 0 ] && grep -q 'SELECTED-BACKEND-FILES: 0' <<<"$OUT" \
  && pass "rc=0, SELECTED-BACKEND-FILES: 0" || fail "rc=$RC out=$OUT"

# ---------- case 7: --why prints reasons ----------
echo "[case 7] --why output contract"
printf 'def list_alerts():\n    return []  # touched\n' > backend/api/routes/alerts.py
OUT=$(run --base HEAD --why)
grep -q 'because: references backend.api.routes.alerts (changed: backend/api/routes/alerts.py)' <<<"$OUT" \
  && pass "why: reference reason" || fail "why reason missing: $OUT"
grep -q 'because: directory policy: change under backend/api/\*' <<<"$OUT" \
  && pass "why: policy reason" || fail "why policy missing: $OUT"
reset_tree

# ---------- case 8: bad base ref -> exit 2 ----------
echo "[case 8] unreachable base ref is loud (rc=2, not silent-empty)"
OUT=$(run --base refs/heads/does-not-exist); RC=$?
[ "$RC" -eq 2 ] && pass "rc=2 on bad ref" || fail "expected rc=2, got rc=$RC out=$OUT"

# ---------- case 9: POLICY-SKIP partition ----------
echo "[case 9] non-backend/non-docs change prints POLICY-SKIP; docs/frontend stay silent"
mkdir -p ai/yolo26 docs frontend
echo 'def t(): ...' > ai/yolo26/test_probe.py
echo 'x' > docs/probe.md
echo 'y' > frontend/probe.ts
OUT=$(run --base HEAD)
grep -q 'POLICY-SKIP: ai/yolo26/test_probe.py' <<<"$OUT" \
  && pass "POLICY-SKIP printed for ai/" || fail "POLICY-SKIP missing: $OUT"
grep -q 'docs/probe.md' <<<"$OUT" && fail "docs/ should be silent" || pass "docs/ silent"
grep -q 'frontend/probe.ts' <<<"$OUT" && fail "frontend/ should be silent" || pass "frontend/ silent"
rm -rf ai/yolo26/test_probe.py docs/probe.md frontend/probe.ts

# ---------- case 10: untracked new backend module (no git add) ----------
echo "[case 10] untracked new backend module appears (ls-files --others seam)"
printf 'class New: ...\n' > backend/services/brand_new.py
OUT=$(run --base HEAD)
grep -q 'UNMAPPED: backend/services/brand_new.py' <<<"$OUT" \
  && pass "untracked module surfaced (UNMAPPED)" || fail "untracked module missing: $OUT"
reset_tree

rm -rf "$R"

# ---------- runner safe-paths (execute ONLY branches that never launch pytest/npx) ----------
# The lease forbids pytest/vitest/npx. These cases exercise the runners' GUARD
# branches only: empty-list early exit, zero-frontend-change early exit (both
# exit before any xargs/npx line), and the set-e fail-loud on a bad base ref.
echo "[case 11] fast-backend-runner.sh empty-list guard (never reaches pytest)"
R2=$(mktemp -d /tmp/wave3-runner.XXXX)
git init -q "$R2" && git -C "$R2" config user.email t@t && git -C "$R2" config user.name t
: > "$R2/empty.txt"
OUT=$(cd "$R2" && sh /tmp/wave3-drafts/t10/new-files/scripts/fast-backend-runner.sh empty.txt); RC=$?
[ "$RC" -eq 0 ] && grep -q '0 files selected' <<<"$OUT" \
  && pass "empty list -> rc=0, nothing-affected line" || fail "rc=$RC out=$OUT"

echo "[case 12] fast-frontend-runner.sh zero-frontend-change guard (never reaches npx)"
git -C "$R2" commit -q --allow-empty -m base
# The runner cd's to its own repo root — install a copy inside the fixture repo.
mkdir -p "$R2/scripts"
cp /tmp/wave3-drafts/t10/new-files/scripts/fast-frontend-runner.sh "$R2/scripts/"
OUT=$(cd "$R2" && sh scripts/fast-frontend-runner.sh HEAD); RC=$?
[ "$RC" -eq 0 ] && grep -q 'SELECTED-FRONTEND-FILES: 0' <<<"$OUT" \
  && pass "no frontend changes -> count 0, rc=0" || fail "rc=$RC out=$OUT"

echo "[case 13] fast-frontend-runner.sh bad base ref fails loud (rc=2, not silent-empty)"
OUT=$(cd "$R2" && sh scripts/fast-frontend-runner.sh refs/heads/nope 2>&1); RC=$?
[ "$RC" -eq 2 ] && pass "rc=2 on bad ref" || fail "expected rc=2, got rc=$RC: $OUT"

echo "[case 14] fast-frontend-runner.sh CONFIGY notice path (src-only selectable filter; no npx: SELECTABLE empty)"
mkdir -p "$R2/frontend"
git -C "$R2" commit -q --allow-empty -m b2
echo '{"x":1}' > "$R2/frontend/package.json"
OUT=$(cd "$R2" && sh scripts/fast-frontend-runner.sh HEAD~1 2>&1); RC=$?
grep -q 'config-class changes' <<<"$OUT" && grep -q 'package.json' <<<"$OUT" \
  && pass "config-class change routed to notice + count 0 (rc=$RC)" || fail "notice path: rc=$RC out=$OUT"
rm -rf "$R2"

echo "=================================="
[ "$FAIL" -eq 0 ] && echo "LOGIC-SMOKE: ALL PASS" || echo "LOGIC-SMOKE: FAILURES PRESENT"
exit $FAIL

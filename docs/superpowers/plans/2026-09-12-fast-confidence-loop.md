# Fast Confidence Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax to track progress.

**Goal:** a small change earns local test confidence in ≤10 minutes (`validate.sh --fast`), the full gate keeps byte-identical strictness off the developer's critical path, and CI becomes truthful enough to delegate the full run to.

**Architecture:** three moves from the spec: (1) finish the test substrate the repo already designed — per-worker Postgres databases, per-worker Redis logical DBs, env-driven frontend parallelism; (2) tier the gates — a new change-scoped `--fast` mode additive to `scripts/validate.sh`; (3) honest CI — remove the exit-0-on-first-summary hack and the no-pipefail retry mask, add a collection-sanity gate and a nightly full run.

**Tech Stack:** Python 3.11+/pytest/pytest-xdist/psycopg2, vitest 4.0.18, POSIX `sh` (validate.sh), GitHub Actions YAML.

**Spec:** `docs/superpowers/specs/2026-09-12-fast-confidence-loop-design.md` — the spec is the authority; this plan is its argument. Spec §9 sequencing is binding: **execution begins only after M1 close-out** (M1's final no-flag `validate.sh` run recorded green in the M1 ledger).

## Global Constraints

- Nothing in this plan merges while M1's final no-flag `validate.sh` run is outstanding (spec §9). Execution order inside the plan follows spec §9: Tasks 1–4 (honest-CI + frontend envs, no substrate dependency) → Tasks 5–8 (per-worker PG) → Task 9 (per-worker Redis) → Tasks 10–13 (`--fast` tier) → Task 14 (nightly) → Task 15 (measurement record).
- Full-gate strictness is **byte-identical** except for exactly two sanctioned deltas, each recorded with a before/after quote in its commit message: (a) frontend test runs may gain env-var-prefix and `--maxWorkers` additions that are no-ops when the envs are unset (Task 3 — CI leaves both unset, so the CI invocation stays byte-identical); (b) the `--dist=loadgroup` flag is removed from `scripts/validate.sh` **only if M1 shipped it** and the green-×2 condition holds (Task 8). Today's tree (post `c29c319b`) has no `--dist` flag in validate.sh — verify with `grep -n 'dist=' scripts/validate.sh` before assuming either way.
- No coverage-bar movement, no test deletion, no `.skip`, no assertion contortion (spec §7). The M1 escalation rules transplant verbatim.
- No production runtime code changes: all substrate work is confined to `backend/tests/`, `frontend/vite.config.ts` (test block only), `scripts/`, and `.github/workflows/`. No `docker-compose.prod.yml` edits.
- `scripts/validate.sh` is `#!/bin/sh` POSIX — no bashisms (no arrays, no `[[ ]]`, no `local` in new code paths that run under `sh`). The pyproject `testpaths` spans `backend/tests`, `ai/*/tests`, `setup_lib/tests` — the fast-tier backend selector is scoped to `backend/**` changes by policy and prints what it skipped.
- Every commit message ends with the `Co-Authored-By: Claude Code <noreply@anthropic.com>` trailer.
- CI workflow edits keep the repo's sha-pinned action style (`actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4`, `astral-sh/setup-uv@e4db8464a088ece1b920f60402e813ea4de65b8f # v4`).

## File Structure

New files:

| File | Responsibility |
| --- | --- |
| `scripts/check-test-collection.py` | Collection-sanity gate: zero-byte tracked test files + zero-test collected files (spec §5.3). stdlib-only; `--allow` is emergency-only and must carry a tracking ref in-file. |
| `scripts/test_check_test_collection.py` | Its unit tests (lives in `scripts/`, outside pytest `testpaths`, so it never self-collects; run explicitly). |
| `.github/workflows/flake-allowlist.yml` | The single registered-flake list (test-id → tracking ref + expiry), machine-readable, grepped at load by callers. |
| `scripts/check-flake-allowlist.py` | Allowlist hygiene: every entry has a tracking ref + parseable ISO expiry; expired ⇒ nonzero. |
| `scripts/test_check_flake_allowlist.py` | Its unit tests. |
| `backend/tests/test_db_isolation.py` | Contract tests for the per-worker PG + Redis isolation machinery (tasks 5–9). Name matches `python_files = ["test_*.py"]`; lands in the already-collected `backend/tests` root (1 sibling: `test_utils.py`). |
| `scripts/fast_select.py` | Backend change→test selection: dotted-import + patch-string resolution over a `git ls-files` candidate set (spec §4.1's proximity table realized by import truth — the fact-sweep showed filename mirroring silently drops 9 route + 18 service modules, and lazy imports/patch-strings defeat top-level-import scans). Directory policy for `backend/api/**` (contracts + security smoke). |
| `scripts/test_fast_select.py` | Its unit tests. |
| `scripts/fast-backend-runner.sh` | Runs the selected backend set with `--dist=loadgroup` + `-p no:randomly` + no-cov (selection is position-dependent under `-p randomly`, so fast-tier selection and fast-tier run must agree on ordering determinism). |
| `scripts/fast-frontend-runner.sh` | `vitest related --run` wrapper: NODE_OPTIONS wrapper replication, changed-file filtering to `frontend/`, selection-count parsing (a zero-selection related run exits 0 — exit code alone cannot distinguish "nothing affected" from "all green"). |
| `scripts/fast-validation-playbook.sh` | The §6.3 scripted 5-change playbook with per-change timing + wall assertions. |
| `.github/workflows/nightly-full-validation.yml` | Nightly no-flag full-gate run + job summary (spec §5.4). |
| `docs/development/fast-confidence-loop-measurements.md` | Before/after numbers per spec §6; the M1 CI-blind-spot findings ride along. |

Modified files (line anchors are post-`c29c319b`/`f2b941f4` positions — re-grep before editing):

| File | Change |
| --- | --- |
| `.github/workflows/ci.yml` | §5.2 retry-mask removal (4 integration sites), §5.1 frontend hack replacement + pipefail, §5.3 collection-sanity steps, allowlist wiring |
| `frontend/vite.config.ts` | test block only: env-driven `fileParallelism`/`maxWorkers`/`minWorkers` (Task 3); `--testPool` CLI override (Task 4) |
| `scripts/validate.sh` | frontend heap envs (Task 3); `--fast` flag + `run_fast_validation()` dispatch (Task 13) |
| `backend/tests/conftest.py` | per-worker DB + Redis isolation (Tasks 6–7, 9) |
| `scripts/AGENTS.md` + validate.sh header/help | `--fast` documented in all three places the flags are documented (the existing script documents flags in header :10-14, `show_help`, and AGENTS.md — keep all three in sync) |

`frontend/AGENTS.md` — no change required: it does not document the test scripts or validate.sh flags (checked at plan time); if the executor finds it does, update it there too.

---

## Phase A — Honest CI + frontend parallelism (no substrate dependency)

### Task 1: Collection-sanity gate (spec §5.3)

Makes the zero-byte-tracked-test-file class red within one push. The class is proven live: a zero-byte test file made vitest exit 1 (M1 R-T7 gate-impact probe), yet nothing on CI detected it.

**Files:**
- Create: `scripts/check-test-collection.py`
- Test: `scripts/test_check_test_collection.py` (run explicitly: `uv run pytest scripts/test_check_test_collection.py`)
- Modify: `.github/workflows/ci.yml` — new `collection-sanity` job placed before `unit-tests-summary`'s `needs` chain consumes results (add it as a `needs` entry of `unit-tests-summary`, `integration-tests-summary`, and `frontend-tests-summary` so its red reaches `ci-gate`)

**Interfaces:**
- Consumes: nothing (fresh script, stdlib-only).
- Produces: exit 0 clean / exit 1 findings on stderr; `--allow id1,id2` emergency opt-out; the `collection-sanity` CI job both later tasks' injected-failure acceptance runs lean on.

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_check_test_collection.py`:

```python
"""Tests for scripts/check-test-collection.py (run explicitly; outside testpaths)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "check-test-collection.py"


def run_script(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=tmp_path, check=False,
    )


@pytest.fixture()
def git_tree(tmp_path: Path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=tmp_path, check=True)
    return tmp_path


def stage_and_note(git_tree: Path, rel: str, content: bytes) -> None:
    p = git_tree / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    subprocess.run(["git", "add", "--", rel], cwd=git_tree, check=True)


def test_clean_tree_passes(git_tree):
    stage_and_note(git_tree, "backend/tests/unit/test_ok.py", b"def test_a():\n    assert True\n")
    r = run_script(git_tree, "backend/tests")
    assert r.returncode == 0, r.stderr


def test_zero_byte_python_test_detected(git_tree):
    stage_and_note(git_tree, "backend/tests/unit/test_empty.py", b"")
    r = run_script(git_tree, "backend/tests")
    assert r.returncode == 1
    assert "test_empty.py" in r.stderr + r.stdout


def test_zero_byte_ts_test_detected(git_tree):
    stage_and_note(git_tree, "frontend/src/a.test.ts", b"")
    r = run_script(git_tree, "frontend/src")
    assert r.returncode == 1
    assert "a.test.ts" in r.stderr + r.stdout


def test_def_only_py_collects_zero_tests_detected(git_tree):
    stage_and_note(
        git_tree, "backend/tests/unit/test_helpers_only.py",
        b"def helper():\n    return 1\n",
    )
    r = run_script(git_tree, "backend/tests")
    assert r.returncode == 1
    assert "test_helpers_only.py" in r.stderr + r.stdout


def test_allow_suppresses(git_tree):
    stage_and_note(git_tree, "backend/tests/unit/test_empty.py", b"")
    r = run_script(git_tree, "backend/tests", "--allow", "backend/tests/unit/test_empty.py")
    assert r.returncode == 0


def test_ignores_untracked(git_tree):
    p = git_tree / "backend/tests/unit/test_scratch.py"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"")  # never git-added
    r = run_script(git_tree, "backend/tests")
    assert r.returncode == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest scripts/test_check_test_collection.py -v -p no:randomly -o addopts=""`
Expected: FAIL — all five fail because `check-test-collection.py` does not exist (subprocess exits 2 with "No such file"). Note `-o addopts=""`: the repo's global pytest addopts (`-n 8 --dist=worksteal -v --strict-markers -p randomly`) would otherwise apply here; the script's own CI job invokes it the same way.

- [ ] **Step 3: Write the script**

Create `scripts/check-test-collection.py`:

```python
#!/usr/bin/env python3
"""Collection-sanity gate (fast-confidence-loop spec SS5.3).

Fails when any TRACKED test file is zero bytes, or collects zero tests.
Three zero-byte test files sat undetected on main during M1 because the
frontend CI job exit-0s on its first summary line; this script makes that
state red within one push, independently of any job-level hack.

Usage: check-test-collection.py PATH [PATH ...] [--allow ID[,ID...]]
Exit: 0 clean, 1 findings, 2 operational error (git missing, collection crash).
--allow is emergency-only: each allowed id must also appear in
.github/workflows/flake-allowlist.yml with a tracking ref (enforced in Task 2).
"""
from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

PY_SUFFIXES = (".py",)
JS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx")


def tracked_files(roots: list[str]) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z", *roots], capture_output=True, text=True, check=True
    )
    return [Path(p) for p in out.stdout.split("\0") if p]


def is_test_file(p: Path) -> bool:
    name = p.name
    if p.suffix in PY_SUFFIXES:
        return name.startswith("test_")
    if p.suffix in JS_SUFFIXES:
        return ".test." in name or ".spec." in name
    return False


def py_collects_tests(p: Path) -> tuple[bool, str | None]:
    """(ok, reason). AST heuristic: file must define a Test* class or test_* function.

    Deliberately syntactic: import-time side effects (env probes, container
    boots) make real collection too slow/expensive for a preflight. A file
    that defines tests but errors on import stays this gate's blind spot by
    design; the pytest jobs catch that class.
    """
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as exc:
        return True, f"SyntaxError: {exc}"
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            return True, None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            return True, None
    return True, "no test_* function or Test* class defined"


def findings_for(paths: list[Path]) -> list[str]:
    out = []
    for p in paths:
        if not is_test_file(p):
            continue
        try:
            size = p.stat().st_size
        except FileNotFoundError:
            continue  # tracked-but-deleted in this worktree: not this gate's problem
        if size == 0:
            out.append(f"{p}: zero bytes")
        elif p.suffix in PY_SUFFIXES:
            ok, reason = py_collects_tests(p)
            if reason:
                out.append(f"{p}: {reason}")
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--allow", default="", help="comma-separated emergency opt-outs")
    args = ap.parse_args(argv[1:])
    allowed = {a.strip() for a in args.allow.split(",") if a.strip()}
    files = tracked_files(args.roots)
    findings = [f for f in findings_for(files) if f.split(":", 1)[0] not in allowed]
    for f in findings:
        print(f"COLLECTION-SANITY: {f}", file=sys.stderr)
    if findings:
        print(
            f"COLLECTION-SANITY: {len(findings)} file(s) would collect zero tests. "
            "Write tests, delete the file, or add an allowlist entry with a tracking ref.",
            file=sys.stderr,
        )
        return 1
    print(f"collection-sanity: {len(files)} tracked files scanned, all collect >= 1 test")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest scripts/test_check_test_collection.py -v -p no:randomly -o addopts=""`
Expected: PASS (6 tests).

- [ ] **Step 5: Prove it against the live repo (expect GREEN — the three M1 zero-byte files were quarantined, not deleted; verify they are still non-zero)**

```bash
uv run python scripts/check-test-collection.py backend frontend && echo GATE-OK
```
Expected: exit 0. If it reports findings, those are real §5.3-class findings — stop and adjudicate, do not `--allow` past them at first discovery.

- [ ] **Step 6: Add the CI job**

In `ci.yml`, after the `detect-changes` job, add (jobs are name-keyed; placement is cosmetic):

```yaml
  collection-sanity:
    name: Collection Sanity (zero-byte / zero-test tracked files)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4
      - uses: astral-sh/setup-uv@e4db8464a088ece1b920f60402e813ea4de65b8f # v4
      - name: Check tracked test files collect real tests
        run: uv run --no-project python scripts/check-test-collection.py backend frontend
```

Then add `collection-sanity` to the `needs:` lists of `unit-tests-summary`, `integration-tests-summary`, and `frontend-tests-summary` (each `needs:` line is a YAML list — append the entry; grep `needs:` to find all three). This makes its red reach `ci-gate`.

- [ ] **Step 7: Validate the workflow parses and commit**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo YAML-OK
git add scripts/check-test-collection.py scripts/test_check_test_collection.py .github/workflows/ci.yml
git commit -m "ci: collection-sanity gate for zero-byte/zero-test tracked test files (spec 5.3)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

GOTCHAS for this task: the AST heuristic means a py file that imports fine but parametrize-errors is invisible here (documented in the docstring — deliberate, the pytest jobs own that class); JS zero-test detection is zero-byte-only in v1 because vitest collection requires node_modules boot (a `vitest list --json` pass was rejected as slow and crashy as a preflight — recorded as the deliberate v1 limit, matching spec §5.3's proven zero-byte class).
---

### Task 2: Flake allowlist + teardown of the four retry-mask sites (spec §5.2)

The fact-sweep produced a sharper finding than the spec assumed: of the five `exit 0` line numbers the spec cites, **only four are in-loop retry exit-0s** (`ci.yml:462` api, `:573` websocket, `:690` services, `:799` models — the fifth, `:360`, is `unit-tests-summary`'s legitimate "tests were skipped, treat as pass" branch and stays). And the api job's retry loop is **dead code today**: `if uv run pytest ... | tee test-output.log; then` has no `set -o pipefail` anywhere in ci.yml, so the `if` tests `tee`'s status (always 0) and attempt 1 exits 0 **unconditionally**, even with every test failing. The teardown therefore both restores honesty and removes a mask that never let the retries matter.

**Files:**
- Create: `.github/workflows/flake-allowlist.yml`
- Create: `scripts/check-flake-allowlist.py`
- Test: `scripts/test_check_flake_allowlist.py`
- Modify: `.github/workflows/ci.yml:436-470` (api retry step), `:555-580` (websocket), `:671-697` (services), `:781-806` (models)

**Interfaces:**
- Consumes: Task 1's job-placement pattern (same needs-chain wiring — none needed here; the integration jobs already reach `integration-tests-summary`).
- Produces: the allowlist file (canonical list at `.github/workflows/flake-allowlist.yml`), the `apply-flake-reruns` step convention that Task 4's frontend job references, and the allowlist-hygiene job.

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_check_flake_allowlist.py`:

```python
"""Tests for scripts/check-flake-allowlist.py (run explicitly; outside testpaths)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "check-flake-allowlist.py"
REPO_ALLOWLIST = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "flake-allowlist.yml"


def run_on(tmp_path: Path, body: str) -> subprocess.CompletedProcess:
    al = tmp_path / "allowlist.yml"
    al.write_text(body, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(al), "--today", "2026-10-01"],
        capture_output=True, text=True, check=False,
    )


def test_valid_entry_passes(tmp_path):
    r = run_on(tmp_path, "flakes:\n  - id: test_foo\n    tracking: NEM-9999\n    expires: 2026-12-31\n")
    assert r.returncode == 0, r.stderr


def test_missing_tracking_fails(tmp_path):
    r = run_on(tmp_path, "flakes:\n  - id: test_foo\n    expires: 2026-12-31\n")
    assert r.returncode == 1
    assert "tracking" in r.stderr.lower()


def test_missing_expiry_fails(tmp_path):
    r = run_on(tmp_path, "flakes:\n  - id: test_foo\n    tracking: NEM-1\n")
    assert r.returncode == 1


def test_expired_entry_fails(tmp_path):
    r = run_on(tmp_path, "flakes:\n  - id: test_foo\n    tracking: NEM-1\n    expires: 2026-09-01\n")
    assert r.returncode == 1
    assert "expired" in r.stderr.lower()


def test_repo_allowlist_is_valid_today():
    r = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False
    )
    assert r.returncode == 0, r.stderr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest scripts/test_check_flake_allowlist.py -v -p no:randomly -o addopts=""`
Expected: FAIL (script missing; repo-allowlist test fails on both missing file and missing default).

- [ ] **Step 3: Write the allowlist (empty list + format documentation)**

Create `.github/workflows/flake-allowlist.yml`:

```yaml
# Registered flaky tests — the ONLY tests CI may retry (fast-confidence-loop spec SS5.2).
# Policy: un-allowlisted failures fail once and stay failed. Every entry needs a
# tracking ref (Linear issue) and an ISO expiry; expired entries fail CI until
# re-registered or fixed (scripts/check-flake-allowlist.py enforces on every push).
# The integration jobs feed active ids to pytest via -k (see apply-flake-reruns step);
# an empty list means plain single-attempt runs everywhere.
flakes: []
# Example (do not re-add without a real flake and a Linear issue):
# flakes:
#   - id: test_websocket_reconnect_race
#     tracking: NEM-0000
#     expires: 2026-12-31
#     note: one line on root cause or investigation link
```

- [ ] **Step 4: Write the hygiene script**

Create `scripts/check-flake-allowlist.py`:

```python
#!/usr/bin/env python3
"""Flake-allowlist hygiene (fast-confidence-loop spec SS5.2/SS6.6).

Every entry must carry a tracking ref and a non-expired ISO date. An expired
entry fails until it is re-registered or removed — the expiry IS the enforcement.
Parses the YAML with a stdlib line reader (the list is flat and tiny; no PyYAML
dependency so the check runs anywhere, including before `uv sync`).

Usage: check-flake-allowlist.py [--file PATH] [--today YYYY-MM-DD]
Exit: 0 ok, 1 violations, 2 malformed file.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

DEFAULT_FILE = ".github/workflows/flake-allowlist.yml"
ENTRY_RE = re.compile(r"^\s*-\s+id:\s*(\S+)")
FIELD_RE = re.compile(r"^\s+(tracking|expires|note):\s*(.+?)\s*$")


def parse_allowlist(text: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in text.splitlines():
        m = ENTRY_RE.match(line)
        if m:
            entries.append({"id": m.group(1)})
            continue
        if entries:
            fm = FIELD_RE.match(line)
            if fm:
                entries[-1][fm.group(1)] = fm.group(2).strip("'\"")
    return entries


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--today", default="")  # test seam; real runs use system date
    args = ap.parse_args(argv[1:])
    path = Path(args.file)
    if not path.is_file():
        print(f"flake-allowlist: {path} missing", file=sys.stderr)
        return 2
    entries = parse_allowlist(path.read_text(encoding="utf-8"))
    today = (
        dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    )
    violations = []
    for e in entries:
        if not e.get("tracking"):
            violations.append(f"{e['id']}: missing tracking ref")
        raw_exp = e.get("expires", "")
        try:
            exp = dt.date.fromisoformat(raw_exp)
        except ValueError:
            violations.append(f"{e['id']}: missing/unparseable expires date")
            continue
        if exp < today:
            violations.append(f"{e['id']}: expired {exp} — fix or re-register")
    for v in violations:
        print(f"flake-allowlist: {v}", file=sys.stderr)
    if violations:
        return 1
    print(f"flake-allowlist: {len(entries)} entries, all registered and unexpired")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest scripts/test_check_flake_allowlist.py -v -p no:randomly -o addopts=""`
Expected: PASS (6 tests).

- [ ] **Step 6: Teardown the four retry sites in ci.yml**

Each of the four steps collapses from the 3-attempt loop to a single honest run. **API job** (`Run API integration tests with retry`, ci.yml:436-470) becomes:

```yaml
      - name: Run API integration tests
        run: |
          set -euo pipefail
          START_TIME=$(date +%s)
          RERUNS=""
          if [ -f .github/workflows/flake-allowlist.yml ]; then
            RERUNS=$(uv run --no-project python scripts/flake-k-filter.py 2>/dev/null || true)
          fi
          if [ -n "$RERUNS" ]; then
            echo "Rerunning registered flakes: $RERUNS"
            uv run pytest backend/tests/integration/ -k "$RERUNS" -n0 --timeout=30 \
              --reruns 2 --reruns-delay 5 || true
          fi
          if uv run pytest backend/tests/integration/ \
            -k "test_admin_api or test_ai_audit_api or test_alerts_api or test_api_error_scenarios or test_api_errors or test_audit_api or test_cameras_api or test_detections_api or test_dlq_api or test_entities_api or test_events_api or test_http_error_codes or test_logs_api or test_media_api or test_media_security or test_metrics_api or test_notification_api or test_search_api or test_system_api or test_video_streaming or test_zones_api or test_api" \
            -n auto \
            --timeout=30 \
            --cov=backend \
            --cov-fail-under=0 \
            --cov-report=xml:coverage-integration-api.xml \
            --cov-report=term-missing \
            --junit-xml=test-results-integration-api.xml \
            --durations=20 \
            -v 2>&1 | tee test-output.log; then
            END_TIME=$(date +%s)
            DURATION=$((END_TIME - START_TIME))
            WORKERS=$(grep -oP 'gw\d+' test-output.log | sort -u | wc -l || echo "unknown")
            echo "::notice::API Integration Tests completed in ${DURATION}s using ${WORKERS} workers"
            exit 0
          fi
          exit 1
```

`set -euo pipefail` is the load-bearing line: with it, `if pytest | tee` finally tests **pytest's** status. The `-k` keyword list is preserved verbatim; the loop, both `echo "::endgroup::"` wrappers, and the `sleep 10` retry scaffolding are deleted. Create `scripts/flake-k-filter.py` (6-line stdlib script: reads the allowlist YAML via the same line parse as Task 2's hygiene script, prints ids joined by ` or `, prints empty string when the list is empty):

```python
#!/usr/bin/env python3
"""Print allowlist flake ids as a pytest -k expression ('' when none)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_flake_allowlist_lib import active_ids  # noqa: E402

print(" or ".join(active_ids()))
```

**Correction — keep it one file:** inline instead of a lib import (the repo has no `check_flake_allowlist_lib`): copy the 15-line `parse_allowlist` from `check-flake-allowlist.py` into `flake-k-filter.py` as a local function and filter by expiry there; both scripts stay standalone (duplication of a 15-line parser across two scripts is the accepted trade for stdlib-only zero-import coupling; a shared module under `scripts/` would need an importable-package decision this plan deliberately avoids). The registered-flake pre-run (`--reruns 2 ... || true`) only executes when the allowlist is non-empty; today it is `flakes: []`, so the step is a no-op and behavior is single-attempt honest everywhere.

The **websocket** (`:555-580`), **services** (`:671-697`), and **models** (`:781-806`) sites follow the identical shape with their own verbatim `-k` lists preserved (websocket: `test_websocket or test_system_broadcaster or test_redis_pubsub`, `-n0`, `--junit-xml coverage-integration-websocket.xml` — note this site passes the junit filename as `coverage-integration-websocket.xml` today; leave the filename as-is, renaming artifacts is out of scope); services and models keep their `-n0` and their keyword lists verbatim; none of the three had `tee` or the WORKERS notice. For each: delete `for attempt in 1 2 3; do`, both retry `echo`/`sleep 10` blocks, and the trailing `exit 1`-after-loop, keep one run under `set -euo pipefail`, and rename the step from "…with retry" to "Run … tests".

- [ ] **Step 7: Wire the hygiene check into CI**

Add to the existing `collection-sanity` job (from Task 1) a second step:

```yaml
      - name: Flake allowlist hygiene
        run: uv run --no-project python scripts/check-flake-allowlist.py
```

- [ ] **Step 8: Validate + commit**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); yaml.safe_load(open('.github/workflows/flake-allowlist.yml'))" && echo YAML-OK
grep -c 'for attempt in 1 2 3' .github/workflows/ci.yml   # expect 0
grep -n 'set -euo pipefail' .github/workflows/ci.yml | head   # expect the 4 rewritten steps
git add .github/workflows/flake-allowlist.yml scripts/check-flake-allowlist.py scripts/flake-k-filter.py scripts/test_check_flake_allowlist.py .github/workflows/ci.yml
git commit -m "ci: replace blanket integration retry masks with registered-flake allowlist (spec 5.2)

Teardown note: the api job's `if pytest | tee` had no pipefail, so the retry
loop's attempt-1 exit 0 fired unconditionally (mask, not retry). Restores real
exit codes; retries now only for allowlisted ids (list currently empty).

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

GOTCHAS: the three non-api sites DID retry honestly today (no `tee`), so their teardown is a behavior change from ×3-attempt to ×1 — that is the spec's intent ("fail once and stay failed"), but expect first-run red on CI flakes that previously got retried away; each such failure is either a genuine §3-class substrate finding (route it to Tasks 5–9) or the allowlist's first real entries. `pytest-rerunfailures` is already a dev dependency (`pyproject.toml:105`) and every backend job installs with `uv sync --extra dev --frozen`, so `--reruns` needs no new dependency. The `--reruns` flag never existed in ci.yml before (grep-verified); this introduces it only behind the allowlist.

---

### Task 3: Machine-aware frontend parallelism (spec §3.3, config + validate.sh)

**Files:**
- Modify: `frontend/vite.config.ts` (test block, :370-384 region)
- Modify: `scripts/validate.sh` (frontend vitest step, :403-407 region)

**Interfaces:**
- Consumes: nothing.
- Produces: `VITEST_PARALLEL` / `VITEST_MAX_WORKERS` / `VITEST_HEAP_MB` env contract (used by Task 4's CI job, Task 12's fast runner, and the §6.2 acceptance measurement); the validate.sh RAM-detection block.

- [ ] **Step 1: Edit the vite config test block**

In `frontend/vite.config.ts`, replace (`:372-378` region; `loadEnv` is already imported at :1 — the test block is inside `defineConfig`, so resolve envs at config scope where `mode` is available, or simpler: read `process.env` directly — the three vars are process-level intent flags, not Vite-mode envs, and the CI/npm paths all pass them as real env vars):

```ts
      pool: 'forks',
      // Machine-aware parallelism (fast-confidence-loop spec SS3.3).
      // Default is the inherited CI-safe setting: sequential files in each
      // shard, small heap. VITEST_PARALLEL=1 (set by validate.sh on big boxes,
      // and by CI only if a measured runner OOM is being worked around) turns
      // on file-parallelism with a bounded worker count.
      fileParallelism: process.env.VITEST_PARALLEL === '1',
      maxWorkers: Number(process.env.VITEST_MAX_WORKERS ?? 4),
      minWorkers: 1,
      // Restart worker after each test file to prevent memory accumulation
      // This is critical for preventing OOM during long test runs
      isolate: true,
```

(The two existing comments above `pool: 'forks'` stay; the `// Run test files sequentially...` comment that sat above `fileParallelism: false` is replaced by the block comment above.)

- [ ] **Step 2: Edit validate.sh's frontend test step**

In `scripts/validate.sh`, replace:

```sh
    # Run tests
    print_step "Running Vitest (Tests)..."
    if ! npm run test --prefix "$FRONTEND_DIR" -- --run; then
```

with:

```sh
    # Run tests
    print_step "Running Vitest (Tests)..."
    # Machine-aware test execution (fast-confidence-loop spec SS3.3): boxes with
    # >=64 GB RAM run files in parallel with a bigger heap; small/CI runners
    # keep the inherited sequential + 8 GB settings byte-identically.
    MEM_KB=$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || echo 0)
    if [ "${VITEST_PARALLEL:-}" != "0" ] && [ "$MEM_KB" -ge 67108864 ]; then
        export VITEST_PARALLEL=1
        export VITEST_MAX_WORKERS="${VITEST_MAX_WORKERS:-8}"
        export VITEST_HEAP_MB="${VITEST_HEAP_MB:-16384}"
        print_info "Parallel vitest: ${VITEST_MAX_WORKERS} workers, ${VITEST_HEAP_MB} MB heap (RAM $((MEM_KB / 1048576)) GB)"
    fi
    if ! VITEST_HEAP_MB="${VITEST_HEAP_MB:-8192}" npm run test --prefix "$FRONTEND_DIR" -- --run; then
```

and in `frontend/package.json` change the `test` script (:19) from

```json
    "test": "NODE_OPTIONS='--max-old-space-size=8192' vitest",
```

to

```json
    "test": "NODE_OPTIONS=\"--max-old-space-size=${VITEST_HEAP_MB:-8192}\" vitest",
```

and give `test:coverage` (:21) the same wrapper substitution. `print_info` already exists in validate.sh's helper block (grep `print_info` to confirm the exact name — if the helper is named differently, use the file's existing info-level printer).

- [ ] **Step 3: Verify default-off is byte-identical behavior**

```bash
cd frontend && env -u VITEST_PARALLEL npx vitest related --run src/hooks/useAlertsQuery.ts 2>&1 | tail -5
```
Expected: run completes (exit 0; related selects useAlertsQuery's tests), and while it runs, a concurrent `ps -eo comm,args | awk '$1=="node"' | grep -c vitest` shows ≤1 fork at a time (sequential = inherited default preserved).

- [ ] **Step 4: Verify parallel-on works and is faster**

```bash
cd frontend && VITEST_PARALLEL=1 VITEST_MAX_WORKERS=8 VITEST_HEAP_MB=16384 \
  npx vitest run src/components/dashboard src/hooks --reporter=basic 2>&1 | tail -4
```
Expected: green, noticeably faster than the same command without the envs (time both with `time`; record both numbers in the measurements doc, Task 15). On the 72-core box expect 3–6×; if heap-related failures appear, they are §3.3-class findings for this task's review, not noise.

- [ ] **Step 5: Commit**

```bash
git add frontend/vite.config.ts frontend/package.json scripts/validate.sh
git commit -m "config(frontend): env-driven fileParallelism/maxWorkers/heap (spec 3.3)

Defaults unchanged (sequential, 8 GB) so CI is byte-identical; validate.sh
opts in automatically on >=64 GB boxes.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

GOTCHAS: `Number('')` is 0 — if someone exports `VITEST_MAX_WORKERS=` (empty), maxWorkers 0 means "unbounded" in vitest and could fork-bomb a CI runner; the `?? 4` fallback only covers unset, so use `|| 4` semantics: `Number(process.env.VITEST_MAX_WORKERS || 4)`. The `/proc/meminfo` read is Linux-only — macOS dev boxes fall to `echo 0` → sequential (safe direction, correct failure). validate.sh runs `#!/bin/sh`; the `[ "$MEM_KB" -ge ... ]` numeric compare is POSIX (works because MemTotal is pure digits). The `test` script's quoted-NODE_OPTIONS rewrite must survive npm's shell (`sh -c`) — double quotes + `${VAR:-default}` is the portable form; `sh -c 'NODE_OPTIONS="--max-old-space-size=${VITEST_HEAP_MB:-8192}" vitest run src/App.test.tsx'`-style manual check in Step 3's tail output implicitly proves it (heap errors would appear immediately on a big file otherwise).

---

### Task 4: Frontend CI job honesty — replace the exit-0-on-first-summary hack (spec §5.1)

**Files:**
- Modify: `.github/workflows/ci.yml:1296-1321` (the background-run + polling-kill step) and the job env block `:1240-1244`

**Interfaces:**
- Consumes: Task 3's env contract (`VITEST_PARALLEL`, `VITEST_MAX_WORKERS` — read by `frontend/vite.config.ts` regardless of whether vitest is invoked via npm or npx; the heap cap in CI travels via `NODE_OPTIONS` because the step calls `npx` directly, which bypasses the npm-script wrapper).
- Produces: a frontend job whose red/green is truthful — required before Task 14's nightly and the §6.4 acceptance can mean anything; the §6 acceptance test ("injected failing test turns the job red").

- [ ] **Step 1: Replace the hack step**

Replace the current step (background `npx vitest run ... | tee & ` + polling grep + `pkill -9` + `exit 0`, ci.yml:1299-1320) with:

```yaml
      # Real exit code (fast-confidence-loop spec SS5.1). The previous step
      # grepped for the first 'passed' summary line, SIGKILLed vitest, and
      # exit 0'd — an OOM workaround that also hid every failing frontend
      # test (the R-T7-VITEST class). The OOM (old comment: "cleanup takes
      # 5+ minutes and OOMs") is instead bounded at the settings level:
      # 16 shards, at most 2 concurrent forks, 4 GB heap each, teardown
      # capped at 1 s. If a runner OOM recurs anyway that is evidence for a
      # runner-size conversation (spec SS5.5), not for restoring the hack.
      - name: Run tests (real exit code)
        env:
          VITEST_PARALLEL: '1'
          VITEST_MAX_WORKERS: '2'
        run: |
          set -euo pipefail
          npx vitest run --shard=${{ matrix.shard }}/16 \
            --reporter=default --teardownTimeout=1000 2>&1 | tee /tmp/vitest-shard.log
        shell: bash
```

And change the job-level env block (`:1240-1244`, `NODE_OPTIONS: '--max-old-space-size=6144 --expose-gc'`) to:

```yaml
    env:
      NODE_VERSION: '20'
      # 4 GB per fork now that up to 2 forks run per shard (spec 5.1); the old
      # single-fork 6144 MB setting assumed sequential files and OOMed anyway.
      NODE_OPTIONS: '--max-old-space-size=4096 --expose-gc'
```

`set -euo pipefail` makes vitest's exit status the step's status (the old fallback path `wait $vitest_pid; exit $?` at :1319-1320 and the polling loop at :1304-1313 are deleted with the step). Worst-case shard memory: 2 forks × 4 GB ≈ 8 GB on a 16 GB `ubuntu-latest`, with the sequential-shard legacy (fileParallelism) one notch up and shard lifetime short.

- [ ] **Step 2: Prove the job logic locally at shard scale**

The CI step can't run in GH Actions from here, but its exact shape can be proven on a 1/16 shard slice:

```bash
cd frontend && VITEST_PARALLEL=1 VITEST_MAX_WORKERS=2 sh -c '
  set -euo pipefail
  NODE_OPTIONS="--max-old-space-size=4096 --expose-gc" \
  npx vitest run --shard=1/16 --reporter=default --teardownTimeout=1000 2>&1 \
    | tee /tmp/vt-honest.log
  echo "STEP-WOULD-EXIT-0"'
```
Expected: `STEP-WOULD-EXIT-0` prints only on a green shard; watch peak RSS once with `ps -eo rss,comm,args | awk '$2>1000 && /vitest|node/' | sort -rn | head -3` mid-run (record in Task 15's doc). Then the injected-failure half of §6.4:

```bash
cd frontend
printf 'import { describe, it, expect } from "vitest";\ndescribe("injected", () => { it("fails on purpose", () => { expect(1).toBe(2); }); });\n' > src/injected-fail.probe.test.ts
VITEST_PARALLEL=1 VITEST_MAX_WORKERS=2 sh -c 'set -euo pipefail; NODE_OPTIONS="--max-old-space-size=4096" npx vitest run --shard=1/16 --reporter=default --teardownTimeout=1000 >/dev/null 2>&1; echo UNREACHED'; echo "exit=$?"
rm src/injected-fail.probe.test.ts
```
Expected: `UNREACHED` absent and `exit=1` **if shard 1/16 includes the probe** — vitest shards partition the sorted test-file list, and an added src-root test file may land in any shard. Iterate `--shard=k/16` (cheap: add `--reporter=basic` and stop at the first shard whose run lists `injected-fail`) until the injected file is selected, then assert nonzero. **The probe file must never be committed** — Step 4's commit list excludes it and Step 3 deletes it unconditionally.

- [ ] **Step 3: Delete the probe, verify tree clean**

```bash
rm -f src/injected-fail.probe.test.ts && git status --porcelain frontend/src | grep -c . || echo CLEAN
```
Expected: `CLEAN`.

- [ ] **Step 4: Validate YAML + commit**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo YAML-OK
git add .github/workflows/ci.yml
git commit -m "ci(frontend): real exit code replaces exit-0-on-first-summary hack (spec 5.1)

The OOM workaround (grep 'passed' -> pkill -9 -> exit 0, ci.yml:1304-1313)
made failing frontend tests invisible (R-T7-VITEST class). Bounds memory at
the execution-settings level instead: 16 shards x 2 forks x 4 GB heap, and
pipefail makes the shard's exit code the step's verdict.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

GOTCHAS: `VITEST_PARALLEL=1` + `VITEST_MAX_WORKERS=2` only take effect because Task 3 landed first (the config reads them) — if Task 3 is ever reverted, this step silently degrades to sequential files but stays honest (exit code unaffected). `--reporter=default` (not `verbose`) — the hack's regex dependency dies with the hack; nothing else in the job parses the output (the coverage merge job consumes the uploaded raw coverage artifact, `if: always()` at ci.yml:1323-1328, which is untouched). If the full 16-shard CI run OOMs anyway, the measured-exception path is `VITEST_PARALLEL: '0'` on this job only (back to sequential + 1 worker) with the OOM tracked — spec §5.1 names exactly that fallback; what is not permitted is restoring the kill-and-exit-0 hack. The matrix (1..16, `fail-fast: false`) at ci.yml:1234-1239 stays.
---

## Phase B — Per-worker Postgres isolation (spec §3.1)

The serialization root cause (ledger R-T7-DBRACE-FINAL): `get_test_db_url()` returns the exported `TEST_DATABASE_URL` **verbatim**, so all 8+ xdist workers share one database and every `test_db`/`isolated_db` invocation queues on `_reset_db_schema()`'s advisory lock. These tasks make each worker own a database. The integration tier's `_create_worker_database` already proves the mechanism in production use; the tasks below lift the pattern to the root conftest (where the unit tier lives) **without** importing across conftest boundaries (conftest files are loaded by pytest's importer under synthetic module names — cross-conftest imports are brittle; a small deliberate duplication of a proven pattern is the repo's established trade, same as `_get_advisory_lock_key` already being duplicated between the two conftests).

### Task 5: Isolation helpers + contract tests (pure functions first)

**Files:**
- Create: `backend/tests/test_db_isolation.py`
- Modify: `backend/tests/conftest.py` (add module-level helper functions near `get_test_db_url`, ~line 592 region; do NOT change `get_test_db_url` behavior yet)

**Interfaces:**
- Consumes: nothing new (psycopg2 already a dependency; `xdist` already imported at `backend/tests/integration/conftest.py:40`, root conftest does not yet import xdist).
- Produces: `worker_id()` (env-based, no fixture needed), `worker_db_name(base_url)`, `_create_worker_database(base_url, db_name)`, `_drop_worker_database(base_url, db_name)` in `backend/tests/conftest.py` — Task 6's `worker_database` session fixture and Task 9's Redis work consume them; `worker_redis_url_for(base_url)` lands in Task 9 (same test file extends).

- [ ] **Step 1: Write the failing contract tests**

Create `backend/tests/test_db_isolation.py`:

```python
"""Contract tests for per-worker test-database isolation (fast-confidence-loop SS3.1).

These assert the CONTRACT of the helper functions conftest grows, not fixture
behavior: name derivation must be deterministic per worker and collision-free
across workers; helpers must be idempotent and must refuse to drop protected
databases. Run live (helpers act on the real dev Postgres validate.sh exports).
"""
from __future__ import annotations

import os

import pytest

from backend.tests.conftest import (
    _create_worker_database,
    _drop_worker_database,
    worker_db_name,
    worker_id,
)

PROTECTED = ("security", "security_test", "postgres", "template1")


class TestWorkerId:
    def test_defaults_to_master_without_xdist(self, monkeypatch):
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        assert worker_id() == "master"

    def test_reads_env_under_xdist(self, monkeypatch):
        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw3")
        assert worker_id() == "gw3"


class TestWorkerDbName:
    def test_master_gets_deterministic_name(self, monkeypatch):
        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        name = worker_db_name("postgresql+asyncpg://u:p@localhost:5432/base")
        assert name.endswith("_main")
        assert len(name) <= 63  # NAMEDATALEN limit

    def test_gw_suffix_applied(self, monkeypatch):
        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw7")
        name = worker_db_name("postgresql+asyncpg://u:p@localhost:5432/base")
        assert name.endswith("_gw7")

    def test_distinct_across_workers(self, monkeypatch):
        names = set()
        for wid in ("master", "gw0", "gw1", "gw14", "gw15"):
            monkeypatch.setenv("PYTEST_XDIST_WORKER", wid)
            name = worker_db_name("postgresql+asyncpg://u:p@localhost:5432/base_db")
            assert name not in names, f"collision at {wid}: {name}"
            names.add(name)

    def test_sanitized_prefix_from_base(self, monkeypatch):
        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
        name = worker_db_name("postgresql+asyncpg://u:p@h:5432/Security_DB-1")
        assert name.startswith("security_db_1_")
        assert all(c.isalnum() or c == "_" for c in name)


@pytest.fixture(scope="class")
def base_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("no TEST_DATABASE_URL/DATABASE_URL exported (run under validate.sh env)")
    return url


class TestCreateDrop:
    def test_create_is_idempotent_and_urls_point_at_worker_db(self, base_url):
        name = "fcl_probe_gw0"
        url1 = _create_worker_database(base_url, name)
        url2 = _create_worker_database(base_url, name)  # second create must not raise
        assert url1 == url2
        assert url1.endswith(f"/{name}")
        assert "+asyncpg" in url1
        _drop_worker_database(base_url, name)

    def test_drop_refuses_protected_names(self, base_url):
        for protected in PROTECTED:
            with pytest.raises(ValueError):
                _drop_worker_database(base_url, protected)

    def test_roundtrip_isolated_from_base(self, base_url):
        from sqlalchemy import create_engine, text

        name = "fcl_probe_gw1"
        url = _create_worker_database(base_url, name)
        try:
            sync_url = url.replace("+asyncpg", "")
            eng = create_engine(sync_url)
            with eng.begin() as conn:
                conn.execute(text("CREATE TABLE fcl_probe (x int)"))
                conn.execute(text("INSERT INTO fcl_probe VALUES (1)"))
            base_eng = create_engine(base_url.replace("+asyncpg", ""))
            with base_eng.begin() as conn:
                exists = conn.execute(text(
                    "SELECT 1 FROM information_schema.tables WHERE table_name='fcl_probe'"
                )).fetchone()
            assert exists is None, "worker DB writes leaked into the base database"
        finally:
            _drop_worker_database(base_url, name)
```

- [ ] **Step 2: Run to verify they fail**

With the dev stack up and `TEST_DATABASE_URL` exported (validate.sh's discover_containers output, or manually):
Run: `uv run pytest backend/tests/test_db_isolation.py -v -n0 -p no:randomly -o addopts=""`
Expected: collection ERROR — `ImportError: cannot import name '_create_worker_database'`.

- [ ] **Step 3: Implement the helpers in root conftest**

Add to `backend/tests/conftest.py` after `get_test_db_url` (~:591). The create/drop pair mirrors `backend/tests/integration/conftest.py:455-522/:545-642` (lock-free create; advisory-locked drop with retry, `pg_terminate_backend` first, protected-name refusal) — the two conftests already duplicate `_get_advisory_lock_key` for the same reason; do not import one conftest from the other (pytest loads conftests under synthetic module names; cross-import is fragile):

```python
# ── Per-worker test database isolation (fast-confidence-loop spec SS3.1) ─────
# Root-tier tests must not share one database across xdist workers: every
# test_db/isolated_db invocation would queue on _reset_db_schema's advisory
# lock (M1 R-T7-DBRACE-FINAL: load 8.1 on 72 cores, all of it queue). Pattern
# mirrors backend/tests/integration/conftest.py's proven worker machinery;
# duplication across conftests is deliberate (conftest-to-conftest imports are
# brittle under pytest's importer) and matches the existing _get_advisory_lock_key
# duplication.

def worker_id() -> str:
    """Current xdist worker id ('gw0'…) or 'master' when running serially.

    Reads the env var xdist sets in each worker at startup
    (xdist/remote.py: os.environ['PYTEST_XDIST_WORKER'] = workerinput['workerid'])
    so it works inside plain functions without a fixture request.
    """
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


def worker_db_name(base_url: str) -> str:
    """Per-worker database name derived from the base DB name.

    master -> '<base>_main', gwN -> '<base>_gwN'. Base name is sanitized to
    [a-z0-9_] and the total is capped at 63 chars (Postgres NAMEDATALEN).
    """
    from urllib.parse import urlparse

    base = urlparse(base_url.replace("+asyncpg", "")).path.lstrip("/") or "test"
    prefix = re.sub(r"[^a-z0-9_]", "_", base.lower()).strip("_") or "test"
    suffix = "main" if worker_id() == "master" else worker_id()
    name = f"{prefix}_{suffix}"
    return name[:63]


def _create_worker_database(base_url: str, db_name: str) -> str:
    """CREATE DATABASE (IF-MISSING) via psycopg2 autocommit; return worker URL.

    Idempotent: two workers (or a rerun after a crash) racing on the same name
    is safe — the pg_database existence check plus catching duplicate_database
    covers the race window.
    """
    from urllib.parse import urlparse, urlunparse

    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    parsed = urlparse(base_url.replace("+asyncpg", ""))
    conn = psycopg2.connect(
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        user=parsed.username or "postgres",
        password=parsed.password or "postgres",
        dbname=parsed.path.lstrip("/") or "postgres",
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
            if not cur.fetchone():
                try:
                    cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db_name)))
                except psycopg2.errors.DuplicateDatabase:
                    pass  # lost the race to a sibling worker: the DB exists, that is all we wanted
    finally:
        conn.close()
    worker_url = urlunparse(parsed._replace(path=f"/{db_name}"))
    if "postgresql://" in worker_url and "asyncpg" not in worker_url:
        worker_url = worker_url.replace("postgresql://", "postgresql+asyncpg://")
    return worker_url


_PROTECTED_DB_NAMES = frozenset({"security", "security_test", "postgres", "template1", "template0"})


def _drop_worker_database(base_url: str, db_name: str, max_retries: int = 3) -> None:
    """Terminate connections then DROP DATABASE, advisory-locked, retrying.

    Refuses protected names (raises ValueError — these helpers run against the
    developer's live Postgres; a bug here must not be able to eat the dev DB).
    Final failure after retries logs a warning only: leaked fcl/test worker DBs
    are cleaned by the next session's pre-clean sweep, never by failing tests.
    """
    import time

    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    if db_name in _PROTECTED_DB_NAMES:
        raise ValueError(f"refusing to drop protected database: {db_name}")

    from urllib.parse import urlparse

    parsed = urlparse(base_url.replace("+asyncpg", ""))
    lock_key = _get_advisory_lock_key(f"fcl_drop:{db_name}")  # same 64-bit-safe hash helper above

    for attempt in range(max_retries):
        conn = None
        try:
            conn = psycopg2.connect(
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                user=parsed.username or "postgres",
                password=parsed.password or "postgres",
                dbname="postgres",  # must connect elsewhere to DROP
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_lock(%s)", (lock_key,))
                cur.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (db_name,),
                )
                cur.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))
                cur.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
            return
        except psycopg2.Error as exc:
            logger.warning(f"drop {db_name} attempt {attempt + 1} failed: {exc}")
            if attempt + 1 < max_retries:
                time.sleep(0.1 * (2**attempt))
        finally:
            if conn is not None:
                try:
                    conn.close()
                except psycopg2.Error:
                    pass
    logger.warning(f"could not drop worker database {db_name}; stale copy will be swept next session")
```

Add `import re` to the root conftest's stdlib import block if absent (grep first; the file is large — check with `grep -n '^import re' backend/tests/conftest.py`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest backend/tests/test_db_isolation.py -v -n0 -p no:randomly -o addopts=""`
Expected: PASS (9 tests, live against the dev Postgres).

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_db_isolation.py backend/tests/conftest.py
git commit -m "test(core): per-worker DB isolation helpers + contract tests (spec 3.1)

Adds worker_id/worker_db_name/_create_worker_database/_drop_worker_database to
the root conftest (mirrors the integration tier's proven machinery; get_test_db_url
behavior unchanged until the cutover task).

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

GOTCHAS: `_get_advisory_lock_key` exists in root conftest (~:702-719, sha256[:15] % 2**31 — the integration tier has its own copy AND two other inline variants without the `% 2**31`; reuse the root one only); dropping requires connecting to a *different* database (`dbname="postgres"`) — connecting to the target and dropping it fails; the `DuplicateDatabase` except needs psycopg2 ≥ 3.1 exception classes (repo pins psycopg2-binary; confirm with `uv run python -c "import psycopg2; print(hasattr(psycopg2.errors, 'DuplicateDatabase'))"` in Step 3).

---

### Task 6: Cutover `get_test_db_url` to per-worker databases

**Files:**
- Modify: `backend/tests/conftest.py` (`get_test_db_url` at :557-590)
- Test: `backend/tests/test_db_isolation.py` (extend)

**Interfaces:**
- Consumes: Task 5's four helpers.
- Produces: `get_test_db_url()` now returns a **worker-suffixed** URL (the change every downstream consumer sees: `isolated_db` :1489, `test_db` :1641, benchmarks importing it). Consumers keep working because they only treat the return value as "a URL to point DATABASE_URL at" — verified by grep of the five benchmark importers (they write `os.environ` + `get_settings.cache_clear()`, same contract).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_db_isolation.py`:

```python
class TestGetTestDbUrlCutover:
    def test_returns_worker_scoped_url(self, base_url, monkeypatch):
        from backend.tests.conftest import get_test_db_url

        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw9")
        monkeypatch.setenv("TEST_DATABASE_URL", base_url)
        url = get_test_db_url()
        name = url.rsplit("/", 1)[-1]
        assert name.endswith("_gw9")
        assert name != base_url.rsplit("/", 1)[-1]

    def test_repeat_call_is_stable(self, base_url, monkeypatch):
        from backend.tests.conftest import get_test_db_url

        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw8")
        monkeypatch.setenv("TEST_DATABASE_URL", base_url)
        assert get_test_db_url() == get_test_db_url()

    def test_master_suffix(self, base_url, monkeypatch):
        from backend.tests.conftest import get_test_db_url

        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        monkeypatch.setenv("TEST_DATABASE_URL", base_url)
        url = get_test_db_url()
        assert url.rsplit("/", 1)[-1].endswith("_main")

    def test_opt_out_env_restores_verbatim(self, base_url, monkeypatch):
        from backend.tests.conftest import get_test_db_url

        monkeypatch.setenv("TEST_DATABASE_URL", base_url)
        monkeypatch.setenv("TEST_DB_NO_WORKER_SUFFIX", "1")
        assert get_test_db_url() == base_url.replace(
            "postgresql://", "postgresql+asyncpg://"
        ).replace("postgresql+asyncpg://", "postgresql+asyncpg://")
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest backend/tests/test_db_isolation.py::TestGetTestDbUrlCutover -v -n0 -p no:randomly -o addopts=""`
Expected: FAIL — current `get_test_db_url` returns the env verbatim (no suffix).

- [ ] **Step 3: Implement the cutover**

Replace the body of `get_test_db_url` (keep its docstring, rewrite the "Returns" section) so the env-resolution order becomes:

```python
    # 0. Emergency opt-out (documented escape hatch; prints are loud elsewhere):
    if os.environ.get("TEST_DB_NO_WORKER_SUFFIX"):
        env_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
        if env_url:
            if "postgresql://" in env_url and "asyncpg" not in env_url:
                env_url = env_url.replace("postgresql://", "postgresql+asyncpg://")
            return env_url

    # 1. Explicit environment variable override (validate.sh/CI set these).
    #    Returned URL is now PER-WORKER: suffix the base DB name with the xdist
    #    worker id and ensure the database exists (spec 3.1; M1 R-T7-DBRACE-FINAL
    #    proved the verbatim return serializes all workers on one schema-reset
    #    lock). Connection params (host/port/credentials) still come from the env.
    env_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if env_url:
        if "postgresql://" in env_url and "asyncpg" not in env_url:
            env_url = env_url.replace("postgresql://", "postgresql+asyncpg://")
        name = worker_db_name(env_url)
        return _create_worker_database(env_url, name)

    # 2. Check for local PostgreSQL (development environment with Podman/Docker)
    if _check_postgres_connection():
        name = worker_db_name(DEFAULT_DEV_POSTGRES_URL)
        return _create_worker_database(DEFAULT_DEV_POSTGRES_URL, name)

    raise RuntimeError(...)  # unchanged message
```

- [ ] **Step 4: Run the isolation tests + a contention smoke**

```bash
uv run pytest backend/tests/test_db_isolation.py -v -n0 -p no:randomly -o addopts=""
# then prove parallel behavior: same file under 4 workers, twice, each
# worker resetting its OWN schema without queueing
uv run pytest backend/tests/test_utils.py backend/tests/test_db_isolation.py -n4 -p no:randomly -o addopts="-v" 
uv run pytest backend/tests/test_utils.py backend/tests/test_db_isolation.py -n4 -p no:randomly -o addopts="-v"
```
Expected: PASS both; second run must not error on existing databases (create is idempotent).

- [ ] **Step 5: Prove the serialization class is dead (instrumented probe)**

Run the heaviest `test_db` consumer subset with timing, old-vs-new:

```bash
OLDHASH=$(git rev-parse HEAD)
uv run pytest backend/tests/unit/core/test_database.py backend/tests/unit/repositories -n8 -o addopts="-v -m 'not gpu'" 2>&1 | tail -3
```
Record wall-time. (The full before/after DBRACE-cluster measurement belongs to Task 8's acceptance run; here we only require: green + wall-time not worse by more than template-creation cost.)

- [ ] **Step 6: Commit**

```bash
git add backend/tests/conftest.py backend/tests/test_db_isolation.py
git commit -m "test(core): get_test_db_url returns per-worker databases (spec 3.1 cutover)

M1 R-T7-DBRACE-FINAL: every xdist worker shared one exported TEST_DATABASE_URL
and queued on the schema-reset advisory lock. Workers now get <base>_gwN /
<base>_main copies, created idempotently. Emergency opt-out:
TEST_DB_NO_WORKER_SUFFIX=1 (verbatim env, the old behavior).

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

GOTCHAS: `get_test_db_url` is called from fixtures (`isolated_db` :1515, `test_db` :1664) — those fixtures already do `os.environ["DATABASE_URL"] = test_db_url` + `get_settings.cache_clear()` + `init_db()`, so the per-worker URL flows through unchanged; the schema each worker sees is created fresh by `init_db()`/`_reset_db_schema()` in that empty database (first invocation pays full DDL — that is the accepted cost swap: 8 parallel DDL runs replace 1 serialized lock queue). The five benchmark files importing `get_test_db_url` (test_memory.py:43 etc.) now get worker-suffixed URLs too — they run in `backend/tests/benchmarks` which validate.sh --ignore's and CI path-scopes to its own workflow, but flaky-test-detection.yml may run them: the suffixing is harmless there (empty DB, they init their own schema). The opt-out env var is the rollback lever named in spec §3.1's risk framing; keep it out of committed files (documented in the docstring only).

---

### Task 7: Worker-database lifecycle hygiene (create-once + drop-at-session-end + stale sweep)

Create-per-call (Task 6) is idempotent but re-parses pg_database on every fixture invocation, and crashed sessions leak `<base>_gwN` copies. This task adds the session-scoped lifecycle without changing the URL contract.

**Files:**
- Modify: `backend/tests/conftest.py` (new session fixture + module-level memo; extend existing session-scoped hygiene if present)
- Test: `backend/tests/test_db_isolation.py` (extend)

**Interfaces:**
- Consumes: Task 5 helpers, Task 6's `get_test_db_url`.
- Produces: `worker_database` session fixture (autouse within the root tier) guaranteeing create-once + drop-on-session-end; a `_created_worker_db` module memo making post-first `get_test_db_url` calls pure-cache (no psycopg2 round-trip).

- [ ] **Step 1: Write the failing tests**

Append:

```python
class TestSessionLifecycle:
    def test_fixture_exists_and_is_session_scoped(self):
        from backend.tests.conftest import worker_database

        assert worker_database.__pytestfixturefunction__.scope == "session"

    def test_memo_makes_second_call_cache_hit(self, base_url, monkeypatch):
        import backend.tests.conftest as ct

        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw2")
        monkeypatch.setenv("TEST_DATABASE_URL", base_url)
        first = ct.get_test_db_url()
        calls = []
        real = ct._create_worker_database

        def spy(base, name):
            calls.append(name)
            return real(base, name)

        monkeypatch.setattr(ct, "_create_worker_database", spy)
        second = ct.get_test_db_url()
        assert second == first
        assert calls == [], "second call must hit the memo, not psycopg2"
```

- [ ] **Step 2: Verify fail** — `uv run pytest backend/tests/test_db_isolation.py::TestSessionLifecycle -v -n0 -p no:randomly -o addopts=""` → FAIL (no fixture, no memo).

- [ ] **Step 3: Implement**

In `backend/tests/conftest.py`: add module-level `_worker_db_url_cache: dict[str, str] = {}`; inside `get_test_db_url`'s worker path, key the memo on `(worker_id(), env_url)` — cache hit returns without touching psycopg2. Add the session fixture:

```python
@pytest.fixture(scope="session", autouse=True)
def worker_database(request):
    """Own the worker DB for the session: pre-clean stale copies, drop ours at end.

    Autouse at session scope so it wraps test_db/isolated_db lazily (they call
    get_test_db_url themselves; this fixture only guarantees the bookends:
    a stale sweep of <base>_gw* left by crashed sessions, and a best-effort
    drop of this session's DB — leaked databases are swept next session.
    """
    url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url or os.environ.get("TEST_DB_NO_WORKER_SUFFIX"):
        yield
        return
    base = url
    name = worker_db_name(base)
    _sweep_stale_worker_dbs(base, worker_db_name(base))  # prefix-scoped sweep, see below
    yield
    _drop_worker_database(base, name)
```

and the sweep helper (mirrors the integration tier's `cleanup_stale_databases` :793-860 master-only pattern, but keyed on **this tier's** naming — the integration sweep only matches `test_db_gw%`/`template_test` and therefore never sees the root tier's names, and vice versa, which is exactly the mismatch that let `security_test_gwN` leak unnoticed; name the prefix explicitly so the two sweeps stay disjoint):

```python
def _sweep_stale_worker_dbs(base_url: str, own_name: str) -> None:
    """Drop leftover <base>_*_gw* / <base>_main DBs from crashed prior sessions.

    Master/serial only (one sweep per session); never touches the live base DB
    or the integration tier's security_test* namespace (distinct prefix).
    """
    if worker_id() != "master":
        return
    ...  # psycopg2 to dbname='postgres'; SELECT datname FROM pg_database
         # WHERE datname LIKE '<prefix>_%' AND (datname ~ '^<prefix>_gw[0-9]+$'
         # OR datname = '<prefix>_main') AND datname <> current db name;
         # for each: _drop_worker_database(base_url, datname)
```

(Fill the `...` with the pattern from root conftest :824-860's existing sweep — same LIKE+regex shape, `<prefix>` = sanitized base name; the existing `cleanup_stale_databases` fixture's body is the template.)

- [ ] **Step 4: Verify tests pass** (same command as Step 2) → PASS. Then the two-run hygiene check:

```bash
uv run pytest backend/tests/test_db_isolation.py -n4 -p no:randomly -o addopts="-v"
uv run pytest backend/tests/test_db_isolation.py -n4 -p no:randomly -o addopts="-v"  # no leftover errors, no lock waits
psql "postgresql://postgres:postgres@localhost:5432/postgres" -Atc \
  "SELECT datname FROM pg_database WHERE datname LIKE '%\\_gw%' ORDER BY 1" | head
```
Expected: green ×2; between runs, zero leaked `<base>_gw*` rows except any live-session ones (after the second run ends: zero).

- [ ] **Step 5: Commit**

```bash
git add backend/tests/conftest.py backend/tests/test_db_isolation.py
git commit -m "test(core): session-scoped worker DB lifecycle + stale sweep (spec 3.1)

Create-once memo removes the per-call psycopg2 round trip; session teardown
drops the worker DB and pre-cleans crashed sessions' copies. The sweep is
prefix-scoped so it never touches the integration tier's security_test* DBs
(the two tiers' naming namespaces stay disjoint by construction).

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

GOTCHAS: an autouse session fixture in the ROOT conftest applies to every test in `testpaths` (including `ai/*/tests`) — those dirs have their own conftests; the fixture must early-return when no DB env is exported (it does), or AI-tier tests on machines without Postgres would suddenly require it; pytest-xdist `--dist=loadgroup` (validate.sh interim) vs `worksteal` (addopts): either way each worker gets one session, so create-once holds under both; the fixture's drop-at-end races sibling workers only through the advisory lock, which `_drop_worker_database` holds.

---

### Task 8: DBRACE acceptance run + loadgroup supersession decision (spec §3.1 acceptance)

This is the measurement task: no code unless the numbers demand it. It closes the loop on M1's DBRACE ruling and executes spec §9 item 5 (`--dist=loadgroup` removal strictly after green ×2).

**Files:**
- Modify: `scripts/validate.sh` — ONLY if the green-×2 condition holds AND M1 shipped the flag (today's tree: it did not — `grep -n 'dist=' scripts/validate.sh` must be re-run at execution time; if M1's final commit shipped it, remove it here with the supersession note; if not, this task records "no supersession needed" and changes nothing)
- Modify: `docs/development/fast-confidence-loop-measurements.md` (Task 15's file — first row filled: before/after lane numbers)

**Interfaces:**
- Consumes: Tasks 5–7 on disk; the M1 ledger's R-T7-DBRACE-FINAL cluster list (alert_repository 41, zone/queues/admin/dlq, api_protection) as the acceptance set.
- Produces: the two green full-run records that unblock Task 9's clean attribution and Task 10's "selection over a non-contended suite" precondition; the measurements doc's first row.

Pre-existing content to absorb at scaffold time (M1 ledger datapoints that predate this plan — the R-T7-POISON-CASCADE ruling references this file as their canonical home; Task 15's owner merges them in when scaffolding): the 443 GB lane-1 kernel-OOM worker datapoint (spec §3.3 heap rationale) and the D2 late-lane hard-crash tail (same tests pass elsewhere; shared-DB DDL storm hypothesis — spec §3.1 problem statement). Verbatim text lives in the M1 ledger row (R-T7-POISON-CASCADE + AMENDMENT-RESOLUTION) and impl-t7's Task-7 docs draft; the scaffold's first two rows ARE these two datapoints, labeled "measured during M1, pre-plan".

- [ ] **Step 1: Confirm the flag question**

```bash
grep -n 'dist=' scripts/validate.sh || echo NO-DIST-FLAG
git log --oneline -5 -- scripts/validate.sh
```
Record the answer in the ledger/report either way. If a flag exists (M1 shipped it after this plan was drafted), Steps 2–4 run WITH it (green ×2 proven under the belt), Step 5 removes it, Steps 6–7 re-prove ×2 without it before merge of the removal.

- [ ] **Step 2: Run the DBRACE cluster at `-n auto` (run 1 of 2)**

```bash
TEST_DATABASE_URL="postgresql+asyncpg://security:security_dev_password@localhost:5432/security" \
uv run pytest backend/tests/unit/repositories/test_alert_repository.py \
  backend/tests/integration/test_queues_api.py backend/tests/integration/test_admin_api.py \
  backend/tests/integration/test_dlq_api.py backend/tests/unit/test_api_protection.py \
  -n auto --timeout=60 -p no:randomly -o addopts="-v -m 'not gpu'" \
  2>&1 | tee /tmp/fcl-dbrace-run1.log
grep -c 'node down' /tmp/fcl-dbrace-run1.log || true
```
Expected: exit 0 (or only known-red tests unrelated to contention — adjudicate against the ledger's class tables), and `node down` count **0** (spec §6.1). If individual tests are red, this is Task-9's forensics moment: capture tracebacks; DB-class errors (lock wait timeouts, missing tables another worker dropped, UniqueViolation across workers) mean a missed shared-state path; redis-class is expected-red until Task 9.

- [ ] **Step 3: Run 2 of 2.** Same command → `/tmp/fcl-dbrace-run2.log`. Two greens required.

- [ ] **Step 4: Wall-time the combined tier (the §6.1 number)**

```bash
time (TEST_DATABASE_URL="..." ./scripts/validate.sh --backend) 2>&1 | tee /tmp/fcl-full-backend-1.log
```
Record wall-time. Target is spec §6.1 (< 30 min) — if the run lands 30–45 min because Redis (Task 9) is still shared, that is the expected intermediate; note it, don't fail the task. Zero node-downs is the hard requirement; the < 30 min wall is finally adjudicated after Task 9's run.

- [ ] **Step 5 (conditional): remove loadgroup** — only under the Step-1 positive + green-×2 both with it. Replace `--dist=loadgroup` on the pytest line with nothing, and add above it:

```sh
    # Superseded 2026-09-XX: per-worker databases (spec 3.1, plan task 8) remove
    # the shared-DB contention this flag was an interim belt for; green x2 with
    # and without the flag recorded in docs/development/fast-confidence-loop-measurements.md.
```

- [ ] **Step 6: Record + commit** (measurements doc lands here with its first row; if Step 5 ran, its re-proof ×2 precedes the commit):

```bash
git add scripts/validate.sh docs/development/fast-confidence-loop-measurements.md
git commit -m "test: per-worker DB acceptance run green x2; supersede loadgroup if shipped (spec 3.1/6.1)

Before (M1 ledger): combined backend lane ~2.5-3 h, load 8.1/72 cores, all queue.
After: <wall-time from Step 4>, zero node-downs in 2 DBRACE-cluster runs.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

GOTCHAS: `-p no:randomly` keeps the cluster co-located deterministically (under worksteal + randomly, the same 5 files scatter — which is also a valid acceptance shape; the plan chooses the deterministic form first, and Step 4's full validate.sh run covers the scattered form); the run MUST happen on the dev box with the dev stack up (validate.sh's discover_containers exports the same URL — running Steps 2–3 bare without the env silently uses DEFAULT_DEV_POSTGRES_URL and still passes, testing the wrong base name); watch for `duplicate_database` warnings in logs between workers — benign by design (the except), but a *flood* of them means the memo from Task 7 isn't engaging.
---

## Phase C — Per-worker Redis isolation (spec §3.2)

### Task 9: Per-worker Redis logical DB + session-start flush + singleton eviction

The mechanism is a three-parter or it silently does nothing: (1) the URL env must be set **before any client constructs** (RedisClient bakes `self._redis_url` at construction, `backend/core/redis.py:227-228`, and the pool at `connect()`, :637); (2) `get_settings.cache_clear()` (already per-test via `reset_settings_cache`, root conftest :1617/:1638 — but it does not re-derive connections); (3) **eviction of an already-built client** — the module-global `_redis_client` singleton (:2658) survives cache_clear with the old pool baked in. xdist gives each worker a fresh interpreter, so at *session* scope (3) is mostly automatic; the fixture still defensively evicts because serial (`-n0`) sessions and in-test `patch` teardowns can leave a live singleton.

**Files:**
- Modify: `backend/tests/conftest.py` (new helpers + session autouse fixture; extend the `reset_settings_cache` defaults region :1610-1611 to defer to the worker URL)
- Test: `backend/tests/test_db_isolation.py` (extend)

**Interfaces:**
- Consumes: Task 5's `worker_id()`.
- Produces: `worker_redis_url()` (pure function) + `worker_redis` session autouse fixture. The unit tier's `mock_redis`/`mock_redis_client` fixtures are untouched (pure mocks — this task only moves the *real*-connection tier).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_db_isolation.py`:

```python
class TestWorkerRedisUrl:
    def test_master_gets_db0(self, monkeypatch):
        from backend.tests.conftest import worker_redis_url

        monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        assert worker_redis_url() == "redis://localhost:6379/0"

    def test_gw_offset(self, monkeypatch):
        from backend.tests.conftest import worker_redis_url

        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw0")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        assert worker_redis_url() == "redis://localhost:6379/1"

    def test_gw15_offset(self, monkeypatch):
        from backend.tests.conftest import worker_redis_url

        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw15")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
        assert worker_redis_url() == "redis://localhost:6379/16"

    def test_credentials_preserved(self, monkeypatch):
        from backend.tests.conftest import worker_redis_url

        monkeypatch.setenv("PYTEST_XDIST_WORKER", "gw2")
        monkeypatch.setenv("REDIS_URL", "redis://user:pw@example.internal:6380/7")
        assert worker_redis_url() == "redis://user:pw@example.internal:6380/3"

    def test_no_redis_env_returns_none(self, monkeypatch):
        from backend.tests.conftest import worker_redis_url

        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("TEST_REDIS_URL", raising=False)
        assert worker_redis_url() is None

    def test_live_roundtrip(self):
        """Prove the derived URL is a usable, isolated namespace (skip w/o server)."""
        import redis as redis_sync

        from backend.tests.conftest import worker_redis_url

        url = worker_redis_url()
        if url is None:
            pytest.skip("no REDIS_URL exported")
        try:
            client = redis_sync.Redis.from_url(url, socket_connect_timeout=2)
            client.ping()
        except Exception as exc:  # server down or NOAUTH without settings password
            pytest.skip(f"redis unreachable: {exc}")
        key = "fcl:probe:isolation"
        client.set(key, "worker", ex=30)
        base = redis_sync.Redis.from_url(
            url.rsplit("/", 1)[0] + "/0", socket_connect_timeout=2
        )
        try:
            assert base.get(key) is None or url.endswith("/0")
        finally:
            client.delete(key)
```

- [ ] **Step 2: Verify fail** — `uv run pytest backend/tests/test_db_isolation.py::TestWorkerRedisUrl -v -n0 -p no:randomly -o addopts=""` → ImportError on `worker_redis_url`.

- [ ] **Step 3: Implement helpers + session fixture**

Add to `backend/tests/conftest.py` (near the Task 5 block):

```python
def worker_redis_url() -> str | None:
    """Per-worker Redis URL: keep connection params, rewrite the logical DB index.

    Mapping (spec 3.2): master -> db0, gwN -> db(N+1). Honors an explicit
    override: when TEST_REDIS_URL_NO_REWRITE=1 the resolved URL is returned
    verbatim (escape hatch mirroring TEST_DB_NO_WORKER_SUFFIX). Source
    precedence mirrors get_test_redis_url: TEST_REDIS_URL, then REDIS_URL.
    Returns None when neither is set (no live-redis tier on this machine).

    Why db-index-per-worker and not key-prefix-per-worker: the integration
    tier already splits dbs 0-14 by worker; the unit tier shares db 15 today
    only because it is mostly mocked. db0 (validate.sh's export) doubles as
    gw-less traffic and the A2 failure cluster's suspect (R-T7 DBRACE/queues);
    offsetting by +1 also keeps workers off the integration tier's gw0=db0.
    """
    from urllib.parse import urlparse, urlunparse

    raw = os.environ.get("TEST_REDIS_URL") or os.environ.get("REDIS_URL")
    if not raw:
        return None
    if os.environ.get("TEST_REDIS_URL_NO_REWRITE"):
        return raw
    parsed = urlparse(raw)
    wid = worker_id()
    db = 0 if wid == "master" else int(wid[2:]) + 1
    return urlunparse(parsed._replace(path=f"/{db}"))


@pytest.fixture(scope="session", autouse=True)
def worker_redis(request):
    """Pin REDIS_URL to this worker's logical DB for the whole session.

    Runs before any test body (session autouse orders ahead of function
    fixtures): set env -> get_settings.cache_clear() -> evict any
    pre-constructed client so the first real client of the session bakes the
    worker URL (redis.py:228 construction-time bake; 2658 module singleton).
    Also flushes the worker's DB once at session start (spec 3.2 — hygiene
    the shared-db era relied on key-prefix cleanup for).
    """
    url = worker_redis_url()
    if not url:
        yield
        return
    prior = os.environ.get("REDIS_URL")
    os.environ["REDIS_URL"] = url
    from backend.core.config import get_settings

    get_settings.cache_clear()

    # Evict a client that a plugin/conftest import may have constructed with
    # the old URL. Belt-and-braces: fresh xdist interpreters have none.
    try:
        import backend.core.redis as core_redis

        if core_redis._redis_client is not None:
            asyncio.run(core_redis.close_redis())
    except Exception:  # pragma: no cover - best-effort; never fail a session here
        pass

    _flush_worker_redis_db(url)
    yield
    os.environ["REDIS_URL"] = prior if prior is not None else ""
    get_settings.cache_clear()


def _flush_worker_redis_db(url: str) -> None:
    """FLUSHDB the worker's own logical DB (never the shared db, never all)."""
    import redis as redis_sync

    from backend.core.config import get_settings

    kwargs = {"socket_connect_timeout": 2}
    try:
        password = getattr(get_settings(), "redis_password", None)
        if password:
            kwargs["password"] = password
    except Exception:
        pass
    try:
        client = redis_sync.Redis.from_url(url, **kwargs)
        client.flushdb()
        client.close()
    except Exception as exc:
        logger.warning(f"worker redis flush skipped ({url.rsplit('/', 1)[-1]}): {exc}")
```

(`import asyncio` is already at conftest top per the Task 5 grep; if not, add it. The dev box's NOAUTH quirk — localhost:6379 answers PING with -NOAUTH while `.env` carries `REDIS_PASSWORD` — is why the flush pulls `redis_password` from settings; a flush failure is logged and never fails the session.)

Also change the existing default in `reset_settings_cache` (:1610-1611, "set REDIS_URL to DEFAULT_DEV_REDIS_URL if unset") to defer: `os.environ.setdefault("REDIS_URL", DEFAULT_DEV_REDIS_URL)` stays, but the worker fixture has already pinned the value by session start, so per-test setdefault never fires on a worker — no edit needed if `setdefault` is already the semantics; VERIFY with `sed -n '1605,1615p' backend/tests/conftest.py` and only edit if it force-assigns.

- [ ] **Step 4: Verify unit tests pass + A2 acceptance cluster**

```bash
uv run pytest backend/tests/test_db_isolation.py -v -n0 -p no:randomly -o addopts=""
TEST_DATABASE_URL="..." REDIS_URL="redis://localhost:6379/0" \
uv run pytest backend/tests/integration/test_queues_api.py backend/tests/integration/test_admin_api.py backend/tests/integration/test_dlq_api.py \
  -n auto --timeout=60 -p no:randomly -o addopts="-v -m 'not gpu'" 2>&1 | tee /tmp/fcl-a2-redis.log
grep -c 'node down' /tmp/fcl-a2-redis.log || true
```
Expected: green, zero node-downs (spec §3.2 acceptance). Note the integration tier has its OWN `worker_redis_url` session fixture mapping gw0→db0…master→db15 (`backend/tests/integration/conftest.py:683-707`) and its `integration_env` writes REDIS_URL per-test — the root-tier fixture above must not fight it: the integration fixture overwrites within its own scope (function-scoped, wins ordering), and both mappings are worker-exclusive, so no cross-worker collision results. The acceptance run executes the integration chain (the A2 files are integration tests) — this is the *combination* under test; if the two layers fight (flapping between worker db indexes mid-test), the ruling path is: root fixture becomes non-autouse and only the unit tier uses it (record as Ruling; the spec §3.2 scope is "conftest-scope only", the unit tier is the owner of the shared-redis failure class).

- [ ] **Step 5: Commit**

```bash
git add backend/tests/conftest.py backend/tests/test_db_isolation.py
git commit -m "test(core): per-worker Redis logical DB with session-start flush (spec 3.2)

gwN -> db N+1, master -> db 0, connection params preserved; session autouse
sets env + cache_clear + evicts a pre-baked client singleton so the worker URL
actually takes effect (construction-time bake at redis.py:228). A2 acceptance:
queues/admin/dlq green x1 at -n auto, zero node-downs.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

GOTCHAS: `asyncio.run(close_redis())` inside a sync session fixture works only if no event loop is running — session-fixture setup at xdist worker start has none, but under pytest-asyncio auto-mode a mid-session re-entry could; the `except Exception` swallow plus the fresh-interpreter argument is the accepted belt. Redis's `SELECT`-per-connection means db-index isolation shares one server's memory and eviction policy — a full server still breaks everyone (spec accepts: isolation ≠ capacity; capacity is the §5.5 runner conversation). The integration tier's `_get_worker_redis_db` caps at db14 (min(worker_num, 14)) — with `-n >15` the integration tier collides with itself; out of scope (note in measurements doc: 16+ workers is unsupported pre-existing). `reset_settings_cache`'s per-test restore of REDIS_URL (:1627-1630) restores whatever was there at test start — by then that is the worker URL, so the restore is isolation-preserving, and the `get_settings.cache_clear()` after it keeps Settings coherent.

---

## Phase D — The `--fast` tier (spec §4.1)

### Task 10: Backend change→test selector (`scripts/fast_select.py`)

Spec §4.1 sketches a path-proximity table; the plan's fact-sweep measured why a *table* is the wrong v1: filename mirroring silently drops 9 of 62 route modules and 18 of 206 service modules (their only tests are integration-root, differently named), 85 test basenames are duplicated across dirs, and route tests import their module lazily inside test bodies or reference it only as a `patch("backend.api.routes.metrics...")` string. Import-truth beats naming-heuristics and needs no maintained table: the selector builds the dotted-reference index from the test files' own text (imports AND patch strings — one regex over file text captures both) and maps changed modules to every test that mentions them. Spec §4.1's "proximity table realized by import truth" is a RULING recorded here (deviation from the spec's illustrative mechanism, faithful to its intent: predictable, explainable, printed selection).

**Files:**
- Create: `scripts/fast_select.py`
- Test: `scripts/test_fast_select.py`
- Create: `scripts/fast-backend-runner.sh`

**Interfaces:**
- Consumes: git (repo checkout), no third-party deps.
- Produces: `fast_select.py --base REF [--list-out FILE] [--why]` → exit 0 with stdout report; writes the newline-separated selected test-file paths (repo-root-relative) to `--list-out` for Task 13's runner; exit 2 operational error. Directory policy for `backend/api/**` changes emits the smoke set (`backend/tests/contracts` — see Task 13 for the contracts-tier note; the spec's "3 smoke files named in validate.sh's contracts step" does not exist on disk — validate.sh has no contracts step (verified: grep 'contracts' scripts/validate.sh → comment-only hits); ruling: the smoke set IS `backend/tests/contracts/` (4 test files, the CI-named contracts tier), recorded as an in-flight spec-text correction in the measurements doc).

- [ ] **Step 1: Write the failing tests**

Create `scripts/test_fast_select.py`:

```python
"""Tests for scripts/fast_select.py (run explicitly; outside testpaths)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent / "fast_select.py"


@pytest.fixture()
def repo(tmp_path):
    """Tiny synthetic repo shaped like the real one."""
    run = lambda *a: subprocess.run(a, cwd=tmp_path, check=True, capture_output=True)  # noqa: E731
    run("git", "init", "-q")
    run("git", "config", "user.email", "t@t")
    run("git", "config", "user.name", "t")
    (tmp_path / "backend/api/routes").mkdir(parents=True)
    (tmp_path / "backend/services").mkdir(parents=True)
    (tmp_path / "backend/tests/unit/api/routes").mkdir(parents=True)
    (tmp_path / "backend/tests/unit/services").mkdir(parents=True)
    (tmp_path / "backend/tests/contracts").mkdir(parents=True)
    (tmp_path / "backend/api/routes/alerts.py").write_text("def list_alerts(): ...\n")
    (tmp_path / "backend/services/alert_service.py").write_text("class AlertService: ...\n")
    (tmp_path / "backend/tests/unit/api/routes/test_alerts.py").write_text(
        "def test_x():\n    from backend.api.routes.alerts import list_alerts\n"
    )
    (tmp_path / "backend/tests/unit/services/test_alert_service.py").write_text(
        "from backend.services.alert_service import AlertService\n"
    )
    (tmp_path / "backend/tests/unit/services/test_metrics.py").write_text(
        'def test_y(mocker):\n    mocker.patch("backend.api.routes.metrics.get_x")\n'
    )
    (tmp_path / "backend/tests/contracts/test_api_contracts.py").write_text("def test_c(): ...\n")
    for p in ("backend", "backend/api", "backend/api/routes", "backend/services",
              "backend/tests", "backend/tests/unit", "backend/tests/unit/api",
              "backend/tests/unit/api/routes", "backend/tests/unit/services",
              "backend/tests/contracts"):
        init = tmp_path / p / "__init__.py"
        init.touch()
    (tmp_path / "backend/api/routes/metrics.py").write_text("def get_x(): ...\n")
    run("git", "add", "-A")
    run("git", "commit", "-qm", "base")
    return tmp_path


def select(repo, base="HEAD", *args):
    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--base", base, *args],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    return r


def write_and_stage(repo, rel, text):
    (repo / rel).write_text(text)
    subprocess.run(["git", "add", "--", rel], cwd=repo, check=True)


def test_route_change_selects_lazy_import_test(repo):
    write_and_stage(repo, "backend/api/routes/alerts.py", "def list_alerts():\n    return []  # touched\n")
    r = select(repo)
    assert r.returncode == 0, r.stderr
    assert "backend/tests/unit/api/routes/test_alerts.py" in r.stdout
    # directory policy: backend/api/** pulls the contracts smoke tier
    assert "backend/tests/contracts/test_api_contracts.py" in r.stdout


def test_patch_string_reference_counts(repo):
    write_and_stage(repo, "backend/api/routes/metrics.py", "def get_x():\n    return 1  # touched\n")
    r = select(repo)
    assert "backend/tests/unit/services/test_metrics.py" in r.stdout


def test_service_change_selects_importer_only(repo):
    write_and_stage(repo, "backend/services/alert_service.py", "class AlertService:  # touched\n    pass\n")
    r = select(repo)
    assert "backend/tests/unit/services/test_alert_service.py" in r.stdout
    assert "test_alerts.py" not in r.stdout  # the route test must NOT ride along


def test_unmapped_is_loud(repo):
    write_and_stage(repo, "backend/services/orphan.py", "def f():\n    return 1\n")
    r = select(repo)
    assert "UNMAPPED: backend/services/orphan.py" in r.stdout


def test_list_out_file(repo, tmp_path):
    out = tmp_path / "sel.txt"
    write_and_stage(repo, "backend/services/alert_service.py", "class AlertService:  # x\n    pass\n")
    r = select(repo, "--list-out", str(out))
    lines = out.read_text().strip().splitlines()
    assert lines == ["backend/tests/unit/services/test_alert_service.py"]


def test_no_changes_empty_selection(repo):
    r = select(repo)
    assert r.returncode == 0
    assert "SELECTED-BACKEND-FILES: 0" in r.stdout
```

- [ ] **Step 2: Verify fail** — `uv run pytest scripts/test_fast_select.py -v -p no:randomly -o addopts=""` → fails (script missing).

- [ ] **Step 3: Implement the selector**

Create `scripts/fast_select.py`:

```python
#!/usr/bin/env python3
"""Backend change -> test selection for validate.sh --fast (spec SS4.1).

Mechanism (ruling recorded in the plan, Task 10): dotted-reference truth from
the test files' own text, not a path-mirroring table. One regex over each test
file captures every `backend.a.b.c` mention, which uniformly covers top-level
imports, function-local (lazy) imports, and mock patch strings - the three
forms the fact-sweep found, with the lazy/patch forms being exactly what
filename or top-level-AST heuristics silently miss.

Directory policy: any change under backend/api/** adds backend/tests/contracts
(the smoke tier - route wiring / OpenAPI shape break class).

Usage: fast_select.py --base REF [--list-out FILE] [--why]
Stdout: human report ending in machine lines:
  SELECTED-BACKEND-FILES: N
Exit: 0 report produced (selection may be empty), 2 git failure.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REF_RE = re.compile(r"backend(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
API_POLICY_DIR = "backend/api/"
SMOKE_GLOB = "backend/tests/contracts"


def git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True
    )
    if proc.returncode != 0:
        print(f"git {' '.join(args)} failed: {proc.stderr.strip()}", file=sys.stderr)
        raise SystemExit(2)
    return proc.stdout


def changed_files(root: Path, base: str) -> list[str]:
    files = set(git(root, "diff", "--name-only", base).splitlines())
    files |= set(
        git(root, "ls-files", "--others", "--exclude-standard").splitlines()
    )
    return sorted(files)


def module_of(rel: str) -> str | None:
    """backend/services/alert_service.py -> backend.services.alert_service."""
    if not rel.endswith(".py") or not rel.startswith("backend/"):
        return None
    return rel[: -len(".py")].replace("/", ".")


def test_files(root: Path) -> list[str]:
    out = git(root, "ls-files", "-z", "backend/tests").split("\0")
    return [f for f in out if Path(f).name.startswith("test_") and f.endswith(".py")]


def dotted_refs(root: Path, rel_test: str) -> set[str]:
    try:
        text = (root / rel_test).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return set(REF_RE.findall(text))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--list-out", default="")
    ap.add_argument("--why", action="store_true")
    args = ap.parse_args(argv[1:])
    root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").strip())

    changed = changed_files(root, args.base)
    backend_mods: dict[str, str] = {}  # dotted -> changed path
    non_backend = []
    for f in changed:
        mod = module_of(f)
        if mod:
            backend_mods[mod] = f
        elif not f.startswith(("docs/", "frontend/")):
            non_backend.append(f)

    selected: dict[str, list[str]] = defaultdict(list)  # test file -> reasons
    smoke_triggered = False
    for f in changed:
        if f.startswith(API_POLICY_DIR) and f.endswith(".py"):
            smoke_triggered = True

    if backend_mods or smoke_triggered:
        index: dict[str, list[str]] = defaultdict(list)
        for t in test_files(root):
            for ref in dotted_refs(root, t):
                index[ref].append(t)
        for dotted, src in sorted(backend_mods.items()):
            hits = sorted(set(index.get(dotted, [])))
            if not hits:
                print(f"UNMAPPED: {src} (no test references {dotted})")
            for t in hits:
                selected[t].append(f"references {dotted} (changed: {src})")

    if smoke_triggered:
        for t in test_files(root):
            if t.startswith(SMOKE_GLOB):
                selected[t].append(f"directory policy: change under {API_POLICY_DIR}*")

    if non_backend:
        for f in sorted(non_backend):
            print(f"POLICY-SKIP: {f} (outside backend/**; fast tier covers backend + "
                  "frontend; ai/*/tests and setup_lib/tests changes: run the full gate)")

    ordered = sorted(selected)
    for t in ordered:
        print(f"SELECTED {t}")
        if args.why:
            for r in sorted(set(selected[t])):
                print(f"    because: {r}")
    if args.list_out:
        Path(args.list_out).write_text("\n".join(ordered) + ("\n" if ordered else ""), encoding="utf-8")
    print(f"SELECTED-BACKEND-FILES: {len(ordered)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 4: Verify tests pass** — same command as Step 2 → PASS (6).

- [ ] **Step 5: Live sanity (read-only, real repo)**

```bash
uv run python scripts/fast_select.py --base "$(git merge-base HEAD main)" --why | tail -8
```
Expected on a docs-only diff branch tail: `SELECTED-BACKEND-FILES: 0`. Sanity the other direction: `uv run python scripts/fast_select.py --base HEAD~5 --why | grep -E 'SELECTED |UNMAPPED' | head` — on the real repo expect a plausible mix (M1 commits touching backend files → their importers). Timing note for the measurements doc: the full `backend/tests` parse runs once per invocation (≈1-2 s over 913 files at plan time — no caching layer in v1, YAGNI; cache behind a flag only if measurement disagrees).

- [ ] **Step 6: Create the backend runner**

Create `scripts/fast-backend-runner.sh`:

```sh
#!/bin/sh
# Runs the fast tier's selected backend tests (spec 4.1). Deterministic order
# (-p no:randomly) because selection is position-blind while randomly is not:
# selection and run must agree on ordering or a green --fast proves nothing
# about the same selection re-run. No coverage args at all (fast tier has no
# coverage proof - that is the full gate's identity).
set -eu

LIST="${1:?usage: fast-backend-runner.sh LISTFILE}"
if [ ! -s "$LIST" ]; then
    echo "fast(backend): 0 files selected - nothing affected"
    exit 0
fi
# Paths come from git ls-files (no spaces - repo convention; fast_select emits
# them newline-separated and xargs consumes them quoting-safely).
xargs -a "$LIST" -d '\n' -r uv run pytest \
    --dist=loadgroup -p no:randomly \
    -o addopts="-v -m 'not gpu' --timeout=60"
```
`chmod +x scripts/fast-backend-runner.sh`.

- [ ] **Step 7: Commit**

```bash
git add scripts/fast_select.py scripts/test_fast_select.py scripts/fast-backend-runner.sh
git commit -m "scripts: change-scoped backend test selector + runner for --fast tier (spec 4.1)

Import-truth selection (imports, lazy imports, patch strings via one regex)
instead of the spec's illustrative naming table - the fact-sweep showed the
table silently drops 9 route / 18 service modules. Directory policy pulls
backend/tests/contracts for any backend/api change; unmapped files print loud.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

GOTCHAS: the regex `backend(\.\w+)+` also catches prose/docstrings mentioning dotted paths — over-selection direction only (a test mentioning the module in a comment gets run; harmless under an advisory tier, cheaper than AST-parsing 913 files); `--base REF` must be a reachable ref — `git diff --name-only REF` against a non-ancestor fails loud (exit 2, by design: silent-empty selection is the failure mode to avoid); deleted test files can appear in the selection if the *diff* deletes them — `xargs uv run pytest deleted_file` errors loud, which is correct (a deletion changing the selection is a human-should-see-it event; the playbook never deletes files); `-o addopts=` REPLACES the pyproject addopts string wholesale — that's why `-m 'not gpu'` and `-v` are restated inside it (validate.sh's own comment at :283 documents the same trap).

---

### Task 11: Frontend related-tests runner (`scripts/fast-frontend-runner.sh`)

**Files:**
- Create: `scripts/fast-frontend-runner.sh`

**Interfaces:**
- Consumes: Task 3's env contract; vitest 4.0.18 `related` (verified live: command exists, exclude is honored, `--run` is mandatory for determinism).
- Produces: exit 0 + a parsed `SELECTED-FRONTEND-FILES: N` line Task 13 folds into the aggregate header; nonzero on any selected-test failure.

Known traps this runner must encode (all verified in the vitest 4.0.18 source sweep): a related run selecting **zero** tests exits 0 (runRelated forces `passWithNoTests`), so exit code alone cannot tell "nothing affected" from "all green" — parse the selected-file count; positional args are SOURCE files, and a positional matching `vite.config.ts`/`package.json`/any setupFile hits `forceRerunTriggers` and silently becomes a **full 784-file run** — filter change sets to `frontend/src/**` (+ the two `frontend/tests/integration/*.test.ts` files, which are in the default suite) and route config/package changes to "Tier 0 + notice, run the full gate"; direct `npx` bypasses the package.json NODE_OPTIONS wrapper — replicate the heap env.

- [ ] **Step 1: Write the runner**

Create `scripts/fast-frontend-runner.sh`:

```sh
#!/bin/sh
# Fast-tier frontend selection (spec 4.1): vitest's own import-graph selector.
# Guards encoded from the vitest 4.0.18 source sweep:
#  - related + --run is mandatory (without --run it is WATCH MODE on a TTY).
#  - a zero-selection related run exits 0 (passWithNoTests is forced) - the
#    count line below is what distinguishes 'nothing affected' from 'all green'.
#  - positional config/package.json files trip forceRerunTriggers and silently
#    select the FULL suite - excluded from the arg list here, reported instead.
set -eu

BASE="${1:?usage: fast-frontend-runner.sh BASE_REF}"
cd "$(dirname "$0")/.."

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
# vitest's related run prints 'Test Files  N passed' style summaries only when
# it ran something; count lines it executed via the reporter's file markers.
RUN_COUNT=$(grep -cE '^ *(✓|✗|×|❯)? *(Test Files|.*\.test\.(ts|tsx))' "$LOG" || true)
echo "SELECTED-FRONTEND-FILES: ${RUN_COUNT:-0}"
exit $RC
```
`chmod +x`.

- [ ] **Step 2: Prove the three shapes on the live tree**

```bash
BASE=$(git merge-base HEAD main)
# (a) leaf edit -> small selection, exit 0
touch frontend/src/hooks/useAlertsQuery.ts
sh scripts/fast-frontend-runner.sh "$BASE"; echo "rc=$?"
# (b) no frontend change -> 0-line
git checkout -- frontend/ 2>/dev/null || true
sh scripts/fast-frontend-runner.sh "$BASE"; echo "rc=$?"
# (c) zero-selection-but-sources-changed (a util with no importers) -> exits 0, prints 0
printf 'export const fclProbe = 1;\n' > frontend/src/fcl-probe-no-importers.ts
sh scripts/fast-frontend-runner.sh "$BASE"; echo "rc=$?"
rm frontend/src/fcl-probe-no-importers.ts
```
Expected: (a) rc=0 with a selection ≥1 (`useAlertsQuery.test.ts` colocation verified at plan time); (b) `SELECTED-FRONTEND-FILES: 0` rc=0; (c) rc=0 and count line present (the count parsing is the fragile part — if `grep -c` returns 0-lines-not-found exit 1 swallowed by `|| true`, the `:-0` default keeps it clean; verify the actual default-reporter line shape during this step and adjust the regex to what 4.0.18 prints, e.g. counting `✓`-prefixed file lines — that calibration IS step 2's deliverable, record the final regex in the commit).

- [ ] **Step 3: Commit**

```bash
git add scripts/fast-frontend-runner.sh
git commit -m "scripts: vitest-related runner for --fast tier (spec 4.1)

Guards the three 4.0.18 traps: forced --run, zero-selection-exits-0 (count
line disambiguates), config-file positionals full-suite-ing (filtered +
reported instead).

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

GOTCHAS: unquoted `$SELECTABLE` word-splitting is deliberate-POSIX (repo file names contain no spaces — same convention the backend runner relies on; add a guard `case "$SELECTABLE" in *$'\n'*) : ;; esac` only if the executor finds spaced names, which the plan-time `git ls-files frontend/src | grep ' '` check says none do); `related` follows the full transitive import graph, so a change to the shared api client or generated types selects most of the suite — that is correct behavior (spec: related is only *fast* for leaf edits; a wide-selection --fast run degrading to ~full-suite time is honest, not broken — the header count tells the developer why today's fast run wasn't); `tests/integration/*.test.ts` (2 files, in the default suite, NOT excluded) are reachable via the `src/`-filtered list only through the import graph, never as positionals — consistent with `related` semantics.

---

### Task 12: The scripted §6.3 playbook (5 changes × ≤10 min each)

**Files:**
- Create: `scripts/fast-validation-playbook.sh`
- Modify: `docs/development/fast-confidence-loop-measurements.md` (selection table + timings filled by running it)

**Interfaces:**
- Consumes: Tasks 10–11's runners (invokes the runners directly — the playbook predates Task 13's `--fast` wiring by design, so it can also serve as the pre-wiring acceptance harness).
- Produces: the spec §6.3 artifact ("playbook file committed under scripts/"), per-change wall numbers, and the selection table the exit criteria demand. The 5 changes (all five files verified on disk at plan time): route `backend/api/routes/alerts.py`; service `backend/services/alert_service.py`; component `frontend/src/components/dashboard/ActionableInsights.tsx`; hook `frontend/src/hooks/useAlertsQuery.ts`; config `frontend/vite.config.ts` (the config case deliberately demonstrates the full-suite guard: expected result = Tier-0-style notice + nonzero-fast skip, per spec's "files with no import path fall back to Tier 0 + a notice line").

- [ ] **Step 1: Write the playbook**

Create `scripts/fast-validation-playbook.sh`:

```sh
#!/bin/sh
# Spec 6.3 verification playbook: 5 scripted small changes, each timed against
# the fast tier, with per-change wall assertions. Each case: append a comment
# line (behavior-neutral), run the applicable runner, record seconds, revert.
# Usage: scripts/fast-validation-playbook.sh [BASE_REF]   (default merge-base HEAD main)
# Exit: 0 all five within the 10-minute wall; 1 on breach; 2 setup failure.
set -eu
cd "$(git rev-parse --show-toplevel)"
BASE="${1:-$(git merge-base HEAD main)}"
WALL_LIMIT_S=600
RESULTS=$(mktemp); trap 'rm -f "$RESULTS"; git checkout -- . 2>/dev/null || true' EXIT

run_case() {
    NAME="$1"; FILE="$2"; RUNNER="$3"
    START=$(date +%s)
    printf '\n/* fcl playbook probe */\n' >> "$FILE"
    # shellcheck disable=SC2086
    if sh "$RUNNER" "$BASE"; then RC=0; else RC=$?; fi
    # revert this probe before timing bookkeeping so the next case sees a clean tree
    git checkout -- "$FILE"
    END=$(date +%s); DUR=$((END - START))
    printf '%-28s %6ss rc=%s %s\n' "$NAME" "$DUR" "$RC" \
        "$([ "$DUR" -le "$WALL_LIMIT_S" ] && echo OK || echo OVER-WALL)" | tee -a "$RESULTS"
    [ "$DUR" -le "$WALL_LIMIT_S" ]
}

run_case "route (alerts.py)"          backend/api/routes/alerts.py                        scripts/fast-backend-runner.sh  || OVERALL=1
run_case "service (alert_service.py)" backend/services/alert_service.py                 scripts/fast-backend-runner.sh  || OVERALL=1
run_case "component (ActionableInsights)" frontend/src/components/dashboard/ActionableInsights.tsx scripts/fast-frontend-runner.sh || OVERALL=1
run_case "hook (useAlertsQuery)"      frontend/src/hooks/useAlertsQuery.ts              scripts/fast-frontend-runner.sh || OVERALL=1
# config case EXPECTS the guard notice; only the wall bound is asserted:
run_case "config (vite.config.ts)"    frontend/vite.config.ts                            scripts/fast-frontend-runner.sh || OVERALL=1

echo "--- playbook summary ---"; cat "$RESULTS"
exit "${OVERALL:-0}"
```
`chmod +x`. The route/service cases pass a LISTFILE-less runner invocation — no: `fast-backend-runner.sh` takes a LISTFILE. The runner contract is list-file-based (Task 10), so `run_case`'s backend branch must first generate the list: change the backend invocation to a two-step (`uv run python scripts/fast_select.py --base "$BASE" --list-out /tmp/fcl-sel.txt >/dev/null && sh scripts/fast-backend-runner.sh /tmp/fcl-sel.txt`) — implement `run_case`'s third parameter as a *command string* (`$3='uv run python scripts/fast_select.py --base "$BASE" --list-out /tmp/fcl-sel.txt >/dev/null 2>&1 && sh scripts/fast-backend-runner.sh /tmp/fcl-sel.txt'`) executed via `sh -c "$RUNNER"` (rewrite `if sh "$RUNNER"` → `if sh -c "$RUNNER"`). The frontend parameter is `"sh scripts/fast-frontend-runner.sh $BASE"`. This is the shape that keeps the playbook honest: it runs exactly what Task 13's `--fast` will run.

- [ ] **Step 2: Execute and fill the measurements table**

```bash
sh scripts/fast-validation-playbook.sh 2>&1 | tee /tmp/fcl-playbook.log
```
Expected: five OK rows (config case: rc as designed by Task 11's guard, wall bounded). Paste the summary + each case's SELECTED count into `docs/development/fast-confidence-loop-measurements.md` §playbook. If the route case exceeds 600 s because the selector legitimately pulls a wide net (alerts.py fans into ~4-18 test files per the fact-sweep — those files' own fixtures then boot), the ruling menu is, in order: accept and record (advisory tier), narrow `backend/api/**` policy to contracts-only-on-schema-touch (needs a schema-diff heuristic — YAGNI until needed), or split selection from `-p randomly` ordering further. Record the decision in the ledger; do not silently loosen the 600 s wall.

- [ ] **Step 3: Commit**

```bash
git add scripts/fast-validation-playbook.sh docs/development/fast-confidence-loop-measurements.md
git commit -m "scripts: fast-tier 5-change playbook with wall assertions (spec 6.3)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

### Task 13: `validate.sh --fast` wiring (spec §4.1 output contract)

**Files:**
- Modify: `scripts/validate.sh` (arg parser :179-200, new `run_fast_validation()`, dispatch :438-455, header :10-14, `show_help`)
- Modify: `scripts/AGENTS.md` (:303-316 region)

**Interfaces:**
- Consumes: Task 10's runner contract (`fast_select.py --list-out` + `fast-backend-runner.sh LISTFILE`), Task 11's frontend runner, Task 1's selection line formats.
- Produces: the user-facing flag; the aggregate header/footer contract spec §4.1 defines verbatim.

- [ ] **Step 1: Add the flag + function**

Arg parser: add a `--fast` case **before** the catch-all `*)`:

```sh
        --fast)
            RUN_FAST=true
            RUN_BACKEND=false
            RUN_FRONTEND=false
            shift
            ;;
```

Initialize `RUN_FAST=false` beside `RUN_BACKEND=true` (:28-29). New function after `run_frontend_validation`'s closing brace:

```sh
# ─────────────────────────────────────────────────────────────────────────────
# Fast Tier (change-scoped advisory gate - fast-confidence-loop spec SS4.1)
# ─────────────────────────────────────────────────────────────────────────────

run_fast_validation() {
    VALIDATE_BASE="${VALIDATE_BASE:-$(git merge-base HEAD main)}"
    print_step "Fast tier: change set against ${VALIDATE_BASE}"

    SEL_LIST=$(mktemp); trap 'rm -f "$SEL_LIST"' EXIT

    print_step "Backend selection (import-truth selector)..."
    BACKEND_OUT=$(uv run python "$SCRIPT_DIR/fast_select.py" \
        --base "$VALIDATE_BASE" --list-out "$SEL_LIST" ${VALIDATE_WHY:+--why}) || {
        print_error "selector failed"; exit 1
    }
    printf '%s\n' "$BACKEND_OUT"

    print_step "Backend: selected tests (no coverage, loadgroup, deterministic)..."
    sh "$SCRIPT_DIR/fast-backend-runner.sh" "$SEL_LIST" || {
        print_error "Fast backend tests failed"
        exit 1
    }

    print_step "Frontend: vitest related..."
    sh "$SCRIPT_DIR/fast-frontend-runner.sh" "$VALIDATE_BASE" || {
        print_error "Fast frontend tests failed"
        exit 1
    }

    BE_N=$(printf '%s\n' "$BACKEND_OUT" | sed -n 's/^SELECTED-BACKEND-FILES: //p' | tail -1)
    FE_N=$(...)  # capture from the frontend runner's stdout — restructure: tee both
                 # runner outputs to variables and grep the count lines; the
                 # header below must print actual numbers, not placeholders.
    printf '\nSELECTED: %s tests total (backend: %s via import-truth, frontend: %s via related, smoke: contracts-included-when-api-changed)\n' \
        "$(( ${BE_N:-0} + ${FE_N:-0} ))" "${BE_N:-0}" "${FE_N:-0}"
    printf '%s\n' "FAST TIER — no coverage proof; full gate still required before merge."
    # Deliberately NO "VALIDATION SUCCESSFUL" banner: that string belongs to
    # the full gate alone (spec 4.1 output contract).
}
```

The `FE_N=$(...)` line above is intentionally incomplete in this draft because the header must consume BOTH runners' counts: implement it by capturing each runner's stdout through `tee /dev/fd/3`-style capture or simply re-running the greps over a tee'd log — concrete shape:

```sh
    FE_LOG=$(mktemp); trap 'rm -f "$SEL_LIST" "$FE_LOG"' EXIT
    sh "$SCRIPT_DIR/fast-frontend-runner.sh" "$VALIDATE_BASE" 2>&1 | tee "$FE_LOG"
    FE_RC=$?   # with set -e, wrap: if ! sh ... | tee; then ...
```
(`set -e` + pipelines: use `if ! sh "$SCRIPT_DIR/fast-frontend-runner.sh" "$VALIDATE_BASE" 2>&1 | tee "$FE_LOG"; then print_error "Fast frontend tests failed"; exit 1; fi` — note: without pipefail the `if` sees `tee` — same trap the ci.yml audit found; therefore do NOT pipe here: capture with command substitution *and* echo: `FE_OUT=$(sh "$SCRIPT_DIR/fast-frontend-runner.sh" "$VALIDATE_BASE"); FE_RC=$?; printf '%s\n' "$FE_OUT"` — runner is already loud. Apply the identical pattern to the backend runner call.)

Dispatch block (the file has no main(); append before the final banner block, and guard the final banner):

```sh
if [ "$RUN_FAST" = true ]; then
    run_fast_validation
    exit 0   # fast tier never falls through to the full-gate banner
fi
```

The existing final banner stays exactly as-is (only reachable by non-fast paths). Header comment (:10-14 region) and `show_help` gain:

```
#   ./scripts/validate.sh --fast           Change-scoped advisory tier (<=10 min, no coverage)
```

and `scripts/AGENTS.md`'s validate.sh section gains the same line under **Usage**.

- [ ] **Step 2: Acceptance — behavior matrix**

```bash
git status --porcelain | grep . && echo "TREE DIRTY - stash first" || true
./scripts/validate.sh --fast; echo "rc=$?"            # docs-only diff -> green, 0-selected lines, loud footer, NO success banner
git status --porcelain | grep -c .                     # --fast ran but changed nothing (it must NOT write build artifacts either - vitest related doesn't build: verify no frontend/dist churn)
VALIDATE_BASE=$(git rev-parse HEAD~1) ./scripts/validate.sh --fast   # M1-commit diff -> exercises real selection incl. contracts policy
./scripts/validate.sh --backend                        # unchanged behavior spot-check (starts as before)
./scripts/validate.sh --bogus 2>&1 | tail -1          # still the Unknown-option exit 1
```

Expected: `--fast` prints selection report + both runner outputs + the two footer lines; full-gate paths byte-identical (`git diff` on validate.sh shows only additions — the banner block untouched).

- [ ] **Step 3: The no-op run must not print success (spec §4.1 gotcha the fact-sweep pre-flagged)**

Confirm from the Step-2 run output that neither `VALIDATION SUCCESSFUL` nor any coverage-percentage line appears on the `--fast` path.

- [ ] **Step 4: Commit**

```bash
git add scripts/validate.sh scripts/AGENTS.md
git commit -m "feat(validate): --fast change-scoped advisory tier (spec 4.1)

Prints full selection + per-file reasons (--why via VALIDATE_WHY=1), footer
'FAST TIER - no coverage proof; full gate still required before merge.', and
deliberately never the full gate's SUCCESSFUL banner. Full-gate invocation
byte-identical.

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

GOTCHAS: `trap` inside a function with `EXIT` overwrites prior traps in POSIX sh (mktemp cleanup uses one accumulated trap — declare both files in one trap string, as drafted); `set -e` semantics with `$(...)` assignment: `X=$(cmd)` propagates cmd's failure *only* at the assignment line — that's why `FE_RC=$?` follows on its own line only in the non-`set -e` variant; the committed shape uses the `if ! X=$(...)` guard form — the executor picks ONE of these two drafts and deletes the other (the plan mandates the `if ! ... ; then` guard form, final); `git merge-base HEAD main` fails on a repo cloned without a local `main` (fallback `origin/main` — `git rev-parse --verify -q main || echo origin/main` inside the `${VALIDATE_BASE:-...}` default); CI never invokes validate.sh at all today (verified: no workflow references it) so the flag ships dev-box-only by default, which is the design (spec §4.1 "its position moves" happens in Task 14).

---

### Task 14: Nightly full-gate workflow (spec §5.4)

**Files:**
- Create: `.github/workflows/nightly-full-validation.yml`

**Interfaces:**
- Consumes: honest CI (Tasks 1–2, 4) — a nightly wrapping lying jobs is a lie on a schedule, which is why this is gated on Phase A.
- Produces: the §6 exit-criteria substrate ("the full suite ran somewhere trustworthy yesterday") and the standing home for the §6.1/§6.2 wall-time trend rows.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/nightly-full-validation.yml`:

```yaml
# Nightly honest full gate (fast-confidence-loop spec SS5.4).
# validate.sh is dev-box tooling today; this reproduces its semantics on CI
# hardware: combined pytest (cov>=80, same ignore trio) + the honest frontend
# jobs already in ci.yml. Results land in the run's Job Summary.
name: Nightly Full Validation
on:
  schedule:
    - cron: '17 4 * * *'   # 21:17 Pacific-ish drift off the :00 herd; UTC 04:17
  workflow_dispatch: {}

permissions:
  contents: read

jobs:
  backend-full:
    name: Backend full gate (nightly)
    runs-on: ubuntu-latest
    timeout-minutes: 180
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4
      - uses: astral-sh/setup-uv@e4db8464a088ece1b920f60402e813ea4de65b8f # v4
        with:
          enable-cache: true
      - name: Start service containers (postgres + redis)
        run: |
          docker run -d --name postgres -e POSTGRES_USER=security \
            -e POSTGRES_PASSWORD=security_dev_password -e POSTGRES_DB=security \
            -p 5432:5432 postgres:16-alpine
          docker run -d --name redis -p 6379:6379 redis:7-alpine
          timeout 60 sh -c 'until docker exec postgres pg_isready -U security; do sleep 1; done'
      - name: Full backend gate (validate.sh semantics, spec 5.4)
        env:
          TEST_DATABASE_URL: postgresql+asyncpg://security:security_dev_password@localhost:5432/security
          DATABASE_URL: postgresql://security:security_dev_password@localhost:5432/security
          REDIS_URL: redis://localhost:6379/0
        run: |
          uv sync --extra dev --frozen
          uv run pytest backend --cov=backend --cov-report=term-missing \
            --cov-fail-under=80 \
            --ignore=backend/tests/load --ignore=backend/tests/benchmarks \
            --ignore=backend/tests/e2e
      - name: Summary
        if: always()
        run: |
          {
            echo "## Nightly full gate"
            echo "- backend pytest: ${{ job.status }}"
            echo "- see raw log for coverage + duration (feeds spec 6.1 trend)"
          } >> "$GITHUB_STEP_SUMMARY"

  # Frontend + gate reuse: ci.yml's own jobs already run the honest frontend
  # suite 16-way; the nightly triggers a full ci.yml run on the default branch
  # via workflow_run wiring in the NEXT revision if the owner wants one-click
  # parity - keeping v1 to the backend gate (the 2.5 h artifact) + relying on
  # the per-push frontend honesty is the recorded scope call.

  status:
    name: Nightly status
    needs: [backend-full]
    if: always()
    runs-on: ubuntu-latest
    steps:
      - name: Aggregate
        run: |
          echo "nightly full validation: backend=${{ needs.backend-full.result }}" \
            >> "$GITHUB_STEP_SUMMARY"
          [ "${{ needs.backend-full.result }}" = "success" ]
```

- [ ] **Step 2: Validate + dispatch once manually**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/nightly-full-validation.yml'))" && echo YAML-OK
git add .github/workflows/nightly-full-validation.yml
git commit -m "ci: nightly full-gate validation workflow (spec 5.4)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```
Push is owner-gated (M1 policy: pushes authorized per-event); after the owner's next authorized push, run `gh workflow run "Nightly Full Validation"` once and read the Job Summary; record first nightly duration in the measurements doc.

GOTCHAS: cron `17 4 * * *` follows the off-:00 herd convention; the container-spelled credentials mirror the repo's dev defaults and are non-secret dev values (the repo's own DEFAULT_DEV constants carry them) — if a reviewer demands parity with ci.yml's service setup, adopt ci.yml's existing service-container method verbatim instead of `docker run` (ci.yml uses services: blocks or step-up containers — grep `services:` in ci.yml at execution time and mirror whichever the jobs use; this is byte-parity with what unit/integration jobs already prove on the same runner image); pytest here runs with pyproject addopts (`-n 8 --dist=worksteal`) which is validate.sh's effective parallelism too (validate passes no -n; addopts supplies -n 8) — parity holds.

---

### Task 15: Measurements record + M1 blind-spot findings (spec §6)

**Files:**
- Create/modify: `docs/development/fast-confidence-loop-measurements.md` (scaffolded in Task 8, completed here)

**Interfaces:**
- Consumes: every task's recorded numbers.
- Produces: the spec §6 "notes doc under docs/development/" exit artifact.

- [ ] **Step 1: Fill the six-row table** (measured/expected values from this plan's tasks — rows 1–2 from Tasks 8/9 runs, row 2's frontend number from Task 3 Step 4's parallel-env full-suite run: re-run it as `VITEST_PARALLEL=1 VITEST_MAX_WORKERS=16 VITEST_HEAP_MB=32768 npm run test --prefix frontend -- --run` full-suite on the GB300, wall-clock target <10 min, plus the §6 previously-flaky 18-file set green-alone equivalence (rerun `/tmp/t7-vt-18.sh` shape under the envs); row 3 from Task 12; row 4 from Tasks 1/4 acceptance outputs; row 5 = the literal `git diff M1..HEAD -- scripts/validate.sh pyproject.toml` quote with the two sanctioned deltas annotated; row 6 = "allowlist empty, zero blanket retries: `grep -c 'for attempt' ci.yml` → 0".)

- [ ] **Step 2: Append the three M1 CI-blind-spot findings** (each with the evidence pointer already in the M1 ledger): profiler-disabled-in-CI masked the pyroscope aarch64 crash class; the frontend exit-0 hack hid the R-T7-VITEST class for months; zero-byte tracked test files lived green on main (now Task 1's class).

- [ ] **Step 3: Commit**

```bash
git add docs/development/fast-confidence-loop-measurements.md
git commit -m "docs: fast-confidence-loop measurements record + M1 CI blind spots (spec 6)

Co-Authored-By: Claude Code <noreply@anthropic.com>"
```

---

## Plan-level self-review record

- **Spec coverage:** §3.1→Tasks 5–8; §3.2→Task 9; §3.3→Tasks 3–4; §4.1→Tasks 10–13; §4.2→Global Constraints (byte-identity) + Task 13 Step 2; §5.1→Task 4; §5.2→Task 2; §5.3→Task 1; §5.4→Task 14; §6 rows→Task 15; §7 enforced in Global Constraints; §8 needs no task (settled decision); §9 ordering = plan order + the M1 hard gate in Global Constraints. One deliberate deviation, ruled: §4.1's illustrative naming-table becomes import-truth selection (Task 10's rationale block). Two spec-text corrections ruled: the "3 smoke files named in validate.sh's contracts step" (§4.1) do not exist — the smoke set is `backend/tests/contracts/`; the five §5.2 exit-0 sites are four retry masks + one legitimate summary-job skip-bypass (Task 2 header).
- **Placeholder scan:** the Task 13 draft intentionally shows two candidate shapes for FE-count capture and mandates one (`if ! X=$(...)` guard form) — executor deletes the other; `_sweep_stale_worker_dbs`'s `...` names its exact source template (root conftest :824-860 body, prefix parameterized) — fill-in, not TBD, because the body is 30 lines of already-existing repo code the executor copies with the prefix swapped. Everything else carries complete code.
- **Type consistency:** `worker_id()`/`worker_db_name(base_url)`/`_create_worker_database(base_url, name)`/`_drop_worker_database(base_url, name)` used identically in Tasks 5/6/7; `VITEST_PARALLEL/VITEST_MAX_WORKERS/VITEST_HEAP_MB` spelled identically in Tasks 3/4/11; `SELECTED-BACKEND-FILES:`/`SELECTED-FRONTEND-FILES:` lines produced in Tasks 10/11 and consumed in Task 13; `--list-out` produced Task 10, consumed Tasks 12/13.
- **Reviewer-facing rulings embedded at point of use** (deviation risk is highest where the plan diverges from spec text): Task 10 (mechanism), Task 2 (4-vs-5 sites), Task 8 (conditional flag removal), Task 14 (backend-only nightly v1).

# M2 Tasks 10+11 draft — fast selection (wave-3, t10 subdir)

Draft-only. Repo untouched (verified: `git status --porcelain` clean at fa6521ea before
and after this draft; no repo writes of any kind — read-only git only).

## Deliverables

- `m2-t10-t11.patch` — 4 new files, `git apply --check` **rc=0 vs HEAD (fa6521ea)** from
  repo root, AND rc=0 stacked after `/tmp/t3-draft/t3.patch` + `/tmp/wave2-drafts/t4/ci-frontend-honesty.patch`
  (full stack apply proven in a /tmp clone at fa6521ea: /tmp/wave3-drafts/t10/stackcheck —
  t3 rc=0, t4 rc=0, mine STACK_RC=0; file modes land 755/755/644/644).
  Collision check vs queued drafts: t3 touches frontend/vite.config.ts + frontend/package.json +
  scripts/validate.sh; t4 touches .github/workflows/ci.yml; m3-static is docs/analysis — no path
  overlap with scripts/fast_select.py, scripts/test_fast_select.py, scripts/fast-frontend-runner.sh,
  scripts/fast-backend-runner.sh (all four verified absent at HEAD).
- `new-files/scripts/{fast_select.py,test_fast_select.py,fast-frontend-runner.sh,fast-backend-runner.sh}`
- `logic-smoke.sh` — ran it: **14/14 PASS** (stdlib python3 + throwaway /tmp git repos only;
  zero pytest/vitest/npm; smoke exits before any pytest/npx line in every case — cases 11-14 hit
  only the runners' early-exit guard branches).

## Deviations from the plan's verbatim listings (each smoke-proven)

1. **fast_select.py — prefix-aware dotted lookup (`referrers()` helper).** The plan's Step-3
   listing uses exact-match `index.get(dotted, [])` (plan:1783) while its own Step-1 fixture
   test (`test_patch_string_reference_counts`, plan:1693) references the DEEPER path
   `backend.api.routes.metrics.get_x` for a change to `backend/api/routes/metrics.py` —
   the plan's implementation fails the plan's own test (smoke case 2 reproduced the failure,
   then the fix). Prefix match keeps attribute-path patch targets and lazy attribute refs;
   over-selection direction only (safe side for an advisory tier), same class as the plan's
   own docstring-prose GOTCHA.
2. **fast-frontend-runner.sh — loud base/repo verification (exit 2).** The plan's listing pipes
   `git diff --name-only "$BASE" | sed ...`; a pipeline's exit code is sed's, so an unreachable
   BASE_REF (typo'd VALIDATE_BASE) or non-repo cwd printed "nothing affected" and exited 0 —
   a GREEN fast tier that ran zero frontend tests, the exact silent-empty class the plan's
   Task-10 exit-2 rule prohibits. Smoke case 13 proves rc=2 on a bad ref now. (The backend
   side needed no change: fast_select's direct git() wrapper already exits 2 — case 8.)
3. **fast-frontend-runner.sh — count-line grep fixed.** Plan's regex demanded digits BEFORE
   the label; vitest's default summary is `Test Files  N passed (N)` (label first). Rewrote as
   label-anchor + first-number. [UNVERIFIED against live 4.0.18 reporter output — Task 11 Step 2
   live calibration is its first real run; that calibration IS the plan's stated deliverable
   for that step, box is leased.]
4. **fast-frontend-runner.sh — added base-ref existence check but kept `cd "$(dirname "$0")/.."`**
   (repo-root anchor; plan-verbatim).

Everything else is plan-verbatim: task numbering (Task 10 includes fast-backend-runner.sh, the
plan's Files list :1603-1606 — it was NOT folded into Task 11 as the orchestrator brief
suggested; shipping it since the patch is the "full Task 10/11"); test file verbatim from plan
Step 1 (6 tests, `python3`-compatible via subprocess — the plan's own design); SELECTED:/
--why/UNMAPPED/POLICY-SKIP/SELECTED-BACKEND-FILES: machine lines; smoke tier =
backend/tests/contracts (4 files on disk, verified: test_api_contracts /
test_openapi_schema_validation / test_schemathesis_contracts / test_websocket_contracts);
NODE_OPTIONS heap replication matches frontend/package.json `"test"` script (8192, VITEST_HEAP_MB
override aligns with the t3-draft package.json env-driven form); the FAST TIER footer +
SELECTED: aggregate header are Task 13's contract (spec §4.1) — NOT printed here by design
(plan Task 13's run_fast_validation emits them from the count lines).

## House-style checks

- stdlib-only (argparse/subprocess/re/pathlib); `--base` is the required seam (analog of
  check-flake-allowlist.py's --file/--today, scripts/check-flake-allowlist.py:1-70);
  `main(argv) -> int` + `sys.exit(main(sys.argv))`; E501 ignored repo-wide (pyproject.toml:330)
  and scripts/** per-file-ignores already carry T201/S603/S607 (pyproject.toml:411-420) —
  scripts are ruff-pre-commit covered (no exclude), so no T201 print-flags expected. [UNVERIFIED:
  ruff itself not run — box leased.]
- Modes match house mix (scripts/test_check_flake_allowlist.py is 644; shell runners 755).
- No spaces under git ls-files frontend/src (verified) → word-splitting convention safe.

## verifyPlan (micro slots, AFTER gate 14 closes — NOTHING was run now)

1. `uv run pytest scripts/test_fast_select.py -v -p no:randomly -o addopts=""` (expect 6 pass;
   the -o addopts="" is mandatory: pyproject addopts = `-n 8 …` (pyproject.toml:470)).
2. Live vitest-related calibration (Task 11 Step 2 shapes a/b/c) when pytest idle AND box free —
   this also finalizes risk #3's regex; record final regex in commit per plan.
3. Read-only live sanity (no tests run, allowed any time): `python3 scripts/fast_select.py
   --base "$(git merge-base HEAD origin/main)" --why | tail -8` → expect
   `SELECTED-BACKEND-FILES: 0` on docs-only tail. NOTE: no local `main` ref exists at
   fa6521ea (verified: rev-parse --verify main fails; only remotes/origin/main) — the plan's
   literal `merge-base HEAD main` (and Task 13's default base, plan:2110) needs `origin/main`
   or VALIDATE_BASE here; flag for the measurements doc. NOT run now: it enumerates+reads the
   real 913-file backend/tests tree (read-only, but reserved for the micro slot to keep the
   leased box's I/O clean).
4. `git apply --check` both cold (rc=0 proven now) and re-proven immediately before landing
   (ledger/plan docs churn can't collide — disjoint paths — but re-check is one command).

## Apply gates for the orchestrator

- Gate: pytest full-suite GREEN close-out (gate 14) — these files are inert-additive pre-close-out
  (scripts/ outside testpaths, pyproject.toml:464; fast-frontend-runner.sh is not referenced by
  any entry point until Task 13 lands the --fast dispatch).
- Gate: the Step-2 live calibration must land in the SAME commit as fast-frontend-runner.sh per
  plan ("record the final regex in the commit") — current regex is [UNVERIFIED] until then.
- Gate: Task 13 consumes `--list-out`/count-line contracts unchanged — keep stdout machine lines
  frozen.

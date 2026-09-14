# M2 Task 4 — CI frontend honesty (spec §5.1) — draft apply notes

Draft-only. No repo file was modified (repo untouched at HEAD `439cb23b` on
`feat/context-map-2026-09-12`). Patch verified:
`git apply --check /tmp/wave2-drafts/t4/ci-frontend-honesty.patch` → PASS
(1 file `.github/workflows/ci.yml`, +57/−40), plus YAML safe_load of the
resulting file (frontend-tests job parses, 8 steps). Scratch copies used to
generate the diff: `ci.yml.orig` (= HEAD blob) and `ci.yml.new` (= intended
post-apply file) sit next to the patch for reviewer diffing.

## Anchor points (plan line numbers stale; these are CURRENT HEAD 439cb23b)

| Thing | Plan said | Actual at HEAD |
| --- | --- | --- |
| frontend-tests job | — | `ci.yml:1231-1337` (job start :1231, matrix :1243-1248, env :1249-1253) |
| job env `NODE_OPTIONS: '--max-old-space-size=6144 --expose-gc'` | :1240-1244 | **:1253** |
| hack step `- name: Run tests (shard ...)` | :1296-1321 | **:1293-1329** (background+tee :1308, polling grep :1313-1314, `pkill -9 -P` :1319, `exit 0` :1322, legacy `wait`/`exit $?` :1328-1329) |
| coverage upload (`if: always()`) | :1323-1328 | :1331-1337 — untouched |
| T2 rerun convention reference | — | `ci.yml:455-463` (api), 571-579 (websocket), 687-695, 795-803 |
| collection-sanity hygiene step | — | `ci.yml:92-93` (T2 landed; confirmed) |
| flake allowlist | — | `.github/flake-allowlist.yml` (`flakes: []`), relocated by 17b62e1c; filter `scripts/flake-k-filter.py` (stdlib-only, prints ids `" or "`-joined, expired excluded) |

The frontend-tests job text is byte-identical between 17b62e1c (T2 landing) and
HEAD 439cb23b (md5 of the :1231-1340 region matches; later commits are docs-only).

## Diff rationale (and deliberate deviations from the plan snippet)

1. **Hack deleted, real exit code installed.** `set -euo pipefail` + direct
   foreground `npx vitest run ... | tee` makes vitest's exit status the step's
   verdict (pipefail defeats tee masking). `--reporter=default` drops the
   verbose mode the hack's regex consumed; nothing downstream parses the log
   (coverage-merge consumes the uploaded artifact, `if: always()`; grep of all
   `.github/workflows/*.yml` + `scripts/` for consumers of the vitest stdout
   finds none). Tee target is now per-shard `/tmp/vitest-shard-${{ matrix.shard }}.log`
   (scratch only; runner-local).
2. **Job env heap NOT changed** (plan said 6144→4096; patch leaves 6144 and
   adds a comment). Evidence: design §3.3 "Follow-up … gated on a measured CI
   runner OOM fix: raise the 8192 MB cap for CI too. **Until then CI behavior
   is byte-identical to today's**" and §5.1 "`--no-file-parallelism` only if a
   measured runner OOM demands it". Today's CI is sequential + 6144; the plan
   snippet's 2-fork parallel layout (and its 4 GB budget arithmetic) presupposes
   turning parallelism ON in CI, which §3.3 gates behind a *measured* issue.
   The orchestrator brief rules the same way ("CI defaults stay sequential …
   unless a measured OOM issue is referenced"). `--expose-gc` kept —
   `frontend/src/test/setup.ts:149` calls `global.gc` when present.
3. **`VITEST_PARALLEL: '0'` (explicit), not `'1'`/`'2'-workers`.** Consumes
   T3's contract at its default-off corner: vite.config.ts post-T3 reads
   `fileParallelism: process.env.VITEST_PARALLEL === '1'` → false; `maxWorkers`
   inert (vitest 4 forces 1 when fileParallelism is false — cited in
   /tmp/t3-draft/apply-notes.md). Explicit `'0'` is documentation + immune to
   any future config flip that treats unset differently. `VITEST_MAX_WORKERS`
   deliberately unset (inert when sequential). `VITEST_HEAP_MB` deliberately
   NOT set: the step calls `npx` directly, bypassing the package.json
   npm-script wrapper where T3 reads that var (plan Interfaces says exactly
   this: "the heap cap in CI travels via NODE_OPTIONS because the step calls
   npx directly"). No conflict anywhere: the ONLY vitest heap/worker settings
   in all workflows are ci.yml:1253 (this job's NODE_OPTIONS) — grep for
   `--max-workers|max-old-space|VITEST_` across `.github/workflows/*` shows no
   other occurrence; `frontend-e2e*` jobs run playwright, not vitest.
4. **T2's apply-flake-reruns convention ported to vitest** (the brief's ask):
   - new step *Detect registered frontend flakes* runs
     `python3 scripts/flake-k-filter.py` (stdlib-only — bare python3; the job
     has no uv setup step, unlike the pytest jobs), converts the pytest `-k`
     expression to vitest's JS-regex `--testNamePattern` (`" or "` → `|`;
     ids are pytest/vitest-name-shaped so `|` alternation is the right
     translation — flagged below as the one judgment call).
   - new step *Run registered flakes first* mirrors the pytest jobs' ordering
     and shape exactly: runs **before** the strict run, `--retry 2` ≈
     `--reruns 2`, `|| true` ≈ their `|| true`, guarded by
     `if: env.RERUN_PATTERN != ''`. `--passWithNoTests` is vitest-specific and
     required: an allowlisted id lands in exactly 1/16 shards, and vitest
     4.0.18 exits 1 with "No test files found" otherwise (verified in
     `node_modules/vitest/dist/chunks/index.M8mOzt4Y.js:3391` +
     `cli-api.B7PN_QUv.js:6567`; the flag is a registered CLI option in
     `cac.DVeoLl0M.js:898`).
   - Honesty is preserved by the *strict* run being unconditional with a real
     exit code — the rerun pass can never green a failing shard (same
     end-to-end property T2's five pytest sites have). Note faithfully-porting
     T2's semantics also carries its known limitation: the strict run does not
     exclude allowlisted ids, so an allowlisted flake still has to survive one
     un-retried attempt. Changing that is T2-scope policy, not this patch's.
   - With today's empty allowlist both new steps are no-ops
     (`RERUN_PATTERN=''` → rerun step skipped entirely).
5. **Comments preserve the OOM history** (the deleted "cleanup takes 5+
   minutes and OOMs" note is answered in the new comment: bounds stay
   pool=forks/isolate/sequential/6144; OOM recurrence ⇒ runner conversation
   per design §5 item 5, never the hack).

## Acceptance verification on GitHub Actions (branch is pushed; HEAD 439cb23b)

Plan §6 row 4 / Task 4 acceptance: *an intentionally failing frontend test
turns the job RED*. Do it as a self-reverting probe PR against
`feat/context-map-2026-09-12` (or a branch off it carrying this patch):

1. Apply this patch to the repo, commit.
2. `git checkout -b probe/t4-honesty-<date>`; add exactly one file
   `frontend/src/injected-fail.probe.test.ts`:
   `import { describe, it, expect } from "vitest";\ndescribe("injected", () => { it("fails on purpose", () => { expect(1).toBe(2); }); });`
   Commit and push the probe branch (`git push -u origin probe/t4-honesty-…` —
   proxy handles auth; PR `gh pr create --base feat/context-map-2026-09-12 --fill`).
3. In the PR's Actions run, **detect-changes must show `frontend: true`**
   (`frontend/**` filter, ci.yml:48-50). Frontend Tests shards run after
   frontend-lint.
4. **Expected RED, at three levels:** exactly one `Frontend Tests (Vitest N/16)`
   shard job fails (the shard whose 1/16 slice contains the probe file —
   vitest shards partition the file list; 797 tracked `*.test.ts(x)` files on
   disk so no shard empties); `Frontend Tests (Vitest)` (frontend-tests-summary)
   shows ❌ via ci.yml:1390-1392 (`needs.frontend-tests.result == failure` →
   exit 1); `CI Gate (Required Checks)` shows ❌ `Frontend Tests (Vitest)`
   (ci.yml:2514 check_job line). Under the old hack every level was ✅ — a
   useful before/after contrast to quote in the PR: a probe pushed against the
   pre-patch tree must stay green (the bug), post-patch red (the fix).
5. **Also confirm no collateral:** frontend-coverage-merge stays green (it runs
   `always()` on uploaded artifacts, :1340-1369 untouched), and 15 innocent
   shards green (`fail-fast: false`, :1244).
6. Close the PR / delete the probe branch — probe never merges anywhere.

Optional pre-push proof of the step *body* without Actions (forbidden during
the current box lease, allowed after gate 14): run the plan Task 4 Step 2
1/16-shard recipe. During drafting this draft proved the exit-code mechanics
with a fake-vitest simulation only (`OLD-STEP-EXIT=0` vs `NEW-STEP-EXIT=1` on
a "passed line + exit 1" stub — scripts under /tmp/wave2-drafts/t4, deleted).

## What must NOT change (reviewers)

- **R-T7-VITEST quarantine `exclude` array** — `frontend/vite.config.ts:357-378`
  (16 files + defaults; patch touches zero bytes of that file).
- **Coverage bars / merge pipeline** — vite.config.ts thresholds (:414-421:
  stmts 83 / branches 77 / funcs 81 / lines 84), the "do NOT add --coverage"
  note (kept), `frontend-coverage-merge` (:1340+), codecov step,
  `test-coverage-gate.yml` — all untouched.
- Matrix 1..16 + `fail-fast: false` (:1243-1248), job `timeout-minutes: 10`,
  Node pinning, artifact names (`frontend-coverage-shard-*` glob consumed by
  the merge job — byte-identical).
- detect-changes path filters, frontend-tests-summary, ci-gate — untouched.
- The patch adds steps *only*; it removes nothing outside the hack step.

## Apply gates (conditions before applying)

1. **T3 landed** (patch `/tmp/t3-draft/t3.patch` still applies cleanly to HEAD
   — verified `git apply --check` rc=0 — meaning it is NOT yet in the tree).
   Technically T4 stays honest without T3 (`VITEST_PARALLEL: '0'` is inert
   pre-T3; plan GOTCHAS: "silently degrades … but stays honest"), but the env
   contract + "byte-identical" claim in the comment presuppose T3's config, and
   plan §9 orders 3→4. Apply T3 first or together.
2. **M1's final no-flag validate.sh run recorded** (plan Global Constraints:
   "Nothing in this plan merges while M1's final run is outstanding") —
   gate 14 result, [UNVERIFIED here; orchestrator owns].
3. **First-green confidence**: the honest job surfaces ANY non-quarantined
   frontend failure the hack hid. Gate-14's strict validate.sh frontend step
   (npm run test, exit-honest) on the same tree is the pre-evidence; if it's
   green for the frontend tier, first Actions run should be green
   [UNVERIFIED until gate 14 reports].
4. Nothing else — T2 already landed (17b62e1c); §5.3 collection-sanity
   hygiene present (:92-93).

## Risks

- **First-run red**: deterministic failures outside the 16-file quarantine
  would newly redden CI. This is the point of the task, but schedule the push
  for a window where a test-repair follow-up is staffed. Mitigation evidence:
  gate 14 (full validate, strict frontend step).
- **Teardown latency**: the hack killed cleanup at ~20 s; the honest step waits
  for real teardown. Old comment claimed 5+ min cleanup + OOM at 16→24-shard
  settings; per-shard corpus shrank since (quarantine + 16 shards), and
  teardownTimeout=1000 + isolate persist. Worst case is a 10-min job timeout =
  still RED = still honest. If it OOMs, apply §5.1's measured-exception path
  (never the hack).
- **`--testNamePattern` regex translation**: `" or "` → `|` assumes ids carry
  no regex metacharacters (pytest ids don't; JS-regex ids could). Empty
  allowlist today makes this theoretical; a future entry with metacharacters
  needs escaping — cheap to add when an entry exists.
- **GH expression `env.` context in step-level `if`**: supported since
  2021-11; a mis-evaluation would merely skip the (currently no-op) rerun step.
- Actions-only acceptance cannot be executed under the box lease; the
  three-level RED recipe above is the deploy-time proof.

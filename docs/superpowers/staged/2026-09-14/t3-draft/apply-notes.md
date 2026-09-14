# M2 Task 3 — apply notes (draft; patch = /tmp/t3-draft/t3.patch)

Draft-only. No repo file was modified. Patch verified with
`git apply --check /tmp/t3-draft/t3.patch` against HEAD `0e779506` on
`feat/context-map-2026-09-12` → PASS (3 files, +26/−6).

## Anchor points (plan line numbers were stale; these are CURRENT HEAD)

| File | Plan said | Actual anchor at HEAD |
| --- | --- | --- |
| `frontend/vite.config.ts` | :370–384 block, replace :372–378 | `pool: 'forks'` at **:380**; `fileParallelism: false` at **:383**; `isolate: true` at **:386**. Patch hunk `@@ -378,9 +378,17 @@`. |
| `scripts/validate.sh` | frontend vitest step :403–407 | `print_step "Running Vitest (Tests)..."` at **:479**; `if ! npm run test --prefix "$FRONTEND_DIR" -- --run; then` at **:480**. Patch hunk `@@ -477,7 +477,19 @@`. |
| `frontend/package.json` | test script :19 | `"test": "NODE_OPTIONS='--max-old-space-size=8192' vitest"` at **:19**; `test:coverage` at **:21**. Patch hunk `@@ -16,9 +16,9 @@`. |

## Deviations from the plan snippets (all deliberate, with evidence)

1. **`minWorkers: 1` dropped.** This repo pins vitest **4.0.18**
   (`frontend/package.json:119`, installed `node_modules/vitest@4.0.18`).
   `minWorkers` does not exist anywhere in vitest 4 dist (grep over
   `node_modules/vitest/dist/**` finds zero occurrences; the public config type
   `reporters.d.CWXNI2jG.d.ts` has only `maxWorkers?: number | string` and
   `fileParallelism?: boolean` — the v2-era `minForks`/`poolOptions.forks`
   warm-pool options were removed). The plan's snippet predates the v4 option
   surface; shipping `minWorkers: 1` would be dead config (vitest has no strict
   unknown-key error, so it would silently do nothing).
2. **`Number(process.env.VITEST_MAX_WORKERS || 4)` (gotcha form), not `?? 4`**
   from Step 1's snippet — the plan's own GOTCHAS section requires `||`
   (`Number('') === 0` and 0 means *unbounded* in vitest → fork-bomb risk on an
   exported-empty value).
3. **`print_info` does not exist in validate.sh.** Helper block (:54–67) has
   `print_step` / `print_success` / `print_error` / `print_warning` only. The
   plan pre-authorizes "use the file's existing info-level printer" → used
   `print_step` for the parallel-mode banner.
4. **validate.sh: added `MEM_KB="${MEM_KB:-0}"`** after the awk — if
   `/proc/meminfo` exists but awk prints nothing, the bare
   `[ "$MEM_KB" -ge … ]` would error under `set -e`; the `|| echo 0` only covers
   awk *failing*, not empty output. Belt for the macOS/read edge.
5. **package.json quote change is value-identical, not character-identical**
   (`'…'` → `"…"` so `${VITEST_HEAP_MB:-8192}` expands through npm's `sh -c`).
   With the env unset the effective NODE_OPTIONS string is
   `--max-old-space-size=8192` exactly as today, so spec §6 row 5's
   "byte-identical invocations" holds in *effect*; quote the diff in the PR.

## Env contract (VITEST_PARALLEL / VITEST_MAX_WORKERS / VITEST_HEAP_MB)

- **`VITEST_PARALLEL`** — read by `vite.config.ts`: `=== '1'` (exact) enables
  `fileParallelism`. Any other value (unset, `0`, `true`, `yes`) ⇒ sequential —
  and per vitest 4's own type doc, `fileParallelism: false` *overrides
  maxWorkers to 1*, so the default-off path is provably identical to today's
  behavior, not just similar. validate.sh auto-sets `VITEST_PARALLEL=1` only
  when RAM ≥ 64 GiB **and** the var isn't explicitly `0` (the `!= "0"` term is
  the big-box kill switch: `VITEST_PARALLEL=0 ./scripts/validate.sh` forces the
  inherited sequential mode even on the GB300).
- **`VITEST_MAX_WORKERS`** — read by `vite.config.ts` as
  `Number(env || 4)` (only meaningful when parallel is on; inert-then-forced-1
  otherwise). validate.sh defaults it to **8** inside the auto-parallel block,
  honoring a pre-set value. Empty-string export degrades to 4 (never 0/unbounded).
- **`VITEST_HEAP_MB`** — read twice: validate.sh's run line passes
  `VITEST_HEAP_MB="${VITEST_HEAP_MB:-8192}"` into npm's env (auto-block raises
  the default to 16384 on big boxes), and `package.json` `test`/`test:coverage`
  interpolate it into `--max-old-space-size`. The cap is **per Node process**:
  NODE_OPTIONS is inherited by every forked worker, so peak old-space budget is
  ~(workers + main) × heap. `test:ui` intentionally keeps the literal 8192
  (plan scoped only test + test:coverage).
- **Task 4 (CI honesty) and Task 12 (fast runner)** consume this same trio;
  nobody may reinterpret the `'1'`-exactness or the 0-is-unbounded guard.

## Default-off byte-identical argument (patch-reviewer checklist)

- No env ⇒ `fileParallelism:false` (same), maxWorkers ignored→1 (same),
  isolate:true untouched, `--max-old-space-size=8192` (same effective string),
  validate.sh runs `sh`-identical step (added lines only set unexported
  defaults when the RAM test fails; the only inline env on the npm line equals
  today's package.json literal).
- The R-T7-VITEST **16-file quarantine `exclude` array
  (vite.config.ts:357–378) is untouched by the patch** — the hunk begins at
  :378 context and edits nothing above `pool: 'forks'`. Keep it that way through
  any rebase; Task 3 is config-only and must not touch quarantine entries.

## Plan Steps 3/4/5 (verification + commit) were NOT executed

Box lease: a full validation gate is running on this host; Steps 3 and 4 spawn
vitest and are forbidden here. The acceptance procedure (including what Step 4
timing must record) is specified in `/tmp/t3-draft/measurement-plan.md`. Step 5
commit message template in the plan is fine as-is; files: `frontend/vite.config.ts
frontend/package.json scripts/validate.sh`, one commit, trailer
`Co-Authored-By: Claude/Code...` → exactly `Co-Authored-By: Claude Code <noreply@anthropic.com>`.

# Wave-3 drafts — M2 Tasks 13/14/15 (DRAFT-ONLY; repo never touched)

Repo `/agents/agent-nemo2/workspace`, branch `feat/context-map-2026-09-12` @
`fa6521ea`. All patches verified `git apply --check` **from the repo root**:
t13 rc=0, t14 (both variants) rc=0. `git status --porcelain` clean before and
after. Gate-14 (pid 941436, `/tmp/validate-full-14.log`) never signaled — no
pytest/vitest/npm/validate.sh/compose/build executed; only file reads,
read-only git, stdlib-only python3 over /tmp + in-memory patch simulation.

## Files

| File | What |
| --- | --- |
| `t13-validate-fast-wiring.patch` | validate.sh `--fast` + scripts/AGENTS.md docs sync; +93/−0; every hunk carries (in the patch-header block and in-function comments) its M1 §6 gating note |
| `t14-nightly-workflow.patch` | creates `.github/workflows/nightly-full-gate.yml` (dispatch+schedule) |
| `t14-nightly-workflow-schedule-only.patch` | the schedule-only-on-full-gate variant (see §T14 below) |
| `t15-measurements-prefill.md` | Task 15 table, ledger rows prefilled, pending arms blank |
| `nightly-full-gate.yml`, `…-schedule-only.yml`, `validate.sh.new`, `AGENTS.md.new`, `validate.sh.orig`, `AGENTS.md.orig`, `validate.sh.post-t3` | inputs/intermediates (post-T3 simulation artifact) |

## T13 — inertness proof without the flag (required by the brief)

`git apply --stat`: **93 insertions, 0 deletions** — no existing line of
validate.sh is modified. The new *executable* content is exactly two sites,
both unreachable without `--fast`:

1. Arg-parser case arm `--fast)` — can only match when the literal flag is on
   the command line. `--bogus` still falls to the unchanged `*)` exit-1
   branch (context-map verify: parser case arms are exhaustive-match; the
   catch-all is untouched, patch hunk inserts *before* it).
2. Dispatch `if [ "$RUN_FAST" = true ]; then run_fast_validation; exit 0; fi`
   — `RUN_FAST` is initialized `false` (the one other new executable line: an
   assignment) and only flipped by the case arm. Without the flag the
   `if` tests false and control reaches the untouched
   `if [ "$RUN_BACKEND" = true ]` block — the exact bytes that ran before.

Everything else is a function *definition* (`run_fast_validation`, never
called unless dispatched), comments, help/header text, and AGENTS.md prose.
Under `set -e` a function definition has zero side effects. No-flag,
`--backend`, `--frontend` execution paths are byte-identical to HEAD.
`sh -n validate.sh.new` passes (POSIX syntax check; sh is dash here).

**Committed-shape ruling:** the plan shows two candidate shapes for FE-count
capture and mandates the `if ! X=$(...)` guard form — the patch uses the
guard form for all three runner calls, pipes nowhere (validate.sh is `sh`
without pipefail: a `| tee` would mask the runner's verdict — the exact
ci.yml retry-mask class the spec kills), one accumulated EXIT trap declaring
both mktemp files (POSIX trap overwrites, plan GOTCHAS). `main` fallback via
`git rev-parse --verify -q main || echo origin/main` inside the base-ref
default (plan GOTCHAS). Aggregate header prints
`SELECTED: n files total (backend: … via import-truth, frontend: … via
related, smoke: contracts-included-when-api-changed)` — spec §4.1 says
"n tests across m files"; the runners only *report* file counts
(`SELECTED-BACKEND-FILES:`/`SELECTED-FRONTEND-FILES:`, plan :1741/:1955), so
"files" is the truthful unit — flagged as a deliberate spec-text deviation
for the measurements doc, consistent with Task 10's ruled deviations.
Footer string is the plan's verbatim; `VALIDATION SUCCESSFUL` is emitted
only by the untouched final banner.

**Consumed contract (not yet on disk):** `scripts/fast_select.py`,
`scripts/fast-backend-runner.sh`, `scripts/fast-frontend-runner.sh` —
verified ABSENT at fa6521ea (`ls scripts/` shows only `test-fast.sh`, an
unrelated M1-era runner). T13 cannot be *run* until T10–T12 land; it applies
clean regardless (the flag path simply errors loudly via the existing
`print_error` guards if the files are missing — acceptable since apply-gate
ordering puts T13 after them anyway).

**AGENTS.md sync:** the plan names `scripts/AGENTS.md :303-316`; at HEAD the
validate.sh block is :298-313 — patch anchors are content-matched so the
drift is moot. The AGENTS.md hunk adds the `--fast` line under Usage plus an
HTML-comment TODO recording an *existing* staleness finding (block says
"95% coverage", validate.sh gates combined 80; test-runner.sh docstring says
80) — flagged for the M3 static census rather than silently fixed, since
that census (a queued wave-2 draft, `/tmp/wave2-drafts/m3-static/`) owns
census edits. If the census patch touches the same :295-316 region, apply
the census first and re-anchor this 9-line hunk (small overlap risk — see
collision).

## Collision analysis

### vs /tmp/t3-draft/t3.patch (both touch scripts/validate.sh)

Simulated by in-memory python patch application (stdlib only):
- T3 old-range in validate.sh: **lines 477-483** (frontend vitest step).
- T13 old-ranges: **11-16, 27-32, 78-88, 191-196, 508-513, 516-521**.
- **Overlap: none.** T3→T13 stacks OK (626 lines); T13→T3 also stacks OK.
  Contexts are disjoint so `git apply` order-independently succeeds, BUT the
  *line numbers* shift (T3 adds +12 lines before T13's :508 hunk; git's
  offset search absorbs it). **Required apply order: none forced by content;
  recommended T3 first** because T13's hunk contexts at :508-521 sit AFTER
  the T3 region and git offset-matching is more robust applying downward;
  `validate.sh.post-t3` is provided if the orchestrator wants a pre-stacked
  base (regenerate: `git show HEAD:scripts/validate.sh` + t3.patch).

### vs /tmp/wave2-drafts/t4 (ci.yml only)

No file overlap with T13/T14 (t4 modifies `.github/workflows/ci.yml`; my T14
creates NEW files under `.github/workflows/`). No git-apply interaction.
Semantic interaction: my nightly frontend job is honest-exit BY DESIGN and
explicitly does not wait on T4 — T4 fixes ci.yml's push job; the nightly is
independent (plan Task 14 "Consumes honest CI" is about the *pattern*, and I
note below where the plan's premise is stale).

### vs m3-static censuses (docs)

Possible contact ONLY at `scripts/AGENTS.md` validate.sh block (see above).
All other census targets (config READMEs etc.) disjoint.

### vs /tmp/wave3-drafts/t10 (queued)

T10's `scripts/fast_select.py` is a NEW file; no collision. T13 consumes its
CLI contract: `--base REF --list-out FILE [--why]` and the
`SELECTED-BACKEND-FILES: N` stdout line (plan :1741/:1850). If T10's draft
names the runner `fast-backend-runner.sh` differently, update T13's two call
sites — contract pinned in this note.

## T14 — nightly full gate

**Does the nightly reference `--fast`? NO.** Grep-verified my workflow
contains no `--fast`, no `fast_select`/`fast-*-runner` references (full gate
is --fast-free per spec §4.2). The T13 dependency is therefore *one-way*:
none. What T14 does depend on: (a) the M1 §6 green record (plan Global
Constraints bind the whole plan behind it), and (b) ci.yml honesty (Tasks
1-2/4) for the FRONTEND honesty claim — which is why I shipped the schedule-
only variant question below.

**Deviation from plan draft (recorded):** the plan's draft workflow
`pytest backend --cov-fail-under=80` contradicts plan §4.2/T15-row-5
("byte-identical vs M1-final validate.sh") — validate.sh's M1-final shape is
the D14 split + combine + `--ignore ×4` (incl. chaos) + combined 80. A
single-process nightly pytest is NOT that shape. My draft mirrors the D14
split exactly. Also fixed from the plan snippet: it used `docker run`
containers + `security/security_dev_password` creds — adopted ci.yml's
`services:` pattern + ci.yml creds (`postgres/postgres@security_test`, the
byte-parity fallback the plan's own GOTCHAS pre-authorizes), added
`concurrency` (test_github_workflows.TestConcurrencyConfig only requires it
for ci.yml, but the meta-test's action-pin check at :211-228 requires every
`uses:` be `@`-pinned — mine are sha-pinned; runner label `ubuntu-latest` is
in its VALID_RUNNERS set), and made honesty reporting artifact-derived
(coverage re-read from merged data file, vitest status = process exit, no
`|| true` on verdicts, no un-pipefail'd `| tee` on any status-bearing line
— GH `run:` default shell is bash with pipefail off, so I redirect to files
everywhere instead of piping; bashisms like `pipefail`/`>(…)` are avoided
entirely; `set -e` + explicit `$?` capture is plain).

**Schedule-only variant (`t14-nightly-workflow-schedule-only.yml`):** the
brief asked "does T14 reference --fast's runners? if so note T13 dependency
and draft the schedule-only variant separately." It does not, so BOTH
variants are drafted anyway as a *different* fork: draft A keeps
`workflow_dispatch` (manual re-runs needed for the §6.1 green×2 evidence
chain and T14 Step 2's "dispatch once manually"); draft B drops dispatch so
the nightly is purely the §5.4 "ran somewhere trustworthy yesterday"
artifact with zero interactive surface until T13+T4 land (owner preference
between A and B is a STOP-AND-ASK candidate — A strictly dominates for
measurement gathering; I recommend A). Both pass structural YAML checks
(stdlib validator: top-level keys, per-job runs-on/steps, step name/run/uses
presence, action `@`-pinning; only the services `ports:` list items
false-flagged, matching ci.yml's shipped shape).

**Apply gates (T14):** M1 §6 record; owner decision A-vs-B; ideally after
T4 (ci.yml honesty) so the nightly is the only honest full-suite *scheduled*
run while push jobs catch up — NOT after T13 (no dependency).

## T15 — prefill provenance (every prefilled number)

- `2981.18s` serial frontend baseline — /tmp/validate-full-10.log:35473
  `Duration 2981.18s` (verified: awk NR==35473 hits).
- `618.53s` runA2 — docs/plans/2026-09-12-context-map-doc-updates.md:1973,
  :1977 (green, verified: 4165 passed/131 skipped/2 xfailed).
- `597.47s` gate-13 — same file :2158 (RED tier, 11 failed — marked NOT
  quotable as green; −3.4% within noise).
- `87.96%` combined coverage — ledger :1792; literal TOTAL line also at
  /tmp/validate-full-10.log:30 (verified).
- 919.75s pre-T4, teardown 1.043→0.224s, setup p90 1.161s — ledger :1973-
  :1984 region.
- Box reality 16 cores/62.69 GiB — /tmp/t3-draft/measurement-plan.md +
  corroborated here (`/proc/meminfo` read-only).
- `flake-allowlist` at `.github/` NOT `.github/workflows/` — gate-13
  postmortem lesson (test_github_workflows.py:64 globs workflows dir;
  verified at HEAD: the meta-test exists, glob at :64).
- ci.yml retry sites at fa6521ea: 4 integration pytest loops TORN DOWN
  (grep `set -euo pipefail` = 4, all in integration jobs; the api `if pytest
  | tee`-without-pipefail mask class is dead), but **5 `for attempt in 1 2 3`
  loops REMAIN** — frontend npm ci install + Playwright browser installs +
  **Playwright E2E test retries (:1491, :1626)**. The last two are blanket
  TEST retries: §5.2's allowlist intent ("un-allowlisted failures fail once
  and stay failed") arguably covers them; spec §6 row 6 "zero blanket
  retries remain" cannot be signed while they live. **STOP-AND-ASK candidate
  #10 for the owner memo** (the memo currently lists nine).
- M1 §6 anchor `validate.sh exit 0 (coverage gate 80 combined)` —
  milestone1-design.md:178.

## Verify-plan (for whoever applies; NOT run here — box leased to gate 14)

1. After gate 14 completes: `sh -n scripts/validate.sh` (already rc 0 on the
   patched file here), `git apply --check` all three patches at apply-time
   HEAD (anchors may drift; contexts verified against fa6521ea).
2. Inertness acceptance: `./scripts/validate.sh --bogus` → still exit 1 with
   the same two lines; `--help` shows the new line; a no-flag run's first 30
   lines byte-compare against a gate-14 log prefix (excluding timestamps).
3. `--fast` needs T10-T12 scripts on disk; run plan Task 13 Step 2 matrix on
   a docs-only diff (expect SELECTED: 0/0 footer, no banner, tree unchanged
   after).
4. YAML: `python -c "import yaml; yaml.safe_load(...)"` +
   `pytest backend/tests/integration/test_github_workflows.py -k workflows`
   (meta-test must accept the new files: name/on/jobs keys present, runners
   valid, actions pinned — structurally confirmed by stdlib checks here; the
   live meta-test run is a pytest gate → box slot).
5. First nightly: `gh workflow run` after push, record duration + coverage
   in the T15 row.

## Residual risks

- T13 header prints file counts where spec §4.1 said tests/ files breakdown
  wording — deviation recorded in the patch's footer wording (deliberate).
- Nightly timeout bounds (240 min) are estimates on hosted runners
  [UNVERIFIED]; integration alone measured 597-620s on THIS box, unit tier
  + hosted-runner drag dominate.
- `fast-frontend-runner.sh`'s output contract (where its
  `SELECTED-FRONTEND-FILES:` line lands — stdout vs stderr) is T11's; T13
  captures with `2>&1` into the assignment (safe for both) — if T11 prints
  the count to stderr only, `FE_N` still parses because the capture merges.
- `coverage combine --data-file=` semantics assume the repo's
  coverage-version — validate.sh uses the identical flag today (file:356
  region), so parity by construction.

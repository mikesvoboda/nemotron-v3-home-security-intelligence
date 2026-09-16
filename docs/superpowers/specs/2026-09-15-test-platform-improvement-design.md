# Test Platform Improvement — Design

**Status:** approved design, ready for implementation planning
**Date:** 2026-09-15
**Companion documents:** [`docs/plans/2026-09-15-revival-timeline.md`](../../plans/2026-09-15-revival-timeline.md) (how we got here), [`docs/plans/2026-09-12-context-map-doc-updates.md`](../../plans/2026-09-12-context-map-doc-updates.md) (the ledger, ground truth for every gate row and ruling)

## Problem

The codebase is ~2.0M lines of code. Backend carries 659k lines of test code
against 294k lines of production Python — a 2.24:1 ratio. The full local gate
takes ~20 minutes; a CI run takes ~45 minutes of which roughly 13 are queueing.
Developers wait too long between commits.

Separately, the 2026-09-12 revival discovered that tests had been written,
tracked in git, and counted toward coverage while silently not running. That
class of defect must be made structurally impossible, not merely fixed once.

Four goals, in the owner's words: reduce iteration time before pushing; prevent
recurrence of tests that should run but don't; audit whether good patterns are
enforced and whether tests genuinely exercise production code; find
opportunities to make coverage more performant and reliable.

## Decisions (locked by owner, 2026-09-15)

| #   | Decision                                                                                                                  |
| --- | ------------------------------------------------------------------------------------------------------------------------- |
| 1   | One phased program spec, internally sequenced so implementation can stop at any phase boundary with value delivered       |
| 2   | Pre-push target **under 5 minutes**, impact-scoped. The full suite remains authoritative, in CI                           |
| 3   | **Hard ratchet with expiry.** Suppression counts may only decrease; every entry carries an owner and an expiry date       |
| 4   | Self-hosted GB300 (arm64) runs the fast authoritative path; hosted amd64 retained for architecture parity on main/nightly |
| 5   | Test-corpus consolidation is **in scope**, gated on mutation-testing evidence that a test is worthless before removing it |

## What is actually true today

Establishing this precisely matters, because the intuitive framing ("CI is
broken") is wrong and would misdirect the work.

**The test suite is green.** On the most recent `main` run, every test job
passes: backend unit (4/4 shards), backend integration, frontend Vitest (16/16
shards), E2E (6/6 Chromium shards), contract tests, collection sanity. The
required `ci-gate` check succeeds. Combined backend coverage is 87.9% against an
85% floor.

**The `ci.yml` workflow badge is nevertheless red, and has been since
2026-02-25.** The cause is four non-gating jobs, three of which report real
problems that nobody reads:

| Job                    | Reporting                                                                                                | Assessment                           |
| ---------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| Dead Code Detection    | vulture flags unused pytest fixture variables (`clean_tracker`, `real_session_store`, `mock_run_sudo`)   | False positive; needs a whitelist    |
| Test Performance Audit | `FAIL — 46 tests exceeded time limit`; integration tests at ~4.0s against a 5s budget                    | True, and relevant to the speed goal |
| Trivy (backend-deps)   | `cryptography` GHSA-537c-gmf6-5ccf (vulnerable OpenSSL, fixed 48.0.1); `pyarrow` CVE-2026-25087 (23.0.1) | True, unpatched                      |
| Trivy (frontend-deps)  | `serialize-javascript` GHSA-5c6j-r48x-rmvq (RCE, fixed 7.0.3); CVE-2026-27606                            | True, unpatched                      |

A permanently-red badge is what made these invisible. The 2026-09-15 dependency
sweep missed the CVEs because they sit in transitive dependencies that Dependabot
did not surface, and the scanner that did catch them has been ignored for months.

**One signal is genuinely broken.** `scripts/pre-push-tests.sh` runs on every
`git push` (`.pre-commit-config.yaml:270-276`). Its backend and frontend jobs are
written as:

```sh
if uv run pytest ... | head -50 > "$BACKEND_LOG"; then    # :83-89
if npm test  ... | head -30 > "$FRONTEND_LOG"; then       # :104-108
```

The script sets `set -e` (`:15`) but not `set -o pipefail`. `if` therefore tests
`head`'s exit status, not the test runner's. **Two of three pre-push jobs report
success unconditionally.** CI had the identical bug and fixed it deliberately
(`ci.yml:1344-1352`, with the comment "tee's exit status is masked by the pipe");
the fix was never applied to the pre-push hook.

This is the same failure class the revival recovered from — a trusted test
mechanism that does not check anything. It did not recur; it never stopped.

## Evidence base

Gathered 2026-09-15 by five parallel read-only investigations. Cited so the
implementing agent can re-verify rather than trust this document.

**Timing.** Gate 21 (most recent green, full local `validate.sh`): 1200s total —
backend unit 83.54s, backend integration 537.46s, frontend Vitest 394.80s, plus
~170s of lint/typecheck/build. Stages run strictly serially under `set -e`.
Backend integration is the local long pole. In CI, `Integration Tests (API)` is a
single 26-minute job and the DAG's long pole.

**CI queueing.** ~60 jobs fan out from one `detect-changes` gate. Observed on a
representative run: a 10-minute delay before `build-backend-deps` could start
despite its only dependency having finished, and 12+ minutes of stagger between
shards of the same 16-way Vitest matrix. Most of the 45-minute wall clock is
queueing, not compute.

The queueing is consistent with hitting an account-level concurrent-job cap
(GitHub's Free-plan default is 20). **That cap is inferred from the symptom, not
measured** — the implementing agent must confirm the actual limit in
Settings → Billing before sizing the fan-out reduction in Phase 3.

**Two cache defects.** `build-backend-deps` passes `cache-suffix: backend-deps`
(`ci.yml:115`) while all 13 downstream backend jobs use the default cache
namespace — its pre-warm is invisible to every job it exists to serve. Each of the
22 frontend shards restores a `node_modules` cache (`ci.yml:1269-1295`) and then
runs `npm ci`, which deletes and reinstalls `node_modules` unconditionally.

**Duplicate scanning.** `ci.yml`'s 4-way `trivy-scan` matrix (`:2228`) and the
standalone `trivy.yml` (`:47-133`) scan overlapping targets on every push and PR.

**The existing fast tier is real but advisory.** `scripts/fast_select.py` selects
backend tests by regex-scanning test files for `backend.a.b.c` dotted-path
mentions (`:39`, prefix-aware lookup at `:84-100`), plus a directory policy adding
`backend/tests/contracts/` on any `backend/api/**` change (`:124-142`). It is
deliberately **not transitive**: a test that reaches changed code only through an
untouched intermediate module is not selected, and `scripts/test_fast_select.py:82-86`
asserts that exclusion as intended behaviour. Reachable only via
`validate.sh --fast` (`:560-609`); not in pre-commit, not in CI. Measured 5/5
probe cases under a 600s bound, fastest 7s, slowest 178s. The frontend runner
delegates to `vitest related`, which **is** transitive.

A second, competing selector is documented in `docs/development/testing.md:127`:
`pytest --testmon`. Two selectors with different strategies now exist.

**Escape hatches, counted.**

| Hatch                                                 | Count                       | Expiry enforced?               |
| ----------------------------------------------------- | --------------------------- | ------------------------------ |
| `scripts/collection-sanity-allowlist.txt:8-13`        | 6                           | **No** — free-text comments    |
| `.github/flake-allowlist.yml`                         | 0                           | Yes — tracking + expiry, in CI |
| `frontend/vite.config.ts:357-377` quarantine          | 16 files                    | No                             |
| `backend/tests/` `@pytest.mark.skip`                  | 32                          | No                             |
| `@pytest.mark.skipif`                                 | 63                          | No                             |
| `@pytest.mark.xfail`                                  | 4                           | No                             |
| imperative `pytest.skip(...)`                         | 94                          | No                             |
| frontend `.skip`                                      | 54 (`.only`: 0, `.todo`: 0) | No                             |
| excluded test trees (load, benchmarks, e2e, chaos)    | 4 trees                     | No                             |
| `-m 'not gpu'` default (`pyproject.toml:486`)         | all GPU tests               | N/A — intentional              |
| production modules omitted from coverage (`:521-548`) | 5 files                     | No                             |

**An ungoverned second quarantine.** `backend/tests/conftest.py:495-509` converts
any failure on a `@pytest.mark.flaky` test into a skip, with no expiry, tracking
ref, or review. It bypasses `.github/flake-allowlist.yml` entirely. Five tests use
it. The nightly `flaky-test-detection.yml:371` actively recommends adding the
marker as remediation — the automation steers people into the ungoverned path.

**The gates' own tests never run.** `scripts/test_check_test_collection.py` and
`scripts/test_check_flake_allowlist.py` verify the two best-enforced anti-rot
gates. Both sit outside `testpaths` (`pyproject.toml:480`) and are referenced in
zero workflows, hooks, or scripts.

**Two gates that cannot fail.** `check-integration-tests` runs in CI with
`continue-on-error: true` (`test-coverage-gate.yml:94-116`). And
`check_coverage_diff()` (`scripts/check-test-coverage-gate.py:221`) is misnamed —
it never diffs against a base branch, so a coverage drop cannot be detected by it
under any circumstances.

**Test quality is better than the drift history suggests.** 122 of 209 integration
files (58%) use no mocking at all, and the shared client fixture
(`backend/tests/integration/conftest.py:1438-1550`) exercises the real FastAPI app
through httpx `ASGITransport` against real Postgres. Only 603 of 26,650 unit tests
(2.3%) have no assertion of any kind.

**The one systemic quality gap is autospec.** 190 of 7,493 unit `patch(` sites
(2.5%) use `autospec=True`, concentrated in four files; integration is 0 of 949.
Weaker `spec=`/`spec_set=` appears in 141 of 673 files. Roughly 97% of mocks remain
blind to a renamed keyword or an added required parameter — precisely the
signature drift that caused the original breakage.

**No mount-completeness guard.** `/api/backup` was implemented, unit-tested, and
never mounted, returning 404 in production. It is fixed (`backend/main.py:1462`),
but nothing prevents the identical defect recurring for another router.

## Design

### Phase 0 — Make every signal true

Nothing downstream is verifiable while a gate lies. This phase is small and
mostly mechanical.

1. Add `set -o pipefail` to `scripts/pre-push-tests.sh`. Expect a burst of
   newly-visible failures; triage them as real findings, not regressions.
2. Patch the four CVEs. Where a fix is unavailable, register the finding with an
   owner and expiry under the Phase 1 schema rather than suppressing it silently.
3. Collapse the duplicate Trivy pipelines into one.
4. Whitelist the pytest-fixture idiom for vulture so Dead Code Detection reports
   only real findings.
5. Decide the Test Performance Audit's status explicitly: it reports 46 tests near
   their budget. Either it gates, or it is deleted. It may not stay red and
   advisory.
6. Adopt and enforce the invariant: **workflow conclusion equals merge-gate
   conclusion.** A job either gates or does not exist. No permanently-red
   non-gating jobs.
7. Wire `scripts/test_check_test_collection.py` and
   `scripts/test_check_flake_allowlist.py` into CI.
8. Close the `@pytest.mark.flaky` bypass: route it through
   `.github/flake-allowlist.yml`, and change `flaky-test-detection.yml:371` to
   recommend the governed path.
9. Make `check-integration-tests` gate for real (drop `continue-on-error`), and
   either implement `check_coverage_diff()` against the base branch or rename it
   to what it does.

**Acceptance:** `ci.yml` concludes green on `main`. A deliberately failing test,
pushed, is caught by the pre-push hook. Each of the 9 items has a commit.

### Phase 1 — The hard ratchet

One inventory, one schema, one enforcement script.

Every suppression listed in the escape-hatch table gets a registry entry carrying
`owner`, `tracking` (Linear ref), `expires` (ISO date), and `reason`. The
`.github/flake-allowlist.yml` format already does this correctly and is the model
to generalise.

The ratchet script runs in CI and fails when any category's count increases
without a corresponding registry entry. Expiry fires loudly: an expired entry
fails the build rather than silently lapsing.

Add a **route-mount completeness test** asserting that every router module under
`backend/api/routes/` is mounted in `backend/main.py`, closing the `/api/backup`
class permanently.

Environment-probe skips ("no `TEST_DATABASE_URL` exported", "nvidia-smi not
found") are legitimate and exempt; they must be distinguishable in the registry
from "not implemented yet" skips, which are permanent TODOs and must carry
tracking refs.

**Acceptance:** every one of the counted suppressions is either removed or
registered with owner and expiry. CI fails on an unregistered addition. A
synthetic expired entry fails the build.

### Phase 2 — The under-5-minute pre-push loop

The central technical work.

Resolve the two competing selectors first: `fast_select.py` (static, regex,
non-transitive) versus `pytest --testmon` (dynamic, coverage-derived). Pick one
and delete or clearly demote the other. A coverage-derived map knows what each
test actually touched, including through intermediates; a static map is cheaper
and has no warm-up. This choice is the implementing agent's to make on measured
evidence, and must be recorded with its rationale.

Whichever is chosen, **close the transitive blind spot**. Selecting only tests
that textually mention a changed module is defensible for an advisory tier and not
defensible for a gate.

Wire the selector into the repaired pre-push hook, within the 5-minute budget.
Note this **halves the existing bound**: the fast tier was specified and measured
against 600s, and decision 2 sets 300s. The slowest measured probe case today is
178s (a transitive frontend hook change), so the headroom is real but not large —
and closing the backend transitive blind spot will add selections, not remove
them. If 300s proves unreachable without weakening selection, raise the budget
rather than narrowing what gets selected, and record the trade.

**Output contract, non-negotiable:** the runner must emit a manifest that
distinguishes _not selected for this diff_ from _cannot run_. The first is normal
and must be visible; the second is a defect and must fail. If those two states
ever render alike, this design has rebuilt the trap the revival escaped.

**Acceptance:** `fast-validation-playbook.sh` extended with cases that exercise
the transitive path, all passing under 5 minutes. A change to a module reached
only through an intermediate selects the covering test. The manifest is emitted
on every run.

### Phase 3 — CI throughput

Register the GB300 as a self-hosted arm64 runner for the authoritative fast path.
Retain hosted amd64 for parity on `main` and nightly — dual-architecture support
is already a project goal, so arm64 CI is genuine coverage rather than a
compromise.

Mechanical fixes, each independently landable: correct the `cache-suffix`
mismatch (`ci.yml:115`); drop the no-op `node_modules` cache restore
(`ci.yml:1269-1295`); add concurrency groups with `cancel-in-progress` to
`trivy.yml`, `sast.yml`, `gitleaks.yml`, `dependency-audit.yml`, `agents-md.yml`.

Then reduce fan-out. Sixty jobs against roughly twenty slots is what produces the
observed queueing. Fewer, better-packed jobs will beat more shards until the fan-out
is below the cap. Rebalance the 26-minute `Integration Tests (API)` job once
queueing no longer confounds its measurement.

**Acceptance:** measured CI wall-clock reduction with queue time reported
separately from compute time. Self-hosted runner executes the gate and its
results agree with the hosted amd64 run.

### Phase 4 — Trust, then consolidation

Ordered deliberately: establish which tests are worth keeping before removing any.

1. **Scripted autospec sweep.** Raise adoption from 2.5% unit / 0% integration.
   Mechanical and scriptable; the Sep-15 pass proved it finds real defects (four
   `init_db` stubs missing an attribute the real function reads on every path).
   Add a gate so new unspecced patches are rejected.
2. **Expand mutation testing.** mutmut and Stryker are already installed
   (`scripts/mutation-test.sh`, `.github/workflows/mutation-testing.yml`) and
   narrowly aimed at a few utility modules. Widen coverage to
   `backend/services/` and `backend/api/routes/`. Mutation score, not line
   coverage, is the measure of whether tests exercise production code.
3. **Consolidate on evidence.** A test that survives mutation of the code it
   claims to cover is a deletion candidate; so are the 603 zero-assertion and 577
   mock-only-assert tests, once mutation confirms nothing is lost. Start with the
   largest files (`test_prompts.py`, 8,022 lines). `parametrize-guard` already
   proved the pattern, merging 39 near-duplicate methods into 8 without losing
   coverage.
4. **Re-enable coverage** on the 5 omitted production modules, or record why each
   must stay omitted with an expiry.

**Acceptance:** mutation score reported for the widened target set and trending
up. Every deletion cites the mutation evidence that licensed it. Suite wall-clock
and line count both measurably down, with coverage and mutation score not down.

## Non-goals

- Rewriting the test framework, or migrating off pytest/vitest.
- The ~102-file backend test-directory taxonomy reorganisation. It is already
  specified, already gated on an owner-approved category map, and explicitly
  forbidden from bulk auto-sorting.
- Changing production behaviour, except where Phase 0 patches a vulnerable
  dependency.
- Raising coverage thresholds. Coverage percentage is not the target; mutation
  score is.

## Open rulings required from the owner

These are shipped production defects found by the revival, currently covered by
honest skips. They are outside this spec's scope but block real coverage of three
features:

1. **R-T9-EXPORTDEFER** — `export_service.py:824` reads a deferred ORM column in an
   async path; every export of a non-empty event set fails with `MissingGreenlet`
   in production today.
2. **R-T9-MQTTPUMP** — `MQTTClient` never starts its background processing task; no
   MQTT message is ever delivered.
3. **R-T9-MVSOURCE** — dashboard materialized-view DDL was removed from migration
   history while `services/materialized_views.py` still queries those objects.

## Risks

**Phase 0 will look like a regression.** Fixing `pipefail` turns a silent
always-pass into a gate that reports real failures. That is the fix working.
Communicate it before landing.

**The ratchet adds friction before the fast path removes it.** This is the
accepted cost of the chosen sequencing: a ratchet built on a lying gate ratchets
nothing.

**Consolidation is the only phase that can destroy value.** Its gate is mutation
evidence, not judgement. No deletion without a surviving-mutant record.

# Test Platform Improvement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut the pre-push feedback loop to under 5 minutes on a ~2.0M LoC codebase while making the "test exists but never runs" failure class structurally impossible.

**Architecture:** Five sequential phases. Phase 0 repairs signals that currently lie, because nothing downstream is verifiable until they tell the truth. Phase 1 installs a hard ratchet so suppressions can only decrease. Phase 2 builds the impact-scoped fast loop on top of a gate that now works. Phase 3 attacks CI wall-clock. Phase 4 establishes which tests are worth keeping, then consolidates on that evidence.

**Tech Stack:** pytest + pytest-xdist + pytest-timeout, vitest, mutmut, Stryker, GitHub Actions, pre-commit, uv, podman.

**Spec:** [`docs/superpowers/specs/2026-09-15-test-platform-improvement-design.md`](../specs/2026-09-15-test-platform-improvement-design.md) — read it first. This plan argues from that spec and does not restate its evidence.

## Global Constraints

- **TDD is mandatory.** Every behavioural change starts with a failing test. (`CLAUDE.md`)
- **Never bypass pre-commit hooks.** No `--no-verify`, no `SKIP=`. Verify hooks are installed first: `pre-commit install && pre-commit install --hook-type pre-push`.
- **Coverage floors:** backend unit 85%, frontend 83%. Do not lower them to make a task pass.
- **Ports come from `.env`.** Never hardcode a port in compose files.
- **Container rebuilds always use `--no-cache`.**
- **Podman, not Docker**, for compose operations.
- **Linear operations go through the `/linear-python` skill only.**
- **Full validation:** `./scripts/validate.sh`. It runs serially under `set -e`; first failure aborts.
- **Phase order is load-bearing.** Do not start Phase 2 before Phase 0 lands — a fast selector on a lying gate is worse than no selector.

## How to use this plan

Each work package (WP) is independently landable and independently reviewable. A package states **what to achieve** and **how it will be judged**, not every keystroke. You are expected to do the heavy compute — run the suites, take the measurements, run the mutation passes — and to choose mechanics that fit what you measure.

Where a package says **MEASURE**, do not guess: produce the number and record it in the package's commit message.
Where a package says **DECIDE**, the choice is yours to make on evidence; record the rationale in the ledger.
Where a package says **RULING**, stop and ask the owner.

Record findings in `docs/plans/2026-09-12-context-map-doc-updates.md` (the ledger), following its existing row format.

---

# Phase 0 — Make every signal true

Small, mostly mechanical, and blocking. Expect Phase 0 to _increase_ visible failures. That is the fix working.

### WP0.1: Repair the pre-push gate — highest priority in this plan

**Files:** Modify `scripts/pre-push-tests.sh:15,83-89,104-108`

Two of three pre-push jobs currently report success unconditionally, because `if cmd | head -N; then` tests `head`'s exit status. `set -e` at line 15 does not help; there is no `pipefail`.

The fix pattern already exists in this repo at `ci.yml:1344-1352`. Apply the equivalent here. Either add `set -o pipefail` alongside `set -e`, or capture the runner's status explicitly via `${PIPESTATUS[0]}` — **DECIDE** based on whether any other logic in the script relies on pipe-failure tolerance.

- [ ] Write a test that proves the hook fails when a test fails. A shell-level test asserting non-zero exit with a deliberately broken test is sufficient; put it in `scripts/` beside the other gate tests.
- [ ] Run it and watch it fail against the current script.
- [ ] Apply the fix.
- [ ] Run it and watch it pass.
- [ ] **MEASURE:** run the repaired hook against current `main`. Record how many real failures it surfaces. They are pre-existing, not regressions.
- [ ] Triage what it surfaces. Each genuine failure becomes its own commit; do not fold them into this one.
- [ ] Commit.

**Done when:** a deliberately failing backend test and a deliberately failing frontend test each block a `git push`.

### WP0.2: Patch the four CVEs

**Files:** Modify `pyproject.toml`, `uv.lock`, `frontend/package.json`, `frontend/package-lock.json`

| Package                | Advisory            | Fixed in |
| ---------------------- | ------------------- | -------- |
| `cryptography`         | GHSA-537c-gmf6-5ccf | 48.0.1   |
| `pyarrow`              | CVE-2026-25087      | 23.0.1   |
| `serialize-javascript` | GHSA-5c6j-r48x-rmvq | 7.0.3    |
| (frontend transitive)  | CVE-2026-27606      | see scan |

All four are transitive — Dependabot did not surface them. Where a fix requires a major bump that breaks the build, do not suppress silently: register it under the WP1.2 schema with an owner and expiry.

- [ ] Bump, re-lock, run `./scripts/validate.sh`.
- [ ] Confirm both Trivy jobs go green.
- [ ] Commit.

**Done when:** `Trivy Scan (backend-deps)` and `Trivy Scan (frontend-deps)` both pass.

### WP0.3: Collapse duplicate Trivy scanning

**Files:** Modify `.github/workflows/ci.yml:2228`, `.github/workflows/trivy.yml:47-133`

Two independent Trivy pipelines scan overlapping targets on every push and PR. **DECIDE** which survives; the standalone workflow is the more natural home. Delete the other.

- [ ] Commit.

**Done when:** exactly one Trivy pipeline runs per push, with no loss of scanned surface. Prove the surface is unchanged by diffing the scanned target lists before and after.

### WP0.4: Stop vulture's false positives

**Files:** Modify vulture config (whitelist file or `pyproject.toml`), referencing `backend/tests/integration/api/test_jobs_api.py`, `backend/tests/integration/test_auth_flow.py`, `backend/tests/unit/test_deploy_phases.py`

vulture flags pytest fixtures requested by name for their side effects — `clean_tracker`, `real_session_store`, `mock_run_sudo` — as unused variables. This is a standard pytest idiom vulture cannot model.

Whitelist the idiom. Do **not** silence the whole job and do not rename the fixtures.

- [ ] Commit.

**Done when:** `Dead Code Detection` passes and still reports genuine dead code. Verify the second half by planting a real unused function and confirming it is caught.

### WP0.5: Resolve the Test Performance Audit — RULING

**Files:** Modify `.github/workflows/ci.yml` (job definition)

The job reports `FAIL — 46 tests exceeded time limit`: integration tests at ~4.0s against a 5s budget, unit tests at ~0.9s against 1s. This is a true signal about the slow integration tier and is directly relevant to Phase 2.

It may not remain red-and-advisory. Either it gates, or it is deleted.

- [ ] **MEASURE:** produce the full list of 46 tests with their durations and tiers.
- [ ] **RULING:** present to the owner — gate at the current threshold (requires fixing 46 tests first), gate at a raised threshold, or delete the job and fold the signal into Phase 2's work.
- [ ] Implement the ruling. Commit.

**Done when:** the job either gates or no longer exists.

### WP0.6: Enforce "workflow conclusion equals gate conclusion"

**Files:** Modify `.github/workflows/ci.yml:2507` (`ci-gate` needs list), plus any job that neither gates nor should exist

A job either gates merges or it does not exist. No permanently-red non-gating jobs — that state is what made WP0.2's CVEs invisible for six months.

- [ ] Enumerate every `ci.yml` job not in `ci-gate`'s needs list.
- [ ] For each: promote into the gate, or delete, or move to a scheduled workflow where red is triaged. **DECIDE** per job.
- [ ] Commit.

**Done when:** `ci.yml` concludes green on `main`, and a deliberately broken test turns it red.

### WP0.7: Run the gates' own tests

**Files:** Modify `.github/workflows/ci.yml` (extend the `collection-sanity` job)

`scripts/test_check_test_collection.py` and `scripts/test_check_flake_allowlist.py` verify the two best-enforced anti-rot gates. They sit outside `testpaths` (`pyproject.toml:480`) and are referenced nowhere.

They are correctly outside `testpaths` — they must not self-collect. Invoke them explicitly instead.

- [ ] Add a CI step running both.
- [ ] Prove it works: temporarily break `check-test-collection.py`, confirm CI catches it, revert.
- [ ] Commit.

**Done when:** a regression in either gate script fails CI.

### WP0.8: Close the ungoverned quarantine

**Files:** Modify `backend/tests/conftest.py:495-509`, `.github/workflows/flaky-test-detection.yml:371`, `.github/flake-allowlist.yml`; audit the 5 `@pytest.mark.flaky` call sites

`pytest_runtest_makereport` converts any failure on a `flaky`-marked test into a skip — no expiry, no tracking, no review. It bypasses `.github/flake-allowlist.yml`, which enforces both. The nightly detector recommends the ungoverned marker as the remediation.

- [ ] Make the marker require a matching `flake-allowlist.yml` entry; fail collection if a marked test has no entry.
- [ ] Migrate the 5 existing call sites into the allowlist with owner, tracking ref, and expiry.
- [ ] Change `flaky-test-detection.yml:371` to recommend the allowlist.
- [ ] Delete `backend/tests/flaky_tests.txt` if nothing reads it — confirm first.
- [ ] Commit.

**Done when:** a `@pytest.mark.flaky` test with no allowlist entry fails collection.

### WP0.9: Make two toothless gates bite

**Files:** Modify `.github/workflows/test-coverage-gate.yml:94-116`, `scripts/check-test-coverage-gate.py:221`

`check-integration-tests` runs with `continue-on-error: true` — it can never fail the workflow. And `check_coverage_diff()` never diffs against a base branch; it reports the current percentage, so a coverage _drop_ cannot be detected by it.

- [ ] Remove `continue-on-error` and make the summary job gate on the result.
- [ ] **DECIDE:** implement a real base-branch diff, or rename the function to what it does. A real diff is the higher-value choice; a misleading name is the actual defect.
- [ ] Test the diff path with a deliberate coverage drop.
- [ ] Commit.

**Done when:** a PR that drops coverage fails.

---

# Phase 1 — The hard ratchet

Counts may only decrease. Every suppression carries an owner and an expiry.

### WP1.1: Census the suppressions

**Files:** Create `scripts/suppression-census.py`, `scripts/test_suppression_census.py`

One script that counts every category in the spec's escape-hatch table and emits machine-readable output.

Categories: `collection-sanity-allowlist.txt` entries; `flake-allowlist.yml` entries; `frontend/vite.config.ts` quarantine list; backend `@pytest.mark.skip` / `skipif` / `xfail`; imperative `pytest.skip()`; frontend `.skip` / `.only` / `.todo`; excluded test trees in `validate.sh` and `nightly-full-gate.yml`; production modules in coverage `omit`.

Spec-recorded baselines to reproduce: 6 / 0 / 16 / 32 / 63 / 4 / 94 / 54 / 4 trees / 5 modules.

- [ ] TDD the script against fixtures.
- [ ] **MEASURE:** run against `main`. Where your count differs from the baseline, the baseline is stale — investigate and record which is right.
- [ ] Commit.

**Done when:** the census runs in CI and its output is stable across runs.

### WP1.2: Registry schema and migration

**Files:** Create `.github/suppression-registry.yml`; modify every file holding a suppression

`.github/flake-allowlist.yml` already models this correctly: `tracking` plus non-expired `expires`, enforced by `check-flake-allowlist.py`. Generalise that format to all categories. Every entry needs `owner`, `tracking`, `expires`, `reason`.

Environment-probe skips ("no `TEST_DATABASE_URL`", "nvidia-smi not found") are legitimate and exempt — but must be _distinguishable in the registry_ from "not implemented yet" skips, which are permanent TODOs and must carry tracking refs. **DECIDE** the mechanism (a `kind:` field is the obvious choice).

- [ ] Migrate all existing suppressions. This is the bulk of the work; expect to touch many files.
- [ ] Commit in reviewable batches, one category per commit.

**Done when:** every suppression the census finds has a registry entry, or has been removed.

### WP1.3: The ratchet gate

**Files:** Create `scripts/ratchet-check.py`, `scripts/test_ratchet_check.py`; create `.github/suppression-baseline.json`; modify `.github/workflows/ci.yml`

Fails CI when any category's count rises above the committed baseline without a corresponding registry entry. Baseline updates downward automatically; upward only with an entry.

- [ ] TDD: a synthetic count increase must fail; a decrease must pass and lower the baseline.
- [ ] Wire into CI.
- [ ] Commit.

**Done when:** adding an unregistered `@pytest.mark.skip` fails CI.

### WP1.4: Expiry enforcement

**Files:** Modify `scripts/ratchet-check.py`

An expired entry fails the build. It does not warn, and it does not silently lapse.

- [ ] TDD with a synthetic expired entry.
- [ ] Commit.

**Done when:** an entry dated in the past fails CI with a message naming the owner.

### WP1.5: Route-mount completeness test

**Files:** Create `backend/tests/unit/test_route_mounting.py`

`/api/backup` was implemented, unit-tested, and never mounted — a 404 in production that no test caught (fixed at `backend/main.py:1462`). Nothing prevents the identical defect for another router.

Assert every router module under `backend/api/routes/` is mounted in `backend/main.py`. Handle the legitimate exceptions (redirect routers, conditionally-mounted routers) via an explicit allowlist in the test, not by weakening the assertion.

- [ ] Write the test. It must fail if you comment out any `include_router` call — verify that.
- [ ] Commit.

**Done when:** removing any `include_router` line fails the suite.

---

# Phase 2 — The under-5-minute pre-push loop

The central technical work. Budget is 300s, halved from the existing 600s bound.

### WP2.1: Selector bake-off — DECIDE

**Files:** Create `docs/development/selector-evaluation.md`

Two competing selectors exist: `scripts/fast_select.py` (static regex over dotted-path mentions, non-transitive) and `pytest --testmon` (dynamic, coverage-derived, transitive), documented at `docs/development/testing.md:127`.

This is heavy compute and it is yours to run. Evaluate both on real changes sampled from recent history.

- [ ] **MEASURE**, for each selector, across at least 20 sampled historical commits:
  - selection time (the selector's own overhead)
  - selected-test runtime
  - **recall against ground truth** — for each sampled commit, did the selector pick the tests that actually broke? Reconstruct ground truth by running the full suite at that commit.
  - warm-up cost and staleness behaviour (testmon needs a populated database; what happens when it is cold or stale?)
- [ ] **DECIDE** which survives. Record the rationale and the numbers.
- [ ] Commit the evaluation document.

**Done when:** one selector is chosen with published numbers, and the other is deleted or explicitly demoted to advisory with a comment saying so.

### WP2.2: Close the transitive blind spot

**Files:** Modify the chosen selector; modify `scripts/test_fast_select.py:82-86` if `fast_select.py` wins

`fast_select.py` selects only tests that _textually mention_ a changed module. A test reaching changed code through an untouched intermediate is not selected — and `test_fast_select.py:82-86` asserts that exclusion as intended behaviour. That assertion is correct for an advisory tier and wrong for a gate; it must be inverted along with the behaviour.

- [ ] Write a failing test for the transitive case: test imports module A, A calls B, B changes, the test must be selected.
- [ ] Implement transitive resolution. **DECIDE** the mechanism — import-graph closure, or coverage-derived mapping if testmon won WP2.1.
- [ ] **MEASURE:** re-run the WP2.1 recall benchmark. Recall must improve; record the new selected-test runtime, which will rise.
- [ ] Commit.

**Done when:** the transitive test case passes and measured recall is higher than the WP2.1 baseline.

### WP2.3: The manifest contract — non-negotiable

**Files:** Modify `scripts/fast-backend-runner.sh`, `scripts/fast-frontend-runner.sh`

Every run emits a manifest distinguishing **not selected for this diff** (normal, must be visible) from **cannot run** (a defect, must fail). Collection errors, import failures, and zero-test files are the second category and must exit non-zero.

If these two states ever render alike, this plan has rebuilt the trap the revival escaped. This is the single most important requirement in Phase 2.

- [ ] TDD both paths: a healthy unselected test, and a test file that cannot be collected.
- [ ] Commit.

**Done when:** a file that fails to import causes a non-zero exit, while a merely-unselected file does not — and the manifest names both, differently.

### WP2.4: Wire into the repaired pre-push hook

**Files:** Modify `scripts/pre-push-tests.sh`, `.pre-commit-config.yaml:270-276`

Depends on WP0.1. Do not start before it lands.

- [ ] **MEASURE:** wall-clock across the WP2.1 sample. Report p50 and p95.
- [ ] If p95 exceeds 300s: **raise the budget and record the trade — do not narrow selection to hit the number.** Narrowing selection to hit a time target is how tests stop running.
- [ ] Commit.

**Done when:** p95 pre-push time is recorded, and the hook runs the selected set and fails on real failures.

### WP2.5: Extend the verification playbook

**Files:** Modify `scripts/fast-validation-playbook.sh`

Today it probes 5 synthetic changes against a 600s bound. Add transitive cases and retarget the bound.

- [ ] Add at least 3 cases exercising the WP2.2 transitive path.
- [ ] Update the bound to the WP2.4 measured figure.
- [ ] Run it; record results in `docs/development/fast-confidence-loop-measurements.md` following the existing row format.
- [ ] Commit.

**Done when:** all playbook cases pass within the recorded bound.

### WP2.6 (DRAFT 2026-09-16, from the WP2.1/2.2 artifacts): Fixture-provider edges in the selector

**Files:** Modify `scripts/fast_select.py`, `scripts/test_fast_select.py`

The WP2.2 conftest rule attaches a test to a conftest only when the test's
text NAMES the conftest module (bake-off test_rum.py does exactly that). The
normal pytest idiom — consume the fixture by parameter name, never mention
the conftest — is still statically invisible: a hub change (config.py,
main.py) that rides through `unit/conftest.py`'s client fixture reaches only
the tests that import the conftest by dotted name. Today's 100% recall holds
because THIS corpus happens to import its conftests; the class is a corpus
accident, not a guarantee.

- [ ] Write the red synthetic test: a test that uses a conftest fixture by
      bare parameter name, asserting a hub-module change selects it.
- [ ] Implement: extract fixture DEFINITIONS per conftest (name -> module),
      attach each test that declares the fixture name as a parameter (AST,
      cheap — the tests are already read for dotted refs). Same producer
      graph carries the conftest->prod half; referrers() semantics unchanged.
- [ ] MEASURE: rebench all 20 cases (recall must not fall; selection cost
      delta recorded) + fs_out_of_tier delta (this rule over-selects toward
      "everything under a conftest with app fixtures" — record the number).
- [ ] Commit.

**Done when:** the bare-name fixture test passes and the bake-off rebench
shows no recall regression, with the over-selection delta recorded.

### WP2.7 (DRAFT 2026-09-16): Measurement harnesses carry their own verification gate

**Files:** Relocate bake-off tooling into `scripts/dev/bakeoff/`; add self-checks

Two harness defects (v1 fails() parser truncating every node id to the word
FAILED; `comm -3`'s tab-led right column poisoning the join) silently lied
for hours until independent count cross-checks caught them. Both were in the
MEASUREMENT layer — the kind of code that gets zero test attention because
it is "just tooling", while producing the numbers a DECIDE rests on. Two
durable rules come out of this:

- [ ] Verification gate INSIDE every heavy measurement script: after each
      parse, assert parsed-count against an independent raw count
      (`grep -c`), print VERIFY lines, fail loud on mismatch. The
      derive-from-raw-logs pattern (never trust the live line; re-derive
      from artifacts) becomes the named standard, not an accident.
- [ ] Relocate protocol v3 (`driver.sh`, `derive.sh`, `rebench.sh`,
      README) from `/tmp/wp21` into `scripts/dev/bakeoff/` — the next
      selector question (sizing, a testmon-audit re-check) must not rebuild
      5 hours of harness, including its defect fixes, from memory.
- [ ] Commit.

**Done when:** the tooling is in-repo, every parse prints its VERIFY line,
and a planted bad-parse fixture trips the gate.

### WP2.8 (DRAFT 2026-09-16): Unit tests may not execute real system commands

**Files:** Create `scripts/check-unit-subprocess.py`; wire in `.pre-commit-config.yaml`

Found the hard way (WP0.5-gated audit, first PR run): `test_podman_install`
executed REAL `sudo apt-get install` / `podman --version` — 23.57s, fixed in
403bdf69. The class is worse than slow: on a developer box it mutates the
system. check-test-mocks guards integration-only; check-test-timeouts guards
sleeps only. Neither sees a unit test spawning binaries.

- [ ] Detection pass: AST-scan `backend/tests/unit/**` for `subprocess.` /
      `os.system` / `shutil.which`-exec sites without a `monkeypatch`/mock
      seam in the same test; output names the file, count recorded (expect:
      near-clean post-403bdf69 — that is the regression-lock use case).
- [ ] Fail-closed check script in the ratchet style: NEW violations block;
      existing recorded in the allowlist with owner+date (counts only fall).
- [ ] Commit.

**Done when:** the check runs in the gate and the podman class has a CI
face — a reintroduced real-command unit test fails, naming the test.

### WP2.9 (DRAFT 2026-09-16): Data-file dependency declaration (compose rule, generalized)

**Files:** Modify `scripts/fast_select.py`, `docs/development/testing.md`

The compose-config rule selects tests by FILENAME appearing in test text —
correct for the evidenced class, but the scope had to be narrowed to root
`docker-compose*.yml` because basename-matching any data file over-selects
(half the suite mentions `pyproject.toml`). If accidental-filename
dependencies grow beyond compose (lockfiles, schema JSON, fixtures dirs),
the principled form is DECLARATION: a marker or module-level manifest naming
a test's data-file deps, selection reading the declaration; text-matching
stays as the fallback for undeclared tests.

- [ ] Trigger check (cheap, now): grep the corpus for tests `Path()`-ing
      tracked non-test data files the selector cannot currently see. If the
      class is compose-only, park this WP with the grep recorded; the plan
      earns its keep only when the class grows.
- [ ] If triggered: `@pytest.mark.datafiles(...)`-style declaration +
      selector rule + red-first tests.
- [ ] Commit.

**Done when:** either the trigger grep shows compose-only (parked, evidence
in commit body) or declared deps are selected and tested.

---

# Phase 3 — CI throughput

Most of the 45-minute CI wall clock is queueing, not compute.

### WP3.1: Confirm the concurrency cap — do this first

**Files:** Modify the spec's evidence section with the confirmed figure

The spec infers a ~20-job cap from queueing symptoms. It is **not measured**. Every sizing decision in this phase depends on it.

- [ ] Confirm the actual limit in GitHub Settings → Billing.
- [ ] Record it. Commit.

**Done when:** the real number is written down.

### WP3.2: Fix the cache-suffix mismatch

**Files:** Modify `.github/workflows/ci.yml:115` and the 13 downstream backend jobs

`build-backend-deps` passes `cache-suffix: backend-deps`; every downstream job uses the default namespace. Its pre-warm is invisible to the 13 jobs it exists to serve.

- [ ] **DECIDE:** align the suffix everywhere, or drop it from `build-backend-deps`.
- [ ] **MEASURE:** per-job setup time before and after.
- [ ] Commit.

**Done when:** downstream jobs demonstrably hit a warm cache.

### WP3.3: Remove the no-op node_modules cache

**Files:** Modify `.github/workflows/ci.yml:1269-1295`

All 22 frontend shards restore a `node_modules` cache, then run `npm ci`, which deletes and reinstalls `node_modules` unconditionally. The restore is pure waste, 22× per run. The `~/.npm` cache from `setup-node` is the one that works — keep it.

- [ ] Commit.

**Done when:** the restore step is gone and frontend shard setup time is unchanged or better.

### WP3.4: Add missing concurrency groups

**Files:** Modify `.github/workflows/trivy.yml`, `sast.yml`, `gitleaks.yml`, `dependency-audit.yml`, `agents-md.yml`

These five lack `concurrency` blocks, so repeated pushes to a PR branch pile up redundant runs that compete for the cap. Copy the pattern from `ci.yml:10-12`.

- [ ] Commit.

**Done when:** a second push to a PR branch cancels the first run of each.

### WP3.5: Reduce fan-out

**Files:** Modify `.github/workflows/ci.yml` matrix definitions

~60 jobs against the WP3.1 cap produces the observed 10-minute startup delay and 12-minute intra-matrix stagger. Fewer, better-packed jobs beat more shards until fan-out drops below the cap.

- [ ] **MEASURE:** current job count, and queue time separately from compute time per job.
- [ ] **DECIDE** new shard counts. The 16-way Vitest matrix and 4-way Trivy matrix are the obvious candidates.
- [ ] **MEASURE** again. Report queue and compute separately — a change that cuts queue time while raising compute time is still a win.
- [ ] Commit.

**Done when:** total CI wall clock is measurably lower, with queue time reported separately.

### WP3.6: Register the GB300 as a self-hosted arm64 runner

**Files:** Create a new workflow or modify `ci.yml` `runs-on` targets

The GB300 runs a full gate in ~20 minutes. Dual-architecture support is already a project goal, so arm64 CI is genuine coverage.

Security matters here: a self-hosted runner on a public repository must never execute untrusted PR code. **Restrict to `push` on branches and trusted PRs; do not expose it to `pull_request_target` or forks.** Confirm the arrangement with the owner before enabling.

- [ ] **RULING:** confirm the runner scope and trust boundary with the owner.
- [ ] Register the runner; keep hosted amd64 for parity on `main` and nightly.
- [ ] **MEASURE:** arm64 and amd64 results must agree. Any divergence is a real dual-arch finding — record it in the ledger.
- [ ] Commit.

**Done when:** the self-hosted runner executes the gate, its results agree with hosted amd64, and it is unreachable from fork PRs.

### WP3.7: Rebalance the integration job

**Files:** Modify `.github/workflows/ci.yml` integration job definitions

`Integration Tests (API)` is a single 26-minute job and the DAG's long pole. Do this **after** WP3.5, so queueing no longer confounds the measurement.

- [ ] **MEASURE:** per-test durations within the job. `backend/tests/plugins/durations_plugin.py` already does this — use it rather than writing new tooling.
- [ ] **DECIDE** a split or rebalance.
- [ ] Commit.

**Done when:** the longest single CI job is measurably shorter.

---

# Phase 4 — Trust, then consolidation

Establish which tests are worth keeping before removing any.

### WP4.1: Scripted autospec sweep

**Files:** Create `scripts/autospec-sweep.py`, `scripts/test_autospec_sweep.py`; modify backend test files in batches

190 of 7,493 unit `patch(` sites use `autospec=True` (2.5%); integration is 0 of 949. ~97% of mocks cannot detect a renamed keyword or an added required parameter — exactly the drift that caused the original breakage.

This must be scripted, not manual. The Sep-15 pass proved it finds real defects: four `init_db` stubs were missing an attribute the real function reads on every path.

- [ ] Build the sweep tool. TDD it.
- [ ] Run it in batches. **Expect failures — they are real findings.** Each failure is a mock that was lying about a signature; fix the test, and check whether the production code is also wrong.
- [ ] **MEASURE:** adoption percentage before and after; count of real defects surfaced.
- [ ] Commit per batch, one directory per commit.

**Done when:** adoption is materially higher and every surfaced defect is triaged.

### WP4.2: Gate new unspecced mocks

**Files:** Create `scripts/check-mock-spec.py`; modify `.pre-commit-config.yaml` and `.github/workflows/ci.yml`

Ratchet-style, consistent with Phase 1: the count of unspecced patch sites may only decrease.

- [ ] TDD; wire into the WP1.3 ratchet rather than building a parallel mechanism.
- [ ] Commit.

**Done when:** adding an unspecced `patch()` fails CI.

### WP4.3: Expand mutation testing

**Files:** Modify `pyproject.toml:597-625` (`[tool.mutmut]`), `frontend/stryker.conf`, `scripts/mutation-test.sh`, `.github/workflows/mutation-testing.yml`

mutmut and Stryker are installed and aimed at a handful of utility modules. Mutation score — not line coverage — is the measure of whether tests exercise production code.

Widen to `backend/services/` and `backend/api/routes/`. Mutation testing is expensive; it runs on a schedule, not per-PR.

- [ ] **DECIDE** the target set and cadence. Prioritise by risk: the 5 modules currently omitted from coverage, and modules with high line coverage but few assertions.
- [ ] **MEASURE:** baseline mutation score per target module. This is heavy compute — budget for it.
- [ ] Publish scores where they are visible.
- [ ] Commit.

**Done when:** mutation score is reported for the widened set and tracked over time.

### WP4.4: Consolidate on mutation evidence

**Files:** Modify backend test files, starting with `backend/tests/unit/test_prompts.py` (8,022 lines)

Backend tests are 659k lines against 294k lines of production Python. Candidates for removal: tests that survive mutation of the code they claim to cover; the 603 zero-assertion tests; the 577 that assert only on mock calls. A concrete starting point is `backend/tests/unit/test_business_metrics.py:78-138` — 13 tests that call a production function and assert nothing.

`parametrize-guard` already proved the pattern, merging 39 near-duplicate methods into 8 without losing coverage.

**No deletion without a surviving-mutant record.** This is the only phase that can destroy value, and its gate is evidence, not judgement.

- [ ] For each candidate: record the mutation evidence, delete or merge, re-run mutation on the affected module.
- [ ] **MEASURE:** lines removed, suite wall-clock delta, mutation score delta. Mutation score must not drop.
- [ ] Commit in small reviewable batches, citing the evidence in each message.

**Done when:** test line count and wall clock are down, with coverage and mutation score not down.

### WP4.5: Re-enable coverage on omitted modules

**Files:** Modify `pyproject.toml:521-548`

Five production modules are invisible to the 85% gate: `api/routes/alerts.py`, `api/routes/audit.py`, `services/video_processor.py`, `services/degradation_manager.py`, `core/tls.py`.

- [ ] For each: write the missing tests and remove the omit, or record why it must stay omitted with an owner and expiry under the WP1.2 registry.
- [ ] Commit per module.

**Done when:** every omit is either gone or registered with an expiry.

---

## Out of scope

- Rewriting the test framework or migrating off pytest/vitest.
- The ~102-file backend test-directory taxonomy reorganisation — already specified, gated on an owner-approved category map, and forbidden from bulk auto-sorting.
- Raising coverage thresholds. Mutation score is the target, not coverage percentage.

## Owner rulings blocking real coverage

Three shipped production defects, currently covered by honest skips. Not this plan's work, but three features have effectively zero live coverage until they are ruled on:

1. **R-T9-EXPORTDEFER** — `export_service.py:824` reads a deferred ORM column in an async path; every export of a non-empty event set fails with `MissingGreenlet` in production today.
2. **R-T9-MQTTPUMP** — `MQTTClient` never starts its background processing task; no MQTT message is ever delivered.
3. **R-T9-MVSOURCE** — dashboard materialized-view DDL was removed from migration history while `services/materialized_views.py` still queries those objects.

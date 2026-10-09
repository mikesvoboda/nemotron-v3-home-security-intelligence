# 01 — Mutation Policy

> Ruled 2026-10-07 (UR-1 to UR-7 in [`README.md`](README.md)). Supersedes
> [`docs/plans/2026-09-29-mutation-ladder-85-goal-prompt.md`](../plans/2026-09-29-mutation-ladder-85-goal-prompt.md)
> and the two `docs/goal-prompt-mutation-80-*.txt` prompts. Evidence: [`00 §4.4, §6`](00-audit.md).

This file is the single source for how mutation testing works from now on — except the interface
bar and the accepted-survivor definitions, which M3 / B2.1 moved to
`docs/developer/patterns/mutation-testing.md`; that doc owns those two sections. Its five packages
(M1–M5) are scheduled in the lane plans by the IDs in the README status table.

## What the score is for

The mutation score is a **diagnostic**: a module's surviving mutants are a to-do list for that
module's tests, worth acting on when the module ships and the survivor reveals a behaviour the
tests do not check. A **floor** protects what has been gained: the score on shipping code does not
go down. There is no numeric target. (UR-1)

The campaign that climbed toward 85% is held after M54 (UR-2). Its batteries stay in the tree and
their kills count. Each battery's future is settled by the module it targets: deleted with its
module in Phase 3, or consolidated when a feature package or the background track reaches that
module (UR-16). New tests are written to the interface bar (`docs/developer/patterns/mutation-testing.md`,
section "The interface bar"); new battery files are not.

## The scored set

The scored set is every module in `[tool.mutmut]`'s mutation paths that **ships**, as the
reachability check (M1) reports it (UR-3). A module leaves the scored set when it stops shipping;
deleting dead code therefore changes the denominator, and that change needs no ruling — the PR
discloses it. Modules on the reachability keep-list ship by declaration and stay scored.

## The interface bar and accepted survivors

Moved to `docs/developer/patterns/mutation-testing.md` ("The interface bar", "Accepted survivors") as `01` M3 / B2.1 required; that doc is the single source. UR-6 and UR-16 above still own the rulings this text illustrated.

## The floor

Two paths enforce it (UR-4); each uses the comparison that is exact for what it sees (UR-5).

**Test-only PRs — zero kill-loss.** A PR that deletes, merges, moves or rewrites tests for a
scored module, and leaves that module's production bytes unchanged, carries before/after evidence:

1. Confirm the production bytes are unchanged: `git diff --stat <base> -- <module path>` prints
   nothing.
2. Fix the **baseline mutant set**: the mutants the base commit generates for the whole module.
   Both suites run against this one set. Regenerating at the head is not equivalent:
   `mutate_only_covered_lines = true` (`pyproject.toml:758`) makes generation depend on what the
   tests cover, so a PR that deletes a line's last covering test would make that line's mutants
   vanish from the head run instead of surviving. Run the whole module, never a subset: subset runs
   remap mutant keys onto different source sites (the campaign's "occurrence-twin" finding,
   superseded ladder doc, MINES (a)).
3. Run the base suite and the head suite against the baseline set with the in-repo runner (M4
   documents the exact command). Match mutants across the two runs by stable identity — module,
   function and the mutated body's hash, as in the accepted-survivors file — never by key alone.
4. Diff the two results with M4's tool. A mutant is **caught** when its result is `killed` or
   `timeout` — the same set the score counts (`scripts/mutation-score.py:71`). A **kill-loss** is a
   baseline mutant the base suite caught whose head result is anything else: survived, no tests,
   not checked, or missing. Moving between `killed` and `timeout` is not a kill-loss.
5. Every kill-loss is either caught again by an above-bar test in the same PR, or added to the
   accepted-survivors file as `below-bar` with the name of the test that used to kill it.
6. The PR body carries the module, before/after killed-or-timeout over the baseline set's total,
   the kill-loss count after step 5, and any accepted-survivor additions.

**Zero kill-loss** means no kill-loss is left after step 5: each one is caught again by an
above-bar test or recorded as an accepted survivor.

PRs that change production code are outside this rule: their mutant set changes with the code.
That is why a feature package lands its consolidation as a separate test-only PR before the PR that
builds the feature (README, Phase 4).

**The weekly run — per-module drop beyond the noise band.** The scheduled `mutation-testing.yml` run
scores each scored module from its banked verdicts. When a module's score falls by more than the
measured noise band, the run opens or updates one GitHub issue naming the module and the newly
surviving mutants. The same blind spot exists here: because only covered lines are mutated, deleting
a module's tests shrinks its mutant count and can _raise_ its score. So the run also alerts when a
module's mutant count falls while its production bytes did not change. It never blocks a merge. The
global score is reported for information only; deleting dead code and adding code both move it for
reasons that say nothing about test quality.

## Where evidence lives

One home per kind of evidence, one producer each (UR-7):

| evidence                              | home                                                               | written by               |
| ------------------------------------- | ------------------------------------------------------------------ | ------------------------ |
| before/after kill evidence for one PR | that PR's body                                                     | the PR author            |
| per-module scores over time           | `.github/mutation-history.json`, one entry per week                | the weekly CI job only   |
| accepted survivors                    | `backend/tests/mutation/accepted_survivors.toml`                   | the PR that accepts them |
| the method                            | this file, then `docs/developer/patterns/mutation-testing.md` (M3) | —                        |

The L ledger (`docs/plans/2026-09-12-context-map-doc-updates.md`) takes no new mutation rows; its
existing rows stay as history.

## Packages

### M1 — Reachability check (scheduled as `O2.3`)

**Files:** create `scripts/reachability.py`, `scripts/reachability/entry_points.toml`,
`scripts/reachability/keep.toml`, `scripts/test_reachability.py`.

Walk imports from the declared entry points and report which Python modules under `backend/`, `ai/`
and `synthbench/` ship. Candidates are non-test modules only: test files (`test_*.py`,
`conftest.py`) and test directories (`tests/`) are never candidates — they leave with the modules
they test. Trace **names, not packages**: `services/__init__.py` imports 56
submodules and re-exports 274 names no production code uses, so a package-level walk calls dead
modules live (`00 §4.1`). String and dynamic imports are resolved through an allowlist in
`entry_points.toml`. `keep.toml` lists modules that ship by declaration, one reason each — the
fake AI provider (`backend/ai_contract/fake/`) is the first entry.

- [ ] TDD the walker on fixture packages: name-level re-exports, `TYPE_CHECKING` imports (not
      shipping), function-level imports (shipping), string imports via the allowlist.
- [ ] Declare the entry points: `backend/main.py` and the worker processes it starts,
      `ai/gateway/main.py`, the synthbench CLI, and every script a workflow or pre-commit hook runs.
- [ ] Output JSON: shipping modules, non-shipping modules with line counts, keep-list hits.
- [ ] **MEASURE:** run it at HEAD; put the non-shipping count and lines in the PR.

**Done when:** the run reports `redis_json`, `scenario_classifier`, `managed_service` and
`orphan_cleanup_service` as not shipping, reports `vlm_analyzer` and `backend/evaluation` as
shipping, and its test suite passes in CI.

### M2 — Weekly scorer and history (scheduled as `O3.5`)

**Files:** modify `scripts/mutation-score.py`, `.github/workflows/mutation-testing.yml`,
`.github/mutation-history.json`.

- [ ] Score per module over the scored set (M1's output) from the banked verdicts, with and without
      accepted survivors (M3's file). Compare only modules whose mutants were all re-checked since
      the previous entry: the weekly job is incremental (a 240-minute budget that resumes), so a
      partially re-checked module has no comparable score.
- [ ] **MEASURE** the noise band: from the existing 57 history runs, the week-to-week score change
      of modules whose source did not change between runs. Record the band and its derivation in
      the PR.
- [ ] On a drop beyond the band, open or update one issue per module (title
      `mutation floor: <module>`), listing the newly surviving mutants. Raise the same issue when a
      module's mutant count falls while its production bytes are unchanged since the previous
      entry: that is lost coverage, which a covered-lines-only score reports as a gain. The job's conclusion
      reports the job's health, never the drop.
- [ ] Write one history entry per weekly run: per-module scores plus the informational global
      score. Compact the existing 57 runs to one summary line each (date, killed-or-timeout, total,
      score) — **DECIDE** the exact shape.
- [ ] Remove every other writer of `mutation-history.json` (`--history` use outside the workflow).

**Done when:** a dry run against a fixture history opens exactly one issue for a module with an
injected score drop and exactly one for a module whose mutant count fell with unchanged source, and
`mutation-history.json` is under 200 KB.

### M3 — The interface bar and the accepted-survivors file (scheduled as `B2.1`)

**Files:** create `backend/tests/mutation/accepted_survivors.toml`,
`backend/tests/unit/test_accepted_survivors.py`; modify
`docs/developer/patterns/mutation-testing.md`.

- [ ] Move the interface bar and the accepted-survivor definitions from this file into
      `mutation-testing.md`, and leave a one-line pointer here. That doc becomes the single source.
- [ ] Create the TOML file with a header comment giving the schema: `module`, `mutant`,
      `body_sha256` (the mutated function's body, so an entry survives key renumbering), `kind`
      (`equivalent` or `below-bar`), `reason`, `date`.
- [ ] A test validates every entry: the fields are present, `kind` is one of the two, the module
      exists.

**Done when:** the doc carries the bar, the file exists with its schema, and the validation test
passes with one sample entry and fails with a malformed one.

### M4 — PR evidence tool (scheduled as `O3.6`)

**Files:** create `scripts/mutation-diff.py`, `scripts/test_mutation_diff.py`; modify
`docs/developer/patterns/mutation-testing.md`.

- [ ] Document the exact commands that fix one module's baseline mutant set at the base commit
      and run both the base suite and the head suite against it, using `scripts/mutation-run.sh`.
      **DECIDE** the mechanism on evidence: generate once at the base and swap the head's tests into
      the mutant home, or turn `mutate_only_covered_lines` off for evidence runs so the set depends
      on production bytes alone. **MEASURE** the wall-clock on one mid-sized module (generation
      included) and put it in the doc.
- [ ] `mutation-diff.py --before <results> --after <results>` matches mutants by stable identity,
      prints the kill-loss list (caught before — `killed` or `timeout` — and survived, no tests,
      not checked or missing after), and exits non-zero when any kill-loss is not covered by an
      accepted-survivors entry.
- [ ] TDD it on fixture result files: no change; killed → survived; killed → missing;
      killed → `no tests`; timeout → survived; timeout → missing; killed → timeout and
      timeout → killed (both **not** a kill-loss); one kill-loss covered by the accepted-survivors
      file.

**Done when:** on a throwaway branch that deletes the **last** test covering one branch of a
module, the documented commands plus the tool report that branch's formerly killed mutants as
kill-loss (never zero), and the tool exits zero once those mutants are accepted.

### M5 — Hold and supersede (scheduled as `O1.1`)

- [ ] Confirm the campaign is held: no mutmut process running, PR #6844 merged or closed.
- [ ] SUPERSEDED banners on the ladder-85 plan and the two goal prompts (landed with this design).
- [ ] A banner at the top of the L ledger: no new mutation rows; method and evidence live per this
      file.

**Done when:** the three superseded docs and the L ledger each open with a banner pointing here.

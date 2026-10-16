# Evidence Harnesses - Agent Guide

## Purpose

Measurement tools a package's own evidence rests on, kept in the repo so a reviewer can re-run the measurement after the sandbox that produced it is gone. Contract rule 3 (`docs/uplevel/README.md`): "Every script, fixture and harness a package relies on is committed. Work from `/tmp` or a home directory does not count as evidence." Precedent: 8521f42bb committed B1.1's latency probe.

This is NOT a test tier. A file here earns the `test_` prefix only when it is a probe written in pytest's shape; nothing here is a regression test, and a package that needs a permanent pin belongs in `backend/tests/unit/` instead.

## What lives here

| Path                                | Kind   | What it measures                                                                                                                                                          |
| ----------------------------------- | ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_r109_nightly_gate_harness.py` | pytest | #7003's claims: the setup_logging asctime leak, the BASE-vs-head census cost, the two gates' per-test budget. 4 gated, 2 bare                                             |
| `r109_discriminator.sh`             | script | #7003's "(b) discriminator" table: the nightly 5 s-budget victims pass on idle CPU and red under hosted oversubscription                                                  |
| `r109c_leakprobe.py`                | plugin | #7010's attribution: which test LEAKS a `backend.core.database` global, which INHERITS a dirty state                                                                      |
| `probe_tie.py`                      | script | #7107's mechanism: `get_latest_by_type`'s `ORDER BY created_at DESC LIMIT 1` has no tiebreak, so a tied pair's winner tracks insertion order and table size, not data     |
| `probe_fix.py`                      | script | #7107's 12-cell matrix: OLD fixture state vs NEW, each through the real repository under three planner settings. Proves the fixture fix makes the winner plan-independent |
| `r228_keyshape_census.py`           | script | #7215's MEASURE: each cached route's stored key (built by the repo's own generators, read back raw) against all seven invalidators. 0/8 reachable before `[r228]`, 7/8 after; the survivor `timeline_summary:*` has no invalidator at all |

## Running

```bash
EVIDENCE_R109=1 uv run pytest backend/tests/evidence/ -p no:randomly --no-cov -v
LOG=/tmp/r109-discriminator.log backend/tests/evidence/r109_discriminator.sh
PYTHONPATH=backend/tests/evidence LEAKPROBE_OUT=/tmp/leaks.txt \
    uv run pytest backend/tests/unit/ -p r109c_leakprobe -q
# The r157 pair takes the DB from $TEST_DATABASE_URL and creates/drops real
# objects in it, so point it at a scratch Postgres (same env the integration
# tier uses, e.g. the one scripts/validate.sh exports).
TEST_DATABASE_URL=... uv run python backend/tests/evidence/probe_tie.py
TEST_DATABASE_URL=... uv run python backend/tests/evidence/probe_fix.py
```

## Patterns and Gotchas

- **The gate is `EVIDENCE_R109=1`.** Four of the six probes in `backend/tests/evidence/test_r109_nightly_gate_harness.py` skip unless it is set; the other two are cheap textual reads over workflow files and run bare, so a bare invocation prints `2 passed, 4 skipped` and is NOT evidence of anything. Set the variable, or read nothing.
- **A pathless `pytest` collects this directory** — `testpaths` covers `backend/tests` (`pyproject.toml:539`) — and two probes write real hundreds-of-MB payloads. That is the reason for the env gate rather than a marker: a marker still leaves the collection import in the sweep. No CI invocation collects it. The PR-gate unit shard passes `backend/tests/unit/` (`ci.yml:774`), the nightly tier passes `backend/tests/unit backend/tests/contracts backend/tests/security` (`nightly-full-gate.yml:122`), `scripts/validate.sh` the same three dirs (`:351`), and every other pytest step in `ci.yml` names explicit paths — 0 workflow files mention `backend/tests/evidence` at all.
- **`probe_tie.py` and `probe_fix.py` are deliberately NOT `test_`-prefixed, and they end in a bare module-level `asyncio.run(main())`.** `python_files = ["test_*.py"]` (`pyproject.toml:540`) is what keeps them out of a pathless `pytest`; either name prefixed would fire the whole probe — which creates and drops a real database — at _collection_ time. They are one-shot reporters that never call `sys.exit`, so a green matrix and a clean run share rc 0 — an unset `$TEST_DATABASE_URL` or an unreachable DB still exits non-zero (KeyError / connection error). Read the printed `PLAN-DEPENDENT` / `plan-INDEPENDENT` lines, never the rc.
- **`probe_fix.py:18` hardcodes a checkout path and does not verify what it audits.** It runs `sys.path.insert(0, "/agents/agent-uplevel-backend/workspace")`, so in a sandbox where that path exists it imports THAT tree regardless of where the script lives — it can print a verdict about a checkout you are not standing in. That is why the claim it carries is scoped to two blob-identical modules: `backend/models/summary.py` (`dcea77555`) and `backend/repositories/summary_repository.py` (`a00d0e3a3`) are unchanged across main, PR head and merge-base, so any tree prints the same twelve cells. A reviewer without that path (the review of #7107 ran it from its own tree) reproduces the matrix anyway. If either module ever changes, re-run the probe from a tree you have read and say which tree printed it.
- **Timing figures are single draws.** The discriminator and the census probes are one measurement per cell, like the seed-pinned runs they replace; the durable claim is PASS/PASS plus magnitude order, not a digit. Quote a leaked-count as "non-zero at both heads", never as a fixed number — it moves with the worksteal assignment.
- **A probe that measures a sweep must not sit inside it.** `r109c_leakprobe.py` is a `pytest_runtest_call` wrapper, not a fixture, because its first version was an autouse `-p` fixture — plugin-depth, so it tore down AFTER the unit conftest's sweep and reported a clean bill of health no matter what tests did. Its header carries the measurement that proved the masking. Anything added here that observes test-side state has the same trap.
- These probes re-measure claims and re-derive comparisons from git blobs; they do NOT re-create the one-off exploratory orderings, and they do not reproduce the hosted log shape (the nightly's unit-tier step redirects to a file and publishes only a tail). Say which a figure came from at the point of use.

## Related

- `docs/uplevel/README.md` - contract rule 3, the reason this directory exists
- `backend/tests/unit/AGENTS.md` - the tier these probes measure, and the autouse sweeps a probe here must stay outside

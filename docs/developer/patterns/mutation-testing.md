# Mutation Testing Guide

Mutation testing is an advanced testing technique that evaluates the effectiveness of your test suite by introducing small changes (mutations) to your source code and checking whether your tests detect them.

## Overview

### What is Mutation Testing?

Traditional code coverage tells you which lines of code are executed by tests, but it doesn't tell you if those tests are actually verifying the correct behavior. Mutation testing fills this gap by:

1. **Creating mutants**: Making small changes to your code (e.g., changing `>` to `>=`, removing a line)
2. **Running tests**: Executing your test suite against each mutant
3. **Evaluating results**: A "killed" mutant means tests caught the bug; a "surviving" mutant indicates a test gap

### Mutation Score

The mutation score is the percentage of mutants killed by your tests:

```
Mutation Score = (Killed Mutants / Total Mutants) × 100
```

| Score     | Rating    | Interpretation                        |
| --------- | --------- | ------------------------------------- |
| 90-100%   | Excellent | Tests effectively detect most changes |
| 80-89%    | Good      | Tests are strong but have some gaps   |
| 60-79%    | Fair      | Tests need improvement in key areas   |
| Below 60% | Poor      | Tests provide weak validation         |

## Quick Start

### Running Mutation Tests

```bash
# Run all mutation tests (backend + frontend)
./scripts/mutation-test.sh

# Backend only (mutmut)
./scripts/mutation-test.sh --backend

# Frontend only (Stryker)
./scripts/mutation-test.sh --frontend

# Specific backend module (bare name -- mutmut 3 mutant-key filter)
./scripts/mutation-test.sh --module severity
```

### Backend (Python with mutmut 3.x — WP4.3)

```bash
# Full widened set (backend/services/ + backend/api/routes/ — [tool.mutmut])
./scripts/mutation-run.sh

# One module (mutmut 3 filters by fnmatch over mutant keys: bare name)
./scripts/mutation-run.sh severity

# Per-module scores + totals from the run cache (what CI publishes)
uv run python scripts/mutation-score.py

# Surviving mutants (the WP4.4 work list), then one specific mutant
uv run mutmut results
uv run mutmut show backend.services.severity.x_classify_score.__mutmut_3
```

> **The 2.x commands are gone.** `mutmut run --paths-to-mutate ... --runner ...`
> and `mutmut html` are mutmut 2 invocations; mutmut 3.8 rejects the flags
> (`Error: No such option '--paths-to-mutate'`) and has no html command. The
> weekly workflow carried exactly those calls behind `|| true` for months,
> "succeeding" with zero data — if you are copying commands from an old PR,
> you are here for the right reason.

### Frontend (TypeScript with Stryker)

```bash
cd frontend

# Run mutation tests
npm run test:mutation

# View HTML report (generated automatically)
open reports/mutation/mutation-report.html
```

## Target Set (WP4.3: the WIDENED set)

Mutation testing is computationally expensive; the PLAN's answer is to run
the full denominator **on a schedule, not per-PR**, and publish scores where
they are tracked.

### Backend denominator (mutmut)

Everything under `backend/services/` and `backend/api/routes/` —
`[tool.mutmut] source_paths` in `pyproject.toml`, mirrored by
`scripts/mutation-score.py --targets` so a run that silently skips a module
shows up as a gap in the published artifact ("targets with no mutants"), not
as a clean number. The 5 legacy modules (bbox_validation, severity,
prompt_parser, search, dedupe) are a subset.

Prioritisation inside the set (PLAN DECIDE, assertion-density screen
2026-09-17): the coverage-omit modules (WP4.5's five) and the low
assertion-per-kloc route tree — `analytics_zones.py` (~71 asserts/kloc at
521 branch points), `admin.py`, `debug.py`, `entities.py`,
`face_recognition.py`, plus `dwell_time_service.py` /
`ai_quality_metrics.py` / `batch_coalescer.py` on the services side. The full
266-module density screen lives in the WP4.3 ledger entry.

**Score formula** (mutmut's own badge, what `mutation-score.py` reports):

```
score = (killed + timeout) / (total − skipped) × 100
```

`mutate_only_covered_lines = true` scopes generation to lines the unit tier
executes, so the score measures test effectiveness (WP4.3's subject) without
charging never-executed lines to it — that is coverage's complaint and
WP4.5's job, and the uncovered-target gap list makes it visible every run.

### The mutant home (`mutants/`) and `also_copy`

mutmut runs pytest with `cwd=mutants/`, a tree with **no editable install**:
`import X` resolves only under `mutants/`, and `Path(__file__).parents[N]` /
"repo root" probes inside tests land on `mutants/` too. So a module's
mutants can only be checked if everything its tests import **or read by
path** exists there — that is `[tool.mutmut] also_copy`'s job, and it is a
different question than `source_paths` (what gets mutated). When a stats or
clean-test pass dies with `ModuleNotFoundError` or an
`AssertionError: … not found at …/mutants/…`, the copy set is what is
missing; `scripts/mutation-run.sh` pre-`mkdir`s the parents that mutmut's
per-file copy (plain `copy2`, no `mkdir`) can't create.

One consequence for tests themselves: under mutation, the class under test
is the mutated copy, whose covered methods mutmut renames
`x<CLOBBER>Class<CLOBBER>method__mutmut_orig/_1` behind its dispatch
decorator. Tests that introspect a real API and compare it against a mock
must ignore `__mutmut`-marked members — that is what
`_is_mutmut_generated` in `test_websocket.py` does; the real-vs-mock
comparison itself is unchanged.

### Process isolation: why `process_isolation = "forkserver"`

mutmut's default `process_isolation = "fork"` forks mutant workers from its
main process — the one that has already run the whole suite for stats — and
"every worker inherits whatever the test setup left in that process"
(mutmut's own `ProcessIsolation` docstring). With Hypothesis in the tree
that poisons the score twice over. Mechanically: `ForkRunner` runs
`collect_stats` and `run_clean_tests` in the same process, so the clean pass
re-executes every `@given` test still in `sys.modules`, and Hypothesis's
`differing_executors` health check errors on a second execution from a
different executor instance (repro: one Python process calling
`pytest.main()` twice over `test_json_utils.py`'s property test — second
run fails). Worse, silently: a mutant worker that inherits the stats pass's
executor state fails the same way _for the mutant_, so any mutant covered by
a property test gets scored **killed** although its test errored before
testing behavior.

`process_isolation = "forkserver"` (a mutmut 3.8 config knob) keeps mutmut's
parent pytest-free and forks each operation — stats, clean tests, every
mutant check — from a dedicated server, so each test executes exactly once
per interpreter. Do NOT "fix" this by suppressing the health check in test
files: the tests are correct under single-execution runs, and a harness
process model is not a test property. Note the key is not part of mutmut's
`config_fingerprint`, so changing it reuses the stats cache rather than
recollecting (which is what you want here — the cache maps tests to
functions, and isolation does not change that mapping).

### Frontend targets (Stryker)

Deliberately unchanged by WP4.3: `src/utils/risk.ts`, `src/utils/time.ts`,
`src/utils/confidence.ts` (thresholds informational, `break: null`). A wider
frontend set waits for a baseline to exist — see `frontend/stryker.config.mjs`
header.

### Where the numbers live

| Place                           | What                                                                           | Retention                  |
| ------------------------------- | ------------------------------------------------------------------------------ | -------------------------- |
| `.github/mutation-history.json` | per-run totals + per-module scores + progress, appended by the weekly workflow | ~60 runs (~1 year), in git |
| Workflow step summary           | worst-15 table + no-mutants gap list                                           | per run                    |
| Run artifacts                   | `mutation-score.json` + verdict pack (metas/stats/spans), not the 1.4GB tree   | 14 days                    |

Weekly runs **converge** rather than restart: the denominator (~88k mutants,
run5) cannot finish inside one job budget from cold, so verdicts ride an
`actions/cache` of the few-MB pack (mutant copies regenerate with no test
execution — ~19 min for 269 files measured locally — and mutmut's
function-hash merge preserves restored verdicts). Projected on run5's cost
model (mutmut's own `estimated_worst_case_time` over its stats cache):
per-mutant pytest boot (~8.5s) dominates the wall-clock, so a 240-min CI step
at 12 workers covers ~24.5% of the denominator per week — **~4 weekly runs to
a completed point**, each starting from the previous one's verdicts. Early
history points are partial — `progress.completed=false`, score pessimistic by
construction (unchecked counts as uncaught) and rising toward the true
number. Only `completed` points are comparable as a trend. A budget-killed
run's torn metas (mid-save truncation) are deleted by the repair step before
the next run — mutmut's own loader crashes on them.

The pre-WP4.3 "Overall Mutation Score: 89.2%" in this file's history is not
kept: it predates the mutmut 3 migration, and the pipeline that supposedly
produced it was dead.

### First honest baseline (WP4.3, run6 — 2026-09-18)

| Metric                   | Value                                                                 |
| ------------------------ | --------------------------------------------------------------------- |
| **Score (mutmut badge)** | **54.0%** — (45,127 killed + 2,611 timeout) / 88,329                  |
| Survived                 | 40,571 (45.9%)                                                        |
| no_tests                 | 20 (heatmap_service 6, stgcn_loader 5, backup_service 2, …)           |
| Checked / completed      | 88,329 / 88,329 — `progress.completed=true`, 0 torn metas             |
| Denominator              | 269 targets → 229 scored; 40 zero-mutant modules printed as gaps      |
| Floor                    | 9 modules at 0.0% (age/gender/zero_dce loaders, jobs/queues routes …) |

The dead pipeline's doc claim was 89.2%; the honest first measurement is
54.0%. This is the first `completed` history point — the trend starts here.
The 40 zero-mutant gap modules include all four WP4.5 coverage omits by
construction (their code is never unit-executed, so
`mutate_only_covered_lines` generates nothing for them — the gap list keeps
that visible until WP4.5 closes it).

## Understanding Results

### Mutant States

| State                | Meaning                                            | Action Required                   |
| -------------------- | -------------------------------------------------- | --------------------------------- |
| Killed               | Test detected the mutation                         | None (good!)                      |
| Survived             | Test ran, did not detect it                        | WP4.4: investigate or consolidate |
| Timeout              | Mutation hung the test (counts as caught)          | Usually OK                        |
| No tests             | Selected tests never entered the mutant's function | Usually a selection gap           |
| Skipped              | Excluded from the score denominator                | Check why                         |
| Suspicious           | Abnormal exit (not a clean kill or pass)           | Investigate                       |
| Caught by type check | `type_check_command` refused the mutant            | None (needs mypy config, unset)   |
| Not checked          | Generated, never run (interrupted run)             | Rerun                             |

### Common Mutation Types

#### Arithmetic Operator Mutations

```python
# Original
result = a + b

# Mutants
result = a - b    # Operator changed
result = a * b    # Operator changed
```

#### Comparison Operator Mutations

```python
# Original
if score > 80:

# Mutants
if score >= 80:   # Boundary change
if score < 80:    # Inverted comparison
if score == 80:   # Equality check
```

#### Boolean Mutations

```python
# Original
if is_valid and has_permission:

# Mutants
if is_valid or has_permission:   # And to or
if not is_valid and has_permission:  # Added negation
```

#### Return Value Mutations

```python
# Original
return True

# Mutants
return False  # Inverted return
return None   # Different return
```

## Improving Mutation Score

### 1. Analyze Surviving Mutants

```bash
# Backend: Show details of a surviving mutant
uv run mutmut show 42

# This shows:
# - The original code
# - The mutated code
# - Which test files were run
```

### 2. Add Targeted Tests

For boundary condition survivors:

```python
# Original code
def is_adult(age: int) -> bool:
    return age >= 18

# Surviving mutant: age > 18 (misses age=18 case)

# Fix: Add boundary test
def test_is_adult_at_boundary():
    assert is_adult(18) is True   # Exactly 18
    assert is_adult(17) is False  # Just below
    assert is_adult(19) is True   # Just above
```

For logic survivors:

```python
# Original code
def calculate_discount(is_member: bool, amount: float) -> float:
    if is_member and amount > 100:
        return amount * 0.1
    return 0

# Surviving mutant: Changed 'and' to 'or'

# Fix: Test both conditions independently
def test_discount_requires_both_conditions():
    # Member with high amount - gets discount
    assert calculate_discount(True, 150) == 15.0

    # Non-member with high amount - no discount
    assert calculate_discount(False, 150) == 0

    # Member with low amount - no discount
    assert calculate_discount(True, 50) == 0
```

### 3. Property-Based Testing

Use Hypothesis to generate test cases that cover edge cases:

```python
from hypothesis import given, strategies as st

@given(st.integers(min_value=0, max_value=100))
def test_risk_score_always_returns_valid_level(score: int):
    level = get_risk_level(score)
    assert level in ['low', 'medium', 'high', 'critical']
```

## Configuration

### Backend (pyproject.toml)

```toml
[tool.mutmut]
# Paths to mutate (well-tested, critical modules)
paths_to_mutate = [
    "backend/services/bbox_validation.py",
    "backend/services/severity.py",
    "backend/services/prompt_parser.py",
    "backend/services/search.py",
    "backend/services/dedupe.py",
]
# Tests directory
tests_dir = ["backend/tests/unit/services/"]
# Extra pytest CLI args - disable xdist for mutation testing
pytest_add_cli_args = ["-x", "-q", "--tb=short", "-p", "no:benchmark", "-o", "addopts="]
# Also copy required backend modules to mutants directory
also_copy = ["backend/"]
```

### Frontend (stryker.config.mjs)

```javascript
export default {
  mutate: ['src/utils/risk.ts', 'src/utils/time.ts'],
  testRunner: 'vitest',
  checkers: ['typescript'],
  thresholds: {
    high: 80,
    low: 60,
    break: null, // Set to fail CI below threshold
  },
};
```

## CI Integration

Mutation testing runs as a **non-blocking** check in CI. This is intentional because:

1. Mutation testing is slow (minutes to hours for full runs)
2. Not all surviving mutants indicate real problems
3. Blocking on 100% mutation score is often impractical

### GitHub Actions Workflow

The mutation testing workflow runs on:

- Weekly schedule (for comprehensive analysis)
- Manual trigger (for on-demand verification)

Results are uploaded as artifacts for review without blocking PRs.

## Best Practices

### Do

- **Start small**: Begin with pure utility functions
- **Focus on critical paths**: Prioritize business logic over UI code
- **Investigate survivors**: Each surviving mutant is a potential test gap
- **Use boundary testing**: Test exact threshold values, not just ranges
- **Combine with property testing**: Use Hypothesis for edge case discovery

### Don't

- **Don't obsess over 100%**: Some mutants are equivalent (semantically identical)
- **Don't test trivial mutations**: Getters, setters, and logging are often not worth testing
- **Don't mutate everything**: Focus on code where correctness matters most
- **Don't block CI on score**: Use mutation testing as guidance, not enforcement

## Equivalent Mutants

Some mutations produce code that is semantically identical to the original. These "equivalent mutants" can never be killed and should be ignored.

Example of equivalent mutant:

```python
# Original
for i in range(len(items)):
    process(items[i])

# Equivalent mutant (same behavior)
for i in range(len(items) + 0):
    process(items[i])
```

## Analysis of Surviving Mutants (NEM-1364)

During the expansion of mutation testing to additional modules (search.py, dedupe.py, prompt_parser.py),
we identified several patterns of surviving mutants:

### SQLAlchemy Query Building (search.py)

Many surviving mutants are in SQLAlchemy expression construction. These mutations survive because:

- Unit tests verify the presence of conditions in compiled query strings
- They don't execute queries against a real database
- The actual behavior requires integration tests

**Example surviving mutant:**

```python
# Original
has_operators = any(op in tsquery_str for op in ["&", "|", "!", "<->"])

# Mutated to:
has_operators = None
```

This survives because the tests check `has_search` boolean but don't verify the query
actually uses `to_tsquery` vs `websearch_to_tsquery`.

**Fix approach:** Add tests that verify the compiled SQL includes expected function calls.

### Parameter Pass-through (dedupe.py)

Some mutations replace parameters with `None` but survive because:

- The parameter is only used for logging/debugging
- Tests verify return values but not stored values

**Example surviving mutant:**

```python
# Original
await self.mark_processed(file_path, file_hash)

# Mutated to:
await self.mark_processed(None, file_hash)
```

**Fix approach:** Added test `test_is_duplicate_and_mark_passes_file_path_to_mark_processed`
that verifies the value stored in Redis matches the file_path.

### Error Handling Paths

Many surviving mutants are in error handling code that would require:

- Injecting specific errors in mocked dependencies
- Testing edge cases that are hard to trigger

These are often acceptable as "equivalent mutants" when the error handling
is defensive programming.

## Troubleshooting

### Mutation Tests Are Too Slow

1. **Narrow scope**: Test fewer modules at once
2. **Use targeted tests**: Configure to run only relevant test files
3. **Increase timeout**: Some mutants legitimately take longer

```bash
# One module's mutants only (mutmut 3: fnmatch over mutant keys, config-owned runner)
./scripts/mutation-run.sh severity

# Cap parallel workers when the box is doing something else
MUTMAX=4 ./scripts/mutation-run.sh
```

Per-mutant test selection is automatic in mutmut 3 (dependency tracking maps
each mutant to the tests that actually enter its function) — the 2.x habit of
hand-wiring `--runner "pytest <one file>"` is both gone and unnecessary.

### Too Many Surviving Mutants

1. Check if tests actually assert behavior (not just call functions)
2. Add edge case tests for boundary conditions
3. Test error paths, not just happy paths

### False Positives

Some survived mutants are acceptable:

- Logging statements
- Debug/trace code
- Defensive programming (e.g., duplicate checks)

## Further Reading

- [mutmut Documentation](https://mutmut.readthedocs.io/)
- [Stryker Documentation](https://stryker-mutator.io/docs/)
- [Mutation Testing: A Practitioner's Guide](https://testing.googleblog.com/2021/04/mutation-testing.html)

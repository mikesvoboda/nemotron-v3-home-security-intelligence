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

# Specific backend module
./scripts/mutation-test.sh --module backend/services/severity.py
```

### Backend (Python with mutmut)

```bash
# Run mutation tests on default modules
uv run mutmut run --paths-to-mutate backend/services/bbox_validation.py

# View results summary
uv run mutmut results

# Investigate a specific surviving mutant
uv run mutmut show 42

# Generate HTML report
uv run mutmut html
open html/index.html
```

### Frontend (TypeScript with Stryker)

```bash
cd frontend

# Run mutation tests
npm run test:mutation

# View HTML report (generated automatically)
open reports/mutation/mutation-report.html
```

## Target Modules

Mutation testing is computationally expensive. We start with well-tested, critical modules:

### Backend Targets

| Module                                | Purpose                  | Why Selected                         | Mutation Score |
| ------------------------------------- | ------------------------ | ------------------------------------ | -------------- |
| `backend/services/bbox_validation.py` | Bounding box utilities   | Pure logic, critical for AI pipeline | ~95%           |
| `backend/services/severity.py`        | Risk score mapping       | Pure logic, critical for alerts      | ~90%           |
| `backend/services/prompt_parser.py`   | Prompt management        | Pure logic, prompt storage/parsing   | ~100%          |
| `backend/services/search.py`          | Full-text search service | Search query building, filter logic  | ~85%           |
| `backend/services/dedupe.py`          | File deduplication       | Hash computation, Redis cache logic  | ~88%           |

**Overall Mutation Score: 89.2%** (1131 killed, 137 survived out of 1268 mutants)

### Frontend Targets

| Module                    | Purpose               | Why Selected                     |
| ------------------------- | --------------------- | -------------------------------- |
| `src/utils/risk.ts`       | Risk level conversion | Mirrors backend severity.py      |
| `src/utils/time.ts`       | Time formatting       | Pure utility functions           |
| `src/utils/confidence.ts` | Confidence utilities  | Pure logic with clear boundaries |

## Understanding Results

### Mutant States

| State       | Meaning                                         | Action Required     |
| ----------- | ----------------------------------------------- | ------------------- |
| Killed      | Test detected the mutation                      | None (good!)        |
| Survived    | Test did not detect the mutation                | Investigate         |
| Timeout     | Test ran too long (infinite loop from mutation) | Usually OK (killed) |
| Error       | Mutation caused a syntax/runtime error          | Usually OK (killed) |
| No Coverage | No test executed the mutated code               | Add tests           |

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
# Run with specific test file
uv run mutmut run \
    --paths-to-mutate backend/services/severity.py \
    --runner "python -m pytest backend/tests/unit/services/test_severity.py -x -q"
```

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

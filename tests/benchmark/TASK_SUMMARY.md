# TDD Phase 1: Benchmark Comparison Tool Tests - Task Summary

## Overview

This task implements comprehensive pytest tests for `scripts/benchmark/compare.py`, a benchmark comparison tool for analyzing LLM performance metrics. Following Test-Driven Development (TDD) principles, these tests represent the **RED phase** where all tests fail initially.

## Files Created

### Test Files

1. **`tests/benchmark/test_compare.py`** (643 lines)
   - 33 comprehensive test cases
   - 9 test classes covering all functionality
   - Full coverage of expected behavior

### Implementation Stubs

2. **`scripts/benchmark/compare.py`** (195 lines)
   - Empty class and function stubs
   - All functions raise `NotImplementedError("TDD: Implementation pending")`
   - Proper docstrings and type hints

### Documentation

3. **`tests/benchmark/README.md`**

   - Complete test documentation
   - Expected JSON structure
   - Example output format
   - Implementation checklist
   - Symbol legend (↑↓—)

4. **`tests/benchmark/__init__.py`**
   - Package initialization
   - Module docstring

## Test Coverage Breakdown

### 1. TestBenchmarkResultLoader (4 tests)

- Load valid JSON benchmark files
- Handle missing files (FileNotFoundError)
- Handle invalid JSON (ValueError)
- Validate required fields

### 2. TestDeltaCalculation (5 tests)

- Calculate percentage deltas (increase/decrease)
- Handle zero baseline (error)
- Handle negative values
- Calculate metric-specific deltas

### 3. TestMarkdownTableGeneration (4 tests)

- Generate latency comparison tables
- Generate throughput comparison tables
- Generate VRAM comparison tables
- Generate quality comparison tables

### 4. TestImprovementRegression (6 tests)

- Latency decrease shows ↓ (improvement)
- Latency increase shows ↑ (regression)
- Throughput increase shows ↑ (improvement)
- VRAM decrease shows ↓ (improvement)
- Quality decrease shows ↑ (regression)
- Zero delta shows — (no change)

### 5. TestMissingMetrics (3 tests)

- Individual missing metrics show N/A
- Missing entire metric categories
- Both baseline and test missing

### 6. TestCLIInterface (4 tests)

- Require baseline and test arguments
- Parse file paths
- Parse optional output file
- Default to stdout

### 7. TestFullComparisonReport (2 tests)

- Generate complete comparison report
- Save report to file

### 8. TestEdgeCases (4 tests)

- Identical results (0% delta)
- Very large deltas (400%+)
- Very small deltas (<1%)
- Empty metrics dictionaries

### 9. TestMultipleComparisons (1 test)

- Compare 3+ benchmark runs

## Test Execution Status

✅ **All 33 tests FAIL as expected** (TDD RED phase)

```bash
$ uv run pytest tests/benchmark/test_compare.py --no-cov -q
============================== 33 failed in 1.51s ==============================
```

Each test fails with:

```
NotImplementedError: TDD: Implementation pending
```

## Expected Comparison Tool Behavior

### Input: Benchmark JSON Files

```json
{
  "model_name": "nemotron-70b-Q4_K_M",
  "timestamp": "2026-02-05T10:30:00",
  "metrics": {
    "latency": {
      "p50_ms": 39600,
      "p95_ms": 42100,
      "p99_ms": 43800
    },
    "throughput": {
      "requests_per_min": 1.51,
      "tokens_per_sec": 12.4
    },
    "vram": {
      "peak_mb": 14700,
      "steady_state_mb": 14200
    },
    "quality": {
      "accuracy_pct": 100.0,
      "risk_level_match_pct": 100.0
    }
  }
}
```

### Output: Markdown Comparison Table

```markdown
| Metric      | Baseline (Q4_K_M) | Test (Q3_K_M) | Delta    |
| ----------- | ----------------- | ------------- | -------- |
| P50 Latency | 39.6s             | 32.1s         | -19.0% ↓ |
| VRAM Peak   | 14.7 GB           | 11.2 GB       | -23.8% ↓ |
| Accuracy    | 100.0%            | 96.2%         | -3.8% ↑  |
```

## Symbol Semantics

- **↓ (down arrow)**: Improvement for lower-is-better metrics (latency, VRAM)
- **↑ (up arrow)**: Improvement for higher-is-better metrics (throughput) OR regression for quality
- **— (em dash)**: No change (0% delta)

## CLI Interface

```bash
# Compare two runs
python scripts/benchmark/compare.py --baseline q4.json --test q3.json

# Save to file
python scripts/benchmark/compare.py --baseline q4.json --test q3.json --output comparison.md

# Compare multiple runs
python scripts/benchmark/compare.py --multiple q4.json q3.json q2.json
```

## Key Design Decisions

1. **Metric-Specific Interpretation**: Different symbols based on whether lower or higher is better
2. **Graceful Degradation**: Missing metrics show "N/A" rather than failing
3. **Percentage Precision**: Single decimal place (e.g., "-19.0%")
4. **Unit Conversion**:
   - Latency: ms → seconds (39600ms → 39.6s)
   - VRAM: MB → GB (14700MB → 14.7 GB)
5. **Error Handling**: Specific exceptions for missing files, invalid JSON, missing fields

## Next Steps (GREEN Phase)

Implement functionality in `scripts/benchmark/compare.py` to make tests pass:

1. ✅ JSON loading with error handling
2. ✅ Delta calculation with zero-baseline protection
3. ✅ Markdown table generation
4. ✅ Symbol formatting based on metric type
5. ✅ Missing metric handling
6. ✅ CLI argument parsing
7. ✅ Report generation and file I/O
8. ✅ Multiple benchmark comparison

## Verification

Run tests to verify RED phase:

```bash
uv run pytest tests/benchmark/test_compare.py -v
```

Expected: 33 tests FAIL with `NotImplementedError`

## Related Linear Issue

**NEM-5443**: [TDD] Phase 1: Benchmark Infrastructure

Part of the LLM performance optimization epic focusing on benchmark infrastructure for comparing model quantizations and configurations.

## File Locations

- **Tests**: `tests/benchmark/test_compare.py`
- **Implementation**: `scripts/benchmark/compare.py`
- **Documentation**: `tests/benchmark/README.md`

## TDD Progress

- [x] **RED Phase**: Write failing tests (COMPLETE)
- [ ] **GREEN Phase**: Implement functionality to pass tests (NEXT)
- [ ] **REFACTOR Phase**: Optimize and clean up implementation (FUTURE)

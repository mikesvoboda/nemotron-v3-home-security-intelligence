# Benchmark Comparison Tool Tests

This directory contains comprehensive tests for the benchmark comparison tool (`scripts/benchmark/compare.py`).

## Test-Driven Development (TDD)

These tests follow TDD principles:

1. **RED Phase** (Current): Tests are written first and fail with `NotImplementedError`
2. **GREEN Phase** (Next): Implement functionality to make tests pass
3. **REFACTOR Phase** (Final): Optimize and clean up implementation while keeping tests green

## Test Coverage

### TestBenchmarkResultLoader

Tests for loading and validating benchmark result JSON files:

- `test_load_single_benchmark_file`: Verify loading valid JSON with proper structure
- `test_load_missing_file_raises_error`: Ensure FileNotFoundError for missing files
- `test_load_invalid_json_raises_error`: Validate JSON parsing error handling
- `test_load_missing_required_fields_raises_error`: Check required field validation

### TestDeltaCalculation

Tests for calculating percentage deltas between baseline and test runs:

- `test_calculate_percentage_delta_decrease`: Test improvements (negative delta)
- `test_calculate_percentage_delta_increase`: Test regressions (positive delta)
- `test_calculate_percentage_delta_zero_baseline`: Validate error for zero baseline
- `test_calculate_percentage_delta_negative_values`: Handle negative metric values
- `test_calculate_latency_deltas`: Comprehensive latency metric delta calculation

### TestMarkdownTableGeneration

Tests for generating formatted markdown comparison tables:

- `test_generate_latency_comparison_table`: P50/P95/P99 latency table
- `test_generate_throughput_comparison_table`: Requests/min and tokens/sec table
- `test_generate_vram_comparison_table`: Peak and steady-state VRAM table
- `test_generate_quality_comparison_table`: Accuracy and risk level match table

### TestImprovementRegression

Tests for highlighting improvements (↓) and regressions (↑):

- `test_latency_decrease_shows_improvement`: Lower latency = ↓ (improvement)
- `test_latency_increase_shows_regression`: Higher latency = ↑ (regression)
- `test_throughput_increase_shows_improvement`: Higher throughput = ↑ (improvement)
- `test_vram_decrease_shows_improvement`: Lower VRAM = ↓ (improvement)
- `test_quality_decrease_shows_regression`: Lower quality = ↑ (regression)
- `test_zero_delta_shows_no_change`: Zero delta = — (no change)

### TestMissingMetrics

Tests for handling missing or incomplete data:

- `test_missing_latency_metric_shows_na`: Individual missing metrics show "N/A"
- `test_missing_entire_metric_category`: Missing category handled gracefully
- `test_both_metrics_missing_shows_na`: Both baseline and test missing shows "N/A"

### TestCLIInterface

Tests for command-line argument parsing:

- `test_cli_requires_baseline_and_test_args`: Verify required arguments
- `test_cli_parse_baseline_and_test_files`: Parse baseline and test file paths
- `test_cli_parse_output_file`: Parse optional output file path
- `test_cli_default_output_to_stdout`: Default to stdout if no output specified

### TestFullComparisonReport

Tests for generating complete comparison reports:

- `test_generate_full_comparison_report`: All sections included in report
- `test_save_report_to_file`: Save markdown report to file

### TestEdgeCases

Tests for edge cases and boundary conditions:

- `test_identical_results_show_zero_deltas`: Identical runs show 0% delta
- `test_very_large_deltas_formatted_correctly`: Handle 400%+ deltas
- `test_very_small_deltas_show_precision`: Handle sub-1% deltas
- `test_empty_metrics_handled_gracefully`: Empty metrics dictionary

### TestMultipleComparisons

Tests for comparing multiple benchmark runs:

- `test_compare_three_benchmark_runs`: Compare 3+ benchmark files

## Expected JSON Structure

Benchmark result files should follow this structure:

```json
{
  "model_name": "nemotron-70b-Q4_K_M",
  "timestamp": "2026-02-05T10:30:00",
  "metrics": {
    "latency": {
      "p50_ms": 39600,
      "p95_ms": 42100,
      "p99_ms": 43800,
      "mean_ms": 39800
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

## Expected Output Format

The comparison tool should generate markdown tables like:

```markdown
# Benchmark Comparison Report

## Latency Comparison

| Metric      | Baseline (Q4_K_M) | Test (Q3_K_M) | Delta    |
| ----------- | ----------------- | ------------- | -------- |
| P50 Latency | 39.6s             | 32.1s         | -19.0% ↓ |
| P95 Latency | 42.1s             | 34.5s         | -18.1% ↓ |
| P99 Latency | 43.8s             | 36.2s         | -17.4% ↓ |

## Throughput Comparison

| Metric       | Baseline (Q4_K_M) | Test (Q3_K_M) | Delta    |
| ------------ | ----------------- | ------------- | -------- |
| Requests/min | 1.51              | 1.87          | +23.8% ↑ |
| Tokens/sec   | 12.4              | 15.3          | +23.4% ↑ |

## VRAM Comparison

| Metric            | Baseline (Q4_K_M) | Test (Q3_K_M) | Delta    |
| ----------------- | ----------------- | ------------- | -------- |
| VRAM Peak         | 14.7 GB           | 11.2 GB       | -23.8% ↓ |
| VRAM Steady-State | 14.2 GB           | 10.8 GB       | -23.9% ↓ |

## Quality Comparison

| Metric           | Baseline (Q4_K_M) | Test (Q3_K_M) | Delta   |
| ---------------- | ----------------- | ------------- | ------- |
| Accuracy         | 100.0%            | 96.2%         | -3.8% ↑ |
| Risk Level Match | 100.0%            | 94.8%         | -5.2% ↑ |
```

## Symbol Legend

- **↓ (down arrow)**: Improvement for metrics where lower is better (latency, VRAM)
- **↑ (up arrow)**: Improvement for metrics where higher is better (throughput, quality) OR regression for lower-is-better metrics
- **— (em dash)**: No change (0% delta)

## Running Tests

Run all benchmark comparison tests:

```bash
# Run all tests
uv run pytest tests/benchmark/test_compare.py -v

# Run specific test class
uv run pytest tests/benchmark/test_compare.py::TestBenchmarkResultLoader -v

# Run specific test
uv run pytest tests/benchmark/test_compare.py::TestBenchmarkResultLoader::test_load_single_benchmark_file -v
```

## Implementation Checklist

When implementing the comparison tool (GREEN phase), ensure:

- [ ] JSON loading with proper error handling
- [ ] Required field validation (model_name, metrics)
- [ ] Percentage delta calculation (handling zero baseline)
- [ ] Markdown table generation with proper formatting
- [ ] Symbol indicators based on metric type (lower/higher is better)
- [ ] Missing metric handling (N/A values)
- [ ] CLI argument parsing (baseline, test, output)
- [ ] File I/O for saving reports
- [ ] Multiple benchmark comparison support

## Related Files

- **Implementation**: `scripts/benchmark/compare.py`
- **Tests**: `tests/benchmark/test_compare.py`

## Next Steps

1. **GREEN Phase**: Implement functionality in `scripts/benchmark/compare.py` to make tests pass
2. **Verify**: Run `uv run pytest tests/benchmark/test_compare.py -v` until all tests pass
3. **REFACTOR Phase**: Optimize implementation while keeping tests green
4. **Integration**: Use comparison tool in CI/CD for performance regression detection

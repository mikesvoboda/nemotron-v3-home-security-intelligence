# Tests - Benchmark Module

## Purpose

Test suite for the benchmark infrastructure under `scripts/benchmark/` — quality scoring, result comparison, engine comparison, and load testing.

## Test Structure

### test_quality.py

Test suite for `scripts/benchmark/quality.py` — the quality-scoring module (42 tests, all passing).

**Coverage Areas:**

- **Risk Score Accuracy**: MAE calculation, threshold validation (±5 acceptable, ±10 marginal)
- **Risk Level Classification**: Exact match rate for low/medium/high/critical levels
- **JSON Validity**: Schema compliance, field validation, error handling
- **Reasoning Quality**: Presence checks, coherence validation, consistency verification

**Test Classes:**

- `TestRiskScoreAccuracy`: MAE calculations and edge cases
- `TestRiskLevelMatching`: Classification accuracy metrics
- `TestJSONValidity`: JSON parsing and validation
- `TestReasoningQuality`: Reasoning presence and quality checks
- `TestQualityScorer`: Integration tests for scoring workflows
- `TestEdgeCases`: Boundary conditions, unicode, large datasets

**Fixtures** (defined in `test_quality.py`):

- `valid_ground_truth`: Sample ground truth data
- `valid_llm_response`: Sample LLM response
- `quality_scorer`: QualityScorer instance
- `sample_dataset`: Multi-sample test data

### test_compare.py

Test suite for `scripts/benchmark/compare.py` — delta calculation and markdown report generation across benchmark result JSON files (33 tests, all passing).

**Test Classes:**

- `TestBenchmarkResultLoader`: JSON loading and required-field validation
- `TestDeltaCalculation`: Percentage deltas against a baseline
- `TestMarkdownTableGeneration`: Latency/throughput/VRAM tables
- `TestImprovementRegression`: Improvement vs regression classification
- `TestMissingMetrics`: Absent-metric handling
- `TestCLIInterface`: Command-line parsing
- `TestFullComparisonReport`: End-to-end report shape
- `TestEdgeCases`, `TestMultipleComparisons`

### test_engine_comparison.py

Test suite for `scripts/benchmark/engine_comparison.py` — engine configuration, request formatting, response parsing, and comparison reporting for the `llama.cpp` and `vllm` arms (44 tests, all passing).

**Test Classes:**

- `TestEngineType`, `TestEngineConfig`, `TestEngineMetrics`: dataclass invariants
- `TestEngineConfigs`: the shipped `ENGINE_CONFIGS` map (ports, api formats)
- `TestEngineComparator`: health checks, benchmarking, `skip_unavailable` behaviour
- `TestOpenAICompatibility`: `/v1/chat/completions` request/response shape
- `TestComparisonReport`, `TestCompareEnginesFunction`: report generation
- `TestDockerComposeIntegration`: the documented `vllm`-profile expectations
- `TestMetricsCollection`, `TestCLI`, `TestEdgeCases`

### test_load_test.py

Test suite for `scripts/benchmark/load_test.py` — sustained-load and burst configuration, metrics, and report generation (29 tests).

**Test Classes:**

- `TestLoadConfig`, `TestSustainedLoadConfig`, `TestBurstConfig`: configuration dataclasses
- `TestLoadTestMetrics`, `TestReportGeneration`: metrics aggregation and output
- `TestLoadTestRunner`, `TestRequestGeneration`, `TestSustainedLoadBehavior`, `TestBurstBehavior`, `TestPriorityQueueMeasurement`: runner behaviour
- `TestCLI`, `TestEdgeCases`

`TestSustainedLoadBehavior`, `TestPriorityQueueMeasurement`, and the sustained-load runner test drive real wall-clock pacing and exceed the 5 s per-test timeout on a GPU-less host; the rest of the file is deterministic.

## Running Tests

```bash
# Run all benchmark tests
uv run pytest tests/benchmark/ -v

# Run quality tests only
uv run pytest tests/benchmark/test_quality.py -v

# Run specific test class
uv run pytest tests/benchmark/test_quality.py::TestRiskScoreAccuracy -v

# Run with coverage
uv run pytest tests/benchmark/ --cov=scripts/benchmark --cov-report=html
```

## Implementation Status

The modules under test are implemented and their suites are green:

- `quality.py`: MAE, JSON validation, reasoning scoring, risk-level matching, dataset aggregation — 42 tests pass.
- `compare.py`: loader, deltas, markdown tables, CLI — 33 tests pass.
- `engine_comparison.py`: configs, comparator, OpenAI compatibility, report — 44 tests pass.
- `load_test.py`: configs, runner, reports, CLI — green apart from the wall-clock pacing tests noted above.

## Key Testing Patterns

1. **Ground Truth Format**:

   ```python
   {
       "risk_score": 25,      # 0-100
       "risk_level": "low",   # low/medium/high/critical
       "summary": "...",
       "reasoning": "..."
   }
   ```

2. **MAE Thresholds**:

   - Acceptable: ±5 points
   - Marginal: ±10 points
   - Out of bounds: >±10 points

3. **Validation Checks**:
   - Empty/None values
   - Mismatched list lengths
   - Out-of-range scores (0-100)
   - Invalid risk levels
   - Missing required fields
   - Type mismatches

## Dependencies

- pytest fixtures for test data setup
- `scripts.benchmark.quality`, `.compare`, `.engine_comparison`, `.load_test`
- Standard library: json, typing

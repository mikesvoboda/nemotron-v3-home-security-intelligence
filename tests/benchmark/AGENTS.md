# Tests - Benchmark Module

## Purpose

Test suite for LLM benchmark infrastructure, validating quality scoring, metrics collection, and performance comparison functionality.

## Test Structure

### test_quality.py

Comprehensive test suite for `scripts/benchmark/quality.py` - quality scoring module.

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

**Fixtures:**

- `valid_ground_truth`: Sample ground truth data
- `valid_llm_response`: Sample LLM response
- `quality_scorer`: QualityScorer instance
- `sample_dataset`: Multi-sample test data

### test_metrics.py

Tests for metrics collection (latency, VRAM, throughput).

### test_compare.py

Tests for benchmark comparison and analysis.

### test_runner.py

Comprehensive test suite for `scripts/benchmark/run_benchmark.py` - the main benchmark orchestrator.

**Coverage Areas:**

- **Configuration**: BenchmarkConfig initialization, validation, and defaults
- **Evaluation Set Loading**: 100-event dataset loading and validation
- **Single Request Latency**: One request at a time, measure response time
- **Sustained Load**: Continuous requests at configurable rate
- **Burst Handling**: Simulate 10+ simultaneous detections
- **Cold Start**: Time from service start to first successful inference
- **Results Output**: JSON file generation with metadata
- **CLI Argument Parsing**: Command-line interface validation
- **Error Handling**: Service unavailable, timeout, partial failures
- **Integration**: End-to-end workflow testing

**Test Classes:**

- `TestBenchmarkConfig`: Configuration dataclass tests (6 tests)
- `TestBenchmarkRunner`: Runner initialization and evaluation set loading (3 tests)
- `TestSingleRequestLatency`: Single request scenario tests (3 tests)
- `TestSustainedLoad`: Sustained load scenario tests (3 tests)
- `TestBurstHandling`: Burst scenario tests (3 tests)
- `TestColdStart`: Cold start scenario tests (3 tests)
- `TestBenchmarkOrchestration`: Full orchestration tests (3 tests)
- `TestResultsOutput`: JSON output tests (3 tests)
- `TestCLIArgumentParsing`: CLI argument tests (9 tests)
- `TestErrorHandling`: Error resilience tests (3 tests)
- `TestIntegration`: End-to-end workflow tests (2 tests)

**Total:** 40 test cases

**Fixtures:**

- `mock_metrics_collector`: Mocked MetricsCollector with realistic metrics
- `mock_quality_scorer`: Mocked QualityScorer for response evaluation
- `mock_evaluation_set`: Temporary directory with 100 sample JSON events
- `benchmark_config`: Fully configured BenchmarkConfig instance

**Stub Implementation:** `scripts/benchmark/run_benchmark.py` contains:

- `BenchmarkConfig` dataclass with validation stubs
- `BenchmarkResults` dataclass for result structure
- `QualityScorer` class with scoring method stubs
- `BenchmarkRunner` class with scenario execution stubs
- `parse_args()` function (fully implemented, tests passing)
- `main()` async entry point stub

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

## TDD Status

Current phase: **RED** - Tests written first, all tests should FAIL until implementation is complete.

Expected behavior:

- All tests raise `NotImplementedError` with message "TDD RED phase: implement this function/method"
- Imports succeed (stub implementations exist)
- Test structure and assertions are validated

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
- `scripts.benchmark.quality` module (stub exists)
- Standard library: json, typing

## Next Steps (GREEN Phase)

1. Implement `calculate_risk_score_mae()` function
2. Implement `validate_json_response()` function
3. Implement `check_reasoning_quality()` function
4. Implement `QualityScorer.calculate_risk_level_match_rate()` method
5. Implement `QualityScorer.score_response()` method
6. Implement `QualityScorer.score_dataset()` method
7. Verify all tests pass
8. Refactor for optimization (REFACTOR phase)

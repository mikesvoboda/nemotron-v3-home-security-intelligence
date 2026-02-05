# Scripts - Benchmark Module

## Purpose

LLM performance benchmarking infrastructure for measuring and comparing model quality, latency, throughput, and resource utilization.

## Files

### quality.py

Quality scoring module for evaluating LLM responses against ground truth data.

**Status**: TDD RED phase (stub implementation)

**Components:**

#### Data Classes

- `RiskScoreMetrics`: Single response evaluation results

  - mae: Mean absolute error
  - risk_level_match: Boolean for classification match
  - json_valid: JSON validity flag
  - reasoning_score: Quality score (0.0-1.0)

- `QualityReport`: Aggregated dataset metrics
  - overall_quality: Combined quality score (0.0-1.0)
  - average_mae: Mean absolute error across dataset
  - mae_acceptable_rate: Percentage within ±5 threshold
  - mae_marginal_rate: Percentage within ±10 threshold
  - risk_level_accuracy: Classification match rate
  - json_validity_rate: Valid JSON percentage
  - average_reasoning_score: Mean reasoning quality
  - total_samples: Dataset size

#### Functions

- `calculate_risk_score_mae()`: MAE calculation with validation
- `validate_json_response()`: JSON parsing and schema validation
- `check_reasoning_quality()`: Reasoning coherence and quality scoring

#### Classes

- `QualityScorer`: Main scoring orchestrator
  - `calculate_risk_level_match_rate()`: Classification accuracy
  - `score_response()`: Single response evaluation
  - `score_dataset()`: Batch scoring with aggregation

### metrics.py

Metrics collection for latency, VRAM, and throughput measurement.

### compare.py

Benchmark comparison and analysis utilities.

### runner.py

Benchmark execution orchestration and workflow management.

## Ground Truth Schema

```python
{
    "risk_score": int,      # 0-100 range
    "risk_level": str,      # low/medium/high/critical
    "summary": str,         # Brief description
    "reasoning": str        # Detailed explanation
}
```

## Quality Thresholds

| Metric              | Acceptable | Marginal | Poor |
| ------------------- | ---------- | -------- | ---- |
| MAE                 | ≤5         | ≤10      | >10  |
| Risk Level Accuracy | ≥90%       | ≥70%     | <70% |
| JSON Validity       | 100%       | ≥95%     | <95% |
| Reasoning Score     | ≥0.7       | ≥0.5     | <0.5 |

## Usage Example (After Implementation)

```python
from scripts.benchmark.quality import QualityScorer

# Initialize scorer
scorer = QualityScorer()

# Score single response
ground_truth = {
    "risk_score": 25,
    "risk_level": "low",
    "summary": "Person at door",
    "reasoning": "Low risk during daytime"
}
llm_response = {
    "risk_score": 27,
    "risk_level": "low",
    "summary": "Person detected",
    "reasoning": "Minimal risk"
}
metrics = scorer.score_response(ground_truth, llm_response)

# Score dataset
dataset = [(ground_truth1, response1), (ground_truth2, response2)]
report = scorer.score_dataset(dataset)
print(f"Overall quality: {report.overall_quality:.2%}")
```

## Development Workflow

### Current Phase: RED

- [x] Tests written (42 tests)
- [x] Stub implementation created
- [x] All tests fail with NotImplementedError
- [ ] Implementation pending

### Next Phase: GREEN

1. Implement MAE calculation with validation
2. Implement JSON validation with schema checks
3. Implement reasoning quality scoring
4. Implement risk level matching
5. Implement single response scoring
6. Implement dataset aggregation
7. Verify all 42 tests pass

### Final Phase: REFACTOR

- Optimize performance for large datasets
- Add caching for repeated validations
- Extract constants for thresholds
- Add logging and debugging support
- Consider async/parallel processing

## Testing

```bash
# Run quality module tests
uv run pytest tests/benchmark/test_quality.py -v

# Run with coverage
uv run pytest tests/benchmark/test_quality.py --cov=scripts/benchmark/quality

# Check test status
uv run pytest tests/benchmark/test_quality.py --tb=no -q
```

## Dependencies

- Standard library: json, dataclasses, typing
- No external dependencies required

## Design Decisions

1. **Dataclasses over dicts**: Type safety and IDE support
2. **Separate functions vs methods**: Reusable utility functions
3. **MAE thresholds**: Based on risk scoring domain (0-100 scale)
4. **Quality score**: Weighted combination of all metrics
5. **Validation strictness**: Fail fast on schema violations

## Integration Points

- Synthetic data generation (for ground truth)
- LLM inference pipeline (for responses)
- Benchmark comparison (for historical analysis)
- CI/CD metrics collection (for performance tracking)

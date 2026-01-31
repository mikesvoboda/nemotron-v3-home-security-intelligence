# Automated Risk Score Validation Test Suite

**Date:** 2026-01-31
**Status:** Implemented
**Related Issues:** NEM-4533, NEM-4529, NEM-4527

## Context

The AI pipeline's risk scoring accuracy needed automated validation against synthetic test scenarios. Previously, validation was manual and inconsistent, making it difficult to catch regressions in risk assessment quality.

## Decision

Implemented a comprehensive automated validation test suite with three components:

### 1. Integration Test Suite (NEM-4533)

**File:** `backend/tests/integration/test_risk_score_validation.py`

**Features:**

- Loads synthetic scenarios from `data/synthetic/` with `expected_labels.json`
- Compares actual risk scores to expected ranges
- Reports pass/fail based on score being within expected range
- Calculates **gap rate** (should be <20%)
- Validates per-class detection accuracy (precision, recall, F1)
- Generates scenario-type breakdown (normal/suspicious/threats)
- Analyzes confidence distribution percentiles

**Key Metrics:**

1. **Gap Rate:**

   - Percentage of scenarios where actual risk score falls outside expected range
   - Target: < 20%
   - Calculation: `(Scenarios with gaps / Total scenarios) × 100%`

2. **Per-Class Metrics (NEM-4529):**

   - Precision, recall, F1 for each object class (Person, Car, Dog, etc.)
   - Identifies which detection types are underperforming

3. **Per-Scenario-Type Metrics (NEM-4529):**

   - Aggregated metrics by category (normal, suspicious, threats)
   - Highlights which scenario types have highest error rates

4. **Confidence Distribution (NEM-4529):**
   - P50, P90, P95, P99 percentiles of detection confidence
   - Indicates model certainty patterns

**Test Methods:**

```python
class TestRiskScoreValidation:
    async def test_load_synthetic_scenarios()
    async def test_risk_score_ranges_match_category()
    async def test_gap_rate_below_threshold()
    async def test_per_class_detection_accuracy()
    async def test_scenario_type_breakdown()
    async def test_confidence_distribution_percentiles()
```

### 2. Enhanced Validation Script (NEM-4529)

**File:** `scripts/validate_detections.py` (improvements documented, to be applied in separate PR)

**Planned Enhancements:**

- Per-class precision/recall/F1 calculation
- Scenario-type breakdown analysis
- Confidence distribution percentiles
- Enhanced JSON export with detailed metrics

**Note:** Script enhancements are documented but not applied in this PR to maintain separation of concerns. They will be implemented after the test suite is merged and validated.

### 3. Coverage Documentation (NEM-4527)

**File:** `docs/guides/detection-validation-coverage.md`

**Contents:**

- How to process synthetic scenarios through the pipeline
- Three methods: camera directory, API upload, bulk processing script
- Interpreting validation results
- Troubleshooting guide
- Best practices for continuous validation

## Implementation Details

### Gap Calculation

```python
if expected_min <= actual_score <= expected_max:
    gap = 0.0  # Within range
elif actual_score < expected_min:
    gap = float(expected_min - actual_score)  # Below range
else:
    gap = float(actual_score - expected_max)  # Above range
```

### Per-Class Metrics

For each object class:

```python
precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
recall = TP / (TP + FN) if (TP + FN) > 0 else 0.0
f1_score = 2 * (precision * recall) / (precision + recall)
```

### Scenario Type Inference

```python
def _infer_scenario_type(scenario_name: str) -> str:
    if any(marker in scenario_lower for marker in ["suspicious", "casing", "loiter"]):
        return "suspicious"
    if any(marker in scenario_lower for marker in ["threat", "break", "intrude"]):
        return "threats"
    return "normal"
```

## Consequences

### Positive

1. **Automated Quality Gates:**

   - CI/CD can fail builds if gap rate > 20%
   - Prevents regressions in risk scoring accuracy

2. **Detailed Diagnostics:**

   - Per-class metrics identify specific detection issues
   - Scenario-type breakdown shows which categories need improvement
   - Confidence analysis reveals model certainty patterns

3. **Continuous Improvement:**

   - Track metrics over time to measure improvements
   - A/B test prompt changes with quantitative metrics
   - Validate model updates before deployment

4. **Documentation:**
   - Comprehensive guide for expanding validation coverage
   - Clear troubleshooting steps
   - Best practices for synthetic scenario generation

### Negative

1. **Database Dependency:**

   - Tests require database with processed scenarios
   - Can't run in pure unit test mode
   - Mitigated by: Clear fixtures, good error messages

2. **Synthetic Data Quality:**

   - Results depend on quality of synthetic scenarios
   - Some scenarios may be miscategorized
   - Mitigated by: Lenient category checks, clear reporting

3. **Processing Time:**
   - Processing all scenarios takes time
   - Running validation suite is slower than unit tests
   - Mitigated by: Can run on subset of scenarios, parallel processing

## Testing

### Running Tests

```bash
# Run all validation tests
uv run pytest backend/tests/integration/test_risk_score_validation.py -v

# Run specific test
uv run pytest backend/tests/integration/test_risk_score_validation.py::TestRiskScoreValidation::test_gap_rate_below_threshold -v

# Run without database (only fixture tests)
uv run pytest backend/tests/integration/test_risk_score_validation.py::TestRiskScoreValidation::test_load_synthetic_scenarios -v
```

### Expected Output

```
================================================================================
RISK SCORE VALIDATION REPORT
================================================================================
Total Scenarios: 150
Scenarios with Gaps: 12
Overall Gap Rate: 8.0%
Threshold: 20.0%

Per-Category Gap Rates:
--------------------------------------------------------------------------------
  normal      :   2/ 80 (  2.5%)
  suspicious  :   7/ 50 ( 14.0%)
  threats     :   3/ 20 ( 15.0%)

Top 10 Largest Gaps:
--------------------------------------------------------------------------------
  prowling_20260125_180257                 | Expected: [35, 60] | Actual:  75 | Gap:  15
  ...
================================================================================
```

## Future Enhancements

1. **Temporal Analysis:**

   - Track gap rate trends over time
   - Alert on significant regressions
   - Visualize improvements in dashboard

2. **Confidence Calibration:**

   - Compare predicted vs actual risk levels
   - Measure calibration error
   - Identify overconfident/underconfident predictions

3. **Scenario Generation Automation:**

   - Auto-generate scenarios from production events
   - Create edge cases based on historical failures
   - Expand coverage systematically

4. **Integration with CI/CD:**
   - Automated scenario processing on PR
   - Comment PR with validation results
   - Block merge if gap rate exceeds threshold

## References

- [Testing Guide](../development/testing.md)
- [Detection Validation Coverage Guide](../guides/detection-validation-coverage.md)
- [Video Analytics Guide](../guides/video-analytics.md)
- [Test Suite Source](../../backend/tests/integration/test_risk_score_validation.py)
- Linear Issues: NEM-4533, NEM-4529, NEM-4527

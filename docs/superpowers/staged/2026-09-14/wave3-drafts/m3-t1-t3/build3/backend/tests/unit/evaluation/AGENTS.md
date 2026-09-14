# Unit Tests for Backend Evaluation

## Purpose

This directory contains unit tests for the `backend/evaluation/` module, which provides infrastructure for evaluating and comparing prompt performance through automated testing with mock scenarios, metrics calculation, and report generation.

## Key Files

| File              | Tests For                                          | Test Count |
| ----------------- | -------------------------------------------------- | ---------- |
| `test_harness.py` | `PromptEvaluator`, `PromptTemplate`, scenario gen  | ~30        |
| `test_metrics.py` | Metric calculations, aggregation, template ranking | ~25        |
| `test_reports.py` | JSON/HTML report generation, summary tables        | ~20        |

## Dependencies

These tests require pandas:

```python
pd = pytest.importorskip("pandas", reason="pandas required for evaluation tests")
```

## Test Patterns

### PromptTemplate Tests (`test_harness.py`)

Tests verify prompt template dataclass creation:

```python
def test_prompt_template_creation():
    """PromptTemplate should be creatable with all required fields."""
    template = PromptTemplate(
        name="test",
        description="Test template",
        template_key="TEST_PROMPT",
        enrichment_required="none",
    )
    assert template.name == "test"
    assert template.enrichment_required == "none"
```

### EvaluationResult Tests (`test_harness.py`)

Tests verify result dataclass defaults and field storage:

```python
def test_evaluation_result_defaults():
    """EvaluationResult should have sensible defaults."""
    result = EvaluationResult(
        scenario_id="test_001",
        template_name="basic",
        scenario_type="normal",
        enrichment_level="none",
    )
    assert result.risk_score == 0
    assert result.success is True
    assert result.error_message == ""
```

### Mock Scenario Generation Tests (`test_harness.py`)

Tests verify scenario generator output:

```python
def test_generates_requested_count():
    """Should generate the requested number of scenarios."""
    scenarios = generate_mock_scenarios(10)
    assert len(scenarios) == 10

def test_ground_truth_ranges_match_scenario_types():
    """Ground truth ranges should match scenario types."""
    scenarios = generate_mock_scenarios(40)

    expected_ranges = {
        "normal": (0, 25),
        "suspicious": (30, 55),
        "threat": (70, 100),
        "edge_case": (20, 60),
    }

    for _, row in scenarios.iterrows():
        expected = expected_ranges[row["scenario_type"]]
        assert row["ground_truth_range"] == expected
```

### Metric Calculation Tests (`test_metrics.py`)

Tests verify risk deviation and similarity calculations:

```python
def test_score_within_range_returns_zero():
    """Score within expected range should return 0."""
    assert calculate_risk_deviation(50, (40, 60)) == 0.0
    assert calculate_risk_deviation(40, (40, 60)) == 0.0  # At lower bound

def test_reasoning_similarity():
    """Partial overlap should return appropriate similarity."""
    # Jaccard similarity: shared / union
    sim = calculate_reasoning_similarity(
        "unknown person at door",
        "unknown person at front door"
    )
    assert sim == pytest.approx(0.8)  # 4/5 overlap
```

### Key Point Coverage Tests (`test_metrics.py`)

Tests verify coverage calculation:

```python
def test_all_key_points_covered():
    """All key points mentioned should return 1.0."""
    reasoning = "Unknown person detected at night near the front door"
    key_points = ["unknown person", "night", "front door"]
    assert calculate_key_point_coverage(reasoning, key_points) == 1.0

def test_empty_key_points_returns_one():
    """Empty key points list should return 1.0 (vacuously true)."""
    assert calculate_key_point_coverage("any reasoning", []) == 1.0
```

### Template Ranking Tests (`test_metrics.py`)

Tests verify template comparison and ranking:

```python
def test_templates_ranked_by_composite_score():
    """Templates should be ranked by composite score (higher is better)."""
    metrics = {
        "by_template": {
            "template_a": {
                "mean_risk_deviation": 0.0,  # Perfect
                "mean_key_point_coverage": 1.0,
                "mean_reasoning_similarity": 1.0,
            },
            "template_b": {
                "mean_risk_deviation": 50.0,  # Poor
                "mean_key_point_coverage": 0.5,
                "mean_reasoning_similarity": 0.5,
            },
        }
    }
    rankings = rank_templates(metrics)

    assert rankings[0]["template_name"] == "template_a"
    assert rankings[0]["rank"] == 1
```

### Report Generation Tests (`test_reports.py`)

Tests verify report structure and content:

```python
def test_generates_valid_html():
    """Should generate valid HTML structure."""
    html = generate_html_report(sample_results, sample_metrics)

    assert html.startswith("<!DOCTYPE html>")
    assert "<html" in html
    assert "</html>" in html

def test_escapes_html_in_content():
    """Should escape HTML special characters in content."""
    sample_results.loc[0, "reasoning"] = "<script>alert('xss')</script>"
    html = generate_html_report(sample_results, sample_metrics)

    assert "<script>alert" not in html
```

### Async Evaluation Tests (`test_harness.py`)

Tests verify async evaluation flow:

```python
@pytest.mark.asyncio
async def test_evaluate_all_mock_mode():
    """Evaluate all should process all scenarios and templates."""
    evaluator = PromptEvaluator(mock_mode=True)
    scenarios = generate_mock_scenarios(5)
    templates = [template_basic, template_enriched]

    results_df = await evaluator.evaluate_all(scenarios, templates=templates)

    # 5 scenarios * 2 templates = 10 results
    assert len(results_df) == 10
```

## Running Tests

```bash
# Run all evaluation unit tests
uv run pytest backend/tests/unit/evaluation/ -v

# Run specific test file
uv run pytest backend/tests/unit/evaluation/test_metrics.py -v

# Skip if pandas not available
uv run pytest backend/tests/unit/evaluation/ -v --ignore-glob="**/test_*.py" || true
```

## Test Coverage Areas

### Harness Module

- Template creation and validation
- Scenario generation with correct distributions
- Mock response generation
- LLM response parsing (including `<think>` blocks)
- Async evaluation orchestration
- Progress callback handling

### Metrics Module

- Risk deviation calculation
- Tokenization for similarity
- Jaccard similarity (reasoning)
- Key point coverage
- Aggregate metrics by template/scenario type
- Template ranking by composite score

### Reports Module

- JSON report structure
- HTML report generation with escaping
- Summary table formatting
- File save with directory creation
- Format validation errors

## Related Documentation

| Path                            | Purpose                             |
| ------------------------------- | ----------------------------------- |
| `/backend/evaluation/AGENTS.md` | Evaluation module documentation     |
| `/backend/tests/AGENTS.md`      | Test infrastructure overview        |
| `/docs/development/testing.md`  | Testing patterns and best practices |

# Unit Tests for Backend Config

## Purpose

This directory contains unit tests for the `backend/config/` module, which provides A/B testing experiments, prompt version management, shadow mode deployment, and phased rollout configurations.

## Key Files

| File                             | Tests For                              | Test Count |
| -------------------------------- | -------------------------------------- | ---------- |
| `test_prompt_experiment.py`      | `PromptExperimentConfig` class         | ~15        |
| `test_prompt_ab_rollout.py`      | `ABRolloutManager` and related classes | ~25        |
| `test_ab_rollout_production.py`  | Production A/B test configuration      | ~12        |
| `test_ab_rollout_lifecycle.py`   | Experiment lifecycle transitions       | ~10        |
| `test_shadow_mode_deployment.py` | Shadow mode comparison infrastructure  | ~20        |

## Test Patterns

### Singleton Reset Pattern

Tests use `autouse` fixtures to reset module-level singletons:

```python
@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons before each test."""
    reset_prompt_experiment_config()
    reset_rollout_manager()
    reset_shadow_mode_deployment_config()
    yield
    reset_prompt_experiment_config()
    reset_rollout_manager()
    reset_shadow_mode_deployment_config()
```

### Configuration Validation Tests

Tests verify dataclass `__post_init__` validation:

```python
def test_invalid_treatment_percentage():
    """treatment_percentage must be 0.0-1.0."""
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        ABRolloutConfig(treatment_percentage=1.5)

def test_invalid_test_duration():
    """test_duration_hours must be positive."""
    with pytest.raises(ValueError, match="must be positive"):
        ABRolloutConfig(test_duration_hours=-1)
```

### Hash-Based Assignment Tests

Tests verify consistent camera-to-group assignment:

```python
def test_camera_assignment_consistency():
    """Same camera always gets same group."""
    config = PromptExperimentConfig(treatment_percentage=0.5)

    # Multiple calls should return same version
    v1 = config.get_version_for_camera("front_door")
    v2 = config.get_version_for_camera("front_door")
    assert v1 == v2

def test_treatment_percentage_distribution():
    """50% treatment should give ~50% cameras to treatment."""
    config = PromptExperimentConfig(treatment_percentage=0.5)

    treatment_count = sum(
        1 for i in range(1000)
        if config.get_version_for_camera(f"cam_{i}") == PromptVersion.V2_CALIBRATED
    )
    assert 400 < treatment_count < 600  # Allow variance
```

### Rollback Condition Tests

Tests verify auto-rollback trigger conditions:

```python
def test_rollback_on_fp_rate_increase():
    """Rollback triggers when FP rate exceeds threshold."""
    manager = ABRolloutManager(
        ABRolloutConfig(),
        AutoRollbackConfig(max_fp_rate_increase=0.05, min_samples=10),
    )
    manager.start()

    # Control: 10% FP rate
    for _ in range(10):
        manager.record_control_feedback(is_false_positive=(i < 1))

    # Treatment: 20% FP rate (10% increase > 5% threshold)
    for i in range(10):
        manager.record_treatment_feedback(is_false_positive=(i < 2))

    result = manager.check_rollback_needed()
    assert result.should_rollback
    assert "FP rate" in result.reason
```

### Shadow Mode Comparison Tests

Tests verify shadow mode metrics tracking:

```python
def test_shadow_mode_stats_tracking():
    """Stats tracker aggregates comparison results."""
    tracker = ShadowModeStatsTracker()

    result = ShadowModeComparisonResult(
        control_risk_score=50,
        treatment_risk_score=40,
        control_latency_ms=100.0,
        treatment_latency_ms=120.0,
        risk_score_diff=10,
        latency_diff_ms=20.0,
        latency_increase_pct=20.0,
        latency_warning_triggered=False,
        timestamp="2024-01-15T10:30:00Z",
    )
    tracker.record(result)

    stats = tracker.get_stats()
    assert stats.total_comparisons == 1
    assert stats.lower_count == 1  # treatment was lower
```

## Running Tests

```bash
# Run all config unit tests
uv run pytest backend/tests/unit/config/ -v

# Run specific test file
uv run pytest backend/tests/unit/config/test_prompt_ab_rollout.py -v

# Run with coverage
uv run pytest backend/tests/unit/config/ --cov=backend.config --cov-report=term-missing
```

## Test Categories

### Validation Tests

- Configuration dataclass validation
- Parameter boundary checking
- Type validation

### Behavior Tests

- Experiment lifecycle (start/stop/expire)
- Group assignment consistency
- Metrics recording and aggregation

### Rollback Tests

- FP rate threshold checking
- Latency threshold checking
- Error rate threshold checking
- Minimum samples requirement

### Serialization Tests

- `to_dict()` / `from_dict()` round-trip
- ISO timestamp handling

## Related Documentation

| Path                           | Purpose                             |
| ------------------------------ | ----------------------------------- |
| `/backend/config/AGENTS.md`    | Config module documentation         |
| `/backend/tests/AGENTS.md`     | Test infrastructure overview        |
| `/docs/development/testing.md` | Testing patterns and best practices |

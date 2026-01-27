# Backend Config Directory

## Purpose

This directory contains configuration modules for A/B testing experiments, prompt version management, shadow mode deployment, and phased rollout strategies. These configurations enable safe, measured deployment of new AI prompt versions with automatic rollback capabilities.

## Key Files

| File                        | Purpose                                                                    |
| --------------------------- | -------------------------------------------------------------------------- |
| `__init__.py`               | Package exports for all configuration classes and functions                |
| `prompt_experiment.py`      | Core experiment configuration with version assignment                      |
| `prompt_ab_rollout.py`      | A/B rollout manager with metrics collection and auto-rollback              |
| `ab_rollout_production.py`  | Production-specific A/B test configuration (50/50, 48 hours)               |
| `shadow_mode_deployment.py` | Shadow mode configuration for parallel prompt execution                    |
| `prompt_ab_config.py`       | Prompt A/B experiment configuration with predefined experiments (NEM-3731) |

## Architecture

### Experiment Flow

```
1. Shadow Mode          2. A/B Testing           3. Full Rollout
   ├── Run v1 + v2         ├── Hash-based split     ├── treatment=1.0
   ├── Use v1 results      ├── Collect metrics      └── All cameras on v2
   └── Log v2 for compare  └── Auto-rollback if bad
```

### Key Classes

**`PromptExperimentConfig`** (`prompt_experiment.py`):

- Controls shadow mode vs A/B test mode
- Hash-based camera assignment for consistent experiences
- Auto-rollback thresholds (latency, FP rate)

**`ABRolloutManager`** (`prompt_ab_rollout.py`):

- Manages experiment lifecycle (start/stop)
- Tracks per-group metrics (control vs treatment)
- Automatic rollback condition checking
- Singleton pattern via `get_rollout_manager()`

**`ShadowModeDeploymentConfig`** (`shadow_mode_deployment.py`):

- Parallel execution of both prompts
- Control result used, treatment logged
- Latency warning threshold detection
- Rolling statistics via `ShadowModeStatsTracker`

**`PromptExperiment`** (`prompt_ab_config.py`):

- Defines prompt A/B experiments with control/variant keys
- Configurable traffic split (default 10% to variant)
- Predefined experiments: `rubric_vs_current`, `cot_vs_current`
- Integration with statistical analysis via `ab_experiment_runner.py`

## Patterns Used

### Module-Level Singletons

Each configuration module uses a singleton pattern with getter/reset functions:

```python
# Access global config
config = get_prompt_experiment_config()
manager = get_rollout_manager()

# Reset for testing
reset_prompt_experiment_config()
reset_rollout_manager()
```

### Hash-Based Assignment

Cameras are consistently assigned to experiment groups using hash-based assignment:

```python
def get_version_for_camera(camera_id: str) -> PromptVersion:
    hash_val = hash(camera_id) % 100
    if hash_val < self.treatment_percentage * 100:
        return PromptVersion.V2_CALIBRATED
    return PromptVersion.V1_ORIGINAL
```

### Auto-Rollback Thresholds

Automatic rollback triggers when treatment degrades beyond thresholds:

| Metric      | Default Threshold | Configuration Key          |
| ----------- | ----------------- | -------------------------- |
| FP Rate     | +5%               | `max_fp_rate_increase`     |
| Latency     | +50%              | `max_latency_increase_pct` |
| Error Rate  | +5%               | `max_error_rate_increase`  |
| Min Samples | 100               | `min_samples`              |

## Usage Examples

### Start Production A/B Test

```python
from backend.config import start_production_ab_rollout, get_experiment_status

# Start 48-hour, 50/50 A/B test
manager = start_production_ab_rollout()

# Check status
status = get_experiment_status()
print(f"Active: {status['is_active']}, Remaining: {status['remaining_hours']}h")
```

### Record Metrics

```python
from backend.config import get_production_rollout_manager

manager = get_production_rollout_manager()
if manager:
    # Record analysis metrics
    manager.record_treatment_analysis(latency_ms=150.0, risk_score=45)

    # Record user feedback
    manager.record_treatment_feedback(is_false_positive=False)

    # Check rollback conditions
    result = manager.check_rollback_needed()
    if result.should_rollback:
        manager.stop()
```

### Shadow Mode Comparison

```python
from backend.config import (
    get_shadow_mode_deployment_config,
    record_and_track_shadow_comparison,
    ShadowModeComparisonResult,
)

config = get_shadow_mode_deployment_config()

# Record comparison result
result = ShadowModeComparisonResult(
    control_risk_score=45,
    treatment_risk_score=38,
    control_latency_ms=100.0,
    treatment_latency_ms=120.0,
    risk_score_diff=7,
    latency_diff_ms=20.0,
    latency_increase_pct=20.0,
    latency_warning_triggered=False,
    timestamp="2024-01-15T10:30:00Z",
    camera_id="front_door",
)
record_and_track_shadow_comparison(result)
```

## Related Documentation

| Path                          | Purpose                       |
| ----------------------------- | ----------------------------- |
| `/backend/AGENTS.md`          | Backend architecture overview |
| `/backend/services/AGENTS.md` | Service layer documentation   |
| `/backend/core/AGENTS.md`     | Core infrastructure           |

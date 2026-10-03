# A/B Test Configuration Example

This example shows how to set up and run A/B experiments comparing different prompt versions.

## Defining an Experiment

```python
from backend.config.prompt_ab_config import PromptExperiment

# Create a new experiment
experiment = PromptExperiment(
    name="rubric_vs_baseline",
    description="Compare rubric-based scoring against calibrated baseline",
    control_prompt_key="calibrated_system",    # Current production prompt
    variant_prompt_key="rubric_enhanced",      # New prompt to test
    traffic_split=0.1,                         # 10% to variant
    eval_dataset_path="data/synthetic",
    metrics=[
        "json_parse_success_rate",
        "score_in_range_accuracy",
        "level_match_accuracy",
        "response_latency_ms",
    ],
    enabled=True,
)
```

## Traffic Split Options

| Split | Use Case                                       |
| ----- | ---------------------------------------------- |
| 0.01  | Initial validation, minimal risk               |
| 0.05  | Early testing with larger sample               |
| 0.10  | Standard A/B test (recommended starting point) |
| 0.25  | Confident testing, faster convergence          |
| 0.50  | Equal split for final comparison               |

## Using Predefined Experiments

```python
from backend.config.prompt_ab_config import (
    get_experiment,
    list_experiments,
    get_enabled_experiments,
)

# List all available experiments
print("Available experiments:", list_experiments())
# Output: ['rubric_vs_current', 'cot_vs_current']

# Get a specific experiment
experiment = get_experiment("rubric_vs_current")
print(f"Testing: {experiment.control_prompt_key} vs {experiment.variant_prompt_key}")
print(f"Traffic to variant: {experiment.traffic_split:.0%}")

# Get all enabled experiments
for exp in get_enabled_experiments():
    print(f"Active: {exp.name}")
```

## Shadow Mode Testing

For high-stakes changes, run both prompts and compare without affecting production:

```python
async def shadow_test(sample, experiment):
    """Run both prompts and compare without affecting output."""
    # Always use control for actual response
    control_response = await run_analysis(sample, experiment.control_prompt_key)

    # Run variant in background (shadow)
    variant_response = await run_analysis(sample, experiment.variant_prompt_key)

    # Log comparison for analysis
    log_shadow_comparison(
        sample_id=sample.scenario_id,
        control_score=control_response["risk_score"],
        variant_score=variant_response["risk_score"],
        score_diff=abs(control_response["risk_score"] - variant_response["risk_score"]),
    )

    # Return only control response for actual use
    return control_response
```

## See Also

- [Basic Risk Analysis](basic-risk-analysis.md) - Control prompt example
- [Rubric-Based Prompt](rubric-based-prompt.md) - Variant prompt example
- [Main Documentation](../../developer/nemotron-prompting.md#ab-testing-framework)
- Implementation: `backend/config/prompt_ab_config.py`

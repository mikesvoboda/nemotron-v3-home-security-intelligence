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

## Selecting Variant at Runtime

```python
from backend.evaluation.ab_experiment_runner import select_variant

# Each request is randomly assigned to control or variant
prompt_key = select_variant(experiment)

# Load the appropriate prompt template
if prompt_key == "calibrated_system":
    prompt = CALIBRATED_SYSTEM_PROMPT
elif prompt_key == "rubric_enhanced":
    prompt = RUBRIC_ENHANCED_PROMPT
```

## Collecting Results

```python
import time

# Track metrics for each request
results = {
    "control": [],
    "variant": [],
}

for sample in evaluation_samples:
    # Select variant
    prompt_key = select_variant(experiment)
    is_variant = prompt_key == experiment.variant_prompt_key

    # Run analysis
    start = time.monotonic()
    response = await analyze_with_prompt(sample, prompt_key)
    latency_ms = (time.monotonic() - start) * 1000

    # Record metrics
    metrics = {
        "sample_id": sample.scenario_id,
        "latency_ms": latency_ms,
        "json_parse_success": response is not None,
        "score": response.get("risk_score") if response else None,
        "level": response.get("risk_level") if response else None,
    }

    if is_variant:
        results["variant"].append(metrics)
    else:
        results["control"].append(metrics)
```

## Statistical Analysis

```python
from backend.evaluation.ab_experiment_runner import (
    analyze_experiment,
    summarize_results,
)

# Extract accuracy scores from results
control_scores = [
    1.0 if is_score_in_range(m["score"], sample) else 0.0
    for m in results["control"]
]
variant_scores = [
    1.0 if is_score_in_range(m["score"], sample) else 0.0
    for m in results["variant"]
]

# Analyze for statistical significance
analysis = analyze_experiment(
    control_scores=control_scores,
    variant_scores=variant_scores,
    alpha=0.05,  # 95% confidence level
)

# Print summary
print(summarize_results(analysis))
```

## Example Output

```text
A/B Experiment Results (SIGNIFICANT)
=====================================
Control: mean=0.8200, std=0.0385, n=450
Variant: mean=0.8950, std=0.0307, n=50

Statistical Analysis:
- t-statistic: 4.2156
- p-value: 0.0003
- Effect size (Cohen's d): 2.1842 (large)
- Significant at alpha=0.05: True

Interpretation:
- Variant performs BETTER than control
- The difference IS statistically significant
```

## Effect Size Interpretation

Cohen's d measures practical significance:

| Range     | Interpretation                              |
| --------- | ------------------------------------------- |
| d < 0.2   | Negligible - probably not worth rolling out |
| 0.2 - 0.5 | Small - consider if low-cost change         |
| 0.5 - 0.8 | Medium - meaningful improvement             |
| d >= 0.8  | Large - strong case for rolling out         |

## Complete Workflow Example

```python
from backend.config.prompt_ab_config import PromptExperiment, get_experiment
from backend.evaluation.ab_experiment_runner import (
    select_variant,
    analyze_experiment,
    summarize_results,
)
from backend.evaluation.prompt_eval_dataset import load_synthetic_eval_dataset
from backend.evaluation.prompt_evaluator import evaluate_prediction

async def run_ab_experiment(experiment_name: str, num_samples: int = 500):
    """Run a complete A/B experiment."""
    # Get experiment config
    experiment = get_experiment(experiment_name)
    if not experiment:
        raise ValueError(f"Unknown experiment: {experiment_name}")

    # Load evaluation dataset
    samples = load_synthetic_eval_dataset()[:num_samples]

    # Collect results
    control_accuracy = []
    variant_accuracy = []

    for sample in samples:
        # Random assignment
        prompt_key = select_variant(experiment)
        is_variant = prompt_key == experiment.variant_prompt_key

        # Run analysis (simplified)
        response = await run_analysis(sample, prompt_key)

        # Evaluate accuracy
        eval_result = evaluate_prediction(
            sample=sample,
            actual_score=response["risk_score"],
            actual_level=response["risk_level"],
        )

        # Record (1.0 for correct, 0.0 for incorrect)
        accuracy = 1.0 if eval_result.is_accurate else 0.0

        if is_variant:
            variant_accuracy.append(accuracy)
        else:
            control_accuracy.append(accuracy)

    # Analyze results
    results = analyze_experiment(control_accuracy, variant_accuracy)

    print(f"\n{experiment.name} Results")
    print(f"Control ({experiment.control_prompt_key}): n={len(control_accuracy)}")
    print(f"Variant ({experiment.variant_prompt_key}): n={len(variant_accuracy)}")
    print(summarize_results(results))

    return results

# Run the experiment
results = await run_ab_experiment("rubric_vs_current", num_samples=500)

# Decision
if results.is_significant and results.effect_size > 0.5:
    print("Recommendation: Roll out variant to production")
elif results.is_significant and results.effect_size > 0:
    print("Recommendation: Continue testing with larger sample")
else:
    print("Recommendation: Keep current prompt, variant shows no improvement")
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
- [Main Documentation](../../development/nemotron-prompting.md#ab-testing-framework)
- Implementation: `backend/config/prompt_ab_config.py`
- Implementation: `backend/evaluation/ab_experiment_runner.py`

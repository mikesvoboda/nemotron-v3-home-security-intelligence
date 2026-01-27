# Nemotron Prompting Best Practices

This guide documents prompt engineering techniques and best practices for working with NVIDIA Nemotron models in the home security monitoring system.

## Table of Contents

- [Model Overview](#model-overview)
- [ChatML Prompt Format](#chatml-prompt-format)
- [Chain-of-Thought Reasoning](#chain-of-thought-reasoning)
- [Structured Output (NVIDIA NIM)](#structured-output-nvidia-nim)
- [Risk Score Calibration](#risk-score-calibration)
- [Rubric-Based Scoring](#rubric-based-scoring)
- [Threat Categories](#threat-categories)
- [Testing and Evaluation](#testing-and-evaluation)
- [A/B Testing Framework](#ab-testing-framework)

## Model Overview

### Nemotron-3-Nano-30B

The production model is NVIDIA's state-of-the-art instruction-following model optimized for reasoning tasks.

| Specification      | Value                           |
| ------------------ | ------------------------------- |
| **Model Name**     | Nemotron-3-Nano-30B-A3B         |
| **Parameters**     | 30 billion (MoE active routing) |
| **Context Window** | 131,072 tokens (128K)           |
| **Quantization**   | Q4_K_M (4-bit, medium quality)  |
| **VRAM Required**  | ~14.7 GB                        |
| **Inference Time** | 2-5 seconds per analysis        |

### Key Capabilities

- **Instruction Following**: Trained on diverse instruction-response pairs
- **Reasoning**: Built-in chain-of-thought support via `'detailed thinking on'`
- **JSON Output**: Native JSON generation with optional schema enforcement
- **Long Context**: 128K token window enables rich historical analysis

## ChatML Prompt Format

Nemotron uses ChatML format for message structuring. All prompts use these delimiters:

```text
<|im_start|>system
{system message}
<|im_end|>
<|im_start|>user
{user message}
<|im_end|>
<|im_start|>assistant
{model response begins here}
```

### Example Prompt

```python
prompt = """<|im_start|>system
You are a home security analyst for a residential property.
Output ONLY valid JSON. No preamble, no explanation.<|im_end|>
<|im_start|>user
Camera: Front Door
Time: 14:30:00 to 14:31:00

DETECTIONS:
- 14:30:05: person detected (confidence: 0.92)

Analyze the risk and output JSON with risk_score (0-100), risk_level, summary, and reasoning.<|im_end|>
<|im_start|>assistant
"""
```

### Stop Tokens

Configure stop tokens to terminate generation at ChatML boundaries:

```python
payload = {
    "prompt": prompt,
    "temperature": 0.7,
    "top_p": 0.95,
    "max_tokens": 1536,
    "stop": ["<|im_end|>", "<|im_start|>"]  # ChatML terminators
}
```

## Chain-of-Thought Reasoning

### Enabling Reasoning Mode

Nemotron models support built-in chain-of-thought reasoning. Enable it by including `'detailed thinking on'` at the start of the system prompt:

```python
SYSTEM_PROMPT_WITH_REASONING = """detailed thinking on

You are a home security analyst for a residential property.

REASONING INSTRUCTIONS:
1. First, output your reasoning in <think>...</think> tags
2. Consider: time of day, location, object types, household context
3. Evaluate each factor systematically before determining the risk score
4. After </think>, output ONLY valid JSON with no additional text

Output format after </think>:
{"risk_score": N, "risk_level": "level", "summary": "...", "reasoning": "..."}"""
```

### Model Output Format

When reasoning is enabled, the model outputs:

```text
<think>
Let me analyze this detection systematically:

1. Time: 14:30 - normal business hours
2. Location: Front door - entry point
3. Detection: Single person with high confidence (0.92)
4. Context: Daytime delivery is common at this hour

Risk factors:
- Normal hours: low risk modifier
- Single person: not a group, lower risk
- No suspicious behavior detected

Final assessment: Likely a delivery or expected visitor.
</think>
{"risk_score": 15, "risk_level": "low", "summary": "Person detected at front door during daytime", "reasoning": "Single person detection during normal business hours at front entrance. Pattern consistent with delivery or expected visitor."}
```

### Parsing Reasoning

The backend extracts reasoning using regex:

```python
from backend.services.nemotron_analyzer import extract_reasoning_and_response

text = "<think>Analyzing the scene...</think>{\"risk_score\": 25}"
reasoning, json_response = extract_reasoning_and_response(text)

# reasoning = "Analyzing the scene..."
# json_response = '{"risk_score": 25}'
```

**Implementation**: See `backend/services/nemotron_analyzer.py` - `extract_reasoning_and_response()`

## Structured Output (NVIDIA NIM)

NVIDIA NIM endpoints support guided generation parameters that enforce valid output structure.

### guided_json

Enforce a JSON schema on the output:

```python
from backend.api.schemas.llm_response import RISK_ANALYSIS_JSON_SCHEMA

# The schema defines:
# - risk_score: integer 0-100
# - risk_level: enum ["low", "medium", "high", "critical"]
# - summary: string (max 200 chars)
# - reasoning: string
# - entities: array of detected entities
# - recommended_action: enum

response = client.chat.completions.create(
    model="nemotron",
    messages=[...],
    extra_body={
        "nvext": {
            "guided_json": RISK_ANALYSIS_JSON_SCHEMA
        }
    }
)
```

**Implementation**: See `backend/api/schemas/llm_response.py` - `RISK_ANALYSIS_JSON_SCHEMA`

### guided_choice

Constrain output to a predefined set of values:

```python
from backend.services.guided_constraints import (
    RISK_LEVEL_CHOICES,       # ["low", "medium", "high", "critical"]
    RECOMMENDED_ACTION_CHOICES,  # ["none", "review_later", "review_soon", "alert_homeowner", "immediate_response"]
    ENTITY_TYPE_CHOICES,      # ["person", "vehicle", "animal", "object"]
    THREAT_LEVEL_CHOICES,     # ["low", "medium", "high"]
)

# Use in nvext namespace
config = {
    "nvext": {
        "guided_choice": RISK_LEVEL_CHOICES
    }
}
```

**Implementation**: See `backend/services/guided_constraints.py`

### guided_regex

Constrain output to match a regex pattern:

```python
from backend.services.guided_constraints import get_guided_regex_config

# Risk score: 0-100
config = get_guided_regex_config("risk_score")
# Returns: {'nvext': {'guided_regex': '[0-9]|[1-9][0-9]|100'}}

# Threat level score: 0-4
config = get_guided_regex_config("threat_level_score")
# Returns: {'nvext': {'guided_regex': '[0-4]'}}
```

### Configuration

Enable/disable guided_json via settings:

```bash
# .env
NEMOTRON_USE_GUIDED_JSON=true
NEMOTRON_GUIDED_JSON_FALLBACK=true  # Fall back to regex parsing if guided_json unsupported
```

## Risk Score Calibration

### Target Distribution

The system is calibrated to expect the following risk score distribution:

| Risk Level   | Score Range | Expected Frequency | Description                |
| ------------ | ----------- | ------------------ | -------------------------- |
| **LOW**      | 0-29        | 80%                | Normal household activity  |
| **MEDIUM**   | 30-59       | 15%                | Worth noting, not alarming |
| **HIGH**     | 60-84       | 4%                 | Genuinely suspicious       |
| **CRITICAL** | 85-100      | 1%                 | Immediate threats only     |

### Calibration Prompt

Include calibration guidance in the system prompt:

```python
CALIBRATED_SYSTEM_PROMPT = """You are a home security analyst for a residential property.

CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,
delivery workers, and pets represent normal household activity. Your job is to
identify genuine anomalies, not flag everyday life.

CALIBRATION: In a typical day, expect:
- 80% of events to be LOW risk (0-29): Normal activity
- 15% to be MEDIUM risk (30-59): Worth noting but not alarming
- 4% to be HIGH risk (60-84): Genuinely suspicious, warrants review
- 1% to be CRITICAL (85-100): Immediate threats only

If you're scoring >20% of events as HIGH or CRITICAL, you are miscalibrated.

Output ONLY valid JSON. No preamble, no explanation."""
```

**Implementation**: See `backend/services/prompts.py` - `CALIBRATED_SYSTEM_PROMPT`

### Scoring Reference Table

Provide concrete examples to anchor scoring:

```markdown
## SCORING REFERENCE

| Scenario                    | Score  | Reasoning               |
| --------------------------- | ------ | ----------------------- |
| Resident arriving home      | 5-15   | Expected activity       |
| Delivery driver at door     | 15-25  | Normal service visit    |
| Unknown person on sidewalk  | 20-35  | Public area, passive    |
| Unknown person lingering    | 45-60  | Warrants attention      |
| Person testing door handles | 70-85  | Clear suspicious intent |
| Active break-in or violence | 85-100 | Immediate threat        |
```

## Rubric-Based Scoring

For more consistent risk assessment, use explicit rubrics that the model evaluates independently.

### Scoring Formula

```text
risk_score = (threat_level * 25) + (apparent_intent * 15) + (time_context * 10)
```

Maximum theoretical score is 165, capped at 100.

### Threat Level Rubric (0-4)

| Score | Level           | Description                                                 |
| ----- | --------------- | ----------------------------------------------------------- |
| 0     | No threat       | Normal expected activity (resident, family, service worker) |
| 1     | Minimal threat  | Unusual but explainable (unknown person on public sidewalk) |
| 2     | Moderate threat | Warrants attention (lingering, repeated passes)             |
| 3     | High threat     | Clear suspicious intent (testing doors, peering in windows) |
| 4     | Critical threat | Active danger (break-in, weapon visible, violence)          |

### Apparent Intent Rubric (0-3)

| Score | Level               | Description                                   |
| ----- | ------------------- | --------------------------------------------- |
| 0     | Benign intent       | Clear legitimate purpose (delivery, visiting) |
| 1     | Unclear intent      | Cannot determine purpose                      |
| 2     | Questionable intent | Behavior suggests reconnaissance              |
| 3     | Malicious intent    | Actions indicate criminal purpose             |

### Time Context Rubric (0-2)

| Score | Level             | Description                         |
| ----- | ----------------- | ----------------------------------- |
| 0     | Normal timing     | Activity expected at this hour      |
| 1     | Unusual timing    | Activity uncommon but not alarming  |
| 2     | Suspicious timing | Activity rarely occurs at this hour |

### Rubric-Enhanced Prompt

See `backend/services/risk_rubrics.py` for the complete `RUBRIC_ENHANCED_PROMPT` that includes:

1. All rubric definitions with examples
2. Scoring formula explanation
3. Example calculations
4. Instructions to output `rubric_scores` in the JSON response

**Implementation**: See `backend/services/risk_rubrics.py`

## Threat Categories

Classify detected threats into specific categories for targeted alerting.

### Available Categories

```python
from backend.services.threat_categories import ThreatCategory

# Categories ordered by severity
ThreatCategory.VIOLENCE           # Physical violence or fighting
ThreatCategory.WEAPON_VISIBLE     # Firearm, knife, or weapon visible
ThreatCategory.CRIMINAL_PLANNING  # Evidence of planning criminal activity
ThreatCategory.THREAT_INTIMIDATION # Threatening or intimidating behavior
ThreatCategory.FRAUD_DECEPTION    # Deceptive behavior (impersonation)
ThreatCategory.ILLEGAL_ACTIVITY   # General illegal activity detected
ThreatCategory.PROPERTY_DAMAGE    # Vandalism or destruction
ThreatCategory.TRESPASSING        # Unauthorized entry or presence
ThreatCategory.THEFT_ATTEMPT      # Taking property without permission
ThreatCategory.SURVEILLANCE_CASING # Reconnaissance or casing
ThreatCategory.NONE               # No threat detected
```

### Including in Prompts

```python
from backend.services.threat_categories import get_category_prompt_section

prompt_section = get_category_prompt_section()
# Returns formatted markdown list of all categories with descriptions
```

**Implementation**: See `backend/services/threat_categories.py`

## Testing and Evaluation

### Synthetic Evaluation Data

Synthetic scenarios for testing are located in `data/synthetic/`:

```text
data/synthetic/
├── normal/           # Low-risk scenarios (80% of training)
│   ├── delivery_driver_*/
│   ├── resident_arrival_*/
│   ├── pet_activity_*/
│   └── vehicle_parking_*/
├── suspicious/       # Medium-risk scenarios (15%)
│   ├── loitering_*/
│   └── casing_*/
└── threats/          # High/critical scenarios (5%)
    ├── break_in_*/
    └── vandalism_*/
```

### Scenario Structure

Each scenario folder contains:

```text
scenario_name_timestamp/
├── expected_labels.json   # Ground truth with expected risk scores
├── scenario_spec.json     # Full scenario specification
├── metadata.json          # Generation metadata
├── generation_prompt.txt  # Prompt used for media generation
└── media/                 # Generated images/videos (optional)
    ├── 001.png
    └── 002.png
```

### Expected Labels Format

```json
{
  "detections": [{ "class": "person", "min_confidence": 0.8, "count": 1 }],
  "risk": {
    "min_score": 0,
    "max_score": 15,
    "level": "low",
    "expected_factors": []
  },
  "florence_caption": {
    "must_contain": ["person", "package"],
    "must_not_contain": ["suspicious", "threat"]
  }
}
```

### Loading Evaluation Data

```python
from backend.evaluation.prompt_eval_dataset import (
    load_synthetic_eval_dataset,
    get_samples_by_category,
    get_scenario_summary,
)

# Load all samples
samples = load_synthetic_eval_dataset()
print(f"Loaded {len(samples)} samples")

# Group by category
by_category = get_samples_by_category(samples)
for cat, cat_samples in by_category.items():
    print(f"  {cat}: {len(cat_samples)} samples")

# Get summary statistics
summary = get_scenario_summary(samples)
```

**Implementation**: See `backend/evaluation/prompt_eval_dataset.py`

### Evaluating Predictions

```python
from backend.evaluation.prompt_evaluator import (
    evaluate_prediction,
    evaluate_batch,
    calculate_metrics,
    summarize_results,
)

# Evaluate a single prediction
result = evaluate_prediction(
    sample=sample,
    actual_score=25,
    actual_level="low"
)

print(f"Score in range: {result.score_in_range}")
print(f"Level match: {result.level_match}")
print(f"Deviation: {result.deviation}")

# Batch evaluation
results = evaluate_batch(samples, predictions)
metrics = calculate_metrics(results)

print(f"Score accuracy: {metrics['accuracy']:.1%}")
print(f"Level accuracy: {metrics['level_accuracy']:.1%}")
print(f"Combined accuracy: {metrics['combined_accuracy']:.1%}")
```

**Implementation**: See `backend/evaluation/prompt_evaluator.py`

### E2E Testing with Synthetic Media

To run end-to-end tests with synthetic media:

1. Copy media files to the camera import directory:

   ```bash
   cp data/synthetic/normal/delivery_driver_*/media/* /export/foscam/synthetic_camera/
   ```

2. The detection pipeline will process the files automatically

3. Compare output events against expected labels

## A/B Testing Framework

### Experiment Configuration

Define experiments comparing prompt versions:

```python
from backend.config.prompt_ab_config import (
    PromptExperiment,
    get_experiment,
    list_experiments,
)

# Get a predefined experiment
experiment = get_experiment("rubric_vs_current")
print(f"Testing: {experiment.control_prompt_key} vs {experiment.variant_prompt_key}")
print(f"Traffic split: {experiment.traffic_split:.0%} to variant")

# Create a custom experiment
custom = PromptExperiment(
    name="cot_reasoning_test",
    description="Test chain-of-thought reasoning impact",
    control_prompt_key="calibrated_system",
    variant_prompt_key="reasoning_enabled",
    traffic_split=0.1,  # 10% to variant
    metrics=[
        "json_parse_success_rate",
        "score_in_range_accuracy",
        "level_match_accuracy",
        "response_latency_ms",
    ]
)
```

**Implementation**: See `backend/config/prompt_ab_config.py`

### Running Experiments

```python
from backend.evaluation.ab_experiment_runner import (
    select_variant,
    analyze_experiment,
    summarize_results,
)

# Select variant for a request
prompt_key = select_variant(experiment)

# After collecting data, analyze results
results = analyze_experiment(
    control_scores=[0.82, 0.85, 0.79, 0.88, 0.83],
    variant_scores=[0.91, 0.89, 0.93, 0.87, 0.92],
    alpha=0.05  # Significance level
)

# Check statistical significance
if results.is_significant:
    print(f"Significant! p-value: {results.p_value:.4f}")
    print(f"Effect size (Cohen's d): {results.effect_size:.2f}")

# Generate summary
print(summarize_results(results))
```

**Implementation**: See `backend/evaluation/ab_experiment_runner.py`

### Predefined Experiments

| Experiment Name     | Control           | Variant           | Description                        |
| ------------------- | ----------------- | ----------------- | ---------------------------------- |
| `rubric_vs_current` | calibrated_system | rubric_enhanced   | Compare rubric-based scoring       |
| `cot_vs_current`    | calibrated_system | reasoning_enabled | Compare chain-of-thought reasoning |

## Reference Files

| File                                         | Purpose                                |
| -------------------------------------------- | -------------------------------------- |
| `backend/services/nemotron_analyzer.py`      | Main analyzer with guided_json support |
| `backend/services/prompts.py`                | Prompt templates and formatting        |
| `backend/services/risk_rubrics.py`           | Rubric definitions and scoring         |
| `backend/services/threat_categories.py`      | Threat category enum and descriptions  |
| `backend/services/guided_constraints.py`     | Choice and regex constraints           |
| `backend/api/schemas/llm_response.py`        | JSON schema for risk analysis          |
| `backend/config/prompt_ab_config.py`         | A/B testing configuration              |
| `backend/evaluation/prompt_evaluator.py`     | Evaluation metrics                     |
| `backend/evaluation/ab_experiment_runner.py` | A/B experiment runner                  |
| `backend/evaluation/prompt_eval_dataset.py`  | Synthetic dataset loading              |
| `data/synthetic/`                            | Synthetic scenario files               |

## External Resources

- [NVIDIA Nemotron-3-Nano-30B on HuggingFace](https://huggingface.co/nvidia/Nemotron-3-Nano-30B-A3B-GGUF)
- [NVIDIA NIM Documentation](https://docs.nvidia.com/nim/)
- [NVIDIA NIM Guided Generation](https://docs.nvidia.com/nim/large-language-models/latest/structured-output.html)
- [llama.cpp Server Documentation](https://github.com/ggerganov/llama.cpp/tree/master/examples/server)

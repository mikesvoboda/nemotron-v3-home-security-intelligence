# Rubric-Based Scoring Prompt Example

This example demonstrates explicit rubric-based scoring for consistent, reproducible risk assessments.

## The Scoring Formula

```text
risk_score = (threat_level * 25) + (apparent_intent * 15) + (time_context * 10)
```

Maximum theoretical score is 165, capped at 100.

## Complete Prompt Template

```python
from backend.services.risk_rubrics import RUBRIC_ENHANCED_PROMPT

# RUBRIC_ENHANCED_PROMPT includes:
# 1. System prompt with calibration
# 2. Full rubric definitions
# 3. Scoring examples table
# 4. Instructions to output rubric_scores

prompt = RUBRIC_ENHANCED_PROMPT.format(
    camera_name="Front Door",
    start_time="14:30:00",
    end_time="14:31:00",
    detections_list="""- 14:30:05: person detected (confidence: 0.92)
- 14:30:12: person detected (confidence: 0.89)
- 14:30:20: person detected (confidence: 0.91)"""
)
```

## Rubric Definitions

### Threat Level (0-4, weight: 25)

| Score | Level           | Description                                                 |
| ----- | --------------- | ----------------------------------------------------------- |
| 0     | No threat       | Normal expected activity (resident, family, service worker) |
| 1     | Minimal threat  | Unusual but explainable (unknown person on public sidewalk) |
| 2     | Moderate threat | Warrants attention (lingering, repeated passes)             |
| 3     | High threat     | Clear suspicious intent (testing doors, peering in windows) |
| 4     | Critical threat | Active danger (break-in, weapon visible, violence)          |

### Apparent Intent (0-3, weight: 15)

| Score | Level               | Description                                   |
| ----- | ------------------- | --------------------------------------------- |
| 0     | Benign intent       | Clear legitimate purpose (delivery, visiting) |
| 1     | Unclear intent      | Cannot determine purpose                      |
| 2     | Questionable intent | Behavior suggests reconnaissance              |
| 3     | Malicious intent    | Actions indicate criminal purpose             |

### Time Context (0-2, weight: 10)

| Score | Level             | Description                         |
| ----- | ----------------- | ----------------------------------- |
| 0     | Normal timing     | Activity expected at this hour      |
| 1     | Unusual timing    | Activity uncommon but not alarming  |
| 2     | Suspicious timing | Activity rarely occurs at this hour |

## Scoring Examples

| Scenario                         | Threat | Intent | Time | Score | Level    |
| -------------------------------- | ------ | ------ | ---- | ----- | -------- |
| Resident arriving home           | 0      | 0      | 0    | 0     | LOW      |
| Delivery driver at door          | 0      | 0      | 0    | 0     | LOW      |
| Unknown person on sidewalk       | 1      | 1      | 0    | 40    | MEDIUM   |
| Unknown person lingering (night) | 2      | 2      | 2    | 90    | CRITICAL |
| Person testing door handles      | 3      | 3      | 0    | 100   | CRITICAL |
| Active break-in                  | 4      | 3      | 2    | 100   | CRITICAL |

## Expected Response Format

```json
{
  "risk_score": 25,
  "risk_level": "low",
  "summary": "Person detected at front door during business hours, likely delivery.",
  "reasoning": "Single person with high confidence detections at entry point during normal hours. Behavior pattern consistent with delivery or expected visitor.",
  "rubric_scores": {
    "threat_level": 1,
    "apparent_intent": 0,
    "time_context": 0
  }
}
```

## Score Calculation Example

For "Unknown person lingering at night":

```text
threat_level = 2 (Moderate threat - warrants attention)
apparent_intent = 2 (Questionable - behavior suggests reconnaissance)
time_context = 2 (Suspicious timing - late night)

risk_score = (2 * 25) + (2 * 15) + (2 * 10)
           = 50 + 30 + 20
           = 100 (capped from theoretical 100)

risk_level = "critical" (85-100 range)
```

## Python Implementation

```python
from backend.services.risk_rubrics import (
    calculate_risk_score,
    RubricScores,
    RUBRIC_ENHANCED_PROMPT,
)

# Calculate score from rubric values
def get_risk_score(threat: int, intent: int, time: int) -> int:
    """Calculate risk score from rubric dimensions."""
    return calculate_risk_score(threat, intent, time)

# Validate rubric scores from LLM response
def validate_rubric_response(response: dict) -> RubricScores:
    """Validate and normalize rubric scores."""
    rubric_data = response.get("rubric_scores", {})
    return RubricScores(
        threat_level=rubric_data.get("threat_level", 0),
        apparent_intent=rubric_data.get("apparent_intent", 0),
        time_context=rubric_data.get("time_context", 0),
    )

# Verify LLM calculated correctly
def verify_calculation(response: dict) -> bool:
    """Check if LLM's risk_score matches rubric calculation."""
    rubric = validate_rubric_response(response)
    expected = calculate_risk_score(
        rubric.threat_level,
        rubric.apparent_intent,
        rubric.time_context,
    )
    return response.get("risk_score") == expected
```

## Benefits of Rubric-Based Scoring

1. **Reproducibility**: Same inputs should yield same outputs
2. **Transparency**: Each dimension is scored independently
3. **Debuggability**: Can identify which factor drove the score
4. **Calibration**: Easier to adjust weights and thresholds
5. **Auditability**: Clear reasoning chain for compliance

## When to Use

- Production risk assessments requiring consistency
- Compliance/audit scenarios requiring explainability
- A/B testing prompt variants
- Training data collection with ground truth

## See Also

- [Basic Risk Analysis](basic-risk-analysis.md) - Simpler prompt without rubrics
- [Chain-of-Thought Example](chain-of-thought.md) - Add reasoning transparency
- [Main Documentation](../../development/nemotron-prompting.md)
- Implementation: `backend/services/risk_rubrics.py`

# Chain-of-Thought Reasoning Example

This example demonstrates how to enable and use Nemotron's built-in chain-of-thought reasoning for transparent risk assessment.

## Enabling Reasoning Mode

Include `'detailed thinking on'` at the start of the system prompt:

```python
SYSTEM_PROMPT_WITH_REASONING = """detailed thinking on

You are a home security analyst for a residential property.

CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,
delivery workers, and pets represent normal household activity. Your job is to
identify genuine anomalies, not flag everyday life.

CALIBRATION: In a typical day, expect:
- 80% of events to be LOW risk (0-29): Normal activity
- 15% to be MEDIUM risk (30-59): Worth noting but not alarming
- 4% to be HIGH risk (60-84): Genuinely suspicious, warrants review
- 1% to be CRITICAL (85-100): Immediate threats only

REASONING INSTRUCTIONS:
1. First, output your reasoning in <think>...</think> tags
2. Consider: time of day, location, object types, household context
3. Evaluate each factor systematically before determining the risk score
4. After </think>, output ONLY valid JSON with no additional text

Output format after </think>:
{"risk_score": N, "risk_level": "level", "summary": "...", "reasoning": "..."}"""
```

## Complete Prompt Example

```python
prompt = f"""<|im_start|>system
{SYSTEM_PROMPT_WITH_REASONING}<|im_end|>
<|im_start|>user
## EVENT CONTEXT
Camera: Front Door
Time: 23:42:00 to 23:43:00

## DETECTIONS
- 23:42:05: person detected (confidence: 0.88)
- 23:42:12: person detected (confidence: 0.85)
- 23:42:30: person detected (confidence: 0.87)
- 23:42:45: person detected (confidence: 0.86)

## CONTEXT
- No face match in household database
- Time is outside normal hours (typically 7 AM - 10 PM)
- Person appears to be approaching the door

## YOUR TASK
Analyze this detection systematically. First show your reasoning in <think>...</think> tags,
then output the final JSON assessment.<|im_end|>
<|im_start|>assistant
"""
```

## Expected Model Output

```text
<think>
Let me analyze this detection systematically:

1. TIME ANALYSIS
   - 23:42 (11:42 PM) - Late evening, outside typical household activity hours
   - Normal activity window is 7 AM - 10 PM
   - Late-night activity warrants elevated attention

2. LOCATION ANALYSIS
   - Front door camera - primary entry point
   - High-security zone requiring careful assessment
   - Multiple consecutive detections suggest sustained presence

3. PERSON ANALYSIS
   - No face match found in household database
   - Unknown individual at late hour
   - Confidence scores are consistent (0.85-0.88)
   - Not a fleeting detection - person present for ~40 seconds

4. BEHAVIORAL PATTERNS
   - 4 detections over 40 seconds indicates lingering
   - Approaching the door at this hour is unusual
   - No obvious legitimate purpose (delivery unlikely at this hour)

5. RISK FACTORS
   + Late hour: +15 points
   + Unknown person: +20 points
   + Lingering behavior: +10 points
   + Front door (entry point): +5 points
   - High confidence detections: neutral
   - No threatening items visible: -5 points

6. CALIBRATION CHECK
   - This scenario has multiple concerning factors
   - Unknown person + late hour + lingering = elevated risk
   - But no active threat indicators (no weapon, no forced entry attempt)
   - Should be MEDIUM-HIGH, not CRITICAL

7. FINAL ASSESSMENT
   Score: 50 + 5 = 55 (MEDIUM range: 30-59)
   This warrants review but is not an immediate emergency.
</think>
{"risk_score": 55, "risk_level": "medium", "summary": "Unknown person detected at front door late at night, lingering for approximately 40 seconds without entering.", "reasoning": "Person detected at 11:42 PM outside normal hours with no face match. Multiple detections over 40 seconds indicate sustained presence. Late hour and unknown identity are concerning, but no active threat indicators present. Warrants prompt review."}
```

## Parsing the Response

```python
from backend.services.nemotron_analyzer import extract_reasoning_and_response
import json

# Parse the raw output
raw_output = response["content"]
reasoning, json_response = extract_reasoning_and_response(raw_output)

# reasoning contains the <think> content
print("Model reasoning:")
print(reasoning)

# json_response contains the JSON
risk_data = json.loads(json_response)
print(f"Risk score: {risk_data['risk_score']}")
print(f"Risk level: {risk_data['risk_level']}")
```

## Storing Reasoning for Audit

```python
from backend.api.schemas.llm_response import LLMResponseWithReasoning

# Create response object with reasoning preserved
response_with_cot = LLMResponseWithReasoning(
    risk_score=risk_data["risk_score"],
    risk_level=risk_data["risk_level"],
    summary=risk_data["summary"],
    reasoning=risk_data["reasoning"],
    chain_of_thought=reasoning,  # Preserve the <think> content
)

# The chain_of_thought field can be:
# - Stored in database for audit trails
# - Logged for debugging
# - Used for model improvement analysis
# - Displayed in admin interface for review
```

## Benefits of Chain-of-Thought

### 1. Debugging

When the model produces unexpected scores, the reasoning reveals why:

```text
# Why did this get scored HIGH?
<think>
...
5. RISK FACTORS
   + Unknown vehicle parked for 2 hours: +30 points
   + Same vehicle seen 3 times this week: +20 points
   + Driver never exits vehicle: +15 points
...
</think>
```

### 2. Auditing

Compliance requirements often need decision justification:

```python
# Store for compliance audit
audit_log = {
    "event_id": event.id,
    "timestamp": datetime.utcnow(),
    "risk_score": response.risk_score,
    "model_reasoning": response.chain_of_thought,
    "final_summary": response.summary,
}
```

### 3. Model Improvement

Identify miscalibration patterns:

```python
# Find cases where reasoning mentions "delivery" but scored HIGH
miscalibrated = [
    r for r in results
    if "delivery" in r.chain_of_thought.lower()
    and r.risk_score > 60
]
```

### 4. User Trust

Show homeowners why alerts triggered:

```text
Alert: Medium Risk Activity Detected

Summary: Unknown person at front door at 11:42 PM

Why this was flagged:
- Time: 11:42 PM (outside normal hours)
- Person: Not recognized by face detection
- Behavior: Lingered for 40 seconds
- Location: Front door (entry point)

This appears to warrant review but is not an immediate emergency.
```

## Performance Considerations

Chain-of-thought reasoning increases output length:

- Without CoT: ~100-200 tokens
- With CoT: ~500-1000 tokens

Mitigations:

1. Only enable CoT for elevated risk scenarios
2. Truncate reasoning before database storage
3. Use streaming to start processing JSON immediately

```python
# Conditional CoT based on preliminary assessment
if preliminary_risk > 40:
    prompt = prompt_with_reasoning
else:
    prompt = basic_prompt
```

## See Also

- [Basic Risk Analysis](basic-risk-analysis.md) - Without reasoning
- [Rubric-Based Prompt](rubric-based-prompt.md) - Structured scoring
- [Main Documentation](../../development/nemotron-prompting.md)
- Implementation: `backend/services/prompts.py` - `CALIBRATED_SYSTEM_PROMPT_WITH_REASONING`

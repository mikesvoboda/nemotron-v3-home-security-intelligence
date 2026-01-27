# Basic Risk Analysis Prompt Example

This example shows a minimal prompt for risk analysis with Nemotron.

## Prompt Template

```python
prompt = """<|im_start|>system
You are a home security analyst for a residential property.

CRITICAL PRINCIPLE: Most detections are NOT threats. Residents, family members,
delivery workers, and pets represent normal household activity. Your job is to
identify genuine anomalies, not flag everyday life.

CALIBRATION: In a typical day, expect:
- 80% of events to be LOW risk (0-29): Normal activity
- 15% to be MEDIUM risk (30-59): Worth noting but not alarming
- 4% to be HIGH risk (60-84): Genuinely suspicious, warrants review
- 1% to be CRITICAL (85-100): Immediate threats only

If you're scoring >20% of events as HIGH or CRITICAL, you are miscalibrated.

Output ONLY valid JSON. No preamble, no explanation.<|im_end|>
<|im_start|>user
## SCORING REFERENCE
| Scenario | Score | Reasoning |
|----------|-------|-----------|
| Resident arriving home | 5-15 | Expected activity |
| Delivery driver at door | 15-25 | Normal service visit |
| Unknown person on sidewalk | 20-35 | Public area, passive |
| Unknown person lingering | 45-60 | Warrants attention |
| Person testing door handles | 70-85 | Clear suspicious intent |
| Active break-in or violence | 85-100 | Immediate threat |

## EVENT CONTEXT
Camera: Front Door
Time: 14:30:00 to 14:31:00

## DETECTIONS
- 14:30:05: person detected (confidence: 0.92)
- 14:30:08: person detected (confidence: 0.89)
- 14:30:15: person detected (confidence: 0.91)

## YOUR TASK
Analyze this camera event. Output JSON with:
- risk_score: Integer from 0-100
- risk_level: "low", "medium", "high", or "critical"
- summary: 1-2 sentence description
- reasoning: Brief explanation of your assessment<|im_end|>
<|im_start|>assistant
"""
```

## Expected Response

```json
{
  "risk_score": 20,
  "risk_level": "low",
  "summary": "Single person detected at front door during daytime hours.",
  "reasoning": "Person detected with high confidence during normal business hours. Pattern consistent with delivery or expected visitor. No suspicious behavior indicators present."
}
```

## API Call

```python
import httpx

async def analyze_basic(prompt: str) -> dict:
    payload = {
        "prompt": prompt,
        "temperature": 0.7,
        "top_p": 0.95,
        "max_tokens": 512,
        "stop": ["<|im_end|>", "<|im_start|>"]
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8091/completion",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30.0
        )
        response.raise_for_status()
        result = response.json()

    # Parse JSON from completion
    import json
    return json.loads(result["content"])
```

## Key Design Decisions

1. **Calibration in System Prompt**: Sets expectations for score distribution
2. **Scoring Reference Table**: Anchors the model with concrete examples
3. **Structured Output Request**: Explicitly requests JSON fields
4. **Stop Tokens**: Prevents runaway generation
5. **Temperature 0.7**: Balances consistency with nuance

## When to Use

- Quick risk assessments without enrichment data
- Testing and development
- Fallback when enrichment services unavailable

## See Also

- [Rubric-Based Prompt Example](rubric-based-prompt.md) - More structured scoring
- [Chain-of-Thought Example](chain-of-thought.md) - Transparent reasoning
- [Main Documentation](../../development/nemotron-prompting.md)

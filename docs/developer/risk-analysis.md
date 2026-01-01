# Risk Analysis

> Nemotron LLM integration for risk scoring and event generation.

**Time to read:** ~10 min
**Prerequisites:** [Batching Logic](batching-logic.md)

---

## What Nemotron Does

Nemotron Mini 4B Instruct analyzes batched detections and generates:

1. Risk score (0-100)
2. Risk level (low/medium/high/critical)
3. Human-readable summary
4. Reasoning explanation

---

## Source Files

- `/ai/nemotron/` - Model files and configuration
- `/backend/services/nemotron_analyzer.py` - Analysis service
- `/backend/services/prompts.py` - Prompt templates

---

## Analysis Flow

```
Batch closed
      |
      v
Load detection details from DB
      |
      v
Format prompt with context
      |
      v
Call Nemotron /completion
      |
      v
Parse JSON response
      |
      v
Validate and normalize
      |
      v
Create Event record
      |
      v
Broadcast via WebSocket
```

---

## Prompt Structure

The prompt template is defined in `/backend/services/prompts.py`:

```python
RISK_ANALYSIS_PROMPT = """You are a home security AI analyst.
Analyze the following detections and provide a risk assessment.

Camera: {camera_name}
Time Window: {start_time} to {end_time}
Detections:
{detections_list}

Respond in JSON format:
{{
  "risk_score": <0-100>,
  "risk_level": "<low|medium|high|critical>",
  "summary": "<brief 1-2 sentence summary>",
  "reasoning": "<detailed explanation>"
}}

Risk guidelines:
- Low (0-29): Normal activity (pets, known vehicles, delivery)
- Medium (30-59): Unusual but not alarming (unknown person during day)
- High (60-84): Concerning activity (person at odd hours, loitering)
- Critical (85-100): Immediate attention (forced entry, suspicious behavior)
"""
```

---

## Context Provided to LLM

1. **Camera Name**: Human-readable identifier (e.g., "Front Door")
2. **Time Window**: ISO format timestamps
3. **Detection List**: Formatted as:
   ```
   1. 14:30:00 - person (confidence: 0.95)
   2. 14:30:15 - person (confidence: 0.92)
   3. 14:30:30 - car (confidence: 0.87)
   ```

---

## API Call

**Endpoint:** `POST http://localhost:8091/completion`

**Request:**

```json
{
  "prompt": "<formatted prompt>",
  "temperature": 0.7,
  "max_tokens": 500,
  "stop": ["\n\n"]
}
```

**Response:**

```json
{
  "content": "{\n  \"risk_score\": 65,\n  ...\n}",
  "model": "nemotron-mini-4b-instruct-q4_k_m.gguf",
  "tokens_predicted": 87,
  "tokens_evaluated": 245
}
```

---

## Output Format

The LLM produces JSON:

```json
{
  "risk_score": 65,
  "risk_level": "high",
  "summary": "Unknown person detected approaching front door at night",
  "reasoning": "Single person detection at 2:15 AM is unusual.
               The person appeared to be approaching the entrance.
               Time of day and approach pattern warrant elevated concern."
}
```

---

## Risk Level Mapping

| Score Range | Level      | Description                        |
| ----------- | ---------- | ---------------------------------- |
| 0-29        | `low`      | Normal activity, no concern        |
| 30-59       | `medium`   | Unusual but not threatening        |
| 60-84       | `high`     | Suspicious, needs attention        |
| 85-100      | `critical` | Potential threat, immediate action |

---

## Validation and Normalization

The `_validate_risk_data()` method ensures valid output:

```python
def _validate_risk_data(self, data: dict) -> dict:
    # Validate risk_score (0-100, integer)
    risk_score = data.get("risk_score", 50)
    risk_score = max(0, min(100, int(risk_score)))

    # Validate risk_level
    valid_levels = ["low", "medium", "high", "critical"]
    risk_level = str(data.get("risk_level", "medium")).lower()

    if risk_level not in valid_levels:
        # Infer from risk_score
        if risk_score < 30:
            risk_level = "low"
        elif risk_score < 60:
            risk_level = "medium"
        elif risk_score < 85:
            risk_level = "high"
        else:
            risk_level = "critical"

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "summary": data.get("summary", "Risk analysis completed"),
        "reasoning": data.get("reasoning", "No detailed reasoning provided"),
    }
```

---

## JSON Extraction

LLM output may contain extra text. The analyzer extracts JSON using regex:

```python
json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
matches = re.findall(json_pattern, text, re.DOTALL)
```

---

## Fallback Behavior

When LLM analysis fails, default values are used:

```python
{
    "risk_score": 50,
    "risk_level": "medium",
    "summary": "Analysis unavailable - LLM service error",
    "reasoning": "Failed to analyze detections due to service error"
}
```

---

## Error Handling

| Error                  | Response           | Recovery      |
| ---------------------- | ------------------ | ------------- |
| Batch not found        | Raise `ValueError` | Skip batch    |
| Nemotron unreachable   | Use fallback       | Event created |
| Nemotron timeout (60s) | Use fallback       | Event created |
| Invalid LLM JSON       | Use fallback       | Event created |

---

## Performance

| Metric              | Value                       |
| ------------------- | --------------------------- |
| Inference time      | 2-5 seconds per batch       |
| Token generation    | ~50-100 tokens/second (GPU) |
| Context processing  | ~1000 tokens/second         |
| Concurrent requests | 2 (configured)              |
| VRAM usage          | ~3GB (Q4_K_M quantization)  |
| Context window      | 4096 tokens                 |

---

## Event Database Model

```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    batch_id VARCHAR NOT NULL,
    camera_id VARCHAR NOT NULL,
    started_at TIMESTAMP NOT NULL,
    ended_at TIMESTAMP NOT NULL,
    risk_score INTEGER NOT NULL,
    risk_level VARCHAR NOT NULL,
    summary TEXT,
    reasoning TEXT,
    detection_ids TEXT,  -- JSON array
    reviewed BOOLEAN DEFAULT FALSE,
    notes TEXT,
    is_fast_path BOOLEAN DEFAULT FALSE
);
```

---

## WebSocket Broadcast

After event creation, broadcast to all connected clients:

```python
await self.broadcaster.broadcast_event({
    "type": "new_event",
    "event": event.to_dict()
})
```

Clients receive:

```json
{
  "type": "new_event",
  "event": {
    "id": 42,
    "camera_id": "front_door",
    "risk_score": 65,
    "risk_level": "high",
    "summary": "Unknown person detected...",
    "started_at": "2025-12-28T14:30:00",
    "ended_at": "2025-12-28T14:31:30"
  }
}
```

---

## Next Steps

- [Pipeline Overview](pipeline-overview.md) - Full pipeline context
- [Batching Logic](batching-logic.md) - Batch aggregation details

---

## See Also

- [Risk Levels Reference](../reference/config/risk-levels.md) - Canonical risk level definitions
- [AI Overview](../operator/ai-overview.md) - Nemotron deployment
- [Alerts](alerts.md) - How risk scores trigger alerts
- [Understanding Alerts](../user/understanding-alerts.md) - User-friendly risk level guide

---

[Back to Developer Hub](../developer-hub.md)

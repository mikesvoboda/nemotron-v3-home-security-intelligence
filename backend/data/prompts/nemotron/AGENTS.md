# Nemotron Prompts Directory - Agent Guide

## Purpose

This directory contains configuration files for the Nemotron LLM, which performs comprehensive risk analysis on security events. Nemotron receives enriched detection data from multiple AI models and produces a structured risk assessment with risk score (0-100), risk level, reasoning, entities, and recommended actions.

## Files

| File              | Purpose                                                  | Version Control  |
| ----------------- | -------------------------------------------------------- | ---------------- |
| `current.json`    | Current active configuration used by the risk analyzer   | Runtime-managed  |
| `history/`        | Version history directory                                | -                |
| `history/v1.json` | Initial default configuration (system prompt and params) | Checked into git |

## Configuration Schema

```json
{
  "model_name": "nemotron",
  "config": {
    "system_prompt": "<|im_start|>system\n...full prompt text...<|im_end|>",
    "temperature": 0.7,
    "max_tokens": 2048
  },
  "version": 1,
  "created_at": "2026-01-06T13:16:23.587270+00:00",
  "created_by": "system",
  "description": "Initial default configuration",
  "updated_at": "2026-01-06T13:16:23.587270+00:00"
}
```

## Configuration Fields

### `system_prompt` (string, required)

The full system prompt for the Nemotron LLM. This prompt:

- Defines the role as "advanced home security risk analyzer"
- Instructs the model to output ONLY valid JSON (no preamble or markdown)
- Provides comprehensive context sections that are interpolated at runtime:
  - Camera & time context (camera name, timestamp, day of week, lighting)
  - Environmental context (weather, image quality)
  - Detection data with full AI enrichment attributes
  - Violence analysis
  - Behavioral analysis (pose, action recognition)
  - Vehicle analysis (classification, damage detection)
  - Person analysis (clothing via Fashion-CLIP)
  - Pet detection (false positive filtering)
  - Spatial context (depth estimation)
  - Re-identification (person/vehicle tracking across cameras)
  - Zone analysis
  - Baseline comparison and deviation scoring
  - Cross-camera activity correlation
  - Scene analysis

**Risk Interpretation Guide (included in prompt):**

The prompt includes a detailed guide for interpreting different types of events:

- Violence detection thresholds
- Weather impact on visibility
- Clothing/attire risk factors (all black + face covering = HIGH RISK)
- Vehicle analysis patterns (work van at night = suspicious)
- Pet detection (high-confidence cat/dog = likely false positive)
- Pose/behavior analysis (crouching near entry = suspicious)
- Image quality indicators (sudden quality drop = possible tampering)
- Time context (late night + artificial light = concerning)

**Risk Levels:**

- `low (0-29)`: Normal activity, no action needed
- `medium (30-59)`: Notable activity, worth reviewing
- `high (60-84)`: Suspicious activity, recommend alert
- `critical (85-100)`: Immediate threat, urgent action required

**Expected JSON Output Format:**

```json
{
  "risk_score": 0-100,
  "risk_level": "low|medium|high|critical",
  "summary": "1-2 sentence summary",
  "reasoning": "detailed multi-paragraph explanation",
  "entities": [
    {
      "type": "person|vehicle|pet",
      "description": "detailed description with attributes",
      "threat_level": "low|medium|high"
    }
  ],
  "flags": [
    {
      "type": "violence|suspicious_attire|vehicle_damage|unusual_behavior|quality_issue",
      "description": "text",
      "severity": "warning|alert|critical"
    }
  ],
  "recommended_action": "specific action to take",
  "confidence_factors": {
    "detection_quality": "good|fair|poor",
    "weather_impact": "none|minor|significant",
    "enrichment_coverage": "full|partial|minimal"
  }
}
```

### `temperature` (float, optional)

LLM sampling temperature controlling randomness in responses.

- **Range:** 0.0 to 2.0
- **Default:** 0.7
- **Lower values (0.0-0.5):** More deterministic, consistent risk scores
- **Higher values (0.8-2.0):** More creative, varied reasoning

For security analysis, a moderate temperature (0.7) balances consistency with nuanced interpretation of complex scenarios.

### `max_tokens` (int, optional)

Maximum number of tokens in the LLM response.

- **Range:** 100 to 8192
- **Default:** 2048
- **Typical response size:** 500-1500 tokens (depending on event complexity)
- **Set higher for complex events** with many detections and cross-camera correlations

## Usage in Risk Analysis Pipeline

The risk analysis service (`/backend/services/risk_analysis.py`) loads the current Nemotron configuration and uses it to analyze security events:

1. **Load config:** `get_prompt_storage().get_config("nemotron")`
2. **Interpolate context:** Replace `{camera_name}`, `{timestamp}`, `{detections_with_all_attributes}`, etc. with runtime data
3. **Call Nemotron API:** Send interpolated prompt to llama.cpp server
4. **Parse JSON response:** Extract risk score, level, reasoning, entities, flags
5. **Store results:** Save to `events` table in PostgreSQL

## Customization Examples

### Increase Sensitivity to Night Activity

Modify the risk interpretation guide to treat nighttime detections more seriously:

```
### Time Context
- Late night (11pm-5am) + any person detection = elevated concern (minimum medium risk)
- Late night + vehicle = investigate (minimum medium risk)
- Business hours + service uniform = normal activity
```

### Add Custom Risk Factors

Add new sections to the prompt for site-specific concerns:

```
### Known Vehicle Whitelist
- License plate ABC-123: Family vehicle (low risk)
- License plate XYZ-789: Neighbor vehicle (low risk)
- Unknown vehicles at night: elevated concern
```

### Adjust Risk Thresholds

Modify the risk level definitions:

```
### Risk Levels
- low (0-19): Normal activity, no action needed
- medium (20-49): Notable activity, worth reviewing
- high (50-79): Suspicious activity, recommend alert
- critical (80-100): Immediate threat, urgent action required
```

## Version History

Each configuration update creates a new version in `history/vN.json`. Use the API or `PromptStorageService` to:

- View version history: `GET /api/prompts/nemotron/history`
- Restore previous version: `POST /api/prompts/nemotron/versions/{version}/restore`
- Compare versions: Diff the JSON files in `history/`

## Testing Configuration Changes

Before deploying a modified prompt:

1. **Validate syntax:** Use `POST /api/prompts/nemotron/test` with an existing event ID
2. **Review mock output:** Compare before/after risk scores and reasoning
3. **Test with representative events:** Use events with different risk levels (low, medium, high, critical)
4. **Check JSON parsing:** Ensure the LLM consistently returns valid JSON (no markdown code blocks)

## Performance Considerations

- **Prompt length:** The default prompt is ~3000 tokens. Longer prompts increase inference time.
- **Max tokens:** Higher `max_tokens` increases latency. Monitor P95 inference time.
- **Temperature:** Higher temperature increases response variability (less predictable risk scores).

## Related Documentation

- `/backend/services/risk_analysis.py` - Risk analysis service using Nemotron
- `/backend/services/prompts.py` - Prompt template definitions
- `/ai/nemotron/AGENTS.md` - Nemotron model server setup
- `/backend/api/routes/prompt_management.py` - Prompt configuration API

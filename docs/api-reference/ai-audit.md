---
title: AI Audit API
description: REST API endpoints for AI pipeline audit management
source_refs:
  - backend/api/routes/ai_audit.py
  - backend/api/schemas/ai_audit.py
  - backend/models/event_audit.py
  - backend/services/audit_service.py
---

# AI Audit API

The AI Audit API provides endpoints for auditing AI pipeline performance. This includes tracking model contributions, quality scores, consistency checks, and generating recommendations for prompt improvements.

## Endpoints Overview

| Method | Endpoint                                   | Description                           |
| ------ | ------------------------------------------ | ------------------------------------- |
| GET    | `/api/ai-audit/events/{event_id}`          | Get audit for a specific event        |
| POST   | `/api/ai-audit/events/{event_id}/evaluate` | Trigger full evaluation for an event  |
| GET    | `/api/ai-audit/stats`                      | Get aggregate audit statistics        |
| GET    | `/api/ai-audit/leaderboard`                | Get model leaderboard by contribution |
| GET    | `/api/ai-audit/recommendations`            | Get aggregated prompt recommendations |
| POST   | `/api/ai-audit/batch`                      | Trigger batch audit processing        |

---

## GET /api/ai-audit/events/{event_id}

Get audit information for a specific event.

Retrieves the AI pipeline audit record for the given event, including model contributions, quality scores, and prompt improvement suggestions.

**Source:** [`get_event_audit`](../../backend/api/routes/ai_audit.py:106)

**Parameters:**

| Name       | Type    | In   | Required | Description                          |
| ---------- | ------- | ---- | -------- | ------------------------------------ |
| `event_id` | integer | path | Yes      | The ID of the event to get audit for |

**Response:** `200 OK`

```json
{
  "id": 1,
  "event_id": 42,
  "audited_at": "2025-12-23T12:00:00Z",
  "is_fully_evaluated": true,
  "contributions": {
    "rtdetr": true,
    "florence": true,
    "clip": false,
    "violence": true,
    "clothing": true,
    "vehicle": false,
    "pet": false,
    "weather": true,
    "image_quality": true,
    "zones": true,
    "baseline": false,
    "cross_camera": false
  },
  "prompt_length": 4096,
  "prompt_token_estimate": 1024,
  "enrichment_utilization": 0.75,
  "scores": {
    "context_usage": 4.2,
    "reasoning_coherence": 4.5,
    "risk_justification": 3.8,
    "consistency": 4.0,
    "overall": 4.1
  },
  "consistency_risk_score": 72,
  "consistency_diff": 3,
  "self_eval_critique": "The model appropriately identified the person as a potential security concern...",
  "improvements": {
    "missing_context": ["Time of day context could help", "Previous activity history"],
    "confusing_sections": [],
    "unused_data": ["Weather data was provided but not referenced"],
    "format_suggestions": ["Consider bullet points for clarity"],
    "model_gaps": ["Face detection could improve identification"]
  }
}
```

**Errors:**

| Code | Description              |
| ---- | ------------------------ |
| 404  | Event not found          |
| 404  | No audit found for event |

**Example Request:**

```bash
curl http://localhost:8000/api/ai-audit/events/42
```

---

## POST /api/ai-audit/events/{event_id}/evaluate

Trigger full evaluation for a specific event's audit.

Runs the complete self-evaluation pipeline including self-critique, rubric scoring, consistency check, and prompt improvement analysis for the given event.

**Source:** [`evaluate_event`](../../backend/api/routes/ai_audit.py:149)

**Parameters:**

| Name       | Type    | In    | Required | Description                                                    |
| ---------- | ------- | ----- | -------- | -------------------------------------------------------------- |
| `event_id` | integer | path  | Yes      | The ID of the event to evaluate                                |
| `force`    | boolean | query | No       | Force re-evaluation even if already evaluated (default: false) |

**Response:** `200 OK`

Returns the same response structure as `GET /api/ai-audit/events/{event_id}` with updated evaluation results.

**Errors:**

| Code | Description              |
| ---- | ------------------------ |
| 404  | Event not found          |
| 404  | No audit found for event |

**Example Requests:**

```bash
# Evaluate an event
curl -X POST http://localhost:8000/api/ai-audit/events/42/evaluate

# Force re-evaluation
curl -X POST "http://localhost:8000/api/ai-audit/events/42/evaluate?force=true"
```

---

## GET /api/ai-audit/stats

Get aggregate AI audit statistics.

Returns aggregate statistics including total events, quality scores, model contribution rates, and audit trends over the specified period.

**Source:** [`get_audit_stats`](../../backend/api/routes/ai_audit.py:202)

**Parameters:**

| Name        | Type    | In    | Required | Description                                  |
| ----------- | ------- | ----- | -------- | -------------------------------------------- |
| `days`      | integer | query | No       | Number of days to include (1-90, default: 7) |
| `camera_id` | string  | query | No       | Filter by camera ID                          |

**Response:** `200 OK`

```json
{
  "total_events": 500,
  "audited_events": 480,
  "fully_evaluated_events": 450,
  "avg_quality_score": 4.2,
  "avg_consistency_rate": 0.85,
  "avg_enrichment_utilization": 0.72,
  "model_contribution_rates": {
    "rtdetr": 0.98,
    "florence": 0.82,
    "clip": 0.45,
    "violence": 0.65,
    "clothing": 0.78,
    "vehicle": 0.35,
    "pet": 0.22,
    "weather": 0.88,
    "image_quality": 0.95,
    "zones": 0.67,
    "baseline": 0.42,
    "cross_camera": 0.15
  },
  "audits_by_day": [
    { "date": "2025-12-17", "count": 45 },
    { "date": "2025-12-18", "count": 52 },
    { "date": "2025-12-19", "count": 68 },
    { "date": "2025-12-20", "count": 71 },
    { "date": "2025-12-21", "count": 65 },
    { "date": "2025-12-22", "count": 78 },
    { "date": "2025-12-23", "count": 101 }
  ]
}
```

**Response Fields:**

| Field                        | Type    | Description                               |
| ---------------------------- | ------- | ----------------------------------------- |
| `total_events`               | integer | Total events in period                    |
| `audited_events`             | integer | Events with audit records                 |
| `fully_evaluated_events`     | integer | Events with complete evaluation           |
| `avg_quality_score`          | float   | Average overall quality score (1-5 scale) |
| `avg_consistency_rate`       | float   | Rate of consistent risk scoring (0-1)     |
| `avg_enrichment_utilization` | float   | Average enrichment data utilization (0-1) |
| `model_contribution_rates`   | object  | Contribution rate per model (0-1)         |
| `audits_by_day`              | array   | Daily audit counts for trending           |

**Example Requests:**

```bash
# Get stats for last 7 days
curl http://localhost:8000/api/ai-audit/stats

# Get stats for last 30 days
curl "http://localhost:8000/api/ai-audit/stats?days=30"

# Filter by camera
curl "http://localhost:8000/api/ai-audit/stats?camera_id=front_door"
```

---

## GET /api/ai-audit/leaderboard

Get model leaderboard ranked by contribution rate.

Returns a ranked list of AI models by their contribution rate, along with quality correlation data showing how each model's presence correlates with higher quality scores.

**Source:** [`get_model_leaderboard`](../../backend/api/routes/ai_audit.py:236)

**Parameters:**

| Name   | Type    | In    | Required | Description                                  |
| ------ | ------- | ----- | -------- | -------------------------------------------- |
| `days` | integer | query | No       | Number of days to include (1-90, default: 7) |

**Response:** `200 OK`

```json
{
  "entries": [
    {
      "model_name": "rtdetr",
      "contribution_rate": 0.98,
      "quality_correlation": 0.72,
      "event_count": 490
    },
    {
      "model_name": "image_quality",
      "contribution_rate": 0.95,
      "quality_correlation": 0.68,
      "event_count": 475
    },
    {
      "model_name": "weather",
      "contribution_rate": 0.88,
      "quality_correlation": 0.45,
      "event_count": 440
    },
    {
      "model_name": "florence",
      "contribution_rate": 0.82,
      "quality_correlation": 0.81,
      "event_count": 410
    },
    {
      "model_name": "clothing",
      "contribution_rate": 0.78,
      "quality_correlation": 0.55,
      "event_count": 390
    }
  ],
  "period_days": 7
}
```

**Response Fields:**

| Field         | Type    | Description                            |
| ------------- | ------- | -------------------------------------- |
| `entries`     | array   | Ranked list of model entries           |
| `period_days` | integer | Number of days included in calculation |

**Entry Fields:**

| Field                 | Type    | Description                                          |
| --------------------- | ------- | ---------------------------------------------------- |
| `model_name`          | string  | Model identifier                                     |
| `contribution_rate`   | float   | Percentage of events with this model's data (0-1)    |
| `quality_correlation` | float   | Correlation between model presence and quality score |
| `event_count`         | integer | Number of events where this model contributed        |

**Example Request:**

```bash
# Get leaderboard for last 7 days
curl http://localhost:8000/api/ai-audit/leaderboard

# Get leaderboard for last 30 days
curl "http://localhost:8000/api/ai-audit/leaderboard?days=30"
```

---

## GET /api/ai-audit/recommendations

Get aggregated prompt improvement recommendations.

Analyzes all audits to produce actionable recommendations for improving the AI pipeline prompt templates. Recommendations are prioritized based on frequency of occurrence across events.

**Source:** [`get_recommendations`](../../backend/api/routes/ai_audit.py:270)

**Parameters:**

| Name   | Type    | In    | Required | Description                                  |
| ------ | ------- | ----- | -------- | -------------------------------------------- |
| `days` | integer | query | No       | Number of days to analyze (1-90, default: 7) |

**Response:** `200 OK`

```json
{
  "recommendations": [
    {
      "category": "missing_context",
      "suggestion": "Include historical activity patterns for the camera",
      "frequency": 145,
      "priority": "high"
    },
    {
      "category": "unused_data",
      "suggestion": "Weather data is frequently provided but not referenced in reasoning",
      "frequency": 98,
      "priority": "medium"
    },
    {
      "category": "model_gaps",
      "suggestion": "Face detection could improve person identification accuracy",
      "frequency": 67,
      "priority": "medium"
    },
    {
      "category": "format_suggestions",
      "suggestion": "Use structured detection lists instead of prose",
      "frequency": 45,
      "priority": "low"
    },
    {
      "category": "confusing_sections",
      "suggestion": "Clarify the relationship between zone alerts and risk scoring",
      "frequency": 23,
      "priority": "low"
    }
  ],
  "total_events_analyzed": 450
}
```

**Response Fields:**

| Field                   | Type    | Description                               |
| ----------------------- | ------- | ----------------------------------------- |
| `recommendations`       | array   | List of prioritized recommendations       |
| `total_events_analyzed` | integer | Number of fully evaluated events analyzed |

**Recommendation Categories:**

| Category             | Description                                               |
| -------------------- | --------------------------------------------------------- |
| `missing_context`    | Information that would help the LLM make better decisions |
| `confusing_sections` | Parts of the prompt that led to unclear reasoning         |
| `unused_data`        | Enrichment data provided but not utilized                 |
| `format_suggestions` | Recommendations for prompt structure improvements         |
| `model_gaps`         | Vision models that could improve analysis if added        |

**Priority Levels:**

| Priority | Criteria                      |
| -------- | ----------------------------- |
| `high`   | Mentioned in >20% of events   |
| `medium` | Mentioned in 10-20% of events |
| `low`    | Mentioned in <10% of events   |

**Example Request:**

```bash
# Get recommendations for last 7 days
curl http://localhost:8000/api/ai-audit/recommendations

# Get recommendations for last 90 days
curl "http://localhost:8000/api/ai-audit/recommendations?days=90"
```

---

## POST /api/ai-audit/batch

Trigger batch audit processing for multiple events.

Queues events for audit processing based on the provided criteria. Events are processed synchronously and evaluated.

**Source:** [`trigger_batch_audit`](../../backend/api/routes/ai_audit.py:307)

**Request Body:**

```json
{
  "limit": 100,
  "min_risk_score": 50,
  "force_reevaluate": false
}
```

**Request Fields:**

| Field              | Type    | Required | Description                                               |
| ------------------ | ------- | -------- | --------------------------------------------------------- |
| `limit`            | integer | No       | Max events to process (1-1000, default: 100)              |
| `min_risk_score`   | integer | No       | Only process events with risk score >= this value (0-100) |
| `force_reevaluate` | boolean | No       | Re-evaluate already evaluated events (default: false)     |

**Response:** `200 OK`

```json
{
  "queued_count": 75,
  "message": "Successfully processed 75 events for audit evaluation"
}
```

**Response Fields:**

| Field          | Type    | Description                |
| -------------- | ------- | -------------------------- |
| `queued_count` | integer | Number of events processed |
| `message`      | string  | Status message             |

**Example Requests:**

```bash
# Process up to 100 unevaluated events
curl -X POST http://localhost:8000/api/ai-audit/batch \
  -H "Content-Type: application/json" \
  -d '{}'

# Process high-risk events only
curl -X POST http://localhost:8000/api/ai-audit/batch \
  -H "Content-Type: application/json" \
  -d '{"min_risk_score": 70, "limit": 50}'

# Force re-evaluation of all events
curl -X POST http://localhost:8000/api/ai-audit/batch \
  -H "Content-Type: application/json" \
  -d '{"force_reevaluate": true, "limit": 200}'
```

---

## Data Models

### EventAuditResponse

Full audit response for a single event.

**Source:** [`EventAuditResponse`](../../backend/api/schemas/ai_audit.py:45)

| Field                    | Type               | Description                                    |
| ------------------------ | ------------------ | ---------------------------------------------- |
| `id`                     | integer            | Audit record ID                                |
| `event_id`               | integer            | Associated event ID                            |
| `audited_at`             | datetime           | When the audit was created                     |
| `is_fully_evaluated`     | boolean            | Whether full evaluation has completed          |
| `contributions`          | ModelContributions | Model contribution flags                       |
| `prompt_length`          | integer            | Length of the LLM prompt in characters         |
| `prompt_token_estimate`  | integer            | Estimated token count for the prompt           |
| `enrichment_utilization` | float              | Ratio of enrichment data utilized (0-1)        |
| `scores`                 | QualityScores      | Self-evaluation quality scores                 |
| `consistency_risk_score` | integer            | Risk score from consistency check (nullable)   |
| `consistency_diff`       | integer            | Difference from original risk score (nullable) |
| `self_eval_critique`     | string             | Self-evaluation text critique (nullable)       |
| `improvements`           | PromptImprovements | Prompt improvement suggestions                 |

### ModelContributions

Model contribution flags indicating which models contributed to the event.

**Source:** [`ModelContributions`](../../backend/api/schemas/ai_audit.py:8)

| Field           | Type    | Description                  |
| --------------- | ------- | ---------------------------- |
| `rtdetr`        | boolean | RT-DETR object detection     |
| `florence`      | boolean | Florence-2 vision attributes |
| `clip`          | boolean | CLIP embeddings              |
| `violence`      | boolean | Violence detection           |
| `clothing`      | boolean | Clothing analysis            |
| `vehicle`       | boolean | Vehicle classification       |
| `pet`           | boolean | Pet classification           |
| `weather`       | boolean | Weather classification       |
| `image_quality` | boolean | Image quality assessment     |
| `zones`         | boolean | Zone analysis                |
| `baseline`      | boolean | Baseline comparison          |
| `cross_camera`  | boolean | Cross-camera correlation     |

### QualityScores

Self-evaluation quality scores on a 1-5 scale.

**Source:** [`QualityScores`](../../backend/api/schemas/ai_audit.py:25)

| Field                 | Type  | Description                                    |
| --------------------- | ----- | ---------------------------------------------- |
| `context_usage`       | float | How well the model used provided context (1-5) |
| `reasoning_coherence` | float | Coherence and clarity of reasoning (1-5)       |
| `risk_justification`  | float | Quality of risk score justification (1-5)      |
| `consistency`         | float | Consistency with similar events (1-5)          |
| `overall`             | float | Overall quality score (1-5)                    |

### PromptImprovements

Prompt improvement suggestions from self-evaluation.

**Source:** [`PromptImprovements`](../../backend/api/schemas/ai_audit.py:35)

| Field                | Type          | Description                                |
| -------------------- | ------------- | ------------------------------------------ |
| `missing_context`    | array[string] | Context that would help decision-making    |
| `confusing_sections` | array[string] | Prompt sections that led to unclear output |
| `unused_data`        | array[string] | Enrichment data provided but not used      |
| `format_suggestions` | array[string] | Prompt structure improvement ideas         |
| `model_gaps`         | array[string] | Vision models that could improve analysis  |

### AuditStatsResponse

Aggregate audit statistics response.

**Source:** [`AuditStatsResponse`](../../backend/api/schemas/ai_audit.py:77)

| Field                        | Type               | Description                               |
| ---------------------------- | ------------------ | ----------------------------------------- |
| `total_events`               | integer            | Total events in period                    |
| `audited_events`             | integer            | Events with audit records                 |
| `fully_evaluated_events`     | integer            | Events with complete evaluation           |
| `avg_quality_score`          | float              | Average overall quality score (nullable)  |
| `avg_consistency_rate`       | float              | Average consistency rate (nullable)       |
| `avg_enrichment_utilization` | float              | Average enrichment utilization (nullable) |
| `model_contribution_rates`   | dict[string,float] | Contribution rate per model               |
| `audits_by_day`              | array[dict]        | Daily audit counts                        |

### LeaderboardResponse

Model leaderboard response.

**Source:** [`LeaderboardResponse`](../../backend/api/schemas/ai_audit.py:104)

| Field         | Type                         | Description                  |
| ------------- | ---------------------------- | ---------------------------- |
| `entries`     | array[ModelLeaderboardEntry] | Ranked list of model entries |
| `period_days` | integer                      | Number of days included      |

### ModelLeaderboardEntry

Single entry in model leaderboard.

**Source:** [`ModelLeaderboardEntry`](../../backend/api/schemas/ai_audit.py:95)

| Field                 | Type    | Description                                |
| --------------------- | ------- | ------------------------------------------ |
| `model_name`          | string  | Model identifier                           |
| `contribution_rate`   | float   | Rate of events with this model's data      |
| `quality_correlation` | float   | Correlation with quality scores (nullable) |
| `event_count`         | integer | Number of events with this model           |

### RecommendationsResponse

Aggregated recommendations response.

**Source:** [`RecommendationsResponse`](../../backend/api/schemas/ai_audit.py:120)

| Field                   | Type                      | Description                 |
| ----------------------- | ------------------------- | --------------------------- |
| `recommendations`       | array[RecommendationItem] | Prioritized recommendations |
| `total_events_analyzed` | integer                   | Number of events analyzed   |

### RecommendationItem

Single recommendation item.

**Source:** [`RecommendationItem`](../../backend/api/schemas/ai_audit.py:111)

| Field        | Type    | Description                                              |
| ------------ | ------- | -------------------------------------------------------- |
| `category`   | string  | Category: missing_context, unused_data, model_gaps, etc. |
| `suggestion` | string  | The recommendation text                                  |
| `frequency`  | integer | Number of events mentioning this issue                   |
| `priority`   | string  | Priority level: high, medium, low                        |

### BatchAuditRequest

Request for batch audit processing.

**Source:** [`BatchAuditRequest`](../../backend/api/schemas/ai_audit.py:127)

| Field              | Type    | Required | Description                                  |
| ------------------ | ------- | -------- | -------------------------------------------- |
| `limit`            | integer | No       | Max events to process (1-1000, default: 100) |
| `min_risk_score`   | integer | No       | Minimum risk score filter (0-100)            |
| `force_reevaluate` | boolean | No       | Re-evaluate already evaluated events         |

### BatchAuditResponse

Response for batch audit request.

**Source:** [`BatchAuditResponse`](../../backend/api/schemas/ai_audit.py:135)

| Field          | Type    | Description                |
| -------------- | ------- | -------------------------- |
| `queued_count` | integer | Number of events processed |
| `message`      | string  | Status message             |

---

## Related Documentation

- [Events API](events.md) - Events are the primary data source for audits
- [Enrichment API](enrichment.md) - Vision model results tracked by audits
- [Model Zoo API](model-zoo.md) - AI model status monitoring
- [Audit API](audit.md) - System audit logs (different from AI audit)
- [System API](system.md) - System configuration and monitoring

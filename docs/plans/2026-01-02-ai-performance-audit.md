# AI Performance Audit System Design

**Date:** 2026-01-02
**Status:** Approved
**Author:** Claude + User collaboration

## Overview

A comprehensive AI pipeline audit and scoring system that enables debugging, batch evaluation, and quality improvement for the Nemotron risk analysis pipeline and its supporting AI model zoo.

## Goals

1. **Debugging** - Analyze specific events to see what each model contributed and why Nemotron made certain decisions
2. **Batch Evaluation** - Process many events to generate aggregate statistics
3. **Quality Improvement** - Generate actionable recommendations for improving prompts and model configurations
4. **Self-Evaluation** - Use Nemotron to evaluate its own responses for quality and consistency

## Data Model

### EventAudit Table

```python
class EventAudit(Base):
    __tablename__ = "event_audits"

    id: Mapped[int]  # Primary key
    event_id: Mapped[int]  # FK -> events.id, unique constraint
    audited_at: Mapped[datetime]

    # Model contribution flags (captured real-time)
    has_rtdetr: Mapped[bool]
    has_florence: Mapped[bool]
    has_clip: Mapped[bool]
    has_violence: Mapped[bool]
    has_clothing: Mapped[bool]
    has_vehicle: Mapped[bool]
    has_pet: Mapped[bool]
    has_weather: Mapped[bool]
    has_image_quality: Mapped[bool]
    has_zones: Mapped[bool]
    has_baseline: Mapped[bool]
    has_cross_camera: Mapped[bool]

    # Prompt metrics
    prompt_length: Mapped[int]  # character count
    prompt_token_estimate: Mapped[int]  # rough token count
    enrichment_utilization: Mapped[float]  # 0-1, % of available enrichments used

    # Self-evaluation scores (from Nemotron, 1-5 scale)
    context_usage_score: Mapped[float | None]
    reasoning_coherence_score: Mapped[float | None]
    risk_justification_score: Mapped[float | None]
    consistency_score: Mapped[float | None]
    overall_quality_score: Mapped[float | None]

    # Self-evaluation details
    self_eval_critique: Mapped[str | None]
    self_eval_prompt: Mapped[str | None]
    self_eval_response: Mapped[str | None]

    # Prompt improvement suggestions
    missing_context: Mapped[str | None]  # JSON array
    confusing_sections: Mapped[str | None]  # JSON array
    unused_data: Mapped[str | None]  # JSON array
    format_suggestions: Mapped[str | None]  # JSON array
    model_gaps: Mapped[str | None]  # JSON array

    # Aggregated recommendations (JSON)
    recommendations: Mapped[str | None]
```

## Self-Evaluation Modes

### Mode 1: Self-Critique

Free-form critique of the model's own response, identifying strengths and weaknesses.

```
You previously analyzed a security event and provided this assessment:
- Risk Score: {risk_score}
- Summary: {summary}
- Reasoning: {reasoning}

Original context provided:
{llm_prompt}

Critique your own response. What did you do well? What could be improved?
What context did you ignore or underweight?
```

### Mode 2: Structured Rubric

Quantitative scoring on specific dimensions (1-5 scale).

```
Evaluate this security analysis on a 1-5 scale for each dimension:

Original prompt: {llm_prompt}
Your response: {summary} | {reasoning} | Risk: {risk_score}

Score each (1=poor, 5=excellent):
1. CONTEXT_USAGE: Did you reference all relevant enrichment data?
2. REASONING_COHERENCE: Is your reasoning logical and well-structured?
3. RISK_JUSTIFICATION: Does the evidence support your risk score?
4. ACTIONABILITY: Is your summary useful for a homeowner?

Output JSON: {"context_usage": N, "reasoning_coherence": N,
"risk_justification": N, "actionability": N, "explanation": "..."}
```

### Mode 3: Consistency Check

Re-analyze the same data to check if the model produces consistent results.

```
Here is security event data. What risk score (0-100) would you assign?

{llm_prompt_without_previous_response}

Output JSON: {"risk_score": N, "risk_level": "...", "brief_reason": "..."}
```

Scores differing by >15 points indicate inconsistency.

### Mode 4: Prompt Improvement

Analyze the prompt itself and suggest improvements.

```
You were given this prompt for security analysis:

{llm_prompt}

And you produced this response:
- Risk Score: {risk_score}
- Reasoning: {reasoning}

Analyze the PROMPT itself (not your response). Suggest improvements:

1. MISSING_CONTEXT: What information would have helped you make a better assessment?
2. CONFUSING_SECTIONS: Which parts of the prompt were unclear or contradictory?
3. UNUSED_DATA: Which provided data was not useful for this analysis?
4. FORMAT_SUGGESTIONS: How could the prompt structure be improved?
5. MODEL_GAPS: Which AI models should have provided data but didn't?

Output JSON: {
  "missing_context": ["...", "..."],
  "confusing_sections": ["..."],
  "unused_data": ["..."],
  "format_suggestions": ["..."],
  "model_gaps": ["..."],
  "rewritten_prompt_section": "..."
}
```

## API Endpoints

### Audit Routes (`/api/audit/`)

| Method | Endpoint                                | Description                              |
| ------ | --------------------------------------- | ---------------------------------------- |
| GET    | `/api/audit/events/{event_id}`          | Full audit for a single event            |
| POST   | `/api/audit/events/{event_id}/evaluate` | Trigger full self-evaluation (on-demand) |
| GET    | `/api/audit/stats`                      | Aggregate statistics for dashboard       |
| GET    | `/api/audit/leaderboard`                | Model rankings by usefulness             |
| POST   | `/api/audit/batch`                      | Trigger batch audit for recent events    |
| GET    | `/api/audit/recommendations`            | Aggregated improvement recommendations   |

### Query Parameters

- `GET /api/audit/stats?days=7&camera_id=xxx` - Filter by time range and camera
- `POST /api/audit/batch` body: `{ "limit": 100, "min_risk_score": 50 }`

## Timing Strategy (Hybrid)

### Real-time (Inline)

When `NemotronAnalyzer.analyze_batch()` creates an event:

- Create partial `EventAudit` record
- Capture model contribution flags
- Calculate prompt metrics (length, token estimate, utilization)
- Minimal overhead (<5ms)

### Background Worker

Periodic processing (default: every 5 minutes):

- Query events with partial audits (no self-evaluation scores)
- Prioritize high-risk events (risk_score >= 60)
- Run all 4 evaluation modes
- Update audit record with scores and recommendations

### On-Demand

User-triggered via API or UI:

- Click "Audit" on event card
- "Run Batch Audit" button on dashboard
- Immediate processing, returns results

## Frontend UI

### AI Performance Page (`/ai-performance`)

#### Dashboard Header

```
┌─────────────────────────────────────────────────────────────────┐
│  AI Performance Overview                        [Last 7 days ▼] │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────┤
│ Events      │ Avg Quality │ Consistency │ Prompt Util │ Audited │
│ Audited     │ Score       │ Rate        │ Rate        │ Today   │
│   1,247     │   4.2/5     │    91%      │    78%      │   43    │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────┘
```

#### Model Leaderboard (Left Panel)

- Contribution rates for each model
- Correlation with quality scores
- Visual bar charts

#### Recommendations Panel (Right Panel)

- Top improvement suggestions
- Common missing context patterns
- Unused data to remove
- Model health alerts

### Event-Level Drill-Down

Added to EventDetailModal as "AI Audit" tab:

- Quality scores with visual bars
- Model contribution checklist
- Self-critique text
- Prompt improvement suggestions
- Raw prompt/response viewers
- "Re-run Evaluation" button

### Event Card Badges

- Small quality score indicator (color-coded)
- Icon for unaudited events

## File Structure

```
backend/
├── models/
│   └── audit.py                 # EventAudit model
├── services/
│   └── audit_service.py         # Core audit logic + self-evaluation
├── api/
│   ├── routes/
│   │   └── audit.py             # API endpoints
│   └── schemas/
│       └── audit.py             # Pydantic schemas
├── alembic/versions/
│   └── add_event_audits.py      # Migration

frontend/src/
├── pages/
│   └── AIPerformancePage.tsx    # Main dashboard
├── components/
│   └── audit/
│       ├── AuditDashboard.tsx   # Aggregate stats + charts
│       ├── ModelLeaderboard.tsx # Rankings panel
│       ├── RecommendationsPanel.tsx
│       ├── EventAuditDetail.tsx # Drill-down view
│       └── AuditBadge.tsx       # Small indicator for event cards
├── hooks/
│   └── useAudit.ts              # API hooks
└── services/
    └── auditApi.ts              # API client
```

## Data Flow

```
Event Created → Partial Audit (model flags) → Background Worker
                                                    ↓
                                          Full Self-Evaluation
                                          (4 modes in sequence)
                                                    ↓
                                          Scores + Recommendations
                                                    ↓
                                    Dashboard Aggregation + Drill-down
```

## Key Metrics

| Metric                    | Description                                    |
| ------------------------- | ---------------------------------------------- |
| Model Contribution Rate   | % of events where model provided data          |
| Quality Score             | Average self-evaluation score (1-5)            |
| Consistency Rate          | % of events where re-analysis matched original |
| Prompt Utilization        | % of available enrichments included in prompt  |
| Model-Quality Correlation | Which models correlate with higher scores      |

## Success Criteria

1. Can view audit details for any event within 1 click
2. Dashboard shows actionable recommendations
3. Self-evaluation scores correlate with human judgment
4. Prompt improvements lead to measurably better analysis
5. Background processing doesn't impact real-time pipeline performance

## Future Enhancements

- A/B testing for prompt variations
- Human feedback integration (thumbs up/down on events)
- Automated prompt optimization based on recommendations
- Model performance degradation alerts
- Export audit data for external analysis

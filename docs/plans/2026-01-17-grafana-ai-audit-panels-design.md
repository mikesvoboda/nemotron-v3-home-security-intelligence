# Grafana AI Audit Panels Design

**Date:** 2026-01-17
**Status:** Approved
**Author:** Claude (brainstorming session with Mike)

## Summary

Embed Grafana dashboard directly into the AI Performance page via iframe, replacing the current native Tremor charts. Add a new "AI Quality & Audit" row to Grafana with 7 panels exposing AI audit system metrics via JSON datasource.

## Background

The current AI Performance page uses native Tremor charts with link-based Grafana integration. The user wants:

1. Richer visualizations than Tremor offers
2. Single pane of glass (no context-switching)
3. Reuse existing Grafana dashboards
4. Real-time streaming capabilities

### Decision: Full Page Iframe Embed

After evaluating iframe embedding, native React rebuild, and hybrid approaches, we chose **iframe embedding** for quick integration with all Grafana features intact.

### Gap Analysis

Grafana covers most metrics except AI audit data from `/api/ai-audit/*` endpoints:

- Model contribution rates
- Quality scores
- Enrichment utilization
- Consistency rates
- Recommendations

These will be added as new Grafana panels using the existing JSON datasource.

## Design

### New Grafana Row: "AI Quality & Audit"

**Position:** After "AI Inference" row

#### Layout (24-unit grid)

**Row 1:**
| Panel | Width | Type |
|-------|-------|------|
| Quality Score Trend | 8 | Time series |
| Enrichment Utilization | 4 | Gauge |
| Consistency Rate | 4 | Gauge |
| Audit Coverage | 4 | Stat |

**Row 2:**
| Panel | Width | Type |
|-------|-------|------|
| Model Contribution Heatmap | 12 | Heatmap/Table |
| Quality Correlation Leaderboard | 6 | Table |
| Recommendation Frequency | 6 | Bar chart |

### Panel Specifications

#### Panel 1: Quality Score Trend

- **Type:** Time series
- **Query:** `/api/ai-audit/stats?days=$audit_days`
- **Field:** `audits_by_day[].avg_quality_score`
- **Y-axis:** 1-5 scale
- **Thresholds:** <3 red, 3-4 yellow, >4 green

#### Panel 2: Enrichment Utilization

- **Type:** Gauge
- **Query:** `/api/ai-audit/stats?days=$audit_days`
- **Field:** `avg_enrichment_utilization`
- **Display:** Percentage (0-100%)
- **Thresholds:** <50% red, 50-75% yellow, >75% green

#### Panel 3: Consistency Rate

- **Type:** Gauge
- **Query:** `/api/ai-audit/stats?days=$audit_days`
- **Field:** `avg_consistency_rate`
- **Display:** Percentage (0-100%)
- **Thresholds:** <80% red, 80-90% yellow, >90% green

#### Panel 4: Audit Coverage

- **Type:** Stat
- **Query:** `/api/ai-audit/stats?days=$audit_days`
- **Calculation:** `fully_evaluated_events / total_events * 100`
- **Display:** "X% evaluated" with spark trend
- **Thresholds:** <70% red, 70-90% yellow, >90% green

#### Panel 5: Model Contribution Heatmap

- **Type:** Heatmap (fallback: table with colored cells)
- **Query:** `/api/ai-audit/stats?days=14`
- **Field:** `audits_by_day[].model_contributions`
- **Rows:** 12 models (yolo26, florence, clip, violence, clothing, vehicle, pet, weather, image_quality, zones, baseline, cross_camera)
- **Columns:** Days
- **Color:** Intensity by contribution count

#### Panel 6: Quality Correlation Leaderboard

- **Type:** Table
- **Query:** `/api/ai-audit/leaderboard?days=$audit_days`
- **Columns:** Model Name | Contribution Rate | Quality Correlation | Event Count
- **Sort:** By quality_correlation descending
- **Styling:** Colored bars for rates, highlight top 3

#### Panel 7: Recommendation Frequency

- **Type:** Bar chart (horizontal)
- **Query:** `/api/ai-audit/recommendations?days=$audit_days`
- **Field:** `recommendations[].frequency` grouped by `category`
- **Categories:** missing_context, unused_data, model_gaps, format_suggestions, confusing_sections
- **Color:** By priority (high=red, medium=yellow, low=blue)

### Dashboard Variable

Add `$audit_days` dropdown variable:

- **Name:** audit_days
- **Label:** Audit Period
- **Type:** Custom
- **Values:** 7, 14, 30, 90
- **Default:** 7

### Data Source

Use existing `Backend-API` JSON datasource (`http://backend:8000`).

**Endpoints:**

- `GET /api/ai-audit/stats?days={n}&camera_id={optional}`
- `GET /api/ai-audit/leaderboard?days={n}`
- `GET /api/ai-audit/recommendations?days={n}`

### Frontend Changes

Replace `AIPerformancePage.tsx` content with embedded Grafana iframe:

```tsx
<iframe
  src={`${grafanaUrl}/d/hsi-pipeline?orgId=1&kiosk`}
  className="w-full h-[calc(100vh-64px)] border-0"
  title="AI Performance Dashboard"
/>
```

- Use `kiosk` mode to hide Grafana chrome
- Keep header with refresh button and title
- Preserve error/loading states

### Refresh Rate

Audit panels: 5-minute refresh (vs 10s for real-time Prometheus panels)

## Implementation Steps

1. Add `$audit_days` dashboard variable to Grafana
2. Create "AI Quality & Audit" row in `consolidated.json`
3. Add 7 panels with JSON datasource queries
4. Update `AIPerformancePage.tsx` to embed Grafana iframe
5. Remove unused native chart components (or keep for fallback)
6. Update tests

## Alternatives Considered

1. **Native React rebuild** - More control but significant effort
2. **Hybrid approach** - Complex to maintain two rendering paradigms
3. **Link-based (current)** - Context switching hurts UX

## Dependencies

- Grafana JSON datasource plugin (already installed)
- Backend AI audit endpoints (already exist)
- Grafana anonymous auth (already enabled)

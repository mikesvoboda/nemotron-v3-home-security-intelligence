# AI Performance Components

This directory contains components for the AI Performance page (`/ai`), which provides
detailed monitoring of AI model performance and pipeline health.

## Overview

The AI Performance page consolidates AI-related metrics into a dedicated view:

- Model status for RT-DETRv2 (object detection) and Nemotron (LLM risk analysis)
- Latency statistics with percentile breakdowns
- Pipeline queue depths and throughput
- Error tracking and DLQ status

## Components

### AIPerformancePage.tsx

Main page component that orchestrates the AI performance dashboard.

**Features:**

- Uses `useAIMetrics` hook for real-time data polling
- Shows Grafana link for detailed metrics
- Refresh button for manual data updates
- Loading and error states

### AIAuditPage.tsx

Dashboard for AI quality metrics and prompt improvement recommendations.

**Features:**

- Displays quality score metrics and trends
- Shows prompt improvement recommendations
- Period selector (24h, 7d, 14d, 30d, 90d)
- Trigger batch audit functionality
- Manual refresh capability

**Subcomponents used:**

- `QualityScoreTrends` - Quality metric stat cards
- `RecommendationsPanel` - Grouped improvement suggestions
- `BatchAuditModal` - Batch audit configuration dialog

### BatchAuditModal.tsx

Modal dialog for triggering batch AI audit processing.

**Features:**

- Configurable event limit (1-1000, default 50)
- Configurable minimum risk score filter (0-100, default 50)
- Force re-evaluate checkbox for already-evaluated events
- Loading state during submission
- Error display with clear action

### InsightsCharts.tsx

Visualization charts for AI performance insights.

**Charts:**

- Detection class distribution (DonutChart showing person/vehicle/animal/package counts)
- Risk score distribution (clickable bar chart showing events by risk level)

**Interactivity:**

- Clicking on a risk level bar navigates to Timeline page with that filter applied
- Hover tooltips with event counts
- Responsive layout

### ModelContributionChart.tsx

Bar chart showing AI model contribution rates.

**Features:**

- Horizontal bar chart of model contribution percentages
- Human-readable model labels (RT-DETR, Florence, CLIP, etc.)
- Sorted by contribution rate (highest first)
- Empty state when no data available

### ModelLeaderboard.tsx

Sortable table ranking AI models by contribution.

**Features:**

- Sortable columns: Model, Contribution Rate, Events, Quality Correlation
- Rank badges for top 3 models (1st, 2nd, 3rd)
- Color-coded contribution rate badges
- Period indicator showing data range

### ModelStatusCards.tsx

Displays RT-DETRv2 and Nemotron model status cards side-by-side.

**Shows:**

- Health status badges (healthy/unhealthy/degraded/unknown)
- Inline latency statistics (avg, p95, p99)
- Model descriptions

### ModelZooSection.tsx

Displays Model Zoo status cards and latency chart.

**Features:**

- Dropdown-controlled latency chart (Avg, P50, P95 ms over time)
- Compact status cards for all 18 Model Zoo models
- Models grouped by category (Detection, Classification, Segmentation, etc.)
- VRAM budget/usage display
- Active vs disabled models separation
- Auto-refresh with configurable polling interval

### LatencyPanel.tsx

Detailed latency metrics with progress bars and percentile breakdowns.

**Sections:**

- AI Service Latency (RT-DETRv2 detection, Nemotron analysis)
- Pipeline Stage Latency (watch_to_detect, detect_to_batch, batch_to_analyze)
- Total pipeline end-to-end latency

### PipelineHealthPanel.tsx

Queue depths, throughput, and error monitoring.

**Shows:**

- Detection and Analysis queue depths with status colors
- Total detections and events counters
- Pipeline errors by type
- Queue overflow counts
- Dead Letter Queue items

### QualityScoreTrends.tsx

Displays AI quality score metrics as stat cards with visual progress indicators.

**Metrics:**

- Average Quality Score (1-5 scale)
- Consistency Rate (1-5 scale)
- Enrichment Utilization (percentage)
- Evaluation Coverage (percentage of events evaluated)

**Features:**

- Color-coded progress bars (green/yellow/red based on thresholds)
- Shows event counts for context

### RecommendationsPanel.tsx

Displays grouped prompt improvement suggestions from AI audit analysis.

**Features:**

- Recommendations grouped by category:
  - Missing Context - Information needed for better assessments
  - Unused Data - Data that was not useful
  - Model Gaps - AI models that should have provided data
  - Format Suggestions - Prompt structure improvements
  - Confusing Sections - Unclear or contradictory parts
- Priority badges (high/medium/low)
- Frequency counts
- Expandable accordion sections

## Data Flow

```
/api/metrics (Prometheus) ─┐
                           │
/api/system/telemetry ─────┼──► useAIMetrics ──► AIPerformancePage
                           │       hook             └── ModelStatusCards
/api/system/health ────────┤                        └── LatencyPanel
                           │                        └── PipelineHealthPanel
/api/system/pipeline-latency
```

## Hook: useAIMetrics

Located in `frontend/src/hooks/useAIMetrics.ts`.

**Returns:**

- `data`: Combined AI performance metrics
- `isLoading`: Loading state
- `error`: Error message if fetch failed
- `refresh`: Manual refresh function

**Options:**

- `pollingInterval`: How often to refresh (default: 5000ms)
- `enablePolling`: Whether to poll (default: true)

## Metrics Parser

Located in `frontend/src/services/metricsParser.ts`.

Parses Prometheus text format from `/api/metrics` endpoint.

**Key functions:**

- `parseMetrics()`: Parse all metrics from text
- `extractHistogram()`: Extract histogram data by name and labels
- `histogramToLatencyMetrics()`: Convert histogram to latency stats with percentiles
- `parseAIMetrics()`: Parse complete AI metrics response

## Testing

```bash
# Run all AI component tests
npm test -- --run src/components/ai/

# Run metrics parser tests
npm test -- --run src/services/metricsParser.test.ts
```

## Related Files

- `frontend/src/services/metricsParser.ts` - Prometheus metrics parser
- `frontend/src/hooks/useAIMetrics.ts` - AI metrics hook
- `backend/core/metrics.py` - Backend Prometheus metrics definitions
- `backend/api/routes/system.py` - System API endpoints

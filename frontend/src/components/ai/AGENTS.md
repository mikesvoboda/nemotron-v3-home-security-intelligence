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

### ModelStatusCards.tsx

Displays RT-DETRv2 and Nemotron model status cards side-by-side.

**Shows:**

- Health status badges (healthy/unhealthy/degraded/unknown)
- Inline latency statistics (avg, p95, p99)
- Model descriptions

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

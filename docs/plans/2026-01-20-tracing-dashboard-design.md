# HSI Distributed Tracing Dashboard Design

**Date:** 2026-01-20
**Status:** Approved

## Overview

A dedicated Grafana dashboard for distributed tracing that provides debugging, monitoring, and analysis capabilities for the HSI pipeline. The dashboard is embedded in the frontend's `/tracing` page via iframe.

## Requirements

- **Debugging:** Find where things are slow/broken with error traces, latency outliers, drill-down
- **Monitoring:** Real-time pipeline health, success rates, current latencies
- **Analysis:** Historical trends, P95/P99 latencies, throughput patterns

## Dashboard Layout

All rows visible without scrolling on 1080p+ displays.

```
┌─────────────────────────────────────────────────────────────────┐
│ ROW 1: Pipeline Health (4 panels, ~80px height)                 │
│ [Success Rate] [Latency by Stage] [Active Traces] [Error Count] │
├─────────────────────────────────────────────────────────────────┤
│ ROW 2: Service Health (4 panels, ~80px height)                  │
│ [Service Status] [Request Rate] [Error Rate] [P95 Latency]      │
├─────────────────────────────────────────────────────────────────┤
│ ROW 3: Business Metrics (4 panels, ~80px height)                │
│ [Events Processed] [Detections/min] [Cost/Analysis] [Queues]    │
├─────────────────────────────────────────────────────────────────┤
│ ROW 4: Auto-loaded Traces (~200px height)                       │
│ [Latest Error Trace (if any)] [Latest Pipeline Run]             │
├─────────────────────────────────────────────────────────────────┤
│ ROW 5: Debug Suite (~400px height)                              │
│ [Trace Table] [Latency Histogram] [Service Map] [Error Panel]   │
└─────────────────────────────────────────────────────────────────┘
```

## Row Specifications

### Row 1: Pipeline Health

| Panel | Type | Query | Thresholds |
|-------|------|-------|------------|
| Success Rate | Stat + gauge | % traces without errors (1h) | Green ≥95%, Yellow ≥80%, Red <80% |
| Latency by Stage | Bar gauge | P95 latency per operation | Per-stage thresholds |
| Active Traces | Stat + sparkline | Traces started in last 5min | N/A |
| Error Count | Stat | Error traces in last 1h | Green =0, Yellow 1-5, Red >5 |

**Latency by Stage breakdown:**
- `detection_processing` → "Detection"
- `analysis_processing` → "Enrichment"
- `llm_inference` → "LLM"

### Row 2: Service Health

| Panel | Type | Query | Thresholds |
|-------|------|-------|------------|
| Service Status | Stat + value mapping | Traces received in last 5min | Healthy/Degraded/Down |
| Request Rate | Stat + sparkline | Traces per minute (1h) | N/A |
| Error Rate | Stat + gauge | (errors/total) × 100 | Green <1%, Yellow <5%, Red ≥5% |
| P95 Latency | Stat + sparkline | 95th percentile duration | Based on expected pipeline time |

### Row 3: Business Metrics

| Panel | Type | Query | Source |
|-------|------|-------|--------|
| Events Processed | Stat + sparkline | Completed analysis_processing traces | Jaeger |
| Detections/min | Stat + sparkline | detection_processing rate | Jaeger |
| Cost per Analysis | Stat | hsi_cost_per_event_usd | Prometheus |
| Queue Depths | Bar gauge | detection + analysis queue depths | Prometheus |

### Row 4: Auto-loaded Traces

| Panel | Width | Query | Behavior |
|-------|-------|-------|----------|
| Latest Error Trace | 50% | Most recent trace with error=true | Shows "No errors" if none |
| Latest Pipeline Run | 50% | Most recent analysis_processing | Full pipeline waterfall |

Both use Grafana's native Jaeger trace visualization with clickable spans.

### Row 5: Debug Suite

| Panel | Position | Type | Content |
|-------|----------|------|---------|
| Recent Traces Table | Left 50% | Table | Last 20 pipeline traces, filterable |
| Latency Distribution | Top-right 25% | Histogram | Duration distribution with P50/P95/P99 |
| Service Dependency Map | Middle-right 25% | Node graph | Service connections from traces |
| Error Traces Panel | Bottom-right 25% | Table | All errors in last 1h |

## Data Sources

- **Jaeger** (primary): All trace data, service dependencies
- **Prometheus**: Queue depths, costs, existing HSI metrics

## Frontend Integration

Update `TracingPage.tsx` to load the dashboard:
```typescript
const getDashboardUrl = () => {
  return `${grafanaUrl}/d/hsi-tracing/hsi-distributed-tracing?orgId=1&kiosk=1&theme=dark&refresh=30s`;
};
```

## Configuration

- **Default time range:** Last 1 hour
- **Auto-refresh:** 30 seconds
- **Theme:** Dark (matches frontend)
- **Kiosk mode:** Enabled (hides Grafana chrome)

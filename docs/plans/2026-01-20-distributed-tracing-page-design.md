# Distributed Tracing Page Design

**Date:** 2026-01-20
**Status:** Approved
**Author:** Claude (with Mike Svoboda)

## Overview

Add a dedicated Distributed Tracing page to the frontend that embeds Grafana's Explore view with Jaeger as the datasource. This provides unified trace visualization with consistent dark theme styling and rich metric correlations.

## Goals

1. Integrate distributed tracing into the main application UI
2. Match the look and feel of existing pages (dark theme, consistent header pattern)
3. Maximize value by correlating traces with 50+ Prometheus metrics
4. Provide trace comparison capability via Grafana split view
5. Keep Jaeger UI accessible as power-user fallback

## Architecture Decision

**Chosen Approach:** Option D - Keep Jaeger + Add as Grafana Datasource

### Why This Approach

| Alternative                | Reason Not Chosen                                             |
| -------------------------- | ------------------------------------------------------------- |
| Iframe Jaeger directly     | Light theme only, no metric correlation                       |
| Native React components    | High development effort, reinventing wheel                    |
| Replace with Grafana Tempo | Infrastructure migration risk, lose Jaeger's trace comparison |

### Benefits of Chosen Approach

- Zero infrastructure migration (Jaeger stays as-is)
- Consistent dark theme via Grafana
- 50+ trace-to-metric correlations
- Split view for trace comparison
- Jaeger UI remains accessible for power users

## Technical Design

### 1. Infrastructure Changes

#### Grafana Datasource Configuration

**File:** `monitoring/grafana/provisioning/datasources/prometheus.yml`

Add Jaeger datasource with comprehensive metric correlations:

```yaml
- name: Jaeger
  type: jaeger
  access: proxy
  url: http://jaeger:16686
  isDefault: false
  editable: false
  jsonData:
    nodeGraph:
      enabled: true
    tracesToMetrics:
      datasourceUid: 'prometheus'
      spanStartTimeShift: '-5m'
      spanEndTimeShift: '5m'
      tags:
        - key: 'service.name'
          value: 'service'
        - key: 'db.system'
          value: 'db_system'
        - key: 'http.method'
          value: 'method'
        - key: 'http.status_code'
          value: 'status_code'
      queries:
        # Pipeline Health
        - name: 'Pipeline Errors/min'
          query: 'rate(hsi_pipeline_errors_total[1m]) * 60'
        - name: 'Detection Queue Depth'
          query: 'hsi_detection_queue_depth'
        - name: 'Analysis Queue Depth'
          query: 'hsi_analysis_queue_depth'
        - name: 'Circuit Breaker State'
          query: 'hsi_circuit_breaker_state'
        - name: 'System Health'
          query: 'hsi_system_healthy_healthy'

        # AI Service Latencies
        - name: 'RT-DETR Latency (p95)'
          query: 'histogram_quantile(0.95, rate(rtdetr_inference_latency_seconds_bucket[5m]))'
        - name: 'Nemotron Tokens/sec'
          query: 'hsi_nemotron_tokens_per_second'
        - name: 'Florence Latency (p95)'
          query: 'histogram_quantile(0.95, rate(florence_inference_latency_seconds_bucket[5m]))'
        - name: 'CLIP Latency (p95)'
          query: 'histogram_quantile(0.95, rate(clip_inference_latency_seconds_bucket[5m]))'
        - name: 'Enrichment Latency (p95)'
          query: 'histogram_quantile(0.95, rate(enrichment_inference_latency_seconds_bucket[5m]))'

        # Batch Processing
        - name: 'Batch Latency (avg)'
          query: 'hsi_batch_latency_avg_ms'
        - name: 'Batch Latency (p95)'
          query: 'hsi_batch_latency_p95_ms'
        - name: 'Batch Latency (p99)'
          query: 'hsi_batch_latency_p99_ms'
        - name: 'Detect Latency (p95)'
          query: 'hsi_detect_latency_p95_ms'
        - name: 'Analyze Latency (p95)'
          query: 'hsi_analyze_latency_p95_ms'

        # Database Performance
        - name: 'DB Query Latency (p95)'
          query: 'histogram_quantile(0.95, rate(hsi_db_query_duration_seconds_bucket[5m]))'
        - name: 'Slow Queries/min'
          query: 'rate(hsi_slow_queries_total[1m]) * 60'
        - name: 'Database Health'
          query: 'hsi_database_healthy_healthy'

        # Redis/Cache Performance
        - name: 'Redis Commands/sec'
          query: 'rate(redis_commands_processed_total[1m])'
        - name: 'Redis Memory MB'
          query: 'redis_memory_used_bytes / 1024 / 1024'
        - name: 'Cache Hit Rate %'
          query: '100 * hsi_cache_hits_total / (hsi_cache_hits_total + hsi_cache_misses_total)'
        - name: 'Redis Clients'
          query: 'redis_connected_clients'
        - name: 'Redis Health'
          query: 'hsi_redis_healthy_healthy'

        # GPU Metrics
        - name: 'GPU Utilization %'
          query: 'hsi_gpu_utilization'
        - name: 'GPU Temperature C'
          query: 'hsi_gpu_temperature'
        - name: 'GPU Memory Used MB'
          query: 'hsi_gpu_memory_used_mb'
        - name: 'GPU Memory Total MB'
          query: 'hsi_gpu_memory_total_mb'
        - name: 'GPU Power Watts'
          query: 'hsi_gpu_power_limit_watts'

        # LLM/Nemotron Specific
        - name: 'LLM Context Utilization %'
          query: '100 * hsi_llm_context_utilization_sum / hsi_llm_context_utilization_count'
        - name: 'Prompt Tokens (avg)'
          query: 'hsi_prompt_tokens_sum / hsi_prompt_tokens_count'
        - name: 'Prompts Truncated/min'
          query: 'rate(hsi_prompts_truncated_total[1m]) * 60'
        - name: 'High Utilization Prompts/min'
          query: 'rate(hsi_prompts_high_utilization_total[1m]) * 60'

        # Enrichment Model Zoo
        - name: 'Enrichment Calls/min'
          query: 'rate(hsi_enrichment_model_calls_total[1m]) * 60'
        - name: 'Enrichment Errors/min'
          query: 'rate(hsi_enrichment_model_errors_total[1m]) * 60'
        - name: 'Enrichment Success Rate %'
          query: '100 * hsi_enrichment_success_rate'
        - name: 'Partial Batches/min'
          query: 'rate(hsi_enrichment_partial_batches_total[1m]) * 60'

        # Detection Metrics
        - name: 'Detections/min'
          query: 'rate(hsi_detections_processed_total[1m]) * 60'
        - name: 'Filtered (Low Conf)/min'
          query: 'rate(hsi_detections_filtered_low_confidence_total[1m]) * 60'
        - name: 'Avg Confidence'
          query: 'hsi_detection_confidence_sum / hsi_detection_confidence_count'

        # Event Metrics
        - name: 'Events Created/min'
          query: 'rate(hsi_events_created_total[1m]) * 60'
        - name: 'High Risk Events/min'
          query: 'rate(hsi_events_by_risk_level_total{level="high"}[1m]) * 60'
        - name: 'Critical Events/min'
          query: 'rate(hsi_events_by_risk_level_total{level="critical"}[1m]) * 60'
        - name: 'Avg Risk Score'
          query: 'hsi_risk_score_sum / hsi_risk_score_count'

        # Cost Tracking
        - name: 'Daily Cost USD'
          query: 'hsi_daily_cost_usd'
        - name: 'Monthly Cost USD'
          query: 'hsi_monthly_cost_usd'
        - name: 'Cost per Detection'
          query: 'hsi_cost_per_detection_usd'
        - name: 'Cost per Event'
          query: 'hsi_cost_per_event_usd'

        # SLO Metrics
        - name: 'API Availability (1h)'
          query: '100 * hsi:api_availability:ratio_rate1h'
        - name: 'API Success Rate (5m)'
          query: '100 * hsi:api_requests:success_rate_5m'
        - name: 'Error Budget Remaining %'
          query: '100 * hsi:error_budget:api_availability_remaining'

        # Worker Pool
        - name: 'Workers Active'
          query: 'hsi_worker_active_count'
        - name: 'Workers Busy'
          query: 'hsi_worker_busy_count'
        - name: 'Workers Idle'
          query: 'hsi_worker_idle_count'
```

#### Grafana Environment Variables

**File:** `docker-compose.prod.yml` (grafana service)

```yaml
environment:
  - GF_SECURITY_ALLOW_EMBEDDING=true
  - GF_AUTH_ANONYMOUS_ENABLED=true
  - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
  - GF_EXPLORE_ENABLED=true
```

### 2. Frontend Changes

#### TracingPage Component

**File:** `frontend/src/components/tracing/TracingPage.tsx`

```tsx
/**
 * TracingPage - Distributed tracing dashboard via Grafana/Jaeger
 *
 * Embeds Grafana's Explore view with Jaeger datasource for:
 * - Trace search and visualization
 * - Service dependency graphs
 * - Trace comparison (split view)
 * - Correlation to metrics
 */

import {
  Activity,
  RefreshCw,
  ExternalLink,
  AlertCircle,
  SplitSquareHorizontal,
} from 'lucide-react';
import { useEffect, useState, useRef, useCallback } from 'react';

import { fetchConfig } from '../../services/api';
import { resolveGrafanaUrl } from '../../utils/grafanaUrl';

export default function TracingPage() {
  const [grafanaUrl, setGrafanaUrl] = useState<string>('/grafana');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [viewMode, setViewMode] = useState<'search' | 'dependencies'>('search');
  const iframeRef = useRef<HTMLIFrameElement>(null);

  // Fetch Grafana URL from config
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await fetchConfig();
        const configWithGrafana = config as typeof config & { grafana_url?: string };
        if (configWithGrafana.grafana_url) {
          const resolvedUrl = resolveGrafanaUrl(configWithGrafana.grafana_url);
          setGrafanaUrl(resolvedUrl);
        }
        setIsLoading(false);
      } catch (err) {
        console.error('Failed to fetch config:', err);
        setError('Failed to load configuration. Using default Grafana URL.');
        setIsLoading(false);
      }
    };
    void loadConfig();
  }, []);

  // Handle refresh
  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    if (iframeRef.current) {
      const currentSrc = iframeRef.current.src;
      iframeRef.current.src = '';
      setTimeout(() => {
        if (iframeRef.current) {
          iframeRef.current.src = currentSrc;
        }
        setIsRefreshing(false);
      }, 100);
    } else {
      setIsRefreshing(false);
    }
  }, []);

  // Construct Grafana Explore URL
  const getExploreUrl = () => {
    const baseParams = 'orgId=1&kiosk=1&theme=dark';
    const jaegerQuery = encodeURIComponent(
      JSON.stringify({
        datasource: 'Jaeger',
        queries: [
          {
            refId: 'A',
            queryType: viewMode === 'search' ? 'search' : 'dependencyGraph',
            service: 'nemotron-backend',
          },
        ],
      })
    );
    return `${grafanaUrl}/explore?${baseParams}&left=${jaegerQuery}`;
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#121212] p-8" data-testid="tracing-loading">
        <div className="mx-auto max-w-[1920px]">
          <div className="mb-8">
            <div className="h-10 w-72 animate-pulse rounded-lg bg-gray-800"></div>
            <div className="mt-2 h-5 w-96 animate-pulse rounded-lg bg-gray-800"></div>
          </div>
          <div className="h-[calc(100vh-200px)] animate-pulse rounded-lg bg-gray-800"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#121212]" data-testid="tracing-page">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-gray-800 px-8 py-4">
        <div className="flex items-center gap-3">
          <Activity className="h-8 w-8 text-[#76B900]" />
          <h1 className="text-page-title">Distributed Tracing</h1>
        </div>

        <div className="flex items-center gap-3">
          {/* View Mode Toggle */}
          <div className="flex rounded-lg bg-gray-800 p-1">
            <button
              onClick={() => setViewMode('search')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                viewMode === 'search' ? 'bg-[#76B900] text-black' : 'text-gray-400 hover:text-white'
              }`}
              data-testid="view-mode-search"
            >
              Trace Search
            </button>
            <button
              onClick={() => setViewMode('dependencies')}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                viewMode === 'dependencies'
                  ? 'bg-[#76B900] text-black'
                  : 'text-gray-400 hover:text-white'
              }`}
              data-testid="view-mode-dependencies"
            >
              Service Map
            </button>
          </div>

          {/* Compare Traces */}
          <a
            href={`${grafanaUrl}/explore?orgId=1&theme=dark&split=true`}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            data-testid="compare-traces-link"
          >
            <SplitSquareHorizontal className="h-4 w-4" />
            Compare Traces
          </a>

          {/* Open Jaeger */}
          <a
            href="http://localhost:16686"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700"
            data-testid="jaeger-external-link"
          >
            <ExternalLink className="h-4 w-4" />
            Open Jaeger
          </a>

          {/* Refresh */}
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 rounded-lg bg-gray-800 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 disabled:opacity-50"
            data-testid="tracing-refresh-button"
          >
            <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div
          className="mx-8 mt-4 flex items-center gap-3 rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-4"
          data-testid="tracing-error"
        >
          <AlertCircle className="h-5 w-5 text-yellow-500" />
          <span className="text-sm text-yellow-200">{error}</span>
        </div>
      )}

      {/* Grafana iframe */}
      <iframe
        ref={iframeRef}
        src={getExploreUrl()}
        className="h-[calc(100vh-73px)] w-full border-0"
        title="Distributed Tracing"
        data-testid="tracing-iframe"
      />
    </div>
  );
}
```

#### Module Export

**File:** `frontend/src/components/tracing/index.ts`

```tsx
export { default as TracingPage } from './TracingPage';
```

#### Route Configuration

**File:** `frontend/src/App.tsx`

```tsx
// Add lazy import (after OperationsPage)
const TracingPage = lazy(() =>
  import('./components/tracing').then((module) => ({ default: module.TracingPage }))
);

// Add route (after /operations)
<Route path="/tracing" element={<TracingPage />} />;
```

#### Navigation Configuration

**File:** `frontend/src/components/layout/sidebarNav.ts`

```tsx
// Add import
import { Activity } from 'lucide-react';

// Update OPERATIONS group
{
  id: 'operations',
  label: 'OPERATIONS',
  defaultExpanded: false,
  items: [
    { id: 'jobs', label: 'Jobs', icon: Briefcase, path: '/jobs' },
    { id: 'operations', label: 'Pipeline', icon: Workflow, path: '/operations' },
    { id: 'tracing', label: 'Tracing', icon: Activity, path: '/tracing' },
    { id: 'logs', label: 'Logs', icon: ScrollText, path: '/logs' },
  ],
},
```

### 3. Testing

#### Unit Tests

**File:** `frontend/src/components/tracing/TracingPage.test.tsx`

See Section 5 of the brainstorming session for complete test implementation covering:

- Rendering states (loading, loaded, error)
- View mode toggle functionality
- External links (Compare Traces, Open Jaeger)
- Refresh functionality
- Config loading and error handling
- Iframe URL construction

## File Summary

| File                                                         | Action | Lines Changed |
| ------------------------------------------------------------ | ------ | ------------- |
| `monitoring/grafana/provisioning/datasources/prometheus.yml` | Edit   | +120          |
| `docker-compose.prod.yml`                                    | Edit   | +4            |
| `frontend/src/components/tracing/TracingPage.tsx`            | Create | ~180          |
| `frontend/src/components/tracing/TracingPage.test.tsx`       | Create | ~120          |
| `frontend/src/components/tracing/index.ts`                   | Create | ~1            |
| `frontend/src/components/layout/sidebarNav.ts`               | Edit   | +2            |
| `frontend/src/App.tsx`                                       | Edit   | +4            |

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        YOUR APP                                 │
├─────────────────────────────────────────────────────────────────┤
│  Sidebar              │  TracingPage                            │
│  ───────              │  ───────────                            │
│  OPERATIONS           │  ┌───────────────────────────────────┐  │
│  ├─ Jobs              │  │ [Search|Map] [Compare] [Jaeger]   │  │
│  ├─ Pipeline          │  ├───────────────────────────────────┤  │
│  ├─ Tracing  ◄────────┼──│                                   │  │
│  └─ Logs              │  │   Grafana Explore (iframe)        │  │
│                       │  │   with Jaeger datasource          │  │
│                       │  │                                   │  │
│                       │  │   Click span → 50+ metrics        │  │
│                       │  └───────────────────────────────────┘  │
└───────────────────────┴─────────────────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
        ┌──────────┐         ┌──────────┐         ┌──────────┐
        │  Jaeger  │ ◄────── │ Grafana  │ ──────► │Prometheus│
        │  :16686  │  query  │  :3002   │  query  │  :9090   │
        └──────────┘         └──────────┘         └──────────┘
              ▲
              │ OTLP traces
        ┌─────┴─────┐
        │  Backend  │
        │  (OTEL)   │
        └───────────┘
```

## Success Criteria

1. TracingPage renders with dark theme matching existing pages
2. Grafana Explore iframe loads with Jaeger datasource
3. View mode toggle switches between trace search and service map
4. Compare Traces link opens Grafana split view
5. Open Jaeger link opens native Jaeger UI
6. Clicking a span shows 50+ correlated Prometheus metrics
7. All unit tests pass with >80% coverage
8. Navigation item appears in Operations group

# System Components Directory

## Purpose

Contains React components for comprehensive system observability and monitoring features. These components display real-time system metrics, GPU statistics, service health, container status, database metrics, and pipeline performance across a redesigned multi-panel dashboard interface with visual pipeline flow and infrastructure grid.

## Files

Most `.tsx` files here have a co-located `.test.tsx`. Exceptions: `GPUHistoryPanel.tsx` and `PerformanceHistoryPanel.tsx` are covered through `SystemMonitoringPage.test.tsx`, and `WorkerStatusPanel.tsx` has no test coverage yet.

| File                              | Purpose                                              |
| --------------------------------- | ---------------------------------------------------- |
| `CircuitBreakerPanel.tsx`         | Circuit breaker states for resilience                |
| `CollapsibleSection.tsx`          | Collapsible section wrapper component                |
| `ContainersPanel.tsx`             | Container status and metrics                         |
| `DatabasesPanel.tsx`              | PostgreSQL and Redis metrics                         |
| `DebugModeToggle.tsx`             | Toggle for debug mode settings                       |
| `FileOperationsPanel.tsx`         | File operations status panel                         |
| `GPUHistoryPanel.tsx`             | GPU utilization/temperature/memory over time         |
| `HostSystemPanel.tsx`             | Host OS and hardware metrics                         |
| `KubernetesProbesPanel.tsx`       | Liveness/readiness probe status                      |
| `PerformanceHistoryPanel.tsx`     | GPU/CPU/RAM history chart with time range            |
| `PipelineFlowVisualization.tsx`   | Visual pipeline stages with worker status            |
| `PipelineLatencyHistoryPanel.tsx` | Per-stage latency history (averages and percentiles) |
| `PipelineMetricsPanel.tsx`        | Queue depths and latency percentiles                 |
| `PrometheusMonitoringPanel.tsx`   | Prometheus target health summary                     |
| `QueueMetricsPanel.tsx`           | Live queue depth/throughput from WebSocket events    |
| `ServicesPanel.tsx`               | Services status panel                                |
| `SeverityConfigPanel.tsx`         | Severity threshold configuration                     |
| `SystemHealthIndicator.tsx`       | Compact health badge used in headers                 |
| `SystemMonitoringPage.tsx`        | Main system monitoring page                          |
| `SystemMonitoringPage.test.tsx`   | Full-page integration test                           |
| `TimeRangeSelector.tsx`           | Time range selection for metrics                     |
| `WebSocketHealthPanel.tsx`        | WebSocket broadcaster health and circuit state       |
| `WorkerActionConfirmDialog.tsx`   | Confirm dialog for stop/restart worker actions       |
| `WorkerCard.tsx`                  | Single worker status card (NEM-4831)                 |
| `WorkerManagementPanel.tsx`       | Supervisor status plus worker start/stop/restart     |
| `WorkerStatusPanel.tsx`           | Read-only background worker status display           |
| `index.ts`                        | Barrel exports                                       |

> **Deleted in #3471** ("remove orphaned Infrastructure page and components"):
> `AiModelsPanel`, `BackgroundJobsPanel`, `InfrastructureStatusGrid`,
> `ModelZooPanel`, `PerformanceAlerts`, `SystemSummaryRow`. Do not resurrect
> them from this document — the Model Zoo table now lives at
> `frontend/src/components/settings/ModelZooPanel.tsx`, and
> `SystemMonitoringPage` composes the panels listed above instead.

## Key Components

### SystemMonitoringPage.tsx

**Purpose:** The `/operations` route. Composes collapsible panels over a
telemetry + readiness + circuit-breaker polling loop.

**Key Features:**

- Polls telemetry, readiness, config, and circuit breakers
- Sections gated by `useSystemPageSections` so users can show/hide panels
- Debug mode toggle (visible only when the backend runs with `DEBUG=true`)
- Loading skeleton states and an error state with a reload button

Sections rendered (from the page's own imports): `PipelineFlowVisualization`,
`GPUHistoryPanel`, `PerformanceHistoryPanel`, `PipelineLatencyHistoryPanel`,
`QueueMetricsPanel`, `DatabasesPanel`, `ServicesPanel`, `ContainersPanel`,
`HostSystemPanel`, `CircuitBreakerPanel`, `WebSocketHealthPanel`,
`PrometheusMonitoringPanel`, `KubernetesProbesPanel`, `FileOperationsPanel`,
`WorkerManagementPanel`, `WorkerStatusPanel`, and `BatchStatisticsDashboard`
(from `../batch`).

**No props** - Top-level page component

---

### PipelineFlowVisualization.tsx

**Purpose:** Visual representation of the AI processing pipeline with stage metrics and worker status

**Key Features:**

- 4 pipeline stages: File Watch, Detection, Batch, Analysis
- Per-stage metrics: throughput, queue depth, latency
- Background worker status indicators
- Total pipeline latency display (avg, p95, p99)
- Expandable worker details section
- Color-coded health based on baseline comparisons

**Props Interface:**

```typescript
interface PipelineFlowVisualizationProps {
  stages: PipelineStageData[];
  workers: BackgroundWorkerStatus[];
  totalLatency: TotalLatency;
  baselineLatencies?: BaselineLatencies;
  isLoading?: boolean;
  error?: string | null;
  className?: string;
}
```

---

### PipelineMetricsPanel.tsx

**Purpose:** Detailed pipeline metrics with queue depths and latency percentiles

**Key Features:**

- Detection and analysis queue depths
- Stage latencies (P50, P95, P99)
- Throughput metrics
- Time series charts

---

### CircuitBreakerPanel.tsx

**Purpose:** Displays circuit breaker states for system resilience

**Key Features:**

- Shows state for each circuit breaker (closed, open, half-open)
- Failure counts and thresholds
- Last state change timestamp
- Color-coded indicators

---

### WorkerStatusPanel.tsx

**Purpose:** Read-only view of pipeline worker health, driven entirely by
WebSocket events (NEM-3127, NEM-3402). It does not poll a REST endpoint.

**Key Features:**

- Subscribes through `useWorkerStatusWebSocket`; no timer, no fetch
- Overall pipeline health badge: `PipelineHealthStatus` of `healthy` /
  `warning` / `error` / `unknown`
- One card per reported worker with states `running`, `stopped`, `error`,
  `starting`
- A connection indicator (Wi-Fi icon) distinguishes "all workers down" from
  "we lost the WebSocket"

**Props:**

```typescript
interface WorkerStatusPanelProps {
  className?: string;
  'data-testid'?: string;
}
```

The worker roster is not enumerated here — it comes from the backend
supervisor. `WorkerManagementPanel.tsx` (NEM-4831) is the interactive
counterpart: it reads `GET /api/system/supervisor` and offers
start/stop/restart through `POST /api/system/supervisor/workers/{name}/{action}`,
with `WorkerActionConfirmDialog` guarding the destructive ones.

---

### HostSystemPanel.tsx

**Purpose:** Displays host operating system and hardware metrics

**Key Features:**

- CPU utilization
- Memory usage (used/total, percentage)
- Disk usage with progress bar (color-coded by threshold)
- System uptime display
- Hostname and OS version
- Healthy / Warning / Critical status badge

This is a presentational component: it renders the `metrics` prop and fetches
nothing itself.

**Props:**

```typescript
interface HostSystemPanelProps {
  metrics: HostSystemMetrics | null;
  stats?: SystemStats | null; // provides uptime
  osInfo?: string;
  hostname?: string;
  isLoading?: boolean;
  error?: string | null;
  className?: string;
}
```

---

### ContainersPanel.tsx

**Purpose:** Displays Podman container status and resource usage

**Key Features:**

- Polls `fetchContainerServices(category)` on `pollingInterval` (default 30s)
- Per-container card: state, image, CPU, memory, uptime, health-check status,
  restart count
- Category summary bar (infrastructure / ai / monitoring) with running totals

**Props:**

```typescript
interface ContainersPanelProps {
  pollingInterval?: number; // ms, default 30000
  category?: ContainerCategory; // infrastructure | ai | monitoring
  className?: string;
  'data-testid'?: string;
}
```

---

### DatabasesPanel.tsx

**Purpose:** Displays PostgreSQL and Redis database metrics

**Key Features:**

- PostgreSQL metrics:
  - Connection count (active/max)
  - Database size
  - Transaction rate
- Redis metrics:
  - Memory usage
  - Connected clients
  - Operations per second
  - Cache hit rate
- Connection status indicators
- Performance warnings for threshold breaches
- `debugMode` reveals extra Redis detail from `/api/debug/redis/info`

**Props:**

```typescript
interface DatabasesPanelProps {
  postgresql: DatabaseMetrics | null;
  redis: RedisMetrics | null;
  timeRange: string;
  history: DatabaseHistoryData;
  className?: string;
  'data-testid'?: string;
  debugMode?: boolean;
  redisDebugInfo?: RedisInfo | null;
}
```

---

### TimeRangeSelector.tsx

**Purpose:** Toggle button group for selecting a history window

**Key Features:**

- Preset ranges: 5m, 15m, 60m
- Callback on selection change, with the current selection highlighted

**Props:**

```typescript
interface TimeRangeSelectorProps {
  selectedRange: TimeRange;
  onRangeChange: (range: TimeRange) => void;
  className?: string;
}

// from ../../types/performance
type TimeRange = '5m' | '15m' | '60m';
```

---

### index.ts

**Barrel exports** (the authoritative list; the page itself imports its panels
directly rather than through the barrel):

```typescript
(SystemMonitoringPage,
  TimeRangeSelector,
  DatabasesPanel,
  PipelineMetricsPanel,
  CircuitBreakerPanel,
  ServicesPanel,
  SeverityConfigPanel,
  FileOperationsPanel,
  HostSystemPanel,
  ContainersPanel,
  WorkerStatusPanel(+WorkerStatusPanelNamed),
  QueueMetricsPanel);
```

Components not in the barrel — `PipelineFlowVisualization`,
`GPUHistoryPanel`, `PerformanceHistoryPanel`, `PipelineLatencyHistoryPanel`,
`PrometheusMonitoringPanel`, `KubernetesProbesPanel`, `WebSocketHealthPanel`,
`WorkerManagementPanel`, `WorkerCard`, `WorkerActionConfirmDialog`,
`CollapsibleSection`, `DebugModeToggle`, `SystemHealthIndicator` — are
imported by path where they're used.

## Types

### TimeRange

```typescript
// types/performance.ts
type TimeRange = '5m' | '15m' | '60m';
```

### HealthStatus

```typescript
// types/websocket.ts
type HealthStatus = 'healthy' | 'degraded' | 'unhealthy';
```

`PipelineHealthStatus` (from `hooks/useWorkerStatusWebSocket`) is a separate
four-value union: `healthy | warning | error | unknown`.

## Related Hooks

The panels use TanStack Query hooks in `frontend/src/hooks/`, imported by
path. The ones that matter here:

| Hook                                                                                                           | Used by                       |
| -------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| `useGPUMetricsHistory`                                                                                         | `GPUHistoryPanel`             |
| `usePerformanceHistory`                                                                                        | `PerformanceHistoryPanel`     |
| `usePipelineLatencyHistory`                                                                                    | `PipelineLatencyHistoryPanel` |
| `useQueueMetricsWebSocket`                                                                                     | `QueueMetricsPanel`           |
| `useWorkerStatusWebSocket`                                                                                     | `WorkerStatusPanel`           |
| `useSupervisorStatus`, `useWorkerActions`, `useRestartHistory`                                                 | worker management panels      |
| `useServiceStatus`, `useServiceMutations`                                                                      | `ServicesPanel`               |
| `useMonitoringHealth`                                                                                          | `SystemHealthIndicator`       |
| `useSystemPageSections`, `useSystemConfigQuery`, `useDebugQueries`, `usePerformanceMetrics`, `useLocalStorage` | `SystemMonitoringPage`        |

(`useGpuHistory` also exists and backs `dashboard/GpuStats`, but the panels in
this directory use `useGPUMetricsHistory`.)

## Design Decisions

### Native Tremor Charts vs Grafana Embeds

We chose native Tremor charts because:

1. No authentication complexity
2. No CSP/iframe issues
3. Tremor already in frontend stack
4. Backend already has metrics endpoints

### Grafana Link

Instead of embedding Grafana panels, we provide a simple link to standalone Grafana for users who want detailed historical analysis and custom queries.

## Styling

- Dark theme with NVIDIA branding
- Page background: `bg-[#121212]`; panels use the shared `#1A1A1A` panel tone
- Primary accent: `#76B900` (NVIDIA Green)
- Tremor `emerald` for positive metrics, `yellow`/`red` for degraded and
  critical states

## Backend Endpoints Reached

Confirmed in `backend/api/routes/`:

- `GET /api/system/health` and `GET /api/system/health/live` (sub-500ms liveness) and `GET /api/system/health/ready` - service health and worker readiness
- `GET /api/system/health/websocket` - `WebSocketHealthPanel`
- `GET /api/system/telemetry` - queue depths and latency percentiles
- `GET /api/system/circuit-breakers` - `CircuitBreakerPanel`
- `GET /api/system/config` - debug-mode and Grafana URL config
- `GET /api/system/services` - `ServicesPanel` / `ContainersPanel` (`backend/api/routes/services.py`)
- `GET /api/system/gpu/history`, `GET /api/system/performance/history`, `GET /api/system/pipeline-latency/history` - the history panels
- `GET /api/system/supervisor` and `POST /api/system/supervisor/workers/{name}/{start|stop|restart}` - `WorkerManagementPanel`
- `GET /api/system/storage`, `GET /api/system/jobs` - file operations and job panels

## Testing

Every component here has a co-located `*.test.tsx`. Run the directory in one
shot:

```bash
cd frontend && npm test -- src/components/system/
```

## Entry Points

**Start here:** `SystemMonitoringPage.tsx` - composes everything else.
**Then explore:** `PipelineFlowVisualization.tsx` - visual pipeline with stage metrics
**Also see:** `WorkerManagementPanel.tsx` - supervisor status and worker control
**Also see:** `CircuitBreakerPanel.tsx` - circuit breaker resilience patterns

## Dependencies

- `@tremor/react` - `Card`, `Callout`, `Title`, `Text`, `Badge`, `Button`, `AreaChart`, `ProgressBar`
- `lucide-react` - icons
- `clsx` - conditional class composition
- `../../hooks/*` - the query/WebSocket hooks listed above
- `../../services/api` - typed REST client

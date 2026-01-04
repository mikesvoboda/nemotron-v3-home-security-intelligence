# System Components Directory

## Purpose

Contains React components for comprehensive system observability and monitoring features. These components display real-time system metrics, GPU statistics, service health, container status, database metrics, and pipeline performance across a redesigned multi-panel dashboard interface with visual pipeline flow and infrastructure grid.

## Files

| File                                     | Purpose                                            |
| ---------------------------------------- | -------------------------------------------------- |
| `SystemMonitoringPage.tsx`               | Main system monitoring page (redesigned)           |
| `SystemMonitoringPage.test.tsx`          | Test suite for SystemMonitoringPage                |
| `SystemSummaryRow.tsx`                   | Clickable summary indicators for system health     |
| `SystemSummaryRow.test.tsx`              | Test suite for SystemSummaryRow                    |
| `PipelineFlowVisualization.tsx`          | Visual pipeline stages with worker status          |
| `PipelineFlowVisualization.test.tsx`     | Test suite for PipelineFlowVisualization           |
| `InfrastructureStatusGrid.tsx`           | Grid of infrastructure cards                       |
| `InfrastructureStatusGrid.test.tsx`      | Test suite for InfrastructureStatusGrid            |
| `WorkerStatusPanel.tsx`                  | Background workers status display                  |
| `WorkerStatusPanel.test.tsx`             | Test suite for WorkerStatusPanel                   |
| `HostSystemPanel.tsx`                    | Host OS and hardware metrics                       |
| `HostSystemPanel.test.tsx`               | Test suite for HostSystemPanel                     |
| `ContainersPanel.tsx`                    | Container status and metrics                       |
| `ContainersPanel.test.tsx`               | Test suite for ContainersPanel                     |
| `DatabasesPanel.tsx`                     | PostgreSQL and Redis metrics                       |
| `DatabasesPanel.test.tsx`                | Test suite for DatabasesPanel                      |
| `AiModelsPanel.tsx`                      | AI model status and metrics                        |
| `AiModelsPanel.test.tsx`                 | Test suite for AiModelsPanel                       |
| `ModelZooPanel.tsx`                      | AI Model Zoo status table with VRAM usage          |
| `ModelZooPanel.test.tsx`                 | Test suite for ModelZooPanel                       |
| `PipelineMetricsPanel.tsx`               | Queue depths and latency percentiles               |
| `PipelineMetricsPanel.test.tsx`          | Test suite for PipelineMetricsPanel                |
| `CircuitBreakerPanel.tsx`                | Circuit breaker states for resilience              |
| `CircuitBreakerPanel.test.tsx`           | Test suite for CircuitBreakerPanel                 |
| `SeverityConfigPanel.tsx`                | Severity threshold configuration                   |
| `SeverityConfigPanel.test.tsx`           | Test suite for SeverityConfigPanel                 |
| `PerformanceAlerts.tsx`                  | Performance threshold alerts                       |
| `PerformanceAlerts.test.tsx`             | Test suite for PerformanceAlerts                   |
| `TimeRangeSelector.tsx`                  | Time range selection for metrics                   |
| `TimeRangeSelector.test.tsx`             | Test suite for TimeRangeSelector                   |
| `index.ts`                               | Barrel exports                                     |

## Key Components

### SystemMonitoringPage.tsx

**Purpose:** Comprehensive system monitoring dashboard with redesigned layout featuring summary row, pipeline visualization, and infrastructure grid

**Key Features:**

- Summary row with 5 clickable health indicators
- Visual pipeline flow with stage metrics and worker status
- Infrastructure status grid (PostgreSQL, Redis, Containers, Host, Circuit Breakers)
- AI models section with Model Zoo panel
- Time range selector for historical data
- Auto-refresh with configurable intervals
- Loading skeleton states
- Error state with reload button

**Layout:**

```
+------------------------------------------------+
|   System Monitoring        [TimeRangeSelector] |
+------------------------------------------------+
|            SystemSummaryRow                    |
|  [Overall] [GPU] [Pipeline] [AI] [Infra]      |
+------------------------------------------------+
|        PipelineFlowVisualization               |
|  Watch -> Detect -> Batch -> Analyze           |
|  (with worker status and metrics)              |
+------------------------------------------------+
|         InfrastructureStatusGrid               |
|  [PostgreSQL] [Redis] [Containers] [Host]      |
|  [Circuit Breakers]                            |
+------------------------------------------------+
|         AiModelsPanel / ModelZooPanel          |
+------------------------------------------------+
```

**No props** - Top-level page component

---

### SystemSummaryRow.tsx

**Purpose:** Horizontal row of 5 clickable summary indicators showing system health at a glance

**Key Features:**

- 5 indicators: Overall, GPU, Pipeline, AI Models, Infrastructure
- Color-coded states: healthy (green), degraded (yellow), critical (red)
- Click-to-scroll to relevant page sections
- Hover tooltips with additional metrics
- Uses hooks: useHealthStatus, useModelZooStatus, usePerformanceMetrics

**Props Interface:**

```typescript
interface SystemSummaryRowProps {
  className?: string;
  onIndicatorClick?: (sectionId: string) => void;
}
```

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

### InfrastructureStatusGrid.tsx

**Purpose:** Grid of infrastructure status cards with expandable details

**Key Features:**

- PostgreSQL: status, latency, pool usage, active queries, DB size
- Redis: status, ops/sec, memory, clients, hit rate
- Containers: running/total, per-container CPU/memory
- Host System: CPU, memory, disk usage
- Circuit Breakers: state (closed/open/half-open), failure counts

**Props Interface:**

```typescript
interface InfrastructureStatusGridProps {
  postgresql: PostgreSQLDetails;
  redis: RedisDetails;
  containers: ContainerDetails;
  host: HostDetails;
  circuitBreakers: CircuitBreakerInfo[];
  isLoading?: boolean;
  error?: string | null;
  className?: string;
}
```

---

### ModelZooPanel.tsx

**Purpose:** Displays AI Model Zoo status and VRAM usage

**Key Features:**

- VRAM budget progress bar showing current consumption
- Table of all models with status badges
- Status colors: green (loaded), yellow (loading), red (error), gray (unloaded/disabled)
- Model categories and VRAM usage per model
- Refresh button

**Props Interface:**

```typescript
interface ModelZooPanelProps {
  models: ModelStatusResponse[];
  vramStats: VRAMStats | null;
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
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

**Purpose:** Displays status of all 8 background workers with real-time polling

**Key Features:**

- Status display for all background workers:
  - GPU Monitor, Cleanup Service, System Broadcaster
  - File Watcher, Detection Worker, Analysis Worker
  - Batch Timeout Worker, Metrics Worker
- Critical worker highlighting (detection_worker, analysis_worker):
  - Special NVIDIA green border when running
  - "Critical" badge
  - Red border when stopped
- Summary badges showing running/stopped counts
- Worker descriptions and human-readable names
- Error messages for stopped workers
- Auto-polling with configurable interval (default: 10s)
- Sorted list: critical workers first, then alphabetical
- Loading skeleton and error states

**Props:**

```typescript
interface WorkerStatusPanelProps {
  /** Polling interval in milliseconds (default: 10000) */
  pollingInterval?: number;
  /** Optional callback when worker status changes */
  onStatusChange?: (workers: WorkerStatus[]) => void;
}
```

**Worker Display Names:**

| Worker Name          | Display Name         | Description                              |
| -------------------- | -------------------- | ---------------------------------------- |
| gpu_monitor          | GPU Monitor          | Monitors GPU utilization and temperature |
| cleanup_service      | Cleanup Service      | Removes old data based on retention      |
| system_broadcaster   | System Broadcaster   | Broadcasts system status via WebSocket   |
| file_watcher         | File Watcher         | Watches for new camera images            |
| detection_worker     | Detection Worker     | Processes images through RT-DETRv2       |
| analysis_worker      | Analysis Worker      | Analyzes detections with Nemotron LLM    |
| batch_timeout_worker | Batch Timeout Worker | Handles batch processing timeouts        |
| metrics_worker       | Metrics Worker       | Collects and reports pipeline metrics    |

---

### HostSystemPanel.tsx

**Purpose:** Displays host operating system and hardware metrics

**Key Features:**

- CPU utilization with core count
- Memory usage (used/total GB, percentage)
- Disk usage with progress bar (color-coded by threshold)
- Network I/O rates (bytes/sec)
- System uptime display
- Hostname and OS version
- GPU temperature and utilization (if available)
- Auto-refresh support

**Props:**

```typescript
interface HostSystemPanelProps {
  timeRange?: TimeRange;
  className?: string;
}
```

---

### ContainersPanel.tsx

**Purpose:** Displays Podman container status and resource usage

**Key Features:**

- List of all running containers
- Container status indicators (running, stopped, error)
- CPU and memory usage per container
- Container uptime
- Image name and version
- Port mappings display
- Health check status (if configured)
- Restart count tracking

**Props:**

```typescript
interface ContainersPanelProps {
  timeRange?: TimeRange;
  className?: string;
}
```

---

### DatabasesPanel.tsx

**Purpose:** Displays PostgreSQL and Redis database metrics

**Key Features:**

- PostgreSQL metrics:
  - Connection count (active/max)
  - Database size
  - Query latency
  - Transaction rate
- Redis metrics:
  - Memory usage
  - Connected clients
  - Key count
  - Operations per second
- Connection status indicators
- Performance warnings for threshold breaches

**Props:**

```typescript
interface DatabasesPanelProps {
  timeRange?: TimeRange;
  className?: string;
}
```

---

### AiModelsPanel.tsx

**Purpose:** Displays AI model status and inference metrics

**Key Features:**

- RT-DETRv2 model status and metrics:
  - Load status (loaded/unloaded/error)
  - GPU memory usage
  - Inference FPS
  - Queue depth
- Nemotron model status and metrics:
  - Load status
  - GPU memory usage
  - Inference latency
  - Queue depth
- Total GPU memory allocation
- Model warm-up status

**Props:**

```typescript
interface AiModelsPanelProps {
  className?: string;
}
```

---

### PerformanceAlerts.tsx

**Purpose:** Displays active performance alerts when thresholds are breached

**Key Features:**

- Alert severity levels (warning, critical)
- Alert types:
  - High CPU usage
  - High memory usage
  - Low disk space
  - High GPU temperature
  - Queue backlog
- Auto-dismissing alerts after resolution
- Compact alert cards with icons
- Links to relevant dashboard sections

**Props:**

```typescript
interface PerformanceAlertsProps {
  alerts?: PerformanceAlert[];
  className?: string;
}
```

---

### TimeRangeSelector.tsx

**Purpose:** Dropdown selector for historical data time ranges

**Key Features:**

- Preset time ranges: 1h, 6h, 24h, 7d
- Compact dropdown design
- Callback on selection change
- Current selection indicator

**Props:**

```typescript
interface TimeRangeSelectorProps {
  value: TimeRange;
  onChange: (range: TimeRange) => void;
  className?: string;
}

type TimeRange = '1h' | '6h' | '24h' | '7d';
```

---

### index.ts

**Barrel exports:**

```typescript
export { default as SystemMonitoringPage } from './SystemMonitoringPage';
export { default as WorkerStatusPanel } from './WorkerStatusPanel';
export { default as TimeRangeSelector } from './TimeRangeSelector';
export { default as PerformanceAlerts } from './PerformanceAlerts';
export { default as AiModelsPanel } from './AiModelsPanel';
export { default as DatabasesPanel } from './DatabasesPanel';
export { default as HostSystemPanel } from './HostSystemPanel';
export { default as ContainersPanel } from './ContainersPanel';
export { default as PipelineMetricsPanel } from './PipelineMetricsPanel';
export { default as CircuitBreakerPanel } from './CircuitBreakerPanel';
export { default as SeverityConfigPanel } from './SeverityConfigPanel';
```

**Note:** SystemSummaryRow, PipelineFlowVisualization, InfrastructureStatusGrid, and ModelZooPanel are used internally by SystemMonitoringPage and are not exported from index.ts.

## Types

### TimeRange

Time range type for historical metrics:

```typescript
type TimeRange = '1h' | '6h' | '24h' | '7d';
```

### HealthStatus

System health status type:

```typescript
type HealthStatus = 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
```

## Related Hooks

### useGpuHistory

Located in `/hooks/useGpuHistory.ts`, this hook polls GPU metrics and maintains a rolling history buffer.

```typescript
const { current, history, isLoading, error, start, stop, clearHistory } = useGpuHistory({
  pollingInterval: 5000, // ms
  maxDataPoints: 60,
  autoStart: true,
});
```

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
- Background colors: `#1A1A1A`, `#121212`
- Primary accent: `#76B900` (NVIDIA Green)
- Temperature colors: green (<70), yellow (70-80), red (>80)
- Tremor chart colors: 'emerald' for positive metrics

## API Endpoints Used

- `GET /api/system/stats` - Total cameras/events/detections/uptime
- `GET /api/system/health` - Detailed service health
- `GET /api/system/health/ready` - Worker readiness status
- `GET /api/system/telemetry` - Queue depths + latency percentiles
- `GET /api/system/gpu` - Current GPU metrics
- `GET /api/system/host` - Host system metrics
- `GET /api/system/containers` - Container status
- `GET /api/system/databases` - Database metrics

## Testing

Comprehensive test coverage:

- `SystemMonitoringPage.test.tsx` - Full page integration, new layout, panel rendering
- `SystemSummaryRow.test.tsx` - Indicator states, click handling, tooltips
- `PipelineFlowVisualization.test.tsx` - Stage rendering, worker status, latency display
- `InfrastructureStatusGrid.test.tsx` - Card rendering, expand/collapse, status colors
- `WorkerStatusPanel.test.tsx` - Worker status display, polling, critical worker highlighting
- `HostSystemPanel.test.tsx` - Host metrics display, threshold colors
- `ContainersPanel.test.tsx` - Container list, status indicators
- `DatabasesPanel.test.tsx` - PostgreSQL and Redis metrics display
- `AiModelsPanel.test.tsx` - Model status, memory usage display
- `ModelZooPanel.test.tsx` - Model table, VRAM progress bar
- `PipelineMetricsPanel.test.tsx` - Queue depths, latency charts
- `CircuitBreakerPanel.test.tsx` - Circuit breaker states, failure counts
- `SeverityConfigPanel.test.tsx` - Threshold inputs, save handling
- `PerformanceAlerts.test.tsx` - Alert rendering, severity levels
- `TimeRangeSelector.test.tsx` - Selection handling, dropdown behavior

## Entry Points

**Start here:** `SystemMonitoringPage.tsx` - Main page integrating all system monitoring features
**Then explore:** `SystemSummaryRow.tsx` - Summary indicators at page top
**Then explore:** `PipelineFlowVisualization.tsx` - Visual pipeline with stage metrics
**Then explore:** `InfrastructureStatusGrid.tsx` - Infrastructure cards grid
**Also see:** `WorkerStatusPanel.tsx` - Background worker status with critical worker highlighting
**Also see:** `ModelZooPanel.tsx` - AI Model Zoo status and VRAM usage
**Also see:** `CircuitBreakerPanel.tsx` - Circuit breaker resilience patterns

## Dependencies

- `@tremor/react` - Card, Title, Text, Badge, Metric, AreaChart, DonutChart, ProgressBar
- `lucide-react` - Server, Clock, Camera, AlertCircle, Activity, CheckCircle, XCircle, AlertTriangle, Database, Container, Cpu, HardDrive
- `clsx` - Conditional class composition
- `../../hooks/useHealthStatus` - REST API health status hook
- `../../services/api` - fetchStats, fetchTelemetry, fetchGPUStats, fetchHostMetrics, fetchContainerStatus
- `../dashboard/GpuStats` - Reused GPU stats component
- `../dashboard/PipelineQueues` - Reused queue depth component

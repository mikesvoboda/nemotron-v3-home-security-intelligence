# System Components Directory

## Purpose

Contains React components for system observability and monitoring features. These components display real-time system metrics, GPU statistics, service health, and pipeline performance.

## Files

| File                            | Purpose                             |
| ------------------------------- | ----------------------------------- |
| `SystemMonitoringPage.tsx`      | Main system monitoring page         |
| `SystemMonitoringPage.test.tsx` | Test suite for SystemMonitoringPage |
| `WorkerStatusPanel.tsx`         | Background workers status display   |
| `WorkerStatusPanel.test.tsx`    | Test suite for WorkerStatusPanel    |
| `index.ts`                      | Barrel exports                      |

## Key Components

### SystemMonitoringPage.tsx

**Purpose:** Comprehensive system monitoring dashboard aggregating metrics from multiple endpoints

**Key Features:**

- System overview: uptime, total cameras, events, detections
- Service health status with per-service breakdown
- Pipeline queue depths (detection, analysis)
- GPU statistics (reuses GpuStats component)
- Pipeline latency percentiles (avg, P95, P99)
- Auto-refresh every 5 seconds for telemetry/GPU
- Loading skeleton states
- Error state with reload button

**API Endpoints:**

- `GET /api/system/stats` - Total cameras/events/detections/uptime
- `GET /api/system/health` - Detailed service health (via useHealthStatus hook)
- `GET /api/system/telemetry` - Queue depths + latency percentiles
- `GET /api/system/gpu` - Current GPU metrics

**Layout:**

```
+----------------------------------------+
|        System Monitoring Header        |
+----------------------------------------+
| System Overview | Service Health       |
| (stats card)    | (per-service status) |
+----------------------------------------+
| Pipeline Queues |                      |
+----------------------------------------+
|          GPU Stats (2 columns)         |
+----------------------------------------+
| Latency Stats   |                      |
| (Detection/     |                      |
|  Analysis)      |                      |
+----------------------------------------+
```

**No props** - Top-level page component

## Types

### GpuMetricDataPoint

Historical GPU metric data point for time series charts:

```typescript
interface GpuMetricDataPoint {
  timestamp: string; // ISO timestamp
  utilization: number;
  memory_used: number;
  temperature: number;
}
```

### QueueStats

Pipeline queue statistics:

```typescript
interface QueueStats {
  pending: number;
  processing: number;
}
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

See `/docs/decisions/grafana-integration.md` for full context. We chose native Tremor charts because:

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

**API Integration:**

- `fetchReadiness()` - GET /api/system/health/ready

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

## Entry Points

**Start here:** `SystemMonitoringPage.tsx` - Main page integrating all system monitoring features
**Then explore:** `WorkerStatusPanel.tsx` - Background worker status with critical worker highlighting

## Dependencies

- `@tremor/react` - Card, Title, Text, Badge, Metric, AreaChart, DonutChart, ProgressBar
- `lucide-react` - Server, Clock, Camera, AlertCircle, Activity, CheckCircle, XCircle, AlertTriangle
- `clsx` - Conditional class composition
- `../../hooks/useHealthStatus` - REST API health status hook
- `../../services/api` - fetchStats, fetchTelemetry, fetchGPUStats
- `../dashboard/GpuStats` - Reused GPU stats component
- `../dashboard/PipelineQueues` - Reused queue depth component

# System Components Directory

## Purpose

Contains React components for system observability and monitoring features. These components display real-time system metrics, GPU statistics, service health, and pipeline performance.

## Files

| File                            | Purpose                             |
| ------------------------------- | ----------------------------------- |
| `SystemMonitoringPage.tsx`      | Main system monitoring page         |
| `SystemMonitoringPage.test.tsx` | Test suite for SystemMonitoringPage |
| `ObservabilityPanel.tsx`        | Observability dashboard section     |
| `ObservabilityPanel.test.tsx`   | Test suite for ObservabilityPanel   |
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

---

### ObservabilityPanel.tsx

Main component for the system observability dashboard section.

**Features:**

- GPU utilization over time (Tremor AreaChart)
- GPU memory usage (Tremor DonutChart + ProgressBar)
- GPU temperature gauge with color coding
- Pipeline queue statistics (pending/processing)
- System health status indicator
- Grafana link for detailed metrics

**Props:**

- `gpuUtilization`: Current GPU utilization percentage (0-100)
- `gpuMemoryUsed`: Current GPU memory used in MB
- `gpuMemoryTotal`: Total GPU memory in MB
- `gpuTemperature`: Current GPU temperature in Celsius
- `gpuHistory`: Array of historical GPU metrics for charts
- `queueStats`: Pipeline queue statistics (pending, processing)
- `healthStatus`: System health status ('healthy', 'degraded', 'unhealthy', 'unknown')
- `grafanaUrl`: URL for Grafana (default: 'http://localhost:3000')
- `className`: Additional CSS classes

**Usage:**

```tsx
import { ObservabilityPanel } from '@/components/system';
import { useGpuHistory, useSystemStatus } from '@/hooks';

function Dashboard() {
  const { current, history } = useGpuHistory();
  const { status } = useSystemStatus();

  return (
    <ObservabilityPanel
      gpuUtilization={current?.utilization ?? null}
      gpuMemoryUsed={current?.memory_used ?? null}
      gpuMemoryTotal={current?.memory_total ?? null}
      gpuTemperature={current?.temperature ?? null}
      gpuHistory={history}
      queueStats={{ pending: 0, processing: 0 }}
      healthStatus={status?.health ?? 'unknown'}
    />
  );
}
```

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

## Testing

Test file: `ObservabilityPanel.test.tsx`

Tests cover:

- Component rendering
- Health status display
- GPU metrics display
- Temperature color coding
- Queue statistics
- Grafana link behavior
- Edge cases (null values, zeros)

## Styling

- Dark theme with NVIDIA branding
- Background colors: `#1A1A1A`, `#121212`
- Primary accent: `#76B900` (NVIDIA Green)
- Temperature colors: green (<70), yellow (70-80), red (>80)
- Tremor chart colors: 'emerald' for positive metrics

## Integration

This component is designed to be added to the main dashboard page or as a dedicated observability section. It works alongside existing dashboard components like `GpuStats` and `RiskGauge`.

## Entry Points

**Start here:** `SystemMonitoringPage.tsx` - Main page integrating all system monitoring features
**Then explore:** `ObservabilityPanel.tsx` - Detailed observability metrics with charts

## Dependencies

- `@tremor/react` - Card, Title, Text, Badge, Metric, AreaChart, DonutChart, ProgressBar
- `lucide-react` - Server, Clock, Camera, AlertCircle, Activity, CheckCircle, XCircle, AlertTriangle
- `clsx` - Conditional class composition
- `../../hooks/useHealthStatus` - REST API health status hook
- `../../services/api` - fetchStats, fetchTelemetry, fetchGPUStats
- `../dashboard/GpuStats` - Reused GPU stats component
- `../dashboard/PipelineQueues` - Reused queue depth component

# Performance Components Directory

## Purpose

Contains React components for real-time system performance monitoring, providing comprehensive visualization of GPU metrics, AI model status, database health, host system resources, and container status. These components receive data via WebSocket from the `/ws/system` endpoint and display it using Tremor charts and custom visualizations.

## Files

| File                            | Purpose                                          |
| ------------------------------- | ------------------------------------------------ |
| `PerformanceDashboard.tsx`      | Main dashboard with metric cards grid            |
| `PerformanceDashboard.test.tsx` | Test suite for PerformanceDashboard              |
| `PerformanceCharts.tsx`         | Time-series charts for historical metrics        |
| `PerformanceCharts.test.tsx`    | Test suite for PerformanceCharts                 |
| `PerformanceAlerts.tsx`         | Active performance alerts display                |
| `PerformanceAlerts.test.tsx`    | Test suite for PerformanceAlerts                 |

## Key Components

### PerformanceDashboard.tsx

**Purpose:** Main dashboard component displaying real-time performance metrics in a card grid layout

**Key Features:**

- Time range selector (5m, 15m, 60m)
- Connection status indicator (WebSocket)
- GPU Card: utilization %, VRAM usage, temperature, power
- AI Models Card: RT-DETRv2 and Nemotron status with slots info
- Database Card: PostgreSQL connections, cache hit ratio, transactions/min
- Redis Card: memory usage, hit ratio, connected clients
- Host Card: CPU %, RAM %, disk %
- Containers Card: health status for all containers
- Auto-refresh every 5 seconds via WebSocket

**Layout:**

```
+----------------------------------------------------------+
|  System Performance          [5m][15m][60m] [Connected]  |
|  Real-time metrics updated every 5 seconds               |
+----------------------------------------------------------+
|  +---------------+  +---------------+  +---------------+ |
|  | GPU           |  | AI Models     |  | PostgreSQL    | |
|  | Util: 45%     |  | RT-DETRv2: OK |  | Conn: 12/100  | |
|  | VRAM: 8.2/24  |  | Nemotron: OK  |  | Cache: 98.2%  | |
|  | Temp: 62C     |  | Slots: 2/4    |  | Trans: 150/m  | |
|  +---------------+  +---------------+  +---------------+ |
|  +---------------+  +---------------+  +---------------+ |
|  | Redis         |  | Host System   |  | Containers    | |
|  | Mem: 256 MB   |  | CPU: 23%      |  | 6/6 Healthy   | |
|  | Hit: 95.3%    |  | RAM: 16/32 GB |  | [backend]     | |
|  | Clients: 8    |  | Disk: 45%     |  | [frontend]    | |
|  +---------------+  +---------------+  +---------------+ |
+----------------------------------------------------------+
```

**Props Interface:**

```typescript
interface PerformanceDashboardProps {
  className?: string;
}
```

---

### PerformanceCharts.tsx

**Purpose:** Time-series visualization for system performance metrics using Tremor charts

**Key Features:**

- Four chart panels:
  1. GPU Utilization (AreaChart) - GPU % and VRAM % over time
  2. Temperature (LineChart) - GPU temp with warning (75C) and critical (85C) thresholds
  3. Inference Latency (LineChart) - RT-DETRv2, Nemotron, and pipeline latencies
  4. Resource Usage (AreaChart) - CPU, RAM, Disk percentages
- Time range selection (5m, 15m, 60m)
- Connection status indicator
- Empty state placeholders when no data
- Data point count display

**Layout:**

```
+---------------------------+  +---------------------------+
|  GPU Utilization          |  |  GPU Temperature          |
|  [AreaChart]              |  |  [LineChart with          |
|  - GPU Utilization        |  |   threshold lines]        |
|  - VRAM Usage             |  |                           |
+---------------------------+  +---------------------------+
|  Inference Latency        |  |  System Resources         |
|  [LineChart]              |  |  [AreaChart]              |
|  - RT-DETRv2              |  |  - CPU                    |
|  - Nemotron               |  |  - RAM                    |
|  - Pipeline               |  |  - Disk                   |
+---------------------------+  +---------------------------+
```

**Props Interface:**

```typescript
interface PerformanceChartsProps {
  className?: string;
  timeRange?: TimeRange;
  historyData?: PerformanceUpdate[];
  hideTimeRangeSelector?: boolean;
}
```

---

### PerformanceAlerts.tsx

**Purpose:** Displays active performance alerts when thresholds are breached

**Key Features:**

- Alert severity levels (warning, critical)
- Sorted by severity (critical first)
- Alert information:
  - Metric name in human-readable format
  - Current value vs threshold
  - Alert message
- Color-coded Tremor Callout components
- Empty state when no active alerts
- Auto-formatting for different metric types (%, C, ms, MB, GB)

**Alert Types:**

- High GPU utilization
- High GPU temperature
- High CPU usage
- High memory usage
- Low disk space
- High inference latency
- Queue backlog

**Props Interface:**

```typescript
interface PerformanceAlertsProps {
  className?: string;
}
```

## Types

### TimeRange

Available time range options:

```typescript
type TimeRange = '5m' | '15m' | '60m';
```

### GpuMetrics

GPU metrics from WebSocket:

```typescript
interface GpuMetrics {
  name: string;
  utilization: number;
  vram_used_gb: number;
  vram_total_gb: number;
  temperature: number;
  power_watts: number;
}
```

### AiModelMetrics

AI model metrics (RT-DETRv2):

```typescript
interface AiModelMetrics {
  status: string;
  vram_gb: number;
  device: string;
}
```

### NemotronMetrics

Nemotron LLM metrics:

```typescript
interface NemotronMetrics {
  status: string;
  slots_active: number;
  slots_total: number;
  context_size: number;
}
```

### DatabaseMetrics

PostgreSQL metrics:

```typescript
interface DatabaseMetrics {
  status: string;
  connections_active: number;
  connections_max: number;
  cache_hit_ratio: number;
  transactions_per_min: number;
}
```

### RedisMetrics

Redis metrics:

```typescript
interface RedisMetrics {
  status: string;
  memory_mb: number;
  hit_ratio: number;
  connected_clients: number;
}
```

### HostMetrics

Host system metrics:

```typescript
interface HostMetrics {
  cpu_percent: number;
  ram_used_gb: number;
  ram_total_gb: number;
  disk_used_gb: number;
  disk_total_gb: number;
}
```

### ContainerMetrics

Container health metrics:

```typescript
interface ContainerMetrics {
  name: string;
  health: string; // 'healthy' | 'unhealthy' | 'starting'
}
```

### PerformanceAlert

Alert threshold breach:

```typescript
interface PerformanceAlert {
  severity: 'warning' | 'critical';
  metric: string;
  value: number;
  threshold: number;
  message: string;
}
```

## Related Hooks

### usePerformanceMetrics

Main hook providing all performance data from WebSocket:

```typescript
const {
  current,      // Current metrics snapshot
  history,      // Historical data by time range
  alerts,       // Active alerts
  isConnected,  // WebSocket connection status
  timeRange,    // Current time range selection
  setTimeRange, // Change time range
} = usePerformanceMetrics();
```

## Styling

- Dark theme with NVIDIA branding
- Background colors: `#1A1A1A`, `#121212`
- Primary accent: `#76B900` (NVIDIA Green)
- Tremor Card components with gray-800 borders
- Progress bar colors:
  - Green: < 80% usage
  - Yellow: 80-95% usage
  - Red: > 95% usage
- Temperature colors:
  - Green: < 70C
  - Yellow: 70-85C
  - Red: > 85C
- Chart colors:
  - GPU: emerald, blue
  - Temperature: amber (with yellow/red threshold lines)
  - Latency: cyan, violet, emerald
  - Resources: blue, amber, rose

## API Endpoints Used

- `WS /ws/system` - Real-time system metrics stream

## Entry Points

**Start here:** `PerformanceDashboard.tsx` - Main dashboard with metric cards
**Then explore:** `PerformanceCharts.tsx` - Time-series visualizations
**Also see:** `PerformanceAlerts.tsx` - Threshold breach alerts

## Dependencies

- `@tremor/react` - Card, Title, Text, ProgressBar, Badge, AreaChart, LineChart, Grid, Col, Callout
- `lucide-react` - Cpu, Brain, Database, HardDrive, Box, Thermometer, Zap, Activity, Users, Wifi, WifiOff, MemoryStick, Layers, Monitor, CheckCircle, XCircle, AlertCircle, AlertTriangle, Timer icons
- `clsx` - Conditional class composition
- `../../hooks/usePerformanceMetrics` - WebSocket data hook

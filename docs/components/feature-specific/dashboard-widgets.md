# Dashboard Widget Components

> Components for the main monitoring dashboard.

---

## Overview

The dashboard page (`DashboardPage`) is the primary interface for monitoring home security. It displays real-time camera feeds, events, system status, and AI pipeline metrics.

**Location:** `frontend/src/components/dashboard/`

---

## Page Components

### DashboardPage

Main dashboard orchestrating all widgets.

**Location:** `frontend/src/components/dashboard/DashboardPage.tsx`

**Features:**

- Responsive grid layout
- Real-time data via WebSocket
- Configurable widget visibility
- Loading and error states

**Data Dependencies:**

- `useSystemStatus()` - System health (WebSocket-based real-time updates)
- `useHealthStatusQuery()` - Service health (TanStack Query with caching)
- `useRecentEventsQuery()` - Recent events list
- `useCamerasQuery()` - Camera status and list
- `useGpuStatsQuery()` - GPU metrics (polling)
- `useGpuStatsWebSocket()` - GPU metrics (real-time WebSocket updates)

---

### DashboardLayout

Responsive layout wrapper for dashboard widgets.

**Location:** `frontend/src/components/dashboard/DashboardLayout.tsx`

**Props:**

| Prop     | Type        | Default | Description       |
| -------- | ----------- | ------- | ----------------- |
| children | `ReactNode` | -       | Widget components |

**Layout Breakpoints:**

| Breakpoint | Columns | Description             |
| ---------- | ------- | ----------------------- |
| < 640px    | 1       | Mobile - single column  |
| 640-1024px | 2       | Tablet - two columns    |
| > 1024px   | 3       | Desktop - three columns |

---

### DashboardConfigModal

Modal for configuring dashboard preferences.

**Location:** `frontend/src/components/dashboard/DashboardConfigModal.tsx`

**Props:**

| Prop    | Type                                | Default | Description      |
| ------- | ----------------------------------- | ------- | ---------------- |
| isOpen  | `boolean`                           | -       | Modal visibility |
| onClose | `() => void`                        | -       | Close handler    |
| config  | `DashboardConfig`                   | -       | Current config   |
| onSave  | `(config: DashboardConfig) => void` | -       | Save handler     |

**Configurable Options:**

- Widget visibility toggles
- Refresh intervals
- Default time range
- Display density

---

## Widget Components

### StatsRow

Key metrics cards with integrated sparklines.

**Location:** `frontend/src/components/dashboard/StatsRow.tsx`

**Displays:**

- Active cameras count
- Events today count
- Current risk level (with sparkline)
- System status indicator

**Props:**

| Prop             | Type                                                  | Default | Description                                            |
| ---------------- | ----------------------------------------------------- | ------- | ------------------------------------------------------ |
| activeCameras    | `number`                                              | -       | Number of active cameras                               |
| eventsToday      | `number`                                              | -       | Total number of events today                           |
| currentRiskScore | `number`                                              | -       | Current risk score (0-100)                             |
| systemStatus     | `'healthy' \| 'degraded' \| 'unhealthy' \| 'unknown'` | -       | System health status                                   |
| riskHistory      | `number[]`                                            | -       | Optional array of historical risk values for sparkline |
| className        | `string`                                              | `''`    | Additional CSS classes                                 |

**Usage:**

```tsx
<StatsRow
  activeCameras={7}
  eventsToday={156}
  currentRiskScore={45}
  systemStatus="healthy"
  riskHistory={[30, 35, 42, 38, 45]}
/>
```

---

### CameraGrid

Responsive camera thumbnail grid.

**Location:** `frontend/src/components/dashboard/CameraGrid.tsx`

**Props:**

| Prop       | Type                   | Default | Description            |
| ---------- | ---------------------- | ------- | ---------------------- |
| cameras    | `Camera[]`             | -       | Camera list            |
| onSelect   | `(id: string) => void` | -       | Camera select handler  |
| showStatus | `boolean`              | `true`  | Show status indicators |

**Features:**

- Live thumbnail refresh
- Online/offline status
- Last motion indicator
- Click to expand

---

### ActivityFeed

Scrolling event feed with auto-scroll.

**Location:** `frontend/src/components/dashboard/ActivityFeed.tsx`

**Props:**

| Prop         | Type                   | Default | Description               |
| ------------ | ---------------------- | ------- | ------------------------- |
| events       | `Event[]`              | -       | Recent events             |
| maxItems     | `number`               | `20`    | Max visible items         |
| autoScroll   | `boolean`              | `true`  | Auto-scroll on new events |
| onEventClick | `(id: string) => void` | -       | Event click handler       |

**Features:**

- Animated entry for new events
- Risk-colored borders
- Relative timestamps
- Click to view details

---

### GpuStats

GPU utilization metrics display.

**Location:** `frontend/src/components/dashboard/GpuStats.tsx`

**Props:**

| Prop        | Type         | Default | Description            |
| ----------- | ------------ | ------- | ---------------------- |
| gpuData     | `GpuMetrics` | -       | GPU metrics            |
| showHistory | `boolean`    | `true`  | Show utilization chart |

**Displays:**

- GPU utilization percentage
- Memory usage (used/total)
- Temperature
- Historical utilization chart

---

### PipelineQueues

AI pipeline queue depth display.

**Location:** `frontend/src/components/dashboard/PipelineQueues.tsx`

**Props:**

| Prop      | Type            | Default | Description      |
| --------- | --------------- | ------- | ---------------- |
| queues    | `QueueStatus[]` | -       | Queue metrics    |
| showAlert | `boolean`       | `true`  | Alert on backlog |

**Displays:**

- Frame capture queue
- Detection queue
- Enrichment queue
- Alert threshold indicator

---

### PipelineTelemetry

Pipeline latency and throughput metrics.

**Location:** `frontend/src/components/dashboard/PipelineTelemetry.tsx`

**Props:**

| Prop      | Type              | Default | Description        |
| --------- | ----------------- | ------- | ------------------ |
| telemetry | `PipelineMetrics` | -       | Pipeline metrics   |
| timeRange | `string`          | `1h`    | Metrics time range |

**Displays:**

- End-to-end latency (p50, p95, p99)
- Frames processed per second
- Detection success rate
- Enrichment latency

---

### SummaryCards

Summary card container for dashboard overview.

**Location:** `frontend/src/components/dashboard/SummaryCards.tsx`

**Props:**

| Prop      | Type        | Default | Description   |
| --------- | ----------- | ------- | ------------- |
| summaries | `Summary[]` | -       | Summary data  |
| isLoading | `boolean`   | `false` | Loading state |
| error     | `Error`     | -       | Error state   |

**Related Components:**

- `SummaryBulletList` - Bullet list within summary
- `SummaryCardEmpty` - Empty state
- `SummaryCardError` - Error state
- `SummaryCardSkeleton` - Loading skeleton

---

### BatchAggregatorCard

Batch processing status aggregator.

**Location:** `frontend/src/components/dashboard/BatchAggregatorCard.tsx`

**Props:**

| Prop          | Type          | Default | Description          |
| ------------- | ------------- | ------- | -------------------- |
| batchStatus   | `BatchStatus` | -       | Current batch status |
| onViewDetails | `() => void`  | -       | View details handler |

**Displays:**

- Current batch window status
- Detections aggregated
- Time remaining in window
- Batch closure reason

---

### ExpandableSummary

Expandable summary section.

**Location:** `frontend/src/components/dashboard/ExpandableSummary.tsx`

**Props:**

| Prop        | Type        | Default | Description       |
| ----------- | ----------- | ------- | ----------------- |
| title       | `string`    | -       | Section title     |
| summary     | `string`    | -       | Collapsed summary |
| children    | `ReactNode` | -       | Expanded content  |
| defaultOpen | `boolean`   | `false` | Initial state     |

---

### SeverityBadge

Severity level badge component.

**Location:** `frontend/src/components/dashboard/SeverityBadge.tsx`

**Props:**

| Prop     | Type                                           | Default | Description        |
| -------- | ---------------------------------------------- | ------- | ------------------ |
| severity | `'info' \| 'warning' \| 'error' \| 'critical'` | -       | Severity level     |
| showIcon | `boolean`                                      | `true`  | Show severity icon |

---

## Data Flow

```
WebSocket Connection
        │
        ▼
┌───────────────────┐
│  useSystemStatus  │──── System health updates
└───────────────────┘
        │
        ▼
┌───────────────────┐
│   DashboardPage   │──── Orchestrates all widgets
└───────────────────┘
        │
        ├──► StatsRow (summary metrics)
        ├──► CameraGrid (camera feeds)
        ├──► ActivityFeed (event stream)
        ├──► GpuStats (GPU metrics)
        ├──► PipelineQueues (queue depths)
        └──► PipelineTelemetry (latency/throughput)
```

---

## Refresh Patterns

| Widget            | Refresh Method    | Interval   |
| ----------------- | ----------------- | ---------- |
| StatsRow          | WebSocket push    | Real-time  |
| CameraGrid        | Thumbnail polling | 5 seconds  |
| ActivityFeed      | WebSocket push    | Real-time  |
| GpuStats          | REST polling      | 10 seconds |
| PipelineQueues    | WebSocket push    | Real-time  |
| PipelineTelemetry | REST polling      | 30 seconds |

---

## Testing

```bash
cd frontend && npm test -- --testPathPattern=dashboard
```

Test coverage includes:

- Widget rendering states (loading, error, empty, data)
- User interactions (expand, collapse, select)
- Real-time updates via mocked WebSocket
- Responsive layout behavior
- Accessibility compliance

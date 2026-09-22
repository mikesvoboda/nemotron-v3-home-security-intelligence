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
- `useRecentEventsQuery()` - Recent events list
- `useEventStream()` - Live events over WebSocket
- `useSceneChangeEvents()` - Scene-change event stream
- `useThreatDetection()` - Active threat detection state
- `useSummaries()` - Hourly/daily AI summaries
- `useAIMetrics()` - AI pipeline metrics
- `useDateRangeState()` - Shared date-range filter state
- Cameras and event stats load in `useEffect` via `fetchCameras()` and `fetchEventStats()` from `services/api`

---

### DashboardLayout

Responsive layout wrapper for dashboard widgets. Takes a `widgetProps` bag plus one render function per widget (`renderStatsRow`, `renderAISummaryRow?`, `renderCameraGrid`, `renderActivityFeed`, `renderGpuStats`, `renderPipelineTelemetry`, ...), so the layout stays agnostic of data fetching.

**Location:** `frontend/src/components/dashboard/DashboardLayout.tsx`

**Layout structure** (Tailwind classes on the widget containers):

- Main area (camera grid + activity feed): single column, two-column at `lg` (`lg:grid-cols-[1.5fr,1fr]`, `xl:grid-cols-[2fr,1fr]`)
- System widgets area (GPU stats, pipeline telemetry, pipeline queues): `grid-cols-1`, `sm:grid-cols-2`, `lg:grid-cols-3`

---

### DashboardConfigModal

Modal for configuring dashboard preferences.

**Location:** `frontend/src/components/dashboard/DashboardConfigModal.tsx`

**Props:**

| Prop           | Type                                | Default | Description      |
| -------------- | ----------------------------------- | ------- | ---------------- |
| isOpen         | `boolean`                           | -       | Modal visibility |
| onClose        | `() => void`                        | -       | Close handler    |
| config         | `DashboardConfig`                   | -       | Current config   |
| onConfigChange | `(config: DashboardConfig) => void` | -       | Change handler   |

**Configurable Options:**

- Widget visibility toggles (switch per widget)

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

| Prop                   | Type                                        | Default | Description                                        |
| ---------------------- | ------------------------------------------- | ------- | -------------------------------------------------- |
| cameras                | `CameraStatus[]`                            | -       | Camera list                                        |
| selectedCameraId       | `string`                                    | -       | Currently selected camera                          |
| onCameraClick          | `(cameraId: string) => void`                | -       | Camera select handler                              |
| enableWebSocketUpdates | `boolean`                                   | `false` | Real-time camera status via WebSocket              |
| onCameraStatusChange   | `(event: CameraStatusEventPayload) => void` | -       | Callback on WebSocket status change                |
| sceneChangeActivityIds | `Set<string> \| string[]`                   | -       | Cameras with recent scene-change activity          |
| cameraActivityMap      | `Record<string, CameraActivityState>`       | -       | Per-camera activity state for the richer indicator |
| enableSnapshotRefresh  | `boolean`                                   | `true`  | Show per-card snapshot refresh button              |
| onSnapshotRefresh      | `(cameraId: string) => void`                | -       | Snapshot refresh handler                           |
| className              | `string`                                    | -       | Additional CSS classes                             |

**Features:**

- Thumbnail per camera (loaded for online/recording cameras; placeholder otherwise)
- Online/offline status
- Manual snapshot refresh button per card (NEM-4947)
- Optional real-time status updates (NEM-2295)

---

### ActivityFeed

Scrolling event feed with auto-scroll.

**Location:** `frontend/src/components/dashboard/ActivityFeed.tsx`

**Props:**

| Prop         | Type                        | Default | Description               |
| ------------ | --------------------------- | ------- | ------------------------- |
| events       | `ActivityEvent[]`           | -       | Recent events             |
| maxItems     | `number`                    | `10`    | Max visible items         |
| autoScroll   | `boolean`                   | `true`  | Auto-scroll on new events |
| onEventClick | `(eventId: string) => void` | -       | Event click handler       |
| showHeader   | `boolean`                   | `true`  | Show the feed header      |
| className    | `string`                    | -       | Additional CSS classes    |

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

All metric props are optional overrides — the widget fetches its own data via `useGpuStatsQuery` (polling, 5 s) and `useGpuHistoryQuery`, and renders the passed values until data arrives.

| Prop                | Type                        | Default | Description                                       |
| ------------------- | --------------------------- | ------- | ------------------------------------------------- |
| gpuName             | `string \| null`            | -       | GPU device name (e.g. `NVIDIA RTX A5500`)         |
| utilization         | `number \| null`            | -       | GPU utilization 0-100% (initial/override display) |
| memoryUsed          | `number \| null`            | -       | Memory used in MB                                 |
| memoryTotal         | `number \| null`            | -       | Memory total in MB                                |
| temperature         | `number \| null`            | -       | Temperature in Celsius                            |
| powerUsage          | `number \| null`            | -       | Power usage in Watts                              |
| inferenceFps        | `number \| null`            | -       | Inference FPS                                     |
| statsQueryOptions   | `UseGpuStatsQueryOptions`   | -       | Options for the GPU stats query hook              |
| historyQueryOptions | `UseGpuHistoryQueryOptions` | -       | Options for the GPU history query hook            |
| timeRange           | `TimeRange`                 | -       | Historical data range (`5m` / `15m` / `60m`)      |
| historyData         | `GPUStatsSample[]`          | -       | External history data (bypasses internal query)   |
| className           | `string`                    | -       | Additional CSS classes                            |

**Displays:**

- GPU utilization percentage
- Memory usage (used/total)
- Temperature
- Power usage and inference FPS
- Historical utilization chart

---

### PipelineQueues

AI pipeline queue depth display.

**Location:** `frontend/src/components/dashboard/PipelineQueues.tsx`

**Props:**

| Prop             | Type                           | Default | Description                                        |
| ---------------- | ------------------------------ | ------- | -------------------------------------------------- |
| detectionQueue   | `number`                       | -       | Detection queue depth (fallback value)             |
| analysisQueue    | `number`                       | -       | Analysis queue depth (fallback value)              |
| queuesStatus     | `QueuesStatusResponse \| null` | -       | Detailed status from `useQueuesStatus` (preferred) |
| isLoading        | `boolean`                      | -       | Queue status loading state                         |
| warningThreshold | `number`                       | `10`    | Depth above which a warning is shown               |
| className        | `string`                       | -       | Additional CSS classes                             |

**Displays:**

- Detection queue depth
- Analysis queue depth
- Warning indicator when a queue exceeds `warningThreshold`

---

### PipelineTelemetry

Pipeline latency and throughput metrics.

**Location:** `frontend/src/components/dashboard/PipelineTelemetry.tsx`

**Props:**

The widget fetches its own telemetry (polling, default 5 s) — it takes no metrics prop.

| Prop                    | Type     | Default | Description                                  |
| ----------------------- | -------- | ------- | -------------------------------------------- |
| pollingInterval         | `number` | `5000`  | Telemetry polling interval in ms             |
| queueWarningThreshold   | `number` | `10`    | Queue depth above which a warning is shown   |
| latencyWarningThreshold | `number` | `10000` | Latency in ms above which a warning is shown |
| className               | `string` | -       | Additional CSS classes                       |

**Displays:**

- Processing latency (avg, p95, p99) per pipeline stage
- Throughput history
- Queue depth with warning thresholds

---

### SummaryCards

Summary card container for dashboard overview.

**Location:** `frontend/src/components/dashboard/SummaryCards.tsx`

**Props:**

| Prop         | Type                         | Default | Description                      |
| ------------ | ---------------------------- | ------- | -------------------------------- |
| hourly       | `Summary \| null`            | -       | Hourly summary data              |
| daily        | `Summary \| null`            | -       | Daily summary data               |
| isLoading    | `boolean`                    | -       | Loading state                    |
| error        | `Error \| null`              | -       | Error state                      |
| onRetry      | `() => void`                 | -       | Retry after error                |
| isRetrying   | `boolean`                    | -       | Retry in progress                |
| onViewFull   | `(summary: Summary) => void` | -       | "View Full Summary" handler      |
| onViewEvents | `() => void`                 | -       | Navigate to events (empty state) |

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

| Prop       | Type                     | Default | Description                          |
| ---------- | ------------------------ | ------- | ------------------------------------ |
| batchState | `BatchAggregatorUIState` | -       | Batch state from `usePipelineStatus` |
| isLoading  | `boolean`                | -       | Loading state                        |
| className  | `string`                 | -       | Additional CSS classes               |

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

| Prop            | Type                          | Default | Description                        |
| --------------- | ----------------------------- | ------- | ---------------------------------- |
| summary         | `Summary`                     | -       | The summary data to display        |
| defaultExpanded | `boolean`                     | -       | Whether the card starts expanded   |
| onExpandChange  | `(expanded: boolean) => void` | -       | Fired when expansion state changes |
| summaryType     | `'hourly' \| 'daily'`         | -       | Used for unique ARIA ID generation |
| className       | `string`                      | -       | Additional CSS classes             |

---

### SeverityBadge

Severity level badge component.

**Location:** `frontend/src/components/dashboard/SeverityBadge.tsx`

**Props:**

| Prop      | Type                                               | Default | Description                         |
| --------- | -------------------------------------------------- | ------- | ----------------------------------- |
| level     | `SeverityLevel` (`clear/low/medium/high/critical`) | -       | Severity level to display           |
| count     | `number`                                           | -       | Event count to show                 |
| pulsing   | `boolean`                                          | -       | Pulsing animation (critical alerts) |
| size      | `'sm' \| 'md'`                                     | -       | Size variant                        |
| className | `string`                                           | -       | Additional CSS classes              |

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

| Widget            | Refresh Method                                                                                          | Interval                     |
| ----------------- | ------------------------------------------------------------------------------------------------------- | ---------------------------- |
| StatsRow          | `/ws/system` push (`useSystemStatus`) + event stats queries                                             | System channel cadence (5 s) |
| CameraGrid        | Manual per-card snapshot refresh (`onSnapshotRefresh`); optional WebSocket status updates               | On demand                    |
| ActivityFeed      | `/ws/events` push (`useEventStream`)                                                                    | Real-time                    |
| GpuStats          | `useGpuStatsQuery` polling (`statsQueryOptions.refetchInterval`)                                        | 5 s default                  |
| PipelineQueues    | `queuesStatus` from `useQueuesStatus` polling, else the `detectionQueue`/`analysisQueue` fallback props | 5 s default                  |
| PipelineTelemetry | `fetchTelemetry` polling (`pollingInterval`)                                                            | 5 s default                  |

---

## Testing

```bash
cd frontend && npm test -- src/components/dashboard
```

Test coverage includes:

- Widget rendering states (loading, error, empty, data)
- User interactions (expand, collapse, select)
- Real-time updates via mocked WebSocket
- Responsive layout behavior
- Accessibility compliance

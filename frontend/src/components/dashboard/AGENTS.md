# Dashboard Components Directory

## Purpose

Contains all components for the main security dashboard page, including risk visualization, camera status displays, activity feeds, GPU monitoring, and pipeline status. These components provide real-time monitoring and status at a glance.

## Files

| File                                    | Purpose                                                  |
| --------------------------------------- | -------------------------------------------------------- |
| `ActivityFeed.tsx`                      | Scrolling feed of recent events                          |
| `ActivityFeed.test.tsx`                 | Test suite for ActivityFeed                              |
| `CameraGrid.tsx`                        | Responsive grid of camera thumbnails                     |
| `CameraGrid.test.tsx`                   | Test suite for CameraGrid                                |
| `DashboardConfigModal.tsx`              | Modal for dashboard configuration settings               |
| `DashboardConfigModal.test.tsx`         | Test suite for DashboardConfigModal                      |
| `DashboardLayout.tsx`                   | Responsive layout wrapper for dashboard widgets          |
| `DashboardLayout.test.tsx`              | Test suite for DashboardLayout                           |
| `DashboardPage.tsx`                     | Main dashboard page orchestrating all widgets            |
| `DashboardPage.test.tsx`                | Test suite for DashboardPage                             |
| `ExpandableSummary.tsx`                 | Expandable summary section with toggle                   |
| `ExpandableSummary.test.tsx`            | Test suite for ExpandableSummary                         |
| `GpuStats.tsx`                          | GPU metrics with utilization history                     |
| `GpuStats.test.tsx`                     | Test suite for GpuStats                                  |
| `PipelineQueues.tsx`                    | AI pipeline queue depth display                          |
| `PipelineQueues.test.tsx`               | Test suite for PipelineQueues                            |
| `PipelineTelemetry.tsx`                 | Pipeline latency and throughput metrics                  |
| `PipelineTelemetry.test.tsx`            | Test suite for PipelineTelemetry                         |
| `SeverityBadge.tsx`                     | Severity level badge component                           |
| `SeverityBadge.test.tsx`                | Test suite for SeverityBadge                             |
| `StatsRow.tsx`                          | Key metrics summary cards with integrated risk sparkline |
| `StatsRow.test.tsx`                     | Test suite for StatsRow                                  |
| `SummaryBulletList.tsx`                 | Bullet list component for AI summaries                   |
| `SummaryBulletList.test.tsx`            | Test suite for SummaryBulletList                         |
| `SummaryCardEmpty.tsx`                  | Empty state for summary cards                            |
| `SummaryCardEmpty.test.tsx`             | Test suite for SummaryCardEmpty                          |
| `SummaryCardError.tsx`                  | Error state for summary cards                            |
| `SummaryCardError.test.tsx`             | Test suite for SummaryCardError                          |
| `SummaryCards.tsx`                      | Summary cards container component                        |
| `SummaryCards.test.tsx`                 | Test suite for SummaryCards                              |
| `SummaryCards.a11y.test.tsx`            | Accessibility tests for SummaryCards                     |
| `SummaryCards.integration.test.tsx`     | Integration tests for SummaryCards                       |
| `SummaryCardsIntegration.test.tsx`      | Additional integration tests                             |
| `SummaryCardSkeleton.tsx`               | Loading skeleton for summary cards                       |
| `SummaryCardSkeleton.test.tsx`          | Test suite for SummaryCardSkeleton                       |
| `index.ts`                              | Barrel exports for dashboard components                  |

## Key Components

### DashboardPage.tsx

**Purpose:** Main dashboard page that orchestrates all dashboard components

**Layout:**

```
+--------------------------------------------------+
|                 Security Dashboard               |
|            (header + subtitle)                   |
+--------------------------------------------------+
|  StatsRow (4 cards: cameras, events, risk with   |
|            sparkline, status)                    |
+--------------------------------------------------+
|              CameraGrid (Camera Status)          |
+--------------------------------------------------+
```

**Data Flow:**

1. **Initial Load:** Fetches cameras, GPU stats, events, and event stats via REST API
2. **Real-time Updates:** Subscribes to WebSocket for events and system status
3. **Polling:** GPU stats polled every 5 seconds
4. **Merging:** WebSocket events merged with initial events (deduplication by ID)

**State Management:**

```typescript
// REST API data
const [cameras, setCameras] = useState<Camera[]>([]);
const [gpuStats, setGpuStats] = useState<GPUStats | null>(null);
const [initialEvents, setInitialEvents] = useState<Event[]>([]);
const [eventStats, setEventStats] = useState<EventStatsResponse | null>(null);

// WebSocket hooks
const { events: wsEvents } = useEventStream();
const { status: systemStatus } = useSystemStatus();
```

**Key Calculations:**

- `currentRiskScore` - Latest event's risk score (or 0)
- `riskHistory` - Last 10 events' risk scores for sparkline
- `activeCamerasCount` - Cameras with status 'online'
- `eventsToday` - Stats API count + new WebSocket events from today

**Loading/Error States:**

- Loading: Skeleton screens for all widgets
- Error: Red error card with reload button

**No props** - Top-level page component

---

### CameraGrid.tsx

**Purpose:** Responsive grid of camera cards with status indicators

**Props Interface:**

```typescript
interface CameraGridProps {
  cameras: CameraStatus[];
  selectedCameraId?: string;
  onCameraClick?: (cameraId: string) => void;
  className?: string;
}

interface CameraStatus {
  id: string;
  name: string;
  status: 'online' | 'offline' | 'error' | 'recording' | 'unknown';
  thumbnail_url?: string;
  last_seen_at?: string;
}
```

**Key Features:**

- Responsive grid: 1 col (mobile) -> 2 (sm) -> 3 (lg) -> 4 (xl)
- Status indicator badges with color-coded dots
- Thumbnail with loading skeleton and error fallback
- Click handler for camera selection
- Selected camera highlighting with green border and glow
- Empty state with "No cameras configured" message

**Status Colors:**

| Status    | Color  | Icon     |
| --------- | ------ | -------- |
| online    | green  | Camera   |
| recording | yellow | Video    |
| offline   | gray   | VideoOff |
| error     | red    | VideoOff |
| unknown   | gray   | Camera   |

**CameraCard Subcomponent:**

- Handles individual camera rendering
- Image loading state with skeleton
- Image error fallback to icon placeholder
- Last seen timestamp formatting

---

### ActivityFeed.tsx

**Purpose:** Scrolling feed of recent security events with auto-scroll capability

**Props Interface:**

```typescript
interface ActivityFeedProps {
  events: ActivityEvent[];
  maxItems?: number; // Default: 10
  onEventClick?: (eventId: string) => void;
  autoScroll?: boolean; // Default: true
  className?: string;
}

interface ActivityEvent {
  id: string;
  timestamp: string;
  camera_name: string;
  risk_score: number;
  summary: string;
  thumbnail_url?: string;
}
```

**Key Features:**

- Real-time event display with newest at bottom
- Auto-scroll toggle (Pause/Resume button)
- Click events to open detail view
- Thumbnail with fallback placeholder
- RiskBadge with score display
- Relative timestamps ("5 mins ago")
- Footer showing count ("Showing 10 of 45 events")
- Empty state with camera icon

**Auto-scroll Behavior:**

- Scrolls to bottom when new events arrive
- Only if autoScroll is enabled
- Tracks previous event count to detect new arrivals

**Timestamp Formatting:**

| Time Difference | Display         |
| --------------- | --------------- |
| < 1 minute      | Just now        |
| 1 minute        | 1 min ago       |
| < 60 minutes    | X mins ago      |
| 1 hour          | 1 hour ago      |
| < 24 hours      | X hours ago     |
| >= 24 hours     | Jan 15, 3:45 PM |

---

### GpuStats.tsx

**Purpose:** Display GPU metrics in a dashboard card with utilization history and interactive controls

**Props Interface:**

```typescript
interface GpuStatsProps {
  gpuName?: string | null; // GPU device name (e.g., 'NVIDIA RTX A5500')
  utilization?: number | null; // 0-100% (optional, for initial/override)
  memoryUsed?: number | null; // MB (optional, for initial/override)
  memoryTotal?: number | null; // MB (optional, for initial/override)
  temperature?: number | null; // Celsius (optional, for initial/override)
  powerUsage?: number | null; // Watts (optional)
  inferenceFps?: number | null; // FPS (optional, for initial/override)
  className?: string;
  historyOptions?: UseGpuHistoryOptions; // Options for GPU history hook
  showHistoryControls?: boolean; // Show start/stop/clear buttons (default: true)
}
```

**Key Features:**

- Uses Tremor Card, ProgressBar, Title, Text, AreaChart, TabGroup, TabList, Tab components
- Displays: GPU name, utilization %, memory (GB), temperature (C), power (W), inference FPS
- Tabbed history charts: Utilization, Temperature, Memory
- Real-time data via `useGpuHistory` hook with polling
- Start/stop/clear controls for history collection
- Color-coded temperature and power thresholds
- Handles null values gracefully with "N/A"
- Falls back to props when hook data unavailable

**Temperature Color Coding:**

| Temperature | Color  |
| ----------- | ------ |
| < 70C       | green  |
| 70-80C      | yellow |
| > 80C       | red    |

**Power Usage Color Coding:**

| Power    | Color  |
| -------- | ------ |
| < 150W   | green  |
| 150-250W | yellow |
| > 250W   | red    |

**History Chart Tabs:**

- **Utilization** - GPU usage % over time (emerald color)
- **Temperature** - Temperature C over time (amber color)
- **Memory** - Memory GB over time (blue color)

**History Controls:**

- Pause/Resume button to toggle polling
- Clear button to reset history data
- Data point count indicator

**Dependencies:**

- `@tremor/react` - Card, ProgressBar, Title, Text, AreaChart, TabGroup, TabList, Tab
- `../../hooks/useGpuHistory` - GPU metrics polling and history collection

---

### StatsRow.tsx

**Purpose:** Display key metrics in the dashboard header as a responsive grid with integrated risk sparkline

**Props Interface:**

```typescript
interface StatsRowProps {
  activeCameras: number;
  eventsToday: number;
  currentRiskScore: number;
  systemStatus: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  riskHistory?: number[]; // Optional array of historical risk values for sparkline
  className?: string;
}
```

**Key Features:**

- Four stat cards in responsive grid, all clickable with navigation
- Color-coded risk level using utils/risk with integrated sparkline
- System status with pulse animation when healthy
- NVIDIA dark theme styling
- SVG sparkline showing risk history (when 2+ data points provided)

**Cards:**

| Card           | Icon     | Color        | Navigates To |
| -------------- | -------- | ------------ | ------------ |
| Active Cameras | Camera   | NVIDIA green | /settings    |
| Events Today   | Calendar | blue         | /timeline    |
| Current Risk   | Shield   | (by level)   | /alerts      |
| System Status  | Activity | (by status)  | /system      |

**Risk Sparkline:**

- Displayed next to risk score when `riskHistory` has 2+ values
- Color matches current risk level (green/yellow/orange/red)
- SVG with filled area and line path
- Hidden from accessibility tree (decorative)

**System Status Colors:**

| Status    | Color  | Animation     |
| --------- | ------ | ------------- |
| healthy   | green  | animate-pulse |
| degraded  | yellow | none          |
| unhealthy | red    | none          |
| unknown   | gray   | none          |

---

### PipelineQueues.tsx

**Purpose:** Display AI processing pipeline queue depths

**Props Interface:**

```typescript
interface PipelineQueuesProps {
  detectionQueue: number;
  analysisQueue: number;
  warningThreshold?: number; // Default: 10
  className?: string;
}
```

**Key Features:**

- Shows queue depth for RT-DETRv2 detection and Nemotron analysis
- Warning indicators when queues exceed threshold
- Color-coded badges (gray/green/yellow/red)
- Warning alert when queues are backing up

**Queue Status Colors:**

| Depth | Color  |
| ----- | ------ |
| 0     | gray   |
| 1-5   | green  |
| 6-10  | yellow |
| > 10  | red    |

**Dependencies:**

- `@tremor/react` - Card, Title, Text, Badge

---

### PipelineTelemetry.tsx

**Purpose:** Display pipeline latency and throughput metrics with time series charts

**Props Interface:**

```typescript
interface PipelineTelemetryProps {
  className?: string;
}
```

**Key Features:**

- Pipeline latency percentiles (P50, P95, P99) for detection and analysis stages
- Throughput metrics (events/second, detections/second)
- Time series charts showing historical performance
- Auto-refresh with configurable poll interval
- Loading skeleton and error states
- Color-coded performance indicators (green/yellow/red thresholds)

**Metrics Displayed:**

| Metric Category | Values Shown               |
| --------------- | -------------------------- |
| Detection       | P50, P95, P99 latency      |
| Analysis        | P50, P95, P99 latency      |
| Throughput      | Events/sec, Detections/sec |

**API Integration:**

- `GET /api/system/telemetry` - Fetch pipeline metrics

**Dependencies:**

- `@tremor/react` - Card, Title, Text, AreaChart, Badge
- `lucide-react` - Activity, Clock icons

## Important Patterns

### Data Transformation

DashboardPage transforms API data to component-specific formats:

```typescript
// Camera[] -> CameraStatus[]
const cameraStatuses: CameraStatus[] = cameras.map((camera) => ({
  id: camera.id,
  name: camera.name,
  status: camera.status,
  thumbnail_url: getCameraSnapshotUrl(camera.id),
  last_seen_at: camera.last_seen_at,
}));

// SecurityEvent[] -> ActivityEvent[]
const activityEvents: ActivityEvent[] = mergedEvents.map((event) => ({
  id: String(event.id),
  timestamp: event.timestamp ?? event.started_at,
  camera_name: cameraNameMap.get(event.camera_id) ?? 'Unknown Camera',
  risk_score: event.risk_score,
  summary: event.summary,
}));
```

### Real-time Updates

- WebSocket hooks provide live data (`useEventStream`, `useSystemStatus`)
- Components receive updated props via React re-renders
- Event merging avoids duplicates between REST and WebSocket data

### Loading States

- DashboardPage shows skeleton screens during initial load
- Individual components handle null/missing data gracefully
- Error states with retry capability

### Responsive Design

- Mobile-first grid layouts with Tailwind breakpoints
- Components adapt to container size
- Fixed height containers with overflow scroll where appropriate

## Testing

All components have comprehensive test files:

- `DashboardPage.test.tsx` - Full integration test, data fetching, loading/error states
- `CameraGrid.test.tsx` - Grid layout, status indicators, click handling, empty state
- `ActivityFeed.test.tsx` - Auto-scroll, pause/resume, event rendering, empty state
- `GpuStats.test.tsx` - Tremor components, temperature colors, null handling, history chart
- `StatsRow.test.tsx` - Stat cards, status colors, risk level display, sparkline rendering
- `PipelineQueues.test.tsx` - Queue badges, warning states, thresholds
- `PipelineTelemetry.test.tsx` - Latency charts, throughput display, auto-refresh

## Component Hierarchy

```
DashboardPage
├── StatsRow (with integrated risk sparkline)
├── CameraGrid
│   └── CameraCard (per camera)
└── ActivityFeed (optional)
    └── RiskBadge (from common/)
```

## Dependencies

- `@tremor/react` - Card, ProgressBar, Title, Text, Badge, AreaChart
- `lucide-react` - Various icons
- `clsx` - Conditional class composition
- `react` - useState, useEffect, useRef, useMemo
- `../../hooks` - useEventStream, useSystemStatus
- `../../services/api` - fetchCameras, fetchGPUStats, fetchEvents, fetchEventStats, fetchGpuHistory
- `../../utils/risk` - getRiskColor, getRiskLabel, getRiskLevel
- `../common/RiskBadge` - Risk level badge

## Entry Points

**Start here:** `DashboardPage.tsx` - Full dashboard composition and data flow
**Then explore:** `StatsRow.tsx` - Key metrics with integrated SVG sparkline
**Also see:** `ActivityFeed.tsx` - Real-time feed patterns
**Monitoring:** `GpuStats.tsx` - GPU metrics and history display

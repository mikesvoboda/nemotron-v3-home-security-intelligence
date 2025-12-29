# Dashboard Components Directory

## Purpose

Contains all components for the main security dashboard page, including risk visualization, camera status displays, activity feeds, GPU monitoring, and pipeline status. These components provide real-time monitoring and status at a glance.

## Files

| File                    | Purpose                                       |
| ----------------------- | --------------------------------------------- |
| `DashboardPage.tsx`     | Main dashboard page orchestrating all widgets |
| `RiskGauge.tsx`         | Circular SVG gauge for risk score             |
| `CameraGrid.tsx`        | Responsive grid of camera thumbnails          |
| `ActivityFeed.tsx`      | Scrolling feed of recent events               |
| `GpuStats.tsx`          | GPU metrics with utilization history          |
| `StatsRow.tsx`          | Key metrics summary cards                     |
| `PipelineQueues.tsx`    | AI pipeline queue depth display               |
| `RiskGauge.example.tsx` | Example usage for RiskGauge                   |

## Key Components

### DashboardPage.tsx

**Purpose:** Main dashboard page that orchestrates all dashboard components

**Layout:**

```
+--------------------------------------------------+
|                 Security Dashboard               |
|            (header + subtitle)                   |
+--------------------------------------------------+
|  StatsRow (4 cards: cameras, events, risk, status) |
+--------------------------------------------------+
|    RiskGauge Card     |      GpuStats Card      |
|   (Current Risk)      |    (GPU Statistics)     |
+--------------------------------------------------+
|              CameraGrid (Camera Status)          |
+--------------------------------------------------+
|              ActivityFeed (Live Activity)        |
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

### RiskGauge.tsx

**Purpose:** Circular SVG gauge displaying risk score (0-100) with animated transitions

**Props Interface:**

```typescript
interface RiskGaugeProps {
  value: number; // Risk score 0-100
  history?: number[]; // Historical values for sparkline
  size?: 'sm' | 'md' | 'lg'; // Default: 'md'
  showLabel?: boolean; // Show risk level label (default: true)
  className?: string;
}
```

**Key Features:**

- Animated circular progress using SVG stroke-dasharray
- Color-coded by risk level (green/yellow/orange/red)
- Glow filter effect on high/critical levels
- Optional sparkline chart showing risk history
- ARIA meter role for accessibility

**Size Configurations:**

| Size | Dimensions | Stroke | Font Size |
| ---- | ---------- | ------ | --------- |
| sm   | 120px      | 8px    | 20px      |
| md   | 160px      | 12px   | 28px      |
| lg   | 200px      | 16px   | 36px      |

**Risk Level Colors:**

| Score Range | Level    | Color   |
| ----------- | -------- | ------- |
| 0-25        | low      | #76B900 |
| 26-50       | medium   | #FFB800 |
| 51-75       | high     | #E74856 |
| 76-100      | critical | #ef4444 |

**Animation:**

- 1 second smooth transition on value changes
- Uses setInterval for 60fps animation
- Skipped in test environment for instant updates

**Dependencies:**

- `../../utils/risk` - getRiskColor, getRiskLabel, getRiskLevel

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

**Purpose:** Display GPU metrics in a dashboard card with utilization history

**Props Interface:**

```typescript
interface GpuStatsProps {
  utilization: number | null; // 0-100%
  memoryUsed: number | null; // MB
  memoryTotal: number | null; // MB
  temperature: number | null; // Celsius
  inferenceFps: number | null;
  className?: string;
}
```

**Key Features:**

- Uses Tremor Card, ProgressBar, Title, Text, AreaChart components
- Displays: utilization %, memory (GB), temperature (C), inference FPS
- GPU utilization history chart (fetched on mount)
- Color-coded temperature thresholds
- Handles null values gracefully with "N/A"

**Temperature Color Coding:**

| Temperature | Color  |
| ----------- | ------ |
| < 70C       | green  |
| 70-80C      | yellow |
| > 80C       | red    |

**History Chart:**

- Fetches last 100 GPU samples on mount
- Displays as Tremor AreaChart
- Loading/error/empty states handled

**Dependencies:**

- `@tremor/react` - Card, ProgressBar, Title, Text, AreaChart
- `../../services/api` - fetchGpuHistory

---

### StatsRow.tsx

**Purpose:** Display key metrics in the dashboard header as a responsive grid

**Props Interface:**

```typescript
interface StatsRowProps {
  activeCameras: number;
  eventsToday: number;
  currentRiskScore: number;
  systemStatus: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  className?: string;
}
```

**Key Features:**

- Four stat cards in responsive grid
- Color-coded risk level using utils/risk
- System status with pulse animation when healthy
- NVIDIA dark theme styling

**Cards:**

| Card           | Icon     | Color        |
| -------------- | -------- | ------------ |
| Active Cameras | Camera   | NVIDIA green |
| Events Today   | Calendar | blue         |
| Current Risk   | Shield   | (by level)   |
| System Status  | Activity | (by status)  |

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

### RiskGauge.example.tsx

**Purpose:** Example usage and documentation for RiskGauge component

Shows various configurations:

- All size variants (sm, md, lg)
- With and without history sparkline
- Different risk levels

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
- `RiskGauge.test.tsx` - SVG rendering, animations, color coding, sparkline
- `CameraGrid.test.tsx` - Grid layout, status indicators, click handling, empty state
- `ActivityFeed.test.tsx` - Auto-scroll, pause/resume, event rendering, empty state
- `GpuStats.test.tsx` - Tremor components, temperature colors, null handling, history chart
- `StatsRow.test.tsx` - Stat cards, status colors, risk level display
- `PipelineQueues.test.tsx` - Queue badges, warning states, thresholds

## Component Hierarchy

```
DashboardPage
├── StatsRow
├── RiskGauge (wrapped in Card)
├── GpuStats
├── CameraGrid
│   └── CameraCard (per camera)
└── ActivityFeed
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
**Then explore:** `RiskGauge.tsx` - SVG visualization techniques
**Also see:** `ActivityFeed.tsx` - Real-time feed patterns
**Monitoring:** `GpuStats.tsx` - GPU metrics and history display

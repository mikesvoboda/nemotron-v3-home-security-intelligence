# Dashboard Components Directory

## Purpose

Contains all components for the main security dashboard page, including risk visualization, camera status displays, activity feeds, and GPU monitoring. These components provide real-time monitoring and status at a glance.

## Key Components

### DashboardPage.tsx

**Purpose:** Main dashboard page that orchestrates all dashboard components

**Key Features:**

- Fetches initial data from REST API (cameras, GPU stats)
- Subscribes to WebSocket streams for real-time updates (events, system status)
- Grid layout: RiskGauge + GpuStats (top row), CameraGrid (middle), ActivityFeed (bottom)
- Loading skeletons during initial data fetch
- Error boundary with reload button
- Polls GPU stats every 5 seconds
- Max width: 1920px, centered layout

**Data Flow:**

- REST API: `fetchCameras()`, `fetchGPUStats()`
- WebSocket: `useEventStream()`, `useSystemStatus()`
- Transforms API data to component-specific formats

**No props** - Top-level page component

### RiskGauge.tsx

**Purpose:** Circular SVG gauge displaying risk score (0-100) with animated transitions

**Key Features:**

- Animated circular progress indicator with smooth transitions
- Color-coded risk levels: green (0-25 low), yellow (26-50 medium), orange (51-75 high), red (76-100 critical)
- Optional sparkline chart showing risk history
- Three size variants: sm (120px), md (160px), lg (200px)
- Glow filter effect on high/critical risk levels
- ARIA meter role for accessibility

**Props:**

- `value: number` - Risk score 0-100 (required)
- `history?: number[]` - Historical risk values for sparkline
- `size?: 'sm' | 'md' | 'lg'` - Default: 'md'
- `showLabel?: boolean` - Show risk level label (Low/Medium/High/Critical)
- `className?: string` - Additional CSS classes

**Helper Functions:**

- `generateSparklinePath()` - Creates SVG path for sparkline visualization
- Uses `getRiskColor()`, `getRiskLabel()`, `getRiskLevel()` from utils/risk

### CameraGrid.tsx

**Purpose:** Responsive grid of camera cards with status indicators

**Key Features:**

- Responsive grid: 1 col (mobile) → 2 (tablet) → 3 (lg) → 4 (xl)
- Camera status indicators: online (green), recording (yellow), offline (red), unknown (gray)
- Thumbnail or placeholder with camera icon
- Last seen timestamp display
- Click handlers for camera selection
- Selected camera highlighting with NVIDIA green border and glow
- Empty state with "No cameras configured" message

**Props:**

- `cameras: CameraStatus[]` - Array of camera status objects (required)
- `selectedCameraId?: string` - ID of selected camera
- `onCameraClick?: (cameraId: string) => void` - Click handler
- `className?: string`

**CameraStatus Interface:**

```typescript
{
  id: string;
  name: string;
  status: 'online' | 'offline' | 'recording' | 'unknown';
  thumbnail_url?: string;
  last_seen_at?: string;
}
```

### ActivityFeed.tsx

**Purpose:** Scrolling feed of recent security events with auto-scroll capability

**Key Features:**

- Real-time event display with auto-scroll to latest
- Pause/resume auto-scroll toggle button
- Click events to open detail view
- Empty state with camera icon and message
- Thumbnail display with fallback to camera icon placeholder
- Risk badges, camera names, timestamps (relative time: "5 mins ago")
- Footer showing count (e.g., "Showing 10 of 45 events")
- Custom scrollbar styling

**Props:**

- `events: ActivityEvent[]` - Array of events (required)
- `maxItems?: number` - Maximum events to display (default: 10)
- `onEventClick?: (eventId: string) => void` - Event click handler
- `autoScroll?: boolean` - Auto-scroll to bottom (default: true)
- `className?: string`

**ActivityEvent Interface:**

```typescript
{
  id: string;
  timestamp: string;
  camera_name: string;
  risk_score: number;
  summary: string;
  thumbnail_url?: string;
}
```

### GpuStats.tsx

**Purpose:** Display GPU metrics in a dashboard card using Tremor components

**Key Features:**

- Uses Tremor Card, ProgressBar, Title, Text components
- Displays: utilization %, memory usage (GB), temperature (°C), inference FPS
- Color-coded temperature: green (<70°C), yellow (70-80°C), red (>80°C)
- Progress bars for utilization, memory, temperature
- Handles null values gracefully with "N/A" display
- Icons from lucide-react: Cpu, Thermometer, Activity, Zap

**Props:**

- `utilization: number | null` - 0-100% GPU usage
- `memoryUsed: number | null` - Used memory in MB
- `memoryTotal: number | null` - Total memory in MB
- `temperature: number | null` - Temperature in Celsius
- `inferenceFps: number | null` - Inference speed
- `className?: string`

**Helper Functions:**

- `getTemperatureColor()` - Returns Tremor color based on temp threshold
- `formatValue()` - Formats number with fallback for null
- `formatMemory()` - Formats memory as GB and calculates percentage

### StatsRow.tsx

**Purpose:** Display key metrics in the dashboard header area as a responsive grid of stat cards

**Key Features:**

- Four stat cards: Active Cameras, Events Today, Current Risk Level, System Status
- Responsive grid: 1 col (mobile) -> 2 (sm) -> 4 (lg)
- Color-coded risk level using utils/risk functions
- System status indicator with pulse animation when healthy
- Icons from lucide-react: Camera, Calendar, Shield, Activity
- NVIDIA dark theme with #1A1A1A cards and gray-800 borders

**Props:**

- `activeCameras: number` - Number of active cameras (required)
- `eventsToday: number` - Total number of events today (required)
- `currentRiskScore: number` - Risk score 0-100 (required)
- `systemStatus: 'healthy' | 'degraded' | 'unhealthy' | 'unknown'` - System health status (required)
- `className?: string` - Additional CSS classes

**System Status Colors:**

- healthy: green (with pulse animation)
- degraded: yellow
- unhealthy: red
- unknown: gray

**Usage Example:**

```tsx
<StatsRow activeCameras={4} eventsToday={23} currentRiskScore={42} systemStatus="healthy" />
```

### RiskGauge.example.tsx

**Purpose:** Example usage and documentation for RiskGauge component

- Shows all size variants, with/without history, different risk levels
- Useful for testing and visual verification

## Important Patterns

### Data Transformation

DashboardPage acts as a data adapter, transforming API responses to component-specific formats:

- `Camera[]` → `CameraStatus[]` for CameraGrid
- `SecurityEvent[]` → `ActivityEvent[]` for ActivityFeed
- Extracts risk score and history from events for RiskGauge

### Real-time Updates

- WebSocket hooks (`useEventStream`, `useSystemStatus`) provide live data
- Components receive updated props automatically via React re-renders
- Auto-scroll in ActivityFeed triggered by events length change

### Loading States

- Skeleton screens during initial data fetch
- Individual component loading states (GpuStats shows N/A for null values)
- Error states with retry buttons

### Responsive Design

- Mobile-first grid layouts with breakpoints
- Components adapt to container size
- ActivityFeed has fixed height with overflow scroll

### Styling Conventions

- Tremor components for data visualization (GpuStats)
- Custom SVG for RiskGauge (more control over animations)
- Consistent card styling: bg-[#1A1A1A], border-gray-800
- NVIDIA green (#76B900) for primary actions and healthy metrics

## Testing

All components have comprehensive test files:

- `DashboardPage.test.tsx` - Integration test of full dashboard
- `RiskGauge.test.tsx` - SVG rendering, animations, color coding, sparkline
- `CameraGrid.test.tsx` - Grid layout, status indicators, click handling
- `ActivityFeed.test.tsx` - Auto-scroll, pause/resume, event rendering
- `GpuStats.test.tsx` - Tremor components, color coding, null handling
- `StatsRow.test.tsx` - Stat cards rendering, status colors, risk levels

## Entry Points

**Start here:** `DashboardPage.tsx` - Understand the full dashboard composition and data flow
**Then explore:** `RiskGauge.tsx` - See SVG-based visualization and animation techniques
**Also see:** `StatsRow.tsx` - Simple stat cards with responsive grid layout
**Deep dive:** `ActivityFeed.tsx` - Learn real-time feed patterns and auto-scroll logic

## Dependencies

- `@tremor/react` - Card, ProgressBar, Title, Text, Badge components
- `lucide-react` - Icons for all components
- `clsx` - Conditional class name composition
- `react` - useState, useEffect, useRef hooks
- `../../hooks` - useEventStream, useSystemStatus (WebSocket hooks)
- `../../services/api` - fetchCameras, fetchGPUStats
- `../../utils/risk` - getRiskColor, getRiskLabel, getRiskLevel

## Future Enhancements

- Camera thumbnails from live video feeds
- Click-to-zoom on cameras in CameraGrid
- Export activity feed to CSV/JSON
- Customizable risk thresholds
- Historical trend charts (beyond sparkline)

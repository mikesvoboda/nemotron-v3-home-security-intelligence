# Analytics Components

## Purpose

Analytics page components for baseline analysis, anomaly detection, pipeline latency monitoring, and scene change detection. Provides insights into activity patterns, class frequency distribution, and camera tampering detection.

## Key Components

### Main Page

**AnalyticsPage.tsx** - Analytics dashboard with camera selector and baseline visualization
- Displays activity heatmaps, class frequency charts, anomaly configuration
- Includes pipeline latency monitoring and scene change detection
- Manages camera selection and data refresh
- Shows learning progress indicators (learning complete vs still learning)

**Props:**
- None (page component, uses URL parameters if needed)

**Data Flow:**
- Fetches cameras from `/api/cameras`
- Fetches activity baseline from `/api/analytics/cameras/{id}/activity-baseline`
- Fetches class baseline from `/api/analytics/cameras/{id}/class-baseline`
- Fetches anomaly config from `/api/analytics/anomaly-config`

### Visualization Components

**ActivityHeatmap.tsx** - 24x7 activity pattern heatmap
- Displays hourly activity levels across all days of the week
- Color-coded cells (green scale for normal, orange/red for peaks)
- Shows sample counts and learning progress
- Identifies peak activity hours

**Props:**
```typescript
interface ActivityHeatmapProps {
  entries: ActivityBaselineEntry[];        // Activity data by hour/day
  learningComplete: boolean;               // Whether baseline is established
  minSamplesRequired: number;              // Minimum samples per cell
}
```

**ClassFrequencyChart.tsx** - Object class frequency distribution
- Bar chart showing detection counts by object class (person, vehicle, animal, etc.)
- Highlights most common class
- Displays unique class count
- Uses Tremor BarChart component

**Props:**
```typescript
interface ClassFrequencyChartProps {
  entries: ClassBaselineEntry[];           // Class frequency data
  uniqueClasses: number;                   // Count of unique classes
  mostCommonClass: string | null;          // Most frequently detected class
}
```

**AnomalyConfigPanel.tsx** - Anomaly detection configuration
- Configure activity and class anomaly thresholds
- Enable/disable anomaly detection
- Displays current configuration status
- Save/update settings via API

**Props:**
```typescript
interface AnomalyConfigPanelProps {
  config: AnomalyConfig;                   // Current configuration
  onConfigUpdated: (config: AnomalyConfig) => void;  // Callback after update
}
```

**PipelineLatencyPanel.tsx** - AI pipeline latency monitoring
- Displays latency metrics for each pipeline stage
- Shows p50, p95, p99 percentiles
- Time-series graph of latency trends
- Configurable time ranges (1h, 6h, 24h, 7d, 30d)
- Stage breakdown: Watch→Detect, Detect→Batch, Batch→Analyze, Total

**Props:**
```typescript
interface PipelineLatencyPanelProps {
  refreshInterval?: number;                // Auto-refresh interval in ms (default: 0 = disabled)
}
```

**SceneChangePanel.tsx** - Camera tampering detection
- Lists detected scene changes (moved, rotated, obscured, different)
- Displays similarity scores and change types
- Allows acknowledging scene changes
- Shows timestamps and acknowledgement status
- Used for camera health monitoring

**Props:**
```typescript
interface SceneChangePanelProps {
  cameraId: string;                        // Camera ID to monitor
  cameraName?: string;                     // Display name
}
```

## Component Patterns

### State Management
- Local component state for UI interactions
- API data fetching with loading/error states
- Refresh functionality with loading indicators

### Data Visualization
- Uses Tremor charts (BarChart, AreaChart)
- Custom heatmap implementation with Tailwind colors
- Color-coded severity indicators (green → yellow → orange → red)

### API Integration
```typescript
// Analytics API endpoints
fetchCameras()                              // GET /api/cameras
fetchCameraActivityBaseline(cameraId)       // GET /api/analytics/cameras/{id}/activity-baseline
fetchCameraClassBaseline(cameraId)          // GET /api/analytics/cameras/{id}/class-baseline
fetchAnomalyConfig()                        // GET /api/analytics/anomaly-config
updateAnomalyConfig(config)                 // PUT /api/analytics/anomaly-config
fetchPipelineLatency()                      // GET /api/analytics/pipeline-latency
fetchPipelineLatencyHistory(minutes, bucket) // GET /api/analytics/pipeline-latency/history
fetchSceneChanges(cameraId, params)         // GET /api/analytics/scene-changes
acknowledgeSceneChange(changeId)            // POST /api/analytics/scene-changes/{id}/acknowledge
```

## Styling

### NVIDIA Theme
- Dark backgrounds: `bg-gray-800`, `bg-gray-900`, `bg-[#1F1F1F]`
- NVIDIA green accent: `#76B900` for highlights
- Border colors: `border-gray-700`, `border-gray-800`
- Text colors: `text-white`, `text-gray-300`, `text-gray-400`

### Color Scales
- **Activity levels:** Gray (no activity) → Green (normal) → Orange (peak)
- **Latency status:** Green (good) → Yellow (warning) → Red (degraded)
- **Scene changes:** Yellow (unacknowledged) → Green (acknowledged)

**ChartTooltip.tsx** - NVIDIA-themed tooltip component for charts
- Provides consistent dark-themed tooltips
- Supports delayed display and keyboard navigation
- Used by heatmaps and bar charts for data display

**Props:**
```typescript
interface ChartTooltipProps {
  content: ReactNode;              // Tooltip content
  children: ReactNode;             // Trigger element
  position?: 'top' | 'bottom' | 'left' | 'right';  // Position preference
  disabled?: boolean;              // Disable tooltip
  delay?: number;                  // Show delay in ms (default: 100)
}
```

**DateRangeDropdown.tsx** - Quick date range selector
- Provides preset options: Today, Yesterday, Last 7/30/90 days
- Custom date range picker integration
- URL parameter persistence support

## File Inventory

```
analytics/
├── AGENTS.md                           # This file
├── AnalyticsPage.tsx                   # Main analytics page
├── AnalyticsPage.test.tsx              # Page tests
├── ActivityHeatmap.tsx                 # 24x7 activity heatmap
├── ActivityHeatmap.test.tsx            # Heatmap tests
├── ChartTooltip.tsx                    # NVIDIA-themed tooltip component
├── ChartTooltip.test.tsx               # Tooltip tests
├── ClassFrequencyChart.tsx             # Class distribution chart
├── ClassFrequencyChart.test.tsx        # Chart tests
├── CameraUptimeCard.tsx                # Camera uptime with trend indicators
├── CameraUptimeCard.test.tsx           # Uptime card tests
├── CustomDateRangePicker.tsx           # Custom date range input
├── CustomDateRangePicker.test.tsx      # Date picker tests
├── DateRangeDropdown.tsx               # Date range preset dropdown
├── DateRangeDropdown.test.tsx          # Dropdown tests
├── AnomalyConfigPanel.tsx              # Anomaly detection settings
├── AnomalyConfigPanel.test.tsx         # Config panel tests
├── PipelineLatencyPanel.tsx            # Pipeline latency monitoring
├── PipelineLatencyPanel.test.tsx       # Latency panel tests
├── SceneChangePanel.tsx                # Camera tampering detection
├── SceneChangePanel.test.tsx           # Scene change tests
└── index.ts                            # Barrel exports
```

## Usage Example

```typescript
import { AnalyticsPage } from '../components/analytics';

// In router configuration
<Route path="/analytics" element={<AnalyticsPage />} />

// Individual components (for custom layouts)
import {
  ActivityHeatmap,
  ClassFrequencyChart,
  PipelineLatencyPanel,
  SceneChangePanel
} from '../components/analytics';

<ActivityHeatmap
  entries={activityData}
  learningComplete={true}
  minSamplesRequired={100}
/>

<PipelineLatencyPanel refreshInterval={60000} />

<SceneChangePanel cameraId="front_door" cameraName="Front Door" />
```

## Testing

All components have comprehensive test coverage:
- Unit tests for rendering and user interactions
- Mock API responses for data fetching
- Error state handling
- Loading state verification
- User interaction simulation (button clicks, form submissions)

**Run tests:**
```bash
cd frontend
npm test -- analytics
```

## Navigation

- **Parent:** `/frontend/src/components/AGENTS.md` - Component directory overview
- **Related:** `/frontend/src/services/api.ts` - API client functions
- **Related:** `/backend/api/routes/analytics.py` - Analytics API endpoints

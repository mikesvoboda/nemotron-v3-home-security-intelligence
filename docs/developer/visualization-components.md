# Visualization Components

> Developer guide for dashboard widgets, charts, heatmaps, and data visualization components.

This document covers the visualization components used throughout the frontend, including chart libraries, component APIs, data formatting requirements, and patterns for creating custom visualizations.

**Time to read:** ~15 minutes

---

## Chart Library: Tremor

The project uses [Tremor](https://www.tremor.so/) as the primary charting library. Tremor provides React components built on top of Recharts with a focus on dashboard applications.

### Why Tremor?

- Pre-styled for dark themes
- Consistent API across chart types
- TypeScript support
- Accessibility built-in
- Integrates well with Tailwind CSS

### Commonly Used Tremor Components

```typescript
import {
  Card,
  Title,
  Text,
  AreaChart,
  BarChart,
  DonutChart,
  ProgressBar,
  Badge,
  TabGroup,
  TabList,
  Tab,
} from '@tremor/react';
```

### Basic Chart Example

```typescript
import { AreaChart, Card, Title } from '@tremor/react';

const chartData = [
  { time: '10:00', value: 45 },
  { time: '10:05', value: 52 },
  { time: '10:10', value: 48 },
];

function MyChart() {
  return (
    <Card className="border-gray-800 bg-[#1A1A1A]">
      <Title className="text-white">My Chart</Title>
      <AreaChart
        className="h-48"
        data={chartData}
        index="time"
        categories={['value']}
        colors={['emerald']}
        valueFormatter={(value) => `${value}%`}
        showLegend={false}
        showGridLines={false}
        curveType="monotone"
      />
    </Card>
  );
}
```

### Tremor Color Palette

Tremor uses named colors that map to Tailwind:

| Tremor Color | Usage                            |
| ------------ | -------------------------------- |
| `emerald`    | Success, healthy metrics         |
| `amber`      | Warnings, temperature            |
| `blue`       | Memory, neutral info             |
| `red`        | Errors, critical alerts          |
| `green`      | NVIDIA branding, positive values |
| `yellow`     | Caution, medium risk             |
| `orange`     | High risk                        |
| `violet`     | Categories, object classes       |

---

## Dashboard Widget Architecture

### Widget Configuration Store

Location: `frontend/src/stores/dashboardConfig.ts`

The dashboard uses a configuration store to manage widget visibility and ordering:

```typescript
// Widget identifiers
export type WidgetId =
  | 'stats-row'
  | 'camera-grid'
  | 'activity-feed'
  | 'gpu-stats'
  | 'pipeline-telemetry'
  | 'pipeline-queues';

// Widget configuration
export interface WidgetConfig {
  id: WidgetId;
  name: string;
  description: string;
  visible: boolean;
}

// Full dashboard config
export interface DashboardConfig {
  widgets: WidgetConfig[];
  version: number;
}
```

### Key Functions

```typescript
// Load from localStorage (returns default if not found)
loadDashboardConfig(): DashboardConfig

// Save to localStorage
saveDashboardConfig(config: DashboardConfig): void

// Reset to defaults
resetDashboardConfig(): DashboardConfig

// Widget manipulation
setWidgetVisibility(config, widgetId, visible): DashboardConfig
moveWidgetUp(config, widgetId): DashboardConfig
moveWidgetDown(config, widgetId): DashboardConfig
getVisibleWidgets(config): WidgetConfig[]
isWidgetVisible(config, widgetId): boolean
```

### DashboardLayout Component

Location: `frontend/src/components/dashboard/DashboardLayout.tsx`

Uses a render props pattern for flexible widget rendering:

```typescript
interface DashboardLayoutProps {
  widgetProps: WidgetProps;
  renderStatsRow: (props: StatsRowProps) => React.ReactNode;
  renderCameraGrid: (props: CameraGridProps) => React.ReactNode;
  renderActivityFeed: (props: ActivityFeedProps) => React.ReactNode;
  renderGpuStats?: (props: GpuStatsProps) => React.ReactNode;
  renderPipelineTelemetry?: (props: PipelineTelemetryProps) => React.ReactNode;
  renderPipelineQueues?: (props: PipelineQueuesProps) => React.ReactNode;
  isLoading?: boolean;
  renderLoadingSkeleton?: () => React.ReactNode;
}
```

Usage:

```typescript
<DashboardLayout
  widgetProps={{
    statsRow: { activeCameras: 4, eventsToday: 10, ... },
    cameraGrid: { cameras: cameraList, onCameraClick: handleClick },
  }}
  renderStatsRow={(props) => <StatsRow {...props} />}
  renderCameraGrid={(props) => <CameraGrid {...props} />}
  renderActivityFeed={(props) => <ActivityFeed {...props} />}
/>
```

---

## Dashboard Components

### StatsRow

Location: `frontend/src/components/dashboard/StatsRow.tsx`

Displays key metrics with clickable navigation cards.

```typescript
interface StatsRowProps {
  activeCameras: number;
  eventsToday: number;
  currentRiskScore: number;
  systemStatus: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  riskHistory?: number[]; // For sparkline display
  className?: string;
}
```

**Features:**

- Four stat cards with icons and navigation
- Risk score with color-coded sparkline
- System status with animated pulse indicator

**Sparkline Implementation:**

The component generates SVG sparklines using a custom `generateSparklinePath` function:

```typescript
function generateSparklinePath(
  data: number[],
  width: number,
  height: number,
  fillPath: boolean
): string {
  // Normalizes data points to SVG coordinates
  // Returns path string for SVG <path> element
}
```

### GpuStats

Location: `frontend/src/components/dashboard/GpuStats.tsx`

GPU monitoring with tabbed history charts.

```typescript
interface GpuStatsProps {
  gpuName?: string | null;
  utilization?: number | null;
  memoryUsed?: number | null; // MB
  memoryTotal?: number | null; // MB
  temperature?: number | null; // Celsius
  powerUsage?: number | null; // Watts
  inferenceFps?: number | null;
  className?: string;
  historyOptions?: UseGpuHistoryOptions;
  showHistoryControls?: boolean; // Default: true
  timeRange?: TimeRange;
  historyData?: GpuMetricDataPoint[]; // External data override
}
```

**Color Thresholds:**

```typescript
// Temperature colors
function getTemperatureColor(temp: number): 'green' | 'yellow' | 'red' {
  if (temp < 70) return 'green';
  if (temp < 80) return 'yellow';
  return 'red';
}

// Power colors
function getPowerColor(watts: number): 'green' | 'yellow' | 'red' {
  if (watts < 150) return 'green';
  if (watts < 250) return 'yellow';
  return 'red';
}
```

**History Tabs:**

- Utilization (emerald/green area chart)
- Temperature (amber area chart)
- Memory (blue area chart)

### PipelineQueues

Location: `frontend/src/components/dashboard/PipelineQueues.tsx`

Shows AI pipeline queue depths.

```typescript
interface PipelineQueuesProps {
  detectionQueue: number;
  analysisQueue: number;
  warningThreshold?: number; // Default: 10
  className?: string;
}
```

**Queue Status Colors:**
| Depth | Color |
| ----- | ----- |
| 0 | gray |
| 1-5 | green |
| 6-10 | yellow |
| >10 | red |

### PipelineTelemetry

Location: `frontend/src/components/dashboard/PipelineTelemetry.tsx`

Pipeline latency and throughput metrics with time series.

```typescript
interface PipelineTelemetryProps {
  className?: string;
}
```

Fetches data from:

- `GET /api/system/telemetry`

---

## Analytics Components

### ActivityHeatmap

Location: `frontend/src/components/analytics/ActivityHeatmap.tsx`

24x7 heatmap showing activity patterns by hour and day.

```typescript
interface ActivityHeatmapProps {
  entries: ActivityBaselineEntry[];
  learningComplete: boolean;
  minSamplesRequired: number;
}

interface ActivityBaselineEntry {
  day_of_week: number; // 0-6 (Mon-Sun)
  hour: number; // 0-23
  avg_count: number;
  sample_count: number;
  is_peak: boolean;
}
```

**Color Scale:**

```typescript
function getCellColor(avgCount: number, isPeak: boolean): string {
  if (avgCount === 0) return 'bg-gray-800';

  const intensity = avgCount / maxAvgCount;

  if (isPeak) {
    // Orange scale for peaks
    if (intensity > 0.8) return 'bg-orange-500';
    // ...
  }

  // Green scale for normal activity
  if (intensity > 0.8) return 'bg-[#76B900]';
  if (intensity > 0.6) return 'bg-[#76B900]/80';
  // ...
}
```

**Grid Structure:**

- 7 rows (Monday-Sunday)
- 24 columns (hours 0-23)
- Each cell is clickable with tooltip

### ClassFrequencyChart

Location: `frontend/src/components/analytics/ClassFrequencyChart.tsx`

Bar chart showing object class distribution.

```typescript
interface ClassFrequencyChartProps {
  entries: ClassBaselineEntry[];
  uniqueClasses: string[];
  mostCommonClass: string | null;
}

interface ClassBaselineEntry {
  object_class: string;
  frequency: number;
  sample_count: number;
}
```

**Class Color Palette:**

```typescript
const CLASS_COLORS: Record<string, string> = {
  person: '#76B900',
  vehicle: '#F59E0B',
  car: '#F59E0B',
  truck: '#D97706',
  motorcycle: '#B45309',
  bicycle: '#92400E',
  animal: '#8B5CF6',
  dog: '#7C3AED',
  cat: '#6D28D9',
  bird: '#5B21B6',
};
```

### PipelineLatencyPanel

Location: `frontend/src/components/analytics/PipelineLatencyPanel.tsx`

Pipeline latency breakdown with historical trends.

```typescript
interface PipelineLatencyPanelProps {
  refreshInterval?: number; // ms, 0 to disable
}
```

**Stage Configuration:**

```typescript
const STAGE_CONFIG = {
  watch_to_detect: {
    label: 'File Watcher -> YOLO26',
    shortLabel: 'Watch->Detect',
    color: '#76B900',
  },
  detect_to_batch: {
    label: 'YOLO26 -> Batch Aggregator',
    shortLabel: 'Detect->Batch',
    color: '#F59E0B',
  },
  batch_to_analyze: {
    label: 'Batch Aggregator -> Nemotron',
    shortLabel: 'Batch->Analyze',
    color: '#8B5CF6',
  },
  total_pipeline: {
    label: 'Total End-to-End',
    shortLabel: 'Total',
    color: '#3B82F6',
  },
};
```

**Time Range Options:**

```typescript
const TIME_RANGES = [
  { label: '1 hour', value: 60, bucketSeconds: 60 },
  { label: '6 hours', value: 360, bucketSeconds: 300 },
  { label: '24 hours', value: 1440, bucketSeconds: 900 },
];
```

---

## AI Insights Charts

### InsightsCharts

Location: `frontend/src/components/ai/InsightsCharts.tsx`

Combined detection and risk distribution charts.

```typescript
interface InsightsChartsProps {
  detectionsByClass?: Record<string, number>;
  totalDetections?: number;
  className?: string;
}
```

**Contains:**

1. **Detection Class Distribution** - DonutChart showing object type breakdown
2. **Risk Score Distribution** - Clickable bar chart by risk level

**Risk Level Navigation:**

Clicking a risk level bar navigates to the Timeline with filter:

```typescript
onClick={() => navigate(`/timeline?risk_level=${item.riskLevelKey}`)}
```

---

## Data Formatting Patterns

### Time Formatting

```typescript
// Short time for charts
const formatChartTime = (timestamp: string) =>
  new Date(timestamp).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });

// Relative time for feeds
function formatRelativeTime(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const minutes = Math.floor(diff / 60000);

  if (minutes < 1) return 'Just now';
  if (minutes === 1) return '1 min ago';
  if (minutes < 60) return `${minutes} mins ago`;
  // ...
}
```

### Number Formatting

```typescript
// Large numbers
function formatCount(count: number): string {
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
  return count.toString();
}

// Latency
function formatLatency(ms: number | null): string {
  if (ms === null) return 'N/A';
  if (ms < 1) return '<1ms';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

// Memory
function formatMemory(used: number, total: number) {
  const usedGB = (used / 1024).toFixed(1);
  const totalGB = (total / 1024).toFixed(1);
  return `${usedGB} / ${totalGB} GB`;
}
```

### Percentage Calculation

```typescript
// For bar charts
const percentage = (value / maxValue) * 100;

// For progress bars (clamped)
const progressValue = Math.min((value / threshold) * 100, 100);
```

---

## Custom Chart Examples

### Creating a Custom Sparkline

```typescript
import { useMemo } from 'react';

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}

function Sparkline({
  data,
  width = 60,
  height = 24,
  color = '#76B900'
}: SparklineProps) {
  const path = useMemo(() => {
    if (data.length < 2) return '';

    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;

    const points = data.map((value, i) => {
      const x = (i / (data.length - 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
    });

    return points.join(' ');
  }, [data, width, height]);

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <path
        d={path}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
```

### Creating a Gauge Component

```typescript
interface GaugeProps {
  value: number;          // 0-100
  thresholds?: number[];  // Default: [30, 60, 85]
  colors?: string[];      // Default: green, yellow, orange, red
}

function Gauge({
  value,
  thresholds = [30, 60, 85],
  colors = ['#22c55e', '#eab308', '#f97316', '#ef4444']
}: GaugeProps) {
  const getColor = () => {
    if (value < thresholds[0]) return colors[0];
    if (value < thresholds[1]) return colors[1];
    if (value < thresholds[2]) return colors[2];
    return colors[3];
  };

  const angle = (value / 100) * 180 - 90;  // -90 to 90 degrees

  return (
    <svg viewBox="0 0 100 60" className="w-full">
      {/* Background arc */}
      <path
        d="M 10 50 A 40 40 0 0 1 90 50"
        fill="none"
        stroke="#374151"
        strokeWidth="8"
        strokeLinecap="round"
      />
      {/* Value arc */}
      <path
        d={`M 10 50 A 40 40 0 0 1 ${50 + 40 * Math.cos(angle * Math.PI / 180)} ${50 - 40 * Math.sin(angle * Math.PI / 180)}`}
        fill="none"
        stroke={getColor()}
        strokeWidth="8"
        strokeLinecap="round"
      />
      {/* Value text */}
      <text x="50" y="55" textAnchor="middle" className="fill-white text-lg font-bold">
        {value}
      </text>
    </svg>
  );
}
```

---

## Styling Patterns

### NVIDIA Theme Colors

```typescript
// Primary brand green
const NVIDIA_GREEN = '#76B900';
const NVIDIA_GREEN_HOVER = '#8BC727';

// Background colors
const BG_DARK = '#121212';
const BG_CARD = '#1A1A1A';
const BG_ELEVATED = '#1F1F1F';

// Border colors
const BORDER_DEFAULT = 'border-gray-800';
const BORDER_HOVER = 'border-gray-700';
const BORDER_ACCENT = 'border-[#76B900]/30';
```

### Card Styling Pattern

```typescript
<Card className="border-gray-800 bg-[#1A1A1A] shadow-lg">
  <Title className="flex items-center gap-2 text-white">
    <Icon className="h-5 w-5 text-[#76B900]" />
    Card Title
  </Title>
  <Text className="text-gray-400">Subtitle or description</Text>
  {/* Content */}
</Card>
```

### Responsive Grid Patterns

```typescript
// 4-column stats row
<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">

// 2-column with sidebar
<div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr,1fr]">

// 3-column system widgets
<div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
```

---

## Testing Visualization Components

### Test Data Factories

```typescript
// Generate test chart data
function generateChartData(points: number, range: [number, number]) {
  return Array.from({ length: points }, (_, i) => ({
    time: new Date(Date.now() - (points - i) * 60000).toISOString(),
    value: Math.random() * (range[1] - range[0]) + range[0],
  }));
}

// Generate heatmap test data
function generateHeatmapData() {
  return Array.from({ length: 168 }, (_, i) => ({
    day_of_week: Math.floor(i / 24),
    hour: i % 24,
    avg_count: Math.random() * 10,
    sample_count: Math.floor(Math.random() * 100) + 10,
    is_peak: Math.random() > 0.9,
  }));
}
```

### Testing Chart Rendering

```typescript
import { render, screen } from '@testing-library/react';
import { ActivityHeatmap } from './ActivityHeatmap';

describe('ActivityHeatmap', () => {
  it('renders all day labels', () => {
    render(
      <ActivityHeatmap
        entries={[]}
        learningComplete={false}
        minSamplesRequired={10}
      />
    );

    expect(screen.getByText('Mon')).toBeInTheDocument();
    expect(screen.getByText('Sun')).toBeInTheDocument();
  });

  it('shows learning indicator when not complete', () => {
    render(
      <ActivityHeatmap
        entries={generateHeatmapData().slice(0, 50)}
        learningComplete={false}
        minSamplesRequired={10}
      />
    );

    expect(screen.getByText(/Learning/)).toBeInTheDocument();
  });
});
```

---

## Related Documentation

- [Dashboard AGENTS.md](../../frontend/src/components/dashboard/AGENTS.md) - Component details
- [Analytics AGENTS.md](../../frontend/src/components/analytics/AGENTS.md) - Analytics components
- [Frontend Hooks](../architecture/frontend-hooks.md) - Data fetching hooks
- [API Reference](api/core-resources.md) - Analytics API endpoints

---

_Visualization components follow consistent patterns for styling, data formatting, and interactivity. Use these patterns when extending the dashboard._

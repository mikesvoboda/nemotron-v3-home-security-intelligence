# Batch Components Directory

## Purpose

Components for visualizing batch processing statistics and lifecycle events in the AI detection pipeline. The batch system aggregates detections over 90-second time windows with 30-second idle timeout before sending to the LLM for risk assessment.

## Key Components

| File                             | Purpose                                        |
| -------------------------------- | ---------------------------------------------- |
| `BatchStatisticsDashboard.tsx`   | Main dashboard with all batch metrics          |
| `BatchTimelineChart.tsx`         | Timeline visualization of active batches       |
| `BatchClosureReasonChart.tsx`    | Donut chart showing batch closure reasons      |
| `BatchPerCameraTable.tsx`        | Table of per-camera batch statistics           |
| `BatchStatisticsDashboard.test.tsx` | Test suite for the dashboard                |
| `index.ts`                       | Barrel exports for all components and types    |

## Component Details

### BatchStatisticsDashboard

Main dashboard orchestrating all batch statistics visualizations.

**Features:**
- Summary metrics (active batches, total closed, avg duration)
- Batch configuration display (window size, idle timeout)
- WebSocket connection status indicator
- Active batch timeline
- Closure reason distribution chart
- Per-camera breakdown table
- Loading, error, and empty states

**Props:**
| Prop          | Type     | Description            |
| ------------- | -------- | ---------------------- |
| `className`   | `string` | Optional CSS class     |
| `data-testid` | `string` | Test ID (default: `batch-statistics-dashboard`) |

**Summary Metrics:**
- **Active Batches** - Currently open batch count
- **Total Closed** - Completed batch count
- **Avg Duration** - Average batch duration in seconds
- **Batch Window** - Maximum batch lifetime (90s)
- **Idle Timeout** - Inactivity timeout (30s)

### BatchTimelineChart

Visual timeline showing progress of active batches toward closure.

**Features:**
- Horizontal progress bars for each batch
- Color-coded by age (green -> yellow -> red as approaching timeout)
- Shows batch ID, camera, detection count
- Last activity indicator

**Props:**
| Prop                 | Type                   | Description                |
| -------------------- | ---------------------- | -------------------------- |
| `activeBatches`      | `BatchInfoResponse[]`  | Active batches to display  |
| `batchWindowSeconds` | `number`               | Batch window timeout       |
| `className`          | `string`               | Optional CSS class         |

**Color Thresholds:**
- Green (`#76B900`) - Less than 50% of window
- Yellow - 50-80% of window
- Red - More than 80% of window (near timeout)

### BatchClosureReasonChart

Donut chart displaying distribution of batch closure reasons.

**Closure Reasons:**
- `timeout` - Batch window (90s) expired
- `idle` - No activity for idle timeout period (30s)
- `max_size` - Maximum batch size reached

**Props:**
| Prop                       | Type                       | Description               |
| -------------------------- | -------------------------- | ------------------------- |
| `closureReasonStats`       | `ClosureReasonStats`       | Counts per reason         |
| `closureReasonPercentages` | `ClosureReasonPercentages` | Percentages per reason    |
| `totalBatches`             | `number`                   | Total closed batch count  |
| `className`                | `string`                   | Optional CSS class        |

### BatchPerCameraTable

Table showing batch statistics broken down by camera.

**Columns:**
- Camera ID with icon
- Active batch count (green badge if > 0)
- Completed batch count
- Total detection count

**Props:**
| Prop             | Type             | Description           |
| ---------------- | ---------------- | --------------------- |
| `perCameraStats` | `PerCameraStats` | Per-camera statistics |
| `className`      | `string`         | Optional CSS class    |

## Data Flow

```
BatchStatisticsDashboard
├── useBatchStatistics()      → aggregates batch data
│   ├── REST API /api/system/pipeline → active batches
│   └── WebSocket detection.batch events → real-time updates
├── BatchTimelineChart        → active batch progress
├── BatchClosureReasonChart   → closure distribution
└── BatchPerCameraTable       → per-camera breakdown
```

## Hooks Used

| Hook                  | Source                                      | Purpose                          |
| --------------------- | ------------------------------------------- | -------------------------------- |
| `useBatchStatistics`  | `frontend/src/hooks/useBatchStatistics.ts`  | Aggregate batch statistics       |

## Test Coverage

**BatchStatisticsDashboard.test.tsx** covers:
- Dashboard rendering and title
- Active batch count display
- Total closed batch count display
- Average duration display
- Batch configuration display
- WebSocket connection indicator (connected/disconnected)
- Closure reason chart rendering
- Per-camera table rendering
- Loading state skeleton
- Error state with retry button
- Empty state with message
- Active batch timeline rendering
- Accessibility labels

## Types

**From `frontend/src/hooks/useBatchStatistics.ts`:**
```typescript
interface ClosureReasonStats {
  timeout: number;
  idle: number;
  max_size: number;
}

interface ClosureReasonPercentages {
  timeout: number;
  idle: number;
  max_size: number;
}

interface PerCameraStats {
  [cameraId: string]: {
    activeBatchCount: number;
    completedBatchCount: number;
    totalDetections: number;
  };
}
```

**From `frontend/src/types/generated/index.ts`:**
```typescript
interface BatchInfoResponse {
  batch_id: string;
  camera_id: string;
  detection_count: number;
  started_at: number;
  age_seconds: number;
  last_activity_seconds: number;
}
```

## Styling

- Uses NVIDIA dark theme (`bg-[#1A1A1A]`)
- Tremor components for data visualization (DonutChart, Badge, Card)
- NVIDIA green (`#76B900`) for primary accents
- Color-coded status indicators (green/yellow/red)

## Related Documentation

| Document                         | Purpose                           |
| -------------------------------- | --------------------------------- |
| `docs/guides/video-analytics.md` | AI pipeline overview              |
| `CLAUDE.md`                      | Batch processing configuration    |

## Entry Points

- **Start here:** `BatchStatisticsDashboard.tsx` - Used in System Monitoring page
- **For visualization:** `BatchTimelineChart.tsx` - Standalone active batch display

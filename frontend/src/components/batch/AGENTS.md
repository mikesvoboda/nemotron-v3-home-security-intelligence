# Batch Components Directory

## Purpose

Components for visualizing batch processing statistics and lifecycle events in the AI detection pipeline. The batch system aggregates detections over 90-second time windows with 30-second idle timeout before sending to the LLM for risk assessment.

## Key Components

| File                                | Purpose                                     |
| ----------------------------------- | ------------------------------------------- |
| `BatchStatisticsDashboard.tsx`      | Main dashboard with all batch metrics       |
| `BatchTimelineChart.tsx`            | Timeline visualization of active batches    |
| `BatchStatisticsDashboard.test.tsx` | Test suite for the dashboard                |
| `index.ts`                          | Barrel exports for all components and types |

Ruling 134 retired the closure-reason chart, the per-camera table and the
completed-batch timeline view; the active-batches view above is the one that
stays. Absence is guarded by
`../__tests__/batch-history-views-retired.test.tsx`.

## Component Details

### BatchStatisticsDashboard

Main dashboard orchestrating all batch statistics visualizations.

**Features:**

- Summary metrics (active batches, total closed, avg duration)
- Batch configuration display (window size, idle timeout)
- WebSocket connection status indicator
- Active batch timeline
- Loading, error, and empty states

**Props:**

| Prop          | Type     | Description                                     |
| ------------- | -------- | ----------------------------------------------- |
| `className`   | `string` | Optional CSS class                              |
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

| Prop                 | Type                  | Description               |
| -------------------- | --------------------- | ------------------------- |
| `activeBatches`      | `BatchInfoResponse[]` | Active batches to display |
| `batchWindowSeconds` | `number`              | Batch window timeout      |
| `className`          | `string`              | Optional CSS class        |

**Color Thresholds:**

- Green (`#76B900`) - Less than 50% of window
- Yellow - 50-80% of window
- Red - More than 80% of window (near timeout)

## Data Flow

```
BatchStatisticsDashboard
├── useBatchStatistics()      → aggregates batch data
│   ├── REST API /api/system/pipeline → active batches
│   └── WebSocket detection.batch events → real-time updates
└── BatchTimelineChart        → active batch progress
```

## Hooks Used

| Hook                 | Source                                     | Purpose                    |
| -------------------- | ------------------------------------------ | -------------------------- |
| `useBatchStatistics` | `frontend/src/hooks/useBatchStatistics.ts` | Aggregate batch statistics |

## Test Coverage

**BatchStatisticsDashboard.test.tsx** covers:

- Dashboard rendering and title
- Active batch count display
- Total closed batch count display
- Average duration display
- Batch configuration display
- WebSocket connection indicator (connected/disconnected)
- Loading state skeleton
- Error state with retry button
- Empty state with message
- Active batch timeline rendering
- Accessibility labels

## Types

**From `frontend/src/hooks/useBatchStatistics.ts`:**

```typescript
interface UseBatchStatisticsReturn {
  isLoading: boolean;
  error: string | null;
  activeBatchCount: number;
  activeBatches: BatchInfoResponse[];
  completedBatches: DetectionBatchData[];
  totalClosedCount: number;
  batchWindowSeconds: number;
  idleTimeoutSeconds: number;
  averageDurationSeconds: number;
  isWebSocketConnected: boolean;
  refetch: () => Promise<void>;
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
- Tremor components for data visualization (Card, Badge, Text)
- NVIDIA green (`#76B900`) for primary accents
- Color-coded status indicators (green/yellow/red)

## Related Documentation

| Document                         | Purpose                        |
| -------------------------------- | ------------------------------ |
| `docs/guides/video-analytics.md` | AI pipeline overview           |
| `AGENTS.md`                      | Batch processing configuration |

## Entry Points

- **Start here:** `BatchStatisticsDashboard.tsx` - Used in System Monitoring page
- **For visualization:** `BatchTimelineChart.tsx` - Standalone active batch display

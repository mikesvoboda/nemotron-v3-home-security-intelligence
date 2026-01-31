# Zone Analytics Dashboard Design

**Date:** 2025-01-31
**Status:** Draft
**Priority:** HIGH
**Complexity:** Comprehensive

## Problem Statement

The backend has 651+ lines of spatial heuristics in zone services with only ~60% exposed in UI. Critical features missing:

- Line crossing counts (in_count/out_count tracked in DB, no UI)
- Dwell time statistics dashboard
- Loitering threshold customization
- Zone comparison analytics
- Anomaly investigation with context

## Goals

1. Create dedicated Zone Analytics page
2. Visualize line crossing patterns and counts
3. Display dwell time statistics with charts
4. Enable loitering threshold configuration
5. Show zone anomalies with investigation capability

## Non-Goals

- Zone drawing/editing (already exists in ZoneEditor)
- Real-time track visualization (separate feature)
- Cross-camera zone correlation

---

## Architecture Overview

```
/zones (existing) - Zone configuration
/zone-analytics (NEW) - Analytics dashboard
  ├── Zone Selector
  ├── Crossing Statistics Panel
  ├── Dwell Time Statistics Panel
  ├── Active Dwellers Panel
  ├── Anomaly Feed with Investigation
  └── Zone Comparison View
```

---

## API Enhancements

### Existing Endpoints (Already Available)

```
GET /api/analytics-zones/polygon-zones/{zone_id}/dwellers
GET /api/analytics-zones/polygon-zones/{zone_id}/dwell-history
GET /api/analytics-zones/polygon-zones/{zone_id}/dwell-statistics
POST /api/analytics-zones/polygon-zones/{zone_id}/check-loitering
POST /api/analytics-zones/line-zones/{zone_id}/reset-counts
```

### New Endpoints Needed

```
GET /api/analytics-zones/line-zones/{zone_id}/crossing-history
  - Historical crossing events with timestamps
  - Query: start_date, end_date, direction?
  - Returns: { crossings: [{ timestamp, direction, entity_id }], in_total, out_total }

GET /api/analytics-zones/line-zones/{zone_id}/crossing-trends
  - Aggregated crossing counts over time
  - Query: start_date, end_date, interval (hour|day)
  - Returns: { data: [{ timestamp, in_count, out_count }] }

GET /api/analytics-zones/comparison
  - Compare metrics across multiple zones
  - Query: zone_ids[], metric (crossings|dwell_time|anomalies)
  - Returns: { zones: [{ zone_id, name, value, trend }] }

PATCH /api/analytics-zones/polygon-zones/{zone_id}/loitering-config
  - Update loitering threshold
  - Body: { threshold_seconds: number, alert_enabled: boolean }
  - Returns: { success: boolean }

GET /api/zones/{zone_id}/anomalies/{anomaly_id}/context
  - Get anomaly with associated detections
  - Returns: { anomaly, detections: [...], expected_value, actual_value, explanation }
```

---

## Page Layout

### Zone Analytics Page (`/zone-analytics`)

```
┌─────────────────────────────────────────────────────────────┐
│  Zone Analytics                              [Camera ▼]     │
├─────────────────────────────────────────────────────────────┤
│  [Zone Tabs: All | Lines | Polygons | Comparison]           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────┐  ┌─────────────────────────────┐  │
│  │   Zone Selector     │  │   Selected Zone Stats       │  │
│  │   ○ Front Door      │  │   ┌─────────┐ ┌─────────┐   │  │
│  │   ○ Driveway        │  │   │ IN: 47  │ │ OUT: 42 │   │  │
│  │   ● Backyard        │  │   └─────────┘ └─────────┘   │  │
│  │   ○ Side Gate       │  │   [Reset Counts]            │  │
│  └─────────────────────┘  └─────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │   Crossing Trends (24h)                              │  │
│  │   📈 [Area chart: in/out over time]                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────┐  ┌─────────────────────────────┐  │
│  │   Dwell Statistics  │  │   Active Dwellers           │  │
│  │   Avg: 2m 34s       │  │   👤 Person (3m 12s)        │  │
│  │   Max: 15m 02s      │  │   🚗 Vehicle (1m 45s)       │  │
│  │   Min: 0m 12s       │  │   👤 Person (0m 30s)        │  │
│  │   [Configure ⚙️]     │  │                             │  │
│  └─────────────────────┘  └─────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │   Zone Anomalies                        [Filter ▼]   │  │
│  │   ⚠️ 10:32 AM - Unusual activity (expected 2, got 8) │  │
│  │      [View Detections] [Dismiss]                     │  │
│  │   ⚠️ 9:15 AM - Extended dwell time (15m vs 2m avg)   │  │
│  │      [View Detections] [Dismiss]                     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Comparison View

```
┌──────────────────────────────────────────────────────────┐
│   Zone Comparison                    [Metric: Crossings ▼]│
├──────────────────────────────────────────────────────────┤
│                                                          │
│   Zone          │ Today │ Week  │ Trend                  │
│   ─────────────────────────────────────────────────────  │
│   Front Door    │  142  │  984  │ ↑ 12%                  │
│   Driveway      │   87  │  612  │ ↓ 5%                   │
│   Backyard      │   23  │  156  │ → 0%                   │
│   Side Gate     │    8  │   45  │ ↑ 23%                  │
│                                                          │
│   [Bar chart comparing zones]                            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## Components

### New Components

| Component                   | Purpose                   | Props                               |
| --------------------------- | ------------------------- | ----------------------------------- |
| `ZoneAnalyticsPage`         | Main page container       | -                                   |
| `ZoneSelector`              | List zones with selection | zones, selected, onSelect           |
| `CrossingCountCard`         | Display in/out counts     | inCount, outCount, onReset          |
| `CrossingTrendsChart`       | Area chart of crossings   | data, interval                      |
| `DwellStatisticsCard`       | Dwell time stats          | stats, onConfigure                  |
| `ActiveDwellersPanel`       | List of current dwellers  | dwellers                            |
| `LoiteringConfigModal`      | Configure threshold       | zoneId, current, onSave             |
| `ZoneAnomalyFeed`           | List anomalies            | anomalies, onInvestigate, onDismiss |
| `AnomalyInvestigationModal` | Show anomaly context      | anomalyId                           |
| `ZoneComparisonTable`       | Compare zones             | zones, metric                       |
| `ZoneComparisonChart`       | Bar chart comparison      | data                                |

### Component Hierarchy

```
ZoneAnalyticsPage
├── ZoneSelector
├── TabGroup (All | Lines | Polygons | Comparison)
├── CrossingCountCard
│   └── ResetCountsButton
├── CrossingTrendsChart
├── DwellStatisticsCard
│   └── LoiteringConfigModal
├── ActiveDwellersPanel
│   └── DwellerRow
├── ZoneAnomalyFeed
│   └── AnomalyCard
│       └── AnomalyInvestigationModal
└── ZoneComparisonView
    ├── ZoneComparisonTable
    └── ZoneComparisonChart
```

---

## Hooks

```typescript
// useZoneAnalytics.ts

// Crossing data
export function useLineCrossingCounts(zoneId: string) {
  return useQuery({
    queryKey: ['zone-crossing-counts', zoneId],
    queryFn: () => fetchApi(`/api/analytics-zones/line-zones/${zoneId}`),
  });
}

export function useCrossingTrends(zoneId: string, interval: 'hour' | 'day') {
  return useQuery({
    queryKey: ['zone-crossing-trends', zoneId, interval],
    queryFn: () =>
      fetchApi(`/api/analytics-zones/line-zones/${zoneId}/crossing-trends?interval=${interval}`),
  });
}

export function useResetCrossingCounts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (zoneId: string) =>
      fetchApi(`/api/analytics-zones/line-zones/${zoneId}/reset-counts`, { method: 'POST' }),
    onSuccess: (_, zoneId) => queryClient.invalidateQueries(['zone-crossing-counts', zoneId]),
  });
}

// Dwell time data
export function useDwellStatistics(zoneId: string) {
  return useQuery({
    queryKey: ['zone-dwell-stats', zoneId],
    queryFn: () => fetchApi(`/api/analytics-zones/polygon-zones/${zoneId}/dwell-statistics`),
  });
}

export function useActiveDwellers(zoneId: string) {
  return useQuery({
    queryKey: ['zone-active-dwellers', zoneId],
    queryFn: () => fetchApi(`/api/analytics-zones/polygon-zones/${zoneId}/dwellers`),
    refetchInterval: 5000, // Real-time updates
  });
}

export function useUpdateLoiteringConfig() {
  return useMutation({
    mutationFn: ({ zoneId, config }) =>
      fetchApi(`/api/analytics-zones/polygon-zones/${zoneId}/loitering-config`, {
        method: 'PATCH',
        body: JSON.stringify(config),
      }),
  });
}

// Anomalies
export function useZoneAnomalies(zoneId: string) {
  return useQuery({
    queryKey: ['zone-anomalies', zoneId],
    queryFn: () => fetchApi(`/api/zones/${zoneId}/anomalies`),
  });
}

export function useAnomalyContext(anomalyId: string) {
  return useQuery({
    queryKey: ['anomaly-context', anomalyId],
    queryFn: () => fetchApi(`/api/zones/anomalies/${anomalyId}/context`),
    enabled: !!anomalyId,
  });
}

// Comparison
export function useZoneComparison(zoneIds: string[], metric: string) {
  return useQuery({
    queryKey: ['zone-comparison', zoneIds, metric],
    queryFn: () =>
      fetchApi(`/api/analytics-zones/comparison?zone_ids=${zoneIds.join(',')}&metric=${metric}`),
    enabled: zoneIds.length > 0,
  });
}
```

---

## State Management

### URL State (Shareable)

- Selected zone ID
- Active tab
- Date range
- Comparison metric

### Local State

- Modal open states
- Expanded anomaly cards

```typescript
// URL params
const [searchParams, setSearchParams] = useSearchParams();
const selectedZoneId = searchParams.get('zone');
const activeTab = searchParams.get('tab') || 'all';
```

---

## Error Handling

| Scenario            | Handling                             |
| ------------------- | ------------------------------------ |
| No zones configured | Empty state with link to zone editor |
| Zone has no data    | "No activity recorded" message       |
| API error           | Error boundary with retry            |
| Reset counts fails  | Toast notification with error        |

---

## Testing Strategy

### Unit Tests

- Each component renders correctly
- Hooks return expected data shapes
- Chart renders with mock data

### Integration Tests

- Page loads and displays zones
- Zone selection updates all panels
- Reset counts flow works
- Loitering config saves correctly

### E2E Tests

- Navigate to zone analytics
- Select zone and verify data loads
- Configure loitering and verify saved
- Investigate anomaly flow

---

## Rollout Plan

### Phase 1: Core Dashboard (Epic)

1. Backend: Crossing trends endpoint
2. Backend: Anomaly context endpoint
3. Frontend: Page skeleton and routing
4. Frontend: Zone selector component
5. Frontend: Crossing count card with reset

### Phase 2: Dwell Time (Epic)

1. Frontend: Dwell statistics card
2. Frontend: Active dwellers panel
3. Frontend: Loitering config modal
4. Backend: Loitering config PATCH endpoint

### Phase 3: Anomaly Investigation (Epic)

1. Frontend: Anomaly feed component
2. Frontend: Investigation modal
3. Link anomalies to detections

### Phase 4: Comparison View (Epic)

1. Backend: Comparison endpoint
2. Frontend: Comparison table
3. Frontend: Comparison chart

---

## Open Questions

1. **Should we add WebSocket for real-time dweller updates?**

   - Recommendation: Yes, use existing zone WebSocket events

2. **How many zones can be compared at once?**

   - Recommendation: Max 6 for readability

3. **Should anomaly investigation link to event timeline?**
   - Recommendation: Yes, "View in Timeline" button

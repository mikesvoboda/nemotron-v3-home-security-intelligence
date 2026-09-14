# Frontend Hooks Analysis

## Executive Summary

The frontend has **80+ custom React hooks** covering queries, WebSocket, state management, and UI helpers. Strong architecture using TanStack React Query v5.

## Hook Categories

### 1. Query Hooks (TanStack React Query)

#### Alert Hooks

| Hook           | Endpoint                                                   | Purpose                               |
| -------------- | ---------------------------------------------------------- | ------------------------------------- |
| useAlerts      | `/api/alerts/{id}/acknowledge`, `/api/alerts/{id}/dismiss` | Alert mutations                       |
| useAlertsQuery | `/api/events` with risk_level filters                      | Infinite query for high/critical risk |

#### Camera Hooks

| Hook                         | Endpoint                        | Purpose                           |
| ---------------------------- | ------------------------------- | --------------------------------- |
| useCamerasQuery              | `/api/cameras`                  | Camera list with placeholder data |
| useCameraQuery               | `/api/cameras/{id}`             | Single camera fetch               |
| useOnlineCamerasQuery        | (derived)                       | Filter to online cameras          |
| useCameraCountsQuery         | (derived)                       | Aggregate by status               |
| useCameraPathValidationQuery | `/api/cameras/validation/paths` | Path validation                   |
| useCameraBaselineQuery       | `/api/cameras/{id}/baseline`    | Activity baselines                |

#### Detection Hooks

| Hook               | Endpoint                 | Purpose                     |
| ------------------ | ------------------------ | --------------------------- |
| useDetections      | `/api/detections`        | List with cursor pagination |
| useDetectionSearch | `/api/detections/search` | Full-text search            |
| useDetectionLabels | `/api/detections/labels` | Unique labels               |

#### GPU Hooks

| Hook               | Endpoint                             | Purpose               |
| ------------------ | ------------------------------------ | --------------------- |
| useGpus            | `/api/system/gpus`                   | Detected GPUs         |
| useGpuConfig       | `/api/system/gpu-config`             | Current configuration |
| useGpuStatus       | `/api/system/gpu-config/status`      | Apply status polling  |
| useServiceHealth   | `/api/system/gpu-config/services`    | Service health        |
| useUpdateGpuConfig | PUT `/api/system/gpu-config`         | Update assignments    |
| useApplyGpuConfig  | POST `/api/system/gpu-config/apply`  | Apply and restart     |
| useDetectGpus      | POST `/api/system/gpu-config/detect` | Re-scan GPUs          |
| usePreviewStrategy | GET `/api/system/gpu-config/preview` | Preview strategy      |

#### Zone Hooks

| Hook             | Endpoint                         | Purpose       |
| ---------------- | -------------------------------- | ------------- |
| useZones         | `/api/cameras/{camera_id}/zones` | Zone CRUD     |
| useZoneCrossings | Zone crossing events             | Crossing feed |
| useZoneAnomalies | Zone anomaly events              | Anomaly feed  |

### 2. WebSocket Hooks

| Hook                        | WebSocket Endpoint       | Events Handled                          |
| --------------------------- | ------------------------ | --------------------------------------- |
| useWebSocket                | (base)                   | ping/pong, connection management        |
| useEventStream              | `/ws/events`             | event.\*, sequence validation           |
| useDetectionStream          | `/ws/detections`         | detection.new, detection.batch          |
| useSystemStatus             | `/ws/system`             | System health, GPU stats                |
| useCameraStatusWebSocket    | `/ws/camera-status`      | Camera online/offline                   |
| useEventLifecycleWebSocket  | `/ws/events`             | event.created/updated/deleted           |
| useEventEnrichmentWebSocket | `/ws/enrichments`        | enrichment.\* lifecycle                 |
| useGpuStatsWebSocket        | `/ws/gpu-stats`          | Real-time GPU metrics                   |
| useSystemHealthWebSocket    | `/ws/health`             | System health components                |
| useQueueMetricsWebSocket    | `/ws/queues`             | queue.status, pipeline.throughput       |
| useAlertWebSocket           | `/ws/events`             | alert.\* events                         |
| useJobWebSocket             | `/ws/events`             | job_progress, job_completed, job_failed |
| useJobLogsWebSocket         | `/ws/jobs/{job_id}/logs` | Job log streaming                       |
| useServiceStatusWebSocket   | `/ws/events`             | service.status_changed                  |

### 3. State Management Hooks

| Hook                | Purpose                     | Storage          |
| ------------------- | --------------------------- | ---------------- |
| useSettings         | App settings                | localStorage     |
| useLocalStorage     | Generic storage             | localStorage     |
| usePaginationState  | URL-persistent pagination   | URL query params |
| useDateRangeState   | Date range with URL         | URL query params |
| useDeferredFilter   | React 19 deferred rendering | Memory           |
| useDeferredList     | Deferred list rendering     | Memory           |
| useOptimisticState  | React 19 useOptimistic      | Memory           |
| useOptimisticToggle | Optimistic toggle           | Memory           |
| useOptimisticList   | Optimistic list updates     | Memory           |

### 4. Analytics/Reporting Hooks

| Hook                       | Endpoint                                 | Purpose          |
| -------------------------- | ---------------------------------------- | ---------------- |
| useDetectionTrendsQuery    | `/api/analytics/detection-trends`        | Detection counts |
| useRiskScoreTrends         | `/api/analytics/risk-score-trends`       | Risk trends      |
| useRiskScoreDistribution   | `/api/analytics/risk-score-distribution` | Risk histogram   |
| useObjectDistributionQuery | `/api/analytics/object-distribution`     | Object counts    |
| useCameraUptimeQuery       | `/api/analytics/camera-uptime`           | Uptime stats     |
| useCameraAnalytics         | Per-camera analytics                     | Camera-specific  |
| useStorageStatsQuery       | Storage usage                            | Cleanup planning |
| usePerformanceMetrics      | System performance                       | Monitoring       |
| useAIMetrics               | AI model performance                     | Model monitoring |
| useSummaries               | Dashboard summaries                      | Summary cards    |

### 5. Specialized Query Hooks

| Hook                      | Purpose                                  |
| ------------------------- | ---------------------------------------- |
| useAuditLogsInfiniteQuery | Audit log streaming with infinite scroll |
| useEventsQuery            | Event list with cursor pagination        |
| useRecentEventsQuery      | Recently updated events                  |
| useEntityHistory          | Entity appearance history                |
| useSceneChangeAlerts      | Scene change detection                   |
| useJobMutations           | Job start/cancel/retry                   |
| useJobLogsQuery           | Job logs                                 |
| useJobHistoryQuery        | Job history                              |
| usePromptQueries          | LLM prompt management                    |
| useProfilingMutations     | Performance profiling                    |
| useAdminMutations         | Admin seed/cleanup                       |
| useModelZooStatusQuery    | AI model availability                    |

### 6. UI/UX Helper Hooks

| Hook                       | Purpose               |
| -------------------------- | --------------------- |
| useToast                   | Toast notifications   |
| useTheme                   | Theme context         |
| useAudioNotifications      | Sound alerts          |
| useDesktopNotifications    | Browser notifications |
| useIntegratedNotifications | Unified notifications |
| usePushNotifications       | PWA push              |
| useKeyboardShortcuts       | Keyboard commands     |
| useListNavigation          | Keyboard navigation   |
| useChartDimensions         | Chart sizing          |
| useVirtualizedList         | Performance lists     |
| useSwipeGesture            | Mobile swipe          |
| usePullToRefresh           | Pull-to-refresh       |
| useSummaryExpansion        | Collapse/expand       |
| useBulkSelection           | Multi-select          |
| useFormWithApiErrors       | Form validation       |

### 7. Infrastructure/Debug Hooks

| Hook                        | Purpose                    |
| --------------------------- | -------------------------- |
| useWebSocketCapabilities    | Feature detection          |
| useConnectionStatus         | Network connectivity       |
| useNetworkStatus            | PWA offline                |
| useHealthStatus             | Health polling             |
| useHealthStatusQuery        | Health endpoint            |
| useCircuitBreakerStatus     | Circuit breaker            |
| useCircuitBreakerDebugQuery | CB details                 |
| useMemoryStatsQuery         | Memory profiling           |
| useDebugConfigQuery         | Debug config               |
| useDebugQueries             | Pipeline errors, Redis, WS |
| useSetLogLevelMutation      | Dynamic log level          |
| useBatchAggregatorStatus    | Batch aggregation          |
| useBatchProcessingStatus    | Batch processing           |
| useBatchStatistics          | Batch stats                |
| useGpuHistory               | Historical GPU metrics     |
| useGpuStatsQuery            | GPU metrics query          |

## Data Transformation Patterns

### Common Patterns Used

1. **Memoization** - useMemo for derived data
2. **Cursor-based pagination** - Memory efficient
3. **Optimistic updates** - Immediate UI feedback
4. **Cache invalidation** - On mutation success
5. **PlaceholderData** - Loading states
6. **Select option** - Efficient data transformation

```typescript
// Example: PlaceholderData pattern
const { data } = useQuery({
  queryKey: ['cameras'],
  queryFn: fetchCameras,
  placeholderData: previousData,
});

// Example: Select for transformation
const { data } = useQuery({
  queryKey: ['cameras'],
  queryFn: fetchCameras,
  select: (data) => data.filter((c) => c.status === 'online'),
});
```

## WebSocket Pattern

All WebSocket hooks follow consistent pattern:

```typescript
function useXxxWebSocket() {
  const { lastMessage, isConnected } = useWebSocket(buildWebSocketOptions('/ws/xxx'));

  useEffect(() => {
    if (!lastMessage || !isMounted.current) return;

    if (isHeartbeat(lastMessage)) return;
    if (isXxxMessage(lastMessage)) {
      handleMessage(lastMessage);
    }
  }, [lastMessage]);

  return { data, isConnected };
}
```

## Potential Gaps

### Missing Hooks for Backend Features

| Backend Feature                | Hook Status        |
| ------------------------------ | ------------------ |
| Batch job queuing status       | ⚠️ Only monitoring |
| Real-time entity re-ID updates | ⚠️ Only history    |
| Anomaly score streaming        | ❌ Missing         |
| Face detection events          | ❌ Missing         |
| Known persons management       | ❌ Missing         |
| Dwell statistics               | ❌ Missing         |

### Recommended New Hooks

```typescript
// Face recognition management
useFaceEventsQuery();
useKnownPersonsQuery();
useKnownPersonMutations();

// Zone analytics
useDwellStatisticsQuery();
useZoneCrossingCountsQuery();
useZoneLoiteringConfig();

// Notifications
useNotificationChannelsQuery();
useSendNotificationMutation();
```

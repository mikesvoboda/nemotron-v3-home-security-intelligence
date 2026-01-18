# Frontend Hooks Directory

## Purpose

React custom hooks for managing WebSocket connections, real-time event streams, system status monitoring, storage stats, GPU metrics polling, AI service degradation tracking, keyboard navigation, mobile gestures, and offline support (PWA) in the home security dashboard.

## Hook Inventory

This directory contains **90+ hooks/utilities** organized into the following categories:

| Category | Hook Count | Description |
|----------|------------|-------------|
| AI Services | 6 | AI degradation, metrics, model status |
| Monitoring | 8 | Circuit breakers, health, performance |
| WebSocket | 12 | Real-time data connections |
| Data Queries | 25 | TanStack Query hooks for fetching |
| Data Mutations | 10 | TanStack Query mutations for writes |
| UI/UX | 12 | Keyboard, gestures, toasts, navigation |
| PWA/Offline | 3 | Network status, caching, notifications |
| Utilities | 8 | Event emitter, throttling, storage, forms |
| Pagination | 4 | Cursor and offset pagination |

## Comprehensive Hooks Reference

### AI Services Hooks

| Hook | Purpose | Parameters | Return Value | Endpoint/Source |
|------|---------|------------|--------------|-----------------|
| `useAIServiceStatus` | Track AI service degradation via WebSocket | None | `{ degradationMode, services, availableFeatures, hasUnavailableService, isOffline, isDegraded, getServiceState, isFeatureAvailable, lastUpdate }` | `/ws/events` |
| `useAIMetrics` | Fetch AI performance metrics from multiple endpoints | `{ pollingInterval?: number }` | `{ data: AIPerformanceState, isLoading, error, refresh }` | `/api/metrics`, `/api/system/telemetry`, `/api/system/health` |
| `useModelZooStatus` | Poll Model Zoo status with VRAM stats (legacy) | `{ pollingInterval?: number }` | `{ models, vramStats, isLoading, error, refresh }` | `/api/system/models` |
| `useModelZooStatusQuery` | TanStack Query for Model Zoo status | `{ enabled?, refetchInterval? }` | `{ data, models, vramStats, isLoading, isRefetching, error, refetch }` | `/api/system/models` |
| `useAnalysisStream` | SSE-based streaming LLM analysis | `{ onProgress?, onComplete?, onError? }` | `{ status, accumulatedText, result, error, startStream, stopStream, isStreaming }` | `/api/analysis/stream` |
| `useDetectionEnrichment` | Fetch enrichment data for a detection | `detectionId: number` | `{ data, isLoading, error, refetch }` | `/api/detections/{id}/enrichment` |

### Monitoring Hooks

| Hook | Purpose | Parameters | Return Value | Endpoint/Source |
|------|---------|------------|--------------|-----------------|
| `useCircuitBreakerStatus` | Track circuit breaker states via WebSocket | None | `{ breakers, summary, hasOpenBreaker, hasHalfOpenBreaker, allClosed, lastUpdate, getBreaker, isConnected }` | `/ws/system` |
| `useSystemStatus` | System health via WebSocket | None | `{ status, isConnected }` | `/ws/system` |
| `useHealthStatus` | REST-based health polling (legacy) | `{ pollingInterval?, enabled? }` | `{ health, isLoading, error, overallStatus, services, refresh }` | `/api/system/health` |
| `useHealthStatusQuery` | TanStack Query health status | `{ enabled?, refetchInterval? }` | `{ data, isLoading, error, isStale, refetch }` | `/api/system/health` |
| `useFullHealthQuery` | Comprehensive health with circuit breakers | `{ enabled?, refetchInterval? }` | `{ data, overallStatus, postgres, redis, aiServices, circuitBreakers, workers, criticalUnhealthyCount }` | `/api/system/health/full` |
| `usePerformanceMetrics` | Real-time performance via WebSocket | None | `{ current, history, alerts, isConnected, timeRange, setTimeRange }` | `/ws/system` |
| `useGpuStatsQuery` | TanStack Query GPU stats | `{ enabled?, refetchInterval? }` | `{ data, utilization, memoryUsed, temperature, isLoading, error, refetch }` | `/api/system/gpu` |
| `useGpuHistory` | GPU polling with history buffer (legacy) | `{ pollingInterval?, maxDataPoints?, autoStart? }` | `{ current, history, isLoading, error, start, stop, clearHistory }` | `/api/system/gpu` |

### WebSocket Hooks

| Hook | Purpose | Parameters | Return Value | Endpoint/Source |
|------|---------|------------|--------------|-----------------|
| `useWebSocket` | Low-level WebSocket connection manager | `WebSocketOptions` | `{ isConnected, lastMessage, send, connect, disconnect, hasExhaustedRetries, reconnectCount, lastHeartbeat }` | Any WebSocket |
| `useWebSocketStatus` | Enhanced WebSocket with channel status | `{ url, name, ...options }` | `{ channelStatus, lastMessage, send, connect, disconnect }` | Any WebSocket |
| `useConnectionStatus` | Unified status for events+system channels | None | `{ summary, events, systemStatus, clearEvents }` | `/ws/events`, `/ws/system` |
| `useEventStream` | Security events via WebSocket | None | `{ events, isConnected, latestEvent, clearEvents }` | `/ws/events` |
| `useAlertWebSocket` | Alert state changes via WebSocket | `{ onAlertCreated?, onAlertUpdated?, onAlertAcknowledged?, onAlertResolved?, autoInvalidateCache? }` | `{ isConnected, lastAlert, lastEventType, connect, disconnect, hasExhaustedRetries, reconnectCount }` | `/ws/events` |
| `useEventLifecycleWebSocket` | Event lifecycle (create/update/delete) | `{ onEventCreated?, onEventUpdated?, onEventDeleted?, autoInvalidateCache? }` | `{ isConnected, lastEventPayload, lastEventType, connect, disconnect }` | `/ws/events` |
| `useCameraStatusWebSocket` | Camera status changes via WebSocket | `{ onCameraOnline?, onCameraOffline?, onCameraError?, onCameraUpdated? }` | `{ cameraStatuses, isConnected, reconnectCount, lastEvent, reconnect }` | `/ws/events` |
| `useSceneChangeAlerts` | Scene change detection alerts | `{ maxAlerts?, autoDismissMs? }` | `{ alerts, unacknowledgedCount, hasAlerts, dismissAlert, dismissAll, hasBlockedCameras, hasTamperedCameras, blockedCameraIds, tamperedCameraIds }` | `/ws/events` |
| `useJobWebSocket` | Background job status updates | `{ jobType?, onJobUpdate? }` | `{ jobs, isConnected, reconnectCount }` | `/ws/jobs` |
| `useJobLogsWebSocket` | Streaming job logs via WebSocket | `{ jobId, enabled? }` | `{ logs, isConnected, clearLogs }` | `/ws/jobs/{id}/logs` |
| `useWebSocketEvent` | Subscribe to specific WebSocket event types | `{ eventType, handler }` | `{ isConnected }` | Any WebSocket |
| `useWebSocketEvents` | Subscribe to multiple WebSocket event types | `{ handlers: Record }` | `{ isConnected }` | Any WebSocket |

### Data Query Hooks (TanStack Query)

| Hook | Purpose | Parameters | Return Value | Endpoint |
|------|---------|------------|--------------|----------|
| `useCamerasQuery` | Fetch all cameras | `{ enabled? }` | `{ data, cameras, isLoading, error, refetch }` | `/api/cameras` |
| `useCameraQuery` | Fetch single camera | `cameraId: string` | `{ data, isLoading, error, refetch }` | `/api/cameras/{id}` |
| `useEventsInfiniteQuery` | Infinite scroll security events | `{ filters?, limit? }` | `{ data, events, hasNextPage, fetchNextPage, isLoading }` | `/api/events` |
| `useRecentEventsQuery` | Recent events for dashboard | `{ limit?, enabled? }` | `{ data, events, isLoading, error }` | `/api/events/recent` |
| `useDetectionsInfiniteQuery` | Infinite scroll detections | `{ filters?, limit? }` | `{ data, detections, hasNextPage, fetchNextPage }` | `/api/detections` |
| `useAlertsInfiniteQuery` | Infinite scroll alerts | `{ riskFilter?, status? }` | `{ data, alerts, hasNextPage, fetchNextPage }` | `/api/alerts` |
| `useEntitiesInfiniteQuery` | Infinite scroll entities | `{ timeRange?, limit? }` | `{ data, entities, hasNextPage, fetchNextPage }` | `/api/entities` |
| `useEntityHistory` | Entity sighting history | `entityId: string` | `{ data, history, isLoading, error }` | `/api/entities/{id}/history` |
| `useEntityStats` | Entity statistics | `entityId: string` | `{ data, stats, isLoading, error }` | `/api/entities/{id}/stats` |
| `useStorageStatsQuery` | Storage disk usage | `{ enabled?, refetchInterval? }` | `{ data, diskUsagePercent, diskTotalBytes, isLoading, error }` | `/api/system/storage` |
| `useCameraUptimeQuery` | Camera uptime statistics | `cameraId: string` | `{ data, isLoading, error }` | `/api/cameras/{id}/uptime` |
| `useDetectionTrendsQuery` | Detection trends over time | `{ timeRange }` | `{ data, trends, isLoading, error }` | `/api/analytics/detection-trends` |
| `useJobsSearchQuery` | Search background jobs | `{ query?, status?, type? }` | `{ data, jobs, isLoading, error }` | `/api/jobs/search` |
| `useJobHistoryQuery` | Job execution history | `jobId: string` | `{ data, history, isLoading, error }` | `/api/jobs/{id}/history` |
| `useJobLogsQuery` | Fetch job logs (REST) | `jobId: string` | `{ data, logs, isLoading, error }` | `/api/jobs/{id}/logs` |
| `useRecordingsQuery` | Fetch request recordings | `{ limit?, enabled? }` | `{ data, recordings, totalCount, isEmpty, isLoading }` | `/api/debug/recordings` |
| `useDebugConfigQuery` | Debug configuration | `{ enabled? }` | `{ data, entries, isLoading, error }` | `/api/debug/config` |
| `useLogLevelQuery` | Current log level | `{ enabled? }` | `{ data, level, isLoading, error }` | `/api/debug/log-level` |
| `useProfileQuery` | Profiling status | `{ enabled? }` | `{ data, isActive, isLoading, error }` | `/api/debug/profile` |
| `useSystemConfigQuery` | System configuration | `{ enabled? }` | `{ data, config, isLoading, error }` | `/api/system/config` |
| `usePromptConfig` | Prompt configuration | `promptName: string` | `{ data, config, isLoading, error }` | `/api/prompts/{name}` |
| `usePromptHistory` | Prompt version history | `promptName: string` | `{ data, versions, isLoading, error }` | `/api/prompts/{name}/history` |
| `usePipelineErrorsQuery` | Pipeline error logs | `{ enabled? }` | `{ data, errors, isLoading, error }` | `/api/debug/pipeline-errors` |
| `useRedisDebugInfoQuery` | Redis debug info | `{ enabled? }` | `{ data, info, isLoading, error }` | `/api/debug/redis` |
| `useWebSocketConnectionsQuery` | Active WebSocket connections | `{ enabled? }` | `{ data, connections, isLoading, error }` | `/api/debug/websocket-connections` |

### Data Mutation Hooks (TanStack Query)

| Hook | Purpose | Parameters | Return Value | Endpoint |
|------|---------|------------|--------------|----------|
| `useCameraMutation` | Create/update/delete cameras | None | `{ createMutation, updateMutation, deleteMutation }` | `/api/cameras` |
| `useRecordingMutations` | Replay/delete request recordings | None | `{ replayMutation, deleteMutation, clearAllMutation, isReplaying, isDeleting, isClearing }` | `/api/debug/recordings` |
| `useProfilingMutations` | Start/stop/download profiling | None | `useStartProfilingMutation`, `useStopProfilingMutation`, `useDownloadProfileMutation` | `/api/debug/profile` |
| `useJobMutations` | Cancel/retry/delete jobs | None | `{ cancelMutation, retryMutation, deleteMutation }` | `/api/jobs` |
| `useCleanupPreviewMutation` | Preview storage cleanup | None | `{ mutation, previewData, isPending, preview, reset }` | `/api/system/storage/cleanup` |
| `useCleanupMutation` | Execute storage cleanup | None | `{ mutation, isPending, error }` | `/api/system/storage/cleanup` |
| `useAdminMutations` | Admin seed/clear operations | None | `useSeedCamerasMutation`, `useSeedEventsMutation`, `useClearSeededDataMutation` | `/api/admin/*` |
| `useUpdatePromptConfig` | Update prompt configuration | None | `{ mutation, isPending, error }` | `/api/prompts/{name}` |
| `useRestorePromptVersion` | Restore prompt to version | None | `{ mutation, isPending, error }` | `/api/prompts/{name}/restore` |
| `useSetLogLevelMutation` | Change log level | None | `{ setLevel, isPending, error }` | `/api/debug/log-level` |
| `useSnoozeEvent` | Snooze security event | None | `{ snooze, isPending, error }` | `/api/events/{id}/snooze` |

### Saved Searches & Persistence Hooks

| Hook | Purpose | Parameters | Return Value | Storage |
|------|---------|------------|--------------|---------|
| `useSavedSearches` | Manage saved searches | None | `{ savedSearches, saveSearch, deleteSearch, loadSearch, clearAll }` | localStorage (`hsi_saved_searches`) |
| `useLocalStorage` | Generic localStorage persistence | `key: string, defaultValue: T` | `[value, setValue]` | localStorage |
| `useSettings` | App settings management | None | `{ settings, updateSettings, resetSettings }` | localStorage |
| `useSystemPageSections` | System page section states | None | `{ sectionStates, toggleSection, expandAll, collapseAll }` | localStorage |
| `useDevToolsSections` | Dev tools section states | None | `{ sectionStates, toggleSection }` | localStorage |

### UI/UX Hooks

| Hook | Purpose | Parameters | Return Value |
|------|---------|------------|--------------|
| `useKeyboardShortcuts` | Global keyboard navigation (g+d, ?, Cmd+K) | `{ onOpenHelp?, onOpenCommandPalette? }` | `{ isPendingChord }` |
| `useListNavigation` | j/k style list navigation | `{ itemCount, onSelect?, wrap? }` | `{ selectedIndex, setSelectedIndex, resetSelection }` |
| `useToast` | Toast notifications via sonner | None | `{ success, error, warning, info, loading, dismiss, promise }` |
| `useIsMobile` | Mobile viewport detection | `breakpoint?: number` | `boolean` |
| `useSwipeGesture` | Touch swipe detection | `{ onSwipe, threshold?, timeout? }` | `ref callback` |
| `useInfiniteScroll` | Intersection observer for infinite scroll | `{ onLoadMore, hasMore, threshold? }` | `{ ref, isLoading }` |
| `useDateRangeState` | Date range with URL persistence | `{ defaultPreset? }` | `{ range, preset, setPreset, setCustomRange }` |
| `usePaginationState` | Pagination state with URL sync | `{ type, defaultPageSize? }` | Cursor or offset pagination state |
| `useRateLimitCountdown` | Countdown timer for rate limits | `retryAfter: number` | `{ countdown, isRateLimited, formatCountdown }` |
| `useRateLimit` | Rate limit state management | None | `{ isRateLimited, retryAfter, setRateLimited, clear }` |
| `useAudioNotifications` | Audio alert sounds | `{ enabled? }` | `{ playSound, stopSound }` |
| `useDesktopNotifications` | Desktop notification API | `{ enabled? }` | `{ show, permission, requestPermission }` |

### PWA/Offline Hooks

| Hook | Purpose | Parameters | Return Value |
|------|---------|------------|--------------|
| `useNetworkStatus` | Browser connectivity tracking | `{ onOnline?, onOffline? }` | `{ isOnline, isOffline, lastOnlineAt, wasOffline, clearWasOffline }` |
| `useCachedEvents` | IndexedDB event caching | None | `{ cachedEvents, cachedCount, isInitialized, cacheEvent, loadCachedEvents, removeCachedEvent, clearCache }` |
| `usePushNotifications` | Browser push notifications | None | `{ permission, isSupported, hasPermission, requestPermission, showNotification, showSecurityAlert }` |

### Utility Hooks

| Hook | Purpose | Parameters | Return Value |
|------|---------|------------|--------------|
| `usePolling` | Generic REST endpoint polling | `{ fetcher, interval, enabled?, onSuccess?, onError? }` | `{ data, loading, error, refetch }` |
| `useThrottledValue` | Throttle value updates | `value: T, { interval? }` | `T` (throttled) |
| `useRetry` | Retry with exponential backoff | `{ maxAttempts?, baseDelay? }` | `{ retry, isRetrying, retryCount, reset }` |
| `useCursorPaginatedQuery` | Generic cursor pagination | `{ queryKey, fetcher, limit? }` | `{ data, items, hasNextPage, fetchNextPage, hasPreviousPage, fetchPreviousPage }` |
| `useFormWithApiErrors` | Map API validation errors to forms | `form: UseFormReturn` | `{ applyApiValidationErrors, useApiMutation }` |
| `useServiceStatus` | Per-service status tracking | `{ onStatusChange? }` | `{ services, getStatus }` |
| `useDebounce` | Debounce value updates | `value: T, delay: number` | `T` (debounced) |
| `typedEventEmitter` | Type-safe WebSocket event emitter class | N/A (class) | `TypedWebSocketEmitter` |

## Key Files

| File                         | Purpose                                                           | Exported |
| ---------------------------- | ----------------------------------------------------------------- | -------- |
| `index.ts`                   | Central export point for hooks and types                          | N/A      |
| `typedEventEmitter.ts`       | Type-safe WebSocket event emitter with compile-time checking      | Yes      |
| `usePolling.ts`              | Generic polling hook for REST endpoints with interval fetching    | Yes      |
| `useWebSocket.ts`            | Low-level WebSocket connection manager                            | Yes      |
| `useWebSocketStatus.ts`      | Enhanced WebSocket with channel status tracking                   | Yes      |
| `useConnectionStatus.ts`     | Unified connection status for all WS channels                     | Yes      |
| `useEventStream.ts`          | Security events via `/ws/events` WebSocket                        | Yes      |
| `useSystemStatus.ts`         | System health via `/ws/system` WebSocket                          | Yes      |
| `useGpuHistory.ts`           | GPU metrics polling with history buffer                           | Yes      |
| `useHealthStatus.ts`         | REST-based health status polling (legacy)                         | Yes      |
| `useHealthStatusQuery.ts`    | TanStack Query-based health status fetching                       | Yes      |
| `useFullHealthQuery.ts`      | TanStack Query for comprehensive health with circuit breakers     | Yes      |
| `useCamerasQuery.ts`         | TanStack Query hooks for camera CRUD operations                   | Yes      |
| `useGpuStatsQuery.ts`        | TanStack Query for GPU stats and history                          | Yes      |
| `useModelZooStatusQuery.ts`  | TanStack Query for Model Zoo status with VRAM stats               | Yes      |
| `useStorageStatsQuery.ts`    | TanStack Query for storage stats with cleanup mutation            | Yes      |
| `usePerformanceMetrics.ts`   | System performance metrics via WebSocket                          | Yes      |
| `useAIMetrics.ts`            | Fetches AI performance metrics from multiple endpoints            | Yes      |
| `useAIServiceStatus.ts`      | AI service degradation and circuit breaker status via WebSocket   | Yes      |
| `useDetectionEnrichment.ts`  | Fetches enrichment data for a specific detection                  | Yes      |
| `useModelZooStatus.ts`       | Fetches and polls Model Zoo status with VRAM stats (legacy)       | Yes      |
| `useSavedSearches.ts`        | Manages saved searches in localStorage                            | Yes      |
| `useLocalStorage.ts`         | Generic localStorage persistence hook                             | Yes      |
| `useThrottledValue.ts`       | Throttles value updates to reduce re-renders                      | Yes      |
| `useToast.ts`                | Toast notifications using sonner                                  | Yes      |
| `useKeyboardShortcuts.ts`    | Global keyboard navigation shortcuts (g+d, ?, Cmd+K)              | Yes      |
| `useListNavigation.ts`       | j/k style list navigation with Enter selection                    | Yes      |
| `useIsMobile.ts`             | Mobile viewport detection via MediaQueryList                      | Yes      |
| `useSwipeGesture.ts`         | Touch swipe gesture detection                                     | Yes      |
| `useNetworkStatus.ts`        | Browser network connectivity tracking for PWA                     | Yes      |
| `useCachedEvents.ts`         | Offline event caching using IndexedDB                             | Yes      |
| `usePushNotifications.ts`    | Browser push notification permissions and display                 | Yes      |
| `useStorageStats.ts`         | Storage disk usage polling with cleanup preview (uses usePolling) | No       |
| `useServiceStatus.ts`        | Per-service status tracking                                       | No       |
| `useSidebarContext.ts`       | Context hook for mobile sidebar state                             | No       |
| `useSystemPageSections.ts`   | System page collapsible section state management                  | No       |
| `webSocketManager.ts`        | Singleton WebSocket connection manager with deduplication         | No       |

### Test Files

| File                              | Coverage                                                  |
| --------------------------------- | --------------------------------------------------------- |
| `typedEventEmitter.test.ts`       | Event subscription, emission, once, message handling      |
| `usePolling.test.ts`              | Generic polling, callbacks, error handling, interval      |
| `useWebSocket.test.ts`            | Connection lifecycle, message handling, reconnects        |
| `useWebSocket.timeout.test.ts`    | Connection timeout scenarios                              |
| `useWebSocketStatus.test.ts`      | Channel status tracking, reconnect state                  |
| `useConnectionStatus.test.ts`     | Multi-channel status aggregation                          |
| `useEventStream.test.ts`          | Event buffering, envelope parsing, non-event filtering    |
| `useSystemStatus.test.ts`         | Backend message transformation, type guards               |
| `useGpuHistory.test.ts`           | Polling, history buffer, start/stop controls              |
| `useHealthStatus.test.ts`         | REST polling, error handling, refresh                     |
| `useHealthStatus.msw.test.ts`     | MSW-based integration tests                               |
| `useHealthStatusQuery.test.ts`    | TanStack Query health status, caching, refetch            |
| `useCamerasQuery.test.ts`         | TanStack Query cameras CRUD, cache invalidation           |
| `useGpuStatsQuery.test.ts`        | TanStack Query GPU stats and history                      |
| `useModelZooStatusQuery.test.ts`  | TanStack Query Model Zoo polling, VRAM calculation        |
| `useStorageStatsQuery.test.ts`    | TanStack Query storage stats and cleanup preview          |
| `useStorageStats.test.ts`         | Storage polling, cleanup preview                          |
| `useStorageStats.msw.test.ts`     | MSW-based integration tests                               |
| `useServiceStatus.test.ts`        | Service status parsing                                    |
| `usePerformanceMetrics.test.ts`   | WebSocket performance metrics, alerts, history buffer     |
| `useAIMetrics.test.ts`            | Multi-endpoint fetching, state combination, polling       |
| `useAIServiceStatus.test.ts`      | AI degradation mode, service status, feature availability |
| `useDetectionEnrichment.test.ts`  | Detection enrichment fetching, loading/error states       |
| `useModelZooStatus.test.ts`       | Model Zoo polling, VRAM calculation, refresh              |
| `useModelZooStatus.msw.test.ts`   | MSW-based integration tests                               |
| `useSavedSearches.test.ts`        | LocalStorage persistence, CRUD operations, cross-tab sync |
| `useLocalStorage.test.ts`         | LocalStorage read/write, SSR safety                       |
| `useThrottledValue.test.ts`       | Value throttling, interval batching                       |
| `useToast.test.ts`                | Toast variants, actions, promise-based toasts             |
| `useKeyboardShortcuts.test.ts`    | Chord detection, modifier keys, input field bypass        |
| `useListNavigation.test.ts`       | j/k navigation, Home/End, Enter selection                 |
| `useIsMobile.test.ts`             | Viewport detection, resize handling                       |
| `useSwipeGesture.test.ts`         | Swipe detection, threshold, timeout                       |
| `useNetworkStatus.test.ts`        | Online/offline detection, callbacks                       |
| `useCachedEvents.test.ts`         | IndexedDB CRUD operations                                 |
| `usePushNotifications.test.ts`    | Permission handling, notification display                 |
| `useSidebarContext.test.tsx`      | Context provider, mobile menu state                       |
| `webSocketManager.test.ts`        | Connection deduplication, ref counting, subscribers       |
| `webSocketManager.timeout.test.ts`| Timeout and reconnection scenarios                        |

## Hook Details

### `typedEventEmitter.ts`

Type-safe WebSocket event emitter class for compile-time type checking of event names and payloads.

**Features:**

- Compile-time type safety for event subscription and emission
- Uses `Set<Handler>` for O(1) add/remove and duplicate prevention
- `handleMessage()` method for automatic WebSocket message routing
- `once()` method for one-time event handlers
- Error isolation: one handler failure doesn't break others

**Key Classes/Functions:**

```typescript
class TypedWebSocketEmitter {
  on<K extends WebSocketEventKey>(event: K, handler: WebSocketEventHandler<K>): () => void;
  off<K extends WebSocketEventKey>(event: K, handler: WebSocketEventHandler<K>): void;
  emit<K extends WebSocketEventKey>(event: K, data: WebSocketEventMap[K]): void;
  once<K extends WebSocketEventKey>(event: K, handler: WebSocketEventHandler<K>): () => void;
  handleMessage(message: unknown): boolean;
  has(event: WebSocketEventKey): boolean;
  listenerCount(event: WebSocketEventKey): number;
  removeAllListeners(event: WebSocketEventKey): void;
  clear(): void;
  events(): WebSocketEventKey[];
}

// Factory function
function createTypedEmitter(): TypedWebSocketEmitter;

// Safe emission with runtime type validation
function safeEmit(emitter: TypedWebSocketEmitter, event: unknown, data: unknown): boolean;
```

**Usage Example:**

```typescript
const emitter = createTypedEmitter();

// Type-safe subscription
const unsubscribe = emitter.on('event', (data) => {
  console.log(data.risk_score); // TypeScript knows this is SecurityEventData
});

// Handle raw WebSocket message
ws.onmessage = (e) => {
  const message = JSON.parse(e.data);
  emitter.handleMessage(message);
};
```

### `useFullHealthQuery.ts`

TanStack Query hook for comprehensive system health with circuit breaker states.

**Features:**

- Fetches from `GET /api/system/health/full`
- Tracks health of all AI services with circuit breaker states
- Infrastructure health (PostgreSQL, Redis)
- Background worker status
- Critical vs non-critical service health counts

**Options Interface:**

```typescript
interface UseFullHealthQueryOptions {
  enabled?: boolean;              // default: true
  refetchInterval?: number | false; // default: 30000
  staleTime?: number;             // default: REALTIME_STALE_TIME (5s)
}
```

**Return Interface:**

```typescript
interface UseFullHealthQueryReturn {
  data: FullHealthResponse | undefined;
  isLoading: boolean;
  isRefetching: boolean;
  error: Error | null;
  isStale: boolean;
  overallStatus: ServiceHealthState | null;
  isReady: boolean;
  statusMessage: string;
  postgres: InfrastructureHealthStatus | null;
  redis: InfrastructureHealthStatus | null;
  aiServices: AIServiceHealthStatus[];
  circuitBreakers: CircuitBreakerSummary | null;
  workers: WorkerHealthStatusFull[];
  criticalUnhealthyCount: number;
  nonCriticalUnhealthyCount: number;
  refetch: () => Promise<unknown>;
}
```

### `useAIServiceStatus.ts`

Hook for tracking AI service degradation status via WebSocket.

**Features:**

- Listens to `ai_service_status` messages from `/ws/events`
- Tracks degradation modes: `normal`, `degraded`, `minimal`, `offline`
- Provides circuit breaker states for each AI service
- Tracks available features based on service availability
- Type guards for runtime message validation

**Degradation Modes:**

| Mode | Description |
|------|-------------|
| `normal` | All AI services healthy |
| `degraded` | Non-critical services (Florence-2, CLIP) unavailable |
| `minimal` | Critical services (RT-DETRv2, Nemotron) partially available |
| `offline` | All AI services unavailable |

**Types:**

```typescript
type AIServiceName = 'rtdetr' | 'nemotron' | 'florence' | 'clip';
type DegradationLevel = 'normal' | 'degraded' | 'minimal' | 'offline';
type CircuitState = 'closed' | 'open' | 'half_open';

interface AIServiceState {
  service: AIServiceName;
  status: 'healthy' | 'degraded' | 'unavailable';
  circuit_state: CircuitState;
  last_success: string | null;
  failure_count: number;
  error_message: string | null;
  last_check: string | null;
}
```

**Return Interface:**

```typescript
interface UseAIServiceStatusResult {
  degradationMode: DegradationLevel;
  services: Record<AIServiceName, AIServiceState | null>;
  availableFeatures: string[];
  hasUnavailableService: boolean;
  isOffline: boolean;
  isDegraded: boolean;
  getServiceState: (name: AIServiceName) => AIServiceState | null;
  isFeatureAvailable: (feature: string) => boolean;
  lastUpdate: string | null;
}
```

**Usage Example:**

```typescript
function AIStatusBanner() {
  const { degradationMode, isDegraded, services, getServiceState } = useAIServiceStatus();

  if (!isDegraded) return null;

  const rtdetr = getServiceState('rtdetr');

  return (
    <Banner variant="warning">
      System in {degradationMode} mode.
      {rtdetr?.status === 'unavailable' && ' Object detection unavailable.'}
    </Banner>
  );
}
```

### `useCircuitBreakerStatus.ts`

Hook for tracking circuit breaker states via WebSocket. Circuit breakers protect services from cascading failures by temporarily blocking requests when a service is unhealthy.

**Features:**

- Subscribes to `circuit_breaker_update` messages via `/ws/system`
- Tracks per-breaker state, failure counts, and timestamps
- Provides summary counts and derived boolean flags
- Type-safe with comprehensive type guards

**Circuit Breaker States:**

| State | Description |
|-------|-------------|
| `closed` | Normal operation, requests flow through |
| `open` | Service unhealthy, requests are blocked |
| `half_open` | Testing if service has recovered |

**Types:**

```typescript
type CircuitBreakerStateType = 'closed' | 'open' | 'half_open';

interface CircuitBreakerState {
  name: string;                      // e.g., 'rtdetr', 'nemotron'
  state: CircuitBreakerStateType;
  failure_count: number;
  success_count: number;
  last_failure_time?: string | null;
  last_success_time?: string | null;
}

interface CircuitBreakerSummary {
  total: number;
  closed: number;
  open: number;
  half_open: number;
}
```

**Return Interface:**

```typescript
interface UseCircuitBreakerStatusReturn {
  breakers: Record<string, CircuitBreakerState>;
  summary: CircuitBreakerSummary;
  hasOpenBreaker: boolean;      // True if any breaker is open
  hasHalfOpenBreaker: boolean;  // True if any breaker is half_open
  allClosed: boolean;           // True if all breakers are healthy
  lastUpdate: string | null;
  getBreaker: (name: string) => CircuitBreakerState | null;
  isConnected: boolean;
}
```

**Usage Example:**

```typescript
function CircuitBreakerDisplay() {
  const { breakers, summary, hasOpenBreaker, allClosed } = useCircuitBreakerStatus();

  return (
    <div>
      <Badge color={allClosed ? 'green' : 'red'}>
        {summary.closed}/{summary.total} Healthy
      </Badge>
      {hasOpenBreaker && (
        <Alert>Some services are protected by open circuit breakers</Alert>
      )}
      {Object.values(breakers).map(breaker => (
        <div key={breaker.name}>
          {breaker.name}: {breaker.state} (failures: {breaker.failure_count})
        </div>
      ))}
    </div>
  );
}
```

### `useSceneChangeAlerts.ts`

Hook for tracking unacknowledged scene change alerts from WebSocket. Scene changes indicate potential camera tampering and should be reviewed.

**Features:**

- Subscribes to `scene_change` messages via `/ws/events`
- Tracks unacknowledged alerts with dismiss/acknowledge functionality
- Provides computed flags for blocked and tampered cameras
- Configurable max alerts and auto-dismiss timeout

**Change Types:**

| Type | Severity | Description |
|------|----------|-------------|
| `view_blocked` | High | Camera view is obstructed |
| `view_tampered` | High | Camera has been tampered with |
| `angle_changed` | Medium | Camera angle has shifted |

**Types:**

```typescript
interface SceneChangeAlert {
  id: number;
  cameraId: string;
  detectedAt: string;
  changeType: string;
  similarityScore: number;  // 0-1, lower = more different from baseline
  dismissed: boolean;
  receivedAt: Date;
}

interface UseSceneChangeAlertsOptions {
  maxAlerts?: number;       // Default: 50
  autoDismissMs?: number;   // 0 = never auto-dismiss
}
```

**Return Interface:**

```typescript
interface UseSceneChangeAlertsReturn {
  alerts: SceneChangeAlert[];
  unacknowledgedCount: number;
  hasAlerts: boolean;
  dismissAlert: (id: number) => void;
  dismissAll: () => void;
  acknowledgeAlert: (id: number) => void;  // alias for dismissAlert
  acknowledgeAll: () => void;              // alias for dismissAll
  clearAlerts: () => void;
  isConnected: boolean;
  hasBlockedCameras: boolean;
  hasTamperedCameras: boolean;
  blockedCameraIds: string[];
  tamperedCameraIds: string[];
}
```

**Usage Example:**

```typescript
function SceneChangeMonitor() {
  const { hasAlerts, unacknowledgedCount, alerts, dismissAll, hasBlockedCameras } =
    useSceneChangeAlerts({ maxAlerts: 100 });

  return (
    <div>
      {hasBlockedCameras && <Alert severity="critical">Camera view blocked!</Alert>}
      {hasAlerts && (
        <Badge count={unacknowledgedCount} onClick={dismissAll}>
          Scene Changes
        </Badge>
      )}
      {alerts.map(alert => (
        <div key={alert.id}>
          {alert.cameraId}: {formatChangeType(alert.changeType)}
        </div>
      ))}
    </div>
  );
}
```

### `useAnalysisStream.ts`

React hook for SSE-based streaming LLM analysis. Provides progressive updates during Nemotron inference, allowing the UI to display partial results and typing indicators.

**Features:**

- Creates Server-Sent Events connection for streaming analysis
- Tracks connection status: `idle`, `connecting`, `connected`, `complete`, `error`
- Accumulates text progressively during inference
- Provides callbacks for progress, completion, and errors
- Safe cleanup on unmount

**Types:**

```typescript
type AnalysisStreamStatus = 'idle' | 'connecting' | 'connected' | 'complete' | 'error';

interface AnalysisStreamResult {
  eventId: number;
  riskScore: number;    // 0-100
  riskLevel: string;
  summary: string;
}

interface AnalysisStreamError {
  code: string;
  message: string;
  recoverable: boolean;
}
```

**Return Interface:**

```typescript
interface UseAnalysisStreamReturn {
  status: AnalysisStreamStatus;
  accumulatedText: string;         // Progressive text during streaming
  result: AnalysisStreamResult | null;
  error: AnalysisStreamError | null;
  startStream: (params: AnalysisStreamParams) => void;
  stopStream: () => void;
  isStreaming: boolean;
}
```

**Usage Example:**

```typescript
function LiveAnalysis({ batchId, cameraId }) {
  const { status, accumulatedText, result, error, startStream, stopStream, isStreaming } =
    useAnalysisStream({
      onComplete: (result) => console.log('Analysis complete:', result.riskScore),
    });

  useEffect(() => {
    startStream({ batchId, cameraId });
    return () => stopStream();
  }, [batchId, cameraId, startStream, stopStream]);

  if (error) return <div>Error: {error.message}</div>;
  if (isStreaming) return <div>Analyzing... {accumulatedText}</div>;
  if (result) return <div>Risk: {result.riskLevel} ({result.riskScore})</div>;
  return null;
}
```

### `useRecordingMutations.ts`

TanStack Query mutations for request recording operations (replay, delete, clear). Used in the Developer Tools panel for debugging API interactions.

**Features:**

- Replay recorded requests and compare responses
- Delete individual recordings
- Clear all recordings
- Automatic cache invalidation on success

**Return Interface:**

```typescript
interface UseRecordingMutationsReturn {
  replayMutation: UseMutationResult<ReplayResponse, Error, string>;
  deleteMutation: UseMutationResult<{ message: string }, Error, string>;
  clearAllMutation: UseMutationResult<{ message: string; deleted_count: number }, Error, void>;
  isReplaying: boolean;
  isDeleting: boolean;
  isClearing: boolean;
  isAnyMutating: boolean;
}
```

**Usage Example:**

```typescript
function RecordingsPanel() {
  const { replayMutation, deleteMutation, clearAllMutation, isReplaying } = useRecordingMutations();

  const handleReplay = (recordingId: string) => {
    replayMutation.mutate(recordingId, {
      onSuccess: (data) => console.log('Replay result:', data),
    });
  };

  const handleDelete = (recordingId: string) => {
    deleteMutation.mutate(recordingId);
  };

  const handleClearAll = () => {
    if (confirm('Delete all recordings?')) {
      clearAllMutation.mutate();
    }
  };

  return (
    <div>
      <Button onClick={handleClearAll} disabled={clearAllMutation.isPending}>
        Clear All
      </Button>
      {/* ... recording list ... */}
    </div>
  );
}
```

### `useProfilingMutations.ts`

React Query mutations for performance profiling operations. Used in the Developer Tools panel to capture and analyze backend performance.

**Features:**

- Start CPU profiling with `useStartProfilingMutation`
- Stop profiling and get results with `useStopProfilingMutation`
- Download .prof file with `useDownloadProfileMutation`
- Automatic cache invalidation on state changes

**Return Interfaces:**

```typescript
interface UseStartProfilingMutationReturn {
  start: () => Promise<StartProfilingResponse>;
  isPending: boolean;
  error: Error | null;
  reset: () => void;
}

interface UseStopProfilingMutationReturn {
  stop: () => Promise<StopProfilingResponse>;
  results: StopProfilingResponse | undefined;  // Top functions by CPU time
  isPending: boolean;
  error: Error | null;
  reset: () => void;
}

interface UseDownloadProfileMutationReturn {
  download: () => Promise<Blob>;
  isPending: boolean;
  error: Error | null;
  reset: () => void;
}
```

**Usage Example:**

```typescript
function ProfilingPanel() {
  const { start, isPending: isStarting } = useStartProfilingMutation();
  const { stop, results, isPending: isStopping } = useStopProfilingMutation();
  const { download, isPending: isDownloading } = useDownloadProfileMutation();

  const handleStart = async () => {
    await start();
    console.log('Profiling started');
  };

  const handleStop = async () => {
    const result = await stop();
    console.log('Top functions:', result.results.top_functions);
  };

  const handleDownload = async () => {
    const blob = await download();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'profile.prof';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <Button onClick={handleStart} disabled={isStarting}>Start Profiling</Button>
      <Button onClick={handleStop} disabled={isStopping}>Stop Profiling</Button>
      <Button onClick={handleDownload} disabled={isDownloading}>Download</Button>
      {results && (
        <ProfilingResults data={results.results} />
      )}
    </div>
  );
}
```

### `useCachedEvents.ts`

Hook for offline event caching using IndexedDB (PWA support).

**Features:**

- Stores security events in IndexedDB for offline access
- Automatic database initialization with indexes
- CRUD operations for cached events
- Events sorted by timestamp (newest first)

**Return Interface:**

```typescript
interface UseCachedEventsReturn {
  cachedEvents: CachedEvent[];
  cachedCount: number;
  isInitialized: boolean;
  error: string | null;
  cacheEvent: (event: CachedEvent) => Promise<void>;
  loadCachedEvents: () => Promise<void>;
  removeCachedEvent: (id: string) => Promise<void>;
  clearCache: () => Promise<void>;
}
```

### `usePolling.ts`

Generic reusable hook for polling REST endpoints at a configurable interval.

**Features:**

- Fetches data on mount and at regular intervals
- Configurable polling interval
- Enable/disable polling dynamically
- Success and error callbacks
- Manual refetch capability
- Type-safe with generics

**Options Interface:**

```typescript
interface UsePollingOptions<T> {
  fetcher: () => Promise<T>;     // Async function to fetch data
  interval: number;               // Polling interval in milliseconds
  enabled?: boolean;              // Enable polling (default: true)
  onSuccess?: (data: T) => void;  // Called on successful fetch
  onError?: (error: Error) => void; // Called on fetch error
}
```

**Return Interface:**

```typescript
interface UsePollingReturn<T> {
  data: T | null;                 // Fetched data
  loading: boolean;               // Initial loading state only
  error: Error | null;            // Error from last fetch
  refetch: () => Promise<void>;   // Manual refetch function
}
```

**Usage Example:**

```typescript
const { data, loading, error, refetch } = usePolling({
  fetcher: () => fetchStorageStats(),
  interval: 60000,        // Poll every minute
  enabled: true,
  onSuccess: (data) => console.log('Fetched:', data),
  onError: (error) => console.error('Error:', error),
});
```

**Note:** The `loading` state is `true` only during the initial fetch. This follows the pattern used by TanStack Query's `isLoading` vs `isFetching`. Use `refetch` for manual refresh without loading state changes.

### `useWebSocket.ts`

Low-level WebSocket connection manager with automatic reconnection logic.

**Features:**

- Automatic reconnection with configurable attempts and intervals (default: 5 attempts, 3s interval)
- Message serialization (JSON) and deserialization with fallback to raw data
- Connection state tracking (`isConnected`)
- Manual connect/disconnect controls
- Lifecycle callbacks: `onOpen`, `onClose`, `onError`, `onMessage`, `onHeartbeat`
- SSR-safe: checks for `window.WebSocket` availability
- Prevents duplicate connections (checks OPEN/CONNECTING states)
- Handles server heartbeat (ping) messages automatically
- Tracks last heartbeat timestamp for connection health monitoring

**Options Interface:**

```typescript
interface WebSocketOptions {
  url: string;
  onMessage?: (data: unknown) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  onMaxRetriesExhausted?: () => void;
  onHeartbeat?: () => void; // Called when server heartbeat received
  reconnect?: boolean; // default: true
  reconnectInterval?: number; // default: 1000ms (base for exponential backoff)
  reconnectAttempts?: number; // default: 5
  connectionTimeout?: number; // default: 10000ms
  autoRespondToHeartbeat?: boolean; // default: true - auto-send pong response
}
```

**Return Interface:**

```typescript
interface UseWebSocketReturn {
  isConnected: boolean;
  lastMessage: unknown;
  send: (data: unknown) => void;
  connect: () => void;
  disconnect: () => void;
  hasExhaustedRetries: boolean;
  reconnectCount: number;
  lastHeartbeat: Date | null; // Timestamp of last server heartbeat
}
```

**Server Heartbeat Handling:**

The backend sends periodic heartbeat messages in the format `{"type": "ping"}` to keep connections alive (default: every 30 seconds). The hook:

- Automatically detects these heartbeat messages
- Updates `lastHeartbeat` timestamp for connection health tracking
- Sends `{"type": "pong"}` response by default (controlled by `autoRespondToHeartbeat`)
- Calls the optional `onHeartbeat` callback
- Does NOT update `lastMessage` or call `onMessage` for heartbeats to prevent unnecessary re-renders

### `useEventStream.ts`

High-level hook for receiving security events via WebSocket (`/ws/events` endpoint).

**Features:**

- Receives backend event messages in envelope format: `{type: "event", data: {...}}`
- Type guard functions (`isSecurityEvent`, `isBackendEventMessage`) for message validation
- Ignores non-event messages (e.g., `service_status`, `ping`)
- Maintains in-memory buffer of last 100 events (newest first, constant `MAX_EVENTS`)
- Provides `latestEvent` computed value via `useMemo`
- `clearEvents()` method to reset buffer
- Uses `buildWebSocketUrl()` from api service for URL construction

**SecurityEvent Interface:**

```typescript
interface SecurityEvent {
  id: string | number;
  event_id?: number;
  batch_id?: string;
  camera_id: string;
  camera_name?: string;
  risk_score: number;
  risk_level: 'low' | 'medium' | 'high' | 'critical';
  summary: string;
  timestamp?: string;
  started_at?: string;
}
```

**Return Interface:**

```typescript
interface UseEventStreamReturn {
  events: SecurityEvent[];
  isConnected: boolean;
  latestEvent: SecurityEvent | null;
  clearEvents: () => void;
}
```

### `useSystemStatus.ts`

High-level hook for receiving system health updates via WebSocket (`/ws/system` endpoint).

**Features:**

- Receives backend `system_status` messages and transforms to frontend format
- Tracks GPU metrics: utilization, temperature, memory (used/total)
- Tracks active camera count and overall system health
- Type guard function `isBackendSystemStatus()` for message validation
- Uses `buildWebSocketUrl()` from api service for URL construction

**SystemStatus Interface:**

```typescript
interface SystemStatus {
  health: 'healthy' | 'degraded' | 'unhealthy';
  gpu_utilization: number | null;
  gpu_temperature: number | null;
  gpu_memory_used: number | null;
  gpu_memory_total: number | null;
  active_cameras: number;
  last_update: string;
}
```

**Return Interface:**

```typescript
interface UseSystemStatusReturn {
  status: SystemStatus | null;
  isConnected: boolean;
}
```

### `useGpuHistory.ts`

Hook for polling GPU stats and maintaining a rolling history buffer for time-series visualization.

**Features:**

- Polls `GET /api/system/gpu` at configurable intervals (default: 5000ms)
- Maintains rolling buffer of historical metrics (default: 60 data points)
- Start/stop polling controls
- Clear history method
- Auto-start option (default: true)

**Options Interface:**

```typescript
interface UseGpuHistoryOptions {
  pollingInterval?: number; // default: 5000ms
  maxDataPoints?: number; // default: 60
  autoStart?: boolean; // default: true
}
```

**GpuMetricDataPoint Interface:**

```typescript
interface GpuMetricDataPoint {
  timestamp: string;
  utilization: number;
  memory_used: number;
  temperature: number;
}
```

**Return Interface:**

```typescript
interface UseGpuHistoryReturn {
  current: GPUStats | null;
  history: GpuMetricDataPoint[];
  isLoading: boolean;
  error: string | null;
  start: () => void;
  stop: () => void;
  clearHistory: () => void;
}
```

### `useHealthStatus.ts`

Hook for REST-based health status polling from `GET /api/system/health`.

**Features:**

- Polls health endpoint at configurable intervals (default: 30000ms)
- Provides overall system status and per-service status
- Manual refresh capability
- Mount-safe state updates (tracks mounted state)
- Preserves previous health data on error

**Options Interface:**

```typescript
interface UseHealthStatusOptions {
  pollingInterval?: number; // default: 30000ms
  enabled?: boolean; // default: true
}
```

**Return Interface:**

```typescript
interface UseHealthStatusReturn {
  health: HealthResponse | null;
  isLoading: boolean;
  error: string | null;
  overallStatus: 'healthy' | 'degraded' | 'unhealthy' | null;
  services: Record;
  refresh: () => Promise;
}
```

### `useWebSocketStatus.ts`

Enhanced WebSocket hook that tracks detailed channel status including reconnection state.

**Features:**

- Full WebSocket lifecycle management with reconnection
- Channel-level status tracking (name, state, reconnect attempts)
- Last message timestamp tracking
- SSR-safe (checks for `window.WebSocket` availability)

**Types:**

```typescript
type ConnectionState = 'connected' | 'disconnected' | 'reconnecting';

interface ChannelStatus {
  name: string;
  state: ConnectionState;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  lastMessageTime: Date | null;
}

interface UseWebSocketStatusReturn {
  channelStatus: ChannelStatus;
  lastMessage: unknown;
  send: (data: unknown) => void;
  connect: () => void;
  disconnect: () => void;
}
```

### `useConnectionStatus.ts`

Unified hook that manages both `/ws/events` and `/ws/system` WebSocket channels.

**Features:**

- Single hook for all WebSocket connections
- Aggregated connection summary (overall state, any reconnecting, all connected)
- Stores events in memory buffer (max 100 events)
- Parses backend system status messages

**Return Interface:**

```typescript
interface ConnectionStatusSummary {
  eventsChannel: ChannelStatus;
  systemChannel: ChannelStatus;
  overallState: ConnectionState;
  anyReconnecting: boolean;
  allConnected: boolean;
  totalReconnectAttempts: number;
}

interface UseConnectionStatusReturn {
  summary: ConnectionStatusSummary;
  events: SecurityEvent[];
  systemStatus: BackendSystemStatus | null;
  clearEvents: () => void;
}
```

### `useStorageStats.ts`

Hook for polling storage statistics and previewing cleanup operations.

**Features:**

- Polls `GET /api/system/storage` at configurable intervals (default: 60s)
- Provides disk usage metrics (used, total, free, percent)
- Storage breakdown by category (thumbnails, images, clips)
- Database record counts (events, detections, GPU stats, logs)
- Cleanup preview functionality (dry run mode)

**Options Interface:**

```typescript
interface UseStorageStatsOptions {
  pollInterval?: number; // default: 60000ms
  enablePolling?: boolean; // default: true
}
```

**Return Interface:**

```typescript
interface UseStorageStatsReturn {
  stats: StorageStatsResponse | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise;
  previewCleanup: () => Promise;
  previewLoading: boolean;
  cleanupPreview: CleanupResponse | null;
}
```

### `usePerformanceMetrics.ts`

Hook for real-time system performance metrics via WebSocket (`/ws/system` endpoint).

**Features:**

- Subscribes to `performance_update` messages via the system WebSocket channel
- Maintains circular buffers for historical data at 3 time resolutions (5m, 15m, 60m)
- Tracks GPU metrics, AI model status, inference latencies, database metrics
- Surfaces active performance alerts (warning/critical severity)
- Downsamples updates: 5m buffer gets every update, 15m every 3rd, 60m every 12th

**Types:**

```typescript
type TimeRange = '5m' | '15m' | '60m';

interface PerformanceUpdate {
  timestamp: string;
  gpu: GpuMetrics | null;
  ai_models: Record;
  nemotron: NemotronMetrics | null;
  inference: InferenceMetrics | null;
  databases: Record;
  host: HostMetrics | null;
  containers: ContainerMetrics[];
  alerts: PerformanceAlert[];
}

interface UsePerformanceMetricsReturn {
  current: PerformanceUpdate | null;
  history: PerformanceHistory;
  alerts: PerformanceAlert[];
  isConnected: boolean;
  timeRange: TimeRange;
  setTimeRange: (range: TimeRange) => void;
}
```

### `useGpuStatsQuery.ts`

TanStack Query hooks for GPU statistics (replaces manual polling).

**Features:**

- `useGpuStatsQuery`: Fetches current GPU stats from `GET /api/system/gpu`
- `useGpuHistoryQuery`: Fetches GPU history from `GET /api/system/gpu/history`
- Automatic request deduplication across components
- Built-in caching with configurable stale time
- Default 5s refetch interval for real-time data

**Return Interfaces:**

```typescript
interface UseGpuStatsQueryReturn {
  data: GPUStats | undefined;
  isLoading: boolean;
  isRefetching: boolean;
  error: Error | null;
  isStale: boolean;
  refetch: () => Promise<unknown>;
  utilization: number | null;
  memoryUsed: number | null;
  temperature: number | null;
}

interface UseGpuHistoryQueryReturn {
  data: GPUStatsHistoryResponse | undefined;
  history: GPUStatsHistoryResponse['samples'];
  isLoading: boolean;
  isRefetching: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}
```

### `useModelZooStatusQuery.ts`

TanStack Query hook for Model Zoo status (replaces manual polling).

**Features:**

- Fetches from `GET /api/system/models`
- Provides list of all AI models in the Model Zoo
- Calculates VRAM usage statistics (budget, used, available, percentage)
- Default 10s refetch interval

**Return Interface:**

```typescript
interface UseModelZooStatusQueryReturn {
  data: ModelRegistryResponse | undefined;
  models: ModelStatusResponse[];
  vramStats: VRAMStats | null;
  isLoading: boolean;
  isRefetching: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
}
```

### `useStorageStatsQuery.ts`

TanStack Query hooks for storage statistics.

**Features:**

- `useStorageStatsQuery`: Fetches storage stats from `GET /api/system/storage`
- `useCleanupPreviewMutation`: Mutation for cleanup preview (dry run)
- Longer stale time (5 minutes) since storage changes slowly
- Default 60s refetch interval

**Return Interfaces:**

```typescript
interface UseStorageStatsQueryReturn {
  data: StorageStatsResponse | undefined;
  isLoading: boolean;
  isRefetching: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
  diskUsagePercent: number | null;
  diskTotalBytes: number | null;
  diskUsedBytes: number | null;
  diskFreeBytes: number | null;
}

interface UseCleanupPreviewMutationReturn {
  mutation: ReturnType<typeof useMutation>;
  previewData: CleanupResponse | undefined;
  isPending: boolean;
  error: Error | null;
  preview: () => Promise<CleanupResponse>;
  reset: () => void;
}
```

### `useAIMetrics.ts`

Hook for fetching AI performance metrics from multiple API endpoints and combining them into unified state.

**Features:**

- Fetches from `/api/metrics`, `/api/system/telemetry`, `/api/system/health`, `/api/system/pipeline-latency`
- Combines RT-DETR and Nemotron model statuses
- Tracks detection/analysis latency metrics with percentiles
- Monitors queue depths, errors, and throughput
- Configurable polling interval (default: 5000ms)
- Manual refresh capability

**Return Interface:**

```typescript
interface UseAIMetricsResult {
  data: AIPerformanceState;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}
```

### `useDetectionEnrichment.ts`

Hook for fetching enrichment data (vision model results) for a specific detection.

**Features:**

- Fetches structured enrichment results from `/api/detections/{id}/enrichment`
- Contains results from 18+ vision models run during detection processing
- Automatic fetching when detectionId changes
- Manual refetch capability

**Return Interface:**

```typescript
interface UseDetectionEnrichmentReturn {
  data: EnrichmentResponse | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}
```

### `useModelZooStatus.ts`

Hook for fetching and polling Model Zoo status including VRAM statistics. This is the legacy polling hook; prefer `useModelZooStatusQuery` for new development.

**Features:**

- Polls `/api/system/models` at configurable intervals (default: 10000ms)
- Provides list of all AI models in the Model Zoo
- Calculates VRAM usage statistics (budget, used, available, percentage)
- Manual refresh capability
- Tracks loading state per request

**Options Interface:**

```typescript
interface UseModelZooStatusOptions {
  pollingInterval?: number;  // default: 10000 (10 seconds), 0 to disable
}
```

**Types:**

```typescript
interface VRAMStats {
  budget_mb: number;       // Total VRAM budget
  used_mb: number;         // Currently used VRAM
  available_mb: number;    // Available VRAM
  usage_percent: number;   // Usage percentage (0-100)
}

interface ModelStatusResponse {
  name: string;
  loaded: boolean;
  memory_mb: number;
  load_time_seconds: number | null;
  last_inference_time: string | null;
}
```

**Return Interface:**

```typescript
interface UseModelZooStatusReturn {
  models: ModelStatusResponse[];
  vramStats: VRAMStats | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}
```

**Usage Example:**

```typescript
function ModelZooPanel() {
  const { models, vramStats, isLoading, error, refresh } = useModelZooStatus({
    pollingInterval: 10000,
  });

  if (isLoading && !models.length) return <Spinner />;
  if (error) return <ErrorMessage message={error} />;

  return (
    <div>
      {vramStats && (
        <ProgressBar
          value={vramStats.usage_percent}
          label={`VRAM: ${vramStats.used_mb}/${vramStats.budget_mb} MB`}
        />
      )}
      <h3>Loaded Models</h3>
      {models.filter(m => m.loaded).map(model => (
        <div key={model.name}>
          {model.name}: {model.memory_mb} MB
        </div>
      ))}
      <Button onClick={refresh}>Refresh</Button>
    </div>
  );
}
```

### `useSavedSearches.ts`

Hook for managing saved searches with localStorage persistence. Allows users to save, recall, and manage frequently used search configurations.

**Features:**

- Persists searches to localStorage (key: `hsi_saved_searches`)
- Limits to 10 most recent searches (configurable via `MAX_SAVED_SEARCHES`)
- CRUD operations: save, delete, load, clearAll
- Cross-tab sync via storage event listener
- Handles localStorage errors gracefully (quota exceeded, unavailable)
- Type guards for runtime validation of stored data

**Types:**

```typescript
interface SavedSearch {
  id: string;              // Unique identifier (generated)
  name: string;            // User-defined name
  query: string;           // The search query string
  filters: SearchFilters;  // Applied filters
  createdAt: string;       // ISO timestamp
}

interface LoadedSearch {
  query: string;
  filters: SearchFilters;
}
```

**Return Interface:**

```typescript
interface UseSavedSearchesReturn {
  savedSearches: SavedSearch[];  // Newest first
  saveSearch: (name: string, query: string, filters: SearchFilters) => void;
  deleteSearch: (id: string) => void;
  loadSearch: (id: string) => LoadedSearch | null;
  clearAll: () => void;
}
```

**Usage Example:**

```typescript
function SearchPanel() {
  const { savedSearches, saveSearch, deleteSearch, loadSearch, clearAll } = useSavedSearches();
  const [query, setQuery] = useState('');
  const [filters, setFilters] = useState<SearchFilters>({});

  const handleSave = () => {
    const name = prompt('Enter a name for this search:');
    if (name) {
      saveSearch(name, query, filters);
    }
  };

  const handleLoad = (id: string) => {
    const search = loadSearch(id);
    if (search) {
      setQuery(search.query);
      setFilters(search.filters);
    }
  };

  return (
    <div>
      <SearchBar query={query} filters={filters} onChange={setQuery} onFiltersChange={setFilters} />
      <Button onClick={handleSave}>Save Search</Button>

      <h3>Saved Searches</h3>
      {savedSearches.map(search => (
        <div key={search.id}>
          <span onClick={() => handleLoad(search.id)}>{search.name}</span>
          <Button onClick={() => deleteSearch(search.id)}>Delete</Button>
        </div>
      ))}
      {savedSearches.length > 0 && (
        <Button onClick={clearAll}>Clear All</Button>
      )}
    </div>
  );
}
```

### `useLocalStorage.ts`

Generic hook for persisting state in localStorage with SSR safety.

**Features:**

- useState-like API with automatic persistence
- SSR-safe (checks for `window` availability)
- JSON serialization/deserialization
- Handles localStorage errors gracefully

**Usage Example:**

```typescript
const [theme, setTheme] = useLocalStorage<string>('theme', 'dark');
setTheme('light'); // Automatically persists to localStorage
```

### `useThrottledValue.ts`

Hook that throttles value updates to reduce re-renders.

**Features:**

- Batches updates within configurable interval (default: 500ms)
- Leading edge emission (first value immediate)
- Designed for WebSocket data that arrives frequently
- Reduces unnecessary re-renders

**Usage Example:**

```typescript
const { events } = useEventStream();
const throttledEvents = useThrottledValue(events, { interval: 500 });
// throttledEvents updates at most every 500ms
```

### `useToast.ts`

Hook for managing toast notifications using sonner.

**Features:**

- Variants: `success`, `error`, `warning`, `info`, `loading`
- Support for action and cancel buttons
- Promise-based toasts for async operations
- Configurable duration (error toasts default to 8s)
- Memoized return object for stable references

**Return Interface:**

```typescript
interface UseToastReturn {
  success: (message: string, options?: ToastOptions) => string | number;
  error: (message: string, options?: ToastOptions) => string | number;
  warning: (message: string, options?: ToastOptions) => string | number;
  info: (message: string, options?: ToastOptions) => string | number;
  loading: (message: string, options?: ToastOptions) => string | number;
  dismiss: (toastId?: string | number) => void;
  promise: <T>(promise: Promise<T>, messages: PromiseMessages<T>) => Promise<T>;
}
```

### `useKeyboardShortcuts.ts`

Hook providing global keyboard navigation shortcuts.

**Features:**

- Single-key shortcuts: `?` for help
- Chord shortcuts: `g + d` for dashboard, `g + t` for timeline, etc.
- Modifier shortcuts: `Cmd/Ctrl + K` for command palette
- Automatically ignores shortcuts when typing in input fields
- Chord timeout of 1 second

**Chord Routes:**

| Chord | Route |
|-------|-------|
| g + d | / (Dashboard) |
| g + t | /timeline |
| g + a | /analytics |
| g + l | /alerts |
| g + e | /entities |
| g + o | /logs |
| g + s | /system |
| g + , | /settings |

**Return Interface:**

```typescript
interface UseKeyboardShortcutsReturn {
  isPendingChord: boolean;
}
```

### `useListNavigation.ts`

Hook providing j/k style list navigation.

**Features:**

- `j`/`ArrowDown`: Move down
- `k`/`ArrowUp`: Move up
- `Home`: Jump to first item
- `End`: Jump to last item
- `Enter`: Select current item
- Optional wrap-around at boundaries
- Automatically ignores shortcuts in input fields

**Return Interface:**

```typescript
interface UseListNavigationReturn {
  selectedIndex: number;
  setSelectedIndex: (index: number) => void;
  resetSelection: () => void;
}
```

### `useIsMobile.ts`

Hook for detecting mobile viewport using MediaQueryList API.

**Features:**

- Configurable breakpoint (default: 768px)
- Reactive updates on viewport resize
- SSR-safe (defaults to false)

**Usage Example:**

```typescript
const isMobile = useIsMobile(); // default 768px breakpoint
const isTablet = useIsMobile(1024); // custom breakpoint
```

### `useSwipeGesture.ts`

Hook for detecting touch swipe gestures.

**Features:**

- Detects left, right, up, down swipes
- Configurable threshold (default: 50px)
- Configurable timeout (default: 300ms)
- Returns ref callback to attach to element
- Passive touch event listeners

**Usage Example:**

```typescript
const swipeRef = useSwipeGesture({
  onSwipe: (direction) => console.log(`Swiped ${direction}`),
  threshold: 50,
  timeout: 300,
});

return <div ref={swipeRef}>Swipe me</div>;
```

### `useNetworkStatus.ts`

Hook for tracking browser network connectivity (PWA support).

**Features:**

- Tracks online/offline state
- Callbacks for online/offline transitions
- `wasOffline` flag to show reconnection notifications
- Last online timestamp tracking

**Return Interface:**

```typescript
interface UseNetworkStatusReturn {
  isOnline: boolean;
  isOffline: boolean;
  lastOnlineAt: Date | null;
  wasOffline: boolean;
  clearWasOffline: () => void;
}
```

### `usePushNotifications.ts`

Hook for managing browser push notifications (PWA support).

**Features:**

- Request notification permission
- Show custom notifications
- Convenience method for security alerts
- Service worker notification fallback
- Permission state tracking

**Return Interface:**

```typescript
interface UsePushNotificationsReturn {
  permission: NotificationPermission;
  isSupported: boolean;
  hasPermission: boolean;
  hasInteracted: boolean;
  isSubscribed: boolean;
  requestPermission: () => Promise<NotificationPermission>;
  showNotification: (title: string, options?: NotificationOptions) => Promise<void>;
  showSecurityAlert: (options: SecurityAlertOptions) => Promise<void>;
}
```

### `useSystemPageSections.ts`

Hook for managing System Monitoring page collapsible section states.

**Features:**

- Persists section states to localStorage
- Default expanded/collapsed states per section
- Toggle, expand all, collapse all, reset to defaults
- Handles 11 section types

**Return Interface:**

```typescript
interface UseSystemPageSectionsReturn {
  sectionStates: Record<SystemSectionId, boolean>;
  toggleSection: (sectionId: SystemSectionId) => void;
  setSection: (sectionId: SystemSectionId, isOpen: boolean) => void;
  expandAll: () => void;
  collapseAll: () => void;
  resetToDefaults: () => void;
}
```

### `useAlertWebSocket.ts`

WebSocket hook for real-time alert state changes. Subscribes to alert events and provides callbacks for handling alert lifecycle.

**Events Handled:**

| Event | Description |
|-------|-------------|
| `alert_created` | New alert triggered from rule evaluation |
| `alert_updated` | Alert modified (metadata, channels updated) |
| `alert_acknowledged` | Alert marked as seen by user |
| `alert_resolved` | Alert resolved/dismissed |

**Options Interface:**

```typescript
interface UseAlertWebSocketOptions {
  url?: string;                    // WebSocket URL (default: env or ws://localhost:8000/ws/events)
  autoInvalidateCache?: boolean;   // Auto-invalidate React Query cache (default: true)
  onAlertCreated?: AlertEventHandler;
  onAlertUpdated?: AlertEventHandler;
  onAlertAcknowledged?: AlertEventHandler;
  onAlertResolved?: AlertEventHandler;
  onAnyAlertEvent?: (eventType: string, alert: WebSocketAlertData) => void;
  enabled?: boolean;               // Enable connection (default: true)
}
```

**Return Interface:**

```typescript
interface UseAlertWebSocketReturn {
  isConnected: boolean;
  lastAlert: WebSocketAlertData | null;
  lastEventType: string | null;
  connect: () => void;
  disconnect: () => void;
  hasExhaustedRetries: boolean;
  reconnectCount: number;
}
```

**Usage Example:**

```typescript
function AlertNotifications() {
  const { isConnected, lastAlert } = useAlertWebSocket({
    onAlertCreated: (alert) => {
      showNotification(`New ${alert.severity} alert: ${alert.title}`);
    },
    onAlertAcknowledged: (alert) => {
      console.log('Alert acknowledged:', alert.id);
    },
  });

  return <Badge status={isConnected ? 'connected' : 'disconnected'} />;
}
```

### `useEventLifecycleWebSocket.ts`

WebSocket hook for real-time security event lifecycle changes (create/update/delete).

**Events Handled:**

| Event | Description |
|-------|-------------|
| `event.created` | New security event detected and stored |
| `event.updated` | Security event modified (risk score, status, etc.) |
| `event.deleted` | Security event removed |

**Options Interface:**

```typescript
interface UseEventLifecycleWebSocketOptions {
  url?: string;
  autoInvalidateCache?: boolean;  // Auto-invalidate events query cache (default: true)
  onEventCreated?: (event: EventCreatedPayload) => void;
  onEventUpdated?: (event: EventUpdatedPayload) => void;
  onEventDeleted?: (event: EventDeletedPayload) => void;
  onAnyEventLifecycle?: (eventType: string, data: Payload) => void;
  enabled?: boolean;
}
```

**Return Interface:**

```typescript
interface UseEventLifecycleWebSocketReturn {
  isConnected: boolean;
  lastEventPayload: EventCreatedPayload | EventUpdatedPayload | EventDeletedPayload | null;
  lastEventType: 'event.created' | 'event.updated' | 'event.deleted' | null;
  connect: () => void;
  disconnect: () => void;
  hasExhaustedRetries: boolean;
  reconnectCount: number;
}
```

**Usage Example:**

```typescript
function EventMonitor() {
  const { isConnected, lastEventType } = useEventLifecycleWebSocket({
    onEventCreated: (event) => {
      showNotification(`New ${event.risk_level} risk event detected`);
    },
    onEventUpdated: (event) => {
      console.log('Event updated:', event.id, event.updated_fields);
    },
    onEventDeleted: (event) => {
      console.log('Event deleted:', event.id, event.reason);
    },
  });

  return <div>Connected: {isConnected ? 'Yes' : 'No'}</div>;
}
```

### `useCameraStatusWebSocket.ts`

Hook for subscribing to camera status WebSocket events. Provides real-time updates when camera status changes.

**Events Handled:**

| Event | Description |
|-------|-------------|
| `camera.online` | Camera came online |
| `camera.offline` | Camera went offline |
| `camera.error` | Camera encountered an error |
| `camera.updated` | Camera configuration updated |

**Options Interface:**

```typescript
interface UseCameraStatusWebSocketOptions {
  url?: string;
  connectionConfig?: Partial<ConnectionConfig>;
  onCameraOnline?: (event: CameraStatusEventPayload) => void;
  onCameraOffline?: (event: CameraStatusEventPayload) => void;
  onCameraError?: (event: CameraStatusEventPayload) => void;
  onCameraUpdated?: (event: CameraStatusEventPayload) => void;
  onCameraStatusChange?: (event: CameraStatusEventPayload) => void;
  enabled?: boolean;  // Default: true
}
```

**Return Interface:**

```typescript
interface UseCameraStatusWebSocketReturn {
  cameraStatuses: Record<string, CameraStatusState>;
  isConnected: boolean;
  reconnectCount: number;
  lastEvent: CameraStatusEventPayload | null;
  reconnect: () => void;
}
```

**Usage Example:**

```typescript
function CameraGrid() {
  const { cameraStatuses, isConnected } = useCameraStatusWebSocket({
    onCameraOnline: (event) => console.log('Camera online:', event.camera_name),
    onCameraOffline: (event) => toast.warning(`Camera offline: ${event.camera_name}`),
  });

  return (
    <div>
      {Object.entries(cameraStatuses).map(([id, status]) => (
        <CameraCard
          key={id}
          name={status.camera_name}
          status={status.status}
          lastUpdated={status.lastUpdated}
        />
      ))}
    </div>
  );
}
```

### Non-Exported Hooks

The following hooks are NOT exported from `index.ts` and are used internally or directly imported:

**`useServiceStatus.ts`** - Per-service status tracking. The backend's `ServiceHealthMonitor` (health_monitor.py) monitors services and broadcasts `service_status` messages. Use `useSystemStatus` for overall system health or `usePerformanceMetrics` for detailed metrics.

**`useStorageStats.ts`** - Storage disk usage polling with cleanup preview. Import directly when needed. Consider using `useStorageStatsQuery` for TanStack Query benefits.

**`useSidebarContext.ts`** - Context hook for mobile sidebar state. Used by Layout component for sidebar toggle state management.

**`useSystemPageSections.ts`** - System page collapsible section state management. Import directly in System page.

**`webSocketManager.ts`** - Singleton WebSocket connection manager with deduplication. Used internally by WebSocket hooks for connection sharing.

### `webSocketManager.ts`

Singleton class that manages WebSocket connections with deduplication and reference counting.

**Features:**

- Connection deduplication: multiple subscribers to same URL share one connection
- Reference counting: connection closes only when all subscribers disconnect
- Automatic reconnection with exponential backoff and jitter
- Server heartbeat (ping/pong) handling
- Connection timeout handling
- SSR-safe: checks for `window.WebSocket` availability

**Key Functions:**

```typescript
// Subscribe to a WebSocket URL
subscribe(url: string, subscriber: Subscriber, config: ConnectionConfig): () => void

// Send data through WebSocket
send(url: string, data: unknown): boolean

// Get connection state
getConnectionState(url: string): { isConnected, reconnectCount, hasExhaustedRetries, lastHeartbeat }

// Manual reconnect
reconnect(url: string): void

// Get subscriber count
getSubscriberCount(url: string): number

// Clear all connections
clearAll(): void
```

## Custom Hooks Patterns

### URL Construction Pattern

WebSocket hooks use `buildWebSocketUrl()` from `../services/api` for URL construction:

```typescript
import { buildWebSocketUrl } from '../services/api';

// Respects VITE_WS_BASE_URL env var
// Falls back to window.location.host
// Appends api_key query param if VITE_API_KEY is configured
const wsUrl = buildWebSocketUrl('/ws/events');
```

### Message Envelope Pattern

Both `useEventStream` and `useSystemStatus` expect messages in envelope format:

```typescript
// Backend sends messages wrapped in an envelope
{
  type: 'event' | 'system_status',  // Message type discriminator
  data: { ... },                     // Actual payload
  timestamp?: string                 // Optional timestamp
}
```

Type guards validate the envelope structure before processing.

### Reconnection Pattern

The base `useWebSocket` hook handles reconnection with counter tracking:

- Reconnect counter resets on successful connection
- Reconnection stops when `disconnect()` is called manually
- Cleanup clears pending reconnection timeouts

### TanStack Query vs Polling Pattern

This codebase has both patterns for historical reasons:

| Pattern | Hooks | Use When |
|---------|-------|----------|
| TanStack Query | `use*Query`, `use*Mutation` | New code, need caching/deduplication |
| usePolling | `useHealthStatus`, `useGpuHistory`, `useModelZooStatus` | Legacy, being migrated |

Prefer TanStack Query hooks for new development.

## Dependencies

- React hooks: `useState`, `useEffect`, `useRef`, `useCallback`, `useMemo`
- TanStack Query: `useQuery`, `useMutation`, `useQueryClient`
- API service: `buildWebSocketUrl`, `fetchGPUStats`, `fetchHealth`, etc.
- Sonner: Toast notifications
- Testing: `vitest`, `@testing-library/react`, MSW

## Usage Examples

### Event Stream

```typescript
const { events, isConnected, latestEvent, clearEvents } = useEventStream();

if (latestEvent) {
  console.log(`New event: ${latestEvent.summary} (Risk: ${latestEvent.risk_level})`);
}
```

### System Status

```typescript
const { status, isConnected } = useSystemStatus();

if (status) {
  console.log(`Health: ${status.health}, GPU: ${status.gpu_utilization}%`);
}
```

### GPU Stats with TanStack Query

```typescript
const { utilization, temperature, isLoading, error } = useGpuStatsQuery({
  refetchInterval: 5000,
});

if (isLoading) return <Spinner />;
if (error) return <Error message={error.message} />;

return (
  <div>
    <span>Utilization: {utilization ?? 'N/A'}%</span>
    <span>Temperature: {temperature ?? 'N/A'}C</span>
  </div>
);
```

### AI Service Degradation

```typescript
const { degradationMode, isDegraded, getServiceState } = useAIServiceStatus();

if (isDegraded) {
  const rtdetr = getServiceState('rtdetr');
  console.log(`System degraded. RT-DETR status: ${rtdetr?.status}`);
}
```

### Offline Support

```typescript
const { isOnline, wasOffline, clearWasOffline } = useNetworkStatus();
const { cachedEvents, cacheEvent } = useCachedEvents();

if (!isOnline) {
  // Show cached events while offline
  return <CachedEventsList events={cachedEvents} />;
}

if (wasOffline) {
  return <ReconnectedBanner onDismiss={clearWasOffline} />;
}
```

### Keyboard Navigation

```typescript
const { isPendingChord } = useKeyboardShortcuts({
  onOpenHelp: () => setHelpModalOpen(true),
  onOpenCommandPalette: () => setCommandPaletteOpen(true),
});

// Show chord indicator when g is pressed
{isPendingChord && <ChordIndicator />}
```

## Notes

- All WebSocket URLs are constructed via `buildWebSocketUrl()` which respects `VITE_WS_BASE_URL` and `VITE_API_KEY`
- SSR-safe: checks for `window.WebSocket` availability before connecting
- Events are stored in reverse chronological order (newest first)
- Connection state is tracked per hook instance
- The `useWebSocket` hook auto-connects on mount and disconnects on unmount
- Message parsing falls back to raw data if JSON parsing fails
- Non-event messages (e.g., `service_status`, `ping`) are silently ignored by `useEventStream`
- TanStack Query hooks should be preferred over legacy polling hooks for new development

## Entry Points

For AI agents exploring this codebase:

1. **Start with `index.ts`** - Central export point showing all available hooks
2. **WebSocket foundation**: `useWebSocket.ts` is the base layer for real-time data
3. **High-level hooks**: `useEventStream.ts` and `useSystemStatus.ts` build on WebSocket
4. **TanStack Query hooks**: `use*Query.ts` files for modern server state management
5. **REST hooks**: `useHealthStatus.ts` and `useGpuHistory.ts` use polling (legacy)
6. **PWA hooks**: `useNetworkStatus.ts`, `useCachedEvents.ts`, `usePushNotifications.ts`
7. **UI hooks**: `useKeyboardShortcuts.ts`, `useListNavigation.ts`, `useToast.ts`
8. **Tests**: Each hook has corresponding `.test.ts` file with usage patterns

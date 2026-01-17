export { useWebSocket } from './useWebSocket';
export type { WebSocketOptions, UseWebSocketReturn } from './useWebSocket';

export { useWebSocketStatus } from './useWebSocketStatus';
export type {
  ConnectionState,
  ChannelStatus,
  WebSocketStatusOptions,
  UseWebSocketStatusReturn,
} from './useWebSocketStatus';

export { useConnectionStatus } from './useConnectionStatus';
export type { ConnectionStatusSummary, UseConnectionStatusReturn } from './useConnectionStatus';

export { useEventStream } from './useEventStream';
export type { SecurityEvent, UseEventStreamReturn } from './useEventStream';

export { useSystemStatus } from './useSystemStatus';
export type { SystemStatus, UseSystemStatusReturn } from './useSystemStatus';

export { useGpuHistory } from './useGpuHistory';
export type {
  GpuMetricDataPoint,
  UseGpuHistoryOptions,
  UseGpuHistoryReturn,
} from './useGpuHistory';

export { useHealthStatusQuery } from './useHealthStatusQuery';
export type {
  UseHealthStatusQueryOptions,
  UseHealthStatusQueryReturn,
} from './useHealthStatusQuery';

export { useCamerasQuery, useCameraQuery, useCameraMutation } from './useCamerasQuery';
export type {
  UseCamerasQueryOptions,
  UseCamerasQueryReturn,
  UseCameraQueryOptions,
  UseCameraQueryReturn,
  UseCameraMutationReturn,
} from './useCamerasQuery';

export { useGpuStatsQuery, useGpuHistoryQuery } from './useGpuStatsQuery';
export type {
  UseGpuStatsQueryOptions,
  UseGpuStatsQueryReturn,
  UseGpuHistoryQueryOptions,
  UseGpuHistoryQueryReturn,
} from './useGpuStatsQuery';

export { useModelZooStatusQuery } from './useModelZooStatusQuery';
export type {
  VRAMStats as VRAMStatsQuery,
  UseModelZooStatusQueryOptions,
  UseModelZooStatusQueryReturn,
} from './useModelZooStatusQuery';

export {
  useStorageStatsQuery,
  useCleanupPreviewMutation,
  useCleanupMutation,
} from './useStorageStatsQuery';
export type {
  UseStorageStatsQueryOptions,
  UseStorageStatsQueryReturn,
  UseCleanupPreviewMutationReturn,
  UseCleanupMutationReturn,
} from './useStorageStatsQuery';

export { usePerformanceMetrics } from './usePerformanceMetrics';
export type {
  TimeRange,
  GpuMetrics,
  AiModelMetrics,
  NemotronMetrics,
  InferenceMetrics,
  DatabaseMetrics,
  RedisMetrics,
  HostMetrics,
  ContainerMetrics,
  PerformanceAlert,
  PerformanceUpdate,
  PerformanceHistory,
  UsePerformanceMetricsReturn,
} from './usePerformanceMetrics';

export { useAIMetrics } from './useAIMetrics';
export type {
  AIModelStatus,
  AIPerformanceState,
  UseAIMetricsResult,
  UseAIMetricsOptions,
} from './useAIMetrics';

export { useDetectionEnrichment } from './useDetectionEnrichment';
export type {
  UseDetectionEnrichmentOptions,
  UseDetectionEnrichmentReturn,
} from './useDetectionEnrichment';

export { useSavedSearches } from './useSavedSearches';
export type { SavedSearch, LoadedSearch, UseSavedSearchesReturn } from './useSavedSearches';

export { useLocalStorage } from './useLocalStorage';

export { usePolling } from './usePolling';
export type { UsePollingOptions, UsePollingReturn } from './usePolling';

export { useThrottledValue } from './useThrottledValue';
export type { UseThrottledValueOptions } from './useThrottledValue';

export { useToast } from './useToast';
export type { ToastAction, ToastOptions, PromiseMessages, UseToastReturn } from './useToast';

export { useKeyboardShortcuts } from './useKeyboardShortcuts';
export type {
  UseKeyboardShortcutsOptions,
  UseKeyboardShortcutsReturn,
} from './useKeyboardShortcuts';

export { useListNavigation } from './useListNavigation';
export type { UseListNavigationOptions, UseListNavigationReturn } from './useListNavigation';

// PWA Hooks
export { useNetworkStatus } from './useNetworkStatus';
export type { UseNetworkStatusOptions, UseNetworkStatusReturn } from './useNetworkStatus';

export { useCachedEvents } from './useCachedEvents';
export type { CachedEvent, UseCachedEventsReturn } from './useCachedEvents';

export { usePushNotifications } from './usePushNotifications';
export type { SecurityAlertOptions, UsePushNotificationsReturn } from './usePushNotifications';

// Mobile Hooks
export { useIsMobile } from './useIsMobile';

export { useSwipeGesture } from './useSwipeGesture';
export type { SwipeDirection, SwipeGestureOptions } from './useSwipeGesture';

// Infinite scroll hook
export { useInfiniteScroll } from './useInfiniteScroll';
export type { UseInfiniteScrollOptions, UseInfiniteScrollReturn } from './useInfiniteScroll';

// Cursor-based pagination hooks
export {
  useCursorPaginatedQuery,
  default as useCursorPaginatedQueryDefault,
} from './useCursorPaginatedQuery';
export type {
  CursorPaginatedResponse,
  UseCursorPaginatedQueryOptions,
  UseCursorPaginatedQueryReturn,
  ExtractItemType,
} from './useCursorPaginatedQuery';

// Pagination state with URL persistence
export { usePaginationState, default as usePaginationStateDefault } from './usePaginationState';
export type {
  PaginationType,
  UsePaginationStateOptions,
  BasePaginationState,
  CursorPaginationState,
  OffsetPaginationState,
  PaginationState,
  UseCursorPaginationStateReturn,
  UseOffsetPaginationStateReturn,
  UsePaginationStateReturn,
} from './usePaginationState';

export { useEventsInfiniteQuery, eventsQueryKeys } from './useEventsQuery';
export type {
  EventFilters,
  UseEventsInfiniteQueryOptions,
  UseEventsInfiniteQueryReturn,
} from './useEventsQuery';

export { useRecentEventsQuery, recentEventsQueryKeys } from './useRecentEventsQuery';
export type {
  UseRecentEventsQueryOptions,
  UseRecentEventsQueryReturn,
} from './useRecentEventsQuery';

export { useDetectionsInfiniteQuery, detectionsQueryKeys } from './useDetectionsQuery';
export type {
  UseDetectionsInfiniteQueryOptions,
  UseDetectionsInfiniteQueryReturn,
} from './useDetectionsQuery';

export { useAlertsInfiniteQuery, alertsQueryKeys } from './useAlertsQuery';
export type {
  AlertRiskFilter,
  UseAlertsInfiniteQueryOptions,
  UseAlertsInfiniteQueryReturn,
} from './useAlertsQuery';

export { useAlertWebSocket } from './useAlertWebSocket';
export type {
  AlertEventHandler,
  UseAlertWebSocketOptions,
  UseAlertWebSocketReturn,
} from './useAlertWebSocket';

export { useEventLifecycleWebSocket } from './useEventLifecycleWebSocket';
export type {
  EventCreatedHandler,
  EventUpdatedHandler,
  EventDeletedHandler,
  UseEventLifecycleWebSocketOptions,
  UseEventLifecycleWebSocketReturn,
} from './useEventLifecycleWebSocket';

export { useWebSocketEvent, useWebSocketEvents } from './useWebSocketEvent';
export type {
  UseWebSocketEventOptions,
  UseWebSocketEventReturn,
  UseWebSocketEventsOptions,
  WebSocketEventHandlers,
} from './useWebSocketEvent';

export { useEntitiesInfiniteQuery, entitiesInfiniteQueryKeys } from './useEntitiesInfiniteQuery';
export type {
  EntityTimeRangeFilter,
  UseEntitiesInfiniteQueryOptions,
  UseEntitiesInfiniteQueryReturn,
} from './useEntitiesInfiniteQuery';

export { useEntitiesV2Query, useEntityHistory, useEntityStats } from './useEntityHistory';
export type {
  UseEntitiesV2QueryOptions,
  UseEntitiesV2QueryReturn,
  UseEntityHistoryOptions,
  UseEntityHistoryReturn,
  UseEntityStatsOptions,
  UseEntityStatsReturn,
} from './useEntityHistory';

export { useServiceStatus } from './useServiceStatus';
export type {
  ServiceName,
  ServiceStatusType,
  ServiceStatus,
  ServiceStatusChangeCallback,
  UseServiceStatusOptions,
  UseServiceStatusResult,
} from './useServiceStatus';

export { useCircuitBreakerStatus } from './useCircuitBreakerStatus';
export type {
  CircuitBreakerStateType,
  CircuitBreakerState,
  CircuitBreakerSummary,
  UseCircuitBreakerStatusReturn,
} from './useCircuitBreakerStatus';

export { useSceneChangeAlerts, formatChangeType, getChangeSeverity } from './useSceneChangeAlerts';
export type {
  SceneChangeAlert,
  UseSceneChangeAlertsOptions,
  UseSceneChangeAlertsReturn,
} from './useSceneChangeAlerts';

export { useCameraStatusWebSocket } from './useCameraStatusWebSocket';
export type {
  CameraStatusState,
  UseCameraStatusWebSocketOptions,
  UseCameraStatusWebSocketReturn,
} from './useCameraStatusWebSocket';

export { useRateLimitCountdown, formatCountdown } from './useRateLimitCountdown';
export type { UseRateLimitCountdownReturn } from './useRateLimitCountdown';

export { useRateLimit } from './useRateLimit';
export type { UseRateLimitReturn } from './useRateLimit';

// Ambient status awareness hooks
export { useAudioNotifications } from './useAudioNotifications';
export type {
  SoundType,
  UseAudioNotificationsOptions,
  UseAudioNotificationsReturn,
} from './useAudioNotifications';

export { useDesktopNotifications } from './useDesktopNotifications';
export type {
  DesktopNotificationOptions,
  SecurityAlertNotificationOptions,
  UseDesktopNotificationsOptions,
  UseDesktopNotificationsReturn,
} from './useDesktopNotifications';

export { useSettings } from './useSettings';
export type {
  AmbientSettings,
  AudioSettings,
  DesktopNotificationSettings,
  FaviconSettings,
  AmbientStatusSettings,
  AppSettings,
  UseSettingsReturn,
} from './useSettings';
export { DEFAULT_SETTINGS } from './useSettings';

// Form validation error mapping hooks
export {
  applyApiValidationErrors,
  useApiMutation,
  isApiValidationException,
  extractFieldPath,
} from './useFormWithApiErrors';
export type {
  ValidationFieldError,
  ApiValidationException,
  FastAPIValidationError,
  UseApiMutationOptions,
  UseApiMutationResult,
} from './useFormWithApiErrors';

// Retry with backoff hooks
export {
  useRetry,
  useRetryStore,
  useActiveRetries,
  useHasActiveRetries,
  parseRetryAfter,
  calculateBackoff,
  formatRetryCountdown,
  generateRetryId,
  DEFAULT_RETRY_CONFIG,
} from './useRetry';
export type {
  RetryConfig,
  RetryState,
  PendingRetry,
  RetryStoreState,
  UseRetryReturn,
} from './useRetry';

// Event snooze hooks (NEM-2360, NEM-2361)
export { useSnoozeEvent } from './useSnoozeEvent';
export type { UseSnoozeEventOptions, UseSnoozeEventReturn } from './useSnoozeEvent';

// Date range state with URL persistence (NEM-2701)
export { useDateRangeState, calculatePresetRange, PRESET_LABELS } from './useDateRangeState';
export type {
  DateRangePreset,
  DateRange,
  UseDateRangeStateOptions,
  DateRangeApiParams,
  UseDateRangeStateReturn,
} from './useDateRangeState';

// Job mutation hooks (NEM-2712)
export { useJobMutations, default as useJobMutationsDefault } from './useJobMutations';
export type { UseJobMutationsOptions, UseJobMutationsReturn } from './useJobMutations';

// Job logs query hooks (NEM-2710)
export { useJobLogsQuery, jobLogsQueryKeys } from './useJobLogsQuery';
export type {
  UseJobLogsQueryOptions,
  UseJobLogsQueryReturn,
} from './useJobLogsQuery';

// Job logs WebSocket hooks (NEM-2711)
export { useJobLogsWebSocket, default as useJobLogsWebSocketDefault } from './useJobLogsWebSocket';
export type {
  UseJobLogsWebSocketOptions,
  UseJobLogsWebSocketReturn,
} from './useJobLogsWebSocket';

// Job history query hooks (NEM-2713)
export { useJobHistoryQuery, jobHistoryQueryKeys } from './useJobHistoryQuery';
export type {
  UseJobHistoryQueryOptions,
  UseJobHistoryQueryReturn,
} from './useJobHistoryQuery';

// Jobs search query hooks (NEM-2709)
export { useJobsSearchQuery, jobsSearchQueryKeys } from './useJobsSearchQuery';
export type {
  UseJobsSearchQueryOptions,
  UseJobsSearchQueryReturn,
} from './useJobsSearchQuery';

// Prompt management hooks (NEM-2697)
export {
  usePromptConfig,
  usePromptHistory,
  useUpdatePromptConfig,
  useRestorePromptVersion,
} from './usePromptQueries';
export type {
  UsePromptConfigOptions,
  UsePromptConfigReturn,
  UsePromptHistoryOptions,
  UsePromptHistoryReturn,
  UpdatePromptConfigVariables,
  UseUpdatePromptConfigReturn,
  UseRestorePromptVersionReturn,
} from './usePromptQueries';

// System config hook (NEM-2719)
export { useSystemConfigQuery } from './useSystemConfigQuery';
export type {
  UseSystemConfigQueryOptions,
  UseSystemConfigQueryReturn,
} from './useSystemConfigQuery';

// Developer tools section state hook (NEM-2719)
export { useDevToolsSections } from './useDevToolsSections';
export type { DevToolsSectionId } from './useDevToolsSections';

// Debug configuration and log level hooks (NEM-2722)
export { useDebugConfigQuery } from './useDebugConfigQuery';
export type {
  ConfigEntry,
  UseDebugConfigQueryOptions,
  UseDebugConfigQueryReturn,
} from './useDebugConfigQuery';

export { useLogLevelQuery } from './useLogLevelQuery';
export type { UseLogLevelQueryOptions, UseLogLevelQueryReturn } from './useLogLevelQuery';

export { useSetLogLevelMutation } from './useSetLogLevelMutation';
export type { LogLevel, UseSetLogLevelMutationReturn } from './useSetLogLevelMutation';

// Performance profiling hooks (NEM-2720)
export { useProfileQuery } from './useProfileQuery';
export type { UseProfileQueryOptions, UseProfileQueryReturn } from './useProfileQuery';

export {
  useStartProfilingMutation,
  useStopProfilingMutation,
  useDownloadProfileMutation,
} from './useProfilingMutations';
export type {
  UseStartProfilingMutationReturn,
  UseStopProfilingMutationReturn,
  UseDownloadProfileMutationReturn,
} from './useProfilingMutations';

// Admin seed/cleanup mutations (NEM-2723)
export {
  useAdminMutations,
  useSeedCamerasMutation,
  useSeedEventsMutation,
  useSeedPipelineLatencyMutation,
  useClearSeededDataMutation,
} from './useAdminMutations';
export type {
  SeedCamerasRequest,
  SeedCamerasResponse,
  SeedEventsRequest,
  SeedEventsResponse,
  SeedPipelineLatencyRequest,
  SeedPipelineLatencyResponse,
  ClearSeededDataRequest,
  ClearSeededDataResponse,
} from './useAdminMutations';

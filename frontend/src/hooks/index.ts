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

export { useHealthStatusQuery, useHealthSummaryQuery } from './useHealthStatusQuery';
export type {
  UseHealthStatusQueryOptions,
  UseHealthStatusQueryReturn,
  HealthSummary,
  UseHealthSummaryQueryReturn,
} from './useHealthStatusQuery';

export {
  useCamerasQuery,
  useCameraQuery,
  useCameraMutation,
  useOnlineCamerasQuery,
  useCameraCountsQuery,
} from './useCamerasQuery';
export type {
  UseCamerasQueryOptions,
  UseCamerasQueryReturn,
  UseCameraQueryOptions,
  UseCameraQueryReturn,
  UseCameraMutationReturn,
  UseOnlineCamerasQueryReturn,
  UseCameraCountsQueryReturn,
} from './useCamerasQuery';

// Camera soft delete hooks (NEM-3643)
export {
  useDeletedCamerasQuery,
  useDeleteCameraMutation,
  useRestoreCameraMutation,
  useCameraDeleteRestore,
  deletedCamerasQueryKeys,
} from './useCameraDelete';
export type {
  UseDeletedCamerasQueryOptions,
  UseDeletedCamerasQueryReturn,
  UseDeleteCameraMutationReturn,
  UseRestoreCameraMutationReturn,
  UseCameraDeleteRestoreReturn,
} from './useCameraDelete';

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

export { useDetectionEnrichment, detectionEnrichmentKeys } from './useDetectionEnrichment';
export type {
  UseDetectionEnrichmentOptions,
  UseDetectionEnrichmentReturn,
} from './useDetectionEnrichment';

export { useDetectionLabelsQuery, detectionLabelsKeys } from './useDetectionLabelsQuery';
export type {
  UseDetectionLabelsQueryOptions,
  UseDetectionLabelsQueryReturn,
} from './useDetectionLabelsQuery';

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
export type {
  SecurityAlertOptions,
  UsePushNotificationsOptions,
  UsePushNotificationsReturn,
} from './usePushNotifications';

// Mobile Hooks
export { useIsMobile } from './useIsMobile';

// Chart dimension hooks (NEM-2991)
export { useChartDimensions, default as useChartDimensionsDefault } from './useChartDimensions';
export type { ChartDimensions, UseChartDimensionsOptions } from './useChartDimensions';

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

export { useEventDetectionsQuery, eventDetectionsQueryKeys } from './useEventDetectionsQuery';
export type {
  UseEventDetectionsQueryOptions,
  UseEventDetectionsQueryReturn,
} from './useEventDetectionsQuery';

// Event enrichments batch query hook (NEM-3596)
export { useEventEnrichmentsQuery, eventEnrichmentsQueryKeys } from './useEventEnrichmentsQuery';
export type {
  UseEventEnrichmentsQueryOptions,
  UseEventEnrichmentsQueryReturn,
} from './useEventEnrichmentsQuery';

export { useAlertsInfiniteQuery, alertsQueryKeys } from './useAlertsQuery';
export type {
  AlertRiskFilter,
  UseAlertsInfiniteQueryOptions,
  UseAlertsInfiniteQueryReturn,
} from './useAlertsQuery';

// Alert instance management hooks (NEM-3647)
export {
  useAcknowledgeAlert,
  useDismissAlert,
  useAlertMutations,
  default as useAlertMutationsDefault,
} from './useAlerts';
export type {
  AlertMutationContext,
  UseAcknowledgeAlertOptions,
  UseAcknowledgeAlertReturn,
  UseDismissAlertOptions,
  UseDismissAlertReturn,
  UseAlertMutationsReturn,
} from './useAlerts';

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

export { useSceneChangeEvents } from './useSceneChangeEvents';
export type {
  SceneChangeEventData,
  CameraActivityState,
  UseSceneChangeEventsOptions,
  UseSceneChangeEventsReturn,
} from './useSceneChangeEvents';

export { useCameraStatusWebSocket } from './useCameraStatusWebSocket';
export type {
  CameraStatusState,
  UseCameraStatusWebSocketOptions,
  UseCameraStatusWebSocketReturn,
} from './useCameraStatusWebSocket';

export { useRateLimitCountdown, formatCountdown } from './useRateLimitCountdown';
export type { UseRateLimitCountdownReturn } from './useRateLimitCountdown';

// Optimistic locking hook (NEM-3626)
export { useOptimisticLocking } from './useOptimisticLocking';
export type {
  UseOptimisticLockingOptions,
  UseOptimisticLockingReturn,
} from './useOptimisticLocking';

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
export type { UseJobLogsQueryOptions, UseJobLogsQueryReturn } from './useJobLogsQuery';

// Job logs WebSocket hooks (NEM-2711)
export { useJobLogsWebSocket, default as useJobLogsWebSocketDefault } from './useJobLogsWebSocket';
export type { UseJobLogsWebSocketOptions, UseJobLogsWebSocketReturn } from './useJobLogsWebSocket';

// Job history query hooks (NEM-2713)
export { useJobHistoryQuery, jobHistoryQueryKeys } from './useJobHistoryQuery';
export type { UseJobHistoryQueryOptions, UseJobHistoryQueryReturn } from './useJobHistoryQuery';

// Jobs search query hooks (NEM-2709)
export { useJobsSearchQuery, jobsSearchQueryKeys } from './useJobsSearchQuery';
export type { UseJobsSearchQueryOptions, UseJobsSearchQueryReturn } from './useJobsSearchQuery';

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

// Debug panel enhancement queries (NEM-2717)
export {
  usePipelineErrorsQuery,
  useRedisDebugInfoQuery,
  useWebSocketConnectionsQuery,
  debugQueryKeys,
} from './useDebugQueries';
export type {
  DebugQueryOptions,
  UsePipelineErrorsQueryReturn,
  UseRedisDebugInfoQueryReturn,
  UseWebSocketConnectionsQueryReturn,
} from './useDebugQueries';

// Dashboard summaries hooks (NEM-2895)
export { useSummaries, default as useSummariesDefault } from './useSummaries';
export type { UseSummariesOptions } from './useSummaries';

// Summary expansion state persistence (NEM-2925)
export { useSummaryExpansion, default as useSummaryExpansionDefault } from './useSummaryExpansion';
export type { UseSummaryExpansionOptions, UseSummaryExpansionReturn } from './useSummaryExpansion';

// Pull-to-refresh hook (NEM-2970)
export { usePullToRefresh, default as usePullToRefreshDefault } from './usePullToRefresh';
export type { PullToRefreshOptions, PullToRefreshReturn } from './usePullToRefresh';

// Feature error boundary HOC for granular error isolation
export {
  withFeatureErrorBoundary,
  default as withFeatureErrorBoundaryDefault,
} from './useFeatureErrorBoundary';
export type { WithFeatureErrorBoundaryOptions } from './useFeatureErrorBoundary';

// Settings API hooks (NEM-3121)
export {
  useSettingsQuery,
  useUpdateSettings,
  useSettingsApi,
  settingsQueryKeys,
  fetchSettings,
  updateSettings,
  default as useSettingsApiDefault,
} from './useSettingsApi';
export type {
  DetectionSettings as ApiDetectionSettings,
  BatchSettings as ApiBatchSettings,
  SeveritySettings as ApiSeveritySettings,
  FeatureSettings as ApiFeatureSettings,
  RateLimitingSettings as ApiRateLimitingSettings,
  QueueSettings as ApiQueueSettings,
  RetentionSettings as ApiRetentionSettings,
  SettingsResponse as ApiSettingsResponse,
  DetectionSettingsUpdate,
  BatchSettingsUpdate,
  SeveritySettingsUpdate,
  FeatureSettingsUpdate,
  RateLimitingSettingsUpdate,
  QueueSettingsUpdate,
  RetentionSettingsUpdate,
  SettingsUpdate,
  UseSettingsOptions as UseSettingsApiOptions,
  UseSettingsReturn as UseSettingsApiReturn,
  UseUpdateSettingsReturn,
} from './useSettingsApi';

// Property and Area management hooks (NEM-3135)
export {
  usePropertiesQuery,
  useAreasQuery,
  useAreaCamerasQuery,
  usePropertyMutations,
  useAreaMutations,
  propertyQueryKeys,
  areaQueryKeys,
} from './usePropertyQueries';
export type {
  PropertyResponse,
  PropertyCreate,
  PropertyUpdate,
  PropertyListResponse,
  AreaResponse,
  AreaCreate,
  AreaUpdate,
  AreaListResponse,
  AreaCameraResponse,
  AreaCamerasResponse,
  CameraLinkResponse,
  UsePropertiesQueryOptions,
  UsePropertiesQueryReturn,
  UseAreasQueryOptions,
  UseAreasQueryReturn,
  UseAreaCamerasQueryOptions,
  UseAreaCamerasQueryReturn,
  UsePropertyMutationsReturn,
  UseAreaMutationsReturn,
} from './usePropertyQueries';

// Audit logs infinite query hook (NEM-3170, NEM-3180)
export { useAuditLogsInfiniteQuery, auditLogsQueryKeys } from './useAuditLogsInfiniteQuery';
export type {
  AuditLogFilters,
  UseAuditLogsInfiniteQueryOptions,
  UseAuditLogsInfiniteQueryReturn,
} from './useAuditLogsInfiniteQuery';

// Detection stream WebSocket hook (NEM-3169)
export { useDetectionStream, default as useDetectionStreamDefault } from './useDetectionStream';
export type {
  DetectionEventHandler,
  BatchEventHandler,
  UseDetectionStreamOptions,
  UseDetectionStreamReturn,
} from './useDetectionStream';

// Service status WebSocket hook (NEM-3169)
export {
  useServiceStatusWebSocket,
  default as useServiceStatusWebSocketDefault,
} from './useServiceStatusWebSocket';
export type {
  ServiceStatus as ServiceStatusWebSocketType,
  ServiceStatusEntry,
  ServiceStatusMap,
  ServiceStatusChangeHandler,
  UseServiceStatusWebSocketOptions,
  UseServiceStatusWebSocketReturn,
} from './useServiceStatusWebSocket';

// GPU stats WebSocket hook (NEM-3169)
export {
  useGpuStatsWebSocket,
  default as useGpuStatsWebSocketDefault,
} from './useGpuStatsWebSocket';
export type {
  GpuStatsEntry,
  GpuStatsUpdateHandler,
  UseGpuStatsWebSocketOptions,
  UseGpuStatsWebSocketReturn,
} from './useGpuStatsWebSocket';

// System health WebSocket hook (NEM-3169)
export {
  useSystemHealthWebSocket,
  default as useSystemHealthWebSocketDefault,
} from './useSystemHealthWebSocket';
export type {
  HealthStatus as SystemHealthStatus,
  ComponentHealthMap,
  HealthChangeEntry,
  HealthChangeHandler,
  UseSystemHealthWebSocketOptions,
  UseSystemHealthWebSocketReturn,
} from './useSystemHealthWebSocket';

// Memory debug stats hook (NEM-3173)
export {
  useMemoryStatsQuery,
  MEMORY_STATS_QUERY_KEY,
  default as useMemoryStatsQueryDefault,
} from './useMemoryStatsQuery';
export type { UseMemoryStatsQueryOptions, UseMemoryStatsQueryReturn } from './useMemoryStatsQuery';

// Circuit breaker debug hook (NEM-3173)
export {
  useCircuitBreakerDebugQuery,
  CIRCUIT_BREAKER_DEBUG_QUERY_KEY,
  default as useCircuitBreakerDebugQueryDefault,
} from './useCircuitBreakerDebugQuery';
export type {
  UseCircuitBreakerDebugQueryOptions,
  UseCircuitBreakerDebugQueryReturn,
} from './useCircuitBreakerDebugQuery';

// GPU configuration hooks (Multi-GPU Support - NEM-3300)
export {
  useGpus,
  useGpuConfig,
  useGpuStatus,
  useUpdateGpuConfig,
  useApplyGpuConfig,
  useDetectGpus,
  usePreviewStrategy,
  GPU_QUERY_KEYS,
} from './useGpuConfig';
export type {
  GpuDevice,
  GpuListResponse,
  GpuConfig,
  GpuConfigUpdateRequest,
  GpuConfigUpdateResponse,
  GpuApplyResult,
  GpuStatusResponse,
  StrategyPreviewResponse,
  GpuAssignment,
  ServiceStatus as GpuServiceStatus,
  UseGpusOptions,
  UseGpusReturn,
  UseGpuConfigOptions,
  UseGpuConfigReturn,
  UseGpuStatusOptions,
  UseGpuStatusReturn,
  UseUpdateGpuConfigReturn,
  UseApplyGpuConfigReturn,
  UseDetectGpusReturn,
  UsePreviewStrategyReturn,
} from './useGpuConfig';

// TanStack Query v5 Advanced Patterns (NEM-3409, NEM-3410, NEM-3411, NEM-3412)
export {
  // PlaceholderData factories (NEM-3409)
  createPlaceholderCameras,
  createPlaceholderHealthStatus,
  createPlaceholderGpuStats,
  createPlaceholderEventStats,
  // Select functions for data transformation (NEM-3410)
  selectOnlineCameras,
  selectCameraCountsByStatus,
  selectHealthSummary,
  selectRiskDistribution,
  // AbortSignal utilities (NEM-3411)
  withAbortSignal,
  createSignalAwareQueryFn,
  // Parallel queries (NEM-3412)
  useDashboardQueries,
  useQueries,
} from './useQueryPatterns';
export type {
  QueryFnWithSignal,
  DashboardQueryConfig,
  DashboardQueryResult,
  DashboardQueriesResult,
} from './useQueryPatterns';

// Parallel Dashboard Data Hook (NEM-3412)
export { useDashboardData, default as useDashboardDataDefault } from './useDashboardData';
export type {
  UseDashboardDataOptions,
  DashboardData,
  UseDashboardDataReturn,
} from './useDashboardData';

// React 19 performance optimization hooks (NEM-3421)
export {
  useDeferredFilter,
  useDeferredSearch,
  default as useDeferredFilterDefault,
} from './useDeferredFilter';
export type {
  UseDeferredFilterOptions,
  UseDeferredFilterResult,
  UseDeferredSearchOptions,
} from './useDeferredFilter';

// Virtualized list hook (NEM-3423)
export { useVirtualizedList, default as useVirtualizedListDefault } from './useVirtualizedList';
export type { UseVirtualizedListOptions, UseVirtualizedListReturn } from './useVirtualizedList';

// Route prefetching hook (NEM-3359)
export { useRoutePrefetch, default as useRoutePrefetchDefault } from './useRoutePrefetch';
export type { UseRoutePrefetchOptions, UseRoutePrefetchReturn } from './useRoutePrefetch';

// Suspense query hooks (NEM-3360)
export {
  useSuspenseCamerasQuery,
  useSuspenseHealthQuery,
  useSuspenseSettingsQuery,
  useSuspenseNotificationPreferencesQuery,
  useSuspenseEventsInfiniteQuery,
} from './useSuspenseQueries';
export type {
  UseSuspenseCamerasQueryOptions,
  UseSuspenseCamerasQueryReturn,
  UseSuspenseHealthQueryOptions,
  UseSuspenseHealthQueryReturn,
  UseSuspenseSettingsQueryOptions,
  UseSuspenseSettingsQueryReturn,
  UseSuspenseNotificationPreferencesQueryOptions,
  UseSuspenseNotificationPreferencesQueryReturn,
  UseSuspenseEventsInfiniteQueryOptions,
  UseSuspenseEventsInfiniteQueryReturn,
} from './useSuspenseQueries';

// Optimistic mutation hooks (NEM-3361)
export {
  useOptimisticSettingsUpdate,
  useOptimisticNotificationPreferencesUpdate,
  useOptimisticCameraNotificationSettingUpdate,
  useOptimisticQuietHoursPeriodMutations,
} from './useOptimisticMutations';
export type {
  UseOptimisticSettingsUpdateOptions,
  UseOptimisticSettingsUpdateReturn,
  UseOptimisticNotificationPreferencesUpdateOptions,
  UseOptimisticNotificationPreferencesUpdateReturn,
  UseOptimisticCameraNotificationSettingUpdateOptions,
  UseOptimisticCameraNotificationSettingUpdateReturn,
  UseOptimisticQuietHoursPeriodMutationsOptions,
  UseOptimisticQuietHoursPeriodMutationsReturn,
} from './useOptimisticMutations';

// React 19 useOptimistic state hooks (NEM-3355)
export {
  useOptimisticToggle,
  useOptimisticList,
  useOptimisticValue,
  useOptimisticAction,
  createOptimisticReducer,
} from './useOptimisticState';
export type {
  OptimisticUpdateFn,
  UseOptimisticToggleReturn,
  UseOptimisticListReturn,
  UseOptimisticValueReturn,
  UseOptimisticActionOptions,
  UseOptimisticActionReturn,
} from './useOptimisticState';

// React 19 use() hook utilities (NEM-3357)
export {
  createContextWithUse,
  usePromiseValue,
  useConditionalContext,
  useContextOrDefault,
  createSuspenseResource,
  wrapPromise,
} from './useContextValue';
export type {
  ContextWithUse,
  CreateContextWithUseOptions,
  UsePromiseResult,
  UseConditionalContextResult,
  SuspenseResource,
} from './useContextValue';

// Batch status monitoring hook (NEM-3652)
export { useBatchStatus, default as useBatchStatusDefault } from './useBatchStatus';
export type {
  ActiveBatch,
  QueueDepths,
  BatchStats,
  UseBatchStatusOptions,
  UseBatchStatusReturn,
} from './useBatchStatus';
export type {
  UseCameraBaselineQueryOptions,
  UseCameraBaselineQueryReturn,
  UseCameraActivityBaselineQueryOptions,
  UseCameraActivityBaselineQueryReturn,
  UseCameraClassBaselineQueryOptions,
  UseCameraClassBaselineQueryReturn,
} from './useCameraBaselineQuery';

// Enrichment WebSocket hook (NEM-3627)
export {
  useEventEnrichmentWebSocket,
  default as useEventEnrichmentWebSocketDefault,
} from './useEventEnrichmentWebSocket';
export type {
  ActiveEnrichment,
  EnrichmentHistoryEntry,
  UseEventEnrichmentWebSocketOptions,
  UseEventEnrichmentWebSocketReturn,
} from './useEventEnrichmentWebSocket';

// Queue metrics WebSocket hook (NEM-3637)
export {
  useQueueMetricsWebSocket,
  default as useQueueMetricsWebSocketDefault,
} from './useQueueMetricsWebSocket';
export type {
  QueueStatusEntry,
  ThroughputEntry,
  UseQueueMetricsWebSocketOptions,
  UseQueueMetricsWebSocketReturn,
} from './useQueueMetricsWebSocket';

// Notification preferences hooks (NEM-3582)
export {
  useNotificationPreferences,
  useCameraNotificationSettings,
  useCameraNotificationSettingMutation,
  useQuietHoursPeriods,
  useQuietHoursPeriodMutations,
} from './useNotificationPreferences';
export type {
  UseNotificationPreferencesOptions,
  UseNotificationPreferencesReturn,
  UseCameraNotificationSettingsOptions,
  UseCameraNotificationSettingsReturn,
  UseCameraNotificationSettingMutationReturn,
  UseQuietHoursPeriodsOptions,
  UseQuietHoursPeriodsReturn,
  UseQuietHoursPeriodMutationsReturn,
} from './useNotificationPreferences';

// Integrated notifications hook (NEM-3537, NEM-3540, NEM-3617)
export {
  useIntegratedNotifications,
  default as useIntegratedNotificationsDefault,
} from './useIntegratedNotifications';
export type {
  IntegratedNotificationOptions,
  SecurityAlertOptions as IntegratedSecurityAlertOptions,
  UseIntegratedNotificationsReturn,
} from './useIntegratedNotifications';

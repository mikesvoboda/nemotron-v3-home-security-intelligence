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

export { useHealthStatus } from './useHealthStatus';
export type { UseHealthStatusOptions, UseHealthStatusReturn } from './useHealthStatus';

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

export { useStorageStatsQuery, useCleanupPreviewMutation, useCleanupMutation } from './useStorageStatsQuery';
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

export { useModelZooStatus } from './useModelZooStatus';
export type {
  VRAMStats,
  UseModelZooStatusOptions,
  UseModelZooStatusReturn,
} from './useModelZooStatus';

export { useSavedSearches } from './useSavedSearches';
export type { SavedSearch, LoadedSearch, UseSavedSearchesReturn } from './useSavedSearches';

export { useLocalStorage } from './useLocalStorage';

export { usePolling } from './usePolling';
export type { UsePollingOptions, UsePollingReturn } from './usePolling';

export { useThrottledValue } from './useThrottledValue';
export type { UseThrottledValueOptions } from './useThrottledValue';

export { useToast } from './useToast';
export type {
  ToastAction,
  ToastOptions,
  PromiseMessages,
  UseToastReturn,
} from './useToast';

export { useKeyboardShortcuts } from './useKeyboardShortcuts';
export type {
  UseKeyboardShortcutsOptions,
  UseKeyboardShortcutsReturn,
} from './useKeyboardShortcuts';

export { useListNavigation } from './useListNavigation';
export type {
  UseListNavigationOptions,
  UseListNavigationReturn,
} from './useListNavigation';

// PWA Hooks
export { useNetworkStatus } from './useNetworkStatus';
export type {
  UseNetworkStatusOptions,
  UseNetworkStatusReturn,
} from './useNetworkStatus';

export { useCachedEvents } from './useCachedEvents';
export type {
  CachedEvent,
  UseCachedEventsReturn,
} from './useCachedEvents';

export { usePushNotifications } from './usePushNotifications';
export type {
  SecurityAlertOptions,
  UsePushNotificationsReturn,
} from './usePushNotifications';

// Mobile Hooks
export { useIsMobile } from './useIsMobile';

export { useSwipeGesture } from './useSwipeGesture';
export type { SwipeDirection, SwipeGestureOptions } from './useSwipeGesture';

// Infinite scroll hook
export { useInfiniteScroll } from './useInfiniteScroll';
export type {
  UseInfiniteScrollOptions,
  UseInfiniteScrollReturn,
} from './useInfiniteScroll';

// Cursor-based pagination hooks
export { useCursorPaginatedQuery, default as useCursorPaginatedQueryDefault } from './useCursorPaginatedQuery';
export type {
  CursorPaginatedResponse,
  UseCursorPaginatedQueryOptions,
  UseCursorPaginatedQueryReturn,
  ExtractItemType,
} from './useCursorPaginatedQuery';

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

export { useServiceStatus } from './useServiceStatus';
export type {
  ServiceName,
  ServiceStatusType,
  ServiceStatus,
  UseServiceStatusResult,
} from './useServiceStatus';

export { useSceneChangeAlerts, formatChangeType, getChangeSeverity } from './useSceneChangeAlerts';
export type {
  SceneChangeAlert,
  UseSceneChangeAlertsOptions,
  UseSceneChangeAlertsReturn,
} from './useSceneChangeAlerts';

export { useRateLimitCountdown, formatCountdown } from './useRateLimitCountdown';
export type { UseRateLimitCountdownReturn } from './useRateLimitCountdown';

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

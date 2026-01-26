/**
 * Centralized Zustand Store Index (NEM-3789)
 *
 * Provides a unified export point for all Zustand stores with consistent patterns:
 * - All stores use Zustand 5 patterns (useShallow, createWithEqualityFn)
 * - Middleware utilities for Immer, DevTools, and subscribeWithSelector
 * - Type-safe selectors and shallow hooks for optimal re-render prevention
 *
 * @module stores
 *
 * @example
 * ```tsx
 * // Import specific stores
 * import { useSettingsStore, useAudioSettings } from '@/stores';
 *
 * // Import middleware utilities
 * import { createImmerStore, useShallow, shallow } from '@/stores';
 *
 * // Import all stores at once
 * import * as stores from '@/stores';
 * ```
 */

// ============================================================================
// Middleware Utilities (NEM-3788)
// ============================================================================

export {
  // Core Immer utilities
  produce,
  castDraft,
  current,
  isDraft,
  original,
  type Draft,

  // Zustand shallow utilities (Zustand 5 pattern)
  shallow,
  useShallow,
  subscribeWithSelector,

  // Immer store creators
  createImmerStore,
  createImmerSelectorStore,
  createImmerDevtoolsStore,
  type ImmerSetState,
  type ImmerStateCreator,
  type ImmerStoreOptions,

  // Immer utility functions
  applyImmerUpdate,
  createImmerAction,
  safeReadCurrent,
  safeReadOriginal,
  combineImmerUpdates,

  // Selector utilities
  createShallowSelector,
  shallowEqual,
  createComputedSelector,

  // Transient update utilities
  createTransientSlice,
  createTransientBatcher,
  type TransientSlice,
  type TransientBatchOptions,

  // WebSocket event utilities
  createWebSocketEventHandler,
  createDebouncedUpdater,
} from './middleware';

// ============================================================================
// Settings Store (NEM-3786)
// ============================================================================

export {
  // Main store
  useSettingsStore,

  // Types
  type AmbientSettings,
  type AudioSettings,
  type DesktopNotificationSettings,
  type FaviconSettings,
  type AmbientStatusSettings,
  type AppSettingsState,
  type SettingsActions,
  type SettingsStore,

  // Constants
  SETTINGS_STORAGE_KEY,
  SETTINGS_VERSION,
  DEFAULT_SETTINGS_STATE,

  // Selectors
  selectAmbientStatus,
  selectAmbientEnabled,
  selectAudioSettings,
  selectDesktopNotificationSettings,
  selectFaviconSettings,
  selectHasAnyNotificationEnabled,

  // Shallow hooks (Zustand 5 pattern)
  useAmbientSettings,
  useAudioSettings,
  useDesktopNotificationSettingsHook,
  useFaviconSettings,
  useSettingsActions,
  useFullSettings,
} from './settings-store';

// ============================================================================
// Dashboard Config Store
// ============================================================================

export {
  // Main store
  useDashboardConfigStore,

  // Types
  type WidgetId,
  type WidgetConfig,
  type ThemeSetting,
  type DashboardConfigState,
  type DashboardConfigActions,
  type DashboardConfigStore,
  type DashboardConfig,

  // Constants
  STORAGE_KEY as DASHBOARD_CONFIG_STORAGE_KEY,
  CONFIG_VERSION as DASHBOARD_CONFIG_VERSION,
  DEFAULT_REFRESH_INTERVAL,
  DEFAULT_WIDGETS,
  DEFAULT_CONFIG_STATE,

  // Selectors
  selectVisibleWidgets,
  selectIsWidgetVisible,
  selectWidgetById,
  selectWidgetIndex,
  selectCanMoveUp,
  selectCanMoveDown,
  selectEffectiveTheme,

  // Compatibility functions
  getDashboardConfig,
  setDashboardConfig,
} from './dashboard-config-store';

// ============================================================================
// Prometheus Alert Store
// ============================================================================

export {
  // Main store
  usePrometheusAlertStore,

  // Types
  type StoredPrometheusAlert,
  type PrometheusAlertState,

  // Selectors
  selectCriticalAlerts,
  selectWarningAlerts,
  selectInfoAlerts,
  selectAlertsSortedBySeverity,
  selectAlertByFingerprint,
  selectAlertsByName,
  selectHasActiveAlerts,
  selectHasCriticalAlerts,
} from './prometheus-alert-store';

// ============================================================================
// Rate Limit Store
// ============================================================================

export {
  // Main store
  useRateLimitStore,

  // Types
  type RateLimitInfo,
  type RateLimitState,

  // Selectors
  selectRateLimitUsagePercent,
  selectIsHighUsage,

  // Shallow hooks
  useRateLimitStatus,
  useRateLimitCurrent,
  useRateLimitActions,
} from './rate-limit-store';

// ============================================================================
// Real-time Metrics Store
// ============================================================================

export {
  // Main store
  useRealtimeMetricsStore,

  // Types
  type GPUMetrics,
  type PipelineMetrics,
  type InferenceMetrics,
  type RealtimeMetricsState,
  type GPUStatsEventPayload,
  type PipelineMetricsEventPayload,
  type InferenceMetricsEventPayload,

  // WebSocket event handlers
  handleGPUStatsEvent,
  handlePipelineMetricsEvent,
  handleInferenceMetricsEvent,

  // Selectors
  selectGPUUtilization,
  selectGPUMemoryUtilization,
  selectGPUTemperature,
  selectPipelineThroughput,
  selectTotalQueueDepth,
  selectPipelineErrorRate,
  selectCombinedModelLatency,
  selectGPUHealthStatus,
  selectPipelineHealthStatus,
} from './realtime-metrics-store';

// ============================================================================
// Storage Status Store
// ============================================================================

export {
  // Main store
  useStorageStatusStore,

  // Types
  type StorageStatus,
  type StorageStatusState,

  // Constants
  CRITICAL_USAGE_THRESHOLD,
  HIGH_USAGE_THRESHOLD,

  // Selectors
  selectFormattedUsage,

  // Shallow hooks
  useStorageWarningStatus,
  useStorageStatus,
  useStorageActions,
} from './storage-status-store';

// ============================================================================
// Worker Status Store
// ============================================================================

export {
  // Main store
  useWorkerStatusStore,

  // Types
  type PipelineHealthStatus,
  type WorkerStatus,
  type WorkerStatusState,

  // Selectors
  selectErrorWorkers,
  selectWarningWorkers,
  selectRunningWorkers,
  selectWorkerByName,
  selectWorkersByType,
} from './worker-status-store';

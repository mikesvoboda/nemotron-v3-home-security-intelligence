/**
 * useSettingsApi - TanStack Query hooks for settings API
 *
 * Provides hooks for fetching and updating system settings via the
 * /api/v1/settings endpoint. Settings are user-configurable values
 * that control detection thresholds, batch processing, feature toggles,
 * rate limiting, queue management, and data retention.
 *
 * Implements optimistic updates for instant UI feedback on mutations.
 *
 * Phase 2.3: Frontend settings API hook (NEM-3121)
 * Part of the Orphaned Infrastructure Integration epic (NEM-3113).
 *
 * @module hooks/useSettingsApi
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { STATIC_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Type Definitions
// ============================================================================

/**
 * Detection settings for object detection thresholds.
 */
export interface DetectionSettings {
  /** Minimum confidence threshold for object detections (0.0-1.0) */
  confidence_threshold: number;
  /** Confidence threshold for fast-path high-priority analysis (0.0-1.0) */
  fast_path_threshold: number;
}

/**
 * Batch processing settings for detection grouping.
 */
export interface BatchSettings {
  /** Time window in seconds for batch processing detections */
  window_seconds: number;
  /** Idle timeout in seconds before processing incomplete batch */
  idle_timeout_seconds: number;
}

/**
 * Severity threshold settings for risk score categorization.
 */
export interface SeveritySettings {
  /** Maximum risk score for LOW severity (0 to this value = LOW) */
  low_max: number;
  /** Maximum risk score for MEDIUM severity */
  medium_max: number;
  /** Maximum risk score for HIGH severity (above = CRITICAL) */
  high_max: number;
}

/**
 * Feature toggle settings for AI pipeline components.
 */
export interface FeatureSettings {
  /** Enable Florence-2 vision extraction for vehicle/person attributes */
  vision_extraction_enabled: boolean;
  /** Enable CLIP re-identification for tracking entities across cameras */
  reid_enabled: boolean;
  /** Enable SSIM-based scene change detection */
  scene_change_enabled: boolean;
  /** Enable automatic clip generation for events */
  clip_generation_enabled: boolean;
  /** Enable BRISQUE image quality assessment (CPU-based) */
  image_quality_enabled: boolean;
  /** Enable automatic background AI audit evaluation when GPU is idle */
  background_eval_enabled: boolean;
}

/**
 * Rate limiting settings for API protection.
 */
export interface RateLimitingSettings {
  /** Enable rate limiting for API endpoints */
  enabled: boolean;
  /** Maximum requests per minute per client IP */
  requests_per_minute: number;
  /** Additional burst allowance for short request spikes */
  burst_size: number;
}

/**
 * Queue settings for Redis-based processing queues.
 */
export interface QueueSettings {
  /** Maximum size of Redis queues */
  max_size: number;
  /** Queue fill ratio (0.0-1.0) at which to start backpressure warnings */
  backpressure_threshold: number;
}

/**
 * Data retention settings for events and logs.
 */
export interface RetentionSettings {
  /** Number of days to retain events and detections */
  days: number;
  /** Number of days to retain logs */
  log_days: number;
}

/**
 * Complete settings response from GET /api/v1/settings.
 */
export interface SettingsResponse {
  /** Detection confidence threshold settings */
  detection: DetectionSettings;
  /** Batch processing settings */
  batch: BatchSettings;
  /** Severity threshold settings for risk categorization */
  severity: SeveritySettings;
  /** Feature toggle settings */
  features: FeatureSettings;
  /** Rate limiting settings */
  rate_limiting: RateLimitingSettings;
  /** Queue settings */
  queue: QueueSettings;
  /** Data retention settings */
  retention: RetentionSettings;
}

// ============================================================================
// Update Type Definitions (all fields optional for partial updates)
// ============================================================================

/**
 * Detection settings update (all fields optional).
 */
export interface DetectionSettingsUpdate {
  confidence_threshold?: number;
  fast_path_threshold?: number;
}

/**
 * Batch settings update (all fields optional).
 */
export interface BatchSettingsUpdate {
  window_seconds?: number;
  idle_timeout_seconds?: number;
}

/**
 * Severity settings update (all fields optional).
 */
export interface SeveritySettingsUpdate {
  low_max?: number;
  medium_max?: number;
  high_max?: number;
}

/**
 * Feature settings update (all fields optional).
 */
export interface FeatureSettingsUpdate {
  vision_extraction_enabled?: boolean;
  reid_enabled?: boolean;
  scene_change_enabled?: boolean;
  clip_generation_enabled?: boolean;
  image_quality_enabled?: boolean;
  background_eval_enabled?: boolean;
}

/**
 * Rate limiting settings update (all fields optional).
 */
export interface RateLimitingSettingsUpdate {
  enabled?: boolean;
  requests_per_minute?: number;
  burst_size?: number;
}

/**
 * Queue settings update (all fields optional).
 */
export interface QueueSettingsUpdate {
  max_size?: number;
  backpressure_threshold?: number;
}

/**
 * Retention settings update (all fields optional).
 */
export interface RetentionSettingsUpdate {
  days?: number;
  log_days?: number;
}

/**
 * Settings update request for PATCH /api/v1/settings.
 * All fields are optional to support partial updates.
 */
export interface SettingsUpdate {
  detection?: DetectionSettingsUpdate;
  batch?: BatchSettingsUpdate;
  severity?: SeveritySettingsUpdate;
  features?: FeatureSettingsUpdate;
  rate_limiting?: RateLimitingSettingsUpdate;
  queue?: QueueSettingsUpdate;
  retention?: RetentionSettingsUpdate;
}

// ============================================================================
// Optimistic Update Context
// ============================================================================

/**
 * Context for optimistic update rollback.
 */
interface SettingsOptimisticContext {
  previousSettings: SettingsResponse | undefined;
}

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for settings API.
 */
export const settingsQueryKeys = {
  /** Base key for all settings queries */
  all: ['settings'] as const,
  /** Current settings */
  current: () => [...settingsQueryKeys.all, 'current'] as const,
};

// ============================================================================
// API Functions
// ============================================================================

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '';
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined;

/**
 * Build headers for API requests.
 */
function buildHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }
  return headers;
}

/**
 * Handle API response and extract error message on failure.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorBody = (await response.json()) as { detail?: string };
      if (errorBody.detail) {
        errorMessage = errorBody.detail;
      }
    } catch {
      // Use default error message if JSON parsing fails
    }
    throw new Error(errorMessage);
  }
  return response.json() as Promise<T>;
}

/**
 * Fetch current system settings from the API.
 */
export async function fetchSettings(): Promise<SettingsResponse> {
  const response = await fetch(`${BASE_URL}/api/v1/settings`, {
    method: 'GET',
    headers: buildHeaders(),
  });
  return handleResponse<SettingsResponse>(response);
}

/**
 * Update system settings via the API.
 */
export async function updateSettings(update: SettingsUpdate): Promise<SettingsResponse> {
  const response = await fetch(`${BASE_URL}/api/v1/settings`, {
    method: 'PATCH',
    headers: buildHeaders(),
    body: JSON.stringify(update),
  });
  return handleResponse<SettingsResponse>(response);
}

// ============================================================================
// Hook Options and Return Types
// ============================================================================

/**
 * Options for configuring the useSettings hook.
 */
export interface UseSettingsOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds.
   * @default false (no auto-refetch)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * @default STATIC_STALE_TIME (5 minutes)
   */
  staleTime?: number;

  /**
   * Number of retry attempts on failure.
   * @default 1
   */
  retry?: number | false;
}

/**
 * Return type for the useSettings hook.
 */
export interface UseSettingsReturn {
  /** Current settings data, undefined if not yet fetched */
  settings: SettingsResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether any fetch is in progress (including background refetch) */
  isFetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the query has errored */
  isError: boolean;
  /** Whether the query was successful */
  isSuccess: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Return type for the useUpdateSettings hook.
 */
export interface UseUpdateSettingsReturn {
  /** Update settings mutation function */
  mutate: (update: SettingsUpdate) => void;
  /** Update settings mutation function (async) */
  mutateAsync: (update: SettingsUpdate) => Promise<SettingsResponse>;
  /** Whether the mutation is in progress */
  isPending: boolean;
  /** Whether the mutation was successful */
  isSuccess: boolean;
  /** Whether the mutation has errored */
  isError: boolean;
  /** Error object if the mutation failed */
  error: Error | null;
  /** The data returned from the last successful mutation */
  data: SettingsResponse | undefined;
  /** Reset mutation state */
  reset: () => void;
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook to fetch current system settings using TanStack Query.
 */
export function useSettingsQuery(options: UseSettingsOptions = {}): UseSettingsReturn {
  const {
    enabled = true,
    refetchInterval = false,
    staleTime = STATIC_STALE_TIME,
    retry = 1,
  } = options;

  const query = useQuery({
    queryKey: settingsQueryKeys.current(),
    queryFn: fetchSettings,
    enabled,
    refetchInterval,
    staleTime,
    retry,
  });

  return {
    settings: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    isError: query.isError,
    isSuccess: query.isSuccess,
    refetch: query.refetch,
  };
}

/**
 * Deep merge two settings objects for optimistic updates.
 */
function mergeSettings(current: SettingsResponse, updates: SettingsUpdate): SettingsResponse {
  return {
    detection: { ...current.detection, ...updates.detection },
    batch: { ...current.batch, ...updates.batch },
    severity: { ...current.severity, ...updates.severity },
    features: { ...current.features, ...updates.features },
    rate_limiting: { ...current.rate_limiting, ...updates.rate_limiting },
    queue: { ...current.queue, ...updates.queue },
    retention: { ...current.retention, ...updates.retention },
  };
}

/**
 * Hook to update system settings with optimistic updates.
 */
export function useUpdateSettings(): UseUpdateSettingsReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: updateSettings,

    // Optimistic update: Apply changes immediately before API response
    onMutate: async (update: SettingsUpdate): Promise<SettingsOptimisticContext> => {
      await queryClient.cancelQueries({ queryKey: settingsQueryKeys.current() });

      const previousSettings = queryClient.getQueryData<SettingsResponse>(
        settingsQueryKeys.current()
      );

      if (previousSettings) {
        const optimisticSettings = mergeSettings(previousSettings, update);
        queryClient.setQueryData(settingsQueryKeys.current(), optimisticSettings);
      }

      return { previousSettings };
    },

    // Rollback on error
    onError: (
      _error: Error,
      _update: SettingsUpdate,
      context: SettingsOptimisticContext | undefined
    ) => {
      if (context?.previousSettings) {
        queryClient.setQueryData(settingsQueryKeys.current(), context.previousSettings);
      }
    },

    // On success, update cache with server response
    onSuccess: (data: SettingsResponse) => {
      queryClient.setQueryData(settingsQueryKeys.current(), data);
    },

    // Always invalidate after mutation settles
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: settingsQueryKeys.all });
    },
  });

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    data: mutation.data,
    reset: mutation.reset,
  };
}

/**
 * Combined hook for settings API operations.
 */
export function useSettingsApi(options: UseSettingsOptions = {}) {
  const settingsQuery = useSettingsQuery(options);
  const updateMutation = useUpdateSettings();

  return {
    settings: settingsQuery.settings,
    isLoading: settingsQuery.isLoading,
    isFetching: settingsQuery.isFetching,
    error: settingsQuery.error,
    isError: settingsQuery.isError,
    isSuccess: settingsQuery.isSuccess,
    refetch: settingsQuery.refetch,
    updateMutation,
  };
}

export default useSettingsApi;

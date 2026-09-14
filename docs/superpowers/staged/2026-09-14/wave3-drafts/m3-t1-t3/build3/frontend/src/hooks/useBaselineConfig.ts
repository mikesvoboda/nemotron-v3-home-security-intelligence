/**
 * React Query hooks for baseline configuration management
 *
 * Provides typed hooks for:
 * - Fetching camera baseline configuration
 * - Updating per-camera baseline settings
 * - Resetting baseline data for a camera
 *
 * @see NEM-4921 - Phase 3: Baseline Tuning UI
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import {
  fetchBaselineConfig,
  updateBaselineConfig,
  resetCameraBaseline,
  type BaselineConfigResponse,
  type BaselineConfigUpdate,
  type BaselineResetResponse,
} from '../services/baselineConfigApi';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for baseline config queries.
 * Ensures consistent cache key generation across the app.
 */
export const baselineConfigKeys = {
  all: ['baseline-config'] as const,
  config: (cameraId: string) => [...baselineConfigKeys.all, cameraId] as const,
  baseline: (cameraId: string) => ['baseline', cameraId] as const,
};

// ============================================================================
// useBaselineConfigQuery
// ============================================================================

/**
 * Hook to fetch baseline configuration for a camera.
 *
 * Returns the active configuration for anomaly detection, including both
 * per-camera overrides (if enabled) and global defaults.
 *
 * @param cameraId - ID of the camera
 * @returns React Query result with BaselineConfigResponse
 *
 * @example
 * ```typescript
 * const { data, isLoading, error } = useBaselineConfigQuery('front_door');
 *
 * if (data?.override_global_config) {
 *   console.log('Using custom settings:', data.threshold_stdev);
 * }
 * ```
 */
export function useBaselineConfigQuery(cameraId: string) {
  return useQuery<BaselineConfigResponse, Error>({
    queryKey: baselineConfigKeys.config(cameraId),
    queryFn: () => fetchBaselineConfig(cameraId),
    enabled: !!cameraId,
  });
}

// ============================================================================
// useUpdateBaselineConfig
// ============================================================================

/**
 * Hook to update baseline configuration for a camera.
 *
 * Returns a mutation that updates per-camera configuration overrides.
 * Automatically invalidates the config query on success.
 *
 * @param cameraId - ID of the camera
 * @returns React Query mutation for BaselineConfigUpdate
 *
 * @example
 * ```typescript
 * const mutation = useUpdateBaselineConfig('front_door');
 *
 * mutation.mutate({
 *   threshold_stdev: 3.0,
 *   min_samples: 15,
 *   override_global_config: true,
 * });
 * ```
 */
export function useUpdateBaselineConfig(cameraId: string) {
  const queryClient = useQueryClient();

  return useMutation<BaselineConfigResponse, Error, BaselineConfigUpdate>({
    mutationFn: (config: BaselineConfigUpdate) => updateBaselineConfig(cameraId, config),
    onSuccess: () => {
      // Invalidate the config query to refetch updated data
      void queryClient.invalidateQueries({ queryKey: baselineConfigKeys.config(cameraId) });
    },
  });
}

// ============================================================================
// useResetBaseline
// ============================================================================

/**
 * Hook to reset all baseline data for a camera.
 *
 * Returns a mutation that deletes all ActivityBaseline and ClassBaseline
 * records for the camera. Automatically invalidates related queries on success.
 *
 * @param cameraId - ID of the camera
 * @returns React Query mutation for baseline reset
 *
 * @example
 * ```typescript
 * const mutation = useResetBaseline('front_door');
 *
 * mutation.mutate();
 *
 * if (mutation.isSuccess) {
 *   console.log(`Deleted ${mutation.data.activity_baselines_deleted} activity baselines`);
 * }
 * ```
 */
export function useResetBaseline(cameraId: string) {
  const queryClient = useQueryClient();

  return useMutation<BaselineResetResponse, Error, void>({
    mutationFn: () => resetCameraBaseline(cameraId),
    onSuccess: () => {
      // Invalidate config and baseline queries to show fresh data
      void queryClient.invalidateQueries({ queryKey: baselineConfigKeys.config(cameraId) });
      void queryClient.invalidateQueries({ queryKey: baselineConfigKeys.baseline(cameraId) });
    },
  });
}

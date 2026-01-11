/**
 * useNotificationPreferences - TanStack Query hooks for notification preferences
 *
 * This module provides hooks for managing notification preferences using
 * TanStack Query. It includes:
 * - useNotificationPreferences: Fetch and update global notification preferences
 * - useCameraNotificationSettings: Fetch all camera notification settings
 * - useCameraNotificationSettingMutation: Update camera notification settings
 * - useQuietHoursPeriods: Fetch all quiet hours periods
 * - useQuietHoursPeriodMutations: Create and delete quiet hours periods
 *
 * @module hooks/useNotificationPreferences
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchNotificationPreferences,
  updateNotificationPreferences,
  fetchCameraNotificationSettings,
  updateCameraNotificationSetting,
  fetchQuietHoursPeriods,
  createQuietHoursPeriod,
  deleteQuietHoursPeriod,
  type NotificationPreferencesResponse,
  type NotificationPreferencesUpdate,
  type CameraNotificationSettingResponse,
  type CameraNotificationSettingUpdate,
  type QuietHoursPeriodResponse,
  type QuietHoursPeriodCreate,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// useNotificationPreferences - Global notification preferences
// ============================================================================

/**
 * Options for configuring the useNotificationPreferences hook
 */
export interface UseNotificationPreferencesOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useNotificationPreferences hook
 */
export interface UseNotificationPreferencesReturn {
  /** Current notification preferences */
  preferences: NotificationPreferencesResponse | null;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Mutation for updating preferences */
  updateMutation: ReturnType<
    typeof useMutation<NotificationPreferencesResponse, Error, NotificationPreferencesUpdate>
  >;
}

/**
 * Hook to fetch and update global notification preferences.
 *
 * @param options - Configuration options
 * @returns Preferences data, query state, and update mutation
 *
 * @example
 * ```tsx
 * const { preferences, isLoading, updateMutation } = useNotificationPreferences();
 *
 * // Toggle notifications
 * const handleToggle = () => {
 *   updateMutation.mutate({ enabled: !preferences?.enabled });
 * };
 * ```
 */
export function useNotificationPreferences(
  options: UseNotificationPreferencesOptions = {}
): UseNotificationPreferencesReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: queryKeys.notifications.preferences.global,
    queryFn: fetchNotificationPreferences,
    enabled,
    staleTime,
    retry: 1,
  });

  const updateMutation = useMutation({
    mutationFn: (update: NotificationPreferencesUpdate) => updateNotificationPreferences(update),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.notifications.preferences.global,
      });
    },
  });

  return {
    preferences: query.data ?? null,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
    updateMutation,
  };
}

// ============================================================================
// useCameraNotificationSettings - Camera-specific notification settings
// ============================================================================

/**
 * Options for configuring the useCameraNotificationSettings hook
 */
export interface UseCameraNotificationSettingsOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useCameraNotificationSettings hook
 */
export interface UseCameraNotificationSettingsReturn {
  /** List of camera notification settings */
  settings: CameraNotificationSettingResponse[];
  /** Total count of settings */
  count: number;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch all camera notification settings.
 *
 * @param options - Configuration options
 * @returns Settings list and query state
 *
 * @example
 * ```tsx
 * const { settings, isLoading } = useCameraNotificationSettings();
 *
 * return (
 *   <ul>
 *     {settings.map(setting => (
 *       <li key={setting.id}>{setting.camera_id}: {setting.enabled ? 'On' : 'Off'}</li>
 *     ))}
 *   </ul>
 * );
 * ```
 */
export function useCameraNotificationSettings(
  options: UseCameraNotificationSettingsOptions = {}
): UseCameraNotificationSettingsReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.notifications.preferences.cameras.list(),
    queryFn: fetchCameraNotificationSettings,
    enabled,
    staleTime,
    retry: 1,
  });

  const settings = useMemo(() => query.data?.items ?? [], [query.data?.items]);
  const count = useMemo(() => query.data?.pagination?.total ?? 0, [query.data?.pagination?.total]);

  return {
    settings,
    count,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useCameraNotificationSettingMutation - Update camera notification settings
// ============================================================================

/**
 * Return type for the useCameraNotificationSettingMutation hook
 */
export interface UseCameraNotificationSettingMutationReturn {
  /** Mutation for updating a camera notification setting */
  updateMutation: ReturnType<
    typeof useMutation<
      CameraNotificationSettingResponse,
      Error,
      { cameraId: string; update: CameraNotificationSettingUpdate }
    >
  >;
}

/**
 * Hook providing mutation for updating camera notification settings.
 *
 * @returns Update mutation
 *
 * @example
 * ```tsx
 * const { updateMutation } = useCameraNotificationSettingMutation();
 *
 * // Update camera setting
 * await updateMutation.mutateAsync({
 *   cameraId: 'front_door',
 *   update: { enabled: false, risk_threshold: 70 }
 * });
 * ```
 */
export function useCameraNotificationSettingMutation(): UseCameraNotificationSettingMutationReturn {
  const queryClient = useQueryClient();

  const updateMutation = useMutation({
    mutationFn: ({ cameraId, update }: { cameraId: string; update: CameraNotificationSettingUpdate }) =>
      updateCameraNotificationSetting(cameraId, update),
    onSuccess: (_data, variables) => {
      // Invalidate the list of all camera settings
      void queryClient.invalidateQueries({
        queryKey: queryKeys.notifications.preferences.cameras.all,
      });
      // Also invalidate the specific camera setting
      void queryClient.invalidateQueries({
        queryKey: queryKeys.notifications.preferences.cameras.detail(variables.cameraId),
      });
    },
  });

  return { updateMutation };
}

// ============================================================================
// useQuietHoursPeriods - Quiet hours periods
// ============================================================================

/**
 * Options for configuring the useQuietHoursPeriods hook
 */
export interface UseQuietHoursPeriodsOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useQuietHoursPeriods hook
 */
export interface UseQuietHoursPeriodsReturn {
  /** List of quiet hours periods */
  periods: QuietHoursPeriodResponse[];
  /** Total count of periods */
  count: number;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch all quiet hours periods.
 *
 * @param options - Configuration options
 * @returns Periods list and query state
 *
 * @example
 * ```tsx
 * const { periods, isLoading } = useQuietHoursPeriods();
 *
 * return (
 *   <ul>
 *     {periods.map(period => (
 *       <li key={period.id}>{period.label}: {period.start_time} - {period.end_time}</li>
 *     ))}
 *   </ul>
 * );
 * ```
 */
export function useQuietHoursPeriods(
  options: UseQuietHoursPeriodsOptions = {}
): UseQuietHoursPeriodsReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.notifications.preferences.quietHours.list(),
    queryFn: fetchQuietHoursPeriods,
    enabled,
    staleTime,
    retry: 1,
  });

  const periods = useMemo(() => query.data?.items ?? [], [query.data?.items]);
  const count = useMemo(() => query.data?.pagination?.total ?? 0, [query.data?.pagination?.total]);

  return {
    periods,
    count,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useQuietHoursPeriodMutations - Create and delete quiet hours periods
// ============================================================================

/**
 * Return type for the useQuietHoursPeriodMutations hook
 */
export interface UseQuietHoursPeriodMutationsReturn {
  /** Mutation for creating a new quiet hours period */
  createMutation: ReturnType<typeof useMutation<QuietHoursPeriodResponse, Error, QuietHoursPeriodCreate>>;
  /** Mutation for deleting a quiet hours period */
  deleteMutation: ReturnType<typeof useMutation<void, Error, string>>;
}

/**
 * Hook providing mutations for creating and deleting quiet hours periods.
 *
 * @returns Create and delete mutations
 *
 * @example
 * ```tsx
 * const { createMutation, deleteMutation } = useQuietHoursPeriodMutations();
 *
 * // Create a new period
 * await createMutation.mutateAsync({
 *   label: 'Night Time',
 *   start_time: '22:00:00',
 *   end_time: '06:00:00',
 *   days: ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
 * });
 *
 * // Delete a period
 * await deleteMutation.mutateAsync('period-uuid');
 * ```
 */
export function useQuietHoursPeriodMutations(): UseQuietHoursPeriodMutationsReturn {
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (period: QuietHoursPeriodCreate) => createQuietHoursPeriod(period),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.notifications.preferences.quietHours.all,
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (periodId: string) => deleteQuietHoursPeriod(periodId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.notifications.preferences.quietHours.all,
      });
    },
  });

  return {
    createMutation,
    deleteMutation,
  };
}

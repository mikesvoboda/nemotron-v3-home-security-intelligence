/**
 * useOptimisticMutations - Enhanced mutations with optimistic updates (NEM-3361)
 *
 * This module provides mutation hooks with built-in optimistic updates for
 * instant UI feedback. Each mutation follows the pattern:
 *
 * 1. Cancel outgoing queries to prevent race conditions
 * 2. Snapshot current state for rollback
 * 3. Apply optimistic update immediately
 * 4. On error: rollback to snapshot
 * 5. On success: replace optimistic data with server response
 * 6. On settled: invalidate queries for consistency
 *
 * @module hooks/useOptimisticMutations
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';

import {
  updateSettings,
  type SettingsResponse,
  type SettingsUpdate,
  settingsQueryKeys,
} from './useSettingsApi';
import {
  updateNotificationPreferences,
  updateCameraNotificationSetting,
  createQuietHoursPeriod,
  deleteQuietHoursPeriod,
  type NotificationPreferencesResponse,
  type NotificationPreferencesUpdate,
  type CameraNotificationSettingResponse,
  type CameraNotificationSettingUpdate,
  type QuietHoursPeriodResponse,
  type QuietHoursPeriodCreate,
} from '../services/api';
import { cancelOutgoingQueries, rollbackSingle } from '../services/optimisticUpdates';
import { queryKeys } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Context for optimistic mutation rollback
 */
interface OptimisticContext<T> {
  previousData: T | undefined;
  optimisticId?: string | number;
}

// ============================================================================
// useOptimisticSettingsUpdate - Settings with optimistic update
// ============================================================================

/**
 * Options for useOptimisticSettingsUpdate
 */
export interface UseOptimisticSettingsUpdateOptions {
  /** Callback on successful update */
  onSuccess?: (data: SettingsResponse) => void;
  /** Callback on error */
  onError?: (error: Error) => void;
}

/**
 * Return type for useOptimisticSettingsUpdate
 */
export interface UseOptimisticSettingsUpdateReturn {
  /** Update settings with optimistic feedback */
  mutate: (update: SettingsUpdate) => void;
  /** Update settings with optimistic feedback (async) */
  mutateAsync: (update: SettingsUpdate) => Promise<SettingsResponse>;
  /** Whether the mutation is in progress */
  isPending: boolean;
  /** Whether the mutation was successful */
  isSuccess: boolean;
  /** Whether the mutation errored */
  isError: boolean;
  /** Error from the mutation */
  error: Error | null;
  /** Data from successful mutation */
  data: SettingsResponse | undefined;
  /** Reset mutation state */
  reset: () => void;
}

/**
 * Hook for updating settings with optimistic updates.
 *
 * Provides instant UI feedback by immediately applying the update
 * to the cache, with automatic rollback on error.
 *
 * @param options - Configuration options
 * @returns Mutation functions and state
 *
 * @example
 * ```tsx
 * const { mutate, isPending } = useOptimisticSettingsUpdate();
 *
 * const handleToggleFeature = () => {
 *   // UI updates immediately, no waiting for server
 *   mutate({
 *     features: { reid_enabled: false }
 *   });
 * };
 * ```
 */
export function useOptimisticSettingsUpdate(
  options: UseOptimisticSettingsUpdateOptions = {}
): UseOptimisticSettingsUpdateReturn {
  const { onSuccess, onError } = options;
  const queryClient = useQueryClient();
  const settingsKey = settingsQueryKeys.current();

  const mutation = useMutation({
    mutationFn: updateSettings,

    onMutate: async (update: SettingsUpdate) => {
      await cancelOutgoingQueries(queryClient, settingsKey);

      const previousData = queryClient.getQueryData<SettingsResponse>(settingsKey);

      // Apply optimistic update - merge updates with current data
      if (previousData) {
        const optimisticData: SettingsResponse = {
          ...previousData,
          ...(update.detection && {
            detection: { ...previousData.detection, ...update.detection },
          }),
          ...(update.batch && {
            batch: { ...previousData.batch, ...update.batch },
          }),
          ...(update.severity && {
            severity: { ...previousData.severity, ...update.severity },
          }),
          ...(update.features && {
            features: { ...previousData.features, ...update.features },
          }),
          ...(update.rate_limiting && {
            rate_limiting: { ...previousData.rate_limiting, ...update.rate_limiting },
          }),
          ...(update.queue && {
            queue: { ...previousData.queue, ...update.queue },
          }),
          ...(update.retention && {
            retention: { ...previousData.retention, ...update.retention },
          }),
        };

        queryClient.setQueryData(settingsKey, optimisticData);
      }

      return { previousData };
    },

    onError: (error, _variables, context?: OptimisticContext<SettingsResponse>) => {
      if (context?.previousData) {
        rollbackSingle(queryClient, settingsKey, context.previousData);
      }
      onError?.(error);
    },

    onSuccess: (data) => {
      queryClient.setQueryData(settingsKey, data);
      onSuccess?.(data);
    },

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

// ============================================================================
// useOptimisticNotificationPreferencesUpdate
// ============================================================================

/**
 * Options for useOptimisticNotificationPreferencesUpdate
 */
export interface UseOptimisticNotificationPreferencesUpdateOptions {
  /** Callback on successful update */
  onSuccess?: (data: NotificationPreferencesResponse) => void;
  /** Callback on error */
  onError?: (error: Error) => void;
}

/**
 * Return type for useOptimisticNotificationPreferencesUpdate
 */
export interface UseOptimisticNotificationPreferencesUpdateReturn {
  /** Update preferences with optimistic feedback */
  mutate: (update: NotificationPreferencesUpdate) => void;
  /** Update preferences with optimistic feedback (async) */
  mutateAsync: (update: NotificationPreferencesUpdate) => Promise<NotificationPreferencesResponse>;
  /** Whether the mutation is in progress */
  isPending: boolean;
  /** Whether the mutation was successful */
  isSuccess: boolean;
  /** Whether the mutation errored */
  isError: boolean;
  /** Error from the mutation */
  error: Error | null;
  /** Reset mutation state */
  reset: () => void;
}

/**
 * Hook for updating notification preferences with optimistic updates.
 *
 * @param options - Configuration options
 * @returns Mutation functions and state
 *
 * @example
 * ```tsx
 * const { mutate } = useOptimisticNotificationPreferencesUpdate();
 *
 * // Toggle switches update instantly
 * mutate({ enabled: false });
 * ```
 */
export function useOptimisticNotificationPreferencesUpdate(
  options: UseOptimisticNotificationPreferencesUpdateOptions = {}
): UseOptimisticNotificationPreferencesUpdateReturn {
  const { onSuccess, onError } = options;
  const queryClient = useQueryClient();
  const prefsKey = queryKeys.notifications.preferences.global;

  const mutation = useMutation({
    mutationFn: updateNotificationPreferences,

    onMutate: async (update: NotificationPreferencesUpdate) => {
      await cancelOutgoingQueries(queryClient, prefsKey);

      const previousData = queryClient.getQueryData<NotificationPreferencesResponse>(prefsKey);

      // Apply optimistic update with null filtering
      if (previousData) {
        const optimisticData: NotificationPreferencesResponse = {
          ...previousData,
          ...(update.enabled !== null && update.enabled !== undefined && { enabled: update.enabled }),
          ...(update.risk_filters !== null && update.risk_filters !== undefined && { risk_filters: update.risk_filters }),
          ...(update.sound !== null && update.sound !== undefined && { sound: update.sound }),
        };
        queryClient.setQueryData(prefsKey, optimisticData);
      }

      return { previousData };
    },

    onError: (error, _variables, context?: OptimisticContext<NotificationPreferencesResponse>) => {
      if (context?.previousData) {
        rollbackSingle(queryClient, prefsKey, context.previousData);
      }
      onError?.(error);
    },

    onSuccess: (data) => {
      queryClient.setQueryData(prefsKey, data);
      onSuccess?.(data);
    },

    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.notifications.preferences.all });
    },
  });

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    reset: mutation.reset,
  };
}

// ============================================================================
// useOptimisticCameraNotificationSettingUpdate
// ============================================================================

/**
 * Options for useOptimisticCameraNotificationSettingUpdate
 */
export interface UseOptimisticCameraNotificationSettingUpdateOptions {
  /** Callback on successful update */
  onSuccess?: (data: CameraNotificationSettingResponse) => void;
  /** Callback on error */
  onError?: (error: Error) => void;
}

/**
 * Return type for useOptimisticCameraNotificationSettingUpdate
 */
export interface UseOptimisticCameraNotificationSettingUpdateReturn {
  /** Update camera setting with optimistic feedback */
  mutate: (variables: { cameraId: string; update: CameraNotificationSettingUpdate }) => void;
  /** Update camera setting with optimistic feedback (async) */
  mutateAsync: (variables: {
    cameraId: string;
    update: CameraNotificationSettingUpdate;
  }) => Promise<CameraNotificationSettingResponse>;
  /** Whether the mutation is in progress */
  isPending: boolean;
  /** Whether the mutation was successful */
  isSuccess: boolean;
  /** Whether the mutation errored */
  isError: boolean;
  /** Error from the mutation */
  error: Error | null;
  /** Reset mutation state */
  reset: () => void;
}

/**
 * Hook for updating camera notification settings with optimistic updates.
 *
 * @param options - Configuration options
 * @returns Mutation functions and state
 */
export function useOptimisticCameraNotificationSettingUpdate(
  options: UseOptimisticCameraNotificationSettingUpdateOptions = {}
): UseOptimisticCameraNotificationSettingUpdateReturn {
  const { onSuccess, onError } = options;
  const queryClient = useQueryClient();
  const listKey = queryKeys.notifications.preferences.cameras.list();

  const mutation = useMutation({
    mutationFn: ({
      cameraId,
      update,
    }: {
      cameraId: string;
      update: CameraNotificationSettingUpdate;
    }) => updateCameraNotificationSetting(cameraId, update),

    onMutate: async ({
      cameraId,
      update,
    }: {
      cameraId: string;
      update: CameraNotificationSettingUpdate;
    }) => {
      await cancelOutgoingQueries(queryClient, listKey);

      const previousData = queryClient.getQueryData<{
        items: CameraNotificationSettingResponse[];
      }>(listKey);

      // Optimistically update the camera setting in the list
      queryClient.setQueryData<{ items: CameraNotificationSettingResponse[] }>(listKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          items: old.items.map((item) => {
            if (item.camera_id !== cameraId) return item;
            // Apply non-null updates
            const updatedItem: CameraNotificationSettingResponse = { ...item };
            if (update.enabled !== null && update.enabled !== undefined) {
              updatedItem.enabled = update.enabled;
            }
            if (update.risk_threshold !== null && update.risk_threshold !== undefined) {
              updatedItem.risk_threshold = update.risk_threshold;
            }
            return updatedItem;
          }),
        };
      });

      return { previousData };
    },

    onError: (
      error,
      _variables,
      context?: OptimisticContext<{ items: CameraNotificationSettingResponse[] }>
    ) => {
      if (context?.previousData) {
        queryClient.setQueryData(listKey, context.previousData);
      }
      onError?.(error);
    },

    onSuccess: (data, variables) => {
      // Update both list and detail caches
      void queryClient.invalidateQueries({
        queryKey: queryKeys.notifications.preferences.cameras.all,
      });
      void queryClient.invalidateQueries({
        queryKey: queryKeys.notifications.preferences.cameras.detail(variables.cameraId),
      });
      onSuccess?.(data);
    },
  });

  return {
    mutate: mutation.mutate,
    mutateAsync: mutation.mutateAsync,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    reset: mutation.reset,
  };
}

// ============================================================================
// useOptimisticQuietHoursPeriodMutations
// ============================================================================

/**
 * Options for useOptimisticQuietHoursPeriodMutations
 */
export interface UseOptimisticQuietHoursPeriodMutationsOptions {
  /** Callback on successful create */
  onCreateSuccess?: (data: QuietHoursPeriodResponse) => void;
  /** Callback on create error */
  onCreateError?: (error: Error) => void;
  /** Callback on successful delete */
  onDeleteSuccess?: () => void;
  /** Callback on delete error */
  onDeleteError?: (error: Error) => void;
}

/**
 * Return type for useOptimisticQuietHoursPeriodMutations
 */
export interface UseOptimisticQuietHoursPeriodMutationsReturn {
  /** Create a quiet hours period with optimistic feedback */
  createPeriod: ReturnType<typeof useMutation<QuietHoursPeriodResponse, Error, QuietHoursPeriodCreate>>;
  /** Delete a quiet hours period with optimistic feedback */
  deletePeriod: ReturnType<typeof useMutation<void, Error, string>>;
}

/**
 * Hook for quiet hours period mutations with optimistic updates.
 *
 * @param options - Configuration options
 * @returns Create and delete mutations with optimistic updates
 *
 * @example
 * ```tsx
 * const { createPeriod, deletePeriod } = useOptimisticQuietHoursPeriodMutations();
 *
 * // Create appears instantly in UI
 * createPeriod.mutate({
 *   label: 'Night Time',
 *   start_time: '22:00:00',
 *   end_time: '06:00:00',
 *   days: ['monday', 'tuesday']
 * });
 *
 * // Delete removes from UI instantly
 * deletePeriod.mutate('period-uuid');
 * ```
 */
export function useOptimisticQuietHoursPeriodMutations(
  options: UseOptimisticQuietHoursPeriodMutationsOptions = {}
): UseOptimisticQuietHoursPeriodMutationsReturn {
  const { onCreateSuccess, onCreateError, onDeleteSuccess, onDeleteError } = options;
  const queryClient = useQueryClient();
  const listKey = queryKeys.notifications.preferences.quietHours.list();

  const createPeriod = useMutation({
    mutationFn: createQuietHoursPeriod,

    onMutate: async (newPeriod: QuietHoursPeriodCreate) => {
      await cancelOutgoingQueries(queryClient, listKey);

      const previousData = queryClient.getQueryData<{
        items: QuietHoursPeriodResponse[];
      }>(listKey);

      // Create optimistic period with temporary ID
      const optimisticPeriod: QuietHoursPeriodResponse = {
        id: `temp-${Date.now()}`,
        label: newPeriod.label,
        start_time: newPeriod.start_time,
        end_time: newPeriod.end_time,
        days: newPeriod.days ?? [],
      };

      queryClient.setQueryData<{ items: QuietHoursPeriodResponse[]; pagination: { total: number; limit: number; offset: number } }>(listKey, (old) => ({
        items: [...(old?.items ?? []), optimisticPeriod],
        pagination: { total: (old?.items?.length ?? 0) + 1, limit: 100, offset: 0 },
      }));

      return { previousData, optimisticId: optimisticPeriod.id };
    },

    onError: (
      error,
      _variables,
      context?: OptimisticContext<{ items: QuietHoursPeriodResponse[] }>
    ) => {
      if (context?.previousData) {
        queryClient.setQueryData(listKey, context.previousData);
      }
      onCreateError?.(error);
    },

    onSuccess: (data, _variables, context) => {
      // Replace optimistic item with real one
      queryClient.setQueryData<{ items: QuietHoursPeriodResponse[]; pagination?: { total: number; limit: number; offset: number } }>(listKey, (old) => ({
        items: (old?.items ?? []).map((item) =>
          item.id === context?.optimisticId ? data : item
        ),
        pagination: old?.pagination ?? { total: 1, limit: 100, offset: 0 },
      }));
      onCreateSuccess?.(data);
    },

    onSettled: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.notifications.preferences.quietHours.all,
      });
    },
  });

  const deletePeriod = useMutation({
    mutationFn: deleteQuietHoursPeriod,

    onMutate: async (periodId: string) => {
      await cancelOutgoingQueries(queryClient, listKey);

      const previousData = queryClient.getQueryData<{
        items: QuietHoursPeriodResponse[];
      }>(listKey);

      // Optimistically remove the period
      queryClient.setQueryData<{ items: QuietHoursPeriodResponse[] }>(listKey, (old) => ({
        items: (old?.items ?? []).filter((item) => item.id !== periodId),
        pagination: {
          total: Math.max(0, (old?.items?.length ?? 0) - 1),
          limit: 100,
          offset: 0,
        },
      }));

      return { previousData };
    },

    onError: (
      error,
      _variables,
      context?: OptimisticContext<{ items: QuietHoursPeriodResponse[] }>
    ) => {
      if (context?.previousData) {
        queryClient.setQueryData(listKey, context.previousData);
      }
      onDeleteError?.(error);
    },

    onSuccess: () => {
      onDeleteSuccess?.();
    },

    onSettled: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.notifications.preferences.quietHours.all,
      });
    },
  });

  return {
    createPeriod,
    deletePeriod,
  };
}

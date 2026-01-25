/**
 * useSystemSetting - TanStack Query hook for system settings (NEM-3638)
 *
 * This hook provides access to individual system settings stored as key-value
 * pairs in the backend. It supports fetching, updating, and deleting settings.
 *
 * @module hooks/useSystemSetting
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import { DEFAULT_STALE_TIME } from '../services/queryClient';
import {
  fetchSystemSetting,
  fetchSystemSettings,
  updateSystemSetting,
  deleteSystemSetting,
  type SystemSettingResponse,
  type SystemSettingListResponse,
} from '../services/systemSettingsApi';

/**
 * Query key factory for system settings.
 */
export const systemSettingQueryKeys = {
  all: ['system-settings'] as const,
  list: () => [...systemSettingQueryKeys.all, 'list'] as const,
  detail: (key: string) => [...systemSettingQueryKeys.all, 'detail', key] as const,
};

/**
 * Options for useSystemSetting hook.
 */
export interface UseSystemSettingOptions {
  /**
   * The setting key to fetch.
   */
  key: string;

  /**
   * Whether to enable the query.
   * When false, the query will not execute.
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
 * Return type for useSystemSetting hook.
 */
export interface UseSystemSettingReturn {
  /** The setting value, undefined if not yet fetched or not found */
  setting: SystemSettingResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether any fetch is in progress (including background refetch) */
  isFetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the query has errored */
  isError: boolean;
  /** Whether the setting was not found (404) */
  isNotFound: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Mutation to update the setting */
  updateSetting: ReturnType<typeof useMutation<SystemSettingResponse, Error, Record<string, unknown>>>;
  /** Mutation to delete the setting */
  deleteSetting: ReturnType<typeof useMutation<void, Error, void>>;
}

/**
 * Hook to fetch and manage a specific system setting.
 *
 * @param options - Configuration options including the setting key
 * @returns Setting data, query state, and mutations
 *
 * @example
 * ```tsx
 * // Basic usage
 * const { setting, isLoading, updateSetting } = useSystemSetting({
 *   key: 'default_gpu_strategy',
 * });
 *
 * if (isLoading) return <Spinner />;
 * if (!setting) return <div>Setting not found</div>;
 *
 * return (
 *   <div>
 *     <pre>{JSON.stringify(setting.value, null, 2)}</pre>
 *     <button onClick={() => updateSetting.mutate({ strategy: 'balanced' })}>
 *       Update
 *     </button>
 *   </div>
 * );
 * ```
 */
export function useSystemSetting(options: UseSystemSettingOptions): UseSystemSettingReturn {
  const { key, enabled = true, staleTime = DEFAULT_STALE_TIME } = options;
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: systemSettingQueryKeys.detail(key),
    queryFn: () => fetchSystemSetting(key),
    enabled: enabled && key.length > 0,
    staleTime,
    retry: (failureCount, error) => {
      // Don't retry on 404
      if (error instanceof Error && error.message.includes('404')) {
        return false;
      }
      return failureCount < 2;
    },
  });

  const updateMutation = useMutation({
    mutationFn: (value: Record<string, unknown>) => updateSystemSetting(key, value),
    onSuccess: (data) => {
      // Update the cache with the new value
      queryClient.setQueryData(systemSettingQueryKeys.detail(key), data);
      // Invalidate the list query
      void queryClient.invalidateQueries({ queryKey: systemSettingQueryKeys.list() });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteSystemSetting(key),
    onSuccess: () => {
      // Remove from cache
      queryClient.removeQueries({ queryKey: systemSettingQueryKeys.detail(key) });
      // Invalidate the list query
      void queryClient.invalidateQueries({ queryKey: systemSettingQueryKeys.list() });
    },
  });

  // Determine if the error is a 404
  const isNotFound = query.isError && query.error?.message?.includes('404');

  return {
    setting: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    isError: query.isError,
    isNotFound,
    refetch: query.refetch,
    updateSetting: updateMutation,
    deleteSetting: deleteMutation,
  };
}

/**
 * Options for useSystemSettings hook.
 */
export interface UseSystemSettingsOptions {
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
 * Return type for useSystemSettings hook.
 */
export interface UseSystemSettingsReturn {
  /** List of all settings */
  settings: SystemSettingResponse[];
  /** Total number of settings */
  total: number;
  /** Full response data */
  data: SystemSettingListResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether any fetch is in progress */
  isFetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch all system settings.
 *
 * @param options - Configuration options
 * @returns List of all settings and query state
 *
 * @example
 * ```tsx
 * const { settings, isLoading } = useSystemSettings();
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <ul>
 *     {settings.map(s => (
 *       <li key={s.key}>{s.key}: {JSON.stringify(s.value)}</li>
 *     ))}
 *   </ul>
 * );
 * ```
 */
export function useSystemSettings(
  options: UseSystemSettingsOptions = {}
): UseSystemSettingsReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: systemSettingQueryKeys.list(),
    queryFn: fetchSystemSettings,
    enabled,
    staleTime,
    retry: 2,
  });

  return {
    settings: query.data?.items ?? [],
    total: query.data?.total ?? 0,
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    refetch: query.refetch,
  };
}

export default useSystemSetting;

/**
 * useSystemConfigQuery - TanStack Query hook for system configuration
 *
 * This hook fetches system configuration including the debug flag
 * for controlling access to developer tools.
 *
 * @module hooks/useSystemConfigQuery
 */

import { useQuery } from '@tanstack/react-query';

import { fetchConfig, type SystemConfig } from '../services/api';
import { queryKeys, STATIC_STALE_TIME } from '../services/queryClient';

/**
 * Options for configuring the useSystemConfigQuery hook
 */
export interface UseSystemConfigQueryOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default STATIC_STALE_TIME (5 minutes)
   */
  staleTime?: number;
}

/**
 * Return type for the useSystemConfigQuery hook
 */
export interface UseSystemConfigQueryReturn {
  /** Current system configuration, undefined if not yet fetched */
  data: SystemConfig | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether debug mode is enabled (defaults to false if data not loaded) */
  debugEnabled: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch system configuration using TanStack Query.
 *
 * This hook fetches from GET /api/system/config and provides:
 * - Automatic caching with long stale time (config rarely changes)
 * - Derived `debugEnabled` flag for easy access control
 * - Request deduplication across components
 *
 * @param options - Configuration options
 * @returns System config data and query state
 *
 * @example
 * ```tsx
 * // Check if debug mode is enabled
 * const { debugEnabled, isLoading } = useSystemConfigQuery();
 *
 * if (isLoading) return <Spinner />;
 * if (!debugEnabled) return <Navigate to="/" />;
 *
 * return <DeveloperToolsPage />;
 * ```
 */
export function useSystemConfigQuery(
  options: UseSystemConfigQueryOptions = {}
): UseSystemConfigQueryReturn {
  const { enabled = true, staleTime = STATIC_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.system.config,
    queryFn: fetchConfig,
    enabled,
    staleTime,
    // Config is static, so we can retry a few times
    retry: 2,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    // Safe default to false when data is not loaded
    debugEnabled: query.data?.debug ?? false,
    refetch: query.refetch,
  };
}

/**
 * useLogLevelQuery - TanStack Query hook for fetching current log level
 *
 * This hook fetches the current log level from GET /api/debug/log-level
 * for display in the Log Level Adjuster panel.
 *
 * Features:
 * - Automatic request deduplication across components
 * - Built-in caching with realtime stale time
 * - Derived currentLevel for easy access
 *
 * @module hooks/useLogLevelQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchLogLevel, type LogLevelResponse } from '../services/api';
import { queryKeys, REALTIME_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the useLogLevelQuery hook
 */
export interface UseLogLevelQueryOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default REALTIME_STALE_TIME (5 seconds)
   */
  staleTime?: number;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default false
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useLogLevelQuery hook
 */
export interface UseLogLevelQueryReturn {
  /** Raw log level response, undefined if not yet fetched */
  data: LogLevelResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Current log level string, null if not yet loaded */
  currentLevel: string | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch current log level using TanStack Query.
 *
 * This hook fetches from GET /api/debug/log-level and provides:
 * - Raw response data
 * - Derived currentLevel for easy access
 * - Automatic caching with realtime stale time
 *
 * @param options - Configuration options
 * @returns Log level data and query state
 *
 * @example
 * ```tsx
 * const { currentLevel, isLoading, error } = useLogLevelQuery();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return <span>Current level: {currentLevel}</span>;
 * ```
 */
export function useLogLevelQuery(options: UseLogLevelQueryOptions = {}): UseLogLevelQueryReturn {
  const { enabled = true, staleTime = REALTIME_STALE_TIME, refetchInterval = false } = options;

  const query = useQuery({
    queryKey: queryKeys.debug.logLevel,
    queryFn: fetchLogLevel,
    enabled,
    staleTime,
    refetchInterval,
    // Fast retry for log level checks
    retry: 1,
  });

  // Derive current level from data
  const currentLevel = useMemo(() => query.data?.level ?? null, [query.data?.level]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    currentLevel,
    refetch: query.refetch,
  };
}

export default useLogLevelQuery;

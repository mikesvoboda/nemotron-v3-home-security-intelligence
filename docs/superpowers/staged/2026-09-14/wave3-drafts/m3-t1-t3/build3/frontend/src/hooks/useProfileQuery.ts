/**
 * useProfileQuery - React Query hook for fetching profile status
 *
 * This hook provides query functionality for fetching the current profiling status
 * from GET /api/debug/profile.
 *
 * Features:
 * - Automatic caching with configurable stale time
 * - Optional polling during profiling via refetchInterval
 * - Derived state for isProfiling, elapsedSeconds, and results
 *
 * @module hooks/useProfileQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchProfileStatus,
  type ProfileStatusResponse,
  type ProfileResults,
} from '../services/api';
import { queryKeys, REALTIME_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the useProfileQuery hook
 */
export interface UseProfileQueryOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds.
   * Set to a value like 1000 for polling during profiling.
   * Set to false to disable automatic refetching.
   * @default false
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * @default REALTIME_STALE_TIME (5 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useProfileQuery hook
 */
export interface UseProfileQueryReturn {
  /** Raw profile status data */
  data: ProfileStatusResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Whether profiling is currently active */
  isProfiling: boolean;
  /** Elapsed time in seconds (null if not profiling) */
  elapsedSeconds: number | null;
  /** Profiling results (null if no results available) */
  results: ProfileResults | null;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch profiling status using TanStack Query.
 *
 * This hook fetches from GET /api/debug/profile and provides:
 * - Current profiling status (idle, profiling, completed)
 * - Elapsed time during profiling
 * - Results after profiling is stopped
 *
 * @param options - Configuration options
 * @returns Profile status data and query state
 *
 * @example
 * ```tsx
 * const { isProfiling, elapsedSeconds, results, isLoading } = useProfileQuery({
 *   refetchInterval: isProfiling ? 1000 : false, // Poll while profiling
 * });
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <div>
 *     <p>Status: {isProfiling ? `Profiling (${elapsedSeconds}s)` : 'Idle'}</p>
 *     {results && <ResultsTable data={results.top_functions} />}
 *   </div>
 * );
 * ```
 */
export function useProfileQuery(options: UseProfileQueryOptions = {}): UseProfileQueryReturn {
  const { enabled = true, refetchInterval = false, staleTime = REALTIME_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.debug.profile,
    queryFn: fetchProfileStatus,
    enabled,
    refetchInterval,
    staleTime,
    retry: 2,
  });

  // Derive isProfiling from the data
  const isProfiling = useMemo(() => query.data?.is_profiling ?? false, [query.data?.is_profiling]);

  // Derive elapsedSeconds from the data
  const elapsedSeconds = useMemo(
    () => query.data?.elapsed_seconds ?? null,
    [query.data?.elapsed_seconds]
  );

  // Derive results from the data
  const results = useMemo(() => query.data?.results ?? null, [query.data?.results]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    isProfiling,
    elapsedSeconds,
    results,
    error: query.error,
    refetch: query.refetch,
  };
}

export default useProfileQuery;

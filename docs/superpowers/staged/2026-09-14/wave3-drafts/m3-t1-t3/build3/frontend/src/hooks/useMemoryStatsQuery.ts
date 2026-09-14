/**
 * useMemoryStatsQuery - TanStack Query hook for memory statistics
 *
 * Provides memory stats data with mutations for GC and tracemalloc control.
 *
 * Debug endpoints (only available when backend debug=True):
 * - GET /api/debug/memory - Memory statistics
 * - POST /api/debug/memory/gc - Trigger garbage collection
 * - POST /api/debug/memory/tracemalloc/start - Start tracemalloc
 * - POST /api/debug/memory/tracemalloc/stop - Stop tracemalloc
 *
 * @module hooks/useMemoryStatsQuery
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';

import {
  fetchMemoryStats,
  triggerGc,
  startTracemalloc,
  stopTracemalloc,
  type MemoryStatsResponse,
  type TriggerGcResponse,
  type StartTracemallocResponse,
  type StopTracemallocResponse,
} from '../services/api';
import { REALTIME_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key for memory stats
 */
export const MEMORY_STATS_QUERY_KEY = ['debug', 'memory-stats'] as const;

// ============================================================================
// Options Interface
// ============================================================================

/**
 * Options for useMemoryStatsQuery hook
 */
export interface UseMemoryStatsQueryOptions {
  /**
   * Whether to enable the query (should be tied to debug mode)
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds
   * @default REALTIME_STALE_TIME (5 seconds)
   */
  staleTime?: number;

  /**
   * Number of top objects to return
   * @default 20
   */
  topN?: number;
}

// ============================================================================
// Return Type
// ============================================================================

/**
 * Return type for useMemoryStatsQuery hook
 */
export interface UseMemoryStatsQueryReturn {
  /** Memory stats data */
  data: MemoryStatsResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Trigger garbage collection */
  triggerGc: () => Promise<TriggerGcResponse>;
  /** Start tracemalloc tracing */
  startTracemalloc: (nframes?: number) => Promise<StartTracemallocResponse>;
  /** Stop tracemalloc tracing */
  stopTracemalloc: () => Promise<StopTracemallocResponse>;
  /** Whether GC trigger is pending */
  isGcPending: boolean;
  /** Whether start tracemalloc is pending */
  isTracemallocStartPending: boolean;
  /** Whether stop tracemalloc is pending */
  isTracemallocStopPending: boolean;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch memory statistics from the debug API.
 *
 * Provides memory usage data with controls for GC and tracemalloc.
 *
 * @param options - Query options
 * @returns Memory stats data and mutation functions
 *
 * @example
 * ```tsx
 * function MemoryPanel() {
 *   const {
 *     data,
 *     isLoading,
 *     triggerGc,
 *     isGcPending,
 *   } = useMemoryStatsQuery();
 *
 *   if (isLoading) return <Loading />;
 *
 *   return (
 *     <div>
 *       <p>RSS: {data?.process_rss_human}</p>
 *       <button onClick={triggerGc} disabled={isGcPending}>
 *         Force GC
 *       </button>
 *     </div>
 *   );
 * }
 * ```
 */
export function useMemoryStatsQuery(
  options: UseMemoryStatsQueryOptions = {}
): UseMemoryStatsQueryReturn {
  const { enabled = true, staleTime = REALTIME_STALE_TIME, topN = 20 } = options;
  const queryClient = useQueryClient();

  // Query for memory stats
  const query = useQuery<MemoryStatsResponse>({
    queryKey: [...MEMORY_STATS_QUERY_KEY, topN],
    queryFn: () => fetchMemoryStats({ topN }),
    enabled,
    staleTime,
    retry: 1,
  });

  // GC mutation
  const gcMutation = useMutation<TriggerGcResponse>({
    mutationFn: () => triggerGc(),
    onSuccess: () => {
      // Refetch memory stats after GC
      void queryClient.invalidateQueries({ queryKey: MEMORY_STATS_QUERY_KEY });
    },
  });

  // Start tracemalloc mutation
  const startTracemallocMutation = useMutation<StartTracemallocResponse, Error, number | undefined>(
    {
      mutationFn: (nframes) => startTracemalloc(nframes),
      onSuccess: () => {
        // Refetch memory stats after starting tracemalloc
        void queryClient.invalidateQueries({ queryKey: MEMORY_STATS_QUERY_KEY });
      },
    }
  );

  // Stop tracemalloc mutation
  const stopTracemallocMutation = useMutation<StopTracemallocResponse>({
    mutationFn: () => stopTracemalloc(),
    onSuccess: () => {
      // Refetch memory stats after stopping tracemalloc
      void queryClient.invalidateQueries({ queryKey: MEMORY_STATS_QUERY_KEY });
    },
  });

  // Wrapped mutation functions
  const triggerGcFn = useCallback(async () => {
    return gcMutation.mutateAsync();
  }, [gcMutation]);

  const startTracemallocFn = useCallback(
    async (nframes?: number) => {
      return startTracemallocMutation.mutateAsync(nframes);
    },
    [startTracemallocMutation]
  );

  const stopTracemallocFn = useCallback(async () => {
    return stopTracemallocMutation.mutateAsync();
  }, [stopTracemallocMutation]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
    triggerGc: triggerGcFn,
    startTracemalloc: startTracemallocFn,
    stopTracemalloc: stopTracemallocFn,
    isGcPending: gcMutation.isPending,
    isTracemallocStartPending: startTracemallocMutation.isPending,
    isTracemallocStopPending: stopTracemallocMutation.isPending,
  };
}

export default useMemoryStatsQuery;

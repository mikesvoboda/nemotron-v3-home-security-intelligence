/**
 * useCircuitBreakerDebugQuery - TanStack Query hook for debug circuit breaker status
 *
 * Provides circuit breaker debug data with reset mutation.
 *
 * Debug endpoints (only available when backend debug=True):
 * - GET /api/debug/circuit-breakers - All circuit breaker states
 * - POST /api/system/circuit-breakers/{name}/reset - Reset a circuit breaker
 *
 * @module hooks/useCircuitBreakerDebugQuery
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';

import {
  fetchDebugCircuitBreakers,
  resetCircuitBreaker,
  type DebugCircuitBreakersResponse,
} from '../services/api';
import { REALTIME_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key for debug circuit breakers
 */
export const CIRCUIT_BREAKER_DEBUG_QUERY_KEY = ['debug', 'circuit-breakers'] as const;

// ============================================================================
// Options Interface
// ============================================================================

/**
 * Options for useCircuitBreakerDebugQuery hook
 */
export interface UseCircuitBreakerDebugQueryOptions {
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
   * Polling interval in milliseconds (false to disable)
   * @default 5000
   */
  refetchInterval?: number | false;
}

// ============================================================================
// Return Type
// ============================================================================

/**
 * Return type for useCircuitBreakerDebugQuery hook
 */
export interface UseCircuitBreakerDebugQueryReturn {
  /** Circuit breakers data */
  data: DebugCircuitBreakersResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Reset a circuit breaker by name */
  resetBreaker: (name: string) => Promise<unknown>;
  /** Whether a reset is pending */
  isResetPending: boolean;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch circuit breaker debug information.
 *
 * Provides detailed circuit breaker states from the debug API with
 * a mutation to reset individual breakers.
 *
 * @param options - Query options
 * @returns Circuit breaker data and reset mutation
 *
 * @example
 * ```tsx
 * function CircuitBreakerPanel() {
 *   const {
 *     data,
 *     isLoading,
 *     resetBreaker,
 *     isResetPending,
 *   } = useCircuitBreakerDebugQuery();
 *
 *   if (isLoading) return <Loading />;
 *
 *   return (
 *     <div>
 *       {Object.values(data?.circuit_breakers ?? {}).map(breaker => (
 *         <div key={breaker.name}>
 *           {breaker.name}: {breaker.state}
 *           {breaker.state !== 'closed' && (
 *             <button onClick={() => resetBreaker(breaker.name)}>
 *               Reset
 *             </button>
 *           )}
 *         </div>
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
export function useCircuitBreakerDebugQuery(
  options: UseCircuitBreakerDebugQueryOptions = {}
): UseCircuitBreakerDebugQueryReturn {
  const { enabled = true, staleTime = REALTIME_STALE_TIME, refetchInterval = 5000 } = options;
  const queryClient = useQueryClient();

  // Query for circuit breaker states
  const query = useQuery<DebugCircuitBreakersResponse>({
    queryKey: CIRCUIT_BREAKER_DEBUG_QUERY_KEY,
    queryFn: () => fetchDebugCircuitBreakers(),
    enabled,
    staleTime,
    refetchInterval,
    retry: 1,
  });

  // Reset mutation
  const resetMutation = useMutation({
    mutationFn: (name: string) => resetCircuitBreaker(name),
    onSuccess: () => {
      // Refetch circuit breaker data after reset
      void queryClient.invalidateQueries({ queryKey: CIRCUIT_BREAKER_DEBUG_QUERY_KEY });
    },
  });

  // Wrapped reset function
  const resetBreakerFn = useCallback(
    async (name: string) => {
      return resetMutation.mutateAsync(name);
    },
    [resetMutation]
  );

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
    resetBreaker: resetBreakerFn,
    isResetPending: resetMutation.isPending,
  };
}

export default useCircuitBreakerDebugQuery;

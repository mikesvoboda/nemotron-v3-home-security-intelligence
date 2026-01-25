/**
 * useQueuesStatus Hook
 *
 * Fetches queue status from the backend API with automatic polling.
 * Provides detailed queue metrics including depth, workers, throughput,
 * and health status for all job queues.
 *
 * @see backend/api/routes/queues.py - GET /api/queues/status
 * @see backend/api/schemas/queue_status.py - Response schemas
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchQueuesStatus } from '../services/api';
import { computeDerivedQueueState } from '../types/queue';

import type {
  QueuesStatusResponse,
  QueueStatus,
  DerivedQueueState,
} from '../types/queue';

/**
 * Query key for queues status data.
 */
export const QUEUES_STATUS_QUERY_KEY = ['queues', 'status'] as const;

/**
 * Default refetch interval in milliseconds (5 seconds).
 */
const DEFAULT_REFETCH_INTERVAL = 5000;

/**
 * Options for the useQueuesStatus hook.
 */
export interface UseQueuesStatusOptions {
  /**
   * Whether to enable automatic refetching.
   * @default true
   */
  enabled?: boolean;
  /**
   * Refetch interval in milliseconds.
   * @default 5000
   */
  refetchInterval?: number;
}

/**
 * Return type for the useQueuesStatus hook.
 */
export interface UseQueuesStatusReturn {
  /** Raw queues status response from the API */
  data: QueuesStatusResponse | null;
  /** Whether the initial fetch is loading */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isFetching: boolean;
  /** Error if the fetch failed */
  error: Error | null;
  /** Derived state computed from the queue status */
  derivedState: DerivedQueueState;
  /** Queues with critical health status */
  criticalQueues: QueueStatus[];
  /** Maximum wait time across all queues in seconds */
  longestWaitTime: number;
  /** Manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch and monitor queue status with automatic polling.
 *
 * Provides real-time visibility into job queue health including:
 * - Queue depth and worker counts
 * - Throughput metrics (jobs/min, avg processing time)
 * - Oldest job wait time
 * - Health status (healthy/warning/critical)
 *
 * @param options - Configuration options
 * @returns Queue status data, loading state, and derived metrics
 *
 * @example
 * ```tsx
 * function QueueMonitor() {
 *   const {
 *     data,
 *     isLoading,
 *     derivedState,
 *     criticalQueues,
 *   } = useQueuesStatus({ refetchInterval: 5000 });
 *
 *   if (isLoading) return <Spinner />;
 *
 *   return (
 *     <div>
 *       <Badge color={derivedState.hasCritical ? 'red' : 'green'}>
 *         {data?.summary.overall_status}
 *       </Badge>
 *       {criticalQueues.map(queue => (
 *         <Alert key={queue.name}>
 *           {queue.name} is critical: {queue.depth} jobs waiting
 *         </Alert>
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
export function useQueuesStatus(
  options: UseQueuesStatusOptions = {}
): UseQueuesStatusReturn {
  const { enabled = true, refetchInterval = DEFAULT_REFETCH_INTERVAL } = options;

  const query = useQuery({
    queryKey: QUEUES_STATUS_QUERY_KEY,
    queryFn: fetchQueuesStatus,
    enabled,
    refetchInterval,
    // Keep showing stale data while refetching
    staleTime: refetchInterval / 2,
    // Don't retry too aggressively for status endpoints
    retry: 1,
  });

  // Compute derived state from the raw response
  const derivedState = useMemo(
    () => computeDerivedQueueState(query.data ?? null),
    [query.data]
  );

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    derivedState,
    criticalQueues: derivedState.criticalQueues,
    longestWaitTime: derivedState.longestWaitTime,
    refetch: query.refetch,
  };
}

export default useQueuesStatus;

/**
 * usePipelineStatus Hook
 *
 * Fetches pipeline status from the backend API with automatic polling.
 * Provides visibility into FileWatcher, BatchAggregator, and DegradationManager.
 *
 * @see backend/api/routes/system.py - GET /api/system/pipeline
 * @see backend/api/schemas/system.py - PipelineStatusResponse
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchPipelineStatus } from '../services/api';
import { computeBatchAggregatorState } from '../types/queue';

import type {
  PipelineStatusResponse,
  BatchAggregatorUIState,
} from '../types/queue';

/**
 * Query key for pipeline status data.
 */
export const PIPELINE_STATUS_QUERY_KEY = ['system', 'pipeline'] as const;

/**
 * Default refetch interval in milliseconds (5 seconds).
 */
const DEFAULT_REFETCH_INTERVAL = 5000;

/**
 * Options for the usePipelineStatus hook.
 */
export interface UsePipelineStatusOptions {
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
 * Return type for the usePipelineStatus hook.
 */
export interface UsePipelineStatusReturn {
  /** Raw pipeline status response from the API */
  data: PipelineStatusResponse | null;
  /** Whether the initial fetch is loading */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isFetching: boolean;
  /** Error if the fetch failed */
  error: Error | null;
  /** Derived batch aggregator state for UI display */
  batchAggregatorState: BatchAggregatorUIState;
  /** Whether the file watcher is running */
  fileWatcherRunning: boolean;
  /** Whether the system is in degraded mode */
  isDegraded: boolean;
  /** Manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch and monitor pipeline status with automatic polling.
 *
 * Provides real-time visibility into the AI processing pipeline:
 * - FileWatcher: Monitors camera directories for new uploads
 * - BatchAggregator: Groups detections into time-based batches
 * - DegradationManager: Handles graceful degradation
 *
 * @param options - Configuration options
 * @returns Pipeline status data, loading state, and derived metrics
 *
 * @example
 * ```tsx
 * function PipelineMonitor() {
 *   const {
 *     data,
 *     isLoading,
 *     batchAggregatorState,
 *     fileWatcherRunning,
 *     isDegraded,
 *   } = usePipelineStatus({ refetchInterval: 5000 });
 *
 *   if (isLoading) return <Spinner />;
 *
 *   return (
 *     <div>
 *       <Badge color={fileWatcherRunning ? 'green' : 'red'}>
 *         FileWatcher: {fileWatcherRunning ? 'Running' : 'Stopped'}
 *       </Badge>
 *       <Text>Active Batches: {batchAggregatorState.activeBatchCount}</Text>
 *       {batchAggregatorState.hasTimeoutWarning && (
 *         <Alert>Batches approaching timeout!</Alert>
 *       )}
 *     </div>
 *   );
 * }
 * ```
 */
export function usePipelineStatus(
  options: UsePipelineStatusOptions = {}
): UsePipelineStatusReturn {
  const { enabled = true, refetchInterval = DEFAULT_REFETCH_INTERVAL } = options;

  const query = useQuery({
    queryKey: PIPELINE_STATUS_QUERY_KEY,
    queryFn: fetchPipelineStatus,
    enabled,
    refetchInterval,
    // Keep showing stale data while refetching
    staleTime: refetchInterval / 2,
    // Don't retry too aggressively for status endpoints
    retry: 1,
  });

  // Compute derived batch aggregator state from the raw response
  const batchAggregatorState = useMemo(
    () => computeBatchAggregatorState(query.data?.batch_aggregator),
    [query.data?.batch_aggregator]
  );

  // Extract FileWatcher running state
  const fileWatcherRunning = query.data?.file_watcher?.running ?? false;

  // Extract degradation state
  const isDegraded = query.data?.degradation?.is_degraded ?? false;

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    batchAggregatorState,
    fileWatcherRunning,
    isDegraded,
    refetch: query.refetch,
  };
}

export default usePipelineStatus;

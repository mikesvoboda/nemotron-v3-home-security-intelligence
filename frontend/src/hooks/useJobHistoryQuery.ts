/**
 * useJobHistoryQuery - React Query hook for fetching job state transition history
 *
 * This hook provides the job history data including state transitions
 * for displaying in a timeline component.
 *
 * @module hooks/useJobHistoryQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchJobHistory,
  type JobHistoryResponse,
  type JobTransitionResponse,
} from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the useJobHistoryQuery hook
 */
export interface UseJobHistoryQueryOptions {
  /**
   * Whether to enable the query
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds
   * @default DEFAULT_STALE_TIME
   */
  staleTime?: number;

  /**
   * Refetch interval in milliseconds
   * @default false (no auto-refetch)
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useJobHistoryQuery hook
 */
export interface UseJobHistoryQueryReturn {
  /** Complete job history data */
  history: JobHistoryResponse | null;

  /** State transitions extracted from history */
  transitions: JobTransitionResponse[];

  /** Current job status */
  currentStatus: string | null;

  /** Whether the initial fetch is in progress */
  isLoading: boolean;

  /** Whether any fetch is in progress (including background refetch) */
  isFetching: boolean;

  /** Error object if the query failed */
  error: Error | null;

  /** Whether the query has errored */
  isError: boolean;

  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

// ============================================================================
// Query Key Factory
// ============================================================================

export const jobHistoryQueryKeys = {
  all: ['jobs', 'history'] as const,
  detail: (jobId: string) => [...jobHistoryQueryKeys.all, jobId] as const,
};

// ============================================================================
// Main Hook Implementation
// ============================================================================

/**
 * Hook to fetch job history including state transitions.
 *
 * @param jobId - The job ID to fetch history for
 * @param options - Configuration options
 * @returns Job history data and query state
 *
 * @example
 * ```tsx
 * const {
 *   history,
 *   transitions,
 *   currentStatus,
 *   isLoading,
 * } = useJobHistoryQuery('142');
 * ```
 */
export function useJobHistoryQuery(
  jobId: string,
  options: UseJobHistoryQueryOptions = {}
): UseJobHistoryQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME, refetchInterval = false } = options;

  const query = useQuery<JobHistoryResponse, Error>({
    queryKey: jobHistoryQueryKeys.detail(jobId),
    queryFn: () => fetchJobHistory(jobId),
    enabled: enabled && Boolean(jobId),
    staleTime,
    refetchInterval,
  });

  // Extract transitions from history data
  const transitions = useMemo((): JobTransitionResponse[] => {
    if (!query.data?.transitions) {
      return [];
    }
    return query.data.transitions;
  }, [query.data?.transitions]);

  // Get current status from history
  const currentStatus = useMemo((): string | null => {
    if (!query.data?.status) {
      return null;
    }
    return query.data.status;
  }, [query.data?.status]);

  return {
    history: query.data ?? null,
    transitions,
    currentStatus,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export default useJobHistoryQuery;

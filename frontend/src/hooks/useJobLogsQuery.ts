/**
 * React Query hook for fetching job logs.
 *
 * Provides job log data with automatic polling support for real-time updates.
 */

import { useQuery } from '@tanstack/react-query';

import { fetchJobLogs, type JobLogsQueryParams } from '../services/api';

import type { JobLogsResponse, JobLogEntryResponse } from '../types/generated';

/**
 * Query key factory for job logs queries.
 * Enables fine-grained cache invalidation.
 */
export const jobLogsQueryKeys = {
  all: ['jobLogs'] as const,
  byJob: (jobId: string) => [...jobLogsQueryKeys.all, jobId] as const,
  byJobWithParams: (jobId: string, params?: JobLogsQueryParams) =>
    [...jobLogsQueryKeys.byJob(jobId), params] as const,
};

/**
 * Options for useJobLogsQuery hook.
 */
export interface UseJobLogsQueryOptions extends JobLogsQueryParams {
  /** The job ID to fetch logs for. If undefined or empty, query is disabled. */
  jobId: string | undefined;
  /** Whether the query is enabled. Defaults to true when jobId is valid. */
  enabled?: boolean;
  /** Polling interval in milliseconds. If not provided, no polling occurs. */
  refetchInterval?: number;
  /** Number of retries on failure. Defaults to 1. */
  retry?: number;
}

/**
 * Return type for useJobLogsQuery hook.
 */
export interface UseJobLogsQueryReturn {
  /** Array of log entries */
  logs: JobLogEntryResponse[];
  /** Total number of log entries */
  totalCount: number;
  /** Whether more logs exist beyond the current limit */
  hasMore: boolean;
  /** Job ID from the response */
  jobId: string | undefined;
  /** Whether the query is currently loading */
  isLoading: boolean;
  /** Whether the query is fetching (initial or subsequent) */
  isFetching: boolean;
  /** Error if the query failed */
  error: Error | null;
  /** Whether the query errored */
  isError: boolean;
  /** Function to manually refetch the logs */
  refetch: () => void;
}

/**
 * Hook for fetching job logs with optional polling.
 *
 * @param options - Query options including jobId, filters, and polling interval
 * @returns Job logs data with query state
 *
 * @example
 * // Basic usage
 * const { logs, isLoading } = useJobLogsQuery({ jobId: 'job-123' });
 *
 * @example
 * // With polling for real-time updates
 * const { logs, isLoading } = useJobLogsQuery({
 *   jobId: 'job-123',
 *   refetchInterval: 2000, // Poll every 2 seconds
 * });
 *
 * @example
 * // With filters
 * const { logs } = useJobLogsQuery({
 *   jobId: 'job-123',
 *   level: 'ERROR',
 *   limit: 50,
 * });
 */
export function useJobLogsQuery(options: UseJobLogsQueryOptions): UseJobLogsQueryReturn {
  const {
    jobId,
    enabled = true,
    refetchInterval,
    retry = 1,
    limit,
    offset,
    level,
  } = options;

  // Build query params from options
  const queryParams: JobLogsQueryParams | undefined =
    limit !== undefined || offset !== undefined || level !== undefined
      ? { limit, offset, level }
      : undefined;

  // Query is only enabled when jobId is a non-empty string
  const isValidJobId = Boolean(jobId && jobId.trim());
  const queryEnabled = enabled && isValidJobId;

  const {
    data,
    isLoading,
    isFetching,
    error,
    isError,
    refetch,
  } = useQuery<JobLogsResponse, Error>({
    queryKey: jobLogsQueryKeys.byJobWithParams(jobId ?? '', queryParams),
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion -- queryEnabled ensures jobId is valid
    queryFn: () => fetchJobLogs(jobId!, queryParams),
    enabled: queryEnabled,
    refetchInterval: queryEnabled ? refetchInterval : undefined,
    retry,
  });

  return {
    logs: data?.logs ?? [],
    totalCount: data?.total ?? 0,
    hasMore: data?.has_more ?? false,
    jobId: data?.job_id,
    isLoading: queryEnabled ? isLoading : false,
    isFetching,
    error: error ?? null,
    isError,
    refetch: () => void refetch(),
  };
}

export default useJobLogsQuery;

/**
 * useExportJobs - React Query hooks for export job management
 *
 * Provides hooks for:
 * - Listing export jobs
 * - Starting new export jobs
 * - Cancelling export jobs
 * - Polling for job status updates
 *
 * @module hooks/useExportJobs
 * @see NEM-3177
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  listExportJobs,
  startExportJob,
  cancelExportJob,
  getExportStatus,
} from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

import type {
  ExportJob,
  ExportJobCreateParams,
  ExportJobListResponse,
  ExportJobStartResponse,
  ExportJobCancelResponse,
  ExportJobStatus,
  ExportPaginationMeta,
} from '../types/export';

// ============================================================================
// Query Key Factory
// ============================================================================

/**
 * Query key factory for export jobs.
 * Provides consistent, typed query keys for all export-related queries.
 */
export const exportJobsQueryKeys = {
  /** Base key for all export queries */
  all: ['exports'] as const,

  /** Key for listing export jobs */
  list: (filters?: { status?: ExportJobStatus }) =>
    filters ? ([...exportJobsQueryKeys.all, 'list', filters] as const) : ([...exportJobsQueryKeys.all, 'list'] as const),

  /** Key for individual export job detail */
  detail: (jobId: string) => [...exportJobsQueryKeys.all, 'detail', jobId] as const,
};

// ============================================================================
// Types
// ============================================================================

/**
 * Options for the useExportJobsQuery hook
 */
export interface UseExportJobsQueryOptions {
  /** Filter by job status */
  status?: ExportJobStatus;
  /** Number of items per page */
  limit?: number;
  /** Number of items to skip */
  offset?: number;
  /** Whether to enable the query */
  enabled?: boolean;
  /** Custom stale time */
  staleTime?: number;
  /** Refetch interval */
  refetchInterval?: number | false;
}

/**
 * Return type for useExportJobsQuery
 */
export interface UseExportJobsQueryReturn {
  /** List of export jobs */
  jobs: ExportJob[];
  /** Pagination metadata */
  pagination: ExportPaginationMeta | null;
  /** Whether the query is loading */
  isLoading: boolean;
  /** Whether the query is fetching (includes background refetches) */
  isFetching: boolean;
  /** Whether there was an error */
  isError: boolean;
  /** Error object if any */
  error: Error | null;
  /** Function to refetch the data */
  refetch: () => Promise<unknown>;
}

/**
 * Options for the useExportJobStatus hook
 */
export interface UseExportJobStatusOptions {
  /** Whether to enable the query */
  enabled?: boolean;
  /** Poll interval in milliseconds (set to false or 0 to disable) */
  pollInterval?: number | false;
}

/**
 * Return type for useExportJobStatus
 */
export interface UseExportJobStatusReturn {
  /** The export job data */
  job: ExportJob | null;
  /** Whether the query is loading */
  isLoading: boolean;
  /** Whether the query is fetching */
  isFetching: boolean;
  /** Whether there was an error */
  isError: boolean;
  /** Error object if any */
  error: Error | null;
  /** Whether the job is complete (completed or failed) */
  isComplete: boolean;
  /** Whether the job is running */
  isRunning: boolean;
  /** Function to refetch the data */
  refetch: () => Promise<unknown>;
}

/**
 * Return type for useStartExportJob
 */
export interface UseStartExportJobReturn {
  /** Function to start an export job */
  startExport: (params: ExportJobCreateParams) => Promise<ExportJobStartResponse>;
  /** The response data from the last mutation */
  data: ExportJobStartResponse | undefined;
  /** Whether the mutation is pending */
  isPending: boolean;
  /** Whether the mutation succeeded */
  isSuccess: boolean;
  /** Whether the mutation failed */
  isError: boolean;
  /** Error object if any */
  error: Error | null;
  /** Reset the mutation state */
  reset: () => void;
}

/**
 * Return type for useCancelExportJob
 */
export interface UseCancelExportJobReturn {
  /** Function to cancel an export job */
  cancelJob: (jobId: string) => Promise<ExportJobCancelResponse>;
  /** Whether the mutation is pending */
  isPending: boolean;
  /** Whether the mutation succeeded */
  isSuccess: boolean;
  /** Whether the mutation failed */
  isError: boolean;
  /** Error object if any */
  error: Error | null;
  /** Reset the mutation state */
  reset: () => void;
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook to fetch a list of export jobs with optional filtering.
 *
 * @param options - Query options including status filter and pagination
 * @returns Export jobs list and query state
 *
 * @example
 * ```tsx
 * const { jobs, isLoading, pagination } = useExportJobsQuery({ status: 'pending' });
 * ```
 */
export function useExportJobsQuery(options: UseExportJobsQueryOptions = {}): UseExportJobsQueryReturn {
  const {
    status,
    limit = 50,
    offset = 0,
    enabled = true,
    staleTime = DEFAULT_STALE_TIME,
    refetchInterval = false,
  } = options;

  const query = useQuery<ExportJobListResponse, Error>({
    queryKey: exportJobsQueryKeys.list(status ? { status } : undefined),
    queryFn: () => listExportJobs(status, limit, offset),
    enabled,
    staleTime,
    refetchInterval,
  });

  return {
    jobs: query.data?.items ?? [],
    pagination: query.data?.pagination ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Hook to fetch and poll status for a specific export job.
 *
 * @param jobId - The export job ID to fetch
 * @param options - Query options including poll interval
 * @returns Export job data and query state
 *
 * @example
 * ```tsx
 * const { job, isComplete, isRunning } = useExportJobStatus('job-123', { pollInterval: 2000 });
 * ```
 */
export function useExportJobStatus(
  jobId: string,
  options: UseExportJobStatusOptions = {}
): UseExportJobStatusReturn {
  const { enabled = true, pollInterval = false } = options;

  const query = useQuery<ExportJob, Error>({
    queryKey: exportJobsQueryKeys.detail(jobId),
    queryFn: () => getExportStatus(jobId),
    enabled: enabled && Boolean(jobId),
    staleTime: 1000, // Short stale time for status polling
    refetchInterval: (query) => {
      // Stop polling if job is complete or failed
      const data = query.state.data;
      if (data?.status === 'completed' || data?.status === 'failed') {
        return false;
      }
      return pollInterval;
    },
  });

  const isComplete = useMemo(
    () => query.data?.status === 'completed' || query.data?.status === 'failed',
    [query.data?.status]
  );

  const isRunning = useMemo(
    () => query.data?.status === 'running' || query.data?.status === 'pending',
    [query.data?.status]
  );

  return {
    job: query.data ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isError: query.isError,
    error: query.error,
    isComplete,
    isRunning,
    refetch: query.refetch,
  };
}

/**
 * Hook to start a new export job.
 *
 * @returns Mutation functions and state for starting exports
 *
 * @example
 * ```tsx
 * const { startExport, isPending } = useStartExportJob();
 * await startExport({ export_type: 'events', export_format: 'csv' });
 * ```
 */
export function useStartExportJob(): UseStartExportJobReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation<ExportJobStartResponse, Error, ExportJobCreateParams>({
    mutationFn: (params) => startExportJob(params),
    onSuccess: () => {
      // Invalidate the jobs list to refresh it
      void queryClient.invalidateQueries({ queryKey: exportJobsQueryKeys.all });
    },
  });

  return {
    startExport: mutation.mutateAsync,
    data: mutation.data,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    reset: mutation.reset,
  };
}

/**
 * Hook to cancel an export job.
 *
 * @returns Mutation functions and state for cancelling exports
 *
 * @example
 * ```tsx
 * const { cancelJob, isPending } = useCancelExportJob();
 * await cancelJob('job-123');
 * ```
 */
export function useCancelExportJob(): UseCancelExportJobReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation<ExportJobCancelResponse, Error, string>({
    mutationFn: (jobId) => cancelExportJob(jobId),
    onSuccess: (_data, jobId) => {
      // Invalidate the specific job and the list
      void queryClient.invalidateQueries({ queryKey: exportJobsQueryKeys.detail(jobId) });
      void queryClient.invalidateQueries({ queryKey: exportJobsQueryKeys.list() });
    },
  });

  return {
    cancelJob: mutation.mutateAsync,
    isPending: mutation.isPending,
    isSuccess: mutation.isSuccess,
    isError: mutation.isError,
    error: mutation.error,
    reset: mutation.reset,
  };
}

export default useExportJobsQuery;

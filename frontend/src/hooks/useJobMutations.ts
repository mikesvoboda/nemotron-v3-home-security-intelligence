/**
 * Hook for job lifecycle mutations (NEM-2712).
 *
 * Provides mutations for managing background job lifecycle:
 * - Cancel: Graceful cancellation of pending/running jobs
 * - Abort: Force stop of running jobs (may cause inconsistency)
 * - Retry: Create new job from failed/cancelled job
 * - Delete: Remove job record permanently
 *
 * @example
 * ```tsx
 * const { cancelJob, isCancelling } = useJobMutations({
 *   onCancelSuccess: (response) => toast.success('Job cancelled'),
 * });
 *
 * await cancelJob('job-123');
 * ```
 */
import { useMutation, useQueryClient } from '@tanstack/react-query';

import { cancelJob, abortJob, retryJob, deleteJob } from '../services/api';
import { queryKeys } from '../services/queryClient';

import type {
  JobCancelResponse,
  JobAbortResponse,
  JobResponse,
} from '../services/api';

/**
 * Options for useJobMutations hook.
 */
export interface UseJobMutationsOptions {
  /** Callback when cancel succeeds */
  onCancelSuccess?: (response: JobCancelResponse, jobId: string) => void;
  /** Callback when cancel fails */
  onCancelError?: (error: Error, jobId: string) => void;
  /** Callback when abort succeeds */
  onAbortSuccess?: (response: JobAbortResponse, jobId: string) => void;
  /** Callback when abort fails */
  onAbortError?: (error: Error, jobId: string) => void;
  /** Callback when retry succeeds (returns new job) */
  onRetrySuccess?: (response: JobResponse, jobId: string) => void;
  /** Callback when retry fails */
  onRetryError?: (error: Error, jobId: string) => void;
  /** Callback when delete succeeds */
  onDeleteSuccess?: (response: JobCancelResponse, jobId: string) => void;
  /** Callback when delete fails */
  onDeleteError?: (error: Error, jobId: string) => void;
  /** Whether to invalidate queries on success (default: true) */
  invalidateQueries?: boolean;
}

/**
 * Return type for useJobMutations hook.
 */
export interface UseJobMutationsReturn {
  /** Cancel a job (graceful stop) */
  cancelJob: (jobId: string) => Promise<JobCancelResponse>;
  /** Abort a job (force stop) */
  abortJob: (jobId: string) => Promise<JobAbortResponse>;
  /** Retry a failed/cancelled job */
  retryJob: (jobId: string) => Promise<JobResponse>;
  /** Delete a job record */
  deleteJob: (jobId: string) => Promise<JobCancelResponse>;
  /** Whether a cancel operation is in progress */
  isCancelling: boolean;
  /** Whether an abort operation is in progress */
  isAborting: boolean;
  /** Whether a retry operation is in progress */
  isRetrying: boolean;
  /** Whether a delete operation is in progress */
  isDeleting: boolean;
  /** Whether any mutation is in progress */
  isMutating: boolean;
  /** Error from the last operation */
  error: Error | null;
  /** Reset the error state */
  reset: () => void;
}

/**
 * Hook for managing job lifecycle mutations.
 *
 * @param options - Configuration options for callbacks and query invalidation
 * @returns Object with mutation functions and state
 */
export function useJobMutations(options: UseJobMutationsOptions = {}): UseJobMutationsReturn {
  const {
    onCancelSuccess,
    onCancelError,
    onAbortSuccess,
    onAbortError,
    onRetrySuccess,
    onRetryError,
    onDeleteSuccess,
    onDeleteError,
    invalidateQueries = true,
  } = options;

  const queryClient = useQueryClient();

  // Cancel mutation
  const cancelMutation = useMutation({
    mutationFn: (jobId: string) => cancelJob(jobId),
    onSuccess: (data, jobId) => {
      if (invalidateQueries) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
      }
      onCancelSuccess?.(data, jobId);
    },
    onError: (error: unknown, jobId) => {
      onCancelError?.(error instanceof Error ? error : new Error(String(error)), jobId);
    },
  });

  // Abort mutation
  const abortMutation = useMutation({
    mutationFn: (jobId: string) => abortJob(jobId),
    onSuccess: (data, jobId) => {
      if (invalidateQueries) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
      }
      onAbortSuccess?.(data, jobId);
    },
    onError: (error: unknown, jobId) => {
      onAbortError?.(error instanceof Error ? error : new Error(String(error)), jobId);
    },
  });

  // Retry mutation
  const retryMutation = useMutation({
    mutationFn: (jobId: string) => retryJob(jobId),
    onSuccess: (data, jobId) => {
      if (invalidateQueries) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
      }
      onRetrySuccess?.(data, jobId);
    },
    onError: (error: unknown, jobId) => {
      onRetryError?.(error instanceof Error ? error : new Error(String(error)), jobId);
    },
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => deleteJob(jobId),
    onSuccess: (data, jobId) => {
      if (invalidateQueries) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
      }
      onDeleteSuccess?.(data, jobId);
    },
    onError: (error: unknown, jobId) => {
      onDeleteError?.(error instanceof Error ? error : new Error(String(error)), jobId);
    },
  });

  // Compute combined error state
  const error = (cancelMutation.error ??
    abortMutation.error ??
    retryMutation.error ??
    deleteMutation.error) as Error | null;

  // Compute combined pending states
  const isCancelling = cancelMutation.isPending;
  const isAborting = abortMutation.isPending;
  const isRetrying = retryMutation.isPending;
  const isDeleting = deleteMutation.isPending;
  const isMutating = isCancelling || isAborting || isRetrying || isDeleting;

  // Reset all mutations
  const reset = () => {
    cancelMutation.reset();
    abortMutation.reset();
    retryMutation.reset();
    deleteMutation.reset();
  };

  return {
    cancelJob: (jobId: string) => cancelMutation.mutateAsync(jobId),
    abortJob: (jobId: string) => abortMutation.mutateAsync(jobId),
    retryJob: (jobId: string) => retryMutation.mutateAsync(jobId),
    deleteJob: (jobId: string) => deleteMutation.mutateAsync(jobId),
    isCancelling,
    isAborting,
    isRetrying,
    isDeleting,
    isMutating,
    error,
    reset,
  };
}

export default useJobMutations;

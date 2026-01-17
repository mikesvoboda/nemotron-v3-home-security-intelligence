/**
 * useProfilingMutations - React Query mutations for profiling operations
 *
 * This module provides mutation hooks for:
 * - Starting profiling (POST /api/debug/profile/start)
 * - Stopping profiling (POST /api/debug/profile/stop)
 * - Downloading profile data (GET /api/debug/profile/download)
 *
 * @module hooks/useProfilingMutations
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';

import {
  startProfiling,
  stopProfiling,
  downloadProfile,
  type StartProfilingResponse,
  type StopProfilingResponse,
} from '../services/api';
import { queryKeys } from '../services/queryClient';

// ============================================================================
// useStartProfilingMutation
// ============================================================================

/**
 * Return type for the useStartProfilingMutation hook
 */
export interface UseStartProfilingMutationReturn {
  /** Function to start profiling */
  start: () => Promise<StartProfilingResponse>;
  /** Whether the start operation is in progress */
  isPending: boolean;
  /** Error from the start operation */
  error: Error | null;
  /** Reset the mutation state */
  reset: () => void;
}

/**
 * Hook for starting profiling.
 *
 * Calls POST /api/debug/profile/start and invalidates the profile query
 * on success to update the status.
 *
 * @returns Mutation for starting profiling
 *
 * @example
 * ```tsx
 * const { start, isPending, error } = useStartProfilingMutation();
 *
 * const handleStart = async () => {
 *   try {
 *     await start();
 *     console.log('Profiling started');
 *   } catch (err) {
 *     console.error('Failed to start:', err);
 *   }
 * };
 * ```
 */
export function useStartProfilingMutation(): UseStartProfilingMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: startProfiling,
    onSuccess: () => {
      // Invalidate profile query to update status
      void queryClient.invalidateQueries({ queryKey: queryKeys.debug.profile });
    },
  });

  return {
    start: () => mutation.mutateAsync(),
    isPending: mutation.isPending,
    error: mutation.error,
    reset: mutation.reset,
  };
}

// ============================================================================
// useStopProfilingMutation
// ============================================================================

/**
 * Return type for the useStopProfilingMutation hook
 */
export interface UseStopProfilingMutationReturn {
  /** Function to stop profiling */
  stop: () => Promise<StopProfilingResponse>;
  /** Results from the last stop operation */
  results: StopProfilingResponse | undefined;
  /** Whether the stop operation is in progress */
  isPending: boolean;
  /** Error from the stop operation */
  error: Error | null;
  /** Reset the mutation state */
  reset: () => void;
}

/**
 * Hook for stopping profiling and getting results.
 *
 * Calls POST /api/debug/profile/stop and invalidates the profile query
 * on success. Returns the profiling results with top functions by CPU time.
 *
 * @returns Mutation for stopping profiling
 *
 * @example
 * ```tsx
 * const { stop, results, isPending, error } = useStopProfilingMutation();
 *
 * const handleStop = async () => {
 *   try {
 *     const result = await stop();
 *     console.log('Top functions:', result.results.top_functions);
 *   } catch (err) {
 *     console.error('Failed to stop:', err);
 *   }
 * };
 * ```
 */
export function useStopProfilingMutation(): UseStopProfilingMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: stopProfiling,
    onSuccess: () => {
      // Invalidate profile query to update status
      void queryClient.invalidateQueries({ queryKey: queryKeys.debug.profile });
    },
  });

  return {
    stop: () => mutation.mutateAsync(),
    results: mutation.data,
    isPending: mutation.isPending,
    error: mutation.error,
    reset: mutation.reset,
  };
}

// ============================================================================
// useDownloadProfileMutation
// ============================================================================

/**
 * Return type for the useDownloadProfileMutation hook
 */
export interface UseDownloadProfileMutationReturn {
  /** Function to download the profile */
  download: () => Promise<Blob>;
  /** Whether the download is in progress */
  isPending: boolean;
  /** Error from the download operation */
  error: Error | null;
  /** Reset the mutation state */
  reset: () => void;
}

/**
 * Hook for downloading profile data as a .prof file.
 *
 * Calls GET /api/debug/profile/download and returns a Blob that can be
 * used to trigger a file download.
 *
 * @returns Mutation for downloading profile data
 *
 * @example
 * ```tsx
 * const { download, isPending, error } = useDownloadProfileMutation();
 *
 * const handleDownload = async () => {
 *   try {
 *     const blob = await download();
 *     const url = URL.createObjectURL(blob);
 *     const a = document.createElement('a');
 *     a.href = url;
 *     a.download = 'profile.prof';
 *     a.click();
 *     URL.revokeObjectURL(url);
 *   } catch (err) {
 *     console.error('Failed to download:', err);
 *   }
 * };
 * ```
 */
export function useDownloadProfileMutation(): UseDownloadProfileMutationReturn {
  const mutation = useMutation({
    mutationFn: downloadProfile,
  });

  return {
    download: () => mutation.mutateAsync(),
    isPending: mutation.isPending,
    error: mutation.error,
    reset: mutation.reset,
  };
}

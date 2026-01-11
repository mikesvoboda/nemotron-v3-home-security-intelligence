/**
 * useStorageStatsQuery - TanStack Query hooks for storage statistics
 *
 * This module provides hooks for fetching storage statistics using TanStack Query.
 * It replaces the manual polling implementation in useStorageStats with
 * automatic caching, deduplication, and background refetching.
 *
 * Includes:
 * - useStorageStatsQuery: Fetch storage statistics
 * - useCleanupPreviewMutation: Preview cleanup results (dry run)
 *
 * Benefits over the original useStorageStats:
 * - Automatic request deduplication across components
 * - Built-in caching with configurable stale time
 * - Mutation with cache invalidation for cleanup operations
 * - DevTools integration for debugging
 *
 * @module hooks/useStorageStatsQuery
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchStorageStats,
  previewCleanup,
  triggerCleanup,
  type StorageStatsResponse,
  type CleanupResponse,
} from '../services/api';
import { queryKeys, STATIC_STALE_TIME } from '../services/queryClient';

// ============================================================================
// useStorageStatsQuery
// ============================================================================

/**
 * Options for configuring the useStorageStatsQuery hook
 */
export interface UseStorageStatsQueryOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default 60000 (1 minute - storage stats change slowly)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * @default STATIC_STALE_TIME (5 minutes)
   */
  staleTime?: number;
}

/**
 * Return type for the useStorageStatsQuery hook
 */
export interface UseStorageStatsQueryReturn {
  /** Storage stats response, undefined if not yet fetched */
  data: StorageStatsResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Disk usage percentage (0-100), null if unavailable */
  diskUsagePercent: number | null;
  /** Total disk space in bytes, null if unavailable */
  diskTotalBytes: number | null;
  /** Used disk space in bytes, null if unavailable */
  diskUsedBytes: number | null;
  /** Free disk space in bytes, null if unavailable */
  diskFreeBytes: number | null;
}

/**
 * Hook to fetch storage statistics using TanStack Query.
 *
 * This hook fetches from GET /api/system/storage and provides:
 * - Disk usage metrics
 * - Automatic caching with longer stale time (storage changes slowly)
 * - Configurable polling via refetchInterval
 *
 * @param options - Configuration options
 * @returns Storage stats and query state
 *
 * @example
 * ```tsx
 * const { data, isLoading, diskUsagePercent, error } = useStorageStatsQuery({
 *   refetchInterval: 60000, // Poll every minute
 * });
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <div>
 *     <p>Disk usage: {diskUsagePercent}%</p>
 *     <ProgressBar value={diskUsagePercent ?? 0} />
 *   </div>
 * );
 * ```
 */
export function useStorageStatsQuery(
  options: UseStorageStatsQueryOptions = {}
): UseStorageStatsQueryReturn {
  const {
    enabled = true,
    refetchInterval = 60000,
    staleTime = STATIC_STALE_TIME,
  } = options;

  const query = useQuery({
    queryKey: queryKeys.system.storage,
    queryFn: fetchStorageStats,
    enabled,
    refetchInterval,
    staleTime,
    retry: 2,
  });

  // Derive common metrics
  const diskUsagePercent = useMemo(
    () => query.data?.disk_usage_percent ?? null,
    [query.data?.disk_usage_percent]
  );

  const diskTotalBytes = useMemo(
    () => query.data?.disk_total_bytes ?? null,
    [query.data?.disk_total_bytes]
  );

  const diskUsedBytes = useMemo(
    () => query.data?.disk_used_bytes ?? null,
    [query.data?.disk_used_bytes]
  );

  const diskFreeBytes = useMemo(
    () => query.data?.disk_free_bytes ?? null,
    [query.data?.disk_free_bytes]
  );

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
    diskUsagePercent,
    diskTotalBytes,
    diskUsedBytes,
    diskFreeBytes,
  };
}

// ============================================================================
// useCleanupPreviewMutation
// ============================================================================

/**
 * Return type for the useCleanupPreviewMutation hook
 */
export interface UseCleanupPreviewMutationReturn {
  /** Mutation for previewing cleanup */
  mutation: ReturnType<typeof useMutation<CleanupResponse, Error, void>>;
  /** Last cleanup preview result */
  previewData: CleanupResponse | undefined;
  /** Whether the preview is in progress */
  isPending: boolean;
  /** Error from the preview operation */
  error: Error | null;
  /** Function to trigger cleanup preview */
  preview: () => Promise<CleanupResponse>;
  /** Reset the mutation state */
  reset: () => void;
}

/**
 * Hook providing mutation for cleanup preview operations.
 *
 * This mutation performs a dry run of the cleanup operation,
 * showing what would be deleted without actually deleting anything.
 *
 * @returns Mutation for cleanup preview
 *
 * @example
 * ```tsx
 * const { preview, previewData, isPending, error } = useCleanupPreviewMutation();
 *
 * const handlePreview = async () => {
 *   const result = await preview();
 *   console.log('Would delete:', result.files_deleted);
 *   console.log('Space freed:', result.bytes_freed);
 * };
 *
 * return (
 *   <div>
 *     <button onClick={handlePreview} disabled={isPending}>
 *       {isPending ? 'Loading...' : 'Preview Cleanup'}
 *     </button>
 *     {previewData && (
 *       <p>Would free {formatBytes(previewData.bytes_freed)}</p>
 *     )}
 *   </div>
 * );
 * ```
 */
export function useCleanupPreviewMutation(): UseCleanupPreviewMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: previewCleanup,
    onSuccess: () => {
      // Optionally invalidate storage stats after preview
      // (preview doesn't change anything, but user might want fresh stats)
      void queryClient.invalidateQueries({ queryKey: queryKeys.system.storage });
    },
  });

  return {
    mutation,
    previewData: mutation.data,
    isPending: mutation.isPending,
    error: mutation.error,
    preview: () => mutation.mutateAsync(),
    reset: mutation.reset,
  };
}

// ============================================================================
// useCleanupMutation
// ============================================================================

/**
 * Return type for the useCleanupMutation hook
 */
export interface UseCleanupMutationReturn {
  /** Mutation for executing cleanup */
  mutation: ReturnType<typeof useMutation<CleanupResponse, Error, void>>;
  /** Last cleanup result */
  cleanupData: CleanupResponse | undefined;
  /** Whether the cleanup is in progress */
  isPending: boolean;
  /** Error from the cleanup operation */
  error: Error | null;
  /** Function to trigger cleanup */
  cleanup: () => Promise<CleanupResponse>;
  /** Reset the mutation state */
  reset: () => void;
}

/**
 * Hook providing mutation for cleanup operations.
 *
 * This mutation performs the actual cleanup operation,
 * deleting old data according to retention policy.
 *
 * @returns Mutation for cleanup
 *
 * @example
 * ```tsx
 * const { cleanup, cleanupData, isPending, error } = useCleanupMutation();
 *
 * const handleCleanup = async () => {
 *   const result = await cleanup();
 *   console.log('Deleted:', result.events_deleted);
 *   console.log('Space freed:', result.space_reclaimed);
 * };
 *
 * return (
 *   <div>
 *     <button onClick={handleCleanup} disabled={isPending}>
 *       {isPending ? 'Cleaning...' : 'Run Cleanup'}
 *     </button>
 *     {cleanupData && (
 *       <p>Freed {formatBytes(cleanupData.space_reclaimed)}</p>
 *     )}
 *   </div>
 * );
 * ```
 */
export function useCleanupMutation(): UseCleanupMutationReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: triggerCleanup,
    onSuccess: () => {
      // Invalidate storage stats after cleanup since disk usage has changed
      void queryClient.invalidateQueries({ queryKey: queryKeys.system.storage });
      // Also invalidate system stats as event counts may have changed
      void queryClient.invalidateQueries({ queryKey: queryKeys.system.stats });
      // Invalidate events queries since events may have been deleted
      void queryClient.invalidateQueries({ queryKey: queryKeys.events.all });
    },
  });

  return {
    mutation,
    cleanupData: mutation.data,
    isPending: mutation.isPending,
    error: mutation.error,
    cleanup: () => mutation.mutateAsync(),
    reset: mutation.reset,
  };
}

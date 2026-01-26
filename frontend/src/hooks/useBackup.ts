/**
 * TanStack Query hooks for Backup/Restore operations
 *
 * This module provides hooks for fetching and mutating backup/restore data
 * using TanStack Query. It includes:
 *
 * Queries:
 * - useBackupList: Fetch list of available backups
 * - useBackupJob: Fetch backup job status with polling support
 * - useRestoreJob: Fetch restore job status with polling support
 *
 * Mutations:
 * - useCreateBackup: Create a new backup job
 * - useDeleteBackup: Delete a backup file
 * - useStartRestore: Start restore from uploaded file
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with automatic cache invalidation
 * - Configurable polling for job status monitoring
 * - Proper error handling
 *
 * @module hooks/useBackup
 * @see docs/plans/interfaces/backup-restore-interfaces.md - Interface definitions
 * @see NEM-3566
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

import * as backupApi from '../services/backupApi';
import { DEFAULT_STALE_TIME, REALTIME_STALE_TIME } from '../services/queryClient';
import { isBackupJobComplete, isRestoreJobComplete } from '../types/backup';

import type {
  BackupJob,
  BackupJobStartResponse,
  BackupListResponse,
  RestoreJob,
  RestoreJobStartResponse,
} from '../types/backup';

// Re-export types for convenience
export type {
  BackupJob,
  BackupJobProgress,
  BackupJobStartResponse,
  BackupJobStatus,
  BackupListItem,
  BackupListResponse,
  BackupManifest,
  BackupContentInfo,
  RestoreJob,
  RestoreJobProgress,
  RestoreJobStartResponse,
  RestoreJobStatus,
} from '../types/backup';

// Re-export status helpers
export {
  isBackupJob,
  isRestoreJob,
  isBackupJobComplete,
  isBackupJobRunning,
  isBackupJobPending,
  isBackupJobFailed,
  isRestoreJobComplete,
  isRestoreJobInProgress,
  isRestoreJobPending,
  isRestoreJobFailed,
} from '../types/backup';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query keys for backup/restore queries.
 * Follows the hierarchical pattern for cache invalidation.
 */
export const BACKUP_QUERY_KEYS = {
  /** Base key for all backup queries - use for bulk invalidation */
  all: ['backup'] as const,
  /** Backup list */
  list: ['backup', 'list'] as const,
  /** Specific backup job */
  job: (id: string) => ['backup', 'job', id] as const,
  /** Specific restore job */
  restore: (id: string) => ['backup', 'restore', id] as const,
} as const;

// ============================================================================
// useBackupList - Fetch list of available backups
// ============================================================================

/**
 * Options for configuring the useBackupList hook.
 */
export interface UseBackupListOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useBackupList hook.
 */
export interface UseBackupListReturn {
  /** Backup list data */
  data: BackupListResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch the list of available backups using TanStack Query.
 *
 * Returns all backup jobs with their status and download URLs.
 *
 * @param options - Configuration options
 * @returns Backup list and query state
 *
 * @example
 * ```tsx
 * const { data, isLoading, error } = useBackupList();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <div>
 *     <p>Total backups: {data?.total}</p>
 *     {data?.backups.map(backup => (
 *       <BackupItem key={backup.id} backup={backup} />
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useBackupList(options: UseBackupListOptions = {}): UseBackupListReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: BACKUP_QUERY_KEYS.list,
    queryFn: backupApi.listBackups,
    enabled,
    staleTime,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useBackupJob - Fetch backup job status with polling
// ============================================================================

/**
 * Options for configuring the useBackupJob hook.
 */
export interface UseBackupJobOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds for polling.
   * Set to false to disable polling.
   * Polling automatically stops when job is complete.
   * @default 2000 (2 seconds)
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useBackupJob hook.
 */
export interface UseBackupJobReturn {
  /** Backup job data */
  data: BackupJob | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch backup job status with optional polling using TanStack Query.
 *
 * Returns the full job details including progress, timing, and result.
 * Enables 2-second polling by default, which automatically stops when
 * the job is complete (completed or failed).
 *
 * @param jobId - Backup job identifier
 * @param options - Configuration options
 * @returns Backup job status and query state
 *
 * @example
 * ```tsx
 * // Poll while job is running
 * const { data: job, isLoading } = useBackupJob(jobId);
 *
 * if (isLoading) return <Spinner />;
 *
 * if (job?.status === 'completed') {
 *   return <DownloadButton url={job.file_path} />;
 * }
 *
 * if (job?.status === 'running') {
 *   return <ProgressBar percent={job.progress.progress_percent} />;
 * }
 * ```
 */
export function useBackupJob(
  jobId: string,
  options: UseBackupJobOptions = {}
): UseBackupJobReturn {
  const { enabled = true, refetchInterval = 2000 } = options;

  const query = useQuery({
    queryKey: BACKUP_QUERY_KEYS.job(jobId),
    queryFn: () => backupApi.getBackupJob(jobId),
    enabled: enabled && !!jobId,
    staleTime: REALTIME_STALE_TIME,
    // Stop polling when job is complete
    refetchInterval: (query) => {
      if (refetchInterval === false) return false;
      const data = query.state.data;
      if (data && isBackupJobComplete(data)) return false;
      return refetchInterval;
    },
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useRestoreJob - Fetch restore job status with polling
// ============================================================================

/**
 * Options for configuring the useRestoreJob hook.
 */
export interface UseRestoreJobOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds for polling.
   * Set to false to disable polling.
   * Polling automatically stops when job is complete.
   * @default 2000 (2 seconds)
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useRestoreJob hook.
 */
export interface UseRestoreJobReturn {
  /** Restore job data */
  data: RestoreJob | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch restore job status with optional polling using TanStack Query.
 *
 * Returns the full job details including progress, timing, and result.
 * Enables 2-second polling by default, which automatically stops when
 * the job is complete (completed or failed).
 *
 * @param jobId - Restore job identifier
 * @param options - Configuration options
 * @returns Restore job status and query state
 *
 * @example
 * ```tsx
 * // Poll while job is running
 * const { data: job, isLoading } = useRestoreJob(jobId);
 *
 * if (isLoading) return <Spinner />;
 *
 * if (job?.status === 'completed') {
 *   return <SuccessMessage items={job.items_restored} />;
 * }
 *
 * if (job?.status === 'validating') {
 *   return <StatusMessage>Validating backup file...</StatusMessage>;
 * }
 *
 * if (job?.status === 'restoring') {
 *   return <ProgressBar percent={job.progress.progress_percent} />;
 * }
 * ```
 */
export function useRestoreJob(
  jobId: string,
  options: UseRestoreJobOptions = {}
): UseRestoreJobReturn {
  const { enabled = true, refetchInterval = 2000 } = options;

  const query = useQuery({
    queryKey: BACKUP_QUERY_KEYS.restore(jobId),
    queryFn: () => backupApi.getRestoreJob(jobId),
    enabled: enabled && !!jobId,
    staleTime: REALTIME_STALE_TIME,
    // Stop polling when job is complete
    refetchInterval: (query) => {
      if (refetchInterval === false) return false;
      const data = query.state.data;
      if (data && isRestoreJobComplete(data)) return false;
      return refetchInterval;
    },
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

// ============================================================================
// useCreateBackup - Create a new backup job
// ============================================================================

/**
 * Return type for the useCreateBackup hook.
 */
export interface UseCreateBackupReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<BackupJobStartResponse, Error, void>>;
  /** Convenience method to create backup */
  createBackup: () => Promise<BackupJobStartResponse>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for creating a new backup job.
 *
 * Automatically invalidates the backup list on success.
 *
 * @returns Mutation for creating backup
 *
 * @example
 * ```tsx
 * const { createBackup, isLoading } = useCreateBackup();
 *
 * const handleCreateBackup = async () => {
 *   const { job_id, status, message } = await createBackup();
 *   toast.success(message);
 *   // Navigate to job details or start polling
 *   setActiveJobId(job_id);
 * };
 * ```
 */
export function useCreateBackup(): UseCreateBackupReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: backupApi.createBackup,
    onSuccess: () => {
      // Invalidate backup list to show new job
      void queryClient.invalidateQueries({
        queryKey: BACKUP_QUERY_KEYS.list,
      });
    },
  });

  return {
    mutation,
    createBackup: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useDeleteBackup - Delete a backup file
// ============================================================================

/**
 * Return type for the useDeleteBackup hook.
 */
export interface UseDeleteBackupReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<void, Error, string>>;
  /** Convenience method to delete backup */
  deleteBackup: (jobId: string) => Promise<void>;
  /** Whether the mutation is in progress */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for deleting a backup file.
 *
 * Automatically invalidates the backup list on success.
 *
 * @returns Mutation for deleting backup
 *
 * @example
 * ```tsx
 * const { deleteBackup, isLoading } = useDeleteBackup();
 *
 * const handleDelete = async (backupId: string) => {
 *   if (confirm('Delete this backup?')) {
 *     await deleteBackup(backupId);
 *     toast.success('Backup deleted');
 *   }
 * };
 * ```
 */
export function useDeleteBackup(): UseDeleteBackupReturn {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: backupApi.deleteBackup,
    onSuccess: () => {
      // Invalidate backup list to remove deleted item
      void queryClient.invalidateQueries({
        queryKey: BACKUP_QUERY_KEYS.list,
      });
    },
  });

  return {
    mutation,
    deleteBackup: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// useStartRestore - Start restore from uploaded file
// ============================================================================

/**
 * Return type for the useStartRestore hook.
 */
export interface UseStartRestoreReturn {
  /** The mutation object */
  mutation: ReturnType<typeof useMutation<RestoreJobStartResponse, Error, File>>;
  /** Convenience method to start restore */
  startRestore: (file: File) => Promise<RestoreJobStartResponse>;
  /** Whether the mutation is in progress (file upload in progress) */
  isLoading: boolean;
  /** Error if the mutation failed */
  error: Error | null;
}

/**
 * Hook providing mutation for starting a restore job from an uploaded file.
 *
 * Handles file upload as multipart/form-data.
 *
 * @returns Mutation for starting restore
 *
 * @example
 * ```tsx
 * const { startRestore, isLoading } = useStartRestore();
 *
 * const handleFileSelect = async (file: File) => {
 *   const { job_id, status, message } = await startRestore(file);
 *   toast.info(message);
 *   // Navigate to restore status page or start polling
 *   setActiveRestoreJobId(job_id);
 * };
 *
 * return (
 *   <input
 *     type="file"
 *     accept=".zip"
 *     onChange={(e) => {
 *       const file = e.target.files?.[0];
 *       if (file) handleFileSelect(file);
 *     }}
 *     disabled={isLoading}
 *   />
 * );
 * ```
 */
export function useStartRestore(): UseStartRestoreReturn {
  const mutation = useMutation({
    mutationFn: backupApi.startRestore,
  });

  return {
    mutation,
    startRestore: mutation.mutateAsync,
    isLoading: mutation.isPending,
    error: mutation.error,
  };
}

// ============================================================================
// Utility: Get Backup Download URL
// ============================================================================

/**
 * Re-export getBackupDownloadUrl for convenience.
 *
 * @example
 * ```tsx
 * import { getBackupDownloadUrl } from '../hooks/useBackup';
 *
 * const downloadUrl = getBackupDownloadUrl(backup.id);
 * // Use in anchor tag
 * <a href={downloadUrl} download>Download Backup</a>
 * ```
 */
export { getBackupDownloadUrl } from '../services/backupApi';

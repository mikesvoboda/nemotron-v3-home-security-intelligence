/**
 * useOrphanCleanup - Hook for managing orphan file cleanup operations
 *
 * Wraps the orphan cleanup mutation with additional state management for:
 * - Tracking whether a cleanup is currently running
 * - Storing the most recent cleanup result
 * - Distinguishing between preview (dry_run) and actual cleanup operations
 * - Providing default parameter values
 *
 * @see NEM-3568 Admin Cleanup Endpoints Frontend UI
 * @see backend/api/routes/admin.py - Backend implementation
 *
 * @module hooks/useOrphanCleanup
 */

import { useCallback, useState } from 'react';

import {
  useOrphanCleanupMutation,
  type OrphanCleanupRequest,
  type OrphanCleanupResponse,
} from './useAdminMutations';

// =============================================================================
// Types
// =============================================================================

/**
 * Parameters for running an orphan cleanup operation.
 */
export interface OrphanCleanupParams {
  /** If true, only report what would be deleted without actually deleting */
  dryRun?: boolean;
  /** Minimum age in hours before a file can be deleted (1-720) */
  minAgeHours?: number;
  /** Maximum gigabytes to delete in one run (0.1-100) */
  maxDeleteGb?: number;
}

/**
 * Return type for the useOrphanCleanup hook.
 */
export interface UseOrphanCleanupReturn {
  /** Whether a cleanup operation is currently running */
  isRunning: boolean;
  /** The result of the most recent cleanup operation */
  result: OrphanCleanupResponse | null;
  /** Whether the most recent result was from a dry run (preview) */
  lastRunWasDryRun: boolean | null;
  /** Error from the most recent cleanup operation, if any */
  error: Error | null;
  /** Run an orphan cleanup operation with the specified parameters */
  runCleanup: (params?: OrphanCleanupParams) => Promise<OrphanCleanupResponse>;
  /** Run a preview (dry run) cleanup operation */
  runPreview: (params?: Omit<OrphanCleanupParams, 'dryRun'>) => Promise<OrphanCleanupResponse>;
  /** Clear the stored result */
  clearResult: () => void;
}

// =============================================================================
// Constants
// =============================================================================

/** Default minimum file age in hours before deletion */
export const DEFAULT_MIN_AGE_HOURS = 24;

/** Default maximum GB to delete per run */
export const DEFAULT_MAX_DELETE_GB = 10;

// =============================================================================
// Hook Implementation
// =============================================================================

/**
 * Hook for managing orphan file cleanup operations.
 *
 * Provides a convenient interface for running cleanup operations with
 * automatic state management for tracking results and operation status.
 *
 * @returns Object with cleanup state and methods
 *
 * @example
 * ```tsx
 * const { isRunning, result, runCleanup, runPreview } = useOrphanCleanup();
 *
 * // Run a preview to see what would be deleted
 * const previewResult = await runPreview({ minAgeHours: 48 });
 * console.log(`Would delete ${previewResult.deleted_files} files`);
 *
 * // Run actual cleanup
 * const cleanupResult = await runCleanup({
 *   dryRun: false,
 *   minAgeHours: 48,
 *   maxDeleteGb: 5,
 * });
 * console.log(`Deleted ${cleanupResult.deleted_files} files`);
 * ```
 */
export function useOrphanCleanup(): UseOrphanCleanupReturn {
  const mutation = useOrphanCleanupMutation();

  // Track the most recent result and whether it was a dry run
  const [result, setResult] = useState<OrphanCleanupResponse | null>(null);
  const [lastRunWasDryRun, setLastRunWasDryRun] = useState<boolean | null>(null);

  /**
   * Run an orphan cleanup operation.
   */
  const runCleanup = useCallback(
    async (params: OrphanCleanupParams = {}): Promise<OrphanCleanupResponse> => {
      const request: OrphanCleanupRequest = {
        dry_run: params.dryRun ?? true,
        min_age_hours: params.minAgeHours ?? DEFAULT_MIN_AGE_HOURS,
        max_delete_gb: params.maxDeleteGb ?? DEFAULT_MAX_DELETE_GB,
      };

      const response = await mutation.mutateAsync(request);

      setResult(response);
      setLastRunWasDryRun(request.dry_run ?? true);

      return response;
    },
    [mutation]
  );

  /**
   * Run a preview (dry run) cleanup operation.
   * Convenience wrapper that always sets dryRun to true.
   */
  const runPreview = useCallback(
    async (params: Omit<OrphanCleanupParams, 'dryRun'> = {}): Promise<OrphanCleanupResponse> => {
      return runCleanup({ ...params, dryRun: true });
    },
    [runCleanup]
  );

  /**
   * Clear the stored result.
   */
  const clearResult = useCallback(() => {
    setResult(null);
    setLastRunWasDryRun(null);
  }, []);

  return {
    isRunning: mutation.isPending,
    result,
    lastRunWasDryRun,
    error: mutation.error,
    runCleanup,
    runPreview,
    clearResult,
  };
}

// Re-export types for convenience
export type { OrphanCleanupRequest, OrphanCleanupResponse } from './useAdminMutations';

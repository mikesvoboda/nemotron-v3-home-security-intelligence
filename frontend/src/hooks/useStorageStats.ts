import { useState, useCallback } from 'react';

import { usePolling } from './usePolling';
import {
  fetchStorageStats,
  previewCleanup,
  type StorageStatsResponse,
  type CleanupResponse,
} from '../services/api';

/**
 * Return type for the useStorageStats hook.
 */
export interface UseStorageStatsReturn {
  /** Current storage statistics */
  stats: StorageStatsResponse | null;
  /** Whether storage stats are currently being loaded */
  loading: boolean;
  /** Error message if storage stats failed to load */
  error: string | null;
  /** Manually trigger a refresh of storage stats */
  refresh: () => Promise<void>;
  /** Preview cleanup results (dry run) */
  previewCleanup: () => Promise<CleanupResponse | null>;
  /** Whether cleanup preview is in progress */
  previewLoading: boolean;
  /** Cleanup preview results */
  cleanupPreview: CleanupResponse | null;
}

/**
 * Hook options for configuring polling behavior.
 */
export interface UseStorageStatsOptions {
  /** Polling interval in milliseconds (default: 60000 = 1 minute) */
  pollInterval?: number;
  /** Whether to enable automatic polling (default: true) */
  enablePolling?: boolean;
}

/**
 * Hook for fetching and polling storage statistics.
 *
 * Provides real-time disk usage metrics with automatic polling.
 * Also provides cleanup preview functionality.
 *
 * @param options - Hook configuration options
 * @returns Storage stats, loading state, and control functions
 *
 * @example
 * ```tsx
 * const { stats, loading, error, refresh, previewCleanup, cleanupPreview } = useStorageStats({
 *   pollInterval: 30000, // Poll every 30 seconds
 * });
 *
 * if (loading) return <Spinner />;
 * if (error) return <Error message={error} />;
 *
 * return (
 *   <div>
 *     <p>Disk usage: {stats?.disk_usage_percent}%</p>
 *     <button onClick={refresh}>Refresh</button>
 *   </div>
 * );
 * ```
 */
export function useStorageStats(options: UseStorageStatsOptions = {}): UseStorageStatsReturn {
  const { pollInterval = 60000, enablePolling = true } = options;

  const [previewLoading, setPreviewLoading] = useState(false);
  const [cleanupPreview, setCleanupPreview] = useState<CleanupResponse | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  // Use the generic polling hook for fetching storage stats
  const {
    data: stats,
    loading,
    error: pollingError,
    refetch,
  } = usePolling<StorageStatsResponse>({
    fetcher: fetchStorageStats,
    interval: pollInterval,
    enabled: enablePolling,
  });

  // Convert Error to string for backward compatibility
  const error = previewError ?? pollingError?.message ?? null;

  /**
   * Manually trigger a refresh of storage stats.
   * Sets loading state before refetch for backward compatibility.
   */
  const refresh = useCallback(async () => {
    await refetch();
  }, [refetch]);

  /**
   * Preview what would be deleted by a cleanup operation.
   */
  const handlePreviewCleanup = useCallback(async (): Promise<CleanupResponse | null> => {
    try {
      setPreviewLoading(true);
      setPreviewError(null);
      const result = await previewCleanup();
      setCleanupPreview(result);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to preview cleanup';
      setPreviewError(message);
      return null;
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  return {
    stats,
    loading,
    error,
    refresh,
    previewCleanup: handlePreviewCleanup,
    previewLoading,
    cleanupPreview,
  };
}

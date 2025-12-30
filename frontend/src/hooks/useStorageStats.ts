import { useState, useEffect, useCallback } from 'react';

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

  const [stats, setStats] = useState<StorageStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [cleanupPreview, setCleanupPreview] = useState<CleanupResponse | null>(null);

  /**
   * Fetch storage stats from the API.
   */
  const fetchStats = useCallback(async () => {
    try {
      setError(null);
      const data = await fetchStorageStats();
      setStats(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to fetch storage stats';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Manually trigger a refresh of storage stats.
   */
  const refresh = useCallback(async () => {
    setLoading(true);
    await fetchStats();
  }, [fetchStats]);

  /**
   * Preview what would be deleted by a cleanup operation.
   */
  const handlePreviewCleanup = useCallback(async (): Promise<CleanupResponse | null> => {
    try {
      setPreviewLoading(true);
      const result = await previewCleanup();
      setCleanupPreview(result);
      return result;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to preview cleanup';
      setError(message);
      return null;
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    void fetchStats();
  }, [fetchStats]);

  // Set up polling
  useEffect(() => {
    if (!enablePolling || pollInterval <= 0) {
      return;
    }

    const intervalId = setInterval(() => {
      void fetchStats();
    }, pollInterval);

    return () => {
      clearInterval(intervalId);
    };
  }, [enablePolling, pollInterval, fetchStats]);

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

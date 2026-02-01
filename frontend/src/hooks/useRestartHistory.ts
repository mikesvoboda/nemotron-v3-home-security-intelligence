/**
 * Hook for fetching restart history with pagination and filtering.
 *
 * Provides paginated restart history for workers with optional filtering
 * by worker name.
 *
 * @example
 * ```typescript
 * // Basic usage
 * const { data, isLoading, error, refetch } = useRestartHistory();
 *
 * // With pagination
 * const { data } = useRestartHistory({ limit: 20, offset: 40 });
 *
 * // Filter by worker name
 * const { data } = useRestartHistory({ workerName: 'file_watcher' });
 * ```
 */

import { useState, useEffect, useCallback, useRef } from 'react';

import { fetchRestartHistory } from '../services/supervisorApi';

/**
 * Individual restart history item.
 */
export interface RestartHistoryItem {
  /** Worker name that was restarted */
  worker_name: string;
  /** ISO timestamp of the restart attempt */
  timestamp: string;
  /** Restart attempt number (1-based) */
  attempt: number;
  /** Whether the restart succeeded or failed */
  status: 'success' | 'failed';
  /** Error message if restart failed, null otherwise */
  error: string | null;
}

/**
 * Pagination information for restart history.
 */
export interface RestartHistoryPagination {
  /** Total number of items across all pages */
  total: number;
  /** Maximum items per page */
  limit: number;
  /** Current offset from start */
  offset: number;
  /** Whether there are more items after current page */
  has_more: boolean;
}

/**
 * Response from restart history endpoint.
 */
export interface RestartHistoryResponse {
  /** List of restart history items */
  items: RestartHistoryItem[];
  /** Pagination information */
  pagination: RestartHistoryPagination;
}

/**
 * Options for useRestartHistory hook.
 */
export interface UseRestartHistoryOptions {
  /** Filter by specific worker name */
  workerName?: string;
  /** Maximum number of items to return (default: 50) */
  limit?: number;
  /** Number of items to skip for pagination */
  offset?: number;
}

/**
 * Return type for useRestartHistory hook.
 */
export interface UseRestartHistoryResult {
  /** Restart history data, undefined while loading or on error */
  data: RestartHistoryResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if fetch failed, null otherwise */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch restart history with optional filtering and pagination.
 *
 * @param options - Configuration options for filtering and pagination
 * @returns Restart history data, loading state, error, and refetch function
 */
export function useRestartHistory(
  options?: UseRestartHistoryOptions
): UseRestartHistoryResult {
  const { workerName, limit, offset } = options ?? {};

  const [data, setData] = useState<RestartHistoryResponse | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Track if component is mounted to avoid state updates after unmount
  const isMountedRef = useRef(true);

  // Build options object for API call, excluding undefined values
  const buildOptions = useCallback((): UseRestartHistoryOptions | undefined => {
    const opts: UseRestartHistoryOptions = {};
    if (workerName !== undefined) opts.workerName = workerName;
    if (limit !== undefined) opts.limit = limit;
    if (offset !== undefined) opts.offset = offset;
    return Object.keys(opts).length > 0 ? opts : undefined;
  }, [workerName, limit, offset]);

  const fetchData = useCallback(async () => {
    try {
      const response = await fetchRestartHistory(buildOptions());
      if (isMountedRef.current) {
        setData(response);
        setError(null);
        setIsLoading(false);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setIsLoading(false);
      }
    }
  }, [buildOptions]);

  // Refetch function that can be called manually
  const refetch = useCallback(async () => {
    await fetchData();
  }, [fetchData]);

  // Fetch on mount and when options change
  useEffect(() => {
    isMountedRef.current = true;
    void fetchData();

    return () => {
      isMountedRef.current = false;
    };
  }, [fetchData]);

  return {
    data,
    isLoading,
    error,
    refetch,
  };
}

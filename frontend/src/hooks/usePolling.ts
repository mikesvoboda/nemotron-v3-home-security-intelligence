import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Options for configuring the usePolling hook.
 *
 * @template T - The type of data returned by the fetcher function
 */
export interface UsePollingOptions<T> {
  /** Async function that fetches data */
  fetcher: () => Promise<T>;
  /** Polling interval in milliseconds */
  interval: number;
  /** Whether polling is enabled (default: true) */
  enabled?: boolean;
  /** Callback invoked with data on successful fetch */
  onSuccess?: (data: T) => void;
  /** Callback invoked with error on failed fetch */
  onError?: (error: Error) => void;
}

/**
 * Return type for the usePolling hook.
 *
 * @template T - The type of data returned by the fetcher function
 */
export interface UsePollingReturn<T> {
  /** The fetched data, null if not yet fetched or on error */
  data: T | null;
  /** Whether the initial fetch is in progress */
  loading: boolean;
  /** Error from the last fetch, null if successful */
  error: Error | null;
  /** Manually trigger a refetch */
  refetch: () => Promise<void>;
}

/**
 * Generic polling hook that abstracts the common polling pattern.
 *
 * This hook provides a reusable pattern for fetching data on mount
 * and polling at a specified interval. It handles loading state,
 * error management, and provides callbacks for success/error handling.
 *
 * @template T - The type of data returned by the fetcher function
 * @param options - Configuration options for the polling behavior
 * @returns Object containing data, loading state, error, and refetch function
 *
 * @example
 * ```tsx
 * const { data, loading, error, refetch } = usePolling({
 *   fetcher: () => fetchStorageStats(),
 *   interval: 60000, // Poll every minute
 *   enabled: true,
 *   onSuccess: (data) => console.log('Fetched:', data),
 *   onError: (error) => console.error('Error:', error),
 * });
 *
 * if (loading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return <div>{JSON.stringify(data)}</div>;
 * ```
 */
export function usePolling<T>({
  fetcher,
  interval,
  enabled = true,
  onSuccess,
  onError,
}: UsePollingOptions<T>): UsePollingReturn<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Store callbacks in refs to avoid recreating fetchData when they change
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);
  onSuccessRef.current = onSuccess;
  onErrorRef.current = onError;

  // Store fetcher in a ref to allow stable reference for useEffect
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const fetchData = useCallback(async () => {
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
      onSuccessRef.current?.(result);
    } catch (err) {
      const errorObj = err instanceof Error ? err : new Error(String(err));
      setError(errorObj);
      onErrorRef.current?.(errorObj);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch on mount
  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  // Set up polling interval
  useEffect(() => {
    if (!enabled || interval <= 0) {
      return;
    }

    const id = setInterval(() => {
      void fetchData();
    }, interval);

    return () => {
      clearInterval(id);
    };
  }, [enabled, interval, fetchData]);

  return {
    data,
    loading,
    error,
    refetch: fetchData,
  };
}

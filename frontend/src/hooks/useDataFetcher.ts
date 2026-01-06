import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Status of the data fetching operation
 */
export type FetchStatus = 'idle' | 'loading' | 'success' | 'error';

/**
 * Options for configuring the useDataFetcher hook
 */
export interface UseDataFetcherOptions<T> {
  /**
   * The async function that fetches the data.
   * This function can receive an AbortSignal for cancellation support.
   */
  fetcher: (signal?: AbortSignal) => Promise<T>;

  /**
   * Whether to enable automatic fetching on mount and when dependencies change.
   * @default true
   */
  enabled?: boolean;

  /**
   * Number of retry attempts on failure.
   * @default 3
   */
  retryAttempts?: number;

  /**
   * Base delay in milliseconds between retries (exponential backoff is applied).
   * @default 1000
   */
  retryDelay?: number;

  /**
   * Polling interval in milliseconds. Set to 0 to disable polling.
   * @default 0
   */
  pollingInterval?: number;

  /**
   * Whether to pause polling when an error occurs.
   * @default false
   */
  pausePollingOnError?: boolean;

  /**
   * Dependencies that will trigger a refetch when changed.
   * Uses shallow comparison.
   */
  dependencies?: unknown[];

  /**
   * Callback called when data is successfully fetched.
   */
  onSuccess?: (data: T) => void;

  /**
   * Callback called when an error occurs.
   */
  onError?: (error: Error) => void;
}

/**
 * Return type of the useDataFetcher hook
 */
export interface UseDataFetcherReturn<T> {
  /** The fetched data, undefined if not yet fetched or on initial load */
  data: T | undefined;

  /** Error message if the last fetch failed, null otherwise */
  error: string | null;

  /** Whether a fetch is currently in progress */
  isLoading: boolean;

  /** Current status of the fetch operation */
  status: FetchStatus;

  /** Function to manually trigger a refetch */
  refetch: () => Promise<void>;
}

/**
 * A standardized data fetching hook with consistent loading/error/success states,
 * retry logic with exponential backoff, AbortController cleanup, and polling support.
 *
 * @param options - Configuration options for the hook
 * @returns Object containing data, error, loading state, status, and refetch function
 *
 * @example
 * ```tsx
 * const { data, error, isLoading, refetch } = useDataFetcher({
 *   fetcher: () => fetchUsers(),
 *   pollingInterval: 30000,
 *   retryAttempts: 3,
 * });
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error} />;
 *
 * return <UserList users={data} onRefresh={refetch} />;
 * ```
 *
 * @example With dependencies
 * ```tsx
 * const { data } = useDataFetcher({
 *   fetcher: () => fetchUser(userId),
 *   dependencies: [userId],
 * });
 * ```
 *
 * @example Disabled until condition is met
 * ```tsx
 * const { data } = useDataFetcher({
 *   fetcher: () => fetchUserDetails(userId),
 *   enabled: !!userId,
 * });
 * ```
 */
export function useDataFetcher<T>(
  options: UseDataFetcherOptions<T>
): UseDataFetcherReturn<T> {
  const {
    fetcher,
    enabled = true,
    retryAttempts = 3,
    retryDelay = 1000,
    pollingInterval = 0,
    pausePollingOnError = false,
    dependencies = [],
    onSuccess,
    onError,
  } = options;

  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<FetchStatus>(enabled ? 'loading' : 'idle');

  // Track if component is mounted to avoid state updates after unmount
  const isMountedRef = useRef<boolean>(true);

  // Track current abort controller
  const abortControllerRef = useRef<AbortController | null>(null);

  // Track retry timeout
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Track polling interval
  const pollingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Track if polling is paused due to error
  const isPausedRef = useRef<boolean>(false);

  // Track current retry count
  const retryCountRef = useRef<number>(0);

  // Store callbacks in refs to avoid recreating the fetch function
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);
  const fetcherRef = useRef(fetcher);

  // Update refs when callbacks change
  onSuccessRef.current = onSuccess;
  onErrorRef.current = onError;
  fetcherRef.current = fetcher;

  /**
   * Core fetch function with retry logic
   */
  const executeFetch = useCallback(
    async (isRetry: boolean = false): Promise<void> => {
      if (!isMountedRef.current) return;

      // Abort any pending request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      // Create new abort controller for this request
      abortControllerRef.current = new AbortController();
      const signal = abortControllerRef.current.signal;

      // Reset retry count on new fetch (not retry)
      if (!isRetry) {
        retryCountRef.current = 0;
      }

      setStatus('loading');

      try {
        const result = await fetcherRef.current(signal);

        // Check if aborted or unmounted
        if (signal.aborted || !isMountedRef.current) return;

        setData(result);
        setError(null);
        setStatus('success');
        retryCountRef.current = 0;
        isPausedRef.current = false;

        // Call onSuccess callback
        onSuccessRef.current?.(result);
      } catch (err) {
        // Check if aborted or unmounted
        if (!isMountedRef.current) return;
        if (err instanceof DOMException && err.name === 'AbortError') return;

        const errorObj = err instanceof Error ? err : new Error('An unknown error occurred');
        const errorMessage = errorObj.message;

        // Check if we should retry
        if (retryCountRef.current < retryAttempts) {
          retryCountRef.current += 1;
          const delay = retryDelay * Math.pow(2, retryCountRef.current - 1);

          // Clear any existing retry timeout
          if (retryTimeoutRef.current) {
            clearTimeout(retryTimeoutRef.current);
          }

          retryTimeoutRef.current = setTimeout(() => {
            if (isMountedRef.current) {
              void executeFetch(true);
            }
          }, delay);
          return;
        }

        // Max retries exceeded
        setError(errorMessage);
        setStatus('error');

        // Pause polling if configured
        if (pausePollingOnError) {
          isPausedRef.current = true;
        }

        // Call onError callback
        onErrorRef.current?.(errorObj);
      }
    },
    [retryAttempts, retryDelay, pausePollingOnError]
  );

  /**
   * Public refetch function
   */
  const refetch = useCallback(async (): Promise<void> => {
    isPausedRef.current = false;
    await executeFetch(false);
  }, [executeFetch]);

  // Store dependencies in ref for comparison
  const prevDepsRef = useRef<unknown[]>(dependencies);

  // Initial fetch and dependency change handling
  useEffect(() => {
    isMountedRef.current = true;

    // Check if dependencies changed (shallow comparison)
    const depsChanged =
      dependencies.length !== prevDepsRef.current.length ||
      dependencies.some((dep, i) => dep !== prevDepsRef.current[i]);

    prevDepsRef.current = dependencies;

    if (enabled && (depsChanged || status === 'idle' || status === 'loading')) {
      void executeFetch(false);
    } else if (!enabled) {
      // When disabled, abort any pending requests
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      // Clear any pending retry
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
    }

    return () => {
      isMountedRef.current = false;

      // Abort any pending request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      // Clear retry timeout
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, executeFetch, ...dependencies]);

  // Polling effect
  useEffect(() => {
    if (!enabled || pollingInterval <= 0) {
      // Clear any existing polling interval
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      return;
    }

    pollingIntervalRef.current = setInterval(() => {
      if (isMountedRef.current && !isPausedRef.current) {
        void executeFetch(false);
      }
    }, pollingInterval);

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [enabled, pollingInterval, executeFetch]);

  return {
    data,
    error,
    isLoading: status === 'loading',
    status,
    refetch,
  };
}

export default useDataFetcher;

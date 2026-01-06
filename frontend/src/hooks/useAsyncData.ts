import { useState, useCallback, useEffect, useRef } from 'react';

import {
  type AsyncState,
  idle,
  loading,
  error,
  success,
  isSuccess,
  isLoading,
} from '../types/async-state';

/**
 * Options for the useAsyncData hook.
 */
export interface UseAsyncDataOptions<T> {
  /**
   * Initial data to use (skips the initial idle state).
   * Useful when you have cached data or server-side rendered data.
   */
  initialData?: T;

  /**
   * Whether to fetch data immediately on mount.
   * @default true
   */
  immediate?: boolean;

  /**
   * Whether to keep previous data visible during refetch.
   * Enables stale-while-revalidate (SWR) pattern.
   * @default false
   */
  keepPreviousData?: boolean;

  /**
   * Dependencies that trigger a refetch when changed.
   * Similar to useEffect dependencies.
   */
  deps?: readonly unknown[];

  /**
   * Callback when fetch succeeds.
   */
  onSuccess?: (data: T) => void;

  /**
   * Callback when fetch fails.
   */
  onError?: (error: Error) => void;
}

/**
 * Return type for the useAsyncData hook.
 */
export interface UseAsyncDataReturn<T> {
  /** Current async state (idle | loading | error | success) */
  state: AsyncState<T>;

  /** Convenience getter for data (undefined if not success/loading with previous) */
  data: T | undefined;

  /** Convenience getter for error (undefined if not error state) */
  error: Error | undefined;

  /** Whether currently in loading state */
  isLoading: boolean;

  /** Whether currently in error state */
  isError: boolean;

  /** Whether currently in success state */
  isSuccess: boolean;

  /** Whether currently in idle state */
  isIdle: boolean;

  /** Trigger a refetch manually */
  refetch: () => Promise<void>;

  /** Reset to idle state */
  reset: () => void;

  /** Manually set data (transitions to success state) */
  setData: (data: T) => void;

  /** Manually set error (transitions to error state) */
  setError: (error: Error) => void;
}

/**
 * A hook for managing async data fetching with type-safe state management.
 *
 * Uses the AsyncState discriminated union pattern for compile-time safety
 * and exhaustive state handling.
 *
 * @param fetchFn - Async function that fetches the data
 * @param options - Configuration options
 * @returns Object containing state, data accessors, and control functions
 *
 * @example
 * ```typescript
 * // Basic usage
 * const { data, isLoading, error, refetch } = useAsyncData(
 *   () => api.getUsers()
 * );
 *
 * // With options
 * const { state, data, isLoading } = useAsyncData(
 *   () => api.getUser(userId),
 *   {
 *     immediate: true,
 *     keepPreviousData: true,
 *     deps: [userId],
 *     onSuccess: (user) => console.log('Fetched', user.name),
 *     onError: (err) => toast.error(err.message),
 *   }
 * );
 *
 * // With AsyncState pattern
 * switch (state.status) {
 *   case 'idle':
 *     return null;
 *   case 'loading':
 *     return <Spinner />;
 *   case 'error':
 *     return <Error message={state.error.message} />;
 *   case 'success':
 *     return <UserProfile user={state.data} />;
 * }
 * ```
 */
export function useAsyncData<T>(
  fetchFn: () => Promise<T>,
  options: UseAsyncDataOptions<T> = {}
): UseAsyncDataReturn<T> {
  const {
    initialData,
    immediate = true,
    keepPreviousData = false,
    deps = [],
    onSuccess,
    onError,
  } = options;

  // Initialize state - use success if initialData provided, otherwise idle
  const [state, setState] = useState<AsyncState<T>>(() =>
    initialData !== undefined ? success(initialData) : idle()
  );

  // Track if component is mounted to prevent state updates after unmount
  const isMountedRef = useRef(true);

  // Track the current fetch to handle race conditions
  const fetchIdRef = useRef(0);

  // Store callbacks in refs to avoid stale closures
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);
  const fetchFnRef = useRef(fetchFn);

  // Update refs when callbacks change
  useEffect(() => {
    onSuccessRef.current = onSuccess;
    onErrorRef.current = onError;
    fetchFnRef.current = fetchFn;
  });

  // Track mounted state
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const execute = useCallback(async () => {
    // Increment fetch ID to track this request
    const currentFetchId = ++fetchIdRef.current;

    // Get previous data for SWR pattern if enabled
    const previousData =
      keepPreviousData && isSuccess(state) ? state.data : undefined;

    // Transition to loading state
    if (!isMountedRef.current) return;
    setState(loading(previousData));

    try {
      const result = await fetchFnRef.current();

      // Only update state if this is still the latest request and component is mounted
      if (currentFetchId !== fetchIdRef.current || !isMountedRef.current) {
        return;
      }

      setState(success(result));
      onSuccessRef.current?.(result);
    } catch (err) {
      // Only update state if this is still the latest request and component is mounted
      if (currentFetchId !== fetchIdRef.current || !isMountedRef.current) {
        return;
      }

      const errorObj = err instanceof Error ? err : new Error(String(err));
      setState(error(errorObj));
      onErrorRef.current?.(errorObj);
    }
  }, [keepPreviousData, state]);

  const refetch = useCallback(async () => {
    await execute();
  }, [execute]);

  const reset = useCallback(() => {
    // Cancel any in-flight requests
    fetchIdRef.current++;
    setState(idle());
  }, []);

  const setData = useCallback((data: T) => {
    setState(success(data));
  }, []);

  const setError = useCallback((err: Error) => {
    setState(error(err));
  }, []);

  // Fetch on mount if immediate is true
  useEffect(() => {
    if (immediate) {
      void execute();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [immediate, ...deps]);

  // Compute convenience getters
  const data =
    isSuccess(state)
      ? state.data
      : isLoading(state) && state.previousData !== undefined
        ? state.previousData
        : undefined;

  const errorValue = state.status === 'error' ? state.error : undefined;

  return {
    state,
    data,
    error: errorValue,
    isLoading: state.status === 'loading',
    isError: state.status === 'error',
    isSuccess: state.status === 'success',
    isIdle: state.status === 'idle',
    refetch,
    reset,
    setData,
    setError,
  };
}

/**
 * A simpler version of useAsyncData for one-off async operations.
 * Does not automatically fetch on mount - you control when to execute.
 *
 * @param asyncFn - Async function to execute
 * @returns Object containing state, execute function, and control functions
 *
 * @example
 * ```typescript
 * const { execute, isLoading, error } = useAsyncAction(
 *   (userId: string) => api.deleteUser(userId)
 * );
 *
 * async function handleDelete() {
 *   await execute(userId);
 *   navigate('/users');
 * }
 * ```
 */
export function useAsyncAction<TArgs extends unknown[], TResult>(
  asyncFn: (...args: TArgs) => Promise<TResult>
): UseAsyncActionReturn<TArgs, TResult> {
  const [state, setState] = useState<AsyncState<TResult>>(idle());

  const isMountedRef = useRef(true);
  const executionIdRef = useRef(0);
  const asyncFnRef = useRef(asyncFn);

  useEffect(() => {
    asyncFnRef.current = asyncFn;
  });

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const execute = useCallback(async (...args: TArgs): Promise<TResult> => {
    const currentId = ++executionIdRef.current;

    if (!isMountedRef.current) {
      throw new Error('Component unmounted');
    }

    setState(loading());

    try {
      const result = await asyncFnRef.current(...args);

      if (currentId !== executionIdRef.current || !isMountedRef.current) {
        throw new Error('Stale request');
      }

      setState(success(result));
      return result;
    } catch (err) {
      if (currentId !== executionIdRef.current || !isMountedRef.current) {
        throw err;
      }

      const errorObj = err instanceof Error ? err : new Error(String(err));
      setState(error(errorObj));
      throw errorObj;
    }
  }, []);

  const reset = useCallback(() => {
    executionIdRef.current++;
    setState(idle());
  }, []);

  const data = isSuccess(state) ? state.data : undefined;
  const errorValue = state.status === 'error' ? state.error : undefined;

  return {
    state,
    data,
    error: errorValue,
    isLoading: state.status === 'loading',
    isError: state.status === 'error',
    isSuccess: state.status === 'success',
    isIdle: state.status === 'idle',
    execute,
    reset,
  };
}

/**
 * Return type for the useAsyncAction hook.
 */
export interface UseAsyncActionReturn<TArgs extends unknown[], TResult> {
  /** Current async state */
  state: AsyncState<TResult>;

  /** Convenience getter for data */
  data: TResult | undefined;

  /** Convenience getter for error */
  error: Error | undefined;

  /** Whether currently in loading state */
  isLoading: boolean;

  /** Whether currently in error state */
  isError: boolean;

  /** Whether currently in success state */
  isSuccess: boolean;

  /** Whether currently in idle state */
  isIdle: boolean;

  /** Execute the async action with arguments */
  execute: (...args: TArgs) => Promise<TResult>;

  /** Reset to idle state */
  reset: () => void;
}

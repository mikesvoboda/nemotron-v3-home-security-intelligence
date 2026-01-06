/**
 * Async State Management Types with Discriminated Unions
 *
 * This module provides type-safe async state management using discriminated unions.
 * The `status` field serves as the discriminant, enabling TypeScript to narrow the
 * state type and provide proper type inference for data and error handling.
 *
 * Benefits:
 * - Impossible states are unrepresentable (e.g., can't have data while loading)
 * - TypeScript narrows types automatically based on status
 * - Forces handling of all states (loading, error, success)
 * - Prevents common bugs like accessing data before it's loaded
 *
 * @example
 * ```tsx
 * function EventList() {
 *   const [state, setState] = useState<AsyncState<Event[]>>(idle());
 *
 *   useEffect(() => {
 *     setState(loading());
 *     fetchEvents()
 *       .then(data => setState(success(data)))
 *       .catch(err => setState(failure(err)));
 *   }, []);
 *
 *   // Pattern matching with switch
 *   switch (state.status) {
 *     case 'idle':
 *       return <div>No data loaded</div>;
 *     case 'loading':
 *       return <Spinner />;
 *     case 'error':
 *       return <ErrorMessage error={state.error} onRetry={state.retry} />;
 *     case 'success':
 *       return <EventGrid events={state.data} />;
 *   }
 * }
 * ```
 */

// ============================================================================
// Async State Types
// ============================================================================

/**
 * Initial state before any data fetching has occurred.
 */
export interface IdleState {
  status: 'idle';
}

/**
 * Loading state while data is being fetched.
 * Optionally preserves previous data for optimistic UI updates.
 */
export interface LoadingState<T> {
  status: 'loading';
  /** Previous data (if any) for optimistic UI */
  previousData?: T;
}

/**
 * Error state when data fetching has failed.
 */
export interface ErrorState {
  status: 'error';
  /** The error that occurred */
  error: Error;
  /** Optional retry function */
  retry?: () => void;
}

/**
 * Success state when data has been successfully loaded.
 */
export interface SuccessState<T> {
  status: 'success';
  /** The loaded data */
  data: T;
  /** Timestamp of when data was fetched */
  fetchedAt?: Date;
}

/**
 * Discriminated union of all async states.
 * Use this as the base type for component state when fetching data.
 *
 * @example
 * ```tsx
 * const [state, setState] = useState<AsyncState<User>>(idle());
 * ```
 */
export type AsyncState<T> = IdleState | LoadingState<T> | ErrorState | SuccessState<T>;

/**
 * All possible async status values.
 */
export type AsyncStatus = AsyncState<unknown>['status'];

// ============================================================================
// State Factory Functions
// ============================================================================

/**
 * Creates an idle state.
 *
 * @example
 * ```ts
 * const initialState = idle<User[]>();
 * ```
 */
export function idle<T>(): AsyncState<T> {
  return { status: 'idle' };
}

/**
 * Creates a loading state, optionally preserving previous data.
 *
 * @param previousData - Optional previous data to preserve during loading
 *
 * @example
 * ```ts
 * // Fresh load
 * setState(loading());
 *
 * // Refresh with previous data visible
 * setState(loading(currentEvents));
 * ```
 */
export function loading<T>(previousData?: T): AsyncState<T> {
  return previousData !== undefined
    ? { status: 'loading', previousData }
    : { status: 'loading' };
}

/**
 * Creates an error state.
 *
 * @param error - The error that occurred (string, Error, or unknown)
 * @param retry - Optional retry function
 *
 * @example
 * ```ts
 * setState(failure(new Error('Network error')));
 * setState(failure('Something went wrong', refetch));
 * ```
 */
export function failure<T>(error: unknown, retry?: () => void): AsyncState<T> {
  const errorObj =
    error instanceof Error
      ? error
      : typeof error === 'string'
        ? new Error(error)
        : new Error('Unknown error');

  return { status: 'error', error: errorObj, retry };
}

/**
 * Creates a success state.
 *
 * @param data - The successfully loaded data
 * @param fetchedAt - Optional timestamp of when data was fetched
 *
 * @example
 * ```ts
 * setState(success(events));
 * setState(success(user, new Date()));
 * ```
 */
export function success<T>(data: T, fetchedAt?: Date): AsyncState<T> {
  return { status: 'success', data, fetchedAt };
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard for idle state.
 */
export function isIdle<T>(state: AsyncState<T>): state is IdleState {
  return state.status === 'idle';
}

/**
 * Type guard for loading state.
 */
export function isLoading<T>(state: AsyncState<T>): state is LoadingState<T> {
  return state.status === 'loading';
}

/**
 * Type guard for error state.
 */
export function isError<T>(state: AsyncState<T>): state is ErrorState {
  return state.status === 'error';
}

/**
 * Type guard for success state.
 */
export function isSuccess<T>(state: AsyncState<T>): state is SuccessState<T> {
  return state.status === 'success';
}

/**
 * Type guard for states that have data (loading with previousData or success).
 */
export function hasData<T>(
  state: AsyncState<T>
): state is LoadingState<T> & { previousData: T } | SuccessState<T> {
  if (state.status === 'success') return true;
  if (state.status === 'loading' && state.previousData !== undefined) return true;
  return false;
}

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get data from a state if available, or undefined otherwise.
 * Works with success state or loading state with previousData.
 *
 * @example
 * ```ts
 * const data = getData(state); // T | undefined
 * if (data) {
 *   // Use data safely
 * }
 * ```
 */
export function getData<T>(state: AsyncState<T>): T | undefined {
  if (state.status === 'success') return state.data;
  if (state.status === 'loading') return state.previousData;
  return undefined;
}

/**
 * Get error from a state if in error state, or undefined otherwise.
 */
export function getError<T>(state: AsyncState<T>): Error | undefined {
  return state.status === 'error' ? state.error : undefined;
}

/**
 * Map over the data in a success state.
 * Returns the original state unchanged if not in success state.
 *
 * @example
 * ```ts
 * const mappedState = mapData(state, events => events.filter(e => e.risk_score > 50));
 * ```
 */
export function mapData<T, U>(
  state: AsyncState<T>,
  fn: (data: T) => U
): AsyncState<U> {
  if (state.status === 'success') {
    return success(fn(state.data), state.fetchedAt);
  }
  if (state.status === 'loading' && state.previousData !== undefined) {
    return { status: 'loading', previousData: fn(state.previousData) };
  }
  // For idle and error states, we can return them as-is since they don't have data
  return state as AsyncState<U>;
}

/**
 * Pattern match on async state.
 * Forces handling of all cases and provides type-safe access to data/error.
 *
 * @example
 * ```tsx
 * return matchState(state, {
 *   idle: () => <EmptyState />,
 *   loading: (prev) => prev ? <EventList events={prev} loading /> : <Spinner />,
 *   error: (error, retry) => <ErrorMessage error={error} onRetry={retry} />,
 *   success: (data) => <EventList events={data} />,
 * });
 * ```
 */
export function matchState<T, R>(
  state: AsyncState<T>,
  handlers: {
    idle: () => R;
    loading: (previousData?: T) => R;
    error: (error: Error, retry?: () => void) => R;
    success: (data: T, fetchedAt?: Date) => R;
  }
): R {
  switch (state.status) {
    case 'idle':
      return handlers.idle();
    case 'loading':
      return handlers.loading(state.previousData);
    case 'error':
      return handlers.error(state.error, state.retry);
    case 'success':
      return handlers.success(state.data, state.fetchedAt);
  }
}

// ============================================================================
// Extended Async State with Refresh
// ============================================================================

/**
 * Refreshing state - successfully loaded but currently refreshing.
 */
export interface RefreshingState<T> {
  status: 'refreshing';
  /** Current data being refreshed */
  data: T;
  /** Timestamp of when data was originally fetched */
  fetchedAt?: Date;
}

/**
 * Extended async state that includes a refreshing state.
 * Use this when you need to show both stale data and a refresh indicator.
 */
export type RefreshableState<T> = AsyncState<T> | RefreshingState<T>;

/**
 * Type guard for refreshing state.
 */
export function isRefreshing<T>(
  state: RefreshableState<T>
): state is RefreshingState<T> {
  return (state as RefreshingState<T>).status === 'refreshing';
}

/**
 * Creates a refreshing state from a success state.
 */
export function refreshing<T>(data: T, fetchedAt?: Date): RefreshingState<T> {
  return { status: 'refreshing', data, fetchedAt };
}

// ============================================================================
// Paginated Async State
// ============================================================================

/**
 * Paginated data with metadata.
 */
export interface PaginatedData<T> {
  /** Current page items */
  items: T[];
  /** Total number of items across all pages */
  total: number;
  /** Current page number (0-indexed) */
  page: number;
  /** Items per page */
  pageSize: number;
  /** Whether there are more pages */
  hasMore: boolean;
}

/**
 * Async state for paginated data.
 */
export type PaginatedState<T> = AsyncState<PaginatedData<T>>;

/**
 * Creates a success state with paginated data.
 */
export function paginatedSuccess<T>(
  items: T[],
  total: number,
  page: number,
  pageSize: number
): PaginatedState<T> {
  return success({
    items,
    total,
    page,
    pageSize,
    hasMore: (page + 1) * pageSize < total,
  });
}

// ============================================================================
// Hook Return Type Helper
// ============================================================================

/**
 * Standard return type for async data hooks.
 * Provides a consistent interface for all data fetching hooks.
 *
 * @example
 * ```ts
 * function useEvents(): AsyncHookReturn<Event[]> {
 *   const [state, setState] = useState<AsyncState<Event[]>>(idle());
 *   const refetch = useCallback(() => { ... }, []);
 *   return { ...state, refetch };
 * }
 * ```
 */
export type AsyncHookReturn<T> = AsyncState<T> & {
  /** Function to refetch data */
  refetch: () => void;
};

/**
 * Creates a hook return value from state and refetch function.
 */
export function createAsyncHookReturn<T>(
  state: AsyncState<T>,
  refetch: () => void
): AsyncHookReturn<T> {
  return { ...state, refetch };
}

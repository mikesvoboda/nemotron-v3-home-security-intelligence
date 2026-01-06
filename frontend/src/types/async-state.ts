/**
 * Async State Discriminated Union Types
 *
 * This module provides a type-safe discriminated union pattern for managing
 * async operation states (idle, loading, error, success). Using the `status`
 * field as the discriminator enables exhaustive type checking and compile-time safety.
 *
 * @see frontend/src/hooks/useAsyncData.ts - Hook using this pattern
 */

// ============================================================================
// Status Type
// ============================================================================

/**
 * All possible async state status values.
 */
export type AsyncStatus = 'idle' | 'loading' | 'error' | 'success';

// ============================================================================
// State Types (Discriminated Union Members)
// ============================================================================

/**
 * Initial state before any operation has started.
 */
export interface IdleState {
  readonly status: 'idle';
}

/**
 * State while an async operation is in progress.
 * Optionally tracks previous data for optimistic updates.
 */
export interface LoadingState<T = unknown> {
  readonly status: 'loading';
  /** Previous data from a successful fetch (for optimistic updates / SWR patterns) */
  readonly previousData?: T;
}

/**
 * State when an async operation has failed.
 */
export interface ErrorState {
  readonly status: 'error';
  /** The error that occurred */
  readonly error: Error;
}

/**
 * State when an async operation has completed successfully.
 */
export interface SuccessState<T> {
  readonly status: 'success';
  /** The successfully fetched data */
  readonly data: T;
}

/**
 * Discriminated union of all async operation states.
 * The `status` field acts as the discriminator for type narrowing.
 *
 * @typeParam T - The type of data on success
 */
export type AsyncState<T> = IdleState | LoadingState<T> | ErrorState | SuccessState<T>;

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard for IdleState.
 */
export function isIdle<T>(state: AsyncState<T>): state is IdleState {
  return state.status === 'idle';
}

/**
 * Type guard for LoadingState.
 */
export function isLoading<T>(state: AsyncState<T>): state is LoadingState<T> {
  return state.status === 'loading';
}

/**
 * Type guard for ErrorState.
 */
export function isError<T>(state: AsyncState<T>): state is ErrorState {
  return state.status === 'error';
}

/**
 * Type guard for SuccessState.
 */
export function isSuccess<T>(state: AsyncState<T>): state is SuccessState<T> {
  return state.status === 'success';
}

// ============================================================================
// Factory Functions
// ============================================================================

/**
 * Creates an idle state.
 */
export function idle(): IdleState {
  return { status: 'idle' };
}

/**
 * Creates a loading state, optionally with previous data.
 */
export function loading<T>(previousData?: T): LoadingState<T> {
  if (previousData !== undefined) {
    return { status: 'loading', previousData };
  }
  return { status: 'loading' };
}

/**
 * Creates an error state.
 */
export function error(err: Error): ErrorState {
  return { status: 'error', error: err };
}

/**
 * Creates a success state with data.
 */
export function success<T>(data: T): SuccessState<T> {
  return { status: 'success', data };
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Extracts data from an AsyncState, returning a default value if not in success state.
 */
export function getDataOrDefault<T>(state: AsyncState<T>, defaultValue: T): T {
  if (isSuccess(state)) {
    return state.data;
  }
  return defaultValue;
}

/**
 * Maps over the data in an AsyncState if it's in success state.
 * Preserves the state type for idle, loading, and error states.
 */
export function mapAsyncState<T, U>(state: AsyncState<T>, fn: (data: T) => U): AsyncState<U> {
  switch (state.status) {
    case 'idle':
      return state;
    case 'loading':
      if (state.previousData !== undefined) {
        return loading(fn(state.previousData));
      }
      return loading<U>();
    case 'error':
      return state;
    case 'success':
      return success(fn(state.data));
    default:
      return assertNever(state);
  }
}

/**
 * Combines multiple AsyncStates into one.
 * Returns loading if any are loading, error if any have errors,
 * success only if all are successful.
 */
export function combineAsyncStates<T extends readonly AsyncState<unknown>[]>(
  states: T
): AsyncState<{ [K in keyof T]: T[K] extends AsyncState<infer U> ? U : never }> {
  for (const state of states) {
    if (isLoading(state)) {
      return loading();
    }
  }

  for (const state of states) {
    if (isError(state)) {
      return state;
    }
  }

  const allSuccess = states.every(isSuccess);
  if (allSuccess) {
    const data = states.map((s) => (s as SuccessState<unknown>).data) as {
      [K in keyof T]: T[K] extends AsyncState<infer U> ? U : never;
    };
    return success(data);
  }

  return idle();
}

/**
 * Gets any available data from an AsyncState, including previous data during loading.
 * Useful for SWR (stale-while-revalidate) patterns.
 */
export function getAvailableData<T>(state: AsyncState<T>): T | undefined {
  if (isSuccess(state)) {
    return state.data;
  }
  if (isLoading(state) && state.previousData !== undefined) {
    return state.previousData;
  }
  return undefined;
}

// ============================================================================
// Exhaustiveness Helper
// ============================================================================

/**
 * Helper for exhaustive switch/if-else checks.
 * When used in the default case of a switch statement, TypeScript will
 * error if any case is not handled.
 */
export function assertNever(value: never): never {
  throw new Error(`Unexpected value: ${JSON.stringify(value)}`);
}

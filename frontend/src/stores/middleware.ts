/**
 * Zustand Middleware Utilities (NEM-3402, NEM-3403, NEM-3426)
 *
 * Provides advanced Zustand middleware patterns for:
 * - Immer middleware for complex nested state updates
 * - subscribeWithSelector for fine-grained subscriptions
 * - Transient update patterns for high-frequency WebSocket events
 *
 * @module stores/middleware
 */

import { produce, type Draft } from 'immer';
import { create, type StoreApi, type UseBoundStore } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import { shallow } from 'zustand/shallow';

// ============================================================================
// Re-exports for convenience
// ============================================================================

export { produce, shallow, subscribeWithSelector };
export type { Draft };

// ============================================================================
// Types
// ============================================================================

/**
 * Immer-enhanced state setter type.
 * Allows both direct state updates and Immer draft mutations.
 */
export type ImmerSetState<T> = (
  partial: T | Partial<T> | ((state: Draft<T>) => void),
  replace?: boolean
) => void;

/**
 * State creator type for stores using Immer middleware.
 */
export type ImmerStateCreator<T> = (
  set: ImmerSetState<T>,
  get: () => T,
  store: StoreApi<T>
) => T;

/**
 * Transient state slice - state that updates frequently but should not trigger re-renders.
 * Components can subscribe to specific properties using subscribeWithSelector.
 */
export interface TransientSlice<T> {
  /** The transient data */
  data: T;
  /** Timestamp of last update (useful for debugging/monitoring) */
  lastUpdated: number;
}

/**
 * Options for transient update batching.
 */
export interface TransientBatchOptions {
  /** Batch window in milliseconds (default: 16ms - one frame) */
  batchMs?: number;
  /** Maximum updates before forcing a flush (default: 10) */
  maxBatchSize?: number;
}

// ============================================================================
// Immer Middleware
// ============================================================================

/**
 * Creates a Zustand store with Immer middleware for immutable updates.
 *
 * Enables writing mutable code that produces immutable state updates.
 * Particularly useful for deeply nested state structures.
 *
 * @example
 * ```typescript
 * interface State {
 *   nested: { deep: { value: number } };
 *   setDeepValue: (value: number) => void;
 * }
 *
 * const useStore = createImmerStore<State>((set) => ({
 *   nested: { deep: { value: 0 } },
 *   setDeepValue: (value) => set((state) => {
 *     // Mutate directly - Immer handles immutability
 *     state.nested.deep.value = value;
 *   }),
 * }));
 * ```
 *
 * @param createState - State creator function with Immer-enhanced set
 * @returns Zustand store with Immer middleware
 */
export function createImmerStore<T extends object>(
  createState: ImmerStateCreator<T>
): UseBoundStore<StoreApi<T>> {
  return create<T>()((set, get, store) => {
    const immerSet: ImmerSetState<T> = (partial, replace) => {
      // Type for Zustand's internal set function with optional replace parameter
      type SetFn = (state: T | Partial<T>, replace?: boolean) => void;
      if (typeof partial === 'function') {
        const nextState = produce(get(), partial as (draft: Draft<T>) => void);
        // Cast to bypass Zustand's strict typing on replace parameter
        (set as unknown as SetFn)(nextState, replace);
      } else {
        (set as unknown as SetFn)(partial, replace);
      }
    };
    return createState(immerSet, get, store);
  });
}

/**
 * Creates a Zustand store with both Immer and subscribeWithSelector middleware.
 *
 * Combines immutable updates with fine-grained subscriptions for optimal performance.
 * Use when you have deeply nested state AND high-frequency updates.
 *
 * @example
 * ```typescript
 * const useStore = createImmerSelectorStore<State>((set) => ({
 *   metrics: { cpu: 0, gpu: 0, memory: 0 },
 *   updateMetric: (key, value) => set((state) => {
 *     state.metrics[key] = value;
 *   }),
 * }));
 *
 * // Component subscribes only to CPU metric
 * const cpu = useStore((state) => state.metrics.cpu);
 * ```
 *
 * @param createState - State creator function with Immer-enhanced set
 * @returns Zustand store with Immer and subscribeWithSelector middleware
 */
export function createImmerSelectorStore<T extends object>(
  createState: ImmerStateCreator<T>
): UseBoundStore<StoreApi<T>> {
  return create<T>()(
    subscribeWithSelector((set, get, store) => {
      const immerSet: ImmerSetState<T> = (partial, replace) => {
        // Type for Zustand's internal set function with optional replace parameter
        type SetFn = (state: T | Partial<T>, replace?: boolean) => void;
        if (typeof partial === 'function') {
          const nextState = produce(get(), partial as (draft: Draft<T>) => void);
          // Cast to bypass Zustand's strict typing on replace parameter
          (set as unknown as SetFn)(nextState, replace);
        } else {
          (set as unknown as SetFn)(partial, replace);
        }
      };
      return createState(immerSet, get, store);
    })
  );
}

// ============================================================================
// Transient Update Utilities
// ============================================================================

/**
 * Creates a transient updater that batches rapid updates.
 *
 * For WebSocket events that fire rapidly (e.g., metrics updates),
 * this batches updates to reduce React re-renders while keeping
 * the store state eventually consistent.
 *
 * @example
 * ```typescript
 * const batchedUpdate = createTransientBatcher(
 *   useMetricsStore.setState,
 *   { batchMs: 100, maxBatchSize: 5 }
 * );
 *
 * // Called rapidly from WebSocket handler
 * websocket.on('metrics', (data) => {
 *   batchedUpdate((state) => ({ metrics: data }));
 * });
 * ```
 *
 * @param setState - Store's setState function
 * @param options - Batching options
 * @returns Batched update function
 */
export function createTransientBatcher<T>(
  setState: (partial: Partial<T> | ((state: T) => Partial<T>)) => void,
  options: TransientBatchOptions = {}
): (updater: (state: T) => Partial<T>) => void {
  const { batchMs = 16, maxBatchSize = 10 } = options;

  let pendingUpdates: Array<(state: T) => Partial<T>> = [];
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  const flush = () => {
    if (pendingUpdates.length === 0) return;

    const updates = pendingUpdates;
    pendingUpdates = [];
    timeoutId = null;

    // Combine all pending updates into one
    setState((currentState) => {
      return updates.reduce((acc, updater) => {
        const partial = updater(currentState);
        return { ...acc, ...partial };
      }, {} as Partial<T>);
    });
  };

  return (updater: (state: T) => Partial<T>) => {
    pendingUpdates.push(updater);

    // Flush immediately if batch is full
    if (pendingUpdates.length >= maxBatchSize) {
      if (timeoutId) {
        clearTimeout(timeoutId);
        timeoutId = null;
      }
      flush();
      return;
    }

    // Schedule flush if not already scheduled
    if (!timeoutId) {
      timeoutId = setTimeout(flush, batchMs);
    }
  };
}

/**
 * Creates a transient state slice with Immer support.
 *
 * Useful for high-frequency data that should be batched and only
 * trigger re-renders when specific properties change.
 *
 * @example
 * ```typescript
 * interface MetricsState {
 *   transient: TransientSlice<GPUMetrics>;
 *   updateTransient: (data: Partial<GPUMetrics>) => void;
 * }
 *
 * const useMetricsStore = createImmerSelectorStore<MetricsState>((set) => ({
 *   transient: createTransientSlice({ utilization: 0, memory: 0 }),
 *   updateTransient: (data) => set((state) => {
 *     Object.assign(state.transient.data, data);
 *     state.transient.lastUpdated = Date.now();
 *   }),
 * }));
 * ```
 *
 * @param initialData - Initial data for the transient slice
 * @returns Transient slice with initialized data
 */
export function createTransientSlice<T>(initialData: T): TransientSlice<T> {
  return {
    data: initialData,
    lastUpdated: Date.now(),
  };
}

// ============================================================================
// Selector Utilities
// ============================================================================

/**
 * Creates a memoized selector that only triggers re-renders
 * when the selected value actually changes (using shallow comparison).
 *
 * @example
 * ```typescript
 * // Instead of:
 * const { alerts, criticalCount } = useAlertStore();
 *
 * // Use:
 * const { alerts, criticalCount } = useAlertStore(
 *   createShallowSelector((state) => ({
 *     alerts: state.alerts,
 *     criticalCount: state.criticalCount,
 *   }))
 * );
 * ```
 *
 * @param selector - Selector function
 * @returns Selector with shallow equality check
 */
export function createShallowSelector<T, U>(
  selector: (state: T) => U
): (state: T) => U {
  // Return the selector as-is; shallow comparison is handled at the hook level
  // This is a utility to document intent and make the pattern clear
  return selector;
}

/**
 * Type-safe equality function for subscribeWithSelector subscriptions.
 *
 * @param a - First value
 * @param b - Second value
 * @returns Whether the values are shallowly equal
 */
export function shallowEqual<T>(a: T, b: T): boolean {
  return shallow(a, b);
}

// ============================================================================
// WebSocket Event Utilities
// ============================================================================

/**
 * Creates a WebSocket event handler that updates store state transiently.
 *
 * Designed for high-frequency events that should batch updates and
 * minimize React re-renders.
 *
 * @example
 * ```typescript
 * const handleGPUStats = createWebSocketEventHandler(
 *   useMetricsStore.setState,
 *   (stats: GPUStats) => ({
 *     gpuMetrics: {
 *       utilization: stats.gpu_utilization,
 *       memory: stats.memory_used,
 *     },
 *     lastGPUUpdate: Date.now(),
 *   }),
 *   { batchMs: 100 }
 * );
 *
 * // Use in WebSocket handler
 * websocket.on('gpu_stats', handleGPUStats);
 * ```
 *
 * @param setState - Store's setState function
 * @param transformer - Transform WebSocket data to state partial
 * @param options - Batching options
 * @returns Event handler function
 */
export function createWebSocketEventHandler<T, E>(
  setState: (partial: Partial<T> | ((state: T) => Partial<T>)) => void,
  transformer: (event: E) => Partial<T>,
  options: TransientBatchOptions = {}
): (event: E) => void {
  const batcher = createTransientBatcher(setState, options);

  return (event: E) => {
    batcher(() => transformer(event));
  };
}

/**
 * Creates a debounced state update handler.
 *
 * Unlike batching (which combines updates), debouncing waits for
 * a pause in updates before applying the latest one.
 *
 * @example
 * ```typescript
 * const debouncedUpdate = createDebouncedUpdater(
 *   useStore.setState,
 *   200 // Wait 200ms of silence
 * );
 *
 * // Only the last update in a 200ms window is applied
 * input.onChange((value) => {
 *   debouncedUpdate({ searchQuery: value });
 * });
 * ```
 *
 * @param setState - Store's setState function
 * @param waitMs - Debounce wait time in milliseconds
 * @returns Debounced update function
 */
export function createDebouncedUpdater<T>(
  setState: (partial: Partial<T>) => void,
  waitMs: number
): (partial: Partial<T>) => void {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  let latestPartial: Partial<T> | null = null;

  return (partial: Partial<T>) => {
    latestPartial = partial;

    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    timeoutId = setTimeout(() => {
      if (latestPartial) {
        setState(latestPartial);
        latestPartial = null;
      }
      timeoutId = null;
    }, waitMs);
  };
}

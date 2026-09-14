/**
 * Auto-Selectors Utility for Zustand Stores (NEM-3787)
 *
 * Creates auto-generated selectors for Zustand stores to prevent unnecessary re-renders.
 * Instead of subscribing to the entire store, components can use individual property selectors
 * that only trigger re-renders when that specific property changes.
 *
 * @module utils/createSelectors
 */

import type { StoreApi, UseBoundStore } from 'zustand';

/**
 * Extended store type with auto-generated selectors.
 *
 * Adds a `use` object that contains selector hooks for each state property.
 * Each selector returns only that property and causes re-renders only when
 * that specific property changes.
 */
export type WithSelectors<S> = S extends { getState: () => infer T }
  ? S & { use: { [K in keyof T]: () => T[K] } }
  : never;

/**
 * Creates auto-generated selectors for a Zustand store.
 *
 * This utility wraps a Zustand store and adds a `use` object containing
 * individual selector hooks for each property in the store state.
 * This enables fine-grained subscriptions that prevent unnecessary re-renders.
 *
 * Benefits:
 * - Automatic memoization: Components only re-render when their selected value changes
 * - Type-safe: All selectors are fully typed based on the store state
 * - Clean API: Simple `.use.propertyName()` syntax
 * - Zero boilerplate: No need to manually create selectors for each property
 *
 * @example
 * ```typescript
 * // Define your store
 * const useEventStoreBase = create<EventState>()((set) => ({
 *   events: [],
 *   filters: { riskLevel: null },
 *   selectedEventId: null,
 *   setFilters: (filters) => set({ filters }),
 *   setSelectedEventId: (id) => set({ selectedEventId: id }),
 * }));
 *
 * // Create auto-selectors
 * export const useEventStore = createSelectors(useEventStoreBase);
 *
 * // Usage in components - only re-renders when events change
 * const events = useEventStore.use.events();
 *
 * // Only re-renders when filters change
 * const filters = useEventStore.use.filters();
 *
 * // Actions are also accessible via selectors (stable references)
 * const setFilters = useEventStore.use.setFilters();
 *
 * // Traditional usage still works
 * const { events, filters } = useEventStore();
 * ```
 *
 * @param store - The base Zustand store to enhance
 * @returns The enhanced store with auto-generated selectors
 */
export function createSelectors<S extends UseBoundStore<StoreApi<object>>>(
  store: S
): WithSelectors<S> {
  // Get the initial state to determine available keys
  const state = store.getState();

  // Create the use object with selector hooks for each key
  const use = {} as Record<string, () => unknown>;

  for (const key of Object.keys(state)) {
    // Create a selector hook for each property
    // Each selector subscribes only to that specific property
    use[key] = () => store((s) => s[key as keyof typeof s]);
  }

  // Extend the store with the use object
  const storeWithSelectors = store as WithSelectors<S>;
  storeWithSelectors.use = use as WithSelectors<S>['use'];

  return storeWithSelectors;
}

/**
 * Type helper to extract the state type from a store with selectors.
 *
 * @example
 * ```typescript
 * type EventState = ExtractState<typeof useEventStore>;
 * ```
 */
export type ExtractState<S> = S extends { getState: () => infer T } ? T : never;

/**
 * Type helper to get the selector keys from a store with selectors.
 *
 * @example
 * ```typescript
 * type EventSelectors = SelectorKeys<typeof useEventStore>;
 * // 'events' | 'filters' | 'selectedEventId' | 'setFilters' | ...
 * ```
 */
export type SelectorKeys<S> = S extends { use: infer U } ? keyof U : never;

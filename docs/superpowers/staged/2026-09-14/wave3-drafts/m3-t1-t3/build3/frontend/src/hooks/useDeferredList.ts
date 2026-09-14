/**
 * useDeferredList - React 19 performance optimization hook for large list rendering
 *
 * Uses useDeferredValue to defer expensive list rendering operations, allowing the UI
 * to remain responsive while the list is being updated. This is particularly useful for:
 * - Large lists with complex item rendering
 * - Lists that update frequently (e.g., real-time data)
 * - Filtered/sorted lists where the transformation is expensive
 *
 * @module hooks/useDeferredList
 * @see https://react.dev/reference/react/useDeferredValue
 */

import { useDeferredValue, useMemo } from 'react';

/**
 * Options for useDeferredList hook
 */
export interface UseDeferredListOptions<T> {
  /**
   * The items to render
   */
  items: T[];

  /**
   * Minimum number of items before deferring kicks in.
   * Below this threshold, rendering happens synchronously.
   * @default 50
   */
  deferThreshold?: number;

  /**
   * Whether to skip deferred rendering and use immediate values.
   * Useful for testing or when deferring is unnecessary.
   * @default false
   */
  skipDefer?: boolean;
}

/**
 * Return type for useDeferredList hook
 */
export interface UseDeferredListResult<T> {
  /**
   * The items to render (may be stale while transition is pending)
   */
  deferredItems: T[];

  /**
   * Whether the displayed items are stale (deferred value differs from current)
   */
  isStale: boolean;

  /**
   * The count of items currently being displayed
   */
  displayCount: number;

  /**
   * The total count of items (may differ from displayCount when stale)
   */
  totalCount: number;
}

/**
 * Hook that defers large list updates using React 19's useDeferredValue.
 *
 * This hook is designed to keep the UI responsive when rendering large lists.
 * The list updates are deferred with lower priority, allowing user interactions
 * to remain snappy while the list is being re-rendered.
 *
 * @example
 * ```tsx
 * function EventList({ events }: { events: Event[] }) {
 *   const { deferredItems, isStale } = useDeferredList({
 *     items: events,
 *     deferThreshold: 100,
 *   });
 *
 *   return (
 *     <div className={isStale ? 'opacity-70' : ''}>
 *       {deferredItems.map(event => (
 *         <EventCard key={event.id} event={event} />
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 *
 * @param options - Configuration options for the list
 * @returns Deferred items and stale state
 */
export function useDeferredList<T>(options: UseDeferredListOptions<T>): UseDeferredListResult<T> {
  const { items, deferThreshold = 50, skipDefer = false } = options;

  // Determine if we should use deferred value based on item count
  const shouldDefer = !skipDefer && items.length >= deferThreshold;

  // Defer the items array to allow React to prioritize user input
  // This is the key React 19 optimization - list updates are deferred
  // so interactions remain responsive even with large lists
  const deferredItems = useDeferredValue(items);

  // Check if we're showing stale data
  const isStale = shouldDefer && items !== deferredItems;

  // Memoize the result to prevent unnecessary re-renders
  const result = useMemo(
    () => ({
      deferredItems: shouldDefer ? deferredItems : items,
      isStale,
      displayCount: shouldDefer ? deferredItems.length : items.length,
      totalCount: items.length,
    }),
    [shouldDefer, deferredItems, items, isStale]
  );

  return result;
}

export default useDeferredList;

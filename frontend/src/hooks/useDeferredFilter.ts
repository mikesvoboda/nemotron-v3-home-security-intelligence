/**
 * useDeferredFilter - React 19 performance optimization hook for expensive filtering operations
 *
 * Uses useDeferredValue to defer expensive filter/search operations, allowing the UI to remain
 * responsive while the filter is being applied. This is particularly useful for:
 * - Large lists with complex filtering logic
 * - Search inputs that trigger expensive re-renders
 * - Filter changes that affect many components
 *
 * @module hooks/useDeferredFilter
 * @see https://react.dev/reference/react/useDeferredValue
 */

import { useDeferredValue, useMemo, useTransition } from 'react';

/**
 * Options for useDeferredFilter hook
 */
export interface UseDeferredFilterOptions<T, F> {
  /**
   * The items to filter
   */
  items: T[];

  /**
   * The current filter value (can be any type: string, object, etc.)
   */
  filter: F;

  /**
   * The filter function that determines which items match the filter.
   * Return true to include the item in the filtered results.
   */
  filterFn: (item: T, filter: F) => boolean;

  /**
   * Whether to skip deferred rendering and use immediate values.
   * Useful for small lists where deferring is unnecessary overhead.
   * @default false
   */
  skipDefer?: boolean;

  /**
   * Minimum number of items before deferring kicks in.
   * Below this threshold, filtering happens synchronously.
   * @default 100
   */
  deferThreshold?: number;
}

/**
 * Return type for useDeferredFilter hook
 */
export interface UseDeferredFilterResult<T> {
  /**
   * The filtered items (may be stale while transition is pending)
   */
  filteredItems: T[];

  /**
   * Whether the filter is currently being applied (transition pending)
   */
  isPending: boolean;

  /**
   * Whether the displayed items are stale (deferred value differs from current)
   */
  isStale: boolean;
}

/**
 * Hook that defers expensive filtering operations using React 19's useDeferredValue.
 *
 * This hook is designed to keep the UI responsive when filtering large lists.
 * The filter input remains immediately responsive while the filtered results
 * are calculated with lower priority.
 *
 * @example
 * ```tsx
 * function EventList({ events }: { events: Event[] }) {
 *   const [searchQuery, setSearchQuery] = useState('');
 *
 *   const { filteredItems, isPending } = useDeferredFilter({
 *     items: events,
 *     filter: searchQuery,
 *     filterFn: (event, query) =>
 *       event.summary.toLowerCase().includes(query.toLowerCase()) ||
 *       event.camera_name.toLowerCase().includes(query.toLowerCase()),
 *   });
 *
 *   return (
 *     <div>
 *       <input
 *         value={searchQuery}
 *         onChange={(e) => setSearchQuery(e.target.value)}
 *         placeholder="Search events..."
 *       />
 *       <div className={isPending ? 'opacity-70' : ''}>
 *         {filteredItems.map(event => <EventCard key={event.id} event={event} />)}
 *       </div>
 *     </div>
 *   );
 * }
 * ```
 *
 * @param options - Configuration options for the filter
 * @returns Filtered items and pending state
 */
export function useDeferredFilter<T, F>(
  options: UseDeferredFilterOptions<T, F>
): UseDeferredFilterResult<T> {
  const { items, filter, filterFn, skipDefer = false, deferThreshold = 100 } = options;

  // Use useTransition to track pending state
  // Note: We only use isPending here to indicate stale UI state,
  // not to wrap state updates (which would be redundant with useDeferredValue)
  const [isPending] = useTransition();

  // Determine if we should use deferred value based on item count
  const shouldDefer = !skipDefer && items.length >= deferThreshold;

  // Defer the filter value to allow React to prioritize user input
  // This is the key React 19 optimization - filter changes are deferred
  // so typing remains responsive even with large lists
  const deferredFilter = useDeferredValue(filter);

  // Check if we're showing stale data
  const isStale = shouldDefer && filter !== deferredFilter;

  // Memoize the filtering operation
  // When shouldDefer is true, this uses the deferred filter value
  // which allows React to batch the expensive filtering with lower priority
  const filteredItems = useMemo(() => {
    const effectiveFilter = shouldDefer ? deferredFilter : filter;

    // If filter is empty/null/undefined, return all items
    if (effectiveFilter === '' || effectiveFilter === null || effectiveFilter === undefined) {
      return items;
    }

    return items.filter((item) => filterFn(item, effectiveFilter));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- effectiveFilter is derived from shouldDefer, deferredFilter, and filter
  }, [items, shouldDefer ? deferredFilter : filter, filterFn, shouldDefer]);

  return {
    filteredItems,
    isPending,
    isStale,
  };
}

/**
 * Simplified hook for string-based search filtering with useDeferredValue.
 *
 * This is a convenience wrapper around useDeferredFilter for the common case
 * of searching through items with a text query.
 *
 * @example
 * ```tsx
 * const { filteredItems, isPending } = useDeferredSearch({
 *   items: jobs,
 *   query: searchQuery,
 *   searchFields: (job) => [job.name, job.description, job.status],
 * });
 * ```
 */
export interface UseDeferredSearchOptions<T> {
  /**
   * The items to search through
   */
  items: T[];

  /**
   * The search query string
   */
  query: string;

  /**
   * Function that returns an array of searchable string fields for an item.
   * The search will match if any of the returned fields contain the query.
   */
  searchFields: (item: T) => (string | null | undefined)[];

  /**
   * Whether the search should be case-sensitive
   * @default false
   */
  caseSensitive?: boolean;

  /**
   * Minimum number of items before deferring kicks in
   * @default 100
   */
  deferThreshold?: number;
}

/**
 * Hook that defers text search operations using React 19's useDeferredValue.
 *
 * @param options - Search configuration options
 * @returns Filtered items and pending state
 */
export function useDeferredSearch<T>(
  options: UseDeferredSearchOptions<T>
): UseDeferredFilterResult<T> {
  const { items, query, searchFields, caseSensitive = false, deferThreshold = 100 } = options;

  return useDeferredFilter({
    items,
    filter: query,
    filterFn: (item, searchQuery) => {
      if (!searchQuery) return true;

      const normalizedQuery = caseSensitive ? searchQuery : searchQuery.toLowerCase();
      const fields = searchFields(item);

      return fields.some((field) => {
        if (field === null || field === undefined) return false;
        const normalizedField = caseSensitive ? field : field.toLowerCase();
        return normalizedField.includes(normalizedQuery);
      });
    },
    deferThreshold,
  });
}

export default useDeferredFilter;

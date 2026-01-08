/**
 * Group items by a key selector function.
 *
 * Uses native Object.groupBy when available (Node 21+, Chrome 117+, Firefox 119+)
 * with a fallback implementation for older environments.
 *
 * @param items - Array of items to group
 * @param keySelector - Function to extract the grouping key from each item
 * @returns Object with keys as group identifiers and values as arrays of items
 *
 * @example
 * ```typescript
 * const events = [
 *   { id: 1, risk_level: 'high' },
 *   { id: 2, risk_level: 'low' },
 *   { id: 3, risk_level: 'high' },
 * ];
 *
 * const grouped = groupBy(events, (e) => e.risk_level);
 * // { high: [{ id: 1, ... }, { id: 3, ... }], low: [{ id: 2, ... }] }
 * ```
 */
export function groupBy<T, K extends PropertyKey>(
  items: T[],
  keySelector: (item: T) => K
): Partial<Record<K, T[]>> {
  // Use native Object.groupBy if available (Node 21+, Chrome 117+, Firefox 119+)
  if ('groupBy' in Object && typeof (Object as ObjectWithGroupBy).groupBy === 'function') {
    return (Object as ObjectWithGroupBy).groupBy(items, keySelector);
  }

  // Fallback implementation for older environments
  return items.reduce(
    (groups, item) => {
      const key = keySelector(item);
      (groups[key] ??= []).push(item);
      return groups;
    },
    {} as Partial<Record<K, T[]>>
  );
}

/**
 * Count items by group using groupBy.
 *
 * A convenience function that groups items and returns the count per group
 * instead of the grouped arrays.
 *
 * @param items - Array of items to count by group
 * @param keySelector - Function to extract the grouping key from each item
 * @returns Object with keys as group identifiers and values as counts
 *
 * @example
 * ```typescript
 * const events = [
 *   { id: 1, risk_level: 'high' },
 *   { id: 2, risk_level: 'low' },
 *   { id: 3, risk_level: 'high' },
 * ];
 *
 * const counts = countBy(events, (e) => e.risk_level);
 * // { high: 2, low: 1 }
 * ```
 */
export function countBy<T, K extends PropertyKey>(
  items: T[],
  keySelector: (item: T) => K
): Partial<Record<K, number>> {
  const groups = groupBy(items, keySelector);
  const counts: Partial<Record<K, number>> = {};

  for (const key in groups) {
    if (Object.prototype.hasOwnProperty.call(groups, key)) {
      counts[key as K] = groups[key as K]?.length ?? 0;
    }
  }

  return counts;
}

/**
 * Type declaration for Object.groupBy (ES2024)
 * @internal
 */
interface ObjectWithGroupBy {
  groupBy<T, K extends PropertyKey>(
    items: Iterable<T>,
    keySelector: (item: T, index: number) => K
  ): Partial<Record<K, T[]>>;
}

/**
 * Functional pipeline utilities for composable data transformations.
 *
 * This module provides a declarative approach to data transformation using
 * function composition. Instead of imperative loops and mutations, use
 * pipelines to express intent clearly.
 *
 * @example
 * ```typescript
 * import { pipe, filterByQuery, sortByDate, take } from './pipeline';
 *
 * // Compose transforms into a reusable pipeline
 * const filteredEvents = pipe(
 *   filterByQuery(searchQuery),
 *   sortByDate('desc'),
 *   take(20)
 * )(events);
 * ```
 *
 * @module pipeline
 */

// ============================================================================
// Types
// ============================================================================

/**
 * A transform function that takes an array and returns a transformed array.
 * All transforms must be pure functions that do not mutate the input.
 */
export type Transform<T> = (data: T[]) => T[];

/**
 * Base type constraints for event-like objects.
 * Used to constrain generic types in transform functions.
 */
export interface EventLike {
  summary?: string | null;
  started_at: string;
  risk_score?: number | null;
}

// ============================================================================
// Core Pipeline Function
// ============================================================================

/**
 * Composes multiple transform functions into a single pipeline.
 *
 * Transforms are applied left-to-right, with each transform receiving
 * the output of the previous transform. This creates a declarative,
 * readable data processing flow.
 *
 * @param transforms - Transform functions to compose
 * @returns A composed transform function
 *
 * @example
 * ```typescript
 * // Single transform
 * const sorted = pipe(sortByDate('desc'))(events);
 *
 * // Multiple transforms
 * const processed = pipe(
 *   filterByQuery('person'),
 *   sortByRisk('desc'),
 *   take(10)
 * )(events);
 *
 * // No transforms (identity)
 * const unchanged = pipe()(events);
 * ```
 */
export function pipe<T>(...transforms: Transform<T>[]): Transform<T> {
  return (data: T[]) => transforms.reduce((acc, fn) => fn(acc), data);
}

// ============================================================================
// Filter Transforms
// ============================================================================

/**
 * Creates a transform that filters events by summary text.
 *
 * The search is case-insensitive and matches any substring.
 * Events without a summary are excluded when a query is provided,
 * but included when the query is empty.
 *
 * @param query - Search query (case-insensitive)
 * @returns Transform function that filters by query
 *
 * @example
 * ```typescript
 * // Filter events containing "person"
 * const withPerson = filterByQuery('person')(events);
 *
 * // Empty query returns all events
 * const allEvents = filterByQuery('')(events);
 * ```
 */
export const filterByQuery = <T extends { summary?: string | null }>(
  query: string
): Transform<T> => {
  const trimmedQuery = query.trim().toLowerCase();

  return (events: T[]) => {
    if (!trimmedQuery) {
      return events;
    }

    return events.filter((event) => {
      const summary = event.summary;
      if (!summary) {
        return false;
      }
      return summary.toLowerCase().includes(trimmedQuery);
    });
  };
};

// ============================================================================
// Sort Transforms
// ============================================================================

/**
 * Creates a transform that sorts events by date.
 *
 * Uses stable sort to preserve original order for equal timestamps.
 * Does not mutate the input array.
 *
 * @param order - Sort order: 'asc' (oldest first) or 'desc' (newest first)
 * @returns Transform function that sorts by date
 *
 * @example
 * ```typescript
 * // Newest events first
 * const newest = sortByDate('desc')(events);
 *
 * // Oldest events first
 * const oldest = sortByDate('asc')(events);
 * ```
 */
export const sortByDate = <T extends { started_at: string }>(
  order: 'asc' | 'desc'
): Transform<T> => {
  return (events: T[]) => {
    // Create a copy to avoid mutation
    return [...events].sort((a, b) => {
      const timeA = new Date(a.started_at).getTime();
      const timeB = new Date(b.started_at).getTime();
      const diff = timeA - timeB;
      return order === 'asc' ? diff : -diff;
    });
  };
};

/**
 * Creates a transform that sorts events by risk score.
 *
 * Treats undefined or null risk_score as 0.
 * Uses stable sort to preserve original order for equal scores.
 * Does not mutate the input array.
 *
 * @param order - Sort order: 'asc' (lowest first) or 'desc' (highest first)
 * @returns Transform function that sorts by risk score
 *
 * @example
 * ```typescript
 * // Highest risk first
 * const highRisk = sortByRisk('desc')(events);
 *
 * // Lowest risk first
 * const lowRisk = sortByRisk('asc')(events);
 * ```
 */
export const sortByRisk = <T extends { risk_score?: number | null }>(
  order: 'asc' | 'desc'
): Transform<T> => {
  return (events: T[]) => {
    // Create a copy to avoid mutation
    return [...events].sort((a, b) => {
      const scoreA = a.risk_score ?? 0;
      const scoreB = b.risk_score ?? 0;
      const diff = scoreA - scoreB;
      return order === 'asc' ? diff : -diff;
    });
  };
};

// ============================================================================
// Pagination Transforms
// ============================================================================

/**
 * Creates a transform that takes the first n items.
 *
 * Useful for pagination or limiting results.
 *
 * @param n - Number of items to take
 * @returns Transform function that takes first n items
 *
 * @example
 * ```typescript
 * // Get first 10 events
 * const firstTen = take(10)(events);
 * ```
 */
export const take = <T>(n: number): Transform<T> => {
  return (data: T[]) => data.slice(0, n);
};

/**
 * Creates a transform that skips the first n items.
 *
 * Useful for pagination offset.
 *
 * @param n - Number of items to skip
 * @returns Transform function that skips first n items
 *
 * @example
 * ```typescript
 * // Skip first 20 events (for page 2)
 * const afterTwenty = skip(20)(events);
 * ```
 */
export const skip = <T>(n: number): Transform<T> => {
  return (data: T[]) => data.slice(n);
};

// ============================================================================
// Utility Transforms
// ============================================================================

/**
 * Identity transform that returns the input unchanged.
 *
 * Useful for conditional transforms where you may or may not want
 * to apply a transformation.
 *
 * @param data - Input array
 * @returns Same array (unchanged)
 *
 * @example
 * ```typescript
 * // Conditionally apply filter
 * const transform = searchQuery ? filterByQuery(searchQuery) : identity;
 * const result = transform(events);
 * ```
 */
export const identity = <T>(data: T[]): T[] => data;

// ============================================================================
// Sort Option Helpers for EventTimeline
// ============================================================================

/**
 * Sort option type matching EventTimeline component.
 */
export type SortOption = 'newest' | 'oldest' | 'risk_high' | 'risk_low';

/**
 * Creates a sort transform based on sort option string.
 *
 * Maps user-friendly sort options to appropriate sort transforms.
 * This is a convenience function for EventTimeline integration.
 *
 * @param option - Sort option from dropdown
 * @returns Appropriate sort transform
 *
 * @example
 * ```typescript
 * const sortTransform = getSortTransform('risk_high');
 * const sorted = sortTransform(events);
 * ```
 */
export const getSortTransform = <T extends { started_at: string; risk_score?: number | null }>(
  option: SortOption
): Transform<T> => {
  switch (option) {
    case 'newest':
      return sortByDate<T>('desc');
    case 'oldest':
      return sortByDate<T>('asc');
    case 'risk_high':
      return sortByRisk<T>('desc');
    case 'risk_low':
      return sortByRisk<T>('asc');
    default:
      return identity;
  }
};

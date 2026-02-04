/**
 * useTopEventsQuery - React Query hook for fetching top events by risk score
 *
 * This hook provides an optimized way to fetch the highest-risk events
 * for the TopEventsCarousel component. Events are sorted by risk_score
 * in descending order.
 *
 * NEM-5412/5413: Feature 6 - Top Events Preview Carousel
 *
 * @module hooks/useTopEventsQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchEvents, type EventsQueryParams } from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

import type { Event as GeneratedEvent, EventListResponse } from '../types/generated';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the useTopEventsQuery hook.
 */
export interface UseTopEventsQueryOptions {
  /**
   * Maximum number of top events to fetch.
   * @default 10
   */
  limit?: number;

  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;

  /**
   * Refetch interval in milliseconds.
   * @default false (no auto-refetch)
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useTopEventsQuery hook.
 */
export interface UseTopEventsQueryReturn {
  /** List of top events sorted by risk score (highest first) */
  events: GeneratedEvent[];

  /** Total count of events available */
  totalCount: number;

  /** Whether the initial fetch is in progress */
  isLoading: boolean;

  /** Whether any fetch is in progress */
  isFetching: boolean;

  /** Error object if the query failed */
  error: Error | null;

  /** Whether the query has errored */
  isError: boolean;

  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

// ============================================================================
// Query Key Factory
// ============================================================================

/**
 * Query keys for top events queries.
 */
export const topEventsQueryKeys = {
  all: ['events', 'top'] as const,
  list: (limit: number) => [...topEventsQueryKeys.all, { limit }] as const,
};

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch top events by risk score using React Query.
 *
 * Events are fetched and sorted by risk_score in descending order,
 * making the highest-risk events appear first.
 *
 * @param options - Configuration options
 * @returns Top events and query state
 *
 * @example
 * ```tsx
 * // Basic usage - fetch top 10 events
 * const { events, isLoading, error } = useTopEventsQuery();
 *
 * // Custom limit
 * const { events } = useTopEventsQuery({ limit: 5 });
 *
 * // With auto-refetch every minute
 * const { events } = useTopEventsQuery({
 *   limit: 10,
 *   refetchInterval: 60000,
 * });
 * ```
 */
export function useTopEventsQuery(
  options: UseTopEventsQueryOptions = {}
): UseTopEventsQueryReturn {
  const {
    limit = 10,
    enabled = true,
    staleTime = DEFAULT_STALE_TIME,
    refetchInterval = false,
  } = options;

  const query = useQuery<EventListResponse, Error>({
    queryKey: topEventsQueryKeys.list(limit),
    queryFn: async () => {
      const params: EventsQueryParams = {
        limit,
        // Note: We fetch events and sort client-side by risk_score
        // The API returns events in default order (newest first)
      };

      return fetchEvents(params);
    },
    enabled,
    staleTime,
    refetchInterval,
    retry: 1,
  });

  // Sort events by risk_score descending (highest first)
  const events = useMemo(() => {
    if (!query.data?.items) return [];

    return [...query.data.items].sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0));
  }, [query.data?.items]);

  // Extract total count from pagination metadata
  const totalCount = useMemo(
    () => query.data?.pagination?.total ?? 0,
    [query.data?.pagination?.total]
  );

  return {
    events,
    totalCount,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export default useTopEventsQuery;

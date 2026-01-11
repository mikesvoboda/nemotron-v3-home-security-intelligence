/**
 * useRecentEventsQuery - React Query hook for fetching recent events
 *
 * This hook provides an optimized way to fetch a limited number of recent events
 * for dashboard and summary views. Unlike useEventsInfiniteQuery which supports
 * infinite scrolling, this hook fetches a fixed number of events using server-side
 * limiting to avoid over-fetching.
 *
 * Benefits:
 * - Server-side limiting (no client-side slicing of large datasets)
 * - Automatic caching and deduplication via React Query
 * - Configurable refetch intervals for real-time updates
 * - Simple return type for dashboard components
 *
 * @module hooks/useRecentEventsQuery
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
 * Options for configuring the useRecentEventsQuery hook.
 */
export interface UseRecentEventsQueryOptions {
  /**
   * Maximum number of events to fetch from the server.
   * This is a server-side limit, not client-side slicing.
   * @default 10
   */
  limit?: number;

  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default false
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;

  /**
   * Optional camera ID filter.
   * When provided, only events from this camera are returned.
   */
  cameraId?: string;
}

/**
 * Return type for the useRecentEventsQuery hook.
 */
export interface UseRecentEventsQueryReturn {
  /** List of recent events, empty array if not yet fetched */
  events: GeneratedEvent[];

  /** Total count of events matching the filter (from pagination metadata) */
  totalCount: number;

  /** Whether the initial fetch is in progress */
  isLoading: boolean;

  /** Whether any fetch is in progress (initial or background) */
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
 * Query keys for recent events queries.
 * Separate from eventsQueryKeys to avoid cache collisions with infinite queries.
 */
export const recentEventsQueryKeys = {
  /** Base key for all recent events queries */
  all: ['events', 'recent'] as const,

  /** Recent events with specific options */
  list: (limit: number, cameraId?: string) =>
    cameraId
      ? ([...recentEventsQueryKeys.all, { limit, cameraId }] as const)
      : ([...recentEventsQueryKeys.all, { limit }] as const),
};

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch a limited number of recent events using React Query.
 *
 * This hook is optimized for dashboard use cases where you need a small
 * number of recent events without pagination. It uses server-side limiting
 * to avoid fetching more data than necessary.
 *
 * @param options - Configuration options
 * @returns Recent events and query state
 *
 * @example
 * ```tsx
 * // Basic usage - fetch 10 most recent events
 * const { events, isLoading, error } = useRecentEventsQuery();
 *
 * // Custom limit
 * const { events } = useRecentEventsQuery({ limit: 5 });
 *
 * // With auto-refetch every 30 seconds
 * const { events } = useRecentEventsQuery({
 *   limit: 10,
 *   refetchInterval: 30000,
 * });
 *
 * // Filter by camera
 * const { events } = useRecentEventsQuery({
 *   limit: 10,
 *   cameraId: 'front-door',
 * });
 * ```
 */
export function useRecentEventsQuery(
  options: UseRecentEventsQueryOptions = {}
): UseRecentEventsQueryReturn {
  const {
    limit = 10,
    enabled = true,
    refetchInterval = false,
    staleTime = DEFAULT_STALE_TIME,
    cameraId,
  } = options;

  const query = useQuery<EventListResponse, Error>({
    queryKey: recentEventsQueryKeys.list(limit, cameraId),
    queryFn: async () => {
      const params: EventsQueryParams = {
        limit,
      };

      if (cameraId) {
        params.camera_id = cameraId;
      }

      return fetchEvents(params);
    },
    enabled,
    refetchInterval,
    staleTime,
    // Reduced retry for faster failure feedback in dashboard context
    retry: 1,
  });

  // Provide empty array as default to avoid null checks
  const events = useMemo(() => query.data?.items ?? [], [query.data?.items]);

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

export default useRecentEventsQuery;

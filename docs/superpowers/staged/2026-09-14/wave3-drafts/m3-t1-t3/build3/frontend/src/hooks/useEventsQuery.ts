/**
 * React Query hooks for fetching events with cursor-based pagination.
 *
 * Uses the generic createInfiniteQueryHook factory to reduce boilerplate
 * while maintaining full type safety and backwards compatibility.
 */

import { createInfiniteQueryHook, type BaseInfiniteQueryOptions } from './useCursorPaginatedQuery';
import { fetchEvents, type EventsQueryParams } from '../services/api';

import type { EventListResponse } from '../types/generated';

export interface EventFilters {
  camera_id?: string;
  risk_level?: string;
  start_date?: string;
  end_date?: string;
  reviewed?: boolean;
  object_type?: string;
  /** Include soft-deleted events in results (NEM-3589) */
  include_deleted?: boolean;
}

export interface UseEventsInfiniteQueryOptions extends BaseInfiniteQueryOptions {
  filters?: EventFilters;
}

/**
 * Return type for useEventsInfiniteQuery.
 * Maintains backwards compatibility by using 'events' instead of 'items'.
 */
export interface UseEventsInfiniteQueryReturn {
  events: EventListResponse['items'];
  pages: EventListResponse[] | undefined;
  totalCount: number;
  isLoading: boolean;
  isFetching: boolean;
  isFetchingNextPage: boolean;
  hasNextPage: boolean;
  fetchNextPage: () => void;
  error: Error | null;
  isError: boolean;
  refetch: () => void;
}

export const eventsQueryKeys = {
  all: ['events'] as const,
  lists: () => [...eventsQueryKeys.all, 'list'] as const,
  list: (filters?: EventFilters) => [...eventsQueryKeys.lists(), filters] as const,
  infinite: (filters?: EventFilters, limit?: number) =>
    [...eventsQueryKeys.all, 'infinite', { filters, limit }] as const,
  detail: (id: number) => [...eventsQueryKeys.all, 'detail', id] as const,
};

/**
 * Internal hook created by factory function.
 * Returns the standardized InfiniteQueryHookReturn interface.
 */
const useEventsInfiniteQueryInternal = createInfiniteQueryHook<
  EventListResponse,
  EventListResponse['items'][number],
  UseEventsInfiniteQueryOptions,
  EventFilters
>({
  getQueryKey: (options) => eventsQueryKeys.infinite(options.filters, options.limit),
  fetchFn: ({ cursor, limit, filters }) => {
    const params: EventsQueryParams = {
      ...filters,
      limit,
      cursor,
    };
    return fetchEvents(params);
  },
  getFilters: (options) => options.filters,
  defaultRetry: 1, // Default to 1 retry for faster failure feedback in list views
  defaultMaxPages: 15, // Limit stored pages for bounded memory (NEM-3362)
});

/**
 * Hook for fetching events with cursor-based infinite pagination.
 *
 * Wraps the factory-generated hook to maintain backwards compatibility
 * by renaming 'items' to 'events' in the return type.
 *
 * @param options - Query options including filters, limit, and React Query options
 * @returns Events data with pagination controls and query state
 */
export function useEventsInfiniteQuery(
  options: UseEventsInfiniteQueryOptions = {}
): UseEventsInfiniteQueryReturn {
  const result = useEventsInfiniteQueryInternal(options);

  // Rename 'items' to 'events' for backwards compatibility
  return {
    events: result.items,
    pages: result.pages,
    totalCount: result.totalCount,
    isLoading: result.isLoading,
    isFetching: result.isFetching,
    isFetchingNextPage: result.isFetchingNextPage,
    hasNextPage: result.hasNextPage,
    fetchNextPage: result.fetchNextPage,
    error: result.error,
    isError: result.isError,
    refetch: result.refetch,
  };
}

export default useEventsInfiniteQuery;

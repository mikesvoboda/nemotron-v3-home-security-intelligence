/**
 * React Query hooks for fetching events with cursor-based pagination.
 */

import { useMemo } from 'react';

import { useCursorPaginatedQuery } from './useCursorPaginatedQuery';
import { fetchEvents, type EventsQueryParams } from '../services/api';

import type { EventListResponse } from '../types/generated';

export interface EventFilters {
  camera_id?: string;
  risk_level?: string;
  start_date?: string;
  end_date?: string;
  reviewed?: boolean;
  object_type?: string;
}

export interface UseEventsInfiniteQueryOptions {
  filters?: EventFilters;
  limit?: number;
  enabled?: boolean;
  staleTime?: number;
  refetchInterval?: number | false;
}

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

export function useEventsInfiniteQuery(
  options: UseEventsInfiniteQueryOptions = {}
): UseEventsInfiniteQueryReturn {
  const {
    filters,
    limit = 50,
    enabled = true,
    staleTime,
    refetchInterval,
  } = options;

  const query = useCursorPaginatedQuery<EventListResponse, EventFilters>({
    queryKey: eventsQueryKeys.infinite(filters, limit),
    queryFn: ({ cursor, filters: queryFilters }) => {
      const params: EventsQueryParams = {
        ...queryFilters,
        limit,
        cursor,
      };
      return fetchEvents(params);
    },
    filters,
    enabled,
    staleTime,
    refetchInterval,
  });

  const events = useMemo(() => {
    if (!query.data?.pages) {
      return [];
    }
    return query.data.pages.flatMap((page) => page.items);
  }, [query.data?.pages]);

  const totalCount = useMemo(() => {
    if (!query.data?.pages?.[0]) {
      return 0;
    }
    return query.data.pages[0].pagination.total;
  }, [query.data?.pages]);

  return {
    events,
    pages: query.data?.pages,
    totalCount,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isFetchingNextPage: query.isFetchingNextPage,
    hasNextPage: query.hasNextPage,
    fetchNextPage: query.fetchNextPage,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export default useEventsInfiniteQuery;

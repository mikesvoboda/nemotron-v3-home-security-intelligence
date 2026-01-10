/**
 * React Query hooks for fetching detections with cursor-based pagination.
 */

import { useMemo } from 'react';

import { useCursorPaginatedQuery } from './useCursorPaginatedQuery';
import { fetchEventDetections, type DetectionQueryParams } from '../services/api';

import type { DetectionListResponse } from '../types/generated';

export interface UseDetectionsInfiniteQueryOptions {
  eventId: number;
  limit?: number;
  enabled?: boolean;
  staleTime?: number;
  refetchInterval?: number | false;
}

export interface UseDetectionsInfiniteQueryReturn {
  detections: DetectionListResponse['items'];
  pages: DetectionListResponse[] | undefined;
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

export const detectionsQueryKeys = {
  all: ['detections'] as const,
  lists: () => [...detectionsQueryKeys.all, 'list'] as const,
  byEvent: (eventId: number) => [...detectionsQueryKeys.lists(), 'event', eventId] as const,
  infinite: (eventId: number, limit?: number) =>
    [...detectionsQueryKeys.all, 'infinite', { eventId, limit }] as const,
  detail: (id: number) => [...detectionsQueryKeys.all, 'detail', id] as const,
};

interface DetectionFilters {
  eventId: number;
}

export function useDetectionsInfiniteQuery(
  options: UseDetectionsInfiniteQueryOptions
): UseDetectionsInfiniteQueryReturn {
  const {
    eventId,
    limit = 50,
    enabled = true,
    staleTime,
    refetchInterval,
  } = options;

  const query = useCursorPaginatedQuery<DetectionListResponse, DetectionFilters>({
    queryKey: detectionsQueryKeys.infinite(eventId, limit),
    queryFn: ({ cursor, filters }) => {
      const params: DetectionQueryParams = {
        limit,
        cursor,
      };
      // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
      return fetchEventDetections(filters!.eventId, params);
    },
    filters: { eventId },
    enabled,
    staleTime,
    refetchInterval,
  });

  const detections = useMemo(() => {
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
    detections,
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

export default useDetectionsInfiniteQuery;

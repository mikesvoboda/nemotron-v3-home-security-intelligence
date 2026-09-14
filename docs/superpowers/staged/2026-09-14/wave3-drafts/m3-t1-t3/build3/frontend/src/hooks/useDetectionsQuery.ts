/**
 * React Query hooks for fetching detections with cursor-based pagination.
 *
 * Uses the generic createInfiniteQueryHook factory to reduce boilerplate
 * while maintaining full type safety and backwards compatibility.
 */

import { createInfiniteQueryHook, type BaseInfiniteQueryOptions } from './useCursorPaginatedQuery';
import { fetchEventDetections, type DetectionQueryParams } from '../services/api';

import type { DetectionListResponse } from '../types/generated';

/**
 * Internal filters type for the detections query.
 * Contains the eventId which is required for fetching detections.
 */
interface DetectionFilters {
  eventId: number;
}

export interface UseDetectionsInfiniteQueryOptions extends BaseInfiniteQueryOptions {
  eventId: number;
}

/**
 * Return type for useDetectionsInfiniteQuery.
 * Maintains backwards compatibility by using 'detections' instead of 'items'.
 */
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

/**
 * Internal hook created by factory function.
 * Returns the standardized InfiniteQueryHookReturn interface.
 */
const useDetectionsInfiniteQueryInternal = createInfiniteQueryHook<
  DetectionListResponse,
  DetectionListResponse['items'][number],
  UseDetectionsInfiniteQueryOptions,
  DetectionFilters
>({
  getQueryKey: (options) => detectionsQueryKeys.infinite(options.eventId, options.limit),
  fetchFn: ({ cursor, limit, filters }) => {
    const params: DetectionQueryParams = {
      limit,
      cursor,
    };
    // filters is guaranteed to have eventId since we set it in getFilters
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    return fetchEventDetections(filters!.eventId, params);
  },
  getFilters: (options) => ({ eventId: options.eventId }),
  defaultMaxPages: 10, // Limit stored pages for bounded memory (NEM-3362)
});

/**
 * Hook for fetching detections for an event with cursor-based infinite pagination.
 *
 * Wraps the factory-generated hook to maintain backwards compatibility
 * by renaming 'items' to 'detections' in the return type.
 *
 * @param options - Query options including eventId, limit, and React Query options
 * @returns Detections data with pagination controls and query state
 */
export function useDetectionsInfiniteQuery(
  options: UseDetectionsInfiniteQueryOptions
): UseDetectionsInfiniteQueryReturn {
  const result = useDetectionsInfiniteQueryInternal(options);

  // Rename 'items' to 'detections' for backwards compatibility
  return {
    detections: result.items,
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

export default useDetectionsInfiniteQuery;

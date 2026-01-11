/**
 * useEntitiesInfiniteQuery - React Query hook for infinite scroll entity loading
 *
 * This hook wraps useInfiniteQuery for entity tracking data, providing
 * infinite scroll pagination support. Since the backend entities endpoint
 * uses offset pagination (not cursor), this hook implements offset-based
 * infinite loading.
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with configurable stale time
 * - Infinite scroll support with proper page management
 * - Auto-refresh at configurable intervals
 * - Background refetching on network reconnect
 *
 * @module hooks/useEntitiesInfiniteQuery
 */

import {
  useInfiniteQuery,
  type InfiniteData,
  type QueryKey,
} from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchEntities,
  type EntitiesQueryParams,
  type EntityListResponse,
} from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

import type { EntitySummary } from '../types/generated';

// ============================================================================
// Types
// ============================================================================

/**
 * Time range filter options for entity queries.
 * Maps to a 'since' timestamp calculated from the current time.
 */
export type EntityTimeRangeFilter = '1h' | '24h' | '7d' | '30d' | 'all';

/**
 * Options for configuring the useEntitiesInfiniteQuery hook
 */
export interface UseEntitiesInfiniteQueryOptions {
  /**
   * Filter by entity type ('person' or 'vehicle')
   */
  entityType?: 'person' | 'vehicle' | 'all';

  /**
   * Filter by camera ID
   */
  cameraId?: string;

  /**
   * Time range filter. Entities seen within this time range will be returned.
   * @default 'all'
   */
  timeRange?: EntityTimeRangeFilter;

  /**
   * Maximum number of results per page
   * @default 50
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
   * @default 30000 (30 seconds)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;

  /**
   * Number of retry attempts for failed queries.
   * @default 1
   */
  retry?: number | boolean;
}

/**
 * Return type for the useEntitiesInfiniteQuery hook
 */
export interface UseEntitiesInfiniteQueryReturn {
  /** All entities from all loaded pages */
  entities: EntitySummary[];

  /** Raw page data for advanced use cases */
  pages: EntityListResponse[] | undefined;

  /** Whether the initial fetch is in progress */
  isLoading: boolean;

  /** Whether any fetch is in progress */
  isFetching: boolean;

  /** Whether the next page is being fetched */
  isFetchingNextPage: boolean;

  /** Whether there are more entities to load */
  hasNextPage: boolean;

  /** Function to fetch the next page */
  fetchNextPage: () => void;

  /** Error object if the query failed */
  error: Error | null;

  /** Whether the query has errored */
  isError: boolean;

  /** Whether the data is stale */
  isStale: boolean;

  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;

  /** Total count of entities matching the filter */
  totalCount: number;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Converts a time range filter to an ISO timestamp string.
 * Returns undefined for 'all' (no filtering).
 */
function timeRangeToSince(timeRange: EntityTimeRangeFilter): string | undefined {
  if (timeRange === 'all') {
    return undefined;
  }

  const now = new Date();
  let sinceDate: Date;

  switch (timeRange) {
    case '1h':
      sinceDate = new Date(now.getTime() - 60 * 60 * 1000);
      break;
    case '24h':
      sinceDate = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      break;
    case '7d':
      sinceDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      break;
    case '30d':
      sinceDate = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      break;
    default:
      return undefined;
  }

  return sinceDate.toISOString();
}

// ============================================================================
// Query Key Factory
// ============================================================================

export const entitiesInfiniteQueryKeys = {
  all: ['entities'] as const,
  infinite: (
    entityType?: 'person' | 'vehicle' | 'all',
    cameraId?: string,
    timeRange?: EntityTimeRangeFilter,
    limit?: number
  ) => [...entitiesInfiniteQueryKeys.all, 'infinite', { entityType, cameraId, timeRange, limit }] as const,
};

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch tracked entities with infinite scroll support.
 *
 * Uses offset-based pagination (the backend's entities endpoint doesn't
 * support cursor pagination yet) with TanStack Query's useInfiniteQuery
 * for efficient infinite scrolling.
 *
 * @param options - Configuration options
 * @returns Entity list data and query state with infinite scroll support
 *
 * @example
 * ```tsx
 * // Basic usage with infinite scroll
 * const {
 *   entities,
 *   isLoading,
 *   hasNextPage,
 *   fetchNextPage,
 *   isFetchingNextPage,
 * } = useEntitiesInfiniteQuery();
 *
 * // With filters
 * const { entities } = useEntitiesInfiniteQuery({
 *   entityType: 'person',
 *   cameraId: 'front_door',
 *   timeRange: '24h',
 * });
 *
 * // Use with useInfiniteScroll hook
 * const { sentinelRef } = useInfiniteScroll({
 *   onLoadMore: fetchNextPage,
 *   hasMore: hasNextPage,
 *   isLoading: isFetchingNextPage,
 * });
 * ```
 */
export function useEntitiesInfiniteQuery(
  options: UseEntitiesInfiniteQueryOptions = {}
): UseEntitiesInfiniteQueryReturn {
  const {
    entityType = 'all',
    cameraId,
    timeRange = 'all',
    limit = 50,
    enabled = true,
    refetchInterval = 30000,
    staleTime = DEFAULT_STALE_TIME,
    retry = 1,
  } = options;

  // Build the query key with all filter parameters
  const queryKey = entitiesInfiniteQueryKeys.infinite(entityType, cameraId, timeRange, limit);

  const query = useInfiniteQuery<
    EntityListResponse,
    Error,
    InfiniteData<EntityListResponse, number>,
    QueryKey,
    number
  >({
    queryKey,
    queryFn: async ({ pageParam = 0 }) => {
      const params: EntitiesQueryParams = {
        limit,
        offset: pageParam,
      };

      if (entityType !== 'all') {
        params.entity_type = entityType;
      }

      if (cameraId) {
        params.camera_id = cameraId;
      }

      const since = timeRangeToSince(timeRange);
      if (since) {
        params.since = since;
      }

      return fetchEntities(params);
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      // Calculate next offset based on items loaded so far
      const totalLoaded = allPages.reduce((sum, page) => sum + page.items.length, 0);

      // If there are more items, return the next offset
      if (lastPage.pagination.has_more) {
        return totalLoaded;
      }

      // No more pages
      return undefined;
    },
    enabled,
    refetchInterval,
    staleTime,
    retry,
  });

  // Flatten all entities from all pages
  const entities = useMemo(() => {
    if (!query.data?.pages) {
      return [];
    }
    return query.data.pages.flatMap((page) => page.items);
  }, [query.data?.pages]);

  // Get total count from first page's pagination
  const totalCount = useMemo(() => {
    if (!query.data?.pages?.[0]) {
      return 0;
    }
    return query.data.pages[0].pagination.total;
  }, [query.data?.pages]);

  const handleFetchNextPage = (): void => {
    void query.fetchNextPage();
  };

  return {
    entities,
    pages: query.data?.pages,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isFetchingNextPage: query.isFetchingNextPage,
    hasNextPage: query.hasNextPage ?? false,
    fetchNextPage: handleFetchNextPage,
    error: query.error,
    isError: query.isError,
    isStale: query.isStale,
    refetch: query.refetch,
    totalCount,
  };
}

export default useEntitiesInfiniteQuery;

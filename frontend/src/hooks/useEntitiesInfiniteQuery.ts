/**
 * useEntitiesInfiniteQuery - React Query hook for infinite scroll entity lists
 *
 * This hook provides cursor-based pagination for the entities list using
 * TanStack Query's infinite query capabilities.
 *
 * Features:
 * - Cursor-based pagination for efficient data loading
 * - Automatic request deduplication
 * - Infinite scroll support
 * - Filtering by entity type, camera, and time range
 * - Auto-refresh at configurable intervals
 *
 * @module hooks/useEntitiesInfiniteQuery
 */

import { useMemo } from 'react';

import { useCursorPaginatedQuery } from './useCursorPaginatedQuery';
import { fetchEntities, type EntitiesQueryParams, type EntityListResponse } from '../services/api';

// ============================================================================
// Types
// ============================================================================

/**
 * Time range filter options for entity queries.
 * Maps to a 'since' timestamp calculated from the current time.
 */
export type EntityTimeRangeFilter = '1h' | '24h' | '7d' | '30d' | 'all';

/**
 * Filter options for the entities infinite query
 */
export interface EntityFilters {
  /**
   * Filter by entity type ('person' or 'vehicle')
   */
  entity_type?: 'person' | 'vehicle';

  /**
   * Filter by camera ID
   */
  camera_id?: string;

  /**
   * Filter entities seen since this timestamp (ISO format)
   */
  since?: string;
}

/**
 * Options for configuring the useEntitiesInfiniteQuery hook
 */
export interface UseEntitiesInfiniteQueryOptions {
  /**
   * Filter options for the query
   */
  filters?: EntityFilters;

  /**
   * Number of items per page
   * @default 50
   */
  limit?: number;

  /**
   * Whether to enable the query
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds
   * @default 30000
   */
  staleTime?: number;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default 30000 (30 seconds)
   */
  refetchInterval?: number | false;

  /**
   * Number of retry attempts for failed queries.
   * @default 1
   */
  retry?: number | boolean;

  /**
   * Maximum number of pages to store in memory.
   * When this limit is reached, older pages are removed when new pages are fetched.
   * This bounds memory usage regardless of scroll depth.
   * TanStack Query v5 feature for memory optimization.
   * @default 10
   */
  maxPages?: number;
}

/**
 * Return type for the useEntitiesInfiniteQuery hook
 */
export interface UseEntitiesInfiniteQueryReturn {
  /** Flattened list of all entities from all pages */
  entities: EntityListResponse['items'];
  /** All loaded pages (for debugging/advanced use) */
  pages: EntityListResponse[] | undefined;
  /** Total count of entities (from first page pagination) */
  totalCount: number;
  /** Whether the initial load is in progress */
  isLoading: boolean;
  /** Whether any fetch is in progress */
  isFetching: boolean;
  /** Whether the next page is being fetched */
  isFetchingNextPage: boolean;
  /** Whether there are more pages to load */
  hasNextPage: boolean;
  /** Function to fetch the next page */
  fetchNextPage: () => void;
  /** Error that occurred during fetching */
  error: Error | null;
  /** Whether an error occurred */
  isError: boolean;
  /** Function to refetch all data */
  refetch: () => void;
}

// ============================================================================
// Query Keys
// ============================================================================

export const entitiesInfiniteQueryKeys = {
  all: ['entities'] as const,
  lists: () => [...entitiesInfiniteQueryKeys.all, 'list'] as const,
  infinite: (filters?: EntityFilters, limit?: number) =>
    [...entitiesInfiniteQueryKeys.all, 'infinite', { filters, limit }] as const,
  detail: (id: string) => [...entitiesInfiniteQueryKeys.all, 'detail', id] as const,
};

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch entities with infinite scroll pagination.
 *
 * Uses cursor-based pagination for efficient loading of large entity lists.
 * Provides automatic polling every 30 seconds by default.
 *
 * @param options - Configuration options
 * @returns Entity list data and pagination state
 *
 * @example
 * ```tsx
 * const {
 *   entities,
 *   isLoading,
 *   hasNextPage,
 *   fetchNextPage,
 *   isFetchingNextPage,
 * } = useEntitiesInfiniteQuery({
 *   filters: { entity_type: 'person' },
 *   limit: 25,
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
    filters,
    limit = 50,
    enabled = true,
    staleTime,
    refetchInterval = 30000,
    retry = 1,
    maxPages = 10, // Default to 10 pages for bounded memory (NEM-3362)
  } = options;

  const query = useCursorPaginatedQuery<EntityListResponse, EntityFilters>({
    queryKey: entitiesInfiniteQueryKeys.infinite(filters, limit),
    queryFn: ({ cursor, filters: queryFilters }) => {
      const params: EntitiesQueryParams = {
        ...queryFilters,
        limit,
        cursor,
      };
      return fetchEntities(params);
    },
    filters,
    enabled,
    staleTime,
    refetchInterval,
    retry,
    maxPages,
  });

  // Flatten all entities from all pages
  const entities = useMemo(() => {
    if (!query.data?.pages) {
      return [];
    }
    return query.data.pages.flatMap((page) => page.items);
  }, [query.data?.pages]);

  // Get total count from first page
  const totalCount = useMemo(() => {
    if (!query.data?.pages?.[0]) {
      return 0;
    }
    return query.data.pages[0].pagination.total;
  }, [query.data?.pages]);

  return {
    entities,
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

export default useEntitiesInfiniteQuery;

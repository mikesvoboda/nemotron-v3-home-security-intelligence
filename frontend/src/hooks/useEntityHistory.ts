/**
 * useEntityHistory - TanStack Query hooks for entity history and statistics
 *
 * This module provides hooks for fetching entity history from both Redis (real-time)
 * and PostgreSQL (historical) using the v2 API endpoints.
 *
 * Features:
 * - Historical entity queries with date range filtering
 * - Entity detections timeline
 * - Aggregated entity statistics
 * - Source filtering (redis, postgres, both)
 *
 * @module hooks/useEntityHistory
 */

import { useQuery, useInfiniteQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchEntitiesV2,
  fetchEntityV2,
  fetchEntityDetections,
  fetchEntityStats,
  type EntitiesV2QueryParams,
  type EntityListResponse,
  type EntityDetail,
  type EntityDetectionsResponse,
  type EntityStatsResponse,
  type SourceFilter,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the useEntitiesV2Query hook
 */
export interface UseEntitiesV2QueryOptions {
  /** Filter by entity type ('person' or 'vehicle') */
  entityType?: 'person' | 'vehicle';
  /** Filter by camera ID */
  cameraId?: string;
  /** Filter entities seen since this timestamp */
  since?: Date;
  /** Filter entities seen until this timestamp */
  until?: Date;
  /** Data source: 'redis', 'postgres', or 'both' */
  source?: SourceFilter;
  /** Maximum number of results per page */
  limit?: number;
  /** Whether to enable the query */
  enabled?: boolean;
  /** Auto-refresh interval in milliseconds (false to disable) */
  refetchInterval?: number | false;
  /** Custom stale time in milliseconds */
  staleTime?: number;
}

/**
 * Return type for the useEntitiesV2Query hook
 */
export interface UseEntitiesV2QueryReturn {
  /** Entity list response from the API */
  data: EntityListResponse | undefined;
  /** List of entities, empty array if not yet fetched */
  entities: EntityListResponse['items'];
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Total count of entities matching the filter */
  totalCount: number;
  /** Whether there are more entities to load */
  hasMore: boolean;
}

/**
 * Options for configuring the useEntityHistory hook
 */
export interface UseEntityHistoryOptions {
  /** Whether to enable the query */
  enabled?: boolean;
  /** Custom stale time in milliseconds */
  staleTime?: number;
}

/**
 * Return type for the useEntityHistory hook
 */
export interface UseEntityHistoryReturn {
  /** Entity detail data */
  entity: EntityDetail | undefined;
  /** Entity detections */
  detections: EntityDetectionsResponse | undefined;
  /** Whether the entity query is loading */
  isLoadingEntity: boolean;
  /** Whether the detections query is loading */
  isLoadingDetections: boolean;
  /** Combined loading state */
  isLoading: boolean;
  /** Entity query error */
  entityError: Error | null;
  /** Detections query error */
  detectionsError: Error | null;
  /** Function to refetch entity */
  refetchEntity: () => Promise<unknown>;
  /** Function to refetch detections */
  refetchDetections: () => Promise<unknown>;
  /** Function to fetch more detections */
  fetchMoreDetections: () => void;
  /** Whether there are more detections to load */
  hasMoreDetections: boolean;
  /** Whether more detections are being fetched */
  isFetchingMoreDetections: boolean;
}

/**
 * Options for configuring the useEntityStats hook
 */
export interface UseEntityStatsOptions {
  /** Filter entities seen since this timestamp */
  since?: Date;
  /** Filter entities seen until this timestamp */
  until?: Date;
  /** Whether to enable the query */
  enabled?: boolean;
  /** Auto-refresh interval in milliseconds (false to disable) */
  refetchInterval?: number | false;
  /** Custom stale time in milliseconds */
  staleTime?: number;
}

/**
 * Return type for the useEntityStats hook
 */
export interface UseEntityStatsReturn {
  /** Entity statistics data */
  data: EntityStatsResponse | undefined;
  /** Total unique entities */
  totalEntities: number;
  /** Total appearances across all entities */
  totalAppearances: number;
  /** Entity counts by type */
  byType: Record<string, number>;
  /** Entity counts by camera */
  byCamera: Record<string, number>;
  /** Count of entities seen more than once */
  repeatVisitors: number;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

// ============================================================================
// useEntitiesV2Query Hook
// ============================================================================

/**
 * Hook to fetch entities from the v2 API with historical support.
 *
 * Supports querying from Redis (hot cache), PostgreSQL (historical), or both.
 * Provides date range filtering and pagination.
 *
 * @param options - Configuration options
 * @returns Entity list data and query state
 *
 * @example
 * ```tsx
 * // Fetch all entities from both sources
 * const { entities, isLoading } = useEntitiesV2Query();
 *
 * // Fetch historical entities with date range
 * const { entities } = useEntitiesV2Query({
 *   source: 'postgres',
 *   since: new Date('2024-01-01'),
 *   until: new Date('2024-01-31'),
 * });
 * ```
 */
export function useEntitiesV2Query(
  options: UseEntitiesV2QueryOptions = {}
): UseEntitiesV2QueryReturn {
  const {
    entityType,
    cameraId,
    since,
    until,
    source,
    limit = 50,
    enabled = true,
    refetchInterval = 30000,
    staleTime = DEFAULT_STALE_TIME,
  } = options;

  // Build query params
  const queryParams: EntitiesV2QueryParams = useMemo(() => {
    const params: EntitiesV2QueryParams = { limit };

    if (entityType) {
      params.entity_type = entityType;
    }
    if (cameraId) {
      params.camera_id = cameraId;
    }
    if (since) {
      params.since = since.toISOString();
    }
    if (until) {
      params.until = until.toISOString();
    }
    if (source) {
      params.source = source;
    }

    return params;
  }, [entityType, cameraId, since, until, source, limit]);

  // Build filter key for query key
  const filterKey = useMemo(() => {
    const filters: Record<string, string | undefined> = {};
    if (entityType) filters.entity_type = entityType;
    if (cameraId) filters.camera_id = cameraId;
    if (since) filters.since = since.toISOString();
    if (until) filters.until = until.toISOString();
    if (source) filters.source = source;
    return Object.keys(filters).length > 0 ? filters : undefined;
  }, [entityType, cameraId, since, until, source]);

  const query = useQuery({
    queryKey: queryKeys.entities.v2.list(filterKey),
    queryFn: () => fetchEntitiesV2(queryParams),
    enabled,
    refetchInterval,
    staleTime,
    retry: 1,
  });

  const entities = useMemo(() => query.data?.items ?? [], [query.data?.items]);
  const totalCount = query.data?.pagination?.total ?? 0;
  const hasMore = query.data?.pagination?.has_more ?? false;

  return {
    data: query.data,
    entities,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
    totalCount,
    hasMore,
  };
}

// ============================================================================
// useEntityHistory Hook
// ============================================================================

/**
 * Hook to fetch entity details and detection timeline from PostgreSQL.
 *
 * Fetches both the entity record and its linked detections for displaying
 * a complete timeline view of all appearances.
 *
 * @param entityId - UUID of the entity to fetch
 * @param options - Configuration options
 * @returns Entity details, detections, and query state
 *
 * @example
 * ```tsx
 * const {
 *   entity,
 *   detections,
 *   isLoading,
 *   fetchMoreDetections,
 *   hasMoreDetections,
 * } = useEntityHistory(entityId);
 *
 * if (isLoading) return <Spinner />;
 * if (!entity) return <NotFound />;
 *
 * return (
 *   <div>
 *     <h1>{entity.entity_type}</h1>
 *     <Timeline detections={detections?.detections ?? []} />
 *     {hasMoreDetections && (
 *       <button onClick={fetchMoreDetections}>Load More</button>
 *     )}
 *   </div>
 * );
 * ```
 */
export function useEntityHistory(
  entityId: string | undefined,
  options: UseEntityHistoryOptions = {}
): UseEntityHistoryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  // Fetch entity details
  const entityQuery = useQuery({
    queryKey: queryKeys.entities.v2.detail(entityId ?? ''),
    queryFn: () => {
      if (!entityId) {
        throw new Error('Entity ID is required');
      }
      return fetchEntityV2(entityId);
    },
    enabled: enabled && !!entityId,
    staleTime,
    retry: 1,
  });

  // Fetch entity detections with infinite query for pagination
  const detectionsQuery = useInfiniteQuery({
    queryKey: queryKeys.entities.v2.detections(entityId ?? ''),
    queryFn: ({ pageParam = 0 }) => {
      if (!entityId) {
        throw new Error('Entity ID is required');
      }
      return fetchEntityDetections(entityId, { limit: 50, offset: pageParam });
    },
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      if (!lastPage.pagination.has_more) {
        return undefined;
      }
      return lastPage.pagination.offset + lastPage.pagination.limit;
    },
    enabled: enabled && !!entityId,
    staleTime,
    retry: 1,
  });

  // Flatten detections from all pages
  const detections = useMemo<EntityDetectionsResponse | undefined>(() => {
    if (!detectionsQuery.data?.pages?.length) {
      return undefined;
    }

    const firstPage = detectionsQuery.data.pages[0];
    const allDetections = detectionsQuery.data.pages.flatMap((page) => page.detections);

    return {
      entity_id: firstPage.entity_id,
      entity_type: firstPage.entity_type,
      detections: allDetections,
      pagination: {
        total: firstPage.pagination.total,
        limit: allDetections.length,
        offset: 0,
        has_more: detectionsQuery.hasNextPage ?? false,
      },
    };
  }, [detectionsQuery.data?.pages, detectionsQuery.hasNextPage]);

  return {
    entity: entityQuery.data,
    detections,
    isLoadingEntity: entityQuery.isLoading,
    isLoadingDetections: detectionsQuery.isLoading,
    isLoading: entityQuery.isLoading || detectionsQuery.isLoading,
    entityError: entityQuery.error,
    detectionsError: detectionsQuery.error,
    refetchEntity: entityQuery.refetch,
    refetchDetections: detectionsQuery.refetch,
    fetchMoreDetections: () => void detectionsQuery.fetchNextPage(),
    hasMoreDetections: detectionsQuery.hasNextPage ?? false,
    isFetchingMoreDetections: detectionsQuery.isFetchingNextPage,
  };
}

// ============================================================================
// useEntityStats Hook
// ============================================================================

/**
 * Hook to fetch aggregated entity statistics.
 *
 * Returns counts of entities by type, camera, and repeat visitors.
 * Supports time range filtering.
 *
 * @param options - Configuration options
 * @returns Entity statistics and query state
 *
 * @example
 * ```tsx
 * const {
 *   totalEntities,
 *   totalAppearances,
 *   byType,
 *   repeatVisitors,
 *   isLoading,
 * } = useEntityStats();
 *
 * // With time range filter
 * const { data } = useEntityStats({
 *   since: new Date('2024-01-01'),
 *   until: new Date('2024-01-31'),
 * });
 * ```
 */
export function useEntityStats(options: UseEntityStatsOptions = {}): UseEntityStatsReturn {
  const {
    since,
    until,
    enabled = true,
    refetchInterval = 60000, // Refresh every minute
    staleTime = DEFAULT_STALE_TIME,
  } = options;

  // Build filter key for query key
  const filterKey = useMemo(() => {
    const filters: Record<string, string | undefined> = {};
    if (since) filters.since = since.toISOString();
    if (until) filters.until = until.toISOString();
    return Object.keys(filters).length > 0 ? filters : undefined;
  }, [since, until]);

  const query = useQuery({
    queryKey: queryKeys.entities.stats(filterKey),
    queryFn: () =>
      fetchEntityStats({
        since: since?.toISOString(),
        until: until?.toISOString(),
      }),
    enabled,
    refetchInterval,
    staleTime,
    retry: 1,
  });

  return {
    data: query.data,
    totalEntities: query.data?.total_entities ?? 0,
    totalAppearances: query.data?.total_appearances ?? 0,
    byType: query.data?.by_type ?? {},
    byCamera: query.data?.by_camera ?? {},
    repeatVisitors: query.data?.repeat_visitors ?? 0,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

export default useEntityHistory;

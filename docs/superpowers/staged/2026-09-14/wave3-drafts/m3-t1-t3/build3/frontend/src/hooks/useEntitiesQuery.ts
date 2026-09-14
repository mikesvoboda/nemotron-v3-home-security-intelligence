/**
 * useEntitiesQuery - TanStack Query hook for entity tracking data
 *
 * This hook provides a TanStack Query wrapper around the entities API
 * with support for filtering and auto-refresh.
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with configurable stale time
 * - Auto-refresh at configurable intervals
 * - Background refetching on network reconnect
 *
 * @module hooks/useEntitiesQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchEntities,
  fetchEntity,
  type EntitiesQueryParams,
  type EntityListResponse,
  type EntityDetail,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Time range filter options for entity queries.
 * Maps to a 'since' timestamp calculated from the current time.
 */
export type TimeRangeFilter = '1h' | '24h' | '7d' | '30d' | 'all';

/**
 * Options for configuring the useEntitiesQuery hook
 */
export interface UseEntitiesQueryOptions {
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
  timeRange?: TimeRangeFilter;

  /**
   * Maximum number of results to return
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
}

/**
 * Return type for the useEntitiesQuery hook
 */
export interface UseEntitiesQueryReturn {
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
  /** Whether the data is stale */
  isStale: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Total count of entities matching the filter */
  totalCount: number;
  /** Whether there are more entities to load */
  hasMore: boolean;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Converts a time range filter to an ISO timestamp string.
 * Returns undefined for 'all' (no filtering).
 */
function timeRangeToSince(timeRange: TimeRangeFilter): string | undefined {
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
// useEntitiesQuery Hook
// ============================================================================

/**
 * Hook to fetch tracked entities using TanStack Query.
 *
 * Provides automatic polling every 30 seconds by default,
 * with support for filtering by entity type, camera, and time range.
 *
 * @param options - Configuration options
 * @returns Entity list data and query state
 *
 * @example
 * ```tsx
 * // Basic usage with auto-refresh
 * const { entities, isLoading, error } = useEntitiesQuery();
 *
 * // With filters
 * const { entities } = useEntitiesQuery({
 *   entityType: 'person',
 *   cameraId: 'front_door',
 *   timeRange: '24h',
 * });
 * ```
 */
export function useEntitiesQuery(options: UseEntitiesQueryOptions = {}): UseEntitiesQueryReturn {
  const {
    entityType = 'all',
    cameraId,
    timeRange = 'all',
    limit = 50,
    enabled = true,
    refetchInterval = 30000, // 30 seconds auto-refresh
    staleTime = DEFAULT_STALE_TIME,
  } = options;

  // Build query params from filter options
  const queryParams: EntitiesQueryParams = useMemo(() => {
    const params: EntitiesQueryParams = { limit };

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

    return params;
  }, [entityType, cameraId, timeRange, limit]);

  // Build the filter object for the query key
  const filterKey = useMemo(() => {
    const filters: Record<string, string | undefined> = {};
    if (entityType !== 'all') filters.entity_type = entityType;
    if (cameraId) filters.camera_id = cameraId;
    if (timeRange !== 'all') filters.since = timeRange;
    return Object.keys(filters).length > 0 ? filters : undefined;
  }, [entityType, cameraId, timeRange]);

  const query = useQuery({
    queryKey: queryKeys.entities.list(filterKey),
    queryFn: () => fetchEntities(queryParams),
    enabled,
    refetchInterval,
    staleTime,
    retry: 1,
  });

  // Provide empty array as default to avoid null checks
  const entities = useMemo(() => query.data?.items ?? [], [query.data?.items]);
  const totalCount = query.data?.pagination?.total ?? 0;
  const hasMore = query.data?.pagination?.has_more ?? false;

  return {
    data: query.data,
    entities,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isStale: query.isStale,
    refetch: query.refetch,
    totalCount,
    hasMore,
  };
}

// ============================================================================
// useEntityDetailQuery Hook
// ============================================================================

/**
 * Options for configuring the useEntityDetailQuery hook
 */
export interface UseEntityDetailQueryOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME
   */
  staleTime?: number;
}

/**
 * Return type for the useEntityDetailQuery hook
 */
export interface UseEntityDetailQueryReturn {
  /** Entity detail data */
  data: EntityDetail | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch a single entity's details using TanStack Query.
 *
 * @param entityId - ID of the entity to fetch, or undefined to disable
 * @param options - Configuration options
 * @returns Entity detail and query state
 *
 * @example
 * ```tsx
 * const { data: entity, isLoading, error } = useEntityDetailQuery(entityId);
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 * if (!entity) return null;
 *
 * return <EntityDetailModal entity={entity} />;
 * ```
 */
export function useEntityDetailQuery(
  entityId: string | undefined,
  options: UseEntityDetailQueryOptions = {}
): UseEntityDetailQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  const query = useQuery({
    queryKey: queryKeys.entities.detail(entityId ?? ''),
    queryFn: () => {
      if (!entityId) {
        throw new Error('Entity ID is required');
      }
      return fetchEntity(entityId);
    },
    enabled: enabled && !!entityId,
    staleTime,
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * useEventDetectionsQuery - TanStack Query hook for fetching event detections
 *
 * This hook fetches all detections for a specific event with proper caching,
 * deduplication, and stale time management to prevent duplicate API calls.
 *
 * @module hooks/useEventDetectionsQuery
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';

import {
  fetchEventDetections,
  type DetectionQueryParams,
  type DetectionOrderBy,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

import type { DetectionListResponse, Detection } from '../types/generated';

/**
 * Options for configuring the useEventDetectionsQuery hook
 */
export interface UseEventDetectionsQueryOptions {
  /**
   * The event ID to fetch detections for.
   * Query is disabled when eventId is not a valid number.
   */
  eventId: number;

  /**
   * Maximum number of detections to fetch.
   * @default 100
   */
  limit?: number;

  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;

  /**
   * Order detections by: 'detected_at' (detection timestamp, default) or
   * 'created_at' (when associated with event - shows detection sequence).
   * NEM-3629: When using 'created_at', responses include association_created_at.
   * @default 'detected_at'
   */
  orderBy?: DetectionOrderBy;
}

/**
 * Return type for the useEventDetectionsQuery hook
 */
export interface UseEventDetectionsQueryReturn {
  /** Array of detections, empty if loading or no data */
  detections: Detection[];
  /** Full response data, undefined if not yet fetched */
  data: DetectionListResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether any fetch is in progress (including background refetch) */
  isFetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the query has errored */
  isError: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Query key factory for event detections.
 * Uses the standard queryKeys.detections.forEvent pattern for consistency.
 * NEM-3629: Includes orderBy in query key for proper cache separation.
 */
export const eventDetectionsQueryKeys = {
  forEvent: (eventId: number, limit?: number, orderBy?: DetectionOrderBy) =>
    limit || orderBy
      ? ([...queryKeys.detections.forEvent(eventId), { limit, orderBy }] as const)
      : queryKeys.detections.forEvent(eventId),
};

/**
 * Hook to fetch detections for a specific event using TanStack Query.
 *
 * This hook provides:
 * - Automatic caching with configurable stale time (default 30s)
 * - Request deduplication across components
 * - Consistent query keys for cache management
 * - Graceful handling of invalid event IDs
 *
 * @param options - Configuration options including eventId
 * @returns Detections data and query state
 *
 * @example
 * ```tsx
 * // Basic usage
 * const { detections, isLoading } = useEventDetectionsQuery({ eventId: 123 });
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <ul>
 *     {detections.map(d => <li key={d.id}>{d.object_type}</li>)}
 *   </ul>
 * );
 * ```
 *
 * @example
 * ```tsx
 * // With custom limit
 * const { detections } = useEventDetectionsQuery({
 *   eventId: 123,
 *   limit: 50,
 *   staleTime: 60000, // 1 minute
 * });
 * ```
 *
 * @example
 * ```tsx
 * // Order by association time (NEM-3629)
 * const { detections } = useEventDetectionsQuery({
 *   eventId: 123,
 *   orderBy: 'created_at', // Shows detection sequence in event
 * });
 * // Each detection.association_created_at shows when it was added to the event
 * ```
 */
export function useEventDetectionsQuery(
  options: UseEventDetectionsQueryOptions
): UseEventDetectionsQueryReturn {
  const {
    eventId,
    limit = 100,
    enabled = true,
    staleTime = DEFAULT_STALE_TIME,
    orderBy,
  } = options;

  // Validate eventId - disable query if invalid
  const isValidEventId = !isNaN(eventId) && eventId > 0;

  const query = useQuery({
    queryKey: eventDetectionsQueryKeys.forEvent(eventId, limit, orderBy),
    queryFn: async () => {
      const params: DetectionQueryParams = { limit, order_detections_by: orderBy };
      return fetchEventDetections(eventId, params);
    },
    enabled: enabled && isValidEventId,
    staleTime,
    // Retry a few times for transient errors
    retry: 2,
  });

  return {
    detections: query.data?.items ?? [],
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
  };
}

/**
 * Prefetch stale time for hover-triggered prefetching (NEM-3594).
 * 30 seconds - data should remain valid while user hovers and decides to click.
 */
export const PREFETCH_STALE_TIME = 30 * 1000;

/**
 * Default limit for prefetched detections.
 * Higher limit to ensure most events have all detections cached.
 */
export const PREFETCH_DEFAULT_LIMIT = 100;

/**
 * Hook to prefetch event detections on hover.
 *
 * Returns a callback that can be used as an onMouseEnter handler
 * to prefetch detections before the user clicks to open the detail modal.
 *
 * This improves perceived performance by:
 * - Pre-loading data during hover (typically 100-500ms before click)
 * - Using existing cached data if available
 * - Not re-fetching if data is still fresh
 *
 * @param options - Configuration options
 * @returns Object with prefetch callback and cache reading utilities
 *
 * @example
 * ```tsx
 * const { prefetchDetections, getCachedCount } = usePrefetchEventDetections();
 *
 * return (
 *   <EventCard
 *     {...props}
 *     onMouseEnter={() => prefetchDetections(event.id)}
 *     detectionCount={getCachedCount(event.id) ?? event.detection_count}
 *   />
 * );
 * ```
 *
 * @see NEM-3594 - Event Detection Relationship Caching
 */
export function usePrefetchEventDetections(options?: {
  /** Custom stale time for prefetched data (default: 30 seconds) */
  staleTime?: number;
  /** Default limit for prefetch (default: 100) */
  limit?: number;
}) {
  const queryClient = useQueryClient();
  const { staleTime = PREFETCH_STALE_TIME, limit = PREFETCH_DEFAULT_LIMIT } = options ?? {};

  /**
   * Prefetch detections for an event.
   * This is safe to call multiple times - TanStack Query will deduplicate requests.
   */
  const prefetchDetections = useCallback(
    (eventId: number, orderBy?: DetectionOrderBy) => {
      if (!eventId || isNaN(eventId) || eventId <= 0) return;

      void queryClient.prefetchQuery({
        queryKey: eventDetectionsQueryKeys.forEvent(eventId, limit, orderBy),
        queryFn: async () => {
          const params: DetectionQueryParams = { limit, order_detections_by: orderBy };
          return fetchEventDetections(eventId, params);
        },
        staleTime,
      });
    },
    [queryClient, staleTime, limit]
  );

  /**
   * Get cached detection count for an event.
   * Returns undefined if no cached data exists.
   *
   * Useful for displaying detection count badges without triggering a fetch.
   */
  const getCachedCount = useCallback(
    (eventId: number, orderBy?: DetectionOrderBy): number | undefined => {
      const data = queryClient.getQueryData<{ items: unknown[] }>(
        eventDetectionsQueryKeys.forEvent(eventId, limit, orderBy)
      );
      return data?.items?.length;
    },
    [queryClient, limit]
  );

  /**
   * Check if detections for an event are cached and fresh.
   */
  const isCached = useCallback(
    (eventId: number, orderBy?: DetectionOrderBy): boolean => {
      const state = queryClient.getQueryState(
        eventDetectionsQueryKeys.forEvent(eventId, limit, orderBy)
      );
      return state?.data !== undefined;
    },
    [queryClient, limit]
  );

  return {
    prefetchDetections,
    getCachedCount,
    isCached,
  };
}

export default useEventDetectionsQuery;

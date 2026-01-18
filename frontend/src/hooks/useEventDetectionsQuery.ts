/**
 * useEventDetectionsQuery - TanStack Query hook for fetching event detections
 *
 * This hook fetches all detections for a specific event with proper caching,
 * deduplication, and stale time management to prevent duplicate API calls.
 *
 * @module hooks/useEventDetectionsQuery
 */

import { useQuery } from '@tanstack/react-query';

import { fetchEventDetections, type DetectionQueryParams } from '../services/api';
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
 */
export const eventDetectionsQueryKeys = {
  forEvent: (eventId: number, limit?: number) =>
    limit
      ? ([...queryKeys.detections.forEvent(eventId), { limit }] as const)
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
 */
export function useEventDetectionsQuery(
  options: UseEventDetectionsQueryOptions
): UseEventDetectionsQueryReturn {
  const { eventId, limit = 100, enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  // Validate eventId - disable query if invalid
  const isValidEventId = !isNaN(eventId) && eventId > 0;

  const query = useQuery({
    queryKey: eventDetectionsQueryKeys.forEvent(eventId, limit),
    queryFn: async () => {
      const params: DetectionQueryParams = { limit };
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

export default useEventDetectionsQuery;

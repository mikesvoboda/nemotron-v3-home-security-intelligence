/**
 * useEventEnrichmentsQuery - TanStack Query hook for fetching batch enrichments for an event
 *
 * This hook uses the optimized GET /api/events/{event_id}/enrichments endpoint
 * to fetch enrichment data for all detections in a single request, instead of
 * making individual per-detection calls. This reduces API calls by ~90% for events
 * with many detections.
 *
 * @module hooks/useEventEnrichmentsQuery
 * @see NEM-3596
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchEventEnrichments, type EventEnrichmentsQueryParams } from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

import type { EventEnrichmentsResponse, EnrichmentResponse } from '../types/generated';

/**
 * Options for configuring the useEventEnrichmentsQuery hook
 */
export interface UseEventEnrichmentsQueryOptions {
  /**
   * The event ID to fetch enrichments for.
   * Query is disabled when eventId is not a valid number.
   */
  eventId: number;

  /**
   * Maximum number of enrichments to fetch.
   * @default 50 (matches backend default)
   */
  limit?: number;

  /**
   * Number of enrichments to skip (for pagination).
   * @default 0
   */
  offset?: number;

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
 * Return type for the useEventEnrichmentsQuery hook
 */
export interface UseEventEnrichmentsQueryReturn {
  /** Array of enrichments, empty if loading or no data */
  enrichments: EnrichmentResponse[];
  /** Full response data, undefined if not yet fetched */
  data: EventEnrichmentsResponse | undefined;
  /** Map of detection ID to enrichment for O(1) lookups */
  enrichmentMap: Map<number, EnrichmentResponse>;
  /** Helper function to get enrichment by detection ID */
  getEnrichmentByDetectionId: (detectionId: number) => EnrichmentResponse | undefined;
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
 * Query key factory for event enrichments.
 * Structured to enable granular cache invalidation.
 */
export const eventEnrichmentsQueryKeys = {
  all: ['eventEnrichments'] as const,
  forEvent: (eventId: number, params?: EventEnrichmentsQueryParams) =>
    [...eventEnrichmentsQueryKeys.all, eventId, params] as const,
};

/**
 * Hook to fetch batch enrichments for all detections in an event.
 *
 * This hook uses the GET /api/events/{event_id}/enrichments endpoint which
 * aggregates enrichment data from all detections in a single API call,
 * providing significant performance improvements over per-detection calls.
 *
 * Benefits:
 * - Reduces API calls by ~90% for events with many detections
 * - Single request instead of N requests for N detections
 * - Built-in caching with TanStack Query
 * - Provides O(1) lookup via enrichmentMap
 *
 * @param options - Configuration options including eventId
 * @returns Enrichments data and query state with lookup helpers
 *
 * @example
 * ```tsx
 * // Basic usage in EventDetailModal
 * const { enrichments, getEnrichmentByDetectionId, isLoading } = useEventEnrichmentsQuery({
 *   eventId: 123,
 *   enabled: isOpen,
 * });
 *
 * // Get enrichment for a specific detection
 * const enrichment = getEnrichmentByDetectionId(detectionId);
 * if (enrichment?.face?.detected) {
 *   console.log('Face detected:', enrichment.face);
 * }
 * ```
 *
 * @example
 * ```tsx
 * // With pagination
 * const { enrichments, data } = useEventEnrichmentsQuery({
 *   eventId: 123,
 *   limit: 20,
 *   offset: 0,
 * });
 *
 * // Check if there are more enrichments
 * if (data?.has_more) {
 *   // Fetch next page...
 * }
 * ```
 */
export function useEventEnrichmentsQuery(
  options: UseEventEnrichmentsQueryOptions
): UseEventEnrichmentsQueryReturn {
  const { eventId, limit, offset, enabled = true, staleTime = DEFAULT_STALE_TIME } = options;

  // Validate eventId - disable query if invalid
  const isValidEventId = !isNaN(eventId) && eventId > 0;

  // Build pagination params only if provided
  const params: EventEnrichmentsQueryParams | undefined =
    limit !== undefined || offset !== undefined ? { limit, offset } : undefined;

  const query = useQuery({
    queryKey: eventEnrichmentsQueryKeys.forEvent(eventId, params),
    queryFn: async () => {
      return fetchEventEnrichments(eventId, params);
    },
    enabled: enabled && isValidEventId,
    staleTime,
    // Retry a couple times for transient errors
    retry: 2,
  });

  // Build a Map for O(1) lookups by detection ID
  const enrichmentMap = useMemo(() => {
    const map = new Map<number, EnrichmentResponse>();
    if (query.data?.enrichments) {
      for (const enrichment of query.data.enrichments) {
        map.set(enrichment.detection_id, enrichment);
      }
    }
    return map;
  }, [query.data?.enrichments]);

  // Helper function to get enrichment by detection ID
  const getEnrichmentByDetectionId = useMemo(
    () =>
      (detectionId: number): EnrichmentResponse | undefined => {
        return enrichmentMap.get(detectionId);
      },
    [enrichmentMap]
  );

  return {
    enrichments: query.data?.enrichments ?? [],
    data: query.data,
    enrichmentMap,
    getEnrichmentByDetectionId,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export default useEventEnrichmentsQuery;

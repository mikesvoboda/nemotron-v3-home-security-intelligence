/**
 * React Query hook for fetching recent events with a fixed limit.
 *
 * This hook is optimized for dashboard usage where only a small number
 * of recent events are needed. It uses server-side limiting to avoid
 * fetching more data than necessary (fixing the double-fetch anti-pattern).
 */

import { useQuery } from '@tanstack/react-query';

import { fetchEvents, type EventsQueryParams } from '../services/api';

import type { Event, EventListResponse } from '../types/generated';

export interface UseRecentEventsQueryOptions {
  /**
   * Maximum number of recent events to fetch.
   * This is passed directly to the server - no client-side slicing.
   * @default 10
   */
  limit?: number;
  /**
   * Whether the query is enabled.
   * @default true
   */
  enabled?: boolean;
  /**
   * How long the data is considered fresh (in milliseconds).
   * @default 30000 (30 seconds)
   */
  staleTime?: number;
  /**
   * Polling interval for automatic refetching (in milliseconds).
   * Set to false to disable polling.
   * @default false
   */
  refetchInterval?: number | false;
  /**
   * Optional camera ID to filter events.
   */
  cameraId?: string;
  /**
   * Optional risk level to filter events.
   */
  riskLevel?: string;
}

export interface UseRecentEventsQueryReturn {
  /** The list of recent events (already limited server-side) */
  events: Event[];
  /** Total count of events matching the filters (not just returned events) */
  totalCount: number;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether any fetch (including refetch) is in progress */
  isFetching: boolean;
  /** Error if the fetch failed */
  error: Error | null;
  /** Whether an error occurred */
  isError: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => void;
}

/**
 * Query key factory for recent events queries.
 * Includes the limit in the key to properly cache different limits.
 */
export const recentEventsQueryKeys = {
  all: ['events', 'recent'] as const,
  list: (limit: number, cameraId?: string, riskLevel?: string) =>
    [...recentEventsQueryKeys.all, { limit, cameraId, riskLevel }] as const,
};

/**
 * Hook for fetching a limited number of recent events.
 *
 * This hook is designed to prevent the double-fetch anti-pattern by:
 * 1. Requesting only the needed number of events from the server
 * 2. Not performing any client-side slicing
 *
 * @example
 * ```tsx
 * // Dashboard showing last 10 events
 * const { events, isLoading } = useRecentEventsQuery({ limit: 10 });
 *
 * // Activity feed showing last 5 events from a specific camera
 * const { events } = useRecentEventsQuery({
 *   limit: 5,
 *   cameraId: 'front-door',
 * });
 * ```
 */
export function useRecentEventsQuery(
  options: UseRecentEventsQueryOptions = {}
): UseRecentEventsQueryReturn {
  const {
    limit = 10,
    enabled = true,
    staleTime = 30000,
    refetchInterval = false,
    cameraId,
    riskLevel,
  } = options;

  const query = useQuery<EventListResponse, Error>({
    queryKey: recentEventsQueryKeys.list(limit, cameraId, riskLevel),
    queryFn: async () => {
      const params: EventsQueryParams = {
        limit,
        // Events are sorted by started_at descending by default on the server
      };

      if (cameraId) {
        params.camera_id = cameraId;
      }
      if (riskLevel) {
        params.risk_level = riskLevel;
      }

      return fetchEvents(params);
    },
    enabled,
    staleTime,
    refetchInterval,
    refetchOnWindowFocus: true,
  });

  const handleRefetch = (): void => {
    void query.refetch();
  };

  return {
    events: query.data?.items ?? [],
    totalCount: query.data?.pagination.total ?? 0,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    isError: query.isError,
    refetch: handleRefetch,
  };
}

export default useRecentEventsQuery;

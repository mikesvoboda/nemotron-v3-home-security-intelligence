/**
 * React Query hook for fetching event statistics.
 *
 * Wraps the fetchEventStats API call with caching, refetch, and filter support.
 * Used by EventStatsPanel to display accurate server-side statistics.
 */

import { useQuery } from '@tanstack/react-query';

import { fetchEventStats, type EventStatsQueryParams } from '../services/api';

import type { EventStatsResponse } from '../types/generated';

/**
 * Options for the useEventStats hook.
 */
export interface UseEventStatsOptions {
  /** Start date filter (YYYY-MM-DD) */
  startDate?: string;
  /** End date filter (YYYY-MM-DD) */
  endDate?: string;
  /** Camera ID filter */
  cameraId?: string;
  /** Whether to enable the query (default: true) */
  enabled?: boolean;
}

/**
 * Return type for useEventStats hook.
 */
export interface UseEventStatsReturn {
  /** Event statistics data */
  stats: EventStatsResponse | undefined;
  /** Whether the query is loading */
  isLoading: boolean;
  /** Whether the query is fetching (includes background refetch) */
  isFetching: boolean;
  /** Whether the query has an error */
  isError: boolean;
  /** Error object if query failed */
  error: Error | null;
  /** Function to manually refetch the data */
  refetch: () => Promise<unknown>;
}

/**
 * Query key factory for event stats queries.
 * Ensures consistent cache key generation across the app.
 */
export const eventStatsQueryKeys = {
  all: ['event-stats'] as const,
  stats: (params?: Pick<UseEventStatsOptions, 'startDate' | 'endDate' | 'cameraId'>) =>
    [
      ...eventStatsQueryKeys.all,
      'stats',
      {
        startDate: params?.startDate,
        endDate: params?.endDate,
        cameraId: params?.cameraId,
      },
    ] as const,
};

/** Stale time for event stats (30 seconds) */
const STATS_STALE_TIME = 30 * 1000;

/**
 * Hook for fetching event statistics from the API.
 *
 * Provides accurate server-side statistics for total events, events by risk level,
 * risk distribution, and events by camera. Statistics are cached for 30 seconds.
 *
 * @param options - Query options including date range and camera filters
 * @returns Stats data with loading state and refetch function
 *
 * @example
 * ```tsx
 * const { stats, isLoading, error } = useEventStats({
 *   startDate: '2025-01-01',
 *   endDate: '2025-01-31',
 *   cameraId: 'front_door',
 * });
 *
 * if (isLoading) return <Skeleton />;
 * if (error) return <Error message={error.message} />;
 *
 * return <StatsPanel total={stats.total_events} />;
 * ```
 */
export function useEventStats(options: UseEventStatsOptions = {}): UseEventStatsReturn {
  const { startDate, endDate, cameraId, enabled = true } = options;

  const queryResult = useQuery({
    queryKey: eventStatsQueryKeys.stats({ startDate, endDate, cameraId }),
    queryFn: ({ signal }) => {
      const params: EventStatsQueryParams = {
        start_date: startDate,
        end_date: endDate,
        camera_id: cameraId,
      };
      return fetchEventStats(params, { signal });
    },
    enabled,
    staleTime: STATS_STALE_TIME,
  });

  return {
    stats: queryResult.data,
    isLoading: queryResult.isLoading,
    isFetching: queryResult.isFetching,
    isError: queryResult.isError,
    error: queryResult.error,
    refetch: queryResult.refetch,
  };
}

export default useEventStats;

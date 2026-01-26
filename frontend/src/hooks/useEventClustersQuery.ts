/**
 * React Query hook for fetching event clusters (NEM-3676).
 *
 * Wraps the fetchEventClusters API call with caching, refetch, and filter support.
 * Groups events that occur within a specified time window into clusters for
 * reduced visual noise on the timeline.
 */

import { useQuery } from '@tanstack/react-query';

import { fetchEventClusters, type EventClustersQueryParams } from '../services/api';

import type { EventClustersResponse } from '../types/generated';

/**
 * Options for the useEventClustersQuery hook.
 */
export interface UseEventClustersOptions {
  /** Start date filter (ISO format, required) */
  startDate: string;
  /** End date filter (ISO format, required) */
  endDate: string;
  /** Camera ID filter (optional) */
  cameraId?: string;
  /** Time window in minutes for clustering events (1-60, default 5) */
  timeWindowMinutes?: number;
  /** Minimum events required to form a cluster (2-100, default 2) */
  minClusterSize?: number;
  /** Whether to enable the query (default: true) */
  enabled?: boolean;
}

/**
 * Return type for useEventClustersQuery hook.
 */
export interface UseEventClustersReturn {
  /** Event clusters data */
  data: EventClustersResponse | undefined;
  /** Individual clusters from the response */
  clusters: EventClustersResponse['clusters'];
  /** Total number of clusters */
  totalClusters: number;
  /** Number of events not belonging to any cluster */
  unclusteredEvents: number;
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
 * Query key factory for event clusters queries.
 * Ensures consistent cache key generation across the app.
 */
export const eventClustersQueryKeys = {
  all: ['event-clusters'] as const,
  clusters: (
    params: Pick<
      UseEventClustersOptions,
      'startDate' | 'endDate' | 'cameraId' | 'timeWindowMinutes' | 'minClusterSize'
    >
  ) =>
    [
      ...eventClustersQueryKeys.all,
      'list',
      {
        startDate: params.startDate,
        endDate: params.endDate,
        cameraId: params.cameraId,
        timeWindowMinutes: params.timeWindowMinutes,
        minClusterSize: params.minClusterSize,
      },
    ] as const,
};

/** Stale time for event clusters (30 seconds) */
const CLUSTERS_STALE_TIME = 30 * 1000;

/**
 * Hook for fetching event clusters from the API.
 *
 * Provides grouped events that occur within a specified time window.
 * Events from the same camera within `timeWindowMinutes` are grouped together.
 * Events from different cameras within 2 minutes are also grouped (cross-camera clusters).
 *
 * @param options - Query options including date range, camera filter, and clustering parameters
 * @returns Clusters data with loading state and refetch function
 *
 * @example
 * ```tsx
 * const { clusters, totalClusters, isLoading, error } = useEventClustersQuery({
 *   startDate: '2026-01-20T00:00:00Z',
 *   endDate: '2026-01-25T23:59:59Z',
 *   cameraId: 'front_door',
 *   timeWindowMinutes: 5,
 *   minClusterSize: 2,
 * });
 *
 * if (isLoading) return <Skeleton />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <div>
 *     <p>Found {totalClusters} clusters</p>
 *     {clusters.map((cluster) => (
 *       <EventClusterCard key={cluster.cluster_id} cluster={cluster} />
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useEventClustersQuery(options: UseEventClustersOptions): UseEventClustersReturn {
  const {
    startDate,
    endDate,
    cameraId,
    timeWindowMinutes,
    minClusterSize,
    enabled = true,
  } = options;

  const queryResult = useQuery({
    queryKey: eventClustersQueryKeys.clusters({
      startDate,
      endDate,
      cameraId,
      timeWindowMinutes,
      minClusterSize,
    }),
    queryFn: ({ signal }) => {
      const params: EventClustersQueryParams = {
        start_date: startDate,
        end_date: endDate,
        camera_id: cameraId,
        time_window_minutes: timeWindowMinutes,
        min_cluster_size: minClusterSize,
      };
      return fetchEventClusters(params, { signal });
    },
    enabled: enabled && Boolean(startDate) && Boolean(endDate),
    staleTime: CLUSTERS_STALE_TIME,
  });

  return {
    data: queryResult.data,
    clusters: queryResult.data?.clusters ?? [],
    totalClusters: queryResult.data?.total_clusters ?? 0,
    unclusteredEvents: queryResult.data?.unclustered_events ?? 0,
    isLoading: queryResult.isLoading,
    isFetching: queryResult.isFetching,
    isError: queryResult.isError,
    error: queryResult.error,
    refetch: queryResult.refetch,
  };
}

export default useEventClustersQuery;

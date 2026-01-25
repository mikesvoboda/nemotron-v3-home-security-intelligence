/**
 * useCameraAnomaliesQuery - TanStack Query hook for camera baseline anomalies (NEM-3577)
 *
 * This module provides a hook for fetching camera anomaly data using TanStack Query.
 * It provides:
 * - Automatic request deduplication across components
 * - Built-in caching with configurable stale time
 * - Background refetching
 * - Type-safe response data
 *
 * @module hooks/useCameraAnomaliesQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchCameraAnomalies,
  type CameraAnomaliesResponse,
  type CameraAnomalyEvent,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the useCameraAnomaliesQuery hook.
 */
export interface UseCameraAnomaliesQueryOptions {
  /**
   * Number of days to look back for anomalies.
   * @default 7
   */
  days?: number;

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
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default false
   */
  refetchInterval?: number | false;
}

/**
 * Return type for the useCameraAnomaliesQuery hook.
 */
export interface UseCameraAnomaliesQueryReturn {
  /** List of anomaly events, empty array if not yet fetched */
  anomalies: CameraAnomalyEvent[];
  /** Full response data, undefined if not yet fetched */
  data: CameraAnomaliesResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether any fetch is in progress (initial or background) */
  isFetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the query has errored */
  isError: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Total count of anomalies in the response */
  count: number;
  /** Number of days covered by the query */
  periodDays: number;
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook to fetch camera baseline anomalies using TanStack Query.
 *
 * Returns anomaly events that deviated significantly from the established
 * baseline activity patterns for the specified camera within the given
 * time period.
 *
 * @param cameraId - The camera ID to fetch anomalies for
 * @param options - Configuration options
 * @returns Camera anomaly data and query state
 *
 * @example
 * ```tsx
 * // Fetch anomalies from the last 7 days (default)
 * const { anomalies, isLoading, error } = useCameraAnomaliesQuery('front-door');
 *
 * // Fetch anomalies from the last 30 days
 * const { anomalies, isLoading, error } = useCameraAnomaliesQuery('front-door', {
 *   days: 30,
 * });
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <ul>
 *     {anomalies.map((anomaly, index) => (
 *       <li key={index}>
 *         {anomaly.detection_class}: {anomaly.reason}
 *       </li>
 *     ))}
 *   </ul>
 * );
 * ```
 */
export function useCameraAnomaliesQuery(
  cameraId: string,
  options: UseCameraAnomaliesQueryOptions = {}
): UseCameraAnomaliesQueryReturn {
  const {
    days = 7,
    enabled = true,
    staleTime = DEFAULT_STALE_TIME,
    refetchInterval = false,
  } = options;

  const query = useQuery<CameraAnomaliesResponse, Error>({
    queryKey: queryKeys.cameras.anomalies(cameraId, days),
    queryFn: () => fetchCameraAnomalies(cameraId, days),
    enabled: enabled && !!cameraId,
    staleTime,
    refetchInterval,
    // Reduced retry for faster failure feedback
    retry: 1,
  });

  // Provide empty array as default to avoid null checks
  const anomalies = useMemo<CameraAnomalyEvent[]>(
    () => query.data?.anomalies ?? [],
    [query.data]
  );

  const count = useMemo(() => query.data?.count ?? 0, [query.data]);
  const periodDays = useMemo(() => query.data?.period_days ?? days, [query.data, days]);

  return {
    anomalies,
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
    count,
    periodDays,
  };
}

// Re-export types for convenience
export type { CameraAnomaliesResponse, CameraAnomalyEvent };

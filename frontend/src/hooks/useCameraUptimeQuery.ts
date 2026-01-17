/**
 * useCameraUptimeQuery - TanStack Query hook for camera uptime analytics
 *
 * This module provides a hook for fetching camera uptime data using TanStack Query.
 * It provides:
 * - Automatic request deduplication across components
 * - Built-in caching with configurable stale time
 * - Background refetching
 * - Type-safe response data
 *
 * @module hooks/useCameraUptimeQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchCameraUptime,
  type CameraUptimeResponse,
  type CameraUptimeDataPoint,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Date range parameters for camera uptime query.
 */
export interface CameraUptimeDateRange {
  /** Start date in ISO format (YYYY-MM-DD) */
  startDate: string;
  /** End date in ISO format (YYYY-MM-DD) */
  endDate: string;
}

/**
 * Options for configuring the useCameraUptimeQuery hook.
 */
export interface UseCameraUptimeQueryOptions {
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
 * Return type for the useCameraUptimeQuery hook.
 */
export interface UseCameraUptimeQueryReturn {
  /** List of camera uptime data, empty array if not yet fetched */
  cameras: CameraUptimeDataPoint[];
  /** Full response data, undefined if not yet fetched */
  data: CameraUptimeResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook to fetch camera uptime data using TanStack Query.
 *
 * Returns uptime percentage and detection count for each camera within
 * the specified date range. Uptime is calculated based on the number of
 * days with at least one detection divided by the total days in the range.
 *
 * @param dateRange - Date range for the uptime calculation
 * @param options - Configuration options
 * @returns Camera uptime data and query state
 *
 * @example
 * ```tsx
 * const dateRange = {
 *   startDate: '2026-01-10',
 *   endDate: '2026-01-17',
 * };
 *
 * const { cameras, isLoading, error } = useCameraUptimeQuery(dateRange);
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <ul>
 *     {cameras.map(cam => (
 *       <li key={cam.camera_id}>
 *         {cam.camera_name}: {cam.uptime_percentage.toFixed(1)}%
 *       </li>
 *     ))}
 *   </ul>
 * );
 * ```
 */
export function useCameraUptimeQuery(
  dateRange: CameraUptimeDateRange,
  options: UseCameraUptimeQueryOptions = {}
): UseCameraUptimeQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME, refetchInterval = false } = options;

  const query = useQuery<CameraUptimeResponse, Error>({
    queryKey: queryKeys.analytics.cameraUptime({
      startDate: dateRange.startDate,
      endDate: dateRange.endDate,
    }),
    queryFn: () =>
      fetchCameraUptime({
        start_date: dateRange.startDate,
        end_date: dateRange.endDate,
      }),
    enabled,
    staleTime,
    refetchInterval,
    // Reduced retry for faster failure feedback
    retry: 1,
  });

  // Provide empty array as default to avoid null checks
  const cameras = useMemo<CameraUptimeDataPoint[]>(
    () => query.data?.cameras ?? [],
    [query.data]
  );

  return {
    cameras,
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

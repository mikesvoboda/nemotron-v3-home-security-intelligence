/**
 * useCameraActivityQuery - TanStack Query hook for camera activity heatmap analytics
 *
 * This module provides a hook for fetching camera activity data using TanStack Query.
 * Used for the Camera Activity Heatmap feature (NEM-5388/5389/5390/5391).
 *
 * Features:
 * - Automatic request deduplication across components
 * - Built-in caching with configurable stale time
 * - Background refetching
 * - Type-safe response data
 *
 * @module hooks/useCameraActivityQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchCameraActivity,
  type CameraActivityResponse,
  type CameraActivityDataPoint,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Date range parameters for camera activity query.
 */
export interface CameraActivityDateRange {
  /** Start date in ISO format (YYYY-MM-DD) */
  startDate: string;
  /** End date in ISO format (YYYY-MM-DD) */
  endDate: string;
}

/**
 * Options for configuring the useCameraActivityQuery hook.
 */
export interface UseCameraActivityQueryOptions {
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
 * Return type for the useCameraActivityQuery hook.
 */
export interface UseCameraActivityQueryReturn {
  /** List of camera activity data, empty array if not yet fetched */
  cameras: CameraActivityDataPoint[];
  /** Full response data, undefined if not yet fetched */
  data: CameraActivityResponse | undefined;
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
 * Hook to fetch camera activity data using TanStack Query.
 *
 * Returns aggregated event data per camera for building an activity heatmap
 * visualization. Data includes event counts, max risk scores, computed risk
 * levels, and thumbnail paths for the highest-risk detections.
 *
 * @param dateRange - Date range for the activity calculation
 * @param options - Configuration options
 * @returns Camera activity data and query state
 *
 * @example
 * ```tsx
 * const dateRange = {
 *   startDate: '2026-01-10',
 *   endDate: '2026-01-17',
 * };
 *
 * const { cameras, isLoading, error } = useCameraActivityQuery(dateRange);
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <div className="grid grid-cols-2 gap-4">
 *     {cameras.map(cam => (
 *       <CameraActivityCard
 *         key={cam.camera_id}
 *         name={cam.camera_name}
 *         eventCount={cam.event_count}
 *         riskLevel={cam.risk_level}
 *         thumbnailPath={cam.thumbnail_path}
 *       />
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useCameraActivityQuery(
  dateRange: CameraActivityDateRange,
  options: UseCameraActivityQueryOptions = {}
): UseCameraActivityQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME, refetchInterval = false } = options;

  const query = useQuery<CameraActivityResponse, Error>({
    queryKey: queryKeys.analytics.cameraActivity({
      startDate: dateRange.startDate,
      endDate: dateRange.endDate,
    }),
    queryFn: () =>
      fetchCameraActivity({
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
  const cameras = useMemo<CameraActivityDataPoint[]>(() => query.data?.cameras ?? [], [query.data]);

  return {
    cameras,
    data: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

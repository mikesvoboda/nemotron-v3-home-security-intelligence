/**
 * useDetectionStatsQuery - TanStack Query hook for detection statistics
 *
 * This hook fetches detection statistics from the /api/detections/stats endpoint.
 * It supports optional filtering by camera ID for camera-specific analytics.
 *
 * @module hooks/useDetectionStatsQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchDetectionStats,
  type DetectionStatsResponse,
  type DetectionStatsQueryParams,
} from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

/**
 * Query key factory for detection stats queries.
 *
 * Keys follow a hierarchical pattern: ['detections', 'stats', params?]
 *
 * @example
 * // Invalidate all detection stats queries
 * queryClient.invalidateQueries({ queryKey: detectionStatsQueryKeys.all });
 *
 * // Invalidate specific camera stats
 * queryClient.invalidateQueries({
 *   queryKey: detectionStatsQueryKeys.byParams({ camera_id: 'cam-123' })
 * });
 */
export const detectionStatsQueryKeys = {
  /** Base key for all detection stats queries - use for bulk invalidation */
  all: ['detections', 'stats'] as const,
  /** Detection stats with specific parameters */
  byParams: (params: DetectionStatsQueryParams) =>
    [...detectionStatsQueryKeys.all, params] as const,
};

/**
 * Options for configuring the useDetectionStatsQuery hook
 */
export interface UseDetectionStatsQueryOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * Data older than this will be refetched in the background.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;

  /**
   * Number of retry attempts on failure.
   * Set to false or 0 to disable retries.
   * @default 1
   */
  retry?: number | boolean;
}

/**
 * Return type for the useDetectionStatsQuery hook
 */
export interface UseDetectionStatsQueryReturn {
  /** Raw API response data, undefined if not yet fetched */
  data: DetectionStatsResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the query is in an error state */
  isError: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Derived: Total detection count, 0 if data not loaded */
  totalDetections: number;
  /** Derived: Detection counts by class, empty object if data not loaded */
  detectionsByClass: Record<string, number>;
  /** Derived: Average confidence score, null if data not loaded */
  averageConfidence: number | null;
}

/**
 * Hook to fetch detection statistics using TanStack Query.
 *
 * This hook fetches from GET /api/detections/stats and provides:
 * - Automatic caching and request deduplication
 * - Optional filtering by camera ID
 * - Derived values for total detections, class distribution, and confidence
 *
 * @param params - Optional query parameters including camera_id filter
 * @param options - Configuration options
 * @returns Detection stats data and query state
 *
 * @example
 * ```tsx
 * // Basic usage - fetch all detection stats
 * const { totalDetections, detectionsByClass, isLoading, error } = useDetectionStatsQuery();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <StatsCard
 *     total={totalDetections}
 *     byClass={detectionsByClass}
 *   />
 * );
 * ```
 *
 * @example
 * ```tsx
 * // With camera filter
 * const { totalDetections, detectionsByClass } = useDetectionStatsQuery({
 *   camera_id: selectedCameraId,
 * });
 *
 * // Stats automatically refetch when selectedCameraId changes
 * ```
 */
export function useDetectionStatsQuery(
  params: DetectionStatsQueryParams = {},
  options: UseDetectionStatsQueryOptions = {}
): UseDetectionStatsQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME, retry = 1 } = options;

  const query = useQuery<DetectionStatsResponse, Error>({
    queryKey: detectionStatsQueryKeys.byParams(params),
    queryFn: () => fetchDetectionStats(params),
    enabled,
    staleTime,
    retry,
  });

  // Derive total detections from the response
  const totalDetections = useMemo((): number => {
    if (!query.data) return 0;
    return query.data.total_detections;
  }, [query.data]);

  // Derive detections by class from the response
  const detectionsByClass = useMemo((): Record<string, number> => {
    if (!query.data) return {};
    return query.data.detections_by_class;
  }, [query.data]);

  // Derive average confidence from the response
  const averageConfidence = useMemo((): number | null => {
    if (!query.data) return null;
    return query.data.average_confidence;
  }, [query.data]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
    totalDetections,
    detectionsByClass,
    averageConfidence,
  };
}

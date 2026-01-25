/**
 * useObjectDistributionQuery - TanStack Query hook for object distribution analytics
 *
 * This module provides a hook for fetching object distribution data using TanStack Query.
 * Object distribution shows the breakdown of detections by object type (person, car, etc.).
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with configurable stale time
 * - Background refetching support
 * - DevTools integration for debugging
 *
 * @module hooks/useObjectDistributionQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchObjectDistribution, type ObjectDistributionParams } from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';

import type {
  ObjectDistributionResponse,
  ObjectDistributionDataPoint,
} from '../types/analytics';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for object distribution queries.
 * Enables granular cache invalidation based on date range.
 */
export const objectDistributionQueryKeys = {
  all: ['analytics', 'object-distribution'] as const,
  byDateRange: (params: ObjectDistributionParams) =>
    [...objectDistributionQueryKeys.all, params] as const,
};

// ============================================================================
// Hook Options
// ============================================================================

/**
 * Options for configuring the useObjectDistributionQuery hook.
 */
export interface UseObjectDistributionQueryOptions {
  /**
   * Whether to enable the query.
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
   */
  refetchInterval?: number | false;
}

// ============================================================================
// Hook Return Type
// ============================================================================

/**
 * Return type for the useObjectDistributionQuery hook.
 */
export interface UseObjectDistributionQueryReturn {
  /** Full response data, undefined if not yet fetched */
  data: ObjectDistributionResponse | undefined;
  /** Array of object type data points for charting */
  objectTypes: ObjectDistributionDataPoint[];
  /** Total detections in the date range */
  totalDetections: number;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether an error occurred */
  isError: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch object distribution data using TanStack Query.
 *
 * Fetches from GET /api/analytics/object-distribution and provides:
 * - Automatic caching and request deduplication
 * - Configurable stale time
 * - Derived objectTypes array and totalDetections for easy charting
 *
 * @param params - Date range parameters (start_date, end_date)
 * @param options - Configuration options
 * @returns Object distribution data and query state
 *
 * @example
 * ```tsx
 * // Fetch object distribution for the last 7 days
 * const { objectTypes, totalDetections, isLoading } = useObjectDistributionQuery({
 *   start_date: '2026-01-10',
 *   end_date: '2026-01-17',
 * });
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <DonutChart
 *     data={objectTypes}
 *     category="count"
 *     index="object_type"
 *     label={`${totalDetections} total`}
 *   />
 * );
 * ```
 */
export function useObjectDistributionQuery(
  params: ObjectDistributionParams,
  options: UseObjectDistributionQueryOptions = {}
): UseObjectDistributionQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME, refetchInterval } = options;

  const query = useQuery<ObjectDistributionResponse, Error>({
    queryKey: queryKeys.analytics.objectDistribution({
      startDate: params.start_date,
      endDate: params.end_date,
    }),
    queryFn: () => fetchObjectDistribution(params),
    enabled,
    staleTime,
    refetchInterval,
    // Use 1 retry for faster failure feedback
    retry: 1,
  });

  // Derive objectTypes array, defaulting to empty array
  const objectTypes = useMemo(
    () => query.data?.object_types ?? [],
    [query.data?.object_types]
  );

  // Derive total detections, defaulting to 0
  const totalDetections = useMemo(
    () => query.data?.total_detections ?? 0,
    [query.data?.total_detections]
  );

  return {
    data: query.data,
    objectTypes,
    totalDetections,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export default useObjectDistributionQuery;

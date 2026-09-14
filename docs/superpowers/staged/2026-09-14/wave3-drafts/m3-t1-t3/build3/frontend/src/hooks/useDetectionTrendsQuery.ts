/**
 * useDetectionTrendsQuery - TanStack Query hook for detection trend data
 *
 * This hook fetches detection trend data from the analytics API endpoint.
 * It provides daily detection counts for a specified date range.
 *
 * @module hooks/useDetectionTrendsQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchDetectionTrends } from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

import type {
  DetectionTrendsResponse,
  DetectionTrendsParams,
  DetectionTrendDataPoint,
} from '../types/analytics';

/**
 * Query key factory for detection trends queries.
 *
 * Keys follow a hierarchical pattern: ['analytics', 'detection-trends', params?]
 *
 * @example
 * // Invalidate all detection trends queries
 * queryClient.invalidateQueries({ queryKey: detectionTrendsQueryKeys.all });
 *
 * // Invalidate specific date range
 * queryClient.invalidateQueries({
 *   queryKey: detectionTrendsQueryKeys.byDateRange({ start_date: '2026-01-10', end_date: '2026-01-16' })
 * });
 */
export const detectionTrendsQueryKeys = {
  /** Base key for all detection trends queries - use for bulk invalidation */
  all: ['analytics', 'detection-trends'] as const,
  /** Detection trends for a specific date range */
  byDateRange: (params: DetectionTrendsParams) =>
    [...detectionTrendsQueryKeys.all, params] as const,
};

/**
 * Options for configuring the useDetectionTrendsQuery hook
 */
export interface UseDetectionTrendsQueryOptions {
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
 * Return type for the useDetectionTrendsQuery hook
 */
export interface UseDetectionTrendsQueryReturn {
  /** Raw API response data, undefined if not yet fetched */
  data: DetectionTrendsResponse | undefined;
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
  /** Derived: Array of data points, empty if data not loaded */
  dataPoints: DetectionTrendDataPoint[];
  /** Derived: Total detection count, 0 if data not loaded */
  totalDetections: number;
}

/**
 * Hook to fetch detection trends using TanStack Query.
 *
 * This hook fetches from GET /api/analytics/detection-trends and provides:
 * - Automatic caching and request deduplication
 * - Derived values for data points and total detections
 * - Conditional fetching based on valid date parameters
 *
 * @param params - Date range parameters for the query
 * @param options - Configuration options
 * @returns Detection trends data and query state
 *
 * @example
 * ```tsx
 * // Basic usage
 * const { dataPoints, totalDetections, isLoading, error } = useDetectionTrendsQuery({
 *   start_date: '2026-01-10',
 *   end_date: '2026-01-16',
 * });
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <Chart
 *     data={dataPoints}
 *     total={totalDetections}
 *   />
 * );
 * ```
 *
 * @example
 * ```tsx
 * // With dynamic date range
 * const [dateRange, setDateRange] = useState({
 *   start_date: getLastWeekStart(),
 *   end_date: getToday(),
 * });
 *
 * const { dataPoints, refetch } = useDetectionTrendsQuery(dateRange);
 *
 * // Data automatically refetches when dateRange changes
 * const handleDateChange = (newRange) => setDateRange(newRange);
 * ```
 */
export function useDetectionTrendsQuery(
  params: DetectionTrendsParams,
  options: UseDetectionTrendsQueryOptions = {}
): UseDetectionTrendsQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME, retry = 1 } = options;

  // Only enable the query if both dates are provided and not empty
  const isValidParams = Boolean(params.start_date && params.end_date);
  const queryEnabled = enabled && isValidParams;

  const query = useQuery<DetectionTrendsResponse, Error>({
    queryKey: detectionTrendsQueryKeys.byDateRange(params),
    queryFn: () => fetchDetectionTrends(params),
    enabled: queryEnabled,
    staleTime,
    retry,
  });

  // Derive data points from the response
  const dataPoints = useMemo((): DetectionTrendDataPoint[] => {
    if (!query.data) return [];
    return query.data.data_points;
  }, [query.data]);

  // Derive total detections from the response
  const totalDetections = useMemo((): number => {
    if (!query.data) return 0;
    return query.data.total_detections;
  }, [query.data]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
    dataPoints,
    totalDetections,
  };
}

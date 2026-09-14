/**
 * useRiskScoreTrends - TanStack Query hook for risk score trend analytics
 *
 * This module provides a hook for fetching risk score trend data using TanStack Query.
 * Risk score trends show the average risk score over time.
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with configurable stale time
 * - Background refetching support
 * - DevTools integration for debugging
 *
 * @module hooks/useRiskScoreTrends
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchRiskScoreTrends,
  type RiskScoreTrendsParams,
  type RiskScoreTrendsResponse,
  type RiskScoreTrendDataPoint,
} from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for risk score trends queries.
 * Enables granular cache invalidation based on date range.
 */
export const riskScoreTrendsQueryKeys = {
  all: ['analytics', 'risk-score-trends'] as const,
  byDateRange: (params: RiskScoreTrendsParams) =>
    [...riskScoreTrendsQueryKeys.all, params] as const,
};

// ============================================================================
// Hook Options
// ============================================================================

/**
 * Options for configuring the useRiskScoreTrends hook.
 */
export interface UseRiskScoreTrendsOptions {
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
 * Return type for the useRiskScoreTrends hook.
 */
export interface UseRiskScoreTrendsReturn {
  /** Full response data, undefined if not yet fetched */
  data: RiskScoreTrendsResponse | undefined;
  /** Array of trend data points for charting */
  dataPoints: RiskScoreTrendDataPoint[];
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
 * Hook to fetch risk score trend data using TanStack Query.
 *
 * Fetches from GET /api/analytics/risk-score-trends and provides:
 * - Automatic caching and request deduplication
 * - Configurable stale time
 * - Derived dataPoints array for easy charting
 *
 * @param params - Date range parameters (start_date, end_date)
 * @param options - Configuration options
 * @returns Risk score trend data and query state
 *
 * @example
 * ```tsx
 * // Fetch risk score trends for the last 7 days
 * const { dataPoints, isLoading } = useRiskScoreTrends({
 *   start_date: '2026-01-10',
 *   end_date: '2026-01-17',
 * });
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <LineChart
 *     data={dataPoints}
 *     index="date"
 *     categories={['avg_score']}
 *   />
 * );
 * ```
 */
export function useRiskScoreTrends(
  params: RiskScoreTrendsParams,
  options: UseRiskScoreTrendsOptions = {}
): UseRiskScoreTrendsReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME, refetchInterval } = options;

  // Only enable the query if both dates are provided and not empty
  const isValidParams = Boolean(params.start_date && params.end_date);
  const queryEnabled = enabled && isValidParams;

  const query = useQuery<RiskScoreTrendsResponse, Error>({
    queryKey: riskScoreTrendsQueryKeys.byDateRange(params),
    queryFn: () => fetchRiskScoreTrends(params),
    enabled: queryEnabled,
    staleTime,
    refetchInterval,
    // Use 1 retry for faster failure feedback
    retry: 1,
  });

  // Derive dataPoints array, defaulting to empty array
  const dataPoints = useMemo((): RiskScoreTrendDataPoint[] => {
    if (!query.data) return [];
    return query.data.data_points;
  }, [query.data]);

  return {
    data: query.data,
    dataPoints,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export default useRiskScoreTrends;

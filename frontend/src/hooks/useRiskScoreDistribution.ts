/**
 * useRiskScoreDistribution - TanStack Query hook for risk score distribution analytics
 *
 * This module provides a hook for fetching risk score distribution data using TanStack Query.
 * Risk score distribution shows a histogram of events grouped by score buckets.
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with configurable stale time
 * - Background refetching support
 * - DevTools integration for debugging
 *
 * @module hooks/useRiskScoreDistribution
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchRiskScoreDistribution,
  type RiskScoreDistributionParams,
  type RiskScoreDistributionResponse,
  type RiskScoreDistributionBucket,
} from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for risk score distribution queries.
 * Enables granular cache invalidation based on date range and bucket size.
 */
export const riskScoreDistributionQueryKeys = {
  all: ['analytics', 'risk-score-distribution'] as const,
  byParams: (params: RiskScoreDistributionParams) =>
    [...riskScoreDistributionQueryKeys.all, params] as const,
};

// ============================================================================
// Hook Options
// ============================================================================

/**
 * Options for configuring the useRiskScoreDistribution hook.
 */
export interface UseRiskScoreDistributionOptions {
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
 * Return type for the useRiskScoreDistribution hook.
 */
export interface UseRiskScoreDistributionReturn {
  /** Full response data, undefined if not yet fetched */
  data: RiskScoreDistributionResponse | undefined;
  /** Array of distribution buckets for charting */
  buckets: RiskScoreDistributionBucket[];
  /** Total events in the distribution */
  totalEvents: number;
  /** Bucket size used in the query */
  bucketSize: number;
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
 * Hook to fetch risk score distribution data using TanStack Query.
 *
 * Fetches from GET /api/analytics/risk-score-distribution and provides:
 * - Automatic caching and request deduplication
 * - Configurable stale time
 * - Derived buckets array for easy charting
 *
 * @param params - Date range and optional bucket_size parameters
 * @param options - Configuration options
 * @returns Risk score distribution data and query state
 *
 * @example
 * ```tsx
 * // Fetch risk score distribution for the last 7 days
 * const { buckets, totalEvents, isLoading } = useRiskScoreDistribution({
 *   start_date: '2026-01-10',
 *   end_date: '2026-01-17',
 * });
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <BarChart
 *     data={buckets}
 *     index="min_score"
 *     categories={['count']}
 *   />
 * );
 * ```
 */
export function useRiskScoreDistribution(
  params: RiskScoreDistributionParams,
  options: UseRiskScoreDistributionOptions = {}
): UseRiskScoreDistributionReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME, refetchInterval } = options;

  // Only enable the query if both dates are provided and not empty
  const isValidParams = Boolean(params.start_date && params.end_date);
  const queryEnabled = enabled && isValidParams;

  const query = useQuery<RiskScoreDistributionResponse, Error>({
    queryKey: riskScoreDistributionQueryKeys.byParams(params),
    queryFn: () => fetchRiskScoreDistribution(params),
    enabled: queryEnabled,
    staleTime,
    refetchInterval,
    // Use 1 retry for faster failure feedback
    retry: 1,
  });

  // Derive buckets array, defaulting to empty array
  const buckets = useMemo((): RiskScoreDistributionBucket[] => {
    if (!query.data) return [];
    return query.data.buckets;
  }, [query.data]);

  // Derive total events from the response
  const totalEvents = useMemo((): number => {
    if (!query.data) return 0;
    return query.data.total_events;
  }, [query.data]);

  // Derive bucket size from the response
  const bucketSize = useMemo((): number => {
    if (!query.data) return params.bucket_size ?? 10;
    return query.data.bucket_size;
  }, [query.data, params.bucket_size]);

  return {
    data: query.data,
    buckets,
    totalEvents,
    bucketSize,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
  };
}

export default useRiskScoreDistribution;

/**
 * useRiskHistoryQuery - TanStack Query hook for risk history analytics
 *
 * This module provides a hook for fetching risk history data using TanStack Query.
 * Risk history shows the distribution of events by risk level over time.
 *
 * Benefits:
 * - Automatic request deduplication across components
 * - Built-in caching with configurable stale time
 * - Background refetching support
 * - DevTools integration for debugging
 *
 * @module hooks/useRiskHistoryQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchRiskHistory, type RiskHistoryQueryParams } from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

import type { RiskHistoryResponse, RiskHistoryDataPoint } from '../types/analytics';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query key factory for risk history queries.
 * Enables granular cache invalidation based on date range.
 */
export const riskHistoryQueryKeys = {
  all: ['analytics', 'risk-history'] as const,
  byDateRange: (params: RiskHistoryQueryParams) =>
    [...riskHistoryQueryKeys.all, params] as const,
};

// ============================================================================
// Hook Options
// ============================================================================

/**
 * Options for configuring the useRiskHistoryQuery hook.
 */
export interface UseRiskHistoryQueryOptions {
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
 * Return type for the useRiskHistoryQuery hook.
 */
export interface UseRiskHistoryQueryReturn {
  /** Full response data, undefined if not yet fetched */
  data: RiskHistoryResponse | undefined;
  /** Array of risk history data points for charting */
  dataPoints: RiskHistoryDataPoint[];
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
 * Hook to fetch risk history data using TanStack Query.
 *
 * Fetches from GET /api/analytics/risk-history and provides:
 * - Automatic caching and request deduplication
 * - Configurable stale time
 * - Derived dataPoints array for easy charting
 *
 * @param params - Date range parameters (start_date, end_date)
 * @param options - Configuration options
 * @returns Risk history data and query state
 *
 * @example
 * ```tsx
 * // Fetch risk history for the last 7 days
 * const { dataPoints, isLoading } = useRiskHistoryQuery({
 *   start_date: '2026-01-10',
 *   end_date: '2026-01-17',
 * });
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <AreaChart
 *     data={dataPoints}
 *     index="date"
 *     categories={['critical', 'high', 'medium', 'low']}
 *     colors={['red', 'orange', 'yellow', 'emerald']}
 *     stack={true}
 *   />
 * );
 * ```
 */
export function useRiskHistoryQuery(
  params: RiskHistoryQueryParams,
  options: UseRiskHistoryQueryOptions = {}
): UseRiskHistoryQueryReturn {
  const { enabled = true, staleTime = DEFAULT_STALE_TIME, refetchInterval } = options;

  const query = useQuery({
    queryKey: riskHistoryQueryKeys.byDateRange(params),
    queryFn: () => fetchRiskHistory(params),
    enabled,
    staleTime,
    refetchInterval,
    // Use 1 retry for faster failure feedback
    retry: 1,
  });

  // Derive dataPoints array, defaulting to empty array
  const dataPoints = useMemo(() => query.data?.data_points ?? [], [query.data?.data_points]);

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

export default useRiskHistoryQuery;

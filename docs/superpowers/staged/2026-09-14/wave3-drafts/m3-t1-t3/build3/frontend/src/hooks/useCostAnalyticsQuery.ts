/**
 * useCostAnalyticsQuery - TanStack Query hook for cost analytics data
 *
 * This hook fetches comprehensive cost analytics data from the API,
 * including budget utilization, token usage, cost breakdowns, and trends.
 *
 * Part of NEM-5024 Phase 2: Cost Analytics Dashboard.
 *
 * @module hooks/useCostAnalyticsQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { fetchCostAnalytics, fetchCostTrends } from '../services/api';
import { DEFAULT_STALE_TIME } from '../services/queryClient';

import type {
  CostAnalyticsResponse,
  CostTrendResponse,
  CostTrendParams,
  DailyCostEntry,
  BudgetUtilization,
} from '../types/costAnalytics';

/**
 * Query key factory for cost analytics queries.
 *
 * Keys follow a hierarchical pattern: ['analytics', 'costs', ...]
 *
 * @example
 * // Invalidate all cost analytics queries
 * queryClient.invalidateQueries({ queryKey: costAnalyticsQueryKeys.all });
 *
 * // Invalidate cost trends
 * queryClient.invalidateQueries({ queryKey: costAnalyticsQueryKeys.trends.all });
 */
const BASE_KEY = ['analytics', 'costs'] as const;
const TRENDS_KEY = [...BASE_KEY, 'trends'] as const;

/**
 * Query key factory for cost analytics queries.
 *
 * Keys follow a hierarchical pattern: ['analytics', 'costs', ...]
 *
 * @example
 * // Invalidate all cost analytics queries
 * queryClient.invalidateQueries({ queryKey: costAnalyticsQueryKeys.all });
 *
 * // Invalidate cost trends
 * queryClient.invalidateQueries({ queryKey: costAnalyticsQueryKeys.trends.all });
 */
export const costAnalyticsQueryKeys = {
  /** Base key for all cost analytics queries */
  all: BASE_KEY,
  /** Summary cost analytics */
  summary: () => [...BASE_KEY, 'summary'] as const,
  /** Cost trends queries */
  trends: {
    all: TRENDS_KEY,
    byDateRange: (params: CostTrendParams) => [...TRENDS_KEY, params] as const,
  },
};

/**
 * Options for configuring the useCostAnalyticsQuery hook
 */
export interface UseCostAnalyticsQueryOptions {
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
   * Number of retry attempts on failure.
   * @default 1
   */
  retry?: number | boolean;

  /**
   * Refetch interval in milliseconds.
   * Set to 0 to disable auto-refetch.
   * @default 60000 (1 minute)
   */
  refetchInterval?: number;
}

/**
 * Return type for the useCostAnalyticsQuery hook
 */
export interface UseCostAnalyticsQueryReturn {
  /** Raw API response data */
  data: CostAnalyticsResponse | undefined;
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

  // Derived values for easy access
  /** Today's cost summary */
  todayCost: DailyCostEntry | undefined;
  /** Daily budget utilization */
  dailyBudget: BudgetUtilization | undefined;
  /** Monthly budget utilization */
  monthlyBudget: BudgetUtilization | undefined;
  /** Cost history data points */
  costHistory: DailyCostEntry[];
  /** Total cost today in USD */
  todayTotalCost: number;
  /** Daily budget utilization ratio (0-1) */
  dailyUtilizationRatio: number;
  /** Monthly budget utilization ratio (0-1) */
  monthlyUtilizationRatio: number;
}

/**
 * Hook to fetch cost analytics using TanStack Query.
 *
 * This hook fetches comprehensive cost analytics data including:
 * - Today's cost summary
 * - Daily and monthly budget utilization
 * - Token usage metrics
 * - Cost breakdown by model
 * - Historical cost data (30 days)
 *
 * @param options - Configuration options
 * @returns Cost analytics data and query state
 *
 * @example
 * ```tsx
 * const {
 *   todayCost,
 *   dailyBudget,
 *   monthlyBudget,
 *   costHistory,
 *   isLoading,
 *   error,
 * } = useCostAnalyticsQuery();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <CostDashboard
 *     todayCost={todayCost}
 *     dailyBudget={dailyBudget}
 *     history={costHistory}
 *   />
 * );
 * ```
 */
export function useCostAnalyticsQuery(
  options: UseCostAnalyticsQueryOptions = {}
): UseCostAnalyticsQueryReturn {
  const {
    enabled = true,
    staleTime = DEFAULT_STALE_TIME,
    retry = 1,
    refetchInterval = 60000,
  } = options;

  const query = useQuery<CostAnalyticsResponse, Error>({
    queryKey: costAnalyticsQueryKeys.summary(),
    queryFn: () => fetchCostAnalytics(),
    enabled,
    staleTime,
    retry,
    refetchInterval: refetchInterval > 0 ? refetchInterval : undefined,
  });

  // Derived values
  const todayCost = useMemo(() => query.data?.today, [query.data]);
  const dailyBudget = useMemo(() => query.data?.daily_budget, [query.data]);
  const monthlyBudget = useMemo(() => query.data?.monthly_budget, [query.data]);
  const costHistory = useMemo(() => query.data?.cost_history ?? [], [query.data]);

  const todayTotalCost = useMemo(() => query.data?.today.total_cost_usd ?? 0, [query.data]);

  const dailyUtilizationRatio = useMemo(
    () => query.data?.daily_budget.utilization_ratio ?? 0,
    [query.data]
  );

  const monthlyUtilizationRatio = useMemo(
    () => query.data?.monthly_budget.utilization_ratio ?? 0,
    [query.data]
  );

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
    todayCost,
    dailyBudget,
    monthlyBudget,
    costHistory,
    todayTotalCost,
    dailyUtilizationRatio,
    monthlyUtilizationRatio,
  };
}

/**
 * Options for configuring the useCostTrendsQuery hook
 */
export type UseCostTrendsQueryOptions = UseCostAnalyticsQueryOptions;

/**
 * Return type for the useCostTrendsQuery hook
 */
export interface UseCostTrendsQueryReturn {
  /** Raw API response data */
  data: CostTrendResponse | undefined;
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

  // Derived values
  /** Trend data points for charting */
  dataPoints: { date: string; cost_usd: number }[];
  /** Total cost over the period */
  totalCost: number;
}

/**
 * Hook to fetch cost trend data for a date range.
 *
 * Returns daily cost totals suitable for trend visualization.
 *
 * @param params - Date range parameters
 * @param options - Configuration options
 * @returns Cost trend data and query state
 *
 * @example
 * ```tsx
 * const { dataPoints, totalCost, isLoading } = useCostTrendsQuery({
 *   start_date: '2026-01-01',
 *   end_date: '2026-01-31',
 * });
 *
 * return <LineChart data={dataPoints} />;
 * ```
 */
export function useCostTrendsQuery(
  params: CostTrendParams,
  options: UseCostTrendsQueryOptions = {}
): UseCostTrendsQueryReturn {
  const {
    enabled = true,
    staleTime = DEFAULT_STALE_TIME,
    retry = 1,
    refetchInterval = 0, // No auto-refresh for historical data
  } = options;

  // Only enable query if valid date params
  const isValidParams = Boolean(params.start_date && params.end_date);
  const queryEnabled = enabled && isValidParams;

  const query = useQuery<CostTrendResponse, Error>({
    queryKey: costAnalyticsQueryKeys.trends.byDateRange(params),
    queryFn: () => fetchCostTrends(params),
    enabled: queryEnabled,
    staleTime,
    retry,
    refetchInterval: refetchInterval > 0 ? refetchInterval : undefined,
  });

  const dataPoints = useMemo(() => query.data?.data_points ?? [], [query.data]);
  const totalCost = useMemo(() => query.data?.total_cost_usd ?? 0, [query.data]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
    dataPoints,
    totalCost,
  };
}

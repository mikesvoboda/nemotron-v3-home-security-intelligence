/**
 * Custom hook for fetching trend data.
 *
 * Provides trend sparkline data with automatic polling and caching.
 *
 * @see NEM-5406/5407/5408/5409 - Feature 5: Trend Comparison Sparklines
 */

import { useQuery } from '@tanstack/react-query';
import { useCallback } from 'react';

import type { TrendsData, TrendType } from '@/types/trends';

import { fetchTrends } from '@/services/api';

/**
 * Query key factory for trends data.
 */
export const trendsQueryKeys = {
  all: ['trends'] as const,
  byType: (type: TrendType) => ['trends', type] as const,
};

/**
 * Configuration options for useTrends hook.
 */
export interface UseTrendsOptions {
  /** Type of trend: 'hourly' (5-min buckets) or 'daily' (1-hour buckets) */
  type?: TrendType;
  /** Whether to enable automatic refetching */
  enabled?: boolean;
  /** Polling interval in milliseconds (default: 2 minutes) */
  refetchInterval?: number;
}

/**
 * Return type for useTrends hook.
 */
export interface UseTrendsResult {
  /** Trends data */
  data: TrendsData | null;
  /** Whether data is being fetched for the first time */
  isLoading: boolean;
  /** Whether data is being refetched in background */
  isFetching: boolean;
  /** Error if fetch failed */
  error: Error | null;
  /** Manually trigger a refetch */
  refetch: () => Promise<void>;
}

/**
 * Hook for fetching trend data with automatic polling.
 *
 * Returns time-bucketed event metrics with rolling 24-hour baseline comparisons
 * for dashboard sparkline visualization.
 *
 * @param options - Configuration options
 * @returns UseTrendsResult with data, loading state, error, and refetch function
 *
 * @example
 * ```tsx
 * function TrendDisplay() {
 *   const { data, isLoading, error, refetch } = useTrends({ type: 'hourly' });
 *
 *   if (isLoading) return <Loading />;
 *   if (error) return <Error message={error.message} onRetry={refetch} />;
 *   if (!data) return <Empty />;
 *
 *   return (
 *     <TrendSparklines data={data} />
 *   );
 * }
 * ```
 */
export function useTrends(options: UseTrendsOptions = {}): UseTrendsResult {
  const { type = 'hourly', enabled = true, refetchInterval = 2 * 60 * 1000 } = options;

  const query = useQuery({
    queryKey: trendsQueryKeys.byType(type),
    queryFn: () => fetchTrends(type),
    enabled,
    refetchInterval,
    staleTime: 60 * 1000, // Consider data stale after 1 minute
    gcTime: 5 * 60 * 1000, // Keep in cache for 5 minutes
  });

  const refetch = useCallback(async () => {
    await query.refetch();
  }, [query]);

  return {
    data: query.data ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error ?? null,
    refetch,
  };
}

export default useTrends;

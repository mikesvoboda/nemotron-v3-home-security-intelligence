/**
 * usePerformanceHistory Hook
 *
 * Fetches historical performance snapshots over specified time range.
 * Provides loading, error, and refetch states for UI consumption.
 */

import { useState, useEffect, useCallback } from 'react';

import {
  getPerformanceHistory,
  type PerformanceSnapshot,
  type TimeRange,
} from '../services/performanceHistoryApi';

// Re-export the PerformanceSnapshot type for consumers
export type { PerformanceSnapshot };

/**
 * Result returned by the usePerformanceHistory hook.
 */
export interface UsePerformanceHistoryResult {
  /** Array of performance snapshots */
  snapshots: PerformanceSnapshot[];
  /** Whether data is currently being loaded */
  isLoading: boolean;
  /** Error that occurred during fetch, if any */
  error: Error | null;
  /** Current time range parameter */
  timeRange: string;
  /** Function to manually refetch the data */
  refetch: () => void;
}

/**
 * usePerformanceHistory - Hook for fetching historical performance data
 *
 * Fetches performance snapshots from the API for the specified time range.
 * Automatically refetches when the time range changes.
 *
 * @param timeRange - Time range to fetch ('5m', '15m', or '60m')
 * @returns Object with snapshots, loading state, error, and refetch function
 *
 * @example
 * ```tsx
 * const { snapshots, isLoading, error, refetch } = usePerformanceHistory('5m');
 *
 * if (isLoading) return <Loading />;
 * if (error) return <Error message={error.message} />;
 *
 * return <Chart data={snapshots} />;
 * ```
 */
export function usePerformanceHistory(
  timeRange: TimeRange = '5m'
): UsePerformanceHistoryResult {
  const [snapshots, setSnapshots] = useState<PerformanceSnapshot[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await getPerformanceHistory(timeRange);
      // Handle malformed responses gracefully
      if (response.snapshots === null || response.snapshots === undefined) {
        setSnapshots([]);
        setError(new Error('Invalid response: snapshots is null'));
      } else {
        setSnapshots(response.snapshots);
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
      setSnapshots([]);
    } finally {
      setIsLoading(false);
    }
  }, [timeRange]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const refetch = useCallback(() => {
    void fetchData();
  }, [fetchData]);

  return {
    snapshots,
    isLoading,
    error,
    timeRange,
    refetch,
  };
}

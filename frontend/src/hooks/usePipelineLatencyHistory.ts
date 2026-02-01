/**
 * usePipelineLatencyHistory Hook
 *
 * Fetches historical pipeline latency stages data over time.
 * Provides loading, error, and refetch states for UI consumption.
 * Includes chart-ready data transformation with stage breakdowns.
 */

import { useState, useEffect, useCallback, useMemo } from 'react';

import {
  getPipelineLatencyHistory,
  type PipelineLatencyHistoryResponse,
  type PipelineLatencySnapshot,
  type StageLatency,
} from '../services/pipelineLatencyApi';

// Re-export types for consumers
export type { PipelineLatencySnapshot, StageLatency, PipelineLatencyHistoryResponse };

/**
 * Chart data point formatted for Tremor charts with all stage latencies.
 */
export interface PipelineLatencyChartDataPoint {
  /** Formatted timestamp for display */
  timestamp: string;
  /** Watch to detect stage average latency (ms) */
  watch_to_detect: number;
  /** Detect to batch stage average latency (ms) */
  detect_to_batch: number;
  /** Batch to analyze stage average latency (ms) */
  batch_to_analyze: number;
  /** Total pipeline average latency (ms) */
  total_pipeline: number;
}

/**
 * Chart data point formatted for percentile visualization.
 * Shows P50/P95/P99 for total pipeline latency.
 */
export interface PipelinePercentileChartDataPoint {
  /** Formatted timestamp for display */
  timestamp: string;
  /** 50th percentile (median) latency (ms) */
  P50: number;
  /** 95th percentile latency (ms) */
  P95: number;
  /** 99th percentile latency (ms) */
  P99: number;
}

/**
 * Options for the usePipelineLatencyHistory hook.
 */
export interface UsePipelineLatencyHistoryOptions {
  /** Time window in minutes (how far back to look, default: 60) */
  since?: number;
  /** Bucket size in seconds (aggregation granularity, default: 60) */
  bucket_seconds?: number;
}

/**
 * Result returned by the usePipelineLatencyHistory hook.
 */
export interface UsePipelineLatencyHistoryResult {
  /** Raw response data from the API */
  data: PipelineLatencyHistoryResponse | undefined;
  /** Whether data is currently being loaded */
  isLoading: boolean;
  /** Error that occurred during fetch, if any */
  error: Error | null;
  /** Function to manually refetch the data */
  refetch: () => void;
  /** Chart-ready data formatted for Tremor (averages by stage) */
  chartData: PipelineLatencyChartDataPoint[] | undefined;
  /** Percentile chart data for total pipeline (P50/P95/P99) */
  percentileChartData: PipelinePercentileChartDataPoint[] | undefined;
}

/**
 * Format timestamp for chart display.
 *
 * @param isoString - ISO 8601 timestamp string
 * @returns Formatted time string (e.g., "10:00")
 */
function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    });
  } catch {
    return isoString;
  }
}

/**
 * Transform pipeline latency snapshots to chart-ready format.
 *
 * @param snapshots - Array of pipeline latency snapshots from API
 * @returns Array of chart data points
 */
function transformToChartData(
  snapshots: PipelineLatencySnapshot[]
): PipelineLatencyChartDataPoint[] {
  return snapshots.map((snapshot) => ({
    timestamp: formatTimestamp(snapshot.timestamp),
    watch_to_detect: snapshot.stages.watch_to_detect?.avg_ms ?? 0,
    detect_to_batch: snapshot.stages.detect_to_batch?.avg_ms ?? 0,
    batch_to_analyze: snapshot.stages.batch_to_analyze?.avg_ms ?? 0,
    total_pipeline: snapshot.stages.total_pipeline?.avg_ms ?? 0,
  }));
}

/**
 * Transform pipeline latency snapshots to percentile chart format.
 * Uses total_pipeline percentiles (P50/P95/P99).
 *
 * @param snapshots - Array of pipeline latency snapshots from API
 * @returns Array of percentile chart data points
 */
function transformToPercentileChartData(
  snapshots: PipelineLatencySnapshot[]
): PipelinePercentileChartDataPoint[] {
  return snapshots.map((snapshot) => ({
    timestamp: formatTimestamp(snapshot.timestamp),
    P50: snapshot.stages.total_pipeline?.p50_ms ?? 0,
    P95: snapshot.stages.total_pipeline?.p95_ms ?? 0,
    P99: snapshot.stages.total_pipeline?.p99_ms ?? 0,
  }));
}

/**
 * usePipelineLatencyHistory - Hook for fetching historical pipeline latency metrics
 *
 * Fetches pipeline latency history from the API with configurable time window
 * and bucket size. Provides both raw data and chart-ready transformed data.
 *
 * @param options - Hook options including since and bucket_seconds
 * @returns Object with data, loading state, error, refetch function, and chartData
 *
 * @example
 * ```tsx
 * const { data, isLoading, error, chartData, refetch } = usePipelineLatencyHistory({
 *   since: 60,
 *   bucket_seconds: 60,
 * });
 *
 * if (isLoading) return <Loading />;
 * if (error) return <Error message={error.message} />;
 *
 * return <AreaChart data={chartData} />;
 * ```
 */
export function usePipelineLatencyHistory(
  options: UsePipelineLatencyHistoryOptions = {}
): UsePipelineLatencyHistoryResult {
  const { since = 60, bucket_seconds = 60 } = options;

  const [data, setData] = useState<PipelineLatencyHistoryResponse | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await getPipelineLatencyHistory({ since, bucket_seconds });
      setData(response);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
      setData(undefined);
    } finally {
      setIsLoading(false);
    }
  }, [since, bucket_seconds]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const refetch = useCallback(() => {
    void fetchData();
  }, [fetchData]);

  // Transform data for chart consumption
  const chartData = useMemo(() => {
    if (!data?.snapshots) return undefined;
    return transformToChartData(data.snapshots);
  }, [data]);

  // Transform data for percentile chart consumption
  const percentileChartData = useMemo(() => {
    if (!data?.snapshots) return undefined;
    return transformToPercentileChartData(data.snapshots);
  }, [data]);

  return {
    data,
    isLoading,
    error,
    refetch,
    chartData,
    percentileChartData,
  };
}

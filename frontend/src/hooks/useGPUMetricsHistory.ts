/**
 * useGPUMetricsHistory Hook
 *
 * Fetches historical GPU utilization, temperature, and memory usage data.
 * Provides loading, error, and refetch states for UI consumption.
 * Includes chart-ready data transformation.
 *
 * NOTE: This is renamed from useGPUHistory to avoid case collision with
 * the existing useGpuHistory hook (which uses polling instead of API fetch).
 */

import { useState, useEffect, useCallback, useMemo } from 'react';

import {
  getGPUHistory,
  type GPUHistoryResponse,
  type GPUHistoryItem,
} from '../services/gpuHistoryApi';

// Re-export types for consumers
export type { GPUHistoryItem, GPUHistoryResponse };

/**
 * Chart data point formatted for Tremor charts.
 */
export interface GPUChartDataPoint {
  /** Formatted timestamp for display */
  timestamp: string;
  /** GPU utilization percentage */
  utilization: number;
  /** GPU temperature in Celsius */
  temperature: number;
  /** Memory used in MB */
  memory_used: number;
  /** Memory usage percentage */
  memory_percent: number;
  /** Power usage in watts */
  power_usage: number;
  /** Inference FPS */
  inference_fps: number;
}

/**
 * Options for the useGPUMetricsHistory hook.
 */
export interface UseGPUMetricsHistoryOptions {
  /** Maximum number of records to fetch (default: 300) */
  limit?: number;
}

/**
 * Result returned by the useGPUMetricsHistory hook.
 */
export interface UseGPUMetricsHistoryResult {
  /** Raw response data from the API */
  data: GPUHistoryResponse | undefined;
  /** Whether data is currently being loaded */
  isLoading: boolean;
  /** Error that occurred during fetch, if any */
  error: Error | null;
  /** Function to manually refetch the data */
  refetch: () => void;
  /** Chart-ready data formatted for Tremor */
  chartData: GPUChartDataPoint[] | undefined;
}

/**
 * Format timestamp for chart display.
 *
 * @param isoString - ISO 8601 timestamp string
 * @returns Formatted time string (e.g., "10:00:00")
 */
function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return isoString;
  }
}

/**
 * Transform GPU history items to chart-ready format.
 *
 * @param items - Array of GPU history items from API
 * @returns Array of chart data points
 */
function transformToChartData(items: GPUHistoryItem[]): GPUChartDataPoint[] {
  return items.map((item) => ({
    timestamp: formatTimestamp(item.recorded_at),
    utilization: item.utilization,
    temperature: item.temperature,
    memory_used: item.memory_used,
    memory_percent:
      item.memory_total > 0 ? (item.memory_used / item.memory_total) * 100 : 0,
    power_usage: item.power_usage,
    inference_fps: item.inference_fps,
  }));
}

/**
 * useGPUMetricsHistory - Hook for fetching historical GPU metrics
 *
 * Fetches GPU history from the API with configurable limit.
 * Provides both raw data and chart-ready transformed data.
 *
 * @param options - Hook options including limit
 * @returns Object with data, loading state, error, refetch function, and chartData
 *
 * @example
 * ```tsx
 * const { data, isLoading, error, chartData, refetch } = useGPUMetricsHistory({ limit: 300 });
 *
 * if (isLoading) return <Loading />;
 * if (error) return <Error message={error.message} />;
 *
 * return <AreaChart data={chartData} />;
 * ```
 */
export function useGPUMetricsHistory(options: UseGPUMetricsHistoryOptions = {}): UseGPUMetricsHistoryResult {
  const { limit = 300 } = options;

  const [data, setData] = useState<GPUHistoryResponse | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await getGPUHistory(limit);
      setData(response);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
      setData(undefined);
    } finally {
      setIsLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  const refetch = useCallback(() => {
    void fetchData();
  }, [fetchData]);

  // Transform data for chart consumption
  const chartData = useMemo(() => {
    if (!data?.items) return undefined;
    return transformToChartData(data.items);
  }, [data]);

  return {
    data,
    isLoading,
    error,
    refetch,
    chartData,
  };
}

/**
 * useGpuStatsQuery - TanStack Query hooks for GPU statistics
 *
 * This module provides hooks for fetching GPU metrics using TanStack Query.
 * It replaces the manual polling implementation in useGpuHistory with
 * automatic caching, deduplication, and background refetching.
 *
 * Benefits over the original useGpuHistory:
 * - Automatic request deduplication across components
 * - Built-in caching with configurable stale time
 * - Background refetching with refetchInterval
 * - DevTools integration for debugging
 *
 * @module hooks/useGpuStatsQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchGPUStats,
  fetchGpuHistory,
  type GPUStats,
  type GPUStatsHistoryResponse,
} from '../services/api';
import { queryKeys, REALTIME_STALE_TIME } from '../services/queryClient';

// ============================================================================
// useGpuStatsQuery - Fetch current GPU stats
// ============================================================================

/**
 * Options for configuring the useGpuStatsQuery hook
 */
export interface UseGpuStatsQueryOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default 5000 (5 seconds for real-time data)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * @default REALTIME_STALE_TIME (5 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useGpuStatsQuery hook
 */
export interface UseGpuStatsQueryReturn {
  /** Current GPU stats, undefined if not yet fetched */
  data: GPUStats | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the data is stale */
  isStale: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** GPU utilization percentage (0-100), null if unavailable */
  utilization: number | null;
  /** Memory used in MB, null if unavailable */
  memoryUsed: number | null;
  /** Temperature in Celsius, null if unavailable */
  temperature: number | null;
}

/**
 * Hook to fetch current GPU statistics using TanStack Query.
 *
 * This hook fetches from GET /api/system/gpu and provides:
 * - Automatic caching and request deduplication
 * - Configurable polling via refetchInterval
 * - Derived values for common GPU metrics
 *
 * @param options - Configuration options
 * @returns GPU stats data and query state
 *
 * @example
 * ```tsx
 * // Basic usage with default 5s polling
 * const { data, isLoading, utilization, temperature } = useGpuStatsQuery({
 *   refetchInterval: 5000,
 * });
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <div>
 *     <span>Utilization: {utilization ?? 'N/A'}%</span>
 *     <span>Temperature: {temperature ?? 'N/A'}°C</span>
 *   </div>
 * );
 * ```
 */
export function useGpuStatsQuery(
  options: UseGpuStatsQueryOptions = {}
): UseGpuStatsQueryReturn {
  const {
    enabled = true,
    refetchInterval = 5000,
    staleTime = REALTIME_STALE_TIME,
  } = options;

  const query = useQuery({
    queryKey: queryKeys.system.gpu,
    queryFn: fetchGPUStats,
    enabled,
    refetchInterval,
    staleTime,
    // Reduced retry for real-time data
    retry: 1,
  });

  // Derive common metrics
  const utilization = useMemo(
    () => query.data?.utilization ?? null,
    [query.data?.utilization]
  );

  const memoryUsed = useMemo(
    () => query.data?.memory_used ?? null,
    [query.data?.memory_used]
  );

  const temperature = useMemo(
    () => query.data?.temperature ?? null,
    [query.data?.temperature]
  );

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isStale: query.isStale,
    refetch: query.refetch,
    utilization,
    memoryUsed,
    temperature,
  };
}

// ============================================================================
// useGpuHistoryQuery - Fetch GPU stats history
// ============================================================================

/**
 * Options for configuring the useGpuHistoryQuery hook
 */
export interface UseGpuHistoryQueryOptions {
  /**
   * Number of historical data points to fetch.
   * @default 60
   */
  limit?: number;

  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default 5000 (5 seconds)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * @default REALTIME_STALE_TIME (5 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useGpuHistoryQuery hook
 */
export interface UseGpuHistoryQueryReturn {
  /** GPU history response, undefined if not yet fetched */
  data: GPUStatsHistoryResponse | undefined;
  /** Array of historical GPU stats samples */
  history: GPUStatsHistoryResponse['samples'];
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch GPU statistics history using TanStack Query.
 *
 * This hook fetches historical GPU metrics from GET /api/system/gpu/history
 * for time-series visualization.
 *
 * @param options - Configuration options
 * @returns GPU history data and query state
 *
 * @example
 * ```tsx
 * const { history, isLoading } = useGpuHistoryQuery({
 *   limit: 60, // Last 60 data points
 *   refetchInterval: 5000, // Refresh every 5 seconds
 * });
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <LineChart data={history.map(s => ({
 *     time: s.recorded_at,
 *     utilization: s.utilization,
 *   }))} />
 * );
 * ```
 */
export function useGpuHistoryQuery(
  options: UseGpuHistoryQueryOptions = {}
): UseGpuHistoryQueryReturn {
  const {
    limit = 60,
    enabled = true,
    refetchInterval = 5000,
    staleTime = REALTIME_STALE_TIME,
  } = options;

  const query = useQuery({
    queryKey: queryKeys.system.gpuHistory(limit),
    queryFn: () => fetchGpuHistory(limit),
    enabled,
    refetchInterval,
    staleTime,
    retry: 1,
  });

  // Provide empty array as default
  const history = useMemo(() => query.data?.samples ?? [], [query.data?.samples]);

  return {
    data: query.data,
    history,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
  };
}

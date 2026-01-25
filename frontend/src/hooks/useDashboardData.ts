/**
 * useDashboardData - Parallel data fetching hook for the Dashboard
 *
 * This hook demonstrates TanStack Query v5 patterns for fetching multiple
 * independent data sources in parallel:
 *
 * - useQueries for parallel data fetching (NEM-3412)
 * - placeholderData for better UX during loading (NEM-3409)
 * - select for data transformation at query level (NEM-3410)
 * - AbortSignal for proper query cancellation on unmount (NEM-3411)
 *
 * @module hooks/useDashboardData
 * @see NEM-3409 - placeholderData pattern
 * @see NEM-3410 - select option for data transformation
 * @see NEM-3411 - AbortSignal for query cancellation
 * @see NEM-3412 - parallel queries with useQueries
 */

import { useQueries } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  createPlaceholderCameras,
  createPlaceholderHealthStatus,
  createPlaceholderEventStats,
  createPlaceholderGpuStats,
  selectOnlineCameras,
  selectHealthSummary,
  selectRiskDistribution,
} from './useQueryPatterns';
import {
  fetchCameras,
  fetchHealth,
  fetchEventStats,
  fetchGPUStats,
  type Camera,
  type HealthResponse,
  type EventStatsResponse,
  type GPUStats,
} from '../services/api';
import { queryKeys, DEFAULT_STALE_TIME, REALTIME_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the useDashboardData hook
 */
export interface UseDashboardDataOptions {
  /**
   * Whether to enable all queries.
   * @default true
   */
  enabled?: boolean;

  /**
   * Whether to include GPU stats in the parallel fetch.
   * @default false
   */
  includeGpuStats?: boolean;

  /**
   * Date range for event stats query.
   */
  eventStatsDateRange?: {
    start_date?: string;
    end_date?: string;
  };
}

/**
 * Aggregated dashboard data from parallel queries
 */
export interface DashboardData {
  /** All cameras */
  cameras: Camera[];
  /** Online cameras only (via select) */
  onlineCameras: Camera[];
  /** Health status */
  health: HealthResponse | undefined;
  /** Health summary (via select) */
  healthSummary:
    | {
        status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
        serviceCount: number;
        healthyServiceCount: number;
        timestamp: string;
      }
    | undefined;
  /** Event statistics */
  eventStats: EventStatsResponse | undefined;
  /** Risk distribution (via select) */
  riskDistribution:
    | {
        low: number;
        medium: number;
        high: number;
        lowPercent: number;
        mediumPercent: number;
        highPercent: number;
      }
    | undefined;
  /** GPU statistics (if enabled) */
  gpuStats: GPUStats | undefined;
}

/**
 * Return type for useDashboardData hook
 */
export interface UseDashboardDataReturn {
  /** Aggregated dashboard data */
  data: DashboardData;
  /** Whether any query is in initial loading state */
  isLoading: boolean;
  /** Whether all queries have completed (regardless of success/error) */
  isComplete: boolean;
  /** Whether any query has an error */
  hasErrors: boolean;
  /** Errors by query key */
  errors: {
    cameras?: Error;
    health?: Error;
    eventStats?: Error;
    gpuStats?: Error;
  };
  /** Whether any data is placeholder data */
  isPlaceholderData: boolean;
  /** Individual query states for fine-grained UI control */
  queryStates: {
    cameras: { isLoading: boolean; isError: boolean; isPlaceholderData: boolean };
    health: { isLoading: boolean; isError: boolean; isPlaceholderData: boolean };
    eventStats: { isLoading: boolean; isError: boolean; isPlaceholderData: boolean };
    gpuStats?: { isLoading: boolean; isError: boolean; isPlaceholderData: boolean };
  };
  /** Refetch all queries */
  refetchAll: () => void;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for fetching all dashboard data in parallel.
 *
 * Uses TanStack Query's useQueries to execute multiple independent queries
 * simultaneously, improving page load performance. Each query uses:
 * - AbortSignal for proper cancellation on unmount (NEM-3411)
 * - placeholderData for immediate UI feedback (NEM-3409)
 * - select for efficient data transformation (NEM-3410)
 *
 * @param options - Configuration options
 * @returns Aggregated dashboard data with loading/error states
 *
 * @example
 * ```tsx
 * const { data, isLoading, hasErrors, isPlaceholderData } = useDashboardData({
 *   includeGpuStats: true,
 *   eventStatsDateRange: { start_date: '2024-01-01' },
 * });
 *
 * // Render with loading awareness
 * return (
 *   <div className={isPlaceholderData ? 'animate-pulse' : ''}>
 *     <CameraGrid cameras={data.onlineCameras} />
 *     <HealthStatus summary={data.healthSummary} />
 *     <RiskChart distribution={data.riskDistribution} />
 *     {data.gpuStats && <GpuPanel stats={data.gpuStats} />}
 *   </div>
 * );
 * ```
 */
export function useDashboardData(options: UseDashboardDataOptions = {}): UseDashboardDataReturn {
  const { enabled = true, includeGpuStats = false, eventStatsDateRange } = options;

  // Create stable placeholder data references (NEM-3409)
  const cameraPlaceholder = useMemo(() => createPlaceholderCameras(6), []);
  const healthPlaceholder = useMemo(() => createPlaceholderHealthStatus(), []);
  const eventStatsPlaceholder = useMemo(() => createPlaceholderEventStats(), []);
  const gpuStatsPlaceholder = useMemo(() => createPlaceholderGpuStats(), []);

  // Build query configurations for parallel execution (NEM-3412)
  // Using explicit types to avoid inference issues with heterogeneous query configs
  const queryConfigs = useMemo(() => {
    // Base configurations for cameras, health, and event stats
    const configs: Array<{
      queryKey: readonly unknown[];
      queryFn: (context: { signal: AbortSignal }) => Promise<unknown>;
      placeholderData: unknown;
      staleTime: number;
      enabled: boolean;
    }> = [
      // Cameras query - AbortSignal integration (NEM-3411)
      {
        queryKey: queryKeys.cameras.list(),
        queryFn: ({ signal }) => fetchCameras({ signal }),
        placeholderData: cameraPlaceholder,
        staleTime: DEFAULT_STALE_TIME,
        enabled,
      },
      // Health query - AbortSignal integration (NEM-3411)
      {
        queryKey: queryKeys.system.health,
        queryFn: ({ signal }) => fetchHealth({ signal }),
        placeholderData: healthPlaceholder,
        staleTime: REALTIME_STALE_TIME,
        enabled,
      },
      // Event stats query - AbortSignal integration (NEM-3411)
      {
        queryKey: queryKeys.events.stats(eventStatsDateRange),
        queryFn: ({ signal }) => fetchEventStats(eventStatsDateRange, { signal }),
        placeholderData: eventStatsPlaceholder,
        staleTime: DEFAULT_STALE_TIME,
        enabled,
      },
    ];

    // Optionally include GPU stats - AbortSignal integration (NEM-3411)
    if (includeGpuStats) {
      configs.push({
        queryKey: queryKeys.system.gpu,
        queryFn: ({ signal }) => fetchGPUStats({ signal }),
        placeholderData: gpuStatsPlaceholder,
        staleTime: REALTIME_STALE_TIME,
        enabled,
      });
    }

    return configs;
  }, [
    enabled,
    includeGpuStats,
    eventStatsDateRange,
    cameraPlaceholder,
    healthPlaceholder,
    eventStatsPlaceholder,
    gpuStatsPlaceholder,
  ]);

  // Execute all queries in parallel using useQueries (NEM-3412)
  const results = useQueries({ queries: queryConfigs });

  // Extract individual query results
  const [camerasResult, healthResult, eventStatsResult, gpuStatsResult] = results;

  // Apply select transformations (NEM-3410)
  const onlineCameras = useMemo(() => {
    const cameras = camerasResult?.data as Camera[] | undefined;
    return cameras ? selectOnlineCameras(cameras) : [];
  }, [camerasResult?.data]);

  const healthSummary = useMemo(() => {
    const health = healthResult?.data as HealthResponse | undefined;
    return health ? selectHealthSummary(health) : undefined;
  }, [healthResult?.data]);

  const riskDistribution = useMemo(() => {
    const stats = eventStatsResult?.data as EventStatsResponse | undefined;
    return stats ? selectRiskDistribution(stats) : undefined;
  }, [eventStatsResult?.data]);

  // Aggregate data
  const data: DashboardData = useMemo(
    () => ({
      cameras: (camerasResult?.data as Camera[]) ?? [],
      onlineCameras,
      health: healthResult?.data as HealthResponse | undefined,
      healthSummary,
      eventStats: eventStatsResult?.data as EventStatsResponse | undefined,
      riskDistribution,
      gpuStats: includeGpuStats ? (gpuStatsResult?.data as GPUStats | undefined) : undefined,
    }),
    [
      camerasResult?.data,
      onlineCameras,
      healthResult?.data,
      healthSummary,
      eventStatsResult?.data,
      riskDistribution,
      includeGpuStats,
      gpuStatsResult?.data,
    ]
  );

  // Aggregate loading state
  const isLoading = results.some((r) => r.isLoading);
  const isComplete = results.every((r) => r.fetchStatus === 'idle');
  const hasErrors = results.some((r) => r.isError);
  const isPlaceholderData = results.some((r) => r.isPlaceholderData);

  // Collect errors
  const errors = useMemo(() => {
    const errs: UseDashboardDataReturn['errors'] = {};
    if (camerasResult?.error) errs.cameras = camerasResult.error;
    if (healthResult?.error) errs.health = healthResult.error;
    if (eventStatsResult?.error) errs.eventStats = eventStatsResult.error;
    if (gpuStatsResult?.error) errs.gpuStats = gpuStatsResult.error;
    return errs;
  }, [camerasResult?.error, healthResult?.error, eventStatsResult?.error, gpuStatsResult?.error]);

  // Individual query states
  const queryStates = useMemo(
    () => ({
      cameras: {
        isLoading: camerasResult?.isLoading ?? false,
        isError: camerasResult?.isError ?? false,
        isPlaceholderData: camerasResult?.isPlaceholderData ?? false,
      },
      health: {
        isLoading: healthResult?.isLoading ?? false,
        isError: healthResult?.isError ?? false,
        isPlaceholderData: healthResult?.isPlaceholderData ?? false,
      },
      eventStats: {
        isLoading: eventStatsResult?.isLoading ?? false,
        isError: eventStatsResult?.isError ?? false,
        isPlaceholderData: eventStatsResult?.isPlaceholderData ?? false,
      },
      ...(includeGpuStats && gpuStatsResult
        ? {
            gpuStats: {
              isLoading: gpuStatsResult.isLoading,
              isError: gpuStatsResult.isError,
              isPlaceholderData: gpuStatsResult.isPlaceholderData,
            },
          }
        : {}),
    }),
    [
      camerasResult?.isLoading,
      camerasResult?.isError,
      camerasResult?.isPlaceholderData,
      healthResult?.isLoading,
      healthResult?.isError,
      healthResult?.isPlaceholderData,
      eventStatsResult?.isLoading,
      eventStatsResult?.isError,
      eventStatsResult?.isPlaceholderData,
      includeGpuStats,
      gpuStatsResult,
    ]
  );

  // Refetch all queries
  const refetchAll = () => {
    results.forEach((result) => {
      void result.refetch();
    });
  };

  return {
    data,
    isLoading,
    isComplete,
    hasErrors,
    errors,
    isPlaceholderData,
    queryStates,
    refetchAll,
  };
}

export default useDashboardData;

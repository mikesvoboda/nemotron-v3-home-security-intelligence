/**
 * TanStack Query v5 Advanced Patterns
 *
 * This module provides utility functions and patterns for optimizing data fetching:
 *
 * 1. **placeholderData**: Provide meaningful skeleton data during loading states
 * 2. **select**: Transform API responses at the query level for efficient memoization
 * 3. **AbortSignal**: Proper query cancellation on unmount via queryFn context
 * 4. **useQueries**: Parallel queries for dashboard data that can be fetched independently
 *
 * @module hooks/useQueryPatterns
 * @see NEM-3409 - Implement placeholderData pattern
 * @see NEM-3410 - Implement select option for data transformation
 * @see NEM-3411 - Integrate AbortSignal for query cancellation
 * @see NEM-3412 - Implement parallel queries with useQueries
 */

import { useQueries, type UseQueryOptions, type QueryKey } from '@tanstack/react-query';
import { useMemo } from 'react';

import type { Camera } from '../services/api';
import type {
  HealthResponse,
  GPUStats,
  EventStatsResponse,
  ServiceStatus,
} from '../types/generated';

// ============================================================================
// PlaceholderData Factories (NEM-3409)
// ============================================================================

/**
 * Creates placeholder camera data for loading states.
 * Provides meaningful skeleton data that matches the expected shape.
 *
 * @param count - Number of placeholder cameras to create
 * @returns Array of placeholder Camera objects
 *
 * @example
 * ```tsx
 * const { data } = useQuery({
 *   queryKey: ['cameras'],
 *   queryFn: fetchCameras,
 *   placeholderData: createPlaceholderCameras(6),
 * });
 * ```
 */
export function createPlaceholderCameras(count: number = 6): Camera[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `placeholder-${i}`,
    name: `Loading Camera ${i + 1}`,
    folder_path: '/loading',
    status: 'offline' as const,
    last_seen_at: null,
    created_at: new Date().toISOString(),
  }));
}

/**
 * Creates placeholder health status data for loading states.
 * Shows a "checking" status while the actual health check is in progress.
 *
 * @returns Placeholder HealthResponse object
 *
 * @example
 * ```tsx
 * const { data } = useQuery({
 *   queryKey: ['system', 'health'],
 *   queryFn: fetchHealth,
 *   placeholderData: createPlaceholderHealthStatus(),
 * });
 * ```
 */
export function createPlaceholderHealthStatus(): HealthResponse {
  const placeholderService: ServiceStatus = {
    status: 'unknown',
  };

  return {
    status: 'degraded',
    timestamp: new Date().toISOString(),
    services: {
      database: placeholderService,
      redis: placeholderService,
      detection_model: placeholderService,
      analysis_model: placeholderService,
    },
  };
}

/**
 * Creates placeholder GPU stats data for loading states.
 * Uses partial properties that match the GPUStatsResponse schema.
 *
 * @returns Placeholder GPUStats object
 */
export function createPlaceholderGpuStats(): GPUStats {
  // Return minimal placeholder data matching GPUStatsResponse schema
  // Most fields are optional in the generated type
  return {
    gpu_name: 'Loading GPU...',
    memory_used: 0,
    memory_total: 0,
    utilization: 0,
    temperature: 0,
    power_usage: 0,
    power_limit: 0,
  } as GPUStats;
}

/**
 * Creates placeholder event stats data for loading states.
 * Uses the shape matching EventStatsResponse schema.
 *
 * @returns Placeholder EventStatsResponse object
 */
export function createPlaceholderEventStats(): EventStatsResponse {
  return {
    total_events: 0,
    events_by_risk_level: {
      critical: 0,
      high: 0,
      low: 0,
      medium: 0,
    },
    events_by_camera: [],
  } as EventStatsResponse;
}

// ============================================================================
// Select Functions for Data Transformation (NEM-3410)
// ============================================================================

/**
 * Selects only online cameras from the camera list.
 * Use with the `select` option for efficient memoization.
 *
 * @param cameras - Array of all cameras
 * @returns Array of cameras with 'online' status
 *
 * @example
 * ```tsx
 * const { data: onlineCameras } = useQuery({
 *   queryKey: ['cameras'],
 *   queryFn: fetchCameras,
 *   select: selectOnlineCameras,
 * });
 * ```
 */
export function selectOnlineCameras(cameras: Camera[]): Camera[] {
  return cameras.filter((camera) => camera.status === 'online');
}

/**
 * Selects camera count by status from the camera list.
 *
 * @param cameras - Array of all cameras
 * @returns Object with counts by status
 */
export function selectCameraCountsByStatus(cameras: Camera[]): {
  online: number;
  offline: number;
  error: number;
  total: number;
} {
  const counts = { online: 0, offline: 0, error: 0, total: cameras.length };

  for (const camera of cameras) {
    if (camera.status === 'online') counts.online++;
    else if (camera.status === 'offline') counts.offline++;
    else if (camera.status === 'error') counts.error++;
  }

  return counts;
}

/**
 * Selects the overall status and service map from health response.
 *
 * @param health - Health response from API
 * @returns Simplified health status object
 */
export function selectHealthSummary(health: HealthResponse): {
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  serviceCount: number;
  healthyServiceCount: number;
  timestamp: string;
} {
  const services = Object.values(health.services);
  const healthyCount = services.filter((s) => s.status === 'healthy').length;

  return {
    status:
      health.status === 'healthy' || health.status === 'degraded' || health.status === 'unhealthy'
        ? health.status
        : 'unknown',
    serviceCount: services.length,
    healthyServiceCount: healthyCount,
    timestamp: health.timestamp,
  };
}

/**
 * Selects risk distribution from event stats.
 *
 * @param stats - Event stats response from API
 * @returns Risk distribution with percentages
 */
export function selectRiskDistribution(stats: EventStatsResponse): {
  low: number;
  medium: number;
  high: number;
  lowPercent: number;
  mediumPercent: number;
  highPercent: number;
} {
  const total = stats.total_events || 1; // Avoid division by zero
  const low = stats.events_by_risk_level.low ?? 0;
  const medium = stats.events_by_risk_level.medium ?? 0;
  const high = stats.events_by_risk_level.high ?? 0;

  return {
    low,
    medium,
    high,
    lowPercent: Math.round((low / total) * 100),
    mediumPercent: Math.round((medium / total) * 100),
    highPercent: Math.round((high / total) * 100),
  };
}

// ============================================================================
// AbortSignal Integration (NEM-3411)
// ============================================================================

/**
 * Type for query functions that accept an abort signal.
 * TanStack Query v5 passes the signal via the QueryFunctionContext.
 */
export interface QueryFnWithSignal<T> {
  (context: { signal: AbortSignal }): Promise<T>;
}

/**
 * Wraps a fetch function to use the AbortSignal from query context.
 * This enables proper cancellation when queries are aborted (e.g., on unmount).
 *
 * @param fetchFn - The original fetch function that accepts an optional signal
 * @returns A query function that extracts the signal from context
 *
 * @example
 * ```tsx
 * // In your API module
 * export async function fetchCameras(options?: { signal?: AbortSignal }): Promise<Camera[]> {
 *   return fetchApi('/api/cameras', { signal: options?.signal });
 * }
 *
 * // In your hook
 * const { data } = useQuery({
 *   queryKey: ['cameras'],
 *   queryFn: withAbortSignal(fetchCameras),
 * });
 * ```
 */
export function withAbortSignal<T>(
  fetchFn: (options?: { signal?: AbortSignal }) => Promise<T>
): QueryFnWithSignal<T> {
  return ({ signal }) => fetchFn({ signal });
}

/**
 * Creates a query function that passes the abort signal to the fetch call.
 * Alternative to withAbortSignal for inline usage.
 *
 * @param endpoint - The API endpoint to fetch
 * @param fetchFn - The fetch function that accepts endpoint and options
 * @returns A query function with proper abort signal handling
 *
 * @example
 * ```tsx
 * const { data } = useQuery({
 *   queryKey: ['camera', cameraId],
 *   queryFn: createSignalAwareQueryFn(
 *     `/api/cameras/${cameraId}`,
 *     (url, { signal }) => fetchApi(url, { signal })
 *   ),
 * });
 * ```
 */
export function createSignalAwareQueryFn<T>(
  endpoint: string,
  fetchFn: (endpoint: string, options: { signal: AbortSignal }) => Promise<T>
): QueryFnWithSignal<T> {
  return ({ signal }) => fetchFn(endpoint, { signal });
}

// ============================================================================
// Parallel Queries with useQueries (NEM-3412)
// ============================================================================

/**
 * Configuration for a dashboard query in the parallel queries pattern.
 */
export interface DashboardQueryConfig<TData, TSelected = TData> {
  /** Unique key for this query */
  key: string;
  /** Query key array for React Query */
  queryKey: QueryKey;
  /** Function to fetch the data */
  queryFn: QueryFnWithSignal<TData>;
  /** Optional selector to transform the data */
  select?: (data: TData) => TSelected;
  /** Optional placeholder data for loading states */
  placeholderData?: TData;
  /** Stale time in milliseconds */
  staleTime?: number;
  /** Whether to enable the query */
  enabled?: boolean;
}

/**
 * Result from a parallel dashboard query.
 */
export interface DashboardQueryResult<TData> {
  data: TData | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
  isPlaceholderData: boolean;
}

/**
 * Combined results from parallel dashboard queries.
 */
export interface DashboardQueriesResult<T extends Record<string, unknown>> {
  /** All query results by key */
  data: { [K in keyof T]: T[K] | undefined };
  /** Whether any query is loading */
  isLoading: boolean;
  /** Whether all queries have completed (successfully or with error) */
  isComplete: boolean;
  /** Whether any query has an error */
  hasErrors: boolean;
  /** Errors by query key */
  errors: { [K in keyof T]?: Error };
  /** Individual query states */
  queries: { [K in keyof T]: DashboardQueryResult<T[K]> };
}

/**
 * Hook for fetching multiple independent queries in parallel.
 * Useful for dashboard pages that need to load several data sources.
 *
 * @param configs - Array of query configurations
 * @returns Combined query results with aggregate loading/error states
 *
 * @example
 * ```tsx
 * const { data, isLoading, hasErrors } = useDashboardQueries([
 *   {
 *     key: 'cameras',
 *     queryKey: ['cameras'],
 *     queryFn: ({ signal }) => fetchCameras({ signal }),
 *     placeholderData: createPlaceholderCameras(6),
 *   },
 *   {
 *     key: 'health',
 *     queryKey: ['system', 'health'],
 *     queryFn: ({ signal }) => fetchHealth({ signal }),
 *     select: selectHealthSummary,
 *   },
 *   {
 *     key: 'eventStats',
 *     queryKey: ['events', 'stats'],
 *     queryFn: ({ signal }) => fetchEventStats({ signal }),
 *   },
 * ]);
 *
 * // Access individual results
 * const cameras = data.cameras; // Camera[] | undefined
 * const health = data.health; // HealthSummary | undefined
 * ```
 */
export function useDashboardQueries<
  TConfigs extends readonly DashboardQueryConfig<unknown, unknown>[],
>(
  configs: TConfigs
): DashboardQueriesResult<{
  [K in TConfigs[number]['key']]: Extract<TConfigs[number], { key: K }> extends DashboardQueryConfig<
    infer _TData,
    infer TSelected
  >
    ? TSelected
    : never;
}> {
  // Build query options from configs
  const queryOptions = configs.map(
    (config): UseQueryOptions<unknown, Error, unknown, QueryKey> => ({
      queryKey: config.queryKey,
      queryFn: config.queryFn,
      select: config.select,
      placeholderData: config.placeholderData,
      staleTime: config.staleTime,
      enabled: config.enabled ?? true,
    })
  );

  // Execute all queries in parallel
  const results = useQueries({ queries: queryOptions });

  // Aggregate results into a structured response
  return useMemo(() => {
    const data: Record<string, unknown> = {};
    const errors: Record<string, Error> = {};
    const queries: Record<string, DashboardQueryResult<unknown>> = {};

    let isLoading = false;
    let isComplete = true;
    let hasErrors = false;

    configs.forEach((config, index) => {
      const result = results[index];

      data[config.key] = result.data;
      queries[config.key] = {
        data: result.data,
        isLoading: result.isLoading,
        isError: result.isError,
        error: result.error,
        isPlaceholderData: result.isPlaceholderData,
      };

      if (result.isLoading) {
        isLoading = true;
        isComplete = false;
      }

      if (result.isError && result.error) {
        hasErrors = true;
        errors[config.key] = result.error;
      }

      if (result.fetchStatus === 'fetching') {
        isComplete = false;
      }
    });

    return {
      data,
      isLoading,
      isComplete,
      hasErrors,
      errors,
      queries,
    } as DashboardQueriesResult<{
      [K in TConfigs[number]['key']]: Extract<
        TConfigs[number],
        { key: K }
      > extends DashboardQueryConfig<infer _TData, infer TSelected>
        ? TSelected
        : never;
    }>;
  }, [configs, results]);
}

// ============================================================================
// Re-export for Convenience
// ============================================================================

export { useQueries } from '@tanstack/react-query';

/**
 * useHealthStatusQuery - TanStack Query hook for system health status
 *
 * This hook replaces the custom useHealthStatus hook with TanStack Query
 * for better caching, deduplication, and server-state management.
 *
 * Benefits over the original useHealthStatus:
 * - Automatic request deduplication (multiple components share one request)
 * - Built-in caching with configurable stale time
 * - Background refetching on window focus or network reconnect
 * - Optimistic updates and cache invalidation support
 * - DevTools integration for debugging
 * - AbortSignal integration for proper query cancellation (NEM-3411)
 * - PlaceholderData for better UX during loading states (NEM-3409)
 * - Select option for data transformation (NEM-3410)
 *
 * @module hooks/useHealthStatusQuery
 * @see NEM-3409 - placeholderData pattern
 * @see NEM-3410 - select option for data transformation
 * @see NEM-3411 - AbortSignal for query cancellation
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import { createPlaceholderHealthStatus, selectHealthSummary } from './useQueryPatterns';
import { fetchHealth, type HealthResponse, type ServiceStatus } from '../services/api';
import { queryKeys, REALTIME_STALE_TIME } from '../services/queryClient';

/**
 * Options for configuring the useHealthStatusQuery hook
 */
export interface UseHealthStatusQueryOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default false (no automatic polling - use for manual control)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * Data older than this will be refetched in the background.
   * @default REALTIME_STALE_TIME (5 seconds)
   */
  staleTime?: number;

  /**
   * Whether to use placeholder data during loading.
   * When true, shows a "checking" status while loading.
   * @default true
   * @see NEM-3409 - placeholderData pattern
   */
  usePlaceholder?: boolean;
}

/**
 * Return type for the useHealthStatusQuery hook
 */
export interface UseHealthStatusQueryReturn {
  /** Current health status from the API, undefined if not yet fetched */
  data: HealthResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the data is stale */
  isStale: boolean;
  /** Overall health status: 'healthy', 'degraded', 'unhealthy', or null if unknown */
  overallStatus: 'healthy' | 'degraded' | 'unhealthy' | null;
  /** Map of service names to their status */
  services: Record<string, ServiceStatus>;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Whether the data is placeholder data (NEM-3409) */
  isPlaceholderData: boolean;
}

/**
 * Hook to fetch system health status using TanStack Query.
 *
 * This hook fetches from GET /api/system/health and provides:
 * - Automatic caching and request deduplication
 * - Derived values for overall status and services
 * - Configurable polling via refetchInterval
 * - Manual refetch capability
 *
 * @param options - Configuration options
 * @returns Health status data and query state
 *
 * @example
 * ```tsx
 * // Basic usage
 * const { data, isLoading, error, overallStatus, services } = useHealthStatusQuery();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <div>
 *     <span>Status: {overallStatus}</span>
 *     {Object.entries(services).map(([name, status]) => (
 *       <span key={name}>{name}: {status.status}</span>
 *     ))}
 *   </div>
 * );
 * ```
 *
 * @example
 * ```tsx
 * // With polling
 * const { data, refetch } = useHealthStatusQuery({
 *   refetchInterval: 30000, // Poll every 30 seconds
 * });
 * ```
 *
 * @example
 * ```tsx
 * // Disabled until needed
 * const { data, refetch } = useHealthStatusQuery({
 *   enabled: isVisible,
 * });
 * ```
 */
export function useHealthStatusQuery(
  options: UseHealthStatusQueryOptions = {}
): UseHealthStatusQueryReturn {
  const {
    enabled = true,
    refetchInterval = false,
    staleTime = REALTIME_STALE_TIME,
    usePlaceholder = true,
  } = options;

  // Create stable placeholder data reference (NEM-3409)
  const placeholderData = useMemo(
    () => (usePlaceholder ? createPlaceholderHealthStatus() : undefined),
    [usePlaceholder]
  );

  const query = useQuery({
    queryKey: queryKeys.system.health,
    // AbortSignal integration (NEM-3411): Pass signal from queryFn context
    queryFn: ({ signal }) => fetchHealth({ signal }),
    enabled,
    refetchInterval,
    staleTime,
    // Disable retry for health checks to fail fast
    retry: 1,
    // PlaceholderData pattern (NEM-3409): Show "checking" status during loading
    placeholderData,
  });

  // Derive overall status from health response
  const overallStatus = useMemo((): 'healthy' | 'degraded' | 'unhealthy' | null => {
    const status = query.data?.status;
    if (status === 'healthy' || status === 'degraded' || status === 'unhealthy') {
      return status;
    }
    return null;
  }, [query.data?.status]);

  // Derive services map from health response
  const services = useMemo((): Record<string, ServiceStatus> => {
    return query.data?.services ?? {};
  }, [query.data?.services]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isStale: query.isStale,
    overallStatus,
    services,
    refetch: query.refetch,
    isPlaceholderData: query.isPlaceholderData,
  };
}

// ============================================================================
// Convenience Hook with Select Pattern (NEM-3410)
// ============================================================================

/**
 * Health summary result from the select transformation
 */
export interface HealthSummary {
  status: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  serviceCount: number;
  healthyServiceCount: number;
  timestamp: string;
}

/**
 * Return type for useHealthSummaryQuery hook
 */
export interface UseHealthSummaryQueryReturn {
  /** Health summary with service counts */
  summary: HealthSummary | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Whether the data is placeholder data */
  isPlaceholderData: boolean;
}

/**
 * Hook to fetch health summary using the select pattern.
 *
 * This hook demonstrates the select option (NEM-3410) for transforming
 * the full health response into a lightweight summary object.
 *
 * @param options - Configuration options
 * @returns Health summary with service counts
 *
 * @example
 * ```tsx
 * const { summary, isLoading } = useHealthSummaryQuery();
 *
 * if (isLoading) return <Spinner />;
 *
 * return (
 *   <div>
 *     <span>Status: {summary?.status}</span>
 *     <span>{summary?.healthyServiceCount}/{summary?.serviceCount} healthy</span>
 *   </div>
 * );
 * ```
 */
export function useHealthSummaryQuery(
  options: Omit<UseHealthStatusQueryOptions, 'usePlaceholder'> = {}
): UseHealthSummaryQueryReturn {
  const { enabled = true, refetchInterval = false, staleTime = REALTIME_STALE_TIME } = options;

  // Create stable placeholder data reference
  const placeholderData = useMemo(() => createPlaceholderHealthStatus(), []);

  const query = useQuery({
    queryKey: queryKeys.system.health,
    // AbortSignal integration (NEM-3411)
    queryFn: ({ signal }) => fetchHealth({ signal }),
    enabled,
    refetchInterval,
    staleTime,
    retry: 1,
    placeholderData,
    // Select pattern (NEM-3410): Transform to summary
    select: selectHealthSummary,
  });

  return {
    summary: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    refetch: query.refetch,
    isPlaceholderData: query.isPlaceholderData,
  };
}

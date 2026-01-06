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
 *
 * @module hooks/useHealthStatusQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

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
  } = options;

  const query = useQuery({
    queryKey: queryKeys.system.health,
    queryFn: fetchHealth,
    enabled,
    refetchInterval,
    staleTime,
    // Disable retry for health checks to fail fast
    retry: 1,
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
  };
}

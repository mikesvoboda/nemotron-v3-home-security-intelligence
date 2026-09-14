/**
 * useHealthStatus - TanStack Query hook for system health status with legacy API compatibility
 *
 * This hook provides system health monitoring using TanStack Query's built-in polling.
 * It maintains backward compatibility with the original useHealthStatus interface
 * while leveraging TanStack Query features:
 *
 * - Automatic request deduplication (multiple components share one request)
 * - Built-in caching with configurable stale time
 * - Background refetching via refetchInterval
 * - AbortSignal integration for proper query cancellation
 * - PlaceholderData for better UX during loading states
 *
 * @module hooks/useHealthStatus
 * @see NEM-5008 - Migrate useHealthStatus hook from manual polling to TanStack Query
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo, useCallback } from 'react';

import { createPlaceholderHealthStatus } from './useQueryPatterns';
import { fetchHealth, type HealthResponse, type ServiceStatus } from '../services/api';
import { queryKeys, REALTIME_STALE_TIME } from '../services/queryClient';

export interface UseHealthStatusOptions {
  /** Polling interval in milliseconds. Defaults to 30000 (30 seconds). */
  pollingInterval?: number;
  /** Whether to start polling immediately. Defaults to true. */
  enabled?: boolean;
}

export interface UseHealthStatusReturn {
  /** Current health status from the API, null if not yet fetched */
  health: HealthResponse | null;
  /** Whether the health check is currently loading */
  isLoading: boolean;
  /** Error message if the health check failed */
  error: string | null;
  /** Overall health status: 'healthy', 'degraded', 'unhealthy', or null if unknown */
  overallStatus: 'healthy' | 'degraded' | 'unhealthy' | null;
  /** Map of service names to their status */
  services: Record<string, ServiceStatus>;
  /** Manually trigger a health check refresh */
  refresh: () => Promise<void>;
}

const DEFAULT_POLLING_INTERVAL = 30000; // 30 seconds

/**
 * Hook to fetch and poll system health status using TanStack Query.
 *
 * This hook fetches from GET /api/system/health and polls periodically using
 * TanStack Query's refetchInterval. It provides request deduplication, caching,
 * and all the benefits of TanStack Query while maintaining backward compatibility.
 *
 * @param options - Configuration options for polling behavior
 * @returns Health status information and loading state
 *
 * @example
 * ```tsx
 * const { health, isLoading, error, overallStatus, services } = useHealthStatus();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error} />;
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
 */
export function useHealthStatus(options: UseHealthStatusOptions = {}): UseHealthStatusReturn {
  const { pollingInterval = DEFAULT_POLLING_INTERVAL, enabled = true } = options;

  // Create stable placeholder data reference
  const placeholderData = useMemo(() => createPlaceholderHealthStatus(), []);

  // Determine refetch interval - if pollingInterval is 0 or negative, disable polling
  const refetchInterval = pollingInterval > 0 ? pollingInterval : false;

  const query = useQuery({
    queryKey: queryKeys.system.health,
    // AbortSignal integration: Pass signal from queryFn context
    queryFn: ({ signal }) => fetchHealth({ signal }),
    enabled,
    refetchInterval,
    // Use faster stale time for health checks
    staleTime: REALTIME_STALE_TIME,
    // Disable retry for health checks to fail fast (matches original behavior)
    retry: 1,
    // Don't refetch in background when window is not focused
    refetchIntervalInBackground: false,
    // PlaceholderData for better UX during loading states
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

  // Create a stable refresh function that respects the enabled state
  const refresh = useCallback(async (): Promise<void> => {
    // Respect the enabled option - don't fetch if disabled
    // This maintains compatibility with the original hook's behavior
    if (!enabled) {
      return;
    }
    await query.refetch();
  }, [enabled, query]);

  // Convert Error to string for backward compatibility
  const errorMessage = useMemo((): string | null => {
    if (!query.error) return null;

    // Handle API errors with detail field
    const err = query.error as Error & { detail?: string };
    if (err.detail) {
      return err.detail;
    }

    // Fallback to message property
    if (query.error.message) {
      return query.error.message;
    }

    return 'Failed to fetch health status';
  }, [query.error]);

  return {
    // Return null instead of undefined for backward compatibility
    // Also filter out placeholder data to match original behavior (null when loading)
    health: query.isPlaceholderData ? null : (query.data ?? null),
    isLoading: query.isLoading,
    error: errorMessage,
    overallStatus: query.isPlaceholderData ? null : overallStatus,
    services: query.isPlaceholderData ? {} : services,
    refresh,
  };
}

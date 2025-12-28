import { useState, useEffect, useCallback, useRef } from 'react';

import { fetchHealth, type HealthResponse, type ServiceStatus } from '../services/api';

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
 * Hook to fetch and poll system health status from the REST API.
 *
 * This hook fetches from GET /api/system/health on mount and polls periodically.
 * It provides overall system status and per-service status information.
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

  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Use ref to track if component is mounted to avoid state updates after unmount
  const isMountedRef = useRef<boolean>(true);

  const fetchHealthStatus = useCallback(async () => {
    if (!isMountedRef.current) return;

    try {
      const response = await fetchHealth();
      if (isMountedRef.current) {
        setHealth(response);
        setError(null);
        setIsLoading(false);
      }
    } catch (err) {
      if (isMountedRef.current) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to fetch health status';
        setError(errorMessage);
        setIsLoading(false);
        // Keep previous health data on error so UI doesn't flash empty
      }
    }
  }, []);

  // Initial fetch on mount
  useEffect(() => {
    isMountedRef.current = true;

    if (enabled) {
      void fetchHealthStatus();
    }

    return () => {
      isMountedRef.current = false;
    };
  }, [enabled, fetchHealthStatus]);

  // Set up polling interval
  useEffect(() => {
    if (!enabled || pollingInterval <= 0) return;

    const intervalId = setInterval(() => {
      void fetchHealthStatus();
    }, pollingInterval);

    return () => {
      clearInterval(intervalId);
    };
  }, [enabled, pollingInterval, fetchHealthStatus]);

  // Derive overall status from health response
  const overallStatus: 'healthy' | 'degraded' | 'unhealthy' | null =
    health?.status === 'healthy' || health?.status === 'degraded' || health?.status === 'unhealthy'
      ? health.status
      : null;

  // Derive services map from health response
  const services: Record<string, ServiceStatus> = health?.services ?? {};

  return {
    health,
    isLoading,
    error,
    overallStatus,
    services,
    refresh: fetchHealthStatus,
  };
}

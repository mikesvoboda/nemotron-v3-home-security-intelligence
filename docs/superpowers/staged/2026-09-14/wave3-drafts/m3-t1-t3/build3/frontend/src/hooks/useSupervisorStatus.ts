/**
 * Hook for fetching supervisor status with optional polling.
 *
 * Provides real-time supervisor status including worker list and states.
 * Supports optional automatic polling for live updates.
 *
 * @example
 * ```typescript
 * // Basic usage
 * const { data, isLoading, error, refetch } = useSupervisorStatus();
 *
 * // With polling every 5 seconds
 * const { data } = useSupervisorStatus({ pollInterval: 5000 });
 * ```
 */

import { useState, useEffect, useCallback, useRef } from 'react';

import { fetchSupervisorStatus } from '../services/supervisorApi';

/**
 * Worker status information.
 */
export interface WorkerStatus {
  /** Worker name identifier */
  name: string;
  /** Current status of the worker */
  status: 'running' | 'stopped' | 'crashed' | 'restarting' | 'failed';
  /** Number of times the worker has been restarted */
  restart_count: number;
  /** Maximum allowed restarts before marking as failed */
  max_restarts: number;
  /** ISO timestamp of last successful start, or null if never started */
  last_started_at: string | null;
  /** ISO timestamp of last crash, or null if never crashed */
  last_crashed_at: string | null;
  /** Error message if worker is in error state, otherwise null */
  error: string | null;
}

/**
 * Supervisor status response.
 */
export interface SupervisorStatus {
  /** Whether the supervisor is running */
  running: boolean;
  /** Total number of workers */
  worker_count: number;
  /** List of worker statuses */
  workers: WorkerStatus[];
  /** ISO timestamp of when this status was generated */
  timestamp: string;
}

/**
 * Options for useSupervisorStatus hook.
 */
export interface UseSupervisorStatusOptions {
  /** Polling interval in milliseconds. If not provided, polling is disabled. */
  pollInterval?: number;
}

/**
 * Return type for useSupervisorStatus hook.
 */
export interface UseSupervisorStatusResult {
  /** Supervisor status data, undefined while loading or on error */
  data: SupervisorStatus | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if fetch failed, null otherwise */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch and optionally poll supervisor status.
 *
 * @param options - Configuration options
 * @returns Supervisor status data, loading state, error, and refetch function
 */
export function useSupervisorStatus(
  options?: UseSupervisorStatusOptions
): UseSupervisorStatusResult {
  const { pollInterval } = options ?? {};

  const [data, setData] = useState<SupervisorStatus | undefined>(undefined);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Track if component is mounted to avoid state updates after unmount
  const isMountedRef = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      const response = await fetchSupervisorStatus();
      if (isMountedRef.current) {
        setData(response);
        setError(null);
        setIsLoading(false);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err : new Error(String(err)));
        setIsLoading(false);
      }
    }
  }, []);

  // Refetch function that can be called manually
  const refetch = useCallback(async () => {
    await fetchData();
  }, [fetchData]);

  // Initial fetch on mount
  useEffect(() => {
    isMountedRef.current = true;
    void fetchData();

    return () => {
      isMountedRef.current = false;
    };
  }, [fetchData]);

  // Polling effect
  useEffect(() => {
    if (!pollInterval || pollInterval <= 0) {
      return;
    }

    const intervalId = setInterval(() => {
      void fetchData();
    }, pollInterval);

    return () => {
      clearInterval(intervalId);
    };
  }, [pollInterval, fetchData]);

  return {
    data,
    isLoading,
    error,
    refetch,
  };
}

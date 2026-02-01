import { useState, useEffect, useCallback, useRef } from 'react';

import { fetchMonitoringHealth } from '../services/monitoringApi';

import type { MonitoringHealthResponse } from '../services/monitoringApi';

export interface UseMonitoringHealthOptions {
  pollingInterval?: number;
}

export interface UseMonitoringHealthResult {
  data: MonitoringHealthResponse | null;
  isLoading: boolean;
  error: Error | null;
  isHealthy: boolean;
  refetch: () => void;
}

/**
 * Hook for fetching and managing Prometheus monitoring health status
 *
 * Features:
 * - Fetches monitoring health on mount
 * - Supports optional polling interval
 * - Computed isHealthy property
 * - Manual refetch function
 */
export function useMonitoringHealth(
  options?: UseMonitoringHealthOptions
): UseMonitoringHealthResult {
  const { pollingInterval } = options ?? {};

  const [data, setData] = useState<MonitoringHealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Track if component is mounted
  const isMountedRef = useRef(true);

  // Fetch function
  const fetchData = useCallback(async () => {
    try {
      const response = await fetchMonitoringHealth();
      if (isMountedRef.current) {
        setData(response);
        setError(null);
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err : new Error(String(err)));
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  // Refetch function (resets loading state and fetches fresh data)
  const refetch = useCallback(() => {
    void fetchData();
  }, [fetchData]);

  // Initial fetch
  useEffect(() => {
    isMountedRef.current = true;
    void fetchData();

    return () => {
      isMountedRef.current = false;
    };
  }, [fetchData]);

  // Polling
  useEffect(() => {
    if (!pollingInterval || pollingInterval <= 0) {
      return;
    }

    const intervalId = setInterval(() => {
      void fetchData();
    }, pollingInterval);

    return () => {
      clearInterval(intervalId);
    };
  }, [pollingInterval, fetchData]);

  // Computed isHealthy property
  const isHealthy = data?.healthy ?? false;

  return {
    data,
    isLoading,
    error,
    isHealthy,
    refetch,
  };
}

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';

import { fetchMonitoringTargets } from '../services/monitoringApi';

import type { MonitoringTargetsResponse, TargetDetail } from '../services/monitoringApi';

export interface UseMonitoringTargetsOptions {
  pollingInterval?: number;
}

export interface UseMonitoringTargetsResult {
  data: MonitoringTargetsResponse | null;
  isLoading: boolean;
  error: Error | null;
  targetsByJob: Record<string, TargetDetail[]>;
  refetch: () => void;
}

/**
 * Hook for fetching and managing Prometheus monitoring targets
 *
 * Features:
 * - Fetches monitoring targets on mount
 * - Supports optional polling interval
 * - Groups targets by job in targetsByJob
 * - Manual refetch function
 */
export function useMonitoringTargets(
  options?: UseMonitoringTargetsOptions
): UseMonitoringTargetsResult {
  const { pollingInterval } = options ?? {};

  const [data, setData] = useState<MonitoringTargetsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Track if component is mounted
  const isMountedRef = useRef(true);

  // Fetch function
  const fetchData = useCallback(async () => {
    try {
      const response = await fetchMonitoringTargets();
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

  // Refetch function
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

  // Group targets by job
  const targetsByJob = useMemo<Record<string, TargetDetail[]>>(() => {
    if (!data?.targets) {
      return {};
    }

    return data.targets.reduce<Record<string, TargetDetail[]>>((acc, target) => {
      if (!acc[target.job]) {
        acc[target.job] = [];
      }
      acc[target.job].push(target);
      return acc;
    }, {});
  }, [data]);

  return {
    data,
    isLoading,
    error,
    targetsByJob,
    refetch,
  };
}

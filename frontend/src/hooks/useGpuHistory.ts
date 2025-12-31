import { useState, useEffect, useCallback, useRef } from 'react';

import { fetchGPUStats, type GPUStats } from '../services/api';

/**
 * GPU metric data point with timestamp
 */
export interface GpuMetricDataPoint {
  timestamp: string;
  utilization: number;
  memory_used: number;
  temperature: number;
}

export interface UseGpuHistoryOptions {
  /** Polling interval in milliseconds (default: 5000) */
  pollingInterval?: number;
  /** Maximum number of data points to keep (default: 60) */
  maxDataPoints?: number;
  /** Whether to start polling immediately (default: true) */
  autoStart?: boolean;
}

export interface UseGpuHistoryReturn {
  /** Current GPU stats */
  current: GPUStats | null;
  /** Historical GPU metrics */
  history: GpuMetricDataPoint[];
  /** Whether currently fetching */
  isLoading: boolean;
  /** Error message if fetch failed */
  error: string | null;
  /** Start polling */
  start: () => void;
  /** Stop polling */
  stop: () => void;
  /** Clear history */
  clearHistory: () => void;
}

/**
 * useGpuHistory - Hook for polling and storing GPU metrics history
 *
 * Polls the /api/system/gpu endpoint at regular intervals and maintains
 * a rolling buffer of historical metrics for time-series visualization.
 *
 * @example
 * ```tsx
 * const { current, history, isLoading, error } = useGpuHistory({
 *   pollingInterval: 5000,
 *   maxDataPoints: 60,
 * });
 * ```
 */
export function useGpuHistory(options: UseGpuHistoryOptions = {}): UseGpuHistoryReturn {
  const { pollingInterval = 5000, maxDataPoints = 60, autoStart = true } = options;

  const [current, setCurrent] = useState<GPUStats | null>(null);
  const [history, setHistory] = useState<GpuMetricDataPoint[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(autoStart);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStats = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const stats = await fetchGPUStats();
      setCurrent(stats);

      // Add to history if we have valid data
      if (stats.utilization !== null || stats.memory_used !== null || stats.temperature !== null) {
        const dataPoint: GpuMetricDataPoint = {
          timestamp: new Date().toISOString(),
          utilization: stats.utilization ?? 0,
          memory_used: stats.memory_used ?? 0,
          temperature: stats.temperature ?? 0,
        };

        setHistory((prev) => {
          const newHistory = [...prev, dataPoint];
          // Keep only the last maxDataPoints
          if (newHistory.length > maxDataPoints) {
            return newHistory.slice(-maxDataPoints);
          }
          return newHistory;
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch GPU stats');
    } finally {
      setIsLoading(false);
    }
  }, [maxDataPoints]);

  const start = useCallback(() => {
    setIsPolling(true);
  }, []);

  const stop = useCallback(() => {
    setIsPolling(false);
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  // Initial fetch and polling setup
  useEffect(() => {
    // Always clear existing interval first to prevent orphaned intervals
    // This guards against rapid toggles of isPolling
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (!isPolling) return;

    // Fetch immediately
    void fetchStats();

    // Set up polling interval
    intervalRef.current = setInterval(() => {
      void fetchStats();
    }, pollingInterval);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isPolling, pollingInterval, fetchStats]);

  return {
    current,
    history,
    isLoading,
    error,
    start,
    stop,
    clearHistory,
  };
}

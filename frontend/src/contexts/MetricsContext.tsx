/**
 * MetricsContext - Specialized context for GPU and performance metrics.
 *
 * This context provides GPU-specific data and operations, reducing
 * re-renders for components that only need metrics data rather than
 * all system data.
 *
 * Benefits:
 * - Components using only GPU data won't re-render when camera/health updates
 * - Clear separation of concerns
 * - Optimized high-frequency polling for real-time metrics
 *
 * @module contexts/MetricsContext
 */

import React, { createContext, useContext, useMemo, type ReactNode } from 'react';

import { useGpuStatsQuery } from '../hooks/useGpuStatsQuery';

import type { GPUStats } from '../services/api';

// ============================================================================
// Types
// ============================================================================

/**
 * Default GPU stats values when data is not yet available.
 */
// eslint-disable-next-line react-refresh/only-export-components
export const DEFAULT_GPU_STATS: GPUStats = {
  gpu_name: 'Unknown',
  utilization: 0,
  memory_used: 0,
  memory_total: 0,
  temperature: 0,
  power_usage: 0,
  inference_fps: null,
};

/**
 * Metrics data available through the context.
 */
export interface MetricsContextData {
  /** GPU statistics */
  gpuStats: GPUStats;
  /** GPU utilization percentage (0-100), null if unavailable */
  utilization: number | null;
  /** Memory used in MB, null if unavailable */
  memoryUsed: number | null;
  /** Memory total in MB */
  memoryTotal: number;
  /** Memory usage percentage (0-100) */
  memoryUsagePercent: number;
  /** Temperature in Celsius, null if unavailable */
  temperature: number | null;
  /** Power usage in watts, null if unavailable */
  powerUsage: number | null;
  /** Inference FPS, null if unavailable */
  inferenceFps: number | null;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Whether the data is stale */
  isStale: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
  /** Check if GPU is under heavy load (>80% utilization) */
  isHighLoad: boolean;
  /** Check if GPU temperature is high (>80C) */
  isHighTemperature: boolean;
}

/**
 * Props for the MetricsProvider component.
 */
export interface MetricsProviderProps {
  children: ReactNode;
  /**
   * Polling interval for GPU stats in milliseconds.
   * @default 5000 (5 seconds)
   */
  pollingInterval?: number;
  /**
   * Whether to enable data fetching.
   * @default true
   */
  enabled?: boolean;
}

// ============================================================================
// Context
// ============================================================================

/**
 * Context for metrics data. Do not use directly - use the useMetricsContext hook.
 */
// eslint-disable-next-line react-refresh/only-export-components
export const MetricsContext = createContext<MetricsContextData | null>(null);

MetricsContext.displayName = 'MetricsContext';

// ============================================================================
// Provider Component
// ============================================================================

/**
 * Provider component that fetches and manages GPU/metrics data.
 *
 * This provider should be placed high in your component tree. It can be
 * used standalone or as part of the SystemDataProvider composition.
 */
export function MetricsProvider({
  children,
  pollingInterval = 5_000,
  enabled = true,
}: MetricsProviderProps): React.ReactElement {
  const {
    data,
    isLoading,
    isRefetching,
    error,
    isStale,
    utilization,
    memoryUsed,
    temperature,
    refetch,
  } = useGpuStatsQuery({
    enabled,
    refetchInterval: pollingInterval,
    staleTime: pollingInterval,
  });

  const gpuStats = data ?? DEFAULT_GPU_STATS;

  // Calculate derived values
  const memoryTotal = gpuStats.memory_total ?? 0;
  const memoryUsagePercent = useMemo(() => {
    if (!memoryTotal || memoryTotal <= 0 || memoryUsed === null) return 0;
    return Math.round((memoryUsed / memoryTotal) * 100);
  }, [memoryUsed, memoryTotal]);

  const powerUsage = gpuStats.power_usage ?? null;
  const inferenceFps = gpuStats.inference_fps ?? null;

  // Status checks
  const isHighLoad = (utilization ?? 0) > 80;
  const isHighTemperature = (temperature ?? 0) > 80;

  // Memoized context value - only changes when GPU data changes
  const value = useMemo<MetricsContextData>(
    () => ({
      gpuStats,
      utilization,
      memoryUsed,
      memoryTotal,
      memoryUsagePercent,
      temperature,
      powerUsage,
      inferenceFps,
      isLoading,
      isRefetching,
      error,
      isStale,
      refetch,
      isHighLoad,
      isHighTemperature,
    }),
    [
      gpuStats,
      utilization,
      memoryUsed,
      memoryTotal,
      memoryUsagePercent,
      temperature,
      powerUsage,
      inferenceFps,
      isLoading,
      isRefetching,
      error,
      isStale,
      refetch,
      isHighLoad,
      isHighTemperature,
    ]
  );

  return <MetricsContext.Provider value={value}>{children}</MetricsContext.Provider>;
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook to access metrics data from the MetricsContext.
 *
 * Must be used within a MetricsProvider. Throws an error if used outside
 * the provider to help catch usage errors early.
 *
 * @throws Error if used outside of MetricsProvider
 *
 * @example
 * ```tsx
 * function GpuMonitor() {
 *   const { gpuStats, utilization, temperature, isHighLoad } = useMetricsContext();
 *
 *   return (
 *     <div>
 *       <span>Utilization: {utilization ?? 'N/A'}%</span>
 *       <span>Temperature: {temperature ?? 'N/A'}C</span>
 *       {isHighLoad && <Warning>High GPU load!</Warning>}
 *     </div>
 *   );
 * }
 * ```
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useMetricsContext(): MetricsContextData {
  const context = useContext(MetricsContext);
  if (!context) {
    throw new Error('useMetricsContext must be used within a MetricsProvider');
  }
  return context;
}

/**
 * Hook to optionally access metrics data. Returns null if outside provider.
 *
 * Use this when the component may be rendered outside the provider context,
 * or when you want to handle the absence of context gracefully.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useMetricsContextOptional(): MetricsContextData | null {
  return useContext(MetricsContext);
}

export default MetricsProvider;

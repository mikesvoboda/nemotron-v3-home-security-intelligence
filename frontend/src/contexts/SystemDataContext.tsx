/**
 * SystemDataContext - Shared context for frequently-polled system state.
 *
 * This context centralizes system data queries (cameras, health status, GPU stats)
 * to avoid duplicate requests from multiple components. Using TanStack Query under
 * the hood provides automatic caching and request deduplication.
 *
 * Benefits:
 * - Single source of truth for system state
 * - Request deduplication across the app
 * - Consistent polling intervals
 * - Easy access to loading/error states
 * - Centralized refetch capability
 *
 * @example
 * ```tsx
 * // In App.tsx - wrap your app with the provider
 * import { SystemDataProvider } from './contexts';
 *
 * function App() {
 *   return (
 *     <SystemDataProvider>
 *       <Dashboard />
 *     </SystemDataProvider>
 *   );
 * }
 *
 * // In any component - use the hook
 * import { useSystemData } from './contexts';
 *
 * function CameraGrid() {
 *   const { cameras, isLoading, error } = useSystemData();
 *
 *   if (isLoading) return <Spinner />;
 *   if (error) return <ErrorMessage error={error} />;
 *
 *   return <Grid cameras={cameras} />;
 * }
 * ```
 */

import React, { createContext, useContext, useMemo, type ReactNode } from 'react';

import { useCamerasQuery } from '../hooks/useCamerasQuery';
import { useGpuStatsQuery } from '../hooks/useGpuStatsQuery';
import { useHealthStatusQuery } from '../hooks/useHealthStatusQuery';

import type { Camera, GPUStats, HealthResponse, ServiceStatus } from '../services/api';

// ============================================================================
// Types
// ============================================================================

/**
 * Default health status values when data is not yet available.
 */
// eslint-disable-next-line react-refresh/only-export-components
export const DEFAULT_HEALTH: HealthResponse = {
  status: 'unknown',
  timestamp: new Date().toISOString(),
  services: {},
};

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
 * System data available through the context.
 */
export interface SystemData {
  /** List of all cameras, empty array if not loaded */
  cameras: Camera[];
  /** System health status */
  systemHealth: HealthResponse;
  /** GPU statistics */
  gpuStats: GPUStats;
  /** Overall health status derived from systemHealth */
  overallStatus: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  /** Map of service names to their status */
  services: Record<string, ServiceStatus>;
  /** Whether any of the queries are currently loading initial data */
  isLoading: boolean;
  /** Whether any of the queries are currently refetching in the background */
  isRefetching: boolean;
  /** First error encountered from any of the queries, null if no errors */
  error: Error | null;
  /** Function to trigger a refetch of all queries */
  refetch: () => void;
  /** Individual query states for granular control */
  queries: {
    cameras: {
      isLoading: boolean;
      isRefetching: boolean;
      error: Error | null;
    };
    health: {
      isLoading: boolean;
      isRefetching: boolean;
      error: Error | null;
    };
    gpu: {
      isLoading: boolean;
      isRefetching: boolean;
      error: Error | null;
    };
  };
}

/**
 * Props for the SystemDataProvider component.
 */
export interface SystemDataProviderProps {
  children: ReactNode;
  /**
   * Polling interval for camera data in milliseconds.
   * @default 30000 (30 seconds)
   */
  cameraPollingInterval?: number;
  /**
   * Polling interval for health status in milliseconds.
   * @default 10000 (10 seconds)
   */
  healthPollingInterval?: number;
  /**
   * Polling interval for GPU stats in milliseconds.
   * @default 5000 (5 seconds)
   */
  gpuPollingInterval?: number;
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
 * Context for system data. Do not use directly - use the useSystemData hook.
 */
// eslint-disable-next-line react-refresh/only-export-components
export const SystemDataContext = createContext<SystemData | null>(null);

SystemDataContext.displayName = 'SystemDataContext';

// ============================================================================
// Provider Component
// ============================================================================

/**
 * Provider component that fetches and manages system data.
 *
 * This provider should be placed high in your component tree, ideally wrapping
 * the entire application or the main dashboard area.
 *
 * Uses TanStack Query under the hood for caching and request deduplication,
 * so multiple components using useSystemData will share the same data without
 * making duplicate requests.
 */
export function SystemDataProvider({
  children,
  cameraPollingInterval = 30_000,
  healthPollingInterval = 10_000,
  gpuPollingInterval = 5_000,
  enabled = true,
}: SystemDataProviderProps): React.ReactElement {
  // Cameras query - less frequent updates
  const camerasQuery = useCamerasQuery({
    enabled,
    refetchInterval: cameraPollingInterval,
    staleTime: cameraPollingInterval,
  });

  // Health status query - moderate frequency
  const healthQuery = useHealthStatusQuery({
    enabled,
    refetchInterval: healthPollingInterval,
    staleTime: healthPollingInterval,
  });

  // GPU stats query - high frequency for real-time metrics
  const gpuQuery = useGpuStatsQuery({
    enabled,
    refetchInterval: gpuPollingInterval,
    staleTime: gpuPollingInterval,
  });

  // Aggregate loading state
  const isLoading = camerasQuery.isLoading || healthQuery.isLoading || gpuQuery.isLoading;
  const isRefetching =
    camerasQuery.isRefetching || healthQuery.isRefetching || gpuQuery.isRefetching;

  // First error from any query
  const error = camerasQuery.error || healthQuery.error || gpuQuery.error;

  // Refetch all queries
  const refetch = useMemo(
    () => () => {
      void camerasQuery.refetch();
      void healthQuery.refetch();
      void gpuQuery.refetch();
    },
    [camerasQuery, healthQuery, gpuQuery]
  );

  // Memoized context value
  const value = useMemo<SystemData>(
    () => ({
      cameras: camerasQuery.cameras,
      systemHealth: healthQuery.data ?? DEFAULT_HEALTH,
      gpuStats: gpuQuery.data ?? DEFAULT_GPU_STATS,
      overallStatus: healthQuery.overallStatus ?? 'unknown',
      services: healthQuery.services,
      isLoading,
      isRefetching,
      error,
      refetch,
      queries: {
        cameras: {
          isLoading: camerasQuery.isLoading,
          isRefetching: camerasQuery.isRefetching,
          error: camerasQuery.error,
        },
        health: {
          isLoading: healthQuery.isLoading,
          isRefetching: healthQuery.isRefetching,
          error: healthQuery.error,
        },
        gpu: {
          isLoading: gpuQuery.isLoading,
          isRefetching: gpuQuery.isRefetching,
          error: gpuQuery.error,
        },
      },
    }),
    [
      camerasQuery.cameras,
      camerasQuery.isLoading,
      camerasQuery.isRefetching,
      camerasQuery.error,
      healthQuery.data,
      healthQuery.overallStatus,
      healthQuery.services,
      healthQuery.isLoading,
      healthQuery.isRefetching,
      healthQuery.error,
      gpuQuery.data,
      gpuQuery.isLoading,
      gpuQuery.isRefetching,
      gpuQuery.error,
      isLoading,
      isRefetching,
      error,
      refetch,
    ]
  );

  return <SystemDataContext.Provider value={value}>{children}</SystemDataContext.Provider>;
}

// ============================================================================
// Hook
// ============================================================================

/**
 * Hook to access system data from the SystemDataContext.
 *
 * Must be used within a SystemDataProvider. Throws an error if used outside
 * the provider to help catch usage errors early.
 *
 * @throws Error if used outside of SystemDataProvider
 *
 * @example
 * ```tsx
 * function Dashboard() {
 *   const { cameras, gpuStats, isLoading, error, refetch } = useSystemData();
 *
 *   if (isLoading) return <LoadingSpinner />;
 *   if (error) return <ErrorMessage error={error} onRetry={refetch} />;
 *
 *   return (
 *     <div>
 *       <CameraGrid cameras={cameras} />
 *       <GpuStatsPanel stats={gpuStats} />
 *     </div>
 *   );
 * }
 * ```
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useSystemData(): SystemData {
  const context = useContext(SystemDataContext);
  if (!context) {
    throw new Error('useSystemData must be used within a SystemDataProvider');
  }
  return context;
}

/**
 * Hook to optionally access system data. Returns null if outside provider.
 *
 * Use this when the component may be rendered outside the provider context,
 * or when you want to handle the absence of context gracefully.
 *
 * @example
 * ```tsx
 * function OptionalStatusIndicator() {
 *   const systemData = useSystemDataOptional();
 *
 *   // Will return null if not within provider
 *   if (!systemData) return null;
 *
 *   return <StatusBadge status={systemData.overallStatus} />;
 * }
 * ```
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useSystemDataOptional(): SystemData | null {
  return useContext(SystemDataContext);
}

export default SystemDataProvider;

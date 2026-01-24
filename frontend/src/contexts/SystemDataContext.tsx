/**
 * SystemDataContext - Shared context for frequently-polled system state.
 *
 * This context centralizes system data queries (cameras, health status, GPU stats)
 * to avoid duplicate requests from multiple components. Using TanStack Query under
 * the hood provides automatic caching and request deduplication.
 *
 * Architecture:
 * - SystemDataProvider composes CameraProvider, HealthProvider, and MetricsProvider
 * - useSystemData provides combined access for components needing all data
 * - Use specialized hooks (useCameraContext, useHealthContext, useMetricsContext)
 *   when you only need a subset of data to reduce unnecessary re-renders
 *
 * Benefits:
 * - Single source of truth for system state
 * - Request deduplication across the app
 * - Consistent polling intervals
 * - Easy access to loading/error states
 * - Centralized refetch capability
 * - Optimized re-renders through context splitting
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
 *
 * // For optimized re-renders, use specialized context
 * import { useCameraContext } from './contexts';
 *
 * function CameraList() {
 *   // Only re-renders when camera data changes, not when GPU/health changes
 *   const { cameras, isLoading } = useCameraContext();
 *   // ...
 * }
 * ```
 */

import React, { createContext, useContext, useMemo, type ReactNode } from 'react';

import { CameraProvider, useCameraContextOptional } from './CameraContext';
import { HealthProvider, useHealthContextOptional, DEFAULT_HEALTH } from './HealthContext';
import { MetricsProvider, useMetricsContextOptional, DEFAULT_GPU_STATS } from './MetricsContext';

import type { Camera, GPUStats, HealthResponse, ServiceStatus } from '../services/api';

// ============================================================================
// Re-export defaults for backward compatibility
// ============================================================================

export { DEFAULT_HEALTH, DEFAULT_GPU_STATS };

// ============================================================================
// Types
// ============================================================================

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
// Inner Provider Component
// ============================================================================

/**
 * Inner component that composes data from all specialized contexts.
 * This must be rendered inside the specialized providers.
 */
function SystemDataInnerProvider({ children }: { children: ReactNode }): React.ReactElement {
  // Access specialized contexts
  const cameraContext = useCameraContextOptional();
  const healthContext = useHealthContextOptional();
  const metricsContext = useMetricsContextOptional();

  // Aggregate loading state
  const isLoading =
    (cameraContext?.isLoading ?? true) ||
    (healthContext?.isLoading ?? true) ||
    (metricsContext?.isLoading ?? true);

  const isRefetching =
    (cameraContext?.isRefetching ?? false) ||
    (healthContext?.isRefetching ?? false) ||
    (metricsContext?.isRefetching ?? false);

  // First error from any context
  const error = cameraContext?.error ?? healthContext?.error ?? metricsContext?.error ?? null;

  // Refetch all contexts
  const refetch = useMemo(
    () => () => {
      void cameraContext?.refetch();
      void healthContext?.refetch();
      void metricsContext?.refetch();
    },
    [cameraContext, healthContext, metricsContext]
  );

  // Memoized context value
  const value = useMemo<SystemData>(
    () => ({
      cameras: cameraContext?.cameras ?? [],
      systemHealth: healthContext?.systemHealth ?? DEFAULT_HEALTH,
      gpuStats: metricsContext?.gpuStats ?? DEFAULT_GPU_STATS,
      overallStatus: healthContext?.overallStatus ?? 'unknown',
      services: healthContext?.services ?? {},
      isLoading,
      isRefetching,
      error,
      refetch,
      queries: {
        cameras: {
          isLoading: cameraContext?.isLoading ?? true,
          isRefetching: cameraContext?.isRefetching ?? false,
          error: cameraContext?.error ?? null,
        },
        health: {
          isLoading: healthContext?.isLoading ?? true,
          isRefetching: healthContext?.isRefetching ?? false,
          error: healthContext?.error ?? null,
        },
        gpu: {
          isLoading: metricsContext?.isLoading ?? true,
          isRefetching: metricsContext?.isRefetching ?? false,
          error: metricsContext?.error ?? null,
        },
      },
    }),
    [
      cameraContext?.cameras,
      cameraContext?.isLoading,
      cameraContext?.isRefetching,
      cameraContext?.error,
      healthContext?.systemHealth,
      healthContext?.overallStatus,
      healthContext?.services,
      healthContext?.isLoading,
      healthContext?.isRefetching,
      healthContext?.error,
      metricsContext?.gpuStats,
      metricsContext?.isLoading,
      metricsContext?.isRefetching,
      metricsContext?.error,
      isLoading,
      isRefetching,
      error,
      refetch,
    ]
  );

  return <SystemDataContext.Provider value={value}>{children}</SystemDataContext.Provider>;
}

// ============================================================================
// Provider Component
// ============================================================================

/**
 * Provider component that fetches and manages system data.
 *
 * This provider should be placed high in your component tree, ideally wrapping
 * the entire application or the main dashboard area.
 *
 * The provider composes three specialized contexts:
 * - CameraProvider: Camera state (30s polling)
 * - HealthProvider: System health (10s polling)
 * - MetricsProvider: GPU metrics (5s polling)
 *
 * This composition allows components to subscribe to specific slices of data
 * using specialized hooks (useCameraContext, useHealthContext, useMetricsContext)
 * to reduce unnecessary re-renders.
 */
export function SystemDataProvider({
  children,
  cameraPollingInterval = 30_000,
  healthPollingInterval = 10_000,
  gpuPollingInterval = 5_000,
  enabled = true,
}: SystemDataProviderProps): React.ReactElement {
  return (
    <CameraProvider pollingInterval={cameraPollingInterval} enabled={enabled}>
      <HealthProvider pollingInterval={healthPollingInterval} enabled={enabled}>
        <MetricsProvider pollingInterval={gpuPollingInterval} enabled={enabled}>
          <SystemDataInnerProvider>{children}</SystemDataInnerProvider>
        </MetricsProvider>
      </HealthProvider>
    </CameraProvider>
  );
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
 * Note: For optimized re-renders, consider using specialized hooks:
 * - useCameraContext() - only camera data
 * - useHealthContext() - only health data
 * - useMetricsContext() - only GPU/metrics data
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

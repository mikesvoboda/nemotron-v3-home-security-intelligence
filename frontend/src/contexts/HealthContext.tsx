/**
 * HealthContext - Specialized context for system health state management.
 *
 * This context provides health-specific data and operations, reducing
 * re-renders for components that only need health status rather than
 * all system data.
 *
 * Benefits:
 * - Components using only health data won't re-render when camera/GPU updates
 * - Clear separation of concerns
 * - Optimized polling interval for health checks
 *
 * @module contexts/HealthContext
 */

import React, { createContext, useContext, useMemo, type ReactNode } from 'react';

import { useHealthStatusQuery } from '../hooks/useHealthStatusQuery';

import type { HealthResponse, ServiceStatus } from '../services/api';

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
 * Health data available through the context.
 */
export interface HealthContextData {
  /** System health status */
  systemHealth: HealthResponse;
  /** Overall health status derived from systemHealth */
  overallStatus: 'healthy' | 'degraded' | 'unhealthy' | 'unknown';
  /** Map of service names to their status */
  services: Record<string, ServiceStatus>;
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
  /** Check if a specific service is healthy */
  isServiceHealthy: (serviceName: string) => boolean;
  /** Get status of a specific service */
  getServiceStatus: (serviceName: string) => ServiceStatus | undefined;
}

/**
 * Props for the HealthProvider component.
 */
export interface HealthProviderProps {
  children: ReactNode;
  /**
   * Polling interval for health status in milliseconds.
   * @default 10000 (10 seconds)
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
 * Context for health data. Do not use directly - use the useHealthContext hook.
 */
// eslint-disable-next-line react-refresh/only-export-components
export const HealthContext = createContext<HealthContextData | null>(null);

HealthContext.displayName = 'HealthContext';

// ============================================================================
// Provider Component
// ============================================================================

/**
 * Provider component that fetches and manages health status data.
 *
 * This provider should be placed high in your component tree. It can be
 * used standalone or as part of the SystemDataProvider composition.
 */
export function HealthProvider({
  children,
  pollingInterval = 10_000,
  enabled = true,
}: HealthProviderProps): React.ReactElement {
  const { data, isLoading, isRefetching, error, isStale, overallStatus, services, refetch } =
    useHealthStatusQuery({
      enabled,
      refetchInterval: pollingInterval,
      staleTime: pollingInterval,
    });

  // Helper to check if a service is healthy
  const isServiceHealthy = useMemo(
    () => (serviceName: string) => {
      const service = services[serviceName];
      return service?.status === 'healthy';
    },
    [services]
  );

  // Helper to get service status
  const getServiceStatus = useMemo(
    () => (serviceName: string) => services[serviceName],
    [services]
  );

  // Memoized context value - only changes when health data changes
  const value = useMemo<HealthContextData>(
    () => ({
      systemHealth: data ?? DEFAULT_HEALTH,
      overallStatus: overallStatus ?? 'unknown',
      services,
      isLoading,
      isRefetching,
      error,
      isStale,
      refetch,
      isServiceHealthy,
      getServiceStatus,
    }),
    [
      data,
      overallStatus,
      services,
      isLoading,
      isRefetching,
      error,
      isStale,
      refetch,
      isServiceHealthy,
      getServiceStatus,
    ]
  );

  return <HealthContext.Provider value={value}>{children}</HealthContext.Provider>;
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook to access health data from the HealthContext.
 *
 * Must be used within a HealthProvider. Throws an error if used outside
 * the provider to help catch usage errors early.
 *
 * @throws Error if used outside of HealthProvider
 *
 * @example
 * ```tsx
 * function HealthIndicator() {
 *   const { overallStatus, services, isLoading } = useHealthContext();
 *
 *   if (isLoading) return <Spinner />;
 *
 *   return (
 *     <div>
 *       <span>Status: {overallStatus}</span>
 *       {Object.entries(services).map(([name, status]) => (
 *         <ServiceBadge key={name} name={name} status={status} />
 *       ))}
 *     </div>
 *   );
 * }
 * ```
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useHealthContext(): HealthContextData {
  const context = useContext(HealthContext);
  if (!context) {
    throw new Error('useHealthContext must be used within a HealthProvider');
  }
  return context;
}

/**
 * Hook to optionally access health data. Returns null if outside provider.
 *
 * Use this when the component may be rendered outside the provider context,
 * or when you want to handle the absence of context gracefully.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function useHealthContextOptional(): HealthContextData | null {
  return useContext(HealthContext);
}

export default HealthProvider;

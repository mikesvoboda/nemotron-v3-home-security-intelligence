/**
 * useFullHealthQuery - TanStack Query hook for comprehensive system health status
 *
 * This hook fetches from GET /api/system/health/full to provide complete health
 * information including all AI services, circuit breaker states, and workers.
 *
 * Implements NEM-1582: Service health check orchestration and circuit breaker integration
 *
 * @module hooks/useFullHealthQuery
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchFullHealth,
  type FullHealthResponse,
  type ServiceHealthState,
  type AIServiceHealthStatus,
  type CircuitBreakerSummary,
  type InfrastructureHealthStatus,
  type WorkerHealthStatusFull,
} from '../services/api';
import { REALTIME_STALE_TIME } from '../services/queryClient';

/**
 * Query key for full health endpoint
 */
export const FULL_HEALTH_QUERY_KEY = ['system', 'health', 'full'] as const;

/**
 * Options for configuring the useFullHealthQuery hook
 */
export interface UseFullHealthQueryOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching.
   * @default 30000 (30 seconds)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * Data older than this will be refetched in the background.
   * @default REALTIME_STALE_TIME (5 seconds)
   */
  staleTime?: number;
}

/**
 * Return type for the useFullHealthQuery hook
 */
export interface UseFullHealthQueryReturn {
  /** Full health response from the API, undefined if not yet fetched */
  data: FullHealthResponse | undefined;

  /** Whether the initial fetch is in progress */
  isLoading: boolean;

  /** Whether a background refetch is in progress */
  isRefetching: boolean;

  /** Error object if the query failed */
  error: Error | null;

  /** Whether the data is stale */
  isStale: boolean;

  /** Overall system health status */
  overallStatus: ServiceHealthState | null;

  /** Whether the system is ready to receive traffic */
  isReady: boolean;

  /** Human-readable status message */
  statusMessage: string;

  /** PostgreSQL health status */
  postgres: InfrastructureHealthStatus | null;

  /** Redis health status */
  redis: InfrastructureHealthStatus | null;

  /** Array of AI service health statuses */
  aiServices: AIServiceHealthStatus[];

  /** Circuit breaker summary */
  circuitBreakers: CircuitBreakerSummary | null;

  /** Background worker statuses */
  workers: WorkerHealthStatusFull[];

  /** Number of unhealthy critical services */
  criticalUnhealthyCount: number;

  /** Number of unhealthy non-critical services */
  nonCriticalUnhealthyCount: number;

  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch comprehensive system health status using TanStack Query.
 *
 * This hook fetches from GET /api/system/health/full and provides:
 * - Health status of all AI services with circuit breaker states
 * - Infrastructure health (PostgreSQL, Redis)
 * - Background worker status
 * - Overall system readiness
 *
 * @param options - Configuration options
 * @returns Full health status data and query state
 *
 * @example
 * ```tsx
 * // Basic usage
 * const {
 *   isReady,
 *   overallStatus,
 *   aiServices,
 *   circuitBreakers,
 *   statusMessage,
 * } = useFullHealthQuery();
 *
 * return (
 *   <div>
 *     <span className={isReady ? 'text-green' : 'text-red'}>
 *       {statusMessage}
 *     </span>
 *     {aiServices.map(service => (
 *       <ServiceCard key={service.name} service={service} />
 *     ))}
 *     {circuitBreakers?.open > 0 && (
 *       <Alert>
 *         {circuitBreakers.open} circuit breakers are open!
 *       </Alert>
 *     )}
 *   </div>
 * );
 * ```
 *
 * @example
 * ```tsx
 * // With longer polling interval for dashboard
 * const { aiServices, isRefetching } = useFullHealthQuery({
 *   refetchInterval: 60000, // Poll every 60 seconds
 * });
 * ```
 */
export function useFullHealthQuery(
  options: UseFullHealthQueryOptions = {}
): UseFullHealthQueryReturn {
  const {
    enabled = true,
    refetchInterval = 30000, // Default to 30 second polling
    staleTime = REALTIME_STALE_TIME,
  } = options;

  const query = useQuery({
    queryKey: FULL_HEALTH_QUERY_KEY,
    queryFn: fetchFullHealth,
    enabled,
    refetchInterval,
    staleTime,
    // Disable retry for health checks to fail fast
    retry: 1,
  });

  // Derive overall status
  const overallStatus = useMemo((): ServiceHealthState | null => {
    return query.data?.status ?? null;
  }, [query.data?.status]);

  // Derive readiness
  const isReady = useMemo((): boolean => {
    return query.data?.ready ?? false;
  }, [query.data?.ready]);

  // Derive status message
  const statusMessage = useMemo((): string => {
    return query.data?.message ?? 'Checking system health...';
  }, [query.data?.message]);

  // Derive AI services
  const aiServices = useMemo((): AIServiceHealthStatus[] => {
    return query.data?.ai_services ?? [];
  }, [query.data?.ai_services]);

  // Count unhealthy critical services
  const criticalUnhealthyCount = useMemo((): number => {
    if (!query.data) return 0;

    let count = 0;

    // Check infrastructure
    if (query.data.postgres?.status !== 'healthy') count++;
    if (query.data.redis?.status !== 'healthy') count++;

    // Check critical AI services (rtdetr, nemotron)
    const criticalServices = ['rtdetr', 'nemotron'];
    for (const service of query.data.ai_services ?? []) {
      if (criticalServices.includes(service.name) && service.status !== 'healthy') {
        count++;
      }
    }

    // Check critical workers
    for (const worker of query.data.workers ?? []) {
      if (worker.critical && !worker.running) {
        count++;
      }
    }

    return count;
  }, [query.data]);

  // Count unhealthy non-critical services
  const nonCriticalUnhealthyCount = useMemo((): number => {
    if (!query.data) return 0;

    let count = 0;
    const nonCriticalServices = ['florence', 'clip', 'enrichment'];

    for (const service of query.data.ai_services ?? []) {
      if (nonCriticalServices.includes(service.name) && service.status !== 'healthy') {
        count++;
      }
    }

    // Check non-critical workers
    for (const worker of query.data.workers ?? []) {
      if (!worker.critical && !worker.running) {
        count++;
      }
    }

    return count;
  }, [query.data]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    isStale: query.isStale,
    overallStatus,
    isReady,
    statusMessage,
    postgres: query.data?.postgres ?? null,
    redis: query.data?.redis ?? null,
    aiServices,
    circuitBreakers: query.data?.circuit_breakers ?? null,
    workers: query.data?.workers ?? [],
    criticalUnhealthyCount,
    nonCriticalUnhealthyCount,
    refetch: query.refetch,
  };
}

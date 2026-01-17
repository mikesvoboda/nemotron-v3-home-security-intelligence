/**
 * useDebugQueries - TanStack Query hooks for debug-specific API endpoints
 *
 * These hooks provide debug data that is only fetched when debug mode is enabled.
 * Each hook accepts an `enabled` option that should be set based on the debug mode state.
 *
 * Debug endpoints (only available when backend debug=True):
 * - GET /api/debug/pipeline-errors - Recent pipeline errors
 * - GET /api/debug/redis/info - Detailed Redis stats
 * - GET /api/debug/websocket/connections - WebSocket broadcaster status
 *
 * @module hooks/useDebugQueries
 */

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

import {
  fetchPipelineErrors,
  fetchRedisDebugInfo,
  fetchWebSocketConnections,
  type PipelineErrorsResponse,
  type RedisDebugInfoResponse,
  type WebSocketConnectionsResponse,
  type PipelineError,
  type WebSocketBroadcasterStatus,
  type RedisInfo,
  type RedisPubsubInfo,
} from '../services/api';
import { REALTIME_STALE_TIME } from '../services/queryClient';

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query keys for debug-specific queries
 */
export const debugQueryKeys = {
  pipelineErrors: ['debug', 'pipeline-errors'] as const,
  redisInfo: ['debug', 'redis-info'] as const,
  websocketConnections: ['debug', 'websocket-connections'] as const,
} as const;

// ============================================================================
// Common Options Interface
// ============================================================================

/**
 * Common options for debug queries
 */
export interface DebugQueryOptions {
  /**
   * Whether to enable the query (should be tied to debug mode)
   * @default false
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds
   * @default REALTIME_STALE_TIME (5 seconds)
   */
  staleTime?: number;
}

// ============================================================================
// usePipelineErrorsQuery
// ============================================================================

/**
 * Return type for usePipelineErrorsQuery hook
 */
export interface UsePipelineErrorsQueryReturn {
  /** Raw response data */
  data: PipelineErrorsResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Array of pipeline errors */
  errors: PipelineError[];
  /** Total count of errors */
  errorCount: number;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch pipeline errors from the debug API.
 *
 * Only fetches when enabled=true (should be tied to debug mode).
 *
 * @param options - Query options including enabled flag
 * @returns Pipeline errors data and query state
 *
 * @example
 * ```tsx
 * function PipelineMetricsPanel({ debugMode }: Props) {
 *   const { errors, errorCount, isLoading } = usePipelineErrorsQuery({
 *     enabled: debugMode,
 *   });
 *
 *   if (!debugMode) return null;
 *
 *   return (
 *     <CollapsibleSection title={`Recent Errors (${errorCount})`}>
 *       {errors.map(error => <ErrorItem key={error.timestamp} {...error} />)}
 *     </CollapsibleSection>
 *   );
 * }
 * ```
 */
export function usePipelineErrorsQuery(
  options: DebugQueryOptions = {}
): UsePipelineErrorsQueryReturn {
  const { enabled = false, staleTime = REALTIME_STALE_TIME } = options;

  const query = useQuery<PipelineErrorsResponse>({
    queryKey: debugQueryKeys.pipelineErrors,
    queryFn: () => fetchPipelineErrors(),
    enabled,
    staleTime,
    // Debug endpoints may return 404 when debug mode is off
    retry: 1,
  });

  // Derive errors array from data
  const errors = useMemo(() => query.data?.errors ?? [], [query.data]);

  // Derive error count from data
  const errorCount = useMemo(() => query.data?.total ?? 0, [query.data]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    errors,
    errorCount,
    refetch: query.refetch,
  };
}

// ============================================================================
// useRedisDebugInfoQuery
// ============================================================================

/**
 * Return type for useRedisDebugInfoQuery hook
 */
export interface UseRedisDebugInfoQueryReturn {
  /** Raw response data */
  data: RedisDebugInfoResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Redis server info (version, clients, memory, etc.) */
  redisInfo: RedisInfo | null;
  /** Pub/sub channel information */
  pubsubInfo: RedisPubsubInfo | null;
  /** Connection status (connected, unavailable, error) */
  connectionStatus: string | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch Redis debug information from the debug API.
 *
 * Only fetches when enabled=true (should be tied to debug mode).
 *
 * @param options - Query options including enabled flag
 * @returns Redis debug info and query state
 *
 * @example
 * ```tsx
 * function DatabasesPanel({ debugMode }: Props) {
 *   const { redisInfo, pubsubInfo, connectionStatus } = useRedisDebugInfoQuery({
 *     enabled: debugMode,
 *   });
 *
 *   if (!debugMode) return null;
 *
 *   return (
 *     <CollapsibleSection title="Redis Debug Info">
 *       <Text>Status: {connectionStatus}</Text>
 *       <Text>Version: {redisInfo?.redis_version}</Text>
 *       <Text>Channels: {pubsubInfo?.channels.join(', ')}</Text>
 *     </CollapsibleSection>
 *   );
 * }
 * ```
 */
export function useRedisDebugInfoQuery(
  options: DebugQueryOptions = {}
): UseRedisDebugInfoQueryReturn {
  const { enabled = false, staleTime = REALTIME_STALE_TIME } = options;

  const query = useQuery({
    queryKey: debugQueryKeys.redisInfo,
    queryFn: fetchRedisDebugInfo,
    enabled,
    staleTime,
    retry: 1,
  });

  // Derive Redis info from data
  const redisInfo = useMemo(() => query.data?.info ?? null, [query.data]);

  // Derive pubsub info from data
  const pubsubInfo = useMemo(() => query.data?.pubsub ?? null, [query.data]);

  // Derive connection status from data
  const connectionStatus = useMemo(() => query.data?.status ?? null, [query.data]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    redisInfo,
    pubsubInfo,
    connectionStatus,
    refetch: query.refetch,
  };
}

// ============================================================================
// useWebSocketConnectionsQuery
// ============================================================================

/**
 * Return type for useWebSocketConnectionsQuery hook
 */
export interface UseWebSocketConnectionsQueryReturn {
  /** Raw response data */
  data: WebSocketConnectionsResponse | undefined;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Whether a background refetch is in progress */
  isRefetching: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Event broadcaster status */
  eventBroadcaster: WebSocketBroadcasterStatus | null;
  /** System broadcaster status */
  systemBroadcaster: WebSocketBroadcasterStatus | null;
  /** Total WebSocket connections across all broadcasters */
  totalConnections: number;
  /** Whether any broadcaster is in degraded state */
  hasAnyDegradation: boolean;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch WebSocket connection status from the debug API.
 *
 * Only fetches when enabled=true (should be tied to debug mode).
 *
 * @param options - Query options including enabled flag
 * @returns WebSocket connection data and query state
 *
 * @example
 * ```tsx
 * function CircuitBreakerPanel({ debugMode }: Props) {
 *   const { eventBroadcaster, systemBroadcaster, totalConnections } =
 *     useWebSocketConnectionsQuery({ enabled: debugMode });
 *
 *   if (!debugMode) return null;
 *
 *   return (
 *     <CollapsibleSection title={`WebSocket Status (${totalConnections} connections)`}>
 *       <BroadcasterStatus name="Events" {...eventBroadcaster} />
 *       <BroadcasterStatus name="System" {...systemBroadcaster} />
 *     </CollapsibleSection>
 *   );
 * }
 * ```
 */
export function useWebSocketConnectionsQuery(
  options: DebugQueryOptions = {}
): UseWebSocketConnectionsQueryReturn {
  const { enabled = false, staleTime = REALTIME_STALE_TIME } = options;

  const query = useQuery({
    queryKey: debugQueryKeys.websocketConnections,
    queryFn: fetchWebSocketConnections,
    enabled,
    staleTime,
    retry: 1,
  });

  // Derive event broadcaster from data
  const eventBroadcaster = useMemo(() => query.data?.event_broadcaster ?? null, [query.data]);

  // Derive system broadcaster from data
  const systemBroadcaster = useMemo(() => query.data?.system_broadcaster ?? null, [query.data]);

  // Calculate total connections
  const totalConnections = useMemo(() => {
    if (!query.data) return 0;
    return (
      (query.data.event_broadcaster?.connection_count ?? 0) +
      (query.data.system_broadcaster?.connection_count ?? 0)
    );
  }, [query.data]);

  // Check for any degradation
  const hasAnyDegradation = useMemo(() => {
    if (!query.data) return false;
    return (
      (query.data.event_broadcaster?.is_degraded ?? false) ||
      (query.data.system_broadcaster?.is_degraded ?? false)
    );
  }, [query.data]);

  return {
    data: query.data,
    isLoading: query.isLoading,
    isRefetching: query.isRefetching,
    error: query.error,
    eventBroadcaster,
    systemBroadcaster,
    totalConnections,
    hasAnyDegradation,
    refetch: query.refetch,
  };
}

export default {
  usePipelineErrorsQuery,
  useRedisDebugInfoQuery,
  useWebSocketConnectionsQuery,
};

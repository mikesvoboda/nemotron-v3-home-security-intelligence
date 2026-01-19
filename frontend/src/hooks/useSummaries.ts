/**
 * useSummaries - React hook for fetching dashboard summaries
 *
 * This hook fetches hourly and daily summaries via React Query and
 * subscribes to WebSocket `summary_update` events for real-time updates.
 *
 * Summaries are LLM-generated narrative descriptions of high/critical
 * security events, generated every 5 minutes by a background job.
 *
 * @module hooks/useSummaries
 * @see docs/plans/2026-01-18-dashboard-summaries-design.md
 * @see NEM-2895
 */

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef } from 'react';

import { useWebSocket, type WebSocketOptions } from './useWebSocket';
import { fetchSummaries } from '../services/api';
import { logger } from '../services/logger';
import { queryKeys, DEFAULT_STALE_TIME } from '../services/queryClient';
import { isSummaryUpdateMessage } from '../types/summary';

import type { UseSummariesResult } from '../types/summary';


// ============================================================================
// Types
// ============================================================================

/**
 * Options for configuring the useSummaries hook
 */
export interface UseSummariesOptions {
  /**
   * Whether to enable the query.
   * When false, the query will not execute.
   * @default true
   */
  enabled?: boolean;

  /**
   * Whether to subscribe to WebSocket updates.
   * When true, the hook will automatically refetch when a summary_update
   * message is received.
   * @default true
   */
  enableWebSocket?: boolean;

  /**
   * Refetch interval in milliseconds.
   * Set to false to disable automatic refetching (relies on WebSocket).
   * @default false (relies on WebSocket for updates)
   */
  refetchInterval?: number | false;

  /**
   * Custom stale time in milliseconds.
   * @default DEFAULT_STALE_TIME (30 seconds)
   */
  staleTime?: number;
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_WS_URL =
  (import.meta.env.VITE_WS_URL as string | undefined) ?? 'ws://localhost:8000/ws/events';

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch dashboard summaries (hourly and daily) using React Query
 * with WebSocket-based real-time updates.
 *
 * @param options - Configuration options
 * @returns Summaries data with loading state, error, and refetch function
 *
 * @example
 * ```tsx
 * const { hourly, daily, isLoading, error, refetch } = useSummaries();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <div>
 *     {hourly && <SummaryCard type="hourly" summary={hourly} />}
 *     {daily && <SummaryCard type="daily" summary={daily} />}
 *   </div>
 * );
 * ```
 *
 * @example
 * ```tsx
 * // Disable WebSocket (polling only)
 * const { hourly, daily } = useSummaries({
 *   enableWebSocket: false,
 *   refetchInterval: 60000, // Poll every minute
 * });
 * ```
 */
export function useSummaries(options: UseSummariesOptions = {}): UseSummariesResult {
  const {
    enabled = true,
    enableWebSocket = true,
    refetchInterval = false,
    staleTime = DEFAULT_STALE_TIME,
  } = options;

  const queryClient = useQueryClient();

  // React Query for fetching summaries
  const query = useQuery({
    queryKey: queryKeys.summaries.latest,
    queryFn: fetchSummaries,
    enabled,
    refetchInterval,
    staleTime,
    // Retry once for fast failure feedback
    retry: 1,
  });

  // Callback to invalidate summaries cache (triggers refetch)
  const invalidateSummaries = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.summaries.all });
  }, [queryClient]);

  // Store callback in ref to avoid stale closures
  const invalidateSummariesRef = useRef(invalidateSummaries);
  useEffect(() => {
    invalidateSummariesRef.current = invalidateSummaries;
  });

  // Handle incoming WebSocket messages
  const handleMessage = useCallback((data: unknown) => {
    // Check if this is a summary_update message
    if (!isSummaryUpdateMessage(data)) {
      return;
    }

    logger.debug('Summary WebSocket update received', {
      component: 'useSummaries',
      hasHourly: data.data.hourly !== null,
      hasDaily: data.data.daily !== null,
    });

    // Invalidate cache to trigger refetch with fresh data
    invalidateSummariesRef.current();
  }, []);

  // Configure WebSocket options
  const wsOptions: WebSocketOptions = {
    url: DEFAULT_WS_URL,
    onMessage: handleMessage,
    reconnect: true,
    reconnectInterval: 1000,
    reconnectAttempts: 15,
    connectionTimeout: 10000,
    autoRespondToHeartbeat: true,
  };

  // Use WebSocket hook for real-time updates
  // Only connect if both enabled and enableWebSocket are true
  const shouldConnectWs = enabled && enableWebSocket;
  useWebSocket(shouldConnectWs ? wsOptions : { ...wsOptions, reconnect: false });

  // Disconnect WebSocket when disabled
  // (handled internally by useWebSocket based on reconnect option)

  // Create async refetch wrapper
  const refetch = useCallback(async (): Promise<void> => {
    await query.refetch();
  }, [query]);

  return {
    hourly: query.data?.hourly ?? null,
    daily: query.data?.daily ?? null,
    isLoading: query.isLoading,
    error: query.error,
    refetch,
  };
}

export default useSummaries;

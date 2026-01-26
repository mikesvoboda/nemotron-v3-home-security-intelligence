/**
 * TanStack Query hook for WebSocket event type discovery (NEM-3639).
 *
 * This module provides a hook for fetching the WebSocket event registry,
 * which describes all available event types, their schemas, and channels.
 *
 * Use this hook to:
 * - Display available WebSocket event types in documentation/UI
 * - Validate event payloads against schemas
 * - Show deprecated event types with their replacements
 * - List available channels for subscription
 *
 * @module hooks/useWebSocketCapabilities
 * @see backend/api/schemas/websocket.py - EventRegistryResponse
 */

import { useQuery } from '@tanstack/react-query';

import { fetchWebSocketEventTypes } from '../services/api';
import { STATIC_STALE_TIME } from '../services/queryClient';

import type { EventRegistryResponse, EventTypeInfo } from '../services/api';

// Re-export types for convenience
export type { EventRegistryResponse, EventTypeInfo };

// ============================================================================
// Query Keys
// ============================================================================

/**
 * Query keys for WebSocket capabilities queries.
 */
export const WEBSOCKET_QUERY_KEYS = {
  /** Base key for all WebSocket capability queries */
  all: ['websocket'] as const,
  /** Event type registry */
  events: ['websocket', 'events'] as const,
} as const;

// ============================================================================
// useWebSocketCapabilities Hook
// ============================================================================

/**
 * Options for configuring the useWebSocketCapabilities hook.
 */
export interface UseWebSocketCapabilitiesOptions {
  /**
   * Whether to enable the query.
   * @default true
   */
  enabled?: boolean;

  /**
   * Custom stale time in milliseconds.
   * @default STATIC_STALE_TIME (5 minutes)
   */
  staleTime?: number;
}

/**
 * Return type for the useWebSocketCapabilities hook.
 */
export interface UseWebSocketCapabilitiesReturn {
  /** Full event registry response data */
  data: EventRegistryResponse | undefined;
  /** List of event types (convenience accessor) */
  eventTypes: EventTypeInfo[];
  /** Total count of event types */
  totalCount: number;
  /** List of available channels */
  channels: string[];
  /** Number of deprecated event types */
  deprecatedCount: number;
  /** Whether the initial fetch is in progress */
  isLoading: boolean;
  /** Error object if the query failed */
  error: Error | null;
  /** Function to manually trigger a refetch */
  refetch: () => Promise<unknown>;
}

/**
 * Hook to fetch WebSocket event type registry using TanStack Query.
 *
 * Returns the complete registry of WebSocket event types available in the system,
 * including their schemas, descriptions, channels, and deprecation status.
 *
 * The data is cached for 5 minutes (STATIC_STALE_TIME) since the event registry
 * rarely changes during runtime.
 *
 * @param options - Configuration options
 * @returns WebSocket capabilities and query state
 *
 * @example
 * ```tsx
 * const { eventTypes, channels, isLoading, error } = useWebSocketCapabilities();
 *
 * if (isLoading) return <Spinner />;
 * if (error) return <Error message={error.message} />;
 *
 * return (
 *   <div>
 *     <h2>Available Channels</h2>
 *     <ul>
 *       {channels.map(channel => (
 *         <li key={channel}>{channel}</li>
 *       ))}
 *     </ul>
 *
 *     <h2>Event Types ({totalCount})</h2>
 *     {eventTypes.map(event => (
 *       <EventTypeCard
 *         key={event.type}
 *         type={event.type}
 *         description={event.description}
 *         deprecated={event.deprecated}
 *         replacement={event.replacement}
 *       />
 *     ))}
 *   </div>
 * );
 * ```
 */
export function useWebSocketCapabilities(
  options: UseWebSocketCapabilitiesOptions = {}
): UseWebSocketCapabilitiesReturn {
  const { enabled = true, staleTime = STATIC_STALE_TIME } = options;

  const query = useQuery({
    queryKey: WEBSOCKET_QUERY_KEYS.events,
    queryFn: fetchWebSocketEventTypes,
    enabled,
    staleTime,
    retry: 1,
  });

  return {
    data: query.data,
    eventTypes: query.data?.event_types ?? [],
    totalCount: query.data?.total_count ?? 0,
    channels: query.data?.channels ?? [],
    deprecatedCount: query.data?.deprecated_count ?? 0,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
  };
}

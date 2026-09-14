/**
 * useZoneAnomalies - TanStack Query hook for zone anomaly data management (NEM-3199)
 *
 * This module provides hooks for fetching zone anomaly data and subscribing
 * to real-time WebSocket updates for new anomalies.
 *
 * Features:
 * - useZoneAnomaliesQuery: Fetch anomalies for a zone with filtering
 * - useZoneAnomalyMutation: Acknowledge anomalies
 * - Real-time WebSocket updates via zone.anomaly events
 *
 * @module hooks/useZoneAnomalies
 * @see NEM-3199 Frontend Anomaly Alert Integration
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef } from 'react';

import { useToast } from './useToast';
import { useWebSocketEvents } from './useWebSocketEvent';
import { DEFAULT_STALE_TIME } from '../services/queryClient';
import { isZoneAnomalyEventPayload, ANOMALY_SEVERITY_CONFIG } from '../types/zoneAnomaly';

import type { WebSocketEventKey } from '../types/websocket-events';
import type {
  ZoneAnomaly,
  ZoneAnomalyListResponse,
  ZoneAnomalyAcknowledgeResponse,
  UseZoneAnomaliesOptions,
  UseZoneAnomaliesReturn,
  AnomalySeverity,
} from '../types/zoneAnomaly';

// ============================================================================
// API Functions
// ============================================================================

const API_BASE = '/api';

/**
 * Fetch anomalies for a specific zone.
 */
async function fetchZoneAnomalies(
  zoneId: string,
  options: {
    severity?: AnomalySeverity | AnomalySeverity[];
    unacknowledgedOnly?: boolean;
    since?: string;
    until?: string;
    limit?: number;
    offset?: number;
  } = {}
): Promise<ZoneAnomalyListResponse> {
  const params = new URLSearchParams();

  if (options.severity) {
    const severities = Array.isArray(options.severity) ? options.severity : [options.severity];
    severities.forEach((s) => params.append('severity', s));
  }
  if (options.unacknowledgedOnly) {
    params.set('unacknowledged_only', 'true');
  }
  if (options.since) {
    params.set('since', options.since);
  }
  if (options.until) {
    params.set('until', options.until);
  }
  if (options.limit !== undefined) {
    params.set('limit', options.limit.toString());
  }
  if (options.offset !== undefined) {
    params.set('offset', options.offset.toString());
  }

  const queryString = params.toString();
  const url = `${API_BASE}/zones/${zoneId}/anomalies${queryString ? `?${queryString}` : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch zone anomalies: ${response.statusText}`);
  }

  return response.json() as Promise<ZoneAnomalyListResponse>;
}

/**
 * Fetch all recent anomalies across all zones.
 */
async function fetchAllAnomalies(
  options: {
    severity?: AnomalySeverity | AnomalySeverity[];
    unacknowledgedOnly?: boolean;
    since?: string;
    until?: string;
    limit?: number;
    offset?: number;
  } = {}
): Promise<ZoneAnomalyListResponse> {
  const params = new URLSearchParams();

  if (options.severity) {
    const severities = Array.isArray(options.severity) ? options.severity : [options.severity];
    severities.forEach((s) => params.append('severity', s));
  }
  if (options.unacknowledgedOnly) {
    params.set('unacknowledged_only', 'true');
  }
  if (options.since) {
    params.set('since', options.since);
  }
  if (options.until) {
    params.set('until', options.until);
  }
  if (options.limit !== undefined) {
    params.set('limit', options.limit.toString());
  }
  if (options.offset !== undefined) {
    params.set('offset', options.offset.toString());
  }

  const queryString = params.toString();
  const url = `${API_BASE}/zones/anomalies${queryString ? `?${queryString}` : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch anomalies: ${response.statusText}`);
  }

  return response.json() as Promise<ZoneAnomalyListResponse>;
}

/**
 * Acknowledge an anomaly.
 */
async function acknowledgeAnomaly(anomalyId: string): Promise<ZoneAnomalyAcknowledgeResponse> {
  const response = await fetch(`${API_BASE}/zones/anomalies/${anomalyId}/acknowledge`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to acknowledge anomaly: ${response.statusText}`);
  }

  return response.json() as Promise<ZoneAnomalyAcknowledgeResponse>;
}

// ============================================================================
// Query Keys
// ============================================================================

export const zoneAnomalyQueryKeys = {
  all: ['zone-anomalies'] as const,
  forZone: (zoneId: string) => [...zoneAnomalyQueryKeys.all, 'zone', zoneId] as const,
  list: (filters: Record<string, unknown>) =>
    [...zoneAnomalyQueryKeys.all, 'list', filters] as const,
};

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch zone anomalies with optional real-time WebSocket updates.
 *
 * Provides a type-safe API for fetching anomalies, acknowledging them,
 * and receiving real-time updates when new anomalies are detected.
 *
 * @param options - Configuration options
 * @returns Anomaly data, loading states, and mutation functions
 *
 * @example
 * ```tsx
 * const {
 *   anomalies,
 *   isLoading,
 *   acknowledgeAnomaly,
 *   isConnected,
 * } = useZoneAnomalies({
 *   zoneId: 'zone-123',
 *   unacknowledgedOnly: true,
 *   enableRealtime: true,
 *   onNewAnomaly: (anomaly) => {
 *     toast.warning(`New anomaly: ${anomaly.title}`);
 *   },
 * });
 * ```
 */
export function useZoneAnomalies(options: UseZoneAnomaliesOptions = {}): UseZoneAnomaliesReturn {
  const {
    zoneId,
    severity,
    unacknowledgedOnly = false,
    since,
    until,
    limit = 50,
    offset = 0,
    enabled = true,
    enableRealtime = true,
    onNewAnomaly,
    staleTime = DEFAULT_STALE_TIME,
    refetchInterval = false,
  } = options;

  const queryClient = useQueryClient();
  const toast = useToast();

  // Refs for callbacks to avoid stale closures
  const onNewAnomalyRef = useRef(onNewAnomaly);
  useEffect(() => {
    onNewAnomalyRef.current = onNewAnomaly;
  });

  // Build query key with all filter options
  const queryKey = useMemo(() => {
    const filters = {
      zoneId,
      severity,
      unacknowledgedOnly,
      since,
      until,
      limit,
      offset,
    };
    return zoneAnomalyQueryKeys.list(filters);
  }, [zoneId, severity, unacknowledgedOnly, since, until, limit, offset]);

  // Main query for fetching anomalies
  const query = useQuery({
    queryKey,
    queryFn: () => {
      const fetchOptions = {
        severity,
        unacknowledgedOnly,
        since,
        until,
        limit,
        offset,
      };

      return zoneId ? fetchZoneAnomalies(zoneId, fetchOptions) : fetchAllAnomalies(fetchOptions);
    },
    enabled,
    staleTime,
    refetchInterval,
    retry: 1,
  });

  // Acknowledge mutation
  const acknowledgeMutation = useMutation({
    mutationFn: acknowledgeAnomaly,
    onMutate: async (anomalyId: string) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey });

      // Snapshot for rollback
      const previousData = queryClient.getQueryData<ZoneAnomalyListResponse>(queryKey);

      // Optimistically update the cache
      queryClient.setQueryData<ZoneAnomalyListResponse>(queryKey, (old) => {
        if (!old) return old;
        return {
          ...old,
          items: old.items.map((item) =>
            item.id === anomalyId
              ? {
                  ...item,
                  acknowledged: true,
                  acknowledged_at: new Date().toISOString(),
                }
              : item
          ),
        };
      });

      return { previousData };
    },
    onError: (_err, _anomalyId, context) => {
      // Rollback on error
      if (context?.previousData) {
        queryClient.setQueryData(queryKey, context.previousData);
      }
      toast.error('Failed to acknowledge anomaly');
    },
    onSettled: () => {
      // Refetch to ensure consistency
      void queryClient.invalidateQueries({ queryKey: zoneAnomalyQueryKeys.all });
    },
  });

  // Handle WebSocket events
  const handleWebSocketMessage = useCallback(
    (eventData: unknown) => {
      // Validate the payload
      if (!isZoneAnomalyEventPayload(eventData)) {
        return;
      }

      const payload = eventData;

      // Check if this anomaly is relevant to our current query
      if (zoneId && payload.zone_id !== zoneId) {
        return;
      }

      // Convert WebSocket payload to full ZoneAnomaly
      const newAnomaly: ZoneAnomaly = {
        id: payload.id,
        zone_id: payload.zone_id,
        camera_id: payload.camera_id,
        anomaly_type: payload.anomaly_type,
        severity: payload.severity,
        title: payload.title,
        description: payload.description,
        expected_value: payload.expected_value,
        actual_value: payload.actual_value,
        deviation: payload.deviation,
        detection_id: payload.detection_id,
        thumbnail_url: payload.thumbnail_url,
        acknowledged: false,
        acknowledged_at: null,
        acknowledged_by: null,
        timestamp: payload.timestamp ?? new Date().toISOString(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      // Update the cache with the new anomaly
      queryClient.setQueryData<ZoneAnomalyListResponse>(queryKey, (old) => {
        if (!old) {
          return {
            items: [newAnomaly],
            pagination: {
              total: 1,
              limit,
              offset: 0,
              has_more: false,
            },
          };
        }

        // Check if anomaly already exists
        const exists = old.items.some((item) => item.id === newAnomaly.id);
        if (exists) {
          return old;
        }

        // Add to the beginning of the list
        return {
          ...old,
          items: [newAnomaly, ...old.items],
          pagination: {
            ...old.pagination,
            total: old.pagination.total + 1,
          },
        };
      });

      // Call the onNewAnomaly callback
      onNewAnomalyRef.current?.(newAnomaly);

      // Show toast notification for critical anomalies
      const severityConfig = ANOMALY_SEVERITY_CONFIG[payload.severity];
      const normalizedSeverity = String(payload.severity).toLowerCase();
      if (normalizedSeverity === 'critical') {
        toast.error(`Critical: ${payload.title}`, {
          description: payload.description ?? undefined,
          duration: 10000,
        });
      } else if (normalizedSeverity === 'warning') {
        toast.warning(`Warning: ${payload.title}`, {
          description: payload.description ?? undefined,
        });
      } else {
        toast.info(`${severityConfig.label}: ${payload.title}`);
      }
    },
    [zoneId, queryClient, queryKey, limit, toast]
  );

  // Subscribe to WebSocket events
  // Note: zone.anomaly is not in the standard event types yet, so we cast through unknown
  const { isConnected } = useWebSocketEvents(
    enableRealtime
      ? ({
          // Cast to handle zone.anomaly event type which may not be in the registry yet
          'zone.anomaly': handleWebSocketMessage,
        } as unknown as Record<WebSocketEventKey, (data: unknown) => void>)
      : {},
    { enabled: enableRealtime && enabled }
  );

  // Memoized return values
  const anomalies = useMemo(() => query.data?.items ?? [], [query.data]);
  const totalCount = useMemo(() => query.data?.pagination?.total ?? 0, [query.data]);

  const acknowledgeAnomalyFn = useCallback(
    async (anomalyId: string) => {
      return acknowledgeMutation.mutateAsync(anomalyId);
    },
    [acknowledgeMutation]
  );

  return {
    anomalies,
    totalCount,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    isError: query.isError,
    refetch: query.refetch,
    acknowledgeAnomaly: acknowledgeAnomalyFn,
    isAcknowledging: acknowledgeMutation.isPending,
    isConnected,
  };
}

export default useZoneAnomalies;

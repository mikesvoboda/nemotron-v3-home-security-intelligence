/**
 * useZoneAlerts - TanStack Query hook for unified zone alert management (NEM-3196)
 *
 * This module provides hooks for fetching and combining zone anomaly alerts
 * and trust violation alerts into a unified, prioritized feed with real-time
 * updates via WebSocket.
 *
 * Features:
 * - Combines anomaly alerts and trust violations
 * - Priority-based sorting (CRITICAL > WARNING > INFO)
 * - Batch acknowledge functionality
 * - Real-time WebSocket updates
 *
 * @module hooks/useZoneAlerts
 * @see NEM-3196 ZoneAlertFeed component implementation
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useCallback, useMemo } from 'react';

import { useToast } from './useToast';
import { useWebSocketEvents } from './useWebSocketEvent';
import { DEFAULT_STALE_TIME } from '../services/queryClient';
import { severityToPriority, isTrustViolation } from '../types/zoneAlert';
import { isZoneAnomalyEventPayload } from '../types/zoneAnomaly';

import type { WebSocketEventKey } from '../types/websocket-events';
import type {
  TrustViolation,
  TrustViolationListResponse,
  UnifiedZoneAlert,
  UseZoneAlertsOptions,
  UseZoneAlertsReturn,
  AlertSource,
  SeverityValue,
} from '../types/zoneAlert';
import type { ZoneAnomaly, ZoneAnomalyListResponse, AnomalySeverity } from '../types/zoneAnomaly';

// ============================================================================
// API Functions
// ============================================================================

const API_BASE = '/api';

/**
 * Fetch all recent anomalies across zones.
 */
async function fetchAnomalies(
  options: {
    zones?: string[];
    severities?: SeverityValue[];
    acknowledged?: boolean;
    since?: string;
    limit?: number;
  } = {}
): Promise<ZoneAnomalyListResponse> {
  const params = new URLSearchParams();

  if (options.severities?.length) {
    options.severities.forEach((s) => params.append('severity', s));
  }
  if (options.acknowledged !== undefined) {
    params.set('unacknowledged_only', (!options.acknowledged).toString());
  }
  if (options.since) {
    params.set('since', options.since);
  }
  if (options.limit !== undefined) {
    params.set('limit', options.limit.toString());
  }

  // If filtering by zones, make multiple requests and combine
  if (options.zones?.length) {
    const queryString = params.toString();
    const results = await Promise.all(
      options.zones.map(async (zoneId) => {
        const url = `${API_BASE}/zones/${zoneId}/anomalies${queryString ? `?${queryString}` : ''}`;
        const response = await fetch(url);
        if (!response.ok) {
          // Return empty if zone doesn't exist
          if (response.status === 404) {
            return { items: [], pagination: { total: 0, limit: 50, offset: 0, has_more: false } };
          }
          throw new Error(`Failed to fetch zone anomalies: ${response.statusText}`);
        }
        return response.json() as Promise<ZoneAnomalyListResponse>;
      })
    );

    // Combine results
    const allItems = results.flatMap((r) => r.items);
    return {
      items: allItems,
      pagination: {
        total: allItems.length,
        limit: options.limit ?? 50,
        offset: 0,
        has_more: false,
      },
    };
  }

  // Fetch all anomalies
  const queryString = params.toString();
  const url = `${API_BASE}/zones/anomalies${queryString ? `?${queryString}` : ''}`;

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch anomalies: ${response.statusText}`);
  }

  return response.json() as Promise<ZoneAnomalyListResponse>;
}

/**
 * Fetch trust violations across zones.
 * Note: This assumes a backend endpoint exists. If not, returns empty array.
 */
async function fetchTrustViolations(
  options: {
    zones?: string[];
    severities?: SeverityValue[];
    acknowledged?: boolean;
    since?: string;
    limit?: number;
  } = {}
): Promise<TrustViolationListResponse> {
  const params = new URLSearchParams();

  if (options.zones?.length) {
    options.zones.forEach((z) => params.append('zone_id', z));
  }
  if (options.severities?.length) {
    options.severities.forEach((s) => params.append('severity', s));
  }
  if (options.acknowledged !== undefined) {
    params.set('unacknowledged_only', (!options.acknowledged).toString());
  }
  if (options.since) {
    params.set('since', options.since);
  }
  if (options.limit !== undefined) {
    params.set('limit', options.limit.toString());
  }

  const queryString = params.toString();
  const url = `${API_BASE}/zones/trust-violations${queryString ? `?${queryString}` : ''}`;

  try {
    const response = await fetch(url);
    if (!response.ok) {
      // If endpoint doesn't exist yet, return empty
      if (response.status === 404) {
        return { items: [], pagination: { total: 0, limit: 50, offset: 0, has_more: false } };
      }
      throw new Error(`Failed to fetch trust violations: ${response.statusText}`);
    }
    return response.json() as Promise<TrustViolationListResponse>;
  } catch {
    // Return empty if endpoint doesn't exist
    return { items: [], pagination: { total: 0, limit: 50, offset: 0, has_more: false } };
  }
}

/**
 * Acknowledge an anomaly.
 */
async function acknowledgeAnomaly(anomalyId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/zones/anomalies/${anomalyId}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });

  if (!response.ok) {
    throw new Error(`Failed to acknowledge anomaly: ${response.statusText}`);
  }
}

/**
 * Acknowledge a trust violation.
 */
async function acknowledgeTrustViolation(violationId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/zones/trust-violations/${violationId}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });

  if (!response.ok && response.status !== 404) {
    throw new Error(`Failed to acknowledge trust violation: ${response.statusText}`);
  }
}

// ============================================================================
// Query Keys
// ============================================================================

export const zoneAlertQueryKeys = {
  all: ['zone-alerts'] as const,
  anomalies: (filters: Record<string, unknown>) =>
    [...zoneAlertQueryKeys.all, 'anomalies', filters] as const,
  trustViolations: (filters: Record<string, unknown>) =>
    [...zoneAlertQueryKeys.all, 'trust-violations', filters] as const,
  combined: (filters: Record<string, unknown>) =>
    [...zoneAlertQueryKeys.all, 'combined', filters] as const,
};

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Convert a ZoneAnomaly to a UnifiedZoneAlert.
 */
function anomalyToUnifiedAlert(anomaly: ZoneAnomaly): UnifiedZoneAlert {
  return {
    id: anomaly.id,
    source: 'anomaly',
    zone_id: anomaly.zone_id,
    camera_id: anomaly.camera_id,
    severity: anomaly.severity,
    priority: severityToPriority(anomaly.severity),
    title: anomaly.title,
    description: anomaly.description,
    thumbnail_url: anomaly.thumbnail_url,
    acknowledged: anomaly.acknowledged,
    acknowledged_at: anomaly.acknowledged_at,
    timestamp: anomaly.timestamp,
    originalAlert: anomaly,
  };
}

/**
 * Convert a TrustViolation to a UnifiedZoneAlert.
 */
function trustViolationToUnifiedAlert(violation: TrustViolation): UnifiedZoneAlert {
  return {
    id: violation.id,
    source: 'trust_violation',
    zone_id: violation.zone_id,
    camera_id: violation.camera_id,
    severity: violation.severity,
    priority: severityToPriority(violation.severity),
    title: violation.title,
    description: violation.description,
    thumbnail_url: violation.thumbnail_url,
    acknowledged: violation.acknowledged,
    acknowledged_at: violation.acknowledged_at,
    timestamp: violation.timestamp,
    originalAlert: violation,
  };
}

/**
 * Sort alerts by priority (CRITICAL first) then by timestamp (newest first).
 */
function sortAlerts(alerts: UnifiedZoneAlert[]): UnifiedZoneAlert[] {
  return [...alerts].sort((a, b) => {
    // Sort by priority first (lower = higher priority)
    if (a.priority !== b.priority) {
      return a.priority - b.priority;
    }
    // Then by timestamp (newest first)
    return new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime();
  });
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to fetch combined zone alerts (anomalies + trust violations)
 * with priority sorting and batch acknowledge functionality.
 *
 * @param options - Configuration options
 * @returns Combined alert data, loading states, and mutation functions
 *
 * @example
 * ```tsx
 * const {
 *   alerts,
 *   unacknowledgedCount,
 *   isLoading,
 *   acknowledgeAlert,
 *   acknowledgeAll,
 * } = useZoneAlerts({
 *   zones: ['zone-123'],
 *   severities: ['critical', 'warning'],
 *   enableRealtime: true,
 * });
 * ```
 */
export function useZoneAlerts(options: UseZoneAlertsOptions = {}): UseZoneAlertsReturn {
  const {
    zones,
    severities,
    acknowledged,
    since,
    limit = 100,
    enabled = true,
    enableRealtime = true,
    refetchInterval = false,
  } = options;

  const queryClient = useQueryClient();
  const toast = useToast();

  // Fetch anomalies
  const anomaliesQuery = useQuery({
    queryKey: zoneAlertQueryKeys.anomalies({ zones, severities, acknowledged, since, limit }),
    queryFn: () => fetchAnomalies({ zones, severities, acknowledged, since, limit }),
    enabled,
    staleTime: DEFAULT_STALE_TIME,
    refetchInterval,
    retry: 1,
  });

  // Fetch trust violations
  const trustViolationsQuery = useQuery({
    queryKey: zoneAlertQueryKeys.trustViolations({ zones, severities, acknowledged, since, limit }),
    queryFn: () => fetchTrustViolations({ zones, severities, acknowledged, since, limit }),
    enabled,
    staleTime: DEFAULT_STALE_TIME,
    refetchInterval,
    retry: 1,
  });

  // Combine and sort alerts
  const { alerts, unacknowledgedCount, totalCount } = useMemo(() => {
    const anomalyAlerts = (anomaliesQuery.data?.items ?? []).map(anomalyToUnifiedAlert);
    const violationAlerts = (trustViolationsQuery.data?.items ?? []).map(
      trustViolationToUnifiedAlert
    );

    const combined = [...anomalyAlerts, ...violationAlerts];
    const sorted = sortAlerts(combined);

    // Apply limit
    const limited = limit ? sorted.slice(0, limit) : sorted;

    return {
      alerts: limited,
      unacknowledgedCount: combined.filter((a) => !a.acknowledged).length,
      totalCount: combined.length,
    };
  }, [anomaliesQuery.data, trustViolationsQuery.data, limit]);

  // Acknowledge single alert mutation
  const acknowledgeMutation = useMutation({
    mutationFn: async ({ alertId, source }: { alertId: string; source: AlertSource }) => {
      if (source === 'anomaly') {
        await acknowledgeAnomaly(alertId);
      } else {
        await acknowledgeTrustViolation(alertId);
      }
    },
    onMutate: async ({ alertId, source }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: zoneAlertQueryKeys.all });

      // Get the appropriate query key for optimistic update
      const targetKey =
        source === 'anomaly'
          ? zoneAlertQueryKeys.anomalies({ zones, severities, acknowledged, since, limit })
          : zoneAlertQueryKeys.trustViolations({ zones, severities, acknowledged, since, limit });

      // Snapshot for rollback
      const previousData = queryClient.getQueryData(targetKey);

      // Optimistically update
      if (source === 'anomaly') {
        queryClient.setQueryData<ZoneAnomalyListResponse>(targetKey, (old) => {
          if (!old) return old;
          return {
            ...old,
            items: old.items.map((item) =>
              item.id === alertId
                ? { ...item, acknowledged: true, acknowledged_at: new Date().toISOString() }
                : item
            ),
          };
        });
      } else {
        queryClient.setQueryData<TrustViolationListResponse>(targetKey, (old) => {
          if (!old) return old;
          return {
            ...old,
            items: old.items.map((item) =>
              item.id === alertId
                ? { ...item, acknowledged: true, acknowledged_at: new Date().toISOString() }
                : item
            ),
          };
        });
      }

      return { previousData, targetKey };
    },
    onError: (_err, _vars, context) => {
      // Rollback on error
      if (context?.previousData && context?.targetKey) {
        queryClient.setQueryData(context.targetKey, context.previousData);
      }
      toast.error('Failed to acknowledge alert');
    },
    onSettled: () => {
      // Refetch to ensure consistency
      void queryClient.invalidateQueries({ queryKey: zoneAlertQueryKeys.all });
    },
  });

  // Acknowledge all mutation
  const acknowledgeAllMutation = useMutation({
    mutationFn: async () => {
      const unacknowledgedAlerts = alerts.filter((a) => !a.acknowledged);
      await Promise.all(
        unacknowledgedAlerts.map((alert) =>
          alert.source === 'anomaly'
            ? acknowledgeAnomaly(alert.id)
            : acknowledgeTrustViolation(alert.id)
        )
      );
    },
    onSuccess: () => {
      toast.success('All alerts acknowledged');
      void queryClient.invalidateQueries({ queryKey: zoneAlertQueryKeys.all });
    },
    onError: () => {
      toast.error('Failed to acknowledge all alerts');
    },
  });

  // Acknowledge by severity mutation
  const acknowledgeBySeverityMutation = useMutation({
    mutationFn: async (severity: AnomalySeverity) => {
      const targetAlerts = alerts.filter((a) => !a.acknowledged && a.severity === severity);
      await Promise.all(
        targetAlerts.map((alert) =>
          alert.source === 'anomaly'
            ? acknowledgeAnomaly(alert.id)
            : acknowledgeTrustViolation(alert.id)
        )
      );
    },
    onSuccess: (_data, severity) => {
      toast.success(`All ${severity} alerts acknowledged`);
      void queryClient.invalidateQueries({ queryKey: zoneAlertQueryKeys.all });
    },
    onError: () => {
      toast.error('Failed to acknowledge alerts');
    },
  });

  // Handle WebSocket events for new anomalies
  const handleAnomalyEvent = useCallback(
    (eventData: unknown) => {
      if (!isZoneAnomalyEventPayload(eventData)) {
        return;
      }

      // Check if this anomaly is relevant to our current query
      if (zones?.length) {
        const payload = eventData as { zone_id: string };
        if (!zones.includes(payload.zone_id)) {
          return;
        }
      }

      // Invalidate to refetch
      void queryClient.invalidateQueries({
        queryKey: zoneAlertQueryKeys.anomalies({ zones, severities, acknowledged, since, limit }),
      });

      // Show toast for critical alerts
      const payload = eventData as { severity: AnomalySeverity; title: string };
      if (String(payload.severity).toLowerCase() === 'critical') {
        toast.error(`Critical Alert: ${payload.title}`);
      }
    },
    [zones, severities, acknowledged, since, limit, queryClient, toast]
  );

  // Handle WebSocket events for trust violations
  const handleTrustViolationEvent = useCallback(
    (eventData: unknown) => {
      if (!isTrustViolation(eventData)) {
        return;
      }

      // Check if this violation is relevant to our current query
      if (zones?.length) {
        const payload = eventData;
        if (!zones.includes(payload.zone_id)) {
          return;
        }
      }

      // Invalidate to refetch
      void queryClient.invalidateQueries({
        queryKey: zoneAlertQueryKeys.trustViolations({
          zones,
          severities,
          acknowledged,
          since,
          limit,
        }),
      });

      // Show toast for critical violations
      const payload = eventData;
      if (payload.severity === 'critical') {
        toast.error(`Security Alert: ${payload.title}`);
      }
    },
    [zones, severities, acknowledged, since, limit, queryClient, toast]
  );

  // Subscribe to WebSocket events
  const { isConnected } = useWebSocketEvents(
    enableRealtime
      ? ({
          'zone.anomaly': handleAnomalyEvent,
          'zone.trust_violation': handleTrustViolationEvent,
        } as unknown as Record<WebSocketEventKey, (data: unknown) => void>)
      : {},
    { enabled: enableRealtime && enabled }
  );

  // Callback functions
  const acknowledgeAlertFn = useCallback(
    async (alertId: string, source: AlertSource) => {
      await acknowledgeMutation.mutateAsync({ alertId, source });
    },
    [acknowledgeMutation]
  );

  const acknowledgeAllFn = useCallback(async () => {
    await acknowledgeAllMutation.mutateAsync();
  }, [acknowledgeAllMutation]);

  const acknowledgeBySeverityFn = useCallback(
    async (severity: SeverityValue) => {
      await acknowledgeBySeverityMutation.mutateAsync(severity as AnomalySeverity);
    },
    [acknowledgeBySeverityMutation]
  );

  const refetch = useCallback(async () => {
    await Promise.all([anomaliesQuery.refetch(), trustViolationsQuery.refetch()]);
  }, [anomaliesQuery, trustViolationsQuery]);

  // Compute loading and error states
  const isLoading = anomaliesQuery.isLoading || trustViolationsQuery.isLoading;
  const isFetching = anomaliesQuery.isFetching || trustViolationsQuery.isFetching;
  const error = anomaliesQuery.error ?? trustViolationsQuery.error;
  const isError = anomaliesQuery.isError || trustViolationsQuery.isError;
  const isAcknowledging =
    acknowledgeMutation.isPending ||
    acknowledgeAllMutation.isPending ||
    acknowledgeBySeverityMutation.isPending;

  return {
    alerts,
    unacknowledgedCount,
    totalCount,
    isLoading,
    isFetching,
    error,
    isError,
    refetch,
    acknowledgeAlert: acknowledgeAlertFn,
    acknowledgeAll: acknowledgeAllFn,
    acknowledgeBySeverity: acknowledgeBySeverityFn,
    isAcknowledging,
    isConnected,
  };
}

export default useZoneAlerts;

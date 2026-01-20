/**
 * React hook for managing Prometheus alert state via WebSocket (NEM-3124)
 *
 * This hook subscribes to PROMETHEUS_ALERT WebSocket events and maintains
 * state of active infrastructure alerts. It provides:
 * - Real-time alert state keyed by fingerprint (via Zustand store)
 * - Severity-based counts (critical, warning, info)
 * - Toast notifications based on severity:
 *   - Critical: Error toast (10s duration)
 *   - Warning: Warning toast (5s duration)
 *   - Info: No toast (silent)
 *
 * These are infrastructure monitoring alerts (GPU, memory, pipeline health, etc.)
 * separate from AI-generated security alerts.
 *
 * @example
 * ```tsx
 * import { usePrometheusAlerts } from '@/hooks/usePrometheusAlerts';
 *
 * function AlertBadge() {
 *   const { criticalCount, warningCount, alerts, isConnected } = usePrometheusAlerts();
 *
 *   return (
 *     <div>
 *       {criticalCount > 0 && <Badge color="red">{criticalCount} Critical</Badge>}
 *       {warningCount > 0 && <Badge color="yellow">{warningCount} Warning</Badge>}
 *     </div>
 *   );
 * }
 * ```
 *
 * @module hooks/usePrometheusAlerts
 */

import { useCallback, useEffect, useMemo, useRef } from 'react';
import { toast } from 'sonner';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';
import { logger } from '../services/logger';
import { usePrometheusAlertStore, type StoredPrometheusAlert } from '../stores/prometheus-alert-store';

import type { PrometheusAlertPayload, PrometheusAlertSeverity } from '../types/websocket-events';

// ============================================================================
// Constants
// ============================================================================

/** Duration for critical alert toasts (10 seconds) */
const CRITICAL_TOAST_DURATION = 10000;

/** Duration for warning alert toasts (5 seconds) */
const WARNING_TOAST_DURATION = 5000;

// ============================================================================
// Types
// ============================================================================

/**
 * Extended Prometheus alert with client-side metadata.
 * Re-export for backward compatibility.
 */
export type PrometheusAlert = StoredPrometheusAlert;

/**
 * Alert counts grouped by severity.
 */
export interface AlertCounts {
  critical: number;
  warning: number;
  info: number;
  total: number;
}

/**
 * Options for configuring the usePrometheusAlerts hook.
 */
export interface UsePrometheusAlertsOptions {
  /**
   * Whether to enable the WebSocket connection.
   * @default true
   */
  enabled?: boolean;

  /**
   * Called when a new alert fires.
   */
  onAlertFiring?: (alert: PrometheusAlertPayload) => void;

  /**
   * Called when an alert resolves.
   */
  onAlertResolved?: (alert: PrometheusAlertPayload) => void;

  /**
   * Whether to show toast notifications for alerts.
   * @default true
   */
  showToasts?: boolean;
}

/**
 * Return type for the usePrometheusAlerts hook.
 */
export interface UsePrometheusAlertsReturn {
  /** Map of active alerts keyed by fingerprint */
  alerts: Record<string, StoredPrometheusAlert>;

  /** All active alerts sorted by severity (critical first) */
  alertsSorted: StoredPrometheusAlert[];

  /** Alerts grouped by severity */
  alertsBySeverity: {
    critical: StoredPrometheusAlert[];
    warning: StoredPrometheusAlert[];
    info: StoredPrometheusAlert[];
  };

  /** Count of alerts by severity */
  counts: AlertCounts;

  /** Count of critical severity alerts */
  criticalCount: number;

  /** Count of warning severity alerts */
  warningCount: number;

  /** Count of info severity alerts */
  infoCount: number;

  /** Total count of all active alerts */
  totalCount: number;

  /** Whether there are any active alerts */
  hasActiveAlerts: boolean;

  /** Whether there are critical alerts */
  hasCriticalAlerts: boolean;

  /** Whether the WebSocket is connected */
  isConnected: boolean;

  /** Clear all alerts from the store */
  clearAlerts: () => void;

  /** Force refresh by reconnecting WebSocket */
  refresh: () => void;
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard for PrometheusAlertPayload.
 */
function isPrometheusAlertPayload(data: unknown): data is PrometheusAlertPayload {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const payload = data as Record<string, unknown>;

  return (
    typeof payload.fingerprint === 'string' &&
    (payload.status === 'firing' || payload.status === 'resolved') &&
    typeof payload.alertname === 'string' &&
    typeof payload.severity === 'string' &&
    typeof payload.labels === 'object' &&
    typeof payload.annotations === 'object' &&
    typeof payload.starts_at === 'string' &&
    typeof payload.received_at === 'string'
  );
}

/**
 * Type guard for WebSocket messages with prometheus.alert type.
 * Supports both { type, payload } and { type, data } formats.
 */
function isPrometheusAlertMessage(data: unknown): data is {
  type: 'prometheus.alert';
  payload?: PrometheusAlertPayload;
  data?: PrometheusAlertPayload;
} {
  if (!data || typeof data !== 'object') {
    return false;
  }

  const msg = data as Record<string, unknown>;

  if (msg.type !== 'prometheus.alert') {
    return false;
  }

  // Support both 'payload' and 'data' fields for backward compatibility
  const alertData = msg.payload ?? msg.data;
  return isPrometheusAlertPayload(alertData);
}

/**
 * Extract alert payload from message, supporting both formats.
 */
function extractAlertPayload(
  msg: { type: 'prometheus.alert'; payload?: PrometheusAlertPayload; data?: PrometheusAlertPayload }
): PrometheusAlertPayload {
  return (msg.payload ?? msg.data) as PrometheusAlertPayload;
}

// ============================================================================
// Toast Notification Helper
// ============================================================================

/**
 * Show a toast notification for a Prometheus alert based on severity.
 *
 * @param alert - The alert payload
 */
function showAlertToast(alert: PrometheusAlertPayload): void {
  // Only show toasts for firing alerts
  if (alert.status !== 'firing') {
    return;
  }

  const summary = alert.annotations.summary || alert.alertname;
  const description = alert.annotations.description || '';
  const severity = alert.severity;

  switch (severity) {
    case 'critical':
      toast.error(summary, {
        description: description || undefined,
        duration: CRITICAL_TOAST_DURATION,
      });
      break;

    case 'warning':
      toast.warning(summary, {
        description: description || undefined,
        duration: WARNING_TOAST_DURATION,
      });
      break;

    case 'info':
      // Info alerts are silent - no toast
      break;

    default:
      // Unknown severity treated as info (silent)
      break;
  }
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for managing Prometheus alert state via WebSocket.
 *
 * Subscribes to the events WebSocket channel and filters for `prometheus.alert`
 * events. Updates the Zustand store with alert state and shows toast notifications
 * based on alert severity.
 *
 * @param options - Configuration options
 * @returns Alert state and connection status
 *
 * @example
 * ```tsx
 * const { alerts, counts, hasCriticalAlerts } = usePrometheusAlerts({
 *   onAlertFiring: (alert) => {
 *     console.log('Alert fired:', alert.alertname);
 *   },
 * });
 *
 * return (
 *   <AlertBadge counts={counts} hasCritical={hasCriticalAlerts} />
 * );
 * ```
 */
export function usePrometheusAlerts(
  options: UsePrometheusAlertsOptions = {}
): UsePrometheusAlertsReturn {
  const { enabled = true, onAlertFiring, onAlertResolved, showToasts = true } = options;

  // Track mounted state to prevent state updates after unmount
  const isMountedRef = useRef(true);

  // Store callbacks in refs to avoid stale closures
  const onAlertFiringRef = useRef(onAlertFiring);
  const onAlertResolvedRef = useRef(onAlertResolved);

  // Update refs when callbacks change
  useEffect(() => {
    onAlertFiringRef.current = onAlertFiring;
    onAlertResolvedRef.current = onAlertResolved;
  });

  // Get store state and actions
  const alerts = usePrometheusAlertStore((state) => state.alerts);
  const criticalCount = usePrometheusAlertStore((state) => state.criticalCount);
  const warningCount = usePrometheusAlertStore((state) => state.warningCount);
  const infoCount = usePrometheusAlertStore((state) => state.infoCount);
  const totalCount = usePrometheusAlertStore((state) => state.totalCount);
  const handlePrometheusAlert = usePrometheusAlertStore((state) => state.handlePrometheusAlert);
  const clear = usePrometheusAlertStore((state) => state.clear);

  // Compute derived values using useMemo to avoid infinite re-renders
  // (selectors that return new arrays cause re-renders on every call)
  const alertsSorted = useMemo(() => {
    const severityOrder: Record<PrometheusAlertSeverity, number> = {
      critical: 0,
      warning: 1,
      info: 2,
    };
    return Object.values(alerts).sort(
      (a, b) => severityOrder[a.severity] - severityOrder[b.severity]
    );
  }, [alerts]);

  const hasActiveAlerts = totalCount > 0;
  const hasCriticalAlerts = criticalCount > 0;

  // Compute alerts by severity from alertsSorted
  const alertsBySeverity = useMemo(
    () => ({
      critical: alertsSorted.filter((a) => a.severity === 'critical'),
      warning: alertsSorted.filter((a) => a.severity === 'warning'),
      info: alertsSorted.filter((a) => a.severity === 'info'),
    }),
    [alertsSorted]
  );

  // Compute counts object for backward compatibility
  const counts: AlertCounts = useMemo(
    () => ({
      critical: criticalCount,
      warning: warningCount,
      info: infoCount,
      total: totalCount,
    }),
    [criticalCount, warningCount, infoCount, totalCount]
  );

  // Set mounted state on mount and cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  /**
   * Handle incoming WebSocket messages.
   */
  const handleMessage = useCallback(
    (data: unknown) => {
      // Check if component is still mounted
      if (!isMountedRef.current) {
        return;
      }

      // Check if this is a prometheus.alert message
      if (isPrometheusAlertMessage(data)) {
        const payload = extractAlertPayload(data);

        logger.debug('Received Prometheus alert', {
          component: 'usePrometheusAlerts',
          alertname: payload.alertname,
          status: payload.status,
          severity: payload.severity,
          fingerprint: payload.fingerprint,
        });

        // Update store state
        handlePrometheusAlert(payload);

        // Show toast notification for firing alerts
        if (showToasts) {
          showAlertToast(payload);
        }

        // Call appropriate callback
        if (payload.status === 'firing') {
          onAlertFiringRef.current?.(payload);
        } else if (payload.status === 'resolved') {
          onAlertResolvedRef.current?.(payload);
        }

        return;
      }

      // Ignore other message types - this hook only cares about prometheus.alert
    },
    [handlePrometheusAlert, showToasts]
  );

  // Build WebSocket options for the events channel
  const wsOptions = buildWebSocketOptions('/ws/events');

  // Connect to WebSocket
  const { isConnected, connect, disconnect } = useWebSocket({
    url: wsOptions.url,
    protocols: wsOptions.protocols,
    onMessage: handleMessage,
    reconnect: enabled,
    reconnectInterval: 1000,
    reconnectAttempts: 15,
    connectionTimeout: 10000,
    autoRespondToHeartbeat: true,
  });

  // Disconnect if not enabled
  useEffect(() => {
    if (!enabled) {
      disconnect();
    }
  }, [enabled, disconnect]);

  /**
   * Clear all alerts from the store.
   */
  const clearAlerts = useCallback(() => {
    if (isMountedRef.current) {
      clear();
    }
  }, [clear]);

  /**
   * Force refresh by reconnecting WebSocket.
   */
  const refresh = useCallback(() => {
    disconnect();
    // Small delay before reconnecting
    setTimeout(() => {
      connect();
    }, 100);
  }, [connect, disconnect]);

  return {
    alerts,
    alertsSorted,
    alertsBySeverity,
    counts,
    criticalCount,
    warningCount,
    infoCount,
    totalCount,
    hasActiveAlerts,
    hasCriticalAlerts,
    isConnected,
    clearAlerts,
    refresh,
  };
}

export default usePrometheusAlerts;

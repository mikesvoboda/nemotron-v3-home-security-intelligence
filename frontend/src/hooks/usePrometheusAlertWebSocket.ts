/**
 * usePrometheusAlertWebSocket - WebSocket hook for Prometheus alerts on /ws/system
 *
 * NEM-3124: Subscribes to prometheus.alert events broadcast by the backend on the
 * /ws/system WebSocket endpoint. Updates the Prometheus alert store with incoming
 * alerts and handles alert lifecycle (firing/resolved).
 *
 * Events handled:
 * - prometheus.alert: Infrastructure alerts from Alertmanager webhook
 *
 * @module hooks/usePrometheusAlertWebSocket
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';

import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';
import { logger } from '../services/logger';
import {
  usePrometheusAlertStore,
  type StoredPrometheusAlert,
} from '../stores/prometheus-alert-store';
import { isHeartbeatMessage, isErrorMessage } from '../types/websocket';

import type { PrometheusAlertPayload, PrometheusAlertSeverity } from '../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

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
 * Alert history entry with timestamp for tracking.
 */
export interface AlertHistoryEntry extends StoredPrometheusAlert {
  /** ISO timestamp when this entry was recorded */
  recordedAt: string;
  /** Whether this was a firing or resolved event */
  eventType: 'firing' | 'resolved';
}

/**
 * Callback type for alert events.
 */
export type AlertEventHandler = (payload: PrometheusAlertPayload) => void;

/**
 * Options for configuring the usePrometheusAlertWebSocket hook.
 */
export interface UsePrometheusAlertWebSocketOptions {
  /**
   * Whether to enable the WebSocket connection.
   * @default true
   */
  enabled?: boolean;

  /**
   * Maximum number of historical entries to keep.
   * @default 50
   */
  maxHistory?: number;

  /**
   * Called when a new alert fires.
   */
  onAlertFiring?: AlertEventHandler;

  /**
   * Called when an alert resolves.
   */
  onAlertResolved?: AlertEventHandler;

  /**
   * Called when any alert event is received.
   */
  onAlert?: AlertEventHandler;
}

/**
 * Return type for the usePrometheusAlertWebSocket hook.
 */
export interface UsePrometheusAlertWebSocketReturn {
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

  /** History of alert events (newest first) */
  history: AlertHistoryEntry[];

  /** ISO timestamp of last alert event */
  lastUpdate: string | null;

  /** Clear all alerts from the store */
  clearAlerts: () => void;

  /** Clear the history buffer */
  clearHistory: () => void;

  /** Get alert by fingerprint */
  getAlert: (fingerprint: string) => StoredPrometheusAlert | undefined;

  /** Get alerts by alertname */
  getAlertsByName: (alertname: string) => StoredPrometheusAlert[];
}

// ============================================================================
// Constants
// ============================================================================

const DEFAULT_MAX_HISTORY = 50;

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
    ['critical', 'warning', 'info'].includes(payload.severity) &&
    typeof payload.labels === 'object' &&
    payload.labels !== null &&
    typeof payload.annotations === 'object' &&
    payload.annotations !== null &&
    typeof payload.starts_at === 'string' &&
    typeof payload.received_at === 'string'
  );
}

/**
 * Type guard for prometheus.alert WebSocket messages.
 * Supports both { type, data } and { type, payload } formats.
 */
function isPrometheusAlertMessage(
  value: unknown
): value is { type: 'prometheus.alert'; data?: PrometheusAlertPayload; payload?: PrometheusAlertPayload } {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const msg = value as Record<string, unknown>;
  if (msg.type !== 'prometheus.alert') {
    return false;
  }

  // Support both 'data' and 'payload' field names
  const alertData = msg.data ?? msg.payload;
  return isPrometheusAlertPayload(alertData);
}

/**
 * Extract alert payload from message, supporting both formats.
 */
function extractAlertPayload(msg: {
  type: 'prometheus.alert';
  data?: PrometheusAlertPayload;
  payload?: PrometheusAlertPayload;
}): PrometheusAlertPayload {
  return (msg.data ?? msg.payload) as PrometheusAlertPayload;
}

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook to subscribe to Prometheus alert WebSocket events on /ws/system.
 *
 * Tracks infrastructure monitoring alerts (GPU, memory, pipeline health, etc.)
 * and updates the Prometheus alert Zustand store.
 *
 * @param options - Configuration options
 * @returns Alert state, counts, and utilities
 *
 * @example
 * ```tsx
 * const {
 *   alerts,
 *   counts,
 *   hasCriticalAlerts,
 *   isConnected,
 * } = usePrometheusAlertWebSocket({
 *   onAlertFiring: (alert) => {
 *     if (alert.severity === 'critical') {
 *       playAlertSound();
 *     }
 *   },
 *   onAlertResolved: (alert) => {
 *     console.log(`Alert ${alert.alertname} resolved`);
 *   },
 * });
 *
 * // Display alert badge
 * if (hasCriticalAlerts) {
 *   return <AlertBadge variant="critical" count={counts.critical} />;
 * }
 * ```
 */
export function usePrometheusAlertWebSocket(
  options: UsePrometheusAlertWebSocketOptions = {}
): UsePrometheusAlertWebSocketReturn {
  const {
    enabled = true,
    maxHistory = DEFAULT_MAX_HISTORY,
    onAlertFiring,
    onAlertResolved,
    onAlert,
  } = options;

  // State
  const [history, setHistory] = useState<AlertHistoryEntry[]>([]);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);

  // Track mounted state
  const isMountedRef = useRef(true);

  // Store callbacks in refs to avoid stale closures
  const onAlertFiringRef = useRef(onAlertFiring);
  const onAlertResolvedRef = useRef(onAlertResolved);
  const onAlertRef = useRef(onAlert);

  useEffect(() => {
    onAlertFiringRef.current = onAlertFiring;
    onAlertResolvedRef.current = onAlertResolved;
    onAlertRef.current = onAlert;
  });

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  // Get store state and actions
  const alerts = usePrometheusAlertStore((state) => state.alerts);
  const criticalCount = usePrometheusAlertStore((state) => state.criticalCount);
  const warningCount = usePrometheusAlertStore((state) => state.warningCount);
  const infoCount = usePrometheusAlertStore((state) => state.infoCount);
  const totalCount = usePrometheusAlertStore((state) => state.totalCount);
  const handlePrometheusAlert = usePrometheusAlertStore((state) => state.handlePrometheusAlert);
  const clear = usePrometheusAlertStore((state) => state.clear);

  // Compute derived values
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

  const alertsBySeverity = useMemo(
    () => ({
      critical: alertsSorted.filter((a) => a.severity === 'critical'),
      warning: alertsSorted.filter((a) => a.severity === 'warning'),
      info: alertsSorted.filter((a) => a.severity === 'info'),
    }),
    [alertsSorted]
  );

  const counts: AlertCounts = useMemo(
    () => ({
      critical: criticalCount,
      warning: warningCount,
      info: infoCount,
      total: totalCount,
    }),
    [criticalCount, warningCount, infoCount, totalCount]
  );

  const hasActiveAlerts = totalCount > 0;
  const hasCriticalAlerts = criticalCount > 0;

  // Handle incoming WebSocket messages
  const handleMessage = useCallback(
    (data: unknown) => {
      if (!isMountedRef.current) {
        return;
      }

      // Handle prometheus.alert messages
      if (isPrometheusAlertMessage(data)) {
        const payload = extractAlertPayload(data);
        const timestamp = new Date().toISOString();

        logger.debug('Prometheus.alert event received', {
          component: 'usePrometheusAlertWebSocket',
          alertname: payload.alertname,
          status: payload.status,
          severity: payload.severity,
          fingerprint: payload.fingerprint,
        });

        // Update store state
        handlePrometheusAlert(payload);
        setLastUpdate(timestamp);

        // Add to history
        const historyEntry: AlertHistoryEntry = {
          fingerprint: payload.fingerprint,
          alertname: payload.alertname,
          severity: payload.severity,
          labels: payload.labels,
          annotations: payload.annotations,
          startsAt: payload.starts_at,
          receivedAt: payload.received_at,
          recordedAt: timestamp,
          eventType: payload.status,
        };

        setHistory((prev) => {
          const updated = [historyEntry, ...prev];
          return updated.slice(0, maxHistory);
        });

        // Call appropriate callbacks
        onAlertRef.current?.(payload);
        if (payload.status === 'firing') {
          onAlertFiringRef.current?.(payload);
        } else if (payload.status === 'resolved') {
          onAlertResolvedRef.current?.(payload);
        }

        return;
      }

      // Handle other message types (silently ignore)
      if (isHeartbeatMessage(data)) {
        return;
      }

      if (isErrorMessage(data)) {
        logger.warn('Prometheus alert WebSocket error', {
          component: 'usePrometheusAlertWebSocket',
          message: data.message,
        });
        return;
      }
    },
    [handlePrometheusAlert, maxHistory]
  );

  // Build WebSocket options for /ws/system
  const wsOptions = buildWebSocketOptions('/ws/system');

  // Connect to WebSocket
  const { isConnected } = useWebSocket(
    enabled
      ? {
          url: wsOptions.url,
          protocols: wsOptions.protocols,
          onMessage: handleMessage,
          reconnect: true,
          reconnectInterval: 1000,
          reconnectAttempts: 15,
          connectionTimeout: 10000,
          autoRespondToHeartbeat: true,
        }
      : {
          url: wsOptions.url,
          protocols: wsOptions.protocols,
          onMessage: handleMessage,
          reconnect: false,
        }
  );

  // Helper functions
  const getAlert = useCallback(
    (fingerprint: string): StoredPrometheusAlert | undefined => {
      return alerts[fingerprint];
    },
    [alerts]
  );

  const getAlertsByName = useCallback(
    (alertname: string): StoredPrometheusAlert[] => {
      return Object.values(alerts).filter((a) => a.alertname === alertname);
    },
    [alerts]
  );

  const clearAlerts = useCallback(() => {
    if (!isMountedRef.current) return;
    clear();
  }, [clear]);

  const clearHistory = useCallback(() => {
    if (!isMountedRef.current) return;
    setHistory([]);
  }, []);

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
    history,
    lastUpdate,
    clearAlerts,
    clearHistory,
    getAlert,
    getAlertsByName,
  };
}

export default usePrometheusAlertWebSocket;

/**
 * Prometheus Alert State Management Store (NEM-3124)
 *
 * Provides central state management for Prometheus/Alertmanager alerts across frontend components.
 * Uses Zustand for reactive state management, allowing components to subscribe to infrastructure
 * alerts and display alert status indicators.
 *
 * Prometheus alerts are received via WebSocket from the backend Alertmanager webhook receiver:
 * - prometheus.alert events with status "firing" add/update alerts
 * - prometheus.alert events with status "resolved" remove alerts
 *
 * These are infrastructure monitoring alerts (GPU, memory, pipeline health, etc.)
 * separate from AI-generated security alerts.
 */

import { create } from 'zustand';

import type {
  PrometheusAlertPayload,
  PrometheusAlertSeverity,
} from '../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

/**
 * Stored Prometheus alert with additional metadata.
 */
export interface StoredPrometheusAlert {
  /** Unique alert fingerprint for deduplication */
  fingerprint: string;
  /** Name of the alert */
  alertname: string;
  /** Alert severity level */
  severity: PrometheusAlertSeverity;
  /** Alert labels (key-value pairs) */
  labels: Record<string, string>;
  /** Alert annotations (summary, description, etc.) */
  annotations: Record<string, string>;
  /** ISO 8601 timestamp when alert started */
  startsAt: string;
  /** ISO 8601 timestamp when backend received alert */
  receivedAt: string;
}

/**
 * Prometheus alert store state and actions.
 */
export interface PrometheusAlertState {
  /** Map of alert fingerprint to alert data */
  alerts: Record<string, StoredPrometheusAlert>;
  /** Count of critical severity alerts currently firing */
  criticalCount: number;
  /** Count of warning severity alerts currently firing */
  warningCount: number;
  /** Count of info severity alerts currently firing */
  infoCount: number;
  /** Total count of all firing alerts */
  totalCount: number;

  // Actions
  /** Handle incoming prometheus.alert event */
  handlePrometheusAlert: (payload: PrometheusAlertPayload) => void;
  /** Remove a specific alert by fingerprint */
  removeAlert: (fingerprint: string) => void;
  /** Clear all alerts */
  clear: () => void;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Calculate severity counts from alerts map.
 */
function calculateSeverityCounts(alerts: Record<string, StoredPrometheusAlert>): {
  criticalCount: number;
  warningCount: number;
  infoCount: number;
  totalCount: number;
} {
  const alertList = Object.values(alerts);

  const criticalCount = alertList.filter((a) => a.severity === 'critical').length;
  const warningCount = alertList.filter((a) => a.severity === 'warning').length;
  const infoCount = alertList.filter((a) => a.severity === 'info').length;
  const totalCount = alertList.length;

  return {
    criticalCount,
    warningCount,
    infoCount,
    totalCount,
  };
}

// ============================================================================
// Store
// ============================================================================

/**
 * Zustand store for Prometheus alert state management.
 *
 * Features:
 * - Tracks active Prometheus/Alertmanager alerts keyed by fingerprint
 * - Automatically updates when alerts fire or resolve
 * - Provides severity-based counts for UI display
 * - Shared across components for consistent alert display
 *
 * @example
 * ```tsx
 * import { usePrometheusAlertStore } from '@/stores/prometheus-alert-store';
 *
 * // In a component
 * const { criticalCount, warningCount, alerts } = usePrometheusAlertStore();
 *
 * // Display alert badge
 * if (criticalCount > 0) {
 *   return <Badge color="red">{criticalCount} Critical</Badge>;
 * }
 * ```
 */
export const usePrometheusAlertStore = create<PrometheusAlertState>((set, get) => ({
  alerts: {},
  criticalCount: 0,
  warningCount: 0,
  infoCount: 0,
  totalCount: 0,

  handlePrometheusAlert: (payload: PrometheusAlertPayload) => {
    const { fingerprint, status, alertname, severity, labels, annotations, starts_at, received_at } =
      payload;

    if (status === 'firing') {
      // Add or update the alert
      const alerts = {
        ...get().alerts,
        [fingerprint]: {
          fingerprint,
          alertname,
          severity,
          labels,
          annotations,
          startsAt: starts_at,
          receivedAt: received_at,
        },
      };

      set({
        alerts,
        ...calculateSeverityCounts(alerts),
      });
    } else if (status === 'resolved') {
      // Remove the alert
      const { [fingerprint]: removed, ...remainingAlerts } = get().alerts;

      // Only update if the alert existed
      if (removed) {
        set({
          alerts: remainingAlerts,
          ...calculateSeverityCounts(remainingAlerts),
        });
      }
    }
  },

  removeAlert: (fingerprint: string) => {
    const { [fingerprint]: removed, ...remainingAlerts } = get().alerts;

    if (removed) {
      set({
        alerts: remainingAlerts,
        ...calculateSeverityCounts(remainingAlerts),
      });
    }
  },

  clear: () => {
    set({
      alerts: {},
      criticalCount: 0,
      warningCount: 0,
      infoCount: 0,
      totalCount: 0,
    });
  },
}));

// ============================================================================
// Selectors
// ============================================================================

/**
 * Selector for critical alerts.
 */
export const selectCriticalAlerts = (state: PrometheusAlertState): StoredPrometheusAlert[] => {
  return Object.values(state.alerts).filter((a) => a.severity === 'critical');
};

/**
 * Selector for warning alerts.
 */
export const selectWarningAlerts = (state: PrometheusAlertState): StoredPrometheusAlert[] => {
  return Object.values(state.alerts).filter((a) => a.severity === 'warning');
};

/**
 * Selector for info alerts.
 */
export const selectInfoAlerts = (state: PrometheusAlertState): StoredPrometheusAlert[] => {
  return Object.values(state.alerts).filter((a) => a.severity === 'info');
};

/**
 * Selector for all alerts sorted by severity (critical first, then warning, then info).
 */
export const selectAlertsSortedBySeverity = (
  state: PrometheusAlertState
): StoredPrometheusAlert[] => {
  const severityOrder: Record<PrometheusAlertSeverity, number> = {
    critical: 0,
    warning: 1,
    info: 2,
  };

  return Object.values(state.alerts).sort(
    (a, b) => severityOrder[a.severity] - severityOrder[b.severity]
  );
};

/**
 * Selector for a specific alert by fingerprint.
 */
export const selectAlertByFingerprint = (
  state: PrometheusAlertState,
  fingerprint: string
): StoredPrometheusAlert | undefined => {
  return state.alerts[fingerprint];
};

/**
 * Selector for alerts by alertname.
 */
export const selectAlertsByName = (
  state: PrometheusAlertState,
  alertname: string
): StoredPrometheusAlert[] => {
  return Object.values(state.alerts).filter((a) => a.alertname === alertname);
};

/**
 * Selector to check if there are any firing alerts.
 */
export const selectHasActiveAlerts = (state: PrometheusAlertState): boolean => {
  return state.totalCount > 0;
};

/**
 * Selector to check if there are any critical alerts.
 */
export const selectHasCriticalAlerts = (state: PrometheusAlertState): boolean => {
  return state.criticalCount > 0;
};

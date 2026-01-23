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
 *
 * Enhancements (NEM-3399, NEM-3400, NEM-3428):
 * - DevTools middleware for debugging
 * - useShallow hooks for selective subscriptions
 * - Memoized selectors for derived state
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { useShallow } from 'zustand/shallow';

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
// Store (NEM-3400: DevTools middleware)
// ============================================================================

/**
 * Zustand store for Prometheus alert state management.
 *
 * Features:
 * - Tracks active Prometheus/Alertmanager alerts keyed by fingerprint
 * - Automatically updates when alerts fire or resolve
 * - Provides severity-based counts for UI display
 * - Shared across components for consistent alert display
 * - DevTools integration for debugging (NEM-3400)
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
export const usePrometheusAlertStore = create<PrometheusAlertState>()(
  devtools(
    (set, get) => ({
      alerts: {},
      criticalCount: 0,
      warningCount: 0,
      infoCount: 0,
      totalCount: 0,

      handlePrometheusAlert: (payload: PrometheusAlertPayload) => {
        const {
          fingerprint,
          status,
          alertname,
          severity,
          labels,
          annotations,
          starts_at,
          received_at,
        } = payload;

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

          set(
            {
              alerts,
              ...calculateSeverityCounts(alerts),
            },
            undefined,
            'handlePrometheusAlert/firing'
          );
        } else if (status === 'resolved') {
          // Remove the alert
          const { [fingerprint]: removed, ...remainingAlerts } = get().alerts;

          // Only update if the alert existed
          if (removed) {
            set(
              {
                alerts: remainingAlerts,
                ...calculateSeverityCounts(remainingAlerts),
              },
              undefined,
              'handlePrometheusAlert/resolved'
            );
          }
        }
      },

      removeAlert: (fingerprint: string) => {
        const { [fingerprint]: removed, ...remainingAlerts } = get().alerts;

        if (removed) {
          set(
            {
              alerts: remainingAlerts,
              ...calculateSeverityCounts(remainingAlerts),
            },
            undefined,
            'removeAlert'
          );
        }
      },

      clear: () => {
        set(
          {
            alerts: {},
            criticalCount: 0,
            warningCount: 0,
            infoCount: 0,
            totalCount: 0,
          },
          undefined,
          'clear'
        );
      },
    }),
    { name: 'prometheus-alert-store', enabled: import.meta.env.DEV }
  )
);

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

// ============================================================================
// Memoized Selectors (NEM-3428)
// ============================================================================

/**
 * Cache for memoized selector results.
 * Each selector maintains its own cache entry keyed by relevant state.
 */
const selectorCache = {
  criticalAlerts: {
    alerts: {} as Record<string, StoredPrometheusAlert>,
    result: [] as StoredPrometheusAlert[],
  },
  warningAlerts: {
    alerts: {} as Record<string, StoredPrometheusAlert>,
    result: [] as StoredPrometheusAlert[],
  },
  infoAlerts: {
    alerts: {} as Record<string, StoredPrometheusAlert>,
    result: [] as StoredPrometheusAlert[],
  },
  sortedAlerts: {
    alerts: {} as Record<string, StoredPrometheusAlert>,
    result: [] as StoredPrometheusAlert[],
  },
};

/**
 * Memoized selector for critical alerts.
 * Returns cached result if alerts haven't changed.
 */
export const selectCriticalAlertsMemoized = (
  state: PrometheusAlertState
): StoredPrometheusAlert[] => {
  if (state.alerts === selectorCache.criticalAlerts.alerts) {
    return selectorCache.criticalAlerts.result;
  }
  const result = Object.values(state.alerts).filter((a) => a.severity === 'critical');
  selectorCache.criticalAlerts = { alerts: state.alerts, result };
  return result;
};

/**
 * Memoized selector for warning alerts.
 * Returns cached result if alerts haven't changed.
 */
export const selectWarningAlertsMemoized = (
  state: PrometheusAlertState
): StoredPrometheusAlert[] => {
  if (state.alerts === selectorCache.warningAlerts.alerts) {
    return selectorCache.warningAlerts.result;
  }
  const result = Object.values(state.alerts).filter((a) => a.severity === 'warning');
  selectorCache.warningAlerts = { alerts: state.alerts, result };
  return result;
};

/**
 * Memoized selector for info alerts.
 * Returns cached result if alerts haven't changed.
 */
export const selectInfoAlertsMemoized = (state: PrometheusAlertState): StoredPrometheusAlert[] => {
  if (state.alerts === selectorCache.infoAlerts.alerts) {
    return selectorCache.infoAlerts.result;
  }
  const result = Object.values(state.alerts).filter((a) => a.severity === 'info');
  selectorCache.infoAlerts = { alerts: state.alerts, result };
  return result;
};

/**
 * Memoized selector for alerts sorted by severity.
 * Returns cached result if alerts haven't changed.
 */
export const selectAlertsSortedBySeverityMemoized = (
  state: PrometheusAlertState
): StoredPrometheusAlert[] => {
  if (state.alerts === selectorCache.sortedAlerts.alerts) {
    return selectorCache.sortedAlerts.result;
  }
  const severityOrder: Record<PrometheusAlertSeverity, number> = {
    critical: 0,
    warning: 1,
    info: 2,
  };
  const result = Object.values(state.alerts).sort(
    (a, b) => severityOrder[a.severity] - severityOrder[b.severity]
  );
  selectorCache.sortedAlerts = { alerts: state.alerts, result };
  return result;
};

// ============================================================================
// Shallow Hooks for Selective Subscriptions (NEM-3399)
// ============================================================================

/**
 * Hook to select only alert counts with shallow equality.
 * Prevents re-renders when only alert details change but counts stay the same.
 *
 * @example
 * ```tsx
 * const { criticalCount, warningCount, totalCount } = usePrometheusAlertCounts();
 * ```
 */
export function usePrometheusAlertCounts() {
  return usePrometheusAlertStore(
    useShallow((state) => ({
      criticalCount: state.criticalCount,
      warningCount: state.warningCount,
      infoCount: state.infoCount,
      totalCount: state.totalCount,
    }))
  );
}

/**
 * Hook to select only the alerts map with shallow equality.
 * Useful when you only need alert data, not counts.
 *
 * @example
 * ```tsx
 * const alerts = usePrometheusAlerts();
 * ```
 */
export function usePrometheusAlerts() {
  return usePrometheusAlertStore((state) => state.alerts);
}

/**
 * Hook to select alert actions only.
 * Actions are stable references and don't cause re-renders.
 *
 * @example
 * ```tsx
 * const { handlePrometheusAlert, removeAlert, clear } = usePrometheusAlertActions();
 * ```
 */
export function usePrometheusAlertActions() {
  return usePrometheusAlertStore(
    useShallow((state) => ({
      handlePrometheusAlert: state.handlePrometheusAlert,
      removeAlert: state.removeAlert,
      clear: state.clear,
    }))
  );
}

/**
 * Prometheus Alert State Management Store (NEM-3124, NEM-3402, NEM-3403)
 *
 * Provides central state management for Prometheus/Alertmanager alerts across frontend components.
 * Uses Zustand with Immer middleware for immutable updates and subscribeWithSelector for
 * fine-grained subscriptions to prevent unnecessary re-renders.
 *
 * Prometheus alerts are received via WebSocket from the backend Alertmanager webhook receiver:
 * - prometheus.alert events with status "firing" add/update alerts
 * - prometheus.alert events with status "resolved" remove alerts
 *
 * These are infrastructure monitoring alerts (GPU, memory, pipeline health, etc.)
 * separate from AI-generated security alerts.
 */

import { useShallow } from 'zustand/react/shallow';

import { createComputedSelector, createImmerSelectorStore, type ImmerSetState } from './middleware';

import type { PrometheusAlertPayload, PrometheusAlertSeverity } from '../types/websocket-events';

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
 * - Uses Immer for immutable state updates with mutable syntax
 * - Uses subscribeWithSelector for fine-grained subscriptions
 *
 * @example
 * ```tsx
 * import { usePrometheusAlertStore } from '@/stores/prometheus-alert-store';
 *
 * // In a component - subscribe to specific counts
 * const criticalCount = usePrometheusAlertStore((state) => state.criticalCount);
 *
 * // Subscribe to alerts object with shallow comparison
 * const alerts = usePrometheusAlertStore((state) => state.alerts);
 *
 * // Display alert badge
 * if (criticalCount > 0) {
 *   return <Badge color="red">{criticalCount} Critical</Badge>;
 * }
 *
 * // Subscribe to changes programmatically
 * const unsubscribe = usePrometheusAlertStore.subscribe(
 *   (state) => state.criticalCount,
 *   (newCount, prevCount) => {
 *     if (newCount > prevCount) {
 *       playAlertSound();
 *     }
 *   }
 * );
 * ```
 */
export const usePrometheusAlertStore = createImmerSelectorStore<PrometheusAlertState>(
  (set: ImmerSetState<PrometheusAlertState>, get) => ({
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
        // Add or update the alert using Immer
        set((draft: PrometheusAlertState) => {
          draft.alerts[fingerprint] = {
            fingerprint,
            alertname,
            severity,
            labels,
            annotations,
            startsAt: starts_at,
            receivedAt: received_at,
          };

          // Recalculate counts
          const counts = calculateSeverityCounts(draft.alerts);
          draft.criticalCount = counts.criticalCount;
          draft.warningCount = counts.warningCount;
          draft.infoCount = counts.infoCount;
          draft.totalCount = counts.totalCount;
        });
      } else if (status === 'resolved') {
        // Only update if the alert exists
        if (get().alerts[fingerprint]) {
          set((draft: PrometheusAlertState) => {
            delete draft.alerts[fingerprint];

            // Recalculate counts
            const counts = calculateSeverityCounts(draft.alerts);
            draft.criticalCount = counts.criticalCount;
            draft.warningCount = counts.warningCount;
            draft.infoCount = counts.infoCount;
            draft.totalCount = counts.totalCount;
          });
        }
      }
    },

    removeAlert: (fingerprint: string) => {
      if (get().alerts[fingerprint]) {
        set((draft: PrometheusAlertState) => {
          delete draft.alerts[fingerprint];

          // Recalculate counts
          const counts = calculateSeverityCounts(draft.alerts);
          draft.criticalCount = counts.criticalCount;
          draft.warningCount = counts.warningCount;
          draft.infoCount = counts.infoCount;
          draft.totalCount = counts.totalCount;
        });
      }
    },

    clear: () => {
      set((draft: PrometheusAlertState) => {
        draft.alerts = {};
        draft.criticalCount = 0;
        draft.warningCount = 0;
        draft.infoCount = 0;
        draft.totalCount = 0;
      });
    },
  }),
  { name: 'prometheus-alert-store' }
);

// ============================================================================
// Selectors (Memoized - NEM-5034)
// ============================================================================

/**
 * Memoized selector for critical alerts.
 * Returns stable reference when alerts haven't changed.
 */
export const selectCriticalAlerts = createComputedSelector(
  (state: PrometheusAlertState): StoredPrometheusAlert[] =>
    Object.values(state.alerts).filter((a) => a.severity === 'critical')
);

/**
 * Memoized selector for warning alerts.
 * Returns stable reference when alerts haven't changed.
 */
export const selectWarningAlerts = createComputedSelector(
  (state: PrometheusAlertState): StoredPrometheusAlert[] =>
    Object.values(state.alerts).filter((a) => a.severity === 'warning')
);

/**
 * Memoized selector for info alerts.
 * Returns stable reference when alerts haven't changed.
 */
export const selectInfoAlerts = createComputedSelector(
  (state: PrometheusAlertState): StoredPrometheusAlert[] =>
    Object.values(state.alerts).filter((a) => a.severity === 'info')
);

/**
 * Memoized selector for all alerts sorted by severity (critical first, then warning, then info).
 * Returns stable reference when alerts haven't changed.
 */
export const selectAlertsSortedBySeverity = createComputedSelector(
  (state: PrometheusAlertState): StoredPrometheusAlert[] => {
    const severityOrder: Record<PrometheusAlertSeverity, number> = {
      critical: 0,
      warning: 1,
      info: 2,
    };

    return Object.values(state.alerts).sort(
      (a, b) => severityOrder[a.severity] - severityOrder[b.severity]
    );
  }
);

/**
 * Selector for a specific alert by fingerprint.
 * Not memoized as it returns a direct lookup (O(1) operation).
 */
export const selectAlertByFingerprint = (
  state: PrometheusAlertState,
  fingerprint: string
): StoredPrometheusAlert | undefined => {
  return state.alerts[fingerprint];
};

/**
 * Factory for creating memoized alert-by-name selectors.
 * Each unique alertname gets its own memoized selector.
 *
 * @example
 * ```typescript
 * const selectHighCPUAlerts = createSelectAlertsByName('HighCPU');
 * const alerts = selectHighCPUAlerts(state);
 * ```
 */
const alertsByNameSelectors = new Map<
  string,
  (state: PrometheusAlertState) => StoredPrometheusAlert[]
>();

/**
 * Memoized selector for alerts by alertname.
 * Uses a factory pattern to cache selectors per alertname.
 */
export const selectAlertsByName = (
  state: PrometheusAlertState,
  alertname: string
): StoredPrometheusAlert[] => {
  let selector = alertsByNameSelectors.get(alertname);
  if (!selector) {
    selector = createComputedSelector(
      (s: PrometheusAlertState): StoredPrometheusAlert[] =>
        Object.values(s.alerts).filter((a) => a.alertname === alertname)
    );
    alertsByNameSelectors.set(alertname, selector);
  }
  return selector(state);
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
// Shallow Hooks for Selective Subscriptions (NEM-3790)
// ============================================================================

/**
 * Hook to select alert counts with shallow equality.
 * Prevents re-renders when only the alerts object changes but counts stay the same.
 *
 * @example
 * ```tsx
 * const { criticalCount, warningCount, infoCount, totalCount } = usePrometheusAlertCounts();
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
 * Hook to select alerts map.
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
 * Hook to select prometheus alert actions only.
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

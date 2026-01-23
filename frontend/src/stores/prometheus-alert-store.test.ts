import { describe, it, expect, beforeEach } from 'vitest';

import {
  usePrometheusAlertStore,
  selectCriticalAlerts,
  selectWarningAlerts,
  selectInfoAlerts,
  selectAlertsSortedBySeverity,
  selectAlertByFingerprint,
  selectAlertsByName,
  selectHasActiveAlerts,
  selectHasCriticalAlerts,
  // Memoized selectors (NEM-3428)
  selectCriticalAlertsMemoized,
  selectWarningAlertsMemoized,
  selectInfoAlertsMemoized,
  selectAlertsSortedBySeverityMemoized,
} from './prometheus-alert-store';

import type { PrometheusAlertPayload } from '../types/websocket-events';

// Helper to create a valid Prometheus alert payload
function createAlertPayload(
  overrides: Partial<PrometheusAlertPayload> = {}
): PrometheusAlertPayload {
  return {
    fingerprint: 'abc123',
    status: 'firing',
    alertname: 'HighGPUMemory',
    severity: 'warning',
    labels: { instance: 'localhost:9090', job: 'rtdetr' },
    annotations: { summary: 'GPU memory is high', description: 'GPU memory usage above 80%' },
    starts_at: '2026-01-20T10:00:00Z',
    ends_at: null,
    received_at: '2026-01-20T10:00:01Z',
    ...overrides,
  };
}

describe('prometheus-alert-store', () => {
  beforeEach(() => {
    // Reset store state before each test
    usePrometheusAlertStore.getState().clear();
  });

  describe('initial state', () => {
    it('has empty alerts and zero counts initially', () => {
      const state = usePrometheusAlertStore.getState();
      expect(state.alerts).toEqual({});
      expect(state.criticalCount).toBe(0);
      expect(state.warningCount).toBe(0);
      expect(state.infoCount).toBe(0);
      expect(state.totalCount).toBe(0);
    });
  });

  describe('handlePrometheusAlert', () => {
    it('adds a firing alert to the store', () => {
      const { handlePrometheusAlert } = usePrometheusAlertStore.getState();
      const payload = createAlertPayload({
        fingerprint: 'alert1',
        alertname: 'HighCPU',
        severity: 'critical',
      });

      handlePrometheusAlert(payload);

      const state = usePrometheusAlertStore.getState();
      expect(state.alerts['alert1']).toBeDefined();
      expect(state.alerts['alert1'].alertname).toBe('HighCPU');
      expect(state.alerts['alert1'].severity).toBe('critical');
      expect(state.criticalCount).toBe(1);
      expect(state.totalCount).toBe(1);
    });

    it('updates an existing alert with the same fingerprint', () => {
      const { handlePrometheusAlert } = usePrometheusAlertStore.getState();

      // Add initial alert
      const initial = createAlertPayload({
        fingerprint: 'alert1',
        alertname: 'HighCPU',
        severity: 'warning',
      });
      handlePrometheusAlert(initial);

      // Update with new data
      const updated = createAlertPayload({
        fingerprint: 'alert1',
        alertname: 'HighCPU',
        severity: 'critical', // Severity upgraded
      });
      handlePrometheusAlert(updated);

      const state = usePrometheusAlertStore.getState();
      expect(state.alerts['alert1'].severity).toBe('critical');
      expect(state.criticalCount).toBe(1);
      expect(state.warningCount).toBe(0);
      expect(state.totalCount).toBe(1);
    });

    it('removes a resolved alert from the store', () => {
      const { handlePrometheusAlert } = usePrometheusAlertStore.getState();

      // Add alert
      const firing = createAlertPayload({
        fingerprint: 'alert1',
        status: 'firing',
        severity: 'warning',
      });
      handlePrometheusAlert(firing);

      // Verify it was added
      let state = usePrometheusAlertStore.getState();
      expect(state.alerts['alert1']).toBeDefined();
      expect(state.warningCount).toBe(1);

      // Resolve alert
      const resolved = createAlertPayload({
        fingerprint: 'alert1',
        status: 'resolved',
        severity: 'warning',
      });
      handlePrometheusAlert(resolved);

      // Verify it was removed
      state = usePrometheusAlertStore.getState();
      expect(state.alerts['alert1']).toBeUndefined();
      expect(state.warningCount).toBe(0);
      expect(state.totalCount).toBe(0);
    });

    it('does nothing when resolving a non-existent alert', () => {
      const { handlePrometheusAlert } = usePrometheusAlertStore.getState();

      const resolved = createAlertPayload({
        fingerprint: 'nonexistent',
        status: 'resolved',
      });
      handlePrometheusAlert(resolved);

      const state = usePrometheusAlertStore.getState();
      expect(state.alerts).toEqual({});
      expect(state.totalCount).toBe(0);
    });

    it('calculates correct counts for multiple alerts of different severities', () => {
      const { handlePrometheusAlert } = usePrometheusAlertStore.getState();

      handlePrometheusAlert(
        createAlertPayload({ fingerprint: 'a1', severity: 'critical', alertname: 'Alert1' })
      );
      handlePrometheusAlert(
        createAlertPayload({ fingerprint: 'a2', severity: 'critical', alertname: 'Alert2' })
      );
      handlePrometheusAlert(
        createAlertPayload({ fingerprint: 'a3', severity: 'warning', alertname: 'Alert3' })
      );
      handlePrometheusAlert(
        createAlertPayload({ fingerprint: 'a4', severity: 'info', alertname: 'Alert4' })
      );
      handlePrometheusAlert(
        createAlertPayload({ fingerprint: 'a5', severity: 'info', alertname: 'Alert5' })
      );
      handlePrometheusAlert(
        createAlertPayload({ fingerprint: 'a6', severity: 'info', alertname: 'Alert6' })
      );

      const state = usePrometheusAlertStore.getState();
      expect(state.criticalCount).toBe(2);
      expect(state.warningCount).toBe(1);
      expect(state.infoCount).toBe(3);
      expect(state.totalCount).toBe(6);
    });
  });

  describe('removeAlert', () => {
    it('removes an alert by fingerprint', () => {
      const { handlePrometheusAlert, removeAlert } = usePrometheusAlertStore.getState();

      handlePrometheusAlert(createAlertPayload({ fingerprint: 'alert1', severity: 'critical' }));
      handlePrometheusAlert(createAlertPayload({ fingerprint: 'alert2', severity: 'warning' }));

      let state = usePrometheusAlertStore.getState();
      expect(state.totalCount).toBe(2);

      removeAlert('alert1');

      state = usePrometheusAlertStore.getState();
      expect(state.alerts['alert1']).toBeUndefined();
      expect(state.alerts['alert2']).toBeDefined();
      expect(state.criticalCount).toBe(0);
      expect(state.warningCount).toBe(1);
      expect(state.totalCount).toBe(1);
    });

    it('does nothing when removing a non-existent alert', () => {
      const { handlePrometheusAlert, removeAlert } = usePrometheusAlertStore.getState();

      handlePrometheusAlert(createAlertPayload({ fingerprint: 'alert1' }));

      removeAlert('nonexistent');

      const state = usePrometheusAlertStore.getState();
      expect(state.totalCount).toBe(1);
    });
  });

  describe('clear', () => {
    it('clears all alerts and resets counts', () => {
      const { handlePrometheusAlert, clear } = usePrometheusAlertStore.getState();

      handlePrometheusAlert(createAlertPayload({ fingerprint: 'a1', severity: 'critical' }));
      handlePrometheusAlert(createAlertPayload({ fingerprint: 'a2', severity: 'warning' }));
      handlePrometheusAlert(createAlertPayload({ fingerprint: 'a3', severity: 'info' }));

      let state = usePrometheusAlertStore.getState();
      expect(state.totalCount).toBe(3);

      clear();

      state = usePrometheusAlertStore.getState();
      expect(state.alerts).toEqual({});
      expect(state.criticalCount).toBe(0);
      expect(state.warningCount).toBe(0);
      expect(state.infoCount).toBe(0);
      expect(state.totalCount).toBe(0);
    });
  });

  describe('selectors', () => {
    beforeEach(() => {
      const { handlePrometheusAlert } = usePrometheusAlertStore.getState();

      handlePrometheusAlert(
        createAlertPayload({
          fingerprint: 'critical1',
          alertname: 'HighCPU',
          severity: 'critical',
        })
      );
      handlePrometheusAlert(
        createAlertPayload({
          fingerprint: 'critical2',
          alertname: 'HighMemory',
          severity: 'critical',
        })
      );
      handlePrometheusAlert(
        createAlertPayload({
          fingerprint: 'warning1',
          alertname: 'HighDisk',
          severity: 'warning',
        })
      );
      handlePrometheusAlert(
        createAlertPayload({ fingerprint: 'info1', alertname: 'InfoAlert', severity: 'info' })
      );
    });

    it('selectCriticalAlerts returns only critical alerts', () => {
      const state = usePrometheusAlertStore.getState();
      const critical = selectCriticalAlerts(state);

      expect(critical.length).toBe(2);
      expect(critical.every((a) => a.severity === 'critical')).toBe(true);
    });

    it('selectWarningAlerts returns only warning alerts', () => {
      const state = usePrometheusAlertStore.getState();
      const warnings = selectWarningAlerts(state);

      expect(warnings.length).toBe(1);
      expect(warnings[0].alertname).toBe('HighDisk');
    });

    it('selectInfoAlerts returns only info alerts', () => {
      const state = usePrometheusAlertStore.getState();
      const infos = selectInfoAlerts(state);

      expect(infos.length).toBe(1);
      expect(infos[0].alertname).toBe('InfoAlert');
    });

    it('selectAlertsSortedBySeverity returns alerts sorted by severity', () => {
      const state = usePrometheusAlertStore.getState();
      const sorted = selectAlertsSortedBySeverity(state);

      expect(sorted.length).toBe(4);
      // First should be critical alerts
      expect(sorted[0].severity).toBe('critical');
      expect(sorted[1].severity).toBe('critical');
      // Then warning
      expect(sorted[2].severity).toBe('warning');
      // Then info
      expect(sorted[3].severity).toBe('info');
    });

    it('selectAlertByFingerprint returns the correct alert', () => {
      const state = usePrometheusAlertStore.getState();
      const alert = selectAlertByFingerprint(state, 'warning1');

      expect(alert).toBeDefined();
      expect(alert?.alertname).toBe('HighDisk');
    });

    it('selectAlertByFingerprint returns undefined for non-existent alert', () => {
      const state = usePrometheusAlertStore.getState();
      const alert = selectAlertByFingerprint(state, 'nonexistent');

      expect(alert).toBeUndefined();
    });

    it('selectAlertsByName returns alerts matching the name', () => {
      const { handlePrometheusAlert } = usePrometheusAlertStore.getState();

      // Add another alert with the same name
      handlePrometheusAlert(
        createAlertPayload({
          fingerprint: 'critical3',
          alertname: 'HighCPU',
          severity: 'warning',
          labels: { instance: 'another-host' },
        })
      );

      const state = usePrometheusAlertStore.getState();
      const alerts = selectAlertsByName(state, 'HighCPU');

      expect(alerts.length).toBe(2);
      expect(alerts.every((a) => a.alertname === 'HighCPU')).toBe(true);
    });

    it('selectHasActiveAlerts returns true when alerts exist', () => {
      const state = usePrometheusAlertStore.getState();
      expect(selectHasActiveAlerts(state)).toBe(true);
    });

    it('selectHasActiveAlerts returns false when no alerts', () => {
      usePrometheusAlertStore.getState().clear();
      const state = usePrometheusAlertStore.getState();
      expect(selectHasActiveAlerts(state)).toBe(false);
    });

    it('selectHasCriticalAlerts returns true when critical alerts exist', () => {
      const state = usePrometheusAlertStore.getState();
      expect(selectHasCriticalAlerts(state)).toBe(true);
    });

    it('selectHasCriticalAlerts returns false when no critical alerts', () => {
      // Clear and add only non-critical alerts
      usePrometheusAlertStore.getState().clear();
      const { handlePrometheusAlert } = usePrometheusAlertStore.getState();
      handlePrometheusAlert(createAlertPayload({ fingerprint: 'w1', severity: 'warning' }));

      const state = usePrometheusAlertStore.getState();
      expect(selectHasCriticalAlerts(state)).toBe(false);
    });
  });

  describe('memoized selectors (NEM-3428)', () => {
    beforeEach(() => {
      usePrometheusAlertStore.getState().clear();
      const { handlePrometheusAlert } = usePrometheusAlertStore.getState();
      handlePrometheusAlert(createAlertPayload({ fingerprint: 'c1', severity: 'critical' }));
      handlePrometheusAlert(createAlertPayload({ fingerprint: 'w1', severity: 'warning' }));
      handlePrometheusAlert(createAlertPayload({ fingerprint: 'i1', severity: 'info' }));
    });

    it('selectCriticalAlertsMemoized returns cached result on repeated calls', () => {
      const state = usePrometheusAlertStore.getState();
      const result1 = selectCriticalAlertsMemoized(state);
      const result2 = selectCriticalAlertsMemoized(state);

      expect(result1).toBe(result2); // Same reference
      expect(result1).toHaveLength(1);
    });

    it('selectWarningAlertsMemoized returns cached result on repeated calls', () => {
      const state = usePrometheusAlertStore.getState();
      const result1 = selectWarningAlertsMemoized(state);
      const result2 = selectWarningAlertsMemoized(state);

      expect(result1).toBe(result2); // Same reference
      expect(result1).toHaveLength(1);
    });

    it('selectInfoAlertsMemoized returns cached result on repeated calls', () => {
      const state = usePrometheusAlertStore.getState();
      const result1 = selectInfoAlertsMemoized(state);
      const result2 = selectInfoAlertsMemoized(state);

      expect(result1).toBe(result2); // Same reference
      expect(result1).toHaveLength(1);
    });

    it('selectAlertsSortedBySeverityMemoized returns cached result on repeated calls', () => {
      const state = usePrometheusAlertStore.getState();
      const result1 = selectAlertsSortedBySeverityMemoized(state);
      const result2 = selectAlertsSortedBySeverityMemoized(state);

      expect(result1).toBe(result2); // Same reference
      expect(result1).toHaveLength(3);
      expect(result1[0].severity).toBe('critical');
      expect(result1[1].severity).toBe('warning');
      expect(result1[2].severity).toBe('info');
    });

    it('memoized selectors recompute when state changes', () => {
      const state1 = usePrometheusAlertStore.getState();
      const result1 = selectCriticalAlertsMemoized(state1);

      // Add another alert to change the state
      usePrometheusAlertStore.getState().handlePrometheusAlert(
        createAlertPayload({ fingerprint: 'c2', severity: 'critical' })
      );

      const state2 = usePrometheusAlertStore.getState();
      const result2 = selectCriticalAlertsMemoized(state2);

      expect(result1).not.toBe(result2); // Different reference
      expect(result2).toHaveLength(2);
    });
  });
});

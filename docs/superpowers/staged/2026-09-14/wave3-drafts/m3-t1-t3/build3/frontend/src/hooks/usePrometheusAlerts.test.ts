/**
 * Tests for usePrometheusAlerts hook (NEM-3124)
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { toast } from 'sonner';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { usePrometheusAlerts } from './usePrometheusAlerts';
import { usePrometheusAlertStore } from '../stores/prometheus-alert-store';

import type { PrometheusAlertPayload } from '../types/websocket-events';

// Mock dependencies
vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  },
}));

vi.mock('../services/logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock('../services/api', () => ({
  buildWebSocketOptions: vi.fn(() => ({
    url: 'ws://localhost:8000/ws/events',
    protocols: [],
  })),
}));

// Mock useWebSocket with captured callback
let capturedOnMessage: ((data: unknown) => void) | undefined;

vi.mock('./useWebSocket', () => ({
  useWebSocket: vi.fn((options) => {
    capturedOnMessage = options?.onMessage;
    return {
      isConnected: true,
      lastMessage: null,
      send: vi.fn(),
      connect: vi.fn(),
      disconnect: vi.fn(),
      hasExhaustedRetries: false,
      reconnectCount: 0,
      lastHeartbeat: null,
      connectionId: 'mock-connection-id',
    };
  }),
}));

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

// Helper to create a WebSocket message
function createWebSocketMessage(payload: PrometheusAlertPayload) {
  return {
    type: 'prometheus.alert',
    payload,
  };
}

describe('usePrometheusAlerts', () => {
  beforeEach(() => {
    // Reset store state
    usePrometheusAlertStore.getState().clear();
    // Reset mocks
    vi.clearAllMocks();
    capturedOnMessage = undefined;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('returns empty alerts and zero counts initially', () => {
      const { result } = renderHook(() => usePrometheusAlerts());

      expect(result.current.alerts).toEqual({});
      expect(result.current.alertsSorted).toEqual([]);
      expect(result.current.criticalCount).toBe(0);
      expect(result.current.warningCount).toBe(0);
      expect(result.current.infoCount).toBe(0);
      expect(result.current.totalCount).toBe(0);
      expect(result.current.hasActiveAlerts).toBe(false);
      expect(result.current.hasCriticalAlerts).toBe(false);
    });

    it('returns connection status from useWebSocket', () => {
      const { result } = renderHook(() => usePrometheusAlerts());
      expect(result.current.isConnected).toBe(true);
    });
  });

  describe('message handling', () => {
    it('adds firing alert to store when message received', async () => {
      const { result } = renderHook(() => usePrometheusAlerts());

      const payload = createAlertPayload({
        fingerprint: 'alert1',
        alertname: 'HighCPU',
        severity: 'critical',
        status: 'firing',
      });

      act(() => {
        capturedOnMessage?.(createWebSocketMessage(payload));
      });

      await waitFor(() => {
        expect(result.current.alerts['alert1']).toBeDefined();
        expect(result.current.alerts['alert1'].alertname).toBe('HighCPU');
        expect(result.current.criticalCount).toBe(1);
        expect(result.current.hasActiveAlerts).toBe(true);
        expect(result.current.hasCriticalAlerts).toBe(true);
      });
    });

    it('removes resolved alert from store', async () => {
      const { result } = renderHook(() => usePrometheusAlerts());

      // First, add a firing alert
      const firingPayload = createAlertPayload({
        fingerprint: 'alert1',
        status: 'firing',
        severity: 'warning',
      });

      act(() => {
        capturedOnMessage?.(createWebSocketMessage(firingPayload));
      });

      await waitFor(() => {
        expect(result.current.alerts['alert1']).toBeDefined();
      });

      // Then, resolve it
      const resolvedPayload = createAlertPayload({
        fingerprint: 'alert1',
        status: 'resolved',
        severity: 'warning',
      });

      act(() => {
        capturedOnMessage?.(createWebSocketMessage(resolvedPayload));
      });

      await waitFor(() => {
        expect(result.current.alerts['alert1']).toBeUndefined();
        expect(result.current.totalCount).toBe(0);
      });
    });

    it('ignores non-prometheus.alert messages', async () => {
      const { result } = renderHook(() => usePrometheusAlerts());

      act(() => {
        capturedOnMessage?.({ type: 'event.created', payload: {} });
        capturedOnMessage?.({ type: 'ping' });
        capturedOnMessage?.({ type: 'system.status', payload: {} });
      });

      await waitFor(() => {
        expect(result.current.totalCount).toBe(0);
      });
    });

    it('handles messages with data field instead of payload field', async () => {
      const { result } = renderHook(() => usePrometheusAlerts());

      const payload = createAlertPayload({
        fingerprint: 'alert1',
        alertname: 'TestAlert',
      });

      // Use 'data' instead of 'payload'
      act(() => {
        capturedOnMessage?.({ type: 'prometheus.alert', data: payload });
      });

      await waitFor(() => {
        expect(result.current.alerts['alert1']).toBeDefined();
        expect(result.current.alerts['alert1'].alertname).toBe('TestAlert');
      });
    });
  });

  describe('toast notifications', () => {
    it('shows error toast for critical firing alerts', async () => {
      renderHook(() => usePrometheusAlerts());

      const payload = createAlertPayload({
        fingerprint: 'critical1',
        alertname: 'CriticalAlert',
        severity: 'critical',
        status: 'firing',
        annotations: { summary: 'Critical issue', description: 'Something is very wrong' },
      });

      act(() => {
        capturedOnMessage?.(createWebSocketMessage(payload));
      });

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('Critical issue', {
          description: 'Something is very wrong',
          duration: 10000,
        });
      });
    });

    it('shows warning toast for warning firing alerts', async () => {
      renderHook(() => usePrometheusAlerts());

      const payload = createAlertPayload({
        fingerprint: 'warning1',
        alertname: 'WarningAlert',
        severity: 'warning',
        status: 'firing',
        annotations: { summary: 'Warning issue', description: 'Something needs attention' },
      });

      act(() => {
        capturedOnMessage?.(createWebSocketMessage(payload));
      });

      await waitFor(() => {
        expect(toast.warning).toHaveBeenCalledWith('Warning issue', {
          description: 'Something needs attention',
          duration: 5000,
        });
      });
    });

    it('does not show toast for info alerts', async () => {
      renderHook(() => usePrometheusAlerts());

      const payload = createAlertPayload({
        fingerprint: 'info1',
        alertname: 'InfoAlert',
        severity: 'info',
        status: 'firing',
      });

      act(() => {
        capturedOnMessage?.(createWebSocketMessage(payload));
      });

      await waitFor(() => {
        expect(toast.error).not.toHaveBeenCalled();
        expect(toast.warning).not.toHaveBeenCalled();
      });
    });

    it('does not show toast for resolved alerts', async () => {
      renderHook(() => usePrometheusAlerts());

      // First add a firing alert
      const firingPayload = createAlertPayload({
        fingerprint: 'alert1',
        severity: 'critical',
        status: 'firing',
      });

      act(() => {
        capturedOnMessage?.(createWebSocketMessage(firingPayload));
      });

      vi.clearAllMocks();

      // Then resolve it
      const resolvedPayload = createAlertPayload({
        fingerprint: 'alert1',
        severity: 'critical',
        status: 'resolved',
      });

      act(() => {
        capturedOnMessage?.(createWebSocketMessage(resolvedPayload));
      });

      await waitFor(() => {
        expect(toast.error).not.toHaveBeenCalled();
        expect(toast.warning).not.toHaveBeenCalled();
      });
    });

    it('uses alertname as toast title if no summary annotation', async () => {
      renderHook(() => usePrometheusAlerts());

      const payload = createAlertPayload({
        fingerprint: 'alert1',
        alertname: 'HighMemoryUsage',
        severity: 'critical',
        status: 'firing',
        annotations: {}, // No summary
      });

      act(() => {
        capturedOnMessage?.(createWebSocketMessage(payload));
      });

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith(
          'HighMemoryUsage',
          expect.objectContaining({ duration: 10000 })
        );
      });
    });

    it('respects showToasts=false option', async () => {
      renderHook(() => usePrometheusAlerts({ showToasts: false }));

      const payload = createAlertPayload({
        fingerprint: 'alert1',
        severity: 'critical',
        status: 'firing',
      });

      act(() => {
        capturedOnMessage?.(createWebSocketMessage(payload));
      });

      await waitFor(() => {
        expect(toast.error).not.toHaveBeenCalled();
        expect(toast.warning).not.toHaveBeenCalled();
      });
    });
  });

  describe('callbacks', () => {
    it('calls onAlertFiring callback for firing alerts', async () => {
      const onAlertFiring = vi.fn();
      renderHook(() => usePrometheusAlerts({ onAlertFiring }));

      const payload = createAlertPayload({
        fingerprint: 'alert1',
        status: 'firing',
      });

      act(() => {
        capturedOnMessage?.(createWebSocketMessage(payload));
      });

      await waitFor(() => {
        expect(onAlertFiring).toHaveBeenCalledWith(payload);
      });
    });

    it('calls onAlertResolved callback for resolved alerts', async () => {
      const onAlertResolved = vi.fn();
      renderHook(() => usePrometheusAlerts({ onAlertResolved }));

      // First add a firing alert
      act(() => {
        capturedOnMessage?.(
          createWebSocketMessage(createAlertPayload({ fingerprint: 'alert1', status: 'firing' }))
        );
      });

      // Then resolve it
      const resolvedPayload = createAlertPayload({
        fingerprint: 'alert1',
        status: 'resolved',
      });

      act(() => {
        capturedOnMessage?.(createWebSocketMessage(resolvedPayload));
      });

      await waitFor(() => {
        expect(onAlertResolved).toHaveBeenCalledWith(resolvedPayload);
      });
    });
  });

  describe('clearAlerts', () => {
    it('clears all alerts from the store', async () => {
      const { result } = renderHook(() => usePrometheusAlerts());

      // Add some alerts
      act(() => {
        capturedOnMessage?.(
          createWebSocketMessage(createAlertPayload({ fingerprint: 'a1', severity: 'critical' }))
        );
        capturedOnMessage?.(
          createWebSocketMessage(createAlertPayload({ fingerprint: 'a2', severity: 'warning' }))
        );
      });

      await waitFor(() => {
        expect(result.current.totalCount).toBe(2);
      });

      // Clear alerts
      act(() => {
        result.current.clearAlerts();
      });

      await waitFor(() => {
        expect(result.current.totalCount).toBe(0);
        expect(result.current.alerts).toEqual({});
      });
    });
  });

  describe('alertsBySeverity', () => {
    it('groups alerts by severity correctly', async () => {
      const { result } = renderHook(() => usePrometheusAlerts());

      act(() => {
        capturedOnMessage?.(
          createWebSocketMessage(
            createAlertPayload({ fingerprint: 'c1', severity: 'critical', alertname: 'C1' })
          )
        );
        capturedOnMessage?.(
          createWebSocketMessage(
            createAlertPayload({ fingerprint: 'c2', severity: 'critical', alertname: 'C2' })
          )
        );
        capturedOnMessage?.(
          createWebSocketMessage(
            createAlertPayload({ fingerprint: 'w1', severity: 'warning', alertname: 'W1' })
          )
        );
        capturedOnMessage?.(
          createWebSocketMessage(
            createAlertPayload({ fingerprint: 'i1', severity: 'info', alertname: 'I1' })
          )
        );
      });

      await waitFor(() => {
        expect(result.current.alertsBySeverity.critical.length).toBe(2);
        expect(result.current.alertsBySeverity.warning.length).toBe(1);
        expect(result.current.alertsBySeverity.info.length).toBe(1);
      });
    });
  });

  describe('counts object', () => {
    it('provides counts in both formats for compatibility', async () => {
      const { result } = renderHook(() => usePrometheusAlerts());

      act(() => {
        capturedOnMessage?.(
          createWebSocketMessage(createAlertPayload({ fingerprint: 'c1', severity: 'critical' }))
        );
        capturedOnMessage?.(
          createWebSocketMessage(createAlertPayload({ fingerprint: 'w1', severity: 'warning' }))
        );
        capturedOnMessage?.(
          createWebSocketMessage(createAlertPayload({ fingerprint: 'w2', severity: 'warning' }))
        );
      });

      await waitFor(() => {
        // New format (individual properties)
        expect(result.current.criticalCount).toBe(1);
        expect(result.current.warningCount).toBe(2);
        expect(result.current.infoCount).toBe(0);
        expect(result.current.totalCount).toBe(3);

        // Legacy format (counts object)
        expect(result.current.counts.critical).toBe(1);
        expect(result.current.counts.warning).toBe(2);
        expect(result.current.counts.info).toBe(0);
        expect(result.current.counts.total).toBe(3);
      });
    });
  });
});

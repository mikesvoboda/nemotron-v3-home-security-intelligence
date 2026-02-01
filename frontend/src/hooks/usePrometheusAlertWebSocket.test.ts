/**
 * Tests for usePrometheusAlertWebSocket hook
 *
 * NEM-3124: WebSocket handlers for prometheus.alert events on /ws/system
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { usePrometheusAlertWebSocket } from './usePrometheusAlertWebSocket';
import { usePrometheusAlertStore } from '../stores/prometheus-alert-store';

import type { PrometheusAlertPayload } from '../types/websocket-events';

// Store the captured onMessage handler
const mockOnMessage = vi.fn<(data: unknown) => void>();
const mockWsReturn = {
  isConnected: true,
  lastMessage: null,
  send: vi.fn(),
  connect: vi.fn(),
  disconnect: vi.fn(),
  hasExhaustedRetries: false,
  reconnectCount: 0,
  lastHeartbeat: null,
  connectionId: 'test-connection-id',
};

vi.mock('./useWebSocket', () => ({
  useWebSocket: vi.fn((options: { onMessage?: (data: unknown) => void }) => {
    if (options.onMessage) {
      mockOnMessage.mockImplementation(options.onMessage);
    }
    return mockWsReturn;
  }),
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
    url: 'ws://localhost:8000/ws/system',
    protocols: [],
  })),
}));

describe('usePrometheusAlertWebSocket', () => {
  /**
   * Helper to simulate receiving a WebSocket message.
   */
  const simulateMessage = (message: unknown): void => {
    act(() => {
      mockOnMessage(message);
    });
  };

  /**
   * Create a mock Prometheus alert payload.
   */
  const createAlertPayload = (
    overrides: Partial<PrometheusAlertPayload> = {}
  ): PrometheusAlertPayload => ({
    fingerprint: 'abc123',
    status: 'firing',
    alertname: 'HighGpuUtilization',
    severity: 'warning',
    labels: { instance: 'gpu:0', job: 'nvidia_exporter' },
    annotations: { summary: 'GPU utilization above 90%', description: 'GPU 0 is at 95%' },
    starts_at: '2024-01-01T12:00:00Z',
    ends_at: null,
    received_at: '2024-01-01T12:00:01Z',
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset the store before each test
    usePrometheusAlertStore.getState().clear();
  });

  afterEach(() => {
    // Clean up store after each test
    usePrometheusAlertStore.getState().clear();
  });

  describe('initialization', () => {
    it('should return initial state with empty alerts', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      expect(result.current.alerts).toEqual({});
      expect(result.current.alertsSorted).toEqual([]);
      expect(result.current.history).toEqual([]);
      expect(result.current.isConnected).toBe(true);
      expect(result.current.lastUpdate).toBeNull();
      expect(result.current.totalCount).toBe(0);
      expect(result.current.criticalCount).toBe(0);
      expect(result.current.warningCount).toBe(0);
      expect(result.current.infoCount).toBe(0);
    });

    it('should connect to WebSocket when enabled', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket({ enabled: true }));
      expect(result.current.isConnected).toBe(true);
    });

    it('should expose alertsBySeverity grouped correctly', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      expect(result.current.alertsBySeverity).toEqual({
        critical: [],
        warning: [],
        info: [],
      });
    });

    it('should expose counts object', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      expect(result.current.counts).toEqual({
        critical: 0,
        warning: 0,
        info: 0,
        total: 0,
      });
    });
  });

  describe('prometheus.alert events - firing', () => {
    it('should handle firing alert messages with data field', () => {
      const onAlertFiring = vi.fn();
      const onAlert = vi.fn();
      const { result } = renderHook(() =>
        usePrometheusAlertWebSocket({ onAlertFiring, onAlert })
      );

      const alertPayload = createAlertPayload();

      simulateMessage({
        type: 'prometheus.alert',
        data: alertPayload,
      });

      expect(result.current.alerts).toHaveProperty(alertPayload.fingerprint);
      expect(result.current.totalCount).toBe(1);
      expect(result.current.warningCount).toBe(1);
      expect(result.current.lastUpdate).not.toBeNull();
      expect(onAlertFiring).toHaveBeenCalledWith(alertPayload);
      expect(onAlert).toHaveBeenCalledWith(alertPayload);
    });

    it('should handle firing alert messages with payload field', () => {
      const onAlertFiring = vi.fn();
      const { result } = renderHook(() => usePrometheusAlertWebSocket({ onAlertFiring }));

      const alertPayload = createAlertPayload();

      simulateMessage({
        type: 'prometheus.alert',
        payload: alertPayload,
      });

      expect(result.current.alerts).toHaveProperty(alertPayload.fingerprint);
      expect(result.current.totalCount).toBe(1);
      expect(onAlertFiring).toHaveBeenCalledWith(alertPayload);
    });

    it('should add firing alert to history', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      const alertPayload = createAlertPayload();

      simulateMessage({
        type: 'prometheus.alert',
        data: alertPayload,
      });

      expect(result.current.history).toHaveLength(1);
      expect(result.current.history[0].eventType).toBe('firing');
      expect(result.current.history[0].fingerprint).toBe(alertPayload.fingerprint);
    });

    it('should update existing alert when fired again', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      const alertPayload1 = createAlertPayload({
        starts_at: '2024-01-01T12:00:00Z',
      });

      const alertPayload2 = createAlertPayload({
        starts_at: '2024-01-01T12:05:00Z',
      });

      simulateMessage({ type: 'prometheus.alert', data: alertPayload1 });
      simulateMessage({ type: 'prometheus.alert', data: alertPayload2 });

      // Should still have only one alert
      expect(result.current.totalCount).toBe(1);
      // History should have two entries
      expect(result.current.history).toHaveLength(2);
    });
  });

  describe('prometheus.alert events - resolved', () => {
    it('should handle resolved alert messages', () => {
      const onAlertResolved = vi.fn();
      const onAlert = vi.fn();
      const { result } = renderHook(() =>
        usePrometheusAlertWebSocket({ onAlertResolved, onAlert })
      );

      // First fire the alert
      const firingPayload = createAlertPayload({ status: 'firing' });
      simulateMessage({ type: 'prometheus.alert', data: firingPayload });

      expect(result.current.totalCount).toBe(1);

      // Then resolve it
      const resolvedPayload = createAlertPayload({
        status: 'resolved',
        ends_at: '2024-01-01T12:30:00Z',
      });
      simulateMessage({ type: 'prometheus.alert', data: resolvedPayload });

      expect(result.current.totalCount).toBe(0);
      expect(result.current.alerts).not.toHaveProperty(resolvedPayload.fingerprint);
      expect(onAlertResolved).toHaveBeenCalledWith(resolvedPayload);
      expect(onAlert).toHaveBeenCalledTimes(2);
    });

    it('should add resolved alert to history', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      // First fire the alert
      const firingPayload = createAlertPayload({ status: 'firing' });
      simulateMessage({ type: 'prometheus.alert', data: firingPayload });

      // Then resolve it
      const resolvedPayload = createAlertPayload({ status: 'resolved' });
      simulateMessage({ type: 'prometheus.alert', data: resolvedPayload });

      expect(result.current.history).toHaveLength(2);
      expect(result.current.history[0].eventType).toBe('resolved');
      expect(result.current.history[1].eventType).toBe('firing');
    });

    it('should handle resolving non-existent alert gracefully', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      const resolvedPayload = createAlertPayload({ status: 'resolved' });
      simulateMessage({ type: 'prometheus.alert', data: resolvedPayload });

      // Should not throw, counts should be zero
      expect(result.current.totalCount).toBe(0);
    });
  });

  describe('severity counts', () => {
    it('should count critical alerts correctly', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'crit1', severity: 'critical' }),
      });
      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'crit2', severity: 'critical' }),
      });

      expect(result.current.criticalCount).toBe(2);
      expect(result.current.hasCriticalAlerts).toBe(true);
    });

    it('should count warning alerts correctly', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'warn1', severity: 'warning' }),
      });
      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'warn2', severity: 'warning' }),
      });
      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'warn3', severity: 'warning' }),
      });

      expect(result.current.warningCount).toBe(3);
    });

    it('should count info alerts correctly', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'info1', severity: 'info' }),
      });

      expect(result.current.infoCount).toBe(1);
    });

    it('should maintain correct total count', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'crit1', severity: 'critical' }),
      });
      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'warn1', severity: 'warning' }),
      });
      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'info1', severity: 'info' }),
      });

      expect(result.current.totalCount).toBe(3);
      expect(result.current.hasActiveAlerts).toBe(true);
      expect(result.current.counts).toEqual({
        critical: 1,
        warning: 1,
        info: 1,
        total: 3,
      });
    });
  });

  describe('alertsSorted and alertsBySeverity', () => {
    it('should sort alerts by severity (critical first)', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'info1', severity: 'info', alertname: 'Info' }),
      });
      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({
          fingerprint: 'crit1',
          severity: 'critical',
          alertname: 'Critical',
        }),
      });
      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({
          fingerprint: 'warn1',
          severity: 'warning',
          alertname: 'Warning',
        }),
      });

      expect(result.current.alertsSorted).toHaveLength(3);
      expect(result.current.alertsSorted[0].severity).toBe('critical');
      expect(result.current.alertsSorted[1].severity).toBe('warning');
      expect(result.current.alertsSorted[2].severity).toBe('info');
    });

    it('should group alerts by severity', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'crit1', severity: 'critical' }),
      });
      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'warn1', severity: 'warning' }),
      });
      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'warn2', severity: 'warning' }),
      });

      expect(result.current.alertsBySeverity.critical).toHaveLength(1);
      expect(result.current.alertsBySeverity.warning).toHaveLength(2);
      expect(result.current.alertsBySeverity.info).toHaveLength(0);
    });
  });

  describe('history management', () => {
    it('should respect maxHistory limit', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket({ maxHistory: 3 }));

      for (let i = 1; i <= 5; i++) {
        simulateMessage({
          type: 'prometheus.alert',
          data: createAlertPayload({ fingerprint: `alert${i}`, alertname: `Alert${i}` }),
        });
      }

      expect(result.current.history).toHaveLength(3);
      // Newest first
      expect(result.current.history[0].alertname).toBe('Alert5');
      expect(result.current.history[1].alertname).toBe('Alert4');
      expect(result.current.history[2].alertname).toBe('Alert3');
    });

    it('should clear history while keeping alerts', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'alert1' }),
      });
      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'alert2' }),
      });

      expect(result.current.history).toHaveLength(2);
      expect(result.current.totalCount).toBe(2);

      act(() => {
        result.current.clearHistory();
      });

      expect(result.current.history).toHaveLength(0);
      expect(result.current.totalCount).toBe(2); // Alerts remain
    });
  });

  describe('clearAlerts', () => {
    it('should clear all alerts from the store', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'alert1', severity: 'critical' }),
      });
      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'alert2', severity: 'warning' }),
      });

      expect(result.current.totalCount).toBe(2);

      act(() => {
        result.current.clearAlerts();
      });

      expect(result.current.totalCount).toBe(0);
      expect(result.current.criticalCount).toBe(0);
      expect(result.current.warningCount).toBe(0);
      expect(result.current.hasActiveAlerts).toBe(false);
    });
  });

  describe('helper functions', () => {
    it('should get alert by fingerprint', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      const alertPayload = createAlertPayload({ fingerprint: 'unique123' });
      simulateMessage({ type: 'prometheus.alert', data: alertPayload });

      const alert = result.current.getAlert('unique123');
      expect(alert).toBeDefined();
      expect(alert?.fingerprint).toBe('unique123');

      const nonExistent = result.current.getAlert('nonexistent');
      expect(nonExistent).toBeUndefined();
    });

    it('should get alerts by alertname', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'f1', alertname: 'HighGpuUtilization' }),
      });
      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'f2', alertname: 'HighGpuUtilization' }),
      });
      simulateMessage({
        type: 'prometheus.alert',
        data: createAlertPayload({ fingerprint: 'f3', alertname: 'LowMemory' }),
      });

      const gpuAlerts = result.current.getAlertsByName('HighGpuUtilization');
      expect(gpuAlerts).toHaveLength(2);

      const memoryAlerts = result.current.getAlertsByName('LowMemory');
      expect(memoryAlerts).toHaveLength(1);

      const nonExistent = result.current.getAlertsByName('NonExistent');
      expect(nonExistent).toHaveLength(0);
    });
  });

  describe('message filtering', () => {
    it('should ignore non-prometheus.alert messages', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      simulateMessage({ type: 'ping' });
      simulateMessage({ type: 'system_status', data: { health: 'healthy' } });
      simulateMessage({ type: 'system.health_changed', data: { health: 'healthy' } });
      simulateMessage({ type: 'gpu.stats_updated', data: { utilization: 50 } });

      expect(result.current.alerts).toEqual({});
      expect(result.current.history).toEqual([]);
    });

    it('should ignore malformed prometheus.alert messages', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      simulateMessage(null);
      simulateMessage(undefined);
      simulateMessage({ type: 'prometheus.alert' }); // missing data
      simulateMessage({ type: 'prometheus.alert', data: null });
      simulateMessage({ type: 'prometheus.alert', data: {} }); // invalid payload
      simulateMessage({
        type: 'prometheus.alert',
        data: { fingerprint: 'test' }, // missing required fields
      });

      expect(result.current.alerts).toEqual({});
    });

    it('should reject alerts with invalid severity', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      simulateMessage({
        type: 'prometheus.alert',
        data: {
          ...createAlertPayload(),
          severity: 'unknown' as 'critical' | 'warning' | 'info',
        },
      });

      expect(result.current.totalCount).toBe(0);
    });
  });

  describe('WebSocket error handling', () => {
    it('should handle error messages gracefully', () => {
      const { result } = renderHook(() => usePrometheusAlertWebSocket());

      simulateMessage({ type: 'error', message: 'Connection failed' });

      // Should not throw, state should remain unchanged
      expect(result.current.alerts).toEqual({});
    });
  });
});

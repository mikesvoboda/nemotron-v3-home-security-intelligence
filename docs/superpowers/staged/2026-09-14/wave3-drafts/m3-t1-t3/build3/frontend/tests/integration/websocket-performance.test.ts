/**
 * WebSocket Performance Integration Tests
 *
 * Tests the full WebSocket flow for performance metrics:
 * - Connection lifecycle
 * - Data flow from WebSocket to hook
 * - Hook updates triggering component state changes
 * - History accumulation over time
 * - Error handling for disconnections
 *
 * @see docs/plans/2025-12-31-system-performance-design.md
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { usePerformanceMetrics, PerformanceUpdate } from '../../src/hooks/usePerformanceMetrics';
import * as useWebSocketModule from '../../src/hooks/useWebSocket';
import type { UseWebSocketReturn } from '../../src/hooks/useWebSocket';

// Helper to wrap performance update in the backend envelope format
function wrapInEnvelope(update: PerformanceUpdate): {
  type: 'performance_update';
  data: PerformanceUpdate;
} {
  return { type: 'performance_update', data: update };
}

// Helper to create a valid performance update
function createTestPerformanceUpdate(
  overrides: Partial<PerformanceUpdate> = {}
): PerformanceUpdate {
  return {
    timestamp: new Date().toISOString(),
    gpu: null,
    ai_models: {},
    nemotron: null,
    inference: null,
    databases: {},
    host: null,
    containers: [],
    alerts: [],
    ...overrides,
  };
}

// Helper to create a full performance update with all metrics
function createFullPerformanceUpdate(): PerformanceUpdate {
  return {
    timestamp: new Date().toISOString(),
    gpu: {
      name: 'NVIDIA RTX A5500',
      utilization: 38,
      vram_used_gb: 22.7,
      vram_total_gb: 24.0,
      temperature: 38,
      power_watts: 31,
    },
    ai_models: {
      rtdetr: {
        status: 'healthy',
        vram_gb: 0.17,
        model: 'rtdetr_r50vd_coco_o365',
        device: 'cuda:0',
      },
    },
    nemotron: {
      status: 'healthy',
      slots_active: 0,
      slots_total: 2,
      context_size: 4096,
    },
    inference: {
      rtdetr_latency_ms: { avg: 45, p95: 82, p99: 120 },
      nemotron_latency_ms: { avg: 2100, p95: 4800, p99: 8200 },
      pipeline_latency_ms: { avg: 3200, p95: 6100 },
      throughput: { images_per_min: 12.4, events_per_min: 2.1 },
      queues: { detection: 0, analysis: 0 },
    },
    databases: {
      postgresql: {
        status: 'healthy',
        connections_active: 5,
        connections_max: 30,
        cache_hit_ratio: 98.2,
        transactions_per_min: 1200,
      },
      redis: {
        status: 'healthy',
        connected_clients: 8,
        memory_mb: 1.44,
        hit_ratio: 0.01,
        blocked_clients: 2,
      },
    },
    host: {
      cpu_percent: 12,
      ram_used_gb: 8.2,
      ram_total_gb: 32,
      disk_used_gb: 156,
      disk_total_gb: 500,
    },
    containers: [
      { name: 'backend', status: 'running', health: 'healthy' },
      { name: 'frontend', status: 'running', health: 'healthy' },
      { name: 'postgres', status: 'running', health: 'healthy' },
      { name: 'redis', status: 'running', health: 'healthy' },
      { name: 'ai-yolo26', status: 'running', health: 'healthy' },
      { name: 'ai-llm', status: 'running', health: 'healthy' },
    ],
    alerts: [],
  };
}

describe('WebSocket Performance Integration', () => {
  let mockIsConnected: boolean;
  let onMessageCallback: ((data: unknown) => void) | undefined;
  let onOpenCallback: (() => void) | undefined;
  let onCloseCallback: (() => void) | undefined;
  let onErrorCallback: ((error: Event) => void) | undefined;

  const createMockWebSocketReturn = (): UseWebSocketReturn => ({
    get isConnected() {
      return mockIsConnected;
    },
    lastMessage: null,
    send: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    hasExhaustedRetries: false,
    reconnectCount: 0,
  });

  beforeEach(() => {
    mockIsConnected = true;
    onMessageCallback = undefined;
    onOpenCallback = undefined;
    onCloseCallback = undefined;
    onErrorCallback = undefined;

    vi.spyOn(useWebSocketModule, 'useWebSocket').mockImplementation((options) => {
      onMessageCallback = options.onMessage;
      onOpenCallback = options.onOpen;
      onCloseCallback = options.onClose;
      onErrorCallback = options.onError;
      return createMockWebSocketReturn();
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Connection test', () => {
    it('WebSocket connects successfully to /ws/system', () => {
      renderHook(() => usePerformanceMetrics());

      expect(useWebSocketModule.useWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({
          url: expect.stringContaining('/ws/system'),
        })
      );
    });

    it('hook reflects connected state when WebSocket is connected', () => {
      mockIsConnected = true;

      const { result } = renderHook(() => usePerformanceMetrics());

      expect(result.current.isConnected).toBe(true);
    });

    it('hook reflects disconnected state when WebSocket is not connected', () => {
      mockIsConnected = false;

      const { result } = renderHook(() => usePerformanceMetrics());

      expect(result.current.isConnected).toBe(false);
    });

    it('receives initial system_status message (ignored by performance hook)', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      const systemStatusMessage = {
        type: 'system_status',
        data: {
          health: 'healthy',
          gpu: { utilization: 50 },
          cameras: { active: 3, total: 4 },
        },
        timestamp: new Date().toISOString(),
      };

      act(() => {
        onMessageCallback?.(systemStatusMessage);
      });

      // system_status should be ignored, current should still be null
      expect(result.current.current).toBeNull();
    });

    it('receives performance_update messages', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      const update = createFullPerformanceUpdate();

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update));
      });

      expect(result.current.current).not.toBeNull();
      expect(result.current.current?.gpu?.name).toBe('NVIDIA RTX A5500');
    });
  });

  describe('Data flow test', () => {
    it('performance data flows from WebSocket to hook state', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      const update = createTestPerformanceUpdate({
        gpu: {
          name: 'NVIDIA RTX A5500',
          utilization: 75.5,
          vram_used_gb: 18.0,
          vram_total_gb: 24.0,
          temperature: 55,
          power_watts: 150,
        },
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update));
      });

      expect(result.current.current?.gpu?.utilization).toBe(75.5);
      expect(result.current.current?.gpu?.temperature).toBe(55);
    });

    it('hook updates trigger state changes with new data', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      // First update
      const update1 = createTestPerformanceUpdate({
        gpu: {
          name: 'NVIDIA RTX A5500',
          utilization: 30,
          vram_used_gb: 10.0,
          vram_total_gb: 24.0,
          temperature: 40,
          power_watts: 80,
        },
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update1));
      });

      expect(result.current.current?.gpu?.utilization).toBe(30);

      // Second update
      const update2 = createTestPerformanceUpdate({
        gpu: {
          name: 'NVIDIA RTX A5500',
          utilization: 85,
          vram_used_gb: 20.0,
          vram_total_gb: 24.0,
          temperature: 70,
          power_watts: 200,
        },
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update2));
      });

      expect(result.current.current?.gpu?.utilization).toBe(85);
      expect(result.current.current?.gpu?.temperature).toBe(70);
    });

    it('history accumulates correctly over time', async () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      // Simulate receiving multiple updates over time
      for (let i = 0; i < 10; i++) {
        const update = createTestPerformanceUpdate({
          timestamp: `2025-01-01T12:00:${String(i).padStart(2, '0')}Z`,
          gpu: {
            name: 'NVIDIA RTX A5500',
            utilization: 30 + i * 5,
            vram_used_gb: 15.0 + i * 0.5,
            vram_total_gb: 24.0,
            temperature: 40 + i,
            power_watts: 100 + i * 10,
          },
        });

        act(() => {
          onMessageCallback?.(wrapInEnvelope(update));
        });
      }

      // 5m buffer should have all 10 updates
      expect(result.current.history['5m']).toHaveLength(10);

      // 15m buffer should have updates at positions 3, 6, 9 (every 3rd)
      expect(result.current.history['15m']).toHaveLength(3);

      // First entry in history should be the oldest
      expect(result.current.history['5m'][0].gpu?.utilization).toBe(30);
      // Last entry should be the newest
      expect(result.current.history['5m'][9].gpu?.utilization).toBe(75);
    });

    it('time range selection affects which history buffer is relevant', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      // Send 12 updates to have data in all buffers
      for (let i = 0; i < 12; i++) {
        const update = createTestPerformanceUpdate({
          timestamp: `2025-01-01T12:${String(i).padStart(2, '0')}:00Z`,
          gpu: {
            name: 'NVIDIA RTX A5500',
            utilization: i * 5,
            vram_used_gb: 10.0,
            vram_total_gb: 24.0,
            temperature: 40,
            power_watts: 100,
          },
        });

        act(() => {
          onMessageCallback?.(wrapInEnvelope(update));
        });
      }

      // Default time range is 5m
      expect(result.current.timeRange).toBe('5m');
      expect(result.current.history['5m']).toHaveLength(12);

      // Change to 15m
      act(() => {
        result.current.setTimeRange('15m');
      });

      expect(result.current.timeRange).toBe('15m');
      expect(result.current.history['15m']).toHaveLength(4);

      // Change to 60m
      act(() => {
        result.current.setTimeRange('60m');
      });

      expect(result.current.timeRange).toBe('60m');
      expect(result.current.history['60m']).toHaveLength(1);
    });
  });

  describe('Error handling test', () => {
    it('handles WebSocket disconnect gracefully', () => {
      const { result, rerender } = renderHook(() => usePerformanceMetrics());

      // Initially connected
      expect(result.current.isConnected).toBe(true);

      // Add some data
      const update = createFullPerformanceUpdate();
      act(() => {
        onMessageCallback?.(wrapInEnvelope(update));
      });

      expect(result.current.current).not.toBeNull();

      // Simulate disconnection
      mockIsConnected = false;
      rerender();

      // Should reflect disconnected state
      expect(result.current.isConnected).toBe(false);

      // Data should be preserved
      expect(result.current.current).not.toBeNull();
      expect(result.current.current?.gpu?.name).toBe('NVIDIA RTX A5500');
    });

    it('reconnects on connection loss and continues receiving data', () => {
      const { result, rerender } = renderHook(() => usePerformanceMetrics());

      // Add initial data
      const update1 = createTestPerformanceUpdate({
        gpu: {
          name: 'NVIDIA RTX A5500',
          utilization: 40,
          vram_used_gb: 10.0,
          vram_total_gb: 24.0,
          temperature: 45,
          power_watts: 100,
        },
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update1));
      });

      expect(result.current.history['5m']).toHaveLength(1);

      // Simulate disconnection
      mockIsConnected = false;
      rerender();
      expect(result.current.isConnected).toBe(false);

      // Simulate reconnection
      mockIsConnected = true;
      rerender();
      expect(result.current.isConnected).toBe(true);

      // Receive new data after reconnection
      const update2 = createTestPerformanceUpdate({
        gpu: {
          name: 'NVIDIA RTX A5500',
          utilization: 60,
          vram_used_gb: 15.0,
          vram_total_gb: 24.0,
          temperature: 50,
          power_watts: 120,
        },
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update2));
      });

      // Should have both updates in history
      expect(result.current.history['5m']).toHaveLength(2);
      expect(result.current.current?.gpu?.utilization).toBe(60);
    });

    it('preserves history during disconnect/reconnect cycle', () => {
      const { result, rerender } = renderHook(() => usePerformanceMetrics());

      // Add several data points
      for (let i = 0; i < 5; i++) {
        const update = createTestPerformanceUpdate({
          timestamp: `2025-01-01T12:00:${String(i).padStart(2, '0')}Z`,
          gpu: {
            name: 'NVIDIA RTX A5500',
            utilization: 20 + i * 10,
            vram_used_gb: 10.0,
            vram_total_gb: 24.0,
            temperature: 40,
            power_watts: 100,
          },
        });

        act(() => {
          onMessageCallback?.(wrapInEnvelope(update));
        });
      }

      expect(result.current.history['5m']).toHaveLength(5);

      // Disconnect
      mockIsConnected = false;
      rerender();

      // History should be preserved
      expect(result.current.history['5m']).toHaveLength(5);

      // Reconnect
      mockIsConnected = true;
      rerender();

      // History should still be there
      expect(result.current.history['5m']).toHaveLength(5);

      // Add new data
      const newUpdate = createTestPerformanceUpdate({
        timestamp: '2025-01-01T12:00:10Z',
        gpu: {
          name: 'NVIDIA RTX A5500',
          utilization: 80,
          vram_used_gb: 10.0,
          vram_total_gb: 24.0,
          temperature: 40,
          power_watts: 100,
        },
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(newUpdate));
      });

      // Should now have 6 data points
      expect(result.current.history['5m']).toHaveLength(6);
    });
  });

  describe('Alert flow test', () => {
    it('alerts flow from WebSocket to hook state', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      const update = createTestPerformanceUpdate({
        alerts: [
          {
            severity: 'warning',
            metric: 'gpu_temperature',
            value: 82,
            threshold: 80,
            message: 'GPU temperature high: 82C',
          },
        ],
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update));
      });

      expect(result.current.alerts).toHaveLength(1);
      expect(result.current.alerts[0].severity).toBe('warning');
      expect(result.current.alerts[0].metric).toBe('gpu_temperature');
    });

    it('alerts update when new data arrives', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      // First update with warning
      const update1 = createTestPerformanceUpdate({
        alerts: [
          {
            severity: 'warning',
            metric: 'cpu_usage',
            value: 85,
            threshold: 80,
            message: 'CPU usage high',
          },
        ],
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update1));
      });

      expect(result.current.alerts).toHaveLength(1);
      expect(result.current.alerts[0].severity).toBe('warning');

      // Second update with critical alert
      const update2 = createTestPerformanceUpdate({
        alerts: [
          {
            severity: 'critical',
            metric: 'vram_usage',
            value: 23.5,
            threshold: 22.8,
            message: 'VRAM critical',
          },
        ],
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update2));
      });

      expect(result.current.alerts).toHaveLength(1);
      expect(result.current.alerts[0].severity).toBe('critical');
      expect(result.current.alerts[0].metric).toBe('vram_usage');
    });
  });

  describe('Full integration scenario', () => {
    it('simulates a realistic monitoring session', async () => {
      const { result, rerender } = renderHook(() => usePerformanceMetrics());

      // Initial state
      expect(result.current.isConnected).toBe(true);
      expect(result.current.current).toBeNull();
      expect(result.current.alerts).toHaveLength(0);

      // Receive first update
      const update1 = createFullPerformanceUpdate();
      act(() => {
        onMessageCallback?.(wrapInEnvelope(update1));
      });

      expect(result.current.current).not.toBeNull();
      expect(result.current.history['5m']).toHaveLength(1);

      // Simulate 30 seconds of updates (6 updates at 5s intervals)
      for (let i = 0; i < 6; i++) {
        const update = createTestPerformanceUpdate({
          timestamp: `2025-01-01T12:00:${String((i + 1) * 5).padStart(2, '0')}Z`,
          gpu: {
            name: 'NVIDIA RTX A5500',
            utilization: 40 + i * 5,
            vram_used_gb: 20.0,
            vram_total_gb: 24.0,
            temperature: 50 + i,
            power_watts: 100 + i * 10,
          },
          host: {
            cpu_percent: 20 + i * 2,
            ram_used_gb: 10.0,
            ram_total_gb: 32,
            disk_used_gb: 100,
            disk_total_gb: 500,
          },
        });

        act(() => {
          onMessageCallback?.(wrapInEnvelope(update));
        });
      }

      // Should have 7 points in 5m buffer (1 initial + 6 updates)
      expect(result.current.history['5m']).toHaveLength(7);

      // Last update should be current
      expect(result.current.current?.gpu?.utilization).toBe(65);

      // Trigger an alert
      const alertUpdate = createTestPerformanceUpdate({
        timestamp: '2025-01-01T12:00:35Z',
        gpu: {
          name: 'NVIDIA RTX A5500',
          utilization: 95,
          vram_used_gb: 23.0,
          vram_total_gb: 24.0,
          temperature: 85,
          power_watts: 280,
        },
        alerts: [
          {
            severity: 'critical',
            metric: 'gpu_temperature',
            value: 85,
            threshold: 80,
            message: 'GPU temperature critical',
          },
        ],
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(alertUpdate));
      });

      expect(result.current.alerts).toHaveLength(1);
      expect(result.current.alerts[0].severity).toBe('critical');

      // Change time range
      act(() => {
        result.current.setTimeRange('15m');
      });

      expect(result.current.timeRange).toBe('15m');
      // 15m buffer gets updates at every 3rd message
      expect(result.current.history['15m'].length).toBeGreaterThan(0);

      // Simulate brief disconnect
      mockIsConnected = false;
      rerender();
      expect(result.current.isConnected).toBe(false);

      // Reconnect
      mockIsConnected = true;
      rerender();
      expect(result.current.isConnected).toBe(true);

      // Data should be preserved
      expect(result.current.current?.gpu?.utilization).toBe(95);
      expect(result.current.alerts).toHaveLength(1);
    });
  });
});

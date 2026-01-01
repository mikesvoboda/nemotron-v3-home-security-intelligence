import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import {
  usePerformanceMetrics,
  PerformanceUpdate,
  PerformanceAlert,
  GpuMetrics,
  HostMetrics,
  createEmptyPerformanceUpdate,
  addToCircularBuffer,
  isPerformanceUpdateMessage,
} from './usePerformanceMetrics';
import * as useWebSocketModule from './useWebSocket';

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

// Helper to create a GPU metrics object
function createTestGpuMetrics(overrides: Partial<GpuMetrics> = {}): GpuMetrics {
  return {
    name: 'NVIDIA RTX A5500',
    utilization: 38.0,
    vram_used_gb: 22.7,
    vram_total_gb: 24.0,
    temperature: 38,
    power_watts: 31,
    ...overrides,
  };
}

// Helper to create a host metrics object
function createTestHostMetrics(overrides: Partial<HostMetrics> = {}): HostMetrics {
  return {
    cpu_percent: 12,
    ram_used_gb: 8.2,
    ram_total_gb: 32,
    disk_used_gb: 156,
    disk_total_gb: 500,
    ...overrides,
  };
}

// Helper to create a performance alert
function createTestAlert(overrides: Partial<PerformanceAlert> = {}): PerformanceAlert {
  return {
    severity: 'warning',
    metric: 'gpu_temperature',
    value: 82,
    threshold: 80,
    message: 'GPU temperature high: 82C',
    ...overrides,
  };
}

describe('usePerformanceMetrics', () => {
  const mockWebSocketReturn = {
    isConnected: true,
    lastMessage: null,
    send: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    hasExhaustedRetries: false,
    reconnectCount: 0,
    lastHeartbeat: null,
  };

  let onMessageCallback: ((data: unknown) => void) | undefined;

  beforeEach(() => {
    // Mock useWebSocket to capture the onMessage callback
    vi.spyOn(useWebSocketModule, 'useWebSocket').mockImplementation((options) => {
      onMessageCallback = options.onMessage;
      return mockWebSocketReturn;
    });
    mockWebSocketReturn.isConnected = true;
  });

  afterEach(() => {
    vi.clearAllMocks();
    onMessageCallback = undefined;
  });

  describe('initialization', () => {
    it('should initialize with null current and empty history', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      expect(result.current.current).toBeNull();
      expect(result.current.history['5m']).toEqual([]);
      expect(result.current.history['15m']).toEqual([]);
      expect(result.current.history['60m']).toEqual([]);
      expect(result.current.alerts).toEqual([]);
      expect(result.current.isConnected).toBe(true);
      expect(result.current.timeRange).toBe('5m');
    });

    it('should connect to the correct WebSocket URL', () => {
      renderHook(() => usePerformanceMetrics());

      expect(useWebSocketModule.useWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({
          url: expect.stringContaining('/ws/system'),
          onMessage: expect.any(Function),
        })
      );
    });
  });

  describe('message handling', () => {
    it('should update current with valid performance update from envelope format', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      const update = createTestPerformanceUpdate({
        gpu: createTestGpuMetrics(),
        host: createTestHostMetrics(),
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update));
      });

      expect(result.current.current).not.toBeNull();
      expect(result.current.current?.gpu?.utilization).toBe(38.0);
      expect(result.current.current?.host?.cpu_percent).toBe(12);
    });

    it('should update alerts from performance update', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      const alert = createTestAlert();
      const update = createTestPerformanceUpdate({
        alerts: [alert],
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update));
      });

      expect(result.current.alerts).toHaveLength(1);
      expect(result.current.alerts[0].severity).toBe('warning');
      expect(result.current.alerts[0].metric).toBe('gpu_temperature');
    });

    it('should ignore messages without envelope format', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      // Try sending update directly without envelope - should be ignored
      const rawUpdate = createTestPerformanceUpdate({
        gpu: createTestGpuMetrics(),
      });

      act(() => {
        onMessageCallback?.(rawUpdate);
      });

      expect(result.current.current).toBeNull();
    });

    it('should ignore non-performance_update message types', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      const serviceStatusMessage = {
        type: 'service_status',
        data: {
          service: 'detector',
          status: 'healthy',
        },
      };

      const pingMessage = {
        type: 'ping',
        timestamp: '2025-12-23T10:00:00Z',
      };

      act(() => {
        onMessageCallback?.(serviceStatusMessage);
        onMessageCallback?.(pingMessage);
      });

      expect(result.current.current).toBeNull();
    });

    it('should ignore invalid messages', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      const invalidMessages = [
        { type: 'performance_update', data: {} }, // Missing timestamp
        { type: 'performance_update', data: null },
        { type: 'performance_update' }, // No data
        null,
        undefined,
        'string message',
        42,
        [],
      ];

      act(() => {
        invalidMessages.forEach((msg) => onMessageCallback?.(msg));
      });

      expect(result.current.current).toBeNull();
    });
  });

  describe('history buffers', () => {
    it('should add updates to the 5m buffer on every update', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      const update = createTestPerformanceUpdate({
        gpu: createTestGpuMetrics({ utilization: 50 }),
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update));
      });

      expect(result.current.history['5m']).toHaveLength(1);
    });

    it('should add updates to the 15m buffer every 3rd update', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      // Send 3 updates
      for (let i = 0; i < 3; i++) {
        const update = createTestPerformanceUpdate({
          timestamp: `2025-12-31T10:${String(i).padStart(2, '0')}:00Z`,
          gpu: createTestGpuMetrics({ utilization: 50 + i }),
        });

        act(() => {
          onMessageCallback?.(wrapInEnvelope(update));
        });
      }

      expect(result.current.history['5m']).toHaveLength(3);
      expect(result.current.history['15m']).toHaveLength(1); // Only every 3rd update
    });

    it('should add updates to the 60m buffer every 12th update', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      // Send 12 updates
      for (let i = 0; i < 12; i++) {
        const update = createTestPerformanceUpdate({
          timestamp: `2025-12-31T10:${String(i).padStart(2, '0')}:00Z`,
          gpu: createTestGpuMetrics({ utilization: 50 + i }),
        });

        act(() => {
          onMessageCallback?.(wrapInEnvelope(update));
        });
      }

      expect(result.current.history['5m']).toHaveLength(12);
      expect(result.current.history['15m']).toHaveLength(4); // Every 3rd update
      expect(result.current.history['60m']).toHaveLength(1); // Every 12th update
    });

    it('should enforce MAX_BUFFER_SIZE limit (60) for all buffers', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      // Send 70 updates to exceed the buffer size
      for (let i = 0; i < 70; i++) {
        const update = createTestPerformanceUpdate({
          timestamp: `2025-12-31T10:${String(i).padStart(2, '0')}:00Z`,
          gpu: createTestGpuMetrics({ utilization: i }),
        });

        act(() => {
          onMessageCallback?.(wrapInEnvelope(update));
        });
      }

      expect(result.current.history['5m']).toHaveLength(60);
      // Oldest entry should be the 11th update (index 10) since we remove oldest first
      expect(result.current.history['5m'][0].gpu?.utilization).toBe(10);
      // Newest entry should be the 70th update (index 69)
      expect(result.current.history['5m'][59].gpu?.utilization).toBe(69);
    });
  });

  describe('time range selection', () => {
    it('should default to 5m time range', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      expect(result.current.timeRange).toBe('5m');
    });

    it('should update time range when setTimeRange is called', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      act(() => {
        result.current.setTimeRange('15m');
      });

      expect(result.current.timeRange).toBe('15m');

      act(() => {
        result.current.setTimeRange('60m');
      });

      expect(result.current.timeRange).toBe('60m');

      act(() => {
        result.current.setTimeRange('5m');
      });

      expect(result.current.timeRange).toBe('5m');
    });
  });

  describe('connection status', () => {
    it('should reflect connection status from useWebSocket', () => {
      const { result, rerender } = renderHook(() => usePerformanceMetrics());

      expect(result.current.isConnected).toBe(true);

      // Update mock to return disconnected state
      mockWebSocketReturn.isConnected = false;
      rerender();

      expect(result.current.isConnected).toBe(false);
    });
  });

  describe('alert handling', () => {
    it('should handle multiple alerts', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      const alerts: PerformanceAlert[] = [
        createTestAlert({ severity: 'warning', metric: 'gpu_temperature' }),
        createTestAlert({ severity: 'critical', metric: 'vram_usage', message: 'VRAM critical' }),
      ];

      const update = createTestPerformanceUpdate({ alerts });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update));
      });

      expect(result.current.alerts).toHaveLength(2);
      expect(result.current.alerts[0].severity).toBe('warning');
      expect(result.current.alerts[1].severity).toBe('critical');
    });

    it('should update alerts when new updates arrive', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      // First update with one alert
      const update1 = createTestPerformanceUpdate({
        alerts: [createTestAlert({ message: 'Alert 1' })],
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update1));
      });

      expect(result.current.alerts).toHaveLength(1);
      expect(result.current.alerts[0].message).toBe('Alert 1');

      // Second update with different alerts
      const update2 = createTestPerformanceUpdate({
        alerts: [createTestAlert({ message: 'Alert 2' }), createTestAlert({ message: 'Alert 3' })],
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update2));
      });

      expect(result.current.alerts).toHaveLength(2);
      expect(result.current.alerts[0].message).toBe('Alert 2');
      expect(result.current.alerts[1].message).toBe('Alert 3');
    });

    it('should clear alerts when update has no alerts', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      // First update with alerts
      const update1 = createTestPerformanceUpdate({
        alerts: [createTestAlert()],
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update1));
      });

      expect(result.current.alerts).toHaveLength(1);

      // Second update with no alerts
      const update2 = createTestPerformanceUpdate({ alerts: [] });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update2));
      });

      expect(result.current.alerts).toHaveLength(0);
    });
  });

  describe('complete performance data', () => {
    it('should handle full performance update with all metrics', () => {
      const { result } = renderHook(() => usePerformanceMetrics());

      const update = createTestPerformanceUpdate({
        gpu: createTestGpuMetrics(),
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
          slots_active: 1,
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
          postgres: {
            status: 'healthy',
            connections_active: 5,
            connections_max: 30,
            cache_hit_ratio: 98.2,
            transactions_per_min: 1200,
          },
          redis: {
            status: 'healthy',
            connected_clients: 8,
            memory_mb: 1.5,
            hit_ratio: 99.5,
            blocked_clients: 0,
          },
        },
        host: createTestHostMetrics(),
        containers: [
          { name: 'backend', status: 'running', health: 'healthy' },
          { name: 'frontend', status: 'running', health: 'healthy' },
        ],
        alerts: [createTestAlert()],
      });

      act(() => {
        onMessageCallback?.(wrapInEnvelope(update));
      });

      expect(result.current.current).not.toBeNull();
      expect(result.current.current?.gpu?.name).toBe('NVIDIA RTX A5500');
      expect(result.current.current?.ai_models.rtdetr).toBeDefined();
      expect(result.current.current?.nemotron?.slots_active).toBe(1);
      expect(result.current.current?.inference?.rtdetr_latency_ms.avg).toBe(45);
      expect(result.current.current?.databases.postgres).toBeDefined();
      expect(result.current.current?.databases.redis).toBeDefined();
      expect(result.current.current?.host?.cpu_percent).toBe(12);
      expect(result.current.current?.containers).toHaveLength(2);
      expect(result.current.alerts).toHaveLength(1);
    });
  });
});

describe('utility functions', () => {
  describe('createEmptyPerformanceUpdate', () => {
    it('should create an empty performance update with defaults', () => {
      const update = createEmptyPerformanceUpdate();

      expect(update.timestamp).toBeDefined();
      expect(update.gpu).toBeNull();
      expect(update.ai_models).toEqual({});
      expect(update.nemotron).toBeNull();
      expect(update.inference).toBeNull();
      expect(update.databases).toEqual({});
      expect(update.host).toBeNull();
      expect(update.containers).toEqual([]);
      expect(update.alerts).toEqual([]);
    });
  });

  describe('addToCircularBuffer', () => {
    it('should add items to buffer below max size', () => {
      const buffer = [1, 2, 3];
      const result = addToCircularBuffer(buffer, 4, 10);

      expect(result).toEqual([1, 2, 3, 4]);
    });

    it('should remove oldest when buffer exceeds max size', () => {
      const buffer = [1, 2, 3, 4, 5];
      const result = addToCircularBuffer(buffer, 6, 5);

      expect(result).toEqual([2, 3, 4, 5, 6]);
    });

    it('should handle empty buffer', () => {
      const buffer: number[] = [];
      const result = addToCircularBuffer(buffer, 1, 5);

      expect(result).toEqual([1]);
    });

    it('should not mutate original buffer', () => {
      const buffer = [1, 2, 3];
      const result = addToCircularBuffer(buffer, 4, 5);

      expect(buffer).toEqual([1, 2, 3]);
      expect(result).toEqual([1, 2, 3, 4]);
    });
  });

  describe('isPerformanceUpdateMessage', () => {
    it('should return true for valid performance update message', () => {
      const message = {
        type: 'performance_update',
        data: {
          timestamp: '2025-12-31T10:00:00Z',
          gpu: null,
          ai_models: {},
          nemotron: null,
          inference: null,
          databases: {},
          host: null,
          containers: [],
          alerts: [],
        },
      };

      expect(isPerformanceUpdateMessage(message)).toBe(true);
    });

    it('should return false for wrong message type', () => {
      const message = {
        type: 'service_status',
        data: {
          timestamp: '2025-12-31T10:00:00Z',
        },
      };

      expect(isPerformanceUpdateMessage(message)).toBe(false);
    });

    it('should return false for missing data', () => {
      const message = {
        type: 'performance_update',
      };

      expect(isPerformanceUpdateMessage(message)).toBe(false);
    });

    it('should return false for null/undefined', () => {
      expect(isPerformanceUpdateMessage(null)).toBe(false);
      expect(isPerformanceUpdateMessage(undefined)).toBe(false);
    });

    it('should return false for non-object', () => {
      expect(isPerformanceUpdateMessage('string')).toBe(false);
      expect(isPerformanceUpdateMessage(123)).toBe(false);
      expect(isPerformanceUpdateMessage([])).toBe(false);
    });
  });
});

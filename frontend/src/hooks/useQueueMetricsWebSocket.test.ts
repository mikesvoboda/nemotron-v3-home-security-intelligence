/**
 * Tests for useQueueMetricsWebSocket hook
 *
 * NEM-3637: WebSocket handlers for queue.status and pipeline.throughput events
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useQueueMetricsWebSocket } from './useQueueMetricsWebSocket';

import type {
  QueueStatusPayload,
  PipelineThroughputPayload,
} from '../types/websocket-events';

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

describe('useQueueMetricsWebSocket', () => {
  const simulateMessage = (message: unknown): void => {
    act(() => {
      mockOnMessage(message);
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('initialization', () => {
    it('should return initial state with null queue status', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket());
      expect(result.current.queueStatus).toBeNull();
      expect(result.current.throughput).toBeNull();
      expect(result.current.isConnected).toBe(true);
      expect(result.current.lastUpdate).toBeNull();
    });

    it('should connect to WebSocket when enabled', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket({ enabled: true }));
      expect(result.current.isConnected).toBe(true);
    });
  });

  describe('queue.status events', () => {
    it('should handle queue status messages', () => {
      const onQueueStatus = vi.fn();
      const { result } = renderHook(() =>
        useQueueMetricsWebSocket({ onQueueStatus })
      );

      const payload: QueueStatusPayload = {
        queues: [
          { name: 'detection', depth: 5, workers: 2 },
          { name: 'analysis', depth: 3, workers: 1 },
        ],
        total_queued: 8,
        total_processing: 3,
        overall_status: 'healthy',
      };

      simulateMessage({
        type: 'queue.status',
        data: payload,
      });

      expect(result.current.queueStatus).toEqual(payload);
      expect(result.current.lastUpdate).not.toBeNull();
      expect(onQueueStatus).toHaveBeenCalledWith(payload);
    });

    it('should update queue history', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket());

      simulateMessage({
        type: 'queue.status',
        data: {
          queues: [{ name: 'detection', depth: 5, workers: 2 }],
          total_queued: 5,
          total_processing: 2,
          overall_status: 'healthy',
        },
      });

      simulateMessage({
        type: 'queue.status',
        data: {
          queues: [{ name: 'detection', depth: 10, workers: 2 }],
          total_queued: 10,
          total_processing: 3,
          overall_status: 'warning',
        },
      });

      expect(result.current.queueHistory).toHaveLength(2);
      // Newest first
      expect(result.current.queueHistory[0].total_queued).toBe(10);
    });
  });

  describe('pipeline.throughput events', () => {
    it('should handle throughput messages', () => {
      const onThroughput = vi.fn();
      const { result } = renderHook(() =>
        useQueueMetricsWebSocket({ onThroughput })
      );

      const payload: PipelineThroughputPayload = {
        detections_per_minute: 120.5,
        events_per_minute: 15.2,
        enrichments_per_minute: 12.0,
      };

      simulateMessage({
        type: 'pipeline.throughput',
        data: payload,
      });

      expect(result.current.throughput).toEqual(payload);
      expect(onThroughput).toHaveBeenCalledWith(payload);
    });

    it('should update throughput history', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket());

      simulateMessage({
        type: 'pipeline.throughput',
        data: {
          detections_per_minute: 100,
          events_per_minute: 10,
        },
      });

      simulateMessage({
        type: 'pipeline.throughput',
        data: {
          detections_per_minute: 150,
          events_per_minute: 15,
        },
      });

      expect(result.current.throughputHistory).toHaveLength(2);
      expect(result.current.throughputHistory[0].detections_per_minute).toBe(150);
    });
  });

  describe('derived values', () => {
    it('should compute total queue depth', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket());

      simulateMessage({
        type: 'queue.status',
        data: {
          queues: [
            { name: 'detection', depth: 5, workers: 2 },
            { name: 'analysis', depth: 3, workers: 1 },
          ],
          total_queued: 8,
          total_processing: 3,
          overall_status: 'healthy',
        },
      });

      expect(result.current.totalQueueDepth).toBe(8);
    });

    it('should compute total workers', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket());

      simulateMessage({
        type: 'queue.status',
        data: {
          queues: [
            { name: 'detection', depth: 5, workers: 2 },
            { name: 'analysis', depth: 3, workers: 3 },
          ],
          total_queued: 8,
          total_processing: 3,
          total_workers: 5,
          overall_status: 'healthy',
        },
      });

      expect(result.current.totalWorkers).toBe(5);
    });

    it('should detect warning status', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket());

      simulateMessage({
        type: 'queue.status',
        data: {
          queues: [{ name: 'detection', depth: 50, workers: 2 }],
          total_queued: 50,
          total_processing: 5,
          overall_status: 'warning',
        },
      });

      expect(result.current.isWarning).toBe(true);
      expect(result.current.isCritical).toBe(false);
    });

    it('should detect critical status', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket());

      simulateMessage({
        type: 'queue.status',
        data: {
          queues: [{ name: 'detection', depth: 100, workers: 2 }],
          total_queued: 100,
          total_processing: 10,
          overall_status: 'critical',
        },
      });

      expect(result.current.isCritical).toBe(true);
    });
  });

  describe('getQueueByName', () => {
    it('should return queue info by name', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket());

      simulateMessage({
        type: 'queue.status',
        data: {
          queues: [
            { name: 'detection', depth: 5, workers: 2 },
            { name: 'analysis', depth: 3, workers: 1 },
          ],
          total_queued: 8,
          total_processing: 3,
          overall_status: 'healthy',
        },
      });

      const queue = result.current.getQueueByName('detection');
      expect(queue).not.toBeNull();
      expect(queue?.depth).toBe(5);
      expect(queue?.workers).toBe(2);
    });

    it('should return undefined for unknown queue', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket());

      simulateMessage({
        type: 'queue.status',
        data: {
          queues: [{ name: 'detection', depth: 5, workers: 2 }],
          total_queued: 5,
          total_processing: 2,
          overall_status: 'healthy',
        },
      });

      const queue = result.current.getQueueByName('unknown');
      expect(queue).toBeUndefined();
    });
  });

  describe('clearHistory', () => {
    it('should clear queue and throughput history', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket());

      simulateMessage({
        type: 'queue.status',
        data: {
          queues: [{ name: 'detection', depth: 5, workers: 2 }],
          total_queued: 5,
          total_processing: 2,
          overall_status: 'healthy',
        },
      });

      simulateMessage({
        type: 'pipeline.throughput',
        data: {
          detections_per_minute: 100,
          events_per_minute: 10,
        },
      });

      expect(result.current.queueHistory).toHaveLength(1);
      expect(result.current.throughputHistory).toHaveLength(1);

      act(() => {
        result.current.clearHistory();
      });

      expect(result.current.queueHistory).toHaveLength(0);
      expect(result.current.throughputHistory).toHaveLength(0);
      // Current values should be preserved
      expect(result.current.queueStatus).not.toBeNull();
      expect(result.current.throughput).not.toBeNull();
    });
  });

  describe('message filtering', () => {
    it('should ignore non-queue messages', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket());

      simulateMessage({ type: 'ping' });
      simulateMessage({ type: 'system_status', data: { health: 'healthy' } });
      simulateMessage({ type: 'event.created', data: { id: 1 } });

      expect(result.current.queueStatus).toBeNull();
      expect(result.current.throughput).toBeNull();
    });

    it('should ignore malformed messages', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket());

      simulateMessage(null);
      simulateMessage(undefined);
      simulateMessage({ type: 'queue.status' }); // missing data
      simulateMessage({ type: 'queue.status', data: null });

      expect(result.current.queueStatus).toBeNull();
    });
  });

  describe('history limit', () => {
    it('should respect maxHistory limit for queue status', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket({ maxHistory: 3 }));

      for (let i = 1; i <= 5; i++) {
        simulateMessage({
          type: 'queue.status',
          data: {
            queues: [{ name: 'detection', depth: i * 10, workers: 2 }],
            total_queued: i * 10,
            total_processing: i,
            overall_status: 'healthy',
          },
        });
      }

      expect(result.current.queueHistory).toHaveLength(3);
      expect(result.current.queueHistory[0].total_queued).toBe(50);
    });

    it('should respect maxHistory limit for throughput', () => {
      const { result } = renderHook(() => useQueueMetricsWebSocket({ maxHistory: 3 }));

      for (let i = 1; i <= 5; i++) {
        simulateMessage({
          type: 'pipeline.throughput',
          data: {
            detections_per_minute: i * 100,
            events_per_minute: i * 10,
          },
        });
      }

      expect(result.current.throughputHistory).toHaveLength(3);
      expect(result.current.throughputHistory[0].detections_per_minute).toBe(500);
    });
  });
});

/**
 * Tests for useGpuStatsWebSocket hook
 *
 * NEM-3169: WebSocket handlers for gpu.stats_updated events
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useGpuStatsWebSocket } from './useGpuStatsWebSocket';

import type { GpuStatsUpdatedPayload } from '../types/websocket-events';

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

describe('useGpuStatsWebSocket', () => {
  const simulateMessage = (message: unknown): void => {
    act(() => {
      mockOnMessage(message);
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('initialization', () => {
    it('should return initial state with null stats', () => {
      const { result } = renderHook(() => useGpuStatsWebSocket());
      expect(result.current.stats).toBeNull();
      expect(result.current.history).toEqual([]);
      expect(result.current.isConnected).toBe(true);
      expect(result.current.lastUpdate).toBeNull();
    });

    it('should connect to WebSocket when enabled', () => {
      const { result } = renderHook(() =>
        useGpuStatsWebSocket({ enabled: true })
      );
      expect(result.current.isConnected).toBe(true);
    });
  });

  describe('gpu.stats_updated events', () => {
    it('should handle gpu stats updated messages', () => {
      const onStatsUpdate = vi.fn();
      const { result } = renderHook(() =>
        useGpuStatsWebSocket({ onStatsUpdate })
      );

      const stats: GpuStatsUpdatedPayload = {
        utilization: 75,
        memory_used: 4000000000, // 4GB
        memory_total: 8000000000, // 8GB
        temperature: 65,
        inference_fps: 30,
      };

      simulateMessage({
        type: 'gpu.stats_updated',
        data: stats,
      });

      expect(result.current.stats).toEqual(stats);
      expect(result.current.history).toHaveLength(1);
      expect(result.current.lastUpdate).not.toBeNull();
      expect(onStatsUpdate).toHaveBeenCalledWith(stats);
    });

    it('should accumulate history', () => {
      const { result } = renderHook(() => useGpuStatsWebSocket());

      const stats1: GpuStatsUpdatedPayload = {
        utilization: 50,
        memory_used: 3000000000,
        memory_total: 8000000000,
        temperature: 60,
        inference_fps: 25,
      };

      const stats2: GpuStatsUpdatedPayload = {
        utilization: 75,
        memory_used: 4000000000,
        memory_total: 8000000000,
        temperature: 65,
        inference_fps: 30,
      };

      simulateMessage({ type: 'gpu.stats_updated', data: stats1 });
      simulateMessage({ type: 'gpu.stats_updated', data: stats2 });

      expect(result.current.history).toHaveLength(2);
      // Newest first
      expect(result.current.history[0].utilization).toBe(75);
      expect(result.current.history[1].utilization).toBe(50);
    });

    it('should respect maxHistory limit', () => {
      const { result } = renderHook(() =>
        useGpuStatsWebSocket({ maxHistory: 3 })
      );

      for (let i = 1; i <= 5; i++) {
        simulateMessage({
          type: 'gpu.stats_updated',
          data: {
            utilization: i * 10,
            memory_used: null,
            memory_total: null,
            temperature: null,
            inference_fps: null,
          },
        });
      }

      expect(result.current.history).toHaveLength(3);
      // Newest first
      expect(result.current.history[0].utilization).toBe(50);
      expect(result.current.history[1].utilization).toBe(40);
      expect(result.current.history[2].utilization).toBe(30);
    });
  });

  describe('derived stats', () => {
    it('should compute memory usage percentage', () => {
      const { result } = renderHook(() => useGpuStatsWebSocket());

      simulateMessage({
        type: 'gpu.stats_updated',
        data: {
          utilization: 75,
          memory_used: 4000000000, // 4GB
          memory_total: 8000000000, // 8GB
          temperature: 65,
          inference_fps: 30,
        },
      });

      expect(result.current.memoryUsagePercent).toBe(50);
    });

    it('should return null for memory percentage when data is missing', () => {
      const { result } = renderHook(() => useGpuStatsWebSocket());

      simulateMessage({
        type: 'gpu.stats_updated',
        data: {
          utilization: 75,
          memory_used: null,
          memory_total: null,
          temperature: null,
          inference_fps: null,
        },
      });

      expect(result.current.memoryUsagePercent).toBeNull();
    });

    it('should detect high utilization', () => {
      const { result } = renderHook(() =>
        useGpuStatsWebSocket({ highUtilizationThreshold: 80 })
      );

      simulateMessage({
        type: 'gpu.stats_updated',
        data: {
          utilization: 75,
          memory_used: null,
          memory_total: null,
          temperature: null,
          inference_fps: null,
        },
      });

      expect(result.current.isHighUtilization).toBe(false);

      simulateMessage({
        type: 'gpu.stats_updated',
        data: {
          utilization: 85,
          memory_used: null,
          memory_total: null,
          temperature: null,
          inference_fps: null,
        },
      });

      expect(result.current.isHighUtilization).toBe(true);
    });

    it('should detect high temperature', () => {
      const { result } = renderHook(() =>
        useGpuStatsWebSocket({ highTemperatureThreshold: 80 })
      );

      simulateMessage({
        type: 'gpu.stats_updated',
        data: {
          utilization: 50,
          memory_used: null,
          memory_total: null,
          temperature: 75,
          inference_fps: null,
        },
      });

      expect(result.current.isHighTemperature).toBe(false);

      simulateMessage({
        type: 'gpu.stats_updated',
        data: {
          utilization: 50,
          memory_used: null,
          memory_total: null,
          temperature: 85,
          inference_fps: null,
        },
      });

      expect(result.current.isHighTemperature).toBe(true);
    });
  });

  describe('clearHistory', () => {
    it('should clear history while keeping latest stats', () => {
      const { result } = renderHook(() => useGpuStatsWebSocket());

      simulateMessage({
        type: 'gpu.stats_updated',
        data: {
          utilization: 50,
          memory_used: null,
          memory_total: null,
          temperature: null,
          inference_fps: null,
        },
      });

      simulateMessage({
        type: 'gpu.stats_updated',
        data: {
          utilization: 75,
          memory_used: null,
          memory_total: null,
          temperature: null,
          inference_fps: null,
        },
      });

      expect(result.current.history).toHaveLength(2);

      act(() => {
        result.current.clearHistory();
      });

      expect(result.current.history).toHaveLength(0);
      expect(result.current.stats).not.toBeNull();
      expect(result.current.stats?.utilization).toBe(75);
    });
  });

  describe('message filtering', () => {
    it('should ignore non-gpu messages', () => {
      const { result } = renderHook(() => useGpuStatsWebSocket());

      simulateMessage({ type: 'ping' });
      simulateMessage({ type: 'system_status', data: { health: 'healthy' } });
      simulateMessage({ type: 'service.status_changed', data: { service: 'test' } });

      expect(result.current.stats).toBeNull();
      expect(result.current.history).toEqual([]);
    });

    it('should ignore malformed messages', () => {
      const { result } = renderHook(() => useGpuStatsWebSocket());

      simulateMessage(null);
      simulateMessage(undefined);
      simulateMessage({ type: 'gpu.stats_updated' }); // missing data
      simulateMessage({ type: 'gpu.stats_updated', data: null });

      expect(result.current.stats).toBeNull();
    });
  });
});

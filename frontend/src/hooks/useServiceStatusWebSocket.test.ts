/**
 * Tests for useServiceStatusWebSocket hook
 *
 * NEM-3169: WebSocket handlers for service.status_changed events
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useServiceStatusWebSocket } from './useServiceStatusWebSocket';

import type { ServiceStatusChangedPayload } from '../types/websocket-events';

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

describe('useServiceStatusWebSocket', () => {
  const simulateMessage = (message: unknown): void => {
    act(() => {
      mockOnMessage(message);
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('initialization', () => {
    it('should return initial state with empty services', () => {
      const { result } = renderHook(() => useServiceStatusWebSocket());
      expect(result.current.services).toEqual({});
      expect(result.current.latestChange).toBeNull();
      expect(result.current.isConnected).toBe(true);
      expect(result.current.hasUnhealthyServices).toBe(false);
    });

    it('should connect to WebSocket when enabled', () => {
      const { result } = renderHook(() =>
        useServiceStatusWebSocket({ enabled: true })
      );
      expect(result.current.isConnected).toBe(true);
    });
  });

  describe('service.status_changed events', () => {
    it('should handle service status changed messages', () => {
      const onStatusChange = vi.fn();
      const { result } = renderHook(() =>
        useServiceStatusWebSocket({ onStatusChange })
      );

      const statusChange: ServiceStatusChangedPayload = {
        service: 'rtdetr',
        status: 'healthy',
        previous_status: 'unhealthy',
        message: 'Service recovered',
      };

      simulateMessage({
        type: 'service.status_changed',
        data: statusChange,
      });

      expect(result.current.services).toHaveProperty('rtdetr');
      expect(result.current.services.rtdetr).toEqual({
        service: 'rtdetr',
        status: 'healthy',
        previous_status: 'unhealthy',
        message: 'Service recovered',
        updatedAt: expect.any(String),
      });
      expect(result.current.latestChange).toMatchObject({
        service: 'rtdetr',
        status: 'healthy',
      });
      expect(onStatusChange).toHaveBeenCalledWith(statusChange);
    });

    it('should track multiple services', () => {
      const { result } = renderHook(() => useServiceStatusWebSocket());

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'rtdetr',
          status: 'healthy',
        },
      });

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'nemotron',
          status: 'unhealthy',
          message: 'GPU out of memory',
        },
      });

      expect(Object.keys(result.current.services)).toHaveLength(2);
      expect(result.current.services.rtdetr.status).toBe('healthy');
      expect(result.current.services.nemotron.status).toBe('unhealthy');
    });

    it('should update existing service status', () => {
      const { result } = renderHook(() => useServiceStatusWebSocket());

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'rtdetr',
          status: 'unhealthy',
          message: 'Service down',
        },
      });

      expect(result.current.services.rtdetr.status).toBe('unhealthy');

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'rtdetr',
          status: 'healthy',
          previous_status: 'unhealthy',
          message: 'Service recovered',
        },
      });

      expect(result.current.services.rtdetr.status).toBe('healthy');
      expect(result.current.services.rtdetr.previous_status).toBe('unhealthy');
    });

    it('should detect unhealthy services', () => {
      const { result } = renderHook(() => useServiceStatusWebSocket());

      expect(result.current.hasUnhealthyServices).toBe(false);

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'rtdetr',
          status: 'unhealthy',
        },
      });

      expect(result.current.hasUnhealthyServices).toBe(true);

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'rtdetr',
          status: 'healthy',
        },
      });

      expect(result.current.hasUnhealthyServices).toBe(false);
    });

    it('should filter by service when specified', () => {
      const onStatusChange = vi.fn();
      const { result } = renderHook(() =>
        useServiceStatusWebSocket({
          filterService: 'rtdetr',
          onStatusChange,
        })
      );

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'rtdetr',
          status: 'healthy',
        },
      });

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'nemotron',
          status: 'unhealthy',
        },
      });

      expect(Object.keys(result.current.services)).toHaveLength(1);
      expect(result.current.services).toHaveProperty('rtdetr');
      expect(result.current.services).not.toHaveProperty('nemotron');
      expect(onStatusChange).toHaveBeenCalledTimes(1);
    });
  });

  describe('helper functions', () => {
    it('getServiceStatus should return service status', () => {
      const { result } = renderHook(() => useServiceStatusWebSocket());

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'rtdetr',
          status: 'healthy',
        },
      });

      expect(result.current.getServiceStatus('rtdetr')).toBe('healthy');
      expect(result.current.getServiceStatus('unknown')).toBeUndefined();
    });

    it('isServiceHealthy should return correct health status', () => {
      const { result } = renderHook(() => useServiceStatusWebSocket());

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'rtdetr',
          status: 'healthy',
        },
      });

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'nemotron',
          status: 'unhealthy',
        },
      });

      expect(result.current.isServiceHealthy('rtdetr')).toBe(true);
      expect(result.current.isServiceHealthy('nemotron')).toBe(false);
      expect(result.current.isServiceHealthy('unknown')).toBe(false);
    });

    it('getUnhealthyServices should return list of unhealthy services', () => {
      const { result } = renderHook(() => useServiceStatusWebSocket());

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'rtdetr',
          status: 'healthy',
        },
      });

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'nemotron',
          status: 'unhealthy',
        },
      });

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'vllm',
          status: 'failed',
        },
      });

      const unhealthyServices = result.current.getUnhealthyServices();
      expect(unhealthyServices).toHaveLength(2);
      expect(unhealthyServices.map((s) => s.service)).toContain('nemotron');
      expect(unhealthyServices.map((s) => s.service)).toContain('vllm');
    });
  });

  describe('clearServices', () => {
    it('should clear all service status', () => {
      const { result } = renderHook(() => useServiceStatusWebSocket());

      simulateMessage({
        type: 'service.status_changed',
        data: {
          service: 'rtdetr',
          status: 'healthy',
        },
      });

      expect(Object.keys(result.current.services)).toHaveLength(1);

      act(() => {
        result.current.clearServices();
      });

      expect(result.current.services).toEqual({});
      expect(result.current.latestChange).toBeNull();
    });
  });

  describe('message filtering', () => {
    it('should ignore non-service-status messages', () => {
      const { result } = renderHook(() => useServiceStatusWebSocket());

      simulateMessage({ type: 'ping' });
      simulateMessage({ type: 'event', data: { id: 1 } });
      simulateMessage({ type: 'system_status', data: { health: 'healthy' } });

      expect(result.current.services).toEqual({});
    });

    it('should ignore malformed messages', () => {
      const { result } = renderHook(() => useServiceStatusWebSocket());

      simulateMessage(null);
      simulateMessage(undefined);
      simulateMessage({ type: 'service.status_changed' }); // missing data
      simulateMessage({ type: 'service.status_changed', data: {} }); // missing service

      expect(result.current.services).toEqual({});
    });
  });
});

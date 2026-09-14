/**
 * Tests for useSystemHealthWebSocket hook
 *
 * NEM-3169: WebSocket handlers for system.health_changed events
 */

import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useSystemHealthWebSocket } from './useSystemHealthWebSocket';

import type { SystemHealthChangedPayload } from '../types/websocket-events';

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

describe('useSystemHealthWebSocket', () => {
  const simulateMessage = (message: unknown): void => {
    act(() => {
      mockOnMessage(message);
    });
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('initialization', () => {
    it('should return initial state with unknown health', () => {
      const { result } = renderHook(() => useSystemHealthWebSocket());
      expect(result.current.health).toBeNull();
      expect(result.current.previousHealth).toBeNull();
      expect(result.current.components).toEqual({});
      expect(result.current.isConnected).toBe(true);
      expect(result.current.isHealthy).toBe(false);
      expect(result.current.isDegraded).toBe(false);
      expect(result.current.isUnhealthy).toBe(false);
    });

    it('should connect to WebSocket when enabled', () => {
      const { result } = renderHook(() => useSystemHealthWebSocket({ enabled: true }));
      expect(result.current.isConnected).toBe(true);
    });
  });

  describe('system.health_changed events', () => {
    it('should handle system health changed messages', () => {
      const onHealthChange = vi.fn();
      const { result } = renderHook(() => useSystemHealthWebSocket({ onHealthChange }));

      const healthChange: SystemHealthChangedPayload = {
        health: 'healthy',
        previous_health: 'degraded',
        components: {
          database: 'healthy',
          redis: 'healthy',
          ai_pipeline: 'healthy',
        },
      };

      simulateMessage({
        type: 'system.health_changed',
        data: healthChange,
      });

      expect(result.current.health).toBe('healthy');
      expect(result.current.previousHealth).toBe('degraded');
      expect(result.current.components).toEqual({
        database: 'healthy',
        redis: 'healthy',
        ai_pipeline: 'healthy',
      });
      expect(onHealthChange).toHaveBeenCalledWith(healthChange);
    });

    it('should track health state transitions', () => {
      const { result } = renderHook(() => useSystemHealthWebSocket());

      // Transition to degraded
      simulateMessage({
        type: 'system.health_changed',
        data: {
          health: 'degraded',
          previous_health: 'healthy',
          components: { ai_pipeline: 'degraded' },
        },
      });

      expect(result.current.health).toBe('degraded');
      expect(result.current.previousHealth).toBe('healthy');
      expect(result.current.isDegraded).toBe(true);
      expect(result.current.isHealthy).toBe(false);

      // Transition to unhealthy
      simulateMessage({
        type: 'system.health_changed',
        data: {
          health: 'unhealthy',
          previous_health: 'degraded',
          components: { ai_pipeline: 'unhealthy', database: 'unhealthy' },
        },
      });

      expect(result.current.health).toBe('unhealthy');
      expect(result.current.previousHealth).toBe('degraded');
      expect(result.current.isUnhealthy).toBe(true);
      expect(result.current.isDegraded).toBe(false);

      // Recover to healthy
      simulateMessage({
        type: 'system.health_changed',
        data: {
          health: 'healthy',
          previous_health: 'unhealthy',
          components: { ai_pipeline: 'healthy', database: 'healthy' },
        },
      });

      expect(result.current.health).toBe('healthy');
      expect(result.current.previousHealth).toBe('unhealthy');
      expect(result.current.isHealthy).toBe(true);
      expect(result.current.isUnhealthy).toBe(false);
    });

    it('should maintain transition history', () => {
      const { result } = renderHook(() => useSystemHealthWebSocket({ maxHistory: 3 }));

      simulateMessage({
        type: 'system.health_changed',
        data: {
          health: 'degraded',
          previous_health: 'healthy',
          components: {},
        },
      });

      simulateMessage({
        type: 'system.health_changed',
        data: {
          health: 'unhealthy',
          previous_health: 'degraded',
          components: {},
        },
      });

      simulateMessage({
        type: 'system.health_changed',
        data: {
          health: 'healthy',
          previous_health: 'unhealthy',
          components: {},
        },
      });

      simulateMessage({
        type: 'system.health_changed',
        data: {
          health: 'degraded',
          previous_health: 'healthy',
          components: {},
        },
      });

      expect(result.current.history).toHaveLength(3);
      // Newest first
      expect(result.current.history[0].health).toBe('degraded');
      expect(result.current.history[1].health).toBe('healthy');
      expect(result.current.history[2].health).toBe('unhealthy');
    });
  });

  describe('helper functions', () => {
    it('getComponentHealth should return component health', () => {
      const { result } = renderHook(() => useSystemHealthWebSocket());

      simulateMessage({
        type: 'system.health_changed',
        data: {
          health: 'degraded',
          previous_health: 'healthy',
          components: {
            database: 'healthy',
            redis: 'degraded',
            ai_pipeline: 'unhealthy',
          },
        },
      });

      expect(result.current.getComponentHealth('database')).toBe('healthy');
      expect(result.current.getComponentHealth('redis')).toBe('degraded');
      expect(result.current.getComponentHealth('ai_pipeline')).toBe('unhealthy');
      expect(result.current.getComponentHealth('unknown')).toBeUndefined();
    });

    it('isComponentHealthy should check component health', () => {
      const { result } = renderHook(() => useSystemHealthWebSocket());

      simulateMessage({
        type: 'system.health_changed',
        data: {
          health: 'degraded',
          previous_health: 'healthy',
          components: {
            database: 'healthy',
            redis: 'degraded',
          },
        },
      });

      expect(result.current.isComponentHealthy('database')).toBe(true);
      expect(result.current.isComponentHealthy('redis')).toBe(false);
      expect(result.current.isComponentHealthy('unknown')).toBe(false);
    });

    it('getUnhealthyComponents should return list of unhealthy components', () => {
      const { result } = renderHook(() => useSystemHealthWebSocket());

      simulateMessage({
        type: 'system.health_changed',
        data: {
          health: 'unhealthy',
          previous_health: 'degraded',
          components: {
            database: 'healthy',
            redis: 'degraded',
            ai_pipeline: 'unhealthy',
            metrics: 'unhealthy',
          },
        },
      });

      const unhealthy = result.current.getUnhealthyComponents();
      expect(unhealthy).toHaveLength(3);
      expect(unhealthy).toContain('redis');
      expect(unhealthy).toContain('ai_pipeline');
      expect(unhealthy).toContain('metrics');
    });
  });

  describe('clearHistory', () => {
    it('should clear history while keeping current state', () => {
      const { result } = renderHook(() => useSystemHealthWebSocket());

      simulateMessage({
        type: 'system.health_changed',
        data: {
          health: 'degraded',
          previous_health: 'healthy',
          components: { test: 'degraded' },
        },
      });

      simulateMessage({
        type: 'system.health_changed',
        data: {
          health: 'healthy',
          previous_health: 'degraded',
          components: { test: 'healthy' },
        },
      });

      expect(result.current.history).toHaveLength(2);

      act(() => {
        result.current.clearHistory();
      });

      expect(result.current.history).toHaveLength(0);
      expect(result.current.health).toBe('healthy');
      expect(result.current.components).toEqual({ test: 'healthy' });
    });
  });

  describe('message filtering', () => {
    it('should ignore non-health messages', () => {
      const { result } = renderHook(() => useSystemHealthWebSocket());

      simulateMessage({ type: 'ping' });
      simulateMessage({ type: 'system_status', data: { health: 'healthy' } });
      simulateMessage({ type: 'service.status_changed', data: { service: 'test' } });

      expect(result.current.health).toBeNull();
      expect(result.current.history).toEqual([]);
    });

    it('should ignore malformed messages', () => {
      const { result } = renderHook(() => useSystemHealthWebSocket());

      simulateMessage(null);
      simulateMessage(undefined);
      simulateMessage({ type: 'system.health_changed' }); // missing data
      simulateMessage({ type: 'system.health_changed', data: {} }); // missing health field

      expect(result.current.health).toBeNull();
    });
  });
});

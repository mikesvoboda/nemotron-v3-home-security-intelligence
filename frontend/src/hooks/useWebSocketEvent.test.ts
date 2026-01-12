/**
 * Tests for useWebSocketEvent hook
 *
 * Tests the type-safe WebSocket event subscription functionality
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

import { useWebSocketEvent, useWebSocketEvents } from './useWebSocketEvent';
import * as webSocketManagerModule from './webSocketManager';
import { WSEventType } from '../types/websocket-events';

import type { ConnectionConfig, TypedSubscriberOptions } from './webSocketManager';
import type { AlertCreatedPayload, JobCompletedPayload, WebSocketEventKey } from '../types/websocket-events';

// Mock the webSocketManager module
vi.mock('./webSocketManager', async () => {
  const actual = await vi.importActual('./webSocketManager');
  return {
    ...actual,
    createTypedSubscription: vi.fn(),
  };
});

// Mock the logger
vi.mock('../services/logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

// Define a simple mock subscription interface
interface MockSubscription {
  unsubscribe: ReturnType<typeof vi.fn>;
  emitter: Record<string, never>;
  on: ReturnType<typeof vi.fn>;
  off: ReturnType<typeof vi.fn>;
  once: ReturnType<typeof vi.fn>;
  send: ReturnType<typeof vi.fn>;
  getState: ReturnType<typeof vi.fn>;
}

describe('useWebSocketEvent', () => {
  let mockSubscription: MockSubscription;
  let mockEventHandlers: Map<string, Array<(data: unknown) => void>>;
  let lifecycleCallbacks: TypedSubscriberOptions;

  beforeEach(() => {
    mockEventHandlers = new Map();

    mockSubscription = {
      unsubscribe: vi.fn(),
      emitter: {} as Record<string, never>,
      on: vi.fn((event: WebSocketEventKey, handler: (data: unknown) => void) => {
        const handlers = mockEventHandlers.get(event) || [];
        handlers.push(handler);
        mockEventHandlers.set(event, handlers);
        return () => {
          const currentHandlers = mockEventHandlers.get(event) || [];
          const index = currentHandlers.indexOf(handler);
          if (index > -1) {
            currentHandlers.splice(index, 1);
            mockEventHandlers.set(event, currentHandlers);
          }
        };
      }),
      off: vi.fn(),
      once: vi.fn(),
      send: vi.fn().mockReturnValue(true),
      getState: vi.fn().mockReturnValue({
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
      }),
    };

    vi.mocked(webSocketManagerModule.createTypedSubscription).mockImplementation(
      (_url: string, _config: ConnectionConfig, options: TypedSubscriberOptions = {}) => {
        lifecycleCallbacks = options;
        // Simulate immediate connection
        setTimeout(() => {
          options.onOpen?.();
        }, 0);
        // Return the mock subscription cast to the expected type
        return mockSubscription as unknown as webSocketManagerModule.TypedSubscription;
      }
    );
  });

  afterEach(() => {
    vi.clearAllMocks();
    mockEventHandlers.clear();
  });

  describe('single event subscription', () => {
    it('should subscribe to specified event type', async () => {
      const handler = vi.fn();

      renderHook(() =>
        useWebSocketEvent(WSEventType.ALERT_CREATED, handler)
      );

      await waitFor(() => {
        expect(mockSubscription.on).toHaveBeenCalledWith(
          'alert.created',
          expect.any(Function)
        );
      });
    });

    it('should call handler when event is received', async () => {
      const handler = vi.fn();
      const testPayload: AlertCreatedPayload = {
        alert_id: 123,
        event_id: 456,
        severity: 'critical',
        message: 'Test alert',
        created_at: '2026-01-12T00:00:00Z',
      };

      renderHook(() =>
        useWebSocketEvent(WSEventType.ALERT_CREATED, handler)
      );

      // Wait for subscription to be set up
      await waitFor(() => {
        expect(mockEventHandlers.has('alert.created')).toBe(true);
      });

      // Simulate receiving an event
      act(() => {
        const handlers = mockEventHandlers.get('alert.created') || [];
        handlers.forEach((h) => h(testPayload));
      });

      expect(handler).toHaveBeenCalledWith(testPayload);
    });

    it('should return connection state', () => {
      const handler = vi.fn();

      const { result } = renderHook(() =>
        useWebSocketEvent(WSEventType.JOB_COMPLETED, handler)
      );

      // Initially not connected
      expect(result.current.isConnected).toBe(false);

      // Simulate connection
      act(() => {
        lifecycleCallbacks.onOpen?.();
      });

      expect(result.current.isConnected).toBe(true);
      expect(result.current.reconnectCount).toBe(0);
      expect(result.current.hasExhaustedRetries).toBe(false);
    });

    it('should handle disconnection', async () => {
      const handler = vi.fn();

      const { result } = renderHook(() =>
        useWebSocketEvent(WSEventType.CAMERA_ONLINE, handler)
      );

      // Connect
      act(() => {
        lifecycleCallbacks.onOpen?.();
      });

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Disconnect
      act(() => {
        lifecycleCallbacks.onClose?.();
      });

      await waitFor(() => {
        expect(result.current.isConnected).toBe(false);
      });
    });

    it('should handle max retries exhausted', () => {
      const handler = vi.fn();
      const onMaxRetriesExhausted = vi.fn();

      const { result } = renderHook(() =>
        useWebSocketEvent(WSEventType.SYSTEM_HEALTH_CHANGED, handler, {
          onMaxRetriesExhausted,
        })
      );

      act(() => {
        lifecycleCallbacks.onMaxRetriesExhausted?.();
      });

      expect(result.current.hasExhaustedRetries).toBe(true);
      expect(onMaxRetriesExhausted).toHaveBeenCalled();
    });

    it('should not subscribe when disabled', async () => {
      const handler = vi.fn();

      renderHook(() =>
        useWebSocketEvent(WSEventType.JOB_FAILED, handler, {
          enabled: false,
        })
      );

      // Wait a bit to ensure no subscription
      await new Promise((resolve) => setTimeout(resolve, 50));

      // createTypedSubscription should not have been called with enabled: false
      // (the hook should skip subscription entirely)
      expect(vi.mocked(webSocketManagerModule.createTypedSubscription)).not.toHaveBeenCalled();
    });

    it('should unsubscribe on unmount', async () => {
      const handler = vi.fn();

      const { unmount } = renderHook(() =>
        useWebSocketEvent(WSEventType.ALERT_CREATED, handler)
      );

      await waitFor(() => {
        expect(mockSubscription.on).toHaveBeenCalled();
      });

      unmount();

      expect(mockSubscription.unsubscribe).toHaveBeenCalled();
    });

    it('should call onConnected callback', () => {
      const handler = vi.fn();
      const onConnected = vi.fn();

      renderHook(() =>
        useWebSocketEvent(WSEventType.CAMERA_OFFLINE, handler, {
          onConnected,
        })
      );

      act(() => {
        lifecycleCallbacks.onOpen?.();
      });

      expect(onConnected).toHaveBeenCalled();
    });

    it('should call onDisconnected callback', () => {
      const handler = vi.fn();
      const onDisconnected = vi.fn();

      renderHook(() =>
        useWebSocketEvent(WSEventType.JOB_PROGRESS, handler, {
          onDisconnected,
        })
      );

      act(() => {
        lifecycleCallbacks.onClose?.();
      });

      expect(onDisconnected).toHaveBeenCalled();
    });

    it('should provide reconnect function', async () => {
      const handler = vi.fn();

      const { result } = renderHook(() =>
        useWebSocketEvent(WSEventType.ALERT_CREATED, handler)
      );

      await waitFor(() => {
        expect(mockSubscription.on).toHaveBeenCalled();
      });

      act(() => {
        result.current.reconnect();
      });

      // After reconnect, subscription should be unsubscribed
      expect(mockSubscription.unsubscribe).toHaveBeenCalled();
    });
  });

  describe('useWebSocketEvents (multiple event subscription)', () => {
    it('should subscribe to multiple event types', async () => {
      const alertHandler = vi.fn();
      const jobHandler = vi.fn();

      renderHook(() =>
        useWebSocketEvents({
          [WSEventType.ALERT_CREATED]: alertHandler,
          [WSEventType.JOB_COMPLETED]: jobHandler,
        })
      );

      await waitFor(() => {
        expect(mockSubscription.on).toHaveBeenCalledWith(
          'alert.created',
          expect.any(Function)
        );
        expect(mockSubscription.on).toHaveBeenCalledWith(
          'job.completed',
          expect.any(Function)
        );
      });
    });

    it('should route events to correct handlers', async () => {
      const alertHandler = vi.fn();
      const jobHandler = vi.fn();

      const alertPayload: AlertCreatedPayload = {
        alert_id: 1,
        event_id: 10,
        severity: 'critical',
        message: 'Critical alert',
        created_at: '2026-01-12T00:00:00Z',
      };

      const jobPayload: JobCompletedPayload = {
        job_id: 'job-123',
        completed_at: '2026-01-12T00:00:00Z',
      };

      renderHook(() =>
        useWebSocketEvents({
          [WSEventType.ALERT_CREATED]: alertHandler,
          [WSEventType.JOB_COMPLETED]: jobHandler,
        })
      );

      await waitFor(() => {
        expect(mockEventHandlers.has('alert.created')).toBe(true);
        expect(mockEventHandlers.has('job.completed')).toBe(true);
      });

      // Trigger alert event
      act(() => {
        const handlers = mockEventHandlers.get('alert.created') || [];
        handlers.forEach((h) => h(alertPayload));
      });

      // Trigger job event
      act(() => {
        const handlers = mockEventHandlers.get('job.completed') || [];
        handlers.forEach((h) => h(jobPayload));
      });

      expect(alertHandler).toHaveBeenCalledWith(alertPayload);
      expect(jobHandler).toHaveBeenCalledWith(jobPayload);
    });

    it('should share a single WebSocket connection', async () => {
      const handlers = {
        [WSEventType.ALERT_CREATED]: vi.fn(),
        [WSEventType.CAMERA_ONLINE]: vi.fn(),
        [WSEventType.JOB_STARTED]: vi.fn(),
      };

      renderHook(() => useWebSocketEvents(handlers));

      await waitFor(() => {
        // Should only create one subscription
        expect(webSocketManagerModule.createTypedSubscription).toHaveBeenCalledTimes(1);
      });
    });

    it('should return connection state for multiple subscriptions', () => {
      const { result } = renderHook(() =>
        useWebSocketEvents({
          [WSEventType.ALERT_CREATED]: vi.fn(),
          [WSEventType.JOB_COMPLETED]: vi.fn(),
        })
      );

      // Connect
      act(() => {
        lifecycleCallbacks.onOpen?.();
      });

      expect(result.current.isConnected).toBe(true);
    });

    it('should not subscribe when disabled', async () => {
      vi.mocked(webSocketManagerModule.createTypedSubscription).mockClear();

      renderHook(() =>
        useWebSocketEvents(
          {
            [WSEventType.ALERT_CREATED]: vi.fn(),
          },
          { enabled: false }
        )
      );

      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(webSocketManagerModule.createTypedSubscription).not.toHaveBeenCalled();
    });
  });

  describe('custom URL', () => {
    it('should use custom URL when provided', async () => {
      const customUrl = 'wss://custom.example.com/ws';
      const handler = vi.fn();

      renderHook(() =>
        useWebSocketEvent(WSEventType.ALERT_CREATED, handler, {
          url: customUrl,
        })
      );

      await waitFor(() => {
        expect(webSocketManagerModule.createTypedSubscription).toHaveBeenCalledWith(
          customUrl,
          expect.any(Object),
          expect.any(Object)
        );
      });
    });

    it('should compute default URL from window.location', async () => {
      const handler = vi.fn();

      renderHook(() =>
        useWebSocketEvent(WSEventType.CAMERA_ONLINE, handler)
      );

      await waitFor(() => {
        // Should use computed URL based on window.location
        expect(webSocketManagerModule.createTypedSubscription).toHaveBeenCalledWith(
          expect.stringMatching(/^wss?:\/\//),
          expect.any(Object),
          expect.any(Object)
        );
      });
    });
  });

  describe('connection configuration', () => {
    it('should merge custom config with defaults', async () => {
      const handler = vi.fn();

      renderHook(() =>
        useWebSocketEvent(WSEventType.JOB_PROGRESS, handler, {
          connectionConfig: {
            maxReconnectAttempts: 5,
            reconnectInterval: 2000,
          },
        })
      );

      await waitFor(() => {
        expect(webSocketManagerModule.createTypedSubscription).toHaveBeenCalledWith(
          expect.any(String),
          expect.objectContaining({
            maxReconnectAttempts: 5,
            reconnectInterval: 2000,
            // Defaults should still be present
            reconnect: true,
            connectionTimeout: 10000,
            autoRespondToHeartbeat: true,
          }),
          expect.any(Object)
        );
      });
    });
  });
});

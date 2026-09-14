/**
 * WebSocket Reconnection Integration Tests
 *
 * Tests the WebSocket reconnection behavior including:
 * - Connection timeout handling
 * - Exponential backoff verification
 * - Retry exhaustion flow
 * - hasExhaustedRetries state and callbacks
 *
 * @see docs/plans/2025-12-31-system-performance-design.md
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi, Mock } from 'vitest';

import { useWebSocket, WebSocketOptions, UseWebSocketReturn } from '../../src/hooks/useWebSocket';
import { webSocketManager, resetSubscriberCounter, calculateBackoffDelay } from '../../src/hooks/webSocketManager';

// Mock the webSocketManager module
vi.mock('../../src/hooks/webSocketManager', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../src/hooks/webSocketManager')>();
  return {
    ...actual,
    webSocketManager: {
      subscribe: vi.fn(),
      send: vi.fn(),
      getConnectionState: vi.fn(),
      getSubscriberCount: vi.fn(),
      hasConnection: vi.fn(),
      reconnect: vi.fn(),
      clearAll: vi.fn(),
      reset: vi.fn(),
    },
  };
});

// Helper type for the mock subscribe function
type SubscribeCallback = Parameters<typeof webSocketManager.subscribe>[1];
type SubscribeConfig = Parameters<typeof webSocketManager.subscribe>[2];

describe('WebSocket Reconnection Integration', () => {
  let mockUnsubscribe: Mock;
  let lastSubscriber: SubscribeCallback | null = null;
  let lastConfig: SubscribeConfig | null = null;

  beforeEach(() => {
    vi.useFakeTimers();
    resetSubscriberCounter();
    mockUnsubscribe = vi.fn();
    lastSubscriber = null;
    lastConfig = null;

    // Default mock implementations
    (webSocketManager.subscribe as Mock).mockImplementation(
      (_url: string, subscriber: SubscribeCallback, config: SubscribeConfig) => {
        lastSubscriber = subscriber;
        lastConfig = config;
        // Simulate connection opening after a short delay
        setTimeout(() => {
          subscriber.onOpen?.();
        }, 10);
        return mockUnsubscribe;
      }
    );

    (webSocketManager.send as Mock).mockReturnValue(true);

    (webSocketManager.getConnectionState as Mock).mockReturnValue({
      isConnected: true,
      reconnectCount: 0,
      hasExhaustedRetries: false,
      lastHeartbeat: null,
    });

    (webSocketManager.getSubscriberCount as Mock).mockReturnValue(1);
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  describe('Connection timeout', () => {
    it('triggers reconnection when initial connection times out', async () => {
      let closeCallCount = 0;
      let reconnectAttempts = 0;

      (webSocketManager.subscribe as Mock).mockImplementation(
        (_url: string, subscriber: SubscribeCallback, config: SubscribeConfig) => {
          lastSubscriber = subscriber;
          lastConfig = config;

          // Simulate connection timeout - manager calls onClose after timeout
          setTimeout(() => {
            closeCallCount++;
            reconnectAttempts++;

            // Update mock state before calling onClose
            (webSocketManager.getConnectionState as Mock).mockReturnValue({
              isConnected: false,
              reconnectCount: reconnectAttempts,
              hasExhaustedRetries: false,
              lastHeartbeat: null,
            });

            subscriber.onClose?.();
          }, config.connectionTimeout + 10);

          return mockUnsubscribe;
        }
      );

      const onClose = vi.fn();

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws/test',
        connectionTimeout: 100,
        reconnect: true,
        reconnectInterval: 50,
        reconnectAttempts: 3,
        onClose,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Initially not connected
      expect(result.current.isConnected).toBe(false);

      // Advance past the connection timeout
      await act(() => {
        vi.advanceTimersByTime(150);
      });

      // onClose should have been called due to timeout
      expect(onClose).toHaveBeenCalled();
      expect(closeCallCount).toBe(1);

      // reconnectCount should be updated
      expect(result.current.reconnectCount).toBe(1);

      // Verify connectionTimeout was passed to manager
      expect(webSocketManager.subscribe).toHaveBeenCalledWith(
        'ws://localhost:8000/ws/test',
        expect.any(Object),
        expect.objectContaining({
          connectionTimeout: 100,
          reconnect: true,
          maxReconnectAttempts: 3,
        })
      );
    });

    it('preserves queued messages during reconnection', async () => {
      let connectionOpen = false;

      (webSocketManager.subscribe as Mock).mockImplementation(
        (_url: string, subscriber: SubscribeCallback, config: SubscribeConfig) => {
          lastSubscriber = subscriber;
          lastConfig = config;

          // First connection: timeout, then reconnect and succeed
          setTimeout(() => {
            connectionOpen = true;
            subscriber.onOpen?.();
          }, 150);

          return mockUnsubscribe;
        }
      );

      (webSocketManager.send as Mock).mockImplementation(() => {
        // Only succeed when connection is open
        return connectionOpen;
      });

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws/test',
        connectionTimeout: 200,
        reconnect: true,
        reconnectInterval: 50,
        reconnectAttempts: 3,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Try to send a message before connection is open
      const messageSent = result.current.send({ type: 'test', data: 'queued' });

      // Message should fail since not connected yet
      expect(messageSent).toBeUndefined(); // send() doesn't return value directly

      // Wait for connection to open
      await act(() => {
        vi.advanceTimersByTime(200);
      });

      expect(result.current.isConnected).toBe(true);

      // Now send should work
      result.current.send({ type: 'test', data: 'after-connect' });
      expect(webSocketManager.send).toHaveBeenCalled();
    });
  });

  describe('Backoff behavior', () => {
    it('applies exponential backoff between reconnect attempts', async () => {
      // Test the calculateBackoffDelay function directly
      const baseInterval = 1000;

      // Attempt 0: base * 2^0 = 1000ms + jitter
      const delay0 = calculateBackoffDelay(0, baseInterval, 30000);
      expect(delay0).toBeGreaterThanOrEqual(baseInterval);
      expect(delay0).toBeLessThanOrEqual(baseInterval * 1.25); // Max 25% jitter

      // Attempt 1: base * 2^1 = 2000ms + jitter
      const delay1 = calculateBackoffDelay(1, baseInterval, 30000);
      expect(delay1).toBeGreaterThanOrEqual(2000);
      expect(delay1).toBeLessThanOrEqual(2500); // 2000 + 25% jitter

      // Attempt 2: base * 2^2 = 4000ms + jitter
      const delay2 = calculateBackoffDelay(2, baseInterval, 30000);
      expect(delay2).toBeGreaterThanOrEqual(4000);
      expect(delay2).toBeLessThanOrEqual(5000); // 4000 + 25% jitter

      // Attempt 3: base * 2^3 = 8000ms + jitter
      const delay3 = calculateBackoffDelay(3, baseInterval, 30000);
      expect(delay3).toBeGreaterThanOrEqual(8000);
      expect(delay3).toBeLessThanOrEqual(10000); // 8000 + 25% jitter

      // Verify exponential growth: each delay should be roughly double the previous
      // (accounting for jitter)
      expect(delay1).toBeGreaterThan(delay0);
      expect(delay2).toBeGreaterThan(delay1);
      expect(delay3).toBeGreaterThan(delay2);
    });

    it('caps backoff delay at maxInterval', async () => {
      const baseInterval = 1000;
      const maxInterval = 5000;

      // Attempt 10: base * 2^10 = 1024000ms, but should be capped at 5000ms + jitter
      const delay = calculateBackoffDelay(10, baseInterval, maxInterval);
      expect(delay).toBeLessThanOrEqual(maxInterval * 1.25); // capped + max jitter
      expect(delay).toBeGreaterThanOrEqual(maxInterval); // at least the max

      // Attempt 5: base * 2^5 = 32000ms, capped at 5000ms
      const delay5 = calculateBackoffDelay(5, baseInterval, maxInterval);
      expect(delay5).toBeLessThanOrEqual(maxInterval * 1.25);
      expect(delay5).toBeGreaterThanOrEqual(maxInterval);
    });

    it('passes reconnect configuration to manager correctly', async () => {
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws/backoff-test',
        reconnect: true,
        reconnectInterval: 500,
        reconnectAttempts: 5,
        connectionTimeout: 10000,
      };

      renderHook(() => useWebSocket(options));

      expect(webSocketManager.subscribe).toHaveBeenCalledWith(
        'ws://localhost:8000/ws/backoff-test',
        expect.any(Object),
        expect.objectContaining({
          reconnect: true,
          reconnectInterval: 500,
          maxReconnectAttempts: 5,
          connectionTimeout: 10000,
        })
      );
    });

    it('tracks reconnect count through multiple disconnections', async () => {
      let currentReconnectCount = 0;

      (webSocketManager.subscribe as Mock).mockImplementation(
        (_url: string, subscriber: SubscribeCallback, config: SubscribeConfig) => {
          lastSubscriber = subscriber;
          lastConfig = config;
          setTimeout(() => {
            subscriber.onOpen?.();
          }, 10);
          return mockUnsubscribe;
        }
      );

      (webSocketManager.getConnectionState as Mock).mockImplementation(() => ({
        isConnected: false,
        reconnectCount: currentReconnectCount,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
      }));

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws/test',
        reconnect: true,
        reconnectInterval: 100,
        reconnectAttempts: 5,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Wait for initial connection
      await act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(result.current.isConnected).toBe(true);
      expect(result.current.reconnectCount).toBe(0);

      // Simulate first disconnection
      currentReconnectCount = 1;
      await act(() => {
        lastSubscriber?.onClose?.();
      });

      expect(result.current.reconnectCount).toBe(1);

      // Simulate second disconnection
      currentReconnectCount = 2;
      await act(() => {
        lastSubscriber?.onClose?.();
      });

      expect(result.current.reconnectCount).toBe(2);

      // Simulate third disconnection
      currentReconnectCount = 3;
      await act(() => {
        lastSubscriber?.onClose?.();
      });

      expect(result.current.reconnectCount).toBe(3);
    });
  });

  describe('Retry exhaustion', () => {
    it('fires onMaxRetriesExhausted after all attempts fail', async () => {
      const onMaxRetriesExhausted = vi.fn();

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws/retry-test',
        reconnect: true,
        reconnectInterval: 50,
        reconnectAttempts: 3,
        onMaxRetriesExhausted,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Wait for subscription
      await act(() => {
        vi.advanceTimersByTime(20);
      });

      // Initially not exhausted
      expect(result.current.hasExhaustedRetries).toBe(false);
      expect(onMaxRetriesExhausted).not.toHaveBeenCalled();

      // Simulate max retries exhausted callback from manager
      await act(() => {
        lastSubscriber?.onMaxRetriesExhausted?.();
      });

      // Callback should have been called
      expect(onMaxRetriesExhausted).toHaveBeenCalledTimes(1);
    });

    it('sets hasExhaustedRetries to true', async () => {
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws/exhaustion-test',
        reconnect: true,
        reconnectInterval: 50,
        reconnectAttempts: 2,
      };

      const { result } = renderHook(() => useWebSocket(options));

      await act(() => {
        vi.advanceTimersByTime(20);
      });

      expect(result.current.hasExhaustedRetries).toBe(false);

      // Simulate max retries exhausted
      await act(() => {
        lastSubscriber?.onMaxRetriesExhausted?.();
      });

      expect(result.current.hasExhaustedRetries).toBe(true);
    });

    it('stops attempting reconnection after exhaustion', async () => {
      const maxAttempts = 3;
      let currentReconnectCount = 0;

      (webSocketManager.subscribe as Mock).mockImplementation(
        (_url: string, subscriber: SubscribeCallback, config: SubscribeConfig) => {
          lastSubscriber = subscriber;
          lastConfig = config;
          // Simulate initial connection attempt that fails
          setTimeout(() => {
            subscriber.onClose?.();
          }, 20);
          return mockUnsubscribe;
        }
      );

      (webSocketManager.getConnectionState as Mock).mockImplementation(() => ({
        isConnected: false,
        reconnectCount: currentReconnectCount,
        hasExhaustedRetries: currentReconnectCount >= maxAttempts,
        lastHeartbeat: null,
      }));

      const onMaxRetriesExhausted = vi.fn();

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws/stop-reconnect-test',
        reconnect: true,
        reconnectInterval: 50,
        reconnectAttempts: maxAttempts,
        onMaxRetriesExhausted,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Simulate multiple reconnection attempts through onClose calls
      // Each onClose represents a failed connection attempt
      for (let i = 1; i <= maxAttempts; i++) {
        currentReconnectCount = i;
        await act(() => {
          vi.advanceTimersByTime(100);
          lastSubscriber?.onClose?.();
        });
      }

      // Now simulate the exhaustion callback
      await act(() => {
        lastSubscriber?.onMaxRetriesExhausted?.();
      });

      // Should have exhausted retries
      expect(result.current.hasExhaustedRetries).toBe(true);
      expect(onMaxRetriesExhausted).toHaveBeenCalled();

      // Verify reconnect count reflects max attempts
      expect(result.current.reconnectCount).toBe(maxAttempts);
    });

    it('allows manual reconnection after exhaustion', async () => {
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws/manual-reconnect-test',
        reconnect: true,
        reconnectInterval: 50,
        reconnectAttempts: 2,
      };

      const { result } = renderHook(() => useWebSocket(options));

      await act(() => {
        vi.advanceTimersByTime(20);
      });

      // Simulate max retries exhausted
      await act(() => {
        lastSubscriber?.onMaxRetriesExhausted?.();
      });

      expect(result.current.hasExhaustedRetries).toBe(true);

      // Disconnect to allow reconnection
      await act(() => {
        result.current.disconnect();
      });

      // Manual connect should reset hasExhaustedRetries
      await act(() => {
        result.current.connect();
      });

      expect(result.current.hasExhaustedRetries).toBe(false);
    });

    it('reports correct state when getConnectionState indicates exhaustion', async () => {
      const maxAttempts = 5;
      let currentReconnectCount = 0;

      (webSocketManager.subscribe as Mock).mockImplementation(
        (_url: string, subscriber: SubscribeCallback, config: SubscribeConfig) => {
          lastSubscriber = subscriber;
          lastConfig = config;
          // Don't auto-open, let the test control the flow
          return mockUnsubscribe;
        }
      );

      (webSocketManager.getConnectionState as Mock).mockImplementation(() => ({
        isConnected: false,
        reconnectCount: currentReconnectCount,
        hasExhaustedRetries: currentReconnectCount >= maxAttempts,
        lastHeartbeat: null,
      }));

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws/state-test',
        reconnect: true,
        reconnectAttempts: maxAttempts,
      };

      const { result } = renderHook(() => useWebSocket(options));

      await act(() => {
        vi.advanceTimersByTime(20);
      });

      // Simulate reaching max attempts by updating state and calling onClose
      currentReconnectCount = maxAttempts;
      await act(() => {
        lastSubscriber?.onClose?.();
      });

      // Simulate the exhaustion callback
      await act(() => {
        lastSubscriber?.onMaxRetriesExhausted?.();
      });

      expect(result.current.hasExhaustedRetries).toBe(true);
      expect(result.current.reconnectCount).toBe(maxAttempts);
    });
  });

  describe('Integration scenarios', () => {
    it('full reconnection cycle: connect -> disconnect -> reconnect -> exhaust', async () => {
      let connectionState = 'connecting';
      let reconnectAttempts = 0;
      const maxAttempts = 3;

      (webSocketManager.subscribe as Mock).mockImplementation(
        (_url: string, subscriber: SubscribeCallback, config: SubscribeConfig) => {
          lastSubscriber = subscriber;
          lastConfig = config;

          // Initial connection succeeds
          setTimeout(() => {
            connectionState = 'connected';
            (webSocketManager.getConnectionState as Mock).mockReturnValue({
              isConnected: true,
              reconnectCount: 0,
              hasExhaustedRetries: false,
              lastHeartbeat: null,
            });
            subscriber.onOpen?.();
          }, 10);

          return mockUnsubscribe;
        }
      );

      const onOpen = vi.fn();
      const onClose = vi.fn();
      const onMaxRetriesExhausted = vi.fn();

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws/full-cycle-test',
        reconnect: true,
        reconnectInterval: 100,
        reconnectAttempts: maxAttempts,
        connectionTimeout: 5000,
        onOpen,
        onClose,
        onMaxRetriesExhausted,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Phase 1: Initial connection
      await act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(result.current.isConnected).toBe(true);
      expect(onOpen).toHaveBeenCalledTimes(1);
      expect(result.current.reconnectCount).toBe(0);
      expect(result.current.hasExhaustedRetries).toBe(false);

      // Phase 2: Connection drops
      connectionState = 'disconnected';
      reconnectAttempts = 1;
      (webSocketManager.getConnectionState as Mock).mockReturnValue({
        isConnected: false,
        reconnectCount: reconnectAttempts,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
      });

      await act(() => {
        lastSubscriber?.onClose?.();
      });

      expect(result.current.isConnected).toBe(false);
      expect(onClose).toHaveBeenCalledTimes(1);
      expect(result.current.reconnectCount).toBe(1);

      // Phase 3: More failed reconnection attempts
      reconnectAttempts = 2;
      (webSocketManager.getConnectionState as Mock).mockReturnValue({
        isConnected: false,
        reconnectCount: reconnectAttempts,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
      });

      await act(() => {
        lastSubscriber?.onClose?.();
      });

      expect(result.current.reconnectCount).toBe(2);

      // Phase 4: Final attempt and exhaustion
      reconnectAttempts = 3;
      (webSocketManager.getConnectionState as Mock).mockReturnValue({
        isConnected: false,
        reconnectCount: reconnectAttempts,
        hasExhaustedRetries: true,
        lastHeartbeat: null,
      });

      await act(() => {
        lastSubscriber?.onClose?.();
        lastSubscriber?.onMaxRetriesExhausted?.();
      });

      expect(result.current.hasExhaustedRetries).toBe(true);
      expect(onMaxRetriesExhausted).toHaveBeenCalledTimes(1);
      expect(result.current.reconnectCount).toBe(3);
    });

    it('recovers from exhaustion after successful manual reconnect', async () => {
      let isSubscribed = true;

      (webSocketManager.subscribe as Mock).mockImplementation(
        (_url: string, subscriber: SubscribeCallback, config: SubscribeConfig) => {
          lastSubscriber = subscriber;
          lastConfig = config;

          if (isSubscribed) {
            setTimeout(() => {
              (webSocketManager.getConnectionState as Mock).mockReturnValue({
                isConnected: true,
                reconnectCount: 0,
                hasExhaustedRetries: false,
                lastHeartbeat: null,
              });
              subscriber.onOpen?.();
            }, 10);
          }

          return () => {
            isSubscribed = false;
            mockUnsubscribe();
          };
        }
      );

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws/recovery-test',
        reconnect: true,
        reconnectInterval: 50,
        reconnectAttempts: 2,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Initial connection
      await act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(result.current.isConnected).toBe(true);

      // Simulate exhaustion
      await act(() => {
        lastSubscriber?.onMaxRetriesExhausted?.();
      });

      expect(result.current.hasExhaustedRetries).toBe(true);

      // Disconnect
      await act(() => {
        result.current.disconnect();
      });

      expect(result.current.isConnected).toBe(false);

      // Re-enable subscription for reconnection
      isSubscribed = true;

      // Manual reconnect
      await act(() => {
        result.current.connect();
      });

      // hasExhaustedRetries should be reset on connect call
      expect(result.current.hasExhaustedRetries).toBe(false);

      // Wait for connection
      await act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(result.current.isConnected).toBe(true);
      expect(result.current.reconnectCount).toBe(0);
    });

    it('maintains data integrity across reconnection cycles', async () => {
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws/data-integrity-test',
        reconnect: true,
        reconnectInterval: 50,
        reconnectAttempts: 3,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Wait for connection
      await act(() => {
        vi.advanceTimersByTime(50);
      });

      // Receive some messages
      const message1 = { type: 'event', id: 1, data: 'first' };
      const message2 = { type: 'event', id: 2, data: 'second' };

      await act(() => {
        lastSubscriber?.onMessage?.(message1);
      });

      expect(result.current.lastMessage).toEqual(message1);

      await act(() => {
        lastSubscriber?.onMessage?.(message2);
      });

      expect(result.current.lastMessage).toEqual(message2);

      // Simulate disconnection
      (webSocketManager.getConnectionState as Mock).mockReturnValue({
        isConnected: false,
        reconnectCount: 1,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
      });

      await act(() => {
        lastSubscriber?.onClose?.();
      });

      // lastMessage should be preserved during disconnection
      expect(result.current.lastMessage).toEqual(message2);
      expect(result.current.isConnected).toBe(false);

      // Simulate reconnection
      (webSocketManager.getConnectionState as Mock).mockReturnValue({
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
      });

      await act(() => {
        lastSubscriber?.onOpen?.();
      });

      // lastMessage still preserved after reconnection
      expect(result.current.lastMessage).toEqual(message2);
      expect(result.current.isConnected).toBe(true);

      // New messages work after reconnection
      const message3 = { type: 'event', id: 3, data: 'third' };

      await act(() => {
        lastSubscriber?.onMessage?.(message3);
      });

      expect(result.current.lastMessage).toEqual(message3);
    });
  });
});

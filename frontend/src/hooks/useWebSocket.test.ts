/* eslint-disable @typescript-eslint/unbound-method, @typescript-eslint/require-await -- Mock methods don't use `this` */
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi, Mock } from 'vitest';

import { useWebSocket, WebSocketOptions, calculateBackoffDelay } from './useWebSocket';
import { webSocketManager, resetSubscriberCounter } from './webSocketManager';

// Mock the webSocketManager module
vi.mock('./webSocketManager', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./webSocketManager')>();
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

describe('useWebSocket', () => {
  let mockUnsubscribe: Mock;
  let lastSubscriber: SubscribeCallback | null = null;

  beforeEach(() => {
    resetSubscriberCounter();
    mockUnsubscribe = vi.fn();
    lastSubscriber = null;

    // Default mock implementations
    (webSocketManager.subscribe as Mock).mockImplementation(
      (_url: string, subscriber: SubscribeCallback, _config: SubscribeConfig) => {
        lastSubscriber = subscriber;
        // Simulate connection opening
        setTimeout(() => {
          subscriber.onOpen?.();
        }, 0);
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
  });

  it('should connect to WebSocket on mount', async () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
    };

    const { result } = renderHook(() => useWebSocket(options));

    expect(result.current.isConnected).toBe(false);

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    expect(webSocketManager.subscribe).toHaveBeenCalledWith(
      'ws://localhost:8000/ws',
      expect.any(Object),
      expect.objectContaining({
        reconnect: true,
        reconnectInterval: 1000,
        // Default is now 15 for better backend restart resilience
        maxReconnectAttempts: 15,
        connectionTimeout: 10000,
        autoRespondToHeartbeat: true,
      })
    );
  });

  it('should disconnect on unmount', async () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
    };

    const { result, unmount } = renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    unmount();

    expect(mockUnsubscribe).toHaveBeenCalled();
  });

  it('should handle incoming messages', async () => {
    const onMessage = vi.fn();
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      onMessage,
    };

    const { result } = renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const testData = { type: 'test', message: 'Hello' };

    act(() => {
      lastSubscriber?.onMessage?.(testData);
    });

    expect(onMessage).toHaveBeenCalledWith(testData);
    expect(result.current.lastMessage).toEqual(testData);
  });

  it('should handle non-JSON messages', async () => {
    const onMessage = vi.fn();
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      onMessage,
    };

    const { result } = renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const rawMessage = 'plain text message';

    act(() => {
      lastSubscriber?.onMessage?.(rawMessage);
    });

    expect(onMessage).toHaveBeenCalledWith(rawMessage);
    expect(result.current.lastMessage).toBe(rawMessage);
  });

  it('should send messages when connected', async () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
    };

    const { result } = renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const testData = { type: 'test', message: 'Hello' };

    act(() => {
      result.current.send(testData);
    });

    expect(webSocketManager.send).toHaveBeenCalledWith('ws://localhost:8000/ws', testData);
  });

  it('should not send messages when disconnected', () => {
    (webSocketManager.send as Mock).mockReturnValue(false);

    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
    };

    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { result } = renderHook(() => useWebSocket(options));

    // Don't wait for connection
    const testData = { type: 'test', message: 'Hello' };

    act(() => {
      result.current.send(testData);
    });

    // Logger formats messages as: [${level}] ${component}: ${message}
    // and passes extra data as the second argument
    expect(consoleSpy).toHaveBeenCalledWith(
      '[WARNING] frontend: WebSocket is not connected. Message not sent',
      expect.objectContaining({
        component: 'useWebSocket',
        url: 'ws://localhost:8000/ws',
        data: testData,
      })
    );

    consoleSpy.mockRestore();
  });

  it('should call onOpen callback', async () => {
    const onOpen = vi.fn();
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      onOpen,
    };

    renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(onOpen).toHaveBeenCalled();
    });
  });

  it('should call onClose callback', async () => {
    const onClose = vi.fn();
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      onClose,
      reconnect: false,
    };

    const { result } = renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    act(() => {
      lastSubscriber?.onClose?.();
    });

    await waitFor(() => {
      expect(onClose).toHaveBeenCalled();
    });
  });

  it('should call onError callback', async () => {
    const onError = vi.fn();
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      onError,
    };

    renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(lastSubscriber).not.toBeNull();
    });

    const errorEvent = new Event('error');

    act(() => {
      lastSubscriber?.onError?.(errorEvent);
    });

    expect(onError).toHaveBeenCalledWith(errorEvent);
  });

  it('should update reconnectCount from manager state on close', async () => {
    (webSocketManager.getConnectionState as Mock).mockReturnValue({
      isConnected: false,
      reconnectCount: 2,
      hasExhaustedRetries: false,
      lastHeartbeat: null,
    });

    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      reconnect: true,
      reconnectInterval: 100,
      reconnectAttempts: 3,
    };

    const { result } = renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    act(() => {
      lastSubscriber?.onClose?.();
    });

    await waitFor(() => {
      expect(result.current.isConnected).toBe(false);
    });

    expect(result.current.reconnectCount).toBe(2);
  });

  it('should not reconnect when reconnect is false', async () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      reconnect: false,
    };

    renderHook(() => useWebSocket(options));

    expect(webSocketManager.subscribe).toHaveBeenCalledWith(
      'ws://localhost:8000/ws',
      expect.any(Object),
      expect.objectContaining({
        reconnect: false,
      })
    );
  });

  it('should handle manual disconnect', async () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      reconnect: true,
      reconnectInterval: 100,
    };

    const { result } = renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    act(() => {
      result.current.disconnect();
    });

    expect(mockUnsubscribe).toHaveBeenCalled();
    expect(result.current.isConnected).toBe(false);
  });

  it('should handle manual connect after disconnect', async () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      reconnect: false,
    };

    const { result } = renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    act(() => {
      result.current.disconnect();
    });

    expect(result.current.isConnected).toBe(false);

    act(() => {
      result.current.connect();
    });

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    // subscribe should have been called twice
    expect(webSocketManager.subscribe).toHaveBeenCalledTimes(2);
  });

  it('should not create new connection when already connected', async () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
    };

    const { result } = renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const callCountAfterOpen = (webSocketManager.subscribe as Mock).mock.calls.length;

    // Try to connect again while already open
    act(() => {
      result.current.connect();
    });

    // Should not have created additional subscriptions
    expect((webSocketManager.subscribe as Mock).mock.calls.length).toBe(callCountAfterOpen);
  });

  it('should expose hasExhaustedRetries state', async () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
    };

    const { result } = renderHook(() => useWebSocket(options));

    // Initially should be false
    expect(result.current.hasExhaustedRetries).toBe(false);

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    // After connection, should still be false
    expect(result.current.hasExhaustedRetries).toBe(false);
  });

  it('should expose reconnectCount state', async () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
    };

    const { result } = renderHook(() => useWebSocket(options));

    // Initially should be 0
    expect(result.current.reconnectCount).toBe(0);

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    // After connection, should still be 0
    expect(result.current.reconnectCount).toBe(0);
  });

  it('should call onMaxRetriesExhausted when reconnection attempts exhausted', async () => {
    const onMaxRetriesExhausted = vi.fn();
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      reconnect: true,
      reconnectInterval: 50,
      reconnectAttempts: 1,
      onMaxRetriesExhausted,
    };

    const { result } = renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    // Simulate max retries exhausted
    act(() => {
      lastSubscriber?.onMaxRetriesExhausted?.();
    });

    expect(onMaxRetriesExhausted).toHaveBeenCalled();
    expect(result.current.hasExhaustedRetries).toBe(true);
  });

  it('should accept onMaxRetriesExhausted callback', () => {
    const onMaxRetriesExhausted = vi.fn();
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      reconnect: true,
      reconnectAttempts: 2,
      onMaxRetriesExhausted,
    };

    const { result } = renderHook(() => useWebSocket(options));

    // Callback is provided but not called initially
    expect(result.current.hasExhaustedRetries).toBe(false);
    expect(onMaxRetriesExhausted).not.toHaveBeenCalled();
  });

  it('should accept connectionTimeout option', () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      connectionTimeout: 100,
      reconnect: false,
    };

    const { result } = renderHook(() => useWebSocket(options));

    // Hook should work with connectionTimeout option
    expect(result.current).toBeDefined();
    expect(webSocketManager.subscribe).toHaveBeenCalledWith(
      expect.any(String),
      expect.any(Object),
      expect.objectContaining({
        connectionTimeout: 100,
      })
    );
  });

  it('should handle connectionTimeout with zero value', () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      connectionTimeout: 0,
    };

    const { result } = renderHook(() => useWebSocket(options));

    // Hook should work with connectionTimeout of 0
    expect(result.current).toBeDefined();
    expect(webSocketManager.subscribe).toHaveBeenCalledWith(
      expect.any(String),
      expect.any(Object),
      expect.objectContaining({
        connectionTimeout: 0,
      })
    );
  });

  // Heartbeat handling tests
  describe('heartbeat handling', () => {
    it('should handle server heartbeat messages and update lastHeartbeat', async () => {
      const onHeartbeat = vi.fn();
      const onMessage = vi.fn();
      const heartbeatTime = new Date();

      (webSocketManager.getConnectionState as Mock).mockReturnValue({
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        lastHeartbeat: heartbeatTime,
      });

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        onHeartbeat,
        onMessage,
      };

      const { result } = renderHook(() => useWebSocket(options));

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Initially lastHeartbeat should be null
      expect(result.current.lastHeartbeat).toBeNull();

      // Simulate heartbeat callback from manager
      act(() => {
        lastSubscriber?.onHeartbeat?.();
      });

      // lastHeartbeat should be updated from manager state
      expect(result.current.lastHeartbeat).toEqual(heartbeatTime);
      // onHeartbeat callback should be called
      expect(onHeartbeat).toHaveBeenCalled();
    });

    it('should expose lastHeartbeat in return value', async () => {
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Initially should be null
      expect(result.current.lastHeartbeat).toBeNull();

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // After connection, should still be null (no heartbeat yet)
      expect(result.current.lastHeartbeat).toBeNull();
    });
  });

  // New test for connection deduplication
  describe('connection deduplication', () => {
    it('should share connection for same URL via webSocketManager', async () => {
      const subscribeCalls: string[] = [];

      (webSocketManager.subscribe as Mock).mockImplementation(
        (url: string, subscriber: SubscribeCallback) => {
          subscribeCalls.push(url);
          // Simulate connection opening
          setTimeout(() => {
            subscriber.onOpen?.();
          }, 0);
          return vi.fn();
        }
      );

      (webSocketManager.getSubscriberCount as Mock).mockReturnValue(2);

      const { result: result1 } = renderHook(() =>
        useWebSocket({ url: 'ws://test/events' })
      );
      const { result: result2 } = renderHook(() =>
        useWebSocket({ url: 'ws://test/events' })
      );

      await waitFor(() => {
        expect(result1.current.isConnected).toBe(true);
        expect(result2.current.isConnected).toBe(true);
      });

      // Both hooks should have called subscribe with the same URL
      // The webSocketManager handles the actual deduplication internally
      expect(subscribeCalls.filter((url) => url === 'ws://test/events').length).toBe(2);

      // The manager would report 2 subscribers
      expect(webSocketManager.getSubscriberCount('ws://test/events')).toBe(2);
    });
  });
});

describe('calculateBackoffDelay', () => {
  // Store original Math.random and restore after tests
  let originalRandom: () => number;

  beforeEach(() => {
    originalRandom = Math.random;
  });

  afterEach(() => {
    Math.random = originalRandom;
  });

  describe('exponential backoff progression', () => {
    it('calculates exponential delays (1s, 2s, 4s, 8s, 16s base intervals)', () => {
      // Mock random to return 0 (no jitter) for predictable testing
      Math.random = () => 0;

      const baseInterval = 1000; // 1 second

      // attempt 0: 1000 * 2^0 = 1000ms
      expect(calculateBackoffDelay(0, baseInterval)).toBe(1000);
      // attempt 1: 1000 * 2^1 = 2000ms
      expect(calculateBackoffDelay(1, baseInterval)).toBe(2000);
      // attempt 2: 1000 * 2^2 = 4000ms
      expect(calculateBackoffDelay(2, baseInterval)).toBe(4000);
      // attempt 3: 1000 * 2^3 = 8000ms
      expect(calculateBackoffDelay(3, baseInterval)).toBe(8000);
      // attempt 4: 1000 * 2^4 = 16000ms
      expect(calculateBackoffDelay(4, baseInterval)).toBe(16000);
    });

    it('caps delay at maxInterval (default 30s)', () => {
      Math.random = () => 0;

      const baseInterval = 1000;

      // attempt 5: 1000 * 2^5 = 32000ms, capped at 30000ms
      expect(calculateBackoffDelay(5, baseInterval)).toBe(30000);
      // attempt 6: 1000 * 2^6 = 64000ms, capped at 30000ms
      expect(calculateBackoffDelay(6, baseInterval)).toBe(30000);
      // attempt 10: huge number, still capped at 30000ms
      expect(calculateBackoffDelay(10, baseInterval)).toBe(30000);
    });

    it('respects custom maxInterval', () => {
      Math.random = () => 0;

      const baseInterval = 1000;
      const customMaxInterval = 10000;

      // attempt 0: 1000ms
      expect(calculateBackoffDelay(0, baseInterval, customMaxInterval)).toBe(1000);
      // attempt 3: 8000ms (under cap)
      expect(calculateBackoffDelay(3, baseInterval, customMaxInterval)).toBe(8000);
      // attempt 4: 16000ms -> capped at 10000ms
      expect(calculateBackoffDelay(4, baseInterval, customMaxInterval)).toBe(10000);
      // attempt 5: 32000ms -> capped at 10000ms
      expect(calculateBackoffDelay(5, baseInterval, customMaxInterval)).toBe(10000);
    });
  });

  describe('jitter', () => {
    it('adds up to 25% jitter to the delay', () => {
      // Test with max jitter (random returns 1)
      Math.random = () => 1;

      const baseInterval = 1000;

      // attempt 0: base = 1000, jitter = 1 * 0.25 * 1000 = 250, total = 1250
      expect(calculateBackoffDelay(0, baseInterval)).toBe(1250);
      // attempt 1: base = 2000, jitter = 1 * 0.25 * 2000 = 500, total = 2500
      expect(calculateBackoffDelay(1, baseInterval)).toBe(2500);
    });

    it('adds proportional jitter (12.5% when random=0.5)', () => {
      Math.random = () => 0.5;

      const baseInterval = 1000;

      // attempt 0: base = 1000, jitter = 0.5 * 0.25 * 1000 = 125, total = 1125
      expect(calculateBackoffDelay(0, baseInterval)).toBe(1125);
      // attempt 2: base = 4000, jitter = 0.5 * 0.25 * 4000 = 500, total = 4500
      expect(calculateBackoffDelay(2, baseInterval)).toBe(4500);
    });

    it('returns integer values (no fractional milliseconds)', () => {
      // Use a random value that would produce fractional results
      Math.random = () => 0.333;

      const baseInterval = 1000;
      const result = calculateBackoffDelay(1, baseInterval);

      // Result should be an integer
      expect(Number.isInteger(result)).toBe(true);
    });
  });

  describe('rate limit compliance', () => {
    it('delays help avoid hitting WebSocket rate limit (10/min + 2 burst)', () => {
      Math.random = () => 0;

      const baseInterval = 1000;

      // Calculate total time for 5 reconnection attempts (default)
      // Attempt 0: wait 1s, Attempt 1: wait 2s, Attempt 2: wait 4s, Attempt 3: wait 8s, Attempt 4: wait 16s
      const delays = [0, 1, 2, 3, 4].map((attempt) =>
        calculateBackoffDelay(attempt, baseInterval)
      );
      const totalDelay = delays.reduce((sum, delay) => sum + delay, 0);

      // Total: 1000 + 2000 + 4000 + 8000 + 16000 = 31000ms = 31 seconds
      expect(totalDelay).toBe(31000);

      // With 5 attempts over 31+ seconds, we're well under 10/min rate limit
      // Rate limit is 10 connections per minute (plus 2 burst = 12 total)
      // 5 attempts in 31+ seconds = ~9.7 per minute (safe margin)
    });

    it('respects 30s maximum delay to prevent excessive waits', () => {
      Math.random = () => 0;

      // Even with many attempts, delay never exceeds 30 seconds
      for (let attempt = 0; attempt < 20; attempt++) {
        const delay = calculateBackoffDelay(attempt, 1000);
        expect(delay).toBeLessThanOrEqual(30000);
      }
    });
  });

  describe('edge cases', () => {
    it('handles attempt 0 correctly', () => {
      Math.random = () => 0;
      expect(calculateBackoffDelay(0, 1000)).toBe(1000);
    });

    it('handles different base intervals', () => {
      Math.random = () => 0;

      // 500ms base
      expect(calculateBackoffDelay(0, 500)).toBe(500);
      expect(calculateBackoffDelay(1, 500)).toBe(1000);
      expect(calculateBackoffDelay(2, 500)).toBe(2000);

      // 2000ms base
      expect(calculateBackoffDelay(0, 2000)).toBe(2000);
      expect(calculateBackoffDelay(1, 2000)).toBe(4000);
      expect(calculateBackoffDelay(2, 2000)).toBe(8000);
    });

    it('handles very small base interval', () => {
      Math.random = () => 0;

      // 100ms base
      expect(calculateBackoffDelay(0, 100)).toBe(100);
      expect(calculateBackoffDelay(5, 100)).toBe(3200); // 100 * 32
      expect(calculateBackoffDelay(10, 100)).toBe(30000); // Capped at max
    });
  });
});

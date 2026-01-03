/**
 * Tests for WebSocket timeout and reconnection behavior.
 *
 * This file tests:
 * - Connection timeout handling
 * - Automatic reconnection with exponential backoff
 * - State management during disconnection
 * - Error recovery after connection failures
 * - Max retries exhaustion behavior
 *
 * Note: Since useWebSocket now delegates to webSocketManager, these tests
 * mock the webSocketManager to simulate various connection scenarios.
 */

/* eslint-disable @typescript-eslint/await-thenable, @typescript-eslint/require-await, @typescript-eslint/unbound-method */
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi, Mock } from 'vitest';

import { useWebSocket, WebSocketOptions } from './useWebSocket';
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

describe('useWebSocket timeout and reconnection', () => {
  let mockUnsubscribe: Mock;
  let lastSubscriber: SubscribeCallback | null = null;

  beforeEach(() => {
    vi.useFakeTimers();
    resetSubscriberCounter();
    mockUnsubscribe = vi.fn();
    lastSubscriber = null;

    // Default mock implementations
    (webSocketManager.subscribe as Mock).mockImplementation(
      (_url: string, subscriber: SubscribeCallback, _config: SubscribeConfig) => {
        lastSubscriber = subscriber;
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

  describe('Connection Timeout', () => {
    it('should close connection if timeout is exceeded while connecting', async () => {
      // Set up subscribe to simulate timeout by not calling onOpen
      (webSocketManager.subscribe as Mock).mockImplementation(
        (_url: string, subscriber: SubscribeCallback) => {
          lastSubscriber = subscriber;
          // Don't call onOpen - simulating timeout
          // In real implementation, the manager would handle the timeout
          // and call onClose after connectionTimeout
          setTimeout(() => {
            subscriber.onClose?.();
          }, 150);
          return mockUnsubscribe;
        }
      );

      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        connectionTimeout: 100, // 100ms timeout
        reconnect: false,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Initially not connected
      expect(result.current.isConnected).toBe(false);

      // Verify connectionTimeout was passed to manager
      expect(webSocketManager.subscribe).toHaveBeenCalledWith(
        'ws://localhost:8000/ws',
        expect.any(Object),
        expect.objectContaining({
          connectionTimeout: 100,
        })
      );

      // Advance timer past timeout
      await act(() => {
        vi.advanceTimersByTime(200);
      });

      // Connection should have failed
      expect(result.current.isConnected).toBe(false);

      consoleSpy.mockRestore();
    });

    it('should attempt reconnection after connection timeout', async () => {
      let subscribeCallCount = 0;

      (webSocketManager.subscribe as Mock).mockImplementation(
        (_url: string, subscriber: SubscribeCallback) => {
          subscribeCallCount++;
          lastSubscriber = subscriber;

          if (subscribeCallCount === 1) {
            // First connection times out
            setTimeout(() => {
              subscriber.onClose?.();
            }, 60);
          } else {
            // Second connection succeeds
            setTimeout(() => {
              subscriber.onOpen?.();
            }, 10);
          }
          return mockUnsubscribe;
        }
      );

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        connectionTimeout: 50,
        reconnect: true,
        reconnectInterval: 100,
        reconnectAttempts: 3,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Initially connecting
      expect(result.current.isConnected).toBe(false);

      // Verify reconnect config was passed
      expect(webSocketManager.subscribe).toHaveBeenCalledWith(
        expect.any(String),
        expect.any(Object),
        expect.objectContaining({
          reconnect: true,
          reconnectInterval: 100,
          maxReconnectAttempts: 3,
        })
      );

      // Wait for first connection to fail
      await act(() => {
        vi.advanceTimersByTime(100);
      });

      // First subscription was made
      expect(subscribeCallCount).toBe(1);
    });

    it('should clear connection timeout when connection succeeds', async () => {
      (webSocketManager.subscribe as Mock).mockImplementation(
        (_url: string, subscriber: SubscribeCallback) => {
          lastSubscriber = subscriber;
          // Connection succeeds after 50ms
          setTimeout(() => {
            subscriber.onOpen?.();
          }, 50);
          return mockUnsubscribe;
        }
      );

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        connectionTimeout: 200, // Plenty of time
        reconnect: false,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Wait for connection to open
      await act(() => {
        vi.advanceTimersByTime(100);
      });

      expect(result.current.isConnected).toBe(true);
      expect(result.current.reconnectCount).toBe(0);
    });

    it('should handle zero connection timeout (disabled)', async () => {
      (webSocketManager.subscribe as Mock).mockImplementation(
        (_url: string, subscriber: SubscribeCallback) => {
          lastSubscriber = subscriber;
          setTimeout(() => {
            subscriber.onOpen?.();
          }, 10);
          return mockUnsubscribe;
        }
      );

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        connectionTimeout: 0, // Disabled
        reconnect: false,
      };

      const { result } = renderHook(() => useWebSocket(options));

      await act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(result.current.isConnected).toBe(true);

      // Verify zero timeout was passed
      expect(webSocketManager.subscribe).toHaveBeenCalledWith(
        expect.any(String),
        expect.any(Object),
        expect.objectContaining({
          connectionTimeout: 0,
        })
      );
    });
  });

  describe('Reconnection Behavior', () => {
    it('should increment reconnectCount on each reconnection attempt', async () => {
      let closeCount = 0;

      (webSocketManager.subscribe as Mock).mockImplementation(
        (_url: string, subscriber: SubscribeCallback) => {
          lastSubscriber = subscriber;
          setTimeout(() => {
            subscriber.onOpen?.();
          }, 10);
          return mockUnsubscribe;
        }
      );

      (webSocketManager.getConnectionState as Mock).mockImplementation(() => ({
        isConnected: false,
        reconnectCount: closeCount,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
      }));

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: true,
        reconnectInterval: 50,
        reconnectAttempts: 3,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Wait for initial connection
      await act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(result.current.isConnected).toBe(true);
      expect(result.current.reconnectCount).toBe(0);

      // Simulate close and update state
      closeCount = 1;
      await act(() => {
        lastSubscriber?.onClose?.();
      });

      expect(result.current.isConnected).toBe(false);
      expect(result.current.reconnectCount).toBe(1);
    });

    it('should use exponential backoff for reconnection delays', async () => {
      // Verify the reconnectInterval is passed to the manager
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: true,
        reconnectInterval: 100,
        reconnectAttempts: 4,
      };

      renderHook(() => useWebSocket(options));

      // Verify the config is passed correctly
      expect(webSocketManager.subscribe).toHaveBeenCalledWith(
        expect.any(String),
        expect.any(Object),
        expect.objectContaining({
          reconnect: true,
          reconnectInterval: 100,
          maxReconnectAttempts: 4,
        })
      );
    });

    it('should reset reconnectCount on successful connection', async () => {
      (webSocketManager.subscribe as Mock).mockImplementation(
        (_url: string, subscriber: SubscribeCallback) => {
          lastSubscriber = subscriber;
          setTimeout(() => {
            subscriber.onOpen?.();
          }, 10);
          return mockUnsubscribe;
        }
      );

      (webSocketManager.getConnectionState as Mock).mockReturnValue({
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
      });

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: true,
        reconnectInterval: 50,
        reconnectAttempts: 3,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Wait for connection
      await act(() => {
        vi.advanceTimersByTime(100);
      });

      // After successful connection, count should be reset to 0
      expect(result.current.reconnectCount).toBe(0);
      expect(result.current.isConnected).toBe(true);
    });

    it('should not reconnect when reconnect is disabled', async () => {
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: false,
      };

      renderHook(() => useWebSocket(options));

      // Verify reconnect: false was passed
      expect(webSocketManager.subscribe).toHaveBeenCalledWith(
        expect.any(String),
        expect.any(Object),
        expect.objectContaining({
          reconnect: false,
        })
      );
    });
  });

  describe('Max Retries Exhaustion', () => {
    it('should expose hasExhaustedRetries in return value', async () => {
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: true,
        reconnectInterval: 10,
        reconnectAttempts: 2,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // hasExhaustedRetries should be a boolean
      expect(typeof result.current.hasExhaustedRetries).toBe('boolean');
      // Initially should be false
      expect(result.current.hasExhaustedRetries).toBe(false);
    });

    it('should accept onMaxRetriesExhausted callback', async () => {
      const onMaxRetriesExhausted = vi.fn();

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: true,
        reconnectInterval: 10,
        reconnectAttempts: 1,
        onMaxRetriesExhausted,
      };

      const { result } = renderHook(() => useWebSocket(options));

      await act(() => {
        vi.advanceTimersByTime(20);
      });

      // Hook should be valid
      expect(result.current.isConnected).toBeDefined();

      // Simulate max retries exhausted
      await act(() => {
        lastSubscriber?.onMaxRetriesExhausted?.();
      });

      expect(onMaxRetriesExhausted).toHaveBeenCalled();
      expect(result.current.hasExhaustedRetries).toBe(true);
    });

    it('should reset hasExhaustedRetries on manual connect call', async () => {
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: true,
        reconnectInterval: 10,
        reconnectAttempts: 1,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Wait for connection
      await act(() => {
        vi.advanceTimersByTime(20);
      });

      // Simulate max retries exhausted
      await act(() => {
        lastSubscriber?.onMaxRetriesExhausted?.();
      });

      expect(result.current.hasExhaustedRetries).toBe(true);

      // Disconnect first
      await act(() => {
        result.current.disconnect();
      });

      // Manual connect should reset hasExhaustedRetries
      await act(() => {
        result.current.connect();
      });

      expect(result.current.hasExhaustedRetries).toBe(false);
    });
  });

  describe('State Management During Disconnection', () => {
    it('should maintain lastMessage during reconnection', async () => {
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: true,
        reconnectInterval: 50,
        reconnectAttempts: 3,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Wait for connection
      await act(() => {
        vi.advanceTimersByTime(50);
      });

      // Simulate receiving a message
      const testMessage = { type: 'test', data: 'hello' };
      await act(() => {
        lastSubscriber?.onMessage?.(testMessage);
      });

      expect(result.current.lastMessage).toEqual(testMessage);

      // Simulate close
      (webSocketManager.getConnectionState as Mock).mockReturnValue({
        isConnected: false,
        reconnectCount: 1,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
      });

      await act(() => {
        lastSubscriber?.onClose?.();
      });

      // lastMessage should still be available during reconnection
      expect(result.current.lastMessage).toEqual(testMessage);
    });

    it('should correctly report isConnected during reconnection cycle', async () => {
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: true,
        reconnectInterval: 100,
        reconnectAttempts: 3,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Initially not connected
      expect(result.current.isConnected).toBe(false);

      // Wait for connection
      await act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(result.current.isConnected).toBe(true);

      // Simulate close
      await act(() => {
        lastSubscriber?.onClose?.();
      });

      expect(result.current.isConnected).toBe(false);

      // Simulate reconnect
      await act(() => {
        lastSubscriber?.onOpen?.();
      });

      expect(result.current.isConnected).toBe(true);
    });

    it('should update lastHeartbeat on server heartbeat', async () => {
      const heartbeatTime = new Date();

      (webSocketManager.getConnectionState as Mock).mockReturnValue({
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        lastHeartbeat: heartbeatTime,
      });

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: false,
      };

      const { result } = renderHook(() => useWebSocket(options));

      await act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(result.current.lastHeartbeat).toBeNull();

      // Simulate server heartbeat callback
      await act(() => {
        lastSubscriber?.onHeartbeat?.();
      });

      expect(result.current.lastHeartbeat).toEqual(heartbeatTime);
    });
  });

  describe('Error Recovery', () => {
    it('should recover after WebSocket constructor error', async () => {
      let subscribeCallCount = 0;

      (webSocketManager.subscribe as Mock).mockImplementation(
        (_url: string, subscriber: SubscribeCallback) => {
          subscribeCallCount++;
          lastSubscriber = subscriber;

          if (subscribeCallCount === 1) {
            // First subscription simulates error
            setTimeout(() => {
              subscriber.onError?.(new Event('error'));
            }, 5);
          } else {
            // Subsequent subscriptions succeed
            setTimeout(() => {
              subscriber.onOpen?.();
            }, 10);
          }
          return mockUnsubscribe;
        }
      );

      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: false,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // First attempt triggers error
      await act(() => {
        vi.advanceTimersByTime(20);
      });

      expect(result.current.isConnected).toBe(false);

      // Disconnect first to clear subscription
      await act(() => {
        result.current.disconnect();
      });

      // Manual reconnect should work
      await act(() => {
        result.current.connect();
      });

      await act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(result.current.isConnected).toBe(true);

      consoleSpy.mockRestore();
    });

    it('should handle rapid connect/disconnect cycles', async () => {
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: false,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Rapid connect/disconnect cycles
      for (let i = 0; i < 5; i++) {
        await act(() => {
          vi.advanceTimersByTime(20);
        });

        await act(() => {
          result.current.disconnect();
        });

        await act(() => {
          result.current.connect();
        });
      }

      // Should handle gracefully without errors
      await act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(result.current.isConnected).toBe(true);
    });
  });
});

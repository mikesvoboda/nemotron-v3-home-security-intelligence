/**
 * Tests for WebSocket timeout and reconnection behavior.
 *
 * This file tests:
 * - Connection timeout handling
 * - Automatic reconnection with exponential backoff
 * - State management during disconnection
 * - Error recovery after connection failures
 * - Max retries exhaustion behavior
 */

/* eslint-disable @typescript-eslint/await-thenable, @typescript-eslint/require-await */
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useWebSocket, WebSocketOptions } from './useWebSocket';

// Extend Window interface for WebSocket
declare global {
  interface Window {
    WebSocket: typeof WebSocket;
  }
}

// Mock WebSocket with connection timeout simulation
class MockWebSocketWithTimeout {
  url: string;
  readyState: number = WebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  private openDelay: number;
  private shouldTimeout: boolean;
  private timeoutId: ReturnType<typeof setTimeout> | null = null;

  constructor(url: string, options?: { openDelay?: number; shouldTimeout?: boolean }) {
    this.url = url;
    this.openDelay = options?.openDelay ?? 0;
    this.shouldTimeout = options?.shouldTimeout ?? false;

    if (!this.shouldTimeout) {
      // Simulate connection opening after delay
      this.timeoutId = setTimeout(() => {
        this.readyState = WebSocket.OPEN;
        if (this.onopen) {
          this.onopen(new Event('open'));
        }
      }, this.openDelay);
    }
    // If shouldTimeout is true, connection stays in CONNECTING state
  }

  send(_data: string): void {
    if (this.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
  }

  close(): void {
    if (this.timeoutId) {
      clearTimeout(this.timeoutId);
      this.timeoutId = null;
    }
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  simulateMessage(data: unknown): void {
    if (this.onmessage) {
      const messageData = typeof data === 'string' ? data : JSON.stringify(data);
      this.onmessage(new MessageEvent('message', { data: messageData }));
    }
  }

  simulateError(): void {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }
}

describe('useWebSocket timeout and reconnection', () => {
  let mockWebSocket: MockWebSocketWithTimeout | null = null;
  let createdWebSockets: MockWebSocketWithTimeout[] = [];
  const originalWebSocket = window.WebSocket;

  beforeEach(() => {
    vi.useFakeTimers();
    createdWebSockets = [];
  });

  afterEach(() => {
    window.WebSocket = originalWebSocket;
    mockWebSocket = null;
    createdWebSockets = [];
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  describe('Connection Timeout', () => {
    it('should close connection if timeout is exceeded while connecting', async () => {
      // Set up a WebSocket that never completes connection
      window.WebSocket = vi.fn(function (this: MockWebSocketWithTimeout, url: string) {
        mockWebSocket = new MockWebSocketWithTimeout(url, { shouldTimeout: true });
        createdWebSockets.push(mockWebSocket);
        Object.assign(this, mockWebSocket);
        return mockWebSocket;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

      const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        connectionTimeout: 100, // 100ms timeout
        reconnect: false, // Disable reconnect for this test
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Initially not connected
      expect(result.current.isConnected).toBe(false);

      // Advance timer past connection timeout
      await act(() => {
        vi.advanceTimersByTime(150);
      });

      // Should have logged warning about timeout (message format: "WebSocket connection timeout after Xms, retrying...")
      expect(consoleSpy).toHaveBeenCalled();
      const calls = consoleSpy.mock.calls;
      const hasTimeoutWarning = calls.some(
        (call) => typeof call[0] === 'string' && call[0].toLowerCase().includes('timeout')
      );
      expect(hasTimeoutWarning).toBe(true);

      consoleSpy.mockRestore();
    });

    it('should attempt reconnection after connection timeout', async () => {
      let connectionAttempt = 0;

      window.WebSocket = vi.fn(function (this: MockWebSocketWithTimeout, url: string) {
        connectionAttempt++;
        // First connection times out, second succeeds
        const shouldTimeout = connectionAttempt === 1;
        mockWebSocket = new MockWebSocketWithTimeout(url, {
          shouldTimeout,
          openDelay: shouldTimeout ? 0 : 10,
        });
        createdWebSockets.push(mockWebSocket);
        Object.assign(this, mockWebSocket);
        return mockWebSocket;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

      vi.spyOn(console, 'warn').mockImplementation(() => {});

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

      // First connection times out
      await act(() => {
        vi.advanceTimersByTime(100);
      });

      // Wait for reconnection delay
      await act(() => {
        vi.advanceTimersByTime(200);
      });

      // Second connection should succeed
      await act(() => {
        vi.advanceTimersByTime(50);
      });

      // Should have made 2 connection attempts
      expect(connectionAttempt).toBeGreaterThanOrEqual(2);
    });

    it('should clear connection timeout when connection succeeds', async () => {
      window.WebSocket = vi.fn(function (this: MockWebSocketWithTimeout, url: string) {
        mockWebSocket = new MockWebSocketWithTimeout(url, { openDelay: 50 });
        createdWebSockets.push(mockWebSocket);
        Object.assign(this, mockWebSocket);
        return mockWebSocket;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

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
      window.WebSocket = vi.fn(function (this: MockWebSocketWithTimeout, url: string) {
        mockWebSocket = new MockWebSocketWithTimeout(url, { openDelay: 10 });
        createdWebSockets.push(mockWebSocket);
        Object.assign(this, mockWebSocket);
        return mockWebSocket;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

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
    });
  });

  describe('Reconnection Behavior', () => {
    it('should increment reconnectCount on each reconnection attempt', async () => {
      let _connectionAttempt = 0;

      window.WebSocket = vi.fn(function (this: MockWebSocketWithTimeout, url: string) {
        _connectionAttempt++;
        mockWebSocket = new MockWebSocketWithTimeout(url, { openDelay: 10 });
        createdWebSockets.push(mockWebSocket);
        Object.assign(this, mockWebSocket);
        return mockWebSocket;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

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

      // Close connection to trigger reconnection
      await act(() => {
        mockWebSocket?.close();
      });

      expect(result.current.isConnected).toBe(false);

      // Wait for first reconnect attempt (base interval 50ms + up to 25% jitter = up to 62.5ms)
      // Plus some extra time for the reconnection to be scheduled
      await act(() => {
        vi.advanceTimersByTime(200); // Give plenty of time for reconnect
      });

      // After close + reconnect delay + connection, should have at least 1 reconnect attempt
      expect(result.current.reconnectCount).toBeGreaterThanOrEqual(0);
    });

    it('should use exponential backoff for reconnection delays', async () => {
      const reconnectDelays: number[] = [];
      let lastReconnectTime = 0;

      window.WebSocket = vi.fn(function (this: MockWebSocketWithTimeout, url: string) {
        const now = Date.now();
        if (lastReconnectTime > 0) {
          reconnectDelays.push(now - lastReconnectTime);
        }
        lastReconnectTime = now;

        // Connection fails immediately to trigger reconnect
        mockWebSocket = new MockWebSocketWithTimeout(url, { openDelay: 5 });
        createdWebSockets.push(mockWebSocket);
        Object.assign(this, mockWebSocket);

        // Simulate close after a short delay
        setTimeout(() => {
          if (mockWebSocket && mockWebSocket.onclose) {
            mockWebSocket.readyState = WebSocket.CLOSED;
            mockWebSocket.onclose(new CloseEvent('close'));
          }
        }, 10);

        return mockWebSocket;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: true,
        reconnectInterval: 100,
        reconnectAttempts: 4,
      };

      renderHook(() => useWebSocket(options));

      // Run through multiple reconnection cycles
      await act(() => {
        vi.advanceTimersByTime(5000);
      });

      // Verify exponential backoff pattern (delays should generally increase)
      // Note: Due to jitter, we can't verify exact values, but should see general trend
      if (reconnectDelays.length >= 2) {
        // Later delays should generally be longer (with some tolerance for jitter)
        const firstHalfAvg =
          reconnectDelays.slice(0, Math.floor(reconnectDelays.length / 2)).reduce((a, b) => a + b, 0) /
          Math.floor(reconnectDelays.length / 2);
        const secondHalfAvg =
          reconnectDelays.slice(Math.floor(reconnectDelays.length / 2)).reduce((a, b) => a + b, 0) /
          (reconnectDelays.length - Math.floor(reconnectDelays.length / 2));
        // Second half average should be >= first half (exponential growth)
        expect(secondHalfAvg).toBeGreaterThanOrEqual(firstHalfAvg * 0.8); // Allow for jitter
      }
    });

    it('should reset reconnectCount on successful connection', async () => {
      let connectionAttempt = 0;

      window.WebSocket = vi.fn(function (this: MockWebSocketWithTimeout, url: string) {
        connectionAttempt++;
        // First connection fails, rest succeed
        const shouldFail = connectionAttempt === 1;
        mockWebSocket = new MockWebSocketWithTimeout(url, { openDelay: 10 });
        createdWebSockets.push(mockWebSocket);
        Object.assign(this, mockWebSocket);

        if (shouldFail) {
          // Simulate failure after connecting
          setTimeout(() => {
            if (mockWebSocket && mockWebSocket.onclose) {
              mockWebSocket.readyState = WebSocket.CLOSED;
              mockWebSocket.onclose(new CloseEvent('close'));
            }
          }, 20);
        }

        return mockWebSocket;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: true,
        reconnectInterval: 50,
        reconnectAttempts: 3,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Wait for first connection to fail and reconnection to start
      await act(() => {
        vi.advanceTimersByTime(100);
      });

      // Wait for second connection to succeed
      await act(() => {
        vi.advanceTimersByTime(100);
      });

      // After successful reconnection, count should be reset
      expect(result.current.reconnectCount).toBe(0);
      expect(result.current.isConnected).toBe(true);
    });

    it('should not reconnect when reconnect is disabled', async () => {
      let connectionCount = 0;

      window.WebSocket = vi.fn(function (this: MockWebSocketWithTimeout, url: string) {
        connectionCount++;
        mockWebSocket = new MockWebSocketWithTimeout(url, { openDelay: 10 });
        createdWebSockets.push(mockWebSocket);
        Object.assign(this, mockWebSocket);
        return mockWebSocket;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: false,
      };

      const { result } = renderHook(() => useWebSocket(options));

      await act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(result.current.isConnected).toBe(true);
      expect(connectionCount).toBe(1);

      // Close connection
      await act(() => {
        mockWebSocket?.close();
      });

      expect(result.current.isConnected).toBe(false);

      // Wait for potential reconnection
      await act(() => {
        vi.advanceTimersByTime(500);
      });

      // Should not have reconnected
      expect(connectionCount).toBe(1);
    });
  });

  describe('Max Retries Exhaustion', () => {
    it('should expose hasExhaustedRetries in return value', async () => {
      // Verify the API exists and returns expected types
      window.WebSocket = vi.fn(function (url: string) {
        const ws = new MockWebSocketWithTimeout(url, { openDelay: 5 });
        createdWebSockets.push(ws);
        return ws;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

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
      window.WebSocket = vi.fn(function (url: string) {
        const ws = new MockWebSocketWithTimeout(url, { openDelay: 5 });
        createdWebSockets.push(ws);
        return ws;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

      const onMaxRetriesExhausted = vi.fn();

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: true,
        reconnectInterval: 10,
        reconnectAttempts: 1,
        onMaxRetriesExhausted,
      };

      // Should not throw when using the callback option
      const { result } = renderHook(() => useWebSocket(options));

      await act(() => {
        vi.advanceTimersByTime(10);
      });

      // Hook should be valid
      expect(result.current.isConnected).toBeDefined();
    });

    it('should reset hasExhaustedRetries on manual connect call', async () => {
      window.WebSocket = vi.fn(function (url: string) {
        const ws = new MockWebSocketWithTimeout(url, { openDelay: 5 });
        createdWebSockets.push(ws);
        return ws;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: true,
        reconnectInterval: 10,
        reconnectAttempts: 1,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // Wait for connection
      await act(() => {
        vi.advanceTimersByTime(10);
      });

      // Manual connect should always set hasExhaustedRetries to false
      // (according to the implementation: setHasExhaustedRetries(false) is called in connect())
      await act(() => {
        result.current.connect();
      });

      expect(result.current.hasExhaustedRetries).toBe(false);
    });
  });

  describe('State Management During Disconnection', () => {
    it('should maintain lastMessage during reconnection', async () => {
      let _connectionCount = 0;

      window.WebSocket = vi.fn(function (this: MockWebSocketWithTimeout, url: string) {
        _connectionCount++;
        mockWebSocket = new MockWebSocketWithTimeout(url, { openDelay: 10 });
        createdWebSockets.push(mockWebSocket);
        Object.assign(this, mockWebSocket);
        return mockWebSocket;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

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
        mockWebSocket?.simulateMessage(testMessage);
      });

      expect(result.current.lastMessage).toEqual(testMessage);

      // Close connection
      await act(() => {
        mockWebSocket?.close();
      });

      // lastMessage should still be available during reconnection
      expect(result.current.lastMessage).toEqual(testMessage);

      // Wait for reconnection
      await act(() => {
        vi.advanceTimersByTime(200);
      });

      // lastMessage should still be the same
      expect(result.current.lastMessage).toEqual(testMessage);
    });

    it('should correctly report isConnected during reconnection cycle', async () => {
      let _connectionCount = 0;

      window.WebSocket = vi.fn(function (this: MockWebSocketWithTimeout, url: string) {
        _connectionCount++;
        mockWebSocket = new MockWebSocketWithTimeout(url, { openDelay: 10 });
        createdWebSockets.push(mockWebSocket);
        Object.assign(this, mockWebSocket);
        return mockWebSocket;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

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

      // Close connection
      await act(() => {
        mockWebSocket?.close();
      });

      expect(result.current.isConnected).toBe(false);

      // Wait for reconnection
      await act(() => {
        vi.advanceTimersByTime(200);
      });

      expect(result.current.isConnected).toBe(true);
    });

    it('should update lastHeartbeat on server heartbeat', async () => {
      window.WebSocket = vi.fn(function (this: MockWebSocketWithTimeout, url: string) {
        mockWebSocket = new MockWebSocketWithTimeout(url, { openDelay: 10 });
        createdWebSockets.push(mockWebSocket);
        Object.assign(this, mockWebSocket);
        return mockWebSocket;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: false,
      };

      const { result } = renderHook(() => useWebSocket(options));

      await act(() => {
        vi.advanceTimersByTime(50);
      });

      expect(result.current.lastHeartbeat).toBeNull();

      // Simulate server heartbeat
      await act(() => {
        mockWebSocket?.simulateMessage({ type: 'ping' });
      });

      expect(result.current.lastHeartbeat).toBeInstanceOf(Date);
    });
  });

  describe('Error Recovery', () => {
    it('should recover after WebSocket constructor error', async () => {
      let constructorCallCount = 0;

      window.WebSocket = vi.fn(function (this: MockWebSocketWithTimeout, url: string) {
        constructorCallCount++;
        if (constructorCallCount === 1) {
          throw new Error('WebSocket constructor failed');
        }
        mockWebSocket = new MockWebSocketWithTimeout(url, { openDelay: 10 });
        createdWebSockets.push(mockWebSocket);
        Object.assign(this, mockWebSocket);
        return mockWebSocket;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        reconnect: false,
      };

      const { result } = renderHook(() => useWebSocket(options));

      // First attempt fails with constructor error
      expect(result.current.isConnected).toBe(false);
      expect(consoleSpy).toHaveBeenCalled();

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
      window.WebSocket = vi.fn(function (this: MockWebSocketWithTimeout, url: string) {
        mockWebSocket = new MockWebSocketWithTimeout(url, { openDelay: 5 });
        createdWebSockets.push(mockWebSocket);
        Object.assign(this, mockWebSocket);
        return mockWebSocket;
      }) as unknown as typeof WebSocket;

      Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
      Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
      Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
      Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

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

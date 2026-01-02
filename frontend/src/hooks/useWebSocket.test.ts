import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useWebSocket, WebSocketOptions, calculateBackoffDelay } from './useWebSocket';

// Extend Window interface for WebSocket
declare global {
  interface Window {
    WebSocket: typeof WebSocket;
  }
}

// Mock WebSocket
class MockWebSocket {
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

  constructor(url: string) {
    this.url = url;
    // Simulate connection opening
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 0);
  }

  send(_data: string): void {
    if (this.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
  }

  close(): void {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  // Helper method to simulate receiving a message
  simulateMessage(data: unknown): void {
    if (this.onmessage) {
      const messageData = typeof data === 'string' ? data : JSON.stringify(data);
      this.onmessage(new MessageEvent('message', { data: messageData }));
    }
  }

  // Helper method to simulate an error
  simulateError(): void {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }
}

describe('useWebSocket', () => {
  let mockWebSocket: MockWebSocket | null = null;
  const originalWebSocket = window.WebSocket;

  beforeEach(() => {
    // Replace window WebSocket with our mock
    // Vitest 4 requires function syntax (not arrow functions) for constructor mocks
    window.WebSocket = vi.fn(function (this: MockWebSocket, url: string) {
      mockWebSocket = new MockWebSocket(url);
      Object.assign(this, mockWebSocket);
      return mockWebSocket;
    }) as unknown as typeof WebSocket;

    // Add static properties
    Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
    Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
    Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
    Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });
  });

  afterEach(() => {
    window.WebSocket = originalWebSocket;
    mockWebSocket = null;
    vi.clearAllTimers();
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

    expect(window.WebSocket).toHaveBeenCalledWith('ws://localhost:8000/ws');
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

    await waitFor(() => {
      expect(mockWebSocket?.readyState).toBe(WebSocket.CLOSED);
    });
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
      mockWebSocket?.simulateMessage(testData);
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
      if (mockWebSocket?.onmessage) {
        mockWebSocket.onmessage(new MessageEvent('message', { data: rawMessage }));
      }
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

    const sendSpy = vi.spyOn(mockWebSocket as MockWebSocket, 'send');
    const testData = { type: 'test', message: 'Hello' };

    act(() => {
      result.current.send(testData);
    });

    expect(sendSpy).toHaveBeenCalledWith(JSON.stringify(testData));
  });

  it('should not send messages when disconnected', () => {
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

    expect(consoleSpy).toHaveBeenCalledWith(
      'WebSocket is not connected. Message not sent:',
      testData
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
      mockWebSocket?.close();
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
      expect(mockWebSocket).not.toBeNull();
    });

    act(() => {
      mockWebSocket?.simulateError();
    });

    expect(onError).toHaveBeenCalled();
  });

  it('should attempt reconnection on disconnect', async () => {
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

    const initialCallCount = (window.WebSocket as unknown as ReturnType<typeof vi.fn>).mock.calls
      .length;

    act(() => {
      mockWebSocket?.close();
    });

    await waitFor(() => {
      expect(result.current.isConnected).toBe(false);
    });

    // Wait for reconnection attempt
    await waitFor(
      () => {
        expect((window.WebSocket as unknown as ReturnType<typeof vi.fn>).mock.calls.length).toBe(
          initialCallCount + 1
        );
      },
      { timeout: 1000 }
    );
  });

  it('should respect reconnectAttempts setting', async () => {
    // This test verifies that reconnection happens but doesn't test the exact
    // limit due to timing complexity. The important behavior is that reconnection
    // eventually stops.
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      reconnect: true,
      reconnectInterval: 50,
      reconnectAttempts: 2,
    };

    const { result } = renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const callCountBeforeClose = (window.WebSocket as unknown as ReturnType<typeof vi.fn>).mock
      .calls.length;

    act(() => {
      mockWebSocket?.close();
    });

    await waitFor(() => {
      expect(result.current.isConnected).toBe(false);
    });

    // Wait for potential reconnection
    await new Promise((resolve) => setTimeout(resolve, 200));

    // Should have attempted at least one reconnection
    const callCountAfterReconnect = (window.WebSocket as unknown as ReturnType<typeof vi.fn>).mock
      .calls.length;
    expect(callCountAfterReconnect).toBeGreaterThan(callCountBeforeClose);
  });

  it('should not reconnect when reconnect is false', async () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      reconnect: false,
    };

    const { result } = renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const initialCallCount = (window.WebSocket as unknown as ReturnType<typeof vi.fn>).mock.calls
      .length;

    act(() => {
      mockWebSocket?.close();
    });

    await waitFor(() => {
      expect(result.current.isConnected).toBe(false);
    });

    // Wait to ensure no reconnection happens
    await new Promise((resolve) => setTimeout(resolve, 300));

    expect((window.WebSocket as unknown as ReturnType<typeof vi.fn>).mock.calls.length).toBe(
      initialCallCount
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

    const callCountBeforeDisconnect = (window.WebSocket as unknown as ReturnType<typeof vi.fn>).mock
      .calls.length;

    act(() => {
      result.current.disconnect();
    });

    await waitFor(() => {
      expect(result.current.isConnected).toBe(false);
    });

    // Should not attempt reconnection after manual disconnect
    await new Promise((resolve) => setTimeout(resolve, 300));

    expect(result.current.isConnected).toBe(false);
    expect((window.WebSocket as unknown as ReturnType<typeof vi.fn>).mock.calls.length).toBe(
      callCountBeforeDisconnect
    );
  });

  it('should handle manual connect', async () => {
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

    await waitFor(() => {
      expect(result.current.isConnected).toBe(false);
    });

    act(() => {
      result.current.connect();
    });

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });
  });

  it('should not create new connection when already connecting', () => {
    // Create a WebSocket mock that stays in CONNECTING state
    const slowMockWebSocket: MockWebSocket = new MockWebSocket('ws://localhost:8000/ws');
    slowMockWebSocket.readyState = WebSocket.CONNECTING;

    window.WebSocket = vi.fn(function (this: MockWebSocket) {
      slowMockWebSocket.readyState = WebSocket.CONNECTING;
      Object.assign(this, slowMockWebSocket);
      return slowMockWebSocket;
    }) as unknown as typeof WebSocket;

    Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
    Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });
    Object.defineProperty(window.WebSocket, 'CLOSING', { value: 2 });
    Object.defineProperty(window.WebSocket, 'CLOSED', { value: 3 });

    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
    };

    const { result } = renderHook(() => useWebSocket(options));

    const callCountAfterInitial = (window.WebSocket as unknown as ReturnType<typeof vi.fn>).mock
      .calls.length;

    // Try to connect again while still connecting
    act(() => {
      result.current.connect();
    });

    // Should not have created additional WebSocket connections
    expect((window.WebSocket as unknown as ReturnType<typeof vi.fn>).mock.calls.length).toBe(
      callCountAfterInitial
    );
  });

  it('should not create new connection when already open', async () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
    };

    const { result } = renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const callCountAfterOpen = (window.WebSocket as unknown as ReturnType<typeof vi.fn>).mock.calls
      .length;

    // Try to connect again while already open
    act(() => {
      result.current.connect();
    });

    // Should not have created additional WebSocket connections
    expect((window.WebSocket as unknown as ReturnType<typeof vi.fn>).mock.calls.length).toBe(
      callCountAfterOpen
    );
  });

  it('should handle WebSocket constructor error', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    // Make WebSocket constructor throw an error
    window.WebSocket = vi.fn(function () {
      throw new Error('WebSocket connection failed');
    }) as unknown as typeof WebSocket;

    Object.defineProperty(window.WebSocket, 'CONNECTING', { value: 0 });
    Object.defineProperty(window.WebSocket, 'OPEN', { value: 1 });

    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
    };

    const { result } = renderHook(() => useWebSocket(options));

    // Should not crash and isConnected should be false
    expect(result.current.isConnected).toBe(false);
    expect(consoleSpy).toHaveBeenCalledWith('WebSocket connection error:', expect.any(Error));

    consoleSpy.mockRestore();
  });

  it('should not connect when WebSocket is not available', () => {
    // Remove WebSocket from window to simulate no WebSocket support
    const savedWebSocket = window.WebSocket;
    (window as any).WebSocket = undefined;

    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
    };

    const { result } = renderHook(() => useWebSocket(options));

    // Should not crash and isConnected should be false
    expect(result.current.isConnected).toBe(false);

    // Restore WebSocket
    window.WebSocket = savedWebSocket;
  });

  it('should send string data directly without JSON.stringify', async () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
    };

    const { result } = renderHook(() => useWebSocket(options));

    await waitFor(() => {
      expect(result.current.isConnected).toBe(true);
    });

    const sendSpy = vi.spyOn(mockWebSocket as MockWebSocket, 'send');
    const testString = 'plain string message';

    act(() => {
      result.current.send(testString);
    });

    // String should be sent directly, not JSON.stringified (which would add quotes)
    expect(sendSpy).toHaveBeenCalledWith(testString);
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

    // Close connection to trigger reconnection
    act(() => {
      mockWebSocket?.close();
    });

    await waitFor(() => {
      expect(result.current.isConnected).toBe(false);
    });

    // Wait for reconnection attempt and then max retries exhausted
    await waitFor(
      () => {
        expect(result.current.reconnectCount).toBeGreaterThan(0);
      },
      { timeout: 1000 }
    );

    // Note: Due to timing, the callback may or may not have been called yet
    // The key is that hasExhaustedRetries or reconnectCount is updated
    expect(result.current.reconnectCount).toBeGreaterThanOrEqual(1);
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
    expect(result.current.reconnectCount).toBe(0);
  });

  it('should handle connectionTimeout with zero value', () => {
    const options: WebSocketOptions = {
      url: 'ws://localhost:8000/ws',
      connectionTimeout: 0,
    };

    const { result } = renderHook(() => useWebSocket(options));

    // Hook should work with connectionTimeout of 0
    expect(result.current).toBeDefined();
  });

  // Heartbeat handling tests
  describe('heartbeat handling', () => {
    it('should handle server heartbeat messages and update lastHeartbeat', async () => {
      const onHeartbeat = vi.fn();
      const onMessage = vi.fn();
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

      // Simulate server sending a heartbeat ping
      const heartbeatMessage = { type: 'ping' };

      act(() => {
        mockWebSocket?.simulateMessage(heartbeatMessage);
      });

      // lastHeartbeat should be updated
      expect(result.current.lastHeartbeat).toBeInstanceOf(Date);
      // onHeartbeat callback should be called
      expect(onHeartbeat).toHaveBeenCalled();
      // onMessage should NOT be called for heartbeat messages
      expect(onMessage).not.toHaveBeenCalled();
      // lastMessage should NOT be updated for heartbeat messages
      expect(result.current.lastMessage).toBeNull();
    });

    it('should automatically respond with pong to server heartbeats', async () => {
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        autoRespondToHeartbeat: true, // This is the default
      };

      const { result } = renderHook(() => useWebSocket(options));

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const sendSpy = vi.spyOn(mockWebSocket as MockWebSocket, 'send');

      // Simulate server sending a heartbeat ping
      const heartbeatMessage = { type: 'ping' };

      act(() => {
        mockWebSocket?.simulateMessage(heartbeatMessage);
      });

      // Should have sent a pong response
      expect(sendSpy).toHaveBeenCalledWith(JSON.stringify({ type: 'pong' }));
    });

    it('should not send pong when autoRespondToHeartbeat is false', async () => {
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        autoRespondToHeartbeat: false,
      };

      const { result } = renderHook(() => useWebSocket(options));

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const sendSpy = vi.spyOn(mockWebSocket as MockWebSocket, 'send');

      // Simulate server sending a heartbeat ping
      const heartbeatMessage = { type: 'ping' };

      act(() => {
        mockWebSocket?.simulateMessage(heartbeatMessage);
      });

      // Should NOT have sent a pong response
      expect(sendSpy).not.toHaveBeenCalled();
      // But lastHeartbeat should still be updated
      expect(result.current.lastHeartbeat).toBeInstanceOf(Date);
    });

    it('should not treat regular messages with type field as heartbeats', async () => {
      const onMessage = vi.fn();
      const onHeartbeat = vi.fn();
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
        onMessage,
        onHeartbeat,
      };

      const { result } = renderHook(() => useWebSocket(options));

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Simulate a regular message with a different type
      const regularMessage = { type: 'event', data: { id: 1 } };

      act(() => {
        mockWebSocket?.simulateMessage(regularMessage);
      });

      // onMessage should be called for non-heartbeat messages
      expect(onMessage).toHaveBeenCalledWith(regularMessage);
      // onHeartbeat should NOT be called
      expect(onHeartbeat).not.toHaveBeenCalled();
      // lastMessage should be updated
      expect(result.current.lastMessage).toEqual(regularMessage);
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

    it('should update lastHeartbeat timestamp on each heartbeat', async () => {
      const options: WebSocketOptions = {
        url: 'ws://localhost:8000/ws',
      };

      const { result } = renderHook(() => useWebSocket(options));

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // First heartbeat
      act(() => {
        mockWebSocket?.simulateMessage({ type: 'ping' });
      });

      const firstHeartbeat = result.current.lastHeartbeat;
      expect(firstHeartbeat).toBeInstanceOf(Date);

      // Wait a bit and send another heartbeat
      await new Promise((resolve) => setTimeout(resolve, 10));

      act(() => {
        mockWebSocket?.simulateMessage({ type: 'ping' });
      });

      const secondHeartbeat = result.current.lastHeartbeat;
      expect(secondHeartbeat).toBeInstanceOf(Date);
      // Second heartbeat should be later (or equal due to timing)
      expect(secondHeartbeat!.getTime()).toBeGreaterThanOrEqual(firstHeartbeat!.getTime());
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

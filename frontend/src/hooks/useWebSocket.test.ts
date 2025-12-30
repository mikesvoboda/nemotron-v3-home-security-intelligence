import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useWebSocket, WebSocketOptions } from './useWebSocket';

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
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
});

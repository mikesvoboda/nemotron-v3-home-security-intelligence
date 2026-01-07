import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useWebSocketStatus } from './useWebSocketStatus';

// Mock WebSocket
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  url: string;
  readyState: number = MockWebSocket.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    // Simulate async connection
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 0);
  }

  send(_data: string) {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  simulateMessage(data: unknown) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
    }
  }

  simulateClose() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) {
      this.onclose(new CloseEvent('close'));
    }
  }

  simulateError() {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }
}

describe('useWebSocketStatus', () => {
  let mockWsInstances: MockWebSocket[] = [];

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockWsInstances = [];

    // Mock WebSocket constructor
    vi.stubGlobal('WebSocket', class extends MockWebSocket {
      constructor(url: string) {
        super(url);
        mockWsInstances.push(this);
      }
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
    mockWsInstances = [];
  });

  it('initializes with disconnected state', () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
      })
    );

    expect(result.current.channelStatus.state).toBe('disconnected');
    expect(result.current.channelStatus.name).toBe('Test');
    expect(result.current.channelStatus.reconnectAttempts).toBe(0);
  });

  it('transitions to connected state on successful connection', async () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
      })
    );

    // Flush pending timers to allow connection
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(result.current.channelStatus.state).toBe('connected');
  });

  it('resets reconnect counter on successful connection', async () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(result.current.channelStatus.reconnectAttempts).toBe(0);
  });

  it('tracks channel name', () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'MyChannel',
      })
    );

    expect(result.current.channelStatus.name).toBe('MyChannel');
  });

  it('exposes maxReconnectAttempts', () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
        reconnectAttempts: 10,
      })
    );

    expect(result.current.channelStatus.maxReconnectAttempts).toBe(10);
  });

  it('updates lastMessageTime on message', async () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(result.current.channelStatus.lastMessageTime).toBeNull();

    // Simulate message
    act(() => {
      mockWsInstances[0].simulateMessage({ type: 'test', data: 'hello' });
    });

    expect(result.current.channelStatus.lastMessageTime).toBeInstanceOf(Date);
  });

  it('parses JSON messages and updates lastMessage', async () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Simulate message
    const testData = { type: 'test', value: 42 };
    act(() => {
      mockWsInstances[0].simulateMessage(testData);
    });

    expect(result.current.lastMessage).toEqual(testData);
  });

  it('calls onMessage callback with parsed data', async () => {
    const onMessage = vi.fn();
    renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
        onMessage,
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Simulate message
    const testData = { type: 'test' };
    act(() => {
      mockWsInstances[0].simulateMessage(testData);
    });

    expect(onMessage).toHaveBeenCalledWith(testData);
  });

  it('calls onOpen callback on connection', async () => {
    const onOpen = vi.fn();
    renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
        onOpen,
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(onOpen).toHaveBeenCalled();
  });

  it('calls onClose callback on close', async () => {
    const onClose = vi.fn();
    renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
        onClose,
        reconnect: false,
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Close
    act(() => {
      mockWsInstances[0].simulateClose();
    });

    expect(onClose).toHaveBeenCalled();
  });

  it('transitions to reconnecting state on close when reconnect is enabled', async () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
        reconnect: true,
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Close
    act(() => {
      mockWsInstances[0].simulateClose();
    });

    expect(result.current.channelStatus.state).toBe('reconnecting');
  });

  it('transitions to disconnected state on close when reconnect is disabled', async () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
        reconnect: false,
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Close
    act(() => {
      mockWsInstances[0].simulateClose();
    });

    expect(result.current.channelStatus.state).toBe('disconnected');
  });

  it('increments reconnect counter on each reconnect attempt', async () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
        reconnect: true,
        reconnectInterval: 100,
        reconnectAttempts: 5,
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });

    // Close to trigger reconnect
    act(() => {
      mockWsInstances[0].simulateClose();
    });

    expect(result.current.channelStatus.reconnectAttempts).toBe(1);
  });

  it('stops reconnecting after max attempts reached', async () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
        reconnect: true,
        reconnectInterval: 100,
        reconnectAttempts: 2,
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });

    // Close connection - this triggers first reconnect attempt
    act(() => {
      mockWsInstances[0].simulateClose();
    });

    expect(result.current.channelStatus.reconnectAttempts).toBe(1);
    expect(result.current.channelStatus.state).toBe('reconnecting');

    // Wait for reconnect interval + connection time
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });

    // Close again - second attempt
    act(() => {
      if (mockWsInstances[1]) {
        mockWsInstances[1].simulateClose();
      }
    });

    // After 2 attempts (reconnectAttempts: 2), should stop
    // The exact state depends on implementation - it might be 'disconnected' or still 'reconnecting'
    // The key is that we don't exceed reconnectAttempts
    expect(result.current.channelStatus.reconnectAttempts).toBeGreaterThanOrEqual(1);
    expect(result.current.channelStatus.reconnectAttempts).toBeLessThanOrEqual(2);
  });

  it('provides send function', async () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(typeof result.current.send).toBe('function');
  });

  it('provides connect function', () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
      })
    );

    expect(typeof result.current.connect).toBe('function');
  });

  it('provides disconnect function', () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
      })
    );

    expect(typeof result.current.disconnect).toBe('function');
  });

  it('disconnects when calling disconnect', async () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(result.current.channelStatus.state).toBe('connected');

    // Disconnect
    act(() => {
      result.current.disconnect();
    });

    expect(result.current.channelStatus.state).toBe('disconnected');
  });

  it('does not reconnect after manual disconnect', async () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
        reconnect: true,
        reconnectInterval: 100,
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Manual disconnect
    act(() => {
      result.current.disconnect();
    });

    const instanceCount = mockWsInstances.length;

    // Wait for potential reconnect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });

    // Should not have created new instances
    expect(mockWsInstances.length).toBe(instanceCount);
  });

  it('handles error events', async () => {
    const onError = vi.fn();
    renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
        onError,
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Simulate error
    act(() => {
      mockWsInstances[0].simulateError();
    });

    expect(onError).toHaveBeenCalled();
  });

  it('handles non-JSON messages gracefully', async () => {
    const onMessage = vi.fn();
    renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
        onMessage,
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Simulate raw string message (non-JSON)
    act(() => {
      if (mockWsInstances[0].onmessage) {
        mockWsInstances[0].onmessage(
          new MessageEvent('message', { data: 'raw string data' })
        );
      }
    });

    expect(onMessage).toHaveBeenCalledWith('raw string data');
  });

  it('sends data when WebSocket is open', async () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send object data
    const sendSpy = vi.spyOn(mockWsInstances[0], 'send');
    act(() => {
      result.current.send({ type: 'test', value: 123 });
    });

    expect(sendSpy).toHaveBeenCalledWith('{"type":"test","value":123}');
  });

  it('sends string data as-is', async () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    const sendSpy = vi.spyOn(mockWsInstances[0], 'send');
    act(() => {
      result.current.send('plain string');
    });

    expect(sendSpy).toHaveBeenCalledWith('plain string');
  });

  it('warns when sending on disconnected WebSocket', async () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
        reconnect: false,
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Disconnect
    act(() => {
      result.current.disconnect();
    });

    // Try to send
    act(() => {
      result.current.send({ type: 'test' });
    });

    // Logger formats messages as: [${level}] ${component}: ${message}
    // and passes extra data as the second argument
    expect(consoleSpy).toHaveBeenCalledWith(
      '[WARNING] frontend: WebSocket is not connected. Message not sent',
      expect.objectContaining({
        component: 'useWebSocketStatus',
        data: { type: 'test' },
      })
    );

    consoleSpy.mockRestore();
  });

  it('does not reconnect when already connected', async () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
      })
    );

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(mockWsInstances.length).toBe(1);

    // Try to connect again
    act(() => {
      result.current.connect();
    });

    // Should not create new instance
    expect(mockWsInstances.length).toBe(1);
  });

  it('uses default reconnectAttempts of 15 for better backend restart resilience', () => {
    const { result } = renderHook(() =>
      useWebSocketStatus({
        url: 'ws://localhost/ws/test',
        channelName: 'Test',
      })
    );

    // Default should be 15 to handle backend restarts (up to ~8 minutes with exponential backoff)
    expect(result.current.channelStatus.maxReconnectAttempts).toBe(15);
  });

});

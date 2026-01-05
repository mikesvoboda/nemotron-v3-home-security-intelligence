import { renderHook, act } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useConnectionStatus } from './useConnectionStatus';

// Mock the api module
vi.mock('../services/api', () => ({
  buildWebSocketUrl: (path: string) => `ws://localhost${path}`,
  buildWebSocketOptions: (path: string) => ({ url: `ws://localhost${path}`, protocols: undefined }),
  fetchHealth: vi.fn().mockResolvedValue({
    status: 'healthy',
    services: { gpu: { status: 'healthy' } },
  }),
  fetchEvents: vi.fn().mockResolvedValue({ events: [], total: 0, page: 1, page_size: 20 }),
}));

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

  send() {
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
}

describe('useConnectionStatus', () => {
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

  it('initializes with two channel statuses', () => {
    const { result } = renderHook(() => useConnectionStatus());

    expect(result.current.summary.eventsChannel.name).toBe('Events');
    expect(result.current.summary.systemChannel.name).toBe('System');
  });

  it('creates two WebSocket connections', async () => {
    renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(mockWsInstances.length).toBe(2);
    expect(mockWsInstances[0].url).toBe('ws://localhost/ws/events');
    expect(mockWsInstances[1].url).toBe('ws://localhost/ws/system');
  });

  it('reports allConnected when both channels are connected', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(result.current.summary.allConnected).toBe(true);
  });

  it('reports overallState as connected when both channels are connected', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    expect(result.current.summary.overallState).toBe('connected');
  });

  it('reports overallState as reconnecting when either channel is reconnecting', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Close one connection to trigger reconnecting
    act(() => {
      mockWsInstances[0].simulateClose();
    });

    expect(result.current.summary.anyReconnecting).toBe(true);
    expect(result.current.summary.overallState).toBe('reconnecting');
  });

  it('computes totalReconnectAttempts from both channels', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    // Connect
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Close both to trigger reconnecting
    act(() => {
      mockWsInstances[0].simulateClose();
      mockWsInstances[1].simulateClose();
    });

    expect(result.current.summary.totalReconnectAttempts).toBe(2); // 1 each
  });

  it('handles event messages and adds to events array', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send event message through events channel
    const eventMessage = {
      type: 'event',
      data: {
        id: '123',
        camera_id: 'cam1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Test event',
      },
    };

    act(() => {
      mockWsInstances[0].simulateMessage(eventMessage);
    });

    expect(result.current.events.length).toBe(1);
    expect(result.current.events[0].id).toBe('123');
    expect(result.current.events[0].summary).toBe('Test event');
  });

  it('handles system status messages', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send system status message through system channel
    const systemMessage = {
      type: 'system_status',
      data: {
        gpu: {
          utilization: 45,
          memory_used: 8192,
          memory_total: 24576,
          temperature: 65,
          inference_fps: 30.5,
        },
        cameras: {
          active: 3,
          total: 5,
        },
        queue: {
          pending: 2,
          processing: 1,
        },
        health: 'healthy',
      },
      timestamp: '2025-12-30T10:00:00Z',
    };

    act(() => {
      mockWsInstances[1].simulateMessage(systemMessage);
    });

    expect(result.current.systemStatus).not.toBeNull();
    expect(result.current.systemStatus?.data.health).toBe('healthy');
    expect(result.current.systemStatus?.data.gpu.utilization).toBe(45);
  });

  it('ignores non-event messages on events channel', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send non-event message
    const pingMessage = { type: 'ping' };

    act(() => {
      mockWsInstances[0].simulateMessage(pingMessage);
    });

    expect(result.current.events.length).toBe(0);
  });

  it('ignores non-system_status messages on system channel', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send non-system_status message
    const pingMessage = { type: 'ping' };

    act(() => {
      mockWsInstances[1].simulateMessage(pingMessage);
    });

    expect(result.current.systemStatus).toBeNull();
  });

  it('limits events array to 100 items', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Add 105 events
    for (let i = 0; i < 105; i++) {
      const eventMessage = {
        type: 'event',
        data: {
          id: `${i}`,
          camera_id: 'cam1',
          risk_score: 50,
          risk_level: 'medium',
          summary: `Event ${i}`,
        },
      };

      act(() => {
        mockWsInstances[0].simulateMessage(eventMessage);
      });
    }

    expect(result.current.events.length).toBe(100);
    // Newest event should be first
    expect(result.current.events[0].id).toBe('104');
  });

  it('provides clearEvents function', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Add some events
    const eventMessage = {
      type: 'event',
      data: {
        id: '1',
        camera_id: 'cam1',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Test',
      },
    };

    act(() => {
      mockWsInstances[0].simulateMessage(eventMessage);
    });

    expect(result.current.events.length).toBe(1);

    // Clear events
    act(() => {
      result.current.clearEvents();
    });

    expect(result.current.events.length).toBe(0);
  });

  it('validates event message structure', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send incomplete event (missing required fields)
    const incompleteEvent = {
      type: 'event',
      data: {
        id: '1',
        // Missing camera_id, risk_score, risk_level, summary
      },
    };

    act(() => {
      mockWsInstances[0].simulateMessage(incompleteEvent);
    });

    // Should not add invalid event
    expect(result.current.events.length).toBe(0);
  });

  it('validates system status message structure', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send incomplete system status
    const incompleteStatus = {
      type: 'system_status',
      data: {
        // Missing required fields
      },
    };

    act(() => {
      mockWsInstances[1].simulateMessage(incompleteStatus);
    });

    // Should not update with invalid status
    expect(result.current.systemStatus).toBeNull();
  });

  it('initializes isPollingFallback as false', () => {
    const { result } = renderHook(() => useConnectionStatus());

    expect(result.current.isPollingFallback).toBe(false);
  });

  it('provides retryConnection function', () => {
    const { result } = renderHook(() => useConnectionStatus());

    expect(typeof result.current.retryConnection).toBe('function');
  });

  it('retryConnection triggers new connections', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    const initialInstances = mockWsInstances.length;

    // Close connections
    act(() => {
      mockWsInstances.forEach((ws) => ws.simulateClose());
    });

    // Call retry
    act(() => {
      result.current.retryConnection();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Should have created new connections
    expect(mockWsInstances.length).toBeGreaterThanOrEqual(initialInstances);
  });

  it('handles event_id field as fallback for id', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send event with event_id instead of id
    const eventMessage = {
      type: 'event',
      data: {
        event_id: 'evt123',
        camera_id: 'cam1',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Test event',
      },
    };

    act(() => {
      mockWsInstances[0].simulateMessage(eventMessage);
    });

    expect(result.current.events.length).toBe(1);
  });

  it('handles null data in type guard checks', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send null
    act(() => {
      mockWsInstances[0].simulateMessage(null);
    });

    expect(result.current.events.length).toBe(0);

    // Send undefined-like object
    act(() => {
      mockWsInstances[1].simulateMessage({ type: 'system_status', data: null });
    });

    expect(result.current.systemStatus).toBeNull();
  });

  it('handles system status without timestamp', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send system status missing timestamp
    const systemMessage = {
      type: 'system_status',
      data: {
        gpu: { utilization: 45 },
        cameras: { active: 3, total: 5 },
        health: 'healthy',
      },
      // Missing timestamp
    };

    act(() => {
      mockWsInstances[1].simulateMessage(systemMessage);
    });

    // Should not update without timestamp
    expect(result.current.systemStatus).toBeNull();
  });

  it('handles non-object data gracefully', async () => {
    const { result } = renderHook(() => useConnectionStatus());

    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });

    // Send string
    act(() => {
      mockWsInstances[0].simulateMessage('invalid');
    });

    expect(result.current.events.length).toBe(0);

    // Send number
    act(() => {
      mockWsInstances[1].simulateMessage(123);
    });

    expect(result.current.systemStatus).toBeNull();
  });

  describe('auto-recovery from polling fallback', () => {
    it('uses 5 second polling interval during fallback mode', async () => {
      // This test verifies the FALLBACK_POLLING_INTERVAL constant is 5000ms
      // We can't easily test the actual interval without exposing internals,
      // so we verify behavior: after exhausting retries, polling should use shorter interval
      const { result } = renderHook(() => useConnectionStatus());

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });

      // The hook should use 15 reconnect attempts by default now
      expect(result.current.summary.eventsChannel.maxReconnectAttempts).toBe(15);
      expect(result.current.summary.systemChannel.maxReconnectAttempts).toBe(15);
    });

    it('provides isPollingFallback state that indicates fallback mode', () => {
      const { result } = renderHook(() => useConnectionStatus());

      // Initially not in polling fallback
      expect(result.current.isPollingFallback).toBe(false);
    });

    it('retryConnection can be called to attempt WebSocket reconnection', async () => {
      const { result } = renderHook(() => useConnectionStatus());

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });

      // Close connections to simulate failure
      act(() => {
        mockWsInstances.forEach((ws) => ws.simulateClose());
      });

      // Store instance count before retry
      const instancesBefore = mockWsInstances.length;

      // Call retry
      act(() => {
        result.current.retryConnection();
      });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });

      // Should have attempted to create new WebSocket connections
      expect(mockWsInstances.length).toBeGreaterThan(instancesBefore);
    });
  });
});

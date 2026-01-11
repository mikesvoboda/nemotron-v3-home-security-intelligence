import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useCircuitBreakerStatus, CircuitBreakerStateType } from './useCircuitBreakerStatus';
import * as useWebSocketModule from './useWebSocket';

/**
 * Tests for useCircuitBreakerStatus hook.
 *
 * This hook tracks circuit breaker states (closed, open, half_open) via WebSocket
 * messages broadcast by the backend's SystemBroadcaster.
 */
describe('useCircuitBreakerStatus', () => {
  const mockWebSocketReturn = {
    isConnected: true,
    lastMessage: null,
    send: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    hasExhaustedRetries: false,
    reconnectCount: 0,
    lastHeartbeat: null,
  };

  let onMessageCallback: ((data: unknown) => void) | undefined;

  // Helper to create a circuit breaker update message matching backend format
  const createCircuitBreakerUpdateMessage = (
    breakers: Record<
      string,
      {
        state: CircuitBreakerStateType;
        failure_count: number;
        success_count: number;
        last_failure_time?: string | null;
      }
    >,
    timestamp: string = '2026-01-08T10:00:00Z'
  ) => {
    // Calculate summary from breakers
    let closed = 0;
    let open = 0;
    let half_open = 0;

    for (const breaker of Object.values(breakers)) {
      if (breaker.state === 'closed') closed++;
      else if (breaker.state === 'open') open++;
      else if (breaker.state === 'half_open') half_open++;
    }

    return {
      type: 'circuit_breaker_update',
      data: {
        timestamp,
        summary: {
          total: Object.keys(breakers).length,
          closed,
          open,
          half_open,
        },
        breakers,
      },
    };
  };

  beforeEach(() => {
    // Mock useWebSocket to capture the onMessage callback
    vi.spyOn(useWebSocketModule, 'useWebSocket').mockImplementation((options) => {
      onMessageCallback = options.onMessage;
      return mockWebSocketReturn;
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
    onMessageCallback = undefined;
  });

  it('should initialize with empty breakers and zero summary', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    expect(result.current.breakers).toEqual({});
    expect(result.current.summary).toEqual({
      total: 0,
      closed: 0,
      open: 0,
      half_open: 0,
    });
    expect(result.current.hasOpenBreaker).toBe(false);
    expect(result.current.hasHalfOpenBreaker).toBe(false);
    expect(result.current.allClosed).toBe(false); // No breakers means allClosed is false
    expect(result.current.lastUpdate).toBeNull();
  });

  it('should update state on websocket message', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    const message = createCircuitBreakerUpdateMessage({
      rtdetr: { state: 'closed', failure_count: 0, success_count: 5 },
      nemotron: { state: 'closed', failure_count: 0, success_count: 10 },
    });

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.breakers).toHaveProperty('rtdetr');
    expect(result.current.breakers).toHaveProperty('nemotron');
    expect(result.current.breakers.rtdetr?.state).toBe('closed');
    expect(result.current.breakers.nemotron?.state).toBe('closed');
    expect(result.current.summary.total).toBe(2);
    expect(result.current.summary.closed).toBe(2);
    expect(result.current.lastUpdate).toBe('2026-01-08T10:00:00Z');
  });

  it('should return hasOpenBreaker true when any breaker is open', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    const message = createCircuitBreakerUpdateMessage({
      rtdetr: { state: 'closed', failure_count: 0, success_count: 5 },
      nemotron: { state: 'open', failure_count: 5, success_count: 0 },
    });

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.hasOpenBreaker).toBe(true);
    expect(result.current.summary.open).toBe(1);
  });

  it('should return hasOpenBreaker false when no breaker is open', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    const message = createCircuitBreakerUpdateMessage({
      rtdetr: { state: 'closed', failure_count: 0, success_count: 5 },
      nemotron: { state: 'half_open', failure_count: 3, success_count: 1 },
    });

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.hasOpenBreaker).toBe(false);
    expect(result.current.summary.open).toBe(0);
  });

  it('should return hasHalfOpenBreaker true when any breaker is half_open', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    const message = createCircuitBreakerUpdateMessage({
      rtdetr: { state: 'closed', failure_count: 0, success_count: 5 },
      nemotron: { state: 'half_open', failure_count: 3, success_count: 1 },
    });

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.hasHalfOpenBreaker).toBe(true);
    expect(result.current.summary.half_open).toBe(1);
  });

  it('should return hasHalfOpenBreaker false when no breaker is half_open', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    const message = createCircuitBreakerUpdateMessage({
      rtdetr: { state: 'closed', failure_count: 0, success_count: 5 },
      nemotron: { state: 'closed', failure_count: 0, success_count: 10 },
    });

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.hasHalfOpenBreaker).toBe(false);
    expect(result.current.summary.half_open).toBe(0);
  });

  it('should return allClosed true when all breakers are closed', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    const message = createCircuitBreakerUpdateMessage({
      rtdetr: { state: 'closed', failure_count: 0, success_count: 5 },
      nemotron: { state: 'closed', failure_count: 0, success_count: 10 },
      redis: { state: 'closed', failure_count: 0, success_count: 3 },
    });

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.allClosed).toBe(true);
    expect(result.current.summary.closed).toBe(3);
    expect(result.current.summary.total).toBe(3);
  });

  it('should return allClosed false when any breaker is not closed', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    const message = createCircuitBreakerUpdateMessage({
      rtdetr: { state: 'closed', failure_count: 0, success_count: 5 },
      nemotron: { state: 'open', failure_count: 5, success_count: 0 },
    });

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.allClosed).toBe(false);
  });

  it('should return correct breaker via getBreaker', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    const message = createCircuitBreakerUpdateMessage({
      rtdetr: { state: 'closed', failure_count: 0, success_count: 5 },
      nemotron: { state: 'open', failure_count: 5, success_count: 0, last_failure_time: '2026-01-08T09:55:00Z' },
    });

    act(() => {
      onMessageCallback?.(message);
    });

    const rtdetrBreaker = result.current.getBreaker('rtdetr');
    expect(rtdetrBreaker).toEqual({
      name: 'rtdetr',
      state: 'closed',
      failure_count: 0,
      success_count: 5,
      last_failure_time: undefined,
    });

    const nemotronBreaker = result.current.getBreaker('nemotron');
    expect(nemotronBreaker).toEqual({
      name: 'nemotron',
      state: 'open',
      failure_count: 5,
      success_count: 0,
      last_failure_time: '2026-01-08T09:55:00Z',
    });

    expect(result.current.getBreaker('unknown')).toBeNull();
  });

  it('should filter non-circuit-breaker-update messages', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    const nonCircuitBreakerMessages = [
      { type: 'system_status', data: { health: 'healthy' } },
      { type: 'service_status', data: { service: 'rtdetr', status: 'healthy' } },
      { type: 'event', data: { id: 1 } },
      { type: 'ping' },
      null,
      undefined,
      'string message',
      42,
      [],
    ];

    act(() => {
      nonCircuitBreakerMessages.forEach((msg) => onMessageCallback?.(msg));
    });

    expect(result.current.breakers).toEqual({});
    expect(result.current.summary.total).toBe(0);
  });

  it('should connect to the correct WebSocket URL (/ws/system)', () => {
    renderHook(() => useCircuitBreakerStatus());

    // useCircuitBreakerStatus connects to /ws/system because circuit_breaker_update
    // messages are broadcast via SystemBroadcaster (used by /ws/system)
    expect(useWebSocketModule.useWebSocket).toHaveBeenCalledWith(
      expect.objectContaining({
        url: expect.stringContaining('/ws/system'),
        onMessage: expect.any(Function),
      })
    );
  });

  it('should update breaker states when same breakers send new states', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    // Initial state - all closed
    act(() => {
      onMessageCallback?.(
        createCircuitBreakerUpdateMessage(
          {
            rtdetr: { state: 'closed', failure_count: 0, success_count: 5 },
            nemotron: { state: 'closed', failure_count: 0, success_count: 10 },
          },
          '2026-01-08T10:00:00Z'
        )
      );
    });

    expect(result.current.breakers.rtdetr?.state).toBe('closed');
    expect(result.current.allClosed).toBe(true);

    // rtdetr transitions to open
    act(() => {
      onMessageCallback?.(
        createCircuitBreakerUpdateMessage(
          {
            rtdetr: { state: 'open', failure_count: 5, success_count: 0 },
            nemotron: { state: 'closed', failure_count: 0, success_count: 10 },
          },
          '2026-01-08T10:01:00Z'
        )
      );
    });

    expect(result.current.breakers.rtdetr?.state).toBe('open');
    expect(result.current.breakers.rtdetr?.failure_count).toBe(5);
    expect(result.current.allClosed).toBe(false);
    expect(result.current.hasOpenBreaker).toBe(true);
    expect(result.current.lastUpdate).toBe('2026-01-08T10:01:00Z');
  });

  it('should handle all three circuit breaker states', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    const states: CircuitBreakerStateType[] = ['closed', 'open', 'half_open'];

    states.forEach((state, index) => {
      act(() => {
        onMessageCallback?.(
          createCircuitBreakerUpdateMessage(
            {
              test_breaker: { state, failure_count: index, success_count: 3 - index },
            },
            `2026-01-08T10:0${index}:00Z`
          )
        );
      });

      expect(result.current.breakers.test_breaker?.state).toBe(state);
    });
  });

  it('should handle rapid successive state updates', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    for (let i = 0; i < 10; i++) {
      const state: CircuitBreakerStateType = i % 3 === 0 ? 'closed' : i % 3 === 1 ? 'open' : 'half_open';
      const message = createCircuitBreakerUpdateMessage(
        {
          rtdetr: { state, failure_count: i, success_count: 10 - i },
        },
        `2026-01-08T10:00:${String(i).padStart(2, '0')}Z`
      );

      act(() => {
        onMessageCallback?.(message);
      });
    }

    // Should have the last state (i=9, 9 % 3 = 0, so 'closed')
    expect(result.current.breakers.rtdetr?.state).toBe('closed');
    expect(result.current.breakers.rtdetr?.failure_count).toBe(9);
    expect(result.current.lastUpdate).toBe('2026-01-08T10:00:09Z');
  });

  it('should maintain handleMessage callback stability', () => {
    const { rerender } = renderHook(() => useCircuitBreakerStatus());

    const firstCallback = onMessageCallback;

    rerender();

    const secondCallback = onMessageCallback;

    // useCallback should maintain the same reference
    expect(firstCallback).toBe(secondCallback);
  });

  it('should not mutate received message object', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    const originalMessage = createCircuitBreakerUpdateMessage({
      rtdetr: { state: 'closed', failure_count: 0, success_count: 5 },
    });
    const messageCopy = JSON.parse(JSON.stringify(originalMessage));

    act(() => {
      onMessageCallback?.(originalMessage);
    });

    expect(result.current.breakers.rtdetr?.state).toBe('closed');
    expect(originalMessage).toEqual(messageCopy);
  });

  it('should handle message with null last_failure_time', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    const message = createCircuitBreakerUpdateMessage({
      rtdetr: { state: 'closed', failure_count: 0, success_count: 5, last_failure_time: null },
    });

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.breakers.rtdetr?.last_failure_time).toBeNull();
  });

  it('should handle multiple breakers with mixed states', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    const message = createCircuitBreakerUpdateMessage({
      rtdetr: { state: 'closed', failure_count: 0, success_count: 5 },
      nemotron: { state: 'open', failure_count: 5, success_count: 0 },
      redis: { state: 'half_open', failure_count: 3, success_count: 1 },
      image_processor: { state: 'closed', failure_count: 1, success_count: 10 },
    });

    act(() => {
      onMessageCallback?.(message);
    });

    expect(result.current.summary.total).toBe(4);
    expect(result.current.summary.closed).toBe(2);
    expect(result.current.summary.open).toBe(1);
    expect(result.current.summary.half_open).toBe(1);
    expect(result.current.hasOpenBreaker).toBe(true);
    expect(result.current.hasHalfOpenBreaker).toBe(true);
    expect(result.current.allClosed).toBe(false);
  });

  it('should handle transition from open to half_open to closed', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    // Start with open breaker
    act(() => {
      onMessageCallback?.(
        createCircuitBreakerUpdateMessage({
          rtdetr: { state: 'open', failure_count: 5, success_count: 0 },
        })
      );
    });

    expect(result.current.hasOpenBreaker).toBe(true);
    expect(result.current.hasHalfOpenBreaker).toBe(false);

    // Transition to half_open
    act(() => {
      onMessageCallback?.(
        createCircuitBreakerUpdateMessage({
          rtdetr: { state: 'half_open', failure_count: 5, success_count: 1 },
        })
      );
    });

    expect(result.current.hasOpenBreaker).toBe(false);
    expect(result.current.hasHalfOpenBreaker).toBe(true);

    // Transition to closed
    act(() => {
      onMessageCallback?.(
        createCircuitBreakerUpdateMessage({
          rtdetr: { state: 'closed', failure_count: 0, success_count: 3 },
        })
      );
    });

    expect(result.current.hasOpenBreaker).toBe(false);
    expect(result.current.hasHalfOpenBreaker).toBe(false);
    expect(result.current.allClosed).toBe(true);
  });

  it('should ignore messages with invalid structure', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    const invalidMessages = [
      // Missing type
      { data: { timestamp: '2026-01-08T10:00:00Z', summary: {}, breakers: {} } },
      // Wrong type
      { type: 'circuit_breaker_update_wrong', data: {} },
      // Missing data
      { type: 'circuit_breaker_update' },
      // Missing timestamp in data
      { type: 'circuit_breaker_update', data: { summary: {}, breakers: {} } },
      // Missing summary
      { type: 'circuit_breaker_update', data: { timestamp: '2026-01-08T10:00:00Z', breakers: {} } },
      // Invalid summary (missing fields)
      {
        type: 'circuit_breaker_update',
        data: { timestamp: '2026-01-08T10:00:00Z', summary: { total: 1 }, breakers: {} },
      },
      // Invalid breaker state
      {
        type: 'circuit_breaker_update',
        data: {
          timestamp: '2026-01-08T10:00:00Z',
          summary: { total: 1, closed: 1, open: 0, half_open: 0 },
          breakers: { test: { state: 'invalid_state', failure_count: 0, success_count: 0 } },
        },
      },
      // Missing failure_count in breaker
      {
        type: 'circuit_breaker_update',
        data: {
          timestamp: '2026-01-08T10:00:00Z',
          summary: { total: 1, closed: 1, open: 0, half_open: 0 },
          breakers: { test: { state: 'closed', success_count: 0 } },
        },
      },
    ];

    invalidMessages.forEach((msg) => {
      act(() => {
        onMessageCallback?.(msg);
      });
    });

    // State should remain unchanged (initial state)
    expect(result.current.breakers).toEqual({});
    expect(result.current.summary.total).toBe(0);
  });

  it('should expose isConnected from WebSocket', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    expect(result.current.isConnected).toBe(true);
  });

  it('should handle isConnected false when WebSocket disconnected', () => {
    // Override mock to return disconnected state
    vi.spyOn(useWebSocketModule, 'useWebSocket').mockImplementation((options) => {
      onMessageCallback = options.onMessage;
      return {
        ...mockWebSocketReturn,
        isConnected: false,
      };
    });

    const { result } = renderHook(() => useCircuitBreakerStatus());

    expect(result.current.isConnected).toBe(false);
  });

  it('should return allClosed false when there are no breakers', () => {
    const { result } = renderHook(() => useCircuitBreakerStatus());

    // No messages received - no breakers
    expect(result.current.allClosed).toBe(false);
    expect(result.current.summary.total).toBe(0);

    // Empty breakers message
    const message = createCircuitBreakerUpdateMessage({});

    act(() => {
      onMessageCallback?.(message);
    });

    // Still false because total is 0
    expect(result.current.allClosed).toBe(false);
  });
});

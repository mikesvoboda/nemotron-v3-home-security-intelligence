import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useEventStream, SecurityEvent } from './useEventStream';
import * as useWebSocketModule from './useWebSocket';

// Helper to wrap event data in the backend envelope format
function wrapInEnvelope(event: SecurityEvent): { type: 'event'; data: SecurityEvent } {
  return { type: 'event', data: event };
}

describe('useEventStream', () => {
  const mockWebSocketReturn = {
    isConnected: true,
    lastMessage: null,
    send: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
  };

  let onMessageCallback: ((data: unknown) => void) | undefined;

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

  it('should initialize with empty events array', () => {
    const { result } = renderHook(() => useEventStream());

    expect(result.current.events).toEqual([]);
    expect(result.current.latestEvent).toBeNull();
    expect(result.current.isConnected).toBe(true);
  });

  it('should connect to the correct WebSocket URL', () => {
    renderHook(() => useEventStream());

    expect(useWebSocketModule.useWebSocket).toHaveBeenCalledWith(
      expect.objectContaining({
        url: expect.stringContaining('/ws/events'),
        onMessage: expect.any(Function),
      })
    );
  });

  it('should add valid security events from envelope format to the events array', () => {
    const { result } = renderHook(() => useEventStream());

    const event: SecurityEvent = {
      id: 1,
      event_id: 1,
      batch_id: 'batch_123',
      camera_id: 'front_door',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Person detected at front door',
      started_at: '2025-12-27T14:30:00',
    };

    act(() => {
      onMessageCallback?.(wrapInEnvelope(event));
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0]).toEqual(event);
    expect(result.current.latestEvent).toEqual(event);
  });

  it('should add multiple events in correct order (newest first)', () => {
    const { result } = renderHook(() => useEventStream());

    const event1: SecurityEvent = {
      id: 1,
      camera_id: 'cam-1',
      risk_score: 50,
      risk_level: 'medium',
      summary: 'Event 1',
      started_at: '2025-12-23T10:00:00Z',
    };

    const event2: SecurityEvent = {
      id: 2,
      camera_id: 'cam-2',
      risk_score: 80,
      risk_level: 'high',
      summary: 'Event 2',
      started_at: '2025-12-23T10:05:00Z',
    };

    act(() => {
      onMessageCallback?.(wrapInEnvelope(event1));
    });

    act(() => {
      onMessageCallback?.(wrapInEnvelope(event2));
    });

    expect(result.current.events).toHaveLength(2);
    expect(result.current.events[0]).toEqual(event2); // Newest first
    expect(result.current.events[1]).toEqual(event1);
    expect(result.current.latestEvent).toEqual(event2);
  });

  it('should enforce MAX_EVENTS limit (100)', () => {
    const { result } = renderHook(() => useEventStream());

    // Add 110 events
    act(() => {
      for (let i = 0; i < 110; i++) {
        const event: SecurityEvent = {
          id: i,
          camera_id: 'cam-' + i,
          risk_score: 50,
          risk_level: 'medium',
          summary: 'Event ' + i,
          started_at: '2025-12-23T10:' + String(i).padStart(2, '0') + ':00Z',
        };
        onMessageCallback?.(wrapInEnvelope(event));
      }
    });

    expect(result.current.events).toHaveLength(100);
    expect(result.current.events[0].id).toBe(109); // Most recent
    expect(result.current.events[99].id).toBe(10); // Oldest kept
  });

  it('should ignore messages without envelope format', () => {
    const { result } = renderHook(() => useEventStream());

    // Try sending event directly without envelope - should be ignored
    const rawEvent: SecurityEvent = {
      id: 1,
      camera_id: 'cam-1',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Test event',
      started_at: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(rawEvent);
    });

    expect(result.current.events).toHaveLength(0);
    expect(result.current.latestEvent).toBeNull();
  });

  it('should ignore non-event message types (e.g., service_status)', () => {
    const { result } = renderHook(() => useEventStream());

    const serviceStatusMessage = {
      type: 'service_status',
      data: {
        service: 'detector',
        status: 'healthy',
      },
    };

    const pingMessage = {
      type: 'ping',
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(serviceStatusMessage);
      onMessageCallback?.(pingMessage);
    });

    expect(result.current.events).toHaveLength(0);
    expect(result.current.latestEvent).toBeNull();
  });

  it('should ignore invalid messages missing required fields', () => {
    const { result } = renderHook(() => useEventStream());

    const invalidMessages = [
      { type: 'event', data: { id: 1 } }, // Missing other fields
      { type: 'event', data: { camera_id: 'cam-1' } }, // Missing id, risk fields
      { type: 'event', data: null },
      { type: 'event' }, // No data
      null,
      undefined,
      'string message',
      42,
      [],
    ];

    act(() => {
      invalidMessages.forEach((msg) => onMessageCallback?.(msg));
    });

    expect(result.current.events).toHaveLength(0);
    expect(result.current.latestEvent).toBeNull();
  });

  it('should ignore messages with partial SecurityEvent fields in data', () => {
    const { result } = renderHook(() => useEventStream());

    const partialEventMessage = {
      type: 'event',
      data: {
        id: 1,
        camera_id: 'cam-1',
        risk_score: 75,
        // Missing risk_level, summary
      },
    };

    act(() => {
      onMessageCallback?.(partialEventMessage);
    });

    expect(result.current.events).toHaveLength(0);
    expect(result.current.latestEvent).toBeNull();
  });

  it('should clear all events when clearEvents is called', () => {
    const { result } = renderHook(() => useEventStream());

    const event: SecurityEvent = {
      id: 1,
      camera_id: 'cam-1',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Test event',
      started_at: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(wrapInEnvelope(event));
    });

    expect(result.current.events).toHaveLength(1);

    act(() => {
      result.current.clearEvents();
    });

    expect(result.current.events).toEqual([]);
    expect(result.current.latestEvent).toBeNull();
  });

  it('should update latestEvent when new events arrive', () => {
    const { result } = renderHook(() => useEventStream());

    const event1: SecurityEvent = {
      id: 1,
      camera_id: 'cam-1',
      risk_score: 50,
      risk_level: 'medium',
      summary: 'Event 1',
      started_at: '2025-12-23T10:00:00Z',
    };

    const event2: SecurityEvent = {
      id: 2,
      camera_id: 'cam-2',
      risk_score: 80,
      risk_level: 'high',
      summary: 'Event 2',
      started_at: '2025-12-23T10:05:00Z',
    };

    act(() => {
      onMessageCallback?.(wrapInEnvelope(event1));
    });

    expect(result.current.latestEvent).toEqual(event1);

    act(() => {
      onMessageCallback?.(wrapInEnvelope(event2));
    });

    expect(result.current.latestEvent).toEqual(event2);
  });

  it('should reflect connection status from useWebSocket', () => {
    const { result, rerender } = renderHook(() => useEventStream());

    expect(result.current.isConnected).toBe(true);

    // Update mock to return disconnected state
    mockWebSocketReturn.isConnected = false;
    rerender();

    expect(result.current.isConnected).toBe(false);
  });

  it('should handle all risk levels correctly', () => {
    const { result } = renderHook(() => useEventStream());

    const riskLevels = ['low', 'medium', 'high', 'critical'] as const;

    riskLevels.forEach((level, index: number) => {
      const event: SecurityEvent = {
        id: index,
        camera_id: 'cam-' + index,
        risk_score: 25 * (index + 1),
        risk_level: level,
        summary: level + ' risk event',
        started_at: '2025-12-23T10:' + String(index).padStart(2, '0') + ':00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInEnvelope(event));
      });
    });

    expect(result.current.events).toHaveLength(4);
    const reversedLevels = [...riskLevels].reverse();
    reversedLevels.forEach((level, index: number) => {
      expect(result.current.events[index].risk_level).toBe(level);
    });
  });

  it('should maintain immutability of events array', () => {
    const { result } = renderHook(() => useEventStream());

    const event1: SecurityEvent = {
      id: 1,
      camera_id: 'cam-1',
      risk_score: 50,
      risk_level: 'medium',
      summary: 'Event 1',
      started_at: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(wrapInEnvelope(event1));
    });

    const firstEventsRef = result.current.events;

    const event2: SecurityEvent = {
      id: 2,
      camera_id: 'cam-2',
      risk_score: 80,
      risk_level: 'high',
      summary: 'Event 2',
      started_at: '2025-12-23T10:05:00Z',
    };

    act(() => {
      onMessageCallback?.(wrapInEnvelope(event2));
    });

    const secondEventsRef = result.current.events;

    // Should be a new array reference
    expect(firstEventsRef).not.toBe(secondEventsRef);
    // Original array should be unchanged
    expect(firstEventsRef).toHaveLength(1);
    // New array should have both events
    expect(secondEventsRef).toHaveLength(2);
  });

  it('should memoize latestEvent correctly', () => {
    const { result, rerender } = renderHook(() => useEventStream());

    expect(result.current.latestEvent).toBeNull();

    const event: SecurityEvent = {
      id: 1,
      camera_id: 'cam-1',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Test event',
      started_at: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(wrapInEnvelope(event));
    });

    const firstLatestEvent = result.current.latestEvent;
    expect(firstLatestEvent).toEqual(event);

    // Rerender without changes
    rerender();

    // Should return the same reference
    expect(result.current.latestEvent).toBe(firstLatestEvent);
  });

  it('should handle rapid successive events', () => {
    const { result } = renderHook(() => useEventStream());

    const events: SecurityEvent[] = [];
    for (let i = 0; i < 10; i++) {
      events.push({
        id: i,
        camera_id: 'cam-' + (i % 3), // Cycle through 3 cameras
        risk_score: 50 + i * 5,
        risk_level: 'medium',
        summary: 'Rapid event ' + i,
        started_at: '2025-12-23T10:00:' + String(i).padStart(2, '0') + 'Z',
      });
    }

    act(() => {
      events.forEach((event) => onMessageCallback?.(wrapInEnvelope(event)));
    });

    expect(result.current.events).toHaveLength(10);
    expect(result.current.events[0].id).toBe(9); // Most recent
    expect(result.current.events[9].id).toBe(0); // Oldest
  });

  it('should handle clearEvents being called multiple times', () => {
    const { result } = renderHook(() => useEventStream());

    const event: SecurityEvent = {
      id: 1,
      camera_id: 'cam-1',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Test event',
      started_at: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(wrapInEnvelope(event));
    });

    expect(result.current.events).toHaveLength(1);

    act(() => {
      result.current.clearEvents();
      result.current.clearEvents();
      result.current.clearEvents();
    });

    expect(result.current.events).toEqual([]);
  });

  it('should maintain clearEvents callback stability', () => {
    const { result, rerender } = renderHook(() => useEventStream());

    const firstClearEvents = result.current.clearEvents;

    rerender();

    const secondClearEvents = result.current.clearEvents;

    // useCallback should maintain the same reference
    expect(firstClearEvents).toBe(secondClearEvents);
  });

  it('should handle backend canonical message format', () => {
    const { result } = renderHook(() => useEventStream());

    // This is the exact format from the backend as documented
    const backendMessage = {
      type: 'event',
      data: {
        id: 1,
        event_id: 1,
        batch_id: 'batch_123',
        camera_id: 'front_door',
        risk_score: 75,
        risk_level: 'high' as const,
        summary: 'Person detected at front door',
        started_at: '2025-12-27T14:30:00',
      },
    };

    act(() => {
      onMessageCallback?.(backendMessage);
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0].id).toBe(1);
    expect(result.current.events[0].event_id).toBe(1);
    expect(result.current.events[0].batch_id).toBe('batch_123');
    expect(result.current.events[0].camera_id).toBe('front_door');
    expect(result.current.events[0].risk_score).toBe(75);
    expect(result.current.events[0].risk_level).toBe('high');
    expect(result.current.events[0].summary).toBe('Person detected at front door');
    expect(result.current.events[0].started_at).toBe('2025-12-27T14:30:00');
  });

  it('should accept events with event_id instead of id', () => {
    const { result } = renderHook(() => useEventStream());

    // Event with only event_id (no id field)
    const backendMessage = {
      type: 'event',
      data: {
        event_id: 42,
        camera_id: 'back_yard',
        risk_score: 30,
        risk_level: 'low' as const,
        summary: 'Motion detected',
      },
    };

    act(() => {
      onMessageCallback?.(backendMessage);
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0].event_id).toBe(42);
  });
});

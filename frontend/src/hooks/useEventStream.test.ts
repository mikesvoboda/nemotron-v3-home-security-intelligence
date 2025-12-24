import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import { useEventStream, SecurityEvent } from './useEventStream';
import * as useWebSocketModule from './useWebSocket';

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

  it('should add valid security events to the events array', () => {
    const { result } = renderHook(() => useEventStream());

    const event: SecurityEvent = {
      id: 'event-1',
      camera_id: 'cam-1',
      camera_name: 'Front Door',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Person detected at front door',
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(event);
    });

    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0]).toEqual(event);
    expect(result.current.latestEvent).toEqual(event);
  });

  it('should add multiple events in correct order (newest first)', () => {
    const { result } = renderHook(() => useEventStream());

    const event1: SecurityEvent = {
      id: 'event-1',
      camera_id: 'cam-1',
      camera_name: 'Front Door',
      risk_score: 50,
      risk_level: 'medium',
      summary: 'Event 1',
      timestamp: '2025-12-23T10:00:00Z',
    };

    const event2: SecurityEvent = {
      id: 'event-2',
      camera_id: 'cam-2',
      camera_name: 'Back Door',
      risk_score: 80,
      risk_level: 'high',
      summary: 'Event 2',
      timestamp: '2025-12-23T10:05:00Z',
    };

    act(() => {
      onMessageCallback?.(event1);
    });

    act(() => {
      onMessageCallback?.(event2);
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
          id: `event-${i}`,
          camera_id: `cam-${i}`,
          camera_name: `Camera ${i}`,
          risk_score: 50,
          risk_level: 'medium',
          summary: `Event ${i}`,
          timestamp: `2025-12-23T10:${String(i).padStart(2, '0')}:00Z`,
        };
        onMessageCallback?.(event);
      }
    });

    expect(result.current.events).toHaveLength(100);
    expect(result.current.events[0].id).toBe('event-109'); // Most recent
    expect(result.current.events[99].id).toBe('event-10'); // Oldest kept
  });

  it('should ignore invalid messages missing required fields', () => {
    const { result } = renderHook(() => useEventStream());

    const invalidMessages = [
      { id: 'event-1' }, // Missing other fields
      { camera_id: 'cam-1', camera_name: 'Front' }, // Missing id
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

  it('should ignore messages with partial SecurityEvent fields', () => {
    const { result } = renderHook(() => useEventStream());

    const partialEvent = {
      id: 'event-1',
      camera_id: 'cam-1',
      camera_name: 'Front Door',
      risk_score: 75,
      // Missing risk_level, summary, timestamp
    };

    act(() => {
      onMessageCallback?.(partialEvent);
    });

    expect(result.current.events).toHaveLength(0);
    expect(result.current.latestEvent).toBeNull();
  });

  it('should clear all events when clearEvents is called', () => {
    const { result } = renderHook(() => useEventStream());

    const event: SecurityEvent = {
      id: 'event-1',
      camera_id: 'cam-1',
      camera_name: 'Front Door',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Test event',
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(event);
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
      id: 'event-1',
      camera_id: 'cam-1',
      camera_name: 'Front Door',
      risk_score: 50,
      risk_level: 'medium',
      summary: 'Event 1',
      timestamp: '2025-12-23T10:00:00Z',
    };

    const event2: SecurityEvent = {
      id: 'event-2',
      camera_id: 'cam-2',
      camera_name: 'Back Door',
      risk_score: 80,
      risk_level: 'high',
      summary: 'Event 2',
      timestamp: '2025-12-23T10:05:00Z',
    };

    act(() => {
      onMessageCallback?.(event1);
    });

    expect(result.current.latestEvent).toEqual(event1);

    act(() => {
      onMessageCallback?.(event2);
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
        id: `event-${index}`,
        camera_id: `cam-${index}`,
        camera_name: `Camera ${index}`,
        risk_score: 25 * (index + 1),
        risk_level: level,
        summary: `${level} risk event`,
        timestamp: `2025-12-23T10:${String(index).padStart(2, '0')}:00Z`,
      };

      act(() => {
        onMessageCallback?.(event);
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
      id: 'event-1',
      camera_id: 'cam-1',
      camera_name: 'Front Door',
      risk_score: 50,
      risk_level: 'medium',
      summary: 'Event 1',
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(event1);
    });

    const firstEventsRef = result.current.events;

    const event2: SecurityEvent = {
      id: 'event-2',
      camera_id: 'cam-2',
      camera_name: 'Back Door',
      risk_score: 80,
      risk_level: 'high',
      summary: 'Event 2',
      timestamp: '2025-12-23T10:05:00Z',
    };

    act(() => {
      onMessageCallback?.(event2);
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
      id: 'event-1',
      camera_id: 'cam-1',
      camera_name: 'Front Door',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Test event',
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(event);
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
        id: `event-${i}`,
        camera_id: `cam-${i % 3}`, // Cycle through 3 cameras
        camera_name: `Camera ${i % 3}`,
        risk_score: 50 + i * 5,
        risk_level: 'medium',
        summary: `Rapid event ${i}`,
        timestamp: `2025-12-23T10:00:${String(i).padStart(2, '0')}Z`,
      });
    }

    act(() => {
      events.forEach((event) => onMessageCallback?.(event));
    });

    expect(result.current.events).toHaveLength(10);
    expect(result.current.events[0].id).toBe('event-9'); // Most recent
    expect(result.current.events[9].id).toBe('event-0'); // Oldest
  });

  it('should handle clearEvents being called multiple times', () => {
    const { result } = renderHook(() => useEventStream());

    const event: SecurityEvent = {
      id: 'event-1',
      camera_id: 'cam-1',
      camera_name: 'Front Door',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Test event',
      timestamp: '2025-12-23T10:00:00Z',
    };

    act(() => {
      onMessageCallback?.(event);
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
});

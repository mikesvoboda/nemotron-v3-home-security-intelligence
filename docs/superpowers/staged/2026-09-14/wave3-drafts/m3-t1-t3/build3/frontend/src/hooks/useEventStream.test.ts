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
    hasExhaustedRetries: false,
    reconnectCount: 0,
    lastHeartbeat: null,
    connectionId: 'mock-ws-001',
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

  // wa0t.34: Duplicate event detection tests
  describe('duplicate event detection (wa0t.34)', () => {
    it('should ignore duplicate events with the same id', () => {
      const { result } = renderHook(() => useEventStream());

      const event: SecurityEvent = {
        id: 1,
        camera_id: 'cam-1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Test event',
        started_at: '2025-12-23T10:00:00Z',
      };

      // Send the same event multiple times (simulating network hiccups)
      act(() => {
        onMessageCallback?.(wrapInEnvelope(event));
        onMessageCallback?.(wrapInEnvelope(event));
        onMessageCallback?.(wrapInEnvelope(event));
      });

      // Should only have one event
      expect(result.current.events).toHaveLength(1);
      expect(result.current.events[0]).toEqual(event);
    });

    it('should ignore duplicate events with the same event_id', () => {
      const { result } = renderHook(() => useEventStream());

      const event: SecurityEvent = {
        id: 'unique-uuid',
        event_id: 42,
        camera_id: 'cam-1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Test event',
        started_at: '2025-12-23T10:00:00Z',
      };

      // Send the same event multiple times
      act(() => {
        onMessageCallback?.(wrapInEnvelope(event));
        onMessageCallback?.(wrapInEnvelope(event));
      });

      // Should only have one event (deduped by event_id)
      expect(result.current.events).toHaveLength(1);
    });

    it('should allow events with different IDs', () => {
      const { result } = renderHook(() => useEventStream());

      const event1: SecurityEvent = {
        id: 1,
        camera_id: 'cam-1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Event 1',
        started_at: '2025-12-23T10:00:00Z',
      };

      const event2: SecurityEvent = {
        id: 2,
        camera_id: 'cam-1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Event 2',
        started_at: '2025-12-23T10:01:00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInEnvelope(event1));
        onMessageCallback?.(wrapInEnvelope(event2));
      });

      expect(result.current.events).toHaveLength(2);
    });

    it('should use event_id for deduplication when present', () => {
      const { result } = renderHook(() => useEventStream());

      // Two events with same event_id but different id field
      const event1: SecurityEvent = {
        id: 'uuid-1',
        event_id: 100,
        camera_id: 'cam-1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Event 1',
        started_at: '2025-12-23T10:00:00Z',
      };

      const event2: SecurityEvent = {
        id: 'uuid-2',
        event_id: 100, // Same event_id
        camera_id: 'cam-1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Event 1 duplicate',
        started_at: '2025-12-23T10:00:00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInEnvelope(event1));
        onMessageCallback?.(wrapInEnvelope(event2));
      });

      // Should only have one event (deduped by event_id)
      expect(result.current.events).toHaveLength(1);
      expect(result.current.events[0].id).toBe('uuid-1');
    });

    it('should reset seen event IDs when clearEvents is called', () => {
      const { result } = renderHook(() => useEventStream());

      const event: SecurityEvent = {
        id: 1,
        camera_id: 'cam-1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Test event',
        started_at: '2025-12-23T10:00:00Z',
      };

      // Send event
      act(() => {
        onMessageCallback?.(wrapInEnvelope(event));
      });

      expect(result.current.events).toHaveLength(1);

      // Clear events
      act(() => {
        result.current.clearEvents();
      });

      expect(result.current.events).toHaveLength(0);

      // Send same event again - should be accepted since seen IDs were cleared
      act(() => {
        onMessageCallback?.(wrapInEnvelope(event));
      });

      expect(result.current.events).toHaveLength(1);
    });

    it('should handle string and numeric IDs for deduplication', () => {
      const { result } = renderHook(() => useEventStream());

      // Numeric ID
      const event1: SecurityEvent = {
        id: 123,
        camera_id: 'cam-1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Numeric ID event',
        started_at: '2025-12-23T10:00:00Z',
      };

      // String ID
      const event2: SecurityEvent = {
        id: 'uuid-456',
        camera_id: 'cam-1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'String ID event',
        started_at: '2025-12-23T10:01:00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInEnvelope(event1));
        onMessageCallback?.(wrapInEnvelope(event2));
        // Send duplicates
        onMessageCallback?.(wrapInEnvelope(event1));
        onMessageCallback?.(wrapInEnvelope(event2));
      });

      // Should only have 2 unique events
      expect(result.current.events).toHaveLength(2);
    });
  });

  // wa0t.31: Unmount safety tests
  describe('unmount safety (wa0t.31)', () => {
    it('should not update state after unmount', () => {
      const { result, unmount } = renderHook(() => useEventStream());

      const event: SecurityEvent = {
        id: 1,
        camera_id: 'cam-1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Test event',
        started_at: '2025-12-23T10:00:00Z',
      };

      // Unmount the hook
      unmount();

      // Attempt to send event after unmount
      // This should not throw or update state
      act(() => {
        onMessageCallback?.(wrapInEnvelope(event));
      });

      // No error should occur, state should remain empty
      // (result.current is from before unmount, so it should be empty)
      expect(result.current.events).toHaveLength(0);
    });

    it('should not call setEvents after unmount via clearEvents', () => {
      const { result, unmount } = renderHook(() => useEventStream());

      const event: SecurityEvent = {
        id: 1,
        camera_id: 'cam-1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Test event',
        started_at: '2025-12-23T10:00:00Z',
      };

      // Add an event
      act(() => {
        onMessageCallback?.(wrapInEnvelope(event));
      });

      expect(result.current.events).toHaveLength(1);

      // Capture clearEvents reference before unmount
      const clearEventsFn = result.current.clearEvents;

      // Unmount the hook
      unmount();

      // Calling clearEvents after unmount should not throw
      act(() => {
        clearEventsFn();
      });

      // No error should occur
    });

    it('should properly cleanup on unmount', () => {
      const { unmount } = renderHook(() => useEventStream());

      // Unmount should complete without errors
      expect(() => unmount()).not.toThrow();
    });
  });

  // NEM-2015: LRU cache bounded behavior tests
  describe('LRU cache bounded deduplication (NEM-2015)', () => {
    it('should use LRU cache for deduplication with max 10,000 entries', () => {
      const { result } = renderHook(() => useEventStream());

      // Send more than the MAX_EVENTS (100) unique events to verify
      // the LRU cache handles high volumes correctly
      act(() => {
        for (let i = 0; i < 200; i++) {
          const event: SecurityEvent = {
            id: i,
            camera_id: 'cam-' + (i % 5),
            risk_score: 50 + (i % 50),
            risk_level: 'medium',
            summary: 'Event ' + i,
            started_at: '2025-12-23T10:' + String(i % 60).padStart(2, '0') + ':00Z',
          };
          onMessageCallback?.(wrapInEnvelope(event));
        }
      });

      // Buffer should be limited to MAX_EVENTS (100)
      expect(result.current.events).toHaveLength(100);

      // Attempting to send any of the 200 unique events again should be deduplicated
      // since the LRU cache should still have them (max 10,000 entries)
      act(() => {
        const duplicateEvent: SecurityEvent = {
          id: 150, // An event we already sent
          camera_id: 'cam-0',
          risk_score: 50,
          risk_level: 'medium',
          summary: 'Duplicate Event 150',
          started_at: '2025-12-23T10:30:00Z',
        };
        onMessageCallback?.(wrapInEnvelope(duplicateEvent));
      });

      // Should still be 100 events (duplicate was rejected)
      expect(result.current.events).toHaveLength(100);
    });

    it('should evict old entries from LRU cache when limit is exceeded', () => {
      // Note: We cannot directly test the 10,000 limit without sending 10,000+ events
      // which would be too slow. Instead, we verify the implementation uses LRU cache
      // by checking that:
      // 1. Deduplication works up to reasonable limits
      // 2. Events evicted from the display buffer have their IDs removed from the cache

      const { result } = renderHook(() => useEventStream());

      // Send 150 unique events (buffer limit is 100)
      act(() => {
        for (let i = 1; i <= 150; i++) {
          const event: SecurityEvent = {
            id: i,
            event_id: i,
            camera_id: 'cam-1',
            risk_score: 50,
            risk_level: 'medium',
            summary: 'Event ' + i,
            started_at: '2025-12-23T10:00:' + String(i % 60).padStart(2, '0') + 'Z',
          };
          onMessageCallback?.(wrapInEnvelope(event));
        }
      });

      // Buffer should be limited to 100 (events 51-150)
      expect(result.current.events).toHaveLength(100);
      expect(result.current.events[0].id).toBe(150); // Most recent

      // Events 1-50 were evicted from buffer and their IDs were removed from cache
      // So re-sending event-1 should be accepted
      act(() => {
        const resentEvent: SecurityEvent = {
          id: 1,
          event_id: 1,
          camera_id: 'cam-1',
          risk_score: 80,
          risk_level: 'high',
          summary: 'Resent event 1',
          started_at: '2025-12-23T11:00:00Z',
        };
        onMessageCallback?.(wrapInEnvelope(resentEvent));
      });

      // Event 1 should now be at the front (most recent)
      expect(result.current.events[0].id).toBe(1);
      expect(result.current.events[0].summary).toBe('Resent event 1');
      // Buffer should still be 100
      expect(result.current.events).toHaveLength(100);
    });

    it('should maintain dedup functionality with LRU cache TTL', () => {
      // The LRU cache has a TTL of 1 hour (SEEN_IDS_TTL_MS)
      // This test verifies dedup works within a session
      const { result } = renderHook(() => useEventStream());

      // Send an event
      const event: SecurityEvent = {
        id: 'ttl-test-event',
        camera_id: 'cam-1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'TTL test event',
        started_at: '2025-12-23T10:00:00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInEnvelope(event));
      });

      expect(result.current.events).toHaveLength(1);

      // Send duplicate multiple times rapidly
      act(() => {
        for (let i = 0; i < 100; i++) {
          onMessageCallback?.(wrapInEnvelope(event));
        }
      });

      // Should still have only 1 event
      expect(result.current.events).toHaveLength(1);
    });

    it('should handle mixed event IDs (event_id and id) in LRU cache', () => {
      const { result } = renderHook(() => useEventStream());

      // Event with event_id (preferred for dedup key)
      const eventWithEventId: SecurityEvent = {
        id: 'uuid-123',
        event_id: 999,
        camera_id: 'cam-1',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Event with event_id',
        started_at: '2025-12-23T10:00:00Z',
      };

      // Event with only id (fallback dedup key)
      const eventWithOnlyId: SecurityEvent = {
        id: 'uuid-456',
        camera_id: 'cam-2',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Event with only id',
        started_at: '2025-12-23T10:01:00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInEnvelope(eventWithEventId));
        onMessageCallback?.(wrapInEnvelope(eventWithOnlyId));
      });

      expect(result.current.events).toHaveLength(2);

      // Send duplicates
      act(() => {
        // Duplicate of event_id 999 (should use event_id for dedup)
        const duplicate1: SecurityEvent = {
          id: 'different-uuid',
          event_id: 999, // Same event_id as eventWithEventId
          camera_id: 'cam-1',
          risk_score: 75,
          risk_level: 'high',
          summary: 'Duplicate by event_id',
          started_at: '2025-12-23T10:00:00Z',
        };
        onMessageCallback?.(wrapInEnvelope(duplicate1));

        // Duplicate of id uuid-456 (should use id for dedup since no event_id)
        const duplicate2: SecurityEvent = {
          id: 'uuid-456', // Same id as eventWithOnlyId
          camera_id: 'cam-2',
          risk_score: 50,
          risk_level: 'medium',
          summary: 'Duplicate by id',
          started_at: '2025-12-23T10:01:00Z',
        };
        onMessageCallback?.(wrapInEnvelope(duplicate2));
      });

      // Should still have only 2 events (duplicates rejected)
      expect(result.current.events).toHaveLength(2);
    });
  });

  // NEM-1999: Sequence validation tests
  describe('sequence validation (NEM-1999)', () => {
    // Helper to wrap event data in the backend envelope format with sequence
    function wrapInSequencedEnvelope(
      event: SecurityEvent,
      sequence: number
    ): { type: 'event'; data: SecurityEvent; sequence: number } {
      return { type: 'event', data: event, sequence };
    }

    it('should process events with sequence numbers in order', () => {
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
        camera_id: 'cam-1',
        risk_score: 60,
        risk_level: 'medium',
        summary: 'Event 2',
        started_at: '2025-12-23T10:01:00Z',
      };

      const event3: SecurityEvent = {
        id: 3,
        camera_id: 'cam-1',
        risk_score: 70,
        risk_level: 'high',
        summary: 'Event 3',
        started_at: '2025-12-23T10:02:00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(event1, 1));
        onMessageCallback?.(wrapInSequencedEnvelope(event2, 2));
        onMessageCallback?.(wrapInSequencedEnvelope(event3, 3));
      });

      expect(result.current.events).toHaveLength(3);
      // Events should be in reverse chronological order (newest first)
      expect(result.current.events[0].id).toBe(3);
      expect(result.current.events[1].id).toBe(2);
      expect(result.current.events[2].id).toBe(1);
    });

    it('should buffer out-of-order events and process when gap is filled', () => {
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
        camera_id: 'cam-1',
        risk_score: 60,
        risk_level: 'medium',
        summary: 'Event 2',
        started_at: '2025-12-23T10:01:00Z',
      };

      const event3: SecurityEvent = {
        id: 3,
        camera_id: 'cam-1',
        risk_score: 70,
        risk_level: 'high',
        summary: 'Event 3',
        started_at: '2025-12-23T10:02:00Z',
      };

      // Send events out of order: 1, 3, 2
      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(event1, 1));
      });

      expect(result.current.events).toHaveLength(1);
      expect(result.current.events[0].id).toBe(1);

      // Event 3 arrives before event 2 (out of order)
      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(event3, 3));
      });

      // Event 3 should be buffered since sequence 2 is missing
      // Only event 1 should be in the events array
      expect(result.current.events).toHaveLength(1);

      // Event 2 arrives, filling the gap
      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(event2, 2));
      });

      // Now all events should be processed in order
      expect(result.current.events).toHaveLength(3);
      expect(result.current.events[0].id).toBe(3);
      expect(result.current.events[1].id).toBe(2);
      expect(result.current.events[2].id).toBe(1);
    });

    it('should ignore duplicate sequence numbers (replay protection)', () => {
      const { result } = renderHook(() => useEventStream());

      const event1: SecurityEvent = {
        id: 1,
        camera_id: 'cam-1',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Event 1',
        started_at: '2025-12-23T10:00:00Z',
      };

      const event1Duplicate: SecurityEvent = {
        id: 1,
        camera_id: 'cam-1',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Event 1 duplicate',
        started_at: '2025-12-23T10:00:00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(event1, 1));
        onMessageCallback?.(wrapInSequencedEnvelope(event1Duplicate, 1));
      });

      // Should only have one event (duplicate rejected)
      expect(result.current.events).toHaveLength(1);
      expect(result.current.events[0].summary).toBe('Event 1');
    });

    it('should ignore events with sequence < last processed (replay protection)', () => {
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
        camera_id: 'cam-1',
        risk_score: 60,
        risk_level: 'medium',
        summary: 'Event 2',
        started_at: '2025-12-23T10:01:00Z',
      };

      const event3: SecurityEvent = {
        id: 3,
        camera_id: 'cam-1',
        risk_score: 70,
        risk_level: 'high',
        summary: 'Event 3',
        started_at: '2025-12-23T10:02:00Z',
      };

      // Old event that arrives after seq 3 was processed
      const oldEvent: SecurityEvent = {
        id: 0,
        camera_id: 'cam-1',
        risk_score: 40,
        risk_level: 'low',
        summary: 'Old event',
        started_at: '2025-12-23T09:59:00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(event1, 1));
        onMessageCallback?.(wrapInSequencedEnvelope(event2, 2));
        onMessageCallback?.(wrapInSequencedEnvelope(event3, 3));
      });

      expect(result.current.events).toHaveLength(3);

      // Now an old event with sequence 0 arrives (replay attack or stale message)
      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(oldEvent, 0));
      });

      // Should still have only 3 events (old event rejected)
      expect(result.current.events).toHaveLength(3);
    });

    it('should process multiple buffered events when gap is filled', () => {
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
        camera_id: 'cam-1',
        risk_score: 60,
        risk_level: 'medium',
        summary: 'Event 2',
        started_at: '2025-12-23T10:01:00Z',
      };

      const event3: SecurityEvent = {
        id: 3,
        camera_id: 'cam-1',
        risk_score: 70,
        risk_level: 'high',
        summary: 'Event 3',
        started_at: '2025-12-23T10:02:00Z',
      };

      const event4: SecurityEvent = {
        id: 4,
        camera_id: 'cam-1',
        risk_score: 80,
        risk_level: 'high',
        summary: 'Event 4',
        started_at: '2025-12-23T10:03:00Z',
      };

      const event5: SecurityEvent = {
        id: 5,
        camera_id: 'cam-1',
        risk_score: 90,
        risk_level: 'critical',
        summary: 'Event 5',
        started_at: '2025-12-23T10:04:00Z',
      };

      // Send events: 1, 4, 5, 3, 2
      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(event1, 1));
      });

      expect(result.current.events).toHaveLength(1);

      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(event4, 4));
        onMessageCallback?.(wrapInSequencedEnvelope(event5, 5));
        onMessageCallback?.(wrapInSequencedEnvelope(event3, 3));
      });

      // Events 4, 5, 3 should be buffered
      expect(result.current.events).toHaveLength(1);

      // Event 2 arrives, filling the gap
      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(event2, 2));
      });

      // All events should be processed
      expect(result.current.events).toHaveLength(5);
      // Newest first
      expect(result.current.events[0].id).toBe(5);
      expect(result.current.events[1].id).toBe(4);
      expect(result.current.events[2].id).toBe(3);
      expect(result.current.events[3].id).toBe(2);
      expect(result.current.events[4].id).toBe(1);
    });

    it('should handle events without sequence numbers (backward compatibility)', () => {
      const { result } = renderHook(() => useEventStream());

      // Event without sequence (legacy format)
      const legacyEvent: SecurityEvent = {
        id: 1,
        camera_id: 'cam-1',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Legacy event',
        started_at: '2025-12-23T10:00:00Z',
      };

      act(() => {
        // Use standard envelope without sequence
        onMessageCallback?.(wrapInEnvelope(legacyEvent));
      });

      // Should be processed immediately (no sequence validation)
      expect(result.current.events).toHaveLength(1);
      expect(result.current.events[0].summary).toBe('Legacy event');
    });

    it('should reset sequence state when clearEvents is called', () => {
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
        camera_id: 'cam-1',
        risk_score: 60,
        risk_level: 'medium',
        summary: 'Event 2',
        started_at: '2025-12-23T10:01:00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(event1, 1));
        onMessageCallback?.(wrapInSequencedEnvelope(event2, 2));
      });

      expect(result.current.events).toHaveLength(2);

      // Clear events
      act(() => {
        result.current.clearEvents();
      });

      expect(result.current.events).toHaveLength(0);

      // Send new events starting from sequence 1 again
      const newEvent1: SecurityEvent = {
        id: 101,
        camera_id: 'cam-2',
        risk_score: 70,
        risk_level: 'high',
        summary: 'New Event 1',
        started_at: '2025-12-23T11:00:00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(newEvent1, 1));
      });

      // Should accept the new sequence 1 since state was reset
      expect(result.current.events).toHaveLength(1);
      expect(result.current.events[0].id).toBe(101);
    });

    it('should send resync request when large gap detected', () => {
      // First render to establish baseline - result used for verification
      renderHook(() => useEventStream());

      // Re-mock to capture the send function
      vi.spyOn(useWebSocketModule, 'useWebSocket').mockImplementation((options) => {
        onMessageCallback = options.onMessage;
        return mockWebSocketReturn;
      });

      // Re-render to get the updated mock
      const { result: result2 } = renderHook(() => useEventStream());

      const event1: SecurityEvent = {
        id: 1,
        camera_id: 'cam-1',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Event 1',
        started_at: '2025-12-23T10:00:00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(event1, 1));
      });

      expect(result2.current.events).toHaveLength(1);

      // Send an event with a large gap (e.g., sequence 100 when last was 1)
      // NEM-3905: Default gap threshold is now 50 (was 10)
      // Gap of 99 (100 - 1) exceeds threshold of 50
      const gapEvent: SecurityEvent = {
        id: 100,
        camera_id: 'cam-1',
        risk_score: 80,
        risk_level: 'high',
        summary: 'Event with large gap',
        started_at: '2025-12-23T12:00:00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(gapEvent, 100));
      });

      // Should have called send with resync request
      expect(mockWebSocketReturn.send).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'resync',
          last_sequence: 1,
          channel: 'events',
        })
      );
    });

    it('should expose sequence statistics for monitoring', () => {
      const { result } = renderHook(() => useEventStream());

      // Note: This test verifies the hook exposes sequence statistics
      // The actual implementation will add getSequenceStats() method

      const event1: SecurityEvent = {
        id: 1,
        camera_id: 'cam-1',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Event 1',
        started_at: '2025-12-23T10:00:00Z',
      };

      const event3: SecurityEvent = {
        id: 3,
        camera_id: 'cam-1',
        risk_score: 70,
        risk_level: 'high',
        summary: 'Event 3',
        started_at: '2025-12-23T10:02:00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(event1, 1));
        onMessageCallback?.(wrapInSequencedEnvelope(event3, 3)); // Out of order
      });

      // Check that sequence stats are available
      const stats = result.current.sequenceStats;
      expect(stats).toBeDefined();
      expect(stats.processedCount).toBeGreaterThanOrEqual(1);
      expect(stats.outOfOrderCount).toBeGreaterThanOrEqual(1);
      expect(stats.currentBufferSize).toBeGreaterThanOrEqual(1);
    });

    it('should handle first message with any sequence number', () => {
      const { result } = renderHook(() => useEventStream());

      // First message might have sequence > 1 (e.g., client connecting mid-stream)
      const event: SecurityEvent = {
        id: 42,
        camera_id: 'cam-1',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Mid-stream event',
        started_at: '2025-12-23T10:00:00Z',
      };

      act(() => {
        onMessageCallback?.(wrapInSequencedEnvelope(event, 42));
      });

      // Should accept the first message regardless of sequence
      expect(result.current.events).toHaveLength(1);
      expect(result.current.events[0].id).toBe(42);
    });
  });
});

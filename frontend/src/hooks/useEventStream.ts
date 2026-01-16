import { LRUCache } from 'lru-cache';
import { useState, useCallback, useMemo, useRef, useEffect } from 'react';

import {
  SequenceValidator,
  type SequenceStatistics,
  type SequencedMessage,
} from './sequenceValidator';
import { useWebSocket } from './useWebSocket';
import { buildWebSocketOptions } from '../services/api';
import { logger } from '../services/logger';
import {
  type SecurityEventData,
  type ResyncRequestMessage,
  isEventMessage,
  isHeartbeatMessage,
  isErrorMessage,
} from '../types/websocket';

/**
 * Re-export SecurityEventData as SecurityEvent for backward compatibility.
 * New code should use SecurityEventData from types/websocket.ts directly.
 */
export type SecurityEvent = SecurityEventData;

export interface UseEventStreamReturn {
  events: SecurityEvent[];
  isConnected: boolean;
  latestEvent: SecurityEvent | null;
  clearEvents: () => void;
  /** Sequence validation statistics for monitoring (NEM-1999) */
  sequenceStats: SequenceStatistics;
}

const MAX_EVENTS = 100;

// NEM-2020: LRU cache configuration for deduplication
// Prevents unbounded memory growth over long sessions
const MAX_SEEN_IDS = 10000;
const SEEN_IDS_TTL_MS = 1000 * 60 * 60; // 1 hour

/**
 * Get a unique identifier for an event for deduplication purposes.
 * Uses event_id if available, falls back to id.
 */
function getEventKey(event: SecurityEvent): string {
  const id = event.event_id ?? event.id;
  return String(id);
}

// Default empty statistics for when no events have been processed
const EMPTY_SEQUENCE_STATS: SequenceStatistics = {
  processedCount: 0,
  duplicateCount: 0,
  resyncCount: 0,
  outOfOrderCount: 0,
  currentBufferSize: 0,
};

// Channel name for the events WebSocket
const EVENTS_CHANNEL = 'events';

export function useEventStream(): UseEventStreamReturn {
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [sequenceStats, setSequenceStats] = useState<SequenceStatistics>(EMPTY_SEQUENCE_STATS);

  // Track mounted state to prevent state updates after unmount (wa0t.31)
  const isMountedRef = useRef(true);

  // Track seen event IDs to prevent duplicate events (wa0t.34)
  // NEM-2020: Use LRU cache instead of Set to prevent unbounded memory growth
  const seenEventIdsRef = useRef<LRUCache<string, true>>(
    new LRUCache<string, true>({
      max: MAX_SEEN_IDS,
      ttl: SEEN_IDS_TTL_MS,
    })
  );

  // Ref to store the send function from useWebSocket
  const sendRef = useRef<((data: unknown) => void) | null>(null);

  // NEM-1999: Sequence validator for event ordering
  // Create resync callback that sends resync request via WebSocket
  const sequenceValidatorRef = useRef<SequenceValidator | null>(null);

  // Initialize sequence validator lazily
  if (!sequenceValidatorRef.current) {
    sequenceValidatorRef.current = new SequenceValidator(
      (channel: string, lastSequence: number) => {
        // Send resync request to backend
        const resyncRequest: ResyncRequestMessage = {
          type: 'resync',
          last_sequence: lastSequence,
          channel,
        };
        logger.info('Sending resync request', {
          component: 'useEventStream',
          channel,
          lastSequence,
        });
        sendRef.current?.(resyncRequest);
      }
    );
  }

  // Set mounted state on mount and cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  /**
   * Process a single event: add to events array with deduplication.
   */
  const processEvent = useCallback((event: SecurityEvent) => {
    if (!isMountedRef.current) {
      return;
    }

    const eventKey = getEventKey(event);

    // Check for duplicate events (wa0t.34)
    if (seenEventIdsRef.current.has(eventKey)) {
      return;
    }

    // Mark event as seen (NEM-2020: use .set() for LRU cache)
    seenEventIdsRef.current.set(eventKey, true);

    setEvents((prevEvents) => {
      // Add new event to the beginning of the array
      const newEvents = [event, ...prevEvents];

      // Keep only the most recent MAX_EVENTS
      const trimmedEvents = newEvents.slice(0, MAX_EVENTS);

      // NEM-1998: Bound the seen IDs set to prevent memory leaks
      // When events are evicted from the array, remove their IDs from the set
      // This ensures the set doesn't grow unbounded over time
      if (newEvents.length > MAX_EVENTS) {
        const evictedEvents = newEvents.slice(MAX_EVENTS);
        for (const evictedEvent of evictedEvents) {
          const evictedKey = getEventKey(evictedEvent);
          seenEventIdsRef.current.delete(evictedKey);
        }
      }

      return trimmedEvents;
    });
  }, []);

  const handleMessage = useCallback(
    (data: unknown) => {
      // Check if component is still mounted before updating state (wa0t.31)
      if (!isMountedRef.current) {
        return;
      }

      // Use type guards to validate and narrow the message type
      // First, check for event messages (most common case)
      if (isEventMessage(data)) {
        const event = data.data;

        // NEM-1999: Check if message has sequence number for ordering
        if (data.sequence !== undefined && data.sequence !== null) {
          // Use sequence validator for ordering
          const sequencedMessage: SequencedMessage = {
            type: data.type,
            sequence: data.sequence,
            data: event,
            replay: data.replay,
            requires_ack: data.requires_ack,
            timestamp: data.timestamp,
          };

          const result = sequenceValidatorRef.current?.handleMessage(
            EVENTS_CHANNEL,
            sequencedMessage
          );

          if (result) {
            // Process all events that are now in order
            for (const processedMsg of result.processed) {
              const processedEvent = processedMsg.data as SecurityEvent;
              processEvent(processedEvent);
            }

            // Update sequence statistics
            const stats = sequenceValidatorRef.current?.getStatistics(EVENTS_CHANNEL);
            if (stats) {
              setSequenceStats(stats);
            }
          }
        } else {
          // No sequence number - process immediately (backward compatibility)
          processEvent(event);
        }
        return;
      }

      // Handle other valid EventsChannelMessage types with exhaustive checking pattern
      if (isHeartbeatMessage(data)) {
        // Heartbeat messages are handled by useWebSocket internally
        return;
      }

      if (isErrorMessage(data)) {
        // Error messages are logged via the structured logger
        logger.warn('WebSocket error received', {
          component: 'useEventStream',
          errorMessage: data.message,
        });
        return;
      }

      // Unknown message types are silently ignored
      // This is intentional - the backend may send messages we don't care about
    },
    [processEvent]
  );

  // Build WebSocket options using helper (respects VITE_WS_BASE_URL)
  // SECURITY: API key is passed via Sec-WebSocket-Protocol header, not URL query param
  const wsOptions = buildWebSocketOptions('/ws/events');

  const { isConnected, send } = useWebSocket({
    url: wsOptions.url,
    protocols: wsOptions.protocols,
    onMessage: handleMessage,
  });

  // Store send function in ref for use in resync callback
  useEffect(() => {
    sendRef.current = send;
  }, [send]);

  const clearEvents = useCallback(() => {
    // Check if component is still mounted before updating state
    if (!isMountedRef.current) {
      return;
    }
    setEvents([]);
    // Also clear the seen event IDs cache when events are cleared
    seenEventIdsRef.current.clear();
    // NEM-1999: Reset sequence validator state when events are cleared
    sequenceValidatorRef.current?.reset(EVENTS_CHANNEL);
    setSequenceStats(EMPTY_SEQUENCE_STATS);
  }, []);

  const latestEvent = useMemo(() => {
    return events.length > 0 ? events[0] : null;
  }, [events]);

  return {
    events,
    isConnected,
    latestEvent,
    clearEvents,
    sequenceStats,
  };
}

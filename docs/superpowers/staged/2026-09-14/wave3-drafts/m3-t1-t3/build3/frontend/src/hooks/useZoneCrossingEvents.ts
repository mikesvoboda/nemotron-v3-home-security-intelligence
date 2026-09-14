/**
 * useZoneCrossingEvents - Hook for subscribing to zone crossing WebSocket events (NEM-3195)
 *
 * This hook subscribes to zone.enter, zone.exit, and zone.dwell WebSocket events
 * and maintains a history of crossing events with filtering capabilities.
 *
 * Features:
 * - Subscribe to zone crossing events via WebSocket
 * - Maintain configurable event history (default 100 events)
 * - Filter events by zone, entity type, and event type
 * - Real-time updates with connection status
 *
 * @module hooks/useZoneCrossingEvents
 * @see NEM-3195 Zone Crossing Feed Component
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useWebSocketEvents } from './useWebSocketEvent';
import { ZoneCrossingType, isZoneCrossingEventPayload } from '../types/zoneCrossing';

import type { WebSocketEventKey } from '../types/websocket-events';
import type {
  ZoneCrossingEvent,
  ZoneCrossingFilters,
  UseZoneCrossingEventsOptions,
  UseZoneCrossingEventsReturn,
} from '../types/zoneCrossing';

// ============================================================================
// Constants
// ============================================================================

/** Default maximum number of events to keep in history */
const DEFAULT_MAX_EVENTS = 100;

/** Default filter state */
const DEFAULT_FILTERS: ZoneCrossingFilters = {
  zoneId: 'all',
  entityType: 'all',
  eventType: 'all',
};

// ============================================================================
// Hook Implementation
// ============================================================================

/**
 * Hook for subscribing to zone crossing WebSocket events.
 *
 * Maintains a history of zone crossing events (enter/exit/dwell) with
 * filtering capabilities and real-time WebSocket updates.
 *
 * @param options - Configuration options
 * @returns Event history, filters, and connection state
 *
 * @example
 * ```tsx
 * const {
 *   events,
 *   isConnected,
 *   filters,
 *   setFilters,
 *   clearEvents,
 * } = useZoneCrossingEvents({
 *   maxEvents: 50,
 *   filters: { zoneId: 'front-door' },
 *   onEvent: (event) => {
 *     if (event.type === 'enter') {
 *       toast.info(`${event.entity_type} entered ${event.zone_name}`);
 *     }
 *   },
 * });
 * ```
 */
export function useZoneCrossingEvents(
  options: UseZoneCrossingEventsOptions = {}
): UseZoneCrossingEventsReturn {
  const {
    maxEvents = DEFAULT_MAX_EVENTS,
    filters: initialFilters,
    enabled = true,
    onEvent,
  } = options;

  // State for event history
  const [events, setEvents] = useState<ZoneCrossingEvent[]>([]);

  // State for filters
  const [filters, setFilters] = useState<ZoneCrossingFilters>({
    ...DEFAULT_FILTERS,
    ...initialFilters,
  });

  // Refs for callbacks to avoid stale closures
  const onEventRef = useRef(onEvent);
  const maxEventsRef = useRef(maxEvents);

  useEffect(() => {
    onEventRef.current = onEvent;
    maxEventsRef.current = maxEvents;
  });

  // Clear all events
  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  // Handle incoming zone.enter event
  const handleZoneEnter = useCallback((payload: unknown) => {
    if (!isZoneCrossingEventPayload(payload)) {
      return;
    }

    const event: ZoneCrossingEvent = {
      type: ZoneCrossingType.ENTER,
      zone_id: payload.zone_id,
      zone_name: payload.zone_name,
      entity_id: payload.entity_id,
      entity_type: payload.entity_type,
      detection_id: payload.detection_id,
      timestamp: payload.timestamp,
      thumbnail_url: payload.thumbnail_url,
      dwell_time: null,
    };

    setEvents((prev) => {
      const newEvents = [event, ...prev];
      return newEvents.slice(0, maxEventsRef.current);
    });

    onEventRef.current?.(event);
  }, []);

  // Handle incoming zone.exit event
  const handleZoneExit = useCallback((payload: unknown) => {
    if (!isZoneCrossingEventPayload(payload)) {
      return;
    }

    const event: ZoneCrossingEvent = {
      type: ZoneCrossingType.EXIT,
      zone_id: payload.zone_id,
      zone_name: payload.zone_name,
      entity_id: payload.entity_id,
      entity_type: payload.entity_type,
      detection_id: payload.detection_id,
      timestamp: payload.timestamp,
      thumbnail_url: payload.thumbnail_url,
      dwell_time: payload.dwell_time,
    };

    setEvents((prev) => {
      const newEvents = [event, ...prev];
      return newEvents.slice(0, maxEventsRef.current);
    });

    onEventRef.current?.(event);
  }, []);

  // Handle incoming zone.dwell event
  const handleZoneDwell = useCallback((payload: unknown) => {
    if (!isZoneCrossingEventPayload(payload)) {
      return;
    }

    const event: ZoneCrossingEvent = {
      type: ZoneCrossingType.DWELL,
      zone_id: payload.zone_id,
      zone_name: payload.zone_name,
      entity_id: payload.entity_id,
      entity_type: payload.entity_type,
      detection_id: payload.detection_id,
      timestamp: payload.timestamp,
      thumbnail_url: payload.thumbnail_url,
      dwell_time: payload.dwell_time,
    };

    setEvents((prev) => {
      const newEvents = [event, ...prev];
      return newEvents.slice(0, maxEventsRef.current);
    });

    onEventRef.current?.(event);
  }, []);

  // Subscribe to WebSocket events
  // Note: zone.enter, zone.exit, zone.dwell are not in the standard event types yet
  const { isConnected, reconnectCount, hasExhaustedRetries } = useWebSocketEvents(
    enabled
      ? ({
          'zone.enter': handleZoneEnter,
          'zone.exit': handleZoneExit,
          'zone.dwell': handleZoneDwell,
        } as unknown as Record<WebSocketEventKey, (data: unknown) => void>)
      : {},
    { enabled }
  );

  // Filter events based on current filters
  const filteredEvents = useMemo(() => {
    return events.filter((event) => {
      // Filter by zone ID
      if (filters.zoneId !== 'all' && event.zone_id !== filters.zoneId) {
        return false;
      }

      // Filter by entity type
      if (filters.entityType !== 'all' && event.entity_type !== filters.entityType) {
        return false;
      }

      // Filter by event type
      if (filters.eventType !== 'all' && event.type !== filters.eventType) {
        return false;
      }

      return true;
    });
  }, [events, filters]);

  return {
    events: filteredEvents,
    isConnected,
    reconnectCount,
    hasExhaustedRetries,
    clearEvents,
    setFilters,
    filters,
  };
}

export default useZoneCrossingEvents;

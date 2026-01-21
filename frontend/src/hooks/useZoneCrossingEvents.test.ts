/**
 * Tests for useZoneCrossingEvents hook (NEM-3195)
 *
 * This module tests the zone crossing events hook:
 * - WebSocket event handling (enter, exit, dwell)
 * - Event history management
 * - Filtering capabilities
 * - Connection state
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useZoneCrossingEvents } from './useZoneCrossingEvents';
import { ZoneCrossingType } from '../types/zoneCrossing';

import type { ZoneCrossingEventPayload } from '../types/zoneCrossing';

// Track captured handlers
type EventHandlers = Record<string, (data: unknown) => void>;
let capturedHandlers: EventHandlers = {};
let mockIsConnected = true;
let mockReconnectCount = 0;
let mockHasExhaustedRetries = false;

// Mock useWebSocketEvents
vi.mock('./useWebSocketEvent', () => ({
  useWebSocketEvents: vi.fn((handlers: EventHandlers, options: { enabled: boolean }) => {
    if (options.enabled) {
      capturedHandlers = handlers;
    } else {
      capturedHandlers = {};
    }
    return {
      isConnected: mockIsConnected,
      reconnectCount: mockReconnectCount,
      hasExhaustedRetries: mockHasExhaustedRetries,
      lastHeartbeat: null,
      reconnect: vi.fn(),
    };
  }),
}));

describe('useZoneCrossingEvents', () => {
  // Helper to create a valid event payload
  const createPayload = (overrides: Partial<ZoneCrossingEventPayload> = {}): ZoneCrossingEventPayload => ({
    zone_id: 'zone-1',
    zone_name: 'Front Door',
    entity_id: 'entity-123',
    entity_type: 'person',
    detection_id: 'det-456',
    timestamp: new Date().toISOString(),
    thumbnail_url: null,
    dwell_time: null,
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    capturedHandlers = {};
    mockIsConnected = true;
    mockReconnectCount = 0;
    mockHasExhaustedRetries = false;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('returns empty events array initially', () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      expect(result.current.events).toEqual([]);
    });

    it('returns default filters', () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      expect(result.current.filters).toEqual({
        zoneId: 'all',
        entityType: 'all',
        eventType: 'all',
      });
    });

    it('returns connection state', () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      expect(result.current.isConnected).toBe(true);
      expect(result.current.reconnectCount).toBe(0);
      expect(result.current.hasExhaustedRetries).toBe(false);
    });

    it('returns clearEvents and setFilters functions', () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      expect(typeof result.current.clearEvents).toBe('function');
      expect(typeof result.current.setFilters).toBe('function');
    });
  });

  describe('initial filters', () => {
    it('applies initial filters from options', () => {
      const { result } = renderHook(() =>
        useZoneCrossingEvents({
          filters: {
            zoneId: 'zone-1',
            entityType: 'person',
            eventType: ZoneCrossingType.ENTER,
          },
        })
      );

      expect(result.current.filters).toEqual({
        zoneId: 'zone-1',
        entityType: 'person',
        eventType: ZoneCrossingType.ENTER,
      });
    });

    it('merges partial initial filters with defaults', () => {
      const { result } = renderHook(() =>
        useZoneCrossingEvents({
          filters: {
            zoneId: 'zone-1',
          },
        })
      );

      expect(result.current.filters).toEqual({
        zoneId: 'zone-1',
        entityType: 'all',
        eventType: 'all',
      });
    });
  });

  describe('WebSocket event handling', () => {
    it('subscribes to zone.enter events', () => {
      renderHook(() => useZoneCrossingEvents());

      expect(capturedHandlers['zone.enter']).toBeDefined();
    });

    it('subscribes to zone.exit events', () => {
      renderHook(() => useZoneCrossingEvents());

      expect(capturedHandlers['zone.exit']).toBeDefined();
    });

    it('subscribes to zone.dwell events', () => {
      renderHook(() => useZoneCrossingEvents());

      expect(capturedHandlers['zone.dwell']).toBeDefined();
    });

    it('does not subscribe when disabled', () => {
      renderHook(() => useZoneCrossingEvents({ enabled: false }));

      expect(Object.keys(capturedHandlers)).toHaveLength(0);
    });
  });

  describe('zone.enter events', () => {
    it('adds enter event to history', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      const payload = createPayload();

      act(() => {
        capturedHandlers['zone.enter'](payload);
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
        expect(result.current.events[0].type).toBe(ZoneCrossingType.ENTER);
        expect(result.current.events[0].zone_id).toBe('zone-1');
        expect(result.current.events[0].zone_name).toBe('Front Door');
        expect(result.current.events[0].entity_id).toBe('entity-123');
        expect(result.current.events[0].entity_type).toBe('person');
      });
    });

    it('sets dwell_time to null for enter events', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      act(() => {
        capturedHandlers['zone.enter'](createPayload({ dwell_time: 30 }));
      });

      await waitFor(() => {
        expect(result.current.events[0].dwell_time).toBeNull();
      });
    });
  });

  describe('zone.exit events', () => {
    it('adds exit event to history with dwell_time', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      const payload = createPayload({ dwell_time: 45 });

      act(() => {
        capturedHandlers['zone.exit'](payload);
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
        expect(result.current.events[0].type).toBe(ZoneCrossingType.EXIT);
        expect(result.current.events[0].dwell_time).toBe(45);
      });
    });
  });

  describe('zone.dwell events', () => {
    it('adds dwell event to history with dwell_time', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      const payload = createPayload({ dwell_time: 120 });

      act(() => {
        capturedHandlers['zone.dwell'](payload);
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
        expect(result.current.events[0].type).toBe(ZoneCrossingType.DWELL);
        expect(result.current.events[0].dwell_time).toBe(120);
      });
    });
  });

  describe('event history management', () => {
    it('adds new events to the beginning of the list', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      act(() => {
        capturedHandlers['zone.enter'](createPayload({ entity_id: 'first' }));
      });

      act(() => {
        capturedHandlers['zone.enter'](createPayload({ entity_id: 'second' }));
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(2);
        expect(result.current.events[0].entity_id).toBe('second');
        expect(result.current.events[1].entity_id).toBe('first');
      });
    });

    it('respects maxEvents limit', async () => {
      const { result } = renderHook(() =>
        useZoneCrossingEvents({ maxEvents: 3 })
      );

      act(() => {
        for (let i = 0; i < 5; i++) {
          capturedHandlers['zone.enter'](createPayload({ entity_id: `entity-${i}` }));
        }
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(3);
        // Most recent events should be kept
        expect(result.current.events[0].entity_id).toBe('entity-4');
        expect(result.current.events[1].entity_id).toBe('entity-3');
        expect(result.current.events[2].entity_id).toBe('entity-2');
      });
    });

    it('uses default maxEvents of 100', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      // Add 110 events
      act(() => {
        for (let i = 0; i < 110; i++) {
          capturedHandlers['zone.enter'](createPayload({ entity_id: `entity-${i}` }));
        }
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(100);
      });
    });
  });

  describe('clearEvents', () => {
    it('clears all events from history', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      // Add some events
      act(() => {
        capturedHandlers['zone.enter'](createPayload());
        capturedHandlers['zone.exit'](createPayload());
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(2);
      });

      // Clear events
      act(() => {
        result.current.clearEvents();
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(0);
      });
    });
  });

  describe('filtering', () => {
    it('filters by zoneId', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      // Add events from different zones
      act(() => {
        capturedHandlers['zone.enter'](createPayload({ zone_id: 'zone-1' }));
        capturedHandlers['zone.enter'](createPayload({ zone_id: 'zone-2' }));
        capturedHandlers['zone.enter'](createPayload({ zone_id: 'zone-1' }));
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(3);
      });

      // Apply filter
      act(() => {
        result.current.setFilters({ ...result.current.filters, zoneId: 'zone-1' });
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(2);
        result.current.events.forEach((e) => {
          expect(e.zone_id).toBe('zone-1');
        });
      });
    });

    it('filters by entityType', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      act(() => {
        capturedHandlers['zone.enter'](createPayload({ entity_type: 'person' }));
        capturedHandlers['zone.enter'](createPayload({ entity_type: 'vehicle' }));
        capturedHandlers['zone.enter'](createPayload({ entity_type: 'person' }));
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(3);
      });

      act(() => {
        result.current.setFilters({ ...result.current.filters, entityType: 'vehicle' });
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
        expect(result.current.events[0].entity_type).toBe('vehicle');
      });
    });

    it('filters by eventType', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      act(() => {
        capturedHandlers['zone.enter'](createPayload());
        capturedHandlers['zone.exit'](createPayload());
        capturedHandlers['zone.dwell'](createPayload());
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(3);
      });

      act(() => {
        result.current.setFilters({ ...result.current.filters, eventType: ZoneCrossingType.EXIT });
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
        expect(result.current.events[0].type).toBe(ZoneCrossingType.EXIT);
      });
    });

    it('applies multiple filters together', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      act(() => {
        capturedHandlers['zone.enter'](createPayload({ zone_id: 'zone-1', entity_type: 'person' }));
        capturedHandlers['zone.enter'](createPayload({ zone_id: 'zone-1', entity_type: 'vehicle' }));
        capturedHandlers['zone.exit'](createPayload({ zone_id: 'zone-1', entity_type: 'person' }));
        capturedHandlers['zone.enter'](createPayload({ zone_id: 'zone-2', entity_type: 'person' }));
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(4);
      });

      act(() => {
        result.current.setFilters({
          zoneId: 'zone-1',
          entityType: 'person',
          eventType: ZoneCrossingType.ENTER,
        });
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
        expect(result.current.events[0].zone_id).toBe('zone-1');
        expect(result.current.events[0].entity_type).toBe('person');
        expect(result.current.events[0].type).toBe(ZoneCrossingType.ENTER);
      });
    });

    it('shows all events when filters are "all"', async () => {
      const { result } = renderHook(() =>
        useZoneCrossingEvents({
          filters: { zoneId: 'zone-1', entityType: 'all', eventType: 'all' },
        })
      );

      act(() => {
        capturedHandlers['zone.enter'](createPayload({ zone_id: 'zone-1' }));
        capturedHandlers['zone.enter'](createPayload({ zone_id: 'zone-2' }));
      });

      await waitFor(() => {
        // Only zone-1 should be shown due to initial filter
        expect(result.current.events).toHaveLength(1);
      });

      // Reset to all
      act(() => {
        result.current.setFilters({ zoneId: 'all', entityType: 'all', eventType: 'all' });
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(2);
      });
    });
  });

  describe('onEvent callback', () => {
    it('calls onEvent when enter event is received', async () => {
      const onEvent = vi.fn();
      renderHook(() => useZoneCrossingEvents({ onEvent }));

      const payload = createPayload();

      act(() => {
        capturedHandlers['zone.enter'](payload);
      });

      await waitFor(() => {
        expect(onEvent).toHaveBeenCalledTimes(1);
        expect(onEvent).toHaveBeenCalledWith(
          expect.objectContaining({
            type: ZoneCrossingType.ENTER,
            zone_id: 'zone-1',
          })
        );
      });
    });

    it('calls onEvent when exit event is received', async () => {
      const onEvent = vi.fn();
      renderHook(() => useZoneCrossingEvents({ onEvent }));

      act(() => {
        capturedHandlers['zone.exit'](createPayload());
      });

      await waitFor(() => {
        expect(onEvent).toHaveBeenCalledWith(
          expect.objectContaining({ type: ZoneCrossingType.EXIT })
        );
      });
    });

    it('calls onEvent when dwell event is received', async () => {
      const onEvent = vi.fn();
      renderHook(() => useZoneCrossingEvents({ onEvent }));

      act(() => {
        capturedHandlers['zone.dwell'](createPayload());
      });

      await waitFor(() => {
        expect(onEvent).toHaveBeenCalledWith(
          expect.objectContaining({ type: ZoneCrossingType.DWELL })
        );
      });
    });
  });

  describe('invalid payload handling', () => {
    it('ignores invalid enter payload', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      act(() => {
        capturedHandlers['zone.enter']({ invalid: 'payload' });
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(0);
      });
    });

    it('ignores null payload', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      act(() => {
        capturedHandlers['zone.enter'](null);
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(0);
      });
    });

    it('ignores undefined payload', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      act(() => {
        capturedHandlers['zone.enter'](undefined);
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(0);
      });
    });

    it('ignores payload with missing required fields', async () => {
      const { result } = renderHook(() => useZoneCrossingEvents());

      act(() => {
        capturedHandlers['zone.enter']({
          zone_id: 'zone-1',
          // Missing other required fields
        });
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(0);
      });
    });
  });

  describe('connection state', () => {
    it('reflects WebSocket connection state', () => {
      mockIsConnected = false;
      mockReconnectCount = 3;
      mockHasExhaustedRetries = true;

      const { result } = renderHook(() => useZoneCrossingEvents());

      expect(result.current.isConnected).toBe(false);
      expect(result.current.reconnectCount).toBe(3);
      expect(result.current.hasExhaustedRetries).toBe(true);
    });
  });
});

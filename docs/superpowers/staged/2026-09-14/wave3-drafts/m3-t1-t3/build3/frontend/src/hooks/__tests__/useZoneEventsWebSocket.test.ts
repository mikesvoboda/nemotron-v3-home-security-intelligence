/**
 * Tests for useZoneEventsWebSocket hook (NEM-5073 - TDD Red Phase)
 *
 * Tests the WebSocket subscription functionality for zone-related events:
 * - zone.crossing
 * - zone.dwell_started
 * - zone.dwell_alert
 * - zone.approach
 *
 * These tests are written FIRST (TDD red phase) and will initially FAIL until
 * the hook is implemented in frontend/src/hooks/useZoneEventsWebSocket.ts.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

import { useZoneEventsWebSocket } from '../useZoneEventsWebSocket';
import * as webSocketManagerModule from '../webSocketManager';

import type { ConnectionConfig, TypedSubscriberOptions } from '../webSocketManager';

// Mock the webSocketManager module
vi.mock('../webSocketManager', async () => {
  const actual = await vi.importActual('../webSocketManager');
  return {
    ...actual,
    createTypedSubscription: vi.fn(),
  };
});

// Mock the logger
vi.mock('../../services/logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

// Define a simple mock subscription interface
interface MockSubscription {
  unsubscribe: ReturnType<typeof vi.fn>;
  emitter: Record<string, never>;
  on: ReturnType<typeof vi.fn>;
  off: ReturnType<typeof vi.fn>;
  once: ReturnType<typeof vi.fn>;
  send: ReturnType<typeof vi.fn>;
  getState: ReturnType<typeof vi.fn>;
}

describe('useZoneEventsWebSocket', () => {
  let mockSubscription: MockSubscription;
  let mockEventHandlers: Map<string, Array<(data: unknown) => void>>;

  beforeEach(() => {
    mockEventHandlers = new Map();

    mockSubscription = {
      unsubscribe: vi.fn(),
      emitter: {} as Record<string, never>,
      on: vi.fn((event: string, handler: (data: unknown) => void) => {
        const handlers = mockEventHandlers.get(event) || [];
        handlers.push(handler);
        mockEventHandlers.set(event, handlers);
        return () => {
          const currentHandlers = mockEventHandlers.get(event) || [];
          const index = currentHandlers.indexOf(handler);
          if (index > -1) {
            currentHandlers.splice(index, 1);
            mockEventHandlers.set(event, currentHandlers);
          }
        };
      }),
      off: vi.fn(),
      once: vi.fn(),
      send: vi.fn().mockReturnValue(true),
      getState: vi.fn().mockReturnValue({
        isConnected: true,
        reconnectCount: 0,
        hasExhaustedRetries: false,
        lastHeartbeat: null,
      }),
    };

    vi.mocked(webSocketManagerModule.createTypedSubscription).mockImplementation(
      (_url: string, _config: ConnectionConfig, options: TypedSubscriberOptions = {}) => {
        // Simulate immediate connection
        setTimeout(() => {
          options.onOpen?.();
        }, 0);
        // Return the mock subscription cast to the expected type
        return mockSubscription as unknown as webSocketManagerModule.TypedSubscription;
      }
    );
  });

  afterEach(() => {
    vi.clearAllMocks();
    mockEventHandlers.clear();
  });

  describe('zone.crossing events', () => {
    it('should receive zone.crossing events', async () => {
      const onZoneCrossing = vi.fn();

      renderHook(() =>
        useZoneEventsWebSocket({
          onZoneCrossing,
        })
      );

      await waitFor(() => {
        expect(mockSubscription.on).toHaveBeenCalledWith('zone.crossing', expect.any(Function));
      });

      // Simulate receiving a zone crossing event
      const zoneCrossingData = {
        zone_id: 'zone-123',
        zone_name: 'Front Door Area',
        entity_id: 'entity-456',
        entity_type: 'person',
        camera_id: 'front_door',
        timestamp: '2026-02-01T12:00:00Z',
        direction: 'entering',
      };

      const handlers = mockEventHandlers.get('zone.crossing');
      expect(handlers).toBeDefined();
      expect(handlers!.length).toBeGreaterThan(0);

      act(() => {
        handlers![0](zoneCrossingData);
      });

      expect(onZoneCrossing).toHaveBeenCalledWith(zoneCrossingData);
    });

    it('should validate zone.crossing event data', async () => {
      const onZoneCrossing = vi.fn();

      renderHook(() =>
        useZoneEventsWebSocket({
          onZoneCrossing,
        })
      );

      await waitFor(() => {
        expect(mockSubscription.on).toHaveBeenCalled();
      });

      // Simulate receiving invalid zone crossing event (missing required fields)
      const invalidData = {
        zone_id: 'zone-123',
        // Missing entity_id, camera_id, direction
      };

      const handlers = mockEventHandlers.get('zone.crossing');
      expect(handlers).toBeDefined();

      act(() => {
        handlers![0](invalidData);
      });

      // Should not call handler with invalid data
      expect(onZoneCrossing).not.toHaveBeenCalled();
    });
  });

  describe('zone.dwell_alert events', () => {
    it('should receive zone.dwell_alert events', async () => {
      const onZoneDwellAlert = vi.fn();

      renderHook(() =>
        useZoneEventsWebSocket({
          onZoneDwellAlert,
        })
      );

      await waitFor(() => {
        expect(mockSubscription.on).toHaveBeenCalledWith('zone.dwell_alert', expect.any(Function));
      });

      // Simulate receiving a zone dwell alert event
      const dwellAlertData = {
        zone_id: 'zone-789',
        zone_name: 'Restricted Area',
        entity_id: 'entity-123',
        entity_type: 'person',
        camera_id: 'restricted_cam',
        timestamp: '2026-02-01T12:05:00Z',
        dwell_duration_seconds: 300,
        threshold_seconds: 180,
      };

      const handlers = mockEventHandlers.get('zone.dwell_alert');
      expect(handlers).toBeDefined();
      expect(handlers!.length).toBeGreaterThan(0);

      act(() => {
        handlers![0](dwellAlertData);
      });

      expect(onZoneDwellAlert).toHaveBeenCalledWith(dwellAlertData);
    });

    it('should validate dwell duration and threshold values', async () => {
      const onZoneDwellAlert = vi.fn();

      renderHook(() =>
        useZoneEventsWebSocket({
          onZoneDwellAlert,
        })
      );

      await waitFor(() => {
        expect(mockSubscription.on).toHaveBeenCalled();
      });

      // Simulate receiving event with invalid threshold (negative)
      const invalidData = {
        zone_id: 'zone-789',
        zone_name: 'Area',
        entity_id: 'entity-123',
        entity_type: 'person',
        camera_id: 'cam',
        timestamp: '2026-02-01T12:05:00Z',
        dwell_duration_seconds: 100,
        threshold_seconds: -10, // Invalid
      };

      const handlers = mockEventHandlers.get('zone.dwell_alert');
      expect(handlers).toBeDefined();

      act(() => {
        handlers![0](invalidData);
      });

      // Should not call handler with invalid data
      expect(onZoneDwellAlert).not.toHaveBeenCalled();
    });
  });

  describe('multiple event subscriptions', () => {
    it('should handle multiple zone event types simultaneously', async () => {
      const onZoneCrossing = vi.fn();
      const onZoneDwellAlert = vi.fn();
      const onZoneApproach = vi.fn();

      renderHook(() =>
        useZoneEventsWebSocket({
          onZoneCrossing,
          onZoneDwellAlert,
          onZoneApproach,
        })
      );

      await waitFor(() => {
        expect(mockSubscription.on).toHaveBeenCalledWith('zone.crossing', expect.any(Function));
        expect(mockSubscription.on).toHaveBeenCalledWith('zone.dwell_alert', expect.any(Function));
        expect(mockSubscription.on).toHaveBeenCalledWith('zone.approach', expect.any(Function));
      });

      // Simulate receiving all three event types
      const crossingData = {
        zone_id: 'zone-1',
        zone_name: 'Gate',
        entity_id: 'entity-1',
        entity_type: 'person',
        camera_id: 'cam1',
        timestamp: '2026-02-01T12:00:00Z',
        direction: 'entering',
      };

      const dwellAlertData = {
        zone_id: 'zone-2',
        zone_name: 'Restricted',
        entity_id: 'entity-2',
        entity_type: 'person',
        camera_id: 'cam2',
        timestamp: '2026-02-01T12:01:00Z',
        dwell_duration_seconds: 200,
        threshold_seconds: 150,
      };

      const approachData = {
        zone_id: 'zone-3',
        zone_name: 'Entry',
        entity_id: 'entity-3',
        entity_type: 'vehicle',
        camera_id: 'cam3',
        timestamp: '2026-02-01T12:02:00Z',
        direction: 'north',
        speed: 2.5,
        eta_seconds: 10,
      };

      const crossingHandlers = mockEventHandlers.get('zone.crossing');
      const dwellHandlers = mockEventHandlers.get('zone.dwell_alert');
      const approachHandlers = mockEventHandlers.get('zone.approach');

      act(() => {
        crossingHandlers![0](crossingData);
        dwellHandlers![0](dwellAlertData);
        approachHandlers![0](approachData);
      });

      expect(onZoneCrossing).toHaveBeenCalledWith(crossingData);
      expect(onZoneDwellAlert).toHaveBeenCalledWith(dwellAlertData);
      expect(onZoneApproach).toHaveBeenCalledWith(approachData);
    });
  });

  describe('cleanup', () => {
    it('should unsubscribe on unmount', async () => {
      const onZoneCrossing = vi.fn();

      const { unmount } = renderHook(() =>
        useZoneEventsWebSocket({
          onZoneCrossing,
        })
      );

      await waitFor(() => {
        expect(mockSubscription.on).toHaveBeenCalled();
      });

      unmount();

      expect(mockSubscription.unsubscribe).toHaveBeenCalled();
    });

    it('should remove event handlers on unmount', async () => {
      const onZoneCrossing = vi.fn();
      const onZoneDwellAlert = vi.fn();

      const { unmount } = renderHook(() =>
        useZoneEventsWebSocket({
          onZoneCrossing,
          onZoneDwellAlert,
        })
      );

      await waitFor(() => {
        expect(mockSubscription.on).toHaveBeenCalled();
      });

      // Verify handlers are registered
      expect(mockEventHandlers.get('zone.crossing')?.length).toBeGreaterThan(0);
      expect(mockEventHandlers.get('zone.dwell_alert')?.length).toBeGreaterThan(0);

      unmount();

      // Handlers should be removed
      expect(mockEventHandlers.get('zone.crossing')?.length).toBe(0);
      expect(mockEventHandlers.get('zone.dwell_alert')?.length).toBe(0);
    });
  });

  describe('type guards', () => {
    it('should use type guards to validate zone.crossing event structure', async () => {
      const onZoneCrossing = vi.fn();

      renderHook(() =>
        useZoneEventsWebSocket({
          onZoneCrossing,
        })
      );

      await waitFor(() => {
        expect(mockSubscription.on).toHaveBeenCalled();
      });

      // Valid data with all required fields
      const validData = {
        zone_id: 'zone-123',
        zone_name: 'Area',
        entity_id: 'entity-456',
        entity_type: 'person',
        camera_id: 'cam',
        timestamp: '2026-02-01T12:00:00Z',
        direction: 'entering',
      };

      // Invalid data missing required fields
      const invalidData = {
        zone_id: 'zone-123',
        entity_id: 'entity-456',
        // Missing camera_id, timestamp, direction
      };

      const handlers = mockEventHandlers.get('zone.crossing');
      expect(handlers).toBeDefined();

      act(() => {
        handlers![0](validData);
        handlers![0](invalidData);
      });

      // Should only call handler once (for valid data)
      expect(onZoneCrossing).toHaveBeenCalledTimes(1);
      expect(onZoneCrossing).toHaveBeenCalledWith(validData);
    });

    it('should use type guards to validate zone.dwell_alert event structure', async () => {
      const onZoneDwellAlert = vi.fn();

      renderHook(() =>
        useZoneEventsWebSocket({
          onZoneDwellAlert,
        })
      );

      await waitFor(() => {
        expect(mockSubscription.on).toHaveBeenCalled();
      });

      // Valid data
      const validData = {
        zone_id: 'zone-789',
        zone_name: 'Area',
        entity_id: 'entity-123',
        entity_type: 'person',
        camera_id: 'cam',
        timestamp: '2026-02-01T12:05:00Z',
        dwell_duration_seconds: 300,
        threshold_seconds: 180,
      };

      // Invalid data - wrong field types
      const invalidData = {
        zone_id: 'zone-789',
        zone_name: 'Area',
        entity_id: 'entity-123',
        entity_type: 'person',
        camera_id: 'cam',
        timestamp: '2026-02-01T12:05:00Z',
        dwell_duration_seconds: 'invalid', // Should be number
        threshold_seconds: 180,
      };

      const handlers = mockEventHandlers.get('zone.dwell_alert');
      expect(handlers).toBeDefined();

      act(() => {
        handlers![0](validData);
        handlers![0](invalidData);
      });

      // Should only call handler once (for valid data)
      expect(onZoneDwellAlert).toHaveBeenCalledTimes(1);
      expect(onZoneDwellAlert).toHaveBeenCalledWith(validData);
    });
  });

  describe('connection state', () => {
    it('should provide connection state information', async () => {
      const onZoneCrossing = vi.fn();

      const { result } = renderHook(() =>
        useZoneEventsWebSocket({
          onZoneCrossing,
        })
      );

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      expect(result.current.reconnectCount).toBe(0);
      expect(result.current.hasExhaustedRetries).toBe(false);
    });
  });
});

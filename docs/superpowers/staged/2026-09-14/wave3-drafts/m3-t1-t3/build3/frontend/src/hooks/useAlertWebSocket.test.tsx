/**
 * Tests for useAlertWebSocket hook (NEM-2552, NEM-3125)
 *
 * This hook subscribes to WebSocket alert events and provides callbacks
 * for handling alert state changes (created, updated, deleted, acknowledged, resolved).
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, act } from '@testing-library/react';
import { type ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';

import { alertsQueryKeys } from './useAlertsQuery';
import { useAlertWebSocket } from './useAlertWebSocket';
import * as useWebSocketModule from './useWebSocket';
import { createQueryClient } from '../services/queryClient';

import type { WebSocketAlertData, WebSocketAlertDeletedData } from '../types/generated/websocket';

// Track the captured onMessage callback
let capturedOnMessage: ((data: unknown) => void) | undefined;

// Mock toast functions
const mockToast = {
  success: vi.fn().mockReturnValue('toast-1'),
  error: vi.fn().mockReturnValue('toast-2'),
  warning: vi.fn().mockReturnValue('toast-3'),
  info: vi.fn().mockReturnValue('toast-4'),
  loading: vi.fn().mockReturnValue('toast-5'),
  dismiss: vi.fn(),
  promise: vi.fn(),
};

// Mock the useWebSocket hook
vi.mock('./useWebSocket', () => ({
  useWebSocket: vi.fn(),
}));

// Mock the useToast hook
vi.mock('./useToast', () => ({
  useToast: vi.fn(() => mockToast),
}));

// Create a wrapper with QueryClient
function createWrapper(queryClient?: QueryClient) {
  const client = queryClient ?? createQueryClient();
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe('useAlertWebSocket', () => {
  let mockWebSocketReturn: ReturnType<typeof useWebSocketModule.useWebSocket>;

  // Helper to create mock alert data
  const createMockAlertData = (
    overrides: Partial<WebSocketAlertData> = {}
  ): WebSocketAlertData => ({
    id: 'alert-123',
    event_id: 1,
    rule_id: 'rule-456',
    severity: 'high',
    status: 'pending',
    dedup_key: 'front_door:person:rule1',
    created_at: '2026-01-13T10:00:00Z',
    updated_at: '2026-01-13T10:00:00Z',
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    capturedOnMessage = undefined;

    // Reset toast mocks
    mockToast.success.mockClear();
    mockToast.error.mockClear();
    mockToast.warning.mockClear();
    mockToast.info.mockClear();
    mockToast.loading.mockClear();
    mockToast.dismiss.mockClear();

    mockWebSocketReturn = {
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

    (useWebSocketModule.useWebSocket as Mock).mockImplementation(
      (options: useWebSocketModule.WebSocketOptions) => {
        // Capture the onMessage callback
        capturedOnMessage = options.onMessage;
        return mockWebSocketReturn;
      }
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('WebSocket subscription', () => {
    it('subscribes to WebSocket with correct URL', () => {
      renderHook(() => useAlertWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(useWebSocketModule.useWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({
          url: expect.stringContaining('ws'),
          reconnect: true,
          reconnectInterval: 1000,
          reconnectAttempts: 15,
          connectionTimeout: 10000,
          autoRespondToHeartbeat: true,
        })
      );
    });

    it('uses custom URL when provided', () => {
      const customUrl = 'ws://custom.example.com/ws/events';
      renderHook(() => useAlertWebSocket({ url: customUrl }), {
        wrapper: createWrapper(),
      });

      expect(useWebSocketModule.useWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({
          url: customUrl,
        })
      );
    });

    it('disables reconnect when enabled is false', () => {
      renderHook(() => useAlertWebSocket({ enabled: false }), {
        wrapper: createWrapper(),
      });

      expect(useWebSocketModule.useWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({
          reconnect: false,
        })
      );
    });
  });

  describe('alert_created event handling', () => {
    it('handles alert_created messages and calls callback', () => {
      const onAlertCreated = vi.fn();
      const alertData = createMockAlertData();

      renderHook(() => useAlertWebSocket({ onAlertCreated }), {
        wrapper: createWrapper(),
      });

      // Simulate alert_created message
      act(() => {
        capturedOnMessage?.({
          type: 'alert_created',
          data: alertData,
        });
      });

      expect(onAlertCreated).toHaveBeenCalledWith(alertData);
    });

    it('invalidates alerts cache on alert_created', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const alertData = createMockAlertData();

      renderHook(() => useAlertWebSocket({ autoInvalidateCache: true }), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_created',
          data: alertData,
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: alertsQueryKeys.all,
      });
    });
  });

  describe('alert_updated event handling', () => {
    it('handles alert_updated messages and calls callback', () => {
      const onAlertUpdated = vi.fn();
      const alertData = createMockAlertData({ status: 'delivered' });

      renderHook(() => useAlertWebSocket({ onAlertUpdated }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_updated',
          data: alertData,
        });
      });

      expect(onAlertUpdated).toHaveBeenCalledWith(alertData);
    });

    it('invalidates alerts cache on alert_updated', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const alertData = createMockAlertData();

      renderHook(() => useAlertWebSocket(), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_updated',
          data: alertData,
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: alertsQueryKeys.all,
      });
    });
  });

  describe('alert_acknowledged event handling', () => {
    it('handles alert_acknowledged messages and calls callback', () => {
      const onAlertAcknowledged = vi.fn();
      const alertData = createMockAlertData({ status: 'acknowledged' });

      renderHook(() => useAlertWebSocket({ onAlertAcknowledged }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_acknowledged',
          data: alertData,
        });
      });

      expect(onAlertAcknowledged).toHaveBeenCalledWith(alertData);
    });

    it('invalidates alerts cache on alert_acknowledged', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const alertData = createMockAlertData({ status: 'acknowledged' });

      renderHook(() => useAlertWebSocket(), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_acknowledged',
          data: alertData,
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: alertsQueryKeys.all,
      });
    });
  });

  describe('alert_resolved event handling', () => {
    it('handles alert_resolved messages and calls callback', () => {
      const onAlertResolved = vi.fn();
      const alertData = createMockAlertData({ status: 'dismissed' });

      renderHook(() => useAlertWebSocket({ onAlertResolved }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_resolved',
          data: alertData,
        });
      });

      expect(onAlertResolved).toHaveBeenCalledWith(alertData);
    });

    it('invalidates alerts cache on alert_resolved', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const alertData = createMockAlertData({ status: 'dismissed' });

      renderHook(() => useAlertWebSocket(), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_resolved',
          data: alertData,
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: alertsQueryKeys.all,
      });
    });
  });

  describe('alert_deleted event handling', () => {
    // Helper to create mock deleted alert data
    const createMockDeletedAlertData = (
      overrides: Partial<WebSocketAlertDeletedData> = {}
    ): WebSocketAlertDeletedData => ({
      id: 'alert-123',
      reason: 'Duplicate alert',
      ...overrides,
    });

    it('handles alert_deleted messages and calls callback', () => {
      const onAlertDeleted = vi.fn();
      const deletedData = createMockDeletedAlertData();

      renderHook(() => useAlertWebSocket({ onAlertDeleted }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_deleted',
          data: deletedData,
        });
      });

      expect(onAlertDeleted).toHaveBeenCalledWith(deletedData);
    });

    it('handles alert_deleted messages without reason', () => {
      const onAlertDeleted = vi.fn();
      const deletedData = createMockDeletedAlertData({ reason: null });

      renderHook(() => useAlertWebSocket({ onAlertDeleted }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_deleted',
          data: deletedData,
        });
      });

      expect(onAlertDeleted).toHaveBeenCalledWith(deletedData);
    });

    it('invalidates alerts cache on alert_deleted', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const deletedData = createMockDeletedAlertData();

      renderHook(() => useAlertWebSocket(), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_deleted',
          data: deletedData,
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: alertsQueryKeys.all,
      });
    });

    it('shows toast notification on alert_deleted', () => {
      const deletedData = createMockDeletedAlertData();

      renderHook(() => useAlertWebSocket({ showToasts: true }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_deleted',
          data: deletedData,
        });
      });

      expect(mockToast.info).toHaveBeenCalledWith('Alert dismissed', { duration: 3000 });
    });

    it('does not show toast when showToasts is false', () => {
      const deletedData = createMockDeletedAlertData();

      renderHook(() => useAlertWebSocket({ showToasts: false }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_deleted',
          data: deletedData,
        });
      });

      expect(mockToast.info).not.toHaveBeenCalled();
    });

    it('shows toast by default (showToasts true)', () => {
      const deletedData = createMockDeletedAlertData();

      renderHook(() => useAlertWebSocket(), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_deleted',
          data: deletedData,
        });
      });

      expect(mockToast.info).toHaveBeenCalledWith('Alert dismissed', { duration: 3000 });
    });
  });

  describe('cache invalidation control', () => {
    it('does not invalidate cache when autoInvalidateCache is false', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const alertData = createMockAlertData();

      renderHook(() => useAlertWebSocket({ autoInvalidateCache: false }), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_created',
          data: alertData,
        });
      });

      expect(invalidateSpy).not.toHaveBeenCalled();
    });

    it('invalidates cache by default (autoInvalidateCache true)', () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
      const alertData = createMockAlertData();

      renderHook(() => useAlertWebSocket(), {
        wrapper: createWrapper(queryClient),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_created',
          data: alertData,
        });
      });

      expect(invalidateSpy).toHaveBeenCalled();
    });
  });

  describe('onAnyAlertEvent callback', () => {
    it('calls onAnyAlertEvent for alert event types with full alert data', () => {
      const onAnyAlertEvent = vi.fn();
      const alertData = createMockAlertData();

      renderHook(() => useAlertWebSocket({ onAnyAlertEvent }), {
        wrapper: createWrapper(),
      });

      // Test all event types that have full alert data (alert_deleted is excluded
      // because it has a different data shape and uses onAlertDeleted callback instead)
      const eventTypes = ['alert_created', 'alert_updated', 'alert_acknowledged', 'alert_resolved'];

      eventTypes.forEach((eventType) => {
        act(() => {
          capturedOnMessage?.({
            type: eventType,
            data: alertData,
          });
        });
      });

      expect(onAnyAlertEvent).toHaveBeenCalledTimes(4);
      expect(onAnyAlertEvent).toHaveBeenCalledWith('alert_created', alertData);
      expect(onAnyAlertEvent).toHaveBeenCalledWith('alert_updated', alertData);
      expect(onAnyAlertEvent).toHaveBeenCalledWith('alert_acknowledged', alertData);
      expect(onAnyAlertEvent).toHaveBeenCalledWith('alert_resolved', alertData);
    });

    it('does not call onAnyAlertEvent for alert_deleted (uses different data shape)', () => {
      const onAnyAlertEvent = vi.fn();

      renderHook(() => useAlertWebSocket({ onAnyAlertEvent }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_deleted',
          data: { id: 'alert-123', reason: 'Test reason' },
        });
      });

      expect(onAnyAlertEvent).not.toHaveBeenCalled();
    });

    it('calls onAnyAlertEvent before specific handlers', () => {
      const callOrder: string[] = [];
      const onAnyAlertEvent = vi.fn(() => callOrder.push('any'));
      const onAlertCreated = vi.fn(() => callOrder.push('created'));
      const alertData = createMockAlertData();

      renderHook(() => useAlertWebSocket({ onAnyAlertEvent, onAlertCreated }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'alert_created',
          data: alertData,
        });
      });

      expect(callOrder).toEqual(['any', 'created']);
    });
  });

  describe('stale closure prevention', () => {
    it('uses latest callback references via refs', () => {
      const firstCallback = vi.fn();
      const secondCallback = vi.fn();
      const alertData = createMockAlertData();

      const { rerender } = renderHook(
        ({ onAlertCreated }) => useAlertWebSocket({ onAlertCreated }),
        {
          wrapper: createWrapper(),
          initialProps: { onAlertCreated: firstCallback },
        }
      );

      // Update the callback
      rerender({ onAlertCreated: secondCallback });

      // Trigger alert event
      act(() => {
        capturedOnMessage?.({
          type: 'alert_created',
          data: alertData,
        });
      });

      // Should call the latest callback, not the stale one
      expect(firstCallback).not.toHaveBeenCalled();
      expect(secondCallback).toHaveBeenCalledWith(alertData);
    });
  });

  describe('connection state management', () => {
    it('exposes isConnected state from useWebSocket', () => {
      mockWebSocketReturn.isConnected = true;

      const { result } = renderHook(() => useAlertWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isConnected).toBe(true);
    });

    it('exposes hasExhaustedRetries state', () => {
      mockWebSocketReturn.hasExhaustedRetries = true;

      const { result } = renderHook(() => useAlertWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(result.current.hasExhaustedRetries).toBe(true);
    });

    it('exposes reconnectCount state', () => {
      mockWebSocketReturn.reconnectCount = 3;

      const { result } = renderHook(() => useAlertWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(result.current.reconnectCount).toBe(3);
    });

    it('exposes connect and disconnect functions', () => {
      const { result } = renderHook(() => useAlertWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(typeof result.current.connect).toBe('function');
      expect(typeof result.current.disconnect).toBe('function');
    });
  });

  describe('reconnection attempts tracking', () => {
    it('tracks reconnection count', () => {
      mockWebSocketReturn.reconnectCount = 5;

      const { result } = renderHook(() => useAlertWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(result.current.reconnectCount).toBe(5);
    });

    it('indicates when max retries are exhausted', () => {
      mockWebSocketReturn.hasExhaustedRetries = true;
      mockWebSocketReturn.reconnectCount = 15;

      const { result } = renderHook(() => useAlertWebSocket(), {
        wrapper: createWrapper(),
      });

      expect(result.current.hasExhaustedRetries).toBe(true);
    });
  });

  describe('ignoring non-alert messages', () => {
    it('ignores event messages (not alert)', () => {
      const onAlertCreated = vi.fn();

      renderHook(() => useAlertWebSocket({ onAlertCreated }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'event',
          data: {
            id: 1,
            event_id: 1,
            batch_id: 'batch-1',
            camera_id: 'cam-1',
            risk_score: 75,
            risk_level: 'high',
            summary: 'Test event',
            reasoning: 'Test reasoning',
          },
        });
      });

      expect(onAlertCreated).not.toHaveBeenCalled();
    });

    it('ignores ping messages', () => {
      const onAnyAlertEvent = vi.fn();

      renderHook(() => useAlertWebSocket({ onAnyAlertEvent }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'ping',
        });
      });

      expect(onAnyAlertEvent).not.toHaveBeenCalled();
    });

    it('ignores service_status messages', () => {
      const onAnyAlertEvent = vi.fn();

      renderHook(() => useAlertWebSocket({ onAnyAlertEvent }), {
        wrapper: createWrapper(),
      });

      act(() => {
        capturedOnMessage?.({
          type: 'service_status',
          data: {
            service: 'redis',
            status: 'healthy',
          },
          timestamp: '2026-01-13T10:00:00Z',
        });
      });

      expect(onAnyAlertEvent).not.toHaveBeenCalled();
    });
  });

  describe('enabled option behavior', () => {
    it('calls disconnect when enabled becomes false', () => {
      const { rerender } = renderHook(({ enabled }) => useAlertWebSocket({ enabled }), {
        wrapper: createWrapper(),
        initialProps: { enabled: true },
      });

      // Disable the hook
      rerender({ enabled: false });

      expect(mockWebSocketReturn.disconnect).toHaveBeenCalled();
    });
  });
});

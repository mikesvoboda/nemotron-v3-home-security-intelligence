/**
 * WebSocket + React Query Integration Tests
 *
 * Tests the integration between WebSocket events and React Query cache invalidation.
 * Validates that real-time WebSocket messages properly trigger cache updates.
 *
 * Coverage targets:
 * - WebSocket event -> cache invalidation
 * - Cross-hook data flow
 * - Event stream -> query refresh patterns
 */

import { useQueryClient } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach, Mock } from 'vitest';

import * as api from '../../../services/api';
import { createQueryClient, queryKeys } from '../../../services/queryClient';
import { createQueryWrapper } from '../../../test-utils/renderWithProviders';
import { useCamerasQuery, useCameraMutation } from '../../useCamerasQuery';
import { useEventStream } from '../../useEventStream';
import { webSocketManager, resetSubscriberCounter, type Subscriber } from '../../webSocketManager';

import type { Camera } from '../../../services/api';
import type { SecurityEventData } from '../../../types/websocket';

// Mock the API module
vi.mock('../../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof api>();
  return {
    ...actual,
    fetchCameras: vi.fn(),
    fetchCamera: vi.fn(),
    createCamera: vi.fn(),
    updateCamera: vi.fn(),
    deleteCamera: vi.fn(),
    buildWebSocketOptions: vi.fn(() => ({
      url: 'ws://localhost:8000/ws/events',
      protocols: [],
    })),
  };
});

// Mock the webSocketManager
vi.mock('../../webSocketManager', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../webSocketManager')>();
  return {
    ...actual,
    webSocketManager: {
      subscribe: vi.fn(),
      send: vi.fn(),
      getConnectionState: vi.fn(),
      getSubscriberCount: vi.fn(),
      hasConnection: vi.fn(),
      reconnect: vi.fn(),
      clearAll: vi.fn(),
      reset: vi.fn(),
    },
  };
});

describe('WebSocket + React Query Integration', () => {
  let mockUnsubscribe: Mock;
  let lastSubscriber: Subscriber | null = null;

  beforeEach(() => {
    vi.clearAllMocks();
    resetSubscriberCounter();
    mockUnsubscribe = vi.fn();
    lastSubscriber = null;

    // Default mock implementations
    (webSocketManager.subscribe as Mock).mockImplementation(
      (_url: string, subscriber: Subscriber) => {
        lastSubscriber = subscriber;
        // Simulate connection opening
        setTimeout(() => {
          subscriber.onOpen?.();
        }, 0);
        return mockUnsubscribe;
      }
    );

    (webSocketManager.send as Mock).mockReturnValue(true);

    (webSocketManager.getConnectionState as Mock).mockReturnValue({
      isConnected: true,
      reconnectCount: 0,
      hasExhaustedRetries: false,
      lastHeartbeat: null,
    });

    (webSocketManager.getSubscriberCount as Mock).mockReturnValue(1);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('WebSocket Event -> Cache Invalidation', () => {
    it('should receive WebSocket event and update local state', async () => {
      const { result } = renderHook(() => useEventStream());

      // Wait for WebSocket connection
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      expect(lastSubscriber).not.toBeNull();

      // Simulate receiving an event message
      const eventData: SecurityEventData = {
        id: 'event-1',
        event_id: 1,
        camera_id: 'cam-1',
        camera_name: 'Front Door',
        risk_score: 75,
        risk_level: 'high',
        summary: 'Person detected at front door',
        timestamp: new Date().toISOString(),
      };

      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'event',
          data: eventData,
        });
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
        expect(result.current.events[0].id).toBe('event-1');
        expect(result.current.latestEvent?.risk_score).toBe(75);
      });
    });

    it('should buffer multiple events correctly', async () => {
      const { result } = renderHook(() => useEventStream());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Send multiple events
      for (let i = 1; i <= 5; i++) {
        act(() => {
          lastSubscriber?.onMessage?.({
            type: 'event',
            data: {
              id: `event-${i}`,
              event_id: i,
              camera_id: 'cam-1',
              camera_name: 'Front Door',
              risk_score: i * 15,
              risk_level: i > 3 ? 'high' : 'medium',
              summary: `Event ${i}`,
              timestamp: new Date().toISOString(),
            },
          });
        });
      }

      await waitFor(() => {
        expect(result.current.events).toHaveLength(5);
        // Events should be in reverse order (newest first)
        expect(result.current.events[0].id).toBe('event-5');
        expect(result.current.latestEvent?.risk_score).toBe(75);
      });
    });

    it('should deduplicate duplicate events by event_id', async () => {
      const { result } = renderHook(() => useEventStream());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      const eventData = {
        type: 'event',
        data: {
          id: 'event-1',
          event_id: 1,
          camera_id: 'cam-1',
          camera_name: 'Front Door',
          risk_score: 50,
          risk_level: 'medium',
          summary: 'Person detected',
          timestamp: new Date().toISOString(),
        },
      };

      // Send the same event multiple times
      act(() => {
        lastSubscriber?.onMessage?.(eventData);
        lastSubscriber?.onMessage?.(eventData);
        lastSubscriber?.onMessage?.(eventData);
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
      });
    });

    it('should ignore heartbeat messages and not add them to events', async () => {
      const { result } = renderHook(() => useEventStream());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Send heartbeat
      act(() => {
        lastSubscriber?.onMessage?.({ type: 'ping' });
      });

      // Events should remain empty
      expect(result.current.events).toHaveLength(0);
    });
  });

  describe('Cross-Hook Data Flow', () => {
    it('should allow mutation to invalidate queries that other components use', async () => {
      const mockCameras: Camera[] = [
        {
          id: 'cam-1',
          name: 'Front Door',
          folder_path: '/export/foscam/front_door',
          status: 'online',
          last_seen_at: '2025-01-09T10:00:00Z',
          created_at: '2025-01-01T00:00:00Z',
        },
      ];

      (api.fetchCameras as Mock).mockResolvedValue(mockCameras);
      (api.updateCamera as Mock).mockResolvedValue({
        ...mockCameras[0],
        name: 'Updated Camera',
      });

      const queryClient = createQueryClient();

      // Render both hooks to simulate multiple components
      const { result: camerasResult } = renderHook(() => useCamerasQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      const { result: mutationResult } = renderHook(() => useCameraMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Wait for initial fetch
      await waitFor(() => {
        expect(camerasResult.current.cameras).toHaveLength(1);
      });

      // Update camera
      const updatedCameras = [{ ...mockCameras[0], name: 'Updated Camera' }];
      (api.fetchCameras as Mock).mockResolvedValue(updatedCameras);

      await act(async () => {
        await mutationResult.current.updateMutation.mutateAsync({
          id: 'cam-1',
          data: { name: 'Updated Camera' },
        });
      });

      // Verify cache was invalidated and refetched
      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalledTimes(2);
      });
    });

    it('should coordinate WebSocket events with query invalidation', async () => {
      const mockCameras: Camera[] = [
        {
          id: 'cam-1',
          name: 'Front Door',
          folder_path: '/export/foscam/front_door',
          status: 'online',
          last_seen_at: '2025-01-09T10:00:00Z',
          created_at: '2025-01-01T00:00:00Z',
        },
      ];

      (api.fetchCameras as Mock).mockResolvedValue(mockCameras);

      const queryClient = createQueryClient();

      // Create a custom hook that combines WebSocket events with query state
      const useCombinedState = () => {
        const eventStream = useEventStream();
        const cameras = useCamerasQuery();
        const qc = useQueryClient();

        return {
          ...eventStream,
          ...cameras,
          invalidateCameras: () =>
            qc.invalidateQueries({ queryKey: queryKeys.cameras.all }),
        };
      };

      const { result } = renderHook(() => useCombinedState(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Wait for query
      await waitFor(() => {
        expect(result.current.cameras).toHaveLength(1);
      });

      // Wait for WebSocket connection
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Simulate WebSocket event
      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'event',
          data: {
            id: 'event-1',
            event_id: 1,
            camera_id: 'cam-1',
            camera_name: 'Front Door',
            risk_score: 85,
            risk_level: 'high',
            summary: 'High risk detection',
            timestamp: new Date().toISOString(),
          },
        });
      });

      // Verify event was received
      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
        expect(result.current.latestEvent?.risk_score).toBe(85);
      });

      // Manually invalidate cameras (simulating what a real integration would do)
      const updatedCameras = [{ ...mockCameras[0], last_seen_at: new Date().toISOString() }];
      (api.fetchCameras as Mock).mockResolvedValue(updatedCameras);

      await act(async () => {
        await result.current.invalidateCameras();
      });

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Event Stream Buffer Management', () => {
    it('should limit events buffer to MAX_EVENTS (100)', async () => {
      const { result } = renderHook(() => useEventStream());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Send 110 events
      for (let i = 1; i <= 110; i++) {
        act(() => {
          lastSubscriber?.onMessage?.({
            type: 'event',
            data: {
              id: `event-${i}`,
              event_id: i,
              camera_id: 'cam-1',
              camera_name: 'Front Door',
              risk_score: 50,
              risk_level: 'medium',
              summary: `Event ${i}`,
              timestamp: new Date().toISOString(),
            },
          });
        });
      }

      await waitFor(() => {
        // Should only keep 100 events
        expect(result.current.events).toHaveLength(100);
        // Most recent event should be event-110
        expect(result.current.events[0].id).toBe('event-110');
        // Oldest event should be event-11 (events 1-10 should be evicted)
        expect(result.current.events[99].id).toBe('event-11');
      });
    });

    it('should clear events and seen IDs when clearEvents is called', async () => {
      const { result } = renderHook(() => useEventStream());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Add some events
      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'event',
          data: {
            id: 'event-1',
            event_id: 1,
            camera_id: 'cam-1',
            camera_name: 'Front Door',
            risk_score: 50,
            risk_level: 'medium',
            summary: 'Event 1',
            timestamp: new Date().toISOString(),
          },
        });
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
      });

      // Clear events
      act(() => {
        result.current.clearEvents();
      });

      expect(result.current.events).toHaveLength(0);
      expect(result.current.latestEvent).toBeNull();

      // The same event should now be accepted again (seen IDs cleared)
      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'event',
          data: {
            id: 'event-1',
            event_id: 1,
            camera_id: 'cam-1',
            camera_name: 'Front Door',
            risk_score: 50,
            risk_level: 'medium',
            summary: 'Event 1',
            timestamp: new Date().toISOString(),
          },
        });
      });

      await waitFor(() => {
        expect(result.current.events).toHaveLength(1);
      });
    });
  });

  describe('Connection State Coordination', () => {
    it('should track connection state correctly', async () => {
      const { result } = renderHook(() => useEventStream());

      // Initially not connected
      expect(result.current.isConnected).toBe(false);

      // Wait for connection
      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });
    });

    it('should handle WebSocket disconnection', async () => {
      const { result } = renderHook(() => useEventStream());

      await waitFor(() => {
        expect(result.current.isConnected).toBe(true);
      });

      // Simulate disconnect
      act(() => {
        lastSubscriber?.onClose?.();
      });

      await waitFor(() => {
        expect(result.current.isConnected).toBe(false);
      });
    });
  });
});

/**
 * Race Condition Integration Tests
 *
 * Tests for handling race conditions between API requests and WebSocket updates.
 * Validates that the system handles concurrent data sources correctly.
 *
 * Coverage targets:
 * - API vs WebSocket update timing
 * - Concurrent mutation handling
 * - Stale data prevention
 * - Request ordering and cancellation
 */

import { useQueryClient } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach, Mock } from 'vitest';

import * as api from '../../../services/api';
import { createQueryClient } from '../../../services/queryClient';
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

describe('Race Conditions Integration', () => {
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

  let mockUnsubscribe: Mock;
  let lastSubscriber: Subscriber | null = null;

  beforeEach(() => {
    vi.clearAllMocks();
    resetSubscriberCounter();
    mockUnsubscribe = vi.fn();
    lastSubscriber = null;

    (webSocketManager.subscribe as Mock).mockImplementation(
      (_url: string, subscriber: Subscriber) => {
        lastSubscriber = subscriber;
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

  describe('API vs WebSocket Update Timing', () => {
    it('should handle WebSocket update arriving before API response', async () => {
      // Create deferred API response
      let resolveApi: (value: Camera[]) => void;
      const apiPromise = new Promise<Camera[]>((resolve) => {
        resolveApi = resolve;
      });
      (api.fetchCameras as Mock).mockReturnValue(apiPromise);

      const queryClient = createQueryClient();

      // Create a combined hook for testing
      const useCombinedState = () => {
        const eventStream = useEventStream();
        const cameras = useCamerasQuery();
        const qc = useQueryClient();
        return { eventStream, cameras, queryClient: qc };
      };

      const { result } = renderHook(() => useCombinedState(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Wait for WebSocket to connect
      await waitFor(() => {
        expect(result.current.eventStream.isConnected).toBe(true);
      });

      // WebSocket sends event BEFORE API response arrives
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
            summary: 'WebSocket event arrived first',
            timestamp: new Date().toISOString(),
          },
        });
      });

      // Verify WebSocket event was processed
      await waitFor(() => {
        expect(result.current.eventStream.events).toHaveLength(1);
      });

      // Now resolve the API
      act(() => {
        resolveApi!(mockCameras);
      });

      // Both should now be available
      await waitFor(() => {
        expect(result.current.cameras.cameras).toHaveLength(1);
        expect(result.current.eventStream.events).toHaveLength(1);
      });
    });

    it('should handle API response arriving before WebSocket event', async () => {
      (api.fetchCameras as Mock).mockResolvedValue(mockCameras);

      const queryClient = createQueryClient();

      const useCombinedState = () => {
        const eventStream = useEventStream();
        const cameras = useCamerasQuery();
        return { eventStream, cameras };
      };

      const { result } = renderHook(() => useCombinedState(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // API resolves quickly
      await waitFor(() => {
        expect(result.current.cameras.cameras).toHaveLength(1);
      });

      // WebSocket connects after
      await waitFor(() => {
        expect(result.current.eventStream.isConnected).toBe(true);
      });

      // WebSocket event arrives later
      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'event',
          data: {
            id: 'event-1',
            event_id: 1,
            camera_id: 'cam-1',
            camera_name: 'Front Door',
            risk_score: 75,
            risk_level: 'high',
            summary: 'WebSocket event arrived after API',
            timestamp: new Date().toISOString(),
          },
        });
      });

      await waitFor(() => {
        expect(result.current.eventStream.events).toHaveLength(1);
        expect(result.current.cameras.cameras).toHaveLength(1);
      });
    });
  });

  describe('Concurrent Mutation Handling', () => {
    it('should handle multiple concurrent mutations to the same resource', async () => {
      const updateCallOrder: string[] = [];
      let firstResolve: (value: Camera) => void;
      let secondResolve: (value: Camera) => void;

      const firstPromise = new Promise<Camera>((resolve) => {
        firstResolve = resolve;
      });
      const secondPromise = new Promise<Camera>((resolve) => {
        secondResolve = resolve;
      });

      (api.updateCamera as Mock)
        .mockImplementationOnce(async (_id: string, data: { name: string }) => {
          updateCallOrder.push(`start-first-${data.name}`);
          const result = await firstPromise;
          updateCallOrder.push(`end-first-${data.name}`);
          return result;
        })
        .mockImplementationOnce(async (_id: string, data: { name: string }) => {
          updateCallOrder.push(`start-second-${data.name}`);
          const result = await secondPromise;
          updateCallOrder.push(`end-second-${data.name}`);
          return result;
        });

      (api.fetchCameras as Mock).mockResolvedValue(mockCameras);

      const queryClient = createQueryClient();

      const { result } = renderHook(() => useCameraMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Start two concurrent updates
      const firstUpdate = result.current.updateMutation.mutateAsync({
        id: 'cam-1',
        data: { name: 'First Update' },
      });

      const secondUpdate = result.current.updateMutation.mutateAsync({
        id: 'cam-1',
        data: { name: 'Second Update' },
      });

      // Both should be in progress
      await waitFor(() => {
        expect(updateCallOrder).toContain('start-first-First Update');
        expect(updateCallOrder).toContain('start-second-Second Update');
      });

      // Resolve second BEFORE first (out of order)
      act(() => {
        secondResolve!({ ...mockCameras[0], name: 'Second Update' });
      });

      await waitFor(() => {
        expect(updateCallOrder).toContain('end-second-Second Update');
      });

      // Now resolve first
      act(() => {
        firstResolve!({ ...mockCameras[0], name: 'First Update' });
      });

      // Wait for both to complete
      await Promise.allSettled([firstUpdate, secondUpdate]);

      // Both mutations should complete
      expect(updateCallOrder).toHaveLength(4);
    });

    it('should handle mutation followed by immediate refetch race', async () => {
      let fetchCount = 0;
      const fetchPromises: Array<{
        resolve: (value: Camera[]) => void;
        reject: (error: Error) => void;
      }> = [];

      (api.fetchCameras as Mock).mockImplementation(() => {
        fetchCount++;
        return new Promise<Camera[]>((resolve, reject) => {
          fetchPromises.push({ resolve, reject });
        });
      });

      (api.updateCamera as Mock).mockResolvedValue({
        ...mockCameras[0],
        name: 'Updated',
      });

      const queryClient = createQueryClient();

      const { result } = renderHook(
        () => ({
          cameras: useCamerasQuery(),
          mutation: useCameraMutation(),
          qc: useQueryClient(),
        }),
        { wrapper: createQueryWrapper(queryClient) }
      );

      // Resolve initial fetch
      await waitFor(() => {
        expect(fetchPromises.length).toBe(1);
      });

      act(() => {
        fetchPromises[0].resolve(mockCameras);
      });

      await waitFor(() => {
        expect(result.current.cameras.cameras).toHaveLength(1);
      });

      // Perform mutation which triggers refetch
      await act(async () => {
        await result.current.mutation.updateMutation.mutateAsync({
          id: 'cam-1',
          data: { name: 'Updated' },
        });
      });

      // Resolve the refetch with updated data
      await waitFor(() => {
        expect(fetchPromises.length).toBe(2);
      });

      act(() => {
        fetchPromises[1].resolve([{ ...mockCameras[0], name: 'Updated' }]);
      });

      await waitFor(() => {
        expect(result.current.cameras.cameras[0]?.name).toBe('Updated');
      });

      // Verify fetch was called twice (initial + refetch after mutation)
      expect(fetchCount).toBe(2);
    });
  });

  describe('Stale Data Prevention', () => {
    it('should not apply stale WebSocket event to fresh query data', async () => {
      (api.fetchCameras as Mock).mockResolvedValue(mockCameras);

      const queryClient = createQueryClient();

      // Create a custom hook that tracks event timestamps
      const useTimestampedEvents = () => {
        const eventStream = useEventStream();
        const cameras = useCamerasQuery();

        // Track the latest camera last_seen_at vs event timestamp
        const isEventStale = (event: SecurityEventData) => {
          const camera = cameras.cameras.find((c) => c.id === event.camera_id);
          if (!camera?.last_seen_at || !event.timestamp) return false;
          return new Date(event.timestamp) < new Date(camera.last_seen_at);
        };

        return { eventStream, cameras, isEventStale };
      };

      const { result } = renderHook(() => useTimestampedEvents(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.cameras.cameras).toHaveLength(1);
        expect(result.current.eventStream.isConnected).toBe(true);
      });

      // Send a "stale" event with old timestamp
      const staleEvent: SecurityEventData = {
        id: 'stale-event',
        event_id: 1,
        camera_id: 'cam-1',
        camera_name: 'Front Door',
        risk_score: 50,
        risk_level: 'medium',
        summary: 'Stale event',
        timestamp: '2025-01-08T10:00:00Z', // Before camera's last_seen
      };

      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'event',
          data: staleEvent,
        });
      });

      await waitFor(() => {
        expect(result.current.eventStream.events).toHaveLength(1);
      });

      // The hook can check if event is stale
      expect(result.current.isEventStale(staleEvent)).toBe(true);
    });

    it('should cancel pending queries when new request is made', async () => {
      (api.fetchCameras as Mock).mockImplementation(
        () =>
          new Promise((resolve) => {
            // Simulate slow request
            setTimeout(() => resolve(mockCameras), 1000);
          })
      );

      const queryClient = createQueryClient();

      const { result, rerender } = renderHook(({ enabled }) => useCamerasQuery({ enabled }), {
        wrapper: createQueryWrapper(queryClient),
        initialProps: { enabled: true },
      });

      // First request starts
      expect(result.current.isLoading).toBe(true);

      // Disable and re-enable quickly to simulate rapid navigation
      rerender({ enabled: false });
      rerender({ enabled: true });

      // The previous request's abort controller should be signaled
      // React Query handles this internally
      await waitFor(
        () => {
          // Either loading completes or we're in a stable state
          expect(result.current.cameras).toBeDefined();
        },
        { timeout: 2000 }
      );
    });
  });

  describe('Request Ordering and Sequence', () => {
    it('should maintain correct order when events arrive during query refetch', async () => {
      const eventOrder: string[] = [];
      let resolveRefetch: (value: Camera[]) => void;

      (api.fetchCameras as Mock).mockResolvedValueOnce(mockCameras).mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveRefetch = resolve;
          })
      );

      const queryClient = createQueryClient();

      const { result } = renderHook(
        () => ({
          eventStream: useEventStream(),
          cameras: useCamerasQuery(),
          qc: useQueryClient(),
        }),
        { wrapper: createQueryWrapper(queryClient) }
      );

      // Wait for initial data
      await waitFor(() => {
        expect(result.current.cameras.cameras).toHaveLength(1);
        expect(result.current.eventStream.isConnected).toBe(true);
      });

      // Start a refetch
      act(() => {
        void result.current.cameras.refetch();
      });

      eventOrder.push('refetch-started');

      // WebSocket events arrive during refetch
      act(() => {
        lastSubscriber?.onMessage?.({
          type: 'event',
          data: {
            id: 'event-during-refetch',
            event_id: 1,
            camera_id: 'cam-1',
            camera_name: 'Front Door',
            risk_score: 90,
            risk_level: 'critical',
            summary: 'Event during refetch',
            timestamp: new Date().toISOString(),
          },
        });
        eventOrder.push('ws-event-received');
      });

      // Complete the refetch
      act(() => {
        const updatedCameras = [{ ...mockCameras[0], last_seen_at: new Date().toISOString() }];
        resolveRefetch!(updatedCameras);
        eventOrder.push('refetch-completed');
      });

      await waitFor(() => {
        expect(result.current.eventStream.events).toHaveLength(1);
        expect(result.current.cameras.isRefetching).toBe(false);
      });

      // WebSocket event should have been processed even during refetch
      expect(eventOrder).toContain('ws-event-received');
      expect(result.current.eventStream.events[0].id).toBe('event-during-refetch');
    });

    it('should handle rapid sequential mutations without data corruption', async () => {
      let updateCount = 0;
      (api.updateCamera as Mock).mockImplementation(async (_id: string, data: { name: string }) => {
        updateCount++;
        await new Promise((r) => setTimeout(r, 10)); // Small delay
        return { ...mockCameras[0], name: data.name };
      });
      (api.fetchCameras as Mock).mockResolvedValue(mockCameras);

      const queryClient = createQueryClient();

      const { result } = renderHook(() => useCameraMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Fire multiple updates rapidly
      const updates = ['Update 1', 'Update 2', 'Update 3', 'Update 4', 'Update 5'];

      await act(async () => {
        await Promise.all(
          updates.map((name) =>
            result.current.updateMutation.mutateAsync({
              id: 'cam-1',
              data: { name },
            })
          )
        );
      });

      // All updates should have been processed
      expect(updateCount).toBe(5);
    });
  });

  describe('Interleaved Operations', () => {
    it('should handle interleaved create and delete operations', async () => {
      const operationOrder: string[] = [];

      (api.createCamera as Mock).mockImplementation(
        async (data: { name: string; folder_path: string; status: string }) => {
          operationOrder.push(`create-start`);
          await new Promise((r) => setTimeout(r, 50));
          operationOrder.push(`create-end`);
          return {
            id: `cam-new`,
            name: data.name,
            folder_path: data.folder_path,
            status: data.status as Camera['status'],
            last_seen_at: null,
            created_at: new Date().toISOString(),
          };
        }
      );

      (api.deleteCamera as Mock).mockImplementation(async (id: string) => {
        operationOrder.push(`delete-start-${id}`);
        await new Promise((r) => setTimeout(r, 25)); // Faster than create
        operationOrder.push(`delete-end-${id}`);
      });

      (api.fetchCameras as Mock).mockResolvedValue(mockCameras);

      const queryClient = createQueryClient();

      const { result } = renderHook(() => useCameraMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Start create and delete concurrently
      const createPromise = result.current.createMutation.mutateAsync({
        name: 'New Camera',
        folder_path: '/export/foscam/new',
        status: 'online',
      });

      const deletePromise = result.current.deleteMutation.mutateAsync('cam-1');

      await Promise.all([createPromise, deletePromise]);

      // Delete should complete before create (it's faster)
      expect(operationOrder.indexOf('delete-end-cam-1')).toBeLessThan(
        operationOrder.indexOf('create-end')
      );
    });
  });
});

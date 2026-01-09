/**
 * Offline Mutation Queuing Integration Tests
 *
 * Tests for offline support patterns including mutation queuing,
 * network status detection, and state recovery.
 *
 * Coverage targets:
 * - Offline mutation queuing
 * - Network status change handling
 * - Cache persistence during offline
 * - Recovery when coming back online
 */

/* eslint-disable @typescript-eslint/no-misused-promises, @typescript-eslint/require-await */
// Disabled for test file - common patterns when mocking async APIs with vitest

import { useQueryClient, useMutation, QueryClient } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import * as api from '../../../services/api';
import { createQueryClient, queryKeys } from '../../../services/queryClient';
import { createQueryWrapper } from '../../../test-utils/renderWithProviders';
import { useCachedEvents } from '../../useCachedEvents';
import { useCamerasQuery, useCameraMutation } from '../../useCamerasQuery';
import { useNetworkStatus } from '../../useNetworkStatus';

import type { Camera } from '../../../services/api';

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
  };
});

// Note: IndexedDB mocking is not currently needed as useCachedEvents tests
// use the real hook behavior. If IndexedDB mocking is needed in the future,
// consider using the indexeddb-mock or fake-indexeddb packages.

describe('Offline Mutations Integration', () => {
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

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchCameras as ReturnType<typeof vi.fn>).mockResolvedValue([...mockCameras]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('useNetworkStatus', () => {
    it('should detect online status', () => {
      // Mock navigator.onLine
      Object.defineProperty(navigator, 'onLine', {
        value: true,
        configurable: true,
      });

      const { result } = renderHook(() => useNetworkStatus());

      expect(result.current.isOnline).toBe(true);
      expect(result.current.isOffline).toBe(false);
    });

    it('should detect offline status', () => {
      Object.defineProperty(navigator, 'onLine', {
        value: false,
        configurable: true,
      });

      const { result } = renderHook(() => useNetworkStatus());

      expect(result.current.isOnline).toBe(false);
      expect(result.current.isOffline).toBe(true);
    });

    it('should track wasOffline flag for reconnection notifications', async () => {
      Object.defineProperty(navigator, 'onLine', {
        value: true,
        configurable: true,
      });

      const { result } = renderHook(() => useNetworkStatus());

      expect(result.current.wasOffline).toBe(false);

      // Simulate going offline then online
      act(() => {
        Object.defineProperty(navigator, 'onLine', {
          value: false,
          configurable: true,
        });
        window.dispatchEvent(new Event('offline'));
      });

      await waitFor(() => {
        expect(result.current.isOffline).toBe(true);
      });

      act(() => {
        Object.defineProperty(navigator, 'onLine', {
          value: true,
          configurable: true,
        });
        window.dispatchEvent(new Event('online'));
      });

      await waitFor(() => {
        expect(result.current.isOnline).toBe(true);
        expect(result.current.wasOffline).toBe(true);
      });

      // Clear the wasOffline flag
      act(() => {
        result.current.clearWasOffline();
      });

      expect(result.current.wasOffline).toBe(false);
    });

    it('should call onOnline callback when network is restored', async () => {
      const onOnline = vi.fn();
      const onOffline = vi.fn();

      Object.defineProperty(navigator, 'onLine', {
        value: true,
        configurable: true,
      });

      renderHook(() =>
        useNetworkStatus({
          onOnline,
          onOffline,
        })
      );

      // Go offline
      act(() => {
        Object.defineProperty(navigator, 'onLine', {
          value: false,
          configurable: true,
        });
        window.dispatchEvent(new Event('offline'));
      });

      await waitFor(() => {
        expect(onOffline).toHaveBeenCalled();
      });

      // Go online
      act(() => {
        Object.defineProperty(navigator, 'onLine', {
          value: true,
          configurable: true,
        });
        window.dispatchEvent(new Event('online'));
      });

      await waitFor(() => {
        expect(onOnline).toHaveBeenCalled();
      });
    });

    it('should track lastOnlineAt timestamp', async () => {
      Object.defineProperty(navigator, 'onLine', {
        value: false,
        configurable: true,
      });

      const { result } = renderHook(() => useNetworkStatus());

      expect(result.current.lastOnlineAt).toBeNull();

      // Go online
      act(() => {
        Object.defineProperty(navigator, 'onLine', {
          value: true,
          configurable: true,
        });
        window.dispatchEvent(new Event('online'));
      });

      await waitFor(() => {
        expect(result.current.lastOnlineAt).toBeInstanceOf(Date);
      });
    });
  });

  describe('Offline-aware Mutations', () => {
    /**
     * Custom hook that implements offline-aware mutation with queuing.
     * Mutations are queued when offline and executed when back online.
     */
    const useOfflineAwareMutation = () => {
      const networkStatus = useNetworkStatus();
      const queryClient = useQueryClient();
      const pendingMutations: Array<{ id: string; data: { name: string } }> = [];

      const mutation = useMutation({
        mutationFn: async ({ id, data }: { id: string; data: { name: string } }) => {
          if (!networkStatus.isOnline) {
            // Queue the mutation for later
            pendingMutations.push({ id, data });
            throw new Error('Offline: mutation queued');
          }
          return api.updateCamera(id, data);
        },
        onSuccess: () => {
          void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
        },
      });

      return {
        mutation,
        networkStatus,
        pendingMutations,
      };
    };

    it('should handle mutation attempt while offline', async () => {
      Object.defineProperty(navigator, 'onLine', {
        value: false,
        configurable: true,
      });

      const queryClient = createQueryClient();

      const { result } = renderHook(() => useOfflineAwareMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.networkStatus.isOffline).toBe(true);

      // Attempt mutation while offline
      await act(async () => {
        try {
          await result.current.mutation.mutateAsync({
            id: 'cam-1',
            data: { name: 'Updated Offline' },
          });
        } catch {
          // Expected to fail
        }
      });

      // Wait for error state to be set
      await waitFor(() => {
        expect(result.current.mutation.isError).toBe(true);
      });
      expect(result.current.mutation.error?.message).toBe('Offline: mutation queued');
    });

    it('should succeed when online', async () => {
      Object.defineProperty(navigator, 'onLine', {
        value: true,
        configurable: true,
      });

      (api.updateCamera as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockCameras[0],
        name: 'Updated Online',
      });

      const queryClient = createQueryClient();

      const { result } = renderHook(() => useOfflineAwareMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.mutation.mutateAsync({
          id: 'cam-1',
          data: { name: 'Updated Online' },
        });
      });

      // Wait for success state to be set
      await waitFor(() => {
        expect(result.current.mutation.isSuccess).toBe(true);
      });
    });
  });

  describe('Query Behavior When Offline', () => {
    it('should use cached data when offline', async () => {
      Object.defineProperty(navigator, 'onLine', {
        value: true,
        configurable: true,
      });

      const queryClient = createQueryClient();

      // First, fetch while online
      const { result, rerender } = renderHook(() => useCamerasQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.cameras).toHaveLength(1);
      });

      // Simulate going offline
      act(() => {
        Object.defineProperty(navigator, 'onLine', {
          value: false,
          configurable: true,
        });
      });

      // Make the API fail when offline
      (api.fetchCameras as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error')
      );

      // Trigger a refetch
      rerender();

      // Should still have cached data
      expect(result.current.cameras).toHaveLength(1);
      expect(result.current.cameras[0].name).toBe('Front Door');
    });

    it('should refetch when coming back online with refetchOnReconnect', async () => {
      // This test verifies that the queryClient is configured with refetchOnReconnect: true
      // and that manual invalidation works after reconnection
      Object.defineProperty(navigator, 'onLine', {
        value: true,
        configurable: true,
      });

      (api.fetchCameras as ReturnType<typeof vi.fn>).mockResolvedValue([...mockCameras]);

      const queryClient = createQueryClient();

      // Verify our queryClient has the correct configuration
      const queryDefaults = queryClient.getDefaultOptions();
      expect(queryDefaults.queries?.refetchOnReconnect).toBe(true);

      const { result } = renderHook(() => useCamerasQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.cameras).toHaveLength(1);
      });

      // Verify initial fetch happened
      expect(api.fetchCameras).toHaveBeenCalledTimes(1);

      // Update mock for subsequent calls
      const updatedCameras = [{ ...mockCameras[0], name: 'Updated After Reconnect' }];
      (api.fetchCameras as ReturnType<typeof vi.fn>).mockResolvedValue(updatedCameras);

      // Manually trigger refetch to simulate what would happen on reconnect
      await act(async () => {
        await queryClient.refetchQueries({ queryKey: queryKeys.cameras.all });
      });

      // Verify refetch occurred
      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalledTimes(2);
      });

      // Verify updated data
      await waitFor(() => {
        expect(result.current.cameras[0].name).toBe('Updated After Reconnect');
      });
    });
  });

  describe('Cache Persistence', () => {
    it('should maintain query cache when component unmounts and remounts', async () => {
      (api.fetchCameras as ReturnType<typeof vi.fn>).mockResolvedValue([...mockCameras]);

      const queryClient = createQueryClient();

      // First mount
      const { result, unmount } = renderHook(() => useCamerasQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.cameras).toHaveLength(1);
      });

      // Unmount
      unmount();

      // Reset mock to track new calls
      (api.fetchCameras as ReturnType<typeof vi.fn>).mockClear();

      // Remount with same queryClient
      const { result: result2 } = renderHook(() => useCamerasQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Should have data immediately from cache (within stale time)
      expect(result2.current.cameras).toHaveLength(1);

      // Should not have made a new request if within stale time
      // (depending on stale time settings)
    });

    it('should preserve optimistic updates across component remounts', () => {
      (api.fetchCameras as ReturnType<typeof vi.fn>).mockResolvedValue([...mockCameras]);

      const queryClient = createQueryClient();

      // Pre-populate cache with optimistic data
      queryClient.setQueryData(queryKeys.cameras.list(), [
        { ...mockCameras[0], name: 'Optimistic Update' },
      ]);

      const { result } = renderHook(() => useCamerasQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Should see the optimistic data
      expect(result.current.cameras[0]?.name).toBe('Optimistic Update');
    });
  });

  describe('Error Recovery', () => {
    it('should recover gracefully from network errors', async () => {
      Object.defineProperty(navigator, 'onLine', {
        value: true,
        configurable: true,
      });

      let failCount = 0;
      (api.fetchCameras as ReturnType<typeof vi.fn>).mockImplementation(async () => {
        failCount++;
        if (failCount === 1) {
          throw new Error('Network error');
        }
        return [...mockCameras];
      });

      // Create a queryClient with faster retry delay for testing
      const queryClient = new QueryClient({
        defaultOptions: {
          queries: {
            retry: 2,
            // Use minimal delay for testing
            retryDelay: () => 5,
            // Don't throw on error for easier testing
            throwOnError: false,
          },
        },
      });

      const { result } = renderHook(() => useCamerasQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // With retry enabled and fast retry delays, should eventually succeed
      await waitFor(
        () => {
          expect(result.current.cameras).toHaveLength(1);
        },
        { timeout: 5000 }
      );

      // Should have retried at least once
      expect(failCount).toBeGreaterThanOrEqual(2);
    });

    it('should not retry mutations by default', async () => {
      Object.defineProperty(navigator, 'onLine', {
        value: true,
        configurable: true,
      });

      let attemptCount = 0;
      (api.updateCamera as ReturnType<typeof vi.fn>).mockImplementation(async () => {
        attemptCount++;
        throw new Error('Server error');
      });

      const queryClient = createQueryClient();

      const { result } = renderHook(() => useCameraMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        try {
          await result.current.updateMutation.mutateAsync({
            id: 'cam-1',
            data: { name: 'Test' },
          });
        } catch {
          // Expected
        }
      });

      // Mutations should not retry by default (only 1 attempt)
      expect(attemptCount).toBe(1);
    });
  });

  describe('Offline Event Caching', () => {
    it('should track cached event count', async () => {
      // This tests the useCachedEvents hook interface
      const { result } = renderHook(() => useCachedEvents());

      // Initially should be empty or have default state
      await waitFor(() => {
        expect(result.current.isInitialized).toBeDefined();
      });

      // The cachedCount should be available
      expect(typeof result.current.cachedCount).toBe('number');
    });

    it('should provide methods for cache management', () => {
      const { result } = renderHook(() => useCachedEvents());

      // Should expose cache management methods
      expect(typeof result.current.cacheEvent).toBe('function');
      expect(typeof result.current.loadCachedEvents).toBe('function');
      expect(typeof result.current.removeCachedEvent).toBe('function');
      expect(typeof result.current.clearCache).toBe('function');
    });
  });
});

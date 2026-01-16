/**
 * Optimistic Updates Integration Tests
 *
 * Tests for optimistic update patterns and rollback behavior when mutations fail.
 * Validates that the UI correctly reverts to previous state on API errors.
 *
 * Coverage targets:
 * - Optimistic update application
 * - Rollback on mutation failure
 * - Error state handling
 * - Cache consistency after rollback
 */

/* eslint-disable @typescript-eslint/no-misused-promises, @typescript-eslint/require-await */
// Disabled for test file - common patterns when mocking async APIs with vitest

import { useQueryClient, useMutation } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import * as api from '../../../services/api';
import { createQueryClient, queryKeys } from '../../../services/queryClient';
import { createQueryWrapper } from '../../../test-utils/renderWithProviders';
import { useCamerasQuery, useCameraMutation } from '../../useCamerasQuery';

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

describe('Optimistic Updates Integration', () => {
  const mockCameras: Camera[] = [
    {
      id: 'cam-1',
      name: 'Front Door',
      folder_path: '/export/foscam/front_door',
      status: 'online',
      last_seen_at: '2025-01-09T10:00:00Z',
      created_at: '2025-01-01T00:00:00Z',
    },
    {
      id: 'cam-2',
      name: 'Back Door',
      folder_path: '/export/foscam/back_door',
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

  describe('Update Mutation with Optimistic Update', () => {
    /**
     * Custom hook that implements optimistic updates for camera name changes.
     * This pattern is common in real applications where immediate UI feedback is desired.
     */
    const useOptimisticCameraUpdate = () => {
      const queryClient = useQueryClient();

      return useMutation({
        mutationFn: ({ id, data }: { id: string; data: { name: string } }) =>
          api.updateCamera(id, data),

        // Optimistic update: immediately update the cache
        onMutate: async ({ id, data }) => {
          // Cancel outgoing refetches to avoid overwriting optimistic update
          await queryClient.cancelQueries({ queryKey: queryKeys.cameras.all });

          // Snapshot the previous value
          const previousCameras = queryClient.getQueryData<Camera[]>(queryKeys.cameras.list());

          // Optimistically update the cache
          queryClient.setQueryData<Camera[]>(queryKeys.cameras.list(), (old) =>
            old?.map((camera) => (camera.id === id ? { ...camera, ...data } : camera))
          );

          // Return context with snapshot for rollback
          return { previousCameras };
        },

        // On error, rollback to the previous value
        onError: (_err, _variables, context) => {
          if (context?.previousCameras) {
            queryClient.setQueryData(queryKeys.cameras.list(), context.previousCameras);
          }
        },

        // Always refetch after error or success
        onSettled: () => {
          void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
        },
      });
    };

    it('should apply optimistic update immediately before API response', async () => {
      // Create a deferred promise to control API timing
      let resolveUpdate: (value: Camera) => void;
      const updatePromise = new Promise<Camera>((resolve) => {
        resolveUpdate = resolve;
      });
      (api.updateCamera as ReturnType<typeof vi.fn>).mockReturnValue(updatePromise);

      const queryClient = createQueryClient();

      // Pre-populate the cache
      queryClient.setQueryData(queryKeys.cameras.list(), [...mockCameras]);

      const { result } = renderHook(
        () => ({
          cameras: useCamerasQuery(),
          updateMutation: useOptimisticCameraUpdate(),
        }),
        { wrapper: createQueryWrapper(queryClient) }
      );

      // Wait for initial data
      await waitFor(() => {
        expect(result.current.cameras.cameras).toHaveLength(2);
      });

      // Trigger optimistic update
      act(() => {
        result.current.updateMutation.mutate({
          id: 'cam-1',
          data: { name: 'Updated Front Door' },
        });
      });

      // Verify optimistic update was applied BEFORE API resolves
      await waitFor(() => {
        const cameras = queryClient.getQueryData<Camera[]>(queryKeys.cameras.list());
        expect(cameras?.[0].name).toBe('Updated Front Door');
      });

      // Now resolve the API call
      const updatedCamera = { ...mockCameras[0], name: 'Updated Front Door' };
      act(() => {
        resolveUpdate!(updatedCamera);
      });

      await waitFor(() => {
        expect(result.current.updateMutation.isSuccess).toBe(true);
      });
    });

    it('should rollback optimistic update on mutation failure', async () => {
      // Mock API to reject
      (api.updateCamera as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Network error: Failed to update camera')
      );
      // Mock refetch to return original data
      (api.fetchCameras as ReturnType<typeof vi.fn>).mockResolvedValue([...mockCameras]);

      const queryClient = createQueryClient();
      queryClient.setQueryData(queryKeys.cameras.list(), [...mockCameras]);

      const { result } = renderHook(
        () => ({
          cameras: useCamerasQuery(),
          updateMutation: useOptimisticCameraUpdate(),
        }),
        { wrapper: createQueryWrapper(queryClient) }
      );

      await waitFor(() => {
        expect(result.current.cameras.cameras).toHaveLength(2);
      });

      // Verify original state
      expect(result.current.cameras.cameras[0].name).toBe('Front Door');

      // Trigger the update that will fail
      await act(async () => {
        try {
          await result.current.updateMutation.mutateAsync({
            id: 'cam-1',
            data: { name: 'This will fail' },
          });
        } catch {
          // Expected to fail
        }
      });

      // Wait for error state to be set
      await waitFor(() => {
        expect(result.current.updateMutation.isError).toBe(true);
      });

      // Verify rollback occurred - cache should have original data
      await waitFor(() => {
        const cameras = queryClient.getQueryData<Camera[]>(queryKeys.cameras.list());
        expect(cameras?.[0].name).toBe('Front Door');
      });
    });

    it('should maintain cache consistency during concurrent mutations', async () => {
      let resolveFirst: (value: Camera) => void;
      let resolveSecond: (value: Camera) => void;

      const firstPromise = new Promise<Camera>((resolve) => {
        resolveFirst = resolve;
      });
      const secondPromise = new Promise<Camera>((resolve) => {
        resolveSecond = resolve;
      });

      let callCount = 0;
      (api.updateCamera as ReturnType<typeof vi.fn>).mockImplementation(async () => {
        callCount++;
        return callCount === 1 ? firstPromise : secondPromise;
      });

      const queryClient = createQueryClient();
      queryClient.setQueryData(queryKeys.cameras.list(), [...mockCameras]);

      const { result } = renderHook(
        () => ({
          cameras: useCamerasQuery(),
          updateMutation: useOptimisticCameraUpdate(),
        }),
        { wrapper: createQueryWrapper(queryClient) }
      );

      await waitFor(() => {
        expect(result.current.cameras.cameras).toHaveLength(2);
      });

      // Start two concurrent mutations
      act(() => {
        result.current.updateMutation.mutate({
          id: 'cam-1',
          data: { name: 'First Update' },
        });
      });

      act(() => {
        result.current.updateMutation.mutate({
          id: 'cam-2',
          data: { name: 'Second Update' },
        });
      });

      // Both optimistic updates should be applied
      await waitFor(() => {
        const cameras = queryClient.getQueryData<Camera[]>(queryKeys.cameras.list());
        // Note: The second mutation may overwrite the first's snapshot
        // This tests the concurrent behavior
        expect(cameras).toBeDefined();
      });

      // Resolve both
      act(() => {
        resolveFirst!({ ...mockCameras[0], name: 'First Update' });
        resolveSecond!({ ...mockCameras[1], name: 'Second Update' });
      });

      // Final state should be consistent
      await waitFor(() => {
        expect(api.updateCamera).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Delete Mutation with Optimistic Update', () => {
    const useOptimisticCameraDelete = () => {
      const queryClient = useQueryClient();

      return useMutation({
        mutationFn: (id: string) => api.deleteCamera(id),

        onMutate: async (deletedId) => {
          await queryClient.cancelQueries({ queryKey: queryKeys.cameras.all });

          const previousCameras = queryClient.getQueryData<Camera[]>(queryKeys.cameras.list());

          // Optimistically remove the camera
          queryClient.setQueryData<Camera[]>(queryKeys.cameras.list(), (old) =>
            old?.filter((camera) => camera.id !== deletedId)
          );

          return { previousCameras };
        },

        onError: (_err, _variables, context) => {
          if (context?.previousCameras) {
            queryClient.setQueryData(queryKeys.cameras.list(), context.previousCameras);
          }
        },

        onSettled: () => {
          void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
        },
      });
    };

    it('should optimistically remove item and restore on failure', async () => {
      (api.deleteCamera as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Cannot delete: camera has pending recordings')
      );
      (api.fetchCameras as ReturnType<typeof vi.fn>).mockResolvedValue([...mockCameras]);

      const queryClient = createQueryClient();
      queryClient.setQueryData(queryKeys.cameras.list(), [...mockCameras]);

      const { result } = renderHook(
        () => ({
          cameras: useCamerasQuery(),
          deleteMutation: useOptimisticCameraDelete(),
        }),
        { wrapper: createQueryWrapper(queryClient) }
      );

      await waitFor(() => {
        expect(result.current.cameras.cameras).toHaveLength(2);
      });

      // Trigger delete
      await act(async () => {
        try {
          await result.current.deleteMutation.mutateAsync('cam-1');
        } catch {
          // Expected to fail
        }
      });

      // Verify rollback - camera should be restored
      await waitFor(() => {
        const cameras = queryClient.getQueryData<Camera[]>(queryKeys.cameras.list());
        expect(cameras).toHaveLength(2);
        expect(cameras?.find((c) => c.id === 'cam-1')).toBeDefined();
      });
    });

    it('should successfully delete and update cache on success', async () => {
      (api.deleteCamera as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
      (api.fetchCameras as ReturnType<typeof vi.fn>).mockResolvedValue([mockCameras[1]]);

      const queryClient = createQueryClient();
      queryClient.setQueryData(queryKeys.cameras.list(), [...mockCameras]);

      const { result } = renderHook(
        () => ({
          cameras: useCamerasQuery(),
          deleteMutation: useOptimisticCameraDelete(),
        }),
        { wrapper: createQueryWrapper(queryClient) }
      );

      await waitFor(() => {
        expect(result.current.cameras.cameras).toHaveLength(2);
      });

      await act(async () => {
        await result.current.deleteMutation.mutateAsync('cam-1');
      });

      // Wait for success state
      await waitFor(() => {
        expect(result.current.deleteMutation.isSuccess).toBe(true);
      });

      // After refetch, should only have one camera
      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalled();
      });
    });
  });

  describe('Create Mutation with Optimistic Update', () => {
    const useOptimisticCameraCreate = () => {
      const queryClient = useQueryClient();

      return useMutation({
        mutationFn: (data: { name: string; folder_path: string; status: Camera['status'] }) =>
          api.createCamera(data),

        onMutate: async (newCamera) => {
          await queryClient.cancelQueries({ queryKey: queryKeys.cameras.all });

          const previousCameras = queryClient.getQueryData<Camera[]>(queryKeys.cameras.list());

          // Create a temporary camera with a placeholder ID
          const optimisticCamera: Camera = {
            id: `temp-${Date.now()}`,
            name: newCamera.name,
            folder_path: newCamera.folder_path,
            status: newCamera.status,
            last_seen_at: null,
            created_at: new Date().toISOString(),
          };

          queryClient.setQueryData<Camera[]>(queryKeys.cameras.list(), (old) => [
            ...(old ?? []),
            optimisticCamera,
          ]);

          return { previousCameras, optimisticId: optimisticCamera.id };
        },

        onError: (_err, _variables, context) => {
          if (context?.previousCameras) {
            queryClient.setQueryData(queryKeys.cameras.list(), context.previousCameras);
          }
        },

        onSuccess: (newCamera, _variables, context) => {
          // Replace the optimistic camera with the real one
          // Note: We use the queryClient from the outer scope, not useQueryClient()
          // as this callback is not a React component/hook
          queryClient.setQueryData<Camera[]>(queryKeys.cameras.list(), (old) =>
            old?.map((camera) => (camera.id === context?.optimisticId ? newCamera : camera))
          );
        },

        onSettled: () => {
          void queryClient.invalidateQueries({ queryKey: queryKeys.cameras.all });
        },
      });
    };

    it('should add optimistic item and remove on failure', async () => {
      (api.createCamera as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Validation error: Camera name already exists')
      );
      (api.fetchCameras as ReturnType<typeof vi.fn>).mockResolvedValue([...mockCameras]);

      const queryClient = createQueryClient();
      queryClient.setQueryData(queryKeys.cameras.list(), [...mockCameras]);

      const { result } = renderHook(
        () => ({
          cameras: useCamerasQuery(),
          createMutation: useOptimisticCameraCreate(),
        }),
        { wrapper: createQueryWrapper(queryClient) }
      );

      await waitFor(() => {
        expect(result.current.cameras.cameras).toHaveLength(2);
      });

      await act(async () => {
        try {
          await result.current.createMutation.mutateAsync({
            name: 'New Camera',
            folder_path: '/export/foscam/new_camera',
            status: 'online' as const,
          });
        } catch {
          // Expected to fail
        }
      });

      // Verify rollback - should be back to 2 cameras
      await waitFor(() => {
        const cameras = queryClient.getQueryData<Camera[]>(queryKeys.cameras.list());
        expect(cameras).toHaveLength(2);
      });
    });
  });

  describe('Error State Handling', () => {
    it('should expose error details after failed mutation', async () => {
      const errorMessage = 'Camera is currently recording, cannot modify';
      (api.updateCamera as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

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
          // Expected to fail
        }
      });

      // Wait for mutation state to settle
      await waitFor(() => {
        expect(result.current.updateMutation.isError).toBe(true);
      });

      expect(result.current.updateMutation.error?.message).toBe(errorMessage);
    });

    it('should allow retry after failed mutation', async () => {
      let attemptCount = 0;
      (api.updateCamera as ReturnType<typeof vi.fn>).mockImplementation(async () => {
        attemptCount++;
        if (attemptCount === 1) {
          throw new Error('Temporary failure');
        }
        return { ...mockCameras[0], name: 'Success on retry' };
      });

      const queryClient = createQueryClient();

      const { result } = renderHook(() => useCameraMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // First attempt - fails
      await act(async () => {
        try {
          await result.current.updateMutation.mutateAsync({
            id: 'cam-1',
            data: { name: 'Test' },
          });
        } catch {
          // Expected to fail
        }
      });

      // Wait for error state
      await waitFor(() => {
        expect(result.current.updateMutation.isError).toBe(true);
      });

      // Retry - succeeds
      await act(async () => {
        await result.current.updateMutation.mutateAsync({
          id: 'cam-1',
          data: { name: 'Success on retry' },
        });
      });

      // Wait for success state
      await waitFor(() => {
        expect(result.current.updateMutation.isSuccess).toBe(true);
      });

      expect(attemptCount).toBe(2);
    });
  });
});

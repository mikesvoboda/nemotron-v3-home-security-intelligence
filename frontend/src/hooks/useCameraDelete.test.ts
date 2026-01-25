/**
 * Tests for useCameraDelete hooks
 *
 * @module hooks/useCameraDelete.test
 * @see NEM-3643 - Camera Soft Delete UI
 */

import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils';
import {
  useDeletedCamerasQuery,
  useDeleteCameraMutation,
  useRestoreCameraMutation,
  useCameraDeleteRestore,
  deletedCamerasQueryKeys,
} from './useCameraDelete';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof api>();
  return {
    ...actual,
    fetchDeletedCameras: vi.fn(),
    deleteCamera: vi.fn(),
    restoreCamera: vi.fn(),
  };
});

const mockDeletedCameras: api.Camera[] = [
  {
    id: 'deleted-cam-1',
    name: 'Deleted Front Door',
    folder_path: '/export/foscam/front_door',
    status: 'offline',
    created_at: '2025-01-01T00:00:00Z',
    last_seen_at: '2025-01-15T12:00:00Z',
  },
  {
    id: 'deleted-cam-2',
    name: 'Deleted Backyard',
    folder_path: '/export/foscam/backyard',
    status: 'offline',
    created_at: '2025-01-02T00:00:00Z',
    last_seen_at: null,
  },
];

const mockRestoredCamera: api.Camera = {
  id: 'deleted-cam-1',
  name: 'Deleted Front Door',
  folder_path: '/export/foscam/front_door',
  status: 'online',
  created_at: '2025-01-01T00:00:00Z',
  last_seen_at: '2025-01-20T10:00:00Z',
};

describe('useCameraDelete hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('deletedCamerasQueryKeys', () => {
    it('should have correct structure', () => {
      expect(deletedCamerasQueryKeys.all).toEqual(['cameras', 'deleted']);
      expect(deletedCamerasQueryKeys.list()).toEqual(['cameras', 'deleted', 'list']);
    });
  });

  describe('useDeletedCamerasQuery', () => {
    it('should fetch deleted cameras successfully', async () => {
      vi.mocked(api.fetchDeletedCameras).mockResolvedValue(mockDeletedCameras);

      const { result } = renderHook(() => useDeletedCamerasQuery(), {
        wrapper: createQueryWrapper(),
      });

      // Initial loading state
      expect(result.current.isLoading).toBe(true);
      expect(result.current.deletedCameras).toEqual([]);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Data loaded
      expect(result.current.deletedCameras).toEqual(mockDeletedCameras);
      expect(result.current.error).toBeNull();
      expect(api.fetchDeletedCameras).toHaveBeenCalledTimes(1);
    });

    it('should handle fetch error', async () => {
      const error = new Error('Failed to fetch deleted cameras');
      vi.mocked(api.fetchDeletedCameras).mockRejectedValue(error);

      const { result } = renderHook(() => useDeletedCamerasQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).toEqual(error);
        },
        { timeout: 3000 }
      );

      expect(result.current.deletedCameras).toEqual([]);
    });

    it('should not fetch when disabled', () => {
      vi.mocked(api.fetchDeletedCameras).mockResolvedValue(mockDeletedCameras);

      const { result } = renderHook(() => useDeletedCamerasQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      // Should not be loading (query is disabled)
      expect(result.current.isLoading).toBe(false);
      expect(result.current.deletedCameras).toEqual([]);
      expect(api.fetchDeletedCameras).not.toHaveBeenCalled();
    });

    it('should return empty array when no deleted cameras', async () => {
      vi.mocked(api.fetchDeletedCameras).mockResolvedValue([]);

      const { result } = renderHook(() => useDeletedCamerasQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.deletedCameras).toEqual([]);
    });
  });

  describe('useDeleteCameraMutation', () => {
    it('should delete camera successfully', async () => {
      vi.mocked(api.deleteCamera).mockResolvedValue(undefined);

      const { result } = renderHook(() => useDeleteCameraMutation(), {
        wrapper: createQueryWrapper(),
      });

      // Execute delete mutation
      await result.current.deleteMutation.mutateAsync('cam-1');

      expect(api.deleteCamera).toHaveBeenCalledWith('cam-1');
      expect(api.deleteCamera).toHaveBeenCalledTimes(1);
    });

    it('should handle delete error', async () => {
      const error = new Error('Delete failed');
      vi.mocked(api.deleteCamera).mockRejectedValue(error);

      const { result } = renderHook(() => useDeleteCameraMutation(), {
        wrapper: createQueryWrapper(),
      });

      // Execute delete mutation and expect error
      await expect(result.current.deleteMutation.mutateAsync('cam-1')).rejects.toThrow(
        'Delete failed'
      );

      expect(api.deleteCamera).toHaveBeenCalledWith('cam-1');
    });

    it('should provide correct mutation state', async () => {
      vi.mocked(api.deleteCamera).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(undefined), 100))
      );

      const { result } = renderHook(() => useDeleteCameraMutation(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.deleteMutation.isPending).toBe(false);

      // Start mutation
      const mutationPromise = result.current.deleteMutation.mutateAsync('cam-1');

      await waitFor(() => {
        expect(result.current.deleteMutation.isPending).toBe(true);
      });

      await mutationPromise;

      await waitFor(() => {
        expect(result.current.deleteMutation.isPending).toBe(false);
      });
    });
  });

  describe('useRestoreCameraMutation', () => {
    it('should restore camera successfully', async () => {
      vi.mocked(api.restoreCamera).mockResolvedValue(mockRestoredCamera);

      const { result } = renderHook(() => useRestoreCameraMutation(), {
        wrapper: createQueryWrapper(),
      });

      // Execute restore mutation
      const restored = await result.current.restoreMutation.mutateAsync('deleted-cam-1');

      expect(api.restoreCamera).toHaveBeenCalledWith('deleted-cam-1');
      expect(api.restoreCamera).toHaveBeenCalledTimes(1);
      expect(restored).toEqual(mockRestoredCamera);
    });

    it('should handle restore error', async () => {
      const error = new Error('Camera not found');
      vi.mocked(api.restoreCamera).mockRejectedValue(error);

      const { result } = renderHook(() => useRestoreCameraMutation(), {
        wrapper: createQueryWrapper(),
      });

      // Execute restore mutation and expect error
      await expect(result.current.restoreMutation.mutateAsync('invalid-id')).rejects.toThrow(
        'Camera not found'
      );

      expect(api.restoreCamera).toHaveBeenCalledWith('invalid-id');
    });

    it('should provide correct mutation state', async () => {
      vi.mocked(api.restoreCamera).mockImplementation(
        () => new Promise((resolve) => setTimeout(() => resolve(mockRestoredCamera), 100))
      );

      const { result } = renderHook(() => useRestoreCameraMutation(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.restoreMutation.isPending).toBe(false);

      // Start mutation
      const mutationPromise = result.current.restoreMutation.mutateAsync('deleted-cam-1');

      await waitFor(() => {
        expect(result.current.restoreMutation.isPending).toBe(true);
      });

      await mutationPromise;

      await waitFor(() => {
        expect(result.current.restoreMutation.isPending).toBe(false);
      });
    });
  });

  describe('useCameraDeleteRestore', () => {
    it('should provide both delete and restore mutations', async () => {
      vi.mocked(api.deleteCamera).mockResolvedValue(undefined);
      vi.mocked(api.restoreCamera).mockResolvedValue(mockRestoredCamera);

      const { result } = renderHook(() => useCameraDeleteRestore(), {
        wrapper: createQueryWrapper(),
      });

      // Both mutations should be available
      expect(result.current.deleteMutation).toBeDefined();
      expect(result.current.restoreMutation).toBeDefined();

      // Delete should work
      await result.current.deleteMutation.mutateAsync('cam-1');
      expect(api.deleteCamera).toHaveBeenCalledWith('cam-1');

      // Restore should work
      const restored = await result.current.restoreMutation.mutateAsync('deleted-cam-1');
      expect(api.restoreCamera).toHaveBeenCalledWith('deleted-cam-1');
      expect(restored).toEqual(mockRestoredCamera);
    });
  });
});

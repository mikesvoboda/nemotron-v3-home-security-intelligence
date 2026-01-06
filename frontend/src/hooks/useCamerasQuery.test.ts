import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { createQueryClient, queryKeys } from '../services/queryClient';
import { createQueryWrapper } from '../test-utils/renderWithProviders';
import * as api from '../services/api';
import {
  useCamerasQuery,
  useCameraQuery,
  useCameraMutation,
} from './useCamerasQuery';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchCameras: vi.fn(),
  fetchCamera: vi.fn(),
  createCamera: vi.fn(),
  updateCamera: vi.fn(),
  deleteCamera: vi.fn(),
}));

describe('useCamerasQuery', () => {
  const mockCameras = [
    {
      id: 'cam-1',
      name: 'Front Door',
      enabled: true,
      status: 'online',
      last_seen: '2025-12-28T10:00:00Z',
    },
    {
      id: 'cam-2',
      name: 'Backyard',
      enabled: true,
      status: 'online',
      last_seen: '2025-12-28T10:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchCameras as ReturnType<typeof vi.fn>).mockResolvedValue(mockCameras);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchCameras as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useCamerasQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchCameras as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useCamerasQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.cameras).toEqual([]);
    });
  });

  describe('fetching data', () => {
    it('fetches cameras on mount', async () => {
      renderHook(() => useCamerasQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchCameras).toHaveBeenCalledTimes(1);
      });
    });

    it('updates cameras after successful fetch', async () => {
      const { result } = renderHook(() => useCamerasQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.cameras).toEqual(mockCameras);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useCamerasQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch cameras';
      (api.fetchCameras as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useCamerasQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useCamerasQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchCameras).not.toHaveBeenCalled();
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useCamerasQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });
});

describe('useCameraQuery', () => {
  const mockCamera = {
    id: 'cam-1',
    name: 'Front Door',
    enabled: true,
    status: 'online',
    last_seen: '2025-12-28T10:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchCamera as ReturnType<typeof vi.fn>).mockResolvedValue(mockCamera);
  });

  it('fetches single camera by ID', async () => {
    renderHook(() => useCameraQuery('cam-1'), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(api.fetchCamera).toHaveBeenCalledWith('cam-1');
    });
  });

  it('returns camera data', async () => {
    const { result } = renderHook(() => useCameraQuery('cam-1'), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockCamera);
    });
  });

  it('does not fetch when id is undefined', async () => {
    renderHook(() => useCameraQuery(undefined), {
      wrapper: createQueryWrapper(),
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(api.fetchCamera).not.toHaveBeenCalled();
  });
});

describe('useCameraMutation', () => {
  const mockCamera = {
    id: 'cam-1',
    name: 'Front Door',
    enabled: true,
    status: 'online',
    last_seen: '2025-12-28T10:00:00Z',
  };

  const mockCreatedCamera = {
    id: 'cam-new',
    name: 'New Camera',
    enabled: true,
    status: 'offline',
    last_seen: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.createCamera as ReturnType<typeof vi.fn>).mockResolvedValue(mockCreatedCamera);
    (api.updateCamera as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...mockCamera,
      name: 'Updated Name',
    });
    (api.deleteCamera as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);
    (api.fetchCameras as ReturnType<typeof vi.fn>).mockResolvedValue([mockCamera]);
  });

  describe('createMutation', () => {
    it('creates a new camera', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => useCameraMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.createMutation.mutateAsync({
          name: 'New Camera',
          folder_path: '/export/foscam/new_camera',
          status: 'online',
        });
      });

      expect(api.createCamera).toHaveBeenCalledWith({
        name: 'New Camera',
        folder_path: '/export/foscam/new_camera',
        status: 'online',
      });
    });

    it('invalidates cameras query after create', async () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCameraMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.createMutation.mutateAsync({
          name: 'New Camera',
          folder_path: '/export/foscam/new_camera',
          status: 'online',
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.cameras.all,
      });
    });
  });

  describe('updateMutation', () => {
    it('updates a camera', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => useCameraMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.updateMutation.mutateAsync({
          id: 'cam-1',
          data: { name: 'Updated Name' },
        });
      });

      expect(api.updateCamera).toHaveBeenCalledWith('cam-1', { name: 'Updated Name' });
    });

    it('invalidates cameras query after update', async () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCameraMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.updateMutation.mutateAsync({
          id: 'cam-1',
          data: { name: 'Updated Name' },
        });
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.cameras.all,
      });
    });
  });

  describe('deleteMutation', () => {
    it('deletes a camera', async () => {
      const queryClient = createQueryClient();
      const { result } = renderHook(() => useCameraMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.deleteMutation.mutateAsync('cam-1');
      });

      expect(api.deleteCamera).toHaveBeenCalledWith('cam-1');
    });

    it('invalidates cameras query after delete', async () => {
      const queryClient = createQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCameraMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.deleteMutation.mutateAsync('cam-1');
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.cameras.all,
      });
    });
  });
});

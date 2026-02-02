/**
 * Tests for useSceneChangesQuery hook
 *
 * Task: NEM-4935 - Scene Change Detection History Page
 *
 * This test suite covers:
 * - Query key generation
 * - Data fetching from multiple cameras
 * - Filtering by camera, time range, change type, and acknowledgement status
 * - Error handling
 * - Loading and refetching states
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';

import * as useCamerasQueryModule from './useCamerasQuery';
import { useSceneChangesQuery } from './useSceneChangesQuery';
import * as apiModule from '../services/api';
import { createWrapper } from '../test/utils';

import type { Camera, SceneChangeListResponse } from '../services/api';

// ============================================================================
// Mocks
// ============================================================================

vi.mock('./useCamerasQuery', () => ({
  useCamerasQuery: vi.fn(),
}));

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof apiModule>();
  return {
    ...actual,
    fetchSceneChanges: vi.fn(),
  };
});

// ============================================================================
// Test Data
// ============================================================================

const mockCameras: Camera[] = [
  {
    id: 'cam-1',
    name: 'Front Door',
    folder_path: '/cameras/front',
    status: 'online',
    last_seen_at: '2026-01-31T10:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    ingestion_mode: 'ftp',
    motion_sensitivity: 0.5,
  },
  {
    id: 'cam-2',
    name: 'Back Yard',
    folder_path: '/cameras/back',
    status: 'online',
    last_seen_at: '2026-01-31T10:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    ingestion_mode: 'rtsp',
    motion_sensitivity: 0.7,
  },
];

const mockSceneChangesResponse1: SceneChangeListResponse = {
  camera_id: 'cam-1',
  scene_changes: [
    {
      id: 1,
      change_type: 'view_blocked',
      similarity_score: 0.35,
      detected_at: new Date().toISOString(),
      acknowledged: false,
      acknowledged_at: null,
      file_path: '/path/to/image.jpg',
    },
    {
      id: 2,
      change_type: 'angle_changed',
      similarity_score: 0.65,
      detected_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
      acknowledged: true,
      acknowledged_at: new Date().toISOString(),
      file_path: '/path/to/image2.jpg',
    },
  ],
  total_changes: 2,
  has_more: false,
};

const mockSceneChangesResponse2: SceneChangeListResponse = {
  camera_id: 'cam-2',
  scene_changes: [
    {
      id: 3,
      change_type: 'view_tampered',
      similarity_score: 0.25,
      detected_at: new Date(Date.now() - 1 * 60 * 60 * 1000).toISOString(), // 1 hour ago
      acknowledged: false,
      acknowledged_at: null,
      file_path: '/path/to/image3.jpg',
    },
  ],
  total_changes: 1,
  has_more: false,
};

// Default mock return values
const defaultCamerasReturn: ReturnType<typeof useCamerasQueryModule.useCamerasQuery> = {
  cameras: mockCameras,
  isLoading: false,
  isRefetching: false,
  error: null,
  refetch: vi.fn(),
  isPlaceholderData: false,
};

// ============================================================================
// Tests
// ============================================================================

describe('useSceneChangesQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (useCamerasQueryModule.useCamerasQuery as Mock).mockReturnValue(defaultCamerasReturn);
    (apiModule.fetchSceneChanges as Mock).mockImplementation((cameraId: string) => {
      if (cameraId === 'cam-1') return Promise.resolve(mockSceneChangesResponse1);
      if (cameraId === 'cam-2') return Promise.resolve(mockSceneChangesResponse2);
      return Promise.resolve({ camera_id: cameraId, scene_changes: [], total_changes: 0 });
    });
  });

  // ==========================================================================
  // Basic Functionality Tests
  // ==========================================================================

  describe('basic functionality', () => {
    it('fetches scene changes from all cameras by default', async () => {
      const { result } = renderHook(() => useSceneChangesQuery(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(apiModule.fetchSceneChanges).toHaveBeenCalledWith('cam-1', expect.any(Object));
      expect(apiModule.fetchSceneChanges).toHaveBeenCalledWith('cam-2', expect.any(Object));
    });

    it('fetches scene changes from a specific camera when cameraId is provided', async () => {
      const { result } = renderHook(
        () => useSceneChangesQuery({ cameraId: 'cam-1' }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(apiModule.fetchSceneChanges).toHaveBeenCalledWith('cam-1', expect.any(Object));
      expect(apiModule.fetchSceneChanges).not.toHaveBeenCalledWith('cam-2', expect.any(Object));
    });

    it('enriches scene changes with camera names', async () => {
      const { result } = renderHook(() => useSceneChangesQuery(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.sceneChanges.length).toBeGreaterThan(0);
      expect(result.current.sceneChanges[0].camera_name).toBeDefined();
    });

    it('sorts scene changes by detected_at descending', async () => {
      const { result } = renderHook(() => useSceneChangesQuery(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const dates = result.current.sceneChanges.map((sc) => new Date(sc.detected_at).getTime());
      for (let i = 1; i < dates.length; i++) {
        expect(dates[i - 1]).toBeGreaterThanOrEqual(dates[i]);
      }
    });
  });

  // ==========================================================================
  // Filtering Tests
  // ==========================================================================

  describe('filtering', () => {
    it('filters by acknowledgement status when acknowledgementFilter is "acknowledged"', async () => {
      const { result } = renderHook(
        () => useSceneChangesQuery({ acknowledgementFilter: 'acknowledged' }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(apiModule.fetchSceneChanges).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ acknowledged: true })
      );
    });

    it('filters by acknowledgement status when acknowledgementFilter is "unacknowledged"', async () => {
      const { result } = renderHook(
        () => useSceneChangesQuery({ acknowledgementFilter: 'unacknowledged' }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(apiModule.fetchSceneChanges).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({ acknowledged: false })
      );
    });

    it('filters by change type', async () => {
      const { result } = renderHook(
        () => useSceneChangesQuery({ changeType: 'view_blocked' }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Client-side filtering - all items should have view_blocked type
      result.current.sceneChanges.forEach((sc) => {
        expect(sc.change_type).toBe('view_blocked');
      });
    });

    it('filters by time range', async () => {
      const { result } = renderHook(
        () => useSceneChangesQuery({ timeRange: '1h' }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const oneHourAgo = Date.now() - 60 * 60 * 1000;
      result.current.sceneChanges.forEach((sc) => {
        expect(new Date(sc.detected_at).getTime()).toBeGreaterThanOrEqual(oneHourAgo);
      });
    });
  });

  // ==========================================================================
  // Count Tests
  // ==========================================================================

  describe('counts', () => {
    it('returns correct totalCount', async () => {
      const { result } = renderHook(() => useSceneChangesQuery(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.totalCount).toBe(result.current.sceneChanges.length);
    });

    it('returns correct unacknowledgedCount', async () => {
      const { result } = renderHook(() => useSceneChangesQuery(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const expectedUnacknowledged = result.current.sceneChanges.filter(
        (sc) => !sc.acknowledged
      ).length;
      expect(result.current.unacknowledgedCount).toBe(expectedUnacknowledged);
    });
  });

  // ==========================================================================
  // Loading State Tests
  // ==========================================================================

  describe('loading states', () => {
    it('returns isLoading true while cameras are loading', () => {
      (useCamerasQueryModule.useCamerasQuery as Mock).mockReturnValue({
        ...defaultCamerasReturn,
        isLoading: true,
      });

      const { result } = renderHook(() => useSceneChangesQuery(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('does not fetch when cameras are loading', () => {
      (useCamerasQueryModule.useCamerasQuery as Mock).mockReturnValue({
        ...defaultCamerasReturn,
        cameras: [],
        isLoading: true,
      });

      renderHook(() => useSceneChangesQuery(), {
        wrapper: createWrapper(),
      });

      expect(apiModule.fetchSceneChanges).not.toHaveBeenCalled();
    });

    it('does not fetch when enabled is false', () => {
      renderHook(() => useSceneChangesQuery({ enabled: false }), {
        wrapper: createWrapper(),
      });

      expect(apiModule.fetchSceneChanges).not.toHaveBeenCalled();
    });
  });

  // ==========================================================================
  // Error Handling Tests
  // ==========================================================================

  describe('error handling', () => {
    it('continues fetching from other cameras when one fails', async () => {
      // Make cam-1 fail
      (apiModule.fetchSceneChanges as Mock).mockImplementation((cameraId: string) => {
        if (cameraId === 'cam-1') return Promise.reject(new Error('Network error'));
        if (cameraId === 'cam-2') return Promise.resolve(mockSceneChangesResponse2);
        return Promise.resolve({ camera_id: cameraId, scene_changes: [], total_changes: 0 });
      });

      const { result } = renderHook(() => useSceneChangesQuery(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should have scene changes from cam-2 but not cam-1
      expect(result.current.sceneChanges.length).toBe(1);
      expect(result.current.sceneChanges[0].camera_id).toBe('cam-2');
    });

    it('returns empty array when no cameras have data', async () => {
      (apiModule.fetchSceneChanges as Mock).mockResolvedValue({
        camera_id: 'test',
        scene_changes: [],
        total_changes: 0,
      });

      const { result } = renderHook(() => useSceneChangesQuery(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.sceneChanges).toEqual([]);
      expect(result.current.totalCount).toBe(0);
    });
  });

  // ==========================================================================
  // Refetch Tests
  // ==========================================================================

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useSceneChangesQuery(), {
        wrapper: createWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });
});

/**
 * Tests for useHeatmapQuery hooks
 *
 * Task: NEM-4927 - Heatmaps Visualization Page
 *
 * This test suite covers:
 * - useHeatmapQuery hook for fetching current heatmaps
 * - useHeatmapHistoryQuery hook for fetching historical data
 * - Query key generation
 * - Error handling
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  useHeatmapQuery,
  useHeatmapHistoryQuery,
  useMergedHeatmapQuery,
  heatmapQueryKeys,
} from './useHeatmapQuery';
import * as apiModule from '../services/api';
import { createWrapper } from '../test/utils';

// ============================================================================
// Mocks
// ============================================================================

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof apiModule>();
  return {
    ...actual,
    fetchApi: vi.fn(),
  };
});

// ============================================================================
// Test Data
// ============================================================================

const mockHeatmapResponse = {
  camera_id: 'cam-1',
  resolution: 'hourly',
  time_bucket: '2026-01-31T10:00:00Z',
  image_base64: 'iVBORw0KGgoAAAANSUhEUgAAAAE...',
  width: 640,
  height: 480,
  total_detections: 150,
  colormap: 'jet',
};

const mockHistoryResponse = {
  heatmaps: [
    {
      id: 1,
      camera_id: 'cam-1',
      time_bucket: '2026-01-31T09:00:00Z',
      resolution: 'hourly',
      width: 64,
      height: 48,
      total_detections: 120,
      created_at: '2026-01-31T10:00:00Z',
      updated_at: '2026-01-31T10:00:00Z',
    },
  ],
  total: 1,
};

// ============================================================================
// Tests
// ============================================================================

describe('useHeatmapQuery hooks', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiModule.fetchApi).mockResolvedValue(mockHeatmapResponse);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  // ==========================================================================
  // Query Keys Tests
  // ==========================================================================

  describe('heatmapQueryKeys', () => {
    it('generates correct base key', () => {
      expect(heatmapQueryKeys.all).toEqual(['heatmaps']);
    });

    it('generates correct camera key', () => {
      expect(heatmapQueryKeys.camera('cam-1')).toEqual(['heatmaps', 'camera', 'cam-1']);
    });

    it('generates correct current heatmap key', () => {
      expect(heatmapQueryKeys.current('cam-1', 'hourly', 'jet')).toEqual([
        'heatmaps',
        'camera',
        'cam-1',
        'current',
        'hourly',
        'jet',
      ]);
    });

    it('generates correct history key', () => {
      expect(heatmapQueryKeys.history('cam-1', '24h', 'hourly')).toEqual([
        'heatmaps',
        'camera',
        'cam-1',
        'history',
        '24h',
        'hourly',
      ]);
    });

    it('generates correct merged key', () => {
      const startTime = '2026-01-01T00:00:00Z';
      const endTime = '2026-01-31T23:59:59Z';
      expect(heatmapQueryKeys.merged('cam-1', startTime, endTime, 'daily')).toEqual([
        'heatmaps',
        'camera',
        'cam-1',
        'merged',
        startTime,
        endTime,
        'daily',
      ]);
    });
  });

  // ==========================================================================
  // useHeatmapQuery Tests
  // ==========================================================================

  describe('useHeatmapQuery', () => {
    it('does not fetch when cameraId is not provided', () => {
      const { result } = renderHook(() => useHeatmapQuery({}), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeUndefined();
      expect(apiModule.fetchApi).not.toHaveBeenCalled();
    });

    it('does not fetch when enabled is false', () => {
      const { result } = renderHook(
        () =>
          useHeatmapQuery({
            cameraId: 'cam-1',
            enabled: false,
          }),
        { wrapper: createWrapper() }
      );

      expect(result.current.isLoading).toBe(false);
      expect(apiModule.fetchApi).not.toHaveBeenCalled();
    });

    it('fetches heatmap when cameraId is provided', async () => {
      const { result } = renderHook(
        () =>
          useHeatmapQuery({
            cameraId: 'cam-1',
            resolution: 'hourly',
            colormap: 'jet',
          }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Check that fetchApi was called with correct URL containing params
      expect(apiModule.fetchApi).toHaveBeenCalledWith(
        expect.stringContaining('/api/heatmaps/camera/cam-1')
      );
      expect(apiModule.fetchApi).toHaveBeenCalledWith(
        expect.stringContaining('resolution=hourly')
      );
      expect(apiModule.fetchApi).toHaveBeenCalledWith(
        expect.stringContaining('colormap=jet')
      );
      expect(result.current.data).toEqual(mockHeatmapResponse);
    });

    it('uses default resolution and colormap', async () => {
      const { result } = renderHook(
        () =>
          useHeatmapQuery({
            cameraId: 'cam-1',
          }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Defaults should be hourly resolution and jet colormap
      expect(apiModule.fetchApi).toHaveBeenCalledWith(
        expect.stringContaining('resolution=hourly')
      );
      expect(apiModule.fetchApi).toHaveBeenCalledWith(
        expect.stringContaining('colormap=jet')
      );
    });

    it('handles API errors', async () => {
      const errorMessage = 'Camera not found';
      vi.mocked(apiModule.fetchApi).mockRejectedValue(new Error(errorMessage));

      // Use a custom wrapper with stricter error handling
      const { result } = renderHook(
        () =>
          useHeatmapQuery({
            cameraId: 'invalid-cam',
          }),
        {
          wrapper: createWrapper({
            defaultOptions: {
              queries: {
                retry: false,
                throwOnError: false,
              },
            },
          }),
        }
      );

      // Wait for the query to complete with an error
      await waitFor(
        () => {
          expect(result.current.error).not.toBeNull();
        },
        { timeout: 3000 }
      );

      expect(result.current.error?.message).toBe(errorMessage);
    });
  });

  // ==========================================================================
  // useHeatmapHistoryQuery Tests
  // ==========================================================================

  describe('useHeatmapHistoryQuery', () => {
    beforeEach(() => {
      vi.mocked(apiModule.fetchApi).mockResolvedValue(mockHistoryResponse);
    });

    it('does not fetch when cameraId is not provided', () => {
      const { result } = renderHook(() => useHeatmapHistoryQuery({}), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeUndefined();
      expect(apiModule.fetchApi).not.toHaveBeenCalled();
    });

    it('fetches history when cameraId is provided', async () => {
      const { result } = renderHook(
        () =>
          useHeatmapHistoryQuery({
            cameraId: 'cam-1',
            timeRange: '24h',
          }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(apiModule.fetchApi).toHaveBeenCalledWith(
        expect.stringContaining('/api/heatmaps/camera/cam-1/history')
      );
      expect(result.current.data).toEqual(mockHistoryResponse);
    });

    it('includes resolution filter when provided', async () => {
      const { result } = renderHook(
        () =>
          useHeatmapHistoryQuery({
            cameraId: 'cam-1',
            timeRange: '7d',
            resolution: 'daily',
          }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(apiModule.fetchApi).toHaveBeenCalledWith(
        expect.stringContaining('resolution=daily')
      );
    });
  });

  // ==========================================================================
  // useMergedHeatmapQuery Tests
  // ==========================================================================

  describe('useMergedHeatmapQuery', () => {
    beforeEach(() => {
      vi.mocked(apiModule.fetchApi).mockResolvedValue(mockHeatmapResponse);
    });

    it('does not fetch when cameraId is not provided', () => {
      const { result } = renderHook(
        () =>
          useMergedHeatmapQuery({
            startTime: new Date('2026-01-01'),
            endTime: new Date('2026-01-31'),
          }),
        { wrapper: createWrapper() }
      );

      expect(result.current.isLoading).toBe(false);
      expect(apiModule.fetchApi).not.toHaveBeenCalled();
    });

    it('does not fetch when time range is not provided', () => {
      const { result } = renderHook(
        () =>
          useMergedHeatmapQuery({
            cameraId: 'cam-1',
          }),
        { wrapper: createWrapper() }
      );

      expect(result.current.isLoading).toBe(false);
      expect(apiModule.fetchApi).not.toHaveBeenCalled();
    });

    it('fetches merged heatmap when all params are provided', async () => {
      const startTime = new Date('2026-01-01T00:00:00Z');
      const endTime = new Date('2026-01-31T23:59:59Z');

      const { result } = renderHook(
        () =>
          useMergedHeatmapQuery({
            cameraId: 'cam-1',
            startTime,
            endTime,
            resolution: 'daily',
          }),
        { wrapper: createWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(apiModule.fetchApi).toHaveBeenCalledWith(
        expect.stringContaining('/api/heatmaps/camera/cam-1/merged')
      );
      expect(apiModule.fetchApi).toHaveBeenCalledWith(
        expect.stringContaining('resolution=daily')
      );
      expect(result.current.data).toEqual(mockHeatmapResponse);
    });
  });
});

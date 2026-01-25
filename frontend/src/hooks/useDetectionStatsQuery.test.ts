/**
 * Tests for useDetectionStatsQuery hook
 *
 * Tests cover:
 * - Fetching detection stats with default parameters
 * - Fetching detection stats filtered by camera ID
 * - Loading state management
 * - Error state management
 * - Query key generation for cache invalidation
 * - Derived values (detections by class, total count)
 */
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useDetectionStatsQuery,
  detectionStatsQueryKeys,
} from './useDetectionStatsQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    fetchDetectionStats: vi.fn(),
  };
});

describe('useDetectionStatsQuery', () => {
  const mockStatsResponse = {
    total_detections: 1250,
    detections_by_class: {
      person: 500,
      car: 350,
      truck: 200,
      dog: 100,
      cat: 100,
    },
    average_confidence: 0.87,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchDetectionStats).mockResolvedValue(mockStatsResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('query key factory', () => {
    it('generates base key for all stats queries', () => {
      expect(detectionStatsQueryKeys.all).toEqual(['detections', 'stats']);
    });

    it('generates key without camera filter', () => {
      expect(detectionStatsQueryKeys.byParams({})).toEqual([
        'detections',
        'stats',
        {},
      ]);
    });

    it('generates key with camera filter', () => {
      expect(detectionStatsQueryKeys.byParams({ camera_id: 'cam-123' })).toEqual([
        'detections',
        'stats',
        { camera_id: 'cam-123' },
      ]);
    });
  });

  describe('fetching detection stats', () => {
    it('fetches stats without camera filter', async () => {
      const { result } = renderHook(() => useDetectionStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      // Initially loading
      expect(result.current.isLoading).toBe(true);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchDetectionStats).toHaveBeenCalledWith({});
      expect(result.current.data).toEqual(mockStatsResponse);
      expect(result.current.totalDetections).toBe(1250);
      expect(result.current.detectionsByClass).toEqual(mockStatsResponse.detections_by_class);
      expect(result.current.averageConfidence).toBe(0.87);
    });

    it('fetches stats filtered by camera ID', async () => {
      const { result } = renderHook(
        () => useDetectionStatsQuery({ camera_id: 'front-door' }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchDetectionStats).toHaveBeenCalledWith({
        camera_id: 'front-door',
      });
      expect(result.current.data).toEqual(mockStatsResponse);
    });

    it('refetches when camera_id changes', async () => {
      const { result, rerender } = renderHook(
        ({ cameraId }: { cameraId: string | undefined }) =>
          useDetectionStatsQuery({ camera_id: cameraId }),
        {
          wrapper: createQueryWrapper(),
          initialProps: { cameraId: undefined as string | undefined },
        }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchDetectionStats).toHaveBeenCalledTimes(1);
      expect(api.fetchDetectionStats).toHaveBeenCalledWith({});

      // Change camera_id
      rerender({ cameraId: 'backyard' });

      await waitFor(() => {
        expect(api.fetchDetectionStats).toHaveBeenCalledTimes(2);
      });

      expect(api.fetchDetectionStats).toHaveBeenLastCalledWith({
        camera_id: 'backyard',
      });
    });
  });

  describe('loading state', () => {
    it('starts with isLoading true', () => {
      const { result } = renderHook(() => useDetectionStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeUndefined();
    });

    it('sets isLoading false after fetch completes', async () => {
      const { result } = renderHook(() => useDetectionStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toBeDefined();
    });
  });

  describe('error handling', () => {
    it('handles fetch errors', async () => {
      const mockError = new Error('Network error');
      vi.mocked(api.fetchDetectionStats).mockRejectedValue(mockError);

      const { result } = renderHook(
        () => useDetectionStatsQuery({}, { retry: false }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error).toEqual(mockError);
      expect(result.current.data).toBeUndefined();
    });
  });

  describe('derived values', () => {
    it('provides totalDetections as 0 when data not loaded', () => {
      const { result } = renderHook(() => useDetectionStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.totalDetections).toBe(0);
    });

    it('provides empty detectionsByClass when data not loaded', () => {
      const { result } = renderHook(() => useDetectionStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.detectionsByClass).toEqual({});
    });

    it('provides averageConfidence as null when data not loaded', () => {
      const { result } = renderHook(() => useDetectionStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.averageConfidence).toBeNull();
    });

    it('provides correct derived values after data loads', async () => {
      const { result } = renderHook(() => useDetectionStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.totalDetections).toBe(1250);
      expect(result.current.detectionsByClass).toEqual({
        person: 500,
        car: 350,
        truck: 200,
        dog: 100,
        cat: 100,
      });
      expect(result.current.averageConfidence).toBe(0.87);
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      const { result } = renderHook(
        () => useDetectionStatsQuery({}, { enabled: false }),
        { wrapper: createQueryWrapper() }
      );

      // Wait a bit to ensure no fetch happens
      await new Promise((resolve) => setTimeout(resolve, 100));

      expect(api.fetchDetectionStats).not.toHaveBeenCalled();
      expect(result.current.isLoading).toBe(false);
      expect(result.current.data).toBeUndefined();
    });

    it('fetches when enabled changes from false to true', async () => {
      const { result, rerender } = renderHook(
        ({ enabled }: { enabled: boolean }) =>
          useDetectionStatsQuery({}, { enabled }),
        {
          wrapper: createQueryWrapper(),
          initialProps: { enabled: false },
        }
      );

      expect(api.fetchDetectionStats).not.toHaveBeenCalled();

      rerender({ enabled: true });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchDetectionStats).toHaveBeenCalledTimes(1);
    });
  });

  describe('refetch function', () => {
    it('provides a refetch function', async () => {
      const { result } = renderHook(() => useDetectionStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');

      // Call refetch
      await result.current.refetch();

      expect(api.fetchDetectionStats).toHaveBeenCalledTimes(2);
    });
  });
});

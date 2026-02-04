/**
 * Tests for useCameraActivityQuery hook
 *
 * Tests cover:
 * - Successful data fetching
 * - Loading state handling
 * - Error state handling
 * - Empty data handling
 * - Query key generation
 * - Refetch functionality
 *
 * @see NEM-5388, NEM-5389, NEM-5390, NEM-5391 - Camera Activity Heatmap feature
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useCameraActivityQuery } from './useCameraActivityQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchCameraActivity: vi.fn(),
}));

describe('useCameraActivityQuery', () => {
  const mockDateRange = {
    startDate: '2026-01-10',
    endDate: '2026-01-17',
  };

  const mockCameras = [
    {
      camera_id: 'front-door',
      camera_name: 'Front Door',
      event_count: 87,
      max_risk_score: 92,
      risk_level: 'critical' as const,
      thumbnail_path: '/data/thumbnails/front.jpg',
    },
    {
      camera_id: 'backyard',
      camera_name: 'Backyard',
      event_count: 45,
      max_risk_score: 65,
      risk_level: 'high' as const,
      thumbnail_path: '/data/thumbnails/back.jpg',
    },
  ];

  const mockResponse = {
    cameras: mockCameras,
    start_date: '2026-01-10',
    end_date: '2026-01-17',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('successful fetch', () => {
    it('returns camera data on successful fetch', async () => {
      vi.mocked(api.fetchCameraActivity).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => useCameraActivityQuery(mockDateRange), {
        wrapper: createQueryWrapper(),
      });

      // Initially loading
      expect(result.current.isLoading).toBe(true);
      expect(result.current.cameras).toEqual([]);

      // Wait for data
      await waitFor(() => expect(result.current.isLoading).toBe(false));

      // Verify data
      expect(result.current.cameras).toHaveLength(2);
      expect(result.current.cameras[0].camera_id).toBe('front-door');
      expect(result.current.cameras[1].camera_id).toBe('backyard');
      expect(result.current.data).toEqual(mockResponse);
      expect(result.current.error).toBeNull();
    });

    it('calls API with correct parameters', async () => {
      vi.mocked(api.fetchCameraActivity).mockResolvedValue(mockResponse);

      renderHook(() => useCameraActivityQuery(mockDateRange), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchCameraActivity).toHaveBeenCalledWith({
          start_date: '2026-01-10',
          end_date: '2026-01-17',
        });
      });
    });
  });

  describe('loading state', () => {
    it('returns isLoading true while fetching', async () => {
      // Create a promise that we control
      let resolvePromise: (value: typeof mockResponse) => void;
      const promise = new Promise<typeof mockResponse>((resolve) => {
        resolvePromise = resolve;
      });
      vi.mocked(api.fetchCameraActivity).mockReturnValue(promise);

      const { result } = renderHook(() => useCameraActivityQuery(mockDateRange), {
        wrapper: createQueryWrapper(),
      });

      // Should be loading
      expect(result.current.isLoading).toBe(true);
      expect(result.current.cameras).toEqual([]);

      // Resolve the promise
      resolvePromise!(mockResponse);

      await waitFor(() => expect(result.current.isLoading).toBe(false));
      expect(result.current.cameras).toHaveLength(2);
    });
  });

  describe('error state', () => {
    it('returns error on fetch failure', async () => {
      const errorMessage = 'Network error';
      vi.mocked(api.fetchCameraActivity).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useCameraActivityQuery(mockDateRange), {
        wrapper: createQueryWrapper(),
      });

      // Wait for error with longer timeout to account for retry attempts
      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('empty data', () => {
    it('returns empty array when API returns no cameras', async () => {
      const emptyResponse = {
        cameras: [],
        start_date: '2026-01-10',
        end_date: '2026-01-17',
      };
      vi.mocked(api.fetchCameraActivity).mockResolvedValue(emptyResponse);

      const { result } = renderHook(() => useCameraActivityQuery(mockDateRange), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(result.current.cameras).toEqual([]);
      expect(result.current.data).toEqual(emptyResponse);
      expect(result.current.error).toBeNull();
    });
  });

  describe('options', () => {
    it('respects enabled option', () => {
      vi.mocked(api.fetchCameraActivity).mockResolvedValue(mockResponse);

      const { result } = renderHook(
        () => useCameraActivityQuery(mockDateRange, { enabled: false }),
        { wrapper: createQueryWrapper() }
      );

      // Should not fetch when disabled
      expect(result.current.isLoading).toBe(false);
      expect(api.fetchCameraActivity).not.toHaveBeenCalled();
    });

    it('provides refetch function', async () => {
      vi.mocked(api.fetchCameraActivity).mockResolvedValue(mockResponse);

      const { result } = renderHook(() => useCameraActivityQuery(mockDateRange), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => expect(result.current.isLoading).toBe(false));

      expect(typeof result.current.refetch).toBe('function');

      // Trigger refetch
      await result.current.refetch();

      // Should have called API again
      expect(api.fetchCameraActivity).toHaveBeenCalledTimes(2);
    });
  });
});

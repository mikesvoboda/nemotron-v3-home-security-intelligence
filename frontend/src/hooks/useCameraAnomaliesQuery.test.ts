/**
 * Tests for useCameraAnomaliesQuery hook (NEM-3577)
 *
 * Tests cover:
 * - Initial loading state
 * - Successful data fetch
 * - Error handling
 * - Enabled option
 * - Days parameter handling
 * - Refetch functionality
 */
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useCameraAnomaliesQuery } from './useCameraAnomaliesQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchCameraAnomalies: vi.fn(),
}));

describe('useCameraAnomaliesQuery', () => {
  const mockCameraId = 'front-door';

  const mockAnomaliesResponse = {
    camera_id: 'front-door',
    anomalies: [
      {
        timestamp: '2026-01-03T02:30:00Z',
        detection_class: 'vehicle',
        anomaly_score: 0.95,
        expected_frequency: 0.1,
        observed_frequency: 5.0,
        reason: 'Vehicle detected at 2:30 AM when rarely seen at this hour',
      },
      {
        timestamp: '2026-01-04T14:00:00Z',
        detection_class: 'person',
        anomaly_score: 0.78,
        expected_frequency: 2.5,
        observed_frequency: 12.0,
        reason: 'Unusual number of people detected during typically quiet period',
      },
    ],
    count: 2,
    period_days: 7,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchCameraAnomalies as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockAnomaliesResponse
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchCameraAnomalies as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => useCameraAnomaliesQuery(mockCameraId), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with empty anomalies array', () => {
      (api.fetchCameraAnomalies as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => useCameraAnomaliesQuery(mockCameraId), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.anomalies).toEqual([]);
    });

    it('starts with count of 0', () => {
      (api.fetchCameraAnomalies as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => useCameraAnomaliesQuery(mockCameraId), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.count).toBe(0);
    });
  });

  describe('fetching data', () => {
    it('fetches anomalies on mount with default days parameter', async () => {
      renderHook(() => useCameraAnomaliesQuery(mockCameraId), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchCameraAnomalies).toHaveBeenCalledTimes(1);
        expect(api.fetchCameraAnomalies).toHaveBeenCalledWith(mockCameraId, 7);
      });
    });

    it('fetches anomalies with custom days parameter', async () => {
      renderHook(() => useCameraAnomaliesQuery(mockCameraId, { days: 30 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchCameraAnomalies).toHaveBeenCalledWith(mockCameraId, 30);
      });
    });

    it('updates anomalies after successful fetch', async () => {
      const { result } = renderHook(() => useCameraAnomaliesQuery(mockCameraId), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.anomalies).toEqual(mockAnomaliesResponse.anomalies);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useCameraAnomaliesQuery(mockCameraId), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('returns full data object after fetch', async () => {
      const { result } = renderHook(() => useCameraAnomaliesQuery(mockCameraId), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockAnomaliesResponse);
      });
    });

    it('returns correct count after fetch', async () => {
      const { result } = renderHook(() => useCameraAnomaliesQuery(mockCameraId), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.count).toBe(2);
      });
    });

    it('returns correct periodDays after fetch', async () => {
      const { result } = renderHook(() => useCameraAnomaliesQuery(mockCameraId), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.periodDays).toBe(7);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch camera anomalies';
      (api.fetchCameraAnomalies as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useCameraAnomaliesQuery(mockCameraId), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useCameraAnomaliesQuery(mockCameraId, { enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchCameraAnomalies).not.toHaveBeenCalled();
    });

    it('does not fetch when cameraId is empty string', async () => {
      renderHook(() => useCameraAnomaliesQuery(''), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchCameraAnomalies).not.toHaveBeenCalled();
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useCameraAnomaliesQuery(mockCameraId), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('refetches data when refetch is called', async () => {
      const { result } = renderHook(() => useCameraAnomaliesQuery(mockCameraId), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Clear mock and refetch
      vi.clearAllMocks();
      await result.current.refetch();

      expect(api.fetchCameraAnomalies).toHaveBeenCalledTimes(1);
    });
  });

  describe('camera ID changes', () => {
    it('re-fetches when camera ID changes', async () => {
      const { result, rerender } = renderHook(
        ({ cameraId }) => useCameraAnomaliesQuery(cameraId),
        {
          wrapper: createQueryWrapper(),
          initialProps: { cameraId: mockCameraId },
        }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Change camera ID
      rerender({ cameraId: 'backyard' });

      await waitFor(() => {
        expect(api.fetchCameraAnomalies).toHaveBeenCalledTimes(2);
        expect(api.fetchCameraAnomalies).toHaveBeenLastCalledWith('backyard', 7);
      });
    });
  });

  describe('days parameter changes', () => {
    it('re-fetches when days parameter changes', async () => {
      const { result, rerender } = renderHook(
        ({ days }) => useCameraAnomaliesQuery(mockCameraId, { days }),
        {
          wrapper: createQueryWrapper(),
          initialProps: { days: 7 },
        }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Change days
      rerender({ days: 30 });

      await waitFor(() => {
        expect(api.fetchCameraAnomalies).toHaveBeenCalledTimes(2);
        expect(api.fetchCameraAnomalies).toHaveBeenLastCalledWith(mockCameraId, 30);
      });
    });
  });

  describe('empty response handling', () => {
    it('handles empty anomalies array', async () => {
      (api.fetchCameraAnomalies as ReturnType<typeof vi.fn>).mockResolvedValue({
        camera_id: 'front-door',
        anomalies: [],
        count: 0,
        period_days: 7,
      });

      const { result } = renderHook(() => useCameraAnomaliesQuery(mockCameraId), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.anomalies).toEqual([]);
      expect(result.current.count).toBe(0);
    });
  });
});

/**
 * Tests for useCameraUptimeQuery hook
 *
 * Tests cover:
 * - Initial loading state
 * - Successful data fetch
 * - Error handling
 * - Enabled option
 * - Refetch functionality
 * - Date range parameter handling
 */
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useCameraUptimeQuery } from './useCameraUptimeQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchCameraUptime: vi.fn(),
}));

describe('useCameraUptimeQuery', () => {
  const mockDateRange = {
    startDate: '2026-01-10',
    endDate: '2026-01-17',
  };

  const mockCameraUptimeResponse = {
    cameras: [
      {
        camera_id: 'front-door',
        camera_name: 'Front Door',
        uptime_percentage: 99.2,
        detection_count: 156,
      },
      {
        camera_id: 'backyard',
        camera_name: 'Backyard',
        uptime_percentage: 87.5,
        detection_count: 89,
      },
      {
        camera_id: 'garage',
        camera_name: 'Garage',
        uptime_percentage: 62.1,
        detection_count: 34,
      },
    ],
    start_date: '2026-01-10',
    end_date: '2026-01-17',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchCameraUptime as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockCameraUptimeResponse
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchCameraUptime as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useCameraUptimeQuery(mockDateRange), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with empty cameras array', () => {
      (api.fetchCameraUptime as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useCameraUptimeQuery(mockDateRange), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.cameras).toEqual([]);
    });
  });

  describe('fetching data', () => {
    it('fetches camera uptime on mount with date range', async () => {
      renderHook(() => useCameraUptimeQuery(mockDateRange), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchCameraUptime).toHaveBeenCalledTimes(1);
        expect(api.fetchCameraUptime).toHaveBeenCalledWith({
          start_date: mockDateRange.startDate,
          end_date: mockDateRange.endDate,
        });
      });
    });

    it('updates cameras after successful fetch', async () => {
      const { result } = renderHook(() => useCameraUptimeQuery(mockDateRange), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.cameras).toEqual(mockCameraUptimeResponse.cameras);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useCameraUptimeQuery(mockDateRange), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('returns full data object after fetch', async () => {
      const { result } = renderHook(() => useCameraUptimeQuery(mockDateRange), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockCameraUptimeResponse);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch camera uptime';
      (api.fetchCameraUptime as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useCameraUptimeQuery(mockDateRange), {
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
      renderHook(() => useCameraUptimeQuery(mockDateRange, { enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchCameraUptime).not.toHaveBeenCalled();
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useCameraUptimeQuery(mockDateRange), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });

  describe('date range handling', () => {
    it('re-fetches when date range changes', async () => {
      const { result, rerender } = renderHook(
        ({ dateRange }) => useCameraUptimeQuery(dateRange),
        {
          wrapper: createQueryWrapper(),
          initialProps: { dateRange: mockDateRange },
        }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Change date range
      rerender({
        dateRange: {
          startDate: '2026-01-01',
          endDate: '2026-01-07',
        },
      });

      await waitFor(() => {
        expect(api.fetchCameraUptime).toHaveBeenCalledTimes(2);
        expect(api.fetchCameraUptime).toHaveBeenLastCalledWith({
          start_date: '2026-01-01',
          end_date: '2026-01-07',
        });
      });
    });
  });
});

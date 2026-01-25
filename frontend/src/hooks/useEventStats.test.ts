import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useEventStats, eventStatsQueryKeys } from './useEventStats';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { EventStatsResponse } from '../types/generated';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    fetchEventStats: vi.fn(),
  };
});

describe('useEventStats', () => {
  const mockStats: EventStatsResponse = {
    total_events: 44,
    events_by_risk_level: {
      critical: 2,
      high: 5,
      medium: 12,
      low: 25,
    },
    risk_distribution: [
      { risk_level: 'critical', count: 2 },
      { risk_level: 'high', count: 5 },
      { risk_level: 'medium', count: 12 },
      { risk_level: 'low', count: 25 },
    ],
    events_by_camera: [
      { camera_id: 'front_door', camera_name: 'Front Door', event_count: 30 },
      { camera_id: 'back_door', camera_name: 'Back Door', event_count: 14 },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchEventStats as ReturnType<typeof vi.fn>).mockResolvedValue(mockStats);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchEventStats as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useEventStats(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.stats).toBeUndefined();
    });

    it('fetches stats on mount', async () => {
      const { result } = renderHook(() => useEventStats(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventStats).toHaveBeenCalledTimes(1);
      expect(result.current.stats).toEqual(mockStats);
    });

    it('does not fetch when enabled is false', () => {
      renderHook(() => useEventStats({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      expect(api.fetchEventStats).not.toHaveBeenCalled();
    });
  });

  describe('filter parameters', () => {
    it('passes startDate to API', async () => {
      const { result } = renderHook(
        () => useEventStats({ startDate: '2025-01-01' }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventStats).toHaveBeenCalledWith(
        { start_date: '2025-01-01', end_date: undefined, camera_id: undefined },
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    it('passes endDate to API', async () => {
      const { result } = renderHook(
        () => useEventStats({ endDate: '2025-01-31' }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventStats).toHaveBeenCalledWith(
        { start_date: undefined, end_date: '2025-01-31', camera_id: undefined },
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    it('passes cameraId to API', async () => {
      const { result } = renderHook(
        () => useEventStats({ cameraId: 'front_door' }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventStats).toHaveBeenCalledWith(
        { start_date: undefined, end_date: undefined, camera_id: 'front_door' },
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    it('passes all filter parameters to API', async () => {
      const { result } = renderHook(
        () =>
          useEventStats({
            startDate: '2025-01-01',
            endDate: '2025-01-31',
            cameraId: 'front_door',
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventStats).toHaveBeenCalledWith(
        { start_date: '2025-01-01', end_date: '2025-01-31', camera_id: 'front_door' },
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });
  });

  describe('error handling', () => {
    it('handles API errors gracefully', async () => {
      const apiError = new Error('Network error');
      (api.fetchEventStats as ReturnType<typeof vi.fn>).mockRejectedValue(apiError);

      const { result } = renderHook(() => useEventStats(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isError).toBe(true);
      expect(result.current.error).toBe(apiError);
      expect(result.current.stats).toBeUndefined();
    });
  });

  describe('caching behavior', () => {
    it('uses stale time of 30 seconds', async () => {
      const { result, rerender } = renderHook(() => useEventStats(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventStats).toHaveBeenCalledTimes(1);

      // Rerender should use cached data
      rerender();

      expect(api.fetchEventStats).toHaveBeenCalledTimes(1);
      expect(result.current.stats).toEqual(mockStats);
    });
  });

  describe('refetch functionality', () => {
    it('provides refetch function', async () => {
      (api.fetchEventStats as ReturnType<typeof vi.fn>).mockResolvedValue(mockStats);

      const { result } = renderHook(() => useEventStats(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.refetch).toBeDefined();
      expect(typeof result.current.refetch).toBe('function');

      // Call refetch
      void result.current.refetch();

      await waitFor(() => {
        expect(api.fetchEventStats).toHaveBeenCalledTimes(2);
      });
    });
  });
});

describe('eventStatsQueryKeys', () => {
  it('generates base key', () => {
    expect(eventStatsQueryKeys.all).toEqual(['event-stats']);
  });

  it('generates stats key with no params', () => {
    expect(eventStatsQueryKeys.stats()).toEqual(['event-stats', 'stats', {}]);
  });

  it('generates stats key with startDate', () => {
    expect(eventStatsQueryKeys.stats({ startDate: '2025-01-01' })).toEqual([
      'event-stats',
      'stats',
      { startDate: '2025-01-01', endDate: undefined, cameraId: undefined },
    ]);
  });

  it('generates stats key with all params', () => {
    expect(
      eventStatsQueryKeys.stats({
        startDate: '2025-01-01',
        endDate: '2025-01-31',
        cameraId: 'front_door',
      })
    ).toEqual([
      'event-stats',
      'stats',
      { startDate: '2025-01-01', endDate: '2025-01-31', cameraId: 'front_door' },
    ]);
  });
});

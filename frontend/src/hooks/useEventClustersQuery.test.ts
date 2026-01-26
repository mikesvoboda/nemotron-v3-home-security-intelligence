/**
 * Unit tests for useEventClustersQuery hook (NEM-3676).
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useEventClustersQuery, eventClustersQueryKeys } from './useEventClustersQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { EventClustersResponse } from '../types/generated';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    fetchEventClusters: vi.fn(),
  };
});

describe('useEventClustersQuery', () => {
  const mockClustersResponse: EventClustersResponse = {
    clusters: [
      {
        cluster_id: 'cluster-1',
        start_time: '2026-01-25T10:00:00Z',
        end_time: '2026-01-25T10:05:00Z',
        event_count: 3,
        cameras: ['front_door'],
        risk_levels: { critical: 0, high: 1, medium: 1, low: 1 },
        object_types: { person: 2, vehicle: 1 },
        events: [
          {
            id: 1,
            camera_id: 'front_door',
            started_at: '2026-01-25T10:00:00Z',
            risk_score: 75,
            risk_level: 'high',
            summary: 'Person detected',
          },
          {
            id: 2,
            camera_id: 'front_door',
            started_at: '2026-01-25T10:02:00Z',
            risk_score: 50,
            risk_level: 'medium',
            summary: 'Movement detected',
          },
          {
            id: 3,
            camera_id: 'front_door',
            started_at: '2026-01-25T10:05:00Z',
            risk_score: 25,
            risk_level: 'low',
            summary: 'Vehicle detected',
          },
        ],
      },
    ],
    total_clusters: 1,
    unclustered_events: 5,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchEventClusters as ReturnType<typeof vi.fn>).mockResolvedValue(mockClustersResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchEventClusters as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () =>
          useEventClustersQuery({
            startDate: '2026-01-20T00:00:00Z',
            endDate: '2026-01-25T23:59:59Z',
          }),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeUndefined();
      expect(result.current.clusters).toEqual([]);
    });

    it('fetches clusters on mount', async () => {
      const { result } = renderHook(
        () =>
          useEventClustersQuery({
            startDate: '2026-01-20T00:00:00Z',
            endDate: '2026-01-25T23:59:59Z',
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventClusters).toHaveBeenCalledTimes(1);
      expect(result.current.data).toEqual(mockClustersResponse);
      expect(result.current.clusters).toEqual(mockClustersResponse.clusters);
      expect(result.current.totalClusters).toBe(1);
      expect(result.current.unclusteredEvents).toBe(5);
    });

    it('does not fetch when enabled is false', () => {
      renderHook(
        () =>
          useEventClustersQuery({
            startDate: '2026-01-20T00:00:00Z',
            endDate: '2026-01-25T23:59:59Z',
            enabled: false,
          }),
        { wrapper: createQueryWrapper() }
      );

      expect(api.fetchEventClusters).not.toHaveBeenCalled();
    });

    it('does not fetch when startDate is missing', () => {
      renderHook(
        () =>
          useEventClustersQuery({
            startDate: '',
            endDate: '2026-01-25T23:59:59Z',
          }),
        { wrapper: createQueryWrapper() }
      );

      expect(api.fetchEventClusters).not.toHaveBeenCalled();
    });

    it('does not fetch when endDate is missing', () => {
      renderHook(
        () =>
          useEventClustersQuery({
            startDate: '2026-01-20T00:00:00Z',
            endDate: '',
          }),
        { wrapper: createQueryWrapper() }
      );

      expect(api.fetchEventClusters).not.toHaveBeenCalled();
    });
  });

  describe('filter parameters', () => {
    it('passes required date parameters to API', async () => {
      const { result } = renderHook(
        () =>
          useEventClustersQuery({
            startDate: '2026-01-20T00:00:00Z',
            endDate: '2026-01-25T23:59:59Z',
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventClusters).toHaveBeenCalledWith(
        {
          start_date: '2026-01-20T00:00:00Z',
          end_date: '2026-01-25T23:59:59Z',
          camera_id: undefined,
          time_window_minutes: undefined,
          min_cluster_size: undefined,
        },
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    it('passes cameraId to API', async () => {
      const { result } = renderHook(
        () =>
          useEventClustersQuery({
            startDate: '2026-01-20T00:00:00Z',
            endDate: '2026-01-25T23:59:59Z',
            cameraId: 'front_door',
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventClusters).toHaveBeenCalledWith(
        expect.objectContaining({ camera_id: 'front_door' }),
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    it('passes timeWindowMinutes to API', async () => {
      const { result } = renderHook(
        () =>
          useEventClustersQuery({
            startDate: '2026-01-20T00:00:00Z',
            endDate: '2026-01-25T23:59:59Z',
            timeWindowMinutes: 10,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventClusters).toHaveBeenCalledWith(
        expect.objectContaining({ time_window_minutes: 10 }),
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    it('passes minClusterSize to API', async () => {
      const { result } = renderHook(
        () =>
          useEventClustersQuery({
            startDate: '2026-01-20T00:00:00Z',
            endDate: '2026-01-25T23:59:59Z',
            minClusterSize: 3,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventClusters).toHaveBeenCalledWith(
        expect.objectContaining({ min_cluster_size: 3 }),
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    it('passes all parameters to API', async () => {
      const { result } = renderHook(
        () =>
          useEventClustersQuery({
            startDate: '2026-01-20T00:00:00Z',
            endDate: '2026-01-25T23:59:59Z',
            cameraId: 'front_door',
            timeWindowMinutes: 10,
            minClusterSize: 3,
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventClusters).toHaveBeenCalledWith(
        {
          start_date: '2026-01-20T00:00:00Z',
          end_date: '2026-01-25T23:59:59Z',
          camera_id: 'front_door',
          time_window_minutes: 10,
          min_cluster_size: 3,
        },
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });
  });

  describe('error handling', () => {
    it('handles API errors gracefully', async () => {
      const apiError = new Error('Network error');
      (api.fetchEventClusters as ReturnType<typeof vi.fn>).mockRejectedValue(apiError);

      const { result } = renderHook(
        () =>
          useEventClustersQuery({
            startDate: '2026-01-20T00:00:00Z',
            endDate: '2026-01-25T23:59:59Z',
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.isError).toBe(true);
      expect(result.current.error).toBe(apiError);
      expect(result.current.data).toBeUndefined();
      expect(result.current.clusters).toEqual([]);
      expect(result.current.totalClusters).toBe(0);
      expect(result.current.unclusteredEvents).toBe(0);
    });
  });

  describe('caching behavior', () => {
    it('uses stale time of 30 seconds', async () => {
      const { result, rerender } = renderHook(
        () =>
          useEventClustersQuery({
            startDate: '2026-01-20T00:00:00Z',
            endDate: '2026-01-25T23:59:59Z',
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchEventClusters).toHaveBeenCalledTimes(1);

      // Rerender should use cached data
      rerender();

      expect(api.fetchEventClusters).toHaveBeenCalledTimes(1);
      expect(result.current.data).toEqual(mockClustersResponse);
    });
  });

  describe('refetch functionality', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(
        () =>
          useEventClustersQuery({
            startDate: '2026-01-20T00:00:00Z',
            endDate: '2026-01-25T23:59:59Z',
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.refetch).toBeDefined();
      expect(typeof result.current.refetch).toBe('function');

      // Call refetch
      void result.current.refetch();

      await waitFor(() => {
        expect(api.fetchEventClusters).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('empty response handling', () => {
    it('handles empty clusters array', async () => {
      const emptyResponse: EventClustersResponse = {
        clusters: [],
        total_clusters: 0,
        unclustered_events: 10,
      };
      (api.fetchEventClusters as ReturnType<typeof vi.fn>).mockResolvedValue(emptyResponse);

      const { result } = renderHook(
        () =>
          useEventClustersQuery({
            startDate: '2026-01-20T00:00:00Z',
            endDate: '2026-01-25T23:59:59Z',
          }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.clusters).toEqual([]);
      expect(result.current.totalClusters).toBe(0);
      expect(result.current.unclusteredEvents).toBe(10);
    });
  });
});

describe('eventClustersQueryKeys', () => {
  it('generates base key', () => {
    expect(eventClustersQueryKeys.all).toEqual(['event-clusters']);
  });

  it('generates clusters key with required params only', () => {
    expect(
      eventClustersQueryKeys.clusters({
        startDate: '2026-01-20T00:00:00Z',
        endDate: '2026-01-25T23:59:59Z',
      })
    ).toEqual([
      'event-clusters',
      'list',
      {
        startDate: '2026-01-20T00:00:00Z',
        endDate: '2026-01-25T23:59:59Z',
        cameraId: undefined,
        timeWindowMinutes: undefined,
        minClusterSize: undefined,
      },
    ]);
  });

  it('generates clusters key with all params', () => {
    expect(
      eventClustersQueryKeys.clusters({
        startDate: '2026-01-20T00:00:00Z',
        endDate: '2026-01-25T23:59:59Z',
        cameraId: 'front_door',
        timeWindowMinutes: 10,
        minClusterSize: 3,
      })
    ).toEqual([
      'event-clusters',
      'list',
      {
        startDate: '2026-01-20T00:00:00Z',
        endDate: '2026-01-25T23:59:59Z',
        cameraId: 'front_door',
        timeWindowMinutes: 10,
        minClusterSize: 3,
      },
    ]);
  });
});

/**
 * Tests for useLineZoneAnalytics hooks (NEM-4714)
 *
 * This module tests the line zone analytics hooks:
 * - useLineZoneAnalytics: Fetching line zones for a camera
 * - useCrossingTrends: Fetching crossing trends for a zone
 * - useResetCrossingCounts: Resetting crossing counts
 */
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';

import {
  useLineZoneAnalytics,
  useCrossingTrends,
  useResetCrossingCounts,
  lineZoneAnalyticsQueryKeys,
} from './useLineZoneAnalytics';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { CrossingTrendsResponse, LineZoneWithCounts } from '../types/zoneAnalytics';

// Save original fetch for restoration
const originalFetch = globalThis.fetch;

// Mock fetch globally
const mockFetch = vi.fn();

beforeAll(() => {
  globalThis.fetch = mockFetch as typeof fetch;
});

afterAll(() => {
  globalThis.fetch = originalFetch;
});

describe('useLineZoneAnalytics', () => {
  // Helper to create mock line zone data
  const createMockLineZone = (overrides: Partial<LineZoneWithCounts> = {}): LineZoneWithCounts => ({
    id: Math.floor(Math.random() * 1000),
    name: 'Test Line Zone',
    camera_id: 'cam-123',
    in_count: 10,
    out_count: 5,
    enabled: true,
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true when fetching', () => {
      mockFetch.mockReturnValue(new Promise(() => {})); // Never resolving

      const { result } = renderHook(() => useLineZoneAnalytics({ cameraId: 'cam-123' }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.lineZones).toEqual([]);
    });

    it('starts with empty lineZones array', () => {
      mockFetch.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useLineZoneAnalytics({ cameraId: 'cam-123' }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.lineZones).toEqual([]);
    });
  });

  describe('fetching data', () => {
    it('fetches line zones for a specific camera', async () => {
      const mockZones = [createMockLineZone()];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ zones: mockZones }),
      });

      renderHook(() => useLineZoneAnalytics({ cameraId: 'cam-123' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/analytics-zones/line-zones/camera/cam-123')
        );
      });
    });

    it('updates lineZones after successful fetch', async () => {
      const mockZones = [
        createMockLineZone({ id: 1, name: 'Zone A' }),
        createMockLineZone({ id: 2, name: 'Zone B' }),
      ];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ zones: mockZones }),
      });

      const { result } = renderHook(() => useLineZoneAnalytics({ cameraId: 'cam-123' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.lineZones).toEqual(mockZones);
      });

      expect(result.current.lineZones).toHaveLength(2);
    });

    it('sets isLoading false after fetch', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ zones: [] }),
      });

      const { result } = renderHook(() => useLineZoneAnalytics({ cameraId: 'cam-123' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
      });

      const { result } = renderHook(() => useLineZoneAnalytics({ cameraId: 'cam-123' }), {
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
      renderHook(() => useLineZoneAnalytics({ cameraId: 'cam-123', enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('does not fetch when cameraId is undefined', async () => {
      renderHook(() => useLineZoneAnalytics({}), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('refetch function', () => {
    it('provides refetch function', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ zones: [] }),
      });

      const { result } = renderHook(() => useLineZoneAnalytics({ cameraId: 'cam-123' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('refetch triggers new API call', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ zones: [] }),
      });

      const { result } = renderHook(() => useLineZoneAnalytics({ cameraId: 'cam-123' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const callCountBefore = mockFetch.mock.calls.length;

      act(() => {
        result.current.refetch();
      });

      await waitFor(() => {
        expect(mockFetch.mock.calls.length).toBeGreaterThan(callCountBefore);
      });
    });
  });

  describe('query keys', () => {
    it('generates correct query keys', () => {
      expect(lineZoneAnalyticsQueryKeys.all).toEqual(['line-zones']);
      expect(lineZoneAnalyticsQueryKeys.forCamera('cam-123')).toEqual([
        'line-zones',
        'camera',
        'cam-123',
      ]);
      expect(lineZoneAnalyticsQueryKeys.trends(1, 'hour')).toEqual(['crossing-trends', 1, 'hour']);
      expect(lineZoneAnalyticsQueryKeys.trends(2, 'day')).toEqual(['crossing-trends', 2, 'day']);
    });
  });
});

describe('useCrossingTrends', () => {
  // Helper to create mock trends response
  const createMockTrendsResponse = (
    overrides: Partial<CrossingTrendsResponse> = {}
  ): CrossingTrendsResponse => ({
    zone_id: 1,
    zone_name: 'Test Zone',
    trends: [
      {
        timestamp: '2024-01-01T10:00:00Z',
        in_count: 5,
        out_count: 3,
        net_flow: 2,
      },
      {
        timestamp: '2024-01-01T11:00:00Z',
        in_count: 8,
        out_count: 6,
        net_flow: 2,
      },
    ],
    total_in: 13,
    total_out: 9,
    start_time: '2024-01-01T00:00:00Z',
    end_time: '2024-01-01T23:59:59Z',
    interval: 'hour',
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  describe('fetching trends', () => {
    it('fetches crossing trends for a zone', async () => {
      const mockTrends = createMockTrendsResponse();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockTrends),
      });

      renderHook(() => useCrossingTrends({ zoneId: 1, interval: 'hour' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/analytics-zones/line-zones/1/crossing-trends?interval=hour')
        );
      });
    });

    it('returns trends data after successful fetch', async () => {
      const mockTrends = createMockTrendsResponse();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockTrends),
      });

      const { result } = renderHook(() => useCrossingTrends({ zoneId: 1 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockTrends);
      });
    });

    it('does not fetch when zoneId is undefined', async () => {
      renderHook(() => useCrossingTrends({}), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('uses day interval when specified', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockTrendsResponse({ interval: 'day' })),
      });

      renderHook(() => useCrossingTrends({ zoneId: 1, interval: 'day' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/analytics-zones/line-zones/1/crossing-trends?interval=day')
        );
      });
    });
  });
});

describe('useResetCrossingCounts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  it('calls reset API endpoint', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });

    const { result } = renderHook(() => useResetCrossingCounts(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      await result.current.mutateAsync(123);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/analytics-zones/line-zones/123/reset-counts'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('returns a mutation function', () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    });

    const { result } = renderHook(() => useResetCrossingCounts(), {
      wrapper: createQueryWrapper(),
    });

    expect(typeof result.current.mutateAsync).toBe('function');
    expect(typeof result.current.mutate).toBe('function');
  });

  it('handles reset failure', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      statusText: 'Server Error',
    });

    const { result } = renderHook(() => useResetCrossingCounts(), {
      wrapper: createQueryWrapper(),
    });

    await expect(
      act(async () => {
        await result.current.mutateAsync(123);
      })
    ).rejects.toThrow('Failed to reset counts');
  });
});

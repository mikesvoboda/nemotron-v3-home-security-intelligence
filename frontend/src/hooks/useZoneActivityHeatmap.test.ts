/**
 * Tests for useZoneActivityHeatmap hook (NEM-5024)
 *
 * This module tests the zone activity heatmap data fetching:
 * - Fetching heatmap data for a specific zone
 * - Time range filtering
 * - Loading and error states
 * - Data transformation
 */
import { renderHook, waitFor, act } from '@testing-library/react';
import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
  beforeAll,
  afterAll,
} from 'vitest';

import {
  useZoneActivityHeatmap,
  zoneActivityHeatmapQueryKeys,
} from './useZoneActivityHeatmap';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { ZoneActivityHeatmapResponse } from './useZoneActivityHeatmap';

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

describe('useZoneActivityHeatmap', () => {
  // Helper to create mock response
  const createMockResponse = (
    overrides: Partial<ZoneActivityHeatmapResponse> = {}
  ): ZoneActivityHeatmapResponse => ({
    zone_id: 1,
    zone_name: 'Front Door',
    time_range: '7d',
    weekly_data: [
      { hour: 8, day_of_week: 1, value: 15 },
      { hour: 9, day_of_week: 1, value: 22 },
      { hour: 17, day_of_week: 1, value: 18 },
    ],
    hourly_data: [
      { hour: 0, count: 2 },
      { hour: 8, count: 12 },
      { hour: 9, count: 15 },
    ],
    total_activity: 55,
    start_time: '2026-01-25T00:00:00Z',
    end_time: '2026-02-01T00:00:00Z',
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

      const { result } = renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.isLoading).toBe(true);
      expect(result.current.weeklyData).toEqual([]);
      expect(result.current.hourlyData).toEqual([]);
    });

    it('starts with empty data arrays', () => {
      mockFetch.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.weeklyData).toEqual([]);
      expect(result.current.hourlyData).toEqual([]);
      expect(result.current.totalActivity).toBe(0);
      expect(result.current.zoneName).toBe(null);
    });
  });

  describe('fetching data', () => {
    it('fetches heatmap data for a zone', async () => {
      const mockResponse = createMockResponse();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      renderHook(() => useZoneActivityHeatmap({ zoneId: 1 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/analytics-zones/polygon-zones/1/activity-heatmap')
        );
      });
    });

    it('passes time_range parameter to API', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse({ time_range: '30d' })),
      });

      renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1, timeRange: '30d' }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('time_range=30d')
        );
      });
    });

    it('updates data after successful fetch', async () => {
      const mockResponse = createMockResponse();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const { result } = renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.weeklyData).toHaveLength(3);
      });

      expect(result.current.zoneName).toBe('Front Door');
      expect(result.current.totalActivity).toBe(55);
      expect(result.current.hourlyData).toHaveLength(3);
    });

    it('transforms weekly data to component format', async () => {
      const mockResponse = createMockResponse();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const { result } = renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.weeklyData).toHaveLength(3);
      });

      // Verify transformation (day_of_week -> dayOfWeek)
      expect(result.current.weeklyData[0]).toEqual({
        hour: 8,
        dayOfWeek: 1,
        value: 15,
      });
    });

    it('sets isLoading false after fetch', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse()),
      });

      const { result } = renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
      });

      const { result } = renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
        },
        { timeout: 5000 }
      );

      expect(result.current.isError).toBe(true);
    });

    it('handles 404 zone not found', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      });

      const { result } = renderHook(
        () => useZoneActivityHeatmap({ zoneId: 999 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
        },
        { timeout: 5000 }
      );

      expect(result.current.error?.message).toContain('Zone not found');
    });
  });

  describe('time range options', () => {
    it('uses default time range of 7d', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse()),
      });

      renderHook(() => useZoneActivityHeatmap({ zoneId: 1 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('time_range=7d')
        );
      });
    });

    it('supports 1h time range', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse({ time_range: '1h' })),
      });

      renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1, timeRange: '1h' }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('time_range=1h')
        );
      });
    });

    it('supports 24h time range', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse({ time_range: '24h' })),
      });

      renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1, timeRange: '24h' }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('time_range=24h')
        );
      });
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1, enabled: false }),
        { wrapper: createQueryWrapper() }
      );

      await new Promise((r) => setTimeout(r, 100));
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('does not fetch when zoneId is empty string', async () => {
      renderHook(
        () => useZoneActivityHeatmap({ zoneId: '' }),
        { wrapper: createQueryWrapper() }
      );

      await new Promise((r) => setTimeout(r, 100));
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('refresh function', () => {
    it('provides refresh function', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse()),
      });

      const { result } = renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refresh).toBe('function');
    });

    it('refresh triggers new API call', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse()),
      });

      const { result } = renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const callCountBefore = mockFetch.mock.calls.length;

      await act(async () => {
        await result.current.refresh();
      });

      // Should have at least one more call
      expect(mockFetch.mock.calls.length).toBeGreaterThan(callCountBefore);
    });
  });

  describe('refetch function', () => {
    it('provides refetch function', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse()),
      });

      const { result } = renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });

  describe('query keys', () => {
    it('generates correct query keys', () => {
      expect(zoneActivityHeatmapQueryKeys.all).toEqual(['zone-activity-heatmap']);
      expect(zoneActivityHeatmapQueryKeys.byZone(1)).toEqual([
        'zone-activity-heatmap',
        'zone',
        1,
      ]);
      expect(zoneActivityHeatmapQueryKeys.withRange(1, '7d')).toEqual([
        'zone-activity-heatmap',
        'zone',
        1,
        'range',
        '7d',
      ]);
    });

    it('supports string zone IDs', () => {
      expect(zoneActivityHeatmapQueryKeys.byZone('zone-123')).toEqual([
        'zone-activity-heatmap',
        'zone',
        'zone-123',
      ]);
    });
  });

  describe('empty data handling', () => {
    it('handles empty weekly_data', async () => {
      const mockResponse = createMockResponse({
        weekly_data: [],
        total_activity: 0,
      });
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const { result } = renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.weeklyData).toEqual([]);
      expect(result.current.totalActivity).toBe(0);
    });

    it('handles empty hourly_data', async () => {
      const mockResponse = createMockResponse({
        hourly_data: [],
      });
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const { result } = renderHook(
        () => useZoneActivityHeatmap({ zoneId: 1 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.hourlyData).toEqual([]);
    });
  });
});

/**
 * Tests for useZoneComparison hook (NEM-4714)
 *
 * This module tests the zone comparison hook:
 * - useZoneComparison: Fetching comparison data for multiple zones
 * - Query key generation
 * - Error handling
 */
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';

import {
  useZoneComparison,
  zoneComparisonQueryKeys,
  type ZoneComparisonResponse,
  type ZoneComparisonData,
} from './useZoneComparison';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

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

describe('useZoneComparison', () => {
  // Helper to create mock comparison data
  const createMockComparisonData = (
    overrides: Partial<ZoneComparisonData> = {}
  ): ZoneComparisonData => ({
    zone_id: Math.floor(Math.random() * 1000),
    zone_name: 'Test Zone',
    zone_type: 'entry_point',
    camera_id: 'cam-123',
    value: 42,
    trend_percent: 5.5,
    ...overrides,
  });

  // Helper to create mock response
  const createMockResponse = (
    overrides: Partial<ZoneComparisonResponse> = {}
  ): ZoneComparisonResponse => ({
    metric: 'crossings',
    zones: [
      createMockComparisonData({ zone_id: 1, zone_name: 'Zone A', value: 100 }),
      createMockComparisonData({ zone_id: 2, zone_name: 'Zone B', value: 75 }),
    ],
    start_time: '2024-01-01T00:00:00Z',
    end_time: '2024-01-01T23:59:59Z',
    comparison_period: 'day',
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
        () => useZoneComparison({ zoneIds: [1, 2], metric: 'crossings', period: 'day' }),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeUndefined();
    });

    it('starts with undefined data', () => {
      mockFetch.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () => useZoneComparison({ zoneIds: [1, 2] }),
        { wrapper: createQueryWrapper() }
      );

      expect(result.current.data).toBeUndefined();
    });
  });

  describe('fetching data', () => {
    it('fetches comparison data for specified zones', async () => {
      const mockResponse = createMockResponse();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      renderHook(
        () => useZoneComparison({ zoneIds: [1, 2], metric: 'crossings', period: 'day' }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/analytics-zones/comparison')
        );
      });

      // Check query params
      const callUrl = mockFetch.mock.calls[0][0] as string;
      expect(callUrl).toContain('zone_ids=1');
      expect(callUrl).toContain('zone_ids=2');
      expect(callUrl).toContain('metric=crossings');
      expect(callUrl).toContain('period=day');
    });

    it('returns comparison data after successful fetch', async () => {
      const mockResponse = createMockResponse();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const { result } = renderHook(
        () => useZoneComparison({ zoneIds: [1, 2] }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.data).toEqual(mockResponse);
      });

      expect(result.current.data?.zones).toHaveLength(2);
    });

    it('sets isLoading false after fetch', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse()),
      });

      const { result } = renderHook(
        () => useZoneComparison({ zoneIds: [1, 2] }),
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
        () => useZoneComparison({ zoneIds: [1, 2] }),
        { wrapper: createQueryWrapper() }
      );

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
      renderHook(
        () => useZoneComparison({ zoneIds: [1, 2], enabled: false }),
        { wrapper: createQueryWrapper() }
      );

      await new Promise((r) => setTimeout(r, 100));
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('does not fetch when zoneIds is empty', async () => {
      renderHook(
        () => useZoneComparison({ zoneIds: [] }),
        { wrapper: createQueryWrapper() }
      );

      await new Promise((r) => setTimeout(r, 100));
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });

  describe('default values', () => {
    it('uses crossings as default metric', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse()),
      });

      renderHook(
        () => useZoneComparison({ zoneIds: [1, 2] }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        const callUrl = mockFetch.mock.calls[0][0] as string;
        expect(callUrl).toContain('metric=crossings');
      });
    });

    it('uses day as default period', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse()),
      });

      renderHook(
        () => useZoneComparison({ zoneIds: [1, 2] }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        const callUrl = mockFetch.mock.calls[0][0] as string;
        expect(callUrl).toContain('period=day');
      });
    });
  });

  describe('different metrics and periods', () => {
    it('fetches dwell_time metric', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse({ metric: 'dwell_time' })),
      });

      renderHook(
        () => useZoneComparison({ zoneIds: [1, 2], metric: 'dwell_time' }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        const callUrl = mockFetch.mock.calls[0][0] as string;
        expect(callUrl).toContain('metric=dwell_time');
      });
    });

    it('fetches week period', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse({ comparison_period: 'week' })),
      });

      renderHook(
        () => useZoneComparison({ zoneIds: [1, 2], period: 'week' }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        const callUrl = mockFetch.mock.calls[0][0] as string;
        expect(callUrl).toContain('period=week');
      });
    });

    it('fetches month period', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse({ comparison_period: 'month' })),
      });

      renderHook(
        () => useZoneComparison({ zoneIds: [1, 2], period: 'month' }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        const callUrl = mockFetch.mock.calls[0][0] as string;
        expect(callUrl).toContain('period=month');
      });
    });
  });

  describe('refetch function', () => {
    it('provides refetch function', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(createMockResponse()),
      });

      const { result } = renderHook(
        () => useZoneComparison({ zoneIds: [1, 2] }),
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
      expect(zoneComparisonQueryKeys.all).toEqual(['zone-comparison']);

      // Zone IDs are sorted for cache key consistency
      expect(zoneComparisonQueryKeys.comparison([2, 1], 'crossings', 'day')).toEqual([
        'zone-comparison',
        [1, 2],
        'crossings',
        'day',
      ]);

      expect(zoneComparisonQueryKeys.comparison([3], 'dwell_time', 'week')).toEqual([
        'zone-comparison',
        [3],
        'dwell_time',
        'week',
      ]);
    });
  });
});

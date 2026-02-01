/**
 * Tests for useDwellTimeAnalytics hooks (NEM-4714)
 *
 * This module tests the dwell time analytics hooks:
 * - usePolygonZones: Fetching polygon zones for a camera
 * - useDwellStatistics: Fetching dwell statistics for a zone
 * - useActiveDwellers: Fetching active dwellers for a zone
 * - formatDuration: Utility function for formatting durations
 */
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach, beforeAll, afterAll } from 'vitest';

import {
  usePolygonZones,
  useDwellStatistics,
  useActiveDwellers,
  formatDuration,
  dwellTimeAnalyticsQueryKeys,
} from './useDwellTimeAnalytics';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type {
  DwellStatistics,
  ActiveDwellersResponse,
  PolygonZone,
} from './useDwellTimeAnalytics';

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

describe('usePolygonZones', () => {
  // Helper to create mock polygon zone data
  const createMockPolygonZone = (overrides: Partial<PolygonZone> = {}): PolygonZone => ({
    id: Math.floor(Math.random() * 1000),
    name: 'Test Polygon Zone',
    camera_id: 'cam-123',
    zone_type: 'monitoring',
    is_active: true,
    current_count: 2,
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

      const { result } = renderHook(() => usePolygonZones({ cameraId: 'cam-123' }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.polygonZones).toEqual([]);
    });

    it('starts with empty polygonZones array', () => {
      mockFetch.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => usePolygonZones({ cameraId: 'cam-123' }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.polygonZones).toEqual([]);
    });
  });

  describe('fetching data', () => {
    it('fetches polygon zones for a specific camera', async () => {
      const mockZones = [createMockPolygonZone()];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ zones: mockZones }),
      });

      renderHook(() => usePolygonZones({ cameraId: 'cam-123' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/analytics-zones/polygon-zones/camera/cam-123')
        );
      });
    });

    it('updates polygonZones after successful fetch', async () => {
      const mockZones = [
        createMockPolygonZone({ id: 1, name: 'Zone A' }),
        createMockPolygonZone({ id: 2, name: 'Zone B' }),
      ];
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ zones: mockZones }),
      });

      const { result } = renderHook(() => usePolygonZones({ cameraId: 'cam-123' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.polygonZones).toEqual(mockZones);
      });

      expect(result.current.polygonZones).toHaveLength(2);
    });

    it('sets isLoading false after fetch', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ zones: [] }),
      });

      const { result } = renderHook(() => usePolygonZones({ cameraId: 'cam-123' }), {
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

      const { result } = renderHook(() => usePolygonZones({ cameraId: 'cam-123' }), {
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
      renderHook(() => usePolygonZones({ cameraId: 'cam-123', enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('does not fetch when cameraId is undefined', async () => {
      renderHook(() => usePolygonZones({}), {
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

      const { result } = renderHook(() => usePolygonZones({ cameraId: 'cam-123' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });

  describe('query keys', () => {
    it('generates correct query keys', () => {
      expect(dwellTimeAnalyticsQueryKeys.all).toEqual(['dwell-time']);
      expect(dwellTimeAnalyticsQueryKeys.polygonZones('cam-123')).toEqual([
        'dwell-time',
        'polygon-zones',
        'cam-123',
      ]);
      expect(dwellTimeAnalyticsQueryKeys.statistics(1)).toEqual(['dwell-time', 'statistics', 1]);
      expect(dwellTimeAnalyticsQueryKeys.activeDwellers(2)).toEqual(['dwell-time', 'dwellers', 2]);
    });
  });
});

describe('useDwellStatistics', () => {
  // Helper to create mock dwell statistics
  const createMockDwellStatistics = (
    overrides: Partial<DwellStatistics> = {}
  ): DwellStatistics => ({
    zone_id: 1,
    total_records: 50,
    avg_dwell_seconds: 120,
    max_dwell_seconds: 300,
    min_dwell_seconds: 30,
    alerts_triggered: 3,
    start_time: '2024-01-01T00:00:00Z',
    end_time: '2024-01-01T23:59:59Z',
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  describe('fetching statistics', () => {
    it('fetches dwell statistics for a zone', async () => {
      const mockStats = createMockDwellStatistics();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockStats),
      });

      renderHook(() => useDwellStatistics({ zoneId: 1 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/analytics-zones/polygon-zones/1/dwell-statistics')
        );
      });
    });

    it('returns statistics data after successful fetch', async () => {
      const mockStats = createMockDwellStatistics();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockStats),
      });

      const { result } = renderHook(() => useDwellStatistics({ zoneId: 1 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.statistics).toEqual(mockStats);
      });
    });

    it('does not fetch when zoneId is undefined', async () => {
      renderHook(() => useDwellStatistics({}), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('sets error on fetch failure', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Server Error',
      });

      const { result } = renderHook(() => useDwellStatistics({ zoneId: 1 }), {
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
});

describe('useActiveDwellers', () => {
  // Helper to create mock active dwellers response
  const createMockActiveDwellersResponse = (
    overrides: Partial<ActiveDwellersResponse> = {}
  ): ActiveDwellersResponse => ({
    zone_id: 1,
    dwellers: [
      {
        record_id: 1,
        track_id: 'track-001',
        camera_id: 'cam-123',
        object_class: 'person',
        entry_time: '2024-01-01T10:00:00Z',
        current_dwell_seconds: 60,
      },
      {
        record_id: 2,
        track_id: 'track-002',
        camera_id: 'cam-123',
        object_class: 'person',
        entry_time: '2024-01-01T10:05:00Z',
        current_dwell_seconds: 30,
      },
    ],
    total: 2,
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  describe('fetching active dwellers', () => {
    it('fetches active dwellers for a zone', async () => {
      const mockDwellers = createMockActiveDwellersResponse();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockDwellers),
      });

      renderHook(() => useActiveDwellers({ zoneId: 1 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith(
          expect.stringContaining('/api/analytics-zones/polygon-zones/1/dwellers')
        );
      });
    });

    it('returns dwellers data after successful fetch', async () => {
      const mockDwellers = createMockActiveDwellersResponse();
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockDwellers),
      });

      const { result } = renderHook(() => useActiveDwellers({ zoneId: 1 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockDwellers);
      });
    });

    it('does not fetch when zoneId is undefined', async () => {
      renderHook(() => useActiveDwellers({}), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(mockFetch).not.toHaveBeenCalled();
    });
  });
});

describe('formatDuration', () => {
  it('returns "--" for null values', () => {
    expect(formatDuration(null)).toBe('--');
  });

  it('formats seconds only when less than a minute', () => {
    expect(formatDuration(0)).toBe('0s');
    expect(formatDuration(30)).toBe('30s');
    expect(formatDuration(59)).toBe('59s');
  });

  it('formats minutes and seconds for durations >= 1 minute', () => {
    expect(formatDuration(60)).toBe('1m 0s');
    expect(formatDuration(90)).toBe('1m 30s');
    expect(formatDuration(125)).toBe('2m 5s');
    expect(formatDuration(300)).toBe('5m 0s');
  });

  it('rounds seconds to nearest integer', () => {
    expect(formatDuration(30.4)).toBe('30s');
    expect(formatDuration(30.6)).toBe('31s');
    // 90.5 seconds = 1m 30.5s, rounded to 1m 31s
    expect(formatDuration(90.5)).toBe('1m 31s');
  });

  it('handles large durations', () => {
    expect(formatDuration(3600)).toBe('60m 0s');
    expect(formatDuration(7200)).toBe('120m 0s');
  });
});

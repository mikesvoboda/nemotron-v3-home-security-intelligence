import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { useTimelineData, generateMockTimelineData } from './useTimelineData';

// ============================================================================
// Test Data
// ============================================================================

const mockTimelineResponse = {
  buckets: [
    { timestamp: '2024-01-15T06:00:00Z', event_count: 5, max_risk_score: 20 },
    { timestamp: '2024-01-15T07:00:00Z', event_count: 12, max_risk_score: 45 },
    { timestamp: '2024-01-15T08:00:00Z', event_count: 3, max_risk_score: 75 },
    { timestamp: '2024-01-15T09:00:00Z', event_count: 8, max_risk_score: 90 },
  ],
  total_events: 28,
  start_date: '2024-01-15T06:00:00Z',
  end_date: '2024-01-15T10:00:00Z',
};

// ============================================================================
// Test Setup
// ============================================================================

// Mock fetch globally
const mockFetch = vi.fn();

function createTestWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
    },
  });

  return function TestWrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('useTimelineData', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal('fetch', mockFetch);
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockTimelineResponse),
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('basic functionality', () => {
    it('starts with isLoading true and empty buckets', () => {
      // Return a promise that never resolves to keep loading state
      mockFetch.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(
        () =>
          useTimelineData({
            zoomLevel: 'day',
            startDate: '2024-01-15T06:00:00Z',
            endDate: '2024-01-15T10:00:00Z',
          }),
        { wrapper: createTestWrapper() }
      );

      expect(result.current.isLoading).toBe(true);
      expect(result.current.buckets).toEqual([]);
      expect(result.current.totalEvents).toBe(0);
    });

    it('fetches timeline data successfully', async () => {
      const { result } = renderHook(
        () =>
          useTimelineData({
            zoomLevel: 'day',
            startDate: '2024-01-15T06:00:00Z',
            endDate: '2024-01-15T10:00:00Z',
          }),
        { wrapper: createTestWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.buckets).toHaveLength(4);
      expect(result.current.totalEvents).toBe(28);
      expect(result.current.isError).toBe(false);
    });

    it('transforms risk scores to severity levels', async () => {
      const { result } = renderHook(
        () =>
          useTimelineData({
            zoomLevel: 'day',
            startDate: '2024-01-15T06:00:00Z',
            endDate: '2024-01-15T10:00:00Z',
          }),
        { wrapper: createTestWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Check severity transformations based on risk score thresholds
      // 20 -> low (0-29)
      expect(result.current.buckets[0].maxSeverity).toBe('low');
      // 45 -> medium (30-59)
      expect(result.current.buckets[1].maxSeverity).toBe('medium');
      // 75 -> high (60-84)
      expect(result.current.buckets[2].maxSeverity).toBe('high');
      // 90 -> critical (85-100)
      expect(result.current.buckets[3].maxSeverity).toBe('critical');
    });

    it('handles disabled query', () => {
      const { result } = renderHook(
        () =>
          useTimelineData({
            zoomLevel: 'day',
            enabled: false,
          }),
        { wrapper: createTestWrapper() }
      );

      // Should not have called fetch when disabled
      expect(mockFetch).not.toHaveBeenCalled();
      expect(result.current.buckets).toEqual([]);
      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('error handling', () => {
    it('handles API errors', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
      });

      const { result } = renderHook(
        () =>
          useTimelineData({
            zoomLevel: 'day',
            startDate: '2024-01-15T06:00:00Z',
            endDate: '2024-01-15T10:00:00Z',
          }),
        { wrapper: createTestWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });

      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.buckets).toEqual([]);
    });

    it('handles network errors', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(
        () =>
          useTimelineData({
            zoomLevel: 'day',
            startDate: '2024-01-10T00:00:00Z',
            endDate: '2024-01-11T00:00:00Z',
          }),
        { wrapper: createTestWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isError).toBe(true);
      });
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(
        () =>
          useTimelineData({
            zoomLevel: 'day',
            startDate: '2024-01-15T00:00:00Z',
            endDate: '2024-01-16T00:00:00Z',
          }),
        { wrapper: createTestWrapper() }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });
});

describe('generateMockTimelineData', () => {
  it('generates buckets for hour zoom level', () => {
    const buckets = generateMockTimelineData('hour');

    expect(buckets.length).toBeGreaterThan(0);
    // Hour view should have ~12 buckets (5 min each for 1 hour)
    expect(buckets.length).toBeGreaterThanOrEqual(12);
  });

  it('generates buckets for day zoom level', () => {
    const buckets = generateMockTimelineData('day');

    expect(buckets.length).toBeGreaterThan(0);
    // Day view should have ~24 buckets (1 hour each for 24 hours)
    expect(buckets.length).toBeGreaterThanOrEqual(24);
  });

  it('generates buckets for week zoom level', () => {
    const buckets = generateMockTimelineData('week');

    expect(buckets.length).toBeGreaterThan(0);
    // Week view should have ~7 buckets (1 day each for 7 days)
    expect(buckets.length).toBeGreaterThanOrEqual(7);
  });

  it('uses provided date range', () => {
    const startDate = '2024-01-15T00:00:00Z';
    const endDate = '2024-01-15T06:00:00Z';

    const buckets = generateMockTimelineData('day', startDate, endDate);

    // Should have buckets within the range
    const firstBucket = new Date(buckets[0].timestamp);
    const lastBucket = new Date(buckets[buckets.length - 1].timestamp);

    expect(firstBucket.getTime()).toBeGreaterThanOrEqual(new Date(startDate).getTime());
    expect(lastBucket.getTime()).toBeLessThanOrEqual(new Date(endDate).getTime());
  });

  it('generates valid severity levels', () => {
    const buckets = generateMockTimelineData('day');

    buckets.forEach((bucket) => {
      expect(['low', 'medium', 'high', 'critical']).toContain(bucket.maxSeverity);
    });
  });

  it('generates non-negative event counts', () => {
    const buckets = generateMockTimelineData('day');

    buckets.forEach((bucket) => {
      expect(bucket.eventCount).toBeGreaterThanOrEqual(0);
    });
  });

  it('generates valid ISO timestamps', () => {
    const buckets = generateMockTimelineData('day');

    buckets.forEach((bucket) => {
      const date = new Date(bucket.timestamp);
      expect(date.toISOString()).toBe(bucket.timestamp);
    });
  });
});

/**
 * Tests for useSceneChangeSummaryQuery hook (NEM-3580)
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useSceneChangeSummaryQuery } from './useSceneChangeSummaryQuery';
import * as api from '../services/api';

import type { SceneChangeSummary } from '../services/api';

// Mock the API module
vi.mock('../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../services/api');
  return {
    ...actual,
    fetchSceneChangeSummary: vi.fn(),
  };
});

const mockFetchSceneChangeSummary = vi.mocked(api.fetchSceneChangeSummary);

// Helper to create a test wrapper with QueryClient
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

// Mock summary data
const mockSummary: SceneChangeSummary = {
  cameraId: 'front_door',
  totalChanges: 5,
  unacknowledgedCount: 2,
  acknowledgedCount: 3,
  lastChangeAt: '2026-01-25T10:00:00Z',
  firstChangeAt: '2026-01-20T08:00:00Z',
  byType: [
    { type: 'view_blocked', count: 3, percentage: 60 },
    { type: 'angle_changed', count: 2, percentage: 40 },
  ],
  avgSimilarityScore: 0.45,
  mostCommonType: 'view_blocked',
  periodDays: 7,
};

describe('useSceneChangeSummaryQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchSceneChangeSummary.mockResolvedValue(mockSummary);
  });

  it('fetches summary data successfully', async () => {
    const { result } = renderHook(
      () => useSceneChangeSummaryQuery('front_door'),
      { wrapper: createWrapper() }
    );

    // Initially loading
    expect(result.current.isLoading).toBe(true);

    // Wait for data
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(mockFetchSceneChangeSummary).toHaveBeenCalledWith('front_door', { days: 7 });
    expect(result.current.data).toEqual(mockSummary);
    expect(result.current.totalChanges).toBe(5);
    expect(result.current.unacknowledgedCount).toBe(2);
  });

  it('returns correct acknowledgement breakdown', async () => {
    const { result } = renderHook(
      () => useSceneChangeSummaryQuery('front_door'),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.unacknowledgedCount).toBe(2);
    expect(result.current.acknowledgedCount).toBe(3);
    expect(result.current.hasUnacknowledged).toBe(true);
  });

  it('parses lastChangeAt as Date', async () => {
    const { result } = renderHook(
      () => useSceneChangeSummaryQuery('front_door'),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.lastChangeAt).toBeInstanceOf(Date);
    expect(result.current.lastChangeAt?.toISOString()).toBe('2026-01-25T10:00:00.000Z');
  });

  it('returns type breakdown sorted by count', async () => {
    const { result } = renderHook(
      () => useSceneChangeSummaryQuery('front_door'),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.byType).toHaveLength(2);
    expect(result.current.byType[0].type).toBe('view_blocked');
    expect(result.current.byType[0].count).toBe(3);
    expect(result.current.byType[0].percentage).toBe(60);
  });

  it('returns mostCommonType', async () => {
    const { result } = renderHook(
      () => useSceneChangeSummaryQuery('front_door'),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.mostCommonType).toBe('view_blocked');
  });

  it('returns avgSimilarityScore', async () => {
    const { result } = renderHook(
      () => useSceneChangeSummaryQuery('front_door'),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.avgSimilarityScore).toBe(0.45);
  });

  it('passes custom days parameter', async () => {
    const { result } = renderHook(
      () => useSceneChangeSummaryQuery('front_door', { days: 30 }),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(mockFetchSceneChangeSummary).toHaveBeenCalledWith('front_door', { days: 30 });
  });

  it('does not fetch when disabled', () => {
    const { result } = renderHook(
      () => useSceneChangeSummaryQuery('front_door', { enabled: false }),
      { wrapper: createWrapper() }
    );

    expect(result.current.isLoading).toBe(false);
    expect(mockFetchSceneChangeSummary).not.toHaveBeenCalled();
  });

  it('handles empty camera ID', () => {
    const { result } = renderHook(
      () => useSceneChangeSummaryQuery(''),
      { wrapper: createWrapper() }
    );

    expect(result.current.isLoading).toBe(false);
    expect(mockFetchSceneChangeSummary).not.toHaveBeenCalled();
  });

  it('handles errors gracefully', async () => {
    mockFetchSceneChangeSummary.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(
      () => useSceneChangeSummaryQuery('front_door'),
      { wrapper: createWrapper() }
    );

    // Wait for error state with extended timeout (retry takes time)
    await waitFor(() => expect(result.current.isError).toBe(true), { timeout: 3000 });

    expect(result.current.error).toBeTruthy();
    expect(result.current.totalChanges).toBe(0);
    expect(result.current.byType).toEqual([]);
  });

  it('provides refetch function', async () => {
    const { result } = renderHook(
      () => useSceneChangeSummaryQuery('front_door'),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.refetch).toBeDefined();
    expect(typeof result.current.refetch).toBe('function');

    await result.current.refetch();
    expect(mockFetchSceneChangeSummary).toHaveBeenCalledTimes(2);
  });

  it('returns defaults when no data', () => {
    const { result } = renderHook(
      () => useSceneChangeSummaryQuery('front_door'),
      { wrapper: createWrapper() }
    );

    // Before data loads
    expect(result.current.totalChanges).toBe(0);
    expect(result.current.unacknowledgedCount).toBe(0);
    expect(result.current.acknowledgedCount).toBe(0);
    expect(result.current.lastChangeAt).toBeNull();
    expect(result.current.byType).toEqual([]);
    expect(result.current.mostCommonType).toBeNull();
    expect(result.current.avgSimilarityScore).toBeNull();
    expect(result.current.hasUnacknowledged).toBe(false);
    expect(result.current.periodDays).toBe(7); // Default
  });

  it('handles summary with no changes', async () => {
    const emptySummary: SceneChangeSummary = {
      cameraId: 'front_door',
      totalChanges: 0,
      unacknowledgedCount: 0,
      acknowledgedCount: 0,
      lastChangeAt: null,
      firstChangeAt: null,
      byType: [],
      avgSimilarityScore: null,
      mostCommonType: null,
      periodDays: 7,
    };
    mockFetchSceneChangeSummary.mockResolvedValue(emptySummary);

    const { result } = renderHook(
      () => useSceneChangeSummaryQuery('front_door'),
      { wrapper: createWrapper() }
    );

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.totalChanges).toBe(0);
    expect(result.current.hasUnacknowledged).toBe(false);
    expect(result.current.lastChangeAt).toBeNull();
    expect(result.current.mostCommonType).toBeNull();
  });
});

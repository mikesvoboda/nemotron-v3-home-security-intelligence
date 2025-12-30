import { renderHook, waitFor, act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest';

import { useStorageStats } from './useStorageStats';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api');

describe('useStorageStats', () => {
  const mockStorageStats: api.StorageStatsResponse = {
    disk_used_bytes: 107374182400,
    disk_total_bytes: 536870912000,
    disk_free_bytes: 429496729600,
    disk_usage_percent: 20.0,
    thumbnails: {
      file_count: 1500,
      size_bytes: 75000000,
    },
    images: {
      file_count: 10000,
      size_bytes: 5000000000,
    },
    clips: {
      file_count: 50,
      size_bytes: 500000000,
    },
    events_count: 156,
    detections_count: 892,
    gpu_stats_count: 2880,
    logs_count: 5000,
    timestamp: '2025-12-30T10:30:00Z',
  };

  const mockCleanupPreview: api.CleanupResponse = {
    events_deleted: 10,
    detections_deleted: 50,
    gpu_stats_deleted: 100,
    logs_deleted: 25,
    thumbnails_deleted: 50,
    images_deleted: 0,
    space_reclaimed: 1024000,
    retention_days: 30,
    dry_run: true,
    timestamp: '2025-12-30T10:30:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Use shouldAdvanceTime to prevent waitFor from hanging
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('fetches storage stats on mount', async () => {
    vi.mocked(api.fetchStorageStats).mockResolvedValue(mockStorageStats);

    const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

    expect(result.current.loading).toBe(true);
    expect(result.current.stats).toBe(null);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.stats).toEqual(mockStorageStats);
    expect(result.current.error).toBe(null);
  });

  it('handles fetch error', async () => {
    vi.mocked(api.fetchStorageStats).mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.stats).toBe(null);
    expect(result.current.error).toBe('Network error');
  });

  it('handles non-Error rejection', async () => {
    vi.mocked(api.fetchStorageStats).mockRejectedValue('Unknown error');

    const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.error).toBe('Failed to fetch storage stats');
  });

  it('polls at the specified interval', async () => {
    vi.mocked(api.fetchStorageStats).mockResolvedValue(mockStorageStats);

    renderHook(() => useStorageStats({ pollInterval: 5000, enablePolling: true }));

    // Wait for initial fetch
    await waitFor(() => {
      expect(api.fetchStorageStats).toHaveBeenCalledTimes(1);
    });

    // Advance timer by 5 seconds
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    await waitFor(() => {
      expect(api.fetchStorageStats).toHaveBeenCalledTimes(2);
    });

    // Advance timer by another 5 seconds
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    await waitFor(() => {
      expect(api.fetchStorageStats).toHaveBeenCalledTimes(3);
    });
  });

  it('does not poll when polling is disabled', async () => {
    vi.mocked(api.fetchStorageStats).mockResolvedValue(mockStorageStats);

    renderHook(() => useStorageStats({ pollInterval: 5000, enablePolling: false }));

    // Wait for initial fetch
    await waitFor(() => {
      expect(api.fetchStorageStats).toHaveBeenCalledTimes(1);
    });

    // Advance timer by 10 seconds
    act(() => {
      vi.advanceTimersByTime(10000);
    });

    // Should still only have 1 call (no polling)
    expect(api.fetchStorageStats).toHaveBeenCalledTimes(1);
  });

  it('stops polling on unmount', async () => {
    vi.mocked(api.fetchStorageStats).mockResolvedValue(mockStorageStats);

    const { unmount } = renderHook(() =>
      useStorageStats({ pollInterval: 5000, enablePolling: true })
    );

    // Wait for initial fetch
    await waitFor(() => {
      expect(api.fetchStorageStats).toHaveBeenCalledTimes(1);
    });

    // Unmount the hook
    unmount();

    // Advance timer
    act(() => {
      vi.advanceTimersByTime(10000);
    });

    // Should still only have 1 call
    expect(api.fetchStorageStats).toHaveBeenCalledTimes(1);
  });

  it('provides refresh function', async () => {
    vi.mocked(api.fetchStorageStats).mockResolvedValue(mockStorageStats);

    const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(api.fetchStorageStats).toHaveBeenCalledTimes(1);

    // Call refresh
    await act(async () => {
      await result.current.refresh();
    });

    expect(api.fetchStorageStats).toHaveBeenCalledTimes(2);
  });

  it('sets loading state during refresh', async () => {
    vi.mocked(api.fetchStorageStats).mockResolvedValue(mockStorageStats);

    const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Start refresh but don't await
    let refreshPromise: Promise<void>;
    act(() => {
      refreshPromise = result.current.refresh();
    });

    // Loading should be true
    expect(result.current.loading).toBe(true);

    // Wait for refresh to complete
    await act(async () => {
      await refreshPromise;
    });

    expect(result.current.loading).toBe(false);
  });

  it('provides previewCleanup function', async () => {
    vi.mocked(api.fetchStorageStats).mockResolvedValue(mockStorageStats);
    vi.mocked(api.previewCleanup).mockResolvedValue(mockCleanupPreview);

    const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.cleanupPreview).toBe(null);

    // Call previewCleanup
    let previewResult: api.CleanupResponse | null = null;
    await act(async () => {
      previewResult = await result.current.previewCleanup();
    });

    expect(api.previewCleanup).toHaveBeenCalledTimes(1);
    expect(previewResult).toEqual(mockCleanupPreview);
    expect(result.current.cleanupPreview).toEqual(mockCleanupPreview);
  });

  it('sets previewLoading state during cleanup preview', async () => {
    vi.mocked(api.fetchStorageStats).mockResolvedValue(mockStorageStats);
    vi.mocked(api.previewCleanup).mockResolvedValue(mockCleanupPreview);

    const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.previewLoading).toBe(false);

    // Start preview but don't await
    let previewPromise: Promise<api.CleanupResponse | null>;
    act(() => {
      previewPromise = result.current.previewCleanup();
    });

    // Preview loading should be true
    expect(result.current.previewLoading).toBe(true);

    // Wait for preview to complete
    await act(async () => {
      await previewPromise;
    });

    expect(result.current.previewLoading).toBe(false);
  });

  it('handles previewCleanup error', async () => {
    vi.mocked(api.fetchStorageStats).mockResolvedValue(mockStorageStats);
    vi.mocked(api.previewCleanup).mockRejectedValue(new Error('Preview failed'));

    const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Call previewCleanup
    let previewResult: api.CleanupResponse | null = null;
    await act(async () => {
      previewResult = await result.current.previewCleanup();
    });

    expect(previewResult).toBe(null);
    expect(result.current.error).toBe('Preview failed');
  });

  it('uses default poll interval of 60 seconds', async () => {
    vi.mocked(api.fetchStorageStats).mockResolvedValue(mockStorageStats);

    renderHook(() => useStorageStats({ enablePolling: true }));

    // Wait for initial fetch
    await waitFor(() => {
      expect(api.fetchStorageStats).toHaveBeenCalledTimes(1);
    });

    // Advance by 30 seconds - should not poll yet
    act(() => {
      vi.advanceTimersByTime(30000);
    });

    expect(api.fetchStorageStats).toHaveBeenCalledTimes(1);

    // Advance by another 30 seconds (total 60 seconds) - should poll
    act(() => {
      vi.advanceTimersByTime(30000);
    });

    await waitFor(() => {
      expect(api.fetchStorageStats).toHaveBeenCalledTimes(2);
    });
  });

  it('clears error on successful fetch', async () => {
    vi.mocked(api.fetchStorageStats).mockRejectedValueOnce(new Error('Network error'));
    vi.mocked(api.fetchStorageStats).mockResolvedValueOnce(mockStorageStats);

    const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

    // Wait for error
    await waitFor(() => {
      expect(result.current.error).toBe('Network error');
    });

    // Call refresh
    await act(async () => {
      await result.current.refresh();
    });

    // Error should be cleared
    expect(result.current.error).toBe(null);
    expect(result.current.stats).toEqual(mockStorageStats);
  });
});

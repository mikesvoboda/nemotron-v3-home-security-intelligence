import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';


import { useStorageStatsQuery, useCleanupPreviewMutation, useCleanupMutation } from './useStorageStatsQuery';
import * as api from '../services/api';
import { createQueryClient, queryKeys } from '../services/queryClient';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { QueryClient } from '@tanstack/react-query';

// Mock the API module while preserving original exports like isTimeoutError
vi.mock('../services/api', async (importOriginal) => {
  const originalModule = await importOriginal<typeof api>();
  return {
    ...originalModule,
    fetchStorageStats: vi.fn(),
    previewCleanup: vi.fn(),
    triggerCleanup: vi.fn(),
  };
});

describe('useStorageStatsQuery', () => {
  let queryClient: QueryClient;

  const mockStorageStats = {
    disk_usage_percent: 65.5,
    disk_total_bytes: 1000000000000, // 1TB
    disk_used_bytes: 655000000000, // 655GB
    disk_free_bytes: 345000000000, // 345GB
    thumbnails: { count: 50000, bytes: 5000000000 },
    images: { count: 10000, bytes: 100000000000 },
    clips: { count: 1000, bytes: 50000000000 },
    events_count: 5000,
    detections_count: 50000,
    gpu_stats_count: 100000,
    logs_count: 10000,
    timestamp: '2025-12-28T10:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createQueryClient();
    (api.fetchStorageStats as ReturnType<typeof vi.fn>).mockResolvedValue(mockStorageStats);
  });

  afterEach(() => {
    queryClient.clear();
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchStorageStats as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useStorageStatsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchStorageStats as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useStorageStatsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.data).toBeUndefined();
    });

    it('starts with null derived values', () => {
      (api.fetchStorageStats as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useStorageStatsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.diskUsagePercent).toBeNull();
      expect(result.current.diskTotalBytes).toBeNull();
      expect(result.current.diskUsedBytes).toBeNull();
      expect(result.current.diskFreeBytes).toBeNull();
    });
  });

  describe('fetching data', () => {
    it('fetches storage stats on mount', async () => {
      renderHook(() => useStorageStatsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(api.fetchStorageStats).toHaveBeenCalledTimes(1);
      });
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useStorageStatsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockStorageStats);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useStorageStatsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('derives diskUsagePercent correctly', async () => {
      const { result } = renderHook(() => useStorageStatsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.diskUsagePercent).toBe(65.5);
      });
    });

    it('derives diskTotalBytes correctly', async () => {
      const { result } = renderHook(() => useStorageStatsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.diskTotalBytes).toBe(1000000000000);
      });
    });

    it('derives diskUsedBytes correctly', async () => {
      const { result } = renderHook(() => useStorageStatsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.diskUsedBytes).toBe(655000000000);
      });
    });

    it('derives diskFreeBytes correctly', async () => {
      const { result } = renderHook(() => useStorageStatsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.diskFreeBytes).toBe(345000000000);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch storage stats';
      (api.fetchStorageStats as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useStorageStatsQuery(), {
        wrapper: createQueryWrapper(queryClient),
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
      renderHook(() => useStorageStatsQuery({ enabled: false }), {
        wrapper: createQueryWrapper(queryClient),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchStorageStats).not.toHaveBeenCalled();
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useStorageStatsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });
});

describe('useCleanupPreviewMutation', () => {
  let queryClient: QueryClient;

  const mockCleanupPreview = {
    detections_deleted: 100,
    dry_run: true,
    events_deleted: 50,
    gpu_stats_deleted: 1000,
    images_deleted: 80,
    logs_deleted: 500,
    retention_days: 30,
    space_reclaimed: 5000000000, // 5GB
    thumbnails_deleted: 200,
    timestamp: '2025-12-28T10:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createQueryClient();
    (api.previewCleanup as ReturnType<typeof vi.fn>).mockResolvedValue(mockCleanupPreview);
    (api.fetchStorageStats as ReturnType<typeof vi.fn>).mockResolvedValue({});
  });

  afterEach(() => {
    queryClient.clear();
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isPending false', () => {
      const { result } = renderHook(() => useCleanupPreviewMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.isPending).toBe(false);
    });

    it('starts with undefined previewData', () => {
      const { result } = renderHook(() => useCleanupPreviewMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.previewData).toBeUndefined();
    });

    it('starts with null error', () => {
      const { result } = renderHook(() => useCleanupPreviewMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('preview mutation', () => {
    it('calls previewCleanup API', async () => {
      const { result } = renderHook(() => useCleanupPreviewMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.preview();
      });

      expect(api.previewCleanup).toHaveBeenCalledTimes(1);
    });

    it('returns preview data after success', async () => {
      const { result } = renderHook(() => useCleanupPreviewMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      let previewResult: typeof mockCleanupPreview | undefined;
      await act(async () => {
        previewResult = await result.current.preview();
      });

      expect(previewResult).toEqual(mockCleanupPreview);

      await waitFor(() => {
        expect(result.current.previewData).toEqual(mockCleanupPreview);
      });
    });

    it('invalidates storage query after preview', async () => {
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCleanupPreviewMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.preview();
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.system.storage,
      });
    });

    it('sets error on failure', async () => {
      const errorMessage = 'Failed to preview cleanup';
      (api.previewCleanup as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useCleanupPreviewMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await expect(result.current.preview()).rejects.toThrow(errorMessage);
      });

      // Wait for error state to update
      await waitFor(() => {
        expect(result.current.error).toBeInstanceOf(Error);
      });

      expect(result.current.error?.message).toBe(errorMessage);
    });
  });

  describe('reset', () => {
    it('provides reset function', () => {
      const { result } = renderHook(() => useCleanupPreviewMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(typeof result.current.reset).toBe('function');
    });

    it('clears previewData on reset', async () => {
      const { result } = renderHook(() => useCleanupPreviewMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.preview();
      });

      await waitFor(() => {
        expect(result.current.previewData).toEqual(mockCleanupPreview);
      });

      act(() => {
        result.current.reset();
      });

      await waitFor(() => {
        expect(result.current.previewData).toBeUndefined();
      });
    });
  });
});

describe('useCleanupMutation', () => {
  let queryClient: QueryClient;

  const mockCleanupResult = {
    detections_deleted: 100,
    dry_run: false,
    events_deleted: 50,
    gpu_stats_deleted: 1000,
    images_deleted: 80,
    logs_deleted: 500,
    retention_days: 30,
    space_reclaimed: 5000000000, // 5GB
    thumbnails_deleted: 200,
    timestamp: '2025-12-28T10:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createQueryClient();
    (api.triggerCleanup as ReturnType<typeof vi.fn>).mockResolvedValue(mockCleanupResult);
    (api.fetchStorageStats as ReturnType<typeof vi.fn>).mockResolvedValue({});
  });

  afterEach(() => {
    queryClient.clear();
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isPending false', () => {
      const { result } = renderHook(() => useCleanupMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.isPending).toBe(false);
    });

    it('starts with undefined cleanupData', () => {
      const { result } = renderHook(() => useCleanupMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.cleanupData).toBeUndefined();
    });

    it('starts with null error', () => {
      const { result } = renderHook(() => useCleanupMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('cleanup mutation', () => {
    it('calls triggerCleanup API', async () => {
      const { result } = renderHook(() => useCleanupMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.cleanup();
      });

      expect(api.triggerCleanup).toHaveBeenCalledTimes(1);
    });

    it('returns cleanup data after success', async () => {
      const { result } = renderHook(() => useCleanupMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      let cleanupResult: typeof mockCleanupResult | undefined;
      await act(async () => {
        cleanupResult = await result.current.cleanup();
      });

      expect(cleanupResult).toEqual(mockCleanupResult);

      await waitFor(() => {
        expect(result.current.cleanupData).toEqual(mockCleanupResult);
      });
    });

    it('invalidates storage query after cleanup', async () => {
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCleanupMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.cleanup();
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.system.storage,
      });
    });

    it('invalidates system stats query after cleanup', async () => {
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCleanupMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.cleanup();
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.system.stats,
      });
    });

    it('invalidates events query after cleanup', async () => {
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useCleanupMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.cleanup();
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.events.all,
      });
    });

    it('sets error on failure', async () => {
      const errorMessage = 'Failed to run cleanup';
      (api.triggerCleanup as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useCleanupMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await expect(result.current.cleanup()).rejects.toThrow(errorMessage);
      });

      // Wait for error state to update
      await waitFor(() => {
        expect(result.current.error).toBeInstanceOf(Error);
      });

      expect(result.current.error?.message).toBe(errorMessage);
    });
  });

  describe('reset', () => {
    it('provides reset function', () => {
      const { result } = renderHook(() => useCleanupMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(typeof result.current.reset).toBe('function');
    });

    it('clears cleanupData on reset', async () => {
      const { result } = renderHook(() => useCleanupMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.cleanup();
      });

      await waitFor(() => {
        expect(result.current.cleanupData).toEqual(mockCleanupResult);
      });

      act(() => {
        result.current.reset();
      });

      await waitFor(() => {
        expect(result.current.cleanupData).toBeUndefined();
      });
    });
  });
});

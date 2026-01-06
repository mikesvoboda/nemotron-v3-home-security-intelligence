/**
 * useStorageStats hook MSW test example.
 *
 * This test demonstrates using MSW for hook testing with storage API endpoints
 * including cleanup preview functionality.
 *
 * @see src/mocks/handlers.ts - Default API handlers
 * @see src/mocks/server.ts - MSW server configuration
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { http, HttpResponse, delay } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { useStorageStats } from './useStorageStats';
import { server } from '../mocks/server';
import { clearInFlightRequests } from '../services/api';

import type { StorageStatsResponse, CleanupResponse } from '../services/api';

// ============================================================================
// Test Data
// ============================================================================

const mockStorageStats: StorageStatsResponse = {
  disk_used_bytes: 107374182400, // 100 GB
  disk_total_bytes: 536870912000, // 500 GB
  disk_free_bytes: 429496729600, // 400 GB
  disk_usage_percent: 20.0,
  thumbnails: {
    file_count: 1500,
    size_bytes: 75000000, // 75 MB
  },
  images: {
    file_count: 10000,
    size_bytes: 5000000000, // 5 GB
  },
  clips: {
    file_count: 50,
    size_bytes: 500000000, // 500 MB
  },
  events_count: 156,
  detections_count: 892,
  gpu_stats_count: 2880,
  logs_count: 5000,
  timestamp: '2025-12-30T10:30:00Z',
};

const mockCleanupPreview: CleanupResponse = {
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

// ============================================================================
// Tests
// ============================================================================

describe('useStorageStats (MSW)', () => {
  beforeEach(() => {
    clearInFlightRequests();
  });

  it('fetches storage stats on mount', async () => {
    server.use(
      http.get('/api/system/storage', () => {
        return HttpResponse.json(mockStorageStats);
      })
    );

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
    // Use 400 to avoid retry backoff
    server.use(
      http.get('/api/system/storage', () => {
        return HttpResponse.json(
          { detail: 'Network error' },
          { status: 400 }
        );
      })
    );

    const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.stats).toBe(null);
    expect(result.current.error).toBe('Network error');
  });

  it('shows loading state while fetching', () => {
    server.use(
      http.get('/api/system/storage', async () => {
        await delay('infinite');
        return HttpResponse.json(mockStorageStats);
      })
    );

    const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

    expect(result.current.loading).toBe(true);
    expect(result.current.stats).toBe(null);
  });

  it('supports manual refresh', async () => {
    let callCount = 0;
    server.use(
      http.get('/api/system/storage', () => {
        callCount++;
        return HttpResponse.json(mockStorageStats);
      })
    );

    const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

    // Wait for initial fetch
    await waitFor(() => {
      expect(callCount).toBe(1);
    });

    // Trigger manual refresh
    await act(async () => {
      await result.current.refresh();
    });

    expect(callCount).toBe(2);
  });

  describe('cleanup preview', () => {
    it('fetches cleanup preview', async () => {
      server.use(
        http.get('/api/system/storage', () => {
          return HttpResponse.json(mockStorageStats);
        }),
        http.post('/api/system/cleanup', () => {
          return HttpResponse.json(mockCleanupPreview);
        })
      );

      const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Trigger cleanup preview
      let previewResult: CleanupResponse | null = null;
      await act(async () => {
        previewResult = await result.current.previewCleanup();
      });

      expect(previewResult).toEqual(mockCleanupPreview);
      expect(result.current.cleanupPreview).toEqual(mockCleanupPreview);
    });

    it('handles cleanup preview error', async () => {
      server.use(
        http.get('/api/system/storage', () => {
          return HttpResponse.json(mockStorageStats);
        }),
        // Use 400 to avoid retry backoff
        http.post('/api/system/cleanup', () => {
          return HttpResponse.json(
            { detail: 'Cleanup error' },
            { status: 400 }
          );
        })
      );

      const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Trigger cleanup preview which should fail
      let previewResult: CleanupResponse | null = null;
      await act(async () => {
        previewResult = await result.current.previewCleanup();
      });

      expect(previewResult).toBe(null);
      expect(result.current.error).toBe('Cleanup error');
    });

    it('tracks preview loading state', async () => {
      server.use(
        http.get('/api/system/storage', () => {
          return HttpResponse.json(mockStorageStats);
        }),
        http.post('/api/system/cleanup', async () => {
          await delay(100);
          return HttpResponse.json(mockCleanupPreview);
        })
      );

      const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // Start cleanup preview (don't await immediately)
      let previewPromise: Promise<CleanupResponse | null>;
      act(() => {
        previewPromise = result.current.previewCleanup();
      });

      // Check loading state is true
      expect(result.current.previewLoading).toBe(true);

      // Wait for preview to complete
      await act(async () => {
        await previewPromise;
      });

      expect(result.current.previewLoading).toBe(false);
    });
  });

  describe('return values', () => {
    it('returns all expected properties', () => {
      server.use(
        http.get('/api/system/storage', () => {
          return HttpResponse.json(mockStorageStats);
        })
      );

      const { result } = renderHook(() => useStorageStats({ enablePolling: false }));

      expect(result.current).toHaveProperty('stats');
      expect(result.current).toHaveProperty('loading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('refresh');
      expect(result.current).toHaveProperty('previewCleanup');
      expect(result.current).toHaveProperty('previewLoading');
      expect(result.current).toHaveProperty('cleanupPreview');
      expect(typeof result.current.refresh).toBe('function');
      expect(typeof result.current.previewCleanup).toBe('function');
    });
  });
});

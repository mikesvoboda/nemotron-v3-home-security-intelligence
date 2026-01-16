import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useGpuStatsQuery, useGpuHistoryQuery } from './useGpuStatsQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchGPUStats: vi.fn(),
  fetchGpuHistory: vi.fn(),
}));

describe('useGpuStatsQuery', () => {
  const mockGpuStats = {
    utilization: 75,
    memory_used: 8192,
    memory_total: 24576,
    temperature: 65,
    gpu_name: 'NVIDIA RTX A5500',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchGPUStats as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStats);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchGPUStats as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useGpuStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchGPUStats as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useGpuStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
    });

    it('starts with null derived values', () => {
      (api.fetchGPUStats as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useGpuStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.utilization).toBeNull();
      expect(result.current.memoryUsed).toBeNull();
      expect(result.current.temperature).toBeNull();
    });
  });

  describe('fetching data', () => {
    it('fetches GPU stats on mount', async () => {
      renderHook(() => useGpuStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchGPUStats).toHaveBeenCalledTimes(1);
      });
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useGpuStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockGpuStats);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useGpuStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('derives utilization correctly', async () => {
      const { result } = renderHook(() => useGpuStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.utilization).toBe(75);
      });
    });

    it('derives memoryUsed correctly', async () => {
      const { result } = renderHook(() => useGpuStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.memoryUsed).toBe(8192);
      });
    });

    it('derives temperature correctly', async () => {
      const { result } = renderHook(() => useGpuStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.temperature).toBe(65);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch GPU stats';
      (api.fetchGPUStats as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useGpuStatsQuery(), {
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
      renderHook(() => useGpuStatsQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchGPUStats).not.toHaveBeenCalled();
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useGpuStatsQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });
});

describe('useGpuHistoryQuery', () => {
  // NEM-2178: Updated to use standard pagination envelope format
  const mockGpuHistory = {
    items: [
      {
        recorded_at: '2025-12-28T10:00:00Z',
        utilization: 70,
        memory_used: 8000,
        temperature: 60,
      },
      {
        recorded_at: '2025-12-28T10:00:05Z',
        utilization: 75,
        memory_used: 8192,
        temperature: 65,
      },
    ],
    pagination: {
      total: 2,
      limit: 60,
      offset: 0,
      has_more: false,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchGpuHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuHistory);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with empty history array', () => {
      (api.fetchGpuHistory as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useGpuHistoryQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.history).toEqual([]);
    });
  });

  describe('fetching data', () => {
    it('fetches GPU history on mount', async () => {
      renderHook(() => useGpuHistoryQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchGpuHistory).toHaveBeenCalledTimes(1);
      });
    });

    it('fetches with default limit of 60', async () => {
      renderHook(() => useGpuHistoryQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchGpuHistory).toHaveBeenCalledWith(60);
      });
    });

    it('fetches with custom limit', async () => {
      renderHook(() => useGpuHistoryQuery({ limit: 100 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchGpuHistory).toHaveBeenCalledWith(100);
      });
    });

    it('updates history after successful fetch', async () => {
      const { result } = renderHook(() => useGpuHistoryQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        // NEM-2178: 'history' is derived from 'items' in the pagination envelope
        expect(result.current.history).toEqual(mockGpuHistory.items);
      });
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useGpuHistoryQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockGpuHistory);
      });
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useGpuHistoryQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchGpuHistory).not.toHaveBeenCalled();
    });
  });
});

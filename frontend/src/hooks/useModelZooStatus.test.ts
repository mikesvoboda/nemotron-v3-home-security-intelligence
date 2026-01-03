import { renderHook, waitFor, act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest';

import { useModelZooStatus } from './useModelZooStatus';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api');

describe('useModelZooStatus', () => {
  const mockModelRegistry: api.ModelRegistryResponse = {
    vram_budget_mb: 1650,
    vram_used_mb: 450,
    vram_available_mb: 1200,
    models: [
      {
        name: 'clip_embedder',
        display_name: 'CLIP ViT-L/14',
        vram_mb: 400,
        status: 'loaded',
        category: 'embedding',
        enabled: true,
        available: true,
        path: '/models/clip-vit-l-14',
        load_count: 1547,
      },
      {
        name: 'yolo11-face',
        display_name: 'YOLO11 Face',
        vram_mb: 150,
        status: 'unloaded',
        category: 'detection',
        enabled: true,
        available: false,
        path: '/models/yolo11-face',
        load_count: 0,
      },
      {
        name: 'fashion-clip',
        display_name: 'FashionCLIP',
        vram_mb: 200,
        status: 'unloaded',
        category: 'embedding',
        enabled: true,
        available: false,
        path: '/models/fashion-clip',
        load_count: 0,
      },
      {
        name: 'vitpose-small',
        display_name: 'ViTPose Small',
        vram_mb: 180,
        status: 'disabled',
        category: 'pose',
        enabled: false,
        available: false,
        path: '/models/vitpose-small',
        load_count: 0,
      },
    ],
    loading_strategy: 'sequential',
    max_concurrent_models: 1,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('initial fetch', () => {
    it('fetches model zoo status on mount', async () => {
      vi.mocked(api.fetchModelZooStatus).mockResolvedValue(mockModelRegistry);

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      expect(result.current.isLoading).toBe(true);
      expect(result.current.models).toEqual([]);
      expect(result.current.vramStats).toBe(null);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.models).toEqual(mockModelRegistry.models);
      expect(result.current.vramStats).toEqual({
        budget_mb: 1650,
        used_mb: 450,
        available_mb: 1200,
        usage_percent: expect.closeTo(27.27, 1),
      });
      expect(result.current.error).toBe(null);
    });

    it('handles fetch error gracefully', async () => {
      vi.mocked(api.fetchModelZooStatus).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.models).toEqual([]);
      expect(result.current.vramStats).toBe(null);
      expect(result.current.error).toBe('Network error');
    });

    it('handles non-Error rejection', async () => {
      vi.mocked(api.fetchModelZooStatus).mockRejectedValue('Unknown error');

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBe('Failed to fetch Model Zoo status');
    });
  });

  describe('polling', () => {
    it('polls at the specified interval when enabled', async () => {
      vi.mocked(api.fetchModelZooStatus).mockResolvedValue(mockModelRegistry);

      renderHook(() => useModelZooStatus({ pollingInterval: 10000 }));

      await waitFor(() => {
        expect(api.fetchModelZooStatus).toHaveBeenCalledTimes(1);
      });

      // Advance timer by 10 seconds
      act(() => {
        vi.advanceTimersByTime(10000);
      });

      await waitFor(() => {
        expect(api.fetchModelZooStatus).toHaveBeenCalledTimes(2);
      });

      // Advance timer by another 10 seconds
      act(() => {
        vi.advanceTimersByTime(10000);
      });

      await waitFor(() => {
        expect(api.fetchModelZooStatus).toHaveBeenCalledTimes(3);
      });
    });

    it('does not poll when pollingInterval is 0', async () => {
      vi.mocked(api.fetchModelZooStatus).mockResolvedValue(mockModelRegistry);

      renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(api.fetchModelZooStatus).toHaveBeenCalledTimes(1);
      });

      // Advance timer
      act(() => {
        vi.advanceTimersByTime(30000);
      });

      // Should still only have 1 call
      expect(api.fetchModelZooStatus).toHaveBeenCalledTimes(1);
    });

    it('stops polling on unmount', async () => {
      vi.mocked(api.fetchModelZooStatus).mockResolvedValue(mockModelRegistry);

      const { unmount } = renderHook(() => useModelZooStatus({ pollingInterval: 10000 }));

      await waitFor(() => {
        expect(api.fetchModelZooStatus).toHaveBeenCalledTimes(1);
      });

      unmount();

      act(() => {
        vi.advanceTimersByTime(30000);
      });

      // Should still only have 1 call
      expect(api.fetchModelZooStatus).toHaveBeenCalledTimes(1);
    });
  });

  describe('refresh', () => {
    it('provides a refresh function', async () => {
      vi.mocked(api.fetchModelZooStatus).mockResolvedValue(mockModelRegistry);

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchModelZooStatus).toHaveBeenCalledTimes(1);

      await act(async () => {
        await result.current.refresh();
      });

      expect(api.fetchModelZooStatus).toHaveBeenCalledTimes(2);
    });

    it('sets loading state during refresh', async () => {
      vi.mocked(api.fetchModelZooStatus).mockResolvedValue(mockModelRegistry);

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      let refreshPromise: Promise<void>;
      act(() => {
        refreshPromise = result.current.refresh();
      });

      expect(result.current.isLoading).toBe(true);

      await act(async () => {
        await refreshPromise;
      });

      expect(result.current.isLoading).toBe(false);
    });

    it('clears error on successful refresh', async () => {
      vi.mocked(api.fetchModelZooStatus).mockRejectedValueOnce(new Error('Network error'));
      vi.mocked(api.fetchModelZooStatus).mockResolvedValueOnce(mockModelRegistry);

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.error).toBe('Network error');
      });

      await act(async () => {
        await result.current.refresh();
      });

      expect(result.current.error).toBe(null);
      expect(result.current.models).toEqual(mockModelRegistry.models);
    });
  });

  describe('VRAM stats calculation', () => {
    it('calculates usage percentage correctly', async () => {
      const halfUsedRegistry = {
        ...mockModelRegistry,
        vram_budget_mb: 1000,
        vram_used_mb: 500,
        vram_available_mb: 500,
      };
      vi.mocked(api.fetchModelZooStatus).mockResolvedValue(halfUsedRegistry);

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.vramStats?.usage_percent).toBeCloseTo(50, 1);
    });

    it('handles zero budget gracefully', async () => {
      const zeroBudgetRegistry = {
        ...mockModelRegistry,
        vram_budget_mb: 0,
        vram_used_mb: 0,
        vram_available_mb: 0,
      };
      vi.mocked(api.fetchModelZooStatus).mockResolvedValue(zeroBudgetRegistry);

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.vramStats?.usage_percent).toBe(0);
    });
  });

  describe('model filtering helpers', () => {
    it('returns correct loaded model count', async () => {
      vi.mocked(api.fetchModelZooStatus).mockResolvedValue(mockModelRegistry);

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const loadedModels = result.current.models.filter((m) => m.status === 'loaded');
      expect(loadedModels).toHaveLength(1);
      expect(loadedModels[0].name).toBe('clip_embedder');
    });

    it('returns models grouped by category', async () => {
      vi.mocked(api.fetchModelZooStatus).mockResolvedValue(mockModelRegistry);

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const embeddingModels = result.current.models.filter((m) => m.category === 'embedding');
      expect(embeddingModels).toHaveLength(2);
    });
  });

  describe('default options', () => {
    it('uses default polling interval of 10 seconds', async () => {
      vi.mocked(api.fetchModelZooStatus).mockResolvedValue(mockModelRegistry);

      renderHook(() => useModelZooStatus());

      await waitFor(() => {
        expect(api.fetchModelZooStatus).toHaveBeenCalledTimes(1);
      });

      // Advance by 5 seconds - should not poll yet
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      expect(api.fetchModelZooStatus).toHaveBeenCalledTimes(1);

      // Advance by another 5 seconds (total 10 seconds) - should poll
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      await waitFor(() => {
        expect(api.fetchModelZooStatus).toHaveBeenCalledTimes(2);
      });
    });
  });
});

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useModelZooStatusQuery } from './useModelZooStatusQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchModelZooStatus: vi.fn(),
}));

describe('useModelZooStatusQuery', () => {
  const mockModelRegistry = {
    models: [
      {
        name: 'rtdetr',
        display_name: 'RT-DETR',
        status: 'loaded',
        vram_mb: 2048,
        load_time_seconds: 1.5,
      },
      {
        name: 'nemotron',
        display_name: 'Nemotron',
        status: 'loaded',
        vram_mb: 8192,
        load_time_seconds: 5.0,
      },
    ],
    vram_budget_mb: 24576,
    vram_used_mb: 10240,
    vram_available_mb: 14336,
    total_models: 2,
    loaded_models: 2,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchModelZooStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockModelRegistry);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchModelZooStatus as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useModelZooStatusQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with empty models array', () => {
      (api.fetchModelZooStatus as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useModelZooStatusQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.models).toEqual([]);
    });

    it('starts with null vramStats', () => {
      (api.fetchModelZooStatus as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useModelZooStatusQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.vramStats).toBeNull();
    });
  });

  describe('fetching data', () => {
    it('fetches model zoo status on mount', async () => {
      renderHook(() => useModelZooStatusQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchModelZooStatus).toHaveBeenCalledTimes(1);
      });
    });

    it('updates models after successful fetch', async () => {
      const { result } = renderHook(() => useModelZooStatusQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.models).toEqual(mockModelRegistry.models);
      });
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useModelZooStatusQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockModelRegistry);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useModelZooStatusQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('calculates vramStats correctly', async () => {
      const { result } = renderHook(() => useModelZooStatusQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.vramStats).toEqual({
          budgetMb: 24576,
          usedMb: 10240,
          availableMb: 14336,
          usagePercent: (10240 / 24576) * 100,
        });
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch model zoo status';
      (api.fetchModelZooStatus as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useModelZooStatusQuery(), {
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
      renderHook(() => useModelZooStatusQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchModelZooStatus).not.toHaveBeenCalled();
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useModelZooStatusQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });

  describe('vramStats edge cases', () => {
    it('handles zero budget gracefully', async () => {
      (api.fetchModelZooStatus as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockModelRegistry,
        vram_budget_mb: 0,
        vram_used_mb: 0,
        vram_available_mb: 0,
      });

      const { result } = renderHook(() => useModelZooStatusQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.vramStats?.usagePercent).toBe(0);
      });
    });
  });
});

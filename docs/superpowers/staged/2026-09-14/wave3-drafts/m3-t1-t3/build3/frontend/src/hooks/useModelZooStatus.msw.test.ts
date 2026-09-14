/**
 * useModelZooStatus hook MSW test example.
 *
 * This test demonstrates using MSW for hook testing with more complex
 * response data (model registry with VRAM stats).
 *
 * @see src/mocks/handlers.ts - Default API handlers
 * @see src/mocks/server.ts - MSW server configuration
 */

import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse, delay } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import { useModelZooStatus } from './useModelZooStatus';
import { server } from '../mocks/server';
import { clearInFlightRequests } from '../services/api';

import type { ModelRegistryResponse } from '../services/api';

// ============================================================================
// Test Data
// ============================================================================

const mockModelRegistry: ModelRegistryResponse = {
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

// ============================================================================
// Tests
// ============================================================================

describe('useModelZooStatus (MSW)', () => {
  beforeEach(() => {
    clearInFlightRequests();
  });

  describe('initial fetch', () => {
    it('fetches model zoo status on mount', async () => {
      server.use(
        http.get('/api/system/models', () => {
          return HttpResponse.json(mockModelRegistry);
        })
      );

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
      // Use 400 to avoid retry backoff
      server.use(
        http.get('/api/system/models', () => {
          return HttpResponse.json({ detail: 'Network error' }, { status: 400 });
        })
      );

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBe('Network error');
      expect(result.current.models).toEqual([]);
    });

    it('shows loading state while fetching', () => {
      // Use 60s delay instead of 'infinite' to prevent cleanup hangs
      // The test completes before the delay resolves, but cleanup can finish
      server.use(
        http.get('/api/system/models', async () => {
          await delay(60000);
          return HttpResponse.json(mockModelRegistry);
        })
      );

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      expect(result.current.isLoading).toBe(true);
    });
  });

  describe('model counts', () => {
    it('provides models array for computing loaded count', async () => {
      server.use(
        http.get('/api/system/models', () => {
          return HttpResponse.json(mockModelRegistry);
        })
      );

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Users can compute loaded count from models array
      const loadedCount = result.current.models.filter((m) => m.status === 'loaded').length;
      expect(loadedCount).toBe(1); // Only clip_embedder is loaded
    });

    it('provides models array for computing total count', async () => {
      server.use(
        http.get('/api/system/models', () => {
          return HttpResponse.json(mockModelRegistry);
        })
      );

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.models.length).toBe(4);
    });
  });

  describe('model filtering', () => {
    it('provides method to filter models by category', async () => {
      server.use(
        http.get('/api/system/models', () => {
          return HttpResponse.json(mockModelRegistry);
        })
      );

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const embeddingModels = result.current.models.filter((m) => m.category === 'embedding');
      expect(embeddingModels).toHaveLength(2);
      expect(embeddingModels.map((m) => m.name)).toContain('clip_embedder');
      expect(embeddingModels.map((m) => m.name)).toContain('fashion-clip');
    });

    it('provides method to filter models by status', async () => {
      server.use(
        http.get('/api/system/models', () => {
          return HttpResponse.json(mockModelRegistry);
        })
      );

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      const loadedModels = result.current.models.filter((m) => m.status === 'loaded');
      expect(loadedModels).toHaveLength(1);
      expect(loadedModels[0].name).toBe('clip_embedder');
    });
  });

  describe('vram stats', () => {
    it('calculates VRAM usage percentage', async () => {
      server.use(
        http.get('/api/system/models', () => {
          return HttpResponse.json(mockModelRegistry);
        })
      );

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 450 / 1650 * 100 = 27.27%
      expect(result.current.vramStats?.usage_percent).toBeCloseTo(27.27, 1);
    });

    it('handles zero VRAM budget', async () => {
      const zeroBudgetResponse: ModelRegistryResponse = {
        ...mockModelRegistry,
        vram_budget_mb: 0,
        vram_used_mb: 0,
        vram_available_mb: 0,
      };

      server.use(
        http.get('/api/system/models', () => {
          return HttpResponse.json(zeroBudgetResponse);
        })
      );

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Should handle division by zero gracefully
      expect(result.current.vramStats?.usage_percent).toBe(0);
    });
  });

  describe('return values', () => {
    it('returns all expected properties', () => {
      server.use(
        http.get('/api/system/models', () => {
          return HttpResponse.json(mockModelRegistry);
        })
      );

      const { result } = renderHook(() => useModelZooStatus({ pollingInterval: 0 }));

      expect(result.current).toHaveProperty('models');
      expect(result.current).toHaveProperty('vramStats');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('refresh');
      expect(typeof result.current.refresh).toBe('function');
    });
  });
});

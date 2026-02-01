/**
 * Unit tests for useModelZoo hooks
 *
 * Tests all TanStack Query hooks for Model Zoo management with comprehensive
 * coverage of queries, mutations, cache invalidation, and error handling.
 *
 * TDD RED PHASE: These tests will fail until the hooks are fully implemented.
 *
 * @see NEM-4788
 * @see docs/plans/2025-01-31-model-zoo-management-design.md
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useModels,
  useVRAMSummary,
  useLoadModel,
  useUnloadModel,
  useReloadModel,
  useUnloadAllModels,
  MODEL_ZOO_QUERY_KEYS,
} from './useModelZoo';
import * as modelZooApi from '../services/modelZooApi';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type {
  ModelListResponse,
  VRAMSummaryResponse,
  LoadModelResponse,
  UnloadModelResponse,
  UnloadAllResponse,
  ModelStatus,
  GpuVRAMInfo,
} from '../services/modelZooApi';

// Mock the modelZooApi module
vi.mock('../services/modelZooApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/modelZooApi')>();
  return {
    ...actual,
    listModels: vi.fn(),
    getVRAMSummary: vi.fn(),
    loadModel: vi.fn(),
    unloadModel: vi.fn(),
    reloadModel: vi.fn(),
    unloadAllModels: vi.fn(),
  };
});

// ============================================================================
// Mock Data
// ============================================================================

const mockModelLoaded: ModelStatus = {
  name: 'threat-detection-yolov8n',
  category: 'detection',
  estimated_vram_mb: 300,
  enabled: true,
  service: 'ai-enrichment-light',
  gpu_id: 1,
  runtime: {
    loaded: true,
    actual_vram_mb: 287,
    last_used: '2026-01-31T10:30:00Z',
    load_count: 5,
  },
};

const mockModelUnloaded: ModelStatus = {
  name: 'vehicle-segment-classification',
  category: 'classification',
  estimated_vram_mb: 1500,
  enabled: true,
  service: 'ai-enrichment',
  gpu_id: 0,
  runtime: {
    loaded: false,
    actual_vram_mb: null,
    last_used: null,
    load_count: 0,
  },
};

const mockModelListResponse: ModelListResponse = {
  models: [mockModelLoaded, mockModelUnloaded],
  service_status: {
    'ai-enrichment': 'healthy',
    'ai-enrichment-light': 'healthy',
  },
};

const mockGpuVRAMInfo0: GpuVRAMInfo = {
  gpu_id: 0,
  service: 'ai-enrichment',
  budget_mb: 6800,
  used_mb: 2100,
  available_mb: 4700,
  utilization_percent: 30.9,
  loaded_models: ['fashion-clip', 'vehicle-segment-classification'],
};

const mockGpuVRAMInfo1: GpuVRAMInfo = {
  gpu_id: 1,
  service: 'ai-enrichment-light',
  budget_mb: 1200,
  used_mb: 450,
  available_mb: 750,
  utilization_percent: 37.5,
  loaded_models: ['threat-detection-yolov8n'],
};

const mockVRAMSummaryResponse: VRAMSummaryResponse = {
  gpus: [mockGpuVRAMInfo0, mockGpuVRAMInfo1],
  totals: {
    budget_mb: 8000,
    used_mb: 2550,
    available_mb: 5450,
    model_count: 3,
  },
};

const mockLoadModelResponse: LoadModelResponse = {
  success: true,
  model_name: 'threat-detection-yolov8n',
  service: 'ai-enrichment-light',
  gpu_id: 1,
  load_time_ms: 1250,
  vram_mb: 287,
};

const mockUnloadModelResponse: UnloadModelResponse = {
  success: true,
  model_name: 'threat-detection-yolov8n',
  freed_vram_mb: 287,
};

const mockUnloadAllResponse: UnloadAllResponse = {
  success: true,
  unloaded_count: 3,
  total_freed_vram_mb: 2550,
  errors: [],
};

// ============================================================================
// Query Keys Tests
// ============================================================================

describe('MODEL_ZOO_QUERY_KEYS', () => {
  it('has correct base key for all model zoo queries', () => {
    expect(MODEL_ZOO_QUERY_KEYS.all).toEqual(['system', 'models']);
  });

  it('has correct key for models list', () => {
    expect(MODEL_ZOO_QUERY_KEYS.models).toEqual(['system', 'models', 'list']);
  });

  it('has correct key for VRAM summary', () => {
    expect(MODEL_ZOO_QUERY_KEYS.vramSummary).toEqual(['system', 'models', 'vram-summary']);
  });

  it('creates correct key for individual model', () => {
    expect(MODEL_ZOO_QUERY_KEYS.model('threat-detection-yolov8n')).toEqual([
      'system',
      'models',
      'detail',
      'threat-detection-yolov8n',
    ]);
  });

  it('creates unique model keys for different models', () => {
    const key1 = MODEL_ZOO_QUERY_KEYS.model('model-a');
    const key2 = MODEL_ZOO_QUERY_KEYS.model('model-b');
    expect(key1).not.toEqual(key2);
  });
});

// ============================================================================
// useModels Tests
// ============================================================================

describe('useModels', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches and returns model list', async () => {
    vi.mocked(modelZooApi.listModels).mockResolvedValueOnce(mockModelListResponse);

    const { result } = renderHook(() => useModels(), {
      wrapper: createQueryWrapper(),
    });

    // Initially loading
    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.models).toHaveLength(2);
    expect(result.current.data).toEqual(mockModelListResponse);
    expect(modelZooApi.listModels).toHaveBeenCalledOnce();
  });

  it('returns empty array when no data', () => {
    vi.mocked(modelZooApi.listModels).mockResolvedValueOnce(mockModelListResponse);

    const { result } = renderHook(() => useModels(), {
      wrapper: createQueryWrapper(),
    });

    // Before data loads, models should be empty array
    expect(result.current.models).toEqual([]);
  });

  it('returns service status', async () => {
    vi.mocked(modelZooApi.listModels).mockResolvedValueOnce(mockModelListResponse);

    const { result } = renderHook(() => useModels(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.serviceStatus['ai-enrichment']).toBe('healthy');
    expect(result.current.serviceStatus['ai-enrichment-light']).toBe('healthy');
  });

  it('handles errors gracefully', async () => {
    const error = new Error('Failed to fetch models');
    // Reject both initial call and retry
    vi.mocked(modelZooApi.listModels).mockRejectedValue(error);

    const { result } = renderHook(() => useModels(), {
      wrapper: createQueryWrapper(),
    });

    // Wait for error state with longer timeout to account for retry
    await waitFor(
      () => {
        expect(result.current.error).toBeTruthy();
      },
      { timeout: 5000 }
    );

    expect(result.current.isLoading).toBe(false);
  });

  it('does not fetch when disabled', () => {
    vi.mocked(modelZooApi.listModels).mockResolvedValueOnce(mockModelListResponse);

    const { result } = renderHook(() => useModels({ enabled: false }), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(modelZooApi.listModels).not.toHaveBeenCalled();
  });

  it('provides refetch function', async () => {
    vi.mocked(modelZooApi.listModels).mockResolvedValue(mockModelListResponse);

    const { result } = renderHook(() => useModels(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Call refetch
    await act(async () => {
      await result.current.refetch();
    });

    expect(modelZooApi.listModels).toHaveBeenCalledTimes(2);
  });

  it('tracks isRefetching state', async () => {
    vi.mocked(modelZooApi.listModels).mockResolvedValue(mockModelListResponse);

    const { result } = renderHook(() => useModels(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isRefetching).toBe(false);
  });
});

// ============================================================================
// useVRAMSummary Tests
// ============================================================================

describe('useVRAMSummary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches VRAM data', async () => {
    vi.mocked(modelZooApi.getVRAMSummary).mockResolvedValueOnce(mockVRAMSummaryResponse);

    const { result } = renderHook(() => useVRAMSummary(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.gpus).toHaveLength(2);
    expect(result.current.data?.totals.used_mb).toBe(2550);
    expect(modelZooApi.getVRAMSummary).toHaveBeenCalledOnce();
  });

  it('returns empty array when no data', () => {
    vi.mocked(modelZooApi.getVRAMSummary).mockResolvedValueOnce(mockVRAMSummaryResponse);

    const { result } = renderHook(() => useVRAMSummary(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.gpus).toEqual([]);
  });

  it('handles errors gracefully', async () => {
    const error = new Error('Failed to get VRAM summary');
    vi.mocked(modelZooApi.getVRAMSummary).mockRejectedValue(error);

    const { result } = renderHook(() => useVRAMSummary(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(
      () => {
        expect(result.current.error).toBeTruthy();
      },
      { timeout: 5000 }
    );

    expect(result.current.isLoading).toBe(false);
  });

  it('does not fetch when disabled', () => {
    vi.mocked(modelZooApi.getVRAMSummary).mockResolvedValueOnce(mockVRAMSummaryResponse);

    const { result } = renderHook(() => useVRAMSummary({ enabled: false }), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(modelZooApi.getVRAMSummary).not.toHaveBeenCalled();
  });

  it('provides refetch function', async () => {
    vi.mocked(modelZooApi.getVRAMSummary).mockResolvedValue(mockVRAMSummaryResponse);

    const { result } = renderHook(() => useVRAMSummary(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.refetch();
    });

    expect(modelZooApi.getVRAMSummary).toHaveBeenCalledTimes(2);
  });
});

// ============================================================================
// useLoadModel Tests
// ============================================================================

describe('useLoadModel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('mutation invalidates queries on success', async () => {
    vi.mocked(modelZooApi.loadModel).mockResolvedValueOnce(mockLoadModelResponse);
    vi.mocked(modelZooApi.listModels).mockResolvedValue(mockModelListResponse);

    const { result } = renderHook(
      () => ({
        loadMutation: useLoadModel(),
        models: useModels(),
      }),
      { wrapper: createQueryWrapper() }
    );

    // Wait for initial models fetch
    await waitFor(() => {
      expect(result.current.models.isLoading).toBe(false);
    });

    const initialCallCount = vi.mocked(modelZooApi.listModels).mock.calls.length;

    // Load a model
    await act(async () => {
      await result.current.loadMutation.loadModel('threat-detection-yolov8n');
    });

    // Models should be refetched due to invalidation
    await waitFor(() => {
      expect(vi.mocked(modelZooApi.listModels).mock.calls.length).toBeGreaterThan(initialCallCount);
    });
  });

  it('returns load result with timing info', async () => {
    vi.mocked(modelZooApi.loadModel).mockResolvedValueOnce(mockLoadModelResponse);

    const { result } = renderHook(() => useLoadModel(), {
      wrapper: createQueryWrapper(),
    });

    let loadResult: LoadModelResponse | undefined;
    await act(async () => {
      loadResult = await result.current.loadModel('threat-detection-yolov8n');
    });

    expect(loadResult?.success).toBe(true);
    expect(loadResult?.load_time_ms).toBe(1250);
    expect(loadResult?.vram_mb).toBe(287);
  });

  it('handles load errors', async () => {
    const error = new Error('Failed to load model');
    vi.mocked(modelZooApi.loadModel).mockRejectedValueOnce(error);

    const { result } = renderHook(() => useLoadModel(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      try {
        await result.current.loadModel('unknown-model');
      } catch {
        // Expected error
      }
    });

    await waitFor(() => {
      expect(result.current.mutation.isError).toBe(true);
    });

    expect(result.current.error).toBeTruthy();
  });

  it('tracks isLoading state during load', async () => {
    // Use a deferred promise to control when the mock resolves
    let resolveLoad: (value: LoadModelResponse) => void;
    const mockPromise = new Promise<LoadModelResponse>((resolve) => {
      resolveLoad = resolve;
    });
    vi.mocked(modelZooApi.loadModel).mockReturnValueOnce(mockPromise);

    const { result } = renderHook(() => useLoadModel(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);

    // Start the load but don't await yet
    let loadPromise: Promise<LoadModelResponse>;
    act(() => {
      loadPromise = result.current.loadModel('threat-detection-yolov8n');
    });

    // Now isLoading should be true while waiting
    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    // Resolve the promise
    await act(async () => {
      resolveLoad!(mockLoadModelResponse);
      await loadPromise!;
    });

    // Now isLoading should be false after resolution
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });
});

// ============================================================================
// useUnloadModel Tests
// ============================================================================

describe('useUnloadModel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('mutation invalidates queries on success', async () => {
    vi.mocked(modelZooApi.unloadModel).mockResolvedValueOnce(mockUnloadModelResponse);
    vi.mocked(modelZooApi.listModels).mockResolvedValue(mockModelListResponse);

    const { result } = renderHook(
      () => ({
        unloadMutation: useUnloadModel(),
        models: useModels(),
      }),
      { wrapper: createQueryWrapper() }
    );

    // Wait for initial models fetch
    await waitFor(() => {
      expect(result.current.models.isLoading).toBe(false);
    });

    const initialCallCount = vi.mocked(modelZooApi.listModels).mock.calls.length;

    // Unload a model
    await act(async () => {
      await result.current.unloadMutation.unloadModel('threat-detection-yolov8n');
    });

    // Models should be refetched due to invalidation
    await waitFor(() => {
      expect(vi.mocked(modelZooApi.listModels).mock.calls.length).toBeGreaterThan(initialCallCount);
    });
  });

  it('returns unload result with freed VRAM', async () => {
    vi.mocked(modelZooApi.unloadModel).mockResolvedValueOnce(mockUnloadModelResponse);

    const { result } = renderHook(() => useUnloadModel(), {
      wrapper: createQueryWrapper(),
    });

    let unloadResult: UnloadModelResponse | undefined;
    await act(async () => {
      unloadResult = await result.current.unloadModel('threat-detection-yolov8n');
    });

    expect(unloadResult?.success).toBe(true);
    expect(unloadResult?.freed_vram_mb).toBe(287);
  });

  it('handles unload errors', async () => {
    const error = new Error('Failed to unload model');
    vi.mocked(modelZooApi.unloadModel).mockRejectedValueOnce(error);

    const { result } = renderHook(() => useUnloadModel(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      try {
        await result.current.unloadModel('unknown-model');
      } catch {
        // Expected error
      }
    });

    await waitFor(() => {
      expect(result.current.mutation.isError).toBe(true);
    });

    expect(result.current.error).toBeTruthy();
  });

  it('tracks isLoading state during unload', async () => {
    let resolveUnload: (value: UnloadModelResponse) => void;
    const mockPromise = new Promise<UnloadModelResponse>((resolve) => {
      resolveUnload = resolve;
    });
    vi.mocked(modelZooApi.unloadModel).mockReturnValueOnce(mockPromise);

    const { result } = renderHook(() => useUnloadModel(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);

    let unloadPromise: Promise<UnloadModelResponse>;
    act(() => {
      unloadPromise = result.current.unloadModel('threat-detection-yolov8n');
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    await act(async () => {
      resolveUnload!(mockUnloadModelResponse);
      await unloadPromise!;
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });
});

// ============================================================================
// useReloadModel Tests
// ============================================================================

describe('useReloadModel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('mutation invalidates queries on success', async () => {
    vi.mocked(modelZooApi.reloadModel).mockResolvedValueOnce(mockLoadModelResponse);
    vi.mocked(modelZooApi.listModels).mockResolvedValue(mockModelListResponse);

    const { result } = renderHook(
      () => ({
        reloadMutation: useReloadModel(),
        models: useModels(),
      }),
      { wrapper: createQueryWrapper() }
    );

    await waitFor(() => {
      expect(result.current.models.isLoading).toBe(false);
    });

    const initialCallCount = vi.mocked(modelZooApi.listModels).mock.calls.length;

    await act(async () => {
      await result.current.reloadMutation.reloadModel('threat-detection-yolov8n');
    });

    await waitFor(() => {
      expect(vi.mocked(modelZooApi.listModels).mock.calls.length).toBeGreaterThan(initialCallCount);
    });
  });

  it('returns reload result', async () => {
    vi.mocked(modelZooApi.reloadModel).mockResolvedValueOnce(mockLoadModelResponse);

    const { result } = renderHook(() => useReloadModel(), {
      wrapper: createQueryWrapper(),
    });

    let reloadResult: LoadModelResponse | undefined;
    await act(async () => {
      reloadResult = await result.current.reloadModel('threat-detection-yolov8n');
    });

    expect(reloadResult?.success).toBe(true);
    expect(reloadResult?.load_time_ms).toBe(1250);
  });
});

// ============================================================================
// useUnloadAllModels Tests
// ============================================================================

describe('useUnloadAllModels', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('mutation invalidates queries on success', async () => {
    vi.mocked(modelZooApi.unloadAllModels).mockResolvedValueOnce(mockUnloadAllResponse);
    vi.mocked(modelZooApi.listModels).mockResolvedValue(mockModelListResponse);

    const { result } = renderHook(
      () => ({
        unloadAllMutation: useUnloadAllModels(),
        models: useModels(),
      }),
      { wrapper: createQueryWrapper() }
    );

    await waitFor(() => {
      expect(result.current.models.isLoading).toBe(false);
    });

    const initialCallCount = vi.mocked(modelZooApi.listModels).mock.calls.length;

    await act(async () => {
      await result.current.unloadAllMutation.unloadAll();
    });

    await waitFor(() => {
      expect(vi.mocked(modelZooApi.listModels).mock.calls.length).toBeGreaterThan(initialCallCount);
    });
  });

  it('returns unload all result', async () => {
    vi.mocked(modelZooApi.unloadAllModels).mockResolvedValueOnce(mockUnloadAllResponse);

    const { result } = renderHook(() => useUnloadAllModels(), {
      wrapper: createQueryWrapper(),
    });

    let unloadAllResult: UnloadAllResponse | undefined;
    await act(async () => {
      unloadAllResult = await result.current.unloadAll();
    });

    expect(unloadAllResult?.success).toBe(true);
    expect(unloadAllResult?.unloaded_count).toBe(3);
    expect(unloadAllResult?.total_freed_vram_mb).toBe(2550);
  });

  it('handles partial failure', async () => {
    const partialResponse: UnloadAllResponse = {
      success: false,
      unloaded_count: 2,
      total_freed_vram_mb: 1500,
      errors: ['Model threat-detection in use'],
    };
    vi.mocked(modelZooApi.unloadAllModels).mockResolvedValueOnce(partialResponse);

    const { result } = renderHook(() => useUnloadAllModels(), {
      wrapper: createQueryWrapper(),
    });

    let unloadAllResult: UnloadAllResponse | undefined;
    await act(async () => {
      unloadAllResult = await result.current.unloadAll();
    });

    expect(unloadAllResult?.success).toBe(false);
    expect(unloadAllResult?.errors).toHaveLength(1);
  });
});

// ============================================================================
// Cache Invalidation Tests
// ============================================================================

describe('Cache Invalidation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('useLoadModel invalidates both models and VRAM summary', async () => {
    vi.mocked(modelZooApi.loadModel).mockResolvedValueOnce(mockLoadModelResponse);
    vi.mocked(modelZooApi.listModels).mockResolvedValue(mockModelListResponse);
    vi.mocked(modelZooApi.getVRAMSummary).mockResolvedValue(mockVRAMSummaryResponse);

    const { result } = renderHook(
      () => ({
        loadMutation: useLoadModel(),
        models: useModels(),
        vram: useVRAMSummary(),
      }),
      { wrapper: createQueryWrapper() }
    );

    // Wait for initial fetches
    await waitFor(() => {
      expect(result.current.models.isLoading).toBe(false);
      expect(result.current.vram.isLoading).toBe(false);
    });

    const modelsCallCount = vi.mocked(modelZooApi.listModels).mock.calls.length;
    const vramCallCount = vi.mocked(modelZooApi.getVRAMSummary).mock.calls.length;

    // Load a model
    await act(async () => {
      await result.current.loadMutation.loadModel('threat-detection-yolov8n');
    });

    // Both should be refetched due to invalidation
    await waitFor(() => {
      expect(vi.mocked(modelZooApi.listModels).mock.calls.length).toBeGreaterThan(modelsCallCount);
      expect(vi.mocked(modelZooApi.getVRAMSummary).mock.calls.length).toBeGreaterThan(
        vramCallCount
      );
    });
  });

  it('useUnloadModel invalidates both models and VRAM summary', async () => {
    vi.mocked(modelZooApi.unloadModel).mockResolvedValueOnce(mockUnloadModelResponse);
    vi.mocked(modelZooApi.listModels).mockResolvedValue(mockModelListResponse);
    vi.mocked(modelZooApi.getVRAMSummary).mockResolvedValue(mockVRAMSummaryResponse);

    const { result } = renderHook(
      () => ({
        unloadMutation: useUnloadModel(),
        models: useModels(),
        vram: useVRAMSummary(),
      }),
      { wrapper: createQueryWrapper() }
    );

    await waitFor(() => {
      expect(result.current.models.isLoading).toBe(false);
      expect(result.current.vram.isLoading).toBe(false);
    });

    const modelsCallCount = vi.mocked(modelZooApi.listModels).mock.calls.length;
    const vramCallCount = vi.mocked(modelZooApi.getVRAMSummary).mock.calls.length;

    await act(async () => {
      await result.current.unloadMutation.unloadModel('threat-detection-yolov8n');
    });

    await waitFor(() => {
      expect(vi.mocked(modelZooApi.listModels).mock.calls.length).toBeGreaterThan(modelsCallCount);
      expect(vi.mocked(modelZooApi.getVRAMSummary).mock.calls.length).toBeGreaterThan(
        vramCallCount
      );
    });
  });
});

// ============================================================================
// Hook Return Types Tests
// ============================================================================

describe('Hook Return Types', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('useModels returns correct shape', async () => {
    vi.mocked(modelZooApi.listModels).mockResolvedValueOnce(mockModelListResponse);

    const { result } = renderHook(() => useModels(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current).toHaveProperty('data');
    expect(result.current).toHaveProperty('models');
    expect(result.current).toHaveProperty('serviceStatus');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('isRefetching');
    expect(result.current).toHaveProperty('error');
    expect(result.current).toHaveProperty('refetch');

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('useVRAMSummary returns correct shape', async () => {
    vi.mocked(modelZooApi.getVRAMSummary).mockResolvedValueOnce(mockVRAMSummaryResponse);

    const { result } = renderHook(() => useVRAMSummary(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current).toHaveProperty('data');
    expect(result.current).toHaveProperty('gpus');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('isRefetching');
    expect(result.current).toHaveProperty('error');
    expect(result.current).toHaveProperty('refetch');

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('useLoadModel returns correct shape', () => {
    const { result } = renderHook(() => useLoadModel(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current).toHaveProperty('mutation');
    expect(result.current).toHaveProperty('loadModel');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('error');

    expect(typeof result.current.loadModel).toBe('function');
  });

  it('useUnloadModel returns correct shape', () => {
    const { result } = renderHook(() => useUnloadModel(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current).toHaveProperty('mutation');
    expect(result.current).toHaveProperty('unloadModel');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('error');

    expect(typeof result.current.unloadModel).toBe('function');
  });

  it('useReloadModel returns correct shape', () => {
    const { result } = renderHook(() => useReloadModel(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current).toHaveProperty('mutation');
    expect(result.current).toHaveProperty('reloadModel');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('error');

    expect(typeof result.current.reloadModel).toBe('function');
  });

  it('useUnloadAllModels returns correct shape', () => {
    const { result } = renderHook(() => useUnloadAllModels(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current).toHaveProperty('mutation');
    expect(result.current).toHaveProperty('unloadAll');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('error');

    expect(typeof result.current.unloadAll).toBe('function');
  });
});

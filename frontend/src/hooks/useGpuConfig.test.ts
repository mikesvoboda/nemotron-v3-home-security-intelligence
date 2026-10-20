/**
 * Unit tests for useGpuConfig hooks (F-176, F-178, F-182).
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useGpus, useGpuConfig, usePreviewStrategy, GPU_QUERY_KEYS } from './useGpuConfig';
import * as gpuConfigApi from '../services/gpuConfigApi';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type {
  GpuListResponse,
  GpuConfig,
  StrategyPreviewResponse,
  GpuDevice,
  GpuAssignment,
} from '../services/gpuConfigApi';

vi.mock('../services/gpuConfigApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/gpuConfigApi')>();
  return {
    ...actual,
    getGpus: vi.fn(),
    getGpuConfig: vi.fn(),
    previewStrategy: vi.fn(),
  };
});

const mockGpuDevice: GpuDevice = {
  index: 0,
  name: 'NVIDIA RTX A5500',
  vram_total_mb: 24576,
  vram_used_mb: 8192,
  compute_capability: '8.6',
};

const mockGpuDevice2: GpuDevice = {
  index: 1,
  name: 'NVIDIA RTX A4000',
  vram_total_mb: 16384,
  vram_used_mb: 4096,
  compute_capability: '8.6',
};

const mockGpuListResponse: GpuListResponse = {
  gpus: [mockGpuDevice, mockGpuDevice2],
};

const mockGpuAssignment: GpuAssignment = {
  service: 'ai-llm',
  gpu_index: 0,
  vram_budget_override: null,
};

const mockGpuAssignment2: GpuAssignment = {
  service: 'ai-yolo26',
  gpu_index: 1,
  vram_budget_override: 3.5,
};

const mockGpuConfig: GpuConfig = {
  strategy: 'isolation_first',
  assignments: [mockGpuAssignment, mockGpuAssignment2],
  updated_at: '2026-01-23T10:30:00Z',
};

const mockStrategyPreviewResponse: StrategyPreviewResponse = {
  strategy: 'balanced',
  proposed_assignments: [
    { service: 'ai-llm', gpu_index: 0, vram_budget_override: null },
    { service: 'ai-yolo26', gpu_index: 1, vram_budget_override: null },
  ],
  warnings: [],
};

describe('GPU_QUERY_KEYS', () => {
  it('has correct base key for all GPU queries', () => {
    expect(GPU_QUERY_KEYS.all).toEqual(['gpu']);
  });

  it('has correct key for GPU devices', () => {
    expect(GPU_QUERY_KEYS.gpus).toEqual(['gpu', 'devices']);
  });

  it('has correct key for GPU config', () => {
    expect(GPU_QUERY_KEYS.config).toEqual(['gpu', 'config']);
  });

  it('creates correct key for strategy preview', () => {
    expect(GPU_QUERY_KEYS.preview('isolation_first')).toEqual([
      'gpu',
      'preview',
      'isolation_first',
    ]);
    expect(GPU_QUERY_KEYS.preview('vram_balanced')).toEqual(['gpu', 'preview', 'vram_balanced']);
  });

  it('creates unique preview keys for different strategies', () => {
    const key1 = GPU_QUERY_KEYS.preview('auto');
    const key2 = GPU_QUERY_KEYS.preview('manual');
    expect(key1).not.toEqual(key2);
  });
});

describe('useGpus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches GPU list successfully', async () => {
    vi.mocked(gpuConfigApi.getGpus).mockResolvedValueOnce(mockGpuListResponse);

    const { result } = renderHook(() => useGpus(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.gpus).toHaveLength(2);
    expect(result.current.data).toEqual(mockGpuListResponse);
    expect(gpuConfigApi.getGpus).toHaveBeenCalledOnce();
  });

  it('returns empty array when no data', () => {
    vi.mocked(gpuConfigApi.getGpus).mockResolvedValueOnce(mockGpuListResponse);

    const { result } = renderHook(() => useGpus(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.gpus).toEqual([]);
  });

  it('handles errors gracefully', async () => {
    const error = new Error('GPU detection failed');
    vi.mocked(gpuConfigApi.getGpus).mockRejectedValue(error);

    const { result } = renderHook(() => useGpus(), {
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
    vi.mocked(gpuConfigApi.getGpus).mockResolvedValueOnce(mockGpuListResponse);

    const { result } = renderHook(() => useGpus({ enabled: false }), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(gpuConfigApi.getGpus).not.toHaveBeenCalled();
  });

  it('provides refetch function', async () => {
    vi.mocked(gpuConfigApi.getGpus).mockResolvedValue(mockGpuListResponse);

    const { result } = renderHook(() => useGpus(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.refetch();
    });

    expect(gpuConfigApi.getGpus).toHaveBeenCalledTimes(2);
  });

  it('tracks isRefetching state', async () => {
    vi.mocked(gpuConfigApi.getGpus).mockResolvedValue(mockGpuListResponse);

    const { result } = renderHook(() => useGpus(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isRefetching).toBe(false);
  });
});

describe('useGpuConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches GPU configuration successfully', async () => {
    vi.mocked(gpuConfigApi.getGpuConfig).mockResolvedValueOnce(mockGpuConfig);

    const { result } = renderHook(() => useGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockGpuConfig);
    expect(result.current.data?.strategy).toBe('isolation_first');
    expect(gpuConfigApi.getGpuConfig).toHaveBeenCalledOnce();
  });

  it('returns undefined data when loading', () => {
    vi.mocked(gpuConfigApi.getGpuConfig).mockResolvedValueOnce(mockGpuConfig);

    const { result } = renderHook(() => useGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.data).toBeUndefined();
  });

  it('handles errors gracefully', async () => {
    const error = new Error('Configuration not found');
    vi.mocked(gpuConfigApi.getGpuConfig).mockRejectedValue(error);

    const { result } = renderHook(() => useGpuConfig(), {
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
    vi.mocked(gpuConfigApi.getGpuConfig).mockResolvedValueOnce(mockGpuConfig);

    const { result } = renderHook(() => useGpuConfig({ enabled: false }), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(gpuConfigApi.getGpuConfig).not.toHaveBeenCalled();
  });

  it('provides refetch function', async () => {
    vi.mocked(gpuConfigApi.getGpuConfig).mockResolvedValue(mockGpuConfig);

    const { result } = renderHook(() => useGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.refetch();
    });

    expect(gpuConfigApi.getGpuConfig).toHaveBeenCalledTimes(2);
  });
});

describe('usePreviewStrategy', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('previews strategy successfully', async () => {
    vi.mocked(gpuConfigApi.previewStrategy).mockResolvedValueOnce(mockStrategyPreviewResponse);

    const { result } = renderHook(() => usePreviewStrategy(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      await result.current.preview('isolation_first');
    });

    await waitFor(() => {
      expect(result.current.mutation.isSuccess).toBe(true);
    });

    expect(vi.mocked(gpuConfigApi.previewStrategy).mock.calls[0][0]).toBe('isolation_first');
  });

  it('returns preview data from mutation', async () => {
    vi.mocked(gpuConfigApi.previewStrategy).mockResolvedValueOnce(mockStrategyPreviewResponse);

    const { result } = renderHook(() => usePreviewStrategy(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      await result.current.preview('isolation_first');
    });

    await waitFor(() => {
      expect(result.current.data).toEqual(mockStrategyPreviewResponse);
    });

    expect(result.current.data?.proposed_assignments).toHaveLength(2);
  });

  it('previews different strategies', async () => {
    vi.mocked(gpuConfigApi.previewStrategy).mockResolvedValue(mockStrategyPreviewResponse);

    const { result } = renderHook(() => usePreviewStrategy(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      await result.current.preview('auto');
    });

    await act(async () => {
      await result.current.preview('vram_balanced');
    });

    const calls = vi.mocked(gpuConfigApi.previewStrategy).mock.calls;
    expect(calls[0][0]).toBe('auto');
    expect(calls[1][0]).toBe('vram_balanced');
  });

  it('handles preview errors', async () => {
    const error = new Error('Invalid strategy');
    vi.mocked(gpuConfigApi.previewStrategy).mockRejectedValueOnce(error);

    const { result } = renderHook(() => usePreviewStrategy(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      try {
        await result.current.preview('invalid_strategy');
      } catch {
        // Expected error
      }
    });

    await waitFor(() => {
      expect(result.current.mutation.isError).toBe(true);
    });

    expect(result.current.error).toBeTruthy();
  });

  it('tracks isLoading state during preview', async () => {
    let resolvePreview: (value: StrategyPreviewResponse) => void;
    const mockPromise = new Promise<StrategyPreviewResponse>((resolve) => {
      resolvePreview = resolve;
    });
    vi.mocked(gpuConfigApi.previewStrategy).mockReturnValueOnce(mockPromise);

    const { result } = renderHook(() => usePreviewStrategy(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);

    let previewPromise: Promise<StrategyPreviewResponse>;
    act(() => {
      previewPromise = result.current.preview('auto');
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    await act(async () => {
      resolvePreview!(mockStrategyPreviewResponse);
      await previewPromise!;
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('returns undefined data before first preview', () => {
    const { result } = renderHook(() => usePreviewStrategy(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.data).toBeUndefined();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
  });
});

describe('Hook Return Types', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('useGpus returns correct shape', async () => {
    vi.mocked(gpuConfigApi.getGpus).mockResolvedValueOnce(mockGpuListResponse);

    const { result } = renderHook(() => useGpus(), {
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

  it('useGpuConfig returns correct shape', async () => {
    vi.mocked(gpuConfigApi.getGpuConfig).mockResolvedValueOnce(mockGpuConfig);

    const { result } = renderHook(() => useGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current).toHaveProperty('data');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('error');
    expect(result.current).toHaveProperty('refetch');

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('usePreviewStrategy returns correct shape', () => {
    const { result } = renderHook(() => usePreviewStrategy(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current).toHaveProperty('mutation');
    expect(result.current).toHaveProperty('preview');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('error');
    expect(result.current).toHaveProperty('data');

    expect(typeof result.current.preview).toBe('function');
  });
});

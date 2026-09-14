/**
 * Unit tests for useGpuConfig hooks
 *
 * Tests all TanStack Query hooks for GPU Configuration with comprehensive
 * coverage of queries, mutations, cache invalidation, and error handling.
 *
 * @see NEM-3322
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useGpus,
  useGpuConfig,
  useGpuStatus,
  useUpdateGpuConfig,
  useApplyGpuConfig,
  useDetectGpus,
  usePreviewStrategy,
  GPU_QUERY_KEYS,
} from './useGpuConfig';
import * as gpuConfigApi from '../services/gpuConfigApi';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type {
  GpuListResponse,
  GpuConfig,
  GpuConfigUpdateResponse,
  GpuApplyResult,
  GpuStatusResponse,
  StrategyPreviewResponse,
  GpuDevice,
  GpuAssignment,
  ServiceStatus,
} from '../services/gpuConfigApi';

// Mock the gpuConfigApi module
vi.mock('../services/gpuConfigApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/gpuConfigApi')>();
  return {
    ...actual,
    getGpus: vi.fn(),
    getGpuConfig: vi.fn(),
    updateGpuConfig: vi.fn(),
    applyGpuConfig: vi.fn(),
    getGpuStatus: vi.fn(),
    detectGpus: vi.fn(),
    previewStrategy: vi.fn(),
  };
});

// ============================================================================
// Mock Data
// ============================================================================

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

const mockGpuConfigUpdateResponse: GpuConfigUpdateResponse = {
  success: true,
  warnings: [],
};

const mockGpuConfigUpdateResponseWithWarnings: GpuConfigUpdateResponse = {
  success: true,
  warnings: ['GPU 0 VRAM budget exceeds available VRAM'],
};

const mockGpuApplyResult: GpuApplyResult = {
  success: true,
  warnings: [],
  restarted_services: ['ai-llm', 'ai-yolo26'],
  service_statuses: [
    { service: 'ai-llm', status: 'running', message: null },
    { service: 'ai-yolo26', status: 'running', message: null },
  ],
};

const mockServiceStatus: ServiceStatus = {
  service: 'ai-llm',
  status: 'running',
  message: null,
};

const mockServiceStatus2: ServiceStatus = {
  service: 'ai-yolo26',
  status: 'running',
  message: null,
};

const mockGpuStatusResponse: GpuStatusResponse = {
  in_progress: false,
  services_pending: [],
  services_completed: ['ai-llm', 'ai-yolo26'],
  service_statuses: [mockServiceStatus, mockServiceStatus2],
};

const mockStrategyPreviewResponse: StrategyPreviewResponse = {
  strategy: 'balanced',
  proposed_assignments: [
    { service: 'ai-llm', gpu_index: 0, vram_budget_override: null },
    { service: 'ai-yolo26', gpu_index: 1, vram_budget_override: null },
  ],
  warnings: [],
};

// ============================================================================
// Query Keys Tests
// ============================================================================

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

  it('has correct key for GPU status', () => {
    expect(GPU_QUERY_KEYS.status).toEqual(['gpu', 'status']);
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

// ============================================================================
// useGpus Tests
// ============================================================================

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

    // Initially loading
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

    // Before data loads, gpus should be empty array
    expect(result.current.gpus).toEqual([]);
  });

  it('handles errors gracefully', async () => {
    const error = new Error('GPU detection failed');
    // Reject both initial call and retry
    vi.mocked(gpuConfigApi.getGpus).mockRejectedValue(error);

    const { result } = renderHook(() => useGpus(), {
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

    // Call refetch
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

// ============================================================================
// useGpuConfig Tests
// ============================================================================

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
    // Reject both initial call and retry
    vi.mocked(gpuConfigApi.getGpuConfig).mockRejectedValue(error);

    const { result } = renderHook(() => useGpuConfig(), {
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

// ============================================================================
// useGpuStatus Tests
// ============================================================================

describe('useGpuStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches GPU status successfully', async () => {
    vi.mocked(gpuConfigApi.getGpuStatus).mockResolvedValueOnce(mockGpuStatusResponse);

    const { result } = renderHook(() => useGpuStatus(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.data).toEqual(mockGpuStatusResponse);
    expect(result.current.data?.service_statuses).toHaveLength(2);
  });

  it('does not fetch when disabled', () => {
    vi.mocked(gpuConfigApi.getGpuStatus).mockResolvedValueOnce(mockGpuStatusResponse);

    const { result } = renderHook(() => useGpuStatus(false), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(gpuConfigApi.getGpuStatus).not.toHaveBeenCalled();
  });

  it('handles errors gracefully', async () => {
    const error = new Error('Failed to get status');
    // Reject both initial call and retry
    vi.mocked(gpuConfigApi.getGpuStatus).mockRejectedValue(error);

    const { result } = renderHook(() => useGpuStatus(), {
      wrapper: createQueryWrapper(),
    });

    // Wait for error state with longer timeout to account for retry
    await waitFor(
      () => {
        expect(result.current.error).toBeTruthy();
      },
      { timeout: 5000 }
    );
  });

  it('provides refetch function', async () => {
    vi.mocked(gpuConfigApi.getGpuStatus).mockResolvedValue(mockGpuStatusResponse);

    const { result } = renderHook(() => useGpuStatus(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.refetch();
    });

    expect(gpuConfigApi.getGpuStatus).toHaveBeenCalledTimes(2);
  });

  it('tracks isRefetching state', async () => {
    vi.mocked(gpuConfigApi.getGpuStatus).mockResolvedValue(mockGpuStatusResponse);

    const { result } = renderHook(() => useGpuStatus(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isRefetching).toBe(false);
  });

  it('fetches when enabled becomes true', async () => {
    vi.mocked(gpuConfigApi.getGpuStatus).mockResolvedValue(mockGpuStatusResponse);

    const { rerender } = renderHook(({ enabled }) => useGpuStatus(enabled), {
      wrapper: createQueryWrapper(),
      initialProps: { enabled: false },
    });

    expect(gpuConfigApi.getGpuStatus).not.toHaveBeenCalled();

    rerender({ enabled: true });

    await waitFor(() => {
      expect(gpuConfigApi.getGpuStatus).toHaveBeenCalled();
    });
  });
});

// ============================================================================
// useUpdateGpuConfig Tests
// ============================================================================

describe('useUpdateGpuConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('updates GPU configuration successfully', async () => {
    vi.mocked(gpuConfigApi.updateGpuConfig).mockResolvedValueOnce(mockGpuConfigUpdateResponse);

    const { result } = renderHook(() => useUpdateGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      await result.current.updateConfig({ strategy: 'vram_balanced' });
    });

    await waitFor(() => {
      expect(result.current.mutation.isSuccess).toBe(true);
    });

    // TanStack Query v5 passes mutation context as second arg, so check first arg only
    expect(vi.mocked(gpuConfigApi.updateGpuConfig).mock.calls[0][0]).toEqual({
      strategy: 'vram_balanced',
    });
  });

  it('updates configuration with assignments', async () => {
    vi.mocked(gpuConfigApi.updateGpuConfig).mockResolvedValueOnce(mockGpuConfigUpdateResponse);

    const { result } = renderHook(() => useUpdateGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    const assignments = [{ service: 'ai-llm', gpu_index: 0, vram_budget_override: null }];

    await act(async () => {
      await result.current.updateConfig({ assignments });
    });

    // TanStack Query v5 passes mutation context as second arg, so check first arg only
    expect(vi.mocked(gpuConfigApi.updateGpuConfig).mock.calls[0][0]).toEqual({ assignments });
  });

  it('returns warnings from update response', async () => {
    vi.mocked(gpuConfigApi.updateGpuConfig).mockResolvedValueOnce(
      mockGpuConfigUpdateResponseWithWarnings
    );

    const { result } = renderHook(() => useUpdateGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    let updateResult: GpuConfigUpdateResponse | undefined;
    await act(async () => {
      updateResult = await result.current.updateConfig({ strategy: 'manual' });
    });

    expect(updateResult?.warnings).toHaveLength(1);
    expect(updateResult?.warnings).toContain('GPU 0 VRAM budget exceeds available VRAM');
  });

  it('handles update errors', async () => {
    const error = new Error('Invalid configuration');
    vi.mocked(gpuConfigApi.updateGpuConfig).mockRejectedValueOnce(error);

    const { result } = renderHook(() => useUpdateGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      try {
        await result.current.updateConfig({ strategy: 'invalid' });
      } catch {
        // Expected error
      }
    });

    await waitFor(() => {
      expect(result.current.mutation.isError).toBe(true);
    });

    expect(result.current.error).toBeTruthy();
  });

  it('tracks isLoading state during update', async () => {
    // Use a deferred promise to control when the mock resolves
    let resolveUpdate: (value: GpuConfigUpdateResponse) => void;
    const mockPromise = new Promise<GpuConfigUpdateResponse>((resolve) => {
      resolveUpdate = resolve;
    });
    vi.mocked(gpuConfigApi.updateGpuConfig).mockReturnValueOnce(mockPromise);

    const { result } = renderHook(() => useUpdateGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);

    // Start the update but don't await yet
    let updatePromise: Promise<GpuConfigUpdateResponse>;
    act(() => {
      updatePromise = result.current.updateConfig({ strategy: 'auto' });
    });

    // Now isLoading should be true while waiting
    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    // Resolve the promise
    await act(async () => {
      resolveUpdate!(mockGpuConfigUpdateResponse);
      await updatePromise!;
    });

    // Now isLoading should be false after resolution
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });
});

// ============================================================================
// useApplyGpuConfig Tests
// ============================================================================

describe('useApplyGpuConfig', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('applies GPU configuration successfully', async () => {
    vi.mocked(gpuConfigApi.applyGpuConfig).mockResolvedValueOnce(mockGpuApplyResult);

    const { result } = renderHook(() => useApplyGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      await result.current.applyConfig();
    });

    await waitFor(() => {
      expect(result.current.mutation.isSuccess).toBe(true);
    });

    expect(gpuConfigApi.applyGpuConfig).toHaveBeenCalledOnce();
  });

  it('returns apply result with restarted services', async () => {
    vi.mocked(gpuConfigApi.applyGpuConfig).mockResolvedValueOnce(mockGpuApplyResult);

    const { result } = renderHook(() => useApplyGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    let applyResult: GpuApplyResult | undefined;
    await act(async () => {
      applyResult = await result.current.applyConfig();
    });

    expect(applyResult?.success).toBe(true);
    expect(applyResult?.restarted_services).toContain('ai-llm');
    expect(applyResult?.restarted_services).toContain('ai-yolo26');
  });

  it('handles apply with failed services', async () => {
    const failedResult: GpuApplyResult = {
      success: false,
      warnings: ['Restart failed'],
      restarted_services: ['ai-llm'],
      service_statuses: [
        { service: 'ai-llm', status: 'running', message: null },
        { service: 'ai-yolo26', status: 'error', message: 'Restart failed' },
      ],
    };
    vi.mocked(gpuConfigApi.applyGpuConfig).mockResolvedValueOnce(failedResult);

    const { result } = renderHook(() => useApplyGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    let applyResult: GpuApplyResult | undefined;
    await act(async () => {
      applyResult = await result.current.applyConfig();
    });

    expect(applyResult?.success).toBe(false);
    const failedService = applyResult?.service_statuses.find((s) => s.status === 'error');
    expect(failedService?.service).toBe('ai-yolo26');
  });

  it('handles apply errors', async () => {
    const error = new Error('Docker daemon unavailable');
    vi.mocked(gpuConfigApi.applyGpuConfig).mockRejectedValueOnce(error);

    const { result } = renderHook(() => useApplyGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      try {
        await result.current.applyConfig();
      } catch {
        // Expected error
      }
    });

    await waitFor(() => {
      expect(result.current.mutation.isError).toBe(true);
    });

    expect(result.current.error).toBeTruthy();
  });

  it('tracks isLoading state during apply', async () => {
    // Use a deferred promise to control when the mock resolves
    let resolveApply: (value: GpuApplyResult) => void;
    const mockPromise = new Promise<GpuApplyResult>((resolve) => {
      resolveApply = resolve;
    });
    vi.mocked(gpuConfigApi.applyGpuConfig).mockReturnValueOnce(mockPromise);

    const { result } = renderHook(() => useApplyGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);

    // Start the apply but don't await yet
    let applyPromise: Promise<GpuApplyResult>;
    act(() => {
      applyPromise = result.current.applyConfig();
    });

    // Now isLoading should be true while waiting
    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    // Resolve the promise
    await act(async () => {
      resolveApply!(mockGpuApplyResult);
      await applyPromise!;
    });

    // Now isLoading should be false after resolution
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });
});

// ============================================================================
// useDetectGpus Tests
// ============================================================================

describe('useDetectGpus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('detects GPUs successfully', async () => {
    vi.mocked(gpuConfigApi.detectGpus).mockResolvedValueOnce(mockGpuListResponse);

    const { result } = renderHook(() => useDetectGpus(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      await result.current.detect();
    });

    await waitFor(() => {
      expect(result.current.mutation.isSuccess).toBe(true);
    });

    expect(gpuConfigApi.detectGpus).toHaveBeenCalledOnce();
  });

  it('returns detected GPU list', async () => {
    vi.mocked(gpuConfigApi.detectGpus).mockResolvedValueOnce(mockGpuListResponse);

    const { result } = renderHook(() => useDetectGpus(), {
      wrapper: createQueryWrapper(),
    });

    let detectResult: GpuListResponse | undefined;
    await act(async () => {
      detectResult = await result.current.detect();
    });

    expect(detectResult?.gpus).toHaveLength(2);
    expect(detectResult?.gpus[0].name).toBe('NVIDIA RTX A5500');
  });

  it('handles detection errors', async () => {
    const error = new Error('NVIDIA driver not found');
    vi.mocked(gpuConfigApi.detectGpus).mockRejectedValueOnce(error);

    const { result } = renderHook(() => useDetectGpus(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      try {
        await result.current.detect();
      } catch {
        // Expected error
      }
    });

    await waitFor(() => {
      expect(result.current.mutation.isError).toBe(true);
    });

    expect(result.current.error).toBeTruthy();
  });

  it('tracks isLoading state during detection', async () => {
    // Use a deferred promise to control when the mock resolves
    let resolveDetect: (value: GpuListResponse) => void;
    const mockPromise = new Promise<GpuListResponse>((resolve) => {
      resolveDetect = resolve;
    });
    vi.mocked(gpuConfigApi.detectGpus).mockReturnValueOnce(mockPromise);

    const { result } = renderHook(() => useDetectGpus(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);

    // Start the detect but don't await yet
    let detectPromise: Promise<GpuListResponse>;
    act(() => {
      detectPromise = result.current.detect();
    });

    // Now isLoading should be true while waiting
    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    // Resolve the promise
    await act(async () => {
      resolveDetect!(mockGpuListResponse);
      await detectPromise!;
    });

    // Now isLoading should be false after resolution
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
  });

  it('handles detection returning empty list', async () => {
    const emptyResponse: GpuListResponse = { gpus: [] };
    vi.mocked(gpuConfigApi.detectGpus).mockResolvedValueOnce(emptyResponse);

    const { result } = renderHook(() => useDetectGpus(), {
      wrapper: createQueryWrapper(),
    });

    let detectResult: GpuListResponse | undefined;
    await act(async () => {
      detectResult = await result.current.detect();
    });

    expect(detectResult?.gpus).toHaveLength(0);
  });
});

// ============================================================================
// usePreviewStrategy Tests
// ============================================================================

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

    // TanStack Query v5 passes mutation context as second arg, so check first arg only
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

    // TanStack Query v5 passes mutation context as second arg, so check first arg only
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
    // Use a deferred promise to control when the mock resolves
    let resolvePreview: (value: StrategyPreviewResponse) => void;
    const mockPromise = new Promise<StrategyPreviewResponse>((resolve) => {
      resolvePreview = resolve;
    });
    vi.mocked(gpuConfigApi.previewStrategy).mockReturnValueOnce(mockPromise);

    const { result } = renderHook(() => usePreviewStrategy(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);

    // Start the preview but don't await yet
    let previewPromise: Promise<StrategyPreviewResponse>;
    act(() => {
      previewPromise = result.current.preview('auto');
    });

    // Now isLoading should be true while waiting
    await waitFor(() => {
      expect(result.current.isLoading).toBe(true);
    });

    // Resolve the promise
    await act(async () => {
      resolvePreview!(mockStrategyPreviewResponse);
      await previewPromise!;
    });

    // Now isLoading should be false after resolution
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

  it('useUpdateGpuConfig invalidates config query on success', async () => {
    vi.mocked(gpuConfigApi.updateGpuConfig).mockResolvedValueOnce(mockGpuConfigUpdateResponse);
    vi.mocked(gpuConfigApi.getGpuConfig).mockResolvedValue(mockGpuConfig);

    const { result } = renderHook(
      () => ({
        update: useUpdateGpuConfig(),
        config: useGpuConfig(),
      }),
      { wrapper: createQueryWrapper() }
    );

    // Wait for initial config fetch
    await waitFor(() => {
      expect(result.current.config.isLoading).toBe(false);
    });

    const initialCallCount = vi.mocked(gpuConfigApi.getGpuConfig).mock.calls.length;

    // Update config
    await act(async () => {
      await result.current.update.updateConfig({ strategy: 'vram_balanced' });
    });

    // Config should be refetched due to invalidation
    await waitFor(() => {
      expect(vi.mocked(gpuConfigApi.getGpuConfig).mock.calls.length).toBeGreaterThan(
        initialCallCount
      );
    });
  });

  it('useApplyGpuConfig invalidates status query on success', async () => {
    vi.mocked(gpuConfigApi.applyGpuConfig).mockResolvedValueOnce(mockGpuApplyResult);
    vi.mocked(gpuConfigApi.getGpuStatus).mockResolvedValue(mockGpuStatusResponse);

    const { result } = renderHook(
      () => ({
        apply: useApplyGpuConfig(),
        status: useGpuStatus(),
      }),
      { wrapper: createQueryWrapper() }
    );

    // Wait for initial status fetch
    await waitFor(() => {
      expect(result.current.status.isLoading).toBe(false);
    });

    const initialCallCount = vi.mocked(gpuConfigApi.getGpuStatus).mock.calls.length;

    // Apply config
    await act(async () => {
      await result.current.apply.applyConfig();
    });

    // Status should be refetched due to invalidation
    await waitFor(() => {
      expect(vi.mocked(gpuConfigApi.getGpuStatus).mock.calls.length).toBeGreaterThan(
        initialCallCount
      );
    });
  });

  it('useDetectGpus invalidates gpus query on success', async () => {
    vi.mocked(gpuConfigApi.detectGpus).mockResolvedValueOnce(mockGpuListResponse);
    vi.mocked(gpuConfigApi.getGpus).mockResolvedValue(mockGpuListResponse);

    const { result } = renderHook(
      () => ({
        detect: useDetectGpus(),
        gpus: useGpus(),
      }),
      { wrapper: createQueryWrapper() }
    );

    // Wait for initial gpus fetch
    await waitFor(() => {
      expect(result.current.gpus.isLoading).toBe(false);
    });

    const initialCallCount = vi.mocked(gpuConfigApi.getGpus).mock.calls.length;

    // Detect GPUs
    await act(async () => {
      await result.current.detect.detect();
    });

    // GPUs should be refetched due to invalidation
    await waitFor(() => {
      expect(vi.mocked(gpuConfigApi.getGpus).mock.calls.length).toBeGreaterThan(initialCallCount);
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

  it('useGpus returns correct shape', async () => {
    vi.mocked(gpuConfigApi.getGpus).mockResolvedValueOnce(mockGpuListResponse);

    const { result } = renderHook(() => useGpus(), {
      wrapper: createQueryWrapper(),
    });

    // Check shape before loading completes
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

  it('useUpdateGpuConfig returns correct shape', () => {
    const { result } = renderHook(() => useUpdateGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current).toHaveProperty('mutation');
    expect(result.current).toHaveProperty('updateConfig');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('error');

    expect(typeof result.current.updateConfig).toBe('function');
  });

  it('useApplyGpuConfig returns correct shape', () => {
    const { result } = renderHook(() => useApplyGpuConfig(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current).toHaveProperty('mutation');
    expect(result.current).toHaveProperty('applyConfig');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('error');

    expect(typeof result.current.applyConfig).toBe('function');
  });

  it('useDetectGpus returns correct shape', () => {
    const { result } = renderHook(() => useDetectGpus(), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current).toHaveProperty('mutation');
    expect(result.current).toHaveProperty('detect');
    expect(result.current).toHaveProperty('isLoading');
    expect(result.current).toHaveProperty('error');

    expect(typeof result.current.detect).toBe('function');
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

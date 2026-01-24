/**
 * Tests for MetricsContext.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { act } from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  MetricsProvider,
  useMetricsContext,
  useMetricsContextOptional,
  DEFAULT_GPU_STATS,
} from './MetricsContext';
import { useGpuStatsQuery } from '../hooks/useGpuStatsQuery';

import type { GPUStats } from '../services/api';

// Mock the useGpuStatsQuery hook (must be before imports that use it)
vi.mock('../hooks/useGpuStatsQuery');

// ============================================================================
// Test Utilities
// ============================================================================

// Mock data
const mockGpuStats: GPUStats = {
  gpu_name: 'NVIDIA RTX A5500',
  utilization: 42,
  memory_used: 8192,
  memory_total: 24576,
  temperature: 65,
  power_usage: 150,
  inference_fps: 30,
};

// Create wrapper with QueryClientProvider
function createWrapper(providerOptions: { pollingInterval?: number; enabled?: boolean } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MetricsProvider {...providerOptions}>{children}</MetricsProvider>
      </QueryClientProvider>
    );
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('MetricsContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Set up default mock return value
    vi.mocked(useGpuStatsQuery).mockReturnValue({
      data: mockGpuStats,
      isLoading: false,
      isRefetching: false,
      error: null,
      isStale: false,
      refetch: vi.fn().mockResolvedValue(undefined),
      utilization: 42,
      memoryUsed: 8192,
      temperature: 65,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('useMetricsContext', () => {
    it('provides GPU stats data', () => {
      const { result } = renderHook(() => useMetricsContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.gpuStats).toEqual(mockGpuStats);
      expect(result.current.utilization).toBe(42);
    });

    it('provides derived metrics', () => {
      const { result } = renderHook(() => useMetricsContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.memoryUsed).toBe(8192);
      expect(result.current.memoryTotal).toBe(24576);
      expect(result.current.temperature).toBe(65);
      expect(result.current.powerUsage).toBe(150);
      expect(result.current.inferenceFps).toBe(30);
    });

    it('calculates memory usage percentage', () => {
      const { result } = renderHook(() => useMetricsContext(), {
        wrapper: createWrapper(),
      });

      // 8192 / 24576 * 100 = 33.33...
      expect(result.current.memoryUsagePercent).toBe(33);
    });

    it('provides status checks', () => {
      const { result } = renderHook(() => useMetricsContext(), {
        wrapper: createWrapper(),
      });

      // 42% utilization is not high load (< 80%)
      expect(result.current.isHighLoad).toBe(false);
      // 65C is not high temperature (< 80C)
      expect(result.current.isHighTemperature).toBe(false);
    });

    it('detects high load', () => {
      vi.mocked(useGpuStatsQuery).mockReturnValue({
        data: { ...mockGpuStats, utilization: 90 },
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
        utilization: 90,
        memoryUsed: 8192,
        temperature: 65,
      });

      const { result } = renderHook(() => useMetricsContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isHighLoad).toBe(true);
    });

    it('detects high temperature', () => {
      vi.mocked(useGpuStatsQuery).mockReturnValue({
        data: { ...mockGpuStats, temperature: 85 },
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
        utilization: 42,
        memoryUsed: 8192,
        temperature: 85,
      });

      const { result } = renderHook(() => useMetricsContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isHighTemperature).toBe(true);
    });

    it('provides loading state', () => {
      const { result } = renderHook(() => useMetricsContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.isRefetching).toBe(false);
    });

    it('provides error state when no errors', () => {
      const { result } = renderHook(() => useMetricsContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.error).toBeNull();
    });

    it('throws error when used outside provider', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      const { result } = renderHook(
        () => {
          try {
            return useMetricsContext();
          } catch (e) {
            return e;
          }
        },
        {
          wrapper: ({ children }) => (
            <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
          ),
        }
      );

      expect(result.current).toBeInstanceOf(Error);
      expect((result.current as Error).message).toBe(
        'useMetricsContext must be used within a MetricsProvider'
      );
    });
  });

  describe('useMetricsContextOptional', () => {
    it('returns data when within provider', () => {
      const { result } = renderHook(() => useMetricsContextOptional(), {
        wrapper: createWrapper(),
      });

      expect(result.current).not.toBeNull();
      expect(result.current?.gpuStats).toEqual(mockGpuStats);
    });

    it('returns null when outside provider', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      const { result } = renderHook(() => useMetricsContextOptional(), {
        wrapper: ({ children }) => (
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        ),
      });

      expect(result.current).toBeNull();
    });
  });

  describe('loading states', () => {
    it('shows isLoading when GPU query is loading', () => {
      vi.mocked(useGpuStatsQuery).mockReturnValue({
        data: undefined,
        isLoading: true,
        isRefetching: false,
        error: null,
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
        utilization: null,
        memoryUsed: null,
        temperature: null,
      });

      const { result } = renderHook(() => useMetricsContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('shows isRefetching when query is refetching', () => {
      vi.mocked(useGpuStatsQuery).mockReturnValue({
        data: mockGpuStats,
        isLoading: false,
        isRefetching: true,
        error: null,
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
        utilization: 42,
        memoryUsed: 8192,
        temperature: 65,
      });

      const { result } = renderHook(() => useMetricsContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isRefetching).toBe(true);
    });
  });

  describe('error states', () => {
    it('returns error from GPU query', () => {
      const gpuError = new Error('Failed to fetch GPU stats');
      vi.mocked(useGpuStatsQuery).mockReturnValue({
        data: undefined,
        isLoading: false,
        isRefetching: false,
        error: gpuError,
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
        utilization: null,
        memoryUsed: null,
        temperature: null,
      });

      const { result } = renderHook(() => useMetricsContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.error).toBe(gpuError);
    });
  });

  describe('default values', () => {
    it('provides DEFAULT_GPU_STATS when GPU data is not available', () => {
      vi.mocked(useGpuStatsQuery).mockReturnValue({
        data: undefined,
        isLoading: true,
        isRefetching: false,
        error: null,
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
        utilization: null,
        memoryUsed: null,
        temperature: null,
      });

      const { result } = renderHook(() => useMetricsContext(), {
        wrapper: createWrapper(),
      });

      expect(result.current.gpuStats).toEqual(DEFAULT_GPU_STATS);
    });
  });

  describe('refetch', () => {
    it('calls refetch on GPU query', async () => {
      const gpuRefetch = vi.fn().mockResolvedValue(undefined);

      vi.mocked(useGpuStatsQuery).mockReturnValue({
        data: mockGpuStats,
        isLoading: false,
        isRefetching: false,
        error: null,
        isStale: false,
        refetch: gpuRefetch,
        utilization: 42,
        memoryUsed: 8192,
        temperature: 65,
      });

      const { result } = renderHook(() => useMetricsContext(), {
        wrapper: createWrapper(),
      });

      act(() => {
        void result.current.refetch();
      });

      await waitFor(() => {
        expect(gpuRefetch).toHaveBeenCalled();
      });
    });
  });

  describe('provider configuration', () => {
    it('passes custom polling interval to query', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      function CustomWrapper({ children }: { children: React.ReactNode }) {
        return (
          <QueryClientProvider client={queryClient}>
            <MetricsProvider pollingInterval={3000}>{children}</MetricsProvider>
          </QueryClientProvider>
        );
      }

      renderHook(() => useMetricsContext(), {
        wrapper: CustomWrapper,
      });

      expect(useGpuStatsQuery).toHaveBeenCalledWith({
        enabled: true,
        refetchInterval: 3000,
        staleTime: 3000,
      });
    });

    it('disables query when enabled is false', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      function DisabledWrapper({ children }: { children: React.ReactNode }) {
        return (
          <QueryClientProvider client={queryClient}>
            <MetricsProvider enabled={false}>{children}</MetricsProvider>
          </QueryClientProvider>
        );
      }

      renderHook(() => useMetricsContext(), {
        wrapper: DisabledWrapper,
      });

      expect(useGpuStatsQuery).toHaveBeenCalledWith(expect.objectContaining({ enabled: false }));
    });
  });

  describe('DEFAULT_GPU_STATS constant', () => {
    it('has expected structure', () => {
      expect(DEFAULT_GPU_STATS).toHaveProperty('gpu_name', 'Unknown');
      expect(DEFAULT_GPU_STATS).toHaveProperty('utilization', 0);
      expect(DEFAULT_GPU_STATS).toHaveProperty('memory_used', 0);
      expect(DEFAULT_GPU_STATS).toHaveProperty('memory_total', 0);
      expect(DEFAULT_GPU_STATS).toHaveProperty('temperature', 0);
    });
  });
});

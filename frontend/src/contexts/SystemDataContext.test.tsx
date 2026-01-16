/**
 * Tests for SystemDataContext.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { act } from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

// eslint-disable-next-line import/order
import {
  SystemDataProvider,
  useSystemData,
  useSystemDataOptional,
  DEFAULT_HEALTH,
  DEFAULT_GPU_STATS,
} from './SystemDataContext';

// ============================================================================
// Test Utilities
// ============================================================================

// Mock data
const mockCameras: Camera[] = [
  {
    id: 'front_door',
    name: 'Front Door',
    folder_path: '/export/foscam/front_door',
    status: 'online',
    created_at: '2024-01-01T00:00:00Z',
    last_seen_at: null,
  },
  {
    id: 'backyard',
    name: 'Backyard',
    folder_path: '/export/foscam/backyard',
    status: 'online',
    created_at: '2024-01-01T00:00:00Z',
    last_seen_at: null,
  },
];

const mockHealthResponse: HealthResponse = {
  status: 'healthy',
  timestamp: '2024-01-01T00:00:00Z',
  services: {
    database: { status: 'healthy', message: null },
    redis: { status: 'healthy', message: null },
  },
};

const mockGpuStats: GPUStats = {
  gpu_name: 'NVIDIA RTX A5500',
  utilization: 42,
  memory_used: 8192,
  memory_total: 24576,
  temperature: 65,
  power_usage: 150,
  inference_fps: 30,
};

// Mock the hooks
vi.mock('../hooks/useCamerasQuery', () => ({
  useCamerasQuery: vi.fn(() => ({
    cameras: mockCameras,
    isLoading: false,
    isRefetching: false,
    error: null,
    refetch: vi.fn(),
  })),
}));

vi.mock('../hooks/useHealthStatusQuery', () => ({
  useHealthStatusQuery: vi.fn(() => ({
    data: mockHealthResponse,
    isLoading: false,
    isRefetching: false,
    error: null,
    overallStatus: 'healthy',
    services: mockHealthResponse.services,
    refetch: vi.fn(),
  })),
}));

vi.mock('../hooks/useGpuStatsQuery', () => ({
  useGpuStatsQuery: vi.fn(() => ({
    data: mockGpuStats,
    isLoading: false,
    isRefetching: false,
    error: null,
    refetch: vi.fn(),
  })),
}));

// Import mocked hooks for test manipulation
import { useCamerasQuery } from '../hooks/useCamerasQuery';
import { useGpuStatsQuery } from '../hooks/useGpuStatsQuery';
import { useHealthStatusQuery } from '../hooks/useHealthStatusQuery';

import type { Camera, GPUStats, HealthResponse } from '../services/api';

// Create wrapper with QueryClientProvider
function createWrapper() {
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
        <SystemDataProvider>{children}</SystemDataProvider>
      </QueryClientProvider>
    );
  };
}

// ============================================================================
// Tests
// ============================================================================

describe('SystemDataContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('useSystemData', () => {
    it('provides camera data', () => {
      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.cameras).toEqual(mockCameras);
      expect(result.current.cameras).toHaveLength(2);
    });

    it('provides health status data', () => {
      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.systemHealth).toEqual(mockHealthResponse);
      expect(result.current.overallStatus).toBe('healthy');
    });

    it('provides GPU stats data', () => {
      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.gpuStats).toEqual(mockGpuStats);
      expect(result.current.gpuStats.utilization).toBe(42);
    });

    it('provides services map from health response', () => {
      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.services).toEqual(mockHealthResponse.services);
      expect(result.current.services.database.status).toBe('healthy');
    });

    it('provides loading state', () => {
      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(false);
      expect(result.current.isRefetching).toBe(false);
    });

    it('provides error state when no errors', () => {
      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.error).toBeNull();
    });

    it('provides individual query states', () => {
      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.queries.cameras.isLoading).toBe(false);
      expect(result.current.queries.health.isLoading).toBe(false);
      expect(result.current.queries.gpu.isLoading).toBe(false);
    });

    it('throws error when used outside provider', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      // Wrap without SystemDataProvider
      const { result } = renderHook(
        () => {
          try {
            return useSystemData();
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
        'useSystemData must be used within a SystemDataProvider'
      );
    });
  });

  describe('useSystemDataOptional', () => {
    it('returns data when within provider', () => {
      const { result } = renderHook(() => useSystemDataOptional(), {
        wrapper: createWrapper(),
      });

      expect(result.current).not.toBeNull();
      expect(result.current?.cameras).toEqual(mockCameras);
    });

    it('returns null when outside provider', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      const { result } = renderHook(() => useSystemDataOptional(), {
        wrapper: ({ children }) => (
          <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
        ),
      });

      expect(result.current).toBeNull();
    });
  });

  describe('loading states', () => {
    it('shows isLoading when cameras query is loading', () => {
      vi.mocked(useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: true,
        isRefetching: false,
        error: null,
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.queries.cameras.isLoading).toBe(true);
    });

    it('shows isLoading when health query is loading', () => {
      vi.mocked(useHealthStatusQuery).mockReturnValue({
        data: undefined,
        isLoading: true,
        isRefetching: false,
        error: null,
        overallStatus: null,
        services: {},
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.queries.health.isLoading).toBe(true);
    });

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

      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.queries.gpu.isLoading).toBe(true);
    });

    it('shows isRefetching when any query is refetching', () => {
      vi.mocked(useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: true,
        error: null,
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isRefetching).toBe(true);
      expect(result.current.queries.cameras.isRefetching).toBe(true);
    });
  });

  describe('error states', () => {
    it('returns first error from cameras query', () => {
      const camerasError = new Error('Failed to fetch cameras');
      vi.mocked(useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: false,
        isRefetching: false,
        error: camerasError,
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.error).toBe(camerasError);
      expect(result.current.queries.cameras.error).toBe(camerasError);
    });

    it('returns first error from health query', () => {
      const healthError = new Error('Failed to fetch health');
      vi.mocked(useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: vi.fn().mockResolvedValue(undefined),
      });
      vi.mocked(useHealthStatusQuery).mockReturnValue({
        data: undefined,
        isLoading: false,
        isRefetching: false,
        error: healthError,
        overallStatus: null,
        services: {},
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.error).toBe(healthError);
      expect(result.current.queries.health.error).toBe(healthError);
    });

    it('returns cameras error when multiple errors exist', () => {
      const camerasError = new Error('Cameras error');
      const healthError = new Error('Health error');

      vi.mocked(useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: false,
        isRefetching: false,
        error: camerasError,
        refetch: vi.fn().mockResolvedValue(undefined),
      });
      vi.mocked(useHealthStatusQuery).mockReturnValue({
        data: undefined,
        isLoading: false,
        isRefetching: false,
        error: healthError,
        overallStatus: null,
        services: {},
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      // Should return the first error (cameras)
      expect(result.current.error).toBe(camerasError);
    });
  });

  describe('default values', () => {
    it('provides DEFAULT_HEALTH when health data is not available', () => {
      vi.mocked(useHealthStatusQuery).mockReturnValue({
        data: undefined,
        isLoading: true,
        isRefetching: false,
        error: null,
        overallStatus: null,
        services: {},
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.systemHealth).toEqual(DEFAULT_HEALTH);
    });

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

      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.gpuStats).toEqual(DEFAULT_GPU_STATS);
    });

    it('provides "unknown" status when health status is not available', () => {
      vi.mocked(useHealthStatusQuery).mockReturnValue({
        data: undefined,
        isLoading: true,
        isRefetching: false,
        error: null,
        overallStatus: null,
        services: {},
        isStale: false,
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.overallStatus).toBe('unknown');
    });

    it('provides empty array for cameras when not available', () => {
      vi.mocked(useCamerasQuery).mockReturnValue({
        cameras: [],
        isLoading: true,
        isRefetching: false,
        error: null,
        refetch: vi.fn().mockResolvedValue(undefined),
      });

      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      expect(result.current.cameras).toEqual([]);
    });
  });

  describe('refetch', () => {
    it('calls refetch on all queries', async () => {
      const camerasRefetch = vi.fn().mockResolvedValue(undefined);
      const healthRefetch = vi.fn().mockResolvedValue(undefined);
      const gpuRefetch = vi.fn().mockResolvedValue(undefined);

      vi.mocked(useCamerasQuery).mockReturnValue({
        cameras: mockCameras,
        isLoading: false,
        isRefetching: false,
        error: null,
        refetch: camerasRefetch,
      });
      vi.mocked(useHealthStatusQuery).mockReturnValue({
        data: mockHealthResponse,
        isLoading: false,
        isRefetching: false,
        error: null,
        overallStatus: 'healthy',
        services: mockHealthResponse.services,
        isStale: false,
        refetch: healthRefetch,
      });
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

      const { result } = renderHook(() => useSystemData(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.refetch();
      });

      await waitFor(() => {
        expect(camerasRefetch).toHaveBeenCalled();
        expect(healthRefetch).toHaveBeenCalled();
        expect(gpuRefetch).toHaveBeenCalled();
      });
    });
  });

  describe('provider configuration', () => {
    it('passes custom polling intervals to queries', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      function CustomWrapper({ children }: { children: React.ReactNode }) {
        return (
          <QueryClientProvider client={queryClient}>
            <SystemDataProvider
              cameraPollingInterval={60000}
              healthPollingInterval={20000}
              gpuPollingInterval={3000}
            >
              {children}
            </SystemDataProvider>
          </QueryClientProvider>
        );
      }

      renderHook(() => useSystemData(), {
        wrapper: CustomWrapper,
      });

      expect(useCamerasQuery).toHaveBeenCalledWith({
        enabled: true,
        refetchInterval: 60000,
        staleTime: 60000,
      });
      expect(useHealthStatusQuery).toHaveBeenCalledWith({
        enabled: true,
        refetchInterval: 20000,
        staleTime: 20000,
      });
      expect(useGpuStatsQuery).toHaveBeenCalledWith({
        enabled: true,
        refetchInterval: 3000,
        staleTime: 3000,
      });
    });

    it('disables queries when enabled is false', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });

      function DisabledWrapper({ children }: { children: React.ReactNode }) {
        return (
          <QueryClientProvider client={queryClient}>
            <SystemDataProvider enabled={false}>{children}</SystemDataProvider>
          </QueryClientProvider>
        );
      }

      renderHook(() => useSystemData(), {
        wrapper: DisabledWrapper,
      });

      expect(useCamerasQuery).toHaveBeenCalledWith(expect.objectContaining({ enabled: false }));
      expect(useHealthStatusQuery).toHaveBeenCalledWith(
        expect.objectContaining({ enabled: false })
      );
      expect(useGpuStatsQuery).toHaveBeenCalledWith(expect.objectContaining({ enabled: false }));
    });
  });

  describe('DEFAULT_HEALTH constant', () => {
    it('has expected structure', () => {
      expect(DEFAULT_HEALTH).toHaveProperty('status', 'unknown');
      expect(DEFAULT_HEALTH).toHaveProperty('services');
      expect(DEFAULT_HEALTH).toHaveProperty('timestamp');
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

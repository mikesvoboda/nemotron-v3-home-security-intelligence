/**
 * Tests for TanStack Query v5 Advanced Patterns
 *
 * @see NEM-3409 - placeholderData pattern
 * @see NEM-3410 - select option for data transformation
 * @see NEM-3411 - AbortSignal integration
 * @see NEM-3412 - parallel queries with useQueries
 *
 * @vitest-environment jsdom
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import {
  // PlaceholderData factories
  createPlaceholderCameras,
  createPlaceholderHealthStatus,
  createPlaceholderGpuStats,
  createPlaceholderEventStats,
  // Select functions
  selectOnlineCameras,
  selectCameraCountsByStatus,
  selectHealthSummary,
  selectRiskDistribution,
  // AbortSignal utilities
  withAbortSignal,
  createSignalAwareQueryFn,
  // Parallel queries
  useDashboardQueries,
} from './useQueryPatterns';

import type { Camera } from '../services/api';
import type { ReactNode } from 'react';

// ============================================================================
// Test Wrapper
// ============================================================================

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// ============================================================================
// PlaceholderData Factory Tests (NEM-3409)
// ============================================================================

describe('createPlaceholderCameras', () => {
  it('should create the specified number of placeholder cameras', () => {
    const cameras = createPlaceholderCameras(3);

    expect(cameras).toHaveLength(3);
    cameras.forEach((camera, index) => {
      expect(camera.id).toBe(`placeholder-${index}`);
      expect(camera.name).toBe(`Loading Camera ${index + 1}`);
      expect(camera.status).toBe('offline');
      expect(camera.folder_path).toBe('/loading');
      expect(camera.last_seen_at).toBeNull();
    });
  });

  it('should default to 6 cameras when no count is provided', () => {
    const cameras = createPlaceholderCameras();

    expect(cameras).toHaveLength(6);
  });

  it('should create empty array when count is 0', () => {
    const cameras = createPlaceholderCameras(0);

    expect(cameras).toHaveLength(0);
  });
});

describe('createPlaceholderHealthStatus', () => {
  it('should create a valid placeholder health status', () => {
    const health = createPlaceholderHealthStatus();

    expect(health.status).toBe('degraded');
    expect(health.timestamp).toBeDefined();
    expect(health.services).toBeDefined();
    expect(health.services.database?.status).toBe('unknown');
    expect(health.services.redis?.status).toBe('unknown');
  });
});

describe('createPlaceholderGpuStats', () => {
  it('should create a valid placeholder GPU stats', () => {
    const stats = createPlaceholderGpuStats();

    // Check that expected properties exist
    expect(stats).toBeDefined();
    expect(typeof stats).toBe('object');
  });
});

describe('createPlaceholderEventStats', () => {
  it('should create a valid placeholder event stats', () => {
    const stats = createPlaceholderEventStats();

    expect(stats.total_events).toBe(0);
    expect(stats.events_by_risk_level).toBeDefined();
  });
});

// ============================================================================
// Select Function Tests (NEM-3410)
// ============================================================================

describe('selectOnlineCameras', () => {
  const testCameras: Camera[] = [
    {
      id: '1',
      name: 'Camera 1',
      folder_path: '/cam1',
      status: 'online',
      last_seen_at: null,
      created_at: '2024-01-01',
    },
    {
      id: '2',
      name: 'Camera 2',
      folder_path: '/cam2',
      status: 'offline',
      last_seen_at: null,
      created_at: '2024-01-01',
    },
    {
      id: '3',
      name: 'Camera 3',
      folder_path: '/cam3',
      status: 'online',
      last_seen_at: null,
      created_at: '2024-01-01',
    },
    {
      id: '4',
      name: 'Camera 4',
      folder_path: '/cam4',
      status: 'error',
      last_seen_at: null,
      created_at: '2024-01-01',
    },
  ];

  it('should filter to only online cameras', () => {
    const online = selectOnlineCameras(testCameras);

    expect(online).toHaveLength(2);
    expect(online.every((c) => c.status === 'online')).toBe(true);
    expect(online.map((c) => c.id)).toEqual(['1', '3']);
  });

  it('should return empty array when no cameras are online', () => {
    const allOffline: Camera[] = testCameras.map((c) => ({ ...c, status: 'offline' as const }));
    const online = selectOnlineCameras(allOffline);

    expect(online).toHaveLength(0);
  });
});

describe('selectCameraCountsByStatus', () => {
  const testCameras: Camera[] = [
    {
      id: '1',
      name: 'Camera 1',
      folder_path: '/cam1',
      status: 'online',
      last_seen_at: null,
      created_at: '2024-01-01',
    },
    {
      id: '2',
      name: 'Camera 2',
      folder_path: '/cam2',
      status: 'offline',
      last_seen_at: null,
      created_at: '2024-01-01',
    },
    {
      id: '3',
      name: 'Camera 3',
      folder_path: '/cam3',
      status: 'online',
      last_seen_at: null,
      created_at: '2024-01-01',
    },
    {
      id: '4',
      name: 'Camera 4',
      folder_path: '/cam4',
      status: 'error',
      last_seen_at: null,
      created_at: '2024-01-01',
    },
  ];

  it('should count cameras by status correctly', () => {
    const counts = selectCameraCountsByStatus(testCameras);

    expect(counts).toEqual({
      online: 2,
      offline: 1,
      error: 1,
      total: 4,
    });
  });

  it('should handle empty array', () => {
    const counts = selectCameraCountsByStatus([]);

    expect(counts).toEqual({
      online: 0,
      offline: 0,
      error: 0,
      total: 0,
    });
  });
});

describe('selectHealthSummary', () => {
  it('should extract health summary from healthy response', () => {
    const health = {
      status: 'healthy' as const,
      timestamp: '2024-01-01T00:00:00Z',
      services: {
        database: { status: 'healthy' },
        redis: { status: 'healthy' },
      },
    };

    const summary = selectHealthSummary(health);

    expect(summary.status).toBe('healthy');
    expect(summary.serviceCount).toBe(2);
    expect(summary.healthyServiceCount).toBe(2);
    expect(summary.timestamp).toBe('2024-01-01T00:00:00Z');
  });

  it('should extract health summary from degraded response', () => {
    const health = {
      status: 'degraded' as const,
      timestamp: '2024-01-01T00:00:00Z',
      services: {
        database: { status: 'healthy' },
        redis: { status: 'unhealthy' },
        detection_model: { status: 'unknown' },
      },
    };

    const summary = selectHealthSummary(health);

    expect(summary.status).toBe('degraded');
    expect(summary.serviceCount).toBe(3);
    expect(summary.healthyServiceCount).toBe(1);
  });
});

describe('selectRiskDistribution', () => {
  it('should calculate risk distribution with percentages', () => {
    const stats = {
      total_events: 100,
      events_by_risk_level: { critical: 0, high: 10, low: 60, medium: 30 },
      events_by_camera: [],
    };

    const distribution = selectRiskDistribution(stats);

    expect(distribution.low).toBe(60);
    expect(distribution.medium).toBe(30);
    expect(distribution.high).toBe(10);
    expect(distribution.lowPercent).toBe(60);
    expect(distribution.mediumPercent).toBe(30);
    expect(distribution.highPercent).toBe(10);
  });

  it('should handle zero total events without division by zero', () => {
    const stats = {
      total_events: 0,
      events_by_risk_level: { critical: 0, high: 0, low: 0, medium: 0 },
      events_by_camera: [],
    };

    const distribution = selectRiskDistribution(stats);

    expect(distribution.lowPercent).toBe(0);
    expect(distribution.mediumPercent).toBe(0);
    expect(distribution.highPercent).toBe(0);
  });
});

// ============================================================================
// AbortSignal Integration Tests (NEM-3411)
// ============================================================================

describe('withAbortSignal', () => {
  it('should pass abort signal to the fetch function', async () => {
    const mockFetch = vi.fn().mockResolvedValue([{ id: '1', name: 'Camera' }]);
    const wrappedFn = withAbortSignal(mockFetch);

    const controller = new AbortController();
    await wrappedFn({ signal: controller.signal });

    expect(mockFetch).toHaveBeenCalledWith({ signal: controller.signal });
  });

  it('should work with TanStack Query context shape', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ status: 'healthy' });
    const wrappedFn = withAbortSignal(mockFetch);

    const controller = new AbortController();
    const result = await wrappedFn({ signal: controller.signal });

    expect(result).toEqual({ status: 'healthy' });
  });
});

describe('createSignalAwareQueryFn', () => {
  it('should create a query function that passes signal to fetch', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ id: '123' });
    const queryFn = createSignalAwareQueryFn('/api/cameras/123', mockFetch);

    const controller = new AbortController();
    await queryFn({ signal: controller.signal });

    expect(mockFetch).toHaveBeenCalledWith('/api/cameras/123', { signal: controller.signal });
  });
});

// ============================================================================
// Parallel Queries Tests (NEM-3412)
// ============================================================================

describe('useDashboardQueries', () => {
  it('should fetch multiple queries in parallel', async () => {
    const mockCameras: Camera[] = [
      {
        id: '1',
        name: 'Camera 1',
        folder_path: '/cam1',
        status: 'online',
        last_seen_at: null,
        created_at: '2024-01-01',
      },
    ];

    const mockHealth = {
      status: 'healthy',
      timestamp: '2024-01-01T00:00:00Z',
      services: {},
    };

    const fetchCameras = vi.fn().mockResolvedValue(mockCameras);
    const fetchHealth = vi.fn().mockResolvedValue(mockHealth);

    const { result } = renderHook(
      () =>
        useDashboardQueries([
          {
            key: 'cameras',
            queryKey: ['cameras'],
            queryFn: fetchCameras,
          },
          {
            key: 'health',
            queryKey: ['health'],
            queryFn: fetchHealth,
          },
        ] as const),
      { wrapper: createWrapper() }
    );

    // Initially loading
    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Both queries should have been called
    expect(fetchCameras).toHaveBeenCalled();
    expect(fetchHealth).toHaveBeenCalled();

    // Data should be available
    expect(result.current.data.cameras).toEqual(mockCameras);
    expect(result.current.data.health).toEqual(mockHealth);
    expect(result.current.hasErrors).toBe(false);
  });

  it('should track errors per query', async () => {
    const successFetch = vi.fn().mockResolvedValue([{ id: '1' }]);
    const errorFetch = vi.fn().mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(
      () =>
        useDashboardQueries([
          {
            key: 'success',
            queryKey: ['success-query'],
            queryFn: successFetch,
          },
          {
            key: 'error',
            queryKey: ['error-query'],
            queryFn: errorFetch,
          },
        ] as const),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.hasErrors).toBe(true);
    expect(result.current.errors.error).toBeDefined();
    expect(result.current.errors.error?.message).toBe('Network error');
    expect(result.current.errors.success).toBeUndefined();
    expect(result.current.queries.success.isError).toBe(false);
    expect(result.current.queries.error.isError).toBe(true);
  });

  it('should support enabled option per query', async () => {
    const enabledFetch = vi.fn().mockResolvedValue([]);
    const disabledFetch = vi.fn().mockResolvedValue([]);

    const { result } = renderHook(
      () =>
        useDashboardQueries([
          {
            key: 'enabled',
            queryKey: ['enabled-query'],
            queryFn: enabledFetch,
            enabled: true,
          },
          {
            key: 'disabled',
            queryKey: ['disabled-query'],
            queryFn: disabledFetch,
            enabled: false,
          },
        ] as const),
      { wrapper: createWrapper() }
    );

    await waitFor(() => {
      expect(result.current.queries.enabled.isLoading).toBe(false);
    });

    // Only enabled query should have been called
    expect(enabledFetch).toHaveBeenCalled();
    expect(disabledFetch).not.toHaveBeenCalled();
  });
});

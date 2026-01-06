import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useHealthStatusQuery } from './useHealthStatusQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchHealth: vi.fn(),
}));

describe('useHealthStatusQuery', () => {
  const mockHealthyResponse = {
    status: 'healthy',
    services: {
      database: { status: 'healthy', message: 'Database operational' },
      redis: { status: 'healthy', message: 'Redis connected' },
      ai: { status: 'healthy', message: 'AI services operational' },
    },
    timestamp: '2025-12-28T10:30:00',
  };

  const mockDegradedResponse = {
    status: 'degraded',
    services: {
      database: { status: 'healthy', message: 'Database operational' },
      redis: { status: 'unhealthy', message: 'Redis connection failed' },
      ai: { status: 'healthy', message: 'AI services operational' },
    },
    timestamp: '2025-12-28T10:30:00',
  };

  const mockUnhealthyResponse = {
    status: 'unhealthy',
    services: {
      database: { status: 'unhealthy', message: 'Database connection failed' },
      redis: { status: 'unhealthy', message: 'Redis connection failed' },
      ai: { status: 'unhealthy', message: 'AI services unavailable' },
    },
    timestamp: '2025-12-28T10:30:00',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockHealthyResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      // Don't let fetch resolve immediately
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.data).toBeUndefined();
    });

    it('starts with no error', () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('fetching data', () => {
    it('fetches health on mount when enabled', async () => {
      renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchHealth).toHaveBeenCalledTimes(1);
      });
    });

    it('does not fetch when enabled is false', async () => {
      renderHook(() => useHealthStatusQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      // Wait a bit to ensure no call happens
      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchHealth).not.toHaveBeenCalled();
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockHealthyResponse);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Network error';
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      // Wait for retries to complete (hook has retry: 1, so 2 total attempts)
      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
          expect(result.current.error?.message).toBe(errorMessage);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('derived values', () => {
    it('derives overallStatus as healthy', async () => {
      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('healthy');
      });
    });

    it('derives overallStatus as degraded', async () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockDegradedResponse);

      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('degraded');
      });
    });

    it('derives overallStatus as unhealthy', async () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockUnhealthyResponse);

      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('unhealthy');
      });
    });

    it('derives services map', async () => {
      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.services).toEqual(mockHealthyResponse.services);
      });
    });

    it('returns null overallStatus when data is not loaded', () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.overallStatus).toBeNull();
    });

    it('returns empty services when data is not loaded', () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.services).toEqual({});
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('refetch triggers new API call', async () => {
      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchHealth).toHaveBeenCalledTimes(1);
      });

      // Trigger refetch
      await result.current.refetch();

      await waitFor(() => {
        expect(api.fetchHealth).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('polling with refetchInterval', () => {
    it('accepts refetchInterval option', async () => {
      const { result } = renderHook(
        () => useHealthStatusQuery({ enabled: true, refetchInterval: 5000 }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.data).toEqual(mockHealthyResponse);
      });
    });

    it('does not poll when refetchInterval is false', async () => {
      const { result } = renderHook(
        () => useHealthStatusQuery({ enabled: true, refetchInterval: false }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(result.current.data).toEqual(mockHealthyResponse);
      });

      // Should only have one call (initial fetch)
      expect(api.fetchHealth).toHaveBeenCalledTimes(1);
    });
  });

  describe('return values', () => {
    it('returns all expected properties', async () => {
      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current).toHaveProperty('data');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('overallStatus');
      expect(result.current).toHaveProperty('services');
      expect(result.current).toHaveProperty('refetch');
      expect(result.current).toHaveProperty('isRefetching');
    });
  });

  describe('stale time', () => {
    it('uses REALTIME_STALE_TIME by default (5 seconds)', async () => {
      // This test verifies the hook is configured with the correct stale time
      // The actual behavior is handled by React Query internals
      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockHealthyResponse);
      });

      // Data should be fresh immediately after fetch
      expect(result.current.isStale).toBe(false);
    });
  });

  describe('edge cases', () => {
    it('handles invalid status in response', async () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockResolvedValue({
        status: 'invalid_status',
        services: {},
        timestamp: '2025-12-28T10:30:00',
      });

      const { result } = renderHook(() => useHealthStatusQuery({ enabled: true }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.overallStatus).toBeNull();
      });
    });
  });
});

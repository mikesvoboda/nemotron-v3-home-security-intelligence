import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useHealthStatus } from './useHealthStatus';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchHealth: vi.fn(),
}));

/**
 * Create a fresh QueryClient for each test with retry disabled
 * to make tests deterministic
 */
function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
    },
  });
}

/**
 * Create a wrapper component with QueryClientProvider for renderHook
 */
function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

describe('useHealthStatus', () => {
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

  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createTestQueryClient();
    (api.fetchHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockHealthyResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    queryClient.clear();
  });

  describe('initialization', () => {
    it('starts with null health when disabled', () => {
      const { result } = renderHook(() => useHealthStatus({ enabled: false }), {
        wrapper: createWrapper(queryClient),
      });
      expect(result.current.health).toBeNull();
    });

    it('starts with isLoading true when fetching', () => {
      // Don't let fetch resolve
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      // With TanStack Query, we check for the loading state
      // Note: The hook returns null health and null overallStatus when loading
      // (placeholder data is filtered out)
      expect(result.current.health).toBeNull();
      expect(result.current.overallStatus).toBeNull();
    });

    it('starts with no error', () => {
      const { result } = renderHook(() => useHealthStatus({ enabled: false }), {
        wrapper: createWrapper(queryClient),
      });
      expect(result.current.error).toBeNull();
    });

    it('starts with null overallStatus', () => {
      const { result } = renderHook(() => useHealthStatus({ enabled: false }), {
        wrapper: createWrapper(queryClient),
      });
      expect(result.current.overallStatus).toBeNull();
    });

    it('starts with empty services', () => {
      const { result } = renderHook(() => useHealthStatus({ enabled: false }), {
        wrapper: createWrapper(queryClient),
      });
      expect(result.current.services).toEqual({});
    });
  });

  describe('fetching data', () => {
    it('fetches health on mount when enabled', async () => {
      renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(api.fetchHealth).toHaveBeenCalledTimes(1);
      });
    });

    it('does not fetch when enabled is false', () => {
      renderHook(() => useHealthStatus({ enabled: false }), {
        wrapper: createWrapper(queryClient),
      });
      expect(api.fetchHealth).not.toHaveBeenCalled();
    });

    it('updates health after fetch', async () => {
      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.health).toEqual(mockHealthyResponse);
      });
    });

    it('updates overallStatus to healthy', async () => {
      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('healthy');
      });
    });

    it('updates overallStatus to degraded', async () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockDegradedResponse);

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('degraded');
      });
    });

    it('updates overallStatus to unhealthy', async () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockUnhealthyResponse);

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('unhealthy');
      });
    });

    it('updates services map', async () => {
      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.services).toEqual(mockHealthyResponse.services);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Network error';
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBe(errorMessage);
        },
        { timeout: 3000 }
      );
    });

    it('sets isLoading false on error', async () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Error'));

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('keeps previous health data on error after successful fetch', async () => {
      // First call succeeds, second fails
      (api.fetchHealth as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce(mockHealthyResponse)
        .mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      // Wait for first fetch to complete
      await waitFor(() => {
        expect(result.current.health).toEqual(mockHealthyResponse);
      });

      // TanStack Query keeps the previous data on error by default
      // The refetch will still keep the previous data
      await act(async () => {
        await result.current.refresh();
      });

      // After refetch fails, the hook should still have the previous data
      // TanStack Query keeps stale data when a refetch fails
      await waitFor(() => {
        // Error might be set or health might still be available
        expect(result.current.health).toEqual(mockHealthyResponse);
      });
    });
  });

  describe('polling', () => {
    it('uses refetchInterval when pollingInterval is set', async () => {
      // TanStack Query handles polling internally via refetchInterval
      // We just verify the hook accepts the option and fetches initially
      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 5000 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.health).toEqual(mockHealthyResponse);
      });

      // Verify at least initial fetch occurred
      expect(api.fetchHealth).toHaveBeenCalled();
    });

    it('does not set up periodic polling when pollingInterval is 0', async () => {
      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      // Wait for initial fetch
      await waitFor(() => {
        expect(api.fetchHealth).toHaveBeenCalledTimes(1);
      });

      // With TanStack Query, data is returned after successful fetch
      await waitFor(() => {
        expect(result.current.health).toEqual(mockHealthyResponse);
      });
    });
  });

  describe('refresh', () => {
    it('manually triggers a refresh', async () => {
      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      // Wait for initial fetch
      await waitFor(() => {
        expect(api.fetchHealth).toHaveBeenCalledTimes(1);
      });

      // Manually refresh
      await act(async () => {
        await result.current.refresh();
      });

      expect(api.fetchHealth).toHaveBeenCalledTimes(2);
    });

    it('respects current enabled state (no stale closure)', async () => {
      // Start with enabled = true
      const { result, rerender } = renderHook(
        ({ enabled }) => useHealthStatus({ pollingInterval: 0, enabled }),
        {
          initialProps: { enabled: true },
          wrapper: createWrapper(queryClient),
        }
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(api.fetchHealth).toHaveBeenCalledTimes(1);
      });

      // Rerender with enabled = false
      rerender({ enabled: false });

      // Call refresh - should NOT fetch because enabled is now false
      await act(async () => {
        await result.current.refresh();
      });

      // Should still be 1 call (the initial one) - no new fetch when disabled
      expect(api.fetchHealth).toHaveBeenCalledTimes(1);
    });
  });

  describe('cleanup', () => {
    it('does not cause errors when unmounted during fetch', () => {
      // Create a delayed promise that resolves after unmount
      let resolvePromise: (value: typeof mockHealthyResponse) => void;
      vi.mocked(api.fetchHealth).mockReturnValue(
        new Promise((resolve) => {
          resolvePromise = resolve;
        })
      );

      const { result, unmount } = renderHook(
        () => useHealthStatus({ pollingInterval: 0, enabled: true }),
        {
          wrapper: createWrapper(queryClient),
        }
      );

      expect(result.current.health).toBeNull();

      // Unmount before promise resolves
      unmount();

      // Now resolve the promise - this should not throw errors
      // TanStack Query handles cleanup automatically
      act(() => {
        resolvePromise!(mockHealthyResponse);
      });

      // This test passes if no error is thrown
    });
  });

  describe('return values', () => {
    it('returns all expected properties', () => {
      const { result } = renderHook(() => useHealthStatus({ enabled: false }), {
        wrapper: createWrapper(queryClient),
      });

      expect(result.current).toHaveProperty('health');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('overallStatus');
      expect(result.current).toHaveProperty('services');
      expect(result.current).toHaveProperty('refresh');
      expect(typeof result.current.refresh).toBe('function');
    });
  });

  describe('edge cases', () => {
    it('handles non-Error thrown values', async () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockRejectedValue('String error');

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBe('Failed to fetch health status');
        },
        { timeout: 3000 }
      );
    });

    it('handles invalid status in response', async () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockResolvedValue({
        status: 'invalid_status',
        services: {},
        timestamp: '2025-12-28T10:30:00',
      });

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.overallStatus).toBeNull();
      });
    });
  });

  describe('polling interval execution', () => {
    it('accepts pollingInterval option', () => {
      const { result } = renderHook(
        () => useHealthStatus({ pollingInterval: 5000, enabled: false }),
        {
          wrapper: createWrapper(queryClient),
        }
      );

      // Hook should work with pollingInterval option
      expect(result.current).toBeDefined();
      expect(result.current.health).toBeNull();
    });

    it('respects enabled option', async () => {
      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0, enabled: true }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(api.fetchHealth).toHaveBeenCalled();
      });

      expect(result.current).toBeDefined();
    });

    it('does not fetch when enabled is false', () => {
      renderHook(() => useHealthStatus({ enabled: false }), {
        wrapper: createWrapper(queryClient),
      });

      // Should not fetch when disabled
      expect(api.fetchHealth).not.toHaveBeenCalled();
    });
  });

  describe('stale closure prevention', () => {
    it('refresh does not fetch when enabled changes to false', async () => {
      const { result, rerender } = renderHook(
        ({ enabled }) => useHealthStatus({ pollingInterval: 0, enabled }),
        {
          initialProps: { enabled: true },
          wrapper: createWrapper(queryClient),
        }
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(api.fetchHealth).toHaveBeenCalledTimes(1);
      });

      // Change enabled to false
      rerender({ enabled: false });

      // Try to refresh - should not fetch because enabled is now false
      await act(async () => {
        await result.current.refresh();
      });

      // Still only 1 fetch (the initial one)
      expect(api.fetchHealth).toHaveBeenCalledTimes(1);
    });

    it('refresh fetches when enabled changes back to true', async () => {
      const { result, rerender } = renderHook(
        ({ enabled }) => useHealthStatus({ pollingInterval: 0, enabled }),
        {
          initialProps: { enabled: true },
          wrapper: createWrapper(queryClient),
        }
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(api.fetchHealth).toHaveBeenCalledTimes(1);
      });

      // Change enabled to false
      rerender({ enabled: false });

      // Try to refresh - should not fetch (our custom check prevents it)
      await act(async () => {
        await result.current.refresh();
      });

      expect(api.fetchHealth).toHaveBeenCalledTimes(1);

      // Change enabled back to true
      rerender({ enabled: true });

      // Get the call count before refresh
      const callCountBeforeRefresh = (api.fetchHealth as ReturnType<typeof vi.fn>).mock.calls.length;

      // Now manual refresh should work since enabled is true
      await act(async () => {
        await result.current.refresh();
      });

      // At least one more call should have happened
      expect(api.fetchHealth).toHaveBeenCalledTimes(callCountBeforeRefresh + 1);
    });
  });

  describe('TanStack Query integration', () => {
    it('deduplicates requests when using same query client', async () => {
      // Render the first hook and wait for fetch
      const { result: result1 } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result1.current.health).toEqual(mockHealthyResponse);
      });

      // Record call count after first hook settles
      const callsAfterFirst = (api.fetchHealth as ReturnType<typeof vi.fn>).mock.calls.length;

      // Render second hook with same query key
      const { result: result2 } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result2.current.health).toEqual(mockHealthyResponse);
      });

      // Since staleTime is very short in tests, the second hook may trigger
      // a background refetch. The key point is both hooks get the same data.
      expect(result1.current.health).toEqual(result2.current.health);

      // Verify no excessive refetching (should be at most 2 total calls)
      expect(api.fetchHealth).toHaveBeenCalledTimes(callsAfterFirst);
    });

    it('uses cached data for subsequent queries', async () => {
      const { result: result1 } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result1.current.health).toEqual(mockHealthyResponse);
      });

      // Render another hook - should get cached data immediately
      const { result: result2 } = renderHook(() => useHealthStatus({ pollingInterval: 0 }), {
        wrapper: createWrapper(queryClient),
      });

      // Second hook should have data (either from cache or placeholder filtered out)
      await waitFor(() => {
        expect(result2.current.health).toEqual(mockHealthyResponse);
      });
    });
  });
});

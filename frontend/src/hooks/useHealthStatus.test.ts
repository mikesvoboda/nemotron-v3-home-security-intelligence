import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useHealthStatus } from './useHealthStatus';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchHealth: vi.fn(),
}));

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

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockHealthyResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with null health when disabled', () => {
      const { result } = renderHook(() => useHealthStatus({ enabled: false }));
      expect(result.current.health).toBeNull();
    });

    it('starts with isLoading true', () => {
      // Don't let fetch resolve
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));
      expect(result.current.isLoading).toBe(true);
    });

    it('starts with no error', () => {
      const { result } = renderHook(() => useHealthStatus({ enabled: false }));
      expect(result.current.error).toBeNull();
    });

    it('starts with null overallStatus', () => {
      const { result } = renderHook(() => useHealthStatus({ enabled: false }));
      expect(result.current.overallStatus).toBeNull();
    });

    it('starts with empty services', () => {
      const { result } = renderHook(() => useHealthStatus({ enabled: false }));
      expect(result.current.services).toEqual({});
    });
  });

  describe('fetching data', () => {
    it('fetches health on mount when enabled', async () => {
      renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(api.fetchHealth).toHaveBeenCalledTimes(1);
      });
    });

    it('does not fetch when enabled is false', () => {
      renderHook(() => useHealthStatus({ enabled: false }));
      expect(api.fetchHealth).not.toHaveBeenCalled();
    });

    it('updates health after fetch', async () => {
      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.health).toEqual(mockHealthyResponse);
      });
    });

    it('updates overallStatus to healthy', async () => {
      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('healthy');
      });
    });

    it('updates overallStatus to degraded', async () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockDegradedResponse);

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('degraded');
      });
    });

    it('updates overallStatus to unhealthy', async () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockResolvedValue(mockUnhealthyResponse);

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.overallStatus).toBe('unhealthy');
      });
    });

    it('updates services map', async () => {
      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.services).toEqual(mockHealthyResponse.services);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Network error';
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.error).toBe(errorMessage);
      });
    });

    it('sets isLoading false on error', async () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Error'));

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('keeps previous health data on error after successful fetch', async () => {
      // First call succeeds, second fails
      (api.fetchHealth as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce(mockHealthyResponse)
        .mockRejectedValueOnce(new Error('Network error'));

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      // Wait for first fetch to complete
      await waitFor(() => {
        expect(result.current.health).toEqual(mockHealthyResponse);
      });

      // Manually trigger refresh (which will fail)
      await act(async () => {
        await result.current.refresh().catch(() => {});
      });

      // Error should be set but previous health data preserved
      await waitFor(() => {
        expect(result.current.error).toBe('Network error');
      });

      expect(result.current.health).toEqual(mockHealthyResponse);
    });
  });

  describe('polling', () => {
    it('sets up polling interval when enabled', async () => {
      const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');

      renderHook(() => useHealthStatus({ pollingInterval: 5000 }));

      // Wait for effect to run
      await waitFor(() => {
        expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 5000);
      });

      setIntervalSpy.mockRestore();
    });

    it('does not set up polling when pollingInterval is 0', async () => {
      const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');

      renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      // Wait for initial fetch
      await waitFor(() => {
        expect(api.fetchHealth).toHaveBeenCalledTimes(1);
      });

      // setInterval may be called by waitFor internally with value 50
      // but our hook should not call it with our polling interval
      const pollCalls = setIntervalSpy.mock.calls.filter((call) => {
        // Our hook uses the pollingInterval (which would be positive)
        // waitFor uses 50ms internally
        const interval = call[1] as number;
        return interval !== 50;
      });
      expect(pollCalls).toHaveLength(0);

      setIntervalSpy.mockRestore();
    });
  });

  describe('refresh', () => {
    it('manually triggers a refresh', async () => {
      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

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
  });

  describe('cleanup', () => {
    it('clears interval on unmount', async () => {
      const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');

      const { unmount } = renderHook(() => useHealthStatus({ pollingInterval: 5000 }));

      // Wait for initial fetch
      await waitFor(() => {
        expect(api.fetchHealth).toHaveBeenCalledTimes(1);
      });

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();
      clearIntervalSpy.mockRestore();
    });

    it('does not update state after unmount', () => {
      // Create a delayed promise that resolves after unmount
      let resolvePromise: (value: typeof mockHealthyResponse) => void;
      vi.mocked(api.fetchHealth).mockReturnValue(
        new Promise((resolve) => {
          resolvePromise = resolve;
        })
      );

      const { result, unmount } = renderHook(() =>
        useHealthStatus({ pollingInterval: 0, enabled: true })
      );

      expect(result.current.health).toBeNull();

      // Unmount before promise resolves
      unmount();

      // Now resolve the promise - this should not throw errors
      act(() => {
        resolvePromise!(mockHealthyResponse);
      });

      // This test passes if no error is thrown
    });
  });

  describe('return values', () => {
    it('returns all expected properties', () => {
      const { result } = renderHook(() => useHealthStatus({ enabled: false }));

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

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.error).toBe('Failed to fetch health status');
      });
    });

    it('handles invalid status in response', async () => {
      (api.fetchHealth as ReturnType<typeof vi.fn>).mockResolvedValue({
        status: 'invalid_status',
        services: {},
        timestamp: '2025-12-28T10:30:00',
      });

      const { result } = renderHook(() => useHealthStatus({ pollingInterval: 0 }));

      await waitFor(() => {
        expect(result.current.overallStatus).toBeNull();
      });
    });
  });
});

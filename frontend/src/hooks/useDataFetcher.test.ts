import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useDataFetcher } from './useDataFetcher';

describe('useDataFetcher', () => {
  // Mock data for tests
  interface TestData {
    id: number;
    name: string;
  }

  const mockData: TestData = { id: 1, name: 'test' };
  const mockFetcher = vi.fn<() => Promise<TestData>>();

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetcher.mockResolvedValue(mockData);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initial state', () => {
    it('should start with isLoading true', () => {
      mockFetcher.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher })
      );

      expect(result.current.isLoading).toBe(true);
    });

    it('should start with data as undefined', () => {
      mockFetcher.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher })
      );

      expect(result.current.data).toBeUndefined();
    });

    it('should start with error as null', () => {
      mockFetcher.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher })
      );

      expect(result.current.error).toBeNull();
    });

    it('should start with status as loading', () => {
      mockFetcher.mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher })
      );

      expect(result.current.status).toBe('loading');
    });

    it('should not start fetching when enabled is false', () => {
      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher, enabled: false })
      );

      expect(mockFetcher).not.toHaveBeenCalled();
      expect(result.current.isLoading).toBe(false);
      expect(result.current.status).toBe('idle');
    });
  });

  describe('successful data fetching', () => {
    it('should fetch data on mount', async () => {
      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher })
      );

      await waitFor(() => {
        expect(result.current.data).toEqual(mockData);
      });

      expect(mockFetcher).toHaveBeenCalledTimes(1);
    });

    it('should set isLoading to false after successful fetch', async () => {
      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('should set status to success after successful fetch', async () => {
      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher })
      );

      await waitFor(() => {
        expect(result.current.status).toBe('success');
      });
    });

    it('should clear previous error on successful fetch', async () => {
      // First make it fail
      mockFetcher.mockRejectedValueOnce(new Error('First error'));

      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher, retryAttempts: 0 })
      );

      await waitFor(() => {
        expect(result.current.error).toBe('First error');
      });

      // Now make it succeed
      mockFetcher.mockResolvedValue(mockData);

      await act(async () => {
        await result.current.refetch();
      });

      await waitFor(() => {
        expect(result.current.error).toBeNull();
      });
    });
  });

  describe('error handling', () => {
    it('should set error message on fetch failure', async () => {
      const errorMessage = 'Network error';
      mockFetcher.mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher, retryAttempts: 0 })
      );

      await waitFor(() => {
        expect(result.current.error).toBe(errorMessage);
      });
    });

    it('should set status to error on fetch failure', async () => {
      mockFetcher.mockRejectedValue(new Error('Error'));

      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher, retryAttempts: 0 })
      );

      await waitFor(() => {
        expect(result.current.status).toBe('error');
      });
    });

    it('should set isLoading to false on error', async () => {
      mockFetcher.mockRejectedValue(new Error('Error'));

      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher, retryAttempts: 0 })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('should handle non-Error thrown values', async () => {
      mockFetcher.mockRejectedValue('String error');

      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher, retryAttempts: 0 })
      );

      await waitFor(() => {
        expect(result.current.error).toBe('An unknown error occurred');
      });
    });

    it('should preserve previous data on error', async () => {
      // First call succeeds
      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher, retryAttempts: 0 })
      );

      await waitFor(() => {
        expect(result.current.data).toEqual(mockData);
      });

      // Second call fails
      mockFetcher.mockRejectedValue(new Error('Error'));

      await act(async () => {
        await result.current.refetch();
      });

      await waitFor(() => {
        expect(result.current.error).not.toBeNull();
      });

      // Previous data should be preserved
      expect(result.current.data).toEqual(mockData);
    });
  });

  describe('retry logic', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('should retry on failure with exponential backoff', async () => {
      mockFetcher
        .mockRejectedValueOnce(new Error('First fail'))
        .mockRejectedValueOnce(new Error('Second fail'))
        .mockResolvedValue(mockData);

      renderHook(() =>
        useDataFetcher({
          fetcher: mockFetcher,
          retryAttempts: 3,
          retryDelay: 1000,
        })
      );

      // First attempt
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(1);

      // Advance to first retry (1000ms)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(2);

      // Advance to second retry (2000ms - exponential backoff)
      await act(async () => {
        await vi.advanceTimersByTimeAsync(2000);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(3);
    });

    it('should stop retrying after max attempts', async () => {
      mockFetcher.mockRejectedValue(new Error('Always fails'));

      const { result } = renderHook(() =>
        useDataFetcher({
          fetcher: mockFetcher,
          retryAttempts: 2,
          retryDelay: 100,
        })
      );

      // First attempt
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(1);

      // First retry
      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(2);

      // Second retry
      await act(async () => {
        await vi.advanceTimersByTimeAsync(200);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(3);

      // No more retries
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10000);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(3);
      expect(result.current.status).toBe('error');
    });

    it('should not retry when retryAttempts is 0', async () => {
      mockFetcher.mockRejectedValue(new Error('Error'));

      renderHook(() =>
        useDataFetcher({
          fetcher: mockFetcher,
          retryAttempts: 0,
        })
      );

      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(1);

      // Advance time - no retries should happen
      await act(async () => {
        await vi.advanceTimersByTimeAsync(10000);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(1);
    });
  });

  describe('abort controller cleanup', () => {
    it('should abort pending request when refetch is called', async () => {
      let resolveFirst: () => void;
      const firstPromise = new Promise<TestData>((resolve) => {
        resolveFirst = () => resolve(mockData);
      });

      mockFetcher.mockReturnValueOnce(firstPromise).mockResolvedValue({ ...mockData, id: 2 });

      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher })
      );

      // Start another request before the first completes
      act(() => {
        void result.current.refetch();
      });

      // Resolve first request (should be ignored due to abort)
      act(() => {
        resolveFirst!();
      });

      // Wait for second request to complete
      await waitFor(() => {
        expect(result.current.data?.id).toBe(2);
      });
    });
  });

  describe('polling support', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('should poll at specified interval', async () => {
      mockFetcher.mockResolvedValue(mockData);

      renderHook(() =>
        useDataFetcher({
          fetcher: mockFetcher,
          pollingInterval: 5000,
        })
      );

      // Initial fetch
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(1);

      // Advance to first poll
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(2);

      // Advance to second poll
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(3);
    });

    it('should not poll when pollingInterval is 0', async () => {
      mockFetcher.mockResolvedValue(mockData);

      renderHook(() =>
        useDataFetcher({
          fetcher: mockFetcher,
          pollingInterval: 0,
        })
      );

      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(1);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(1);
    });

    it('should not poll when enabled is false', async () => {
      const { rerender } = renderHook(
        ({ enabled }) =>
          useDataFetcher({
            fetcher: mockFetcher,
            pollingInterval: 1000,
            enabled,
          }),
        { initialProps: { enabled: true } }
      );

      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(1);

      // Disable polling
      rerender({ enabled: false });

      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
      // Should not have called again
      expect(mockFetcher).toHaveBeenCalledTimes(1);
    });

    it('should clear polling interval on unmount', async () => {
      const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');

      const { unmount } = renderHook(() =>
        useDataFetcher({
          fetcher: mockFetcher,
          pollingInterval: 5000,
        })
      );

      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(1);

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();
      clearIntervalSpy.mockRestore();
    });

    it('should pause polling on error when pauseOnError is true', async () => {
      mockFetcher
        .mockResolvedValueOnce(mockData)
        .mockRejectedValueOnce(new Error('Error'))
        .mockResolvedValue(mockData);

      renderHook(() =>
        useDataFetcher({
          fetcher: mockFetcher,
          pollingInterval: 1000,
          retryAttempts: 0,
          pausePollingOnError: true,
        })
      );

      // Initial fetch succeeds
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(1);

      // First poll fails
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1000);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(2);

      // Polling should be paused - no more calls
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(2);
    });
  });

  describe('refetch function', () => {
    it('should manually trigger a refetch', async () => {
      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher })
      );

      await waitFor(() => {
        expect(mockFetcher).toHaveBeenCalledTimes(1);
      });

      await act(async () => {
        await result.current.refetch();
      });

      expect(mockFetcher).toHaveBeenCalledTimes(2);
    });

    it('should set isLoading true during refetch', async () => {
      let resolveSecond: () => void;
      const secondPromise = new Promise<TestData>((resolve) => {
        resolveSecond = () => resolve({ ...mockData, id: 2 });
      });

      mockFetcher.mockResolvedValueOnce(mockData).mockReturnValueOnce(secondPromise);

      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      let refetchPromise: Promise<void>;
      act(() => {
        refetchPromise = result.current.refetch();
      });

      expect(result.current.isLoading).toBe(true);

      await act(async () => {
        resolveSecond!();
        await refetchPromise;
      });

      expect(result.current.isLoading).toBe(false);
    });

    it('should refetch even when enabled is false', async () => {
      const { result } = renderHook(() =>
        useDataFetcher({
          fetcher: mockFetcher,
          enabled: false,
        })
      );

      // Should not fetch automatically
      expect(mockFetcher).not.toHaveBeenCalled();

      // Manual refetch should work
      await act(async () => {
        await result.current.refetch();
      });

      expect(mockFetcher).toHaveBeenCalledTimes(1);
    });
  });

  describe('dependencies', () => {
    it('should refetch when dependencies change', async () => {
      const { rerender } = renderHook(
        ({ deps }) =>
          useDataFetcher({
            fetcher: mockFetcher,
            dependencies: deps,
          }),
        { initialProps: { deps: ['a'] } }
      );

      await waitFor(() => {
        expect(mockFetcher).toHaveBeenCalledTimes(1);
      });

      // Change dependencies
      rerender({ deps: ['b'] });

      await waitFor(() => {
        expect(mockFetcher).toHaveBeenCalledTimes(2);
      });
    });

    it('should not refetch when dependencies are the same', async () => {
      const deps = ['a', 'b'];

      const { rerender } = renderHook(
        ({ deps }) =>
          useDataFetcher({
            fetcher: mockFetcher,
            dependencies: deps,
          }),
        { initialProps: { deps } }
      );

      await waitFor(() => {
        expect(mockFetcher).toHaveBeenCalledTimes(1);
      });

      // Rerender with same dependencies (different array instance but same values)
      rerender({ deps: ['a', 'b'] });

      // Small delay to ensure no refetch happens
      await new Promise((r) => setTimeout(r, 50));

      // Should not trigger refetch (shallow comparison)
      expect(mockFetcher).toHaveBeenCalledTimes(1);
    });
  });

  describe('type safety', () => {
    it('should return data with correct type', async () => {
      const { result } = renderHook(() =>
        useDataFetcher<TestData>({ fetcher: mockFetcher })
      );

      await waitFor(() => {
        expect(result.current.data).toEqual(mockData);
      });

      // TypeScript should know data is TestData | undefined
      if (result.current.data) {
        expect(result.current.data.id).toBe(1);
        expect(result.current.data.name).toBe('test');
      }
    });
  });

  describe('return values', () => {
    it('should return all expected properties', () => {
      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher, enabled: false })
      );

      expect(result.current).toHaveProperty('data');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('status');
      expect(result.current).toHaveProperty('refetch');
      expect(typeof result.current.refetch).toBe('function');
    });
  });

  describe('cleanup on unmount', () => {
    it('should not update state after unmount', () => {
      // Create a delayed promise that resolves after unmount
      let resolvePromise: (value: TestData) => void;
      mockFetcher.mockReturnValue(
        new Promise((resolve) => {
          resolvePromise = resolve;
        })
      );

      const { result, unmount } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher })
      );

      expect(result.current.isLoading).toBe(true);

      // Unmount before promise resolves
      unmount();

      // Now resolve the promise - this should not throw errors
      act(() => {
        resolvePromise!(mockData);
      });

      // Test passes if no error is thrown (React warning about updating unmounted component)
    });

    it('should clear retry timeout on unmount', async () => {
      vi.useFakeTimers();
      const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout');
      mockFetcher.mockRejectedValue(new Error('Error'));

      const { unmount } = renderHook(() =>
        useDataFetcher({
          fetcher: mockFetcher,
          retryAttempts: 3,
          retryDelay: 10000,
        })
      );

      // Wait for initial fetch to fail
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(mockFetcher).toHaveBeenCalledTimes(1);

      unmount();

      expect(clearTimeoutSpy).toHaveBeenCalled();
      clearTimeoutSpy.mockRestore();
      vi.useRealTimers();
    });
  });

  describe('onSuccess callback', () => {
    it('should call onSuccess when fetch succeeds', async () => {
      const onSuccess = vi.fn();

      renderHook(() =>
        useDataFetcher({
          fetcher: mockFetcher,
          onSuccess,
        })
      );

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith(mockData);
      });
    });

    it('should not call onSuccess when fetch fails', async () => {
      const onSuccess = vi.fn();
      mockFetcher.mockRejectedValue(new Error('Error'));

      renderHook(() =>
        useDataFetcher({
          fetcher: mockFetcher,
          onSuccess,
          retryAttempts: 0,
        })
      );

      await waitFor(() => {
        expect(mockFetcher).toHaveBeenCalledTimes(1);
      });

      // Small delay to ensure callback isn't called
      await new Promise((resolve) => setTimeout(resolve, 50));

      expect(onSuccess).not.toHaveBeenCalled();
    });
  });

  describe('onError callback', () => {
    it('should call onError when fetch fails', async () => {
      const onError = vi.fn();
      const error = new Error('Test error');
      mockFetcher.mockRejectedValue(error);

      renderHook(() =>
        useDataFetcher({
          fetcher: mockFetcher,
          onError,
          retryAttempts: 0,
        })
      );

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(error);
      });
    });

    it('should not call onError when fetch succeeds', async () => {
      const onError = vi.fn();

      renderHook(() =>
        useDataFetcher({
          fetcher: mockFetcher,
          onError,
        })
      );

      await waitFor(() => {
        expect(mockFetcher).toHaveBeenCalledTimes(1);
      });

      expect(onError).not.toHaveBeenCalled();
    });
  });

  describe('stale while revalidate pattern', () => {
    it('should keep stale data while refetching', async () => {
      let resolveSecond: () => void;
      const secondPromise = new Promise<TestData>((resolve) => {
        resolveSecond = () => resolve({ id: 2, name: 'updated' });
      });

      mockFetcher.mockResolvedValueOnce(mockData).mockReturnValueOnce(secondPromise);

      const { result } = renderHook(() =>
        useDataFetcher({ fetcher: mockFetcher })
      );

      await waitFor(() => {
        expect(result.current.data).toEqual(mockData);
      });

      // Start refetch
      act(() => {
        void result.current.refetch();
      });

      // Data should still be available (stale)
      expect(result.current.data).toEqual(mockData);
      expect(result.current.isLoading).toBe(true);

      // Complete refetch
      act(() => {
        resolveSecond!();
      });

      await waitFor(() => {
        expect(result.current.data).toEqual({ id: 2, name: 'updated' });
      });
    });
  });
});

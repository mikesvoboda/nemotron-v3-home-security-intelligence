import { renderHook, waitFor, act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest';

import { usePolling } from './usePolling';

describe('usePolling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('initial fetch', () => {
    it('fetches data on mount', async () => {
      const mockData = { value: 42 };
      const fetcher = vi.fn().mockResolvedValue(mockData);

      const { result } = renderHook(() =>
        usePolling({
          fetcher,
          interval: 5000,
        })
      );

      expect(result.current.loading).toBe(true);
      expect(result.current.data).toBe(null);

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.data).toEqual(mockData);
      expect(result.current.error).toBe(null);
      expect(fetcher).toHaveBeenCalledTimes(1);
    });

    it('handles fetch error', async () => {
      const fetcher = vi.fn().mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() =>
        usePolling({
          fetcher,
          interval: 5000,
        })
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.data).toBe(null);
      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe('Network error');
    });

    it('handles non-Error rejection by wrapping in Error', async () => {
      const fetcher = vi.fn().mockRejectedValue('Unknown error');

      const { result } = renderHook(() =>
        usePolling({
          fetcher,
          interval: 5000,
        })
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe('Unknown error');
    });
  });

  describe('polling behavior', () => {
    it('polls at the specified interval', async () => {
      const mockData = { value: 42 };
      const fetcher = vi.fn().mockResolvedValue(mockData);

      renderHook(() =>
        usePolling({
          fetcher,
          interval: 5000,
          enabled: true,
        })
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetcher).toHaveBeenCalledTimes(1);
      });

      // Advance timer by 5 seconds
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      await waitFor(() => {
        expect(fetcher).toHaveBeenCalledTimes(2);
      });

      // Advance timer by another 5 seconds
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      await waitFor(() => {
        expect(fetcher).toHaveBeenCalledTimes(3);
      });
    });

    it('does not poll when enabled is false', async () => {
      const mockData = { value: 42 };
      const fetcher = vi.fn().mockResolvedValue(mockData);

      renderHook(() =>
        usePolling({
          fetcher,
          interval: 5000,
          enabled: false,
        })
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetcher).toHaveBeenCalledTimes(1);
      });

      // Advance timer by 10 seconds
      act(() => {
        vi.advanceTimersByTime(10000);
      });

      // Should still only have 1 call (no polling)
      expect(fetcher).toHaveBeenCalledTimes(1);
    });

    it('does not poll when interval is 0', async () => {
      const mockData = { value: 42 };
      const fetcher = vi.fn().mockResolvedValue(mockData);

      renderHook(() =>
        usePolling({
          fetcher,
          interval: 0,
          enabled: true,
        })
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetcher).toHaveBeenCalledTimes(1);
      });

      // Advance timer
      act(() => {
        vi.advanceTimersByTime(10000);
      });

      // Should still only have 1 call
      expect(fetcher).toHaveBeenCalledTimes(1);
    });

    it('does not poll when interval is negative', async () => {
      const mockData = { value: 42 };
      const fetcher = vi.fn().mockResolvedValue(mockData);

      renderHook(() =>
        usePolling({
          fetcher,
          interval: -1000,
          enabled: true,
        })
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetcher).toHaveBeenCalledTimes(1);
      });

      // Advance timer
      act(() => {
        vi.advanceTimersByTime(10000);
      });

      // Should still only have 1 call
      expect(fetcher).toHaveBeenCalledTimes(1);
    });

    it('stops polling on unmount', async () => {
      const mockData = { value: 42 };
      const fetcher = vi.fn().mockResolvedValue(mockData);

      const { unmount } = renderHook(() =>
        usePolling({
          fetcher,
          interval: 5000,
          enabled: true,
        })
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetcher).toHaveBeenCalledTimes(1);
      });

      // Unmount the hook
      unmount();

      // Advance timer
      act(() => {
        vi.advanceTimersByTime(10000);
      });

      // Should still only have 1 call
      expect(fetcher).toHaveBeenCalledTimes(1);
    });

    it('restarts polling when enabled changes from false to true', async () => {
      const mockData = { value: 42 };
      const fetcher = vi.fn().mockResolvedValue(mockData);

      const { rerender } = renderHook(
        ({ enabled }) =>
          usePolling({
            fetcher,
            interval: 5000,
            enabled,
          }),
        { initialProps: { enabled: false } }
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetcher).toHaveBeenCalledTimes(1);
      });

      // No polling should occur
      act(() => {
        vi.advanceTimersByTime(10000);
      });
      expect(fetcher).toHaveBeenCalledTimes(1);

      // Enable polling
      rerender({ enabled: true });

      // Advance timer
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      await waitFor(() => {
        expect(fetcher).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('callbacks', () => {
    it('calls onSuccess callback with data', async () => {
      const mockData = { value: 42 };
      const fetcher = vi.fn().mockResolvedValue(mockData);
      const onSuccess = vi.fn();

      renderHook(() =>
        usePolling({
          fetcher,
          interval: 5000,
          onSuccess,
        })
      );

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith(mockData);
      });
    });

    it('calls onError callback with error', async () => {
      const error = new Error('Network error');
      const fetcher = vi.fn().mockRejectedValue(error);
      const onError = vi.fn();

      renderHook(() =>
        usePolling({
          fetcher,
          interval: 5000,
          onError,
        })
      );

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith(error);
      });
    });

    it('calls onSuccess on subsequent poll success', async () => {
      const mockData = { value: 42 };
      const fetcher = vi.fn().mockResolvedValue(mockData);
      const onSuccess = vi.fn();

      renderHook(() =>
        usePolling({
          fetcher,
          interval: 5000,
          onSuccess,
        })
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledTimes(1);
      });

      // Advance timer to trigger poll
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('refetch', () => {
    it('provides refetch function that manually triggers fetch', async () => {
      const mockData = { value: 42 };
      const fetcher = vi.fn().mockResolvedValue(mockData);

      const { result } = renderHook(() =>
        usePolling({
          fetcher,
          interval: 5000,
          enabled: false,
        })
      );

      await waitFor(() => {
        expect(fetcher).toHaveBeenCalledTimes(1);
      });

      // Call refetch
      await act(async () => {
        await result.current.refetch();
      });

      expect(fetcher).toHaveBeenCalledTimes(2);
    });

    it('updates data when refetch succeeds', async () => {
      const mockData1 = { value: 42 };
      const mockData2 = { value: 100 };
      const fetcher = vi.fn().mockResolvedValueOnce(mockData1).mockResolvedValueOnce(mockData2);

      const { result } = renderHook(() =>
        usePolling({
          fetcher,
          interval: 5000,
          enabled: false,
        })
      );

      await waitFor(() => {
        expect(result.current.data).toEqual(mockData1);
      });

      // Call refetch
      await act(async () => {
        await result.current.refetch();
      });

      expect(result.current.data).toEqual(mockData2);
    });
  });

  describe('error clearing', () => {
    it('clears error on successful fetch', async () => {
      const mockData = { value: 42 };
      const fetcher = vi
        .fn()
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce(mockData);

      const { result } = renderHook(() =>
        usePolling({
          fetcher,
          interval: 5000,
          enabled: false,
        })
      );

      // Wait for error
      await waitFor(() => {
        expect(result.current.error?.message).toBe('Network error');
      });

      // Call refetch
      await act(async () => {
        await result.current.refetch();
      });

      // Error should be cleared
      expect(result.current.error).toBe(null);
      expect(result.current.data).toEqual(mockData);
    });
  });

  describe('type inference', () => {
    it('correctly infers data type from fetcher', async () => {
      interface MyData {
        id: number;
        name: string;
      }

      const mockData: MyData = { id: 1, name: 'Test' };
      const fetcher = vi.fn().mockResolvedValue(mockData);

      const { result } = renderHook(() =>
        usePolling<MyData>({
          fetcher,
          interval: 5000,
        })
      );

      await waitFor(() => {
        expect(result.current.loading).toBe(false);
      });

      // TypeScript should infer that data is MyData | null
      expect(result.current.data?.id).toBe(1);
      expect(result.current.data?.name).toBe('Test');
    });
  });

  describe('default values', () => {
    it('defaults enabled to true', async () => {
      const mockData = { value: 42 };
      const fetcher = vi.fn().mockResolvedValue(mockData);

      renderHook(() =>
        usePolling({
          fetcher,
          interval: 5000,
          // enabled not specified
        })
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetcher).toHaveBeenCalledTimes(1);
      });

      // Advance timer - should poll since enabled defaults to true
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      await waitFor(() => {
        expect(fetcher).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('stable callbacks', () => {
    it('does not restart polling when callbacks change reference', async () => {
      const mockData = { value: 42 };
      const fetcher = vi.fn().mockResolvedValue(mockData);
      const onSuccess = vi.fn();

      const { rerender } = renderHook(
        ({ onSuccessCallback }) =>
          usePolling({
            fetcher,
            interval: 5000,
            onSuccess: onSuccessCallback,
          }),
        {
          initialProps: {
            onSuccessCallback: onSuccess,
          },
        }
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(fetcher).toHaveBeenCalledTimes(1);
      });

      // Rerender with new callback reference
      rerender({
        onSuccessCallback: vi.fn(),
      });

      // Fetcher should not be called again due to callback change
      expect(fetcher).toHaveBeenCalledTimes(1);
    });
  });
});

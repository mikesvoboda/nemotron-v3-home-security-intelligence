import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useGpuHistory } from './useGpuHistory';
import * as api from '../services/api';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchGPUStats: vi.fn(),
}));

describe('useGpuHistory', () => {
  const mockGpuStats = {
    utilization: 50,
    memory_used: 12288,
    memory_total: 24576,
    temperature: 65,
    inference_fps: 30,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchGPUStats as ReturnType<typeof vi.fn>).mockResolvedValue(mockGpuStats);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with null current stats', () => {
      const { result } = renderHook(() => useGpuHistory({ autoStart: false }));
      expect(result.current.current).toBeNull();
    });

    it('starts with empty history', () => {
      const { result } = renderHook(() => useGpuHistory({ autoStart: false }));
      expect(result.current.history).toHaveLength(0);
    });

    it('starts with isLoading false', () => {
      const { result } = renderHook(() => useGpuHistory({ autoStart: false }));
      expect(result.current.isLoading).toBe(false);
    });

    it('starts with no error', () => {
      const { result } = renderHook(() => useGpuHistory({ autoStart: false }));
      expect(result.current.error).toBeNull();
    });
  });

  describe('auto-start polling', () => {
    it('fetches immediately when autoStart is true (default)', async () => {
      renderHook(() => useGpuHistory({ pollingInterval: 60000 })); // Long interval to prevent multiple calls

      await waitFor(() => {
        expect(api.fetchGPUStats).toHaveBeenCalledTimes(1);
      });
    });

    it('does not fetch when autoStart is false', () => {
      renderHook(() => useGpuHistory({ autoStart: false }));
      expect(api.fetchGPUStats).not.toHaveBeenCalled();
    });
  });

  describe('fetching data', () => {
    it('updates current stats after fetch', async () => {
      const { result } = renderHook(() => useGpuHistory({ pollingInterval: 60000 }));

      await waitFor(() => {
        expect(result.current.current).toEqual(mockGpuStats);
      });
    });

    it('adds data point to history after fetch', async () => {
      const { result } = renderHook(() => useGpuHistory({ pollingInterval: 60000 }));

      await waitFor(() => {
        expect(result.current.history).toHaveLength(1);
        expect(result.current.history[0].utilization).toBe(50);
        expect(result.current.history[0].memory_used).toBe(12288);
        expect(result.current.history[0].temperature).toBe(65);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Network error';
      (api.fetchGPUStats as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useGpuHistory({ pollingInterval: 60000 }));

      await waitFor(() => {
        expect(result.current.error).toBe(errorMessage);
      });
    });
  });

  describe('history management', () => {
    it('clearHistory removes all history', async () => {
      const { result } = renderHook(() => useGpuHistory({ pollingInterval: 60000 }));

      await waitFor(() => {
        expect(result.current.history).toHaveLength(1);
      });

      act(() => {
        result.current.clearHistory();
      });

      expect(result.current.history).toHaveLength(0);
    });

    it('limits history to maxDataPoints', async () => {
      // Mock multiple calls with different data
      const mockData = [
        { ...mockGpuStats, utilization: 10 },
        { ...mockGpuStats, utilization: 20 },
        { ...mockGpuStats, utilization: 30 },
        { ...mockGpuStats, utilization: 40 },
        { ...mockGpuStats, utilization: 50 },
      ];

      let callIndex = 0;
      // eslint-disable-next-line @typescript-eslint/no-misused-promises
      (api.fetchGPUStats as ReturnType<typeof vi.fn>).mockImplementation(() => {
        const data = mockData[Math.min(callIndex, mockData.length - 1)];
        callIndex++;
        return Promise.resolve(data);
      });

      const { result } = renderHook(() =>
        useGpuHistory({ pollingInterval: 60000, maxDataPoints: 3, autoStart: false })
      );

      // Manually trigger multiple fetches
      for (let i = 0; i < 5; i++) {
        act(() => {
          result.current.start();
        });
        await waitFor(() => {
          expect(api.fetchGPUStats).toHaveBeenCalledTimes(i + 1);
        });
        act(() => {
          result.current.stop();
        });
      }

      // Check that history is capped
      expect(result.current.history.length).toBeLessThanOrEqual(3);
    });
  });

  describe('start/stop controls', () => {
    it('stop prevents further polling', async () => {
      const { result, unmount } = renderHook(() => useGpuHistory({ pollingInterval: 60000 }));

      await waitFor(() => {
        expect(api.fetchGPUStats).toHaveBeenCalledTimes(1);
      });

      act(() => {
        result.current.stop();
      });

      // Unmount to ensure cleanup and no additional calls
      unmount();

      // Should still be 1 call
      expect(api.fetchGPUStats).toHaveBeenCalledTimes(1);
    });

    it('start enables polling when autoStart was false', async () => {
      const { result } = renderHook(() =>
        useGpuHistory({ autoStart: false, pollingInterval: 60000 })
      );

      expect(api.fetchGPUStats).not.toHaveBeenCalled();

      act(() => {
        result.current.start();
      });

      await waitFor(() => {
        expect(api.fetchGPUStats).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('null value handling', () => {
    it('handles null utilization by setting to 0', async () => {
      (api.fetchGPUStats as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ...mockGpuStats,
        utilization: null,
      });

      const { result } = renderHook(() => useGpuHistory({ pollingInterval: 60000 }));

      await waitFor(() => {
        expect(result.current.history).toHaveLength(1);
        expect(result.current.history[0].utilization).toBe(0);
      });
    });

    it('handles all null values - no history added', async () => {
      (api.fetchGPUStats as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        utilization: null,
        memory_used: null,
        memory_total: null,
        temperature: null,
        inference_fps: null,
      });

      const { result } = renderHook(() => useGpuHistory({ pollingInterval: 60000 }));

      await waitFor(() => {
        expect(result.current.current).not.toBeNull();
      });

      // History should not be added when all values are null
      expect(result.current.history).toHaveLength(0);
    });
  });

  describe('cleanup', () => {
    it('clears interval on unmount', async () => {
      const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');

      const { unmount } = renderHook(() => useGpuHistory({ pollingInterval: 60000 }));

      await waitFor(() => {
        expect(api.fetchGPUStats).toHaveBeenCalledTimes(1);
      });

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();
    });

    it('clears existing interval before creating new one on rapid toggle', async () => {
      const clearIntervalSpy = vi.spyOn(globalThis, 'clearInterval');

      const { result } = renderHook(() =>
        useGpuHistory({ autoStart: false, pollingInterval: 60000 })
      );

      // Rapidly toggle start/stop multiple times
      for (let i = 0; i < 5; i++) {
        act(() => {
          result.current.start();
        });
        act(() => {
          result.current.stop();
        });
      }

      // Start one final time
      act(() => {
        result.current.start();
      });

      await waitFor(() => {
        expect(api.fetchGPUStats).toHaveBeenCalled();
      });

      // clearInterval should have been called multiple times to clean up orphaned intervals
      // Each start() after the first should clear the previous interval
      expect(clearIntervalSpy.mock.calls.length).toBeGreaterThan(0);
    });

    it('prevents orphaned intervals during rapid isPolling toggles', async () => {
      vi.useFakeTimers({ shouldAdvanceTime: true });

      const { result, unmount } = renderHook(() =>
        useGpuHistory({ autoStart: false, pollingInterval: 1000 })
      );

      // Rapidly toggle start/stop
      act(() => {
        result.current.start();
      });
      act(() => {
        result.current.stop();
      });
      act(() => {
        result.current.start();
      });
      act(() => {
        result.current.stop();
      });
      act(() => {
        result.current.start();
      });

      // Wait for initial fetch
      await waitFor(() => {
        expect(api.fetchGPUStats).toHaveBeenCalled();
      });

      // Clear the call count
      vi.mocked(api.fetchGPUStats).mockClear();

      // Advance time by 5 seconds (5 polling intervals)
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      // If intervals were leaking, we would see more than 5 calls
      // With proper cleanup, we should see exactly 5 calls (once per second)
      await waitFor(() => {
        expect(api.fetchGPUStats).toHaveBeenCalledTimes(5);
      });

      unmount();
      vi.useRealTimers();
    });
  });

  describe('return values', () => {
    it('returns all expected properties', () => {
      const { result } = renderHook(() => useGpuHistory({ autoStart: false }));

      expect(result.current).toHaveProperty('current');
      expect(result.current).toHaveProperty('history');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('start');
      expect(result.current).toHaveProperty('stop');
      expect(result.current).toHaveProperty('clearHistory');
      expect(typeof result.current.start).toBe('function');
      expect(typeof result.current.stop).toBe('function');
      expect(typeof result.current.clearHistory).toBe('function');
    });
  });

  describe('polling interval', () => {
    it('accepts pollingInterval option', () => {
      const { result } = renderHook(() =>
        useGpuHistory({ pollingInterval: 1000, autoStart: false })
      );

      // Hook should work with pollingInterval option
      expect(result.current).toBeDefined();
      expect(result.current.history).toEqual([]);
    });

    it('respects autoStart false', () => {
      renderHook(() => useGpuHistory({ autoStart: false }));

      // Should not fetch when autoStart is false
      expect(api.fetchGPUStats).not.toHaveBeenCalled();
    });

    it('uses maxDataPoints option', () => {
      const { result } = renderHook(() => useGpuHistory({ maxDataPoints: 10, autoStart: false }));

      // Hook should work with maxDataPoints option
      expect(result.current).toBeDefined();
      expect(result.current.history).toEqual([]);
    });
  });
});

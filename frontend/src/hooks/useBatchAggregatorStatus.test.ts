/**
 * Tests for useBatchAggregatorStatus hook
 *
 * @see NEM-3872 - Batch Status Monitoring
 */

import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useBatchAggregatorStatus } from './useBatchAggregatorStatus';
import * as api from '../services/api';

import type { PipelineStatusResponse } from '../types/generated';

// Mock the API module
vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    fetchPipelineStatus: vi.fn(),
  };
});

const mockFetchPipelineStatus = vi.mocked(api.fetchPipelineStatus);

describe('useBatchAggregatorStatus', () => {
  const mockPipelineStatus: PipelineStatusResponse = {
    timestamp: '2026-01-26T10:00:00Z',
    batch_aggregator: {
      active_batches: 3,
      batch_window_seconds: 90,
      idle_timeout_seconds: 30,
      batches: [
        {
          batch_id: 'batch-1',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: Date.now() / 1000 - 45, // 45 seconds ago
          age_seconds: 45,
          last_activity_seconds: 10,
        },
        {
          batch_id: 'batch-2',
          camera_id: 'backyard',
          detection_count: 3,
          started_at: Date.now() / 1000 - 30, // 30 seconds ago
          age_seconds: 30,
          last_activity_seconds: 5,
        },
        {
          batch_id: 'batch-3',
          camera_id: 'driveway',
          detection_count: 8,
          started_at: Date.now() / 1000 - 60, // 60 seconds ago
          age_seconds: 60,
          last_activity_seconds: 15,
        },
      ],
    },
    file_watcher: null,
    degradation: null,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    mockFetchPipelineStatus.mockResolvedValue(mockPipelineStatus);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('initial state', () => {
    it('returns loading state initially', () => {
      const { result } = renderHook(() => useBatchAggregatorStatus());

      expect(result.current.isLoading).toBe(true);
      expect(result.current.error).toBeNull();
    });

    it('fetches pipeline status on mount', async () => {
      renderHook(() => useBatchAggregatorStatus());

      await waitFor(() => {
        expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('data extraction', () => {
    it('returns active batch count', async () => {
      const { result } = renderHook(() => useBatchAggregatorStatus());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.activeBatchCount).toBe(3);
    });

    it('returns batch window and idle timeout from config', async () => {
      const { result } = renderHook(() => useBatchAggregatorStatus());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.batchWindowSeconds).toBe(90);
      expect(result.current.idleTimeoutSeconds).toBe(30);
    });

    it('calculates average batch age', async () => {
      const { result } = renderHook(() => useBatchAggregatorStatus());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Average of 45, 30, 60 = 45
      expect(result.current.averageBatchAge).toBe(45);
    });

    it('calculates total detection count', async () => {
      const { result } = renderHook(() => useBatchAggregatorStatus());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 5 + 3 + 8 = 16
      expect(result.current.totalDetectionCount).toBe(16);
    });
  });

  describe('health indicators', () => {
    it('returns green health when average age is under 50% of window', async () => {
      // Average age 45, window 90 = 50%, threshold is 50%
      // Need lower age for green
      const lowAgeStatus = {
        ...mockPipelineStatus,
        batch_aggregator: {
          ...mockPipelineStatus.batch_aggregator!,
          batches: [
            {
              batch_id: 'batch-1',
              camera_id: 'front_door',
              detection_count: 5,
              started_at: Date.now() / 1000 - 20,
              age_seconds: 20,
              last_activity_seconds: 5,
            },
          ],
          active_batches: 1,
        },
      };
      mockFetchPipelineStatus.mockResolvedValue(lowAgeStatus);

      const { result } = renderHook(() => useBatchAggregatorStatus());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 20 / 90 = 22%, should be green
      expect(result.current.healthIndicator).toBe('green');
    });

    it('returns yellow health when average age is between 50% and 80% of window', async () => {
      const mediumAgeStatus = {
        ...mockPipelineStatus,
        batch_aggregator: {
          ...mockPipelineStatus.batch_aggregator!,
          batches: [
            {
              batch_id: 'batch-1',
              camera_id: 'front_door',
              detection_count: 5,
              started_at: Date.now() / 1000 - 60,
              age_seconds: 60,
              last_activity_seconds: 5,
            },
          ],
          active_batches: 1,
        },
      };
      mockFetchPipelineStatus.mockResolvedValue(mediumAgeStatus);

      const { result } = renderHook(() => useBatchAggregatorStatus());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 60 / 90 = 66%, should be yellow
      expect(result.current.healthIndicator).toBe('yellow');
    });

    it('returns red health when average age is over 80% of window', async () => {
      const highAgeStatus = {
        ...mockPipelineStatus,
        batch_aggregator: {
          ...mockPipelineStatus.batch_aggregator!,
          batches: [
            {
              batch_id: 'batch-1',
              camera_id: 'front_door',
              detection_count: 5,
              started_at: Date.now() / 1000 - 80,
              age_seconds: 80,
              last_activity_seconds: 5,
            },
          ],
          active_batches: 1,
        },
      };
      mockFetchPipelineStatus.mockResolvedValue(highAgeStatus);

      const { result } = renderHook(() => useBatchAggregatorStatus());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // 80 / 90 = 88%, should be red
      expect(result.current.healthIndicator).toBe('red');
    });

    it('returns green health when no active batches', async () => {
      const noActiveBatches = {
        ...mockPipelineStatus,
        batch_aggregator: {
          ...mockPipelineStatus.batch_aggregator!,
          batches: [],
          active_batches: 0,
        },
      };
      mockFetchPipelineStatus.mockResolvedValue(noActiveBatches);

      const { result } = renderHook(() => useBatchAggregatorStatus());

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.healthIndicator).toBe('green');
    });
  });

  describe('polling behavior', () => {
    it('polls when enabled is true', async () => {
      const { result } = renderHook(() =>
        useBatchAggregatorStatus({ enabled: true, pollingInterval: 5000 })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(1);

      // Advance time by polling interval
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      await waitFor(() => {
        expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(2);
      });
    });

    it('does not poll when enabled is false', async () => {
      const { result } = renderHook(() =>
        useBatchAggregatorStatus({ enabled: false, pollingInterval: 5000 })
      );

      // Should not fetch at all when disabled
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      // Initial fetch should be skipped
      expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(0);

      // Advance time by polling interval
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      // Should still be 0 calls
      expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(0);
    });

    it('stops polling when enabled changes to false', async () => {
      const { result, rerender } = renderHook(
        ({ enabled }) => useBatchAggregatorStatus({ enabled, pollingInterval: 5000 }),
        { initialProps: { enabled: true } }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(1);

      // Disable polling
      rerender({ enabled: false });

      // Advance time by polling interval
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      // Should not have polled again
      expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(1);
    });

    it('resumes polling when enabled changes to true', async () => {
      const { result, rerender } = renderHook(
        ({ enabled }) => useBatchAggregatorStatus({ enabled, pollingInterval: 5000 }),
        { initialProps: { enabled: false } }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(0);

      // Enable polling
      rerender({ enabled: true });

      await waitFor(() => {
        expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(1);
      });
    });

    it('uses custom polling interval', async () => {
      const { result } = renderHook(() =>
        useBatchAggregatorStatus({ enabled: true, pollingInterval: 10000 })
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(1);

      // Advance time by less than polling interval
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      // Should not have polled yet
      expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(1);

      // Advance to complete polling interval
      act(() => {
        vi.advanceTimersByTime(5000);
      });

      await waitFor(() => {
        expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('error handling', () => {
    it('handles API errors gracefully', async () => {
      mockFetchPipelineStatus.mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useBatchAggregatorStatus({ enabled: true }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBe('Network error');
    });

    it('handles non-Error objects', async () => {
      mockFetchPipelineStatus.mockRejectedValue('Unknown error');

      const { result } = renderHook(() => useBatchAggregatorStatus({ enabled: true }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.error).toBe('Failed to fetch batch status');
    });
  });

  describe('manual refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useBatchAggregatorStatus({ enabled: true }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('refetch triggers new API call', async () => {
      const { result } = renderHook(() => useBatchAggregatorStatus({ enabled: true }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(1);

      await act(async () => {
        await result.current.refetch();
      });

      expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(2);
    });
  });

  describe('null batch_aggregator', () => {
    it('handles null batch_aggregator gracefully', async () => {
      mockFetchPipelineStatus.mockResolvedValue({
        timestamp: '2026-01-26T10:00:00Z',
        batch_aggregator: null,
        file_watcher: null,
        degradation: null,
      });

      const { result } = renderHook(() => useBatchAggregatorStatus({ enabled: true }));

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.activeBatchCount).toBe(0);
      expect(result.current.batchWindowSeconds).toBe(0);
      expect(result.current.idleTimeoutSeconds).toBe(0);
      expect(result.current.averageBatchAge).toBe(0);
      expect(result.current.totalDetectionCount).toBe(0);
      expect(result.current.healthIndicator).toBe('green');
    });
  });
});

/**
 * Integration Tests for useCameraBaselineQuery Hooks
 *
 * Tests real-world hook behavior including:
 * - Hook → API integration
 * - Data transformation and caching
 * - Error handling and retry logic
 * - Query invalidation and refetching
 * - Stale time and cache behavior
 *
 * @see NEM-4914 - [TDD] Integration tests for Phase 2: Baseline Visualization
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import {
  useCameraBaselineQuery,
  useCameraActivityBaselineQuery,
  cameraBaselineQueryKeys,
} from './useCameraBaselineQuery';
import * as api from '../services/api';

import type {
  BaselineSummaryResponse,
  ActivityBaselineResponse,
} from '../services/api';

// Mock the API module
vi.mock('../services/api', () => ({
  fetchCameraBaseline: vi.fn(),
  fetchCameraActivityBaseline: vi.fn(),
}));

/**
 * Creates a fresh QueryClient for each test.
 * This ensures test isolation by preventing cache contamination.
 */
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false, // Disable retries for predictable test behavior
        gcTime: 0, // Disable garbage collection to prevent cache persistence
      },
    },
  });

/**
 * Creates a QueryClientProvider wrapper for hook tests.
 */
const createWrapper = (queryClient: QueryClient) => {

  return ({ children }: { children: React.ReactNode }) => {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
};

describe('useCameraBaselineQuery Integration Tests', () => {
  const mockCameraId = 'front_door';

  const mockBaselineSummary: BaselineSummaryResponse = {
    camera_id: mockCameraId,
    camera_name: 'Front Door',
    baseline_established: '2026-01-01T00:00:00Z',
    data_points: 720,
    hourly_patterns: {
      '0': { avg_detections: 0.5, std_dev: 0.3, sample_count: 30 },
      '17': { avg_detections: 5.2, std_dev: 1.1, sample_count: 30 },
    },
    daily_patterns: {
      monday: { avg_detections: 45, peak_hour: 17, total_samples: 24 },
    },
    object_baselines: {
      person: { avg_hourly: 2.3, peak_hour: 17, total_detections: 550 },
    },
    current_deviation: {
      score: 1.8,
      interpretation: 'slightly_above_normal',
      contributing_factors: ['person_count_elevated'],
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCameraBaseline).mockResolvedValue(mockBaselineSummary);
  });

  describe('Hook → API Integration', () => {
    it('calls fetchCameraBaseline with correct camera ID', async () => {
      const queryClient = createTestQueryClient();

      renderHook(() => useCameraBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(api.fetchCameraBaseline).toHaveBeenCalledWith(mockCameraId);
      });
    });

    it('returns data from API in expected shape', async () => {
      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockBaselineSummary);
      });
    });

    it('transforms API response to hook interface', async () => {
      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.data).toBeDefined();
        expect(result.current.hasBaseline).toBe(true);
        expect(result.current.isLearning).toBe(false);
      });
    });
  });

  describe('Loading State Management', () => {
    it('returns loading state initially', () => {
      vi.mocked(api.fetchCameraBaseline).mockImplementation(() => new Promise(() => {}));

      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.data).toBeUndefined();
    });

    it('transitions from loading to success', async () => {
      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      // Initially loading
      expect(result.current.isLoading).toBe(true);

      // Wait for success
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockBaselineSummary);
    });
  });

  describe('Error Handling', () => {
    it('returns error on API failure', async () => {
      const errorMessage = 'Network error';
      vi.mocked(api.fetchCameraBaseline).mockRejectedValue(new Error(errorMessage));

      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );

      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe(errorMessage);
    });

    it('handles 404 camera not found', async () => {
      vi.mocked(api.fetchCameraBaseline).mockRejectedValue(new Error('Camera not found'));

      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );

      expect(result.current.error?.message).toBe('Camera not found');
    });
  });

  describe('Cache Behavior', () => {
    it('caches data correctly (no refetch on re-render)', async () => {
      const queryClient = createTestQueryClient();

      const { result, rerender } = renderHook(
        () => useCameraBaselineQuery(mockCameraId),
        {
          wrapper: createWrapper(queryClient),
        }
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.data).toEqual(mockBaselineSummary);
      });

      const initialCallCount = vi.mocked(api.fetchCameraBaseline).mock.calls.length;

      // Re-render hook
      rerender();

      // Should not refetch (data is cached)
      expect(vi.mocked(api.fetchCameraBaseline).mock.calls.length).toBe(initialCallCount);
      expect(result.current.data).toEqual(mockBaselineSummary);
    });

    it('invalidates cache when camera_id changes', async () => {
      const queryClient = createTestQueryClient();

      const { result, rerender } = renderHook(
        ({ cameraId }) => useCameraBaselineQuery(cameraId),
        {
          wrapper: createWrapper(queryClient),
          initialProps: { cameraId: mockCameraId },
        }
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.data).toEqual(mockBaselineSummary);
      });

      // Change camera ID
      const newCameraId = 'back_door';
      const newBaselineSummary: BaselineSummaryResponse = {
        ...mockBaselineSummary,
        camera_id: newCameraId,
        camera_name: 'Back Door',
      };
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue(newBaselineSummary);

      rerender({ cameraId: newCameraId });

      // Should fetch new data for new camera
      await waitFor(() => {
        expect(api.fetchCameraBaseline).toHaveBeenCalledWith(newCameraId);
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(newBaselineSummary);
      });
    });

    it('refetch function triggers new API call', async () => {
      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.data).toEqual(mockBaselineSummary);
      });

      const initialCallCount = vi.mocked(api.fetchCameraBaseline).mock.calls.length;

      // Update mock data
      const updatedSummary: BaselineSummaryResponse = {
        ...mockBaselineSummary,
        data_points: 1000,
      };
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue(updatedSummary);

      // Trigger refetch
      await result.current.refetch();

      // Should have called API again
      expect(vi.mocked(api.fetchCameraBaseline).mock.calls.length).toBe(initialCallCount + 1);

      await waitFor(() => {
        expect(result.current.data).toEqual(updatedSummary);
      });
    });
  });

  describe('Derived Values', () => {
    it('calculates hasBaseline correctly when data_points > 0', async () => {
      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.hasBaseline).toBe(true);
      });
    });

    it('calculates hasBaseline correctly when data_points = 0', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        data_points: 0,
      });

      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.hasBaseline).toBe(false);
      });
    });

    it('calculates isLearning correctly when baseline_established is null', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        baseline_established: null,
      });

      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLearning).toBe(true);
      });
    });

    it('calculates isLearning correctly when baseline_established exists', async () => {
      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLearning).toBe(false);
      });
    });
  });

  describe('Enabled Option', () => {
    it('does not fetch when enabled is false', async () => {
      const queryClient = createTestQueryClient();

      renderHook(() => useCameraBaselineQuery(mockCameraId, { enabled: false }), {
        wrapper: createWrapper(queryClient),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchCameraBaseline).not.toHaveBeenCalled();
    });

    it('does not fetch when cameraId is undefined', async () => {
      const queryClient = createTestQueryClient();

      renderHook(() => useCameraBaselineQuery(undefined), {
        wrapper: createWrapper(queryClient),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchCameraBaseline).not.toHaveBeenCalled();
    });

    it('fetches when enabled changes to true', async () => {
      const queryClient = createTestQueryClient();

      const { rerender } = renderHook(
        ({ enabled }) => useCameraBaselineQuery(mockCameraId, { enabled }),
        {
          wrapper: createWrapper(queryClient),
          initialProps: { enabled: false },
        }
      );

      // Initially disabled
      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchCameraBaseline).not.toHaveBeenCalled();

      // Enable the query
      rerender({ enabled: true });

      // Should fetch data
      await waitFor(() => {
        expect(api.fetchCameraBaseline).toHaveBeenCalledWith(mockCameraId);
      });
    });
  });
});

describe('useCameraActivityBaselineQuery Integration Tests', () => {
  const mockCameraId = 'front_door';

  const mockActivityBaseline: ActivityBaselineResponse = {
    camera_id: mockCameraId,
    entries: [
      { hour: 0, day_of_week: 0, avg_count: 0.5, sample_count: 30, is_peak: false },
      { hour: 17, day_of_week: 4, avg_count: 5.2, sample_count: 30, is_peak: true },
      { hour: 8, day_of_week: 1, avg_count: 3.1, sample_count: 25, is_peak: false },
    ],
    total_samples: 720,
    peak_hour: 17,
    peak_day: 4,
    learning_complete: true,
    min_samples_required: 10,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCameraActivityBaseline).mockResolvedValue(mockActivityBaseline);
  });

  describe('Hook → API Integration', () => {
    it('calls fetchCameraActivityBaseline with correct camera ID', async () => {
      const queryClient = createTestQueryClient();

      renderHook(() => useCameraActivityBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(api.fetchCameraActivityBaseline).toHaveBeenCalledWith(mockCameraId);
      });
    });

    it('returns data from API in expected shape', async () => {
      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraActivityBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockActivityBaseline);
      });
    });

    it('extracts entries array from response', async () => {
      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraActivityBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.entries).toEqual(mockActivityBaseline.entries);
      });
    });

    it('extracts learningComplete flag from response', async () => {
      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraActivityBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.learningComplete).toBe(true);
      });
    });

    it('extracts minSamplesRequired from response', async () => {
      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraActivityBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.minSamplesRequired).toBe(10);
      });
    });
  });

  describe('Loading State Management', () => {
    it('returns loading state initially', () => {
      vi.mocked(api.fetchCameraActivityBaseline).mockImplementation(() => new Promise(() => {}));

      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraActivityBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.entries).toEqual([]);
    });

    it('transitions from loading to success', async () => {
      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraActivityBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      // Initially loading
      expect(result.current.isLoading).toBe(true);

      // Wait for success
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.entries).toEqual(mockActivityBaseline.entries);
    });
  });

  describe('Error Handling', () => {
    it('returns error on API failure', async () => {
      const errorMessage = 'Network error';
      vi.mocked(api.fetchCameraActivityBaseline).mockRejectedValue(new Error(errorMessage));

      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraActivityBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );

      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe(errorMessage);
    });
  });

  describe('Cache Behavior', () => {
    it('caches data correctly (no refetch on re-render)', async () => {
      const queryClient = createTestQueryClient();

      const { result, rerender } = renderHook(
        () => useCameraActivityBaselineQuery(mockCameraId),
        {
          wrapper: createWrapper(queryClient),
        }
      );

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.entries).toEqual(mockActivityBaseline.entries);
      });

      const initialCallCount = vi.mocked(api.fetchCameraActivityBaseline).mock.calls.length;

      // Re-render hook
      rerender();

      // Should not refetch (data is cached)
      expect(vi.mocked(api.fetchCameraActivityBaseline).mock.calls.length).toBe(initialCallCount);
      expect(result.current.entries).toEqual(mockActivityBaseline.entries);
    });
  });

  describe('Query Key Management', () => {
    it('uses correct query key format', () => {
      const expectedKey = cameraBaselineQueryKeys.activity(mockCameraId);
      expect(expectedKey).toEqual(['cameras', 'baseline', 'activity', mockCameraId]);
    });

    it('invalidates correctly with query key', async () => {
      const queryClient = createTestQueryClient();

      const { result } = renderHook(() => useCameraActivityBaselineQuery(mockCameraId), {
        wrapper: createWrapper(queryClient),
      });

      // Wait for initial fetch
      await waitFor(() => {
        expect(result.current.entries).toEqual(mockActivityBaseline.entries);
      });

      const initialCallCount = vi.mocked(api.fetchCameraActivityBaseline).mock.calls.length;

      // Invalidate the query
      await queryClient.invalidateQueries({
        queryKey: cameraBaselineQueryKeys.activity(mockCameraId),
      });

      // Should refetch
      await waitFor(() => {
        expect(vi.mocked(api.fetchCameraActivityBaseline).mock.calls.length).toBeGreaterThan(
          initialCallCount
        );
      });
    });
  });
});

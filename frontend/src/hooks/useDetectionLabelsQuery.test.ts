/**
 * Tests for useDetectionLabelsQuery hook
 *
 * This hook uses TanStack Query to fetch available detection labels with counts.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useDetectionLabelsQuery,
  detectionLabelsKeys,
} from './useDetectionLabelsQuery';
import * as api from '../services/api';
import { createQueryClient, queryKeys } from '../services/queryClient';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { DetectionLabelsResponse } from '../types/generated';
import type { QueryClient } from '@tanstack/react-query';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const originalModule = await importOriginal<typeof api>();
  return {
    ...originalModule,
    fetchDetectionLabels: vi.fn(),
  };
});

describe('useDetectionLabelsQuery', () => {
  let queryClient: QueryClient;

  const mockLabelsResponse: DetectionLabelsResponse = {
    labels: [
      { label: 'person', count: 150 },
      { label: 'car', count: 75 },
      { label: 'dog', count: 30 },
      { label: 'bicycle', count: 12 },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createQueryClient();
    (api.fetchDetectionLabels as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockLabelsResponse
    );
  });

  afterEach(() => {
    queryClient.clear();
    vi.restoreAllMocks();
  });

  describe('query key factory', () => {
    it('uses centralized query keys', () => {
      expect(detectionLabelsKeys.all).toEqual(queryKeys.detections.labels);
    });

    it('has correct key structure', () => {
      expect(detectionLabelsKeys.all).toEqual(['detections', 'labels']);
    });
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchDetectionLabels as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchDetectionLabels as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.data).toBeUndefined();
    });

    it('starts with empty labels array', () => {
      (api.fetchDetectionLabels as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.labels).toEqual([]);
    });
  });

  describe('fetching data', () => {
    it('fetches labels on mount', async () => {
      renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(api.fetchDetectionLabels).toHaveBeenCalledTimes(1);
      });
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockLabelsResponse);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('derives labels array correctly', async () => {
      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.labels).toEqual(mockLabelsResponse.labels);
      });
    });

    it('calculates totalDetections correctly', async () => {
      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        // 150 + 75 + 30 + 12 = 267
        expect(result.current.totalDetections).toBe(267);
      });
    });

    it('calculates labelCount correctly', async () => {
      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.labelCount).toBe(4);
      });
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useDetectionLabelsQuery({ enabled: false }), {
        wrapper: createQueryWrapper(queryClient),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchDetectionLabels).not.toHaveBeenCalled();
    });

    it('fetches when enabled becomes true', async () => {
      const { result, rerender } = renderHook(
        ({ enabled }) => useDetectionLabelsQuery({ enabled }),
        {
          initialProps: { enabled: false },
          wrapper: createQueryWrapper(queryClient),
        }
      );

      expect(api.fetchDetectionLabels).not.toHaveBeenCalled();

      rerender({ enabled: true });

      await waitFor(() => {
        expect(result.current.labels.length).toBeGreaterThan(0);
      });
    });
  });

  describe('error handling', () => {
    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch labels';
      (api.fetchDetectionLabels as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
        },
        { timeout: 5000 }
      );
    });

    it('sets isError flag on failure', async () => {
      (api.fetchDetectionLabels as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('API Error')
      );

      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );
    });

    it('returns empty labels array on error', async () => {
      (api.fetchDetectionLabels as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('API Error')
      );

      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );

      expect(result.current.labels).toEqual([]);
      expect(result.current.totalDetections).toBe(0);
    });
  });

  describe('empty labels', () => {
    it('handles empty labels response', async () => {
      (api.fetchDetectionLabels as ReturnType<typeof vi.fn>).mockResolvedValue({
        labels: [],
      });

      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.labels).toEqual([]);
      expect(result.current.labelCount).toBe(0);
      expect(result.current.totalDetections).toBe(0);
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('refetch triggers new API call', async () => {
      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchDetectionLabels).toHaveBeenCalledTimes(1);

      await result.current.refetch();

      expect(api.fetchDetectionLabels).toHaveBeenCalledTimes(2);
    });
  });

  describe('refetchInterval option', () => {
    it('accepts refetchInterval option', () => {
      const { result } = renderHook(
        () => useDetectionLabelsQuery({ refetchInterval: 60000 }),
        {
          wrapper: createQueryWrapper(queryClient),
        }
      );

      expect(result.current.isLoading).toBe(true);
    });
  });

  describe('staleTime option', () => {
    it('accepts custom staleTime option', async () => {
      const { result } = renderHook(
        () => useDetectionLabelsQuery({ staleTime: 1000 }),
        {
          wrapper: createQueryWrapper(queryClient),
        }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.data).toEqual(mockLabelsResponse);
    });
  });

  describe('caching behavior', () => {
    it('uses cached data on subsequent renders', async () => {
      // First render
      const { result: result1 } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result1.current.labels.length).toBeGreaterThan(0);
      });

      expect(api.fetchDetectionLabels).toHaveBeenCalledTimes(1);

      // Second render with same queryClient - should use cache
      const { result: result2 } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Should immediately have data from cache
      expect(result2.current.labels).toEqual(mockLabelsResponse.labels);
      // Should not have made another API call (cache hit)
      expect(api.fetchDetectionLabels).toHaveBeenCalledTimes(1);
    });
  });

  describe('isFetching and isRefetching', () => {
    it('returns isFetching state', async () => {
      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Initially fetching
      expect(result.current.isFetching).toBe(true);

      await waitFor(() => {
        expect(result.current.isFetching).toBe(false);
      });
    });

    it('returns isRefetching state', async () => {
      const { result } = renderHook(() => useDetectionLabelsQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Initially not refetching (first fetch)
      expect(result.current.isRefetching).toBe(false);

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });
});

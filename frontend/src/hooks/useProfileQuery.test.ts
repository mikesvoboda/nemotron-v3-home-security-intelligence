/**
 * Tests for useProfileQuery hook
 *
 * This hook provides query functionality for fetching current profile status
 * from GET /api/debug/profile
 */

import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useProfileQuery } from './useProfileQuery';
import * as api from '../services/api';
import { createQueryClient } from '../services/queryClient';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { QueryClient } from '@tanstack/react-query';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const originalModule = await importOriginal<typeof api>();
  return {
    ...originalModule,
    fetchProfileStatus: vi.fn(),
  };
});

describe('useProfileQuery', () => {
  let queryClient: QueryClient;

  const mockIdleProfile = {
    status: 'idle' as const,
    is_profiling: false,
    started_at: null,
    elapsed_seconds: null,
    results: null,
  };

  const mockProfilingProfile = {
    status: 'profiling' as const,
    is_profiling: true,
    started_at: '2025-01-17T10:00:00Z',
    elapsed_seconds: 32,
    results: null,
  };

  const mockCompletedProfile = {
    status: 'completed' as const,
    is_profiling: false,
    started_at: '2025-01-17T10:00:00Z',
    elapsed_seconds: 45,
    results: {
      total_time: 45.0,
      top_functions: [
        {
          function_name: 'process_image',
          call_count: 1500,
          total_time: 15.5,
          cumulative_time: 20.3,
          percentage: 34.5,
        },
        {
          function_name: 'detect_objects',
          call_count: 1500,
          total_time: 10.2,
          cumulative_time: 12.1,
          percentage: 22.7,
        },
      ],
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createQueryClient();
    (api.fetchProfileStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockIdleProfile);
  });

  afterEach(() => {
    queryClient.clear();
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.fetchProfileStatus as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useProfileQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with undefined data', () => {
      (api.fetchProfileStatus as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useProfileQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.data).toBeUndefined();
    });
  });

  describe('fetching data', () => {
    it('fetches profile status on mount', async () => {
      renderHook(() => useProfileQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(api.fetchProfileStatus).toHaveBeenCalledTimes(1);
      });
    });

    it('updates data after successful fetch', async () => {
      const { result } = renderHook(() => useProfileQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.data).toEqual(mockIdleProfile);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useProfileQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('derives isProfiling correctly for idle state', async () => {
      const { result } = renderHook(() => useProfileQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isProfiling).toBe(false);
      });
    });

    it('derives isProfiling correctly for profiling state', async () => {
      (api.fetchProfileStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockProfilingProfile);

      const { result } = renderHook(() => useProfileQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isProfiling).toBe(true);
      });
    });

    it('derives elapsedSeconds correctly when profiling', async () => {
      (api.fetchProfileStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockProfilingProfile);

      const { result } = renderHook(() => useProfileQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.elapsedSeconds).toBe(32);
      });
    });

    it('derives results correctly when completed', async () => {
      (api.fetchProfileStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockCompletedProfile);

      const { result } = renderHook(() => useProfileQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.results).toEqual(mockCompletedProfile.results);
      });
    });

    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to fetch profile status';
      (api.fetchProfileStatus as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      const { result } = renderHook(() => useProfileQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useProfileQuery({ enabled: false }), {
        wrapper: createQueryWrapper(queryClient),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchProfileStatus).not.toHaveBeenCalled();
    });
  });

  describe('refetchInterval option', () => {
    it('accepts refetchInterval option', () => {
      const { result } = renderHook(() => useProfileQuery({ refetchInterval: 1000 }), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.isLoading).toBe(true);
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useProfileQuery(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });
  });
});

/**
 * Tests for useProfilingMutations hook
 *
 * This hook provides mutations for:
 * - POST /api/debug/profile/start - Start profiling
 * - POST /api/debug/profile/stop - Stop profiling and get results
 * - GET /api/debug/profile/download - Download .prof file
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useStartProfilingMutation,
  useStopProfilingMutation,
  useDownloadProfileMutation,
} from './useProfilingMutations';
import * as api from '../services/api';
import { createQueryClient, queryKeys } from '../services/queryClient';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { QueryClient } from '@tanstack/react-query';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const originalModule = await importOriginal<typeof api>();
  return {
    ...originalModule,
    startProfiling: vi.fn(),
    stopProfiling: vi.fn(),
    downloadProfile: vi.fn(),
  };
});

describe('useStartProfilingMutation', () => {
  let queryClient: QueryClient;

  const mockStartResponse = {
    status: 'profiling' as const,
    is_profiling: true,
    started_at: '2025-01-17T10:00:00Z',
    message: 'Profiling started',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createQueryClient();
    (api.startProfiling as ReturnType<typeof vi.fn>).mockResolvedValue(mockStartResponse);
  });

  afterEach(() => {
    queryClient.clear();
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isPending false', () => {
      const { result } = renderHook(() => useStartProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.isPending).toBe(false);
    });

    it('starts with null error', () => {
      const { result } = renderHook(() => useStartProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('start mutation', () => {
    it('calls startProfiling API', async () => {
      const { result } = renderHook(() => useStartProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.start();
      });

      expect(api.startProfiling).toHaveBeenCalledTimes(1);
    });

    it('returns response data after success', async () => {
      const { result } = renderHook(() => useStartProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      let startResult: typeof mockStartResponse | undefined;
      await act(async () => {
        startResult = await result.current.start();
      });

      expect(startResult).toEqual(mockStartResponse);
    });

    it('invalidates profile query after start', async () => {
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useStartProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.start();
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.debug.profile,
      });
    });

    it('sets error on failure', async () => {
      const errorMessage = 'Failed to start profiling';
      (api.startProfiling as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useStartProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await expect(result.current.start()).rejects.toThrow(errorMessage);
      });

      await waitFor(() => {
        expect(result.current.error).toBeInstanceOf(Error);
      });

      expect(result.current.error?.message).toBe(errorMessage);
    });
  });

  describe('reset', () => {
    it('provides reset function', () => {
      const { result } = renderHook(() => useStartProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(typeof result.current.reset).toBe('function');
    });
  });
});

describe('useStopProfilingMutation', () => {
  let queryClient: QueryClient;

  const mockStopResponse = {
    status: 'completed' as const,
    is_profiling: false,
    started_at: '2025-01-17T10:00:00Z',
    elapsed_seconds: 45,
    message: 'Profiling stopped',
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
      ],
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createQueryClient();
    (api.stopProfiling as ReturnType<typeof vi.fn>).mockResolvedValue(mockStopResponse);
  });

  afterEach(() => {
    queryClient.clear();
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isPending false', () => {
      const { result } = renderHook(() => useStopProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.isPending).toBe(false);
    });

    it('starts with undefined results', () => {
      const { result } = renderHook(() => useStopProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.results).toBeUndefined();
    });

    it('starts with null error', () => {
      const { result } = renderHook(() => useStopProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('stop mutation', () => {
    it('calls stopProfiling API', async () => {
      const { result } = renderHook(() => useStopProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.stop();
      });

      expect(api.stopProfiling).toHaveBeenCalledTimes(1);
    });

    it('returns response data after success', async () => {
      const { result } = renderHook(() => useStopProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      let stopResult: typeof mockStopResponse | undefined;
      await act(async () => {
        stopResult = await result.current.stop();
      });

      expect(stopResult).toEqual(mockStopResponse);
    });

    it('stores results after success', async () => {
      const { result } = renderHook(() => useStopProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.stop();
      });

      await waitFor(() => {
        expect(result.current.results).toEqual(mockStopResponse);
      });
    });

    it('invalidates profile query after stop', async () => {
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useStopProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.stop();
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.debug.profile,
      });
    });

    it('sets error on failure', async () => {
      const errorMessage = 'Failed to stop profiling';
      (api.stopProfiling as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useStopProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await expect(result.current.stop()).rejects.toThrow(errorMessage);
      });

      await waitFor(() => {
        expect(result.current.error).toBeInstanceOf(Error);
      });

      expect(result.current.error?.message).toBe(errorMessage);
    });
  });

  describe('reset', () => {
    it('provides reset function', () => {
      const { result } = renderHook(() => useStopProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(typeof result.current.reset).toBe('function');
    });

    it('clears results on reset', async () => {
      const { result } = renderHook(() => useStopProfilingMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.stop();
      });

      await waitFor(() => {
        expect(result.current.results).toEqual(mockStopResponse);
      });

      act(() => {
        result.current.reset();
      });

      await waitFor(() => {
        expect(result.current.results).toBeUndefined();
      });
    });
  });
});

describe('useDownloadProfileMutation', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = createQueryClient();
    // Mock downloadProfile to return a blob
    (api.downloadProfile as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Blob(['profile data'], { type: 'application/octet-stream' })
    );
  });

  afterEach(() => {
    queryClient.clear();
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isPending false', () => {
      const { result } = renderHook(() => useDownloadProfileMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.isPending).toBe(false);
    });

    it('starts with null error', () => {
      const { result } = renderHook(() => useDownloadProfileMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.error).toBeNull();
    });
  });

  describe('download mutation', () => {
    it('calls downloadProfile API', async () => {
      const { result } = renderHook(() => useDownloadProfileMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.download();
      });

      expect(api.downloadProfile).toHaveBeenCalledTimes(1);
    });

    it('sets error on failure', async () => {
      const errorMessage = 'Failed to download profile';
      (api.downloadProfile as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useDownloadProfileMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await expect(result.current.download()).rejects.toThrow(errorMessage);
      });

      await waitFor(() => {
        expect(result.current.error).toBeInstanceOf(Error);
      });

      expect(result.current.error?.message).toBe(errorMessage);
    });
  });

  describe('reset', () => {
    it('provides reset function', () => {
      const { result } = renderHook(() => useDownloadProfileMutation(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(typeof result.current.reset).toBe('function');
    });
  });
});

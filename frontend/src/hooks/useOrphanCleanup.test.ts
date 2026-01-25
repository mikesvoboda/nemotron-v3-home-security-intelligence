import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import { createElement } from 'react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import { useOrphanCleanup, DEFAULT_MIN_AGE_HOURS, DEFAULT_MAX_DELETE_GB } from './useOrphanCleanup';

// Mock the useOrphanCleanupMutation hook
const mockMutateAsync = vi.fn();
vi.mock('./useAdminMutations', () => ({
  useOrphanCleanupMutation: () => ({
    mutateAsync: mockMutateAsync,
    isPending: false,
    error: null,
  }),
}));

// Create a wrapper with QueryClient for the hook
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

// Mock response data
const mockResponse = {
  scanned_files: 1000,
  orphaned_files: 25,
  deleted_files: 25,
  deleted_bytes: 1500000000,
  deleted_bytes_formatted: '1.5 GB',
  failed_count: 0,
  failed_deletions: [],
  duration_seconds: 1.5,
  dry_run: true,
  skipped_young: 3,
  skipped_size_limit: 0,
};

describe('useOrphanCleanup', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMutateAsync.mockResolvedValue(mockResponse);
  });

  describe('initial state', () => {
    it('returns correct initial state', () => {
      const { result } = renderHook(() => useOrphanCleanup(), {
        wrapper: createWrapper(),
      });

      expect(result.current.isRunning).toBe(false);
      expect(result.current.result).toBeNull();
      expect(result.current.lastRunWasDryRun).toBeNull();
      expect(result.current.error).toBeNull();
      expect(typeof result.current.runCleanup).toBe('function');
      expect(typeof result.current.runPreview).toBe('function');
      expect(typeof result.current.clearResult).toBe('function');
    });
  });

  describe('runCleanup', () => {
    it('calls mutation with default parameters when none provided', async () => {
      const { result } = renderHook(() => useOrphanCleanup(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.runCleanup();
      });

      expect(mockMutateAsync).toHaveBeenCalledWith({
        dry_run: true,
        min_age_hours: DEFAULT_MIN_AGE_HOURS,
        max_delete_gb: DEFAULT_MAX_DELETE_GB,
      });
    });

    it('calls mutation with custom parameters', async () => {
      const { result } = renderHook(() => useOrphanCleanup(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.runCleanup({
          dryRun: false,
          minAgeHours: 48,
          maxDeleteGb: 5,
        });
      });

      expect(mockMutateAsync).toHaveBeenCalledWith({
        dry_run: false,
        min_age_hours: 48,
        max_delete_gb: 5,
      });
    });

    it('updates result state after successful cleanup', async () => {
      const { result } = renderHook(() => useOrphanCleanup(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.runCleanup({ dryRun: false });
      });

      expect(result.current.result).toEqual(mockResponse);
      expect(result.current.lastRunWasDryRun).toBe(false);
    });

    it('tracks dry_run correctly', async () => {
      const { result } = renderHook(() => useOrphanCleanup(), {
        wrapper: createWrapper(),
      });

      // First run with dry_run=true
      await act(async () => {
        await result.current.runCleanup({ dryRun: true });
      });
      expect(result.current.lastRunWasDryRun).toBe(true);

      // Second run with dry_run=false
      await act(async () => {
        await result.current.runCleanup({ dryRun: false });
      });
      expect(result.current.lastRunWasDryRun).toBe(false);
    });

    it('returns the cleanup response', async () => {
      const { result } = renderHook(() => useOrphanCleanup(), {
        wrapper: createWrapper(),
      });

      let response;
      await act(async () => {
        response = await result.current.runCleanup();
      });

      expect(response).toEqual(mockResponse);
    });

    it('throws on error', async () => {
      mockMutateAsync.mockRejectedValueOnce(new Error('Cleanup failed'));

      const { result } = renderHook(() => useOrphanCleanup(), {
        wrapper: createWrapper(),
      });

      await expect(
        act(async () => {
          await result.current.runCleanup();
        })
      ).rejects.toThrow('Cleanup failed');
    });
  });

  describe('runPreview', () => {
    it('always sets dry_run to true', async () => {
      const { result } = renderHook(() => useOrphanCleanup(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.runPreview({ minAgeHours: 72 });
      });

      expect(mockMutateAsync).toHaveBeenCalledWith({
        dry_run: true,
        min_age_hours: 72,
        max_delete_gb: DEFAULT_MAX_DELETE_GB,
      });
    });

    it('uses default parameters when none provided', async () => {
      const { result } = renderHook(() => useOrphanCleanup(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.runPreview();
      });

      expect(mockMutateAsync).toHaveBeenCalledWith({
        dry_run: true,
        min_age_hours: DEFAULT_MIN_AGE_HOURS,
        max_delete_gb: DEFAULT_MAX_DELETE_GB,
      });
    });

    it('updates lastRunWasDryRun to true', async () => {
      const { result } = renderHook(() => useOrphanCleanup(), {
        wrapper: createWrapper(),
      });

      await act(async () => {
        await result.current.runPreview();
      });

      expect(result.current.lastRunWasDryRun).toBe(true);
    });
  });

  describe('clearResult', () => {
    it('clears the result state', async () => {
      const { result } = renderHook(() => useOrphanCleanup(), {
        wrapper: createWrapper(),
      });

      // First run to set result
      await act(async () => {
        await result.current.runCleanup();
      });
      expect(result.current.result).not.toBeNull();

      // Clear result
      act(() => {
        result.current.clearResult();
      });

      expect(result.current.result).toBeNull();
      expect(result.current.lastRunWasDryRun).toBeNull();
    });
  });

  describe('constants', () => {
    it('exports correct default values', () => {
      expect(DEFAULT_MIN_AGE_HOURS).toBe(24);
      expect(DEFAULT_MAX_DELETE_GB).toBe(10);
    });
  });
});

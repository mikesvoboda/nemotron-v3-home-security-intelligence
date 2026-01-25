/**
 * Tests for useJobMutations hook (NEM-2712).
 *
 * Tests the job lifecycle mutation hook including:
 * - Cancel job (graceful stop)
 * - Abort job (force stop)
 * - Retry job (create new job from failed)
 * - Delete job (remove record)
 *
 * @see docs/development/testing-workflow.md for TDD patterns
 */
import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useJobMutations } from './useJobMutations';
import * as api from '../services/api';
import { queryKeys } from '../services/queryClient';
import { createTestQueryClient } from '../test/utils';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', () => ({
  cancelJob: vi.fn(),
  abortJob: vi.fn(),
  retryJob: vi.fn(),
  deleteJob: vi.fn(),
}));

describe('useJobMutations', () => {
  const mockCancelResponse = {
    job_id: 'job-123',
    message: 'Job cancellation requested',
    status: 'failed' as const,
  };

  const mockAbortResponse = {
    job_id: 'job-123',
    message: 'Job abort requested - worker notified',
    status: 'failed' as const,
  };

  const mockRetryResponse = {
    job_id: 'job-456',
    job_type: 'export',
    status: 'pending' as const,
    progress: 0,
    created_at: '2024-01-15T10:00:00Z',
  };

  const mockDeleteResponse = {
    job_id: 'job-123',
    message: 'Job deleted successfully',
    status: 'failed' as const,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.cancelJob).mockResolvedValue(mockCancelResponse);
    vi.mocked(api.abortJob).mockResolvedValue(mockAbortResponse);
    vi.mocked(api.retryJob).mockResolvedValue(mockRetryResponse);
    vi.mocked(api.deleteJob).mockResolvedValue(mockDeleteResponse);
  });

  describe('cancelJob', () => {
    it('calls API with correct job ID', async () => {
      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.cancelJob('job-123');
      });

      expect(api.cancelJob).toHaveBeenCalledWith('job-123');
    });

    it('returns cancel response on success', async () => {
      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      let response;
      await act(async () => {
        response = await result.current.cancelJob('job-123');
      });

      expect(response).toEqual(mockCancelResponse);
    });

    it('sets isCancelling to true during mutation', async () => {
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });
      vi.mocked(api.cancelJob).mockReturnValue(
        pendingPromise as Promise<typeof mockCancelResponse>
      );

      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Start the mutation without awaiting
      act(() => {
        void result.current.cancelJob('job-123');
      });

      await waitFor(() => {
        expect(result.current.isCancelling).toBe(true);
      });

      // Resolve the promise
      act(() => {
        resolvePromise!(mockCancelResponse);
      });

      await waitFor(() => {
        expect(result.current.isCancelling).toBe(false);
      });
    });

    it('invalidates jobs query on success', async () => {
      const queryClient = createTestQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.cancelJob('job-123');
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.jobs.all,
      });
    });

    it('calls onCancelSuccess callback when provided', async () => {
      const queryClient = createTestQueryClient();
      const onSuccess = vi.fn();
      const { result } = renderHook(() => useJobMutations({ onCancelSuccess: onSuccess }), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.cancelJob('job-123');
      });

      expect(onSuccess).toHaveBeenCalledWith(mockCancelResponse, 'job-123');
    });

    it('calls onCancelError callback when provided', async () => {
      const error = new Error('Cancel failed');
      vi.mocked(api.cancelJob).mockRejectedValue(error);

      // Create client without throwOnError so we can test error callbacks
      const queryClient = createTestQueryClient({
        defaultOptions: {
          mutations: { throwOnError: false, retry: false },
          queries: { retry: false },
        },
      });
      const onError = vi.fn();
      const { result } = renderHook(() => useJobMutations({ onCancelError: onError }), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        try {
          await result.current.cancelJob('job-123');
        } catch {
          // Error may still be thrown from mutateAsync
        }
      });

      expect(onError).toHaveBeenCalledWith(error, 'job-123');
    });
  });

  describe('abortJob', () => {
    it('calls API with correct job ID', async () => {
      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.abortJob('job-123');
      });

      expect(api.abortJob).toHaveBeenCalledWith('job-123');
    });

    it('returns abort response on success', async () => {
      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      let response;
      await act(async () => {
        response = await result.current.abortJob('job-123');
      });

      expect(response).toEqual(mockAbortResponse);
    });

    it('sets isAborting to true during mutation', async () => {
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });
      vi.mocked(api.abortJob).mockReturnValue(pendingPromise as Promise<typeof mockAbortResponse>);

      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      act(() => {
        void result.current.abortJob('job-123');
      });

      await waitFor(() => {
        expect(result.current.isAborting).toBe(true);
      });

      act(() => {
        resolvePromise!(mockAbortResponse);
      });

      await waitFor(() => {
        expect(result.current.isAborting).toBe(false);
      });
    });

    it('calls onAbortSuccess callback when provided', async () => {
      const queryClient = createTestQueryClient();
      const onSuccess = vi.fn();
      const { result } = renderHook(() => useJobMutations({ onAbortSuccess: onSuccess }), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.abortJob('job-123');
      });

      expect(onSuccess).toHaveBeenCalledWith(mockAbortResponse, 'job-123');
    });

    it('invalidates jobs query on success', async () => {
      const queryClient = createTestQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.abortJob('job-123');
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.jobs.all,
      });
    });
  });

  describe('retryJob', () => {
    it('calls API with correct job ID', async () => {
      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.retryJob('job-123');
      });

      expect(api.retryJob).toHaveBeenCalledWith('job-123');
    });

    it('returns new job response on success', async () => {
      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      let response;
      await act(async () => {
        response = await result.current.retryJob('job-123');
      });

      expect(response).toEqual(mockRetryResponse);
    });

    it('sets isRetrying to true during mutation', async () => {
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });
      vi.mocked(api.retryJob).mockReturnValue(pendingPromise as Promise<typeof mockRetryResponse>);

      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      act(() => {
        void result.current.retryJob('job-123');
      });

      await waitFor(() => {
        expect(result.current.isRetrying).toBe(true);
      });

      act(() => {
        resolvePromise!(mockRetryResponse);
      });

      await waitFor(() => {
        expect(result.current.isRetrying).toBe(false);
      });
    });

    it('calls onRetrySuccess callback with new job', async () => {
      const queryClient = createTestQueryClient();
      const onSuccess = vi.fn();
      const { result } = renderHook(() => useJobMutations({ onRetrySuccess: onSuccess }), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.retryJob('job-123');
      });

      expect(onSuccess).toHaveBeenCalledWith(mockRetryResponse, 'job-123');
    });

    it('invalidates jobs query on success', async () => {
      const queryClient = createTestQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.retryJob('job-123');
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.jobs.all,
      });
    });
  });

  describe('deleteJob', () => {
    it('calls API with correct job ID', async () => {
      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.deleteJob('job-123');
      });

      expect(api.deleteJob).toHaveBeenCalledWith('job-123');
    });

    it('returns delete response on success', async () => {
      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      let response;
      await act(async () => {
        response = await result.current.deleteJob('job-123');
      });

      expect(response).toEqual(mockDeleteResponse);
    });

    it('sets isDeleting to true during mutation', async () => {
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });
      vi.mocked(api.deleteJob).mockReturnValue(
        pendingPromise as Promise<typeof mockDeleteResponse>
      );

      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      act(() => {
        void result.current.deleteJob('job-123');
      });

      await waitFor(() => {
        expect(result.current.isDeleting).toBe(true);
      });

      act(() => {
        resolvePromise!(mockDeleteResponse);
      });

      await waitFor(() => {
        expect(result.current.isDeleting).toBe(false);
      });
    });

    it('calls onDeleteSuccess callback when provided', async () => {
      const queryClient = createTestQueryClient();
      const onSuccess = vi.fn();
      const { result } = renderHook(() => useJobMutations({ onDeleteSuccess: onSuccess }), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.deleteJob('job-123');
      });

      expect(onSuccess).toHaveBeenCalledWith(mockDeleteResponse, 'job-123');
    });

    it('invalidates jobs query on success', async () => {
      const queryClient = createTestQueryClient();
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      await act(async () => {
        await result.current.deleteJob('job-123');
      });

      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: queryKeys.jobs.all,
      });
    });
  });

  describe('reset', () => {
    it('resets all mutation states', async () => {
      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      // Execute a mutation first
      await act(async () => {
        await result.current.cancelJob('job-123');
      });

      // Reset
      act(() => {
        result.current.reset();
      });

      // Should have no error
      expect(result.current.error).toBeNull();
    });
  });

  describe('isMutating computed property', () => {
    it('returns true when any mutation is in progress', async () => {
      let resolvePromise: (value: unknown) => void;
      const pendingPromise = new Promise((resolve) => {
        resolvePromise = resolve;
      });
      vi.mocked(api.cancelJob).mockReturnValue(
        pendingPromise as Promise<typeof mockCancelResponse>
      );

      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      act(() => {
        void result.current.cancelJob('job-123');
      });

      await waitFor(() => {
        expect(result.current.isMutating).toBe(true);
      });

      act(() => {
        resolvePromise!(mockCancelResponse);
      });

      await waitFor(() => {
        expect(result.current.isMutating).toBe(false);
      });
    });

    it('returns false when no mutation is in progress', () => {
      const queryClient = createTestQueryClient();
      const { result } = renderHook(() => useJobMutations(), {
        wrapper: createQueryWrapper(queryClient),
      });

      expect(result.current.isMutating).toBe(false);
    });
  });
});

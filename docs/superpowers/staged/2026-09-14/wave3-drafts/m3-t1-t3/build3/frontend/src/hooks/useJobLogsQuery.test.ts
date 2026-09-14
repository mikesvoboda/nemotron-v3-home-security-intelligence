import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useJobLogsQuery, jobLogsQueryKeys } from './useJobLogsQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { JobLogsResponse } from '../types/generated';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    fetchJobLogs: vi.fn(),
  };
});

describe('useJobLogsQuery', () => {
  const mockJobId = '550e8400-e29b-41d4-a716-446655440000';

  const mockLogsResponse: JobLogsResponse = {
    job_id: mockJobId,
    logs: [
      {
        timestamp: '2024-01-15T10:30:00Z',
        level: 'INFO',
        message: 'Starting export job',
        attempt_number: 1,
        context: { event_count: 1000 },
      },
      {
        timestamp: '2024-01-15T10:30:05Z',
        level: 'INFO',
        message: 'Processing events',
        attempt_number: 1,
        context: null,
      },
      {
        timestamp: '2024-01-15T10:31:00Z',
        level: 'WARN',
        message: 'Slow query detected',
        attempt_number: 1,
        context: { query_time_ms: 5000 },
      },
      {
        timestamp: '2024-01-15T10:32:00Z',
        level: 'ERROR',
        message: 'Connection timeout',
        attempt_number: 1,
        context: { timeout_seconds: 30 },
      },
    ],
    total: 4,
    has_more: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchJobLogs as ReturnType<typeof vi.fn>).mockResolvedValue(mockLogsResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true when jobId is provided', () => {
      (api.fetchJobLogs as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useJobLogsQuery({ jobId: mockJobId }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('does not fetch when jobId is undefined', async () => {
      const { result } = renderHook(() => useJobLogsQuery({ jobId: undefined }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchJobLogs).not.toHaveBeenCalled();
      expect(result.current.isLoading).toBe(false);
    });

    it('does not fetch when jobId is empty string', async () => {
      const { result } = renderHook(() => useJobLogsQuery({ jobId: '' }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchJobLogs).not.toHaveBeenCalled();
      expect(result.current.isLoading).toBe(false);
    });

    it('starts with empty logs array', () => {
      (api.fetchJobLogs as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useJobLogsQuery({ jobId: mockJobId }), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.logs).toEqual([]);
    });
  });

  describe('fetching data', () => {
    it('fetches logs on mount when jobId is provided', async () => {
      renderHook(() => useJobLogsQuery({ jobId: mockJobId }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.fetchJobLogs).toHaveBeenCalledTimes(1);
        expect(api.fetchJobLogs).toHaveBeenCalledWith(mockJobId, undefined);
      });
    });

    it('returns logs after successful fetch', async () => {
      const { result } = renderHook(() => useJobLogsQuery({ jobId: mockJobId }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.logs).toEqual(mockLogsResponse.logs);
      });
    });

    it('returns total count from response', async () => {
      const { result } = renderHook(() => useJobLogsQuery({ jobId: mockJobId }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.totalCount).toBe(4);
      });
    });

    it('returns hasMore from response', async () => {
      const { result } = renderHook(() => useJobLogsQuery({ jobId: mockJobId }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.hasMore).toBe(false);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useJobLogsQuery({ jobId: mockJobId }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('query parameters', () => {
    it('passes limit parameter to API', async () => {
      renderHook(() => useJobLogsQuery({ jobId: mockJobId, limit: 50 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchJobLogs).toHaveBeenCalledWith(mockJobId, { limit: 50 });
      });
    });

    it('passes offset parameter to API', async () => {
      renderHook(() => useJobLogsQuery({ jobId: mockJobId, offset: 100 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchJobLogs).toHaveBeenCalledWith(mockJobId, { offset: 100 });
      });
    });

    it('passes level filter to API', async () => {
      renderHook(() => useJobLogsQuery({ jobId: mockJobId, level: 'ERROR' }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchJobLogs).toHaveBeenCalledWith(mockJobId, { level: 'ERROR' });
      });
    });

    it('passes multiple parameters to API', async () => {
      renderHook(
        () => useJobLogsQuery({ jobId: mockJobId, limit: 25, offset: 50, level: 'WARN' }),
        { wrapper: createQueryWrapper() }
      );

      await waitFor(() => {
        expect(api.fetchJobLogs).toHaveBeenCalledWith(mockJobId, {
          limit: 25,
          offset: 50,
          level: 'WARN',
        });
      });
    });
  });

  describe('polling', () => {
    it('accepts refetchInterval option', async () => {
      // Test that the hook accepts refetchInterval without error
      // Actual polling behavior is tested through integration tests
      const { result } = renderHook(
        () => useJobLogsQuery({ jobId: mockJobId, refetchInterval: 1000 }),
        {
          wrapper: createQueryWrapper(),
        }
      );

      // Wait for data to load
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
        expect(result.current.logs.length).toBeGreaterThan(0);
      });

      // Verify hook returns data correctly with polling enabled
      expect(result.current.logs).toEqual(mockLogsResponse.logs);
    });

    it('works without refetchInterval', async () => {
      const { result } = renderHook(() => useJobLogsQuery({ jobId: mockJobId }), {
        wrapper: createQueryWrapper(),
      });

      // Wait for data to load
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
        expect(result.current.logs.length).toBeGreaterThan(0);
      });

      // Verify hook returns data correctly without polling
      expect(result.current.logs).toEqual(mockLogsResponse.logs);
    });
  });

  describe('error handling', () => {
    it('sets error on fetch failure', async () => {
      const errorMessage = 'Job not found';
      (api.fetchJobLogs as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useJobLogsQuery({ jobId: mockJobId, retry: 0 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.error).toBeInstanceOf(Error);
          expect(result.current.error?.message).toBe(errorMessage);
        },
        { timeout: 5000 }
      );
    });

    it('sets isError to true on failure', async () => {
      (api.fetchJobLogs as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useJobLogsQuery({ jobId: mockJobId, retry: 0 }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useJobLogsQuery({ jobId: mockJobId, enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchJobLogs).not.toHaveBeenCalled();
    });

    it('fetches when enabled changes from false to true', async () => {
      const { rerender } = renderHook(
        ({ enabled }) => useJobLogsQuery({ jobId: mockJobId, enabled }),
        {
          wrapper: createQueryWrapper(),
          initialProps: { enabled: false },
        }
      );

      await new Promise((r) => setTimeout(r, 100));
      expect(api.fetchJobLogs).not.toHaveBeenCalled();

      rerender({ enabled: true });

      await waitFor(() => {
        expect(api.fetchJobLogs).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('refetch', () => {
    it('provides refetch function', async () => {
      const { result } = renderHook(() => useJobLogsQuery({ jobId: mockJobId }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('refetch triggers new API call', async () => {
      const { result } = renderHook(() => useJobLogsQuery({ jobId: mockJobId }), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(api.fetchJobLogs).toHaveBeenCalledTimes(1);
      });

      result.current.refetch();

      await waitFor(() => {
        expect(api.fetchJobLogs).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('query keys', () => {
    it('generates correct query keys', () => {
      expect(jobLogsQueryKeys.all).toEqual(['jobLogs']);
      expect(jobLogsQueryKeys.byJob(mockJobId)).toEqual(['jobLogs', mockJobId]);
      expect(jobLogsQueryKeys.byJobWithParams(mockJobId, { limit: 50 })).toEqual([
        'jobLogs',
        mockJobId,
        { limit: 50 },
      ]);
    });
  });
});

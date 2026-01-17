import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useJobsSearchQuery, jobsSearchQueryKeys, type JobsSearchFilters } from './useJobsSearchQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { JobSearchResponse } from '../types/generated';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    searchJobs: vi.fn(),
  };
});

describe('useJobsSearchQuery', () => {
  const mockSearchResponse: JobSearchResponse = {
    data: [
      {
        job_id: 'job-1',
        job_type: 'export',
        status: 'completed',
        progress: 100,
        message: 'Export completed successfully',
        created_at: '2026-01-15T10:30:00Z',
        started_at: '2026-01-15T10:30:01Z',
        completed_at: '2026-01-15T10:31:30Z',
        result: { file_path: '/exports/data.csv' },
        error: null,
      },
      {
        job_id: 'job-2',
        job_type: 'batch_audit',
        status: 'running',
        progress: 45,
        message: 'Processing events: 450/1000',
        created_at: '2026-01-15T11:00:00Z',
        started_at: '2026-01-15T11:00:01Z',
        completed_at: null,
        result: null,
        error: null,
      },
      {
        job_id: 'job-3',
        job_type: 'cleanup',
        status: 'failed',
        progress: 0,
        message: 'Cleanup failed',
        created_at: '2026-01-15T09:00:00Z',
        started_at: '2026-01-15T09:00:01Z',
        completed_at: '2026-01-15T09:00:30Z',
        result: null,
        error: 'Disk space insufficient',
      },
    ],
    meta: {
      total: 150,
      limit: 50,
      offset: 0,
      has_more: true,
    },
    aggregations: {
      by_status: {
        pending: 10,
        running: 5,
        completed: 100,
        failed: 35,
      },
      by_type: {
        export: 60,
        batch_audit: 50,
        cleanup: 30,
        re_evaluation: 10,
      },
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.searchJobs as ReturnType<typeof vi.fn>).mockResolvedValue(mockSearchResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true', () => {
      (api.searchJobs as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useJobsSearchQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
    });

    it('starts with empty jobs array', () => {
      (api.searchJobs as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useJobsSearchQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.jobs).toEqual([]);
    });

    it('starts with totalCount of 0', () => {
      (api.searchJobs as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useJobsSearchQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.totalCount).toBe(0);
    });

    it('starts with empty aggregations', () => {
      (api.searchJobs as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      const { result } = renderHook(() => useJobsSearchQuery(), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.aggregations).toEqual({ by_status: {}, by_type: {} });
    });
  });

  describe('fetching data', () => {
    it('fetches jobs on mount', async () => {
      renderHook(() => useJobsSearchQuery(), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledTimes(1);
      });
    });

    it('updates jobs after successful fetch', async () => {
      const { result } = renderHook(() => useJobsSearchQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.jobs).toEqual(mockSearchResponse.data);
      });
    });

    it('sets totalCount from meta', async () => {
      const { result } = renderHook(() => useJobsSearchQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.totalCount).toBe(150);
      });
    });

    it('sets isLoading false after fetch', async () => {
      const { result } = renderHook(() => useJobsSearchQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('sets aggregations from response', async () => {
      const { result } = renderHook(() => useJobsSearchQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.aggregations).toEqual(mockSearchResponse.aggregations);
      });
    });
  });

  describe('filtering by query', () => {
    it('fetches jobs with search query', async () => {
      const filters: JobsSearchFilters = { q: 'export' };

      renderHook(() => useJobsSearchQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledWith(
          expect.objectContaining({ q: 'export' })
        );
      });
    });

    it('handles empty query', async () => {
      const filters: JobsSearchFilters = { q: '' };

      renderHook(() => useJobsSearchQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledWith(
          expect.objectContaining({ q: '' })
        );
      });
    });
  });

  describe('filtering by status', () => {
    it('fetches jobs with status filter', async () => {
      const filters: JobsSearchFilters = { status: 'failed' };

      renderHook(() => useJobsSearchQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledWith(
          expect.objectContaining({ status: 'failed' })
        );
      });
    });

    it('fetches jobs with pending status', async () => {
      const filters: JobsSearchFilters = { status: 'pending' };

      renderHook(() => useJobsSearchQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledWith(
          expect.objectContaining({ status: 'pending' })
        );
      });
    });

    it('fetches jobs with running status', async () => {
      const filters: JobsSearchFilters = { status: 'running' };

      renderHook(() => useJobsSearchQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledWith(
          expect.objectContaining({ status: 'running' })
        );
      });
    });

    it('fetches jobs with completed status', async () => {
      const filters: JobsSearchFilters = { status: 'completed' };

      renderHook(() => useJobsSearchQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledWith(
          expect.objectContaining({ status: 'completed' })
        );
      });
    });
  });

  describe('filtering by type', () => {
    it('fetches jobs with type filter', async () => {
      const filters: JobsSearchFilters = { type: 'export' };

      renderHook(() => useJobsSearchQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledWith(
          expect.objectContaining({ type: 'export' })
        );
      });
    });

    it('fetches jobs with batch_audit type', async () => {
      const filters: JobsSearchFilters = { type: 'batch_audit' };

      renderHook(() => useJobsSearchQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledWith(
          expect.objectContaining({ type: 'batch_audit' })
        );
      });
    });

    it('fetches jobs with cleanup type', async () => {
      const filters: JobsSearchFilters = { type: 'cleanup' };

      renderHook(() => useJobsSearchQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledWith(
          expect.objectContaining({ type: 'cleanup' })
        );
      });
    });
  });

  describe('combined filters', () => {
    it('fetches jobs with query, status, and type combined', async () => {
      const filters: JobsSearchFilters = {
        q: 'export',
        status: 'failed',
        type: 'export',
      };

      renderHook(() => useJobsSearchQuery({ filters }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledWith(
          expect.objectContaining({
            q: 'export',
            status: 'failed',
            type: 'export',
          })
        );
      });
    });
  });

  describe('pagination', () => {
    it('respects limit parameter', async () => {
      renderHook(() => useJobsSearchQuery({ limit: 25 }), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledWith(
          expect.objectContaining({ limit: 25 })
        );
      });
    });

    it('uses default limit of 50', async () => {
      renderHook(() => useJobsSearchQuery(), { wrapper: createQueryWrapper() });

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledWith(
          expect.objectContaining({ limit: 50 })
        );
      });
    });
  });

  describe('error handling', () => {
    it('sets error on fetch failure', async () => {
      const errorMessage = 'Failed to search jobs';
      (api.searchJobs as ReturnType<typeof vi.fn>).mockRejectedValue(new Error(errorMessage));

      const { result } = renderHook(() => useJobsSearchQuery({ retry: 0 }), {
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
      (api.searchJobs as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));

      const { result } = renderHook(() => useJobsSearchQuery({ retry: 0 }), {
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

  describe('options', () => {
    it('does not fetch when enabled is false', async () => {
      renderHook(() => useJobsSearchQuery({ enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));
      expect(api.searchJobs).not.toHaveBeenCalled();
    });

    it('provides refetch function', async () => {
      const { result } = renderHook(() => useJobsSearchQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(typeof result.current.refetch).toBe('function');
    });

    it('allows refetch to refresh data', async () => {
      const { result } = renderHook(() => useJobsSearchQuery(), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.searchJobs).toHaveBeenCalledTimes(1);

      result.current.refetch();

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('query keys', () => {
    it('generates correct query keys', () => {
      expect(jobsSearchQueryKeys.all).toEqual(['jobs-search']);
      expect(jobsSearchQueryKeys.lists()).toEqual(['jobs-search', 'list']);

      const filters: JobsSearchFilters = { q: 'test', status: 'failed' };
      expect(jobsSearchQueryKeys.list(filters, 25)).toEqual([
        'jobs-search',
        'list',
        { filters, limit: 25 },
      ]);
    });
  });

  describe('debouncing', () => {
    it('uses debounced query when debounceMs is provided', async () => {
      const { result, rerender } = renderHook(
        ({ filters }: { filters: JobsSearchFilters }) =>
          useJobsSearchQuery({ filters, debounceMs: 300 }),
        {
          wrapper: createQueryWrapper(),
          initialProps: { filters: { q: 'test' } },
        }
      );

      // Initial fetch
      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledTimes(1);
      });

      // Rerender with new query
      rerender({ filters: { q: 'test2' } });

      // Should not immediately call API due to debounce
      expect(api.searchJobs).toHaveBeenCalledTimes(1);

      // After debounce delay
      await waitFor(
        () => {
          expect(api.searchJobs).toHaveBeenCalledTimes(2);
        },
        { timeout: 500 }
      );

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });
});

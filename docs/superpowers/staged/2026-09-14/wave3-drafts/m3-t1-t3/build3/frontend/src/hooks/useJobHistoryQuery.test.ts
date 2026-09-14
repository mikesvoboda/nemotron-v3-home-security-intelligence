/**
 * Tests for useJobHistoryQuery hook (NEM-2713)
 *
 * This hook fetches job history including state transitions
 * for displaying in a timeline component.
 */
import { renderHook, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { useJobHistoryQuery, jobHistoryQueryKeys } from './useJobHistoryQuery';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    fetchJobHistory: vi.fn(),
  };
});

describe('useJobHistoryQuery', () => {
  // Helper to create mock job history data
  const createMockJobHistory = (
    overrides: Partial<api.JobHistoryResponse> = {}
  ): api.JobHistoryResponse => ({
    job_id: '142',
    job_type: 'export',
    status: 'completed',
    created_at: '2026-01-17T10:30:00Z',
    started_at: '2026-01-17T10:30:05Z',
    completed_at: '2026-01-17T10:32:00Z',
    transitions: [
      {
        from: null,
        to: 'pending',
        at: '2026-01-17T10:30:00Z',
        triggered_by: 'api',
        details: null,
      },
      {
        from: 'pending',
        to: 'running',
        at: '2026-01-17T10:30:05Z',
        triggered_by: 'worker',
        details: { worker_id: 'worker-1' },
      },
      {
        from: 'running',
        to: 'completed',
        at: '2026-01-17T10:32:00Z',
        triggered_by: 'worker',
        details: null,
      },
    ],
    attempts: [],
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('initialization', () => {
    it('starts with isLoading true when fetching', () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {}) // Never resolving promise
      );

      const { result } = renderHook(() => useJobHistoryQuery('142'), {
        wrapper: createQueryWrapper(),
      });

      expect(result.current.isLoading).toBe(true);
      expect(result.current.history).toBeNull();
    });

    it('fetches job history for the given job ID', async () => {
      const mockHistory = createMockJobHistory();
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      const { result } = renderHook(() => useJobHistoryQuery('142'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchJobHistory).toHaveBeenCalledWith('142');
      expect(result.current.history).toEqual(mockHistory);
    });
  });

  describe('data transformation', () => {
    it('returns transitions array from history', async () => {
      const mockHistory = createMockJobHistory();
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      const { result } = renderHook(() => useJobHistoryQuery('142'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.transitions).toHaveLength(3);
      expect(result.current.transitions[0].to).toBe('pending');
      expect(result.current.transitions[1].to).toBe('running');
      expect(result.current.transitions[2].to).toBe('completed');
    });

    it('returns empty transitions array when history is null', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(
        createMockJobHistory({ transitions: [] })
      );

      const { result } = renderHook(() => useJobHistoryQuery('142'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.transitions).toEqual([]);
    });

    it('returns current status from history', async () => {
      const mockHistory = createMockJobHistory({ status: 'failed' });
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      const { result } = renderHook(() => useJobHistoryQuery('142'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(result.current.currentStatus).toBe('failed');
    });
  });

  describe('error handling', () => {
    it('propagates error from failed query', async () => {
      const testError = new Error('Failed to fetch job history');
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockRejectedValue(testError);

      const { result } = renderHook(() => useJobHistoryQuery('142'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );

      expect(result.current.error).toBeInstanceOf(Error);
      expect(result.current.error?.message).toBe('Failed to fetch job history');
    });

    it('returns null history on error', async () => {
      const testError = new Error('Failed to fetch');
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockRejectedValue(testError);

      const { result } = renderHook(() => useJobHistoryQuery('142'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(
        () => {
          expect(result.current.isError).toBe(true);
        },
        { timeout: 5000 }
      );

      expect(result.current.history).toBeNull();
      expect(result.current.transitions).toEqual([]);
    });
  });

  describe('enabled option', () => {
    it('does not fetch when enabled is false', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(createMockJobHistory());

      const { result } = renderHook(() => useJobHistoryQuery('142', { enabled: false }), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));

      expect(api.fetchJobHistory).not.toHaveBeenCalled();
      expect(result.current.isLoading).toBe(false);
    });

    it('does not fetch when jobId is empty', async () => {
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(createMockJobHistory());

      renderHook(() => useJobHistoryQuery(''), {
        wrapper: createQueryWrapper(),
      });

      await new Promise((r) => setTimeout(r, 100));

      expect(api.fetchJobHistory).not.toHaveBeenCalled();
    });
  });

  describe('refetch function', () => {
    it('refetches data when called', async () => {
      const mockHistory = createMockJobHistory();
      (api.fetchJobHistory as ReturnType<typeof vi.fn>).mockResolvedValue(mockHistory);

      const { result } = renderHook(() => useJobHistoryQuery('142'), {
        wrapper: createQueryWrapper(),
      });

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });

      expect(api.fetchJobHistory).toHaveBeenCalledTimes(1);

      // Refetch
      await result.current.refetch();

      expect(api.fetchJobHistory).toHaveBeenCalledTimes(2);
    });
  });

  describe('jobHistoryQueryKeys', () => {
    it('generates correct query keys', () => {
      expect(jobHistoryQueryKeys.all).toEqual(['jobs', 'history']);
      expect(jobHistoryQueryKeys.detail('142')).toEqual(['jobs', 'history', '142']);
    });
  });
});

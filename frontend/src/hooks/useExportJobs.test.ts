/**
 * useExportJobs hook tests
 *
 * Tests for the export jobs React Query hook that provides:
 * - List export jobs
 * - Start new export jobs
 * - Cancel export jobs
 * - Poll for status updates
 *
 * @see NEM-3177
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  useExportJobsQuery,
  useStartExportJob,
  useCancelExportJob,
  useExportJobStatus,
  exportJobsQueryKeys,
} from './useExportJobs';
import * as api from '../services/api';
import { createQueryWrapper } from '../test-utils/renderWithProviders';

import type { ExportJob, ExportJobListResponse } from '../types/export';

// Mock the API module
vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return {
    ...actual,
    listExportJobs: vi.fn(),
    startExportJob: vi.fn(),
    cancelExportJob: vi.fn(),
    getExportStatus: vi.fn(),
  };
});

// ============================================================================
// Test Data
// ============================================================================

const mockExportJob: ExportJob = {
  id: 'test-job-123',
  status: 'pending',
  export_type: 'events',
  export_format: 'csv',
  progress: {
    total_items: null,
    processed_items: 0,
    progress_percent: 0,
    current_step: 'Initializing...',
    estimated_completion: null,
  },
  created_at: '2025-01-21T10:00:00Z',
  started_at: null,
  completed_at: null,
  result: null,
  error_message: null,
};

const mockCompletedJob: ExportJob = {
  ...mockExportJob,
  id: 'completed-job-456',
  status: 'completed',
  progress: {
    total_items: 100,
    processed_items: 100,
    progress_percent: 100,
    current_step: 'Complete',
    estimated_completion: null,
  },
  started_at: '2025-01-21T10:00:01Z',
  completed_at: '2025-01-21T10:01:00Z',
  result: {
    output_path: '/api/exports/completed-job-456/download',
    output_size_bytes: 12345,
    event_count: 100,
    format: 'csv',
  },
};

const mockExportJobList: ExportJobListResponse = {
  items: [mockCompletedJob, mockExportJob],
  pagination: {
    total: 2,
    limit: 50,
    offset: 0,
    cursor: null,
    next_cursor: null,
    has_more: false,
  },
};

// ============================================================================
// Query Keys Tests
// ============================================================================

describe('exportJobsQueryKeys', () => {
  it('should create correct base key', () => {
    expect(exportJobsQueryKeys.all).toEqual(['exports']);
  });

  it('should create correct list key', () => {
    expect(exportJobsQueryKeys.list()).toEqual(['exports', 'list']);
  });

  it('should create correct list key with filters', () => {
    expect(exportJobsQueryKeys.list({ status: 'pending' })).toEqual([
      'exports',
      'list',
      { status: 'pending' },
    ]);
  });

  it('should create correct detail key', () => {
    expect(exportJobsQueryKeys.detail('job-123')).toEqual(['exports', 'detail', 'job-123']);
  });
});

// ============================================================================
// useExportJobsQuery Tests
// ============================================================================

describe('useExportJobsQuery', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should fetch export jobs list', async () => {
    vi.mocked(api.listExportJobs).mockResolvedValueOnce(mockExportJobList);

    const { result } = renderHook(() => useExportJobsQuery(), {
      wrapper: createQueryWrapper(),
    });

    // Initially loading
    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.jobs).toHaveLength(2);
    expect(result.current.jobs[0].id).toBe('completed-job-456');
    expect(api.listExportJobs).toHaveBeenCalledOnce();
  });

  it('should filter by status when provided', async () => {
    vi.mocked(api.listExportJobs).mockResolvedValueOnce({
      ...mockExportJobList,
      items: [mockExportJob],
    });

    const { result } = renderHook(() => useExportJobsQuery({ status: 'pending' }), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(api.listExportJobs).toHaveBeenCalledWith('pending', 50, 0);
    expect(result.current.jobs).toHaveLength(1);
  });

  it('should handle errors gracefully', async () => {
    const error = new Error('Network error');
    vi.mocked(api.listExportJobs).mockRejectedValueOnce(error);

    const { result } = renderHook(() => useExportJobsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeTruthy();
  });

  it('should not fetch when disabled', () => {
    vi.mocked(api.listExportJobs).mockResolvedValueOnce(mockExportJobList);

    const { result } = renderHook(() => useExportJobsQuery({ enabled: false }), {
      wrapper: createQueryWrapper(),
    });

    // Should not be loading because query is disabled
    expect(result.current.isLoading).toBe(false);
    expect(api.listExportJobs).not.toHaveBeenCalled();
  });

  it('should provide pagination info', async () => {
    vi.mocked(api.listExportJobs).mockResolvedValueOnce(mockExportJobList);

    const { result } = renderHook(() => useExportJobsQuery(), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.pagination).toEqual(mockExportJobList.pagination);
  });
});

// ============================================================================
// useExportJobStatus Tests
// ============================================================================

describe('useExportJobStatus', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should fetch job status by ID', async () => {
    (api.getExportStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockExportJob);

    const { result } = renderHook(() => useExportJobStatus('test-job-123'), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.job).toEqual(mockExportJob);
    expect(api.getExportStatus).toHaveBeenCalledWith('test-job-123');
  });

  it('should mark completed job as complete', async () => {
    (api.getExportStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockCompletedJob);

    const { result } = renderHook(() => useExportJobStatus('completed-job-456'), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.job?.status).toBe('completed');
    expect(result.current.isComplete).toBe(true);
    expect(result.current.isRunning).toBe(false);
  });

  it('should mark pending job as running', async () => {
    (api.getExportStatus as ReturnType<typeof vi.fn>).mockResolvedValue(mockExportJob);

    const { result } = renderHook(() => useExportJobStatus('test-job-123'), {
      wrapper: createQueryWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isRunning).toBe(true);
    expect(result.current.isComplete).toBe(false);
  });

  it('should not fetch when jobId is empty', () => {
    const { result } = renderHook(() => useExportJobStatus(''), {
      wrapper: createQueryWrapper(),
    });

    expect(result.current.isLoading).toBe(false);
    expect(result.current.job).toBeNull();
    expect(api.getExportStatus).not.toHaveBeenCalled();
  });
});

// ============================================================================
// useStartExportJob Tests
// ============================================================================

describe('useStartExportJob', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should start a new export job', async () => {
    (api.startExportJob as ReturnType<typeof vi.fn>).mockResolvedValue({
      job_id: 'new-job-789',
      status: 'pending',
      message: 'Export job created',
    });

    const { result } = renderHook(() => useStartExportJob(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      await result.current.startExport({
        export_type: 'events',
        export_format: 'csv',
      });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.job_id).toBe('new-job-789');
    expect(api.startExportJob).toHaveBeenCalledWith({
      export_type: 'events',
      export_format: 'csv',
    });
  });

  it('should start export with date range filters', async () => {
    (api.startExportJob as ReturnType<typeof vi.fn>).mockResolvedValue({
      job_id: 'filtered-job',
      status: 'pending',
      message: 'Export job created',
    });

    const { result } = renderHook(() => useStartExportJob(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      await result.current.startExport({
        export_type: 'events',
        export_format: 'json',
        start_date: '2025-01-01T00:00:00Z',
        end_date: '2025-01-15T23:59:59Z',
      });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(api.startExportJob).toHaveBeenCalledWith({
      export_type: 'events',
      export_format: 'json',
      start_date: '2025-01-01T00:00:00Z',
      end_date: '2025-01-15T23:59:59Z',
    });
  });

  it('should handle errors', async () => {
    const error = new Error('Failed to start export');
    (api.startExportJob as ReturnType<typeof vi.fn>).mockRejectedValue(error);

    const { result } = renderHook(() => useStartExportJob(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      try {
        await result.current.startExport({ export_type: 'events' });
      } catch {
        // Expected error
      }
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });

    expect(result.current.error).toBeTruthy();
  });
});

// ============================================================================
// useCancelExportJob Tests
// ============================================================================

describe('useCancelExportJob', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should cancel an export job', async () => {
    (api.cancelExportJob as ReturnType<typeof vi.fn>).mockResolvedValue({
      job_id: 'test-job-123',
      status: 'failed',
      message: 'Job cancelled',
      cancelled: true,
    });

    const { result } = renderHook(() => useCancelExportJob(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      await result.current.cancelJob('test-job-123');
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(api.cancelExportJob).toHaveBeenCalledWith('test-job-123');
  });

  it('should handle cancel errors', async () => {
    const error = new Error('Cannot cancel completed job');
    (api.cancelExportJob as ReturnType<typeof vi.fn>).mockRejectedValue(error);

    const { result } = renderHook(() => useCancelExportJob(), {
      wrapper: createQueryWrapper(),
    });

    await act(async () => {
      try {
        await result.current.cancelJob('completed-job-456');
      } catch {
        // Expected error
      }
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });
});

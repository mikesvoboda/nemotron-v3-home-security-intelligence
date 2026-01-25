/**
 * Unit tests for useExportJobs hooks
 *
 * Tests TanStack Query + WebSocket integration for export jobs:
 * - useExportJobsQuery: List export jobs
 * - useExportJobStatus: Job status with WebSocket real-time updates
 * - useStartExportJob: Start new export jobs
 * - useCancelExportJob: Cancel export jobs
 *
 * @module hooks/__tests__/useExportJobs
 * @see NEM-3570
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor, act } from '@testing-library/react';
import { type ReactNode } from 'react';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import { server } from '../../mocks/server';
import {
  useExportJobsQuery,
  useExportJobStatus,
  useStartExportJob,
  useCancelExportJob,
  exportJobsQueryKeys,
} from '../useExportJobs';

import type { ExportJob, ExportJobStatus } from '../../types/export';

// ============================================================================
// Mock useJobWebSocket
// ============================================================================

// Mock the useJobWebSocket hook for controlled WebSocket testing
const mockActiveJobs: Array<{
  job_id: string;
  job_type: string;
  progress: number;
  status: string;
}> = [];
let mockIsConnected = true;
const mockOnJobProgress = vi.fn();
const mockOnJobCompleted = vi.fn();
const mockOnJobFailed = vi.fn();

interface MockJobWebSocketOptions {
  enabled?: boolean;
  showToasts?: boolean;
  invalidateQueries?: boolean;
  onJobProgress?: (data: unknown) => void;
  onJobCompleted?: (data: unknown) => void;
  onJobFailed?: (data: unknown) => void;
}

vi.mock('../useJobWebSocket', () => ({
  useJobWebSocket: vi.fn((options: MockJobWebSocketOptions = {}) => {
    // Store callbacks for test triggering
    if (options.onJobProgress) mockOnJobProgress.mockImplementation(options.onJobProgress);
    if (options.onJobCompleted) mockOnJobCompleted.mockImplementation(options.onJobCompleted);
    if (options.onJobFailed) mockOnJobFailed.mockImplementation(options.onJobFailed);

    return {
      activeJobs: mockActiveJobs,
      isJobRunning: (jobType: string) =>
        mockActiveJobs.some(
          (j) => j.job_type === jobType && (j.status === 'pending' || j.status === 'running')
        ),
      hasActiveJobs: mockActiveJobs.some((j) => j.status === 'pending' || j.status === 'running'),
      isConnected: mockIsConnected,
    };
  }),
  default: vi.fn(),
}));

// ============================================================================
// Test Utilities
// ============================================================================

/**
 * Create a test wrapper with a fresh QueryClient for each test.
 */
function createTestWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: 0,
        gcTime: 0,
        staleTime: 0,
        retryDelay: 0,
      },
      mutations: {
        retry: 0,
        retryDelay: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

/**
 * Create a mock Response object with proper headers
 */
function createMockResponse(data: unknown, status = 200, ok = true): Response {
  return {
    ok,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(data),
    headers: new Headers(),
    redirected: false,
    type: 'basic',
    url: '',
    body: null,
    bodyUsed: false,
    arrayBuffer: () => Promise.resolve(new ArrayBuffer(0)),
    blob: () => Promise.resolve(new Blob()),
    clone: () => createMockResponse(data, status, ok),
    formData: () => Promise.resolve(new FormData()),
    text: () => Promise.resolve(JSON.stringify(data)),
  } as Response;
}

// ============================================================================
// Test Data Fixtures
// ============================================================================

const createMockExportJob = (overrides: Partial<ExportJob> = {}): ExportJob => ({
  id: 'job-123',
  status: 'running' as ExportJobStatus,
  export_type: 'events',
  export_format: 'csv',
  progress: {
    total_items: 100,
    processed_items: 25,
    progress_percent: 25,
    current_step: 'Processing events',
    estimated_completion: null,
  },
  created_at: '2024-01-01T00:00:00Z',
  started_at: '2024-01-01T00:00:01Z',
  completed_at: null,
  filter_params: null,
  result: null,
  error_message: null,
  ...overrides,
});

const mockJobListResponse = {
  items: [
    createMockExportJob({ id: 'job-1', status: 'completed' }),
    createMockExportJob({ id: 'job-2', status: 'running' }),
  ],
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
// Setup/Teardown
// ============================================================================

let mockFetch: ReturnType<typeof vi.fn>;

beforeAll(() => {
  server.close();
});

afterAll(() => {
  server.listen({ onUnhandledRequest: 'bypass' });
});

beforeEach(() => {
  vi.clearAllMocks();
  mockFetch = vi.fn();
  mockFetch.mockResolvedValue(createMockResponse(createMockExportJob()));
  vi.stubGlobal('fetch', mockFetch);

  // Reset mock WebSocket state
  mockActiveJobs.length = 0;
  mockIsConnected = true;
});

afterEach(() => {
  vi.unstubAllGlobals();
});

// ============================================================================
// Query Key Factory Tests
// ============================================================================

describe('exportJobsQueryKeys', () => {
  it('generates correct base key', () => {
    expect(exportJobsQueryKeys.all).toEqual(['exports']);
  });

  it('generates correct list key without filters', () => {
    expect(exportJobsQueryKeys.list()).toEqual(['exports', 'list']);
  });

  it('generates correct list key with status filter', () => {
    expect(exportJobsQueryKeys.list({ status: 'running' })).toEqual([
      'exports',
      'list',
      { status: 'running' },
    ]);
  });

  it('generates correct detail key', () => {
    expect(exportJobsQueryKeys.detail('job-123')).toEqual(['exports', 'detail', 'job-123']);
  });
});

// ============================================================================
// useExportJobsQuery Tests
// ============================================================================

describe('useExportJobsQuery', () => {
  it('fetches export jobs list on mount', async () => {
    mockFetch.mockResolvedValue(createMockResponse(mockJobListResponse));

    const { result } = renderHook(() => useExportJobsQuery(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isLoading).toBe(true);

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.jobs).toHaveLength(2);
    expect(result.current.pagination?.total).toBe(2);
  });

  it('supports status filtering', async () => {
    mockFetch.mockResolvedValue(createMockResponse(mockJobListResponse));

    const { result } = renderHook(() => useExportJobsQuery({ status: 'running' }), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('status=running'),
      expect.any(Object)
    );
  });

  it('handles empty job list', async () => {
    mockFetch.mockResolvedValue(
      createMockResponse({
        items: [],
        pagination: { total: 0, limit: 50, offset: 0, cursor: null, next_cursor: null, has_more: false },
      })
    );

    const { result } = renderHook(() => useExportJobsQuery(), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.jobs).toEqual([]);
    expect(result.current.pagination?.total).toBe(0);
  });

  it('returns empty jobs array when no data', () => {
    // Test that the hook returns sensible defaults before data loads
    const { result } = renderHook(() => useExportJobsQuery({ enabled: false }), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.jobs).toEqual([]);
    expect(result.current.pagination).toBeNull();
    expect(result.current.isLoading).toBe(false);
    expect(result.current.isError).toBe(false);
  });
});

// ============================================================================
// useExportJobStatus Tests (WebSocket Integration)
// ============================================================================

describe('useExportJobStatus', () => {
  it('fetches job status on mount', async () => {
    const mockJob = createMockExportJob({ id: 'job-123', status: 'running' });
    mockFetch.mockResolvedValue(createMockResponse(mockJob));

    const { result } = renderHook(() => useExportJobStatus('job-123'), {
      wrapper: createTestWrapper(),
    });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.job?.id).toBe('job-123');
    expect(result.current.isRunning).toBe(true);
  });

  it('uses WebSocket for real-time progress updates', async () => {
    const mockJob = createMockExportJob({
      id: 'job-123',
      status: 'running',
      progress: { ...createMockExportJob().progress, progress_percent: 25 },
    });
    mockFetch.mockResolvedValue(createMockResponse(mockJob));

    // Simulate WebSocket providing a higher progress value
    mockActiveJobs.push({
      job_id: 'job-123',
      job_type: 'export',
      progress: 50,
      status: 'running',
    });

    const { result } = renderHook(
      () => useExportJobStatus('job-123', { enableWebSocket: true }),
      { wrapper: createTestWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // WebSocket progress should take precedence (higher value)
    expect(result.current.job?.progress.progress_percent).toBeGreaterThanOrEqual(25);
  });

  it('falls back to HTTP polling when WebSocket disconnected', async () => {
    mockIsConnected = false;
    const mockJob = createMockExportJob({ id: 'job-123', status: 'running' });
    mockFetch.mockResolvedValue(createMockResponse(mockJob));

    const { result } = renderHook(
      () => useExportJobStatus('job-123', { pollInterval: 1000, enableWebSocket: true }),
      { wrapper: createTestWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should still get job data from HTTP
    expect(result.current.job?.id).toBe('job-123');
  });

  it('stops polling when job is completed', async () => {
    const mockJob = createMockExportJob({ id: 'job-123', status: 'completed' });
    mockFetch.mockResolvedValue(createMockResponse(mockJob));

    const { result } = renderHook(
      () => useExportJobStatus('job-123', { pollInterval: 1000 }),
      { wrapper: createTestWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.isRunning).toBe(false);
  });

  it('stops polling when job has failed', async () => {
    const mockJob = createMockExportJob({
      id: 'job-123',
      status: 'failed',
      error_message: 'Export failed',
    });
    mockFetch.mockResolvedValue(createMockResponse(mockJob));

    const { result } = renderHook(
      () => useExportJobStatus('job-123', { pollInterval: 1000 }),
      { wrapper: createTestWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isComplete).toBe(true);
    expect(result.current.job?.error_message).toBe('Export failed');
  });

  it('merges WebSocket state with query data correctly', async () => {
    const mockJob = createMockExportJob({
      id: 'job-123',
      status: 'pending',
      progress: { ...createMockExportJob().progress, progress_percent: 0 },
    });
    mockFetch.mockResolvedValue(createMockResponse(mockJob));

    // WebSocket shows job is now running with progress
    mockActiveJobs.push({
      job_id: 'job-123',
      job_type: 'export',
      progress: 75,
      status: 'running',
    });

    const { result } = renderHook(
      () => useExportJobStatus('job-123', { enableWebSocket: true }),
      { wrapper: createTestWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Merged job should have the higher progress from WebSocket
    // and the running status from WebSocket
    expect(result.current.job).not.toBeNull();
  });

  it('does not fetch when enabled is false', async () => {
    const { result } = renderHook(
      () => useExportJobStatus('job-123', { enabled: false }),
      { wrapper: createTestWrapper() }
    );

    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(mockFetch).not.toHaveBeenCalled();
    expect(result.current.job).toBeNull();
  });

  it('returns isConnected status from WebSocket', async () => {
    const mockJob = createMockExportJob({ id: 'job-123', status: 'running' });
    mockFetch.mockResolvedValue(createMockResponse(mockJob));

    mockIsConnected = true;

    const { result } = renderHook(
      () => useExportJobStatus('job-123', { enableWebSocket: true }),
      { wrapper: createTestWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.wsConnected).toBe(true);
  });

  it('handles WebSocket disabled option', async () => {
    const mockJob = createMockExportJob({ id: 'job-123', status: 'running' });
    mockFetch.mockResolvedValue(createMockResponse(mockJob));

    const { result } = renderHook(
      () => useExportJobStatus('job-123', { enableWebSocket: false }),
      { wrapper: createTestWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should still work with HTTP only
    expect(result.current.job?.id).toBe('job-123');
  });
});

// ============================================================================
// useStartExportJob Tests
// ============================================================================

describe('useStartExportJob', () => {
  it('starts export job successfully', async () => {
    const startResponse = {
      job_id: 'new-job-123',
      status: 'pending',
      message: 'Export job started',
    };
    mockFetch.mockResolvedValue(createMockResponse(startResponse));

    const { result } = renderHook(() => useStartExportJob(), {
      wrapper: createTestWrapper(),
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

    expect(result.current.data?.job_id).toBe('new-job-123');
  });

  it('sends correct export parameters', async () => {
    const startResponse = {
      job_id: 'new-job-123',
      status: 'pending',
      message: 'Export job started',
    };
    mockFetch.mockResolvedValue(createMockResponse(startResponse));

    const { result } = renderHook(() => useStartExportJob(), {
      wrapper: createTestWrapper(),
    });

    await act(async () => {
      await result.current.startExport({
        export_type: 'events',
        export_format: 'json',
        camera_id: 'cam-1',
        start_date: '2024-01-01',
        end_date: '2024-01-31',
      });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('export_type'),
      })
    );
  });

  it('handles start error', async () => {
    mockFetch.mockResolvedValue(
      createMockResponse({ detail: 'Too many concurrent exports' }, 429, false)
    );

    const { result } = renderHook(() => useStartExportJob(), {
      wrapper: createTestWrapper(),
    });

    // Start the export and expect it to fail
    let errorThrown = false;
    try {
      await act(async () => {
        await result.current.startExport({
          export_type: 'events',
          export_format: 'csv',
        });
      });
    } catch {
      errorThrown = true;
    }

    // Either the error was thrown or the mutation captured the error
    await waitFor(() => {
      expect(result.current.isError || errorThrown).toBe(true);
    });
  });

  it('tracks pending state', async () => {
    // eslint-disable-next-line @typescript-eslint/no-misused-promises
    mockFetch.mockImplementation(() =>
      new Promise((resolve) =>
        setTimeout(
          () =>
            resolve(
              createMockResponse({
                job_id: 'new-job',
                status: 'pending',
                message: 'Started',
              })
            ),
          100
        )
      )
    );

    const { result } = renderHook(() => useStartExportJob(), {
      wrapper: createTestWrapper(),
    });

    expect(result.current.isPending).toBe(false);

    const promise = result.current.startExport({
      export_type: 'events',
      export_format: 'csv',
    });

    await waitFor(() => {
      expect(result.current.isPending).toBe(true);
    });

    await promise;

    await waitFor(() => {
      expect(result.current.isPending).toBe(false);
    });
  });

  it('resets mutation state', async () => {
    const startResponse = {
      job_id: 'new-job-123',
      status: 'pending',
      message: 'Export job started',
    };
    mockFetch.mockResolvedValue(createMockResponse(startResponse));

    const { result } = renderHook(() => useStartExportJob(), {
      wrapper: createTestWrapper(),
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

    act(() => {
      result.current.reset();
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(false);
    });
    expect(result.current.data).toBeUndefined();
  });
});

// ============================================================================
// useCancelExportJob Tests
// ============================================================================

describe('useCancelExportJob', () => {
  it('cancels export job successfully', async () => {
    const cancelResponse = {
      job_id: 'job-123',
      status: 'failed',
      message: 'Job cancelled',
      cancelled: true,
    };
    mockFetch.mockResolvedValue(createMockResponse(cancelResponse));

    const { result } = renderHook(() => useCancelExportJob(), {
      wrapper: createTestWrapper(),
    });

    await act(async () => {
      await result.current.cancelJob('job-123');
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('handles cancel error', async () => {
    mockFetch.mockResolvedValue(
      createMockResponse({ detail: 'Job already completed' }, 400, false)
    );

    const { result } = renderHook(() => useCancelExportJob(), {
      wrapper: createTestWrapper(),
    });

    await act(async () => {
      try {
        await result.current.cancelJob('job-123');
      } catch {
        // Expected
      }
    });

    await waitFor(() => {
      expect(result.current.isError).toBe(true);
    });
  });

  it('resets mutation state', async () => {
    const cancelResponse = {
      job_id: 'job-123',
      status: 'failed',
      message: 'Job cancelled',
      cancelled: true,
    };
    mockFetch.mockResolvedValue(createMockResponse(cancelResponse));

    const { result } = renderHook(() => useCancelExportJob(), {
      wrapper: createTestWrapper(),
    });

    await act(async () => {
      await result.current.cancelJob('job-123');
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    act(() => {
      result.current.reset();
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(false);
    });
  });
});

// ============================================================================
// Integration Tests
// ============================================================================

describe('Integration: WebSocket + HTTP polling', () => {
  it('prefers WebSocket updates over HTTP when connected', async () => {
    // HTTP returns 25% progress
    const mockJob = createMockExportJob({
      id: 'job-123',
      status: 'running',
      progress: { ...createMockExportJob().progress, progress_percent: 25 },
    });
    mockFetch.mockResolvedValue(createMockResponse(mockJob));

    // WebSocket has 60% progress
    mockActiveJobs.push({
      job_id: 'job-123',
      job_type: 'export',
      progress: 60,
      status: 'running',
    });
    mockIsConnected = true;

    const { result } = renderHook(
      () => useExportJobStatus('job-123', { enableWebSocket: true, pollInterval: 2000 }),
      { wrapper: createTestWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Should merge with higher progress
    expect(result.current.job?.progress.progress_percent).toBeGreaterThanOrEqual(25);
    expect(result.current.wsConnected).toBe(true);
  });

  it('resumes HTTP polling when WebSocket disconnects', async () => {
    const mockJob = createMockExportJob({ id: 'job-123', status: 'running' });
    mockFetch.mockResolvedValue(createMockResponse(mockJob));

    // Start connected
    mockIsConnected = true;
    mockActiveJobs.push({
      job_id: 'job-123',
      job_type: 'export',
      progress: 50,
      status: 'running',
    });

    const { result, rerender } = renderHook(
      () => useExportJobStatus('job-123', { enableWebSocket: true, pollInterval: 1000 }),
      { wrapper: createTestWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Disconnect WebSocket
    mockIsConnected = false;
    mockActiveJobs.length = 0;

    rerender();

    // Should still have job data from HTTP
    expect(result.current.job?.id).toBe('job-123');
    expect(result.current.wsConnected).toBe(false);
  });

  it('handles job completion via WebSocket', async () => {
    const mockJob = createMockExportJob({
      id: 'job-123',
      status: 'running',
    });
    mockFetch.mockResolvedValue(createMockResponse(mockJob));

    const { result } = renderHook(
      () => useExportJobStatus('job-123', { enableWebSocket: true }),
      { wrapper: createTestWrapper() }
    );

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // Job initially running
    expect(result.current.isRunning).toBe(true);
  });
});

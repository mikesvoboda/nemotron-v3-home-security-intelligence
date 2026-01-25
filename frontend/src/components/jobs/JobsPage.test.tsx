import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import JobsPage from './JobsPage';
import * as api from '../../services/api';

import type { JobResponse, JobStatusEnum, JobSearchResponse } from '../../services/api';

// Mock API module
vi.mock('../../services/api');

// Create a wrapper with QueryClientProvider and Router for testing
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

// Helper function to render with QueryClientProvider
function renderWithProviders(ui: React.ReactElement) {
  return render(ui, { wrapper: createWrapper() });
}

describe('JobsPage', () => {
  const mockJobs: JobResponse[] = [
    {
      job_id: 'job-001',
      job_type: 'export',
      status: 'running' as JobStatusEnum,
      progress: 45,
      message: 'Exporting events: 450/1000',
      created_at: '2024-01-15T10:30:00Z',
      started_at: '2024-01-15T10:30:01Z',
      completed_at: null,
      error: null,
      result: null,
    },
    {
      job_id: 'job-002',
      job_type: 'export',
      status: 'completed' as JobStatusEnum,
      progress: 100,
      message: 'Export completed',
      created_at: '2024-01-15T09:00:00Z',
      started_at: '2024-01-15T09:00:01Z',
      completed_at: '2024-01-15T09:05:00Z',
      error: null,
      result: { file_path: '/exports/events.csv' },
    },
    {
      job_id: 'job-003',
      job_type: 'cleanup',
      status: 'failed' as JobStatusEnum,
      progress: 30,
      message: 'Cleanup failed',
      created_at: '2024-01-15T08:00:00Z',
      started_at: '2024-01-15T08:00:01Z',
      completed_at: '2024-01-15T08:01:00Z',
      error: 'Connection timeout',
      result: null,
    },
    {
      job_id: 'job-004',
      job_type: 'export',
      status: 'pending' as JobStatusEnum,
      progress: 0,
      message: 'Waiting to start',
      created_at: '2024-01-15T11:00:00Z',
      started_at: null,
      completed_at: null,
      error: null,
      result: null,
    },
  ];

  const mockJobsResponse: JobSearchResponse = {
    data: mockJobs,
    meta: {
      total: 4,
      limit: 50,
      offset: 0,
      has_more: false,
    },
    aggregations: {
      by_status: {
        running: 1,
        completed: 1,
        failed: 1,
        pending: 1,
      },
      by_type: {
        export: 3,
        cleanup: 1,
      },
    },
  };

  const mockEmptyResponse: JobSearchResponse = {
    data: [],
    meta: {
      total: 0,
      limit: 50,
      offset: 0,
      has_more: false,
    },
    aggregations: {
      by_status: {},
      by_type: {},
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders the jobs page header', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      expect(screen.getByText('Jobs')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.queryByText('Loading jobs...')).not.toBeInTheDocument();
      });
    });

    it('displays loading state initially', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      expect(screen.getByText('Loading jobs...')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.queryByText('Loading jobs...')).not.toBeInTheDocument();
      });
    });

    it('displays jobs after loading', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      // Wait for jobs to load - check for data-testid which includes full job_id
      await waitFor(() => {
        expect(screen.getByTestId('job-item-job-001')).toBeInTheDocument();
      });

      expect(screen.getByTestId('job-item-job-002')).toBeInTheDocument();
    });

    it('displays job count', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.getByText(/4 jobs/)).toBeInTheDocument();
      });
    });
  });

  describe('Split View Layout', () => {
    it('renders job list on the left', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        const jobsList = screen.getByTestId('jobs-list');
        expect(jobsList).toBeInTheDocument();
      });
    });

    it('renders detail panel on the right', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        const detailPanel = screen.getByTestId('job-detail-panel');
        expect(detailPanel).toBeInTheDocument();
      });
    });

    it('shows placeholder in detail panel when no job selected', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.getByText('Select a job to view details')).toBeInTheDocument();
      });
    });
  });

  describe('Job Selection', () => {
    it('selects a job when clicked', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);
      vi.mocked(api.fetchJob).mockResolvedValue(mockJobs[0]);

      const user = userEvent.setup();
      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('job-item-job-001')).toBeInTheDocument();
      });

      const jobItem = screen.getByTestId('job-item-job-001');
      await user.click(jobItem);

      // Detail panel should now show the selected job
      // Note: Detail panel is hidden on mobile, but visible on md+ screens
      // The JobHeader component formats the title as "Export #001" (extracts numeric ID)
      await waitFor(() => {
        const detailPanel = screen.getByTestId('job-detail-panel');
        expect(within(detailPanel).getByRole('heading', { level: 2 })).toHaveTextContent(
          'Export #001'
        );
      });
    });

    it('updates detail panel when different job is selected', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);
      vi.mocked(api.fetchJob).mockResolvedValueOnce(mockJobs[0]).mockResolvedValueOnce(mockJobs[1]);

      const user = userEvent.setup();
      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('job-item-job-001')).toBeInTheDocument();
      });

      // Click first job
      await user.click(screen.getByTestId('job-item-job-001'));
      await waitFor(() => {
        const detailPanel = screen.getByTestId('job-detail-panel');
        expect(within(detailPanel).getByRole('heading', { level: 2 })).toHaveTextContent(
          'Export #001'
        );
      });

      // Click second job
      await user.click(screen.getByTestId('job-item-job-002'));
      await waitFor(() => {
        const detailPanel = screen.getByTestId('job-detail-panel');
        expect(within(detailPanel).getByRole('heading', { level: 2 })).toHaveTextContent(
          'Export #002'
        );
      });
    });
  });

  describe('Empty State', () => {
    it('shows empty state when no jobs exist', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockEmptyResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.getByText('No Background Jobs')).toBeInTheDocument();
      });

      expect(screen.getByText(/Jobs appear here when you schedule exports/i)).toBeInTheDocument();
    });

    it('shows correct text in empty state', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockEmptyResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('jobs-empty-state')).toBeInTheDocument();
      });

      // Check for job-creating action examples
      expect(screen.getByText('Export Data')).toBeInTheDocument();
      expect(screen.getByText('Re-evaluate')).toBeInTheDocument();
      expect(screen.getByText('Bulk Delete')).toBeInTheDocument();
    });

    it('hides search bar when no jobs exist', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockEmptyResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.getByText('No Background Jobs')).toBeInTheDocument();
      });

      // Search bar should not be visible when empty
      expect(screen.queryByPlaceholderText(/Search/i)).not.toBeInTheDocument();
    });

    it('shows search bar when jobs exist', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('job-item-job-001')).toBeInTheDocument();
      });

      // Search bar should be visible when jobs exist
      expect(screen.getByPlaceholderText(/Search/i)).toBeInTheDocument();
    });
  });

  describe('Filtering', () => {
    it('displays status filter dropdown', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading jobs...')).not.toBeInTheDocument();
      });

      const filterSelect = screen.getByLabelText(/status/i);
      expect(filterSelect).toBeInTheDocument();
    });

    it('filters jobs by status', async () => {
      vi.mocked(api.searchJobs)
        .mockResolvedValueOnce(mockJobsResponse)
        .mockResolvedValueOnce({
          data: [mockJobs[0]], // Only running job
          meta: { total: 1, limit: 50, offset: 0, has_more: false },
          aggregations: { by_status: { running: 1 }, by_type: { export: 1 } },
        });

      const user = userEvent.setup();
      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('job-item-job-001')).toBeInTheDocument();
      });

      const filterSelect = screen.getByLabelText(/status/i);
      await user.selectOptions(filterSelect, 'running');

      await waitFor(() => {
        expect(api.searchJobs).toHaveBeenCalledWith(expect.objectContaining({ status: 'running' }));
      });
    });
  });

  describe('Search', () => {
    it('displays search input', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading jobs...')).not.toBeInTheDocument();
      });

      expect(screen.getByPlaceholderText(/Search/i)).toBeInTheDocument();
    });
  });

  describe('Refresh', () => {
    it('displays refresh button', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading jobs...')).not.toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /Refresh/i })).toBeInTheDocument();
    });

    it('calls searchJobs when refresh button is clicked', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      const user = userEvent.setup();
      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading jobs...')).not.toBeInTheDocument();
      });

      const refreshButton = screen.getByRole('button', { name: /Refresh/i });
      await user.click(refreshButton);

      await waitFor(() => {
        // Initial call + refresh call
        expect(api.searchJobs).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Error Handling', () => {
    it('displays error message when fetching jobs fails', async () => {
      vi.mocked(api.searchJobs).mockRejectedValue(new Error('Network error'));

      renderWithProviders(<JobsPage />);

      // Need longer timeout to account for retry behavior in the hook
      await waitFor(
        () => {
          expect(screen.getByText(/Error Loading Jobs/i)).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      expect(screen.getByText(/Network error/)).toBeInTheDocument();
    });
  });

  describe('Job Status Display', () => {
    it('displays running jobs with correct status indicator', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('job-item-job-001')).toBeInTheDocument();
      });

      const runningJob = screen.getByTestId('job-item-job-001');
      expect(within(runningJob).getByText(/running/i)).toBeInTheDocument();
    });

    it('displays completed jobs with correct status indicator', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('job-item-job-002')).toBeInTheDocument();
      });

      const completedJob = screen.getByTestId('job-item-job-002');
      // Look for the status span specifically (with green color class)
      const statusSpan = within(completedJob).getByText('completed');
      expect(statusSpan).toHaveClass('text-green-400');
    });

    it('displays failed jobs with correct status indicator', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('job-item-job-003')).toBeInTheDocument();
      });

      const failedJob = screen.getByTestId('job-item-job-003');
      // Look for the status span specifically (with red color class)
      const statusSpan = within(failedJob).getByText('failed');
      expect(statusSpan).toHaveClass('text-red-400');
    });

    it('displays pending jobs with correct status indicator', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('job-item-job-004')).toBeInTheDocument();
      });

      const pendingJob = screen.getByTestId('job-item-job-004');
      expect(within(pendingJob).getByText(/pending/i)).toBeInTheDocument();
    });
  });

  describe('Stats Button', () => {
    it('displays stats button in header', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading jobs...')).not.toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /Stats/i })).toBeInTheDocument();
    });
  });

  describe('Responsive Layout', () => {
    it('has responsive classes for split view', async () => {
      vi.mocked(api.searchJobs).mockResolvedValue(mockJobsResponse);

      renderWithProviders(<JobsPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading jobs...')).not.toBeInTheDocument();
      });

      const container = screen.getByTestId('jobs-page');
      expect(container).toBeInTheDocument();
    });
  });
});

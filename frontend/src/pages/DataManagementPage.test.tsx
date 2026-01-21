/**
 * DataManagementPage Tests
 *
 * Tests for the Data Management page that provides:
 * - Export scheduling interface
 * - Export job history and status
 * - Backup creation controls
 *
 * @see NEM-3177
 */

import { screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import DataManagementPage from './DataManagementPage';
import * as api from '../services/api';
import { renderWithProviders } from '../test-utils/renderWithProviders';

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
    downloadExportFile: vi.fn(),
  };
});

// ============================================================================
// Test Data
// ============================================================================

const mockPendingJob: ExportJob = {
  id: 'pending-job-123',
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

const mockRunningJob: ExportJob = {
  id: 'running-job-456',
  status: 'running',
  export_type: 'events',
  export_format: 'json',
  progress: {
    total_items: 100,
    processed_items: 50,
    progress_percent: 50,
    current_step: 'Exporting events...',
    estimated_completion: '2025-01-21T10:05:00Z',
  },
  created_at: '2025-01-21T10:00:00Z',
  started_at: '2025-01-21T10:00:01Z',
  completed_at: null,
  result: null,
  error_message: null,
};

const mockCompletedJob: ExportJob = {
  id: 'completed-job-789',
  status: 'completed',
  export_type: 'events',
  export_format: 'csv',
  progress: {
    total_items: 100,
    processed_items: 100,
    progress_percent: 100,
    current_step: 'Complete',
    estimated_completion: null,
  },
  created_at: '2025-01-21T09:00:00Z',
  started_at: '2025-01-21T09:00:01Z',
  completed_at: '2025-01-21T09:01:00Z',
  result: {
    output_path: '/api/exports/completed-job-789/download',
    output_size_bytes: 12345,
    event_count: 100,
    format: 'csv',
  },
  error_message: null,
};

const mockFailedJob: ExportJob = {
  id: 'failed-job-999',
  status: 'failed',
  export_type: 'full_backup',
  export_format: 'zip',
  progress: {
    total_items: 100,
    processed_items: 25,
    progress_percent: 25,
    current_step: 'Failed',
    estimated_completion: null,
  },
  created_at: '2025-01-21T08:00:00Z',
  started_at: '2025-01-21T08:00:01Z',
  completed_at: '2025-01-21T08:00:30Z',
  result: null,
  error_message: 'Disk space exhausted',
};

const mockExportJobList: ExportJobListResponse = {
  items: [mockPendingJob, mockRunningJob, mockCompletedJob, mockFailedJob],
  pagination: {
    total: 4,
    limit: 50,
    offset: 0,
    cursor: null,
    next_cursor: null,
    has_more: false,
  },
};

const emptyJobList: ExportJobListResponse = {
  items: [],
  pagination: {
    total: 0,
    limit: 50,
    offset: 0,
    cursor: null,
    next_cursor: null,
    has_more: false,
  },
};

// ============================================================================
// Tests
// ============================================================================

describe('DataManagementPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('should render the page title', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(emptyJobList);

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByText('Data Management')).toBeInTheDocument();
      });
    });

    it('should render the export section', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(emptyJobList);

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /Export Data/i })).toBeInTheDocument();
      });
    });

    it('should show loading state initially', () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));

      renderWithProviders(<DataManagementPage />);

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });
  });

  describe('export form', () => {
    it('should render export type selector', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(emptyJobList);

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/Export Type/i)).toBeInTheDocument();
      });
    });

    it('should render export format selector', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(emptyJobList);

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/Format/i)).toBeInTheDocument();
      });
    });

    it('should render date range inputs', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(emptyJobList);

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByLabelText(/Start Date/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/End Date/i)).toBeInTheDocument();
      });
    });

    it('should render start export button', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(emptyJobList);

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Start Export/i })).toBeInTheDocument();
      });
    });

    it('should start export when button is clicked', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(emptyJobList);
      (api.startExportJob as ReturnType<typeof vi.fn>).mockResolvedValue({
        job_id: 'new-job',
        status: 'pending',
        message: 'Export started',
      });

      const { user } = renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Start Export/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Start Export/i }));

      await waitFor(() => {
        expect(api.startExportJob).toHaveBeenCalled();
      });
    });
  });

  describe('export job list', () => {
    it('should display export jobs when available', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(mockExportJobList);

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByText('pending-job-123')).toBeInTheDocument();
      });
    });

    it('should show job status for each job', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(mockExportJobList);

      renderWithProviders(<DataManagementPage />);

      // Wait for jobs to load
      await waitFor(() => {
        expect(screen.getByText('pending-job-123')).toBeInTheDocument();
      });

      // Check status badges - they should all be present
      expect(screen.getByText('Pending')).toBeInTheDocument();
      expect(screen.getByText('Running')).toBeInTheDocument();
      expect(screen.getByText('Completed')).toBeInTheDocument();
      expect(screen.getByText('Failed')).toBeInTheDocument();
    });

    it('should show progress for running jobs', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockExportJobList,
        items: [mockRunningJob],
      });

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByText(/50%/i)).toBeInTheDocument();
      });
    });

    it('should show download button for completed jobs', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockExportJobList,
        items: [mockCompletedJob],
      });

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Download/i })).toBeInTheDocument();
      });
    });

    it('should show error message for failed jobs', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockExportJobList,
        items: [mockFailedJob],
      });

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByText(/Disk space exhausted/i)).toBeInTheDocument();
      });
    });

    it('should show cancel button for pending/running jobs', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockExportJobList,
        items: [mockRunningJob],
      });

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
      });
    });

    it('should show empty state when no jobs exist', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(emptyJobList);

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByText(/No export jobs/i)).toBeInTheDocument();
      });
    });
  });

  describe('job actions', () => {
    it('should cancel a job when cancel button is clicked', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockExportJobList,
        items: [mockRunningJob],
      });
      (api.cancelExportJob as ReturnType<typeof vi.fn>).mockResolvedValue({
        job_id: 'running-job-456',
        status: 'failed',
        message: 'Cancelled',
        cancelled: true,
      });

      const { user } = renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Cancel/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Cancel/i }));

      await waitFor(() => {
        expect(api.cancelExportJob).toHaveBeenCalledWith('running-job-456');
      });
    });

    it('should download file when download button is clicked', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockExportJobList,
        items: [mockCompletedJob],
      });
      (api.downloadExportFile as ReturnType<typeof vi.fn>).mockResolvedValue(undefined);

      const { user } = renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Download/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Download/i }));

      await waitFor(() => {
        expect(api.downloadExportFile).toHaveBeenCalledWith('completed-job-789');
      });
    });
  });

  describe('backup section', () => {
    it('should render backup section', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(emptyJobList);

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByText(/Database Backup/i)).toBeInTheDocument();
      });
    });

    it('should render create backup button', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(emptyJobList);

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Create Backup/i })).toBeInTheDocument();
      });
    });
  });

  describe('error handling', () => {
    it('should show error when fetching jobs fails', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('Failed to fetch')
      );

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByText(/Failed to load export jobs/i)).toBeInTheDocument();
      });
    });
  });

  describe('accessibility', () => {
    it('should have data-testid for page', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(emptyJobList);

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByTestId('data-management-page')).toBeInTheDocument();
      });
    });
  });
});

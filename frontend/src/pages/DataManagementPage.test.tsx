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

import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
    // F4.3: Trash retention settings (Settings › Data)
    fetchConfig: vi.fn(),
    updateConfig: vi.fn(),
  };
});

// The Trash retention card toasts on save/failure (no <Toaster> mounts in
// tests, so sonner renders nothing — assert on the hook's calls instead).
const mockShowSuccess = vi.fn();
const mockShowError = vi.fn();
vi.mock('../hooks/useToast', () => ({
  useToast: () => ({
    success: mockShowSuccess,
    error: mockShowError,
    info: vi.fn(),
    warning: vi.fn(),
  }),
}));

// Minimal SystemConfig for the Trash retention card; other fields are filler.
const mockSystemConfig = {
  app_name: 'Home Security Intelligence',
  batch_idle_timeout_seconds: 30,
  batch_window_seconds: 90,
  debug: false,
  detection_confidence_threshold: 0.5,
  fast_path_confidence_threshold: 0.9,
  fast_path_enabled: false,
  grafana_url: '/grafana',
  log_retention_days: 7,
  retention_days: 30,
  trash_retention_days: 30,
  version: '0.1.0',
};

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
  filter_params: null,
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
  filter_params: '{"camera_id":"front_door","risk_level":"high"}',
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
  filter_params: '{"start_date":"2025-01-01","end_date":"2025-01-20"}',
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
  filter_params: null,
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

      // Shipped card shows the TRUNCATED id (job.id.slice(0,8)+'...',
      // DataManagementPage.tsx:301); the full id lives on the card's
      // data-testid. Test was written against full-id-as-text — aligned
      // to the shipped contract.
      await waitFor(() => {
        expect(screen.getByTestId('export-job-pending-job-123')).toBeInTheDocument();
      });
    });

    it('should show job status for each job', async () => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(mockExportJobList);

      renderWithProviders(<DataManagementPage />);

      // Wait for jobs to load (testid — card text is truncated id)
      await waitFor(() => {
        expect(screen.getByTestId('export-job-pending-job-123')).toBeInTheDocument();
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

  // F4.3 (spec 4n-trash.md): the trash_retention_days setting lives under
  // Settings › Data — this page. 0 disables the Trash clock; the backend
  // validates ge=0, le=365.
  describe('Trash Retention (F4.3)', () => {
    beforeEach(() => {
      (api.listExportJobs as ReturnType<typeof vi.fn>).mockResolvedValue(emptyJobList);
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockSystemConfig);
    });

    it('renders the current trash_retention_days from config', async () => {
      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-retention-value')).toHaveTextContent('30 days');
      });
    });

    it('enables Save only after the slider moves and sends a partial PATCH', async () => {
      const user = userEvent.setup();
      // The PATCH answers, then the invalidated config query refetches and
      // the server reports the new value.
      (api.updateConfig as ReturnType<typeof vi.fn>).mockResolvedValue(mockSystemConfig);
      (api.fetchConfig as ReturnType<typeof vi.fn>)
        .mockResolvedValueOnce(mockSystemConfig)
        .mockResolvedValueOnce({ ...mockSystemConfig, trash_retention_days: 14 });

      renderWithProviders(<DataManagementPage />);

      const save = await screen.findByTestId('trash-retention-save');
      expect(save).toBeDisabled();

      // Move the slider 30 → 14 (fireEvent for the range input; userEvent
      // does not synthesize native range drags reliably here).
      const slider = screen.getByTestId('trash-retention-slider');
      fireEvent.change(slider, { target: { value: '14' } });

      expect(save).toBeEnabled();
      expect(screen.getByTestId('trash-retention-value')).toHaveTextContent('14 days');

      await user.click(save);

      await waitFor(() => {
        expect(api.updateConfig).toHaveBeenCalledWith({ trash_retention_days: 14 });
      });
      // Partial PATCH only — no other config key travels.
      expect(api.updateConfig).toHaveBeenCalledTimes(1);
      expect(mockShowSuccess).toHaveBeenCalledWith('Trash retention updated to 14 days');
      // The card refetched config after the PATCH: the header shows the
      // server's new value and Save is clean (disabled) again.
      await waitFor(() => {
        expect(screen.getByTestId('trash-retention-value')).toHaveTextContent('14 days');
      });
      expect(save).toBeDisabled();
    });

    it('Reset returns the slider to the server value without a request', async () => {
      const user = userEvent.setup();

      renderWithProviders(<DataManagementPage />);

      const save = await screen.findByTestId('trash-retention-save');
      fireEvent.change(screen.getByTestId('trash-retention-slider'), { target: { value: '90' } });
      expect(save).toBeEnabled();

      await user.click(screen.getByTestId('trash-retention-reset'));

      expect(screen.getByTestId('trash-retention-value')).toHaveTextContent('30 days');
      expect(save).toBeDisabled();
      expect(api.updateConfig).not.toHaveBeenCalled();
    });

    it('with trash_retention_days = 0 the copy names the disabled clock', async () => {
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockResolvedValue({
        ...mockSystemConfig,
        trash_retention_days: 0,
      });

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(screen.getByTestId('trash-retention-value')).toHaveTextContent('0 days');
      });
      expect(screen.getByText(/0 disables the Trash clock/i)).toBeInTheDocument();
    });

    it('states the setting is unavailable when the backend omits the field', async () => {
      // Spread drops trash_retention_days entirely: pre-B4.4 backend.
      const { trash_retention_days: _omitted, ...withoutTrash } = mockSystemConfig;
      (api.fetchConfig as ReturnType<typeof vi.fn>).mockResolvedValue(withoutTrash);

      renderWithProviders(<DataManagementPage />);

      await waitFor(() => {
        expect(
          screen.getByText(/does not report a Trash retention setting/i)
        ).toBeInTheDocument();
      });
      expect(screen.queryByTestId('trash-retention-slider')).not.toBeInTheDocument();
    });

    it('toasts an error when the save fails and keeps the edit armed', async () => {
      const user = userEvent.setup();
      (api.updateConfig as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('disk full'));

      renderWithProviders(<DataManagementPage />);

      const save = await screen.findByTestId('trash-retention-save');
      fireEvent.change(screen.getByTestId('trash-retention-slider'), { target: { value: '14' } });
      await user.click(save);

      await waitFor(() => {
        expect(mockShowError).toHaveBeenCalledWith('disk full');
      });
      // The edit stays armed — the operator can retry or Reset.
      expect(save).toBeEnabled();
    });
  });
});

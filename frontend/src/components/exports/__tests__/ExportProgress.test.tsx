/**
 * Tests for ExportProgress component (NEM-2386)
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

// Mock the API functions
vi.mock('../../../services/api', () => ({
  getExportStatus: vi.fn(),
  cancelExportJob: vi.fn(),
  downloadExportFile: vi.fn(),
}));

import { getExportStatus, cancelExportJob, downloadExportFile } from '../../../services/api';
import ExportProgress from '../ExportProgress';

import type { ExportJob } from '../../../types/export';

const mockGetExportStatus = vi.mocked(getExportStatus);
const mockCancelExportJob = vi.mocked(cancelExportJob);
const mockDownloadExportFile = vi.mocked(downloadExportFile);

// Sample export job data
const runningJob: ExportJob = {
  id: 'test-job-123',
  status: 'running',
  export_type: 'events',
  export_format: 'csv',
  progress: {
    total_items: 1000,
    processed_items: 500,
    progress_percent: 50,
    current_step: 'Processing events...',
    estimated_completion: null,
  },
  created_at: '2025-01-12T10:00:00Z',
  started_at: '2025-01-12T10:00:01Z',
  completed_at: null,
  filter_params: null,
  result: null,
  error_message: null,
};

const completedJob: ExportJob = {
  id: 'test-job-123',
  status: 'completed',
  export_type: 'events',
  export_format: 'csv',
  progress: {
    total_items: 1000,
    processed_items: 1000,
    progress_percent: 100,
    current_step: 'Complete',
    estimated_completion: null,
  },
  created_at: '2025-01-12T10:00:00Z',
  started_at: '2025-01-12T10:00:01Z',
  completed_at: '2025-01-12T10:01:00Z',
  filter_params: null,
  result: {
    output_path: '/api/exports/test.csv',
    output_size_bytes: 12345,
    event_count: 1000,
    format: 'csv',
  },
  error_message: null,
};

const failedJob: ExportJob = {
  id: 'test-job-123',
  status: 'failed',
  export_type: 'events',
  export_format: 'csv',
  progress: {
    total_items: 1000,
    processed_items: 500,
    progress_percent: 50,
    current_step: 'Failed',
    estimated_completion: null,
  },
  created_at: '2025-01-12T10:00:00Z',
  started_at: '2025-01-12T10:00:01Z',
  completed_at: '2025-01-12T10:00:30Z',
  filter_params: null,
  result: null,
  error_message: 'Database connection error',
};

describe('ExportProgress', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading State', () => {
    it('renders loading state initially', () => {
      // Create a promise that never resolves
      mockGetExportStatus.mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(<ExportProgress jobId="test-job-123" />);

      expect(screen.getByText('Loading export status...')).toBeInTheDocument();
    });
  });

  describe('Running State', () => {
    it('renders progress bar when job is running', async () => {
      mockGetExportStatus.mockResolvedValue(runningJob);

      render(<ExportProgress jobId="test-job-123" />);

      await waitFor(() => {
        expect(screen.getByText('50%')).toBeInTheDocument();
      });

      expect(screen.getByText('Processing events...')).toBeInTheDocument();
      expect(screen.getByText('500 / 1,000 items')).toBeInTheDocument();
    });

    it('renders cancel button when job is running', async () => {
      mockGetExportStatus.mockResolvedValue(runningJob);

      render(<ExportProgress jobId="test-job-123" />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      });
    });

    it('shows confirmation when cancel is clicked', async () => {
      mockGetExportStatus.mockResolvedValue(runningJob);
      const user = userEvent.setup();

      render(<ExportProgress jobId="test-job-123" />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      expect(screen.getByText('Cancel export?')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /no/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /yes/i })).toBeInTheDocument();
    });

    it('cancels job when confirmed', async () => {
      // First call returns running job, subsequent calls return the cancelled job
      mockGetExportStatus.mockResolvedValue(runningJob);
      mockCancelExportJob.mockResolvedValue({
        job_id: 'test-job-123',
        status: 'failed',
        message: 'Cancelled',
        cancelled: true,
      });

      const onCancel = vi.fn();
      const user = userEvent.setup();

      render(<ExportProgress jobId="test-job-123" onCancel={onCancel} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      });

      // Click cancel (shows confirmation)
      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      // Update mock for subsequent calls
      mockGetExportStatus.mockResolvedValue(failedJob);

      const yesButton = screen.getByRole('button', { name: /yes/i });
      await user.click(yesButton);

      await waitFor(() => {
        expect(mockCancelExportJob).toHaveBeenCalledWith('test-job-123');
        expect(onCancel).toHaveBeenCalled();
      });
    });
  });

  describe('Completed State', () => {
    it('renders download button when job is complete', async () => {
      mockGetExportStatus.mockResolvedValue(completedJob);

      render(<ExportProgress jobId="test-job-123" />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /download csv/i })).toBeInTheDocument();
      });
    });

    it('shows completion info when job is complete', async () => {
      mockGetExportStatus.mockResolvedValue(completedJob);

      render(<ExportProgress jobId="test-job-123" />);

      await waitFor(() => {
        expect(screen.getByText('100%')).toBeInTheDocument();
      });

      // Should show file size
      expect(screen.getByText(/12\.1 KB/i)).toBeInTheDocument();

      // Should show duration
      expect(screen.getByText(/completed in 59s/i)).toBeInTheDocument();
    });

    it('calls onComplete when job completes', async () => {
      mockGetExportStatus.mockResolvedValue(completedJob);

      const onComplete = vi.fn();

      render(<ExportProgress jobId="test-job-123" onComplete={onComplete} />);

      await waitFor(() => {
        expect(onComplete).toHaveBeenCalledWith('/api/exports/test.csv');
      });
    });

    it('triggers download when download button is clicked', async () => {
      mockGetExportStatus.mockResolvedValue(completedJob);
      mockDownloadExportFile.mockResolvedValue(undefined);

      const user = userEvent.setup();

      render(<ExportProgress jobId="test-job-123" />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /download csv/i })).toBeInTheDocument();
      });

      const downloadButton = screen.getByRole('button', { name: /download csv/i });
      await user.click(downloadButton);

      await waitFor(() => {
        expect(mockDownloadExportFile).toHaveBeenCalledWith('test-job-123');
      });
    });
  });

  describe('Failed State', () => {
    it('renders error message when job fails', async () => {
      mockGetExportStatus.mockResolvedValue(failedJob);

      render(<ExportProgress jobId="test-job-123" />);

      await waitFor(() => {
        expect(screen.getByText('Database connection error')).toBeInTheDocument();
      });
    });

    it('calls onError when job fails', async () => {
      mockGetExportStatus.mockResolvedValue(failedJob);

      const onError = vi.fn();

      render(<ExportProgress jobId="test-job-123" onError={onError} />);

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith('Database connection error');
      });
    });
  });

  describe('Compact Mode', () => {
    it('renders compact version correctly', async () => {
      mockGetExportStatus.mockResolvedValue(runningJob);

      render(<ExportProgress jobId="test-job-123" compact />);

      await waitFor(() => {
        expect(screen.getByText('50%')).toBeInTheDocument();
      });

      // Should not show full card in compact mode
      expect(screen.queryByText('CSV Export')).not.toBeInTheDocument();
    });

    it('renders compact completed state', async () => {
      mockGetExportStatus.mockResolvedValue(completedJob);

      render(<ExportProgress jobId="test-job-123" compact />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /download/i })).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('renders error state when API call fails', async () => {
      mockGetExportStatus.mockRejectedValue(new Error('Network error'));

      const onError = vi.fn();

      render(<ExportProgress jobId="test-job-123" onError={onError} />);

      await waitFor(() => {
        expect(screen.getByText('Network error')).toBeInTheDocument();
      });

      expect(onError).toHaveBeenCalledWith('Network error');
    });
  });
});

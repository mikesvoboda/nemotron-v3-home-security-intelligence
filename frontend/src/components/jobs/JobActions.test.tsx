/**
 * Tests for JobActions component (NEM-2712).
 *
 * Tests action button rendering based on job status and user interactions:
 * - Pending: Cancel, Delete available
 * - Running (Processing): Cancel, Abort available
 * - Completed: Delete available
 * - Failed: Retry, Delete available
 * - Cancelled: Retry, Delete available
 *
 * @see docs/developer/patterns/AGENTS.md for testing patterns
 */
import { screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import JobActions from './JobActions';
import { useJobMutations } from '../../hooks/useJobMutations';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

import type { JobStatusEnum } from '../../types/generated';

// Mock the useJobMutations hook
vi.mock('../../hooks/useJobMutations', () => ({
  useJobMutations: vi.fn(() => ({
    cancelJob: vi.fn(),
    abortJob: vi.fn(),
    retryJob: vi.fn(),
    deleteJob: vi.fn(),
    isCancelling: false,
    isAborting: false,
    isRetrying: false,
    isDeleting: false,
    isMutating: false,
    error: null,
    reset: vi.fn(),
  })),
}));

// Mock the ConfirmDialog component to simplify testing
vi.mock('./ConfirmDialog', () => ({
  default: vi.fn(({ isOpen, title, onConfirm, onCancel }) => {
    if (!isOpen) return null;
    return (
      <div data-testid="confirm-dialog" role="dialog">
        <p>{title}</p>
        <button onClick={onConfirm} data-testid="dialog-confirm">
          Confirm
        </button>
        <button onClick={onCancel} data-testid="dialog-cancel">
          Cancel
        </button>
      </div>
    );
  }),
}));

describe('JobActions', () => {
  const mockJob = {
    job_id: 'job-123',
    job_type: 'export',
    status: 'pending' as JobStatusEnum,
    progress: 0,
    created_at: '2024-01-15T10:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset the mock to default implementation
    vi.mocked(useJobMutations).mockReturnValue({
      cancelJob: vi.fn(),
      abortJob: vi.fn(),
      retryJob: vi.fn(),
      deleteJob: vi.fn(),
      isCancelling: false,
      isAborting: false,
      isRetrying: false,
      isDeleting: false,
      isMutating: false,
      error: null,
      reset: vi.fn(),
    });
  });

  describe('action availability by status', () => {
    it('shows Cancel and Delete for pending jobs', () => {
      renderWithProviders(<JobActions job={{ ...mockJob, status: 'pending' }} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /abort/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
    });

    it('shows Cancel and Abort for running jobs', () => {
      renderWithProviders(<JobActions job={{ ...mockJob, status: 'running' }} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /abort/i })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
    });

    it('shows only Delete for completed jobs', () => {
      renderWithProviders(<JobActions job={{ ...mockJob, status: 'completed' }} />);

      expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /cancel/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /abort/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
    });

    it('shows Retry and Delete for failed jobs', () => {
      renderWithProviders(<JobActions job={{ ...mockJob, status: 'failed' }} />);

      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /delete/i })).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /cancel/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /abort/i })).not.toBeInTheDocument();
    });
  });

  describe('confirmation dialogs', () => {
    it('shows confirmation dialog when cancel is clicked', async () => {
      const { user } = renderWithProviders(<JobActions job={{ ...mockJob, status: 'pending' }} />);

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      // The mock ConfirmDialog renders the title
      expect(screen.getByText(/Cancel Job/i)).toBeInTheDocument();
    });

    it('shows warning dialog when abort is clicked', async () => {
      const { user } = renderWithProviders(<JobActions job={{ ...mockJob, status: 'running' }} />);

      await user.click(screen.getByRole('button', { name: /abort/i }));

      expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      // The mock ConfirmDialog renders the title
      expect(screen.getByText(/Force Abort Job/i)).toBeInTheDocument();
    });

    it('shows confirmation dialog when delete is clicked', async () => {
      const { user } = renderWithProviders(
        <JobActions job={{ ...mockJob, status: 'completed' }} />
      );

      await user.click(screen.getByRole('button', { name: /delete/i }));

      expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();
      // The mock ConfirmDialog renders the title
      expect(screen.getByText(/Delete Job/i)).toBeInTheDocument();
    });

    it('closes dialog when cancel is clicked in dialog', async () => {
      const { user } = renderWithProviders(<JobActions job={{ ...mockJob, status: 'pending' }} />);

      await user.click(screen.getByRole('button', { name: /cancel/i }));
      expect(screen.getByTestId('confirm-dialog')).toBeInTheDocument();

      await user.click(screen.getByTestId('dialog-cancel'));
      expect(screen.queryByTestId('confirm-dialog')).not.toBeInTheDocument();
    });
  });

  describe('action execution', () => {
    it('calls cancelJob when confirmed', async () => {
      const cancelJob = vi.fn().mockResolvedValue({});
      vi.mocked(useJobMutations).mockReturnValue({
        cancelJob,
        abortJob: vi.fn(),
        retryJob: vi.fn(),
        deleteJob: vi.fn(),
        isCancelling: false,
        isAborting: false,
        isRetrying: false,
        isDeleting: false,
        isMutating: false,
        error: null,
        reset: vi.fn(),
      });

      const { user } = renderWithProviders(<JobActions job={{ ...mockJob, status: 'pending' }} />);

      await user.click(screen.getByRole('button', { name: /cancel/i }));
      await user.click(screen.getByTestId('dialog-confirm'));

      expect(cancelJob).toHaveBeenCalledWith('job-123');
    });

    it('calls abortJob when confirmed', async () => {
      const abortJob = vi.fn().mockResolvedValue({});
      vi.mocked(useJobMutations).mockReturnValue({
        cancelJob: vi.fn(),
        abortJob,
        retryJob: vi.fn(),
        deleteJob: vi.fn(),
        isCancelling: false,
        isAborting: false,
        isRetrying: false,
        isDeleting: false,
        isMutating: false,
        error: null,
        reset: vi.fn(),
      });

      const { user } = renderWithProviders(<JobActions job={{ ...mockJob, status: 'running' }} />);

      await user.click(screen.getByRole('button', { name: /abort/i }));
      await user.click(screen.getByTestId('dialog-confirm'));

      expect(abortJob).toHaveBeenCalledWith('job-123');
    });

    it('calls retryJob when retry button is clicked', async () => {
      const retryJob = vi.fn().mockResolvedValue({ job_id: 'new-job-456', progress: 0 });
      vi.mocked(useJobMutations).mockReturnValue({
        cancelJob: vi.fn(),
        abortJob: vi.fn(),
        retryJob,
        deleteJob: vi.fn(),
        isCancelling: false,
        isAborting: false,
        isRetrying: false,
        isDeleting: false,
        isMutating: false,
        error: null,
        reset: vi.fn(),
      });

      const { user } = renderWithProviders(<JobActions job={{ ...mockJob, status: 'failed' }} />);

      await user.click(screen.getByRole('button', { name: /retry/i }));

      // Retry does not require confirmation
      expect(retryJob).toHaveBeenCalledWith('job-123');
    });

    it('calls deleteJob when confirmed', async () => {
      const deleteJob = vi.fn().mockResolvedValue({});
      vi.mocked(useJobMutations).mockReturnValue({
        cancelJob: vi.fn(),
        abortJob: vi.fn(),
        retryJob: vi.fn(),
        deleteJob,
        isCancelling: false,
        isAborting: false,
        isRetrying: false,
        isDeleting: false,
        isMutating: false,
        error: null,
        reset: vi.fn(),
      });

      const { user } = renderWithProviders(
        <JobActions job={{ ...mockJob, status: 'completed' }} />
      );

      await user.click(screen.getByRole('button', { name: /delete/i }));
      await user.click(screen.getByTestId('dialog-confirm'));

      expect(deleteJob).toHaveBeenCalledWith('job-123');
    });
  });

  describe('loading states', () => {
    it('shows loading state when cancelling', () => {
      vi.mocked(useJobMutations).mockReturnValue({
        cancelJob: vi.fn(),
        abortJob: vi.fn(),
        retryJob: vi.fn(),
        deleteJob: vi.fn(),
        isCancelling: true,
        isAborting: false,
        isRetrying: false,
        isDeleting: false,
        isMutating: true,
        error: null,
        reset: vi.fn(),
      });

      renderWithProviders(<JobActions job={{ ...mockJob, status: 'pending' }} />);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      expect(cancelButton).toBeDisabled();
    });

    it('shows loading state when aborting', () => {
      vi.mocked(useJobMutations).mockReturnValue({
        cancelJob: vi.fn(),
        abortJob: vi.fn(),
        retryJob: vi.fn(),
        deleteJob: vi.fn(),
        isCancelling: false,
        isAborting: true,
        isRetrying: false,
        isDeleting: false,
        isMutating: true,
        error: null,
        reset: vi.fn(),
      });

      renderWithProviders(<JobActions job={{ ...mockJob, status: 'running' }} />);

      const abortButton = screen.getByRole('button', { name: /abort/i });
      expect(abortButton).toBeDisabled();
    });

    it('shows loading state when retrying', () => {
      vi.mocked(useJobMutations).mockReturnValue({
        cancelJob: vi.fn(),
        abortJob: vi.fn(),
        retryJob: vi.fn(),
        deleteJob: vi.fn(),
        isCancelling: false,
        isAborting: false,
        isRetrying: true,
        isDeleting: false,
        isMutating: true,
        error: null,
        reset: vi.fn(),
      });

      renderWithProviders(<JobActions job={{ ...mockJob, status: 'failed' }} />);

      const retryButton = screen.getByRole('button', { name: /retry/i });
      expect(retryButton).toBeDisabled();
    });

    it('shows loading state when deleting', () => {
      vi.mocked(useJobMutations).mockReturnValue({
        cancelJob: vi.fn(),
        abortJob: vi.fn(),
        retryJob: vi.fn(),
        deleteJob: vi.fn(),
        isCancelling: false,
        isAborting: false,
        isRetrying: false,
        isDeleting: true,
        isMutating: true,
        error: null,
        reset: vi.fn(),
      });

      renderWithProviders(<JobActions job={{ ...mockJob, status: 'completed' }} />);

      const deleteButton = screen.getByRole('button', { name: /delete/i });
      expect(deleteButton).toBeDisabled();
    });

    it('disables all buttons during any mutation', () => {
      vi.mocked(useJobMutations).mockReturnValue({
        cancelJob: vi.fn(),
        abortJob: vi.fn(),
        retryJob: vi.fn(),
        deleteJob: vi.fn(),
        isCancelling: true,
        isAborting: false,
        isRetrying: false,
        isDeleting: false,
        isMutating: true,
        error: null,
        reset: vi.fn(),
      });

      renderWithProviders(<JobActions job={{ ...mockJob, status: 'pending' }} />);

      // All available buttons should be disabled
      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      const deleteButton = screen.getByRole('button', { name: /delete/i });
      expect(cancelButton).toBeDisabled();
      expect(deleteButton).toBeDisabled();
    });
  });

  describe('callbacks', () => {
    it('calls onSuccess callback after successful cancel', async () => {
      const onSuccess = vi.fn();
      const cancelJob = vi.fn().mockResolvedValue({ status: 'failed' });
      vi.mocked(useJobMutations).mockReturnValue({
        cancelJob,
        abortJob: vi.fn(),
        retryJob: vi.fn(),
        deleteJob: vi.fn(),
        isCancelling: false,
        isAborting: false,
        isRetrying: false,
        isDeleting: false,
        isMutating: false,
        error: null,
        reset: vi.fn(),
      });

      const { user } = renderWithProviders(
        <JobActions job={{ ...mockJob, status: 'pending' }} onSuccess={onSuccess} />
      );

      await user.click(screen.getByRole('button', { name: /cancel/i }));
      await user.click(screen.getByTestId('dialog-confirm'));

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith('cancel', { status: 'failed' });
      });
    });

    it('calls onError callback on failure', async () => {
      const onError = vi.fn();
      const error = new Error('Failed to cancel');
      const cancelJob = vi.fn().mockRejectedValue(error);
      vi.mocked(useJobMutations).mockReturnValue({
        cancelJob,
        abortJob: vi.fn(),
        retryJob: vi.fn(),
        deleteJob: vi.fn(),
        isCancelling: false,
        isAborting: false,
        isRetrying: false,
        isDeleting: false,
        isMutating: false,
        error: null,
        reset: vi.fn(),
      });

      const { user } = renderWithProviders(
        <JobActions job={{ ...mockJob, status: 'pending' }} onError={onError} />
      );

      await user.click(screen.getByRole('button', { name: /cancel/i }));
      await user.click(screen.getByTestId('dialog-confirm'));

      await waitFor(() => {
        expect(onError).toHaveBeenCalledWith('cancel', error);
      });
    });

    it('calls onDelete callback and navigates after delete', async () => {
      const onDelete = vi.fn();
      const deleteJob = vi.fn().mockResolvedValue({});
      vi.mocked(useJobMutations).mockReturnValue({
        cancelJob: vi.fn(),
        abortJob: vi.fn(),
        retryJob: vi.fn(),
        deleteJob,
        isCancelling: false,
        isAborting: false,
        isRetrying: false,
        isDeleting: false,
        isMutating: false,
        error: null,
        reset: vi.fn(),
      });

      const { user } = renderWithProviders(
        <JobActions job={{ ...mockJob, status: 'completed' }} onDelete={onDelete} />
      );

      await user.click(screen.getByRole('button', { name: /delete/i }));
      await user.click(screen.getByTestId('dialog-confirm'));

      await waitFor(() => {
        expect(onDelete).toHaveBeenCalled();
      });
    });

    it('calls onRetry callback with new job after retry', async () => {
      const onRetry = vi.fn();
      const newJob = {
        job_id: 'new-job-456',
        status: 'pending' as const,
        progress: 0,
        job_type: 'export',
        created_at: '2024-01-15T10:00:00Z',
      };
      const retryJob = vi.fn().mockResolvedValue(newJob);
      vi.mocked(useJobMutations).mockReturnValue({
        cancelJob: vi.fn(),
        abortJob: vi.fn(),
        retryJob,
        deleteJob: vi.fn(),
        isCancelling: false,
        isAborting: false,
        isRetrying: false,
        isDeleting: false,
        isMutating: false,
        error: null,
        reset: vi.fn(),
      });

      const { user } = renderWithProviders(
        <JobActions job={{ ...mockJob, status: 'failed' }} onRetry={onRetry} />
      );

      await user.click(screen.getByRole('button', { name: /retry/i }));

      await waitFor(() => {
        expect(onRetry).toHaveBeenCalledWith(newJob);
      });
    });
  });

  describe('compact mode', () => {
    it('renders icon-only buttons in compact mode', () => {
      renderWithProviders(<JobActions job={{ ...mockJob, status: 'pending' }} compact />);

      // Should have buttons but with sr-only text
      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      expect(cancelButton.querySelector('.sr-only')).toBeInTheDocument();
    });
  });
});

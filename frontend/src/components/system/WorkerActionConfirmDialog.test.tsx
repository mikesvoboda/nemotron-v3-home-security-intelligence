/**
 * Tests for WorkerActionConfirmDialog component (NEM-4831).
 *
 * Tests confirmation dialog functionality for worker actions including:
 * - Rendering title, description, and action buttons
 * - Warning variant for stop actions
 * - Loading states during async operations
 * - Keyboard and click interactions
 */
import { screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import WorkerActionConfirmDialog from './WorkerActionConfirmDialog';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

describe('WorkerActionConfirmDialog', () => {
  const defaultProps = {
    isOpen: true,
    workerName: 'file_watcher',
    action: 'stop' as const,
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders title with worker name when open', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} />);

      expect(screen.getByRole('heading', { name: /file_watcher/i })).toBeInTheDocument();
    });

    it('renders description for stop action', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} action="stop" />);

      const description = screen.getByRole('dialog').querySelector('p');
      expect(description).toHaveTextContent(/stop.*worker/i);
    });

    it('renders description for restart action', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} action="restart" />);

      const description = screen.getByRole('dialog').querySelector('p');
      expect(description).toHaveTextContent(/restart.*worker/i);
    });

    it('renders confirm and cancel buttons', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} />);

      expect(screen.getByRole('button', { name: /stop/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('uses restart label for restart action', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} action="restart" />);

      expect(screen.getByRole('button', { name: /restart/i })).toBeInTheDocument();
    });

    it('does not render when closed', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} isOpen={false} />);

      expect(screen.queryByText(/file_watcher/i)).not.toBeInTheDocument();
    });
  });

  describe('variants', () => {
    it('applies warning styling for stop action', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} action="stop" />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('data-variant', 'warning');
    });

    it('applies default styling for restart action', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} action="restart" />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('data-variant', 'default');
    });

    it('confirm button has warning colors for stop action', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} action="stop" />);

      const confirmButton = screen.getByRole('button', { name: /stop/i });
      expect(confirmButton).toHaveClass('bg-amber-600');
    });

    it('confirm button has primary colors for restart action', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} action="restart" />);

      const confirmButton = screen.getByRole('button', { name: /restart/i });
      expect(confirmButton).toHaveClass('bg-[#76B900]');
    });
  });

  describe('loading state', () => {
    it('shows loading spinner when isLoading is true', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} isLoading={true} />);

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('disables confirm button when loading', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} isLoading={true} />);

      expect(screen.getByRole('button', { name: /stop/i })).toBeDisabled();
    });

    it('disables cancel button when loading', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} isLoading={true} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
    });

    it('shows stopping text when loading stop action', () => {
      renderWithProviders(
        <WorkerActionConfirmDialog {...defaultProps} action="stop" isLoading={true} />
      );

      expect(screen.getByText(/stopping/i)).toBeInTheDocument();
    });

    it('shows restarting text when loading restart action', () => {
      renderWithProviders(
        <WorkerActionConfirmDialog {...defaultProps} action="restart" isLoading={true} />
      );

      expect(screen.getByText(/restarting/i)).toBeInTheDocument();
    });
  });

  describe('interactions', () => {
    it('calls onConfirm when confirm button is clicked', async () => {
      const onConfirm = vi.fn();
      const { user } = renderWithProviders(
        <WorkerActionConfirmDialog {...defaultProps} onConfirm={onConfirm} />
      );

      await user.click(screen.getByRole('button', { name: /stop/i }));

      expect(onConfirm).toHaveBeenCalledTimes(1);
    });

    it('calls onCancel when cancel button is clicked', async () => {
      const onCancel = vi.fn();
      const { user } = renderWithProviders(
        <WorkerActionConfirmDialog {...defaultProps} onCancel={onCancel} />
      );

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(onCancel).toHaveBeenCalledTimes(1);
    });

    it('calls onCancel when backdrop is clicked', async () => {
      const onCancel = vi.fn();
      const { user } = renderWithProviders(
        <WorkerActionConfirmDialog {...defaultProps} onCancel={onCancel} />
      );

      await user.click(screen.getByTestId('dialog-backdrop'));

      expect(onCancel).toHaveBeenCalledTimes(1);
    });

    it('calls onCancel when Escape key is pressed', async () => {
      const onCancel = vi.fn();
      const { user } = renderWithProviders(
        <WorkerActionConfirmDialog {...defaultProps} onCancel={onCancel} />
      );

      await user.keyboard('{Escape}');

      expect(onCancel).toHaveBeenCalledTimes(1);
    });

    it('does not call handlers when loading', async () => {
      const onConfirm = vi.fn();
      const onCancel = vi.fn();
      const { user } = renderWithProviders(
        <WorkerActionConfirmDialog
          {...defaultProps}
          onConfirm={onConfirm}
          onCancel={onCancel}
          isLoading={true}
        />
      );

      await user.click(screen.getByRole('button', { name: /stop/i }));
      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(onConfirm).not.toHaveBeenCalled();
      expect(onCancel).not.toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('has correct role for dialog', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('has aria-labelledby pointing to title', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-labelledby');

      const labelId = dialog.getAttribute('aria-labelledby');
      const titleElement = document.getElementById(labelId!);
      expect(titleElement).toHaveTextContent(/file_watcher/i);
    });

    it('has aria-describedby pointing to description', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-describedby');

      const descId = dialog.getAttribute('aria-describedby');
      const descElement = document.getElementById(descId!);
      expect(descElement).toHaveTextContent(/worker/i);
    });

    it('traps focus within the dialog', async () => {
      const { user } = renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} />);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      const confirmButton = screen.getByRole('button', { name: /stop/i });

      // Dialog opens with cancel button focused
      expect(cancelButton).toHaveFocus();

      // Tab moves to confirm button
      await user.tab();
      expect(confirmButton).toHaveFocus();

      // Tab should cycle back to cancel button (focus trap)
      await user.tab();
      expect(cancelButton).toHaveFocus();
    });

    it('has warning icon for stop action', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} action="stop" />);

      expect(screen.getByTestId('warning-icon')).toBeInTheDocument();
    });

    it('has info icon for restart action', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} action="restart" />);

      expect(screen.getByTestId('info-icon')).toBeInTheDocument();
    });
  });

  describe('worker name display', () => {
    it('displays worker name in title', () => {
      renderWithProviders(
        <WorkerActionConfirmDialog {...defaultProps} workerName="detection_worker" />
      );

      expect(screen.getByRole('heading', { name: /detection_worker/i })).toBeInTheDocument();
    });

    it('displays worker name in description', () => {
      renderWithProviders(
        <WorkerActionConfirmDialog {...defaultProps} workerName="batch_aggregator" />
      );

      const description = screen.getByRole('dialog').querySelector('p');
      expect(description).toHaveTextContent(/batch_aggregator/i);
    });

    it('handles long worker names gracefully', () => {
      const longName = 'very_long_worker_name_that_might_need_truncation';
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} workerName={longName} />);

      expect(screen.getByRole('heading', { name: new RegExp(longName, 'i') })).toBeInTheDocument();
    });
  });

  describe('testid attributes', () => {
    it('has correct testid for dialog', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} />);

      expect(screen.getByTestId('worker-action-confirm-dialog')).toBeInTheDocument();
    });

    it('has correct testid for confirm button', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} />);

      expect(screen.getByTestId('worker-action-confirm-button')).toBeInTheDocument();
    });

    it('has correct testid for cancel button', () => {
      renderWithProviders(<WorkerActionConfirmDialog {...defaultProps} />);

      expect(screen.getByTestId('worker-action-cancel-button')).toBeInTheDocument();
    });
  });
});

/**
 * Tests for ConfirmDialog component (NEM-2712).
 *
 * Tests confirmation dialog functionality for job actions including:
 * - Rendering title, description, and action buttons
 * - Different variants (danger for destructive actions)
 * - Loading states during async operations
 * - Keyboard and click interactions
 */
import { screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import ConfirmDialog from './ConfirmDialog';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

describe('ConfirmDialog', () => {
  const defaultProps = {
    isOpen: true,
    title: 'Confirm Action',
    description: 'Are you sure you want to proceed?',
    confirmLabel: 'Confirm',
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders title and description when open', () => {
      renderWithProviders(<ConfirmDialog {...defaultProps} />);

      expect(screen.getByText('Confirm Action')).toBeInTheDocument();
      expect(screen.getByText('Are you sure you want to proceed?')).toBeInTheDocument();
    });

    it('renders confirm and cancel buttons', () => {
      renderWithProviders(<ConfirmDialog {...defaultProps} />);

      expect(screen.getByRole('button', { name: /confirm/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('uses custom confirm label', () => {
      renderWithProviders(<ConfirmDialog {...defaultProps} confirmLabel="Delete Job" />);

      expect(screen.getByRole('button', { name: /delete job/i })).toBeInTheDocument();
    });

    it('uses custom cancel label', () => {
      renderWithProviders(<ConfirmDialog {...defaultProps} cancelLabel="Go Back" />);

      expect(screen.getByRole('button', { name: /go back/i })).toBeInTheDocument();
    });

    it('does not render when closed', () => {
      renderWithProviders(<ConfirmDialog {...defaultProps} isOpen={false} />);

      expect(screen.queryByText('Confirm Action')).not.toBeInTheDocument();
    });
  });

  describe('variants', () => {
    it('applies danger styling for danger variant', () => {
      renderWithProviders(<ConfirmDialog {...defaultProps} variant="danger" />);

      const confirmButton = screen.getByRole('button', { name: /confirm/i });
      // Should have red/danger colors
      expect(confirmButton).toHaveClass('bg-red-600');
    });

    it('applies default styling when no variant specified', () => {
      renderWithProviders(<ConfirmDialog {...defaultProps} />);

      const confirmButton = screen.getByRole('button', { name: /confirm/i });
      // Should have primary/green colors
      expect(confirmButton).toHaveClass('bg-[#76B900]');
    });

    it('applies warning styling for warning variant', () => {
      renderWithProviders(<ConfirmDialog {...defaultProps} variant="warning" />);

      const confirmButton = screen.getByRole('button', { name: /confirm/i });
      // Should have amber/warning colors
      expect(confirmButton).toHaveClass('bg-amber-600');
    });
  });

  describe('loading state', () => {
    it('shows loading spinner when isLoading is true', () => {
      renderWithProviders(<ConfirmDialog {...defaultProps} isLoading={true} />);

      expect(screen.getByTestId('loading-spinner')).toBeInTheDocument();
    });

    it('disables confirm button when loading', () => {
      renderWithProviders(<ConfirmDialog {...defaultProps} isLoading={true} />);

      expect(screen.getByRole('button', { name: /confirm/i })).toBeDisabled();
    });

    it('disables cancel button when loading', () => {
      renderWithProviders(<ConfirmDialog {...defaultProps} isLoading={true} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeDisabled();
    });

    it('shows loading text when provided', () => {
      renderWithProviders(
        <ConfirmDialog {...defaultProps} isLoading={true} loadingText="Cancelling..." />
      );

      expect(screen.getByText('Cancelling...')).toBeInTheDocument();
    });
  });

  describe('interactions', () => {
    it('calls onConfirm when confirm button is clicked', async () => {
      const onConfirm = vi.fn();
      const { user } = renderWithProviders(
        <ConfirmDialog {...defaultProps} onConfirm={onConfirm} />
      );

      await user.click(screen.getByRole('button', { name: /confirm/i }));

      expect(onConfirm).toHaveBeenCalledTimes(1);
    });

    it('calls onCancel when cancel button is clicked', async () => {
      const onCancel = vi.fn();
      const { user } = renderWithProviders(<ConfirmDialog {...defaultProps} onCancel={onCancel} />);

      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(onCancel).toHaveBeenCalledTimes(1);
    });

    it('calls onCancel when backdrop is clicked (if closeOnBackdrop is true)', async () => {
      const onCancel = vi.fn();
      const { user } = renderWithProviders(
        <ConfirmDialog {...defaultProps} onCancel={onCancel} closeOnBackdrop={true} />
      );

      await user.click(screen.getByTestId('dialog-backdrop'));

      expect(onCancel).toHaveBeenCalledTimes(1);
    });

    it('does not call onCancel when backdrop is clicked (if closeOnBackdrop is false)', async () => {
      const onCancel = vi.fn();
      const { user } = renderWithProviders(
        <ConfirmDialog {...defaultProps} onCancel={onCancel} closeOnBackdrop={false} />
      );

      await user.click(screen.getByTestId('dialog-backdrop'));

      expect(onCancel).not.toHaveBeenCalled();
    });

    it('calls onCancel when Escape key is pressed', async () => {
      const onCancel = vi.fn();
      const { user } = renderWithProviders(<ConfirmDialog {...defaultProps} onCancel={onCancel} />);

      await user.keyboard('{Escape}');

      expect(onCancel).toHaveBeenCalledTimes(1);
    });

    it('does not call handlers when loading', async () => {
      const onConfirm = vi.fn();
      const onCancel = vi.fn();
      const { user } = renderWithProviders(
        <ConfirmDialog
          {...defaultProps}
          onConfirm={onConfirm}
          onCancel={onCancel}
          isLoading={true}
        />
      );

      await user.click(screen.getByRole('button', { name: /confirm/i }));
      await user.click(screen.getByRole('button', { name: /cancel/i }));

      expect(onConfirm).not.toHaveBeenCalled();
      expect(onCancel).not.toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('has correct role for dialog', () => {
      renderWithProviders(<ConfirmDialog {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('has aria-labelledby pointing to title', () => {
      renderWithProviders(<ConfirmDialog {...defaultProps} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-labelledby');

      const labelId = dialog.getAttribute('aria-labelledby');
      const titleElement = document.getElementById(labelId!);
      expect(titleElement).toHaveTextContent('Confirm Action');
    });

    it('has aria-describedby pointing to description', () => {
      renderWithProviders(<ConfirmDialog {...defaultProps} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-describedby');

      const descId = dialog.getAttribute('aria-describedby');
      const descElement = document.getElementById(descId!);
      expect(descElement).toHaveTextContent('Are you sure you want to proceed?');
    });

    it('traps focus within the dialog', async () => {
      const { user } = renderWithProviders(<ConfirmDialog {...defaultProps} />);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      const confirmButton = screen.getByRole('button', { name: /confirm/i });

      // Dialog opens with cancel button focused
      expect(cancelButton).toHaveFocus();

      // Tab moves to confirm button
      await user.tab();
      expect(confirmButton).toHaveFocus();

      // Tab should cycle back to cancel button (focus trap)
      await user.tab();
      expect(cancelButton).toHaveFocus();
    });
  });
});

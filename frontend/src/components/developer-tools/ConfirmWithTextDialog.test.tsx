/**
 * Tests for ConfirmWithTextDialog component
 *
 * Tests the confirmation dialog that requires typing specific text to confirm.
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import ConfirmWithTextDialog from './ConfirmWithTextDialog';

describe('ConfirmWithTextDialog', () => {
  const defaultProps = {
    isOpen: true,
    title: 'Confirm Deletion',
    description: 'This will delete all events permanently.',
    confirmText: 'DELETE',
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
    isLoading: false,
  };

  it('should render when open', () => {
    render(<ConfirmWithTextDialog {...defaultProps} />);

    expect(screen.getByText('Confirm Deletion')).toBeInTheDocument();
    expect(screen.getByText('This will delete all events permanently.')).toBeInTheDocument();
    expect(screen.getByText(/Type "DELETE" to confirm/)).toBeInTheDocument();
  });

  it('should not render when closed', () => {
    render(<ConfirmWithTextDialog {...defaultProps} isOpen={false} />);

    expect(screen.queryByText('Confirm Deletion')).not.toBeInTheDocument();
  });

  it('should disable confirm button until text matches', () => {
    render(<ConfirmWithTextDialog {...defaultProps} />);

    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    expect(confirmButton).toBeDisabled();
  });

  it('should enable confirm button when text matches exactly', async () => {
    const user = userEvent.setup();
    render(<ConfirmWithTextDialog {...defaultProps} />);

    const input = screen.getByPlaceholderText(/type "delete"/i);
    await user.type(input, 'DELETE');

    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    expect(confirmButton).not.toBeDisabled();
  });

  it('should keep confirm button disabled for partial match', async () => {
    const user = userEvent.setup();
    render(<ConfirmWithTextDialog {...defaultProps} />);

    const input = screen.getByPlaceholderText(/type "delete"/i);
    await user.type(input, 'DEL');

    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    expect(confirmButton).toBeDisabled();
  });

  it('should be case-sensitive', async () => {
    const user = userEvent.setup();
    render(<ConfirmWithTextDialog {...defaultProps} />);

    const input = screen.getByPlaceholderText(/type "delete"/i);
    await user.type(input, 'delete');

    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    expect(confirmButton).toBeDisabled();
  });

  it('should call onConfirm when confirm button is clicked', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<ConfirmWithTextDialog {...defaultProps} onConfirm={onConfirm} />);

    const input = screen.getByPlaceholderText(/type "delete"/i);
    await user.type(input, 'DELETE');

    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    await user.click(confirmButton);

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('should call onCancel when cancel button is clicked', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(<ConfirmWithTextDialog {...defaultProps} onCancel={onCancel} />);

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('should show loading state', () => {
    render(<ConfirmWithTextDialog {...defaultProps} isLoading={true} />);

    const confirmButton = screen.getByRole('button', { name: /deleting/i });
    expect(confirmButton).toBeDisabled();
  });

  it('should disable cancel button while loading', () => {
    render(<ConfirmWithTextDialog {...defaultProps} isLoading={true} />);

    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    expect(cancelButton).toBeDisabled();
  });

  it('should clear input when dialog closes and reopens', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<ConfirmWithTextDialog {...defaultProps} />);

    const input = screen.getByPlaceholderText(/type "delete"/i);
    await user.type(input, 'DELETE');
    expect(input).toHaveValue('DELETE');

    // Close dialog
    rerender(<ConfirmWithTextDialog {...defaultProps} isOpen={false} />);

    // Reopen dialog
    rerender(<ConfirmWithTextDialog {...defaultProps} isOpen={true} />);

    const newInput = screen.getByPlaceholderText(/type "delete"/i);
    expect(newInput).toHaveValue('');
  });

  it('should support custom confirm text', async () => {
    const user = userEvent.setup();
    render(
      <ConfirmWithTextDialog
        {...defaultProps}
        confirmText="RESET DATABASE"
        title="Database Reset"
      />
    );

    expect(screen.getByText(/Type "RESET DATABASE" to confirm/)).toBeInTheDocument();

    const input = screen.getByPlaceholderText(/type "reset database"/i);
    await user.type(input, 'RESET DATABASE');

    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    expect(confirmButton).not.toBeDisabled();
  });

  it('should display danger styling for destructive action', () => {
    render(<ConfirmWithTextDialog {...defaultProps} variant="danger" />);

    // The confirm button should have danger styling (red color)
    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    expect(confirmButton).toHaveClass('bg-red-600');
  });

  it('should display warning styling for warning variant', () => {
    render(<ConfirmWithTextDialog {...defaultProps} variant="warning" />);

    // The confirm button should have warning styling (amber/yellow color)
    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    expect(confirmButton).toHaveClass('bg-amber-600');
  });
});

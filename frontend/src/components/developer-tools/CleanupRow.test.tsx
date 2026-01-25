/**
 * Tests for CleanupRow component
 *
 * Tests the row component for cleanup operations with confirmation dialog.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import CleanupRow from './CleanupRow';

describe('CleanupRow', () => {
  const defaultProps = {
    label: 'Delete All Events',
    description: 'Permanently deletes all events from the database.',
    confirmText: 'DELETE',
    onCleanup: vi.fn().mockResolvedValue(undefined),
    isLoading: false,
    variant: 'warning' as const,
  };

  it('should render label and cleanup button', () => {
    render(<CleanupRow {...defaultProps} />);

    // Label appears both in the row and as button text
    const labels = screen.getAllByText('Delete All Events');
    expect(labels.length).toBe(2);
    expect(screen.getByRole('button', { name: /delete all events/i })).toBeInTheDocument();
  });

  it('should render description', () => {
    render(<CleanupRow {...defaultProps} />);

    expect(
      screen.getByText('Permanently deletes all events from the database.')
    ).toBeInTheDocument();
  });

  it('should open confirmation dialog when button is clicked', async () => {
    const user = userEvent.setup();
    render(<CleanupRow {...defaultProps} />);

    const button = screen.getByRole('button', { name: /delete all events/i });
    await user.click(button);

    // Dialog should open
    await waitFor(() => {
      expect(screen.getByText(/Type "DELETE" to confirm/)).toBeInTheDocument();
    });
  });

  it('should call onCleanup when confirmation is provided', async () => {
    const user = userEvent.setup();
    const onCleanup = vi.fn().mockResolvedValue(undefined);
    render(<CleanupRow {...defaultProps} onCleanup={onCleanup} />);

    // Open dialog
    const button = screen.getByRole('button', { name: /delete all events/i });
    await user.click(button);

    // Type confirmation
    const input = await screen.findByPlaceholderText(/type "delete"/i);
    await user.type(input, 'DELETE');

    // Click confirm
    const confirmButton = screen.getByRole('button', { name: /confirm/i });
    await user.click(confirmButton);

    await waitFor(() => {
      expect(onCleanup).toHaveBeenCalledTimes(1);
    });
  });

  it('should close dialog when cancelled', async () => {
    const user = userEvent.setup();
    render(<CleanupRow {...defaultProps} />);

    // Open dialog
    const button = screen.getByRole('button', { name: /delete all events/i });
    await user.click(button);

    // Wait for dialog to open
    await screen.findByText(/Type "DELETE" to confirm/);

    // Click cancel
    const cancelButton = screen.getByRole('button', { name: /cancel/i });
    await user.click(cancelButton);

    // Dialog should close
    await waitFor(() => {
      expect(screen.queryByText(/Type "DELETE" to confirm/)).not.toBeInTheDocument();
    });
  });

  it('should show warning styling for warning variant', () => {
    render(<CleanupRow {...defaultProps} variant="warning" />);

    const button = screen.getByRole('button', { name: /delete all events/i });
    expect(button).toHaveClass('bg-amber-600');
  });

  it('should show danger styling for danger variant', () => {
    render(<CleanupRow {...defaultProps} variant="danger" />);

    const button = screen.getByRole('button', { name: /delete all events/i });
    expect(button).toHaveClass('bg-red-600');
  });

  it('should disable button while loading', () => {
    render(<CleanupRow {...defaultProps} isLoading={true} />);

    const button = screen.getByRole('button', { name: /deleting/i });
    expect(button).toBeDisabled();
  });

  it('should support custom button text', () => {
    render(<CleanupRow {...defaultProps} buttonText="Clear All Data" loadingText="Clearing..." />);

    expect(screen.getByRole('button', { name: /clear all data/i })).toBeInTheDocument();
  });
});

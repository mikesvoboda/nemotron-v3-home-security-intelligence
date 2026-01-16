import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import TrustClassificationControls from './TrustClassificationControls';

import type { TrustClassificationControlsProps, TrustStatus } from './TrustClassificationControls';

describe('TrustClassificationControls', () => {
  const mockOnStatusChange = vi.fn();
  const mockOnError = vi.fn();

  const defaultProps: TrustClassificationControlsProps = {
    currentStatus: 'unknown',
    entityId: 'entity-123',
    onStatusChange: mockOnStatusChange,
    onError: mockOnError,
  };

  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('Status Badge Rendering', () => {
    it('renders trusted status with green styling', () => {
      render(<TrustClassificationControls {...defaultProps} currentStatus="trusted" />);

      const badge = screen.getByTestId('trust-status-badge');
      expect(badge).toHaveTextContent('Trusted');
      expect(badge).toHaveClass('text-green-400', 'bg-green-500/10');
    });

    it('renders untrusted status with red styling', () => {
      render(<TrustClassificationControls {...defaultProps} currentStatus="untrusted" />);

      const badge = screen.getByTestId('trust-status-badge');
      expect(badge).toHaveTextContent('Untrusted');
      expect(badge).toHaveClass('text-red-400', 'bg-red-500/10');
    });

    it('renders unknown status with gray styling', () => {
      render(<TrustClassificationControls {...defaultProps} currentStatus="unknown" />);

      const badge = screen.getByTestId('trust-status-badge');
      expect(badge).toHaveTextContent('Unknown');
      expect(badge).toHaveClass('text-gray-400', 'bg-gray-500/10');
    });

    it('has correct aria-label for accessibility', () => {
      render(<TrustClassificationControls {...defaultProps} currentStatus="trusted" />);

      expect(screen.getByLabelText('Trust status: Trusted')).toBeInTheDocument();
    });

    it('includes role="status" for screen readers', () => {
      render(<TrustClassificationControls {...defaultProps} />);

      expect(screen.getByRole('status')).toBeInTheDocument();
    });
  });

  describe('Action Buttons', () => {
    it('renders all three action buttons when not in readOnly mode', () => {
      render(<TrustClassificationControls {...defaultProps} />);

      expect(screen.getByTestId('trust-button-trusted')).toBeInTheDocument();
      expect(screen.getByTestId('trust-button-untrusted')).toBeInTheDocument();
      expect(screen.getByTestId('trust-button-unknown')).toBeInTheDocument();
    });

    it('highlights current status button with NVIDIA green', () => {
      render(<TrustClassificationControls {...defaultProps} currentStatus="trusted" />);

      const trustedButton = screen.getByTestId('trust-button-trusted');
      expect(trustedButton).toHaveClass('border-[#76B900]', 'text-[#76B900]');
      expect(trustedButton).toHaveAttribute('aria-pressed', 'true');
    });

    it('does not render action buttons in readOnly mode', () => {
      render(<TrustClassificationControls {...defaultProps} readOnly={true} />);

      expect(screen.queryByTestId('trust-action-buttons')).not.toBeInTheDocument();
    });

    it('disables all buttons when isLoading is true', () => {
      render(<TrustClassificationControls {...defaultProps} isLoading={true} />);

      const trustedButton = screen.getByTestId('trust-button-trusted');
      const untrustedButton = screen.getByTestId('trust-button-untrusted');

      expect(trustedButton).toBeDisabled();
      expect(untrustedButton).toBeDisabled();
    });

    it('has correct aria-labels for each button', () => {
      render(<TrustClassificationControls {...defaultProps} />);

      expect(
        screen.getByRole('button', { name: /set trust status to trusted/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /set trust status to untrusted/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /set trust status to unknown/i })
      ).toBeInTheDocument();
    });
  });

  describe('Confirmation Dialog', () => {
    it('shows confirmation dialog when clicking a different status button', async () => {
      const user = userEvent.setup();
      render(<TrustClassificationControls {...defaultProps} currentStatus="unknown" />);

      await user.click(screen.getByTestId('trust-button-trusted'));

      expect(screen.getByTestId('trust-confirmation-dialog')).toBeInTheDocument();
      expect(screen.getByText(/change status to/i)).toBeInTheDocument();
      expect(screen.getByText('Trusted')).toBeInTheDocument();
    });

    it('does not show confirmation when clicking current status button', async () => {
      const user = userEvent.setup();
      render(<TrustClassificationControls {...defaultProps} currentStatus="trusted" />);

      await user.click(screen.getByTestId('trust-button-trusted'));

      expect(screen.queryByTestId('trust-confirmation-dialog')).not.toBeInTheDocument();
    });

    it('hides action buttons when confirmation is shown', async () => {
      const user = userEvent.setup();
      render(<TrustClassificationControls {...defaultProps} currentStatus="unknown" />);

      await user.click(screen.getByTestId('trust-button-trusted'));

      expect(screen.queryByTestId('trust-action-buttons')).not.toBeInTheDocument();
    });

    it('calls onStatusChange when confirm is clicked', async () => {
      const user = userEvent.setup();
      mockOnStatusChange.mockResolvedValueOnce(undefined);
      render(<TrustClassificationControls {...defaultProps} currentStatus="unknown" />);

      await user.click(screen.getByTestId('trust-button-trusted'));
      await user.click(screen.getByTestId('trust-confirm-button'));

      await waitFor(() => {
        expect(mockOnStatusChange).toHaveBeenCalledWith('entity-123', 'trusted');
      });
    });

    it('closes confirmation dialog on successful status change', async () => {
      const user = userEvent.setup();
      mockOnStatusChange.mockResolvedValueOnce(undefined);
      render(<TrustClassificationControls {...defaultProps} currentStatus="unknown" />);

      await user.click(screen.getByTestId('trust-button-trusted'));
      await user.click(screen.getByTestId('trust-confirm-button'));

      await waitFor(() => {
        expect(screen.queryByTestId('trust-confirmation-dialog')).not.toBeInTheDocument();
      });
    });

    it('closes confirmation dialog when cancel is clicked', async () => {
      const user = userEvent.setup();
      render(<TrustClassificationControls {...defaultProps} currentStatus="unknown" />);

      await user.click(screen.getByTestId('trust-button-trusted'));
      expect(screen.getByTestId('trust-confirmation-dialog')).toBeInTheDocument();

      await user.click(screen.getByTestId('trust-cancel-button'));

      expect(screen.queryByTestId('trust-confirmation-dialog')).not.toBeInTheDocument();
    });

    it('shows action buttons again after canceling', async () => {
      const user = userEvent.setup();
      render(<TrustClassificationControls {...defaultProps} currentStatus="unknown" />);

      await user.click(screen.getByTestId('trust-button-trusted'));
      await user.click(screen.getByTestId('trust-cancel-button'));

      expect(screen.getByTestId('trust-action-buttons')).toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('displays error message when onStatusChange fails', async () => {
      const user = userEvent.setup();
      mockOnStatusChange.mockRejectedValueOnce(new Error('API Error'));
      render(<TrustClassificationControls {...defaultProps} />);

      await user.click(screen.getByTestId('trust-button-trusted'));
      await user.click(screen.getByTestId('trust-confirm-button'));

      await waitFor(() => {
        expect(screen.getByTestId('trust-error-message')).toBeInTheDocument();
        expect(screen.getByText('API Error')).toBeInTheDocument();
      });
    });

    it('calls onError callback when status change fails', async () => {
      const user = userEvent.setup();
      const error = new Error('API Error');
      mockOnStatusChange.mockRejectedValueOnce(error);
      render(<TrustClassificationControls {...defaultProps} />);

      await user.click(screen.getByTestId('trust-button-trusted'));
      await user.click(screen.getByTestId('trust-confirm-button'));

      await waitFor(() => {
        expect(mockOnError).toHaveBeenCalledWith(error);
      });
    });

    it('displays generic error message for non-Error rejections', async () => {
      const user = userEvent.setup();
      mockOnStatusChange.mockRejectedValueOnce('Unknown error');
      render(<TrustClassificationControls {...defaultProps} />);

      await user.click(screen.getByTestId('trust-button-trusted'));
      await user.click(screen.getByTestId('trust-confirm-button'));

      await waitFor(() => {
        expect(screen.getByText('Failed to update trust status')).toBeInTheDocument();
      });
    });

    it('clears error when starting a new status change', async () => {
      const user = userEvent.setup();
      mockOnStatusChange
        .mockRejectedValueOnce(new Error('API Error'))
        .mockResolvedValueOnce(undefined);
      render(<TrustClassificationControls {...defaultProps} />);

      // First attempt - fails
      await user.click(screen.getByTestId('trust-button-trusted'));
      await user.click(screen.getByTestId('trust-confirm-button'));
      await waitFor(() => {
        expect(screen.getByText('API Error')).toBeInTheDocument();
      });

      // Cancel the current confirmation to get back to buttons
      await user.click(screen.getByTestId('trust-cancel-button'));

      // Second attempt - should clear error when clicking new button
      await user.click(screen.getByTestId('trust-button-untrusted'));
      expect(screen.queryByText('API Error')).not.toBeInTheDocument();
    });

    it('keeps confirmation dialog open on error and error has role="alert" for accessibility', async () => {
      const user = userEvent.setup();
      mockOnStatusChange.mockRejectedValueOnce(new Error('API Error'));
      render(<TrustClassificationControls {...defaultProps} />);

      await user.click(screen.getByTestId('trust-button-trusted'));
      await user.click(screen.getByTestId('trust-confirm-button'));

      // Wait for error to appear (which means the update completed with error)
      await waitFor(() => {
        expect(screen.getByRole('alert')).toBeInTheDocument();
      });

      // Error message should have testid
      expect(screen.getByTestId('trust-error-message')).toBeInTheDocument();

      // Confirmation dialog should still be open
      expect(screen.getByTestId('trust-confirmation-dialog')).toBeInTheDocument();
    });
  });

  describe('Loading States', () => {
    it('displays loading indicator when isLoading is true', () => {
      render(<TrustClassificationControls {...defaultProps} isLoading={true} />);

      expect(screen.getByTestId('trust-loading')).toBeInTheDocument();
      expect(screen.getByText('Loading trust status...')).toBeInTheDocument();
    });

    it('shows "Updating..." text on confirm button during update', async () => {
      const user = userEvent.setup();
      // Create a promise that we can control
      let resolvePromise!: () => void;
      const pendingPromise = new Promise<void>((resolve) => {
        resolvePromise = resolve;
      });
      mockOnStatusChange.mockReturnValueOnce(pendingPromise);
      render(<TrustClassificationControls {...defaultProps} />);

      await user.click(screen.getByTestId('trust-button-trusted'));
      await user.click(screen.getByTestId('trust-confirm-button'));

      // The button should show "Updating..." while the promise is pending
      expect(screen.getByText('Updating...')).toBeInTheDocument();

      // Clean up - resolve the promise
      resolvePromise();
      await waitFor(() => {
        expect(screen.queryByText('Updating...')).not.toBeInTheDocument();
      });
    });

    it('disables confirm and cancel buttons during update', async () => {
      const user = userEvent.setup();
      let resolvePromise: () => void;
      mockOnStatusChange.mockReturnValueOnce(
        new Promise<void>((resolve) => {
          resolvePromise = resolve;
        })
      );
      render(<TrustClassificationControls {...defaultProps} />);

      await user.click(screen.getByTestId('trust-button-trusted'));
      await user.click(screen.getByTestId('trust-confirm-button'));

      expect(screen.getByTestId('trust-confirm-button')).toBeDisabled();
      expect(screen.getByTestId('trust-cancel-button')).toBeDisabled();

      // Clean up
      resolvePromise!();
    });
  });

  describe('Size Variants', () => {
    it('renders small size variant correctly', () => {
      render(<TrustClassificationControls {...defaultProps} size="sm" />);

      const badge = screen.getByTestId('trust-status-badge');
      expect(badge).toHaveClass('text-xs', 'px-2', 'py-0.5');
    });

    it('renders medium size variant correctly (default)', () => {
      render(<TrustClassificationControls {...defaultProps} />);

      const badge = screen.getByTestId('trust-status-badge');
      expect(badge).toHaveClass('text-sm', 'px-3', 'py-1');
    });

    it('renders large size variant correctly', () => {
      render(<TrustClassificationControls {...defaultProps} size="lg" />);

      const badge = screen.getByTestId('trust-status-badge');
      expect(badge).toHaveClass('text-base', 'px-4', 'py-2');
    });
  });

  describe('Custom className', () => {
    it('applies custom className to container', () => {
      render(<TrustClassificationControls {...defaultProps} className="custom-class" />);

      const container = screen.getByTestId('trust-classification-controls');
      expect(container).toHaveClass('custom-class');
    });

    it('merges custom className with default classes', () => {
      render(<TrustClassificationControls {...defaultProps} className="ml-4" />);

      const container = screen.getByTestId('trust-classification-controls');
      expect(container).toHaveClass('ml-4', 'flex', 'flex-col', 'gap-3');
    });
  });

  describe('Status Change Scenarios', () => {
    it.each([
      ['unknown', 'trusted'],
      ['unknown', 'untrusted'],
      ['trusted', 'untrusted'],
      ['trusted', 'unknown'],
      ['untrusted', 'trusted'],
      ['untrusted', 'unknown'],
    ] as [TrustStatus, TrustStatus][])(
      'changes from %s to %s correctly',
      async (fromStatus, toStatus) => {
        const user = userEvent.setup();
        mockOnStatusChange.mockResolvedValueOnce(undefined);
        render(<TrustClassificationControls {...defaultProps} currentStatus={fromStatus} />);

        await user.click(screen.getByTestId(`trust-button-${toStatus}`));
        await user.click(screen.getByTestId('trust-confirm-button'));

        await waitFor(() => {
          expect(mockOnStatusChange).toHaveBeenCalledWith('entity-123', toStatus);
        });
      }
    );
  });

  describe('Help Button', () => {
    it('renders help button with tooltip when not readOnly', () => {
      render(<TrustClassificationControls {...defaultProps} currentStatus="trusted" />);

      const helpButton = screen.getByRole('button', { name: /trust status help/i });
      expect(helpButton).toBeInTheDocument();
      expect(helpButton).toHaveAttribute('title', 'This entity is a known trusted individual');
    });

    it('does not render help button in readOnly mode', () => {
      render(<TrustClassificationControls {...defaultProps} readOnly={true} />);

      expect(screen.queryByRole('button', { name: /trust status help/i })).not.toBeInTheDocument();
    });
  });

  describe('Snapshots', () => {
    it.each(['trusted', 'untrusted', 'unknown'] as TrustStatus[])(
      'renders %s status correctly',
      (status) => {
        const { container } = render(
          <TrustClassificationControls {...defaultProps} currentStatus={status} />
        );
        expect(container.firstChild).toMatchSnapshot();
      }
    );

    it('renders confirmation dialog correctly', async () => {
      const user = userEvent.setup();
      const { container } = render(<TrustClassificationControls {...defaultProps} />);

      await user.click(screen.getByTestId('trust-button-trusted'));

      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders error state correctly', async () => {
      const user = userEvent.setup();
      mockOnStatusChange.mockRejectedValue(new Error('Test error'));
      const { container } = render(<TrustClassificationControls {...defaultProps} />);

      await user.click(screen.getByTestId('trust-button-trusted'));
      await user.click(screen.getByTestId('trust-confirm-button'));

      // Wait for error to appear
      await waitFor(() => {
        expect(screen.getByTestId('trust-error-message')).toBeInTheDocument();
      });

      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders loading state correctly', () => {
      const { container } = render(
        <TrustClassificationControls {...defaultProps} isLoading={true} />
      );
      expect(container.firstChild).toMatchSnapshot();
    });

    it('renders readOnly mode correctly', () => {
      const { container } = render(
        <TrustClassificationControls {...defaultProps} currentStatus="trusted" readOnly={true} />
      );
      expect(container.firstChild).toMatchSnapshot();
    });

    it.each(['sm', 'md', 'lg'] as const)('renders %s size variant correctly', (size) => {
      const { container } = render(<TrustClassificationControls {...defaultProps} size={size} />);
      expect(container.firstChild).toMatchSnapshot();
    });
  });
});

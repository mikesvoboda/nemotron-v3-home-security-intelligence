/**
 * Tests for ConflictResolutionModal component
 *
 * Tests the modal that appears when optimistic locking conflicts occur,
 * allowing users to retry, cancel, or refresh.
 *
 * @see NEM-3626
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import ConflictResolutionModal from './ConflictResolutionModal';

import type { ConflictResolutionModalProps } from './ConflictResolutionModal';

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: { children: React.ReactNode }) => (
      <div {...props}>{children}</div>
    ),
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useReducedMotion: () => false,
}));

describe('ConflictResolutionModal', () => {
  const defaultProps: ConflictResolutionModalProps = {
    isOpen: true,
    onClose: vi.fn(),
    onRetry: vi.fn(),
    onRefresh: vi.fn(),
    errorMessage: 'This alert was modified by another user.',
    resourceType: 'alert',
    action: 'acknowledge',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders modal content when open', () => {
      render(<ConflictResolutionModal {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByText('Update Conflict')).toBeInTheDocument();
    });

    it('does not render content when closed', () => {
      render(<ConflictResolutionModal {...defaultProps} isOpen={false} />);

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('displays the error message', () => {
      render(<ConflictResolutionModal {...defaultProps} />);

      expect(
        screen.getByText('This alert was modified by another user.')
      ).toBeInTheDocument();
    });

    it('displays contextual title with resource type and action', () => {
      render(<ConflictResolutionModal {...defaultProps} />);

      expect(screen.getByText('Update Conflict')).toBeInTheDocument();
      // Should mention the action in the description
      const descriptions = screen.getAllByText(/acknowledge/i);
      expect(descriptions.length).toBeGreaterThan(0);
    });

    it('shows helpful description about what happened', () => {
      render(<ConflictResolutionModal {...defaultProps} />);

      // Check the description contains modification context
      expect(screen.getByText(/was modified while you were trying to/i)).toBeInTheDocument();
    });

    it('renders Retry button', () => {
      render(<ConflictResolutionModal {...defaultProps} />);

      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    it('renders Cancel button', () => {
      render(<ConflictResolutionModal {...defaultProps} />);

      expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    });

    it('renders Refresh button when onRefresh is provided', () => {
      render(<ConflictResolutionModal {...defaultProps} />);

      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });

    it('does not render Refresh button when onRefresh is not provided', () => {
      render(<ConflictResolutionModal {...defaultProps} onRefresh={undefined} />);

      expect(screen.queryByRole('button', { name: /refresh/i })).not.toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('calls onRetry when Retry button is clicked', async () => {
      const onRetry = vi.fn();
      const user = userEvent.setup();

      render(<ConflictResolutionModal {...defaultProps} onRetry={onRetry} />);

      const retryButton = screen.getByRole('button', { name: /retry/i });
      await user.click(retryButton);

      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when Cancel button is clicked', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup();

      render(<ConflictResolutionModal {...defaultProps} onClose={onClose} />);

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      await user.click(cancelButton);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onRefresh when Refresh button is clicked', async () => {
      const onRefresh = vi.fn();
      const user = userEvent.setup();

      render(<ConflictResolutionModal {...defaultProps} onRefresh={onRefresh} />);

      const refreshButton = screen.getByRole('button', { name: /refresh/i });
      await user.click(refreshButton);

      expect(onRefresh).toHaveBeenCalledTimes(1);
    });

    it('disables buttons when isLoading is true', () => {
      render(<ConflictResolutionModal {...defaultProps} isLoading={true} />);

      const retryButton = screen.getByRole('button', { name: /retry/i });
      const cancelButton = screen.getByRole('button', { name: /cancel/i });

      expect(retryButton).toBeDisabled();
      expect(cancelButton).toBeDisabled();
    });
  });

  describe('Resource Type Variations', () => {
    it('displays correct content for alert resource type', () => {
      render(<ConflictResolutionModal {...defaultProps} resourceType="alert" />);

      // Find in the description text
      const description = screen.getByText(/was modified while you were trying to/i);
      expect(description.textContent).toContain('alert');
    });

    it('displays correct content for event resource type', () => {
      render(<ConflictResolutionModal {...defaultProps} resourceType="event" />);

      const description = screen.getByText(/was modified while you were trying to/i);
      expect(description.textContent).toContain('event');
    });

    it('displays correct content for camera resource type', () => {
      render(<ConflictResolutionModal {...defaultProps} resourceType="camera" />);

      const description = screen.getByText(/was modified while you were trying to/i);
      expect(description.textContent).toContain('camera');
    });
  });

  describe('Action Variations', () => {
    it('displays correct content for acknowledge action', () => {
      render(<ConflictResolutionModal {...defaultProps} action="acknowledge" />);

      // Check description mentions the action
      const description = screen.getByText(/was modified while you were trying to/i);
      expect(description.textContent).toContain('acknowledge');
    });

    it('displays correct content for dismiss action', () => {
      render(<ConflictResolutionModal {...defaultProps} action="dismiss" />);

      const description = screen.getByText(/was modified while you were trying to/i);
      expect(description.textContent).toContain('dismiss');
    });

    it('displays correct content for update action', () => {
      render(<ConflictResolutionModal {...defaultProps} action="update" />);

      const description = screen.getByText(/was modified while you were trying to/i);
      expect(description.textContent).toContain('update');
    });
  });

  describe('Retry Count', () => {
    it('shows retry count when retryCount > 0', () => {
      render(<ConflictResolutionModal {...defaultProps} retryCount={2} />);

      expect(screen.getByText(/2/)).toBeInTheDocument();
    });

    it('shows warning message when approaching max retries', () => {
      render(<ConflictResolutionModal {...defaultProps} retryCount={2} maxRetries={3} />);

      // Should show "final" or "remaining" text
      expect(
        screen.queryByText(/final/i) || screen.queryByText(/1.*remaining/i)
      ).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has dialog role', () => {
      render(<ConflictResolutionModal {...defaultProps} />);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    it('has accessible modal structure', () => {
      render(<ConflictResolutionModal {...defaultProps} />);

      const dialog = screen.getByRole('dialog');
      expect(dialog).toHaveAttribute('aria-modal', 'true');
    });

    it('has accessible title', () => {
      render(<ConflictResolutionModal {...defaultProps} />);

      expect(screen.getByText('Update Conflict')).toBeInTheDocument();
    });

    it('buttons have accessible names', () => {
      render(<ConflictResolutionModal {...defaultProps} />);

      expect(screen.getByRole('button', { name: /retry/i })).toHaveAccessibleName();
      expect(screen.getByRole('button', { name: /cancel/i })).toHaveAccessibleName();
    });
  });

  describe('Error Icon', () => {
    it('displays warning/error icon', () => {
      render(<ConflictResolutionModal {...defaultProps} />);

      // Should have an icon indicating conflict/warning
      const icon = screen.getByTestId('conflict-icon') || screen.getByRole('img', { hidden: true });
      expect(icon || screen.getByText(/!/)).toBeInTheDocument();
    });
  });
});

/**
 * Tests for BatchAuditModal component
 *
 * TDD tests written first to define expected behavior.
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import BatchAuditModal from './BatchAuditModal';
import * as auditApi from '../../services/auditApi';

// Mock the audit API
vi.mock('../../services/auditApi', () => ({
  triggerBatchAudit: vi.fn(),
  AuditApiError: class AuditApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
      this.name = 'AuditApiError';
    }
  },
}));

describe('BatchAuditModal', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    onSuccess: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders nothing when isOpen is false', () => {
      render(<BatchAuditModal {...defaultProps} isOpen={false} />);
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('renders modal when isOpen is true', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    it('renders modal title', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'Trigger Batch Audit' })).toBeInTheDocument();
      });
    });

    it('renders modal description', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        expect(
          screen.getByText(/Queue multiple events for AI self-evaluation/)
        ).toBeInTheDocument();
      });
    });

    it('renders limit input with default value', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        const limitInput = screen.getByLabelText(/Event Limit/i);
        expect(limitInput).toBeInTheDocument();
        expect(limitInput).toHaveValue(50);
      });
    });

    it('renders min risk score input with default value', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        const riskInput = screen.getByLabelText(/Minimum Risk Score/i);
        expect(riskInput).toBeInTheDocument();
        expect(riskInput).toHaveValue(50);
      });
    });

    it('renders force re-evaluate checkbox unchecked by default', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        const forceCheckbox = screen.getByLabelText(/Force Re-evaluate/i);
        expect(forceCheckbox).toBeInTheDocument();
        expect(forceCheckbox).not.toBeChecked();
      });
    });

    it('renders cancel button', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument();
      });
    });

    it('renders submit button', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Start Batch Audit/i })).toBeInTheDocument();
      });
    });

    it('renders close button', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Close modal' })).toBeInTheDocument();
      });
    });
  });

  describe('form interactions', () => {
    it('allows changing limit value', async () => {
      render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const limitInput = screen.getByLabelText(/Event Limit/i);
      fireEvent.change(limitInput, { target: { value: '100', valueAsNumber: 100 } });

      expect(limitInput).toHaveValue(100);
    });

    it('allows changing min risk score value', async () => {
      render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const riskInput = screen.getByLabelText(/Minimum Risk Score/i);
      fireEvent.change(riskInput, { target: { value: '75', valueAsNumber: 75 } });

      expect(riskInput).toHaveValue(75);
    });

    it('allows toggling force re-evaluate checkbox', async () => {
      const user = userEvent.setup();
      render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const forceCheckbox = screen.getByLabelText(/Force Re-evaluate/i);
      expect(forceCheckbox).not.toBeChecked();

      await user.click(forceCheckbox);
      expect(forceCheckbox).toBeChecked();

      await user.click(forceCheckbox);
      expect(forceCheckbox).not.toBeChecked();
    });

    it('validates limit minimum value', async () => {
      render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const limitInput = screen.getByLabelText(/Event Limit/i);
      expect(limitInput).toHaveAttribute('min', '1');
    });

    it('validates limit maximum value', async () => {
      render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const limitInput = screen.getByLabelText(/Event Limit/i);
      expect(limitInput).toHaveAttribute('max', '1000');
    });

    it('validates min risk score minimum value', async () => {
      render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const riskInput = screen.getByLabelText(/Minimum Risk Score/i);
      expect(riskInput).toHaveAttribute('min', '0');
    });

    it('validates min risk score maximum value', async () => {
      render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const riskInput = screen.getByLabelText(/Minimum Risk Score/i);
      expect(riskInput).toHaveAttribute('max', '100');
    });
  });

  describe('close functionality', () => {
    it('calls onClose when cancel button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(<BatchAuditModal {...defaultProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: 'Cancel' }));

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when close button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(<BatchAuditModal {...defaultProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: 'Close modal' }));

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when escape key is pressed', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      render(<BatchAuditModal {...defaultProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.keyboard('{Escape}');

      await waitFor(() => {
        expect(onClose).toHaveBeenCalled();
      });
    });

    it('resets form state when closed and reopened', async () => {
      const { rerender } = render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Modify form values using fireEvent for number inputs (more reliable)
      const limitInput = screen.getByLabelText(/Event Limit/i);
      fireEvent.change(limitInput, { target: { value: '200', valueAsNumber: 200 } });
      expect(limitInput).toHaveValue(200);

      // Close and reopen modal
      rerender(<BatchAuditModal {...defaultProps} isOpen={false} />);
      rerender(<BatchAuditModal {...defaultProps} isOpen={true} />);

      await waitFor(() => {
        // Form should be reset to defaults
        const newLimitInput = screen.getByLabelText(/Event Limit/i);
        expect(newLimitInput).toHaveValue(50);
      });
    });
  });

  describe('form submission', () => {
    it('calls triggerBatchAudit with form values on submit', async () => {
      vi.mocked(auditApi.triggerBatchAudit).mockResolvedValue({
        queued_count: 25,
        message: 'Queued 25 events for processing',
      });

      render(<BatchAuditModal {...defaultProps} />);

      // Wait for modal to be ready
      await waitFor(() => {
        expect(screen.getByTestId('batch-audit-modal')).toBeInTheDocument();
      });

      // Modify form values using fireEvent for number inputs (more reliable)
      const limitInput = screen.getByLabelText(/Event Limit/i);
      fireEvent.change(limitInput, { target: { value: '100', valueAsNumber: 100 } });

      const riskInput = screen.getByLabelText(/Minimum Risk Score/i);
      fireEvent.change(riskInput, { target: { value: '75', valueAsNumber: 75 } });

      const forceCheckbox = screen.getByLabelText(/Force Re-evaluate/i);
      fireEvent.click(forceCheckbox);

      // Submit form
      const submitButton = screen.getByRole('button', { name: /Start Batch Audit/i });
      fireEvent.click(submitButton);

      await waitFor(() => {
        expect(auditApi.triggerBatchAudit).toHaveBeenCalled();
      });
      // Check the call was made with expected values (after first checking it was called)
      expect(auditApi.triggerBatchAudit).toHaveBeenCalledWith(100, 75, true);
    });

    it('calls triggerBatchAudit with default values', async () => {
      const user = userEvent.setup();
      vi.mocked(auditApi.triggerBatchAudit).mockResolvedValue({
        queued_count: 50,
        message: 'Queued 50 events for processing',
      });

      render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Start Batch Audit/i }));

      await waitFor(() => {
        expect(auditApi.triggerBatchAudit).toHaveBeenCalledWith(50, 50, false);
      });
    });

    it('disables submit button while submitting', async () => {
      const user = userEvent.setup();
      let resolveSubmit: () => void;
      const submitPromise = new Promise<{ queued_count: number; message: string }>((resolve) => {
        resolveSubmit = () => resolve({ queued_count: 25, message: 'Done' });
      });
      vi.mocked(auditApi.triggerBatchAudit).mockReturnValue(submitPromise);

      render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const submitButton = screen.getByRole('button', { name: /Start Batch Audit/i });
      await user.click(submitButton);

      expect(submitButton).toBeDisabled();
      expect(screen.getByText(/Processing/i)).toBeInTheDocument();

      resolveSubmit!();
      await waitFor(() => {
        expect(submitButton).not.toBeDisabled();
      });
    });

    it('disables cancel button while submitting', async () => {
      const user = userEvent.setup();
      let resolveSubmit: () => void;
      const submitPromise = new Promise<{ queued_count: number; message: string }>((resolve) => {
        resolveSubmit = () => resolve({ queued_count: 25, message: 'Done' });
      });
      vi.mocked(auditApi.triggerBatchAudit).mockReturnValue(submitPromise);

      render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: 'Cancel' });
      await user.click(screen.getByRole('button', { name: /Start Batch Audit/i }));

      expect(cancelButton).toBeDisabled();

      resolveSubmit!();
      await waitFor(() => {
        expect(cancelButton).not.toBeDisabled();
      });
    });

    it('calls onSuccess with response on successful submit', async () => {
      const user = userEvent.setup();
      const onSuccess = vi.fn();
      const response = {
        queued_count: 25,
        message: 'Queued 25 events for processing',
      };
      vi.mocked(auditApi.triggerBatchAudit).mockResolvedValue(response);

      render(<BatchAuditModal {...defaultProps} onSuccess={onSuccess} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Start Batch Audit/i }));

      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith(response);
      });
    });

    it('closes modal on successful submit', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      vi.mocked(auditApi.triggerBatchAudit).mockResolvedValue({
        queued_count: 25,
        message: 'Done',
      });

      render(<BatchAuditModal {...defaultProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Start Batch Audit/i }));

      await waitFor(() => {
        expect(onClose).toHaveBeenCalled();
      });
    });
  });

  describe('error handling', () => {
    it('displays error message on API failure', async () => {
      const user = userEvent.setup();
      vi.mocked(auditApi.triggerBatchAudit).mockRejectedValue(
        new auditApi.AuditApiError(500, 'Internal server error')
      );

      render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Start Batch Audit/i }));

      await waitFor(() => {
        expect(screen.getByText(/Internal server error/i)).toBeInTheDocument();
      });
    });

    it('displays generic error message for non-API errors', async () => {
      const user = userEvent.setup();
      vi.mocked(auditApi.triggerBatchAudit).mockRejectedValue(new Error('Network error'));

      render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Start Batch Audit/i }));

      await waitFor(() => {
        expect(screen.getByText(/Failed to trigger batch audit/i)).toBeInTheDocument();
      });
    });

    it('clears error when form is modified', async () => {
      const user = userEvent.setup();
      vi.mocked(auditApi.triggerBatchAudit).mockRejectedValue(
        new auditApi.AuditApiError(500, 'Server error')
      );

      render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Trigger error
      await user.click(screen.getByRole('button', { name: /Start Batch Audit/i }));
      await waitFor(() => {
        expect(screen.getByText(/Server error/i)).toBeInTheDocument();
      });

      // Modify form
      const limitInput = screen.getByLabelText(/Event Limit/i);
      await user.clear(limitInput);
      await user.type(limitInput, '100');

      // Error should be cleared
      expect(screen.queryByText(/Server error/i)).not.toBeInTheDocument();
    });

    it('does not close modal on error', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      vi.mocked(auditApi.triggerBatchAudit).mockRejectedValue(
        new auditApi.AuditApiError(500, 'Server error')
      );

      render(<BatchAuditModal {...defaultProps} onClose={onClose} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Start Batch Audit/i }));

      await waitFor(() => {
        expect(screen.getByText(/Server error/i)).toBeInTheDocument();
      });

      // onClose should not be called due to error
      expect(onClose).not.toHaveBeenCalled();
    });

    it('does not call onSuccess on error', async () => {
      const user = userEvent.setup();
      const onSuccess = vi.fn();
      vi.mocked(auditApi.triggerBatchAudit).mockRejectedValue(
        new auditApi.AuditApiError(500, 'Server error')
      );

      render(<BatchAuditModal {...defaultProps} onSuccess={onSuccess} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /Start Batch Audit/i }));

      await waitFor(() => {
        expect(screen.getByText(/Server error/i)).toBeInTheDocument();
      });

      expect(onSuccess).not.toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('has role="dialog"', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    it('has aria-modal attribute', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        const dialog = screen.getByRole('dialog');
        expect(dialog).toHaveAttribute('aria-modal');
      });
    });

    it('close button has aria-label', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        const closeButton = screen.getByRole('button', { name: 'Close modal' });
        expect(closeButton).toHaveAttribute('aria-label', 'Close modal');
      });
    });

    it('form inputs have associated labels', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        expect(screen.getByLabelText(/Event Limit/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/Minimum Risk Score/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/Force Re-evaluate/i)).toBeInTheDocument();
      });
    });

    it('has proper input types', async () => {
      render(<BatchAuditModal {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      const limitInput = screen.getByLabelText(/Event Limit/i);
      const riskInput = screen.getByLabelText(/Minimum Risk Score/i);
      const forceCheckbox = screen.getByLabelText(/Force Re-evaluate/i);

      expect(limitInput).toHaveAttribute('type', 'number');
      expect(riskInput).toHaveAttribute('type', 'number');
      expect(forceCheckbox).toHaveAttribute('type', 'checkbox');
    });
  });

  describe('data-testid attributes', () => {
    it('has data-testid for modal', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        expect(screen.getByTestId('batch-audit-modal')).toBeInTheDocument();
      });
    });

    it('has data-testid for limit input', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        expect(screen.getByTestId('batch-audit-limit')).toBeInTheDocument();
      });
    });

    it('has data-testid for risk score input', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        expect(screen.getByTestId('batch-audit-min-risk')).toBeInTheDocument();
      });
    });

    it('has data-testid for force checkbox', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        expect(screen.getByTestId('batch-audit-force')).toBeInTheDocument();
      });
    });

    it('has data-testid for submit button', async () => {
      render(<BatchAuditModal {...defaultProps} />);
      await waitFor(() => {
        expect(screen.getByTestId('batch-audit-submit')).toBeInTheDocument();
      });
    });
  });
});

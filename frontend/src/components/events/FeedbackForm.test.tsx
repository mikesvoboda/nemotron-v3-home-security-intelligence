import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import FeedbackForm from './FeedbackForm';

import type { FeedbackType } from '../../types/generated';

describe('FeedbackForm', () => {
  const defaultProps = {
    eventId: 123,
    feedbackType: 'false_positive' as FeedbackType,
    currentSeverity: 65,
    onSubmit: vi.fn(),
    onCancel: vi.fn(),
    isSubmitting: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the form with correct title for false_positive', () => {
      render(<FeedbackForm {...defaultProps} />);

      expect(screen.getByTestId('feedback-form')).toBeInTheDocument();
      expect(screen.getByText('False Positive Feedback')).toBeInTheDocument();
    });

    it('renders the form with correct title for wrong_severity', () => {
      render(<FeedbackForm {...defaultProps} feedbackType="wrong_severity" />);

      expect(screen.getByText('Wrong Severity Feedback')).toBeInTheDocument();
    });

    it('renders notes textarea', () => {
      render(<FeedbackForm {...defaultProps} />);

      expect(screen.getByTestId('feedback-notes')).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/explain why this is a false positive/i)).toBeInTheDocument();
    });

    it('renders cancel and submit buttons', () => {
      render(<FeedbackForm {...defaultProps} />);

      expect(screen.getByTestId('cancel-button')).toBeInTheDocument();
      expect(screen.getByTestId('submit-feedback-button')).toBeInTheDocument();
    });
  });

  describe('wrong_severity feedback type', () => {
    it('renders severity slider for wrong_severity type', () => {
      render(<FeedbackForm {...defaultProps} feedbackType="wrong_severity" />);

      expect(screen.getByTestId('severity-slider')).toBeInTheDocument();
      expect(screen.getByLabelText(/expected severity/i)).toBeInTheDocument();
    });

    it('does not render severity slider for false_positive type', () => {
      render(<FeedbackForm {...defaultProps} feedbackType="false_positive" />);

      expect(screen.queryByTestId('severity-slider')).not.toBeInTheDocument();
    });

    it('displays current severity value', () => {
      render(<FeedbackForm {...defaultProps} feedbackType="wrong_severity" />);

      expect(screen.getByText(/current:/i)).toBeInTheDocument();
      expect(screen.getByText('65')).toBeInTheDocument();
    });

    it('slider has correct min and max attributes', () => {
      render(<FeedbackForm {...defaultProps} feedbackType="wrong_severity" />);

      const slider = screen.getByTestId('severity-slider');
      // Verify slider has correct attributes
      expect(slider).toHaveAttribute('min', '0');
      expect(slider).toHaveAttribute('max', '100');
      expect(slider).toHaveAttribute('type', 'range');
    });
  });

  describe('form submission', () => {
    it('calls onSubmit with notes when submitted for false_positive', async () => {
      const user = userEvent.setup();
      render(<FeedbackForm {...defaultProps} feedbackType="false_positive" />);

      const notesInput = screen.getByTestId('feedback-notes');
      await user.type(notesInput, 'This is my cat, not an intruder');

      const submitButton = screen.getByTestId('submit-feedback-button');
      await user.click(submitButton);

      expect(defaultProps.onSubmit).toHaveBeenCalledWith('This is my cat, not an intruder');
    });

    it('calls onSubmit with notes and expectedSeverity for wrong_severity', async () => {
      const user = userEvent.setup();
      render(<FeedbackForm {...defaultProps} feedbackType="wrong_severity" />);

      const notesInput = screen.getByTestId('feedback-notes');
      await user.type(notesInput, 'This should be low risk');

      const submitButton = screen.getByTestId('submit-feedback-button');
      await user.click(submitButton);

      // The severity should be the current value (65) since we didn't change it
      expect(defaultProps.onSubmit).toHaveBeenCalledWith('This should be low risk', 65);
    });

    it('calls onSubmit with empty notes when no notes entered', async () => {
      const user = userEvent.setup();
      render(<FeedbackForm {...defaultProps} feedbackType="false_positive" />);

      const submitButton = screen.getByTestId('submit-feedback-button');
      await user.click(submitButton);

      expect(defaultProps.onSubmit).toHaveBeenCalledWith('');
    });
  });

  describe('cancellation', () => {
    it('calls onCancel when cancel button is clicked', async () => {
      const user = userEvent.setup();
      render(<FeedbackForm {...defaultProps} />);

      const cancelButton = screen.getByTestId('cancel-button');
      await user.click(cancelButton);

      expect(defaultProps.onCancel).toHaveBeenCalled();
    });

    it('calls onCancel when X button is clicked', async () => {
      const user = userEvent.setup();
      render(<FeedbackForm {...defaultProps} />);

      const xButton = screen.getByTestId('cancel-feedback-button');
      await user.click(xButton);

      expect(defaultProps.onCancel).toHaveBeenCalled();
    });
  });

  describe('submitting state', () => {
    it('disables submit button when isSubmitting is true', () => {
      render(<FeedbackForm {...defaultProps} isSubmitting={true} />);

      const submitButton = screen.getByTestId('submit-feedback-button');
      expect(submitButton).toBeDisabled();
    });

    it('disables cancel button when isSubmitting is true', () => {
      render(<FeedbackForm {...defaultProps} isSubmitting={true} />);

      const cancelButton = screen.getByTestId('cancel-button');
      expect(cancelButton).toBeDisabled();
    });

    it('shows "Submitting..." text when isSubmitting is true', () => {
      render(<FeedbackForm {...defaultProps} isSubmitting={true} />);

      expect(screen.getByText('Submitting...')).toBeInTheDocument();
    });
  });

  describe('placeholder text', () => {
    it('shows appropriate placeholder for false_positive', () => {
      render(<FeedbackForm {...defaultProps} feedbackType="false_positive" />);

      expect(screen.getByPlaceholderText(/explain why this is a false positive/i)).toBeInTheDocument();
    });

    it('shows generic placeholder for wrong_severity', () => {
      render(<FeedbackForm {...defaultProps} feedbackType="wrong_severity" />);

      expect(screen.getByPlaceholderText(/add any additional context/i)).toBeInTheDocument();
    });
  });

  describe('severity display labels', () => {
    it.each([
      { score: 90, label: 'Critical' },
      { score: 70, label: 'High' },
      { score: 50, label: 'Medium' },
      { score: 30, label: 'Low' },
      { score: 10, label: 'Minimal' },
    ])('displays $label for severity score $score', ({ score, label }) => {
      render(
        <FeedbackForm
          {...defaultProps}
          feedbackType="wrong_severity"
          currentSeverity={score}
        />
      );

      // Verify severity label is displayed
      // eslint-disable-next-line security/detect-non-literal-regexp
      expect(screen.getByText(new RegExp(label, 'i'))).toBeInTheDocument();
    });
  });
});

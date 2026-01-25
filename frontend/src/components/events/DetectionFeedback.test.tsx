/**
 * Tests for DetectionFeedback component
 *
 * @see DetectionFeedback.tsx
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import DetectionFeedback from './DetectionFeedback';

import type { DetectionFeedbackData } from './DetectionFeedback';

describe('DetectionFeedback', () => {
  const defaultProps = {
    detectionId: 'detection-123',
    eventId: 'event-456',
    onFeedbackSubmit: vi.fn(),
  };

  // Helper to get buttons by their full aria-label
  const getCorrectButton = () => screen.getByRole('button', { name: /^Mark detection as correct$/i });
  const getIncorrectButton = () => screen.getByRole('button', { name: /^Mark detection as incorrect$/i });
  const getUnsureButton = () => screen.getByRole('button', { name: /^Mark detection as unsure$/i });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders all three feedback buttons', () => {
      render(<DetectionFeedback {...defaultProps} />);

      expect(getCorrectButton()).toBeInTheDocument();
      expect(getIncorrectButton()).toBeInTheDocument();
      expect(getUnsureButton()).toBeInTheDocument();
    });

    it('renders with correct test id', () => {
      render(<DetectionFeedback {...defaultProps} />);

      expect(screen.getByTestId('detection-feedback')).toBeInTheDocument();
    });

    it('renders feedback buttons with correct icons', () => {
      render(<DetectionFeedback {...defaultProps} />);

      const container = screen.getByTestId('detection-feedback');
      // Check that SVG icons are present in each button
      const buttons = within(container).getAllByRole('button');
      expect(buttons).toHaveLength(3);
      buttons.forEach((button) => {
        expect(button.querySelector('svg')).toBeInTheDocument();
      });
    });

    it('applies custom className', () => {
      render(<DetectionFeedback {...defaultProps} className="custom-class" />);

      expect(screen.getByTestId('detection-feedback')).toHaveClass('custom-class');
    });
  });

  describe('correct feedback', () => {
    it('calls onFeedbackSubmit with correct data when Correct button is clicked', async () => {
      const user = userEvent.setup();
      const onFeedbackSubmit = vi.fn();
      render(<DetectionFeedback {...defaultProps} onFeedbackSubmit={onFeedbackSubmit} />);

      await user.click(getCorrectButton());

      expect(onFeedbackSubmit).toHaveBeenCalledWith({
        detectionId: 'detection-123',
        eventId: 'event-456',
        feedback: 'correct',
        reason: undefined,
      });
    });

    it('highlights the Correct button after selection', async () => {
      const user = userEvent.setup();
      render(<DetectionFeedback {...defaultProps} />);

      const correctButton = getCorrectButton();
      await user.click(correctButton);

      // Button should have active/selected styling
      expect(correctButton).toHaveAttribute('data-selected', 'true');
    });
  });

  describe('incorrect feedback', () => {
    it('shows reason dropdown when Incorrect button is clicked', async () => {
      const user = userEvent.setup();
      render(<DetectionFeedback {...defaultProps} />);

      await user.click(getIncorrectButton());

      expect(screen.getByTestId('reason-dropdown')).toBeInTheDocument();
    });

    it('displays all reason options in dropdown', async () => {
      const user = userEvent.setup();
      render(<DetectionFeedback {...defaultProps} />);

      await user.click(getIncorrectButton());

      const dropdown = screen.getByTestId('reason-dropdown');
      expect(within(dropdown).getByText('Shadow')).toBeInTheDocument();
      expect(within(dropdown).getByText('Reflection')).toBeInTheDocument();
      expect(within(dropdown).getByText('Animal')).toBeInTheDocument();
      expect(within(dropdown).getByText('Weather')).toBeInTheDocument();
      expect(within(dropdown).getByText('Wrong Label')).toBeInTheDocument();
      expect(within(dropdown).getByText('Other')).toBeInTheDocument();
    });

    it('calls onFeedbackSubmit with reason when reason is selected', async () => {
      const user = userEvent.setup();
      const onFeedbackSubmit = vi.fn();
      render(<DetectionFeedback {...defaultProps} onFeedbackSubmit={onFeedbackSubmit} />);

      await user.click(getIncorrectButton());
      await user.click(screen.getByText('Shadow'));

      expect(onFeedbackSubmit).toHaveBeenCalledWith({
        detectionId: 'detection-123',
        eventId: 'event-456',
        feedback: 'incorrect',
        reason: 'shadow',
      });
    });

    it('highlights the Incorrect button after selection', async () => {
      const user = userEvent.setup();
      render(<DetectionFeedback {...defaultProps} />);

      const incorrectButton = getIncorrectButton();
      await user.click(incorrectButton);

      expect(incorrectButton).toHaveAttribute('data-selected', 'true');
    });
  });

  describe('unsure feedback', () => {
    it('calls onFeedbackSubmit with unsure data when Unsure button is clicked', async () => {
      const user = userEvent.setup();
      const onFeedbackSubmit = vi.fn();
      render(<DetectionFeedback {...defaultProps} onFeedbackSubmit={onFeedbackSubmit} />);

      await user.click(getUnsureButton());

      expect(onFeedbackSubmit).toHaveBeenCalledWith({
        detectionId: 'detection-123',
        eventId: 'event-456',
        feedback: 'unsure',
        reason: undefined,
      });
    });

    it('highlights the Unsure button after selection', async () => {
      const user = userEvent.setup();
      render(<DetectionFeedback {...defaultProps} />);

      const unsureButton = getUnsureButton();
      await user.click(unsureButton);

      expect(unsureButton).toHaveAttribute('data-selected', 'true');
    });
  });

  describe('reason dropdown behavior', () => {
    it('closes reason dropdown when clicking outside', async () => {
      const user = userEvent.setup();
      render(
        <div>
          <DetectionFeedback {...defaultProps} />
          <button data-testid="outside-element">Outside</button>
        </div>
      );

      await user.click(getIncorrectButton());
      expect(screen.getByTestId('reason-dropdown')).toBeInTheDocument();

      await user.click(screen.getByTestId('outside-element'));

      await waitFor(() => {
        expect(screen.queryByTestId('reason-dropdown')).not.toBeInTheDocument();
      });
    });

    it('closes reason dropdown when Escape key is pressed', async () => {
      const user = userEvent.setup();
      render(<DetectionFeedback {...defaultProps} />);

      await user.click(getIncorrectButton());
      expect(screen.getByTestId('reason-dropdown')).toBeInTheDocument();

      await user.keyboard('{Escape}');

      await waitFor(() => {
        expect(screen.queryByTestId('reason-dropdown')).not.toBeInTheDocument();
      });
    });

    it('hides reason dropdown when switching from Incorrect to another feedback type', async () => {
      const user = userEvent.setup();
      render(<DetectionFeedback {...defaultProps} />);

      await user.click(getIncorrectButton());
      expect(screen.getByTestId('reason-dropdown')).toBeInTheDocument();

      await user.click(getCorrectButton());

      expect(screen.queryByTestId('reason-dropdown')).not.toBeInTheDocument();
    });
  });

  describe('keyboard accessibility', () => {
    it('allows keyboard navigation through buttons', async () => {
      const user = userEvent.setup();
      render(<DetectionFeedback {...defaultProps} />);

      const correctButton = getCorrectButton();
      const incorrectButton = getIncorrectButton();
      const unsureButton = getUnsureButton();

      correctButton.focus();
      expect(document.activeElement).toBe(correctButton);

      await user.tab();
      expect(document.activeElement).toBe(incorrectButton);

      await user.tab();
      expect(document.activeElement).toBe(unsureButton);
    });

    it('activates button with Enter key', async () => {
      const user = userEvent.setup();
      const onFeedbackSubmit = vi.fn();
      render(<DetectionFeedback {...defaultProps} onFeedbackSubmit={onFeedbackSubmit} />);

      const correctButton = getCorrectButton();
      correctButton.focus();
      await user.keyboard('{Enter}');

      expect(onFeedbackSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ feedback: 'correct' })
      );
    });

    it('activates button with Space key', async () => {
      const user = userEvent.setup();
      const onFeedbackSubmit = vi.fn();
      render(<DetectionFeedback {...defaultProps} onFeedbackSubmit={onFeedbackSubmit} />);

      const unsureButton = getUnsureButton();
      unsureButton.focus();
      await user.keyboard(' ');

      expect(onFeedbackSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ feedback: 'unsure' })
      );
    });

    it('allows selecting dropdown option with click', async () => {
      const user = userEvent.setup();
      const onFeedbackSubmit = vi.fn();
      render(<DetectionFeedback {...defaultProps} onFeedbackSubmit={onFeedbackSubmit} />);

      // Open the dropdown
      await user.click(getIncorrectButton());

      // The dropdown should be visible
      expect(screen.getByTestId('reason-dropdown')).toBeInTheDocument();

      // The dropdown options have role="option"
      const dropdownOptions = within(screen.getByTestId('reason-dropdown')).getAllByRole('option');
      expect(dropdownOptions).toHaveLength(6);

      // Click on the second option (Reflection)
      await user.click(dropdownOptions[1]);

      // Should have selected Reflection (second item)
      expect(onFeedbackSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ reason: 'reflection' })
      );
    });
  });

  describe('disabled state', () => {
    it('disables all buttons when disabled prop is true', () => {
      render(<DetectionFeedback {...defaultProps} disabled={true} />);

      expect(getCorrectButton()).toBeDisabled();
      expect(getIncorrectButton()).toBeDisabled();
      expect(getUnsureButton()).toBeDisabled();
    });

    it('does not call onFeedbackSubmit when disabled', async () => {
      const user = userEvent.setup();
      const onFeedbackSubmit = vi.fn();
      render(<DetectionFeedback {...defaultProps} onFeedbackSubmit={onFeedbackSubmit} disabled={true} />);

      await user.click(getCorrectButton());

      expect(onFeedbackSubmit).not.toHaveBeenCalled();
    });
  });

  describe('initial feedback state', () => {
    it('shows initial feedback selection when provided', () => {
      render(
        <DetectionFeedback
          {...defaultProps}
          initialFeedback={{ feedback: 'correct', reason: undefined }}
        />
      );

      const correctButton = getCorrectButton();
      expect(correctButton).toHaveAttribute('data-selected', 'true');
    });

    it('shows reason dropdown with selection when initial incorrect feedback has reason', () => {
      render(
        <DetectionFeedback
          {...defaultProps}
          initialFeedback={{ feedback: 'incorrect', reason: 'shadow' }}
        />
      );

      const incorrectButton = getIncorrectButton();
      expect(incorrectButton).toHaveAttribute('data-selected', 'true');
      // The reason badge should be visible
      expect(screen.getByText('Shadow')).toBeInTheDocument();
    });
  });

  describe('compact mode', () => {
    it('renders in compact mode with smaller buttons', () => {
      render(<DetectionFeedback {...defaultProps} compact={true} />);

      const container = screen.getByTestId('detection-feedback');
      expect(container).toHaveClass('detection-feedback--compact');
    });
  });

  describe('hover behavior', () => {
    it('shows tooltip on button hover', async () => {
      const user = userEvent.setup();
      render(<DetectionFeedback {...defaultProps} />);

      const correctButton = getCorrectButton();
      await user.hover(correctButton);

      // Tooltip should appear with description
      await waitFor(() => {
        expect(screen.getByRole('tooltip')).toBeInTheDocument();
      });
    });
  });

  describe('no callback provided', () => {
    it('handles clicks gracefully when no onFeedbackSubmit callback is provided', async () => {
      const user = userEvent.setup();
      // Should not throw when clicked without callback
      render(<DetectionFeedback detectionId="det-1" eventId="evt-1" />);

      await user.click(getCorrectButton());
      // No error should be thrown
    });
  });
});

describe('DetectionFeedbackData type', () => {
  it('should have correct structure', () => {
    const feedbackData: DetectionFeedbackData = {
      detectionId: 'det-123',
      eventId: 'evt-456',
      feedback: 'incorrect',
      reason: 'shadow',
    };

    expect(feedbackData.detectionId).toBe('det-123');
    expect(feedbackData.eventId).toBe('evt-456');
    expect(feedbackData.feedback).toBe('incorrect');
    expect(feedbackData.reason).toBe('shadow');
  });

  it('allows undefined reason for correct feedback', () => {
    const feedbackData: DetectionFeedbackData = {
      detectionId: 'det-123',
      eventId: 'evt-456',
      feedback: 'correct',
      reason: undefined,
    };

    expect(feedbackData.reason).toBeUndefined();
  });
});

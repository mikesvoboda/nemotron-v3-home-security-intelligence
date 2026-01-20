/**
 * Tests for EventFeedbackButtons component
 *
 * NEM-3025: Build frontend quick feedback UI for event review
 *
 * This component provides quick feedback buttons for users to mark events as:
 * - Correct: The classification was accurate
 * - Not a Threat: This was a false positive
 * - Was a Threat: This was a missed detection (shown only for low risk events)
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import EventFeedbackButtons from './EventFeedbackButtons';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../../services/api');
  return {
    ...actual,
    submitEventFeedback: vi.fn(),
  };
});

// Create a wrapper with QueryClientProvider
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

function renderWithQueryClient(ui: React.ReactElement) {
  const testQueryClient = createTestQueryClient();
  return {
    ...render(<QueryClientProvider client={testQueryClient}>{ui}</QueryClientProvider>),
    queryClient: testQueryClient,
  };
}

describe('EventFeedbackButtons', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('rendering', () => {
    it('renders all three buttons for low risk events', () => {
      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="low" />);

      expect(screen.getByTestId('feedback-btn-correct')).toBeInTheDocument();
      expect(screen.getByTestId('feedback-btn-false-positive')).toBeInTheDocument();
      expect(screen.getByTestId('feedback-btn-missed-threat')).toBeInTheDocument();
    });

    it('renders only Correct and Not a Threat buttons for medium risk events', () => {
      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="medium" />);

      expect(screen.getByTestId('feedback-btn-correct')).toBeInTheDocument();
      expect(screen.getByTestId('feedback-btn-false-positive')).toBeInTheDocument();
      expect(screen.queryByTestId('feedback-btn-missed-threat')).not.toBeInTheDocument();
    });

    it('renders only Correct and Not a Threat buttons for high risk events', () => {
      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="high" />);

      expect(screen.getByTestId('feedback-btn-correct')).toBeInTheDocument();
      expect(screen.getByTestId('feedback-btn-false-positive')).toBeInTheDocument();
      expect(screen.queryByTestId('feedback-btn-missed-threat')).not.toBeInTheDocument();
    });

    it('renders only Correct and Not a Threat buttons for critical risk events', () => {
      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="critical" />);

      expect(screen.getByTestId('feedback-btn-correct')).toBeInTheDocument();
      expect(screen.getByTestId('feedback-btn-false-positive')).toBeInTheDocument();
      expect(screen.queryByTestId('feedback-btn-missed-threat')).not.toBeInTheDocument();
    });

    it('displays correct button labels', () => {
      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="low" />);

      expect(screen.getByText('Correct')).toBeInTheDocument();
      expect(screen.getByText('Not a Threat')).toBeInTheDocument();
      expect(screen.getByText('Was a Threat')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      renderWithQueryClient(
        <EventFeedbackButtons eventId={123} currentRiskLevel="low" className="custom-class" />
      );

      expect(screen.getByTestId('event-feedback-buttons')).toHaveClass('custom-class');
    });
  });

  describe('button interactions', () => {
    it('submits "accurate" feedback when Correct button is clicked', async () => {
      const user = userEvent.setup();
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'accurate',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="medium" />);

      await user.click(screen.getByTestId('feedback-btn-correct'));

      await waitFor(() => {
        expect(api.submitEventFeedback).toHaveBeenCalledWith({
          event_id: 123,
          feedback_type: 'accurate',
          notes: null,
        });
      });
    });

    it('submits "false_positive" feedback when Not a Threat button is clicked', async () => {
      const user = userEvent.setup();
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'false_positive',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="medium" />);

      await user.click(screen.getByTestId('feedback-btn-false-positive'));

      await waitFor(() => {
        expect(api.submitEventFeedback).toHaveBeenCalledWith({
          event_id: 123,
          feedback_type: 'false_positive',
          notes: null,
        });
      });
    });

    it('submits "missed_threat" feedback when Was a Threat button is clicked', async () => {
      const user = userEvent.setup();
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'missed_threat',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="low" />);

      await user.click(screen.getByTestId('feedback-btn-missed-threat'));

      await waitFor(() => {
        expect(api.submitEventFeedback).toHaveBeenCalledWith({
          event_id: 123,
          feedback_type: 'missed_threat',
          notes: null,
        });
      });
    });

    it('disables all buttons while mutation is pending', async () => {
      const user = userEvent.setup();

      // Create a promise that we control the resolution of
      let resolveSubmit: (value: api.EventFeedbackResponse) => void = () => {};
      vi.mocked(api.submitEventFeedback).mockImplementation(
        () =>
          new Promise<api.EventFeedbackResponse>((resolve) => {
            resolveSubmit = resolve;
          })
      );

      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="low" />);

      // Click the Correct button
      await user.click(screen.getByTestId('feedback-btn-correct'));

      // All buttons should be disabled while pending
      await waitFor(() => {
        expect(screen.getByTestId('feedback-btn-correct')).toBeDisabled();
        expect(screen.getByTestId('feedback-btn-false-positive')).toBeDisabled();
        expect(screen.getByTestId('feedback-btn-missed-threat')).toBeDisabled();
      });

      // Resolve the promise
      resolveSubmit({
        id: 1,
        event_id: 123,
        feedback_type: 'accurate',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });
    });
  });

  describe('success state', () => {
    it('shows success message after feedback is submitted', async () => {
      const user = userEvent.setup();
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'accurate',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="medium" />);

      await user.click(screen.getByTestId('feedback-btn-correct'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-success')).toBeInTheDocument();
        expect(screen.getByText('Thanks for your feedback!')).toBeInTheDocument();
      });
    });

    it('hides buttons after feedback is submitted', async () => {
      const user = userEvent.setup();
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'accurate',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="medium" />);

      await user.click(screen.getByTestId('feedback-btn-correct'));

      await waitFor(() => {
        expect(screen.queryByTestId('feedback-btn-correct')).not.toBeInTheDocument();
        expect(screen.queryByTestId('feedback-btn-false-positive')).not.toBeInTheDocument();
      });
    });

    it('calls onFeedbackSubmitted callback after successful submission', async () => {
      const user = userEvent.setup();
      const onFeedbackSubmitted = vi.fn();
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'accurate',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(
        <EventFeedbackButtons
          eventId={123}
          currentRiskLevel="medium"
          onFeedbackSubmitted={onFeedbackSubmitted}
        />
      );

      await user.click(screen.getByTestId('feedback-btn-correct'));

      await waitFor(() => {
        expect(onFeedbackSubmitted).toHaveBeenCalled();
      });
    });

    it('invalidates events query after successful submission', async () => {
      const user = userEvent.setup();
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'accurate',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      const { queryClient } = renderWithQueryClient(
        <EventFeedbackButtons eventId={123} currentRiskLevel="medium" />
      );

      // Spy on invalidateQueries
      const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');

      await user.click(screen.getByTestId('feedback-btn-correct'));

      await waitFor(() => {
        expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['events'] });
      });
    });
  });

  describe('error handling', () => {
    it('shows error message when submission fails', async () => {
      const user = userEvent.setup();
      vi.mocked(api.submitEventFeedback).mockRejectedValue(new Error('Network error'));

      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="medium" />);

      await user.click(screen.getByTestId('feedback-btn-correct'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-error')).toBeInTheDocument();
        expect(screen.getByText(/Failed to submit feedback/)).toBeInTheDocument();
      });
    });

    it('shows specific error for 409 conflict (feedback already exists)', async () => {
      const user = userEvent.setup();
      vi.mocked(api.submitEventFeedback).mockRejectedValue(new api.ApiError(409, 'Conflict'));

      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="medium" />);

      await user.click(screen.getByTestId('feedback-btn-correct'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-error')).toBeInTheDocument();
        expect(screen.getByText(/Feedback already submitted/)).toBeInTheDocument();
      });
    });

    it('keeps buttons visible when submission fails', async () => {
      const user = userEvent.setup();
      vi.mocked(api.submitEventFeedback).mockRejectedValue(new Error('Network error'));

      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="medium" />);

      await user.click(screen.getByTestId('feedback-btn-correct'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-error')).toBeInTheDocument();
      });

      // Buttons should still be visible for retry
      expect(screen.getByTestId('feedback-btn-correct')).toBeInTheDocument();
      expect(screen.getByTestId('feedback-btn-false-positive')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('buttons have accessible names', () => {
      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="low" />);

      expect(screen.getByTestId('feedback-btn-correct')).toHaveAccessibleName(/correct/i);
      expect(screen.getByTestId('feedback-btn-false-positive')).toHaveAccessibleName(/not a threat/i);
      expect(screen.getByTestId('feedback-btn-missed-threat')).toHaveAccessibleName(/was a threat/i);
    });

    it('buttons can be navigated with keyboard', async () => {
      const user = userEvent.setup();
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'accurate',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="medium" />);

      // Tab to first button
      await user.tab();
      expect(screen.getByTestId('feedback-btn-correct')).toHaveFocus();

      // Tab to second button
      await user.tab();
      expect(screen.getByTestId('feedback-btn-false-positive')).toHaveFocus();
    });

    it('buttons can be activated with Enter key', async () => {
      const user = userEvent.setup();
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'accurate',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventFeedbackButtons eventId={123} currentRiskLevel="medium" />);

      // Focus the first button
      screen.getByTestId('feedback-btn-correct').focus();

      // Press Enter
      await user.keyboard('{Enter}');

      await waitFor(() => {
        expect(api.submitEventFeedback).toHaveBeenCalled();
      });
    });
  });

  describe('compact mode', () => {
    it('applies compact styling when compact prop is true', () => {
      renderWithQueryClient(
        <EventFeedbackButtons eventId={123} currentRiskLevel="low" compact={true} />
      );

      const buttons = screen.getAllByRole('button');
      // In compact mode, buttons should have smaller padding
      buttons.forEach((button) => {
        expect(button).toHaveClass('px-2');
      });
    });

    it('applies normal styling when compact prop is false', () => {
      renderWithQueryClient(
        <EventFeedbackButtons eventId={123} currentRiskLevel="low" compact={false} />
      );

      const buttons = screen.getAllByRole('button');
      // In normal mode, buttons should have standard padding
      buttons.forEach((button) => {
        expect(button).toHaveClass('px-3');
      });
    });
  });
});

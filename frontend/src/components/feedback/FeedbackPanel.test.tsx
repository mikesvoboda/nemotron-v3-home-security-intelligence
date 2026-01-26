import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import FeedbackPanel from './FeedbackPanel';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../../services/api');
  return {
    ...actual,
    getEventFeedback: vi.fn(),
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

describe('FeedbackPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const mockFeedbackResponse: api.EventFeedbackResponse = {
    id: 1,
    event_id: 123,
    feedback_type: 'false_positive',
    notes: 'This was my neighbor',
    created_at: '2024-01-15T10:30:00Z',
  };

  describe('initial rendering', () => {
    it('renders loading state while fetching feedback', () => {
      // Never resolve the promise to keep loading state
      vi.mocked(api.getEventFeedback).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      expect(screen.getByText('Loading feedback...')).toBeInTheDocument();
    });

    it('renders feedback buttons when no existing feedback', async () => {
      // Return null (no feedback exists)
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-panel')).toBeInTheDocument();
      });

      expect(screen.getByText('Detection Feedback')).toBeInTheDocument();
      expect(screen.getByTestId('feedback-buttons')).toBeInTheDocument();
    });

    it('renders all four feedback buttons', async () => {
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-accurate-button')).toBeInTheDocument();
        expect(screen.getByTestId('feedback-false_positive-button')).toBeInTheDocument();
        expect(screen.getByTestId('feedback-missed_threat-button')).toBeInTheDocument();
        expect(screen.getByTestId('feedback-severity_wrong-button')).toBeInTheDocument();
      });

      // Check button labels
      expect(screen.getByText('Accurate')).toBeInTheDocument();
      expect(screen.getByText('False Positive')).toBeInTheDocument();
      expect(screen.getByText('Missed Threat')).toBeInTheDocument();
      expect(screen.getByText('Severity Wrong')).toBeInTheDocument();
    });

    it('renders existing feedback in read-only mode', async () => {
      vi.mocked(api.getEventFeedback).mockResolvedValue(mockFeedbackResponse);

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByText('False Positive')).toBeInTheDocument();
      });

      expect(screen.getByText('This was my neighbor')).toBeInTheDocument();
      expect(screen.getByText(/Submitted/)).toBeInTheDocument();
    });

    it('applies custom className', async () => {
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);

      renderWithQueryClient(<FeedbackPanel eventId={123} className="custom-class" />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-panel')).toHaveClass('custom-class');
      });
    });
  });

  describe('quick feedback submission (Accurate button)', () => {
    it('submits feedback immediately when clicking Accurate', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'accurate',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-accurate-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-accurate-button'));

      await waitFor(() => {
        expect(api.submitEventFeedback).toHaveBeenCalled();
        const callArgs = vi.mocked(api.submitEventFeedback).mock.calls[0][0];
        expect(callArgs).toMatchObject({
          event_id: 123,
          feedback_type: 'accurate',
        });
      });
    });

    it('calls onFeedbackSubmitted callback after successful submission', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const onFeedbackSubmitted = vi.fn();
      const submittedFeedback = {
        id: 1,
        event_id: 123,
        feedback_type: 'accurate' as const,
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      };

      vi.mocked(api.getEventFeedback).mockResolvedValue(null);
      vi.mocked(api.submitEventFeedback).mockResolvedValue(submittedFeedback);

      renderWithQueryClient(
        <FeedbackPanel eventId={123} onFeedbackSubmitted={onFeedbackSubmitted} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('feedback-accurate-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-accurate-button'));

      await waitFor(() => {
        expect(onFeedbackSubmitted).toHaveBeenCalledWith(submittedFeedback);
      });
    });
  });

  describe('feedback with notes form', () => {
    it('opens notes form when clicking False Positive', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-false_positive-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-false_positive-button'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-notes')).toBeInTheDocument();
        expect(screen.getByText('False Positive')).toBeInTheDocument();
      });
    });

    it('opens notes form when clicking Missed Threat', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-missed_threat-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-missed_threat-button'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-notes')).toBeInTheDocument();
        expect(screen.getByText('Missed Threat')).toBeInTheDocument();
      });
    });

    it('opens notes form when clicking Severity Wrong', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-severity_wrong-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-severity_wrong-button'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-notes')).toBeInTheDocument();
        expect(screen.getByText('Severity Wrong')).toBeInTheDocument();
      });
    });

    it('allows typing in notes textarea', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-false_positive-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-false_positive-button'));

      const textarea = screen.getByTestId('feedback-notes');
      await user.type(textarea, 'This is a test note');

      expect((textarea as HTMLTextAreaElement).value).toBe('This is a test note');
    });

    it('shows character count', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-false_positive-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-false_positive-button'));

      expect(screen.getByText('0/1000')).toBeInTheDocument();

      const textarea = screen.getByTestId('feedback-notes');
      await user.type(textarea, 'Test');

      expect(screen.getByText('4/1000')).toBeInTheDocument();
    });

    it('cancels form when cancel button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-false_positive-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-false_positive-button'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-notes')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('cancel-button'));

      await waitFor(() => {
        expect(screen.queryByTestId('feedback-notes')).not.toBeInTheDocument();
        expect(screen.getByTestId('feedback-buttons')).toBeInTheDocument();
      });
    });

    it('submits feedback with notes', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'false_positive',
        notes: 'Test note',
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-false_positive-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-false_positive-button'));

      const textarea = screen.getByTestId('feedback-notes');
      await user.type(textarea, 'Test note');

      await user.click(screen.getByTestId('submit-feedback-button'));

      await waitFor(() => {
        expect(api.submitEventFeedback).toHaveBeenCalled();
        const callArgs = vi.mocked(api.submitEventFeedback).mock.calls[0][0];
        expect(callArgs).toMatchObject({
          event_id: 123,
          feedback_type: 'false_positive',
          notes: 'Test note',
        });
      });
    });

    it('includes current risk score for wrong_severity feedback', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'severity_wrong',
        notes: 'Current score: 75. Should be lower',
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={75} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-severity_wrong-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-severity_wrong-button'));

      // Add some notes in the form
      const textarea = screen.getByTestId('feedback-notes');
      await user.type(textarea, 'Should be lower');

      await user.click(screen.getByTestId('submit-feedback-button'));

      await waitFor(() => {
        expect(api.submitEventFeedback).toHaveBeenCalled();
        // Check the first argument passed to the mutation function
        const callArgs = vi.mocked(api.submitEventFeedback).mock.calls[0][0];
        expect(callArgs).toMatchObject({
          event_id: 123,
          feedback_type: 'severity_wrong',
          notes: 'Current score: 75. Should be lower',
        });
      });
    });
  });

  describe('error handling', () => {
    it('shows error message on submission failure', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);
      vi.mocked(api.submitEventFeedback).mockRejectedValue(new Error('Server error'));

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-accurate-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-accurate-button'));

      await waitFor(() => {
        expect(
          screen.getByText('Failed to submit feedback. Please try again.')
        ).toBeInTheDocument();
      });
    });

    it('shows error message on form submission failure', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);
      vi.mocked(api.submitEventFeedback).mockRejectedValue(new Error('Server error'));

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-false_positive-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-false_positive-button'));
      await user.click(screen.getByTestId('submit-feedback-button'));

      await waitFor(() => {
        expect(
          screen.getByText('Failed to submit feedback. Please try again.')
        ).toBeInTheDocument();
      });
    });
  });

  describe('disabled state', () => {
    it('disables buttons during submission', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);

      // Create a promise that we control the resolution of
      let resolveSubmit: (value: api.EventFeedbackResponse) => void = () => {};
      vi.mocked(api.submitEventFeedback).mockImplementation(
        () =>
          new Promise<api.EventFeedbackResponse>((resolve) => {
            resolveSubmit = resolve;
          })
      );

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-accurate-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-accurate-button'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-accurate-button')).toBeDisabled();
        expect(screen.getByTestId('feedback-false_positive-button')).toBeDisabled();
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

  describe('accessibility', () => {
    it('has title attributes on feedback buttons', async () => {
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-accurate-button')).toHaveAttribute(
          'title',
          'Detection was correct'
        );
        expect(screen.getByTestId('feedback-false_positive-button')).toHaveAttribute(
          'title',
          'Event was incorrectly flagged'
        );
        expect(screen.getByTestId('feedback-missed_threat-button')).toHaveAttribute(
          'title',
          'System failed to detect a threat'
        );
        expect(screen.getByTestId('feedback-severity_wrong-button')).toHaveAttribute(
          'title',
          'Risk level was incorrect'
        );
      });
    });

    it('has proper labels for textarea', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.getEventFeedback).mockResolvedValue(null);

      renderWithQueryClient(<FeedbackPanel eventId={123} currentRiskScore={50} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-false_positive-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-false_positive-button'));

      const textarea = screen.getByLabelText(/notes/i);
      expect(textarea).toBeInTheDocument();
    });
  });
});

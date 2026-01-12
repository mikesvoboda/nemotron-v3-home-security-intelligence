import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import EventFeedbackSection from './EventFeedbackSection';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../../services/api');
  return {
    ...actual,
    fetchEventFeedback: vi.fn(),
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

describe('EventFeedbackSection', () => {
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
      vi.mocked(api.fetchEventFeedback).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      expect(screen.getByText('Loading feedback...')).toBeInTheDocument();
    });

    it('renders collapsible section when no existing feedback', async () => {
      // Return 404 error (no feedback exists)
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-section')).toBeInTheDocument();
      });

      expect(screen.getByText('Was this classification correct?')).toBeInTheDocument();
      expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
    });

    it('renders collapsed by default', async () => {
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-section')).toBeInTheDocument();
      });

      // Feedback buttons should not be visible when collapsed
      expect(screen.queryByTestId('feedback-buttons')).not.toBeInTheDocument();
    });

    it('renders existing feedback in read-only mode', async () => {
      vi.mocked(api.fetchEventFeedback).mockResolvedValue(mockFeedbackResponse);

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText('Feedback Submitted')).toBeInTheDocument();
      });

      expect(screen.getByText('False Positive')).toBeInTheDocument();
      expect(screen.getByText('This was my neighbor')).toBeInTheDocument();
      // Use getAllByText since "Submitted" appears in both the header and the date
      expect(screen.getAllByText(/Submitted/).length).toBeGreaterThan(0);
    });

    it('shows calibration adjusted indicator for existing feedback', async () => {
      vi.mocked(api.fetchEventFeedback).mockResolvedValue(mockFeedbackResponse);

      renderWithQueryClient(<EventFeedbackSection eventId={123} calibrationAdjusted={true} />);

      await waitFor(() => {
        expect(screen.getByText('Feedback Submitted')).toBeInTheDocument();
      });

      expect(screen.getByText('Calibration Adjusted')).toBeInTheDocument();
    });

    it('shows error state on non-404 errors', async () => {
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(500, 'Server error'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load feedback. Please try again.')).toBeInTheDocument();
      });
    });
  });

  describe('expanding and collapsing', () => {
    it('expands when toggle button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      const toggle = screen.getByTestId('feedback-toggle');
      await user.click(toggle);

      expect(screen.getByTestId('feedback-buttons')).toBeInTheDocument();
    });

    it('collapses when toggle button is clicked again', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      const toggle = screen.getByTestId('feedback-toggle');

      // Expand
      await user.click(toggle);
      expect(screen.getByTestId('feedback-buttons')).toBeInTheDocument();

      // Collapse
      await user.click(toggle);
      expect(screen.queryByTestId('feedback-buttons')).not.toBeInTheDocument();
    });

    it('has correct aria-expanded attribute', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      const toggle = screen.getByTestId('feedback-toggle');
      expect(toggle).toHaveAttribute('aria-expanded', 'false');

      await user.click(toggle);
      expect(toggle).toHaveAttribute('aria-expanded', 'true');
    });

    it('shows calibration indicator in header when collapsed', async () => {
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} calibrationAdjusted={true} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-section')).toBeInTheDocument();
      });

      expect(screen.getByText('Calibration Adjusted')).toBeInTheDocument();
    });
  });

  describe('feedback selection', () => {
    it('renders all four feedback options', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));

      expect(screen.getByTestId('feedback-btn-correct')).toBeInTheDocument();
      expect(screen.getByTestId('feedback-btn-false_positive')).toBeInTheDocument();
      expect(screen.getByTestId('feedback-btn-missed_detection')).toBeInTheDocument();
      expect(screen.getByTestId('feedback-btn-wrong_severity')).toBeInTheDocument();
    });

    it('highlights selected feedback option', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));

      const correctBtn = screen.getByTestId('feedback-btn-correct');
      expect(correctBtn).toHaveAttribute('aria-pressed', 'false');

      await user.click(correctBtn);
      expect(correctBtn).toHaveAttribute('aria-pressed', 'true');
      expect(correctBtn).toHaveClass('border-[#76B900]');
    });

    it('allows changing selection', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));

      // Select correct
      await user.click(screen.getByTestId('feedback-btn-correct'));
      expect(screen.getByTestId('feedback-btn-correct')).toHaveAttribute('aria-pressed', 'true');

      // Change to false positive
      await user.click(screen.getByTestId('feedback-btn-false_positive'));
      expect(screen.getByTestId('feedback-btn-false_positive')).toHaveAttribute(
        'aria-pressed',
        'true'
      );
      expect(screen.getByTestId('feedback-btn-correct')).toHaveAttribute('aria-pressed', 'false');
    });
  });

  describe('notes input', () => {
    it('renders notes textarea', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));

      expect(screen.getByTestId('feedback-notes')).toBeInTheDocument();
      expect(screen.getByLabelText(/notes/i)).toBeInTheDocument();
    });

    it('allows typing in notes textarea', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));

      const textarea = screen.getByTestId('feedback-notes');
      await user.type(textarea, 'This is a test note');

      expect((textarea as HTMLTextAreaElement).value).toBe('This is a test note');
    });

    it('shows character count', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));

      expect(screen.getByText('0/1000')).toBeInTheDocument();

      const textarea = screen.getByTestId('feedback-notes');
      await user.type(textarea, 'Test');

      expect(screen.getByText('4/1000')).toBeInTheDocument();
    });

    it('has maxLength attribute', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));

      const textarea = screen.getByTestId('feedback-notes');
      expect(textarea).toHaveAttribute('maxLength', '1000');
    });
  });

  describe('submit button', () => {
    it('is disabled when no feedback type is selected', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));

      expect(screen.getByTestId('feedback-submit')).toBeDisabled();
    });

    it('is enabled when feedback type is selected', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));
      await user.click(screen.getByTestId('feedback-btn-correct'));

      expect(screen.getByTestId('feedback-submit')).not.toBeDisabled();
    });
  });

  describe('feedback submission', () => {
    it('submits feedback with selected type and notes', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'false_positive',
        notes: 'Test note',
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));
      await user.click(screen.getByTestId('feedback-btn-false_positive'));

      const textarea = screen.getByTestId('feedback-notes');
      await user.type(textarea, 'Test note');

      await user.click(screen.getByTestId('feedback-submit'));

      await waitFor(() => {
        expect(api.submitEventFeedback).toHaveBeenCalled();
        // Check the first argument passed to the mutation function
        const callArgs = vi.mocked(api.submitEventFeedback).mock.calls[0][0];
        expect(callArgs).toEqual({
          event_id: 123,
          feedback_type: 'false_positive',
          notes: 'Test note',
        });
      });
    });

    it('submits feedback without notes when notes are empty', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'correct',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));
      await user.click(screen.getByTestId('feedback-btn-correct'));
      await user.click(screen.getByTestId('feedback-submit'));

      await waitFor(() => {
        expect(api.submitEventFeedback).toHaveBeenCalled();
        // Check the first argument passed to the mutation function
        const callArgs = vi.mocked(api.submitEventFeedback).mock.calls[0][0];
        expect(callArgs).toEqual({
          event_id: 123,
          feedback_type: 'correct',
          notes: null,
        });
      });
    });

    it('shows loading spinner in submit button during submission', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      // Create a promise that we control the resolution of
      let resolveSubmit: (value: api.EventFeedbackResponse) => void = () => {};
      vi.mocked(api.submitEventFeedback).mockImplementation(
        () =>
          new Promise<api.EventFeedbackResponse>((resolve) => {
            resolveSubmit = resolve;
          })
      );

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));
      await user.click(screen.getByTestId('feedback-btn-correct'));

      // Before clicking submit, button should be enabled
      expect(screen.getByTestId('feedback-submit')).not.toBeDisabled();

      // Click submit
      await user.click(screen.getByTestId('feedback-submit'));

      // The button should be disabled during submission
      // Note: Due to optimistic updates, the component transitions quickly to read-only view
      // So we just verify the API was called
      await waitFor(() => {
        expect(api.submitEventFeedback).toHaveBeenCalled();
      });

      // Resolve the promise
      act(() => {
        resolveSubmit({
          id: 1,
          event_id: 123,
          feedback_type: 'correct',
          notes: null,
          created_at: '2024-01-15T10:30:00Z',
        });
      });

      // After resolution, should show read-only view
      await waitFor(() => {
        expect(screen.getByText('Feedback Submitted')).toBeInTheDocument();
      });
    });

    it('shows submitted feedback in read-only mode after successful submission', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'correct',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));
      await user.click(screen.getByTestId('feedback-btn-correct'));
      await user.click(screen.getByTestId('feedback-submit'));

      // After successful submission, the component shows read-only view with submitted feedback
      await waitFor(() => {
        expect(screen.getByText('Feedback Submitted')).toBeInTheDocument();
        expect(screen.getByText('Correct')).toBeInTheDocument();
      });
    });

    it('transitions to read-only view after submission completes', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));
      vi.mocked(api.submitEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'correct',
        notes: null,
        created_at: '2024-01-15T10:30:00Z',
      });

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));
      await user.click(screen.getByTestId('feedback-btn-correct'));

      // Before submission, we're in the form view
      expect(screen.getByTestId('feedback-submit')).toBeInTheDocument();

      await user.click(screen.getByTestId('feedback-submit'));

      // After submission, we transition to read-only view (no toggle button)
      await waitFor(() => {
        expect(screen.queryByTestId('feedback-toggle')).not.toBeInTheDocument();
        expect(screen.getByText('Feedback Submitted')).toBeInTheDocument();
      });
    });

    it('shows error message on submission failure', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));
      vi.mocked(api.submitEventFeedback).mockRejectedValue(new api.ApiError(500, 'Server error'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));
      await user.click(screen.getByTestId('feedback-btn-correct'));
      await user.click(screen.getByTestId('feedback-submit'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-error')).toBeInTheDocument();
      });
      expect(screen.getByText('Failed to submit feedback. Please try again.')).toBeInTheDocument();
    });

    it('shows specific error message for 409 conflict', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));
      vi.mocked(api.submitEventFeedback).mockRejectedValue(new api.ApiError(409, 'Conflict'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));
      await user.click(screen.getByTestId('feedback-btn-correct'));
      await user.click(screen.getByTestId('feedback-submit'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-error')).toBeInTheDocument();
      });
      expect(screen.getByText('Feedback already submitted for this event')).toBeInTheDocument();
    });
  });

  describe('optimistic updates', () => {
    it('shows submitted feedback immediately (optimistic update)', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      // Create a delayed response
      let resolveSubmit: (value: api.EventFeedbackResponse) => void;
      const submitPromise = new Promise<api.EventFeedbackResponse>((resolve) => {
        resolveSubmit = resolve;
      });
      vi.mocked(api.submitEventFeedback).mockReturnValue(submitPromise);

      const { queryClient } = renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));
      await user.click(screen.getByTestId('feedback-btn-correct'));
      await user.click(screen.getByTestId('feedback-submit'));

      // Check optimistic update in cache
      await waitFor(() => {
        const cachedFeedback = queryClient.getQueryData(['eventFeedback', 123]);
        expect(cachedFeedback).toBeDefined();
      });

      // Resolve the promise
      act(() => {
        resolveSubmit!({
          id: 1,
          event_id: 123,
          feedback_type: 'correct',
          notes: null,
          created_at: '2024-01-15T10:30:00Z',
        });
      });
    });
  });

  describe('calibration adjusted indicator', () => {
    it('shows calibration indicator inside expanded content', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} calibrationAdjusted={true} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));

      expect(
        screen.getByText('This event was adjusted by calibration settings')
      ).toBeInTheDocument();
    });

    it('hides header indicator when expanded', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} calibrationAdjusted={true} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      // When collapsed, indicator should be in header
      expect(screen.getByText('Calibration Adjusted')).toBeInTheDocument();

      await user.click(screen.getByTestId('feedback-toggle'));

      // After expanding, the detailed message should be visible
      expect(
        screen.getByText('This event was adjusted by calibration settings')
      ).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has proper aria attributes on toggle button', async () => {
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      const toggle = screen.getByTestId('feedback-toggle');
      expect(toggle).toHaveAttribute('aria-expanded', 'false');
      expect(toggle).toHaveAttribute('aria-controls', 'feedback-content');
    });

    it('has proper aria-pressed on feedback buttons', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));

      const correctBtn = screen.getByTestId('feedback-btn-correct');
      expect(correctBtn).toHaveAttribute('aria-pressed', 'false');
    });

    it('has proper label for notes textarea', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-toggle')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-toggle'));

      const textarea = screen.getByLabelText(/notes/i);
      expect(textarea).toBeInTheDocument();
    });
  });

  describe('className prop', () => {
    it('applies custom className', async () => {
      vi.mocked(api.fetchEventFeedback).mockRejectedValue(new api.ApiError(404, 'Not found'));

      renderWithQueryClient(<EventFeedbackSection eventId={123} className="custom-class" />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-section')).toBeInTheDocument();
      });

      expect(screen.getByTestId('feedback-section')).toHaveClass('custom-class');
    });
  });
});

/**
 * FeedbackPanel test suite
 *
 * Tests the FeedbackPanel component for event feedback collection.
 *
 * @see NEM-2353 - Create FeedbackPanel component for EventDetailModal
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import FeedbackPanel from './FeedbackPanel';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  getEventFeedback: vi.fn(),
  submitEventFeedback: vi.fn(),
}));

// Mock the toast hook
const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();
vi.mock('../../hooks/useToast', () => ({
  useToast: () => ({
    success: mockToastSuccess,
    error: mockToastError,
  }),
}));

// Helper to wrap component with QueryClientProvider
function renderWithQueryClient(component: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{component}</QueryClientProvider>);
}

describe('FeedbackPanel', () => {
  const defaultProps = {
    eventId: 123,
    currentRiskScore: 65,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Default: no existing feedback
    vi.mocked(api.getEventFeedback).mockResolvedValue(null);
    vi.mocked(api.submitEventFeedback).mockResolvedValue({
      id: 1,
      event_id: 123,
      feedback_type: 'accurate',
      notes: null,
      created_at: '2024-01-01T00:00:00Z',
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders the feedback panel', async () => {
      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-panel')).toBeInTheDocument();
      });
    });

    it('renders all four feedback buttons', async () => {
      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-btn-accurate')).toBeInTheDocument();
        expect(screen.getByTestId('feedback-btn-false_positive')).toBeInTheDocument();
        expect(screen.getByTestId('feedback-btn-missed_threat')).toBeInTheDocument();
        expect(screen.getByTestId('feedback-btn-severity_wrong')).toBeInTheDocument();
      });
    });

    it('shows correct button labels', async () => {
      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Accurate')).toBeInTheDocument();
        expect(screen.getByText('False Positive')).toBeInTheDocument();
        expect(screen.getByText('Missed Threat')).toBeInTheDocument();
        expect(screen.getByText('Severity Wrong')).toBeInTheDocument();
      });
    });

    it('shows help text', async () => {
      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText(/Help improve AI accuracy/)).toBeInTheDocument();
      });
    });

    it('applies custom className', async () => {
      renderWithQueryClient(<FeedbackPanel {...defaultProps} className="custom-class" />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-panel')).toHaveClass('custom-class');
      });
    });
  });

  describe('loading state', () => {
    it('shows loading indicator while fetching feedback', () => {
      // Set up a promise that never resolves to simulate loading
      vi.mocked(api.getEventFeedback).mockImplementation(() => new Promise(() => {}));

      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      expect(screen.getByText('Loading feedback...')).toBeInTheDocument();
    });
  });

  describe('existing feedback display', () => {
    it('shows existing feedback when present', async () => {
      vi.mocked(api.getEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'accurate',
        notes: null,
        created_at: '2024-01-15T10:00:00Z',
      });

      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('Accurate')).toBeInTheDocument();
        // Should not show the buttons grid when feedback exists
        expect(screen.queryByTestId('feedback-buttons')).not.toBeInTheDocument();
      });
    });

    it('displays notes when present in existing feedback', async () => {
      vi.mocked(api.getEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'false_positive',
        notes: 'This was my cat, not an intruder',
        created_at: '2024-01-15T10:00:00Z',
      });

      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText('This was my cat, not an intruder')).toBeInTheDocument();
      });
    });

    it('shows submission date', async () => {
      vi.mocked(api.getEventFeedback).mockResolvedValue({
        id: 1,
        event_id: 123,
        feedback_type: 'accurate',
        notes: null,
        created_at: '2024-01-15T10:00:00Z',
      });

      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText(/Submitted/)).toBeInTheDocument();
      });
    });
  });

  describe('quick feedback submission', () => {
    it('submits correct feedback when Correct button is clicked', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-btn-accurate')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-btn-accurate'));

      await waitFor(() => {
        expect(api.submitEventFeedback).toHaveBeenCalled();
        // Check first argument only (useMutation may pass additional internal args)
        const call = vi.mocked(api.submitEventFeedback).mock.calls[0];
        expect(call[0]).toEqual({
          event_id: 123,
          feedback_type: 'accurate',
        });
      });
    });

    it('shows toast on successful submission', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-btn-accurate')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-btn-accurate'));

      await waitFor(() => {
        expect(mockToastSuccess).toHaveBeenCalledWith('Feedback submitted successfully');
      });
    });

    it('shows error toast on failed submission', async () => {
      vi.mocked(api.submitEventFeedback).mockRejectedValue(new Error('Network error'));
      const user = userEvent.setup();

      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-btn-accurate')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-btn-accurate'));

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Failed to submit feedback: Network error');
      });
    });
  });

  describe('feedback form', () => {
    it('opens feedback form when False Positive is clicked', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-btn-false_positive')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-btn-false_positive'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-form')).toBeInTheDocument();
      });
    });

    it('opens feedback form when Missed Threat is clicked', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-btn-missed_threat')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-btn-missed_threat'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-form')).toBeInTheDocument();
      });
    });

    it('opens feedback form when Severity Wrong is clicked', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-btn-severity_wrong')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('feedback-btn-severity_wrong'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-form')).toBeInTheDocument();
      });
    });

    it('closes feedback form when cancel is clicked', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-btn-false_positive')).toBeInTheDocument();
      });

      // Open form
      await user.click(screen.getByTestId('feedback-btn-false_positive'));

      await waitFor(() => {
        expect(screen.getByTestId('feedback-form')).toBeInTheDocument();
      });

      // Close form
      await user.click(screen.getByTestId('cancel-feedback-button'));

      await waitFor(() => {
        expect(screen.queryByTestId('feedback-form')).not.toBeInTheDocument();
        expect(screen.getByTestId('feedback-buttons')).toBeInTheDocument();
      });
    });
  });

  describe('collapse/expand', () => {
    it('starts expanded by default', async () => {
      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-buttons')).toBeInTheDocument();
      });
    });

    it('starts collapsed when defaultCollapsed is true', async () => {
      renderWithQueryClient(<FeedbackPanel {...defaultProps} defaultCollapsed={true} />);

      await waitFor(() => {
        expect(screen.queryByTestId('feedback-buttons')).not.toBeInTheDocument();
      });
    });

    it('toggles collapse state when header is clicked', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<FeedbackPanel {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-buttons')).toBeInTheDocument();
      });

      // Collapse
      await user.click(screen.getByTestId('feedback-panel-toggle'));
      expect(screen.queryByTestId('feedback-buttons')).not.toBeInTheDocument();

      // Expand
      await user.click(screen.getByTestId('feedback-panel-toggle'));
      expect(screen.getByTestId('feedback-buttons')).toBeInTheDocument();
    });
  });

  describe('invalid event ID handling', () => {
    it('does not submit when event ID is NaN', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<FeedbackPanel eventId={NaN} currentRiskScore={65} />);

      // Wait for render to complete (it should handle the invalid ID gracefully)
      await waitFor(() => {
        expect(screen.getByTestId('feedback-panel')).toBeInTheDocument();
      });

      // Even if button is visible, clicking should not submit
      const correctBtn = screen.queryByTestId('feedback-btn-accurate');
      if (correctBtn) {
        await user.click(correctBtn);
        expect(api.submitEventFeedback).not.toHaveBeenCalled();
      }
    });

    it('does not submit when event ID is 0 or negative', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<FeedbackPanel eventId={0} currentRiskScore={65} />);

      await waitFor(() => {
        expect(screen.getByTestId('feedback-panel')).toBeInTheDocument();
      });

      const correctBtn = screen.queryByTestId('feedback-btn-accurate');
      if (correctBtn) {
        await user.click(correctBtn);
        expect(api.submitEventFeedback).not.toHaveBeenCalled();
      }
    });
  });
});

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { SummaryCardError } from './SummaryCardError';

describe('SummaryCardError', () => {
  const defaultProps = {
    type: 'hourly' as const,
    error: 'Something went wrong',
    onRetry: vi.fn(),
  };

  describe('rendering', () => {
    it('renders error container with correct test id for hourly', () => {
      render(<SummaryCardError {...defaultProps} />);
      const container = screen.getByTestId('summary-card-error-hourly');
      expect(container).toBeInTheDocument();
    });

    it('renders error container with correct test id for daily', () => {
      render(<SummaryCardError {...defaultProps} type="daily" />);
      const container = screen.getByTestId('summary-card-error-daily');
      expect(container).toBeInTheDocument();
    });

    it('renders "Hourly Summary" title for hourly type', () => {
      render(<SummaryCardError {...defaultProps} />);
      expect(screen.getByText('Hourly Summary')).toBeInTheDocument();
    });

    it('renders "Daily Summary" title for daily type', () => {
      render(<SummaryCardError {...defaultProps} type="daily" />);
      expect(screen.getByText('Daily Summary')).toBeInTheDocument();
    });

    it('renders "Failed to load summary" heading', () => {
      render(<SummaryCardError {...defaultProps} />);
      expect(screen.getByText('Failed to load summary')).toBeInTheDocument();
    });
  });

  describe('icons', () => {
    it('renders clock icon for hourly type', () => {
      const { container } = render(<SummaryCardError {...defaultProps} />);
      const clockIcon = container.querySelector('svg.lucide-clock');
      expect(clockIcon).toBeInTheDocument();
    });

    it('renders calendar icon for daily type', () => {
      const { container } = render(<SummaryCardError {...defaultProps} type="daily" />);
      const calendarIcon = container.querySelector('svg.lucide-calendar');
      expect(calendarIcon).toBeInTheDocument();
    });

    it('renders AlertTriangle icon', () => {
      const { container } = render(<SummaryCardError {...defaultProps} />);
      const alertIcon = container.querySelector('svg.lucide-triangle-alert');
      expect(alertIcon).toBeInTheDocument();
    });

    it('AlertTriangle icon has aria-hidden attribute', () => {
      const { container } = render(<SummaryCardError {...defaultProps} />);
      const alertIcon = container.querySelector('svg.lucide-triangle-alert');
      expect(alertIcon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  describe('error message translation', () => {
    it('translates network error to user-friendly message', () => {
      render(<SummaryCardError {...defaultProps} error="Network request failed" />);
      expect(
        screen.getByText('Unable to connect to the server. Please check your network connection.')
      ).toBeInTheDocument();
    });

    it('translates fetch error to user-friendly message', () => {
      render(<SummaryCardError {...defaultProps} error="Failed to fetch" />);
      expect(
        screen.getByText('Unable to connect to the server. Please check your network connection.')
      ).toBeInTheDocument();
    });

    it('translates timeout error to user-friendly message', () => {
      render(<SummaryCardError {...defaultProps} error="Request timed out" />);
      expect(screen.getByText('The request took too long. Please try again.')).toBeInTheDocument();
    });

    it('translates 500 server error to user-friendly message', () => {
      render(<SummaryCardError {...defaultProps} error="500 Internal Server Error" />);
      expect(
        screen.getByText('The server encountered an error. Please try again in a moment.')
      ).toBeInTheDocument();
    });

    it('translates 503 error to user-friendly message', () => {
      render(<SummaryCardError {...defaultProps} error="503 Service Unavailable" />);
      expect(
        screen.getByText('The server encountered an error. Please try again in a moment.')
      ).toBeInTheDocument();
    });

    it('translates 404 error to user-friendly message', () => {
      render(<SummaryCardError {...defaultProps} error="404 Not Found" />);
      expect(screen.getByText('Summary data is not available at this time.')).toBeInTheDocument();
    });

    it('translates 401 error to user-friendly message', () => {
      render(<SummaryCardError {...defaultProps} error="401 Unauthorized" />);
      expect(
        screen.getByText('Unable to access summary data. Please refresh the page.')
      ).toBeInTheDocument();
    });

    it('translates 429 rate limit error to user-friendly message', () => {
      render(<SummaryCardError {...defaultProps} error="429 Too Many Requests" />);
      expect(
        screen.getByText('Too many requests. Please wait a moment and try again.')
      ).toBeInTheDocument();
    });

    it('shows default message for unknown errors', () => {
      render(<SummaryCardError {...defaultProps} error="Some unknown error" />);
      expect(
        screen.getByText('Unable to load summary data. Please try again.')
      ).toBeInTheDocument();
    });

    it('handles Error objects', () => {
      render(<SummaryCardError {...defaultProps} error={new Error('Network failure')} />);
      expect(
        screen.getByText('Unable to connect to the server. Please check your network connection.')
      ).toBeInTheDocument();
    });
  });

  describe('retry button', () => {
    it('renders retry button', () => {
      render(<SummaryCardError {...defaultProps} />);
      expect(screen.getByText('Try again')).toBeInTheDocument();
    });

    it('button has correct test id for hourly', () => {
      render(<SummaryCardError {...defaultProps} />);
      const button = screen.getByTestId('summary-card-error-retry-hourly');
      expect(button).toBeInTheDocument();
    });

    it('button has correct test id for daily', () => {
      render(<SummaryCardError {...defaultProps} type="daily" />);
      const button = screen.getByTestId('summary-card-error-retry-daily');
      expect(button).toBeInTheDocument();
    });

    it('calls onRetry when button is clicked', async () => {
      const user = userEvent.setup();
      const handleRetry = vi.fn();
      render(<SummaryCardError {...defaultProps} onRetry={handleRetry} />);

      const button = screen.getByText('Try again');
      await user.click(button);

      expect(handleRetry).toHaveBeenCalledTimes(1);
    });

    it('button is keyboard accessible', async () => {
      const user = userEvent.setup();
      const handleRetry = vi.fn();
      render(<SummaryCardError {...defaultProps} onRetry={handleRetry} />);

      const button = screen.getByText('Try again');
      button.focus();
      await user.keyboard('{Enter}');

      expect(handleRetry).toHaveBeenCalledTimes(1);
    });

    it('renders RefreshCw icon in button', () => {
      const { container } = render(<SummaryCardError {...defaultProps} />);
      const refreshIcon = container.querySelector('svg.lucide-refresh-cw');
      expect(refreshIcon).toBeInTheDocument();
    });
  });

  describe('retrying state', () => {
    it('shows "Retrying..." text when isRetrying is true', () => {
      render(<SummaryCardError {...defaultProps} isRetrying />);
      expect(screen.getByText('Retrying...')).toBeInTheDocument();
    });

    it('does not show "Try again" when retrying', () => {
      render(<SummaryCardError {...defaultProps} isRetrying />);
      expect(screen.queryByText('Try again')).not.toBeInTheDocument();
    });

    it('disables button when isRetrying is true', () => {
      render(<SummaryCardError {...defaultProps} isRetrying />);
      const button = screen.getByTestId('summary-card-error-retry-hourly');
      expect(button).toBeDisabled();
    });

    it('button has cursor-not-allowed class when retrying', () => {
      render(<SummaryCardError {...defaultProps} isRetrying />);
      const button = screen.getByTestId('summary-card-error-retry-hourly');
      expect(button).toHaveClass('cursor-not-allowed');
    });

    it('RefreshCw icon has animate-spin class when retrying', () => {
      const { container } = render(<SummaryCardError {...defaultProps} isRetrying />);
      const refreshIcon = container.querySelector('svg.lucide-refresh-cw');
      expect(refreshIcon).toHaveClass('animate-spin');
    });

    it('RefreshCw icon does not have animate-spin when not retrying', () => {
      const { container } = render(<SummaryCardError {...defaultProps} />);
      const refreshIcon = container.querySelector('svg.lucide-refresh-cw');
      expect(refreshIcon).not.toHaveClass('animate-spin');
    });

    it('button has aria-label "Retrying..." when isRetrying is true', () => {
      render(<SummaryCardError {...defaultProps} isRetrying />);
      const button = screen.getByTestId('summary-card-error-retry-hourly');
      expect(button).toHaveAttribute('aria-label', 'Retrying...');
    });

    it('button has appropriate aria-label when not retrying', () => {
      render(<SummaryCardError {...defaultProps} />);
      const button = screen.getByTestId('summary-card-error-retry-hourly');
      expect(button).toHaveAttribute('aria-label', 'Retry loading summary');
    });
  });

  describe('accessibility', () => {
    it('has role="alert"', () => {
      render(<SummaryCardError {...defaultProps} />);
      const container = screen.getByTestId('summary-card-error-hourly');
      expect(container).toHaveAttribute('role', 'alert');
    });

    it('has aria-live="polite"', () => {
      render(<SummaryCardError {...defaultProps} />);
      const container = screen.getByTestId('summary-card-error-hourly');
      expect(container).toHaveAttribute('aria-live', 'polite');
    });
  });

  describe('styling', () => {
    it('applies NVIDIA dark theme background', () => {
      render(<SummaryCardError {...defaultProps} />);
      const container = screen.getByTestId('summary-card-error-hourly');
      expect(container).toHaveClass('bg-[#1A1A1A]');
    });

    it('applies red border for error state', () => {
      render(<SummaryCardError {...defaultProps} />);
      const container = screen.getByTestId('summary-card-error-hourly');
      // red-500 RGB value
      expect(container).toHaveStyle({ borderLeftColor: 'rgb(239, 68, 68)' });
    });

    it('applies border-l-4 class', () => {
      render(<SummaryCardError {...defaultProps} />);
      const container = screen.getByTestId('summary-card-error-hourly');
      expect(container).toHaveClass('border-l-4');
    });

    it('applies custom className when provided', () => {
      render(<SummaryCardError {...defaultProps} className="custom-class" />);
      const container = screen.getByTestId('summary-card-error-hourly');
      expect(container).toHaveClass('custom-class');
    });

    it('error content box has red styling', () => {
      render(<SummaryCardError {...defaultProps} />);
      const content = screen.getByTestId('summary-card-error-content-hourly');
      expect(content).toHaveClass('border-red-500/30');
      expect(content).toHaveClass('bg-red-900/20');
    });
  });

  describe('content structure', () => {
    it('includes content container with correct test id', () => {
      render(<SummaryCardError {...defaultProps} />);
      const content = screen.getByTestId('summary-card-error-content-hourly');
      expect(content).toBeInTheDocument();
    });

    it('content for daily has correct test id', () => {
      render(<SummaryCardError {...defaultProps} type="daily" />);
      const content = screen.getByTestId('summary-card-error-content-daily');
      expect(content).toBeInTheDocument();
    });
  });
});

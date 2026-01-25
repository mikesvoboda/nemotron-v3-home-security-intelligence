/**
 * Tests for ErrorState component.
 *
 * @see NEM-3529 - Add consistent retry buttons to all error states
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

import ErrorState from './ErrorState';

describe('ErrorState', () => {
  describe('default variant', () => {
    it('renders title correctly', () => {
      render(<ErrorState title="Error loading data" />);
      expect(screen.getByText('Error loading data')).toBeInTheDocument();
    });

    it('renders message when provided as string', () => {
      render(<ErrorState title="Error" message="Something went wrong" />);
      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('renders message when provided as Error object', () => {
      const error = new Error('Network failure');
      render(<ErrorState title="Error" message={error} />);
      expect(screen.getByText('Network failure')).toBeInTheDocument();
    });

    it('does not render message when null', () => {
      render(<ErrorState title="Error" message={null} />);
      // Only the title should be present
      const alert = screen.getByRole('alert');
      expect(alert.textContent).toBe('Error');
    });

    it('renders retry button when onRetry is provided', () => {
      const onRetry = vi.fn();
      render(<ErrorState title="Error" onRetry={onRetry} />);
      expect(screen.getByText('Try again')).toBeInTheDocument();
    });

    it('does not render retry button when onRetry is not provided', () => {
      render(<ErrorState title="Error" />);
      expect(screen.queryByText('Try again')).not.toBeInTheDocument();
    });

    it('calls onRetry when retry button is clicked', () => {
      const onRetry = vi.fn();
      render(<ErrorState title="Error" onRetry={onRetry} />);

      fireEvent.click(screen.getByText('Try again'));
      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('uses custom retry label when provided', () => {
      const onRetry = vi.fn();
      render(<ErrorState title="Error" onRetry={onRetry} retryLabel="Reload" />);
      expect(screen.getByText('Reload')).toBeInTheDocument();
    });

    it('shows retrying state correctly', () => {
      const onRetry = vi.fn();
      render(<ErrorState title="Error" onRetry={onRetry} isRetrying />);

      expect(screen.getByText('Retrying...')).toBeInTheDocument();
      expect(screen.getByTestId('error-state-retry')).toBeDisabled();
    });

    it('disables retry button when retrying', () => {
      const onRetry = vi.fn();
      render(<ErrorState title="Error" onRetry={onRetry} isRetrying />);

      fireEvent.click(screen.getByTestId('error-state-retry'));
      expect(onRetry).not.toHaveBeenCalled();
    });

    it('applies custom className', () => {
      render(<ErrorState title="Error" className="custom-class" />);
      expect(screen.getByRole('alert')).toHaveClass('custom-class');
    });

    it('uses custom testId', () => {
      render(<ErrorState title="Error" testId="custom-error" />);
      expect(screen.getByTestId('custom-error')).toBeInTheDocument();
    });

    it('has correct ARIA attributes', () => {
      render(<ErrorState title="Error" />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveAttribute('aria-live', 'polite');
    });
  });

  describe('compact variant', () => {
    it('renders compact variant correctly', () => {
      render(<ErrorState title="Failed to load" variant="compact" />);
      expect(screen.getByText('Failed to load')).toBeInTheDocument();
    });

    it('renders message in compact variant', () => {
      render(
        <ErrorState
          title="Error"
          message="Details here"
          variant="compact"
        />
      );
      expect(screen.getByText('Details here')).toBeInTheDocument();
    });

    it('renders retry button in compact variant', () => {
      const onRetry = vi.fn();
      render(
        <ErrorState
          title="Error"
          onRetry={onRetry}
          variant="compact"
        />
      );

      expect(screen.getByText('Try again')).toBeInTheDocument();
      fireEvent.click(screen.getByText('Try again'));
      expect(onRetry).toHaveBeenCalledTimes(1);
    });

    it('shows retrying state in compact variant', () => {
      const onRetry = vi.fn();
      render(
        <ErrorState
          title="Error"
          onRetry={onRetry}
          isRetrying
          variant="compact"
        />
      );

      expect(screen.getByText('Retrying...')).toBeInTheDocument();
    });

    it('has correct styling classes for compact variant', () => {
      render(<ErrorState title="Error" variant="compact" />);
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('p-3'); // Compact padding
    });
  });

  describe('accessibility', () => {
    it('retry button has accessible name', () => {
      const onRetry = vi.fn();
      render(<ErrorState title="Error" onRetry={onRetry} />);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent('Try again');
    });

    it('error icon is hidden from screen readers', () => {
      render(<ErrorState title="Error" />);

      // The icon should be inside the alert but marked as aria-hidden
      const alert = screen.getByRole('alert');
      const icon = alert.querySelector('svg');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });
});

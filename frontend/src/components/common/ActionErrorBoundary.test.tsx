/**
 * Tests for ActionErrorBoundary component.
 *
 * @see NEM-3358 - Enhance Error Boundaries with Actions integration
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  ActionErrorBoundary,
  ActionErrorDisplay,
  FormActionError,
} from './ActionErrorBoundary';

import type { FormActionState } from '../../hooks/useFormAction';

// Mock the services
vi.mock('../../services/logger', () => ({
  logger: {
    error: vi.fn(),
    warn: vi.fn(),
    info: vi.fn(),
  },
}));

vi.mock('../../services/sentry', () => ({
  captureError: vi.fn(),
  isSentryEnabled: vi.fn(() => false),
}));

// Component that throws an error
function ThrowingComponent({ shouldThrow = true }: { shouldThrow?: boolean }) {
  if (shouldThrow) {
    throw new Error('Test render error');
  }
  return <div>Rendered successfully</div>;
}

describe('ActionErrorBoundary', () => {
  const originalConsoleError = console.error;

  beforeEach(() => {
    vi.clearAllMocks();
    // Suppress console.error for expected errors
    console.error = vi.fn();
  });

  afterEach(() => {
    console.error = originalConsoleError;
  });

  describe('normal rendering', () => {
    it('renders children when there is no error', () => {
      render(
        <ActionErrorBoundary feature="Test Feature">
          <div>Child content</div>
        </ActionErrorBoundary>
      );

      expect(screen.getByText('Child content')).toBeInTheDocument();
    });

    it('renders children when action state is idle', () => {
      const state: FormActionState = { status: 'idle' };

      render(
        <ActionErrorBoundary feature="Test Feature" actionState={state}>
          <div>Form content</div>
        </ActionErrorBoundary>
      );

      expect(screen.getByText('Form content')).toBeInTheDocument();
    });

    it('renders children when action state is success', () => {
      const state: FormActionState = { status: 'success', data: { ok: true } };

      render(
        <ActionErrorBoundary feature="Test Feature" actionState={state}>
          <div>Success content</div>
        </ActionErrorBoundary>
      );

      expect(screen.getByText('Success content')).toBeInTheDocument();
    });

    it('renders children when action state is pending', () => {
      const state: FormActionState = { status: 'pending' };

      render(
        <ActionErrorBoundary feature="Test Feature" actionState={state}>
          <div>Loading...</div>
        </ActionErrorBoundary>
      );

      expect(screen.getByText('Loading...')).toBeInTheDocument();
    });
  });

  describe('render errors', () => {
    it('catches render errors and displays fallback', () => {
      render(
        <ActionErrorBoundary feature="Dashboard">
          <ThrowingComponent />
        </ActionErrorBoundary>
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/dashboard crashed/i)).toBeInTheDocument();
      expect(screen.getByText('Test render error')).toBeInTheDocument();
    });

    it('displays retry button for render errors', () => {
      render(
        <ActionErrorBoundary feature="Widget">
          <ThrowingComponent />
        </ActionErrorBoundary>
      );

      expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    });

    it('retries rendering when retry button is clicked', () => {
      let shouldThrow = true;

      function ConditionalThrow() {
        if (shouldThrow) {
          throw new Error('Conditional error');
        }
        return <div>Recovered!</div>;
      }

      render(
        <ActionErrorBoundary feature="Test">
          <ConditionalThrow />
        </ActionErrorBoundary>
      );

      // Initially shows error
      expect(screen.getByText(/test crashed/i)).toBeInTheDocument();

      // Stop throwing and click retry
      shouldThrow = false;
      fireEvent.click(screen.getByRole('button', { name: /try again/i }));

      // Should render successfully
      expect(screen.getByText('Recovered!')).toBeInTheDocument();
    });

    it('uses custom render error fallback when provided', () => {
      render(
        <ActionErrorBoundary
          feature="Test"
          renderErrorFallback={<div data-testid="custom-fallback">Custom error UI</div>}
        >
          <ThrowingComponent />
        </ActionErrorBoundary>
      );

      expect(screen.getByTestId('custom-fallback')).toBeInTheDocument();
    });

    it('calls onError callback for render errors', () => {
      const onError = vi.fn();

      render(
        <ActionErrorBoundary feature="Test" onError={onError}>
          <ThrowingComponent />
        </ActionErrorBoundary>
      );

      expect(onError).toHaveBeenCalledWith(
        expect.any(Error),
        'render'
      );
    });
  });

  describe('action errors', () => {
    it('displays action error state', () => {
      const state: FormActionState = {
        status: 'error',
        error: 'Failed to save settings',
      };

      render(
        <ActionErrorBoundary feature="Settings" actionState={state}>
          <div>Form content</div>
        </ActionErrorBoundary>
      );

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/settings encountered an error/i)).toBeInTheDocument();
      expect(screen.getByText('Failed to save settings')).toBeInTheDocument();
    });

    it('displays field-level errors', () => {
      const state: FormActionState = {
        status: 'error',
        error: 'Validation failed',
        fieldErrors: {
          email: 'Invalid email format',
          name: 'Name is required',
        },
      };

      render(
        <ActionErrorBoundary feature="Contact Form" actionState={state}>
          <div>Form content</div>
        </ActionErrorBoundary>
      );

      expect(screen.getByText(/field errors/i)).toBeInTheDocument();
      expect(screen.getByText('Invalid email format')).toBeInTheDocument();
      expect(screen.getByText('Name is required')).toBeInTheDocument();
    });

    it('still renders children below action error', () => {
      const state: FormActionState = {
        status: 'error',
        error: 'Submission failed',
      };

      render(
        <ActionErrorBoundary feature="Form" actionState={state}>
          <div data-testid="form-content">Form fields here</div>
        </ActionErrorBoundary>
      );

      // Error is shown
      expect(screen.getByRole('alert')).toBeInTheDocument();
      // But children are also rendered
      expect(screen.getByTestId('form-content')).toBeInTheDocument();
    });

    it('calls onRetry when retry button is clicked', () => {
      const onRetry = vi.fn();
      const state: FormActionState = {
        status: 'error',
        error: 'Network error',
      };

      render(
        <ActionErrorBoundary feature="API" actionState={state} onRetry={onRetry}>
          <div>Content</div>
        </ActionErrorBoundary>
      );

      fireEvent.click(screen.getByRole('button', { name: /try again/i }));

      expect(onRetry).toHaveBeenCalled();
    });

    it('uses custom action error fallback when provided', () => {
      const state: FormActionState = {
        status: 'error',
        error: 'Test error',
      };

      render(
        <ActionErrorBoundary
          feature="Test"
          actionState={state}
          actionErrorFallback={(actionState, onRetry) => (
            <div data-testid="custom-action-error">
              <span>{actionState.error}</span>
              <button onClick={onRetry}>Custom Retry</button>
            </div>
          )}
        >
          <div>Content</div>
        </ActionErrorBoundary>
      );

      expect(screen.getByTestId('custom-action-error')).toBeInTheDocument();
      expect(screen.getByText('Test error')).toBeInTheDocument();
    });

    it('calls onError callback for action errors', () => {
      const onError = vi.fn();

      // First render with success state
      const { rerender } = render(
        <ActionErrorBoundary
          feature="Test"
          actionState={{ status: 'success' }}
          onError={onError}
        >
          <div>Content</div>
        </ActionErrorBoundary>
      );

      // Then update to error state
      rerender(
        <ActionErrorBoundary
          feature="Test"
          actionState={{ status: 'error', error: 'New error' }}
          onError={onError}
        >
          <div>Content</div>
        </ActionErrorBoundary>
      );

      expect(onError).toHaveBeenCalledWith('New error', 'action');
    });
  });

  describe('compact mode', () => {
    it('renders compact error display', () => {
      const state: FormActionState = {
        status: 'error',
        error: 'Quick error',
      };

      render(
        <ActionErrorBoundary feature="Quick" actionState={state} compact>
          <div>Content</div>
        </ActionErrorBoundary>
      );

      expect(screen.getByTestId('action-error-compact')).toBeInTheDocument();
    });
  });

  describe('render error takes priority', () => {
    it('shows render error even if action state has error', () => {
      const state: FormActionState = {
        status: 'error',
        error: 'Action error',
      };

      render(
        <ActionErrorBoundary feature="Test" actionState={state}>
          <ThrowingComponent />
        </ActionErrorBoundary>
      );

      // Should show render error, not action error
      expect(screen.getByText(/test crashed/i)).toBeInTheDocument();
      expect(screen.queryByText('Action error')).not.toBeInTheDocument();
    });
  });
});

describe('ActionErrorDisplay', () => {
  describe('full display mode', () => {
    it('renders error message', () => {
      const state: FormActionState = {
        status: 'error',
        error: 'Something went wrong',
      };

      render(<ActionErrorDisplay state={state} feature="Upload" />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText(/upload encountered an error/i)).toBeInTheDocument();
      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('shows retry button when onRetry is provided', () => {
      const onRetry = vi.fn();
      const state: FormActionState = {
        status: 'error',
        error: 'Failed',
      };

      render(<ActionErrorDisplay state={state} feature="Test" onRetry={onRetry} />);

      const retryButton = screen.getByRole('button', { name: /try again/i });
      expect(retryButton).toBeInTheDocument();

      fireEvent.click(retryButton);
      expect(onRetry).toHaveBeenCalled();
    });

    it('does not show retry button when onRetry is not provided', () => {
      const state: FormActionState = {
        status: 'error',
        error: 'Failed',
      };

      render(<ActionErrorDisplay state={state} feature="Test" />);

      expect(screen.queryByRole('button', { name: /try again/i })).not.toBeInTheDocument();
    });

    it('displays field errors', () => {
      const state: FormActionState = {
        status: 'error',
        error: 'Validation failed',
        fieldErrors: {
          email: 'Invalid email',
          username: 'Too short',
        },
      };

      render(<ActionErrorDisplay state={state} feature="Login" />);

      expect(screen.getByText(/field errors/i)).toBeInTheDocument();
      expect(screen.getByText('email:')).toBeInTheDocument();
      expect(screen.getByText('Invalid email')).toBeInTheDocument();
      expect(screen.getByText('username:')).toBeInTheDocument();
      expect(screen.getByText('Too short')).toBeInTheDocument();
    });

    it('uses warning style for field-level errors', () => {
      const state: FormActionState = {
        status: 'error',
        fieldErrors: { email: 'Invalid' },
      };

      render(<ActionErrorDisplay state={state} feature="Test" />);

      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('border-yellow-500/50');
    });
  });

  describe('compact mode', () => {
    it('renders compact display', () => {
      const state: FormActionState = {
        status: 'error',
        error: 'Quick error',
      };

      render(<ActionErrorDisplay state={state} feature="Test" compact />);

      expect(screen.getByTestId('action-error-compact')).toBeInTheDocument();
    });

    it('shows inline retry link in compact mode', () => {
      const onRetry = vi.fn();
      const state: FormActionState = {
        status: 'error',
        error: 'Failed',
      };

      render(<ActionErrorDisplay state={state} feature="Test" onRetry={onRetry} compact />);

      const retryLink = screen.getByRole('button', { name: /retry test/i });
      expect(retryLink).toBeInTheDocument();

      fireEvent.click(retryLink);
      expect(onRetry).toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('has role alert', () => {
      const state: FormActionState = {
        status: 'error',
        error: 'Error',
      };

      render(<ActionErrorDisplay state={state} feature="Test" />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('has aria-live polite', () => {
      const state: FormActionState = {
        status: 'error',
        error: 'Error',
      };

      render(<ActionErrorDisplay state={state} feature="Test" />);

      expect(screen.getByRole('alert')).toHaveAttribute('aria-live', 'polite');
    });
  });
});

describe('FormActionError', () => {
  it('returns null when status is not error', () => {
    const { container } = render(
      <FormActionError state={{ status: 'idle' }} feature="Test" />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('returns null when status is success', () => {
    const { container } = render(
      <FormActionError state={{ status: 'success' }} feature="Test" />
    );

    expect(container).toBeEmptyDOMElement();
  });

  it('renders error display when status is error', () => {
    render(
      <FormActionError
        state={{ status: 'error', error: 'Test error' }}
        feature="Test Form"
      />
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Test error')).toBeInTheDocument();
  });

  it('passes through all props to ActionErrorDisplay', () => {
    const onRetry = vi.fn();

    render(
      <FormActionError
        state={{ status: 'error', error: 'Error' }}
        feature="Test"
        onRetry={onRetry}
        compact
      />
    );

    expect(screen.getByTestId('action-error-compact')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalled();
  });
});

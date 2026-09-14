import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import ErrorBoundary, { clearErrorCache, clearBackendLoggedErrors } from './ErrorBoundary';
import * as apiModule from '../../services/api';
import * as sentryModule from '../../services/sentry';

// Base time for consistent testing
const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

// Mock the Sentry module
vi.mock('../../services/sentry', () => ({
  captureError: vi.fn(),
  isSentryEnabled: vi.fn(() => false),
}));

// Mock the API module for backend logging
vi.mock('../../services/api', () => ({
  logFrontendErrorNoThrow: vi.fn(() => Promise.resolve(true)),
  createFrontendErrorPayload: vi.fn((error, options) => ({
    level: 'ERROR',
    message: error.message,
    component: options?.component || 'Unknown',
    url: 'http://localhost:5173',
    user_agent: 'Mozilla/5.0',
    extra: {
      stack: error.stack,
      source: options?.source || 'error_boundary',
      timestamp: '2024-01-15T10:00:00.000Z', // Use deterministic timestamp
      componentStack: options?.componentStack,
    },
  })),
}));

// Component that throws an error when rendered
const ThrowingComponent = ({ shouldThrow = true }: { shouldThrow?: boolean }) => {
  if (shouldThrow) {
    throw new Error('Test error message');
  }
  return <div>Child component rendered successfully</div>;
};

describe('ErrorBoundary', () => {
  // Suppress console.error during tests to avoid noise
  const originalError = console.error;
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
    console.error = vi.fn();
    // Clear error cache before each test to ensure test isolation
    clearErrorCache();
  });
  afterEach(() => {
    console.error = originalError;
    vi.useRealTimers();
  });

  describe('normal rendering', () => {
    it('renders children when there is no error', () => {
      render(
        <ErrorBoundary>
          <div>Normal content</div>
        </ErrorBoundary>
      );
      expect(screen.getByText('Normal content')).toBeInTheDocument();
    });

    it('renders multiple children without error', () => {
      render(
        <ErrorBoundary>
          <div>First child</div>
          <div>Second child</div>
        </ErrorBoundary>
      );
      expect(screen.getByText('First child')).toBeInTheDocument();
      expect(screen.getByText('Second child')).toBeInTheDocument();
    });

    it('renders nested components without error', () => {
      render(
        <ErrorBoundary>
          <div>
            <span>Nested content</span>
          </div>
        </ErrorBoundary>
      );
      expect(screen.getByText('Nested content')).toBeInTheDocument();
    });
  });

  describe('error catching', () => {
    it('catches error and displays fallback UI', () => {
      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('displays the error message in the fallback UI', () => {
      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      expect(screen.getByText('Test error message')).toBeInTheDocument();
    });

    it('logs error to centralized logger', () => {
      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      // The logger.error call results in a formatted console output
      // The format is "[ERROR] <component>: <message>" followed by the extra data
      expect(console.error).toHaveBeenCalledWith(
        '[ERROR] frontend: React component error',
        expect.objectContaining({
          error: 'Test error message',
          stack: expect.any(String),
          componentStack: expect.any(String),
          name: 'Error',
          url: expect.any(String),
        })
      );
    });

    it('calls onError callback when error is caught', () => {
      const onError = vi.fn();
      render(
        <ErrorBoundary onError={onError}>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      expect(onError).toHaveBeenCalledWith(
        expect.any(Error),
        expect.objectContaining({
          componentStack: expect.any(String),
        })
      );
    });
  });

  describe('custom props', () => {
    it('displays custom title when provided', () => {
      render(
        <ErrorBoundary title="Custom Error Title">
          <ThrowingComponent />
        </ErrorBoundary>
      );
      expect(screen.getByText('Custom Error Title')).toBeInTheDocument();
    });

    it('displays custom description when provided', () => {
      render(
        <ErrorBoundary description="Custom error description here">
          <ThrowingComponent />
        </ErrorBoundary>
      );
      expect(screen.getByText('Custom error description here')).toBeInTheDocument();
    });

    it('displays custom fallback when provided', () => {
      render(
        <ErrorBoundary fallback={<div>Custom fallback UI</div>}>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      expect(screen.getByText('Custom fallback UI')).toBeInTheDocument();
      // Default fallback elements should not be present
      expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
    });

    it('renders ReactNode as custom fallback', () => {
      render(
        <ErrorBoundary
          fallback={
            <div data-testid="custom-fallback">
              <h1>Error occurred</h1>
              <p>Please try again</p>
            </div>
          }
        >
          <ThrowingComponent />
        </ErrorBoundary>
      );
      expect(screen.getByTestId('custom-fallback')).toBeInTheDocument();
      expect(screen.getByText('Error occurred')).toBeInTheDocument();
      expect(screen.getByText('Please try again')).toBeInTheDocument();
    });
  });

  describe('recovery buttons', () => {
    it('displays Try Again button in fallback UI', () => {
      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    });

    it('displays Refresh Page button in fallback UI', () => {
      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      expect(screen.getByRole('button', { name: /refresh page/i })).toBeInTheDocument();
    });

    it('resets error state when Try Again is clicked and child stops throwing', () => {
      let shouldThrow = true;

      const DynamicThrowingComponent = () => {
        if (shouldThrow) {
          throw new Error('Test error message');
        }
        return <div>Child component rendered successfully</div>;
      };

      render(
        <ErrorBoundary>
          <DynamicThrowingComponent />
        </ErrorBoundary>
      );

      // Verify error state
      expect(screen.getByRole('alert')).toBeInTheDocument();

      // Now make the child stop throwing
      shouldThrow = false;

      // Click Try Again - this should reset error state and re-render children
      fireEvent.click(screen.getByRole('button', { name: /try again/i }));

      // Child should now render successfully
      expect(screen.getByText('Child component rendered successfully')).toBeInTheDocument();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('calls window.location.reload when Refresh Page is clicked', () => {
      const reloadMock = vi.fn();
      // Store original reload function by creating a bound reference
      const originalReloadFn = window.location.reload.bind(window.location);
      Object.defineProperty(window, 'location', {
        value: { reload: reloadMock },
        writable: true,
      });

      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );

      fireEvent.click(screen.getByRole('button', { name: /refresh page/i }));
      expect(reloadMock).toHaveBeenCalled();

      // Restore original
      Object.defineProperty(window, 'location', {
        value: { reload: originalReloadFn },
        writable: true,
      });
    });

    it('displays Report Issue button in fallback UI', () => {
      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      expect(screen.getByRole('button', { name: /report.*issue/i })).toBeInTheDocument();
    });

    it('opens GitHub issue URL when Report Issue is clicked', () => {
      const openMock = vi.fn();
      const originalOpen = window.open;
      window.open = openMock;

      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );

      fireEvent.click(screen.getByRole('button', { name: /report.*issue/i }));

      expect(openMock).toHaveBeenCalledTimes(1);
      const [url, target, features] = openMock.mock.calls[0];

      // Verify URL structure
      expect(url).toContain('/issues/new?');
      expect(url).toContain('title=');
      expect(url).toContain('body=');
      // Labels may or may not have encoded comma depending on browser
      expect(url).toMatch(/labels=bug[%2C,]user-reported/);

      // Verify window open options
      expect(target).toBe('_blank');
      expect(features).toBe('noopener,noreferrer');

      // Restore original
      window.open = originalOpen;
    });

    it('includes error details in the GitHub issue URL', () => {
      const openMock = vi.fn();
      const originalOpen = window.open;
      window.open = openMock;

      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );

      fireEvent.click(screen.getByRole('button', { name: /report.*issue/i }));

      const url = openMock.mock.calls[0][0] as string;

      // Verify error details are included in the URL
      expect(url).toContain(encodeURIComponent('Test error message'));
      expect(url).toContain(encodeURIComponent('Error Type'));
      expect(url).toContain(encodeURIComponent('Stack Trace'));

      // Restore original
      window.open = originalOpen;
    });
  });

  describe('accessibility', () => {
    it('renders fallback with role="alert"', () => {
      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('renders fallback with aria-live="assertive"', () => {
      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      const alert = screen.getByRole('alert');
      expect(alert).toHaveAttribute('aria-live', 'assertive');
    });

    it('has accessible button labels', () => {
      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /refresh page/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /report.*issue/i })).toBeInTheDocument();
    });

    it('hides decorative icons from screen readers', () => {
      const { container } = render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      const icons = container.querySelectorAll('svg');
      icons.forEach((icon) => {
        expect(icon).toHaveAttribute('aria-hidden', 'true');
      });
    });
  });

  describe('styling', () => {
    it('applies error styling to fallback container', () => {
      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      const alert = screen.getByRole('alert');
      expect(alert).toHaveClass('border-red-500/20', 'bg-red-500/5');
    });

    it('renders AlertOctagon icon in fallback', () => {
      const { container } = render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      const svg = container.querySelector('svg.lucide-octagon-alert');
      expect(svg).toBeInTheDocument();
      expect(svg).toHaveClass('text-red-500');
    });

    it('renders RefreshCw icon in Try Again button', () => {
      const { container } = render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      const buttons = container.querySelectorAll('button');
      const tryAgainButton = Array.from(buttons).find((btn) =>
        btn.textContent?.includes('Try Again')
      );
      expect(tryAgainButton).toBeInTheDocument();
      const refreshIcon = tryAgainButton?.querySelector('svg.lucide-refresh-cw');
      expect(refreshIcon).toBeInTheDocument();
    });
  });

  describe('error boundary isolation', () => {
    it('only catches errors in its children, not siblings', () => {
      render(
        <div>
          <div data-testid="sibling">Sibling content</div>
          <ErrorBoundary>
            <ThrowingComponent />
          </ErrorBoundary>
        </div>
      );
      expect(screen.getByTestId('sibling')).toBeInTheDocument();
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('nested error boundaries work correctly', () => {
      render(
        <ErrorBoundary title="Outer boundary">
          <div data-testid="outer-content">Outer content</div>
          <ErrorBoundary title="Inner boundary">
            <ThrowingComponent />
          </ErrorBoundary>
        </ErrorBoundary>
      );
      // Inner boundary should catch the error
      expect(screen.getByText('Inner boundary')).toBeInTheDocument();
      // Outer boundary should not show error
      expect(screen.queryByText('Outer boundary')).not.toBeInTheDocument();
      // Outer content should still be visible
      expect(screen.getByTestId('outer-content')).toBeInTheDocument();
    });
  });

  describe('getDerivedStateFromError', () => {
    it('updates state with hasError and error on error', () => {
      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      // If getDerivedStateFromError worked, the fallback should be shown
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Test error message')).toBeInTheDocument();
    });
  });

  describe('componentDidCatch', () => {
    it('is called when error occurs', () => {
      const onError = vi.fn();
      render(
        <ErrorBoundary onError={onError}>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      // onError is called from componentDidCatch
      expect(onError).toHaveBeenCalledTimes(1);
    });

    it('receives error and errorInfo', () => {
      const onError = vi.fn();
      render(
        <ErrorBoundary onError={onError}>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      const [error, errorInfo] = onError.mock.calls[0];
      expect(error).toBeInstanceOf(Error);
      expect(error.message).toBe('Test error message');
      expect(errorInfo).toHaveProperty('componentStack');
      expect(typeof errorInfo.componentStack).toBe('string');
    });

    it('logs componentName when provided', () => {
      render(
        <ErrorBoundary componentName="TestComponent">
          <ThrowingComponent />
        </ErrorBoundary>
      );
      // The logger.error call includes componentName in extra data
      expect(console.error).toHaveBeenCalledWith(
        '[ERROR] frontend: React component error',
        expect.objectContaining({
          error: 'Test error message',
          component: 'TestComponent',
        })
      );
    });

    it('deduplicates identical errors and only logs once', () => {
      // Clear error cache to ensure clean state
      clearErrorCache();
      // Clear any previous mock calls
      vi.clearAllMocks();

      // Component that always throws the same error
      const DuplicateThrowingComponent = () => {
        throw new Error('Duplicate error for dedup test');
      };

      // Render first boundary
      render(
        <ErrorBoundary>
          <DuplicateThrowingComponent />
        </ErrorBoundary>
      );

      // Count how many times the error was logged
      const firstCallCount = (console.error as ReturnType<typeof vi.fn>).mock.calls.filter(
        (call) => call[0] === '[ERROR] frontend: React component error'
      ).length;

      expect(firstCallCount).toBe(1);

      // Render second boundary with same error (same message and stack location)
      render(
        <ErrorBoundary>
          <DuplicateThrowingComponent />
        </ErrorBoundary>
      );

      // Should still be 1 due to deduplication
      const secondCallCount = (console.error as ReturnType<typeof vi.fn>).mock.calls.filter(
        (call) => call[0] === '[ERROR] frontend: React component error'
      ).length;

      // With deduplication, the second identical error should not be logged
      expect(secondCallCount).toBe(1);
    });
  });

  describe('default messages', () => {
    it('shows default title when not provided', () => {
      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('shows default description when not provided', () => {
      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );
      expect(
        screen.getByText(
          'An unexpected error occurred. You can try to recover by clicking the button below, or refresh the page.'
        )
      ).toBeInTheDocument();
    });
  });

  describe('Sentry integration', () => {
    beforeEach(() => {
      vi.clearAllMocks();
    });

    it('reports error to Sentry when Sentry is enabled', () => {
      vi.mocked(sentryModule.isSentryEnabled).mockReturnValue(true);

      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );

      expect(sentryModule.captureError).toHaveBeenCalledWith(
        expect.objectContaining({
          message: 'Test error message',
        }),
        expect.objectContaining({
          tags: {
            component: 'ErrorBoundary',
          },
          extra: expect.objectContaining({
            componentStack: expect.any(String),
          }),
        })
      );
    });

    it('does not report error to Sentry when Sentry is disabled', () => {
      vi.mocked(sentryModule.isSentryEnabled).mockReturnValue(false);

      render(
        <ErrorBoundary>
          <ThrowingComponent />
        </ErrorBoundary>
      );

      expect(sentryModule.captureError).not.toHaveBeenCalled();
    });

    it('reports error with custom boundary name in tags', () => {
      vi.mocked(sentryModule.isSentryEnabled).mockReturnValue(true);

      render(
        <ErrorBoundary boundaryName="DashboardBoundary">
          <ThrowingComponent />
        </ErrorBoundary>
      );

      expect(sentryModule.captureError).toHaveBeenCalledWith(
        expect.any(Error),
        expect.objectContaining({
          tags: {
            component: 'DashboardBoundary',
          },
        })
      );
    });
  });

  describe('backend logging integration (NEM-2725)', () => {
    beforeEach(() => {
      vi.clearAllMocks();
      clearBackendLoggedErrors();
    });

    it('logs error to backend via logFrontendErrorNoThrow', async () => {
      render(
        <ErrorBoundary componentName="TestComponent">
          <ThrowingComponent />
        </ErrorBoundary>
      );

      // Wait for async logging to complete
      await vi.waitFor(() => {
        expect(apiModule.logFrontendErrorNoThrow).toHaveBeenCalled();
      });
    });

    it('creates payload with createFrontendErrorPayload', async () => {
      render(
        <ErrorBoundary componentName="DashboardComponent">
          <ThrowingComponent />
        </ErrorBoundary>
      );

      await vi.waitFor(() => {
        expect(apiModule.createFrontendErrorPayload).toHaveBeenCalledWith(
          expect.objectContaining({
            message: 'Test error message',
          }),
          expect.objectContaining({
            component: 'DashboardComponent',
          })
        );
      });
    });

    it('includes component stack in payload', async () => {
      render(
        <ErrorBoundary componentName="HeaderComponent">
          <ThrowingComponent />
        </ErrorBoundary>
      );

      await vi.waitFor(() => {
        expect(apiModule.createFrontendErrorPayload).toHaveBeenCalledWith(
          expect.any(Error),
          expect.objectContaining({
            componentStack: expect.any(String),
          })
        );
      });
    });

    it('deduplicates backend logging for identical errors', async () => {
      // Clear error caches
      clearErrorCache();
      clearBackendLoggedErrors();
      vi.clearAllMocks();

      // Component that always throws the same error
      const BackendDuplicateThrowingComponent = () => {
        throw new Error('Duplicate backend error');
      };

      // Render first boundary
      render(
        <ErrorBoundary>
          <BackendDuplicateThrowingComponent />
        </ErrorBoundary>
      );

      await vi.waitFor(() => {
        expect(apiModule.logFrontendErrorNoThrow).toHaveBeenCalledTimes(1);
      });

      // Render second boundary with same error
      render(
        <ErrorBoundary>
          <BackendDuplicateThrowingComponent />
        </ErrorBoundary>
      );

      // Wait a bit to ensure no additional calls
      await new Promise((resolve) => setTimeout(resolve, 50));

      // Should still be 1 due to deduplication
      expect(apiModule.logFrontendErrorNoThrow).toHaveBeenCalledTimes(1);
    });

    it('does not crash app when backend logging fails', () => {
      // Make backend logging fail
      vi.mocked(apiModule.logFrontendErrorNoThrow).mockRejectedValueOnce(
        new Error('Network error')
      );

      // Should not throw
      expect(() => {
        render(
          <ErrorBoundary>
            <ThrowingComponent />
          </ErrorBoundary>
        );
      }).not.toThrow();

      // Error boundary should still render fallback
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('logs different errors separately', async () => {
      clearBackendLoggedErrors();
      vi.clearAllMocks();

      // Component that throws first error
      const ErrorComponent1 = () => {
        throw new Error('First unique error');
      };

      // Component that throws second error
      const ErrorComponent2 = () => {
        throw new Error('Second unique error');
      };

      render(
        <ErrorBoundary>
          <ErrorComponent1 />
        </ErrorBoundary>
      );

      await vi.waitFor(() => {
        expect(apiModule.logFrontendErrorNoThrow).toHaveBeenCalledTimes(1);
      });

      render(
        <ErrorBoundary>
          <ErrorComponent2 />
        </ErrorBoundary>
      );

      await vi.waitFor(() => {
        expect(apiModule.logFrontendErrorNoThrow).toHaveBeenCalledTimes(2);
      });
    });
  });
});

/**
 * Tests for FeatureErrorBoundary component.
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { FeatureErrorBoundary } from './FeatureErrorBoundary';

// Component that throws an error when rendered
const ThrowingComponent = ({ shouldThrow = true }: { shouldThrow?: boolean }) => {
  if (shouldThrow) {
    throw new Error('Test feature error');
  }
  return <div>Feature component rendered successfully</div>;
};

describe('FeatureErrorBoundary', () => {
  // Suppress console.error during tests to avoid noise
  const originalError = console.error;
  beforeEach(() => {
    console.error = vi.fn();
  });
  afterEach(() => {
    console.error = originalError;
  });

  describe('normal rendering', () => {
    it('renders children when there is no error', () => {
      render(
        <FeatureErrorBoundary feature="Test Feature">
          <div>Normal content</div>
        </FeatureErrorBoundary>
      );
      expect(screen.getByText('Normal content')).toBeInTheDocument();
    });

    it('renders multiple children without error', () => {
      render(
        <FeatureErrorBoundary feature="Test Feature">
          <div>First child</div>
          <div>Second child</div>
        </FeatureErrorBoundary>
      );
      expect(screen.getByText('First child')).toBeInTheDocument();
      expect(screen.getByText('Second child')).toBeInTheDocument();
    });
  });

  describe('error catching', () => {
    it('catches error and displays fallback UI with feature name', () => {
      render(
        <FeatureErrorBoundary feature="Camera Grid">
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Camera Grid encountered an error')).toBeInTheDocument();
    });

    it('displays the error message in the fallback UI', () => {
      render(
        <FeatureErrorBoundary feature="Risk Gauge">
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      expect(screen.getByText('Test feature error')).toBeInTheDocument();
    });

    it('calls onError callback when error is caught', () => {
      const onError = vi.fn();
      render(
        <FeatureErrorBoundary feature="Activity Feed" onError={onError}>
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      expect(onError).toHaveBeenCalledWith(
        expect.any(Error),
        expect.objectContaining({
          componentStack: expect.any(String),
        })
      );
    });

    it('logs error to centralized logger with feature context', () => {
      render(
        <FeatureErrorBoundary feature="GPU Stats">
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      // The logger.error call results in a formatted console output
      expect(console.error).toHaveBeenCalledWith(
        '[ERROR] frontend: Error in GPU Stats',
        expect.objectContaining({
          error: 'Test feature error',
          feature: 'GPU Stats',
        })
      );
    });
  });

  describe('custom fallback', () => {
    it('displays custom fallback when provided', () => {
      render(
        <FeatureErrorBoundary feature="Test Feature" fallback={<div>Custom fallback UI</div>}>
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      expect(screen.getByText('Custom fallback UI')).toBeInTheDocument();
      expect(screen.queryByText('Test Feature encountered an error')).not.toBeInTheDocument();
    });

    it('renders ReactNode as custom fallback', () => {
      render(
        <FeatureErrorBoundary
          feature="Test Feature"
          fallback={
            <div data-testid="custom-fallback">
              <h1>Oops!</h1>
              <p>Something went wrong</p>
            </div>
          }
        >
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      expect(screen.getByTestId('custom-fallback')).toBeInTheDocument();
      expect(screen.getByText('Oops!')).toBeInTheDocument();
    });
  });

  describe('compact mode', () => {
    it('renders compact fallback when compact prop is true', () => {
      render(
        <FeatureErrorBoundary feature="Quick Stats" compact>
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      expect(screen.getByTestId('feature-error-compact')).toBeInTheDocument();
      expect(screen.getByText('Quick Stats unavailable')).toBeInTheDocument();
    });

    it('shows Retry button in compact mode', () => {
      render(
        <FeatureErrorBoundary feature="Quick Stats" compact>
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    it('has accessible label for retry button in compact mode', () => {
      render(
        <FeatureErrorBoundary feature="Quick Stats" compact>
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      const retryButton = screen.getByRole('button', { name: /retry loading quick stats/i });
      expect(retryButton).toBeInTheDocument();
    });
  });

  describe('recovery button', () => {
    it('displays Try again button in default fallback UI', () => {
      render(
        <FeatureErrorBoundary feature="Test Feature">
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    });

    it('resets error state when Try again is clicked and child stops throwing', () => {
      let shouldThrow = true;

      const DynamicThrowingComponent = () => {
        if (shouldThrow) {
          throw new Error('Test feature error');
        }
        return <div>Feature component rendered successfully</div>;
      };

      render(
        <FeatureErrorBoundary feature="Test Feature">
          <DynamicThrowingComponent />
        </FeatureErrorBoundary>
      );

      // Verify error state
      expect(screen.getByRole('alert')).toBeInTheDocument();

      // Now make the child stop throwing
      shouldThrow = false;

      // Click Try Again - this should reset error state and re-render children
      fireEvent.click(screen.getByRole('button', { name: /try again/i }));

      // Child should now render successfully
      expect(screen.getByText('Feature component rendered successfully')).toBeInTheDocument();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('resets error state when Retry is clicked in compact mode', () => {
      let shouldThrow = true;

      const DynamicThrowingComponent = () => {
        if (shouldThrow) {
          throw new Error('Test feature error');
        }
        return <div>Feature component rendered successfully</div>;
      };

      render(
        <FeatureErrorBoundary feature="Test Feature" compact>
          <DynamicThrowingComponent />
        </FeatureErrorBoundary>
      );

      // Verify error state
      expect(screen.getByTestId('feature-error-compact')).toBeInTheDocument();

      // Now make the child stop throwing
      shouldThrow = false;

      // Click Retry
      fireEvent.click(screen.getByRole('button', { name: /retry/i }));

      // Child should now render successfully
      expect(screen.getByText('Feature component rendered successfully')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('renders fallback with role="alert"', () => {
      render(
        <FeatureErrorBoundary feature="Test Feature">
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('renders fallback with aria-live="polite"', () => {
      render(
        <FeatureErrorBoundary feature="Test Feature">
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      const alert = screen.getByRole('alert');
      expect(alert).toHaveAttribute('aria-live', 'polite');
    });

    it('has accessible button labels', () => {
      render(
        <FeatureErrorBoundary feature="Test Feature">
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    });

    it('hides decorative icons from screen readers', () => {
      const { container } = render(
        <FeatureErrorBoundary feature="Test Feature">
          <ThrowingComponent />
        </FeatureErrorBoundary>
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
        <FeatureErrorBoundary feature="Test Feature">
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      const alert = screen.getByTestId('feature-error-boundary');
      expect(alert).toHaveClass('border-red-500/50', 'bg-red-900/20');
    });

    it('renders AlertTriangle icon in fallback', () => {
      const { container } = render(
        <FeatureErrorBoundary feature="Test Feature">
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      const svg = container.querySelector('svg.lucide-triangle-alert');
      expect(svg).toBeInTheDocument();
    });

    it('renders RefreshCw icon in Try again button', () => {
      const { container } = render(
        <FeatureErrorBoundary feature="Test Feature">
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      const refreshIcon = container.querySelector('svg.lucide-refresh-cw');
      expect(refreshIcon).toBeInTheDocument();
    });
  });

  describe('error boundary isolation', () => {
    it('only catches errors in its children, not siblings', () => {
      render(
        <div>
          <div data-testid="sibling">Sibling content</div>
          <FeatureErrorBoundary feature="Test Feature">
            <ThrowingComponent />
          </FeatureErrorBoundary>
        </div>
      );
      expect(screen.getByTestId('sibling')).toBeInTheDocument();
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('nested feature error boundaries work correctly', () => {
      render(
        <FeatureErrorBoundary feature="Outer Feature">
          <div data-testid="outer-content">Outer content</div>
          <FeatureErrorBoundary feature="Inner Feature">
            <ThrowingComponent />
          </FeatureErrorBoundary>
        </FeatureErrorBoundary>
      );
      // Inner boundary should catch the error
      expect(screen.getByText('Inner Feature encountered an error')).toBeInTheDocument();
      // Outer boundary should not show error
      expect(screen.queryByText('Outer Feature encountered an error')).not.toBeInTheDocument();
      // Outer content should still be visible
      expect(screen.getByTestId('outer-content')).toBeInTheDocument();
    });

    it('multiple feature error boundaries work independently', () => {
      render(
        <div>
          <FeatureErrorBoundary feature="Feature A">
            <ThrowingComponent />
          </FeatureErrorBoundary>
          <FeatureErrorBoundary feature="Feature B">
            <div>Feature B works fine</div>
          </FeatureErrorBoundary>
        </div>
      );
      expect(screen.getByText('Feature A encountered an error')).toBeInTheDocument();
      expect(screen.getByText('Feature B works fine')).toBeInTheDocument();
    });
  });

  describe('getDerivedStateFromError', () => {
    it('updates state with hasError and error on error', () => {
      render(
        <FeatureErrorBoundary feature="Test Feature">
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      // If getDerivedStateFromError worked, the fallback should be shown
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Test feature error')).toBeInTheDocument();
    });
  });

  describe('componentDidCatch', () => {
    it('is called when error occurs', () => {
      const onError = vi.fn();
      render(
        <FeatureErrorBoundary feature="Test Feature" onError={onError}>
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      // onError is called from componentDidCatch
      expect(onError).toHaveBeenCalledTimes(1);
    });

    it('receives error and errorInfo', () => {
      const onError = vi.fn();
      render(
        <FeatureErrorBoundary feature="Test Feature" onError={onError}>
          <ThrowingComponent />
        </FeatureErrorBoundary>
      );
      const [error, errorInfo] = onError.mock.calls[0];
      expect(error).toBeInstanceOf(Error);
      expect(error.message).toBe('Test feature error');
      expect(errorInfo).toHaveProperty('componentStack');
      expect(typeof errorInfo.componentStack).toBe('string');
    });
  });
});

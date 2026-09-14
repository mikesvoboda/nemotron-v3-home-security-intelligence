/**
 * Tests for withFeatureErrorBoundary HOC.
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { withFeatureErrorBoundary } from './useFeatureErrorBoundary';

// Component that throws an error when rendered
const ThrowingComponent = ({ shouldThrow = true }: { shouldThrow?: boolean }) => {
  if (shouldThrow) {
    throw new Error('Test HOC error');
  }
  return <div>Component rendered successfully</div>;
};

// Simple component that works normally
const WorkingComponent = ({ message = 'Hello' }: { message?: string }) => {
  return <div data-testid="working-component">{message}</div>;
};

// Named component for display name testing
function NamedComponent() {
  return <div>Named component</div>;
}

describe('withFeatureErrorBoundary HOC', () => {
  // Suppress console.error during tests to avoid noise
  const originalError = console.error;
  beforeEach(() => {
    console.error = vi.fn();
  });
  afterEach(() => {
    console.error = originalError;
  });

  describe('normal rendering', () => {
    it('renders wrapped component when there is no error', () => {
      const WrappedComponent = withFeatureErrorBoundary(WorkingComponent, 'Test Feature');
      render(<WrappedComponent message="Test message" />);

      expect(screen.getByTestId('working-component')).toBeInTheDocument();
      expect(screen.getByText('Test message')).toBeInTheDocument();
    });

    it('passes all props to the wrapped component', () => {
      interface TestProps {
        name: string;
        count: number;
        items: string[];
      }

      const PropsTestComponent = ({ name, count, items }: TestProps) => (
        <div>
          <span data-testid="name">{name}</span>
          <span data-testid="count">{count}</span>
          <span data-testid="items">{items.join(',')}</span>
        </div>
      );

      const WrappedComponent = withFeatureErrorBoundary(PropsTestComponent, 'Props Test');
      render(<WrappedComponent name="Test" count={42} items={['a', 'b', 'c']} />);

      expect(screen.getByTestId('name')).toHaveTextContent('Test');
      expect(screen.getByTestId('count')).toHaveTextContent('42');
      expect(screen.getByTestId('items')).toHaveTextContent('a,b,c');
    });
  });

  describe('error handling', () => {
    it('catches error and displays default fallback UI', () => {
      const WrappedComponent = withFeatureErrorBoundary(ThrowingComponent, 'Error Test');
      render(<WrappedComponent />);

      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('Error Test encountered an error')).toBeInTheDocument();
    });

    it('displays custom fallback when provided', () => {
      const WrappedComponent = withFeatureErrorBoundary(ThrowingComponent, 'Custom Fallback', {
        fallback: <div data-testid="custom-fallback">Custom error message</div>,
      });
      render(<WrappedComponent />);

      expect(screen.getByTestId('custom-fallback')).toBeInTheDocument();
      expect(screen.getByText('Custom error message')).toBeInTheDocument();
    });

    it('calls onError callback when error is caught', () => {
      const onError = vi.fn();
      const WrappedComponent = withFeatureErrorBoundary(ThrowingComponent, 'Callback Test', {
        onError,
      });
      render(<WrappedComponent />);

      expect(onError).toHaveBeenCalledWith(
        expect.any(Error),
        expect.objectContaining({
          componentStack: expect.any(String),
        })
      );
    });

    it('uses compact mode when specified', () => {
      const WrappedComponent = withFeatureErrorBoundary(ThrowingComponent, 'Compact Test', {
        compact: true,
      });
      render(<WrappedComponent />);

      expect(screen.getByTestId('feature-error-compact')).toBeInTheDocument();
      expect(screen.getByText('Compact Test unavailable')).toBeInTheDocument();
    });
  });

  describe('recovery', () => {
    it('allows recovery via Try again button', () => {
      let shouldThrow = true;

      const DynamicComponent = () => {
        if (shouldThrow) {
          throw new Error('Test error');
        }
        return <div data-testid="recovered">Recovered!</div>;
      };

      const WrappedComponent = withFeatureErrorBoundary(DynamicComponent, 'Recovery Test');
      render(<WrappedComponent />);

      // Verify error state
      expect(screen.getByRole('alert')).toBeInTheDocument();

      // Fix the component
      shouldThrow = false;

      // Click Try Again
      fireEvent.click(screen.getByRole('button', { name: /try again/i }));

      // Verify recovery
      expect(screen.getByTestId('recovered')).toBeInTheDocument();
    });
  });

  describe('display name', () => {
    it('sets correct display name for named functions', () => {
      const WrappedComponent = withFeatureErrorBoundary(NamedComponent, 'Named');
      expect(WrappedComponent.displayName).toBe('WithFeatureErrorBoundary(NamedComponent)');
    });

    it('sets correct display name for components with displayName', () => {
      const ComponentWithDisplayName = () => <div>Test</div>;
      ComponentWithDisplayName.displayName = 'CustomDisplayName';

      const WrappedComponent = withFeatureErrorBoundary(ComponentWithDisplayName, 'Display');
      expect(WrappedComponent.displayName).toBe('WithFeatureErrorBoundary(CustomDisplayName)');
    });

    it('uses Component for anonymous functions', () => {
      const WrappedComponent = withFeatureErrorBoundary(() => <div>Anonymous</div>, 'Anon');
      expect(WrappedComponent.displayName).toBe('WithFeatureErrorBoundary(Component)');
    });
  });

  describe('isolation', () => {
    it('catches errors only in the wrapped component tree', () => {
      const WrappedThrowing = withFeatureErrorBoundary(ThrowingComponent, 'Isolated');
      const WrappedWorking = withFeatureErrorBoundary(WorkingComponent, 'Working');

      render(
        <div>
          <WrappedThrowing />
          <WrappedWorking message="Still works" />
        </div>
      );

      // Throwing component shows error
      expect(screen.getByText('Isolated encountered an error')).toBeInTheDocument();

      // Working component still renders
      expect(screen.getByText('Still works')).toBeInTheDocument();
    });
  });

  describe('type safety', () => {
    it('preserves component prop types', () => {
      interface StrictProps {
        required: string;
        optional?: number;
      }

      const StrictComponent = ({ required, optional }: StrictProps) => (
        <div>
          {required}
          {optional}
        </div>
      );

      const WrappedComponent = withFeatureErrorBoundary(StrictComponent, 'Strict');

      // This should compile without type errors
      render(<WrappedComponent required="test" optional={42} />);
      render(<WrappedComponent required="test" />);

      expect(screen.getAllByText(/test/)).toHaveLength(2);
    });
  });
});

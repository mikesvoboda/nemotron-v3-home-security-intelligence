/**
 * Tests for ProfiledComponent and withProfiling HOC.
 *
 * These tests verify that the profiling components correctly wrap
 * children and record render metrics via the PerformanceTracker service.
 */

/* eslint-disable @typescript-eslint/unbound-method */

import { render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ProfiledComponent, useProfiler, withProfiling } from './ProfiledComponent';

// Mock the performanceTracker service
vi.mock('@/services/performanceTracker', () => ({
  performanceTracker: {
    isEnabled: vi.fn(() => true),
    recordRender: vi.fn(),
    getSlowRenderThreshold: vi.fn(() => 16),
  },
}));

// Import mocked module
import { performanceTracker } from '@/services/performanceTracker';

describe('ProfiledComponent', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders children correctly', () => {
    render(
      <ProfiledComponent id="TestComponent">
        <div data-testid="child">Hello World</div>
      </ProfiledComponent>
    );

    expect(screen.getByTestId('child')).toBeInTheDocument();
    expect(screen.getByText('Hello World')).toBeInTheDocument();
  });

  it('records render metric when enabled', () => {
    vi.mocked(performanceTracker.isEnabled).mockReturnValue(true);

    render(
      <ProfiledComponent id="TestComponent" enabled={true}>
        <div>Content</div>
      </ProfiledComponent>
    );

    // React Profiler callback should have been triggered
    expect(performanceTracker.recordRender).toHaveBeenCalled();

    // Verify the metric structure
    const call = vi.mocked(performanceTracker.recordRender).mock.calls[0][0];
    expect(call.component).toBe('TestComponent');
    expect(call.phase).toBe('mount');
    expect(typeof call.actualDuration).toBe('number');
    expect(typeof call.baseDuration).toBe('number');
    expect(typeof call.startTime).toBe('number');
    expect(typeof call.commitTime).toBe('number');
  });

  it('does not record metric when disabled', () => {
    vi.mocked(performanceTracker.isEnabled).mockReturnValue(false);

    render(
      <ProfiledComponent id="TestComponent" enabled={false}>
        <div>Content</div>
      </ProfiledComponent>
    );

    expect(performanceTracker.recordRender).not.toHaveBeenCalled();
  });

  it('uses tracker enabled state by default', () => {
    vi.mocked(performanceTracker.isEnabled).mockReturnValue(true);

    render(
      <ProfiledComponent id="TestComponent">
        <div>Content</div>
      </ProfiledComponent>
    );

    expect(performanceTracker.recordRender).toHaveBeenCalled();
  });

  it('can override enabled state', () => {
    vi.mocked(performanceTracker.isEnabled).mockReturnValue(true);

    render(
      <ProfiledComponent id="TestComponent" enabled={false}>
        <div>Content</div>
      </ProfiledComponent>
    );

    expect(performanceTracker.recordRender).not.toHaveBeenCalled();
  });

  it('handles multiple children', () => {
    render(
      <ProfiledComponent id="MultiChild">
        <div data-testid="child1">First</div>
        <div data-testid="child2">Second</div>
      </ProfiledComponent>
    );

    expect(screen.getByTestId('child1')).toBeInTheDocument();
    expect(screen.getByTestId('child2')).toBeInTheDocument();
  });

  it('handles fragments as children', () => {
    render(
      <ProfiledComponent id="FragmentChild">
        <>
          <span data-testid="span1">A</span>
          <span data-testid="span2">B</span>
        </>
      </ProfiledComponent>
    );

    expect(screen.getByTestId('span1')).toBeInTheDocument();
    expect(screen.getByTestId('span2')).toBeInTheDocument();
  });
});

describe('withProfiling HOC', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(performanceTracker.isEnabled).mockReturnValue(true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('wraps component with profiling', () => {
    interface TestProps {
      message: string;
    }

    function TestComponent({ message }: TestProps) {
      return <div data-testid="test">{message}</div>;
    }

    const ProfiledTest = withProfiling(TestComponent, 'TestComponent');

    render(<ProfiledTest message="Hello" />);

    expect(screen.getByTestId('test')).toBeInTheDocument();
    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(performanceTracker.recordRender).toHaveBeenCalled();
  });

  it('passes props to wrapped component', () => {
    interface TestProps {
      name: string;
      count: number;
      onClick: () => void;
    }

    const clickHandler = vi.fn();

    function TestComponent({ name, count, onClick }: TestProps) {
      return (
        <button data-testid="test" onClick={onClick}>
          {name}: {count}
        </button>
      );
    }

    const ProfiledTest = withProfiling(TestComponent, 'TestComponent');

    render(<ProfiledTest name="Counter" count={42} onClick={clickHandler} />);

    const button = screen.getByTestId('test');
    expect(button).toHaveTextContent('Counter: 42');

    button.click();
    expect(clickHandler).toHaveBeenCalled();
  });

  it('sets correct displayName', () => {
    function MyComponent() {
      return <div>Test</div>;
    }

    const ProfiledMyComponent = withProfiling(MyComponent, 'MyComponent');

    expect(ProfiledMyComponent.displayName).toBe('withProfiling(MyComponent)');
  });

  it('handles component without displayName', () => {
    const AnonymousComponent = () => <div>Anonymous</div>;
    // Remove name by reassigning
    Object.defineProperty(AnonymousComponent, 'name', { value: '' });

    const Profiled = withProfiling(AnonymousComponent, 'Anonymous');

    expect(Profiled.displayName).toBe('withProfiling(Component)');
  });

  it('allows disabling via profilingEnabled prop', () => {
    function TestComponent() {
      return <div data-testid="test">Content</div>;
    }

    const ProfiledTest = withProfiling(TestComponent, 'TestComponent');

    render(<ProfiledTest profilingEnabled={false} />);

    expect(screen.getByTestId('test')).toBeInTheDocument();
    expect(performanceTracker.recordRender).not.toHaveBeenCalled();
  });

  it('records component ID in metrics', () => {
    function TestComponent() {
      return <div>Content</div>;
    }

    const ProfiledTest = withProfiling(TestComponent, 'UniqueComponentId');

    render(<ProfiledTest />);

    const call = vi.mocked(performanceTracker.recordRender).mock.calls[0][0];
    expect(call.component).toBe('UniqueComponentId');
  });
});

describe('useProfiler hook', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns a function to record metrics', () => {
    function TestComponent() {
      const recordRender = useProfiler('TestComponent');

      // Simulate recording a metric
      recordRender({
        phase: 'update',
        actualDuration: 25,
        baseDuration: 10,
        startTime: 1000,
        commitTime: 1025,
      });

      return <div data-testid="test">Content</div>;
    }

    render(<TestComponent />);

    expect(performanceTracker.recordRender).toHaveBeenCalledWith({
      component: 'TestComponent',
      phase: 'update',
      actualDuration: 25,
      baseDuration: 10,
      startTime: 1000,
      commitTime: 1025,
    });
  });

  it('adds component ID to metrics', () => {
    function TestComponent() {
      const recordRender = useProfiler('MySpecificComponent');

      recordRender({
        phase: 'mount',
        actualDuration: 50,
        baseDuration: 20,
        startTime: 500,
        commitTime: 550,
      });

      return <div>Content</div>;
    }

    render(<TestComponent />);

    const call = vi.mocked(performanceTracker.recordRender).mock.calls[0][0];
    expect(call.component).toBe('MySpecificComponent');
  });
});

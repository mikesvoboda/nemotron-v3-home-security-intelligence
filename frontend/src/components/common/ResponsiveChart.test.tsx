import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ResponsiveChart from './ResponsiveChart';

// Mock framer-motion
vi.mock('framer-motion', () => ({
  motion: {
    div: ({
      children,
      className,
      'data-testid': testId,
      onClick,
      role,
      ...props
    }: {
      children?: React.ReactNode;
      className?: string;
      'data-testid'?: string;
      onClick?: () => void;
      role?: string;
      [key: string]: unknown;
    }) => (
      // eslint-disable-next-line jsx-a11y/no-static-element-interactions, jsx-a11y/click-events-have-key-events
      <div
        className={className}
        data-testid={testId}
        onClick={onClick}
        role={role}
        {...props}
      >
        {children}
      </div>
    ),
  },
  AnimatePresence: ({ children }: { children?: React.ReactNode }) => (
    <>{children}</>
  ),
  useReducedMotion: vi.fn(() => false),
}));

const mockLegendItems = [
  { name: 'Person', value: 150, color: '#10b981' },
  { name: 'Vehicle', value: 89, color: '#3b82f6' },
];

describe('ResponsiveChart', () => {
  let originalResizeObserver: typeof ResizeObserver;

  beforeEach(() => {
    originalResizeObserver = globalThis.ResizeObserver;

    globalThis.ResizeObserver = class MockResizeObserver {
      observe = vi.fn();
      unobserve = vi.fn();
      disconnect = vi.fn();
    } as unknown as typeof ResizeObserver;

    // Mock matchMedia for non-mobile
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
  });

  afterEach(() => {
    globalThis.ResizeObserver = originalResizeObserver;
    vi.clearAllMocks();
  });

  describe('basic rendering', () => {
    it('renders children with dimensions', () => {
      render(
        <ResponsiveChart>
          {({ width, height }) => (
            <div data-testid="chart-content">
              Width: {width}, Height: {height}
            </div>
          )}
        </ResponsiveChart>
      );

      expect(screen.getByTestId('chart-content')).toBeInTheDocument();
    });

    it('renders title when provided', () => {
      render(
        <ResponsiveChart title="Detection Distribution">
          {() => <div>Chart</div>}
        </ResponsiveChart>
      );

      expect(screen.getByText('Detection Distribution')).toBeInTheDocument();
    });

    it('renders subtitle when provided', () => {
      render(
        <ResponsiveChart title="Title" subtitle="Last 24 hours">
          {() => <div>Chart</div>}
        </ResponsiveChart>
      );

      expect(screen.getByText('Last 24 hours')).toBeInTheDocument();
    });
  });

  describe('legend integration', () => {
    it('renders legend when legendItems provided', () => {
      render(
        <ResponsiveChart legendItems={mockLegendItems}>
          {() => <div>Chart</div>}
        </ResponsiveChart>
      );

      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
    });

    it('positions legend at top by default', () => {
      render(
        <ResponsiveChart legendItems={mockLegendItems} legendPosition="top">
          {() => <div data-testid="chart-area">Chart</div>}
        </ResponsiveChart>
      );

      const container = screen.getByTestId('responsive-chart');
      // Verify both legend and chart are present
      expect(screen.getByTestId('chart-legend')).toBeInTheDocument();
      expect(screen.getByTestId('chart-area')).toBeInTheDocument();

      // Legend should come before chart in DOM order for top position
      expect(container.innerHTML.indexOf('chart-legend')).toBeLessThan(
        container.innerHTML.indexOf('chart-area')
      );
    });

    it('positions legend at bottom when specified', () => {
      render(
        <ResponsiveChart legendItems={mockLegendItems} legendPosition="bottom">
          {() => <div data-testid="chart-area">Chart</div>}
        </ResponsiveChart>
      );

      const container = screen.getByTestId('responsive-chart');

      // Legend should come after chart in DOM order for bottom position
      expect(container.innerHTML.indexOf('chart-legend')).toBeGreaterThan(
        container.innerHTML.indexOf('chart-area')
      );
    });

    it('hides legend when legendPosition is none', () => {
      render(
        <ResponsiveChart legendItems={mockLegendItems} legendPosition="none">
          {() => <div>Chart</div>}
        </ResponsiveChart>
      );

      expect(screen.queryByTestId('chart-legend')).not.toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('shows loading skeleton when isLoading is true', () => {
      render(
        <ResponsiveChart isLoading>
          {() => <div data-testid="chart-content">Chart</div>}
        </ResponsiveChart>
      );

      expect(screen.getByTestId('chart-loading-skeleton')).toBeInTheDocument();
      expect(screen.queryByTestId('chart-content')).not.toBeInTheDocument();
    });

    it('hides loading skeleton when isLoading is false', () => {
      render(
        <ResponsiveChart isLoading={false}>
          {() => <div data-testid="chart-content">Chart</div>}
        </ResponsiveChart>
      );

      expect(screen.queryByTestId('chart-loading-skeleton')).not.toBeInTheDocument();
      expect(screen.getByTestId('chart-content')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error state when error is provided', () => {
      render(
        <ResponsiveChart error="Failed to load data">
          {() => <div data-testid="chart-content">Chart</div>}
        </ResponsiveChart>
      );

      expect(screen.getByText('Failed to load data')).toBeInTheDocument();
      expect(screen.queryByTestId('chart-content')).not.toBeInTheDocument();
    });

    it('shows retry button when onRetry is provided', () => {
      const handleRetry = vi.fn();
      render(
        <ResponsiveChart error="Failed to load data" onRetry={handleRetry}>
          {() => <div>Chart</div>}
        </ResponsiveChart>
      );

      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
    });

    it('calls onRetry when retry button is clicked', async () => {
      const handleRetry = vi.fn();
      const user = userEvent.setup();

      render(
        <ResponsiveChart error="Failed to load data" onRetry={handleRetry}>
          {() => <div>Chart</div>}
        </ResponsiveChart>
      );

      await user.click(screen.getByRole('button', { name: /retry/i }));
      expect(handleRetry).toHaveBeenCalled();
    });
  });

  describe('empty state', () => {
    it('shows empty state when isEmpty is true', () => {
      render(
        <ResponsiveChart isEmpty emptyMessage="No data available">
          {() => <div data-testid="chart-content">Chart</div>}
        </ResponsiveChart>
      );

      expect(screen.getByText('No data available')).toBeInTheDocument();
      expect(screen.queryByTestId('chart-content')).not.toBeInTheDocument();
    });

    it('uses default empty message when not provided', () => {
      render(
        <ResponsiveChart isEmpty>
          {() => <div>Chart</div>}
        </ResponsiveChart>
      );

      expect(screen.getByText('No data to display')).toBeInTheDocument();
    });
  });

  describe('fullscreen functionality', () => {
    it('shows fullscreen button on mobile', () => {
      // Mock mobile viewport
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        configurable: true,
        value: vi.fn((query: string) => ({
          matches: query.includes('max-width: 768px'),
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      });

      render(
        <ResponsiveChart enableFullscreen>
          {() => <div>Chart</div>}
        </ResponsiveChart>
      );

      expect(screen.getByRole('button', { name: /expand/i })).toBeInTheDocument();
    });

    it('opens fullscreen modal when expand button is clicked', async () => {
      // Mock mobile viewport
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        configurable: true,
        value: vi.fn((query: string) => ({
          matches: query.includes('max-width: 768px'),
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      });

      const user = userEvent.setup();

      render(
        <ResponsiveChart enableFullscreen title="Test Chart">
          {() => <div data-testid="chart-content">Chart</div>}
        </ResponsiveChart>
      );

      await user.click(screen.getByRole('button', { name: /expand/i }));

      await waitFor(() => {
        expect(screen.getByTestId('fullscreen-modal')).toBeInTheDocument();
      });
    });

    it('closes fullscreen modal when close button is clicked', async () => {
      // Mock mobile viewport
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        configurable: true,
        value: vi.fn((query: string) => ({
          matches: query.includes('max-width: 768px'),
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      });

      const user = userEvent.setup();

      render(
        <ResponsiveChart enableFullscreen>
          {() => <div>Chart</div>}
        </ResponsiveChart>
      );

      // Open fullscreen
      await user.click(screen.getByRole('button', { name: /expand/i }));

      await waitFor(() => {
        expect(screen.getByTestId('fullscreen-modal')).toBeInTheDocument();
      });

      // Close fullscreen
      await user.click(screen.getByRole('button', { name: /close/i }));

      await waitFor(() => {
        expect(screen.queryByTestId('fullscreen-modal')).not.toBeInTheDocument();
      });
    });
  });

  describe('accessibility', () => {
    it('has accessible container role', () => {
      render(
        <ResponsiveChart title="Test Chart">
          {() => <div>Chart</div>}
        </ResponsiveChart>
      );

      expect(screen.getByRole('figure')).toBeInTheDocument();
    });

    it('has aria-label when title is provided', () => {
      render(
        <ResponsiveChart title="Test Chart">
          {() => <div>Chart</div>}
        </ResponsiveChart>
      );

      const figure = screen.getByRole('figure');
      expect(figure).toHaveAttribute('aria-label', 'Test Chart');
    });
  });

  describe('custom styling', () => {
    it('applies custom className', () => {
      render(
        <ResponsiveChart className="custom-chart-class">
          {() => <div>Chart</div>}
        </ResponsiveChart>
      );

      const container = screen.getByTestId('responsive-chart');
      expect(container).toHaveClass('custom-chart-class');
    });
  });
});

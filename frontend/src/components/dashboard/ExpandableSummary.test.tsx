import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { ExpandableSummary } from './ExpandableSummary';

import type { Summary } from '@/types/summary';

// Mock date-fns to have consistent time formatting
vi.mock('date-fns', async () => {
  const actual = await vi.importActual('date-fns');
  return {
    ...actual,
    formatDistanceToNow: vi.fn(() => '5 minutes ago'),
    format: vi.fn((_date: Date, formatStr: string) => {
      if (formatStr === 'MMM d, h:mm a') return 'Jan 18, 2:00 PM';
      if (formatStr === 'h:mm a') return '3:00 PM';
      return 'formatted';
    }),
    parseISO: (actual as typeof import('date-fns')).parseISO,
  };
});

// Mock ResizeObserver
class MockResizeObserver {
  callback: ResizeObserverCallback;

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback;
  }

  observe(target: Element) {
    // Simulate initial observation with a height
    this.callback(
      [
        {
          target,
          contentRect: { height: 200 } as DOMRectReadOnly,
          borderBoxSize: [],
          contentBoxSize: [],
          devicePixelContentBoxSize: [],
        },
      ],
      this
    );
  }

  unobserve() {}
  disconnect() {}
}

describe('ExpandableSummary', () => {
  // Base time for consistent testing
  const BASE_TIME = new Date('2026-01-18T15:00:00Z').getTime();

  // Sample summary with short content (no expand button needed)
  const shortSummary: Summary = {
    id: 1,
    content: 'All quiet today.',
    eventCount: 0,
    windowStart: '2026-01-18T14:00:00Z',
    windowEnd: '2026-01-18T15:00:00Z',
    generatedAt: '2026-01-18T14:55:00Z',
  };

  // Sample summary with long prose content
  const longProseSummary: Summary = {
    id: 2,
    content:
      'Multiple security events were detected throughout the day. A suspicious vehicle was observed near the front entrance at 2:15 PM. Package delivery occurred at the back door at 3:30 PM. Motion sensors detected activity in the backyard around 4:00 PM, which was later identified as a neighborhood cat.',
    eventCount: 3,
    windowStart: '2026-01-18T14:00:00Z',
    windowEnd: '2026-01-18T15:00:00Z',
    generatedAt: '2026-01-18T14:55:00Z',
    maxRiskScore: 65,
  };

  // Sample summary with bullet points
  const bulletSummary: Summary = {
    id: 3,
    content: `Summary of events:
- Front door motion detected at 2:15 PM
- Package delivery confirmed at 3:30 PM
- Backyard activity from wildlife at 4:00 PM
- Garage door opened and closed at 5:45 PM`,
    eventCount: 4,
    windowStart: '2026-01-18T14:00:00Z',
    windowEnd: '2026-01-18T15:00:00Z',
    generatedAt: '2026-01-18T14:55:00Z',
    maxRiskScore: 45,
  };

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);

    // Mock ResizeObserver
    globalThis.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;

    // Mock matchMedia for reduced motion
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
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

    // Clear sessionStorage
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
    sessionStorage.clear();
  });

  describe('rendering', () => {
    it('renders with short content without toggle button', () => {
      render(<ExpandableSummary summary={shortSummary} />);

      expect(screen.getByTestId('expandable-summary')).toBeInTheDocument();
      expect(screen.queryByTestId('expandable-summary-toggle')).not.toBeInTheDocument();
    });

    it('renders with long content with toggle button', () => {
      render(<ExpandableSummary summary={longProseSummary} />);

      expect(screen.getByTestId('expandable-summary')).toBeInTheDocument();
      expect(screen.getByTestId('expandable-summary-toggle')).toBeInTheDocument();
    });

    it('renders bullet summary with toggle button', () => {
      render(<ExpandableSummary summary={bulletSummary} />);

      expect(screen.getByTestId('expandable-summary-toggle')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<ExpandableSummary summary={longProseSummary} className="custom-class" />);

      const container = screen.getByTestId('expandable-summary');
      expect(container).toHaveClass('custom-class');
    });
  });

  describe('collapsed state', () => {
    it('shows truncated prose in collapsed state', () => {
      render(<ExpandableSummary summary={longProseSummary} />);

      const preview = screen.getByTestId('expandable-summary-preview');
      expect(preview).toBeInTheDocument();
      expect(preview.textContent).toContain('...');
    });

    it('shows first two bullet points with count in collapsed state', () => {
      render(<ExpandableSummary summary={bulletSummary} />);

      const preview = screen.getByTestId('expandable-summary-preview');
      expect(preview).toBeInTheDocument();

      // Should show first 2 bullets
      expect(preview).toHaveTextContent('Front door motion detected');
      expect(preview).toHaveTextContent('Package delivery confirmed');
      // Should indicate more items
      expect(preview).toHaveTextContent('and 2 more');
    });

    it('shows "View Full Summary" button when collapsed', () => {
      render(<ExpandableSummary summary={longProseSummary} />);

      const button = screen.getByTestId('expandable-summary-toggle');
      expect(button).toHaveTextContent('View Full Summary');
      expect(screen.getByTestId('chevron-down-icon')).toBeInTheDocument();
    });

    it('has data-expanded="false" when collapsed', () => {
      render(<ExpandableSummary summary={longProseSummary} />);

      const container = screen.getByTestId('expandable-summary');
      expect(container).toHaveAttribute('data-expanded', 'false');
    });
  });

  describe('expanded state', () => {
    it('shows full content when expanded', async () => {
      render(<ExpandableSummary summary={longProseSummary} defaultExpanded />);

      // Wait for expansion
      await waitFor(() => {
        expect(screen.getByTestId('expandable-summary-expanded')).toBeInTheDocument();
      });

      const expanded = screen.getByTestId('expandable-summary-expanded');
      expect(expanded).toHaveTextContent('Multiple security events');
      expect(expanded).toHaveTextContent('neighborhood cat');
    });

    it('shows all bullet points when expanded', async () => {
      render(<ExpandableSummary summary={bulletSummary} defaultExpanded />);

      await waitFor(() => {
        expect(screen.getByTestId('expandable-summary-expanded')).toBeInTheDocument();
      });

      const expanded = screen.getByTestId('expandable-summary-expanded');
      expect(expanded).toHaveTextContent('Front door motion detected');
      expect(expanded).toHaveTextContent('Package delivery confirmed');
      expect(expanded).toHaveTextContent('Backyard activity');
      expect(expanded).toHaveTextContent('Garage door opened');
    });

    it('shows metadata when expanded', async () => {
      render(<ExpandableSummary summary={longProseSummary} defaultExpanded />);

      await waitFor(() => {
        expect(screen.getByTestId('expandable-summary-metadata')).toBeInTheDocument();
      });

      const metadata = screen.getByTestId('expandable-summary-metadata');
      expect(metadata).toHaveTextContent('Time window');
      expect(metadata).toHaveTextContent('Generated');
      expect(metadata).toHaveTextContent('3 events');
      expect(metadata).toHaveTextContent('Max risk: 65');
    });

    it('shows "Hide Details" button when expanded', async () => {
      render(<ExpandableSummary summary={longProseSummary} defaultExpanded />);

      await waitFor(() => {
        const button = screen.getByTestId('expandable-summary-toggle');
        expect(button).toHaveTextContent('Hide Details');
      });

      expect(screen.getByTestId('chevron-up-icon')).toBeInTheDocument();
    });

    it('has data-expanded="true" when expanded', async () => {
      render(<ExpandableSummary summary={longProseSummary} defaultExpanded />);

      await waitFor(() => {
        const container = screen.getByTestId('expandable-summary');
        expect(container).toHaveAttribute('data-expanded', 'true');
      });
    });
  });

  describe('toggle interaction', () => {
    it('expands when toggle button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<ExpandableSummary summary={longProseSummary} />);

      const button = screen.getByTestId('expandable-summary-toggle');
      await user.click(button);

      await waitFor(() => {
        expect(screen.getByTestId('expandable-summary')).toHaveAttribute('data-expanded', 'true');
      });
    });

    it('collapses when toggle button is clicked while expanded', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<ExpandableSummary summary={longProseSummary} defaultExpanded />);

      const button = screen.getByTestId('expandable-summary-toggle');
      await user.click(button);

      await waitFor(() => {
        expect(screen.getByTestId('expandable-summary')).toHaveAttribute('data-expanded', 'false');
      });
    });

    it('calls onExpandChange callback when toggled', async () => {
      const onExpandChange = vi.fn();
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<ExpandableSummary summary={longProseSummary} onExpandChange={onExpandChange} />);

      const button = screen.getByTestId('expandable-summary-toggle');
      await user.click(button);

      await waitFor(() => {
        expect(onExpandChange).toHaveBeenCalledWith(true);
      });

      await user.click(button);

      await waitFor(() => {
        expect(onExpandChange).toHaveBeenCalledWith(false);
      });
    });
  });

  describe('keyboard accessibility', () => {
    it('toggles with Enter key', async () => {
      render(<ExpandableSummary summary={longProseSummary} />);

      const button = screen.getByTestId('expandable-summary-toggle');
      button.focus();

      fireEvent.keyDown(button, { key: 'Enter' });

      await waitFor(() => {
        expect(screen.getByTestId('expandable-summary')).toHaveAttribute('data-expanded', 'true');
      });
    });

    it('toggles with Space key', async () => {
      render(<ExpandableSummary summary={longProseSummary} />);

      const button = screen.getByTestId('expandable-summary-toggle');
      button.focus();

      fireEvent.keyDown(button, { key: ' ' });

      await waitFor(() => {
        expect(screen.getByTestId('expandable-summary')).toHaveAttribute('data-expanded', 'true');
      });
    });
  });

  describe('ARIA attributes', () => {
    it('has aria-expanded on toggle button', () => {
      render(<ExpandableSummary summary={longProseSummary} />);

      const button = screen.getByTestId('expandable-summary-toggle');
      expect(button).toHaveAttribute('aria-expanded', 'false');
    });

    it('updates aria-expanded when toggled', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<ExpandableSummary summary={longProseSummary} />);

      const button = screen.getByTestId('expandable-summary-toggle');
      expect(button).toHaveAttribute('aria-expanded', 'false');

      await user.click(button);

      await waitFor(() => {
        expect(button).toHaveAttribute('aria-expanded', 'true');
      });
    });

    it('has aria-controls pointing to content', () => {
      render(<ExpandableSummary summary={longProseSummary} defaultExpanded />);

      const button = screen.getByTestId('expandable-summary-toggle');
      const ariaControls = button.getAttribute('aria-controls');

      expect(ariaControls).toBeTruthy();
      // The expanded content should have this ID
      const expandedContent = document.getElementById(ariaControls!);
      expect(expandedContent).toBeInTheDocument();
    });

    it('has aria-hidden on collapsed content', () => {
      render(<ExpandableSummary summary={longProseSummary} />);

      // Find the expandable wrapper that has aria-hidden
      const expandableWrapper = screen
        .getByTestId('expandable-summary')
        .querySelector('[aria-hidden]');
      expect(expandableWrapper).toHaveAttribute('aria-hidden', 'true');
    });

    it('removes aria-hidden when expanded', async () => {
      render(<ExpandableSummary summary={longProseSummary} defaultExpanded />);

      await waitFor(() => {
        const expandableWrapper = screen
          .getByTestId('expandable-summary')
          .querySelector('[aria-hidden]');
        expect(expandableWrapper).toHaveAttribute('aria-hidden', 'false');
      });
    });

    it('icons have aria-hidden', () => {
      render(<ExpandableSummary summary={longProseSummary} />);

      const icon = screen.getByTestId('chevron-down-icon');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  describe('visual styling', () => {
    it('uses NVIDIA green color for toggle button', () => {
      render(<ExpandableSummary summary={longProseSummary} />);

      const button = screen.getByTestId('expandable-summary-toggle');
      expect(button).toHaveStyle({ color: 'rgb(118, 185, 0)' });
    });

    it('has focus-visible styles on button', () => {
      render(<ExpandableSummary summary={longProseSummary} />);

      const button = screen.getByTestId('expandable-summary-toggle');
      expect(button).toHaveClass('focus-visible:ring-2');
      expect(button).toHaveClass('focus-visible:ring-offset-2');
    });

    it('expanded content has bg-gray-800/50 background', async () => {
      render(<ExpandableSummary summary={longProseSummary} defaultExpanded />);

      await waitFor(() => {
        const expanded = screen.getByTestId('expandable-summary-expanded');
        expect(expanded).toHaveClass('bg-gray-800/50');
      });
    });
  });

  describe('animation', () => {
    it('has transition on expanded content wrapper', () => {
      render(<ExpandableSummary summary={longProseSummary} />);

      const wrapper = screen
        .getByTestId('expandable-summary')
        .querySelector('[class*="overflow-hidden"]');
      expect(wrapper).toHaveStyle({ transition: 'height 300ms ease-in-out' });
    });

    it('respects prefers-reduced-motion', () => {
      // Mock reduced motion preference
      Object.defineProperty(window, 'matchMedia', {
        writable: true,
        value: vi.fn().mockImplementation((query: string) => ({
          matches: query === '(prefers-reduced-motion: reduce)',
          media: query,
          onchange: null,
          addListener: vi.fn(),
          removeListener: vi.fn(),
          addEventListener: vi.fn(),
          removeEventListener: vi.fn(),
          dispatchEvent: vi.fn(),
        })),
      });

      render(<ExpandableSummary summary={longProseSummary} />);

      const wrapper = screen
        .getByTestId('expandable-summary')
        .querySelector('[class*="overflow-hidden"]');
      expect(wrapper).toHaveStyle({ transition: 'height 0ms ease-in-out' });
    });
  });

  describe('sessionStorage persistence', () => {
    it('persists expansion state to sessionStorage', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<ExpandableSummary summary={longProseSummary} summaryType="hourly" />);

      const button = screen.getByTestId('expandable-summary-toggle');
      await user.click(button);

      await waitFor(() => {
        const stored = sessionStorage.getItem('summary-expansion-hourly-2');
        expect(stored).toBe('true');
      });
    });

    it('restores expansion state from sessionStorage', () => {
      // Pre-set the storage value
      sessionStorage.setItem('summary-expansion-hourly-2', 'true');

      render(<ExpandableSummary summary={longProseSummary} summaryType="hourly" />);

      const container = screen.getByTestId('expandable-summary');
      expect(container).toHaveAttribute('data-expanded', 'true');
    });

    it('uses different keys for different summary types', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      const { rerender } = render(
        <ExpandableSummary summary={longProseSummary} summaryType="hourly" />
      );

      const button = screen.getByTestId('expandable-summary-toggle');
      await user.click(button);

      await waitFor(() => {
        expect(sessionStorage.getItem('summary-expansion-hourly-2')).toBe('true');
      });

      // Rerender with different type
      rerender(<ExpandableSummary summary={longProseSummary} summaryType="daily" />);

      // Should be collapsed (different key)
      expect(screen.getByTestId('expandable-summary')).toHaveAttribute('data-expanded', 'false');
    });
  });

  describe('metadata display', () => {
    it('shows singular "event" for count of 1', async () => {
      const singleEventSummary: Summary = {
        ...longProseSummary,
        eventCount: 1,
      };

      render(<ExpandableSummary summary={singleEventSummary} defaultExpanded />);

      await waitFor(() => {
        const metadata = screen.getByTestId('expandable-summary-metadata');
        expect(metadata).toHaveTextContent('1 event');
        expect(metadata).not.toHaveTextContent('1 events');
      });
    });

    it('shows plural "events" for count > 1', async () => {
      render(<ExpandableSummary summary={longProseSummary} defaultExpanded />);

      await waitFor(() => {
        const metadata = screen.getByTestId('expandable-summary-metadata');
        expect(metadata).toHaveTextContent('3 events');
      });
    });

    it('hides event count when 0', async () => {
      const noEventSummary: Summary = {
        ...longProseSummary,
        eventCount: 0,
      };

      render(<ExpandableSummary summary={noEventSummary} defaultExpanded />);

      await waitFor(() => {
        const metadata = screen.getByTestId('expandable-summary-metadata');
        expect(metadata).not.toHaveTextContent('event');
      });
    });

    it('hides max risk when undefined', async () => {
      const noRiskSummary: Summary = {
        ...longProseSummary,
        maxRiskScore: undefined,
      };

      render(<ExpandableSummary summary={noRiskSummary} defaultExpanded />);

      await waitFor(() => {
        const metadata = screen.getByTestId('expandable-summary-metadata');
        expect(metadata).not.toHaveTextContent('Max risk');
      });
    });
  });

  describe('edge cases', () => {
    it('handles summary with numbered bullet points', () => {
      const numberedSummary: Summary = {
        id: 4,
        content: `Events in order:
1. First event at 2:00 PM
2) Second event at 3:00 PM
3. Third event at 4:00 PM`,
        eventCount: 3,
        windowStart: '2026-01-18T14:00:00Z',
        windowEnd: '2026-01-18T15:00:00Z',
        generatedAt: '2026-01-18T14:55:00Z',
      };

      render(<ExpandableSummary summary={numberedSummary} />);

      const preview = screen.getByTestId('expandable-summary-preview');
      expect(preview).toHaveTextContent('First event');
      expect(preview).toHaveTextContent('Second event');
      expect(preview).toHaveTextContent('and 1 more');
    });

    it('handles summary with exactly 150 characters', () => {
      const exactSummary: Summary = {
        id: 5,
        content: 'A'.repeat(150),
        eventCount: 1,
        windowStart: '2026-01-18T14:00:00Z',
        windowEnd: '2026-01-18T15:00:00Z',
        generatedAt: '2026-01-18T14:55:00Z',
      };

      render(<ExpandableSummary summary={exactSummary} />);

      // Should not have toggle button for exactly 150 chars
      expect(screen.queryByTestId('expandable-summary-toggle')).not.toBeInTheDocument();
    });

    it('handles summary with 151 characters', () => {
      const slightlyLongSummary: Summary = {
        id: 6,
        content: 'A'.repeat(151),
        eventCount: 1,
        windowStart: '2026-01-18T14:00:00Z',
        windowEnd: '2026-01-18T15:00:00Z',
        generatedAt: '2026-01-18T14:55:00Z',
      };

      render(<ExpandableSummary summary={slightlyLongSummary} />);

      // Should have toggle button for > 150 chars
      expect(screen.getByTestId('expandable-summary-toggle')).toBeInTheDocument();
    });
  });
});

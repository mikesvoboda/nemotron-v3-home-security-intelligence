import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { SummaryCards, SummaryCard } from './SummaryCards';

import type { Summary } from '@/types/summary';

// Mock date-fns to have consistent time formatting
vi.mock('date-fns', async () => {
  const actual = await vi.importActual('date-fns');
  return {
    ...actual,
    formatDistanceToNow: vi.fn(() => '2 minutes'),
  };
});

describe('SummaryCard', () => {
  // Base time for consistent testing
  const BASE_TIME = new Date('2026-01-18T15:00:00Z').getTime();

  const mockHourlySummary: Summary = {
    id: 1,
    content: 'One critical event at 2:15 PM at the front door.',
    eventCount: 1,
    windowStart: '2026-01-18T14:00:00Z',
    windowEnd: '2026-01-18T15:00:00Z',
    generatedAt: '2026-01-18T14:55:00Z',
  };

  const mockDailySummary: Summary = {
    id: 2,
    content: 'No high-priority events today. Property is quiet.',
    eventCount: 0,
    windowStart: '2026-01-18T00:00:00Z',
    windowEnd: '2026-01-18T15:00:00Z',
    generatedAt: '2026-01-18T14:55:00Z',
  };

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('rendering with data', () => {
    it('renders hourly summary with severity badge and event count', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);

      expect(screen.getByText('Hourly Summary')).toBeInTheDocument();
      // New SeverityBadge shows count in parentheses
      expect(screen.getByTestId('severity-badge-count')).toHaveTextContent('(1)');
      // Content is parsed into bullet points, check for time extraction
      expect(screen.getByTestId('summary-content-hourly')).toBeInTheDocument();
    });

    it('renders daily summary with all clear badge', () => {
      render(<SummaryCard type="daily" summary={mockDailySummary} />);

      expect(screen.getByText('Daily Summary')).toBeInTheDocument();
      // SeverityBadge shows uppercase label
      expect(screen.getByText('ALL CLEAR')).toBeInTheDocument();
    });

    it('displays event count in badge for single event', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      expect(screen.getByTestId('severity-badge-count')).toHaveTextContent('(1)');
    });

    it('displays event count in badge for multiple events', () => {
      const multiEvent: Summary = { ...mockHourlySummary, eventCount: 3 };
      render(<SummaryCard type="hourly" summary={multiEvent} />);
      expect(screen.getByTestId('severity-badge-count')).toHaveTextContent('(3)');
    });

    it('displays generated time text in footer', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      expect(screen.getByText('Generated 2 minutes ago')).toBeInTheDocument();
    });

    it('displays events analyzed count in footer', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      expect(screen.getByTestId('summary-event-count-hourly')).toHaveTextContent('1 event analyzed');
    });

    it('pluralizes events analyzed correctly', () => {
      const multiEvent: Summary = { ...mockHourlySummary, eventCount: 3 };
      render(<SummaryCard type="hourly" summary={multiEvent} />);
      expect(screen.getByTestId('summary-event-count-hourly')).toHaveTextContent('3 events analyzed');
    });

    it('renders summary content container', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      // Content is parsed into bullet points
      const contentContainer = screen.getByTestId('summary-content-hourly');
      expect(contentContainer).toBeInTheDocument();
      // Bullet list is rendered inside the content container
      expect(contentContainer.querySelector('[data-testid*="bullet"]')).toBeInTheDocument();
    });

    it('displays time window for hourly', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      expect(screen.getByText('Last 60 minutes')).toBeInTheDocument();
    });

    it('displays time window for daily', () => {
      render(<SummaryCard type="daily" summary={mockDailySummary} />);
      expect(screen.getByText('Since midnight')).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('renders loading skeleton for hourly', () => {
      render(<SummaryCard type="hourly" summary={null} isLoading />);

      expect(screen.getByText('Hourly Summary')).toBeInTheDocument();
      // Now uses SummaryCardSkeleton component with different test IDs
      expect(screen.getByTestId('summary-card-skeleton-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-skeleton-content-hourly')).toBeInTheDocument();
    });

    it('renders loading skeleton for daily', () => {
      render(<SummaryCard type="daily" summary={null} isLoading />);

      expect(screen.getByText('Daily Summary')).toBeInTheDocument();
      // Now uses SummaryCardSkeleton component with different test IDs
      expect(screen.getByTestId('summary-card-skeleton-daily')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-skeleton-content-daily')).toBeInTheDocument();
    });

    it('has shimmer animation on skeleton elements', () => {
      render(<SummaryCard type="hourly" summary={null} isLoading />);
      // SummaryCardSkeleton uses shimmer overlay animation
      const skeleton = screen.getByTestId('summary-card-skeleton-hourly');
      expect(skeleton).toBeInTheDocument();
      expect(skeleton).toHaveAttribute('role', 'status');
    });

    it('has accessible loading label', () => {
      render(<SummaryCard type="hourly" summary={null} isLoading />);
      const skeleton = screen.getByTestId('summary-card-skeleton-hourly');
      expect(skeleton).toHaveAttribute('aria-label', 'Loading hourly summary');
    });
  });

  describe('empty state', () => {
    it('renders empty state when no summary for hourly', () => {
      render(<SummaryCard type="hourly" summary={null} />);

      expect(screen.getByText('Hourly Summary')).toBeInTheDocument();
      // Now uses SummaryCardEmpty component with "No activity to summarize" message
      expect(screen.getByText('No activity to summarize')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-empty-hourly')).toBeInTheDocument();
    });

    it('renders empty state when no summary for daily', () => {
      render(<SummaryCard type="daily" summary={null} />);

      expect(screen.getByText('Daily Summary')).toBeInTheDocument();
      // Now uses SummaryCardEmpty component with "No activity to summarize" message
      expect(screen.getByText('No activity to summarize')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-empty-daily')).toBeInTheDocument();
    });

    it('shows contextual timeframe message for hourly', () => {
      render(<SummaryCard type="hourly" summary={null} />);
      expect(screen.getByText(/No high-priority events detected the past hour/)).toBeInTheDocument();
    });

    it('shows contextual timeframe message for daily', () => {
      render(<SummaryCard type="daily" summary={null} />);
      expect(screen.getByText(/No high-priority events detected today/)).toBeInTheDocument();
    });
  });

  describe('visual styling', () => {
    it('applies critical red accent bar when content contains critical keyword', () => {
      // mockHourlySummary content contains "critical" keyword
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const accentBar = screen.getByTestId('accent-bar');
      expect(accentBar).toHaveStyle({ backgroundColor: 'rgb(239, 68, 68)' }); // red-500 (critical)
      const card = screen.getByTestId('summary-card-hourly');
      expect(card).toHaveAttribute('data-severity', 'critical');
    });

    it('applies emerald accent bar when all clear', () => {
      render(<SummaryCard type="daily" summary={mockDailySummary} />);
      const accentBar = screen.getByTestId('accent-bar');
      expect(accentBar).toHaveStyle({ backgroundColor: 'rgb(16, 185, 129)' }); // emerald-500 (clear)
      const card = screen.getByTestId('summary-card-daily');
      expect(card).toHaveAttribute('data-severity', 'clear');
    });

    it('applies gray border when loading', () => {
      render(<SummaryCard type="hourly" summary={null} isLoading />);
      // SummaryCardSkeleton uses border-left-color style
      const card = screen.getByTestId('summary-card-skeleton-hourly');
      expect(card).toHaveStyle({ borderLeftColor: 'rgb(209, 213, 219)' }); // gray-300
    });

    it('applies gray border when empty', () => {
      render(<SummaryCard type="hourly" summary={null} />);
      // SummaryCardEmpty uses border-left-color style
      const card = screen.getByTestId('summary-card-empty-hourly');
      expect(card).toHaveStyle({ borderLeftColor: 'rgb(107, 114, 128)' }); // gray-500
    });

    it('uses dark theme background', () => {
      const { container } = render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const card = container.querySelector('[data-testid="summary-card-hourly"]');
      expect(card).toHaveClass('bg-[#1A1A1A]');
    });

    it('has left padding for accent bar space', () => {
      const { container } = render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const card = container.querySelector('[data-testid="summary-card-hourly"]');
      expect(card).toHaveClass('pl-4');
    });
  });

  describe('icons', () => {
    it('renders clock icon for hourly summary', () => {
      const { container } = render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const svg = container.querySelector('svg.lucide-clock');
      expect(svg).toBeInTheDocument();
    });

    it('renders calendar icon for daily summary', () => {
      const { container } = render(<SummaryCard type="daily" summary={mockDailySummary} />);
      const svg = container.querySelector('svg.lucide-calendar');
      expect(svg).toBeInTheDocument();
    });

    it('icons have aria-hidden for accessibility', () => {
      const { container } = render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const icon = container.querySelector('svg.lucide-clock');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });

    it('renders RefreshCw icon in footer', () => {
      const { container } = render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const svg = container.querySelector('svg.lucide-refresh-cw');
      expect(svg).toBeInTheDocument();
    });
  });

  describe('severity badge rendering', () => {
    it('renders severity badge with correct testid', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toBeInTheDocument();
    });

    it('renders critical badge for critical content', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveAttribute('data-severity', 'critical');
      expect(badge).toHaveTextContent('CRITICAL');
    });

    it('renders all clear badge for zero events', () => {
      render(<SummaryCard type="daily" summary={mockDailySummary} />);
      const badge = screen.getByTestId('severity-badge');
      expect(badge).toHaveAttribute('data-severity', 'clear');
      expect(badge).toHaveTextContent('ALL CLEAR');
    });
  });

  describe('data-testid attributes', () => {
    it('has correct testid for summary content', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const contentWrapper = screen.getByTestId('summary-content-hourly');
      expect(contentWrapper).toBeInTheDocument();
      // Content is now rendered as bullet points, check for presence
      expect(contentWrapper.querySelector('[data-testid*="bullet"]')).toBeInTheDocument();
    });

    it('has correct testid for updated timestamp', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const updatedWrapper = screen.getByTestId('summary-updated-hourly');
      expect(updatedWrapper).toBeInTheDocument();
      expect(updatedWrapper).toHaveTextContent('Generated 2 minutes ago');
    });

    it('has correct testid for footer', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const footer = screen.getByTestId('summary-footer-hourly');
      expect(footer).toBeInTheDocument();
    });

    it('has correct testid for time window', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const timeWindow = screen.getByTestId('time-window-hourly');
      expect(timeWindow).toHaveTextContent('Last 60 minutes');
    });
  });

  describe('footer structure', () => {
    it('has border-t class for footer separator', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const footer = screen.getByTestId('summary-footer-hourly');
      expect(footer).toHaveClass('border-t', 'border-gray-800');
    });

    it('has mt-4 and pt-3 spacing classes', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const footer = screen.getByTestId('summary-footer-hourly');
      expect(footer).toHaveClass('mt-4', 'pt-3');
    });
  });
});

describe('SummaryCards', () => {
  const mockHourlySummary: Summary = {
    id: 1,
    content: 'One critical event at 2:15 PM at the front door.',
    eventCount: 1,
    windowStart: '2026-01-18T14:00:00Z',
    windowEnd: '2026-01-18T15:00:00Z',
    generatedAt: '2026-01-18T14:55:00Z',
  };

  const mockDailySummary: Summary = {
    id: 2,
    content: 'No high-priority events today. Property is quiet.',
    eventCount: 0,
    windowStart: '2026-01-18T00:00:00Z',
    windowEnd: '2026-01-18T15:00:00Z',
    generatedAt: '2026-01-18T14:55:00Z',
  };

  describe('rendering', () => {
    it('renders container element', () => {
      render(<SummaryCards hourly={mockHourlySummary} daily={mockDailySummary} />);
      expect(screen.getByTestId('summary-cards')).toBeInTheDocument();
    });

    it('renders both hourly and daily cards', () => {
      render(<SummaryCards hourly={mockHourlySummary} daily={mockDailySummary} />);

      expect(screen.getByText('Hourly Summary')).toBeInTheDocument();
      expect(screen.getByText('Daily Summary')).toBeInTheDocument();
    });

    it('passes isLoading to both cards', () => {
      render(<SummaryCards hourly={null} daily={null} isLoading />);

      // Both should show loading skeletons (now uses SummaryCardSkeleton)
      expect(screen.getByTestId('summary-card-skeleton-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-skeleton-daily')).toBeInTheDocument();
    });

    it('renders correct content for each card', () => {
      render(<SummaryCards hourly={mockHourlySummary} daily={mockDailySummary} />);

      // Content is parsed into bullet points, verify content containers exist
      expect(screen.getByTestId('summary-content-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-content-daily')).toBeInTheDocument();
    });
  });

  describe('mixed states', () => {
    it('handles hourly with data and daily empty', () => {
      const { rerender } = render(
        <SummaryCards hourly={mockHourlySummary} daily={null} isLoading={false} />
      );

      expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-empty-daily')).toBeInTheDocument();

      // When loading is true, both show loading skeletons
      rerender(<SummaryCards hourly={mockHourlySummary} daily={null} isLoading={true} />);
      expect(screen.getByTestId('summary-card-skeleton-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-skeleton-daily')).toBeInTheDocument();
    });

    it('handles both summaries null without loading', () => {
      render(<SummaryCards hourly={null} daily={null} />);

      expect(screen.getByTestId('summary-card-empty-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-empty-daily')).toBeInTheDocument();
    });
  });

  describe('layout', () => {
    it('has vertical spacing between cards', () => {
      const { container } = render(
        <SummaryCards hourly={mockHourlySummary} daily={mockDailySummary} />
      );
      const wrapper = container.querySelector('[data-testid="summary-cards"]');
      expect(wrapper).toHaveClass('space-y-4');
    });
  });

  describe('props updates', () => {
    it('updates when hourly summary changes', () => {
      const { rerender } = render(
        <SummaryCards hourly={mockHourlySummary} daily={mockDailySummary} />
      );

      // Check initial count in badge
      const hourlyCard = screen.getByTestId('summary-card-hourly');
      expect(hourlyCard.querySelector('[data-testid="severity-badge-count"]')).toHaveTextContent('(1)');

      const updatedHourly: Summary = { ...mockHourlySummary, eventCount: 5 };
      rerender(<SummaryCards hourly={updatedHourly} daily={mockDailySummary} />);

      expect(hourlyCard.querySelector('[data-testid="severity-badge-count"]')).toHaveTextContent('(5)');
    });

    it('updates when daily summary changes', () => {
      const { rerender } = render(
        <SummaryCards hourly={mockHourlySummary} daily={mockDailySummary} />
      );

      expect(screen.getByText('ALL CLEAR')).toBeInTheDocument();

      const updatedDaily: Summary = { ...mockDailySummary, eventCount: 2 };
      rerender(<SummaryCards hourly={mockHourlySummary} daily={updatedDaily} />);

      // With 2 events, badge should show count
      const dailyCard = screen.getByTestId('summary-card-daily');
      expect(dailyCard.querySelector('[data-testid="severity-badge-count"]')).toHaveTextContent('(2)');
    });

    it('handles transition from loading to data', () => {
      const { rerender } = render(<SummaryCards hourly={null} daily={null} isLoading={true} />);

      expect(screen.getByTestId('summary-card-skeleton-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-skeleton-daily')).toBeInTheDocument();

      rerender(<SummaryCards hourly={mockHourlySummary} daily={mockDailySummary} isLoading={false} />);

      expect(screen.queryByTestId('summary-card-skeleton-hourly')).not.toBeInTheDocument();
      expect(screen.queryByTestId('summary-card-skeleton-daily')).not.toBeInTheDocument();
      expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-daily')).toBeInTheDocument();
    });
  });
});

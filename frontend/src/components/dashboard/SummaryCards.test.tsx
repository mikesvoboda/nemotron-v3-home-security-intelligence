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
    it('renders hourly summary with event count', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);

      expect(screen.getByText('Hourly Summary')).toBeInTheDocument();
      expect(screen.getByText('1 event')).toBeInTheDocument();
      expect(screen.getByText(/critical event at 2:15 PM/)).toBeInTheDocument();
    });

    it('renders daily summary with all clear badge', () => {
      render(<SummaryCard type="daily" summary={mockDailySummary} />);

      expect(screen.getByText('Daily Summary')).toBeInTheDocument();
      expect(screen.getByText('All clear')).toBeInTheDocument();
    });

    it('pluralizes event count correctly for single event', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      expect(screen.getByText('1 event')).toBeInTheDocument();
    });

    it('pluralizes event count correctly for multiple events', () => {
      const multiEvent: Summary = { ...mockHourlySummary, eventCount: 3 };
      render(<SummaryCard type="hourly" summary={multiEvent} />);
      expect(screen.getByText('3 events')).toBeInTheDocument();
    });

    it('displays updated time text', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      expect(screen.getByText('Updated 2 minutes ago')).toBeInTheDocument();
    });

    it('renders summary content', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      expect(
        screen.getByText('One critical event at 2:15 PM at the front door.')
      ).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('renders loading skeleton for hourly', () => {
      render(<SummaryCard type="hourly" summary={null} isLoading />);

      expect(screen.getByText('Hourly Summary')).toBeInTheDocument();
      expect(screen.getByTestId('loading-skeleton')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-hourly-loading')).toBeInTheDocument();
    });

    it('renders loading skeleton for daily', () => {
      render(<SummaryCard type="daily" summary={null} isLoading />);

      expect(screen.getByText('Daily Summary')).toBeInTheDocument();
      expect(screen.getByTestId('loading-skeleton')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-daily-loading')).toBeInTheDocument();
    });

    it('has animate-pulse class on skeleton', () => {
      render(<SummaryCard type="hourly" summary={null} isLoading />);
      const skeleton = screen.getByTestId('loading-skeleton');
      expect(skeleton).toHaveClass('animate-pulse');
    });
  });

  describe('empty state', () => {
    it('renders empty state when no summary for hourly', () => {
      render(<SummaryCard type="hourly" summary={null} />);

      expect(screen.getByText('Hourly Summary')).toBeInTheDocument();
      expect(screen.getByText(/No summary available/)).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-hourly-empty')).toBeInTheDocument();
    });

    it('renders empty state when no summary for daily', () => {
      render(<SummaryCard type="daily" summary={null} />);

      expect(screen.getByText('Daily Summary')).toBeInTheDocument();
      expect(screen.getByText(/No summary available/)).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-daily-empty')).toBeInTheDocument();
    });

    it('shows generation frequency message', () => {
      render(<SummaryCard type="hourly" summary={null} />);
      expect(screen.getByText(/Summaries are generated every 5 minutes/)).toBeInTheDocument();
    });
  });

  describe('visual styling', () => {
    it('applies amber border when has events', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const card = screen.getByTestId('summary-card-hourly');
      expect(card).toHaveStyle({ borderLeftColor: 'rgb(245, 158, 11)' }); // amber-500
      expect(card).toHaveAttribute('data-has-events', 'true');
    });

    it('applies emerald border when all clear', () => {
      render(<SummaryCard type="daily" summary={mockDailySummary} />);
      const card = screen.getByTestId('summary-card-daily');
      expect(card).toHaveStyle({ borderLeftColor: 'rgb(16, 185, 129)' }); // emerald-500
      expect(card).toHaveAttribute('data-has-events', 'false');
    });

    it('applies gray border when loading', () => {
      render(<SummaryCard type="hourly" summary={null} isLoading />);
      const card = screen.getByTestId('summary-card-hourly-loading');
      expect(card).toHaveStyle({ borderLeftColor: 'rgb(209, 213, 219)' }); // gray-300
    });

    it('applies gray border when empty', () => {
      render(<SummaryCard type="hourly" summary={null} />);
      const card = screen.getByTestId('summary-card-hourly-empty');
      expect(card).toHaveStyle({ borderLeftColor: 'rgb(107, 114, 128)' }); // gray-500
    });

    it('uses dark theme background', () => {
      const { container } = render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const card = container.querySelector('[data-testid="summary-card-hourly"]');
      expect(card).toHaveClass('bg-[#1A1A1A]');
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
  });

  describe('badge rendering', () => {
    it('renders amber badge for events', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const badge = screen.getByTestId('summary-badge-hourly');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent('1 event');
    });

    it('renders emerald badge for all clear', () => {
      render(<SummaryCard type="daily" summary={mockDailySummary} />);
      const badge = screen.getByTestId('summary-badge-daily');
      expect(badge).toBeInTheDocument();
      expect(badge).toHaveTextContent('All clear');
    });
  });

  describe('data-testid attributes', () => {
    it('has correct testid for summary content', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const contentWrapper = screen.getByTestId('summary-content-hourly');
      expect(contentWrapper).toBeInTheDocument();
      expect(contentWrapper).toHaveTextContent('One critical event at 2:15 PM at the front door.');
    });

    it('has correct testid for updated timestamp', () => {
      render(<SummaryCard type="hourly" summary={mockHourlySummary} />);
      const updatedWrapper = screen.getByTestId('summary-updated-hourly');
      expect(updatedWrapper).toBeInTheDocument();
      expect(updatedWrapper).toHaveTextContent('Updated 2 minutes ago');
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

      // Both should show loading skeletons
      const skeletons = screen.getAllByTestId('loading-skeleton');
      expect(skeletons).toHaveLength(2);
    });

    it('renders correct content for each card', () => {
      render(<SummaryCards hourly={mockHourlySummary} daily={mockDailySummary} />);

      expect(screen.getByText(/critical event at 2:15 PM/)).toBeInTheDocument();
      expect(screen.getByText(/No high-priority events today/)).toBeInTheDocument();
    });
  });

  describe('mixed states', () => {
    it('handles hourly with data and daily loading', () => {
      const { rerender } = render(
        <SummaryCards hourly={mockHourlySummary} daily={null} isLoading={false} />
      );

      expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-daily-empty')).toBeInTheDocument();

      // When loading is true, both show loading
      rerender(<SummaryCards hourly={mockHourlySummary} daily={null} isLoading={true} />);
      expect(screen.getAllByTestId('loading-skeleton')).toHaveLength(2);
    });

    it('handles both summaries null without loading', () => {
      render(<SummaryCards hourly={null} daily={null} />);

      expect(screen.getByTestId('summary-card-hourly-empty')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-daily-empty')).toBeInTheDocument();
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

      expect(screen.getByText('1 event')).toBeInTheDocument();

      const updatedHourly: Summary = { ...mockHourlySummary, eventCount: 5 };
      rerender(<SummaryCards hourly={updatedHourly} daily={mockDailySummary} />);

      expect(screen.getByText('5 events')).toBeInTheDocument();
    });

    it('updates when daily summary changes', () => {
      const { rerender } = render(
        <SummaryCards hourly={mockHourlySummary} daily={mockDailySummary} />
      );

      expect(screen.getByText('All clear')).toBeInTheDocument();

      const updatedDaily: Summary = { ...mockDailySummary, eventCount: 2 };
      rerender(<SummaryCards hourly={mockHourlySummary} daily={updatedDaily} />);

      expect(screen.getByText('2 events')).toBeInTheDocument();
    });

    it('handles transition from loading to data', () => {
      const { rerender } = render(<SummaryCards hourly={null} daily={null} isLoading={true} />);

      expect(screen.getAllByTestId('loading-skeleton')).toHaveLength(2);

      rerender(<SummaryCards hourly={mockHourlySummary} daily={mockDailySummary} isLoading={false} />);

      expect(screen.queryByTestId('loading-skeleton')).not.toBeInTheDocument();
      expect(screen.getByTestId('summary-card-hourly')).toBeInTheDocument();
      expect(screen.getByTestId('summary-card-daily')).toBeInTheDocument();
    });
  });
});

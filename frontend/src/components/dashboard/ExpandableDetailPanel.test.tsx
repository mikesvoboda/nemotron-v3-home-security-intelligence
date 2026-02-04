/**
 * Tests for ExpandableDetailPanel component.
 *
 * The ExpandableDetailPanel displays detailed summary information when
 * a user clicks on a summary card, including:
 * - Full narrative description
 * - Timeline view of events
 * - Export options (PDF, JSON, CSV)
 * - Links to individual event details
 *
 * Related Linear issues: NEM-5425, NEM-5426, NEM-5427
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import { ExpandableDetailPanel } from './ExpandableDetailPanel';

import type { SummaryDetail, TimelineEvent } from '@/types/summary';

// Mock date-fns for consistent time formatting
vi.mock('date-fns', async () => {
  const actual = await vi.importActual('date-fns');
  return {
    ...actual,
    formatDistanceToNow: vi.fn(() => '5 minutes'),
    format: vi.fn((_date: Date, formatStr: string) => {
      if (formatStr === 'MMM d, h:mm a') return 'Jan 21, 2:00 PM';
      if (formatStr === 'h:mm a') return '3:00 PM';
      if (formatStr === 'h:mm:ss a') return '2:10:00 PM';
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
    this.callback(
      [
        {
          target,
          contentRect: { height: 400 } as DOMRectReadOnly,
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

describe('ExpandableDetailPanel', () => {
  const BASE_TIME = new Date('2026-01-21T15:00:00Z').getTime();

  // Sample timeline events
  const mockTimelineEvents: TimelineEvent[] = [
    {
      eventId: 101,
      timestamp: '2026-01-21T14:10:00Z',
      cameraName: 'Front Door',
      summary: 'Person detected approaching the front door',
      riskScore: 75,
      riskLevel: 'high',
      eventUrl: '/events/101',
    },
    {
      eventId: 102,
      timestamp: '2026-01-21T14:30:00Z',
      cameraName: 'Driveway',
      summary: 'Vehicle detected in driveway',
      riskScore: 50,
      riskLevel: 'medium',
      eventUrl: '/events/102',
    },
    {
      eventId: 103,
      timestamp: '2026-01-21T14:45:00Z',
      cameraName: 'Backyard',
      summary: 'Motion detected in backyard',
      riskScore: 30,
      riskLevel: 'low',
      eventUrl: '/events/103',
    },
  ];

  // Sample summary detail
  const mockSummaryDetail: SummaryDetail = {
    id: 1,
    summaryType: 'hourly',
    content:
      'Multiple security events were detected in the past hour. A high-risk event occurred at the Front Door when an unrecognized person approached. Vehicle activity was also observed in the Driveway, and motion was detected in the Backyard.',
    eventCount: 3,
    windowStart: '2026-01-21T14:00:00Z',
    windowEnd: '2026-01-21T15:00:00Z',
    generatedAt: '2026-01-21T14:55:00Z',
    timeline: mockTimelineEvents,
    exportFormats: ['json', 'csv', 'pdf'],
    focusAreas: ['Front Door', 'Driveway', 'Backyard'],
    maxRiskScore: 75,
  };

  // Empty summary detail (no events)
  const mockEmptySummaryDetail: SummaryDetail = {
    id: 2,
    summaryType: 'hourly',
    content: 'All clear, no significant security events in the past hour.',
    eventCount: 0,
    windowStart: '2026-01-21T14:00:00Z',
    windowEnd: '2026-01-21T15:00:00Z',
    generatedAt: '2026-01-21T14:55:00Z',
    timeline: [],
    exportFormats: ['json', 'csv', 'pdf'],
    focusAreas: [],
    maxRiskScore: undefined,
  };

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);

    globalThis.ResizeObserver = MockResizeObserver as unknown as typeof ResizeObserver;

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
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('rendering', () => {
    it('renders the panel with summary content', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      expect(screen.getByTestId('expandable-detail-panel')).toBeInTheDocument();
      expect(screen.getByText(/Multiple security events/)).toBeInTheDocument();
    });

    it('does not render when isOpen is false', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen={false} onClose={vi.fn()} />);

      expect(screen.queryByTestId('expandable-detail-panel')).not.toBeInTheDocument();
    });

    it('renders summary type badge', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      expect(screen.getByText(/hourly/i)).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(
        <ExpandableDetailPanel
          detail={mockSummaryDetail}
          isOpen
          onClose={vi.fn()}
          className="custom-class"
        />
      );

      const panel = screen.getByTestId('expandable-detail-panel');
      expect(panel).toHaveClass('custom-class');
    });
  });

  describe('narrative section', () => {
    it('displays full narrative content', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      const narrative = screen.getByTestId('detail-narrative');
      expect(narrative).toHaveTextContent('Multiple security events were detected');
      expect(narrative).toHaveTextContent('unrecognized person approached');
    });

    it('shows event count', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      expect(screen.getByText(/3 events/i)).toBeInTheDocument();
    });

    it('shows focus areas', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      // Focus areas are displayed in metadata - look for the combined string
      expect(screen.getByText('Front Door, Driveway, Backyard')).toBeInTheDocument();
    });

    it('shows max risk score', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      expect(screen.getByText(/75/)).toBeInTheDocument();
    });
  });

  describe('timeline section', () => {
    it('renders timeline header', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      expect(screen.getByText(/Timeline/i)).toBeInTheDocument();
    });

    it('renders all timeline events', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      expect(screen.getByTestId('timeline-event-101')).toBeInTheDocument();
      expect(screen.getByTestId('timeline-event-102')).toBeInTheDocument();
      expect(screen.getByTestId('timeline-event-103')).toBeInTheDocument();
    });

    it('displays event details in timeline', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      const event = screen.getByTestId('timeline-event-101');
      expect(event).toHaveTextContent('Front Door');
      expect(event).toHaveTextContent('Person detected');
    });

    it('shows risk level badge for each event', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      expect(screen.getByTestId('risk-badge-101')).toHaveTextContent(/high/i);
      expect(screen.getByTestId('risk-badge-102')).toHaveTextContent(/medium/i);
      expect(screen.getByTestId('risk-badge-103')).toHaveTextContent(/low/i);
    });

    it('provides link to individual event', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      const eventLink = screen.getByTestId('event-link-101');
      expect(eventLink).toHaveAttribute('href', '/events/101');
    });

    it('shows empty state when no events', () => {
      render(<ExpandableDetailPanel detail={mockEmptySummaryDetail} isOpen onClose={vi.fn()} />);

      expect(screen.getByText(/no events/i)).toBeInTheDocument();
    });
  });

  describe('export section', () => {
    it('renders export buttons', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      expect(screen.getByTestId('export-json-btn')).toBeInTheDocument();
      expect(screen.getByTestId('export-csv-btn')).toBeInTheDocument();
      expect(screen.getByTestId('export-pdf-btn')).toBeInTheDocument();
    });

    it('calls onExport with json format when JSON button clicked', async () => {
      const onExport = vi.fn();
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(
        <ExpandableDetailPanel
          detail={mockSummaryDetail}
          isOpen
          onClose={vi.fn()}
          onExport={onExport}
        />
      );

      await user.click(screen.getByTestId('export-json-btn'));

      expect(onExport).toHaveBeenCalledWith(1, 'json');
    });

    it('calls onExport with csv format when CSV button clicked', async () => {
      const onExport = vi.fn();
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(
        <ExpandableDetailPanel
          detail={mockSummaryDetail}
          isOpen
          onClose={vi.fn()}
          onExport={onExport}
        />
      );

      await user.click(screen.getByTestId('export-csv-btn'));

      expect(onExport).toHaveBeenCalledWith(1, 'csv');
    });

    it('calls onExport with pdf format when PDF button clicked', async () => {
      const onExport = vi.fn();
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(
        <ExpandableDetailPanel
          detail={mockSummaryDetail}
          isOpen
          onClose={vi.fn()}
          onExport={onExport}
        />
      );

      await user.click(screen.getByTestId('export-pdf-btn'));

      expect(onExport).toHaveBeenCalledWith(1, 'pdf');
    });

    it('shows loading state during export', () => {
      render(
        <ExpandableDetailPanel
          detail={mockSummaryDetail}
          isOpen
          onClose={vi.fn()}
          isExporting
          exportFormat="json"
        />
      );

      const jsonBtn = screen.getByTestId('export-json-btn');
      expect(jsonBtn).toBeDisabled();
      expect(jsonBtn).toHaveTextContent(/exporting/i);
    });
  });

  describe('close behavior', () => {
    it('calls onClose when close button clicked', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={onClose} />);

      await user.click(screen.getByTestId('detail-panel-close'));

      expect(onClose).toHaveBeenCalled();
    });

    it('calls onClose when Escape key pressed', () => {
      const onClose = vi.fn();

      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={onClose} />);

      fireEvent.keyDown(document, { key: 'Escape' });

      expect(onClose).toHaveBeenCalled();
    });

    it('calls onClose when overlay clicked', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={onClose} />);

      const overlay = screen.getByTestId('detail-panel-overlay');
      await user.click(overlay);

      expect(onClose).toHaveBeenCalled();
    });

    it('does not close when panel content clicked', async () => {
      const onClose = vi.fn();
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={onClose} />);

      const panel = screen.getByTestId('expandable-detail-panel');
      await user.click(panel);

      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe('accessibility', () => {
    it('has correct ARIA attributes', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      const panel = screen.getByTestId('expandable-detail-panel');
      expect(panel).toHaveAttribute('role', 'dialog');
      expect(panel).toHaveAttribute('aria-modal', 'true');
    });

    it('has accessible close button', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      const closeBtn = screen.getByTestId('detail-panel-close');
      expect(closeBtn).toHaveAttribute('aria-label', 'Close detail panel');
    });

    it('focuses close button when opened', async () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      await waitFor(() => {
        const closeBtn = screen.getByTestId('detail-panel-close');
        expect(document.activeElement).toBe(closeBtn);
      });
    });

    it('timeline events are keyboard navigable', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      const eventLinks = screen.getAllByRole('link');
      eventLinks.forEach((link) => {
        expect(link).toHaveAttribute('tabIndex', '0');
      });
    });
  });

  describe('animation', () => {
    it('has expand animation class when open', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      const panel = screen.getByTestId('expandable-detail-panel');
      expect(panel).toHaveClass('animate-slide-in');
    });

    it('respects prefers-reduced-motion', () => {
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

      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      const panel = screen.getByTestId('expandable-detail-panel');
      expect(panel).not.toHaveClass('animate-slide-in');
    });
  });

  describe('metadata', () => {
    it('shows time window', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      expect(screen.getByTestId('detail-time-window')).toBeInTheDocument();
    });

    it('shows generated time', () => {
      render(<ExpandableDetailPanel detail={mockSummaryDetail} isOpen onClose={vi.fn()} />);

      expect(screen.getByText(/generated/i)).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('handles missing optional fields', () => {
      const minimalDetail: SummaryDetail = {
        id: 3,
        summaryType: 'daily',
        content: 'Minimal content',
        eventCount: 0,
        windowStart: '2026-01-21T00:00:00Z',
        windowEnd: '2026-01-21T15:00:00Z',
        generatedAt: '2026-01-21T14:55:00Z',
        timeline: [],
        exportFormats: ['json'],
      };

      render(<ExpandableDetailPanel detail={minimalDetail} isOpen onClose={vi.fn()} />);

      expect(screen.getByTestId('expandable-detail-panel')).toBeInTheDocument();
      expect(screen.queryByText(/focus areas/i)).not.toBeInTheDocument();
    });

    it('handles very long content', () => {
      const longDetail: SummaryDetail = {
        ...mockSummaryDetail,
        content: 'A'.repeat(2000),
      };

      render(<ExpandableDetailPanel detail={longDetail} isOpen onClose={vi.fn()} />);

      const narrative = screen.getByTestId('detail-narrative');
      expect(narrative).toBeInTheDocument();
    });

    it('handles many timeline events', () => {
      const manyEvents: TimelineEvent[] = Array.from({ length: 20 }, (_, i) => ({
        eventId: i + 1,
        timestamp: `2026-01-21T14:${String(i).padStart(2, '0')}:00Z`,
        cameraName: `Camera ${i + 1}`,
        summary: `Event ${i + 1}`,
        riskScore: 50,
        riskLevel: 'medium',
        eventUrl: `/events/${i + 1}`,
      }));

      const manyEventsDetail: SummaryDetail = {
        ...mockSummaryDetail,
        eventCount: 20,
        timeline: manyEvents,
      };

      render(<ExpandableDetailPanel detail={manyEventsDetail} isOpen onClose={vi.fn()} />);

      // Should render all events (or show virtualized/scrollable list)
      expect(screen.getByTestId('timeline-event-1')).toBeInTheDocument();
      expect(screen.getByTestId('timeline-event-20')).toBeInTheDocument();
    });
  });
});

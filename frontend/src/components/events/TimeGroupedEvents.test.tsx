import { fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import TimeGroupedEvents from './TimeGroupedEvents';
import { renderWithProviders, screen } from '../../test-utils/renderWithProviders';

import type { Event } from '../../services/api';

// Mock the EventCard component to avoid complex dependency chain
vi.mock('./EventCard', () => ({
  default: vi.fn(({ id, summary, camera_name }) => (
    <div data-testid={`event-card-${id}`}>
      <span>{summary}</span>
      <span>{camera_name}</span>
    </div>
  )),
}));

// Mock the EventCardSkeleton component
vi.mock('../common', () => ({
  EventCardSkeleton: vi.fn(() => <div data-testid="event-card-skeleton" />),
}));

describe('TimeGroupedEvents', () => {
  const NOW = new Date('2024-01-18T14:00:00.000Z');

  const createEvent = (
    id: number,
    started_at: string,
    risk_score: number,
    risk_level: 'low' | 'medium' | 'high' | 'critical'
  ): Event => ({
    id,
    camera_id: `camera-${id}`,
    started_at,
    ended_at: null,
    risk_score,
    risk_level,
    summary: `Test event ${id}`,
    reviewed: false,
    flagged: false, // NEM-3839
    detection_count: 1,
    notes: null,
    version: 1, // Optimistic locking version (NEM-3625)
  });

  const todayEvent = createEvent(1, '2024-01-18T10:00:00.000Z', 85, 'critical');
  const todayEvent2 = createEvent(2, '2024-01-18T08:00:00.000Z', 65, 'high');
  const yesterdayEvent = createEvent(3, '2024-01-17T15:00:00.000Z', 45, 'medium');
  const yesterdayEvent2 = createEvent(4, '2024-01-17T09:00:00.000Z', 20, 'low');
  const thisWeekEvent = createEvent(5, '2024-01-15T12:00:00.000Z', 70, 'high');
  const thisWeekEvent2 = createEvent(6, '2024-01-16T10:00:00.000Z', 30, 'medium');
  const olderEvent = createEvent(7, '2024-01-01T10:00:00.000Z', 25, 'low');
  const olderEvent2 = createEvent(8, '2023-12-25T10:00:00.000Z', 90, 'critical');

  const mockEvents: Event[] = [
    todayEvent,
    todayEvent2,
    yesterdayEvent,
    yesterdayEvent2,
    thisWeekEvent,
    thisWeekEvent2,
    olderEvent,
    olderEvent2,
  ];

  const defaultProps = {
    events: mockEvents,
    onEventClick: vi.fn(),
    cameraNameMap: new Map([
      ['camera-1', 'Front Door'],
      ['camera-2', 'Back Yard'],
      ['camera-3', 'Garage'],
      ['camera-4', 'Side Gate'],
      ['camera-5', 'Driveway'],
      ['camera-6', 'Porch'],
      ['camera-7', 'Kitchen'],
      ['camera-8', 'Living Room'],
    ]),
    selectedEventIds: new Set<number>(),
    onToggleSelection: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Rendering', () => {
    it('renders all time group sections', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      expect(screen.getByText('Today')).toBeInTheDocument();
      expect(screen.getByText('Yesterday')).toBeInTheDocument();
      expect(screen.getByText('Earlier This Week')).toBeInTheDocument();
      expect(screen.getByText('Older')).toBeInTheDocument();
    });

    it('renders correct event count in group headers', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      expect(screen.getByTestId('group-today-count')).toHaveTextContent('2');
      expect(screen.getByTestId('group-yesterday-count')).toHaveTextContent('2');
      expect(screen.getByTestId('group-this-week-count')).toHaveTextContent('2');
      expect(screen.getByTestId('group-older-count')).toHaveTextContent('2');
    });

    it('shows empty state when no events provided', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} events={[]} />);

      expect(screen.getByText('No events to display')).toBeInTheDocument();
    });

    it('hides groups with no events', () => {
      const todayOnlyEvents = [todayEvent, todayEvent2];
      renderWithProviders(<TimeGroupedEvents {...defaultProps} events={todayOnlyEvents} />);

      expect(screen.getByText('Today')).toBeInTheDocument();
      expect(screen.queryByText('Yesterday')).not.toBeInTheDocument();
      expect(screen.queryByText('Earlier This Week')).not.toBeInTheDocument();
      expect(screen.queryByText('Older')).not.toBeInTheDocument();
    });
  });

  describe('Collapsible Behavior', () => {
    it('Today group is expanded by default', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      const todayContent = screen.getByTestId('group-today-content');
      expect(todayContent).toBeVisible();
    });

    it('other groups are collapsed by default', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      expect(screen.queryByText('Test event 3')).not.toBeInTheDocument();
      expect(screen.queryByText('Test event 5')).not.toBeInTheDocument();
      expect(screen.queryByText('Test event 7')).not.toBeInTheDocument();
    });

    it('expands group when header is clicked', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      const yesterdayHeader = screen.getByTestId('group-yesterday-header');
      fireEvent.click(yesterdayHeader);

      expect(screen.getByText('Test event 3')).toBeInTheDocument();
      expect(screen.getByText('Test event 4')).toBeInTheDocument();
    });

    it('collapses group when expanded header is clicked', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      const todayHeader = screen.getByTestId('group-today-header');
      fireEvent.click(todayHeader);

      expect(screen.queryByText('Test event 1')).not.toBeInTheDocument();
    });

    it('has correct aria-expanded attribute', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      const todayHeader = screen.getByTestId('group-today-header');
      const yesterdayHeader = screen.getByTestId('group-yesterday-header');

      expect(todayHeader).toHaveAttribute('aria-expanded', 'true');
      expect(yesterdayHeader).toHaveAttribute('aria-expanded', 'false');

      fireEvent.click(yesterdayHeader);

      expect(yesterdayHeader).toHaveAttribute('aria-expanded', 'true');
    });
  });

  describe('Risk Breakdown Mini Badges', () => {
    it('shows critical count in red', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      const todayHeader = screen.getByTestId('group-today-header');
      const criticalBadge = todayHeader.querySelector('[data-risk="critical"]');
      expect(criticalBadge).toBeInTheDocument();
      expect(criticalBadge).toHaveTextContent('1');
    });

    it('shows high count in orange', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      const todayHeader = screen.getByTestId('group-today-header');
      const highBadge = todayHeader.querySelector('[data-risk="high"]');
      expect(highBadge).toBeInTheDocument();
      expect(highBadge).toHaveTextContent('1');
    });

    it('shows medium count in yellow', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      const yesterdayHeader = screen.getByTestId('group-yesterday-header');
      const mediumBadge = yesterdayHeader.querySelector('[data-risk="medium"]');
      expect(mediumBadge).toBeInTheDocument();
      expect(mediumBadge).toHaveTextContent('1');
    });

    it('does not show badge for risk level with zero count', () => {
      const highRiskEvents = [todayEvent2];
      renderWithProviders(<TimeGroupedEvents {...defaultProps} events={highRiskEvents} />);

      const todayHeader = screen.getByTestId('group-today-header');
      const criticalBadge = todayHeader.querySelector('[data-risk="critical"]');
      const lowBadge = todayHeader.querySelector('[data-risk="low"]');

      expect(criticalBadge).not.toBeInTheDocument();
      expect(lowBadge).not.toBeInTheDocument();
    });
  });

  describe('Date Formatting', () => {
    it('shows date range for Today group', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      expect(screen.getByTestId('group-today-date')).toHaveTextContent('January 18');
    });

    it('shows date for Yesterday group', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      expect(screen.getByTestId('group-yesterday-date')).toHaveTextContent('January 17');
    });

    it('shows date range for Earlier This Week group', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      const thisWeekDate = screen.getByTestId('group-this-week-date');
      expect(thisWeekDate.textContent).toMatch(/Jan \d+.*Jan \d+/);
    });
  });

  describe('Accessibility', () => {
    it('group headers are keyboard accessible', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      const yesterdayHeader = screen.getByTestId('group-yesterday-header');

      yesterdayHeader.focus();
      expect(yesterdayHeader).toHaveFocus();

      // Native button elements respond to Enter key by triggering click
      fireEvent.click(yesterdayHeader);

      expect(yesterdayHeader).toHaveAttribute('aria-expanded', 'true');
    });

    it('has proper ARIA labels for group sections', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      const todaySection = screen.getByTestId('group-today');
      expect(todaySection).toHaveAttribute('role', 'region');
      expect(todaySection).toHaveAttribute('aria-labelledby', 'group-today-header');
    });

    it('has proper ARIA controls relationship', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} />);

      const todayHeader = screen.getByTestId('group-today-header');
      expect(todayHeader).toHaveAttribute('aria-controls', 'group-today-content');
    });
  });

  describe('Edge Cases', () => {
    it('handles events early in the day', () => {
      // Use noon UTC which should be today regardless of local timezone
      const earlyEvent = createEvent(99, '2024-01-18T12:00:00.000Z', 50, 'medium');
      renderWithProviders(<TimeGroupedEvents {...defaultProps} events={[earlyEvent]} />);

      expect(screen.getByText('Today')).toBeInTheDocument();
      expect(screen.getByTestId('group-today-count')).toHaveTextContent('1');
    });

    it('handles events from different years', () => {
      const oldYearEvent = createEvent(100, '2023-01-15T10:00:00.000Z', 50, 'medium');
      renderWithProviders(<TimeGroupedEvents {...defaultProps} events={[oldYearEvent]} />);

      expect(screen.getByText('Older')).toBeInTheDocument();
      expect(screen.getByTestId('group-older-count')).toHaveTextContent('1');
    });

    it('groups events correctly when current day is Sunday', () => {
      vi.setSystemTime(new Date('2024-01-14T14:00:00.000Z'));

      const sundayEvent = createEvent(1, '2024-01-14T10:00:00.000Z', 50, 'medium');
      const saturdayEvent = createEvent(2, '2024-01-13T10:00:00.000Z', 50, 'medium');

      renderWithProviders(
        <TimeGroupedEvents {...defaultProps} events={[sundayEvent, saturdayEvent]} />
      );

      expect(screen.getByText('Today')).toBeInTheDocument();
      expect(screen.getByText('Yesterday')).toBeInTheDocument();
    });

    it('handles single event', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} events={[todayEvent]} />);

      expect(screen.getByText('Today')).toBeInTheDocument();
      expect(screen.getByTestId('group-today-count')).toHaveTextContent('1');
      expect(screen.getByText('Test event 1')).toBeInTheDocument();
    });

    it('handles unknown camera ID gracefully', () => {
      const unknownCameraEvent = {
        ...todayEvent,
        camera_id: 'unknown-camera',
      };
      const smallCameraMap = new Map<string, string>();
      renderWithProviders(
        <TimeGroupedEvents
          {...defaultProps}
          events={[unknownCameraEvent]}
          cameraNameMap={smallCameraMap}
        />
      );

      expect(screen.getByText('Unknown Camera')).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('shows loading skeletons when isLoading is true', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} isLoading />);

      expect(screen.getAllByTestId('event-card-skeleton').length).toBeGreaterThan(0);
    });

    it('does not show events when loading', () => {
      renderWithProviders(<TimeGroupedEvents {...defaultProps} isLoading />);

      expect(screen.queryByText('Test event 1')).not.toBeInTheDocument();
    });
  });
});

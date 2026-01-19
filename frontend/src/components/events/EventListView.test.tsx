import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import EventListView, { type EventListViewProps } from './EventListView';

describe('EventListView', () => {
  // Base time for consistent testing
  const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

  // Mock events data
  const mockEvents: EventListViewProps['events'] = [
    {
      id: 1,
      camera_id: 'cam-1',
      camera_name: 'Front Door',
      started_at: new Date(BASE_TIME - 5 * 60 * 1000).toISOString(),
      ended_at: new Date(BASE_TIME).toISOString(),
      risk_score: 75,
      risk_level: 'high',
      summary: 'Person detected at front door',
      thumbnail_url: 'https://example.com/thumb1.jpg',
      reviewed: false,
    },
    {
      id: 2,
      camera_id: 'cam-2',
      camera_name: 'Back Yard',
      started_at: new Date(BASE_TIME - 60 * 60 * 1000).toISOString(),
      ended_at: new Date(BASE_TIME - 55 * 60 * 1000).toISOString(),
      risk_score: 25,
      risk_level: 'low',
      summary: 'Animal crossing the yard',
      thumbnail_url: 'https://example.com/thumb2.jpg',
      reviewed: true,
    },
    {
      id: 3,
      camera_id: 'cam-1',
      camera_name: 'Front Door',
      started_at: new Date(BASE_TIME - 30 * 60 * 1000).toISOString(),
      ended_at: null,
      risk_score: 55,
      risk_level: 'medium',
      summary: 'Vehicle parked in driveway',
      thumbnail_url: null,
      reviewed: false,
    },
  ];

  // Mock system time
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('table structure', () => {
    it('renders table with correct headers', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      expect(screen.getByRole('columnheader', { name: /time/i })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: /camera/i })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: /summary/i })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: /risk/i })).toBeInTheDocument();
      expect(screen.getByRole('columnheader', { name: /actions/i })).toBeInTheDocument();
    });

    it('renders correct number of rows', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      const rows = screen.getAllByRole('row');
      // 1 header row + 3 data rows
      expect(rows).toHaveLength(4);
    });

    it('renders empty state when no events', () => {
      render(
        <EventListView
          events={[]}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      expect(screen.getByText(/no events/i)).toBeInTheDocument();
    });
  });

  describe('event data display', () => {
    it('displays event timestamps', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      // First event is 5 minutes ago
      expect(screen.getByText('5 minutes ago')).toBeInTheDocument();
    });

    it('displays camera names', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      expect(screen.getAllByText('Front Door')).toHaveLength(2);
      expect(screen.getByText('Back Yard')).toBeInTheDocument();
    });

    it('displays event summaries', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      expect(screen.getByText('Person detected at front door')).toBeInTheDocument();
      expect(screen.getByText('Animal crossing the yard')).toBeInTheDocument();
      expect(screen.getByText('Vehicle parked in driveway')).toBeInTheDocument();
    });

    it('displays risk scores with colored badges', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      // Check for risk badges - they display level and score
      expect(screen.getByText('High (75)')).toBeInTheDocument();
      expect(screen.getByText('Low (25)')).toBeInTheDocument();
      expect(screen.getByText('Medium (55)')).toBeInTheDocument();
    });

    it('displays mini thumbnail when available', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      const thumbnails = screen.getAllByRole('img');
      expect(thumbnails).toHaveLength(2); // Only 2 events have thumbnails
    });

    it('displays placeholder when thumbnail is not available', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      // Event 3 has no thumbnail, should show placeholder
      const { container } = render(
        <EventListView
          events={[mockEvents[2]]}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      const eyeIcon = container.querySelector('svg.lucide-eye');
      expect(eyeIcon).toBeInTheDocument();
    });
  });

  describe('row styling', () => {
    it('applies dimmed opacity to reviewed rows', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      const rows = screen.getAllByRole('row');
      // Row index 2 (second data row, id=2) should be reviewed
      expect(rows[2]).toHaveClass('opacity-60');
    });

    it('applies green tint to selected rows', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set([1])}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      const rows = screen.getAllByRole('row');
      // Row index 1 (first data row, id=1) should be selected
      expect(rows[1]).toHaveClass('bg-[#76B900]/10');
    });

    it('applies hover highlight class', () => {
      const { container } = render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      const dataRows = container.querySelectorAll('tbody tr');
      dataRows.forEach((row) => {
        expect(row).toHaveClass('hover:bg-[#252525]');
      });
    });
  });

  describe('selection', () => {
    it('renders checkbox for each row', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      // 1 header checkbox + 3 row checkboxes
      expect(checkboxes).toHaveLength(4);
    });

    it('calls onToggleSelection when row checkbox is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleToggleSelection = vi.fn();

      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={handleToggleSelection}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[1]); // Click first row checkbox

      expect(handleToggleSelection).toHaveBeenCalledWith(1);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('calls onToggleSelectAll when header checkbox is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleToggleSelectAll = vi.fn();

      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={handleToggleSelectAll}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]); // Click header checkbox

      expect(handleToggleSelectAll).toHaveBeenCalled();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('shows checked state for selected rows', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set([1, 3])}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      expect(checkboxes[1]).toBeChecked(); // Event 1
      expect(checkboxes[2]).not.toBeChecked(); // Event 2
      expect(checkboxes[3]).toBeChecked(); // Event 3
    });

    it('shows indeterminate state when some rows selected', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set([1])}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      const headerCheckbox = screen.getAllByRole('checkbox')[0];
      // indeterminate state is set via ref, check the data attribute we set
      expect(headerCheckbox).toHaveAttribute('data-indeterminate', 'true');
    });

    it('shows checked state when all rows selected', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set([1, 2, 3])}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      const headerCheckbox = screen.getAllByRole('checkbox')[0];
      expect(headerCheckbox).toBeChecked();
    });
  });

  describe('sortable columns', () => {
    it('renders sort indicators in column headers', () => {
      const { container } = render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
          sortField="time"
          sortDirection="desc"
        />
      );

      // Time column should show descending sort indicator
      const chevronDown = container.querySelector('[data-testid="sort-indicator-time"] svg.lucide-chevron-down');
      expect(chevronDown).toBeInTheDocument();
    });

    it('calls onSort when sortable column header is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleSort = vi.fn();

      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
          onSort={handleSort}
        />
      );

      const timeHeader = screen.getByRole('columnheader', { name: /time/i });
      await user.click(timeHeader);

      expect(handleSort).toHaveBeenCalledWith('time');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('shows ascending indicator when sorted ascending', () => {
      const { container } = render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
          sortField="risk"
          sortDirection="asc"
        />
      );

      const chevronUp = container.querySelector('[data-testid="sort-indicator-risk"] svg.lucide-chevron-up');
      expect(chevronUp).toBeInTheDocument();
    });

    it('time, camera, and risk columns are sortable', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleSort = vi.fn();

      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
          onSort={handleSort}
        />
      );

      await user.click(screen.getByRole('columnheader', { name: /time/i }));
      expect(handleSort).toHaveBeenCalledWith('time');

      await user.click(screen.getByRole('columnheader', { name: /camera/i }));
      expect(handleSort).toHaveBeenCalledWith('camera');

      await user.click(screen.getByRole('columnheader', { name: /risk/i }));
      expect(handleSort).toHaveBeenCalledWith('risk');

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('actions', () => {
    it('renders view details button for each row', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      const viewButtons = screen.getAllByRole('button', { name: /view details/i });
      expect(viewButtons).toHaveLength(3);
    });

    it('renders mark reviewed button for unreviewed events', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      // Only 2 events are unreviewed (id 1 and 3)
      // The button aria-label is "Mark event X as reviewed"
      const reviewButtons = screen.getAllByRole('button', { name: /mark event \d+ as reviewed/i });
      expect(reviewButtons).toHaveLength(2);
    });

    it('calls onEventClick when view details button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleEventClick = vi.fn();

      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={handleEventClick}
          onMarkReviewed={vi.fn()}
        />
      );

      const viewButtons = screen.getAllByRole('button', { name: /view details/i });
      await user.click(viewButtons[0]);

      expect(handleEventClick).toHaveBeenCalledWith(1);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('calls onMarkReviewed when mark reviewed button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleMarkReviewed = vi.fn();

      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={handleMarkReviewed}
        />
      );

      const reviewButtons = screen.getAllByRole('button', { name: /mark event \d+ as reviewed/i });
      await user.click(reviewButtons[0]);

      expect(handleMarkReviewed).toHaveBeenCalledWith(1);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('row click behavior', () => {
    it('calls onEventClick when row is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleEventClick = vi.fn();

      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={handleEventClick}
          onMarkReviewed={vi.fn()}
        />
      );

      const rows = screen.getAllByRole('row');
      // Click on the summary cell of the first data row
      const summaryCell = within(rows[1]).getByText('Person detected at front door');
      await user.click(summaryCell);

      expect(handleEventClick).toHaveBeenCalledWith(1);

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('does not trigger onEventClick when clicking checkbox', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleEventClick = vi.fn();

      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={handleEventClick}
          onMarkReviewed={vi.fn()}
        />
      );

      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[1]); // Click first row checkbox

      expect(handleEventClick).not.toHaveBeenCalled();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('does not trigger onEventClick when clicking action buttons', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleEventClick = vi.fn();

      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={handleEventClick}
          onMarkReviewed={vi.fn()}
        />
      );

      const reviewButtons = screen.getAllByRole('button', { name: /mark event \d+ as reviewed/i });
      await user.click(reviewButtons[0]);

      expect(handleEventClick).not.toHaveBeenCalled();

      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });
  });

  describe('accessibility', () => {
    it('table has appropriate role', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      expect(screen.getByRole('table')).toBeInTheDocument();
    });

    it('header checkbox has accessible label', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      expect(screen.getByLabelText(/select all events/i)).toBeInTheDocument();
    });

    it('row checkboxes have accessible labels', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      expect(screen.getByLabelText(/select event 1/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/select event 2/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/select event 3/i)).toBeInTheDocument();
    });

    it('sortable columns have aria-sort attribute', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
          sortField="time"
          sortDirection="desc"
        />
      );

      const timeHeader = screen.getByRole('columnheader', { name: /time/i });
      expect(timeHeader).toHaveAttribute('aria-sort', 'descending');
    });
  });

  describe('responsive behavior', () => {
    it('summary column has responsive hiding class for mobile', () => {
      render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      const summaryHeader = screen.getByRole('columnheader', { name: /summary/i });
      expect(summaryHeader).toHaveClass('hidden', 'md:table-cell');
    });
  });

  describe('styling', () => {
    it('applies NVIDIA theme colors', () => {
      const { container } = render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
        />
      );

      // The outermost wrapper has the background color
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass('bg-[#1F1F1F]');
    });

    it('applies custom className', () => {
      const { container } = render(
        <EventListView
          events={mockEvents}
          selectedIds={new Set()}
          onToggleSelection={vi.fn()}
          onToggleSelectAll={vi.fn()}
          onEventClick={vi.fn()}
          onMarkReviewed={vi.fn()}
          className="custom-class"
        />
      );

      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass('custom-class');
    });
  });
});

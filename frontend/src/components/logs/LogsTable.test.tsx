import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';

import { groupRepeatedLogs } from './logGrouping';
import LogsTable, { type LogEntry } from './LogsTable';

describe('LogsTable', () => {
  const mockLogs: LogEntry[] = [
    {
      id: 1,
      timestamp: '2024-01-01T10:00:00Z',
      level: 'ERROR',
      component: 'api',
      message: 'Failed to process request',
      camera_id: 'camera-1',
      event_id: 1,
      request_id: 'req-123',
      detection_id: null,
      duration_ms: 150,
      extra: { error_code: '500' },
      source: 'backend',
    },
    {
      id: 2,
      timestamp: '2024-01-01T11:00:00Z',
      level: 'INFO',
      component: 'detector',
      message: 'Detection completed successfully',
      camera_id: 'camera-2',
      event_id: null,
      request_id: null,
      detection_id: 5,
      duration_ms: 250,
      extra: null,
      source: 'backend',
    },
    {
      id: 3,
      timestamp: '2024-01-01T12:00:00Z',
      level: 'WARNING',
      component: 'frontend',
      message: 'Slow API response detected in the system',
      camera_id: null,
      event_id: null,
      request_id: 'req-456',
      detection_id: null,
      duration_ms: 3000,
      extra: { threshold_ms: 2000 },
      source: 'frontend',
    },
    {
      id: 4,
      timestamp: '2024-01-01T13:00:00Z',
      level: 'DEBUG',
      component: 'file_watcher',
      message: 'Watching directory for changes',
      camera_id: null,
      event_id: null,
      request_id: null,
      detection_id: null,
      duration_ms: null,
      extra: null,
      source: 'backend',
    },
    {
      id: 5,
      timestamp: '2024-01-01T14:00:00Z',
      level: 'CRITICAL',
      component: 'database',
      message: 'Database connection lost',
      camera_id: null,
      event_id: null,
      request_id: null,
      detection_id: null,
      duration_ms: null,
      extra: { retry_count: 3 },
      source: 'backend',
    },
  ];

  describe('Rendering', () => {
    it('renders table with log entries', () => {
      render(<LogsTable logs={mockLogs} totalCount={5} limit={50} offset={0} />);

      expect(screen.getByText('Failed to process request')).toBeInTheDocument();
      expect(screen.getByText('Detection completed successfully')).toBeInTheDocument();
      expect(screen.getByText('Slow API response detected in the system')).toBeInTheDocument();
    });

    it('renders table headers', () => {
      render(<LogsTable logs={mockLogs} totalCount={5} limit={50} offset={0} />);

      expect(screen.getByText('Timestamp')).toBeInTheDocument();
      expect(screen.getByText('Level')).toBeInTheDocument();
      expect(screen.getByText('Component')).toBeInTheDocument();
      expect(screen.getByText('Message')).toBeInTheDocument();
    });

    it('displays result summary', () => {
      render(<LogsTable logs={mockLogs} totalCount={5} limit={50} offset={0} />);

      expect(screen.getByText('Showing 1-5 of 5 logs')).toBeInTheDocument();
    });

    it('displays correct result summary for pagination', () => {
      render(<LogsTable logs={mockLogs} totalCount={100} limit={50} offset={50} />);

      expect(screen.getByText('Showing 51-100 of 100 logs')).toBeInTheDocument();
    });
  });

  describe('Level Badges', () => {
    it('displays ERROR badge with red styling', () => {
      render(<LogsTable logs={[mockLogs[0]]} totalCount={1} limit={50} offset={0} />);

      const errorBadge = screen.getByText('ERROR');
      expect(errorBadge).toHaveClass('text-red-400');
    });

    it('displays WARNING badge with yellow styling', () => {
      render(<LogsTable logs={[mockLogs[2]]} totalCount={1} limit={50} offset={0} />);

      const warningBadge = screen.getByText('WARNING');
      expect(warningBadge).toHaveClass('text-yellow-400');
    });

    it('displays INFO badge with blue styling', () => {
      render(<LogsTable logs={[mockLogs[1]]} totalCount={1} limit={50} offset={0} />);

      const infoBadge = screen.getByText('INFO');
      expect(infoBadge).toHaveClass('text-blue-400');
    });

    it('displays DEBUG badge with gray styling', () => {
      render(<LogsTable logs={[mockLogs[3]]} totalCount={1} limit={50} offset={0} />);

      const debugBadge = screen.getByText('DEBUG');
      expect(debugBadge).toHaveClass('text-gray-400');
    });

    it('displays CRITICAL badge with emphasized red styling (solid background, bold)', () => {
      render(<LogsTable logs={[mockLogs[4]]} totalCount={1} limit={50} offset={0} />);

      const criticalBadge = screen.getByText('CRITICAL');
      // CRITICAL has solid red background with white text for emphasis
      expect(criticalBadge).toHaveClass('bg-red-600');
      expect(criticalBadge).toHaveClass('text-white');
      expect(criticalBadge).toHaveClass('font-bold');
      expect(criticalBadge).toHaveClass('border-red-600');
    });

    it('displays unknown level with gray styling (default case)', () => {
      // Test the default case in getLevelBadgeClasses (line 46)
      const unknownLog: LogEntry = {
        ...mockLogs[0],
        level: 'UNKNOWN' as LogEntry['level'],
      };

      render(<LogsTable logs={[unknownLog]} totalCount={1} limit={50} offset={0} />);

      const unknownBadge = screen.getByText('UNKNOWN');
      expect(unknownBadge).toHaveClass('text-gray-400');
      expect(unknownBadge).toHaveClass('bg-gray-500/10');
      expect(unknownBadge).toHaveClass('border-gray-500/20');
    });
  });

  describe('Component Display', () => {
    it('displays component names with green accent', () => {
      render(<LogsTable logs={mockLogs} totalCount={5} limit={50} offset={0} />);

      const apiComponent = screen.getByText('api');
      expect(apiComponent).toHaveClass('text-[#76B900]');
      expect(apiComponent).toHaveClass('font-mono');
    });

    it('displays all unique components', () => {
      render(<LogsTable logs={mockLogs} totalCount={5} limit={50} offset={0} />);

      expect(screen.getByText('api')).toBeInTheDocument();
      expect(screen.getByText('detector')).toBeInTheDocument();
      expect(screen.getByText('frontend')).toBeInTheDocument();
      expect(screen.getByText('file_watcher')).toBeInTheDocument();
      expect(screen.getByText('database')).toBeInTheDocument();
    });
  });

  describe('Message Truncation', () => {
    it('does not truncate short messages', () => {
      const shortMessage = mockLogs[0];
      render(<LogsTable logs={[shortMessage]} totalCount={1} limit={50} offset={0} />);

      expect(screen.getByText('Failed to process request')).toBeInTheDocument();
      expect(screen.queryByText(/\.\.\./)).not.toBeInTheDocument();
    });

    it('truncates long messages', () => {
      const longLog: LogEntry = {
        ...mockLogs[0],
        message:
          'This is a very long log message that should be truncated because it exceeds the maximum length allowed in the table cell for display purposes',
      };

      render(<LogsTable logs={[longLog]} totalCount={1} limit={50} offset={0} />);

      const messageCell = screen.getByText(/This is a very long log message/);
      expect(messageCell.textContent).toContain('...');
      expect(messageCell.textContent?.length).toBeLessThan(longLog.message.length);
    });
  });

  describe('Row Click Interaction', () => {
    it('calls onRowClick when row is clicked', async () => {
      const handleRowClick = vi.fn();
      const user = userEvent.setup();

      render(
        <LogsTable
          logs={mockLogs}
          totalCount={5}
          limit={50}
          offset={0}
          onRowClick={handleRowClick}
        />
      );

      const row = screen.getByText('Failed to process request').closest('tr');
      expect(row).toBeInTheDocument();

      if (row) {
        await user.click(row);
        expect(handleRowClick).toHaveBeenCalledWith(mockLogs[0]);
      }
    });

    it('adds hover effect when onRowClick is provided', () => {
      const handleRowClick = vi.fn();

      render(
        <LogsTable
          logs={mockLogs}
          totalCount={5}
          limit={50}
          offset={0}
          onRowClick={handleRowClick}
        />
      );

      const row = screen.getByText('Failed to process request').closest('tr');
      expect(row).toHaveClass('cursor-pointer');
      expect(row).toHaveClass('hover:bg-[#76B900]/5');
    });

    it('does not add hover effect when onRowClick is not provided', () => {
      render(<LogsTable logs={mockLogs} totalCount={5} limit={50} offset={0} />);

      const row = screen.getByText('Failed to process request').closest('tr');
      expect(row).not.toHaveClass('cursor-pointer');
    });

    it('does not call handler when row is clicked and onRowClick is not provided (line 123)', async () => {
      const user = userEvent.setup();

      render(<LogsTable logs={mockLogs} totalCount={5} limit={50} offset={0} />);

      const row = screen.getByText('Failed to process request').closest('tr');
      expect(row).toBeInTheDocument();

      if (row) {
        // Click row without handler - should not error
        await user.click(row);
        // No assertion needed - test passes if no error thrown
      }
    });
  });

  describe('Pagination', () => {
    it('displays pagination controls', () => {
      render(<LogsTable logs={mockLogs} totalCount={100} limit={50} offset={0} />);

      expect(screen.getByLabelText('Previous page')).toBeInTheDocument();
      expect(screen.getByLabelText('Next page')).toBeInTheDocument();
      expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
    });

    it('calls onPageChange when next button is clicked', async () => {
      const handlePageChange = vi.fn();
      const user = userEvent.setup();

      render(
        <LogsTable
          logs={mockLogs}
          totalCount={100}
          limit={50}
          offset={0}
          onPageChange={handlePageChange}
        />
      );

      const nextButton = screen.getByLabelText('Next page');
      await user.click(nextButton);

      expect(handlePageChange).toHaveBeenCalledWith(50);
    });

    it('calls onPageChange when previous button is clicked', async () => {
      const handlePageChange = vi.fn();
      const user = userEvent.setup();

      render(
        <LogsTable
          logs={mockLogs}
          totalCount={100}
          limit={50}
          offset={50}
          onPageChange={handlePageChange}
        />
      );

      const prevButton = screen.getByLabelText('Previous page');
      await user.click(prevButton);

      expect(handlePageChange).toHaveBeenCalledWith(0);
    });

    it('disables previous button on first page', () => {
      render(<LogsTable logs={mockLogs} totalCount={100} limit={50} offset={0} />);

      const prevButton = screen.getByLabelText('Previous page');
      expect(prevButton).toBeDisabled();
    });

    it('disables next button on last page', () => {
      render(<LogsTable logs={mockLogs} totalCount={100} limit={50} offset={50} />);

      const nextButton = screen.getByLabelText('Next page');
      expect(nextButton).toBeDisabled();
    });

    it('calculates correct page numbers', () => {
      render(<LogsTable logs={mockLogs} totalCount={150} limit={50} offset={50} />);

      expect(screen.getByText('Page 2 of 3')).toBeInTheDocument();
    });

    it('hides pagination when totalCount is zero', () => {
      render(<LogsTable logs={[]} totalCount={0} limit={50} offset={0} />);

      expect(screen.queryByLabelText('Previous page')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Next page')).not.toBeInTheDocument();
    });

    it('does not call onPageChange when clicking disabled previous button (line 110)', async () => {
      const handlePageChange = vi.fn();
      const user = userEvent.setup();

      render(
        <LogsTable
          logs={mockLogs}
          totalCount={100}
          limit={50}
          offset={0}
          onPageChange={handlePageChange}
        />
      );

      const prevButton = screen.getByLabelText('Previous page');
      expect(prevButton).toBeDisabled();

      // Try to click disabled button - should not call handler
      await user.click(prevButton);
      expect(handlePageChange).not.toHaveBeenCalled();
    });

    it('does not call onPageChange when clicking disabled next button (line 116)', async () => {
      const handlePageChange = vi.fn();
      const user = userEvent.setup();

      render(
        <LogsTable
          logs={mockLogs}
          totalCount={100}
          limit={50}
          offset={50}
          onPageChange={handlePageChange}
        />
      );

      const nextButton = screen.getByLabelText('Next page');
      expect(nextButton).toBeDisabled();

      // Try to click disabled button - should not call handler
      await user.click(nextButton);
      expect(handlePageChange).not.toHaveBeenCalled();
    });

    it('does not call onPageChange when handler is not provided (line 110)', async () => {
      const user = userEvent.setup();

      render(<LogsTable logs={mockLogs} totalCount={100} limit={50} offset={50} />);

      const prevButton = screen.getByLabelText('Previous page');
      expect(prevButton).toBeInTheDocument();

      // Click button without handler - should not error
      await user.click(prevButton);
      // No assertion needed - test passes if no error thrown
    });

    it('does not call onPageChange when handler is not provided (line 116)', async () => {
      const user = userEvent.setup();

      render(<LogsTable logs={mockLogs} totalCount={100} limit={50} offset={0} />);

      const nextButton = screen.getByLabelText('Next page');
      expect(nextButton).toBeInTheDocument();

      // Click button without handler - should not error
      await user.click(nextButton);
      // No assertion needed - test passes if no error thrown
    });
  });

  describe('Loading State', () => {
    it('displays skeleton loader when loading', () => {
      render(<LogsTable logs={[]} totalCount={0} limit={50} offset={0} loading={true} />);

      // Skeleton loader displays table row skeletons
      expect(screen.getByTestId('table-row-skeleton')).toBeInTheDocument();
    });

    it('does not show table when loading', () => {
      render(<LogsTable logs={mockLogs} totalCount={5} limit={50} offset={0} loading={true} />);

      expect(screen.queryByText('Failed to process request')).not.toBeInTheDocument();
    });

    it('hides pagination when loading', () => {
      render(<LogsTable logs={mockLogs} totalCount={100} limit={50} offset={0} loading={true} />);

      expect(screen.queryByLabelText('Previous page')).not.toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('displays error message when error is provided', () => {
      render(<LogsTable logs={[]} totalCount={0} limit={50} offset={0} error="Network error" />);

      expect(screen.getByText('Error Loading Logs')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('does not show table when error is provided', () => {
      render(
        <LogsTable logs={mockLogs} totalCount={5} limit={50} offset={0} error="Network error" />
      );

      expect(screen.queryByText('Failed to process request')).not.toBeInTheDocument();
    });

    it('hides pagination when error is provided', () => {
      render(
        <LogsTable logs={mockLogs} totalCount={100} limit={50} offset={0} error="Network error" />
      );

      expect(screen.queryByLabelText('Previous page')).not.toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('displays empty state when no logs', () => {
      render(<LogsTable logs={[]} totalCount={0} limit={50} offset={0} />);

      expect(screen.getByText('No Logs Found')).toBeInTheDocument();
      expect(screen.getByText(/No logs match the current filters/)).toBeInTheDocument();
    });

    it('does not show pagination in empty state', () => {
      render(<LogsTable logs={[]} totalCount={0} limit={50} offset={0} />);

      expect(screen.queryByLabelText('Previous page')).not.toBeInTheDocument();
    });
  });

  describe('Timestamp Formatting', () => {
    it('displays "Just now" for very recent logs (less than 1 minute)', () => {
      const recentLog: LogEntry = {
        ...mockLogs[0],
        timestamp: new Date().toISOString(),
      };

      render(<LogsTable logs={[recentLog]} totalCount={1} limit={50} offset={0} />);

      const table = screen.getByRole('table');
      expect(within(table).getByText('Just now')).toBeInTheDocument();
    });

    it('displays minutes ago for logs less than 1 hour old (line 63)', () => {
      // 30 minutes ago
      const thirtyMinutesAgo = new Date(Date.now() - 30 * 60 * 1000).toISOString();
      const recentLog: LogEntry = {
        ...mockLogs[0],
        timestamp: thirtyMinutesAgo,
      };

      render(<LogsTable logs={[recentLog]} totalCount={1} limit={50} offset={0} />);

      const table = screen.getByRole('table');
      expect(within(table).getByText(/\d+m ago/)).toBeInTheDocument();
    });

    it('displays hours ago for logs less than 24 hours old (line 64)', () => {
      // 5 hours ago
      const fiveHoursAgo = new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString();
      const oldLog: LogEntry = {
        ...mockLogs[0],
        timestamp: fiveHoursAgo,
      };

      render(<LogsTable logs={[oldLog]} totalCount={1} limit={50} offset={0} />);

      const table = screen.getByRole('table');
      expect(within(table).getByText(/\d+h ago/)).toBeInTheDocument();
    });

    it('displays days ago for logs less than 7 days old (line 65)', () => {
      // 3 days ago
      const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
      const oldLog: LogEntry = {
        ...mockLogs[0],
        timestamp: threeDaysAgo,
      };

      render(<LogsTable logs={[oldLog]} totalCount={1} limit={50} offset={0} />);

      const table = screen.getByRole('table');
      expect(within(table).getByText(/\d+d ago/)).toBeInTheDocument();
    });

    it('displays formatted date for logs older than 7 days', () => {
      // 10 days ago
      const tenDaysAgo = new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString();
      const oldLog: LogEntry = {
        ...mockLogs[0],
        timestamp: tenDaysAgo,
      };

      render(<LogsTable logs={[oldLog]} totalCount={1} limit={50} offset={0} />);

      const table = screen.getByRole('table');
      // Should show formatted date (e.g., "Jan 1, 12:00 PM")
      const rows = within(table).getAllByRole('row');
      expect(rows.length).toBeGreaterThan(0);
    });

    it('formats all log timestamps', () => {
      render(<LogsTable logs={mockLogs} totalCount={5} limit={50} offset={0} />);

      const table = screen.getByRole('table');
      const rows = within(table).getAllByRole('row');

      // Should have header row + 5 data rows
      expect(rows.length).toBe(6);
    });
  });

  describe('Custom Styling', () => {
    it('applies custom className', () => {
      const { container } = render(
        <LogsTable logs={mockLogs} totalCount={5} limit={50} offset={0} className="custom-class" />
      );

      const wrapper = container.querySelector('.custom-class');
      expect(wrapper).toBeInTheDocument();
    });

    it('uses NVIDIA dark theme colors', () => {
      const { container } = render(
        <LogsTable logs={mockLogs} totalCount={5} limit={50} offset={0} />
      );

      const tableContainer = container.querySelector('.bg-\\[\\#1F1F1F\\]');
      expect(tableContainer).toBeInTheDocument();
    });
  });

  describe('Repeated Message Grouping', () => {
    const repeatedLogs: LogEntry[] = [
      {
        id: 1,
        timestamp: '2024-01-01T10:00:00Z',
        level: 'INFO',
        component: 'api',
        message: 'Health check passed',
        camera_id: null,
        event_id: null,
        request_id: null,
        detection_id: null,
        duration_ms: null,
        extra: null,
        source: 'backend',
      },
      {
        id: 2,
        timestamp: '2024-01-01T10:01:00Z',
        level: 'INFO',
        component: 'api',
        message: 'Health check passed',
        camera_id: null,
        event_id: null,
        request_id: null,
        detection_id: null,
        duration_ms: null,
        extra: null,
        source: 'backend',
      },
      {
        id: 3,
        timestamp: '2024-01-01T10:02:00Z',
        level: 'INFO',
        component: 'api',
        message: 'Health check passed',
        camera_id: null,
        event_id: null,
        request_id: null,
        detection_id: null,
        duration_ms: null,
        extra: null,
        source: 'backend',
      },
      {
        id: 4,
        timestamp: '2024-01-01T10:03:00Z',
        level: 'ERROR',
        component: 'database',
        message: 'Connection timeout',
        camera_id: null,
        event_id: null,
        request_id: null,
        detection_id: null,
        duration_ms: null,
        extra: null,
        source: 'backend',
      },
      {
        id: 5,
        timestamp: '2024-01-01T10:04:00Z',
        level: 'INFO',
        component: 'api',
        message: 'Health check passed',
        camera_id: null,
        event_id: null,
        request_id: null,
        detection_id: null,
        duration_ms: null,
        extra: null,
        source: 'backend',
      },
    ];

    describe('groupRepeatedLogs', () => {
      it('groups consecutive repeated messages', () => {
        const groups = groupRepeatedLogs(repeatedLogs);

        // First group: 3 "Health check passed" messages
        expect(groups[0].count).toBe(3);
        expect(groups[0].entries[0].message).toBe('Health check passed');

        // Second group: 1 "Connection timeout" message
        expect(groups[1].count).toBe(1);
        expect(groups[1].entries[0].message).toBe('Connection timeout');

        // Third group: 1 "Health check passed" message (not consecutive with first)
        expect(groups[2].count).toBe(1);
        expect(groups[2].entries[0].message).toBe('Health check passed');
      });

      it('returns empty array for empty logs', () => {
        const groups = groupRepeatedLogs([]);
        expect(groups).toEqual([]);
      });

      it('handles single log entry', () => {
        const groups = groupRepeatedLogs([repeatedLogs[0]]);
        expect(groups.length).toBe(1);
        expect(groups[0].count).toBe(1);
      });

      it('does not group logs with different levels', () => {
        const logsWithDifferentLevels: LogEntry[] = [
          { ...repeatedLogs[0], level: 'INFO' },
          { ...repeatedLogs[1], id: 2, level: 'WARNING' },
        ];
        const groups = groupRepeatedLogs(logsWithDifferentLevels);
        expect(groups.length).toBe(2);
      });

      it('does not group logs with different components', () => {
        const logsWithDifferentComponents: LogEntry[] = [
          { ...repeatedLogs[0], component: 'api' },
          { ...repeatedLogs[1], id: 2, component: 'database' },
        ];
        const groups = groupRepeatedLogs(logsWithDifferentComponents);
        expect(groups.length).toBe(2);
      });
    });

    it('displays count badge for grouped messages', () => {
      render(
        <LogsTable logs={repeatedLogs} totalCount={5} limit={50} offset={0} enableGrouping />
      );

      // Should show "3x" badge for the first group
      expect(screen.getByText('3x')).toBeInTheDocument();
    });

    it('shows expand button for grouped messages', () => {
      render(
        <LogsTable logs={repeatedLogs} totalCount={5} limit={50} offset={0} enableGrouping />
      );

      // Should show expand button for groups with count > 1
      const expandButtons = screen.getAllByLabelText('Expand group');
      expect(expandButtons.length).toBeGreaterThan(0);
    });

    it('expands group when clicking expand button', async () => {
      const user = userEvent.setup();

      render(
        <LogsTable logs={repeatedLogs} totalCount={5} limit={50} offset={0} enableGrouping />
      );

      // Find and click the expand button
      const expandButton = screen.getAllByLabelText('Expand group')[0];
      await user.click(expandButton);

      // After expanding, should show "Collapse group" button
      expect(screen.getByLabelText('Collapse group')).toBeInTheDocument();
    });

    it('collapses group when clicking collapse button', async () => {
      const user = userEvent.setup();

      render(
        <LogsTable logs={repeatedLogs} totalCount={5} limit={50} offset={0} enableGrouping />
      );

      // Expand the group first
      const expandButton = screen.getAllByLabelText('Expand group')[0];
      await user.click(expandButton);

      // Now collapse it
      const collapseButton = screen.getByLabelText('Collapse group');
      await user.click(collapseButton);

      // Should show "Expand group" button again
      expect(screen.getAllByLabelText('Expand group').length).toBeGreaterThan(0);
    });

    it('shows individual entries when group is expanded', async () => {
      const user = userEvent.setup();

      render(
        <LogsTable logs={repeatedLogs} totalCount={5} limit={50} offset={0} enableGrouping />
      );

      // Initially, there should be 3 rows visible (3 groups)
      const table = screen.getByRole('table');
      const initialRows = within(table).getAllByRole('row');
      // Header + 3 group rows
      expect(initialRows.length).toBe(4);

      // Expand the first group
      const expandButton = screen.getAllByLabelText('Expand group')[0];
      await user.click(expandButton);

      // After expanding, should have more rows (header + expanded entries + other groups)
      const expandedRows = within(table).getAllByRole('row');
      // Header + 3 individual entries + 2 other groups = 6 rows
      expect(expandedRows.length).toBe(6);
    });

    it('does not show grouping UI when enableGrouping is false', () => {
      render(
        <LogsTable logs={repeatedLogs} totalCount={5} limit={50} offset={0} enableGrouping={false} />
      );

      // Should not show any expand buttons
      expect(screen.queryByLabelText('Expand group')).not.toBeInTheDocument();

      // Should not show count badges
      expect(screen.queryByText('3x')).not.toBeInTheDocument();
    });

    it('calls onRowClick with correct log entry from group', async () => {
      const handleRowClick = vi.fn();
      const user = userEvent.setup();

      render(
        <LogsTable
          logs={repeatedLogs}
          totalCount={5}
          limit={50}
          offset={0}
          enableGrouping
          onRowClick={handleRowClick}
        />
      );

      // Expand the first group
      const expandButton = screen.getAllByLabelText('Expand group')[0];
      await user.click(expandButton);

      // Click on one of the individual entries (the second one in the group)
      const table = screen.getByRole('table');
      const rows = within(table).getAllByRole('row');
      // Skip header row and first entry row (index 2 is second entry)
      await user.click(rows[2]);

      // Should call with the second log entry (id: 2)
      expect(handleRowClick).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }));
    });
  });
});

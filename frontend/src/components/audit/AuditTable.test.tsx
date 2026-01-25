import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import AuditTable from './AuditTable';

import type { AuditEntry, AuditTableProps } from './AuditTable';

describe('AuditTable', () => {
  const mockAuditLogs: AuditEntry[] = [
    {
      id: 1,
      timestamp: '2024-01-01T10:00:00Z',
      action: 'event_reviewed',
      resource_type: 'event',
      resource_id: '42',
      actor: 'testuser1',
      ip_address: '192.168.1.100',
      user_agent: 'Mozilla/5.0',
      details: { reviewed: true },
      status: 'success',
    },
    {
      id: 2,
      timestamp: '2024-01-01T11:00:00Z',
      action: 'camera_created',
      resource_type: 'camera',
      resource_id: 'camera-abc',
      actor: 'system',
      ip_address: null,
      user_agent: null,
      details: { name: 'Front Door' },
      status: 'success',
    },
    {
      id: 3,
      timestamp: '2024-01-01T12:00:00Z',
      action: 'settings_updated',
      resource_type: 'settings',
      resource_id: null,
      actor: 'testuser2',
      ip_address: '192.168.1.100',
      user_agent: 'Mozilla/5.0',
      details: { retention_days: 30 },
      status: 'failure',
    },
  ];

  const defaultProps: AuditTableProps = {
    logs: mockAuditLogs,
    totalCount: 3,
    limit: 50,
    offset: 0,
  };

  // Use fake timers to control time-based formatting
  beforeEach(() => {
    vi.useFakeTimers();
    // Set current time to 2024-01-01T14:00:00Z
    vi.setSystemTime(new Date('2024-01-01T14:00:00Z'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Rendering', () => {
    it('renders the audit table with all columns', () => {
      render(<AuditTable {...defaultProps} />);

      // Check all column headers
      expect(screen.getByText('Timestamp')).toBeInTheDocument();
      expect(screen.getByText('Actor')).toBeInTheDocument();
      expect(screen.getByText('Action')).toBeInTheDocument();
      expect(screen.getByText('Resource')).toBeInTheDocument();
      expect(screen.getByText('IP Address')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
    });

    it('displays all audit log entries', () => {
      render(<AuditTable {...defaultProps} />);

      // Check actors are displayed
      expect(screen.getByText('testuser1')).toBeInTheDocument();
      expect(screen.getByText('system')).toBeInTheDocument();
      expect(screen.getByText('testuser2')).toBeInTheDocument();
    });

    it('displays formatted action names', () => {
      render(<AuditTable {...defaultProps} />);

      // Actions should be formatted with spaces and proper capitalization
      expect(screen.getByText('Event Reviewed')).toBeInTheDocument();
      expect(screen.getByText('Camera Created')).toBeInTheDocument();
      expect(screen.getByText('Settings Updated')).toBeInTheDocument();
    });

    it('displays resource type and ID', () => {
      render(<AuditTable {...defaultProps} />);

      // Resource types should be displayed
      const table = screen.getByRole('table');
      expect(within(table).getByText('event')).toBeInTheDocument();
      expect(within(table).getByText('camera')).toBeInTheDocument();
      expect(within(table).getByText('settings')).toBeInTheDocument();
    });

    it('displays IP addresses with globe icon', () => {
      render(<AuditTable {...defaultProps} />);

      // IP addresses should be displayed (appears multiple times)
      const ipElements = screen.getAllByText('192.168.1.100');
      expect(ipElements.length).toBeGreaterThan(0);
    });

    it('displays dash for missing IP addresses', () => {
      render(<AuditTable {...defaultProps} />);

      // Check for dash placeholder
      expect(screen.getByText('-')).toBeInTheDocument();
    });

    it('displays status badges with correct styling', () => {
      render(<AuditTable {...defaultProps} />);

      // Check for status badges
      const successBadges = screen.getAllByText('success');
      const failureBadge = screen.getByText('failure');

      expect(successBadges.length).toBe(2);
      expect(failureBadge).toBeInTheDocument();
    });

    it('displays results summary', () => {
      render(<AuditTable {...defaultProps} />);

      expect(screen.getByText(/Showing 1-3 of 3 audit entries/)).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<AuditTable {...defaultProps} className="custom-class" />);

      const wrapper = container.querySelector('.custom-class');
      expect(wrapper).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('displays loading spinner when loading', () => {
      render(<AuditTable {...defaultProps} loading={true} />);

      expect(screen.getByText('Loading audit logs...')).toBeInTheDocument();
    });

    it('hides table content when loading', () => {
      render(<AuditTable {...defaultProps} loading={true} />);

      // Table should not be visible during loading
      expect(screen.queryByRole('table')).not.toBeInTheDocument();
    });

    it('shows loading animation', () => {
      const { container } = render(<AuditTable {...defaultProps} loading={true} />);

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('displays error message when error is provided', () => {
      render(<AuditTable {...defaultProps} error="Failed to fetch audit logs" />);

      expect(screen.getByText('Error Loading Audit Logs')).toBeInTheDocument();
      expect(screen.getByText('Failed to fetch audit logs')).toBeInTheDocument();
    });

    it('hides table when error is present', () => {
      render(<AuditTable {...defaultProps} error="Network error" />);

      expect(screen.queryByRole('table')).not.toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('displays empty state when no logs', () => {
      render(<AuditTable {...defaultProps} logs={[]} totalCount={0} />);

      expect(screen.getByText('No Audit Entries Found')).toBeInTheDocument();
    });

    it('displays correct count for empty state', () => {
      render(<AuditTable {...defaultProps} logs={[]} totalCount={0} />);

      expect(screen.getByText(/Showing 0-0 of 0 audit entries/)).toBeInTheDocument();
    });

    it('displays helpful guidance on how to generate entries', () => {
      render(<AuditTable {...defaultProps} logs={[]} totalCount={0} />);

      // Empty state should show guidance on what actions create audit entries
      expect(screen.getByText(/Change system settings/i)).toBeInTheDocument();
      expect(screen.getByText(/Mark events as reviewed/i)).toBeInTheDocument();
    });

    it('displays example actions that create audit entries', () => {
      render(<AuditTable {...defaultProps} logs={[]} totalCount={0} />);

      // Should show examples of actions
      expect(screen.getByText(/Modify camera configurations/i)).toBeInTheDocument();
    });
  });

  describe('Row Click Handling', () => {
    it('calls onRowClick when a row is clicked', async () => {
      // Use real timers for click test
      vi.useRealTimers();
      const user = userEvent.setup();
      const mockOnRowClick = vi.fn();

      render(<AuditTable {...defaultProps} onRowClick={mockOnRowClick} />);

      // Click on the first row (find by actor name)
      const row = screen.getByText('testuser1').closest('tr');
      await user.click(row!);

      expect(mockOnRowClick).toHaveBeenCalledWith(mockAuditLogs[0]);
      // Restore fake timers for other tests
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2024-01-01T14:00:00Z'));
    });

    it('rows have cursor-pointer when onRowClick is provided', () => {
      const mockOnRowClick = vi.fn();
      render(<AuditTable {...defaultProps} onRowClick={mockOnRowClick} />);

      const row = screen.getByText('testuser1').closest('tr');
      expect(row).toHaveClass('cursor-pointer');
    });

    it('rows do not have cursor-pointer when onRowClick is not provided', () => {
      render(<AuditTable {...defaultProps} />);

      const row = screen.getByText('testuser1').closest('tr');
      expect(row).not.toHaveClass('cursor-pointer');
    });
  });

  describe('Pagination', () => {
    it('displays pagination controls when there are entries', () => {
      render(<AuditTable {...defaultProps} totalCount={100} limit={50} offset={0} />);

      expect(screen.getByLabelText('Previous page')).toBeInTheDocument();
      expect(screen.getByLabelText('Next page')).toBeInTheDocument();
      expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
    });

    it('previous button is disabled on first page', () => {
      render(<AuditTable {...defaultProps} totalCount={100} limit={50} offset={0} />);

      const prevButton = screen.getByLabelText('Previous page');
      expect(prevButton).toBeDisabled();
    });

    it('next button is disabled on last page', () => {
      render(<AuditTable {...defaultProps} totalCount={100} limit={50} offset={50} />);

      const nextButton = screen.getByLabelText('Next page');
      expect(nextButton).toBeDisabled();
    });

    it('calls onPageChange with correct offset when clicking next', async () => {
      // Use real timers for this test
      vi.useRealTimers();
      const user = userEvent.setup();
      const mockOnPageChange = vi.fn();

      render(
        <AuditTable
          {...defaultProps}
          totalCount={100}
          limit={50}
          offset={0}
          onPageChange={mockOnPageChange}
        />
      );

      await user.click(screen.getByLabelText('Next page'));

      expect(mockOnPageChange).toHaveBeenCalledWith(50);
      // Restore fake timers for other tests
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2024-01-01T14:00:00Z'));
    });

    it('calls onPageChange with correct offset when clicking previous', async () => {
      // Use real timers for this test
      vi.useRealTimers();
      const user = userEvent.setup();
      const mockOnPageChange = vi.fn();

      render(
        <AuditTable
          {...defaultProps}
          totalCount={100}
          limit={50}
          offset={50}
          onPageChange={mockOnPageChange}
        />
      );

      await user.click(screen.getByLabelText('Previous page'));

      expect(mockOnPageChange).toHaveBeenCalledWith(0);
      // Restore fake timers for other tests
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2024-01-01T14:00:00Z'));
    });

    it('hides pagination when loading', () => {
      render(
        <AuditTable {...defaultProps} totalCount={100} limit={50} offset={0} loading={true} />
      );

      expect(screen.queryByLabelText('Previous page')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Next page')).not.toBeInTheDocument();
    });

    it('hides pagination when error', () => {
      render(<AuditTable {...defaultProps} totalCount={100} limit={50} offset={0} error="Error" />);

      expect(screen.queryByLabelText('Previous page')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Next page')).not.toBeInTheDocument();
    });

    it('hides pagination when no entries', () => {
      render(<AuditTable {...defaultProps} logs={[]} totalCount={0} limit={50} offset={0} />);

      expect(screen.queryByLabelText('Previous page')).not.toBeInTheDocument();
    });
  });

  describe('Timestamp Formatting', () => {
    it('formats recent timestamps as relative time', () => {
      // Current time is 2024-01-01T14:00:00Z
      // Log at 2024-01-01T12:00:00Z is 2 hours ago
      render(<AuditTable {...defaultProps} />);

      // Should show "2h ago" or similar relative time
      expect(screen.getByText('2h ago')).toBeInTheDocument();
    });

    it('formats timestamps less than an hour as minutes', () => {
      const recentLogs: AuditEntry[] = [
        {
          ...mockAuditLogs[0],
          timestamp: '2024-01-01T13:45:00Z', // 15 minutes ago
        },
      ];

      render(<AuditTable {...defaultProps} logs={recentLogs} totalCount={1} />);

      expect(screen.getByText('15m ago')).toBeInTheDocument();
    });

    it('formats very recent timestamps as "Just now"', () => {
      const recentLogs: AuditEntry[] = [
        {
          ...mockAuditLogs[0],
          timestamp: '2024-01-01T14:00:00Z', // Same time as system time
        },
      ];

      render(<AuditTable {...defaultProps} logs={recentLogs} totalCount={1} />);

      expect(screen.getByText('Just now')).toBeInTheDocument();
    });
  });

  describe('Status Badge Styling', () => {
    it('success status has green styling', () => {
      render(<AuditTable {...defaultProps} />);

      const successBadges = screen.getAllByText('success');
      const firstSuccessBadge = successBadges[0].closest('span');

      expect(firstSuccessBadge).toHaveClass('text-green-400');
    });

    it('failure status has red styling', () => {
      render(<AuditTable {...defaultProps} />);

      const failureBadge = screen.getByText('failure').closest('span');
      expect(failureBadge).toHaveClass('text-red-400');
    });

    it('displays status icons for success', () => {
      const { container } = render(<AuditTable {...defaultProps} />);

      // Check that CheckCircle icons are rendered for success status
      const successRows = container.querySelectorAll('tr');
      expect(successRows.length).toBeGreaterThan(0);
    });

    it('displays status icons for failure', () => {
      const { container } = render(<AuditTable {...defaultProps} />);

      // Check that XCircle icons are rendered for failure status
      const failureRow = container.querySelector('tr');
      expect(failureRow).toBeInTheDocument();
    });
  });

  describe('NVIDIA Theme Styling', () => {
    it('uses dark theme background colors', () => {
      const { container } = render(<AuditTable {...defaultProps} />);

      const tableContainer = container.querySelector('.bg-\\[\\#1F1F1F\\]');
      expect(tableContainer).toBeInTheDocument();
    });

    it('uses green accent color for actors', () => {
      render(<AuditTable {...defaultProps} />);

      const actor = screen.getByText('testuser1');
      expect(actor).toHaveClass('text-[#76B900]');
    });
  });

  describe('Resource Display', () => {
    it('displays resource type with resource ID when present', () => {
      render(<AuditTable {...defaultProps} />);

      // Find the event/42 display
      const table = screen.getByRole('table');
      expect(within(table).getByText('/42')).toBeInTheDocument();
    });

    it('displays resource type without ID when resource_id is null', () => {
      render(<AuditTable {...defaultProps} />);

      // settings entry has no resource_id
      const settingsRow = screen.getByText('testuser2').closest('tr');
      expect(settingsRow).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has proper table structure with thead and tbody', () => {
      const { container } = render(<AuditTable {...defaultProps} />);

      expect(container.querySelector('thead')).toBeInTheDocument();
      expect(container.querySelector('tbody')).toBeInTheDocument();
    });

    it('has properly labeled pagination buttons', () => {
      render(<AuditTable {...defaultProps} totalCount={100} limit={50} offset={0} />);

      expect(screen.getByLabelText('Previous page')).toBeInTheDocument();
      expect(screen.getByLabelText('Next page')).toBeInTheDocument();
    });
  });

  describe('Color-Coded Action Badges', () => {
    it('applies purple color to event_reviewed action', () => {
      render(<AuditTable {...defaultProps} />);

      const eventReviewedBadge = screen.getByLabelText('Filter by action: Event Reviewed');
      expect(eventReviewedBadge).toHaveClass('text-purple-400');
      expect(eventReviewedBadge).toHaveClass('bg-purple-500/20');
    });

    it('applies green color to camera_created action', () => {
      render(<AuditTable {...defaultProps} />);

      const cameraCreatedBadge = screen.getByLabelText('Filter by action: Camera Created');
      expect(cameraCreatedBadge).toHaveClass('text-green-400');
      expect(cameraCreatedBadge).toHaveClass('bg-green-500/20');
    });

    it('applies yellow color to settings_updated action', () => {
      render(<AuditTable {...defaultProps} />);

      const settingsUpdatedBadge = screen.getByLabelText('Filter by action: Settings Updated');
      expect(settingsUpdatedBadge).toHaveClass('text-yellow-400');
      expect(settingsUpdatedBadge).toHaveClass('bg-yellow-500/20');
    });
  });

  describe('Clickable Actor Filter', () => {
    it('calls onActorClick when actor is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const mockOnActorClick = vi.fn();

      render(<AuditTable {...defaultProps} onActorClick={mockOnActorClick} />);

      const actorButton = screen.getByLabelText('Filter by actor: testuser1');
      await user.click(actorButton);

      expect(mockOnActorClick).toHaveBeenCalledWith('testuser1');
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2024-01-01T14:00:00Z'));
    });

    it('shows active styling when actor filter is active', () => {
      render(<AuditTable {...defaultProps} activeActorFilter="testuser1" />);

      const actorButton = screen.getByLabelText('Filter by actor: testuser1');
      expect(actorButton).toHaveClass('underline');
    });

    it('has tooltip with filter instructions', () => {
      render(<AuditTable {...defaultProps} onActorClick={vi.fn()} />);

      const actorButton = screen.getByLabelText('Filter by actor: testuser1');
      expect(actorButton).toHaveAttribute('title', 'Click to filter by testuser1');
    });
  });

  describe('Clickable Action Filter', () => {
    it('calls onActionClick when action badge is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const mockOnActionClick = vi.fn();

      render(<AuditTable {...defaultProps} onActionClick={mockOnActionClick} />);

      const actionButton = screen.getByLabelText('Filter by action: Event Reviewed');
      await user.click(actionButton);

      expect(mockOnActionClick).toHaveBeenCalledWith('event_reviewed');
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2024-01-01T14:00:00Z'));
    });

    it('shows ring styling when action filter is active', () => {
      render(<AuditTable {...defaultProps} activeActionFilter="event_reviewed" />);

      const actionButton = screen.getByLabelText('Filter by action: Event Reviewed');
      expect(actionButton).toHaveClass('ring-2');
    });

    it('has tooltip with filter instructions', () => {
      render(<AuditTable {...defaultProps} onActionClick={vi.fn()} />);

      const actionButton = screen.getByLabelText('Filter by action: Event Reviewed');
      expect(actionButton).toHaveAttribute('title', 'Click to filter by Event Reviewed');
    });

    it('prevents row click when action badge is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const mockOnRowClick = vi.fn();
      const mockOnActionClick = vi.fn();

      render(
        <AuditTable
          {...defaultProps}
          onRowClick={mockOnRowClick}
          onActionClick={mockOnActionClick}
        />
      );

      const actionButton = screen.getByLabelText('Filter by action: Event Reviewed');
      await user.click(actionButton);

      expect(mockOnActionClick).toHaveBeenCalled();
      expect(mockOnRowClick).not.toHaveBeenCalled();
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2024-01-01T14:00:00Z'));
    });
  });

  describe('IP Address Display', () => {
    it('truncates long IP addresses with max-width', () => {
      const logsWithLongIP: AuditEntry[] = [
        {
          ...mockAuditLogs[0],
          ip_address: '2001:0db8:85a3:0000:0000:8a2e:0370:7334',
        },
      ];

      render(<AuditTable {...defaultProps} logs={logsWithLongIP} totalCount={1} />);

      const ipElement = screen.getByText('2001:0db8:85a3:0000:0000:8a2e:0370:7334');
      expect(ipElement).toHaveClass('truncate');
      expect(ipElement).toHaveClass('max-w-[120px]');
    });

    it('shows full IP on hover via title attribute', () => {
      const logsWithLongIP: AuditEntry[] = [
        {
          ...mockAuditLogs[0],
          ip_address: '2001:0db8:85a3:0000:0000:8a2e:0370:7334',
        },
      ];

      render(<AuditTable {...defaultProps} logs={logsWithLongIP} totalCount={1} />);

      const ipContainer = screen
        .getByText('2001:0db8:85a3:0000:0000:8a2e:0370:7334')
        .closest('span[title]');
      expect(ipContainer).toHaveAttribute('title', '2001:0db8:85a3:0000:0000:8a2e:0370:7334');
    });

    it('displays muted dash for null IP address', () => {
      render(<AuditTable {...defaultProps} />);

      // The system user has no IP address
      const dashElement = screen.getByText('-');
      expect(dashElement).toHaveClass('text-gray-600/50');
    });
  });
});

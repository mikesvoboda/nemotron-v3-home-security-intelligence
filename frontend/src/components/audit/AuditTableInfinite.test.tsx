import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import AuditTableInfinite from './AuditTableInfinite';

import type { AuditEntry, AuditTableInfiniteProps } from './AuditTableInfinite';

describe('AuditTableInfinite', () => {
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

  const defaultProps: AuditTableInfiniteProps = {
    logs: mockAuditLogs,
    totalCount: 3,
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
      render(<AuditTableInfinite {...defaultProps} />);

      // Check all column headers
      expect(screen.getByText('Timestamp')).toBeInTheDocument();
      expect(screen.getByText('Actor')).toBeInTheDocument();
      expect(screen.getByText('Action')).toBeInTheDocument();
      expect(screen.getByText('Resource')).toBeInTheDocument();
      expect(screen.getByText('IP Address')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();
    });

    it('displays all audit log entries', () => {
      render(<AuditTableInfinite {...defaultProps} />);

      // Check actors are displayed
      expect(screen.getByText('testuser1')).toBeInTheDocument();
      expect(screen.getByText('system')).toBeInTheDocument();
      expect(screen.getByText('testuser2')).toBeInTheDocument();
    });

    it('displays formatted action names', () => {
      render(<AuditTableInfinite {...defaultProps} />);

      // Actions should be formatted with spaces and proper capitalization
      expect(screen.getByText('Event Reviewed')).toBeInTheDocument();
      expect(screen.getByText('Camera Created')).toBeInTheDocument();
      expect(screen.getByText('Settings Updated')).toBeInTheDocument();
    });

    it('displays resource type and ID', () => {
      render(<AuditTableInfinite {...defaultProps} />);

      // Resource types should be displayed
      const table = screen.getByRole('table');
      expect(within(table).getByText('event')).toBeInTheDocument();
      expect(within(table).getByText('camera')).toBeInTheDocument();
      expect(within(table).getByText('settings')).toBeInTheDocument();
    });

    it('displays results summary with current and total counts', () => {
      render(<AuditTableInfinite {...defaultProps} />);

      expect(screen.getByText(/Showing 3 of 3 audit entries/)).toBeInTheDocument();
    });

    it('displays partial results summary when loading more', () => {
      render(<AuditTableInfinite {...defaultProps} totalCount={100} />);

      expect(screen.getByText(/Showing 3 of 100 audit entries/)).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(
        <AuditTableInfinite {...defaultProps} className="custom-class" />
      );

      const wrapper = container.querySelector('.custom-class');
      expect(wrapper).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('displays loading spinner when loading initially', () => {
      render(<AuditTableInfinite {...defaultProps} loading={true} />);

      expect(screen.getByText('Loading audit logs...')).toBeInTheDocument();
    });

    it('hides table content when loading initially', () => {
      render(<AuditTableInfinite {...defaultProps} loading={true} />);

      // Table should not be visible during loading
      expect(screen.queryByRole('table')).not.toBeInTheDocument();
    });

    it('shows loading animation', () => {
      const { container } = render(<AuditTableInfinite {...defaultProps} loading={true} />);

      const spinner = container.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });
  });

  describe('Loading More State', () => {
    it('displays loading indicator when loading more pages', () => {
      render(<AuditTableInfinite {...defaultProps} loadingMore={true} hasMore={true} />);

      expect(screen.getByText('Loading more...')).toBeInTheDocument();
    });

    it('keeps table visible while loading more pages', () => {
      render(<AuditTableInfinite {...defaultProps} loadingMore={true} hasMore={true} />);

      expect(screen.getByRole('table')).toBeInTheDocument();
    });
  });

  describe('Error State', () => {
    it('displays error message when error is provided', () => {
      render(<AuditTableInfinite {...defaultProps} error="Failed to fetch audit logs" />);

      expect(screen.getByText('Error Loading Audit Logs')).toBeInTheDocument();
      expect(screen.getByText('Failed to fetch audit logs')).toBeInTheDocument();
    });

    it('hides table when error is present', () => {
      render(<AuditTableInfinite {...defaultProps} error="Network error" />);

      expect(screen.queryByRole('table')).not.toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('displays empty state when no logs', () => {
      render(<AuditTableInfinite {...defaultProps} logs={[]} totalCount={0} />);

      expect(screen.getByText('No Audit Entries Found')).toBeInTheDocument();
    });

    it('displays correct count for empty state', () => {
      render(<AuditTableInfinite {...defaultProps} logs={[]} totalCount={0} />);

      expect(screen.getByText(/Showing 0 of 0 audit entries/)).toBeInTheDocument();
    });

    it('displays helpful guidance on how to generate entries', () => {
      render(<AuditTableInfinite {...defaultProps} logs={[]} totalCount={0} />);

      // Empty state should show guidance on what actions create audit entries
      expect(screen.getByText(/Change system settings/i)).toBeInTheDocument();
      expect(screen.getByText(/Mark events as reviewed/i)).toBeInTheDocument();
    });
  });

  describe('Row Click Handling', () => {
    it('calls onRowClick when a row is clicked', async () => {
      // Use real timers for click test
      vi.useRealTimers();
      const user = userEvent.setup();
      const mockOnRowClick = vi.fn();

      render(<AuditTableInfinite {...defaultProps} onRowClick={mockOnRowClick} />);

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
      render(<AuditTableInfinite {...defaultProps} onRowClick={mockOnRowClick} />);

      const row = screen.getByText('testuser1').closest('tr');
      expect(row).toHaveClass('cursor-pointer');
    });

    it('rows do not have cursor-pointer when onRowClick is not provided', () => {
      render(<AuditTableInfinite {...defaultProps} />);

      const row = screen.getByText('testuser1').closest('tr');
      expect(row).not.toHaveClass('cursor-pointer');
    });
  });

  describe('Infinite Scroll Controls', () => {
    it('displays "Load More" button when hasMore is true', () => {
      render(<AuditTableInfinite {...defaultProps} hasMore={true} totalCount={100} />);

      expect(screen.getByText('Load More')).toBeInTheDocument();
    });

    it('displays "All audit entries loaded" when hasMore is false', () => {
      render(<AuditTableInfinite {...defaultProps} hasMore={false} />);

      expect(screen.getByText('All audit entries loaded')).toBeInTheDocument();
    });

    it('hides infinite scroll controls when loading initially', () => {
      render(<AuditTableInfinite {...defaultProps} loading={true} hasMore={true} />);

      expect(screen.queryByText('Load More')).not.toBeInTheDocument();
    });

    it('hides infinite scroll controls when there is an error', () => {
      render(<AuditTableInfinite {...defaultProps} error="Error" hasMore={true} />);

      expect(screen.queryByText('Load More')).not.toBeInTheDocument();
    });

    it('hides infinite scroll controls when there are no entries', () => {
      render(<AuditTableInfinite {...defaultProps} logs={[]} totalCount={0} hasMore={false} />);

      expect(screen.queryByText('All audit entries loaded')).not.toBeInTheDocument();
    });

    it('calls onLoadMore when Load More button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const mockOnLoadMore = vi.fn();

      render(
        <AuditTableInfinite
          {...defaultProps}
          hasMore={true}
          totalCount={100}
          onLoadMore={mockOnLoadMore}
        />
      );

      await user.click(screen.getByText('Load More'));

      expect(mockOnLoadMore).toHaveBeenCalled();
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2024-01-01T14:00:00Z'));
    });
  });

  describe('Timestamp Formatting', () => {
    it('formats recent timestamps as relative time', () => {
      // Current time is 2024-01-01T14:00:00Z
      // Log at 2024-01-01T12:00:00Z is 2 hours ago
      render(<AuditTableInfinite {...defaultProps} />);

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

      render(<AuditTableInfinite {...defaultProps} logs={recentLogs} totalCount={1} />);

      expect(screen.getByText('15m ago')).toBeInTheDocument();
    });

    it('formats very recent timestamps as "Just now"', () => {
      const recentLogs: AuditEntry[] = [
        {
          ...mockAuditLogs[0],
          timestamp: '2024-01-01T14:00:00Z', // Same time as system time
        },
      ];

      render(<AuditTableInfinite {...defaultProps} logs={recentLogs} totalCount={1} />);

      expect(screen.getByText('Just now')).toBeInTheDocument();
    });
  });

  describe('Status Badge Styling', () => {
    it('success status has green styling', () => {
      render(<AuditTableInfinite {...defaultProps} />);

      const successBadges = screen.getAllByText('success');
      const firstSuccessBadge = successBadges[0].closest('span');

      expect(firstSuccessBadge).toHaveClass('text-green-400');
    });

    it('failure status has red styling', () => {
      render(<AuditTableInfinite {...defaultProps} />);

      const failureBadge = screen.getByText('failure').closest('span');
      expect(failureBadge).toHaveClass('text-red-400');
    });
  });

  describe('NVIDIA Theme Styling', () => {
    it('uses dark theme background colors', () => {
      const { container } = render(<AuditTableInfinite {...defaultProps} />);

      const tableContainer = container.querySelector('.bg-\\[\\#1F1F1F\\]');
      expect(tableContainer).toBeInTheDocument();
    });

    it('uses green accent color for actors', () => {
      render(<AuditTableInfinite {...defaultProps} />);

      const actor = screen.getByText('testuser1');
      expect(actor).toHaveClass('text-[#76B900]');
    });
  });

  describe('Clickable Actor Filter', () => {
    it('calls onActorClick when actor is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const mockOnActorClick = vi.fn();

      render(<AuditTableInfinite {...defaultProps} onActorClick={mockOnActorClick} />);

      const actorButton = screen.getByLabelText('Filter by actor: testuser1');
      await user.click(actorButton);

      expect(mockOnActorClick).toHaveBeenCalledWith('testuser1');
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2024-01-01T14:00:00Z'));
    });

    it('shows active styling when actor filter is active', () => {
      render(<AuditTableInfinite {...defaultProps} activeActorFilter="testuser1" />);

      const actorButton = screen.getByLabelText('Filter by actor: testuser1');
      expect(actorButton).toHaveClass('underline');
    });

    it('has tooltip with filter instructions', () => {
      render(<AuditTableInfinite {...defaultProps} onActorClick={vi.fn()} />);

      const actorButton = screen.getByLabelText('Filter by actor: testuser1');
      expect(actorButton).toHaveAttribute('title', 'Click to filter by testuser1');
    });
  });

  describe('Clickable Action Filter', () => {
    it('calls onActionClick when action badge is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const mockOnActionClick = vi.fn();

      render(<AuditTableInfinite {...defaultProps} onActionClick={mockOnActionClick} />);

      const actionButton = screen.getByLabelText('Filter by action: Event Reviewed');
      await user.click(actionButton);

      expect(mockOnActionClick).toHaveBeenCalledWith('event_reviewed');
      vi.useFakeTimers();
      vi.setSystemTime(new Date('2024-01-01T14:00:00Z'));
    });

    it('shows ring styling when action filter is active', () => {
      render(<AuditTableInfinite {...defaultProps} activeActionFilter="event_reviewed" />);

      const actionButton = screen.getByLabelText('Filter by action: Event Reviewed');
      expect(actionButton).toHaveClass('ring-2');
    });

    it('prevents row click when action badge is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const mockOnRowClick = vi.fn();
      const mockOnActionClick = vi.fn();

      render(
        <AuditTableInfinite
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

  describe('Color-Coded Action Badges', () => {
    it('applies purple color to event_reviewed action', () => {
      render(<AuditTableInfinite {...defaultProps} />);

      const eventReviewedBadge = screen.getByLabelText('Filter by action: Event Reviewed');
      expect(eventReviewedBadge).toHaveClass('text-purple-400');
      expect(eventReviewedBadge).toHaveClass('bg-purple-500/20');
    });

    it('applies green color to camera_created action', () => {
      render(<AuditTableInfinite {...defaultProps} />);

      const cameraCreatedBadge = screen.getByLabelText('Filter by action: Camera Created');
      expect(cameraCreatedBadge).toHaveClass('text-green-400');
      expect(cameraCreatedBadge).toHaveClass('bg-green-500/20');
    });

    it('applies yellow color to settings_updated action', () => {
      render(<AuditTableInfinite {...defaultProps} />);

      const settingsUpdatedBadge = screen.getByLabelText('Filter by action: Settings Updated');
      expect(settingsUpdatedBadge).toHaveClass('text-yellow-400');
      expect(settingsUpdatedBadge).toHaveClass('bg-yellow-500/20');
    });
  });

  describe('Load More Ref (for IntersectionObserver)', () => {
    it('renders sentinel div with loadMoreRef when hasMore is true', () => {
      render(
        <AuditTableInfinite
          {...defaultProps}
          hasMore={true}
          totalCount={100}
          loadMoreRef={{ current: null }}
        />
      );

      // The Load More button container should exist
      expect(screen.getByText('Load More').closest('div')).toBeInTheDocument();
    });
  });
});

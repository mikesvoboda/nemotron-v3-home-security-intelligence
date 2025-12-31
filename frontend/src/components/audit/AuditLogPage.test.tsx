import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import AuditLogPage from './AuditLogPage';
import * as api from '../../services/api';

import type { AuditLogListResponse, AuditLogStats } from '../../services/api';

// Mock API module
vi.mock('../../services/api');

describe('AuditLogPage', () => {
  const mockAuditLogs = [
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

  const mockAuditResponse: AuditLogListResponse = {
    logs: mockAuditLogs,
    count: 3,
    limit: 50,
    offset: 0,
  };

  const mockEmptyResponse: AuditLogListResponse = {
    logs: [],
    count: 0,
    limit: 50,
    offset: 0,
  };

  const mockStats: AuditLogStats = {
    total_logs: 100,
    logs_today: 5,
    by_action: {
      event_reviewed: 50,
      camera_created: 30,
      settings_updated: 20,
    },
    by_resource_type: {
      event: 50,
      camera: 30,
      settings: 20,
    },
    by_status: {
      success: 95,
      failure: 5,
    },
    recent_actors: ['admin', 'system', 'api'],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchAuditLogs).mockResolvedValue(mockAuditResponse);
    vi.mocked(api.fetchAuditStats).mockResolvedValue(mockStats);
  });

  describe('Rendering', () => {
    it('renders the audit log page header', async () => {
      render(<AuditLogPage />);

      expect(screen.getByText('Audit Log')).toBeInTheDocument();
      expect(
        screen.getByText(
          'Review security-sensitive operations and system activity across all resources'
        )
      ).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.queryByText('Loading audit logs...')).not.toBeInTheDocument();
      });
    });

    it('displays loading state initially', async () => {
      render(<AuditLogPage />);

      expect(screen.getByText('Loading audit logs...')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.queryByText('Loading audit logs...')).not.toBeInTheDocument();
      });
    });

    it('displays audit logs after loading', async () => {
      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // Check actors are displayed
      expect(screen.getByText('system')).toBeInTheDocument();

      // Check actions are displayed in table (may appear multiple times in stats and table)
      const table = screen.getByRole('table');
      expect(within(table).getByText('Event Reviewed')).toBeInTheDocument();
      expect(within(table).getByText('Camera Created')).toBeInTheDocument();
    });

    it('displays audit entry count', async () => {
      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText(/Showing 1-3 of 3 audit entries/)).toBeInTheDocument();
      });
    });

    it('displays status badges', async () => {
      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // Check for success and failure status badges
      const successBadges = screen.getAllByText('success');
      const failureBadges = screen.getAllByText('failure');
      expect(successBadges.length).toBe(2);
      expect(failureBadges.length).toBe(1);
    });

    it('displays resource type and ID', async () => {
      render(<AuditLogPage />);

      // Wait for table to load
      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // Check resource types are displayed in the table
      const table = screen.getByRole('table');
      // Use getAllByText since resource types may appear multiple times
      expect(within(table).getAllByText(/event/).length).toBeGreaterThan(0);
      expect(within(table).getAllByText(/camera/).length).toBeGreaterThan(0);
      expect(within(table).getAllByText(/settings/).length).toBeGreaterThan(0);
    });
  });

  describe('Statistics Cards', () => {
    it('displays stats cards with data', async () => {
      render(<AuditLogPage />);

      // Wait for stats to load (value appears when loading is complete)
      await waitFor(() => {
        expect(screen.getByText('100')).toBeInTheDocument(); // total_logs
      });

      // Stats cards should show values
      expect(screen.getByText('Total Audit Entries')).toBeInTheDocument();
      expect(screen.getByText('Entries Today')).toBeInTheDocument();
      expect(screen.getByText('Successful Operations')).toBeInTheDocument();
      expect(screen.getByText('95')).toBeInTheDocument(); // success count
      expect(screen.getByText('Failed Operations')).toBeInTheDocument();
    });

    it('displays action breakdown', async () => {
      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('Actions by Type')).toBeInTheDocument();
      });

      expect(screen.getByText('50')).toBeInTheDocument(); // event_reviewed count
    });
  });

  describe('Empty State', () => {
    it('shows friendly placeholder when no audit logs exist', async () => {
      vi.mocked(api.fetchAuditLogs).mockResolvedValue(mockEmptyResponse);

      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('No Audit Entries Found')).toBeInTheDocument();
      });

      expect(
        screen.getByText('No audit logs match the current filters')
      ).toBeInTheDocument();
    });
  });

  describe('Filtering', () => {
    it('displays filter toggle button', async () => {
      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      expect(screen.getByText('Show Filters')).toBeInTheDocument();
    });

    it('shows filters when toggle is clicked', async () => {
      const user = userEvent.setup();
      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      expect(screen.getByText('Hide Filters')).toBeInTheDocument();
      expect(screen.getByLabelText('Action')).toBeInTheDocument();
      expect(screen.getByLabelText('Resource Type')).toBeInTheDocument();
      expect(screen.getByLabelText('Actor')).toBeInTheDocument();
      expect(screen.getByLabelText('Status')).toBeInTheDocument();
    });

    it('filters by action type', async () => {
      const user = userEvent.setup();
      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // Show filters
      await user.click(screen.getByText('Show Filters'));

      // Select an action filter
      const actionSelect = screen.getByLabelText('Action');
      await user.selectOptions(actionSelect, 'event_reviewed');

      // Verify the API was called with the filter
      await waitFor(() => {
        expect(api.fetchAuditLogs).toHaveBeenCalledWith(
          expect.objectContaining({ action: 'event_reviewed' })
        );
      });
    });

    it('filters by status', async () => {
      const user = userEvent.setup();
      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // Show filters
      await user.click(screen.getByText('Show Filters'));

      // Select a status filter
      const statusSelect = screen.getByLabelText('Status');
      await user.selectOptions(statusSelect, 'failure');

      // Verify the API was called with the filter
      await waitFor(() => {
        expect(api.fetchAuditLogs).toHaveBeenCalledWith(
          expect.objectContaining({ status: 'failure' })
        );
      });
    });

    it('clears all filters', async () => {
      const user = userEvent.setup();
      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // Show filters and apply one
      await user.click(screen.getByText('Show Filters'));
      const statusSelect = screen.getByLabelText('Status');
      await user.selectOptions(statusSelect, 'success');

      // Clear filters
      await user.click(screen.getByText('Clear All Filters'));

      // Verify the API was called without filters
      await waitFor(() => {
        expect(api.fetchAuditLogs).toHaveBeenLastCalledWith(
          expect.objectContaining({
            action: undefined,
            status: undefined,
          })
        );
      });
    });
  });

  describe('Pagination', () => {
    it('displays pagination controls when there are multiple pages', async () => {
      vi.mocked(api.fetchAuditLogs).mockResolvedValue({
        ...mockAuditResponse,
        count: 100,
      });

      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Previous page')).toBeInTheDocument();
      expect(screen.getByLabelText('Next page')).toBeInTheDocument();
      expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
    });

    it('navigates to next page', async () => {
      vi.mocked(api.fetchAuditLogs).mockResolvedValue({
        ...mockAuditResponse,
        count: 100,
      });

      const user = userEvent.setup();
      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      await user.click(screen.getByLabelText('Next page'));

      await waitFor(() => {
        expect(api.fetchAuditLogs).toHaveBeenCalledWith(
          expect.objectContaining({ offset: 50 })
        );
      });
    });

    it('previous button is disabled on first page', async () => {
      vi.mocked(api.fetchAuditLogs).mockResolvedValue({
        ...mockAuditResponse,
        count: 100,
      });

      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      const prevButton = screen.getByLabelText('Previous page');
      expect(prevButton).toBeDisabled();
    });
  });

  describe('Detail Modal', () => {
    it('opens detail modal when row is clicked', async () => {
      const user = userEvent.setup();
      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // Click on a row - find by actor text and click the row
      const userCells = screen.getAllByText('testuser1');
      await user.click(userCells[0].closest('tr')!);

      // Modal should open with details
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Check the modal shows the action as dialog title
      const dialog = screen.getByRole('dialog');
      expect(within(dialog).getByText('Event Reviewed')).toBeInTheDocument();
    });

    it('closes detail modal when close button is clicked', async () => {
      const user = userEvent.setup();
      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // Open modal
      const userCells = screen.getAllByText('testuser1');
      await user.click(userCells[0].closest('tr')!);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Close modal - find button within dialog and use first one (X button in header)
      const dialog = screen.getByRole('dialog');
      const closeButtons = within(dialog).getAllByLabelText('Close modal');
      await user.click(closeButtons[0]);

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('displays error message when fetching audit logs fails', async () => {
      vi.mocked(api.fetchAuditLogs).mockRejectedValue(new Error('Network error'));

      render(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('Error Loading Audit Logs')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('handles stats fetch errors gracefully', async () => {
      vi.mocked(api.fetchAuditStats).mockRejectedValue(new Error('Stats fetch failed'));

      render(<AuditLogPage />);

      // Should still load audit logs
      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });
    });
  });

  describe('API Calls', () => {
    it('fetches audit logs on mount', async () => {
      render(<AuditLogPage />);

      await waitFor(() => {
        expect(api.fetchAuditLogs).toHaveBeenCalledWith({
          limit: 50,
          offset: 0,
        });
      });
    });

    it('fetches audit stats on mount', async () => {
      render(<AuditLogPage />);

      await waitFor(() => {
        expect(api.fetchAuditStats).toHaveBeenCalled();
      });
    });
  });
});

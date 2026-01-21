import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import AuditLogPage from './AuditLogPage';
import * as api from '../../services/api';

import type { AuditLogListResponse, AuditLogStats } from '../../services/api';

// Base time for consistent testing (2024-01-15T10:00:00Z)
const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

// Mock API module
vi.mock('../../services/api');

// Create a new QueryClient for each test
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: Infinity,
        staleTime: Infinity,
      },
    },
  });
}

// Create a wrapper with Router and React Query for testing
function createWrapper() {
  const queryClient = createTestQueryClient();
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

// Helper function to render with Router and React Query
function renderWithProviders(ui: React.ReactElement) {
  return render(ui, { wrapper: createWrapper() });
}

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
    items: mockAuditLogs,
    pagination: {
      total: 3,
      limit: 50,
      offset: 0,
      has_more: false,
      next_cursor: null,
    },
  };

  const mockEmptyResponse: AuditLogListResponse = {
    items: [],
    pagination: {
      total: 0,
      limit: 50,
      offset: 0,
      has_more: false,
      next_cursor: null,
    },
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
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
    vi.clearAllMocks();
    vi.mocked(api.fetchAuditLogs).mockResolvedValue(mockAuditResponse);
    vi.mocked(api.fetchAuditStats).mockResolvedValue(mockStats);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Rendering', () => {
    it('renders the audit log page header', async () => {
      renderWithProviders(<AuditLogPage />);

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

    it('displays info box explaining what creates audit entries', async () => {
      renderWithProviders(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading audit logs...')).not.toBeInTheDocument();
      });

      // Info box should explain what actions create audit entries
      expect(screen.getByText(/What gets logged/i)).toBeInTheDocument();
      expect(screen.getByText(/Settings changes/i)).toBeInTheDocument();
      expect(screen.getByText(/Event reviews/i)).toBeInTheDocument();
      expect(screen.getByText(/AI re-evaluations/i)).toBeInTheDocument();
    });

    it('displays loading state initially', async () => {
      renderWithProviders(<AuditLogPage />);

      expect(screen.getByText('Loading audit logs...')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.queryByText('Loading audit logs...')).not.toBeInTheDocument();
      });
    });

    it('displays audit logs after loading', async () => {
      renderWithProviders(<AuditLogPage />);

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
      renderWithProviders(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText(/Showing 3 of 3 audit entries/)).toBeInTheDocument();
      });
    });

    it('displays status badges', async () => {
      renderWithProviders(<AuditLogPage />);

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
      renderWithProviders(<AuditLogPage />);

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
      renderWithProviders(<AuditLogPage />);

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
      renderWithProviders(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('Actions by Type')).toBeInTheDocument();
      });

      expect(screen.getByText('50')).toBeInTheDocument(); // event_reviewed count
    });

    it('clicking "Successful Operations" card filters by status=success', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

      // Wait for stats to load
      await waitFor(() => {
        expect(screen.getByText('Successful Operations')).toBeInTheDocument();
      });

      // Click on the Successful Operations card
      const successCard = screen.getByText('Successful Operations').closest('[role="button"]');
      expect(successCard).toBeInTheDocument();
      await user.click(successCard!);

      // Verify the API was called with status=success filter
      await waitFor(() => {
        expect(api.fetchAuditLogs).toHaveBeenCalledWith(
          expect.objectContaining({ status: 'success' })
        );
      });
    });

    it('clicking "Failed Operations" card filters by status=failure', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

      // Wait for stats to load
      await waitFor(() => {
        expect(screen.getByText('Failed Operations')).toBeInTheDocument();
      });

      // Click on the Failed Operations card
      const failureCard = screen.getByText('Failed Operations').closest('[role="button"]');
      expect(failureCard).toBeInTheDocument();
      await user.click(failureCard!);

      // Verify the API was called with status=failure filter
      await waitFor(() => {
        expect(api.fetchAuditLogs).toHaveBeenCalledWith(
          expect.objectContaining({ status: 'failure' })
        );
      });
    });

    it('clicking "Total Audit Entries" card clears all filters', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

      // Wait for stats to load
      await waitFor(() => {
        expect(screen.getByText('Total Audit Entries')).toBeInTheDocument();
      });

      // First apply a filter by clicking Success card
      const successCard = screen.getByText('Successful Operations').closest('[role="button"]');
      await user.click(successCard!);

      // Verify Success card is active (has ring-2 class)
      await waitFor(() => {
        expect(successCard).toHaveClass('ring-2');
      });

      // Then click Total to clear
      const totalCard = screen.getByText('Total Audit Entries').closest('[role="button"]');
      await user.click(totalCard!);

      // Verify Total card is now active and Success card is no longer active
      await waitFor(() => {
        expect(totalCard).toHaveClass('ring-2');
        expect(successCard).not.toHaveClass('ring-2');
      });
    });

    it('clicking "Entries Today" card filters by today\'s date', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

      // Wait for stats to load
      await waitFor(() => {
        expect(screen.getByText('Entries Today')).toBeInTheDocument();
      });

      // Click on the Entries Today card
      const todayCard = screen.getByText('Entries Today').closest('[role="button"]');
      expect(todayCard).toBeInTheDocument();
      await user.click(todayCard!);

      // Get today's date in YYYY-MM-DD format (using mocked system time)
      const today = '2024-01-15'; // BASE_TIME date

      // Verify the API was called with date filters for today
      await waitFor(() => {
        expect(api.fetchAuditLogs).toHaveBeenCalledWith(
          expect.objectContaining({
            start_date: today,
            end_date: today,
          })
        );
      });
    });

    it('clicking an action badge filters by that action', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

      // Wait for action badges to load
      await waitFor(() => {
        expect(screen.getByText('Actions by Type')).toBeInTheDocument();
      });

      // Find the "Actions by Type" stats card and get the badge within it
      const actionsSection = screen.getByText('Actions by Type').closest('div')?.parentElement;
      expect(actionsSection).toBeInTheDocument();
      const eventReviewedBadge = within(actionsSection!).getByRole('button', { name: /Event Reviewed/i });
      await user.click(eventReviewedBadge);

      // Verify the API was called with action filter
      await waitFor(() => {
        expect(api.fetchAuditLogs).toHaveBeenCalledWith(
          expect.objectContaining({ action: 'event_reviewed' })
        );
      });
    });

    it('clicking active stats card toggles off the filter', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

      // Wait for stats to load
      await waitFor(() => {
        expect(screen.getByText('Successful Operations')).toBeInTheDocument();
      });

      // Click to activate filter
      const successCard = screen.getByText('Successful Operations').closest('[role="button"]');
      await user.click(successCard!);

      // Verify card shows active state
      await waitFor(() => {
        expect(successCard).toHaveClass('ring-2');
      });

      // Click again to toggle off
      await user.click(successCard!);

      // Verify card no longer shows active state
      await waitFor(() => {
        expect(successCard).not.toHaveClass('ring-2');
      });
    });

    it('clicking active action badge toggles off the filter', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

      // Wait for action badges to load
      await waitFor(() => {
        expect(screen.getByText('Actions by Type')).toBeInTheDocument();
      });

      // Find the "Actions by Type" stats card and get the badge within it
      const actionsSection = screen.getByText('Actions by Type').closest('div')?.parentElement;
      expect(actionsSection).toBeInTheDocument();
      const eventReviewedBadge = within(actionsSection!).getByRole('button', { name: /Event Reviewed/i });

      // Click to activate filter - filter chip should appear
      await user.click(eventReviewedBadge);

      // Verify filter chip appears showing the active filter
      await waitFor(() => {
        expect(screen.getByText('Active filters:')).toBeInTheDocument();
      });

      // Click again to toggle off
      await user.click(eventReviewedBadge);

      // Verify filter chip is removed
      await waitFor(() => {
        expect(screen.queryByText('Active filters:')).not.toBeInTheDocument();
      });
    });

    it('stats cards have cursor pointer style', async () => {
      renderWithProviders(<AuditLogPage />);

      // Wait for stats to load
      await waitFor(() => {
        expect(screen.getByText('Successful Operations')).toBeInTheDocument();
      });

      // Check that cards have role="button" indicating they're clickable
      const successCard = screen.getByText('Successful Operations').closest('[role="button"]');
      expect(successCard).toBeInTheDocument();
      expect(successCard).toHaveClass('cursor-pointer');
    });

    it('active stats card shows visual selection ring', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

      // Wait for stats to load
      await waitFor(() => {
        expect(screen.getByText('Successful Operations')).toBeInTheDocument();
      });

      // Click to activate
      const successCard = screen.getByText('Successful Operations').closest('[role="button"]');
      await user.click(successCard!);

      // Check for active styling (ring class)
      await waitFor(() => {
        expect(successCard).toHaveClass('ring-2');
      });
    });

    it('clicking stats card auto-expands filter panel', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

      // Wait for stats to load
      await waitFor(() => {
        expect(screen.getByText('Successful Operations')).toBeInTheDocument();
      });

      // Filters should be hidden initially (Show Filters button visible)
      expect(screen.getByText('Show Filters')).toBeInTheDocument();

      // Click on a stats card
      const successCard = screen.getByText('Successful Operations').closest('[role="button"]');
      await user.click(successCard!);

      // Filter panel should auto-expand (Hide Filters button visible)
      await waitFor(() => {
        expect(screen.getByText('Hide Filters')).toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    it('shows friendly placeholder when no audit logs exist', async () => {
      vi.mocked(api.fetchAuditLogs).mockResolvedValue(mockEmptyResponse);

      renderWithProviders(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('No Audit Entries Found')).toBeInTheDocument();
      });

      // Empty state now includes helpful guidance
      expect(screen.getByText(/No audit logs match the current filters/i)).toBeInTheDocument();
      expect(screen.getByText(/Try these actions to generate entries/i)).toBeInTheDocument();
    });
  });

  describe('Filtering', () => {
    it('displays filter toggle button', async () => {
      renderWithProviders(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      expect(screen.getByText('Show Filters')).toBeInTheDocument();
    });

    it('shows filters when toggle is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

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
      renderWithProviders(<AuditLogPage />);

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
      renderWithProviders(<AuditLogPage />);

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
      renderWithProviders(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // Show filters and apply one
      await user.click(screen.getByText('Show Filters'));
      const statusSelect = screen.getByLabelText('Status');
      await user.selectOptions(statusSelect, 'success');

      // Verify filter is applied (Active badge appears)
      await waitFor(() => {
        expect(screen.getByText('Active')).toBeInTheDocument();
      });

      // Clear filters
      await user.click(screen.getByText('Clear All Filters'));

      // Verify the "Active" badge is gone (indicates filters are cleared)
      await waitFor(() => {
        expect(screen.queryByText('Active')).not.toBeInTheDocument();
      });
    });
  });

  describe('Infinite Scroll', () => {
    it('displays "All audit entries loaded" when no more pages', async () => {
      renderWithProviders(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // With has_more: false, should show all entries loaded message
      expect(screen.getByText('All audit entries loaded')).toBeInTheDocument();
    });

    it('displays "Load More" button when there are more pages', async () => {
      vi.mocked(api.fetchAuditLogs).mockResolvedValue({
        ...mockAuditResponse,
        pagination: {
          ...mockAuditResponse.pagination,
          total: 100,
          has_more: true,
          next_cursor: 'cursor123',
        },
      });

      renderWithProviders(<AuditLogPage />);

      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      expect(screen.getByText('Load More')).toBeInTheDocument();
    });

    it('hides pagination controls when loading initially', () => {
      renderWithProviders(<AuditLogPage />);

      // During initial loading, infinite scroll controls should not be visible
      expect(screen.queryByText('Load More')).not.toBeInTheDocument();
      expect(screen.queryByText('All audit entries loaded')).not.toBeInTheDocument();
    });
  });

  describe('Detail Modal', () => {
    it('opens detail modal when row is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

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
      renderWithProviders(<AuditLogPage />);

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

      renderWithProviders(<AuditLogPage />);

      // Wait for error to appear (React Query may retry before failing)
      await waitFor(() => {
        expect(screen.getByText('Error Loading Audit Logs')).toBeInTheDocument();
      }, { timeout: 3000 });

      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('handles stats fetch errors gracefully', async () => {
      vi.mocked(api.fetchAuditStats).mockRejectedValue(new Error('Stats fetch failed'));

      renderWithProviders(<AuditLogPage />);

      // Should still load audit logs
      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });
    });
  });

  describe('API Calls', () => {
    it('fetches audit logs on mount', async () => {
      renderWithProviders(<AuditLogPage />);

      await waitFor(() => {
        expect(api.fetchAuditLogs).toHaveBeenCalledWith(
          expect.objectContaining({
            limit: 50,
          })
        );
      });
    });

    it('fetches audit stats on mount', async () => {
      renderWithProviders(<AuditLogPage />);

      await waitFor(() => {
        expect(api.fetchAuditStats).toHaveBeenCalled();
      });
    });
  });

  describe('Clickable Table Filters', () => {
    it('clicking actor in table filters by that actor', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

      // Wait for table to load
      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // Find and click the actor button in the table
      const table = screen.getByRole('table');
      const actorButton = within(table).getByLabelText('Filter by actor: testuser1');
      await user.click(actorButton);

      // Verify the API was called with actor filter
      await waitFor(() => {
        expect(api.fetchAuditLogs).toHaveBeenCalledWith(
          expect.objectContaining({ actor: 'testuser1' })
        );
      });
    });

    it('clicking action badge in table filters by that action', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

      // Wait for table to load
      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // Find and click the action badge in the table
      const table = screen.getByRole('table');
      const actionButton = within(table).getByLabelText('Filter by action: Event Reviewed');
      await user.click(actionButton);

      // Verify the API was called with action filter
      await waitFor(() => {
        expect(api.fetchAuditLogs).toHaveBeenCalledWith(
          expect.objectContaining({ action: 'event_reviewed' })
        );
      });
    });
  });

  describe('Filter Chips', () => {
    it('shows filter chip when action filter is applied from table', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

      // Wait for table to load
      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // Click action badge in table
      const table = screen.getByRole('table');
      const actionButton = within(table).getByLabelText('Filter by action: Event Reviewed');
      await user.click(actionButton);

      // Verify filter chip appears
      await waitFor(() => {
        expect(screen.getByText('Active filters:')).toBeInTheDocument();
        expect(screen.getByLabelText(/Clear action filter: Event Reviewed/i)).toBeInTheDocument();
      });
    });

    it('shows filter chip when actor filter is applied from table', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

      // Wait for table to load
      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // Click actor in table
      const table = screen.getByRole('table');
      const actorButton = within(table).getByLabelText('Filter by actor: testuser1');
      await user.click(actorButton);

      // Verify filter chip appears
      await waitFor(() => {
        expect(screen.getByText('Active filters:')).toBeInTheDocument();
        expect(screen.getByLabelText(/Clear actor filter: testuser1/i)).toBeInTheDocument();
      });
    });

    it('clears filter when filter chip is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AuditLogPage />);

      // Wait for table to load
      await waitFor(() => {
        expect(screen.getByText('testuser1')).toBeInTheDocument();
      });

      // Click actor in table to apply filter
      const table = screen.getByRole('table');
      const actorButton = within(table).getByLabelText('Filter by actor: testuser1');
      await user.click(actorButton);

      // Verify filter chip appears
      await waitFor(() => {
        expect(screen.getByLabelText(/Clear actor filter: testuser1/i)).toBeInTheDocument();
      });

      // Click the filter chip to clear
      const clearButton = screen.getByLabelText(/Clear actor filter: testuser1/i);
      await user.click(clearButton);

      // Verify filter chip is gone (main assertion)
      await waitFor(() => {
        expect(screen.queryByText('Active filters:')).not.toBeInTheDocument();
      });
    });
  });
});

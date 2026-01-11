import { within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import EventTimeline from './EventTimeline';
import * as hooks from '../../hooks';
import * as useEventStreamHook from '../../hooks/useEventStream';
import * as api from '../../services/api';
import { renderWithProviders, screen, waitFor, userEvent } from '../../test-utils/renderWithProviders';

import type { Camera, Event, EventListResponse } from '../../services/api';
import type React from 'react';

// Mock API module
vi.mock('../../services/api');

// Mock useEventStream hook with factory function
vi.mock('../../hooks/useEventStream', () => ({
  useEventStream: vi.fn(),
}));

// Mock hooks module (for useEventsInfiniteQuery and useInfiniteScroll)
vi.mock('../../hooks', async () => {
  const actual = await vi.importActual('../../hooks');
  return {
    ...actual,
    useEventsInfiniteQuery: vi.fn(),
    useInfiniteScroll: vi.fn(),
  };
});

// Mock LiveActivitySection component
vi.mock('./LiveActivitySection', () => ({
  default: ({
    events,
    isConnected,
    onEventClick,
    maxItems,
  }: {
    events: Array<{ id: string; camera_name: string }>;
    isConnected: boolean;
    onEventClick?: (eventId: string) => void;
    maxItems: number;
  }) => (
    <div data-testid="live-activity-section">
      <h2>Live Activity</h2>
      <button
        type="button"
        data-testid="activity-feed"
        data-event-count={events.length}
        data-max-items={maxItems}
        data-is-connected={isConnected}
        data-camera-names={events.map((e) => e.camera_name).join(',')}
        onClick={() => onEventClick && events.length > 0 && onEventClick(events[0].id)}
      >
        Activity Feed
      </button>
      {!isConnected && <span>Disconnected</span>}
    </div>
  ),
}));

describe('EventTimeline', () => {
  const mockCameras: Camera[] = [
    {
      id: 'camera-1',
      name: 'Front Door',
      folder_path: '/path/to/front',
      status: 'online',
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T12:00:00Z',
    },
    {
      id: 'camera-2',
      name: 'Back Yard',
      folder_path: '/path/to/back',
      status: 'online',
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T12:00:00Z',
    },
  ];

  const mockEvents: Event[] = [
    {
      id: 1,
      camera_id: 'camera-1',
      started_at: '2024-01-01T10:00:00Z',
      ended_at: '2024-01-01T10:02:00Z',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Person detected near entrance',
      reviewed: false,
      detection_count: 5,
      notes: null,
    },
    {
      id: 2,
      camera_id: 'camera-2',
      started_at: '2024-01-01T11:00:00Z',
      ended_at: '2024-01-01T11:01:00Z',
      risk_score: 25,
      risk_level: 'low',
      summary: 'Cat walking through yard',
      reviewed: true,
      detection_count: 3,
      notes: null,
    },
    {
      id: 3,
      camera_id: 'camera-1',
      started_at: '2024-01-01T12:00:00Z',
      ended_at: null,
      risk_score: 90,
      risk_level: 'critical',
      summary: 'Unknown person at door',
      reviewed: false,
      detection_count: 8,
      notes: null,
    },
  ];

  // Mock WebSocket events for live activity
  const mockWsEvents = [
    {
      id: 'ws-event-1',
      camera_id: 'camera-1',
      camera_name: 'Front Door',
      risk_score: 80,
      risk_level: 'high' as const,
      summary: 'Live person detected',
      timestamp: '2024-01-01T12:30:00Z',
    },
  ];

  // Default mock return value for useEventsInfiniteQuery
  const mockInfiniteQueryReturn = {
    events: mockEvents,
    pages: [{ items: mockEvents, total_count: 3, pagination: { page: 1, per_page: 50, total_pages: 1 } }] as unknown as EventListResponse[],
    totalCount: 3,
    isLoading: false,
    isFetching: false,
    isFetchingNextPage: false,
    hasNextPage: false,
    fetchNextPage: vi.fn(),
    error: null,
    isError: false,
    refetch: vi.fn(),
  };

  // Mock ref for infinite scroll
  const mockLoadMoreRef = { current: null };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);

    // Mock useEventsInfiniteQuery hook
    vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue(mockInfiniteQueryReturn);

    // Mock useInfiniteScroll hook
    vi.mocked(hooks.useInfiniteScroll).mockReturnValue({ loadMoreRef: mockLoadMoreRef as unknown as React.RefObject<HTMLDivElement> });

    // Mock useEventStream hook
    vi.mocked(useEventStreamHook.useEventStream).mockReturnValue({
      events: mockWsEvents,
      isConnected: true,
      latestEvent: mockWsEvents[0],
      clearEvents: vi.fn(),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Rendering', () => {
    it('renders the timeline header', async () => {
      renderWithProviders(<EventTimeline />);

      expect(screen.getByText('Event Timeline')).toBeInTheDocument();
      expect(
        screen.getByText(/View and filter all security events from your cameras/)
      ).toBeInTheDocument();

      // Wait for async state updates to complete to avoid act() warnings
      await waitFor(() => {
        expect(screen.queryByText('Loading events...')).not.toBeInTheDocument();
      });
    });

    it('renders the Live Activity section', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByTestId('live-activity-section')).toBeInTheDocument();
      });

      expect(screen.getByRole('heading', { name: /live activity/i })).toBeInTheDocument();
    });

    it('renders Live Activity with WebSocket events', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        const activityFeed = screen.getByTestId('activity-feed');
        expect(activityFeed).toHaveAttribute('data-event-count', '1');
        expect(activityFeed).toHaveAttribute('data-camera-names', 'Front Door');
      });
    });

    it('shows disconnected indicator when WebSocket is not connected', async () => {
      vi.mocked(useEventStreamHook.useEventStream).mockReturnValue({
        events: [],
        isConnected: false,
        latestEvent: null,
        clearEvents: vi.fn(),
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText(/disconnected/i)).toBeInTheDocument();
      });
    });

    it('does not show disconnected indicator when WebSocket is connected', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.queryByText(/Loading events.../)).not.toBeInTheDocument();
      });

      expect(screen.queryByText(/disconnected/i)).not.toBeInTheDocument();
    });

    it('displays loading state initially with skeleton loaders', () => {
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        events: [],
        isLoading: true,
      });

      renderWithProviders(<EventTimeline />);

      expect(screen.getAllByTestId('event-card-skeleton').length).toBeGreaterThan(0);
    });

    it('displays events after loading', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      expect(screen.getByText('Cat walking through yard')).toBeInTheDocument();
      expect(screen.getByText('Unknown person at door')).toBeInTheDocument();
    });

    it('displays result count', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Showing 3 of 3 events')).toBeInTheDocument();
      });
    });

    it('displays infinite scroll sentinel element', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      expect(screen.getByTestId('infinite-scroll-sentinel')).toBeInTheDocument();
    });

    it('displays "All events loaded" when no more pages', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      expect(screen.getByText('All events loaded')).toBeInTheDocument();
    });

    it('displays loading indicator when fetching next page', async () => {
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        isFetchingNextPage: true,
        hasNextPage: true,
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Loading more events...')).toBeInTheDocument();
      });
    });
  });

  describe('Filtering', () => {
    it('shows filter button and toggles filter panel', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      // Filter panel should not be visible initially
      expect(screen.queryByLabelText('Camera')).not.toBeInTheDocument();

      // Click to show filters
      await user.click(screen.getByText('Show Filters'));

      // Filter panel should now be visible
      expect(screen.getByLabelText('Camera')).toBeInTheDocument();
      expect(screen.getByLabelText('Risk Level')).toBeInTheDocument();
      expect(screen.getByLabelText('Status')).toBeInTheDocument();
      expect(screen.getByLabelText('Start Date')).toBeInTheDocument();
      expect(screen.getByLabelText('End Date')).toBeInTheDocument();

      // Button text should change
      expect(screen.getByText('Hide Filters')).toBeInTheDocument();
    });

    it('filters events by camera', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const cameraSelect = screen.getByLabelText('Camera');
      await user.selectOptions(cameraSelect, 'camera-1');

      await waitFor(() => {
        expect(hooks.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({
            filters: expect.objectContaining({ camera_id: 'camera-1' }),
          })
        );
      });
    });

    it('filters events by risk level', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const riskSelect = screen.getByLabelText('Risk Level');
      await user.selectOptions(riskSelect, 'high');

      await waitFor(() => {
        expect(hooks.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({
            filters: expect.objectContaining({ risk_level: 'high' }),
          })
        );
      });
    });

    it('filters events by reviewed status', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const statusSelect = screen.getByLabelText('Status');
      await user.selectOptions(statusSelect, 'false');

      await waitFor(() => {
        expect(hooks.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({
            filters: expect.objectContaining({ reviewed: false }),
          })
        );
      });
    });

    it('filters events by date range', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const startDateInput = screen.getByLabelText('Start Date');
      const endDateInput = screen.getByLabelText('End Date');

      await user.type(startDateInput, '2024-01-01');
      await user.type(endDateInput, '2024-01-31');

      await waitFor(() => {
        expect(hooks.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({
            filters: expect.objectContaining({
              start_date: '2024-01-01',
              end_date: '2024-01-31',
            }),
          })
        );
      });
    });

    it('clears all filters', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      // Apply some filters
      const cameraSelect = screen.getByLabelText('Camera');
      await user.selectOptions(cameraSelect, 'camera-1');

      await waitFor(() => {
        expect(hooks.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({
            filters: expect.objectContaining({ camera_id: 'camera-1' }),
          })
        );
      });

      // Clear filters
      const clearButton = screen.getByText('Clear All Filters');
      await user.click(clearButton);

      await waitFor(() => {
        expect(hooks.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({
            filters: {},
          })
        );
      });
    });

    it('shows active filter indicator', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      // No active indicator initially
      expect(screen.queryByText('Active')).not.toBeInTheDocument();

      await user.click(screen.getByText('Show Filters'));

      const cameraSelect = screen.getByLabelText('Camera');
      await user.selectOptions(cameraSelect, 'camera-1');

      await waitFor(() => {
        expect(screen.getByText('Active')).toBeInTheDocument();
      });

      expect(screen.getByText('Filters active')).toBeInTheDocument();
    });

    it('filters events by object type', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const objectTypeSelect = screen.getByLabelText('Object Type');
      await user.selectOptions(objectTypeSelect, 'person');

      await waitFor(() => {
        expect(hooks.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({
            filters: expect.objectContaining({ object_type: 'person' }),
          })
        );
      });
    });

    it('displays object type filter dropdown with all options', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const objectTypeSelect = screen.getByLabelText('Object Type');
      expect(objectTypeSelect).toBeInTheDocument();

      // Check all options are present
      const options = within(objectTypeSelect).getAllByRole('option');
      expect(options).toHaveLength(6); // All Object Types + 5 specific types
      expect(
        within(objectTypeSelect).getByRole('option', { name: 'All Object Types' })
      ).toBeInTheDocument();
      expect(within(objectTypeSelect).getByRole('option', { name: 'Person' })).toBeInTheDocument();
      expect(within(objectTypeSelect).getByRole('option', { name: 'Vehicle' })).toBeInTheDocument();
      expect(within(objectTypeSelect).getByRole('option', { name: 'Animal' })).toBeInTheDocument();
      expect(within(objectTypeSelect).getByRole('option', { name: 'Package' })).toBeInTheDocument();
      expect(within(objectTypeSelect).getByRole('option', { name: 'Other' })).toBeInTheDocument();
    });

    it('clears object type filter with clear all filters button', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      // Apply object type filter
      const objectTypeSelect = screen.getByLabelText('Object Type');
      await user.selectOptions(objectTypeSelect, 'vehicle');

      await waitFor(() => {
        expect(hooks.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({
            filters: expect.objectContaining({ object_type: 'vehicle' }),
          })
        );
      });

      // Clear filters
      const clearButton = screen.getByText('Clear All Filters');
      await user.click(clearButton);

      await waitFor(() => {
        expect(hooks.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({
            filters: {},
          })
        );
      });
    });

    it('combines object type filter with other filters', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      // Apply camera filter
      const cameraSelect = screen.getByLabelText('Camera');
      await user.selectOptions(cameraSelect, 'camera-1');

      // Apply object type filter
      const objectTypeSelect = screen.getByLabelText('Object Type');
      await user.selectOptions(objectTypeSelect, 'animal');

      await waitFor(() => {
        expect(hooks.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({
            filters: expect.objectContaining({
              camera_id: 'camera-1',
              object_type: 'animal',
            }),
          })
        );
      });
    });
  });

  // Note: Client-side search has been removed in favor of full-text search only.
  // Full-text search functionality is tested in the "Full-text search" describe block below.

  describe('Infinite Scroll', () => {
    it('calls useInfiniteScroll with correct parameters', async () => {
      const mockFetchNextPage = vi.fn();
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        hasNextPage: true,
        fetchNextPage: mockFetchNextPage,
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(hooks.useInfiniteScroll).toHaveBeenCalledWith(
          expect.objectContaining({
            hasNextPage: true,
            isFetchingNextPage: false,
            fetchNextPage: mockFetchNextPage,
            rootMargin: '200px',
          })
        );
      });
    });

    it('does not display pagination controls', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Pagination controls should not exist with infinite scroll
      expect(screen.queryByLabelText('Previous page')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Next page')).not.toBeInTheDocument();
      expect(screen.queryByText(/Page \d+ of \d+/)).not.toBeInTheDocument();
    });
  });

  describe('Error Handling', () => {
    it('displays error message when fetching events fails', async () => {
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        events: [],
        isError: true,
        error: new Error('Network error'),
      });

      renderWithProviders(<EventTimeline />);

      // Wait for error state to be displayed
      await waitFor(() => {
        expect(screen.getByText('Error Loading Events')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('handles camera fetch errors gracefully', async () => {
      vi.mocked(api.fetchCameras).mockRejectedValue(new Error('Camera fetch failed'));

      renderWithProviders(<EventTimeline />);

      // Should still load events
      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Filter should still be available but with no camera options
      const user2 = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      await user2.click(screen.getByText('Show Filters'));

      const cameraSelect = screen.getByLabelText('Camera');
      const options = within(cameraSelect).getAllByRole('option');

      // Should only have "All Cameras" option
      expect(options).toHaveLength(1);
      expect(options[0]).toHaveTextContent('All Cameras');
    });
  });

  describe('Empty States', () => {
    it('shows empty state when no events exist', async () => {
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        events: [],
        totalCount: 0,
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      // Updated to match new EmptyState component text
      expect(screen.getByText(/No security events have been recorded yet/)).toBeInTheDocument();
    });

    it('shows filtered empty state when filters match no events', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Apply filter that returns no results
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        events: [],
        totalCount: 0,
      });

      await user.click(screen.getByText('Show Filters'));

      const riskSelect = screen.getByLabelText('Risk Level');
      await user.selectOptions(riskSelect, 'low');

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      // Updated to match new EmptyState component text
      expect(screen.getByText(/No events match your current filters/)).toBeInTheDocument();
    });

    it('shows "0 events" instead of confusing "1-0 of 0" when empty', async () => {
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        events: [],
        totalCount: 0,
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      // Should show "0 events" not "1-0 of 0 events"
      expect(screen.getByText('0 events')).toBeInTheDocument();
      expect(screen.queryByText(/1-0 of 0/)).not.toBeInTheDocument();
    });

    it('does not show infinite scroll status when empty', async () => {
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        events: [],
        totalCount: 0,
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      // Infinite scroll status should not be present when there are no events
      expect(screen.queryByTestId('infinite-scroll-sentinel')).not.toBeInTheDocument();
      expect(screen.queryByText('All events loaded')).not.toBeInTheDocument();
    });
  });

  describe('Event Card Integration', () => {
    it('calls onViewEventDetails when View Details is clicked', async () => {
      const handleViewDetails = vi.fn();
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      renderWithProviders(<EventTimeline onViewEventDetails={handleViewDetails} />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Find all "View Details" buttons (there are multiple events)
      // Events are sorted by most recent first (3, 2, 1), so first button is for event 3
      const viewButtons = screen.getAllByText('View Details');
      await user.click(viewButtons[0]);

      expect(handleViewDetails).toHaveBeenCalledWith(3);
    });

    it('displays camera names in event cards', async () => {
      renderWithProviders(<EventTimeline />);

      // Wait for events to load first
      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Camera names should appear after cameras are fetched
      // Use getAllByText since there are multiple events from the same camera
      await waitFor(() => {
        const frontDoorElements = screen.getAllByText('Front Door');
        expect(frontDoorElements.length).toBeGreaterThan(0);
      });

      const backYardElements = screen.getAllByText('Back Yard');
      expect(backYardElements.length).toBeGreaterThan(0);
    });

    it('shows "Unknown Camera" when camera not found', async () => {
      const eventsWithUnknownCamera: Event[] = [
        {
          id: 1,
          camera_id: 'unknown-camera-id',
          started_at: '2024-01-01T10:00:00Z',
          ended_at: null,
          risk_score: 50,
          risk_level: 'medium',
          summary: 'Event from unknown camera',
          reviewed: false,
          detection_count: 1,
          notes: null,
        },
      ];

      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        events: eventsWithUnknownCamera,
        totalCount: 1,
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Unknown Camera')).toBeInTheDocument();
      });
    });
  });

  describe('Bulk Actions', () => {
    it('displays bulk action controls when events are loaded', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Should show select all button
      expect(screen.getByText('Select all')).toBeInTheDocument();
    });

    it('toggles selection for individual events', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Find all selection checkboxes (one for each event)
      const checkboxButtons = screen.getAllByLabelText(/Select event \d+/);
      expect(checkboxButtons.length).toBe(3);

      // Click first checkbox to select
      await user.click(checkboxButtons[0]);

      // Should show selection count
      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeInTheDocument();
      });

      // Should show "Mark as Reviewed" button
      expect(screen.getByText('Mark as Reviewed')).toBeInTheDocument();
    });

    it('selects all events when clicking select all', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Click select all button
      const selectAllButton = screen.getByText('Select all');
      await user.click(selectAllButton);

      // Should show all events selected
      await waitFor(() => {
        expect(screen.getByText('3 selected')).toBeInTheDocument();
      });
    });

    it('deselects all events when clicking select all again', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Click select all twice
      const selectAllButton = screen.getByText('Select all');
      await user.click(selectAllButton);

      await waitFor(() => {
        expect(screen.getByText('3 selected')).toBeInTheDocument();
      });

      const deselectAllButton = screen.getByLabelText('Deselect all events');
      await user.click(deselectAllButton);

      // Should show select all again
      await waitFor(() => {
        expect(screen.getByText('Select all')).toBeInTheDocument();
      });
    });

    it('marks selected events as reviewed', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const mockRefetch = vi.fn();
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        refetch: mockRefetch,
      });

      // Mock bulkUpdateEvents for successful update
      // Events are sorted by most recent first (3, 2, 1), so selecting first two = [3, 2]
      vi.mocked(api.bulkUpdateEvents).mockResolvedValue({
        successful: [3, 2],
        failed: [],
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Select first two events (events are sorted by most recent first: 3, 2, 1)
      const checkboxButtons = screen.getAllByLabelText(/Select event \d+/);
      await user.click(checkboxButtons[0]);
      await user.click(checkboxButtons[1]);

      await waitFor(() => {
        expect(screen.getByText('2 selected')).toBeInTheDocument();
      });

      // Click mark as reviewed
      const markAsReviewedButton = screen.getByText('Mark as Reviewed');
      await user.click(markAsReviewedButton);

      // Should call bulkUpdateEvents with selected event IDs (sorted by most recent: 3, 2)
      await waitFor(() => {
        expect(api.bulkUpdateEvents).toHaveBeenCalledWith([3, 2], { reviewed: true });
      });

      // Should call refetch
      await waitFor(() => {
        expect(mockRefetch).toHaveBeenCalled();
      });

      // Should clear selections
      await waitFor(() => {
        expect(screen.getByText('Select all')).toBeInTheDocument();
      });
    });

    it('shows loading state during bulk update', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      // Mock slow bulkUpdateEvents
      vi.mocked(api.bulkUpdateEvents).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(
              () =>
                resolve({
                  successful: [1],
                  failed: [],
                }),
              100
            )
          )
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Select an event
      const checkboxButtons = screen.getAllByLabelText(/Select event \d+/);
      await user.click(checkboxButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeInTheDocument();
      });

      // Click mark as reviewed
      const markAsReviewedButton = screen.getByText('Mark as Reviewed');
      await user.click(markAsReviewedButton);

      // Should show loading state - both buttons show "Updating..." when loading
      await waitFor(() => {
        expect(screen.getAllByText('Updating...')).toHaveLength(2);
      });

      // Both buttons should be disabled during loading
      const markReviewedButton = screen.getByRole('button', {
        name: /Mark.*selected events as reviewed/,
      });
      const markNotReviewedButton = screen.getByRole('button', {
        name: /Mark.*selected events as not reviewed/,
      });
      expect(markReviewedButton).toBeDisabled();
      expect(markNotReviewedButton).toBeDisabled();
    });

    it('handles bulk update errors gracefully', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const mockRefetch = vi.fn();
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        refetch: mockRefetch,
      });

      // Mock bulkUpdateEvents to return partial failure
      // Events sorted by most recent: 3, 2, 1 - selecting first two gives [3, 2]
      vi.mocked(api.bulkUpdateEvents).mockResolvedValue({
        successful: [3],
        failed: [{ id: 2, error: 'Network error' }],
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Select two events (events sorted by most recent first: 3, 2, 1)
      const checkboxButtons = screen.getAllByLabelText(/Select event \d+/);
      await user.click(checkboxButtons[0]);
      await user.click(checkboxButtons[1]);

      // Click mark as reviewed
      const markAsReviewedButton = screen.getByText('Mark as Reviewed');
      await user.click(markAsReviewedButton);

      // Should call bulkUpdateEvents (events sorted: 3, 2)
      await waitFor(() => {
        expect(api.bulkUpdateEvents).toHaveBeenCalledWith([3, 2], { reviewed: true });
      });

      // Should still call refetch even on partial failure
      await waitFor(() => {
        expect(mockRefetch).toHaveBeenCalled();
      });
    });

    it('does not show bulk action button when no events selected', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Should show select all but not mark as reviewed button
      expect(screen.getByText('Select all')).toBeInTheDocument();
      expect(screen.queryByText('Mark as Reviewed')).not.toBeInTheDocument();
    });

    it('clears selection when toggling individual checkbox off', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Select an event (events sorted by most recent first: 3, 2, 1)
      const checkboxButtons = screen.getAllByLabelText(/Select event \d+/);
      await user.click(checkboxButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeInTheDocument();
      });

      // Deselect the same event (first event is ID 3 due to sorting)
      const deselectButton = screen.getByLabelText('Deselect event 3');
      await user.click(deselectButton);

      // Should show select all again
      await waitFor(() => {
        expect(screen.getByText('Select all')).toBeInTheDocument();
      });
    });

    it('shows Mark Not Reviewed button when events are selected', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Select an event
      const checkboxButtons = screen.getAllByLabelText(/Select event \d+/);
      await user.click(checkboxButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeInTheDocument();
      });

      // Should show both "Mark as Reviewed" and "Mark Not Reviewed" buttons
      expect(screen.getByText('Mark as Reviewed')).toBeInTheDocument();
      expect(screen.getByText('Mark Not Reviewed')).toBeInTheDocument();
    });

    it('marks selected events as not reviewed', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const mockRefetch = vi.fn();
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        refetch: mockRefetch,
      });

      // Mock bulkUpdateEvents for successful update
      // Events sorted by most recent: 3, 2, 1 - selecting first two gives [3, 2]
      vi.mocked(api.bulkUpdateEvents).mockResolvedValue({
        successful: [3, 2],
        failed: [],
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Select first two events (events sorted by most recent first: 3, 2, 1)
      const checkboxButtons = screen.getAllByLabelText(/Select event \d+/);
      await user.click(checkboxButtons[0]);
      await user.click(checkboxButtons[1]);

      await waitFor(() => {
        expect(screen.getByText('2 selected')).toBeInTheDocument();
      });

      // Click mark as not reviewed
      const markAsNotReviewedButton = screen.getByText('Mark Not Reviewed');
      await user.click(markAsNotReviewedButton);

      // Should call bulkUpdateEvents with reviewed: false (events sorted: 3, 2)
      await waitFor(() => {
        expect(api.bulkUpdateEvents).toHaveBeenCalledWith([3, 2], { reviewed: false });
      });

      // Should call refetch
      await waitFor(() => {
        expect(mockRefetch).toHaveBeenCalled();
      });

      // Should clear selections
      await waitFor(() => {
        expect(screen.getByText('Select all')).toBeInTheDocument();
      });
    });

    it('shows loading state during bulk mark as not reviewed', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      // Mock slow bulkUpdateEvents
      vi.mocked(api.bulkUpdateEvents).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(
              () =>
                resolve({
                  successful: [1],
                  failed: [],
                }),
              100
            )
          )
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Select an event
      const checkboxButtons = screen.getAllByLabelText(/Select event \d+/);
      await user.click(checkboxButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeInTheDocument();
      });

      // Click mark as not reviewed
      const markAsNotReviewedButton = screen.getByText('Mark Not Reviewed');
      await user.click(markAsNotReviewedButton);

      // Should show loading state - there are two Updating... buttons (both are disabled)
      await waitFor(() => {
        expect(screen.getAllByText('Updating...')).toHaveLength(2);
      });

      // Both buttons should be disabled
      const markReviewedButton = screen.getByRole('button', {
        name: /Mark.*selected events as reviewed/,
      });
      const markNotReviewedButton = screen.getByRole('button', {
        name: /Mark.*selected events as not reviewed/,
      });
      expect(markReviewedButton).toBeDisabled();
      expect(markNotReviewedButton).toBeDisabled();
    });

    it('handles bulk mark as not reviewed errors gracefully', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const mockRefetch = vi.fn();
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        refetch: mockRefetch,
      });

      // Mock bulkUpdateEvents to return partial failure
      // Events sorted by most recent: 3, 2, 1 - selecting first two gives [3, 2]
      vi.mocked(api.bulkUpdateEvents).mockResolvedValue({
        successful: [3],
        failed: [{ id: 2, error: 'Network error' }],
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Select two events (events sorted by most recent first: 3, 2, 1)
      const checkboxButtons = screen.getAllByLabelText(/Select event \d+/);
      await user.click(checkboxButtons[0]);
      await user.click(checkboxButtons[1]);

      // Click mark as not reviewed
      const markAsNotReviewedButton = screen.getByText('Mark Not Reviewed');
      await user.click(markAsNotReviewedButton);

      // Should call bulkUpdateEvents with reviewed: false (events sorted: 3, 2)
      await waitFor(() => {
        expect(api.bulkUpdateEvents).toHaveBeenCalledWith([3, 2], { reviewed: false });
      });

      // Should still call refetch even on partial failure
      await waitFor(() => {
        expect(mockRefetch).toHaveBeenCalled();
      });
    });

    it('does not show Mark Not Reviewed button when no events selected', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Should show select all but not Mark Not Reviewed button
      expect(screen.getByText('Select all')).toBeInTheDocument();
      expect(screen.queryByText('Mark Not Reviewed')).not.toBeInTheDocument();
    });
  });

  describe('Risk Summary Badges', () => {
    it('displays risk summary badges with correct counts', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Check that risk badges are displayed
      // Our mock data has: 1 high (75), 1 low (25), 1 critical (90)
      await waitFor(() => {
        expect(screen.getByText('1', { selector: '.text-red-400' })).toBeInTheDocument(); // Critical
      });
      expect(screen.getByText('1', { selector: '.text-orange-400' })).toBeInTheDocument(); // High
      expect(screen.getByText('1', { selector: '.text-green-400' })).toBeInTheDocument(); // Low
    });

    it('updates risk summary badges when filters are applied', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      // Mock filtered response with only high risk events
      const highRiskEvents: Event[] = [
        {
          id: 1,
          camera_id: 'camera-1',
          started_at: '2024-01-01T10:00:00Z',
          ended_at: '2024-01-01T10:02:00Z',
          risk_score: 75,
          risk_level: 'high',
          summary: 'Person detected near entrance',
          reviewed: false,
          detection_count: 5,
          notes: null,
        },
      ];

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Update mock to return filtered events
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        events: highRiskEvents,
        totalCount: 1,
      });

      await user.click(screen.getByText('Show Filters'));

      const riskSelect = screen.getByLabelText('Risk Level');
      await user.selectOptions(riskSelect, 'high');

      // Should only show high risk count - wait for critical badge to disappear
      await waitFor(() => {
        expect(screen.getByText('1', { selector: '.text-orange-400' })).toBeInTheDocument(); // High
        expect(screen.queryByText('1', { selector: '.text-red-400' })).not.toBeInTheDocument(); // Critical
        expect(screen.queryByText('1', { selector: '.text-green-400' })).not.toBeInTheDocument(); // Low
      });
    });

    // Test removed: Client-side search has been replaced with full-text search only
    // Risk badges now reflect server-side filtered results, not client-side search

    it('does not display risk badges when loading', () => {
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        events: [],
        isLoading: true,
      });

      renderWithProviders(<EventTimeline />);

      // Should show loading state with skeleton loaders
      expect(screen.getAllByTestId('event-card-skeleton').length).toBeGreaterThan(0);

      // Should not show risk badges during loading
      expect(screen.queryByText('Critical')).not.toBeInTheDocument();
      expect(screen.queryByText('High')).not.toBeInTheDocument();
      expect(screen.queryByText('Medium')).not.toBeInTheDocument();
      expect(screen.queryByText('Low')).not.toBeInTheDocument();
    });

    it('does not display risk badges when there is an error', async () => {
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        events: [],
        isError: true,
        error: new Error('Network error'),
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Error Loading Events')).toBeInTheDocument();
      });

      // Should not show risk badges on error
      expect(screen.queryByText('Critical')).not.toBeInTheDocument();
      expect(screen.queryByText('High')).not.toBeInTheDocument();
      expect(screen.queryByText('Medium')).not.toBeInTheDocument();
      expect(screen.queryByText('Low')).not.toBeInTheDocument();
    });

    it('does not display risk badges when no events are found', async () => {
      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        events: [],
        totalCount: 0,
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      // Should not show risk badges when empty
      expect(screen.queryByText('Critical')).not.toBeInTheDocument();
      expect(screen.queryByText('High')).not.toBeInTheDocument();
      expect(screen.queryByText('Medium')).not.toBeInTheDocument();
      expect(screen.queryByText('Low')).not.toBeInTheDocument();
    });

    it('only displays badges for risk levels that have events', async () => {
      // Mock events with only medium risk
      const mediumRiskEvents: Event[] = [
        {
          id: 1,
          camera_id: 'camera-1',
          started_at: '2024-01-01T10:00:00Z',
          ended_at: '2024-01-01T10:02:00Z',
          risk_score: 50,
          risk_level: 'medium',
          summary: 'Person detected',
          reviewed: false,
          detection_count: 5,
          notes: null,
        },
        {
          id: 2,
          camera_id: 'camera-1',
          started_at: '2024-01-01T11:00:00Z',
          ended_at: '2024-01-01T11:02:00Z',
          risk_score: 45,
          risk_level: 'medium',
          summary: 'Vehicle detected',
          reviewed: false,
          detection_count: 3,
          notes: null,
        },
      ];

      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        events: mediumRiskEvents,
        totalCount: 2,
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected')).toBeInTheDocument();
      });

      // Should only show medium risk badge with count of 2
      await waitFor(() => {
        expect(screen.getByText('2', { selector: '.text-yellow-400' })).toBeInTheDocument(); // Medium
      });

      // Should not show other risk levels
      expect(screen.queryByText('Critical')).not.toBeInTheDocument();
      expect(screen.queryByText('High')).not.toBeInTheDocument();
      expect(screen.queryByText('Low')).not.toBeInTheDocument();
    });

    it('correctly counts multiple events of the same risk level', async () => {
      // Mock events with multiple events per risk level
      const multipleEvents: Event[] = [
        {
          id: 1,
          camera_id: 'camera-1',
          started_at: '2024-01-01T10:00:00Z',
          ended_at: '2024-01-01T10:02:00Z',
          risk_score: 90,
          risk_level: 'critical',
          summary: 'Critical event 1',
          reviewed: false,
          detection_count: 5,
          notes: null,
        },
        {
          id: 2,
          camera_id: 'camera-1',
          started_at: '2024-01-01T11:00:00Z',
          ended_at: '2024-01-01T11:02:00Z',
          risk_score: 95,
          risk_level: 'critical',
          summary: 'Critical event 2',
          reviewed: false,
          detection_count: 3,
          notes: null,
        },
        {
          id: 3,
          camera_id: 'camera-1',
          started_at: '2024-01-01T12:00:00Z',
          ended_at: '2024-01-01T12:02:00Z',
          risk_score: 85,
          risk_level: 'critical',
          summary: 'Critical event 3',
          reviewed: false,
          detection_count: 7,
          notes: null,
        },
      ];

      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        events: multipleEvents,
        totalCount: 3,
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Critical event 1')).toBeInTheDocument();
      });

      // Should show critical risk badge with count of 3
      await waitFor(() => {
        expect(screen.getByText('3', { selector: '.text-red-400' })).toBeInTheDocument(); // Critical
      });
    });

    it('uses risk_level from event when available, falls back to calculated level', async () => {
      // Mock events where some have risk_level and some don't
      const mixedEvents: Event[] = [
        {
          id: 1,
          camera_id: 'camera-1',
          started_at: '2024-01-01T10:00:00Z',
          ended_at: '2024-01-01T10:02:00Z',
          risk_score: 75,
          risk_level: 'high', // Explicitly set
          summary: 'Event with explicit level',
          reviewed: false,
          detection_count: 5,
          notes: null,
        },
        {
          id: 2,
          camera_id: 'camera-1',
          started_at: '2024-01-01T11:00:00Z',
          ended_at: '2024-01-01T11:02:00Z',
          risk_score: 70, // Should calculate to "high"
          risk_level: null,
          summary: 'Event without explicit level',
          reviewed: false,
          detection_count: 3,
          notes: null,
        },
      ];

      vi.mocked(hooks.useEventsInfiniteQuery).mockReturnValue({
        ...mockInfiniteQueryReturn,
        events: mixedEvents,
        totalCount: 2,
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Event with explicit level')).toBeInTheDocument();
      });

      // Should show high risk badge with count of 2 (both events are high risk)
      await waitFor(() => {
        expect(screen.getByText('2', { selector: '.text-orange-400' })).toBeInTheDocument(); // High
      });
    });
  });

  describe('URL Parameter Filtering', () => {
    it('applies risk_level filter from URL parameter', async () => {
      renderWithProviders(<EventTimeline />, { route: '/timeline?risk_level=high' });

      await waitFor(() => {
        expect(hooks.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({
            filters: expect.objectContaining({ risk_level: 'high' }),
          })
        );
      });

      // Filter panel should be visible
      expect(screen.getByLabelText('Risk Level')).toBeInTheDocument();
    });

    it('applies camera filter from URL parameter', async () => {
      renderWithProviders(<EventTimeline />, { route: '/timeline?camera=camera-1' });

      await waitFor(() => {
        expect(hooks.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({
            filters: expect.objectContaining({ camera_id: 'camera-1' }),
          })
        );
      });
    });

    it('applies both camera and risk_level filters from URL parameters', async () => {
      renderWithProviders(<EventTimeline />, {
        route: '/timeline?camera=camera-1&risk_level=critical',
      });

      await waitFor(() => {
        expect(hooks.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({
            filters: expect.objectContaining({
              camera_id: 'camera-1',
              risk_level: 'critical',
            }),
          })
        );
      });
    });

    it('shows filter panel when risk_level URL parameter is present', async () => {
      renderWithProviders(<EventTimeline />, { route: '/timeline?risk_level=medium' });

      await waitFor(() => {
        expect(screen.getByLabelText('Risk Level')).toBeInTheDocument();
      });

      // Filter panel should be visible (showing Hide Filters button)
      expect(screen.getByText('Hide Filters')).toBeInTheDocument();
    });
  });

  describe('Event Detail Modal', () => {
    it('opens modal when clicking on event card', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Click on the event summary text (part of the card, not a button)
      const summaryText = screen.getByText('Person detected near entrance');
      await user.click(summaryText);

      // Modal should open - check for modal title (camera name)
      await waitFor(() => {
        // The modal should display the camera name as title
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    it('closes modal when close button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Open modal by clicking on event
      const summaryText = screen.getByText('Person detected near entrance');
      await user.click(summaryText);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Close modal
      const closeButton = screen.getByLabelText('Close modal');
      await user.click(closeButton);

      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });

    it('event cards are clickable with cursor-pointer', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Find event cards by their role (they should have role="button" since onClick is provided)
      const cardButtons = screen.getAllByRole('button', {
        name: /View details for event from/,
      });
      expect(cardButtons.length).toBeGreaterThan(0);
    });

    it('View Details button calls onViewEventDetails when provided', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      const handleViewDetails = vi.fn();
      renderWithProviders(<EventTimeline onViewEventDetails={handleViewDetails} />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Click View Details button
      const viewDetailsButtons = screen.getAllByText('View Details');
      await user.click(viewDetailsButtons[0]);

      // onViewEventDetails should be called (events are sorted by most recent first,
      // so first button corresponds to event id 3 with latest timestamp)
      expect(handleViewDetails).toHaveBeenCalledWith(3);
    });
  });
});

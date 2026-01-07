import { within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import EventTimeline from './EventTimeline';
import * as useEventStreamHook from '../../hooks/useEventStream';
import * as api from '../../services/api';
import { renderWithProviders, screen, waitFor, userEvent } from '../../test-utils/renderWithProviders';

import type { Camera, Event, EventListResponse } from '../../services/api';

// Mock API module
vi.mock('../../services/api');

// Mock useEventStream hook with factory function
vi.mock('../../hooks/useEventStream', () => ({
  useEventStream: vi.fn(),
}));

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

  const mockEventsResponse: EventListResponse = {
    events: mockEvents,
    count: 3,
    limit: 20,
    offset: 0,
  };

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

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

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

    it('displays loading state initially with skeleton loaders', async () => {
      renderWithProviders(<EventTimeline />);

      expect(screen.getAllByTestId('event-card-skeleton').length).toBeGreaterThan(0);

      // Wait for loading to complete to avoid act() warnings
      await waitFor(() => {
        expect(screen.queryByTestId('event-card-skeleton')).not.toBeInTheDocument();
      });
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
        expect(screen.getByText('Showing 1-3 of 3 events')).toBeInTheDocument();
      });
    });

    it('displays pagination controls', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByLabelText('Previous page')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Next page')).toBeInTheDocument();
      expect(screen.getByText('Page 1 of 1')).toBeInTheDocument();
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
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ camera_id: 'camera-1', offset: 0 }), expect.anything());
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
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ risk_level: 'high', offset: 0 }), expect.anything());
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
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ reviewed: false, offset: 0 }), expect.anything());
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
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({
            start_date: '2024-01-01',
            end_date: '2024-01-31',
            offset: 0,
          }), expect.anything());
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
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ camera_id: 'camera-1' }), expect.anything());
      });

      // Clear filters
      const clearButton = screen.getByText('Clear All Filters');
      await user.click(clearButton);

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith({ limit: 20, offset: 0 }, expect.anything());
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
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ object_type: 'person', offset: 0 }), expect.anything());
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
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ object_type: 'vehicle' }), expect.anything());
      });

      // Clear filters
      const clearButton = screen.getByText('Clear All Filters');
      await user.click(clearButton);

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith({ limit: 20, offset: 0 }, expect.anything());
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
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({
            camera_id: 'camera-1',
            object_type: 'animal',
            offset: 0,
          }), expect.anything());
      });
    });
  });

  describe('Search', () => {
    it('filters events by search query', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search summaries...');
      await user.type(searchInput, 'cat');

      // Should only show the cat event
      await waitFor(() => {
        expect(screen.getByText('Cat walking through yard')).toBeInTheDocument();
      });

      expect(screen.queryByText('Person detected near entrance')).not.toBeInTheDocument();
      expect(screen.queryByText('Unknown person at door')).not.toBeInTheDocument();
    });

    it('clears search query', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search summaries...');
      await user.type(searchInput, 'cat');

      await waitFor(() => {
        expect(screen.queryByText('Person detected near entrance')).not.toBeInTheDocument();
      });

      // Click clear button
      const clearButton = screen.getByLabelText('Clear search');
      await user.click(clearButton);

      // All events should be visible again
      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });
    });

    it('shows no results message when search has no matches', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search summaries...');
      await user.type(searchInput, 'nonexistent');

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      // Updated to match new EmptyState component text
      expect(screen.getByText(/No events match your current filters/)).toBeInTheDocument();
    });
  });

  describe('Pagination', () => {
    beforeEach(() => {
      // Mock response with more events for pagination
      const manyEvents: Event[] = Array.from({ length: 50 }, (_, i) => ({
        id: i + 1,
        camera_id: 'camera-1',
        started_at: `2024-01-01T${String(i).padStart(2, '0')}:00:00Z`,
        ended_at: null,
        risk_score: 50,
        risk_level: 'medium',
        summary: `Event ${i + 1}`,
        reviewed: false,
        detection_count: 1,
        notes: null,
      }));

      vi.mocked(api.fetchEvents).mockResolvedValue({
        events: manyEvents.slice(0, 20),
        count: 50,
        limit: 20,
        offset: 0,
      });
    });

    it('navigates to next page', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
      });

      const nextButton = screen.getByLabelText('Next page');
      expect(nextButton).not.toBeDisabled();

      await user.click(nextButton);

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ offset: 20 }), expect.anything());
      });
    });

    it('navigates to previous page', async () => {
      // Clear previous mocks and set up fresh ones for this test
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);

      // First load (page 1), then page 2, then back to page 1
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce({
          events: mockEvents,
          count: 50,
          limit: 20,
          offset: 0,
        })
        .mockResolvedValueOnce({
          events: mockEvents,
          count: 50,
          limit: 20,
          offset: 20,
        })
        .mockResolvedValueOnce({
          events: mockEvents,
          count: 50,
          limit: 20,
          offset: 0,
        });

      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
      });

      // Navigate to page 2
      const nextButton = screen.getByLabelText('Next page');
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText('Page 2 of 3')).toBeInTheDocument();
      });

      // Navigate back to page 1
      const prevButton = screen.getByLabelText('Previous page');
      await user.click(prevButton);

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ offset: 0 }), expect.anything());
      });
    });

    it('disables previous button on first page', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
      });

      const prevButton = screen.getByLabelText('Previous page');
      expect(prevButton).toBeDisabled();
    });

    it('disables next button on last page', async () => {
      // Clear previous mocks and set up fresh ones for this test
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);

      // Navigate through pages to reach the last page
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce({
          events: mockEvents,
          count: 50,
          limit: 20,
          offset: 0,
        })
        .mockResolvedValueOnce({
          events: mockEvents,
          count: 50,
          limit: 20,
          offset: 20,
        })
        .mockResolvedValueOnce({
          events: mockEvents,
          count: 50,
          limit: 20,
          offset: 40,
        });

      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      // Wait for initial load (page 1)
      await waitFor(() => {
        expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
      });

      // Navigate to page 2
      let nextButton = screen.getByLabelText('Next page');
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText('Page 2 of 3')).toBeInTheDocument();
      });

      // Navigate to page 3 (last page)
      nextButton = screen.getByLabelText('Next page');
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText('Page 3 of 3')).toBeInTheDocument();
      });

      // Next button should be disabled on last page
      nextButton = screen.getByLabelText('Next page');
      expect(nextButton).toBeDisabled();
    });

    it('resets to first page when filters change', async () => {
      // Clear previous mocks and set up fresh ones for this test
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);

      // Initial load, navigate to page 2, then filter change resets to page 1
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce({
          events: mockEvents,
          count: 50,
          limit: 20,
          offset: 0,
        })
        .mockResolvedValueOnce({
          events: mockEvents,
          count: 50,
          limit: 20,
          offset: 20,
        })
        .mockResolvedValueOnce({
          events: mockEvents,
          count: 50,
          limit: 20,
          offset: 0,
        });

      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      // Wait for initial load (page 1)
      await waitFor(() => {
        expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
      });

      // Navigate to page 2
      const nextButton = screen.getByLabelText('Next page');
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText('Page 2 of 3')).toBeInTheDocument();
      });

      // Apply a filter
      await user.click(screen.getByText('Show Filters'));

      const cameraSelect = screen.getByLabelText('Camera');
      await user.selectOptions(cameraSelect, 'camera-1');

      // Should reset to offset 0 when filters change
      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(expect.objectContaining({ camera_id: 'camera-1', offset: 0 }), expect.anything());
      });
    });
  });

  describe('Error Handling', () => {
    it('displays error message when fetching events fails', async () => {
      vi.resetAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchEvents).mockRejectedValue(new Error('Network error'));
      // Re-mock useEventStream after resetAllMocks
      vi.mocked(useEventStreamHook.useEventStream).mockReturnValue({
        events: mockWsEvents,
        isConnected: true,
        latestEvent: mockWsEvents[0],
        clearEvents: vi.fn(),
      });

      renderWithProviders(<EventTimeline />);

      // Wait for error state to be displayed after async fetch fails
      await waitFor(() => {
        expect(screen.getByText('Error Loading Events')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('handles camera fetch errors gracefully', async () => {
      vi.resetAllMocks();
      vi.mocked(api.fetchCameras).mockRejectedValue(new Error('Camera fetch failed'));
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);
      // Re-mock useEventStream after resetAllMocks
      vi.mocked(useEventStreamHook.useEventStream).mockReturnValue({
        events: mockWsEvents,
        isConnected: true,
        latestEvent: mockWsEvents[0],
        clearEvents: vi.fn(),
      });

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
      vi.mocked(api.fetchEvents).mockResolvedValue({
        events: [],
        count: 0,
        limit: 20,
        offset: 0,
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
      vi.mocked(api.fetchEvents).mockResolvedValue({
        events: [],
        count: 0,
        limit: 20,
        offset: 0,
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
      vi.mocked(api.fetchEvents).mockResolvedValue({
        events: [],
        count: 0,
        limit: 20,
        offset: 0,
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      // Should show "0 events" not "1-0 of 0 events"
      expect(screen.getByText('0 events')).toBeInTheDocument();
      expect(screen.queryByText(/1-0 of 0/)).not.toBeInTheDocument();
    });

    it('does not show pagination controls when empty', async () => {
      vi.mocked(api.fetchEvents).mockResolvedValue({
        events: [],
        count: 0,
        limit: 20,
        offset: 0,
      });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      // Pagination controls should not be present when there are no events
      expect(screen.queryByLabelText('Previous page')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Next page')).not.toBeInTheDocument();
      expect(screen.queryByText(/Page \d+ of \d+/)).not.toBeInTheDocument();
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
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

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
      const eventsWithUnknownCamera: EventListResponse = {
        events: [
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
        ],
        count: 1,
        limit: 20,
        offset: 0,
      };

      vi.mocked(api.fetchEvents).mockResolvedValue(eventsWithUnknownCamera);

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
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

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

      // Mock the events reload after bulk update
      vi.mocked(api.fetchEvents).mockResolvedValueOnce({
        ...mockEventsResponse,
        events: mockEvents.map((e) => (e.id === 2 || e.id === 3 ? { ...e, reviewed: true } : e)),
      });

      // Click mark as reviewed
      const markAsReviewedButton = screen.getByText('Mark as Reviewed');
      await user.click(markAsReviewedButton);

      // Should call bulkUpdateEvents with selected event IDs (sorted by most recent: 3, 2)
      await waitFor(() => {
        expect(api.bulkUpdateEvents).toHaveBeenCalledWith([3, 2], { reviewed: true });
      });

      // Should reload events
      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledTimes(2); // Initial load + reload after update
      });

      // Should clear selections
      await waitFor(() => {
        expect(screen.getByText('Select all')).toBeInTheDocument();
      });
    });

    it('shows loading state during bulk update', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

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
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

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

      // Mock the events reload after bulk update
      vi.mocked(api.fetchEvents).mockResolvedValueOnce(mockEventsResponse);

      // Click mark as reviewed
      const markAsReviewedButton = screen.getByText('Mark as Reviewed');
      await user.click(markAsReviewedButton);

      // Should call bulkUpdateEvents (events sorted: 3, 2)
      await waitFor(() => {
        expect(api.bulkUpdateEvents).toHaveBeenCalledWith([3, 2], { reviewed: true });
      });

      // Should show partial success error
      await waitFor(() => {
        expect(screen.getByText(/Updated 1 events, but 1 failed/)).toBeInTheDocument();
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
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

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

      // Mock the events reload after bulk update
      vi.mocked(api.fetchEvents).mockResolvedValueOnce({
        ...mockEventsResponse,
        events: mockEvents.map((e) => (e.id === 2 || e.id === 3 ? { ...e, reviewed: false } : e)),
      });

      // Click mark as not reviewed
      const markAsNotReviewedButton = screen.getByText('Mark Not Reviewed');
      await user.click(markAsNotReviewedButton);

      // Should call bulkUpdateEvents with reviewed: false (events sorted: 3, 2)
      await waitFor(() => {
        expect(api.bulkUpdateEvents).toHaveBeenCalledWith([3, 2], { reviewed: false });
      });

      // Should reload events
      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledTimes(2); // Initial load + reload after update
      });

      // Should clear selections
      await waitFor(() => {
        expect(screen.getByText('Select all')).toBeInTheDocument();
      });
    });

    it('shows loading state during bulk mark as not reviewed', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

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
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

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

      // Mock the events reload after bulk update
      vi.mocked(api.fetchEvents).mockResolvedValueOnce(mockEventsResponse);

      // Click mark as not reviewed
      const markAsNotReviewedButton = screen.getByText('Mark Not Reviewed');
      await user.click(markAsNotReviewedButton);

      // Should call bulkUpdateEvents with reviewed: false (events sorted: 3, 2)
      await waitFor(() => {
        expect(api.bulkUpdateEvents).toHaveBeenCalledWith([3, 2], { reviewed: false });
      });

      // Should show partial success error
      await waitFor(() => {
        expect(screen.getByText(/Updated 1 events, but 1 failed/)).toBeInTheDocument();
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

      // Apply filter
      vi.mocked(api.fetchEvents).mockResolvedValueOnce({
        events: highRiskEvents,
        count: 1,
        limit: 20,
        offset: 0,
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

    it('updates risk summary badges with search query', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // All badges should be present initially (1 critical, 1 high, 1 low)
      await waitFor(() => {
        expect(screen.getByText('1', { selector: '.text-red-400' })).toBeInTheDocument(); // Critical
      });

      // Search for "cat" - should only show the low risk event
      const searchInput = screen.getByPlaceholderText('Search summaries...');
      await user.type(searchInput, 'cat');

      await waitFor(() => {
        expect(screen.getByText('Cat walking through yard')).toBeInTheDocument();
      });

      // Should only show low risk count now
      await waitFor(() => {
        expect(screen.getByText('1', { selector: '.text-green-400' })).toBeInTheDocument(); // Low
      });

      // Should not show other risk levels
      expect(screen.queryByText('1', { selector: '.text-red-400' })).not.toBeInTheDocument(); // Critical
      expect(screen.queryByText('1', { selector: '.text-orange-400' })).not.toBeInTheDocument(); // High
    });

    it('does not display risk badges when loading', () => {
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      // Make fetchEvents pending to simulate loading
      vi.mocked(api.fetchEvents).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

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
      vi.resetAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchEvents).mockRejectedValue(new Error('Network error'));
      // Re-mock useEventStream after resetAllMocks
      vi.mocked(useEventStreamHook.useEventStream).mockReturnValue({
        events: mockWsEvents,
        isConnected: true,
        latestEvent: mockWsEvents[0],
        clearEvents: vi.fn(),
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
      vi.mocked(api.fetchEvents).mockResolvedValue({
        events: [],
        count: 0,
        limit: 20,
        offset: 0,
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

      vi.mocked(api.fetchEvents).mockResolvedValue({
        events: mediumRiskEvents,
        count: 2,
        limit: 20,
        offset: 0,
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

      vi.mocked(api.fetchEvents).mockResolvedValue({
        events: multipleEvents,
        count: 3,
        limit: 20,
        offset: 0,
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

      vi.mocked(api.fetchEvents).mockResolvedValue({
        events: mixedEvents,
        count: 2,
        limit: 20,
        offset: 0,
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
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ risk_level: 'high', offset: 0 }),
          expect.anything()
        );
      });

      // Filter panel should be visible
      expect(screen.getByLabelText('Risk Level')).toBeInTheDocument();
    });

    it('applies camera filter from URL parameter', async () => {
      renderWithProviders(<EventTimeline />, { route: '/timeline?camera=camera-1' });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ camera_id: 'camera-1', offset: 0 }),
          expect.anything()
        );
      });
    });

    it('applies both camera and risk_level filters from URL parameters', async () => {
      renderWithProviders(<EventTimeline />, {
        route: '/timeline?camera=camera-1&risk_level=critical',
      });

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({
            camera_id: 'camera-1',
            risk_level: 'critical',
            offset: 0,
          }),
          expect.anything()
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

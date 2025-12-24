import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import EventTimeline from './EventTimeline';
import * as api from '../../services/api';

import type { Camera, Event, EventListResponse } from '../../services/api';

// Mock API module
vi.mock('../../services/api');

describe('EventTimeline', () => {
  const mockCameras: Camera[] = [
    {
      id: 'camera-1',
      name: 'Front Door',
      folder_path: '/path/to/front',
      status: 'active',
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T12:00:00Z',
    },
    {
      id: 'camera-2',
      name: 'Back Yard',
      folder_path: '/path/to/back',
      status: 'active',
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
    },
  ];

  const mockEventsResponse: EventListResponse = {
    events: mockEvents,
    count: 3,
    limit: 20,
    offset: 0,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);
  });

  describe('Rendering', () => {
    it('renders the timeline header', () => {
      render(<EventTimeline />);

      expect(screen.getByText('Event Timeline')).toBeInTheDocument();
      expect(
        screen.getByText('View and filter all security events from your cameras')
      ).toBeInTheDocument();
    });

    it('displays loading state initially', () => {
      render(<EventTimeline />);

      expect(screen.getByText('Loading events...')).toBeInTheDocument();
    });

    it('displays events after loading', async () => {
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      expect(screen.getByText('Cat walking through yard')).toBeInTheDocument();
      expect(screen.getByText('Unknown person at door')).toBeInTheDocument();
    });

    it('displays result count', async () => {
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Showing 1-3 of 3 events')).toBeInTheDocument();
      });
    });

    it('displays pagination controls', async () => {
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByLabelText('Previous page')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('Next page')).toBeInTheDocument();
      expect(screen.getByText('Page 1 of 1')).toBeInTheDocument();
    });
  });

  describe('Filtering', () => {
    it('shows filter button and toggles filter panel', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

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
      const user = userEvent.setup();
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const cameraSelect = screen.getByLabelText('Camera');
      await user.selectOptions(cameraSelect, 'camera-1');

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ camera_id: 'camera-1', offset: 0 })
        );
      });
    });

    it('filters events by risk level', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const riskSelect = screen.getByLabelText('Risk Level');
      await user.selectOptions(riskSelect, 'high');

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ risk_level: 'high', offset: 0 })
        );
      });
    });

    it('filters events by reviewed status', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const statusSelect = screen.getByLabelText('Status');
      await user.selectOptions(statusSelect, 'false');

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ reviewed: false, offset: 0 })
        );
      });
    });

    it('filters events by date range', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const startDateInput = screen.getByLabelText('Start Date');
      const endDateInput = screen.getByLabelText('End Date');

      await user.type(startDateInput, '2024-01-01');
      await user.type(endDateInput, '2024-01-31');

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({
            start_date: '2024-01-01',
            end_date: '2024-01-31',
            offset: 0,
          })
        );
      });
    });

    it('clears all filters', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      // Apply some filters
      const cameraSelect = screen.getByLabelText('Camera');
      await user.selectOptions(cameraSelect, 'camera-1');

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ camera_id: 'camera-1' })
        );
      });

      // Clear filters
      const clearButton = screen.getByText('Clear All Filters');
      await user.click(clearButton);

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith({ limit: 20, offset: 0 });
      });
    });

    it('shows active filter indicator', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

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
  });

  describe('Search', () => {
    it('filters events by search query', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

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
      const user = userEvent.setup();
      render(<EventTimeline />);

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
      const user = userEvent.setup();
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search summaries...');
      await user.type(searchInput, 'nonexistent');

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      expect(
        screen.getByText('Try adjusting your filters or search query')
      ).toBeInTheDocument();
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
      }));

      vi.mocked(api.fetchEvents).mockResolvedValue({
        events: manyEvents.slice(0, 20),
        count: 50,
        limit: 20,
        offset: 0,
      });
    });

    it('navigates to next page', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
      });

      const nextButton = screen.getByLabelText('Next page');
      expect(nextButton).not.toBeDisabled();

      await user.click(nextButton);

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ offset: 20 })
        );
      });
    });

    it('navigates to previous page', async () => {
      // Clear previous mocks and set up fresh ones for this test
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);

      // Start on page 2
      vi.mocked(api.fetchEvents)
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

      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Showing 21-23 of 50 events')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      const prevButton = screen.getByLabelText('Previous page');
      await user.click(prevButton);

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ offset: 0 })
        );
      });
    });

    it('disables previous button on first page', async () => {
      render(<EventTimeline />);

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

      // Mock last page
      vi.mocked(api.fetchEvents).mockResolvedValue({
        events: mockEvents,
        count: 50,
        limit: 20,
        offset: 40,
      });

      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Page 3 of 3')).toBeInTheDocument();
      });

      const nextButton = screen.getByLabelText('Next page');
      expect(nextButton).toBeDisabled();
    });

    it('resets to first page when filters change', async () => {
      // Clear previous mocks and set up fresh ones for this test
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);

      // Start on page 2, then reset when filters change
      vi.mocked(api.fetchEvents)
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

      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Showing 21-23 of 50 events')).toBeInTheDocument();
      });

      const user = userEvent.setup();
      await user.click(screen.getByText('Show Filters'));

      const cameraSelect = screen.getByLabelText('Camera');
      await user.selectOptions(cameraSelect, 'camera-1');

      // Should reset to offset 0
      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ camera_id: 'camera-1', offset: 0 })
        );
      });
    });
  });

  describe('Error Handling', () => {
    it('displays error message when fetching events fails', async () => {
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchEvents).mockRejectedValue(new Error('Network error'));

      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Error Loading Events')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('handles camera fetch errors gracefully', async () => {
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockRejectedValue(new Error('Camera fetch failed'));
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

      render(<EventTimeline />);

      // Should still load events
      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Filter should still be available but with no camera options
      const user2 = userEvent.setup();
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

      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      expect(
        screen.getByText('No security events have been recorded yet')
      ).toBeInTheDocument();
    });

    it('shows filtered empty state when filters match no events', async () => {
      const user = userEvent.setup();

      render(<EventTimeline />);

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

      expect(
        screen.getByText('Try adjusting your filters or search query')
      ).toBeInTheDocument();
    });
  });

  describe('Event Card Integration', () => {
    it('calls onViewEventDetails when View Details is clicked', async () => {
      const handleViewDetails = vi.fn();
      const user = userEvent.setup();

      render(<EventTimeline onViewEventDetails={handleViewDetails} />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Find all "View Details" buttons (there are multiple events)
      const viewButtons = screen.getAllByText('View Details');
      await user.click(viewButtons[0]);

      expect(handleViewDetails).toHaveBeenCalledWith(1);
    });

    it('displays camera names in event cards', async () => {
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

      render(<EventTimeline />);

      // Wait for events to load first
      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Camera names should appear after cameras are fetched
      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      expect(screen.getByText('Back Yard')).toBeInTheDocument();
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
          },
        ],
        count: 1,
        limit: 20,
        offset: 0,
      };

      vi.mocked(api.fetchEvents).mockResolvedValue(eventsWithUnknownCamera);

      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Unknown Camera')).toBeInTheDocument();
      });
    });
  });
});

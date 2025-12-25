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

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);
  });

  describe('Rendering', () => {
    it('renders the timeline header', async () => {
      render(<EventTimeline />);

      expect(screen.getByText('Event Timeline')).toBeInTheDocument();
      expect(
        screen.getByText('View and filter all security events from your cameras')
      ).toBeInTheDocument();

      // Wait for async state updates to complete to avoid act() warnings
      await waitFor(() => {
        expect(screen.queryByText('Loading events...')).not.toBeInTheDocument();
      });
    });

    it('displays loading state initially', async () => {
      render(<EventTimeline />);

      expect(screen.getByText('Loading events...')).toBeInTheDocument();

      // Wait for loading to complete to avoid act() warnings
      await waitFor(() => {
        expect(screen.queryByText('Loading events...')).not.toBeInTheDocument();
      });
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

    it('filters events by object type', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const objectTypeSelect = screen.getByLabelText('Object Type');
      await user.selectOptions(objectTypeSelect, 'person');

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ object_type: 'person', offset: 0 })
        );
      });
    });

    it('displays object type filter dropdown with all options', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const objectTypeSelect = screen.getByLabelText('Object Type');
      expect(objectTypeSelect).toBeInTheDocument();

      // Check all options are present
      const options = within(objectTypeSelect).getAllByRole('option');
      expect(options).toHaveLength(6); // All Object Types + 5 specific types
      expect(within(objectTypeSelect).getByRole('option', { name: 'All Object Types' })).toBeInTheDocument();
      expect(within(objectTypeSelect).getByRole('option', { name: 'Person' })).toBeInTheDocument();
      expect(within(objectTypeSelect).getByRole('option', { name: 'Vehicle' })).toBeInTheDocument();
      expect(within(objectTypeSelect).getByRole('option', { name: 'Animal' })).toBeInTheDocument();
      expect(within(objectTypeSelect).getByRole('option', { name: 'Package' })).toBeInTheDocument();
      expect(within(objectTypeSelect).getByRole('option', { name: 'Other' })).toBeInTheDocument();
    });

    it('clears object type filter with clear all filters button', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      // Apply object type filter
      const objectTypeSelect = screen.getByLabelText('Object Type');
      await user.selectOptions(objectTypeSelect, 'vehicle');

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({ object_type: 'vehicle' })
        );
      });

      // Clear filters
      const clearButton = screen.getByText('Clear All Filters');
      await user.click(clearButton);

      await waitFor(() => {
        expect(api.fetchEvents).toHaveBeenCalledWith({ limit: 20, offset: 0 });
      });
    });

    it('combines object type filter with other filters', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

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
        expect(api.fetchEvents).toHaveBeenCalledWith(
          expect.objectContaining({
            camera_id: 'camera-1',
            object_type: 'animal',
            offset: 0
          })
        );
      });
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

      const user = userEvent.setup();
      render(<EventTimeline />);

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
      });

      // Navigate to page 2
      const nextButton = screen.getByLabelText('Next page');
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
      });

      // Navigate back to page 1
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

      const user = userEvent.setup();
      render(<EventTimeline />);

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

      const user = userEvent.setup();
      render(<EventTimeline />);

      // Wait for initial load (page 1)
      await waitFor(() => {
        expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
      });

      // Navigate to page 2
      const nextButton = screen.getByLabelText('Next page');
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
      });

      // Apply a filter
      await user.click(screen.getByText('Show Filters'));

      const cameraSelect = screen.getByLabelText('Camera');
      await user.selectOptions(cameraSelect, 'camera-1');

      // Should reset to offset 0 when filters change
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

      // Wait for error state to be displayed after async fetch fails
      await waitFor(
        () => {
          expect(screen.getByText('Error Loading Events')).toBeInTheDocument();
        },
        { timeout: 3000 }
      );

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

      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Unknown Camera')).toBeInTheDocument();
      });
    });
  });

  describe('Bulk Actions', () => {
    it('displays bulk action controls when events are loaded', async () => {
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Should show select all button
      expect(screen.getByText('Select all')).toBeInTheDocument();
    });

    it('toggles selection for individual events', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

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
      const user = userEvent.setup();
      render(<EventTimeline />);

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
      const user = userEvent.setup();
      render(<EventTimeline />);

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
      const user = userEvent.setup();
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

      // Mock bulkUpdateEvents for successful update
      vi.mocked(api.bulkUpdateEvents).mockResolvedValue({
        successful: [1, 2],
        failed: [],
      });

      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Select first two events
      const checkboxButtons = screen.getAllByLabelText(/Select event \d+/);
      await user.click(checkboxButtons[0]);
      await user.click(checkboxButtons[1]);

      await waitFor(() => {
        expect(screen.getByText('2 selected')).toBeInTheDocument();
      });

      // Mock the events reload after bulk update
      vi.mocked(api.fetchEvents).mockResolvedValueOnce({
        ...mockEventsResponse,
        events: mockEvents.map((e) =>
          e.id === 1 || e.id === 2 ? { ...e, reviewed: true } : e
        ),
      });

      // Click mark as reviewed
      const markAsReviewedButton = screen.getByText('Mark as Reviewed');
      await user.click(markAsReviewedButton);

      // Should call bulkUpdateEvents with selected event IDs
      await waitFor(() => {
        expect(api.bulkUpdateEvents).toHaveBeenCalledWith([1, 2], { reviewed: true });
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
      const user = userEvent.setup();
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

      render(<EventTimeline />);

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

      // Should show loading state
      await waitFor(() => {
        expect(screen.getByText('Updating...')).toBeInTheDocument();
      });

      // The button containing "Updating..." should be disabled
      const updatingButton = screen.getByRole('button', { name: /Mark.*selected events as reviewed/ });
      expect(updatingButton).toBeDisabled();
    });

    it('handles bulk update errors gracefully', async () => {
      const user = userEvent.setup();
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEventsResponse);

      // Mock bulkUpdateEvents to return partial failure
      vi.mocked(api.bulkUpdateEvents).mockResolvedValue({
        successful: [1],
        failed: [{ id: 2, error: 'Network error' }],
      });

      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Select two events
      const checkboxButtons = screen.getAllByLabelText(/Select event \d+/);
      await user.click(checkboxButtons[0]);
      await user.click(checkboxButtons[1]);

      // Mock the events reload after bulk update
      vi.mocked(api.fetchEvents).mockResolvedValueOnce(mockEventsResponse);

      // Click mark as reviewed
      const markAsReviewedButton = screen.getByText('Mark as Reviewed');
      await user.click(markAsReviewedButton);

      // Should call bulkUpdateEvents
      await waitFor(() => {
        expect(api.bulkUpdateEvents).toHaveBeenCalledWith([1, 2], { reviewed: true });
      });

      // Should show partial success error
      await waitFor(() => {
        expect(screen.getByText(/Updated 1 events, but 1 failed/)).toBeInTheDocument();
      });
    });

    it('does not show bulk action button when no events selected', async () => {
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Should show select all but not mark as reviewed button
      expect(screen.getByText('Select all')).toBeInTheDocument();
      expect(screen.queryByText('Mark as Reviewed')).not.toBeInTheDocument();
    });

    it('clears selection when toggling individual checkbox off', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Select an event
      const checkboxButtons = screen.getAllByLabelText(/Select event \d+/);
      await user.click(checkboxButtons[0]);

      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeInTheDocument();
      });

      // Deselect the same event
      const deselectButton = screen.getByLabelText('Deselect event 1');
      await user.click(deselectButton);

      // Should show select all again
      await waitFor(() => {
        expect(screen.getByText('Select all')).toBeInTheDocument();
      });
    });
  });

  describe('Risk Summary Badges', () => {
    it('displays risk summary badges with correct counts', async () => {
      render(<EventTimeline />);

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
      const user = userEvent.setup();

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

      render(<EventTimeline />);

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

      // Should only show high risk count
      await waitFor(() => {
        expect(screen.getByText('1', { selector: '.text-orange-400' })).toBeInTheDocument(); // High
      });

      // Should not show other risk levels
      expect(screen.queryByText('1', { selector: '.text-red-400' })).not.toBeInTheDocument(); // Critical
      expect(screen.queryByText('1', { selector: '.text-green-400' })).not.toBeInTheDocument(); // Low
    });

    it('updates risk summary badges with search query', async () => {
      const user = userEvent.setup();
      render(<EventTimeline />);

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

      render(<EventTimeline />);

      // Should show loading state
      expect(screen.getByText('Loading events...')).toBeInTheDocument();

      // Should not show risk badges during loading
      expect(screen.queryByText('Critical')).not.toBeInTheDocument();
      expect(screen.queryByText('High')).not.toBeInTheDocument();
      expect(screen.queryByText('Medium')).not.toBeInTheDocument();
      expect(screen.queryByText('Low')).not.toBeInTheDocument();
    });

    it('does not display risk badges when there is an error', async () => {
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchEvents).mockRejectedValue(new Error('Network error'));

      render(<EventTimeline />);

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

      render(<EventTimeline />);

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

      render(<EventTimeline />);

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

      render(<EventTimeline />);

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

      render(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Event with explicit level')).toBeInTheDocument();
      });

      // Should show high risk badge with count of 2 (both events are high risk)
      await waitFor(() => {
        expect(screen.getByText('2', { selector: '.text-orange-400' })).toBeInTheDocument(); // High
      });
    });
  });
});

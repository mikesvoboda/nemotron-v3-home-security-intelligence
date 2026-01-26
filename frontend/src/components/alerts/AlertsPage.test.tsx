import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import AlertsPage from './AlertsPage';
import * as api from '../../services/api';

import type { Camera, Event, EventListResponse } from '../../services/api';

// Mock API module
vi.mock('../../services/api');

// Create a wrapper with QueryClientProvider for testing
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// Helper function to render with QueryClientProvider
function renderWithQueryClient(ui: React.ReactElement) {
  return render(ui, { wrapper: createWrapper() });
}

// Mock VideoPlayer to avoid video element issues in tests
vi.mock('../video/VideoPlayer', () => ({
  default: vi.fn(
    ({ src, poster, className }: { src: string; poster?: string; className?: string }) => (
      <div data-testid="video-player" data-src={src} data-poster={poster} className={className}>
        Mocked VideoPlayer
      </div>
    )
  ),
}));

describe('AlertsPage', () => {
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

  const mockHighRiskEvents: Event[] = [
    {
      id: 1,
      camera_id: 'camera-1',
      started_at: '2024-01-01T10:00:00Z',
      ended_at: '2024-01-01T10:02:00Z',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Person detected near entrance',
      reviewed: false,
      flagged: false, // NEM-3839
      detection_count: 5,
      notes: null,
      version: 1,
    },
  ];

  const mockCriticalRiskEvents: Event[] = [
    {
      id: 2,
      camera_id: 'camera-2',
      started_at: '2024-01-01T11:00:00Z',
      ended_at: '2024-01-01T11:01:00Z',
      risk_score: 90,
      risk_level: 'critical',
      summary: 'Unknown person at door',
      reviewed: false,
      flagged: false, // NEM-3839
      detection_count: 8,
      notes: null,
      version: 1,
    },
  ];

  const mockHighResponse: EventListResponse = {
    items: mockHighRiskEvents,
    pagination: {
      total: 1,
      limit: 20,
      offset: 0,
      has_more: false,
    },
  };

  const mockCriticalResponse: EventListResponse = {
    items: mockCriticalRiskEvents,
    pagination: {
      total: 1,
      limit: 20,
      offset: 0,
      has_more: false,
    },
  };

  const mockEmptyResponse: EventListResponse = {
    items: [],
    pagination: {
      total: 0,
      limit: 20,
      offset: 0,
      has_more: false,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    // Mock detection fetching for modal
    vi.mocked(api.fetchEventDetections).mockResolvedValue({
      items: [],
      pagination: { total: 0, limit: 100, offset: 0, has_more: false },
    });
    // Mock update event for mark as reviewed
    vi.mocked(api.updateEvent).mockResolvedValue({
      id: 1,
      camera_id: 'camera-1',
      started_at: '2024-01-01T10:00:00Z',
      ended_at: null,
      risk_score: 75,
      risk_level: 'high',
      summary: 'Updated event',
      reviewed: true,
      flagged: false, // NEM-3839
      detection_count: 0,
      notes: null,
      version: 2,
    });
  });

  describe('Rendering', () => {
    it('renders the alerts page header', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      expect(screen.getByText('Alerts')).toBeInTheDocument();
      expect(
        screen.getByText('High and critical risk events requiring attention')
      ).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.queryByText('Loading alerts...')).not.toBeInTheDocument();
      });
    });

    it('displays loading skeleton state initially', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      // Should show skeleton loading cards
      expect(screen.getAllByTestId('alert-card-skeleton').length).toBeGreaterThan(0);

      await waitFor(() => {
        expect(screen.queryByTestId('alert-card-skeleton')).not.toBeInTheDocument();
      });
    });

    it('displays alerts after loading', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      expect(screen.getByText('Unknown person at door')).toBeInTheDocument();
    });

    it('displays alert count', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('2 alerts found')).toBeInTheDocument();
      });
    });

    it('displays risk summary badges', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Check for risk badges with counts
      expect(screen.getByText('1', { selector: '.text-red-400' })).toBeInTheDocument(); // Critical
      expect(screen.getByText('1', { selector: '.text-orange-400' })).toBeInTheDocument(); // High
    });
  });

  describe('Empty State', () => {
    it('shows friendly placeholder when no alerts exist', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockEmptyResponse)
        .mockResolvedValueOnce(mockEmptyResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('No Alerts at This Time')).toBeInTheDocument();
      });

      expect(
        screen.getByText(
          'There are no high or critical risk events to review. Keep up the good work!'
        )
      ).toBeInTheDocument();
    });

    it('shows filtered placeholder when filter returns no results', async () => {
      // Mock will be called multiple times: initial load + after filter change
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEmptyResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('No Alerts at This Time')).toBeInTheDocument();
      });

      // Change filter to critical only
      const filterSelect = screen.getByLabelText('Filter by severity:');
      await user.selectOptions(filterSelect, 'critical');

      await waitFor(() => {
        expect(
          screen.getByText('There are no critical risk events to review.')
        ).toBeInTheDocument();
      });
    });
  });

  describe('Filtering', () => {
    it('displays severity filter dropdown', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      const filterSelect = screen.getByLabelText('Filter by severity:');
      expect(filterSelect).toBeInTheDocument();
    });

    it('filters by critical risk level', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Mock the next set of API calls for filtered results
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const filterSelect = screen.getByLabelText('Filter by severity:');
      await user.selectOptions(filterSelect, 'critical');

      await waitFor(() => {
        expect(screen.getByText('Unknown person at door')).toBeInTheDocument();
      });

      // High risk event should not be visible with critical filter
      expect(screen.queryByText('Person detected near entrance')).not.toBeInTheDocument();
    });

    it('filters by high risk level', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Unknown person at door')).toBeInTheDocument();
      });

      // Mock the next set of API calls for filtered results
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const filterSelect = screen.getByLabelText('Filter by severity:');
      await user.selectOptions(filterSelect, 'high');

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Critical risk event should not be visible with high filter
      expect(screen.queryByText('Unknown person at door')).not.toBeInTheDocument();
    });
  });

  describe('Refresh', () => {
    it('displays refresh button', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      expect(screen.getByText('Refresh')).toBeInTheDocument();
    });

    it('refresh button is disabled while loading', () => {
      vi.mocked(api.fetchEvents).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      renderWithQueryClient(<AlertsPage />);

      const refreshButton = screen.getByText('Refresh').closest('button');
      expect(refreshButton).toBeDisabled();
    });
  });

  describe('Error Handling', () => {
    it('displays error message when fetching alerts fails', async () => {
      // Reset and set mock to reject all calls
      vi.mocked(api.fetchEvents).mockReset();
      vi.mocked(api.fetchEvents).mockRejectedValue(new Error('Network error'));

      renderWithQueryClient(<AlertsPage />);

      // Wait for error state
      await waitFor(() => {
        expect(screen.getByText('Error Loading Alerts')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('handles camera fetch errors gracefully', async () => {
      vi.mocked(api.fetchCameras).mockRejectedValue(new Error('Camera fetch failed'));
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      // Should still load alerts
      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Camera name should fall back to 'Unknown Camera'
      expect(screen.getAllByText('Unknown Camera').length).toBeGreaterThan(0);
    });
  });

  describe('Infinite Scroll', () => {
    it('displays "All alerts loaded" when no more pages are available', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('2 alerts found')).toBeInTheDocument();
      });

      // Should show "All alerts loaded" when all data is loaded
      await waitFor(() => {
        expect(screen.getByText('All alerts loaded')).toBeInTheDocument();
      });
    });

    it('shows partial count when more alerts are available', async () => {
      const manyHighEvents: Event[] = Array.from({ length: 15 }, (_, i) => ({
        id: i + 1,
        camera_id: 'camera-1',
        started_at: `2024-01-01T${String(i).padStart(2, '0')}:00:00Z`,
        ended_at: null,
        risk_score: 75,
        risk_level: 'high',
        summary: `High risk event ${i + 1}`,
        reviewed: false,
        flagged: false, // NEM-3839
        detection_count: 1,
        notes: null,
        version: 1,
      }));

      const manyCriticalEvents: Event[] = Array.from({ length: 15 }, (_, i) => ({
        id: i + 20,
        camera_id: 'camera-2',
        started_at: `2024-01-01T${String(i + 15).padStart(2, '0')}:00:00Z`,
        ended_at: null,
        risk_score: 90,
        risk_level: 'critical',
        summary: `Critical event ${i + 1}`,
        reviewed: false,
        flagged: false, // NEM-3839
        detection_count: 1,
        notes: null,
        version: 1,
      }));

      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce({
          items: manyHighEvents,
          pagination: {
            total: 30,
            limit: 25,
            offset: 0,
            has_more: true,
          },
        })
        .mockResolvedValueOnce({
          items: manyCriticalEvents,
          pagination: {
            total: 30,
            limit: 25,
            offset: 0,
            has_more: true,
          },
        });

      renderWithQueryClient(<AlertsPage />);

      // Should show total count with indication that more are available
      await waitFor(() => {
        expect(screen.getByText(/60 alerts found/)).toBeInTheDocument();
      });

      // When not all alerts are loaded, should show "showing X" indicator
      await waitFor(() => {
        expect(screen.getByText(/showing 30/)).toBeInTheDocument();
      });
    });
  });

  describe('Event Card Integration', () => {
    it('calls onViewEventDetails when View Details is clicked in grid view', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const handleViewDetails = vi.fn();
      const user = userEvent.setup();

      renderWithQueryClient(<AlertsPage onViewEventDetails={handleViewDetails} />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Switch to grid view to access View Details button
      const gridButton = screen.getByRole('button', { name: 'Grid view' });
      await user.click(gridButton);

      await waitFor(() => {
        expect(screen.getByTestId('alerts-grid-view')).toBeInTheDocument();
      });

      const viewButtons = screen.getAllByText('View Details');
      await user.click(viewButtons[0]);

      expect(handleViewDetails).toHaveBeenCalled();
    });

    it('displays camera names in event cards and group headers', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Camera names appear in group headers in grouped view
      await waitFor(() => {
        expect(screen.getAllByText('Front Door').length).toBeGreaterThan(0);
      });

      expect(screen.getAllByText('Back Yard').length).toBeGreaterThan(0);
    });
  });

  describe('Singular/Plural Alert Count', () => {
    it('displays singular "alert" when count is 1', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockEmptyResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('1 alert found')).toBeInTheDocument();
      });
    });

    it('displays plural "alerts" when count is not 1', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('2 alerts found')).toBeInTheDocument();
      });
    });

    it('displays "0 alerts found" when empty', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockEmptyResponse)
        .mockResolvedValueOnce(mockEmptyResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('0 alerts found')).toBeInTheDocument();
      });
    });
  });

  describe('Event Detail Modal', () => {
    it('opens modal when clicking on an alert card in grouped view', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Wait for camera names to load (in grouped view, camera names appear in group headers)
      await waitFor(() => {
        expect(screen.getAllByText('Front Door').length).toBeGreaterThan(0);
      });

      // Find the first event card by data-testid and click on it
      // Note: Card doesn't have role="button" when nested interactive elements exist (snooze)
      const eventCard = screen.getByTestId('event-card-1');
      await user.click(eventCard);

      // Modal should open
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    it('closes modal when clicking close button', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Wait for camera names to load
      await waitFor(() => {
        expect(screen.getAllByText('Front Door').length).toBeGreaterThan(0);
      });

      // Click on event card to open modal
      const eventCard = screen.getByTestId('event-card-1');
      await user.click(eventCard);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Click close button
      const closeButton = screen.getByRole('button', { name: 'Close modal' });
      await user.click(closeButton);

      // Modal should be closed
      await waitFor(() => {
        expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
      });
    });

    it('displays event details in modal', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Wait for camera names to load
      await waitFor(() => {
        expect(screen.getAllByText('Front Door').length).toBeGreaterThan(0);
      });

      // Click on event card to open modal
      const eventCard = screen.getByTestId('event-card-1');
      await user.click(eventCard);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Modal should show event details
      // The modal displays the camera name in the title - use getAllByRole since both card and modal have headings
      const headings = screen.getAllByRole('heading', { name: 'Front Door' });
      // At least one heading should be in the modal (h2 with id="event-detail-title")
      const modalTitle = headings.find((h) => h.id === 'event-detail-title');
      expect(modalTitle).toBeInTheDocument();

      // Should show AI Summary section
      expect(screen.getByText('AI Summary')).toBeInTheDocument();
    });

    it('supports navigation between events in modal', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Wait for camera names to load
      await waitFor(() => {
        expect(screen.getAllByText('Front Door').length).toBeGreaterThan(0);
      });

      // Click on first event card to open modal
      const eventCard = screen.getByTestId('event-card-1');
      await user.click(eventCard);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Modal should have navigation buttons
      expect(screen.getByRole('button', { name: 'Previous event' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Next event' })).toBeInTheDocument();

      // Click Next to navigate to next event
      const nextButton = screen.getByRole('button', { name: 'Next event' });
      await user.click(nextButton);

      // Should navigate to the next event (Back Yard camera)
      await waitFor(() => {
        // In grouped view, both camera names might be visible, so check for heading in modal
        const backYardHeadings = screen.getAllByRole('heading', { name: 'Back Yard' });
        expect(backYardHeadings.length).toBeGreaterThan(0);
      });
    });

    it('marks event as reviewed from modal', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Wait for camera names to load
      await waitFor(() => {
        expect(screen.getAllByText('Front Door').length).toBeGreaterThan(0);
      });

      // Click on event card to open modal
      const eventCard = screen.getByTestId('event-card-1');
      await user.click(eventCard);

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });

      // Mock the next fetch calls after marking as reviewed
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      // Click mark as reviewed button
      const reviewButton = screen.getByRole('button', { name: 'Mark event as reviewed' });
      await user.click(reviewButton);

      // Should call updateEvent API
      await waitFor(() => {
        expect(api.updateEvent).toHaveBeenCalledWith(1, { reviewed: true });
      });
    });
  });

  describe('Bulk Selection', () => {
    // Helper function to switch to grid view
    const switchToGridView = async (user: ReturnType<typeof userEvent.setup>) => {
      const gridButton = screen.getByRole('button', { name: 'Grid view' });
      await user.click(gridButton);
      await waitFor(() => {
        expect(screen.getByTestId('alerts-grid-view')).toBeInTheDocument();
      });
    };

    it('displays checkbox on each alert card in grid view', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      await switchToGridView(user);

      // Each event card should have a checkbox
      const checkboxes = screen.getAllByRole('checkbox');
      expect(checkboxes.length).toBeGreaterThanOrEqual(2);
    });

    it('toggles selection when checkbox is clicked', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      await switchToGridView(user);

      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);

      // Checkbox should be checked
      expect(checkboxes[0]).toBeChecked();
    });

    it('shows bulk action bar when alerts are selected', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      await switchToGridView(user);

      // Select an alert
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);

      // Bulk action bar should appear
      expect(screen.getByTestId('bulk-action-bar')).toBeInTheDocument();
      expect(screen.getByText(/1 selected/)).toBeInTheDocument();
    });

    it('hides bulk action bar when selection is cleared', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      await switchToGridView(user);

      // Select an alert
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);

      // Bulk action bar should appear
      expect(screen.getByTestId('bulk-action-bar')).toBeInTheDocument();

      // Click clear button
      await user.click(screen.getByRole('button', { name: /clear/i }));

      // Bulk action bar should disappear
      expect(screen.queryByTestId('bulk-action-bar')).not.toBeInTheDocument();
    });

    it('selects all alerts when "Select all" is clicked', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      await switchToGridView(user);

      // Select one alert first to show the bulk action bar
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);

      // Click select all
      await user.click(screen.getByRole('button', { name: /select all/i }));

      // All checkboxes should be checked
      const allCheckboxes = screen.getAllByRole('checkbox');
      allCheckboxes.forEach((checkbox) => {
        expect(checkbox).toBeChecked();
      });

      // Should show "2 selected"
      expect(screen.getByText(/2 selected/)).toBeInTheDocument();
    });

    it('dismisses selected alerts when "Dismiss Selected" is clicked', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      await switchToGridView(user);

      // Select first alert (the first checkbox corresponds to the first card in the grid)
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);

      // Mock the API calls for after dismissal
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockEmptyResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      // Click dismiss selected
      await user.click(screen.getByRole('button', { name: /dismiss.*selected/i }));

      // Should call updateEvent with reviewed: true for one of the alerts
      // (The order depends on which card appears first in the grid)
      await waitFor(() => {
        expect(api.updateEvent).toHaveBeenCalledWith(expect.any(Number), { reviewed: true });
      });
    });

    it('highlights selected alert cards', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      await switchToGridView(user);

      // Select first alert (the first checkbox in grid view)
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);

      // The selected card's wrapper should have a highlight class
      // Find the card that corresponds to the first checkbox
      const eventCards = screen.getAllByTestId(/^event-card-/);
      // At least one card's parent should have the ring-2 class
      const hasHighlightedCard = eventCards.some((card) =>
        card.parentElement?.classList.contains('ring-2')
      );
      expect(hasHighlightedCard).toBe(true);
    });
  });

  describe('Keyboard Shortcuts', () => {
    // Helper function to switch to grid view
    const switchToGridView = async (user: ReturnType<typeof userEvent.setup>) => {
      const gridButton = screen.getByRole('button', { name: 'Grid view' });
      await user.click(gridButton);
      await waitFor(() => {
        expect(screen.getByTestId('alerts-grid-view')).toBeInTheDocument();
      });
    };

    it('selects all alerts with Ctrl+A in grid view', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      await switchToGridView(user);

      // Press Ctrl+A
      await user.keyboard('{Control>}a{/Control}');

      // All checkboxes should be checked
      const checkboxes = screen.getAllByRole('checkbox');
      checkboxes.forEach((checkbox) => {
        expect(checkbox).toBeChecked();
      });
    });

    it('clears selection with Escape in grid view', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      await switchToGridView(user);

      // Select an alert first
      const checkboxes = screen.getAllByRole('checkbox');
      await user.click(checkboxes[0]);

      expect(screen.getByTestId('bulk-action-bar')).toBeInTheDocument();

      // Press Escape
      await user.keyboard('{Escape}');

      // Selection should be cleared
      expect(screen.queryByTestId('bulk-action-bar')).not.toBeInTheDocument();
      expect(checkboxes[0]).not.toBeChecked();
    });

    it('selects all with Cmd+A on Mac in grid view', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      await switchToGridView(user);

      // Press Meta+A (Cmd+A on Mac)
      await user.keyboard('{Meta>}a{/Meta}');

      // All checkboxes should be checked
      const checkboxes = screen.getAllByRole('checkbox');
      checkboxes.forEach((checkbox) => {
        expect(checkbox).toBeChecked();
      });
    });
  });

  describe('Camera Grouping', () => {
    it('displays grouped view by default', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Should show grouped view
      expect(screen.getByTestId('alerts-grouped-view')).toBeInTheDocument();
    });

    it('groups alerts by camera', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Should have camera group headers
      expect(screen.getByTestId('alert-camera-group-camera-1')).toBeInTheDocument();
      expect(screen.getByTestId('alert-camera-group-camera-2')).toBeInTheDocument();
    });

    it('sorts camera groups by highest severity', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Get the camera group elements
      const groups = screen.getAllByTestId(/^alert-camera-group-/);

      // Critical (camera-2) should be first, then high (camera-1)
      expect(groups[0]).toHaveAttribute('data-testid', 'alert-camera-group-camera-2');
      expect(groups[1]).toHaveAttribute('data-testid', 'alert-camera-group-camera-1');
    });

    it('shows view mode toggle', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Should have view mode toggle buttons
      expect(screen.getByRole('button', { name: 'Group by camera' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Grid view' })).toBeInTheDocument();
    });

    it('switches to grid view when grid button is clicked', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Click grid view button
      const gridButton = screen.getByRole('button', { name: 'Grid view' });
      await user.click(gridButton);

      // Should show grid view
      await waitFor(() => {
        expect(screen.getByTestId('alerts-grid-view')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('alerts-grouped-view')).not.toBeInTheDocument();
    });

    it('switches back to grouped view when grouped button is clicked', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Switch to grid view first
      const gridButton = screen.getByRole('button', { name: 'Grid view' });
      await user.click(gridButton);

      await waitFor(() => {
        expect(screen.getByTestId('alerts-grid-view')).toBeInTheDocument();
      });

      // Click grouped view button
      const groupedButton = screen.getByRole('button', { name: 'Group by camera' });
      await user.click(groupedButton);

      // Should show grouped view
      await waitFor(() => {
        expect(screen.getByTestId('alerts-grouped-view')).toBeInTheDocument();
      });
    });

    it('shows dismiss all button in camera group header', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Should have dismiss all buttons
      expect(
        screen.getByRole('button', { name: 'Dismiss all alerts for Front Door' })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: 'Dismiss all alerts for Back Yard' })
      ).toBeInTheDocument();
    });

    it('dismisses all alerts for a camera when dismiss all is clicked', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Mock the API calls for after dismissal
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockEmptyResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      // Click dismiss all for Front Door camera
      const dismissButton = screen.getByRole('button', {
        name: 'Dismiss all alerts for Front Door',
      });
      await user.click(dismissButton);

      // Should call updateEvent with reviewed: true for the camera's alerts
      await waitFor(() => {
        expect(api.updateEvent).toHaveBeenCalledWith(1, { reviewed: true });
      });
    });

    it('shows severity badges in camera group header', async () => {
      // Create multiple alerts for the same camera with different severities
      const multipleAlertsForCamera: Event[] = [
        {
          id: 1,
          camera_id: 'camera-1',
          started_at: '2024-01-01T10:00:00Z',
          ended_at: '2024-01-01T10:02:00Z',
          risk_score: 90,
          risk_level: 'critical',
          summary: 'Critical alert 1',
          reviewed: false,
          flagged: false, // NEM-3839
          detection_count: 5,
          notes: null,
          version: 1,
        },
        {
          id: 2,
          camera_id: 'camera-1',
          started_at: '2024-01-01T09:00:00Z',
          ended_at: '2024-01-01T09:05:00Z',
          risk_score: 75,
          risk_level: 'high',
          summary: 'High alert 1',
          reviewed: false,
          flagged: false, // NEM-3839
          detection_count: 3,
          notes: null,
          version: 1,
        },
        {
          id: 3,
          camera_id: 'camera-1',
          started_at: '2024-01-01T08:00:00Z',
          ended_at: '2024-01-01T08:01:00Z',
          risk_score: 80,
          risk_level: 'high',
          summary: 'High alert 2',
          reviewed: false,
          flagged: false, // NEM-3839
          detection_count: 2,
          notes: null,
          version: 1,
        },
      ];

      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce({
          items: multipleAlertsForCamera,
          pagination: { total: 3, limit: 20, offset: 0, has_more: false },
        })
        .mockResolvedValueOnce(mockEmptyResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Critical alert 1')).toBeInTheDocument();
      });

      // Should show severity badges (1 critical, 2 high)
      expect(screen.getByText('1 critical')).toBeInTheDocument();
      expect(screen.getByText('2 high')).toBeInTheDocument();
    });

    it('opens modal when clicking on an alert in grouped view', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Click on an event card within a group
      const eventCard = screen.getByTestId('event-card-1');
      await user.click(eventCard);

      // Modal should open
      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });
  });
});

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

<<<<<<< HEAD
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
  default: vi.fn(({ src, poster, className }: { src: string; poster?: string; className?: string }) => (
    <div data-testid="video-player" data-src={src} data-poster={poster} className={className}>
      Mocked VideoPlayer
=======
// Mock new alert components
vi.mock('./AlertCard', () => ({
  default: vi.fn(({ id, summary, onAcknowledge, onDismiss, selected, onSelectChange }) => (
    <div data-testid={`alert-card-${id}`}>
      <div>{summary}</div>
      {selected !== undefined && (
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onSelectChange?.(id, !selected)}
          data-testid={`checkbox-${id}`}
        />
      )}
      {onAcknowledge && (
        <button onClick={() => onAcknowledge(id)} data-testid={`acknowledge-${id}`}>
          Acknowledge
        </button>
      )}
      {onDismiss && (
        <button onClick={() => onDismiss(id)} data-testid={`dismiss-${id}`}>
          Dismiss
        </button>
      )}
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
    </div>
  )),
}));

vi.mock('./AlertFilters', () => ({
  default: vi.fn(({ activeFilter, onFilterChange, counts }) => (
    <div data-testid="alert-filters">
      <button onClick={() => onFilterChange('all')}>All ({counts.all})</button>
      <button onClick={() => onFilterChange('critical')}>Critical ({counts.critical})</button>
      <button onClick={() => onFilterChange('high')}>High ({counts.high})</button>
      <button onClick={() => onFilterChange('medium')}>Medium ({counts.medium})</button>
      <button onClick={() => onFilterChange('unread')}>Unread ({counts.unread})</button>
      <span>Active: {activeFilter}</span>
    </div>
  )),
}));

vi.mock('./AlertActions', () => ({
  default: vi.fn(
    ({
      selectedCount,
      totalCount,
      onSelectAll,
      onAcknowledgeSelected,
      onDismissSelected,
      onClearSelection,
    }) =>
      totalCount > 0 ? (
        <div data-testid="alert-actions">
          <button onClick={() => onSelectAll(true)}>Select All</button>
          <button onClick={onAcknowledgeSelected}>Acknowledge Selected</button>
          <button onClick={onDismissSelected}>Dismiss Selected</button>
          <button onClick={onClearSelection}>Clear</button>
          <span>{selectedCount} selected</span>
        </div>
      ) : null
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
      detection_count: 5,
      notes: null,
    },
    {
      id: 2,
      camera_id: 'camera-1',
      started_at: '2024-01-01T11:00:00Z',
      ended_at: '2024-01-01T11:01:00Z',
      risk_score: 80,
      risk_level: 'high',
      summary: 'Vehicle in restricted area',
      reviewed: false,
      detection_count: 3,
      notes: null,
    },
  ];

  const mockCriticalRiskEvents: Event[] = [
    {
      id: 3,
      camera_id: 'camera-2',
      started_at: '2024-01-01T11:00:00Z',
      ended_at: '2024-01-01T11:01:00Z',
      risk_score: 90,
      risk_level: 'critical',
      summary: 'Unknown person at door',
      reviewed: false,
      detection_count: 8,
      notes: null,
    },
  ];

  const mockHighResponse: EventListResponse = {
    items: mockHighRiskEvents,
    pagination: {
      total: 2,
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
    vi.resetAllMocks();
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    vi.mocked(api.isAbortError).mockReturnValue(false);
    vi.mocked(api.updateEvent).mockResolvedValue({
      id: 1,
      camera_id: 'camera-1',
      started_at: '2024-01-01T10:00:00Z',
      ended_at: null,
      risk_score: 75,
      risk_level: 'high',
      summary: 'Updated event',
      reviewed: true,
      detection_count: 0,
      notes: null,
    });
  });

  describe('New Header and Statistics', () => {
    it('displays alert statistics in header', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
      });

      // Should show unacknowledged count in header
      expect(screen.getByText(/unacknowledged/i)).toBeInTheDocument();
    });

    it('displays "Configure Rules" button in header', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const mockOnConfigureRules = vi.fn();
      render(<AlertsPage onConfigureRules={mockOnConfigureRules} />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /configure rules/i })).toBeInTheDocument();
      });
    });

<<<<<<< HEAD
    it('displays loading state initially', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      expect(screen.getByText('Loading alerts...')).toBeInTheDocument();

      await waitFor(() => {
        expect(screen.queryByText('Loading alerts...')).not.toBeInTheDocument();
      });
    });

    it('displays alerts after loading', async () => {
=======
    it('displays "Mark All Read" button when there are unacknowledged alerts', async () => {
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /mark all read/i })).toBeInTheDocument();
      });
<<<<<<< HEAD

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
=======
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
    });
  });

  describe('Alert Filters Integration', () => {
    it('renders AlertFilters component with correct counts', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-filters')).toBeInTheDocument();
      });

      // Should show filter counts
      expect(screen.getByText(/All \(3\)/)).toBeInTheDocument();
      expect(screen.getByText(/Critical \(1\)/)).toBeInTheDocument();
      expect(screen.getByText(/High \(2\)/)).toBeInTheDocument();
    });

    it('filters alerts when severity filter is changed', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-filters')).toBeInTheDocument();
      });

      // Mock next fetch for filtered results
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockEmptyResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

<<<<<<< HEAD
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
=======
      // Click critical filter
      const criticalBtn = screen.getByText(/Critical \(1\)/);
      await user.click(criticalBtn);

      await waitFor(() => {
        expect(screen.getByText('Active: critical')).toBeInTheDocument();
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
      });
    });
  });

  describe('Alert Card Rendering', () => {
    it('renders AlertCard components for each alert', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      // Wait for all alert cards to render (more reliable than checking header stats)
      await waitFor(() => {
        expect(screen.getByTestId('alert-card-1')).toBeInTheDocument();
        expect(screen.getByTestId('alert-card-2')).toBeInTheDocument();
        expect(screen.getByTestId('alert-card-3')).toBeInTheDocument();
      });
    });

    it('passes correct props to AlertCard components', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

<<<<<<< HEAD
      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);
=======
      render(<AlertsPage />);
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
        expect(screen.getByText('Unknown person at door')).toBeInTheDocument();
      });
<<<<<<< HEAD

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
=======
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
    });
  });

  describe('Batch Selection and Actions', () => {
    it('renders AlertActions component when alerts exist', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
<<<<<<< HEAD
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
        detection_count: 1,
        notes: null,
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
        detection_count: 1,
        notes: null,
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
    it('calls onViewEventDetails when View Details is clicked', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const handleViewDetails = vi.fn();
      const user = userEvent.setup();

      renderWithQueryClient(<AlertsPage onViewEventDetails={handleViewDetails} />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      const viewButtons = screen.getAllByText('View Details');
      await user.click(viewButtons[0]);

      expect(handleViewDetails).toHaveBeenCalled();
    });

    it('displays camera names in event cards', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      await waitFor(() => {
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      expect(screen.getByText('Back Yard')).toBeInTheDocument();
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
    it('opens modal when clicking on an alert card', async () => {
=======
        expect(screen.getByTestId('alert-actions')).toBeInTheDocument();
      });
    });

    it('allows selecting individual alerts', async () => {
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('checkbox-1')).toBeInTheDocument();
      });

      const checkbox = screen.getByTestId('checkbox-1');
      await user.click(checkbox);

      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeInTheDocument();
      });
    });

    it('allows selecting all alerts', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-actions')).toBeInTheDocument();
      });

      const selectAllBtn = screen.getByText('Select All');
      await user.click(selectAllBtn);

      await waitFor(() => {
        expect(screen.getByText('3 selected')).toBeInTheDocument();
      });
    });

    it('batch acknowledges selected alerts', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      renderWithQueryClient(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-actions')).toBeInTheDocument();
      });

      // Select an alert
      const checkbox = screen.getByTestId('checkbox-1');
      await user.click(checkbox);

      // Click batch acknowledge
      const acknowledgeBtn = screen.getByText('Acknowledge Selected');
      await user.click(acknowledgeBtn);

      await waitFor(() => {
<<<<<<< HEAD
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
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      // Click on first event card to open modal
      const eventCard = screen.getByRole('button', { name: /View details for event from Front Door/i });
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
        expect(screen.getByRole('heading', { name: 'Back Yard' })).toBeInTheDocument();
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
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });

      // Click on event card to open modal
      const eventCard = screen.getByRole('button', { name: /View details for event from Front Door/i });
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
=======
>>>>>>> 79a0e149b (feat: implement 4 parallel tasks - AlertsPage, FeedbackUI, JobTracking, OrphanedCleanup)
        expect(api.updateEvent).toHaveBeenCalledWith(1, { reviewed: true });
      });
    });

    it('clears selection after batch dismiss', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('alert-actions')).toBeInTheDocument();
      });

      // Select an alert
      const checkbox = screen.getByTestId('checkbox-1');
      await user.click(checkbox);

      // Mock refetch
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce({ ...mockHighResponse, items: [mockHighRiskEvents[1]] })
        .mockResolvedValueOnce(mockCriticalResponse);

      // Click batch dismiss
      const dismissBtn = screen.getByText('Dismiss Selected');
      await user.click(dismissBtn);

      await waitFor(() => {
        expect(screen.getByText('0 selected')).toBeInTheDocument();
      });
    });
  });

  describe('Individual Alert Actions', () => {
    it('acknowledges individual alert', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('acknowledge-1')).toBeInTheDocument();
      });

      const acknowledgeBtn = screen.getByTestId('acknowledge-1');
      await user.click(acknowledgeBtn);

      await waitFor(() => {
        expect(api.updateEvent).toHaveBeenCalledWith(1, { reviewed: true });
      });
    });

    it('dismisses individual alert', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockHighResponse)
        .mockResolvedValueOnce(mockCriticalResponse);

      const user = userEvent.setup();
      render(<AlertsPage />);

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.getByText(/unacknowledged/i)).toBeInTheDocument();
      });

      // Now check for dismiss button
      const dismissBtn = screen.getByTestId('dismiss-1');
      await user.click(dismissBtn);

      // Alert should be removed from DOM (component handles dismiss locally, not via refetch)
      await waitFor(() => {
        expect(screen.queryByTestId('alert-card-1')).not.toBeInTheDocument();
      });
    });
  });

  describe('Empty States', () => {
    it('shows empty state when no alerts exist', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockEmptyResponse)
        .mockResolvedValueOnce(mockEmptyResponse);

      render(<AlertsPage />);

      // Wait for loading to complete - empty state shows "No Alerts at This Time"
      await waitFor(() => {
        expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
      });

      expect(screen.getByText(/no alerts/i)).toBeInTheDocument();
    });

    it('does not render AlertActions when no alerts', async () => {
      vi.mocked(api.fetchEvents)
        .mockResolvedValueOnce(mockEmptyResponse)
        .mockResolvedValueOnce(mockEmptyResponse);

      render(<AlertsPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('alert-actions')).not.toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('displays error message when API fails', async () => {
      vi.mocked(api.fetchEvents).mockRejectedValue(new Error('Network error'));

      render(<AlertsPage />);

      // Wait for error state to appear - component shows "Error Loading Alerts" on failure
      await waitFor(
        () => {
          expect(screen.getByText(/error loading alerts/i)).toBeInTheDocument();
        },
        { timeout: 3000 }
      );
    });
  });
});

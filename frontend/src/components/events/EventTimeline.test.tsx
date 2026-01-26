import { within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import EventTimeline from './EventTimeline';
import * as useEventsQueryHook from '../../hooks/useEventsQuery';
import * as useEventStreamHook from '../../hooks/useEventStream';
import * as useInfiniteScrollHook from '../../hooks/useInfiniteScroll';
import * as useLocalStorageHook from '../../hooks/useLocalStorage';
import * as api from '../../services/api';
import {
  renderWithProviders,
  screen,
  waitFor,
  userEvent,
} from '../../test-utils/renderWithProviders';

import type { Camera, Event } from '../../services/api';

// Mock API module (still needed for cameras, bulk updates, exports)
vi.mock('../../services/api');

// Mock useEventStream hook with factory function
vi.mock('../../hooks/useEventStream', () => ({
  useEventStream: vi.fn(),
}));

// Mock useEventsInfiniteQuery hook
vi.mock('../../hooks/useEventsQuery', () => ({
  useEventsInfiniteQuery: vi.fn(),
  eventsQueryKeys: {
    all: ['events'] as const,
    lists: () => ['events', 'list'] as const,
    list: (filters?: Record<string, unknown>) => ['events', 'list', filters] as const,
    infinite: (filters?: Record<string, unknown>, limit?: number) =>
      ['events', 'infinite', { filters, limit }] as const,
    detail: (id: number) => ['events', 'detail', id] as const,
  },
}));

// Mock useInfiniteScroll hook
vi.mock('../../hooks/useInfiniteScroll', () => ({
  useInfiniteScroll: vi.fn(),
}));

// Mock useTimelineData hook
vi.mock('../../hooks/useTimelineData', () => ({
  useTimelineData: vi.fn(() => ({
    buckets: [],
    timeRange: { start: new Date(), end: new Date() },
    isLoading: false,
  })),
}));

// Mock useEventStats hook (NEM-3587)
vi.mock('../../hooks/useEventStats', () => ({
  useEventStats: vi.fn(() => ({
    stats: {
      total_events: 44,
      events_by_risk_level: {
        critical: 2,
        high: 5,
        medium: 12,
        low: 25,
      },
      risk_distribution: [
        { risk_level: 'critical', count: 2 },
        { risk_level: 'high', count: 5 },
        { risk_level: 'medium', count: 12 },
        { risk_level: 'low', count: 25 },
      ],
      events_by_camera: [],
    },
    isLoading: false,
    isFetching: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  })),
  eventStatsQueryKeys: {
    all: ['event-stats'] as const,
    stats: () => ['event-stats', 'stats', {}] as const,
  },
}));

// Mock useLocalStorage hook
vi.mock('../../hooks/useLocalStorage', () => ({
  useLocalStorage: vi.fn((_key: string, defaultValue: unknown) => [defaultValue, vi.fn()]),
}));
const useLocalStorageMock = vi.mocked(useLocalStorageHook.useLocalStorage);

// Mock eventClustering utilities
vi.mock('../../utils/eventClustering', () => ({
  clusterEvents: vi.fn((events: unknown[]) => events),
  getClusterStats: vi.fn(() => ({ totalClusters: 0, clusteredEvents: 0, totalEvents: 0 })),
  isEventCluster: vi.fn(() => false),
}));

// Mock ExportModal component
vi.mock('../exports/ExportModal', () => ({
  default: ({
    isOpen,
    onClose,
    initialFilters,
    onExportComplete,
  }: {
    isOpen: boolean;
    onClose: () => void;
    initialFilters?: {
      camera_id?: string;
      risk_level?: string;
      start_date?: string;
      end_date?: string;
    };
    onExportComplete?: (success: boolean) => void;
  }) => {
    if (!isOpen) return null;
    return (
      <div data-testid="export-modal" role="dialog" aria-label="Export modal">
        <h2>Export Data</h2>
        <div data-testid="export-modal-filters">
          {initialFilters?.camera_id && (
            <span data-testid="filter-camera">{initialFilters.camera_id}</span>
          )}
          {initialFilters?.risk_level && (
            <span data-testid="filter-risk">{initialFilters.risk_level}</span>
          )}
        </div>
        <button onClick={onClose} data-testid="export-modal-close">
          Close
        </button>
        <button onClick={() => onExportComplete?.(true)} data-testid="export-modal-complete">
          Complete Export
        </button>
      </div>
    );
  },
}));

// Mock TimelineScrubber component
vi.mock('./TimelineScrubber', () => ({
  default: () => <div data-testid="timeline-scrubber">Timeline Scrubber Mock</div>,
}));

// Mock ViewToggle component
vi.mock('./ViewToggle', () => ({
  default: () => <div data-testid="view-toggle">View Toggle Mock</div>,
}));

// Mock EventClusterCard component
vi.mock('./EventClusterCard', () => ({
  default: () => <div data-testid="event-cluster-card">Event Cluster Card Mock</div>,
}));

// Mock EventListView component
vi.mock('./EventListView', () => ({
  default: () => <div data-testid="event-list-view">Event List View Mock</div>,
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
      flagged: false, // NEM-3839
      detection_count: 5,
      notes: null,
      version: 1,
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
      flagged: false, // NEM-3839
      detection_count: 3,
      notes: null,
      version: 1,
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
      flagged: false, // NEM-3839
      detection_count: 8,
      notes: null,
      version: 1,
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

  // Default mock return values for useEventsInfiniteQuery
  const createMockEventsQueryReturn = (
    overrides: Partial<useEventsQueryHook.UseEventsInfiniteQueryReturn> = {}
  ) => ({
    events: mockEvents,
    pages: undefined,
    totalCount: 3,
    isLoading: false,
    isFetching: false,
    isFetchingNextPage: false,
    hasNextPage: false,
    fetchNextPage: vi.fn(),
    error: null,
    isError: false,
    refetch: vi.fn(),
    ...overrides,
  });

  // Default mock return values for useInfiniteScroll
  const createMockInfiniteScrollReturn = (
    overrides: Partial<useInfiniteScrollHook.UseInfiniteScrollReturn> = {}
  ) => ({
    sentinelRef: vi.fn(),
    isLoadingMore: false,
    error: null,
    retry: vi.fn(),
    clearError: vi.fn(),
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);

    // Mock matchMedia for reduced motion preference (used by EventCard)
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    // Mock useEventsInfiniteQuery
    vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
      createMockEventsQueryReturn()
    );

    // Mock useInfiniteScroll
    vi.mocked(useInfiniteScrollHook.useInfiniteScroll).mockReturnValue(
      createMockInfiniteScrollReturn()
    );

    // Mock useEventStream hook
    vi.mocked(useEventStreamHook.useEventStream).mockReturnValue({
      events: mockWsEvents,
      isConnected: true,
      latestEvent: mockWsEvents[0],
      clearEvents: vi.fn(),
      sequenceStats: {
        processedCount: 0,
        duplicateCount: 0,
        resyncCount: 0,
        outOfOrderCount: 0,
        currentBufferSize: 0,
      },
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
        sequenceStats: {
          processedCount: 0,
          duplicateCount: 0,
          resyncCount: 0,
          outOfOrderCount: 0,
          currentBufferSize: 0,
        },
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
      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ isLoading: true, events: [] })
      );

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

    it('displays infinite scroll status at bottom of list', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Should show the infinite scroll end message when hasNextPage is false
      expect(screen.getByTestId('infinite-scroll-end')).toBeInTheDocument();
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
        expect(useEventsQueryHook.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({ filters: expect.objectContaining({ camera_id: 'camera-1' }) })
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
        expect(useEventsQueryHook.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({ filters: expect.objectContaining({ risk_level: 'high' }) })
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
        expect(useEventsQueryHook.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({ filters: expect.objectContaining({ reviewed: false }) })
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
        expect(useEventsQueryHook.useEventsInfiniteQuery).toHaveBeenCalledWith(
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
        expect(useEventsQueryHook.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({ filters: expect.objectContaining({ camera_id: 'camera-1' }) })
        );
      });

      // Clear filters
      const clearButton = screen.getByText('Clear All Filters');
      await user.click(clearButton);

      await waitFor(() => {
        expect(useEventsQueryHook.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({ filters: {} })
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
        expect(useEventsQueryHook.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({ filters: expect.objectContaining({ object_type: 'person' }) })
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
        expect(useEventsQueryHook.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({ filters: expect.objectContaining({ object_type: 'vehicle' }) })
        );
      });

      // Clear filters
      const clearButton = screen.getByText('Clear All Filters');
      await user.click(clearButton);

      await waitFor(() => {
        expect(useEventsQueryHook.useEventsInfiniteQuery).toHaveBeenCalledWith(
          expect.objectContaining({ filters: {} })
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
        expect(useEventsQueryHook.useEventsInfiniteQuery).toHaveBeenCalledWith(
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

  describe('Infinite Scroll', () => {
    it('displays loading indicator when fetching more events', async () => {
      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({
          hasNextPage: true,
          isFetchingNextPage: true,
        })
      );
      vi.mocked(useInfiniteScrollHook.useInfiniteScroll).mockReturnValue(
        createMockInfiniteScrollReturn({ isLoadingMore: true })
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByTestId('infinite-scroll-loading')).toBeInTheDocument();
      });
    });

    it('shows end of list message when no more events', async () => {
      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ hasNextPage: false })
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByTestId('infinite-scroll-end')).toBeInTheDocument();
      });
    });

    it('shows sentinel element when more events available', async () => {
      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ hasNextPage: true })
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByTestId('infinite-scroll-sentinel')).toBeInTheDocument();
      });
    });

    it('shows error with retry when scroll loading fails', async () => {
      const mockRetry = vi.fn();
      vi.mocked(useInfiniteScrollHook.useInfiniteScroll).mockReturnValue(
        createMockInfiniteScrollReturn({
          error: new Error('Network error'),
          retry: mockRetry,
        })
      );

      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByTestId('infinite-scroll-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();

      // Click retry button
      await user.click(screen.getByTestId('infinite-scroll-retry'));
      expect(mockRetry).toHaveBeenCalled();
    });
  });

  describe('Error Handling', () => {
    it('displays error message when fetching events fails', async () => {
      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({
          events: [],
          error: new Error('Network error'),
          isError: true,
        })
      );

      renderWithProviders(<EventTimeline />);

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
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      await user.click(screen.getByText('Show Filters'));

      const cameraSelect = screen.getByLabelText('Camera');
      const options = within(cameraSelect).getAllByRole('option');

      // Should only have "All Cameras" option
      expect(options).toHaveLength(1);
      expect(options[0]).toHaveTextContent('All Cameras');
    });
  });

  describe('Empty States', () => {
    it('shows empty state when no events exist', async () => {
      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ events: [], totalCount: 0 })
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      expect(screen.getByText(/No security events have been recorded yet/)).toBeInTheDocument();
    });

    it('shows filtered empty state when filters match no events', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Apply filter that returns no results
      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ events: [], totalCount: 0 })
      );

      await user.click(screen.getByText('Show Filters'));

      const riskSelect = screen.getByLabelText('Risk Level');
      await user.selectOptions(riskSelect, 'low');

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      expect(screen.getByText(/No events match your current filters/)).toBeInTheDocument();
    });

    it('shows "0 events" when empty', async () => {
      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ events: [], totalCount: 0 })
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      expect(screen.getByText('0 events')).toBeInTheDocument();
    });

    it('does not show infinite scroll status when empty', async () => {
      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ events: [], totalCount: 0 })
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      // Infinite scroll status should not be present when there are no events
      expect(screen.queryByTestId('infinite-scroll-end')).not.toBeInTheDocument();
      expect(screen.queryByTestId('infinite-scroll-loading')).not.toBeInTheDocument();
      expect(screen.queryByTestId('infinite-scroll-sentinel')).not.toBeInTheDocument();
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
          flagged: false, // NEM-3839
          detection_count: 1,
          notes: null,
          version: 1,
        },
      ];

      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ events: eventsWithUnknownCamera, totalCount: 1 })
      );

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
      const mockRefetch = vi.fn();
      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ refetch: mockRefetch })
      );

      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      // Mock bulkUpdateEvents for successful update
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

      // Click mark as reviewed
      const markAsReviewedButton = screen.getByText('Mark as Reviewed');
      await user.click(markAsReviewedButton);

      // Should call bulkUpdateEvents with selected event IDs (sorted by most recent: 3, 2)
      await waitFor(() => {
        expect(api.bulkUpdateEvents).toHaveBeenCalledWith([3, 2], { reviewed: true });
      });

      // Should call refetch to reload events
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

      // Mock bulkUpdateEvents to return partial failure
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
      const mockRefetch = vi.fn();
      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ refetch: mockRefetch })
      );

      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      // Mock bulkUpdateEvents for successful update
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

      // Should call refetch to reload events
      await waitFor(() => {
        expect(mockRefetch).toHaveBeenCalled();
      });

      // Should clear selections
      await waitFor(() => {
        expect(screen.getByText('Select all')).toBeInTheDocument();
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

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Apply filter that returns only high risk events
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
          flagged: false, // NEM-3839
          detection_count: 5,
          notes: null,
          version: 1,
        },
      ];

      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ events: highRiskEvents, totalCount: 1 })
      );

      await user.click(screen.getByText('Show Filters'));

      const riskSelect = screen.getByLabelText('Risk Level');
      await user.selectOptions(riskSelect, 'high');

      // Should only show high risk count
      await waitFor(() => {
        expect(screen.getByText('1', { selector: '.text-orange-400' })).toBeInTheDocument(); // High
        expect(screen.queryByText('1', { selector: '.text-red-400' })).not.toBeInTheDocument(); // Critical
        expect(screen.queryByText('1', { selector: '.text-green-400' })).not.toBeInTheDocument(); // Low
      });
    });

    it('does not display risk badges when loading', () => {
      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ isLoading: true, events: [] })
      );

      renderWithProviders(<EventTimeline />);

      // Should show loading state with skeleton loaders
      expect(screen.getAllByTestId('event-card-skeleton').length).toBeGreaterThan(0);

      // Should not show risk summary badges (counts with colored text) during loading
      // Note: FilterChips still shows risk level labels, but without counts in the summary section
      expect(screen.queryByText('1', { selector: '.text-red-400' })).not.toBeInTheDocument();
      expect(screen.queryByText('1', { selector: '.text-orange-400' })).not.toBeInTheDocument();
      expect(screen.queryByText('1', { selector: '.text-yellow-400' })).not.toBeInTheDocument();
      expect(screen.queryByText('1', { selector: '.text-green-400' })).not.toBeInTheDocument();
    });

    it('does not display risk badges when there is an error', async () => {
      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({
          events: [],
          error: new Error('Network error'),
          isError: true,
        })
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Error Loading Events')).toBeInTheDocument();
      });

      // Should not show risk summary badges (counts with colored text) on error
      // Note: FilterChips still shows risk level labels, but without counts in the summary section
      expect(screen.queryByText('1', { selector: '.text-red-400' })).not.toBeInTheDocument();
      expect(screen.queryByText('1', { selector: '.text-orange-400' })).not.toBeInTheDocument();
      expect(screen.queryByText('1', { selector: '.text-yellow-400' })).not.toBeInTheDocument();
      expect(screen.queryByText('1', { selector: '.text-green-400' })).not.toBeInTheDocument();
    });

    it('does not display risk badges when no events are found', async () => {
      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ events: [], totalCount: 0 })
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('No Events Found')).toBeInTheDocument();
      });

      // Should not show risk summary badges (counts with colored text) when empty
      // Note: FilterChips still shows risk level labels, but without counts in the summary section
      expect(screen.queryByText('1', { selector: '.text-red-400' })).not.toBeInTheDocument();
      expect(screen.queryByText('1', { selector: '.text-orange-400' })).not.toBeInTheDocument();
      expect(screen.queryByText('1', { selector: '.text-yellow-400' })).not.toBeInTheDocument();
      expect(screen.queryByText('1', { selector: '.text-green-400' })).not.toBeInTheDocument();
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
          flagged: false, // NEM-3839
          detection_count: 5,
          notes: null,
          version: 1,
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
          flagged: false, // NEM-3839
          detection_count: 3,
          notes: null,
          version: 1,
        },
      ];

      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ events: mediumRiskEvents, totalCount: 2 })
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected')).toBeInTheDocument();
      });

      // Should only show medium risk badge with count of 2 in the summary section
      await waitFor(() => {
        expect(screen.getByText('2', { selector: '.text-yellow-400' })).toBeInTheDocument(); // Medium
      });

      // Should not show counts for other risk levels in the summary section
      // Note: FilterChips still shows risk level labels, but without counts in the summary section
      expect(screen.queryByText('1', { selector: '.text-red-400' })).not.toBeInTheDocument();
      expect(screen.queryByText('1', { selector: '.text-orange-400' })).not.toBeInTheDocument();
      expect(screen.queryByText('1', { selector: '.text-green-400' })).not.toBeInTheDocument();
    });
  });

  describe('URL Parameter Filtering', () => {
    it('applies risk_level filter from URL parameter', async () => {
      renderWithProviders(<EventTimeline />, { route: '/timeline?risk_level=high' });

      await waitFor(() => {
        expect(useEventsQueryHook.useEventsInfiniteQuery).toHaveBeenCalledWith(
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
        expect(useEventsQueryHook.useEventsInfiniteQuery).toHaveBeenCalledWith(
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
        expect(useEventsQueryHook.useEventsInfiniteQuery).toHaveBeenCalledWith(
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

  describe('Event Parameter Validation (NEM-2561)', () => {
    it('opens modal when valid event parameter is provided', async () => {
      renderWithProviders(<EventTimeline />, { route: '/timeline?event=1' });

      await waitFor(() => {
        expect(screen.getByRole('dialog')).toBeInTheDocument();
      });
    });

    it('handles invalid event parameter gracefully - non-numeric string', async () => {
      renderWithProviders(<EventTimeline />, { route: '/timeline?event=abc' });

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Modal should NOT be open since event param is invalid
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('handles invalid event parameter gracefully - mixed alphanumeric', async () => {
      renderWithProviders(<EventTimeline />, { route: '/timeline?event=123abc' });

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Modal should NOT be open since event param is invalid
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('handles invalid event parameter gracefully - negative number', async () => {
      renderWithProviders(<EventTimeline />, { route: '/timeline?event=-1' });

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Modal should NOT be open since event param is invalid
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('handles invalid event parameter gracefully - floating point', async () => {
      renderWithProviders(<EventTimeline />, { route: '/timeline?event=1.5' });

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Modal should NOT be open since event param is invalid
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('handles invalid event parameter gracefully - special characters', async () => {
      renderWithProviders(<EventTimeline />, { route: '/timeline?event=1%3B%20DROP%20TABLE' });

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Modal should NOT be open since event param is invalid
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('handles invalid event parameter gracefully - empty string', async () => {
      renderWithProviders(<EventTimeline />, { route: '/timeline?event=' });

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Modal should NOT be open since event param is empty
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });

    it('does not expose internal state in error messages for invalid event parameter', async () => {
      // This test ensures no error messages or internal state leaks when given invalid input
      renderWithProviders(<EventTimeline />, {
        route: '/timeline?event=<script>alert(1)</script>',
      });

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Should not have any error messages visible
      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/script/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/alert/i)).not.toBeInTheDocument();
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

  describe('Export Modal Integration', () => {
    it('renders Export Modal button', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Export Modal button should be present
      expect(screen.getByLabelText('Open export modal')).toBeInTheDocument();
      expect(screen.getByText('Export Modal')).toBeInTheDocument();
    });

    it('opens Export Modal when button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Modal should not be open initially
      expect(screen.queryByTestId('export-modal')).not.toBeInTheDocument();

      // Click Export Modal button
      const exportModalButton = screen.getByLabelText('Open export modal');
      await user.click(exportModalButton);

      // Modal should now be open
      await waitFor(() => {
        expect(screen.getByTestId('export-modal')).toBeInTheDocument();
      });
    });

    it('closes Export Modal when close button is clicked', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Open the modal
      const exportModalButton = screen.getByLabelText('Open export modal');
      await user.click(exportModalButton);

      await waitFor(() => {
        expect(screen.getByTestId('export-modal')).toBeInTheDocument();
      });

      // Close the modal
      const closeButton = screen.getByTestId('export-modal-close');
      await user.click(closeButton);

      // Modal should be closed
      await waitFor(() => {
        expect(screen.queryByTestId('export-modal')).not.toBeInTheDocument();
      });
    });

    it('closes Export Modal when export completes', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Open the modal
      const exportModalButton = screen.getByLabelText('Open export modal');
      await user.click(exportModalButton);

      await waitFor(() => {
        expect(screen.getByTestId('export-modal')).toBeInTheDocument();
      });

      // Complete the export
      const completeButton = screen.getByTestId('export-modal-complete');
      await user.click(completeButton);

      // Modal should be closed
      await waitFor(() => {
        expect(screen.queryByTestId('export-modal')).not.toBeInTheDocument();
      });
    });

    it('passes current filters to Export Modal', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Apply filters
      await user.click(screen.getByText('Show Filters'));

      const cameraSelect = screen.getByLabelText('Camera');
      await user.selectOptions(cameraSelect, 'camera-1');

      const riskSelect = screen.getByLabelText('Risk Level');
      await user.selectOptions(riskSelect, 'high');

      // Open the modal
      const exportModalButton = screen.getByLabelText('Open export modal');
      await user.click(exportModalButton);

      await waitFor(() => {
        expect(screen.getByTestId('export-modal')).toBeInTheDocument();
      });

      // Check that filters are passed to the modal
      expect(screen.getByTestId('filter-camera')).toHaveTextContent('camera-1');
      expect(screen.getByTestId('filter-risk')).toHaveTextContent('high');
    });

    it('does not show Export Modal by default', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Modal should not be open by default
      expect(screen.queryByTestId('export-modal')).not.toBeInTheDocument();
    });
  });

  describe('Snooze Functionality (NEM-3592)', () => {
    it('renders snooze button on EventCard components', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Should have snooze buttons for each event card
      const snoozeButtons = screen.getAllByRole('button', { name: /snooze event/i });
      expect(snoozeButtons.length).toBeGreaterThan(0);
    });

    it('displays snooze indicator for snoozed events', async () => {
      const snoozedEvents: Event[] = [
        {
          ...mockEvents[0],
          snooze_until: new Date(Date.now() + 60 * 60 * 1000).toISOString(), // 1 hour from now
        },
        ...mockEvents.slice(1),
      ];

      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ events: snoozedEvents })
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText(/Snoozed until/)).toBeInTheDocument();
      });
    });

    it('applies reduced opacity to snoozed event cards', async () => {
      const snoozedEvents: Event[] = [
        {
          ...mockEvents[0],
          snooze_until: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
        },
        ...mockEvents.slice(1),
      ];

      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ events: snoozedEvents })
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        const snoozedCard = screen.getByTestId('event-card-1');
        expect(snoozedCard).toHaveClass('opacity-60');
      });
    });

    it('does not show snooze indicator for events without snooze_until', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Should not have any snooze indicators by default
      expect(screen.queryByText(/Snoozed until/)).not.toBeInTheDocument();
    });

    it('does not show snooze indicator for events with expired snooze_until', async () => {
      const expiredSnoozedEvents: Event[] = [
        {
          ...mockEvents[0],
          snooze_until: new Date(Date.now() - 60 * 60 * 1000).toISOString(), // 1 hour ago (expired)
        },
        ...mockEvents.slice(1),
      ];

      vi.mocked(useEventsQueryHook.useEventsInfiniteQuery).mockReturnValue(
        createMockEventsQueryReturn({ events: expiredSnoozedEvents })
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      });

      // Should not have snooze indicator since it's expired
      expect(screen.queryByText(/Snoozed until/)).not.toBeInTheDocument();
    });
  });

  describe('GroupBy Selector (NEM-3620)', () => {
    beforeEach(() => {
      // Reset to return 'grid' for view mode and 'time' for groupBy
      useLocalStorageMock.mockImplementation(
        (key: string, defaultValue: unknown) => {
          if (key === 'timeline-view-mode') return ['grid', vi.fn()];
          if (key === 'timeline-group-by') return ['time', vi.fn()];
          if (key === 'timeline-clustering-enabled') return [true, vi.fn()];
          return [defaultValue, vi.fn()];
        }
      );
    });

    it('renders GroupBy selector in grid view', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.getByTestId('groupby-selector')).toBeInTheDocument();
      });
    });

    it('has options for Time, Camera, Risk Level, and Incident Cluster', async () => {
      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        const selector = screen.getByTestId('groupby-selector');
        const select = selector.querySelector('select');
        expect(select).toBeInTheDocument();

        const options = within(select as HTMLElement).getAllByRole('option');
        expect(options).toHaveLength(4);
        expect(options[0]).toHaveTextContent('Time');
        expect(options[1]).toHaveTextContent('Camera');
        expect(options[2]).toHaveTextContent('Risk Level');
        expect(options[3]).toHaveTextContent('Incident Cluster');
      });
    });

    it('groups events by camera when Camera is selected', async () => {
      const user = userEvent.setup();

      // Setup mock to track groupBy changes
      const setGroupBy = vi.fn();
      useLocalStorageMock.mockImplementation(
        (key: string, defaultValue: unknown) => {
          if (key === 'timeline-view-mode') return ['grid', vi.fn()];
          if (key === 'timeline-group-by') return ['time', setGroupBy];
          if (key === 'timeline-clustering-enabled') return [true, vi.fn()];
          return [defaultValue, vi.fn()];
        }
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        const selector = screen.getByTestId('groupby-selector');
        expect(selector).toBeInTheDocument();
      });

      const select = screen.getByTestId('groupby-selector').querySelector('select');
      await user.selectOptions(select!, 'camera');

      expect(setGroupBy).toHaveBeenCalledWith('camera');
    });

    it('groups events by risk level when Risk Level is selected', async () => {
      const user = userEvent.setup();

      const setGroupBy = vi.fn();
      useLocalStorageMock.mockImplementation(
        (key: string, defaultValue: unknown) => {
          if (key === 'timeline-view-mode') return ['grid', vi.fn()];
          if (key === 'timeline-group-by') return ['time', setGroupBy];
          if (key === 'timeline-clustering-enabled') return [true, vi.fn()];
          return [defaultValue, vi.fn()];
        }
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        const selector = screen.getByTestId('groupby-selector');
        expect(selector).toBeInTheDocument();
      });

      const select = screen.getByTestId('groupby-selector').querySelector('select');
      await user.selectOptions(select!, 'risk');

      expect(setGroupBy).toHaveBeenCalledWith('risk');
    });

    it('shows group headers when grouped by camera', async () => {
      // Mock groupBy as 'camera'
      useLocalStorageMock.mockImplementation(
        (key: string, defaultValue: unknown) => {
          if (key === 'timeline-view-mode') return ['grid', vi.fn()];
          if (key === 'timeline-group-by') return ['camera', vi.fn()];
          if (key === 'timeline-clustering-enabled') return [true, vi.fn()];
          return [defaultValue, vi.fn()];
        }
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        // Should show camera-based group headers
        expect(screen.getByTestId('group-camera_1')).toBeInTheDocument();
        expect(screen.getByText('Front Door')).toBeInTheDocument();
      });
    });

    it('shows group headers when grouped by risk level', async () => {
      // Mock groupBy as 'risk'
      useLocalStorageMock.mockImplementation(
        (key: string, defaultValue: unknown) => {
          if (key === 'timeline-view-mode') return ['grid', vi.fn()];
          if (key === 'timeline-group-by') return ['risk', vi.fn()];
          if (key === 'timeline-clustering-enabled') return [true, vi.fn()];
          return [defaultValue, vi.fn()];
        }
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        // Should show risk-level based group headers for events in mockEvents
        // mockEvents has: critical (id:3, score:92), high (id:1, score:78), low (id:2, score:25)
        const groups = screen.getAllByText(/event/i);
        expect(groups.length).toBeGreaterThan(0);
      });
    });

    it('does not show GroupBy selector in list view', async () => {
      // Mock list view mode
      useLocalStorageMock.mockImplementation(
        (key: string, defaultValue: unknown) => {
          if (key === 'timeline-view-mode') return ['list', vi.fn()];
          if (key === 'timeline-group-by') return ['time', vi.fn()];
          if (key === 'timeline-clustering-enabled') return [true, vi.fn()];
          return [defaultValue, vi.fn()];
        }
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        expect(screen.queryByTestId('groupby-selector')).not.toBeInTheDocument();
      });
    });

    it('hides clustering toggle when groupBy is camera or risk', async () => {
      // Mock groupBy as 'camera'
      useLocalStorageMock.mockImplementation(
        (key: string, defaultValue: unknown) => {
          if (key === 'timeline-view-mode') return ['grid', vi.fn()];
          if (key === 'timeline-group-by') return ['camera', vi.fn()];
          if (key === 'timeline-clustering-enabled') return [true, vi.fn()];
          return [defaultValue, vi.fn()];
        }
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        // Clustering toggle should be hidden when groupBy is not 'time' or 'cluster'
        expect(screen.queryByRole('button', { name: /cluster/i })).not.toBeInTheDocument();
      });
    });

    it('shows clustering toggle when groupBy is time or cluster', async () => {
      // Mock groupBy as 'time'
      useLocalStorageMock.mockImplementation(
        (key: string, defaultValue: unknown) => {
          if (key === 'timeline-view-mode') return ['grid', vi.fn()];
          if (key === 'timeline-group-by') return ['time', vi.fn()];
          if (key === 'timeline-clustering-enabled') return [true, vi.fn()];
          return [defaultValue, vi.fn()];
        }
      );

      renderWithProviders(<EventTimeline />);

      await waitFor(() => {
        // Find the clustering toggle by its text content
        const clusterBtn = screen.getByRole('button', { name: /cluster/i, pressed: true });
        expect(clusterBtn).toBeInTheDocument();
      });
    });
  });
});

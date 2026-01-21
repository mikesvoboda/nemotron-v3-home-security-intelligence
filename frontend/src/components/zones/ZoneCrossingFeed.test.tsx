/**
 * Tests for ZoneCrossingFeed component (NEM-3195)
 *
 * This module tests the zone crossing feed component:
 * - Rendering event list
 * - Filter functionality
 * - Empty state
 * - Connection status indicator
 * - Event click handling
 * - Clear functionality
 */

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import { ZoneCrossingFeed } from './ZoneCrossingFeed';
import { ZoneCrossingType } from '../../types/zoneCrossing';

import type { ZoneCrossingEvent, ZoneCrossingFilters } from '../../types/zoneCrossing';

// Track mock state
let mockEvents: ZoneCrossingEvent[] = [];
let mockIsConnected = true;
let mockFilters: ZoneCrossingFilters = { zoneId: 'all', entityType: 'all', eventType: 'all' };
let mockSetFilters: (filters: ZoneCrossingFilters) => void = vi.fn();
let mockClearEvents: () => void = vi.fn();

// Mock useZoneCrossingEvents
vi.mock('../../hooks/useZoneCrossingEvents', () => ({
  useZoneCrossingEvents: vi.fn(() => ({
    events: mockEvents,
    isConnected: mockIsConnected,
    reconnectCount: 0,
    hasExhaustedRetries: false,
    clearEvents: mockClearEvents,
    setFilters: mockSetFilters,
    filters: mockFilters,
  })),
}));

// Mock useZonesQuery
vi.mock('../../hooks/useZones', () => ({
  useZonesQuery: vi.fn(() => ({
    zones: [
      { id: 'zone-1', name: 'Front Door' },
      { id: 'zone-2', name: 'Back Yard' },
    ],
    total: 2,
    isLoading: false,
    isRefetching: false,
    error: null,
    refetch: vi.fn(),
  })),
}));

// Helper to wrap component with providers
function renderWithProviders(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
}

describe('ZoneCrossingFeed', () => {
  // Helper to create mock event
  const createMockEvent = (
    overrides: Partial<ZoneCrossingEvent> = {}
  ): ZoneCrossingEvent => ({
    type: ZoneCrossingType.ENTER,
    zone_id: 'zone-1',
    zone_name: 'Front Door',
    entity_id: `entity-${Math.random().toString(36).slice(2, 9)}`,
    entity_type: 'person',
    detection_id: 'det-456',
    timestamp: new Date().toISOString(),
    thumbnail_url: null,
    dwell_time: null,
    ...overrides,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockEvents = [];
    mockIsConnected = true;
    mockFilters = { zoneId: 'all', entityType: 'all', eventType: 'all' };
    mockSetFilters = vi.fn();
    mockClearEvents = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders the feed header', () => {
      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.getByText('Zone Crossings')).toBeInTheDocument();
    });

    it('renders filter controls', () => {
      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.getByLabelText('Filter by event type')).toBeInTheDocument();
      expect(screen.getByLabelText('Filter by zone')).toBeInTheDocument();
      expect(screen.getByLabelText('Filter by entity type')).toBeInTheDocument();
    });

    it('renders event count in subtitle', () => {
      mockEvents = [createMockEvent(), createMockEvent()];

      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.getByText('2 events in feed')).toBeInTheDocument();
    });

    it('uses singular "event" for count of 1', () => {
      mockEvents = [createMockEvent()];

      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.getByText('1 event in feed')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      renderWithProviders(<ZoneCrossingFeed className="custom-class" />);

      const feed = screen.getByTestId('zone-crossing-feed');
      expect(feed).toHaveClass('custom-class');
    });

    it('applies custom maxHeight as string', () => {
      const { container } = renderWithProviders(<ZoneCrossingFeed maxHeight="400px" />);

      const scrollContainer = container.querySelector('.overflow-y-auto');
      expect(scrollContainer).toHaveStyle({ maxHeight: '400px' });
    });

    it('applies custom maxHeight as number', () => {
      const { container } = renderWithProviders(<ZoneCrossingFeed maxHeight={500} />);

      const scrollContainer = container.querySelector('.overflow-y-auto');
      expect(scrollContainer).toHaveStyle({ maxHeight: '500px' });
    });
  });

  describe('empty state', () => {
    it('shows empty state when no events', () => {
      mockEvents = [];

      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.getByTestId('crossing-feed-empty')).toBeInTheDocument();
      expect(screen.getByText('No crossing events')).toBeInTheDocument();
      expect(
        screen.getByText('Waiting for zone crossing activity...')
      ).toBeInTheDocument();
    });

    it('shows filter hint when no events with active filters', () => {
      mockEvents = [];
      mockFilters = { zoneId: 'zone-1', entityType: 'all', eventType: 'all' };

      renderWithProviders(<ZoneCrossingFeed initialFilters={{ zoneId: 'zone-1' }} />);

      expect(
        screen.getByText('Try adjusting your filters to see more events.')
      ).toBeInTheDocument();
    });
  });

  describe('event list', () => {
    it('renders list of events', () => {
      mockEvents = [
        createMockEvent({ zone_name: 'Front Door', type: ZoneCrossingType.ENTER }),
        createMockEvent({ zone_name: 'Back Yard', type: ZoneCrossingType.EXIT }),
      ];

      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.getByTestId('crossing-feed-list')).toBeInTheDocument();
      expect(screen.getAllByTestId('zone-crossing-event')).toHaveLength(2);
    });

    it('displays event type label', () => {
      mockEvents = [createMockEvent({ type: ZoneCrossingType.ENTER })];

      renderWithProviders(<ZoneCrossingFeed />);

      const eventCard = screen.getByTestId('zone-crossing-event');
      // Should have the event type label within the card (not the filter option)
      expect(within(eventCard).getByText('Enter')).toBeInTheDocument();
    });

    it('displays zone name', () => {
      mockEvents = [createMockEvent({ zone_name: 'Custom Zone Name' })];

      renderWithProviders(<ZoneCrossingFeed />);

      const eventCard = screen.getByTestId('zone-crossing-event');
      expect(within(eventCard).getByText('Custom Zone Name')).toBeInTheDocument();
    });

    it('displays entity type', () => {
      mockEvents = [createMockEvent({ entity_type: 'vehicle' })];

      renderWithProviders(<ZoneCrossingFeed />);

      const eventCard = screen.getByTestId('zone-crossing-event');
      expect(within(eventCard).getByText('Vehicle')).toBeInTheDocument();
    });

    it('displays formatted timestamp', () => {
      const timestamp = '2024-01-15T10:30:45Z';
      mockEvents = [createMockEvent({ timestamp })];

      renderWithProviders(<ZoneCrossingFeed />);

      // Should display time in local format
      const event = screen.getByTestId('zone-crossing-event');
      expect(event).toHaveTextContent(/\d{1,2}:\d{2}:\d{2}/);
    });

    it('displays dwell time when present', () => {
      mockEvents = [
        createMockEvent({ type: ZoneCrossingType.EXIT, dwell_time: 90 }),
      ];

      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.getByText('1m 30s')).toBeInTheDocument();
    });

    it('does not display dwell time when null', () => {
      mockEvents = [
        createMockEvent({ type: ZoneCrossingType.ENTER, dwell_time: null }),
      ];

      renderWithProviders(<ZoneCrossingFeed />);

      // Should not have clock icon for dwell time in the details section
      const event = screen.getByTestId('zone-crossing-event');
      const detailsText = event.textContent;
      expect(detailsText).not.toContain('--');
    });

    it('displays truncated entity ID', () => {
      mockEvents = [
        createMockEvent({ entity_id: 'very-long-entity-identifier-123456' }),
      ];

      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.getByText(/ID: very-long-en\.\.\./)).toBeInTheDocument();
    });

    it('displays thumbnail when available', () => {
      mockEvents = [
        createMockEvent({ thumbnail_url: 'http://example.com/thumb.jpg' }),
      ];

      renderWithProviders(<ZoneCrossingFeed />);

      const img = screen.getByAltText('person thumbnail');
      expect(img).toHaveAttribute('src', 'http://example.com/thumb.jpg');
    });
  });

  describe('event types styling', () => {
    it('uses green styling for enter events', () => {
      mockEvents = [createMockEvent({ type: ZoneCrossingType.ENTER })];

      renderWithProviders(<ZoneCrossingFeed />);

      const event = screen.getByTestId('zone-crossing-event');
      expect(event).toHaveClass('bg-green-500/10');
      expect(event).toHaveClass('border-green-500/30');
    });

    it('uses red styling for exit events', () => {
      mockEvents = [createMockEvent({ type: ZoneCrossingType.EXIT })];

      renderWithProviders(<ZoneCrossingFeed />);

      const event = screen.getByTestId('zone-crossing-event');
      expect(event).toHaveClass('bg-red-500/10');
      expect(event).toHaveClass('border-red-500/30');
    });

    it('uses orange styling for dwell events', () => {
      mockEvents = [createMockEvent({ type: ZoneCrossingType.DWELL })];

      renderWithProviders(<ZoneCrossingFeed />);

      const event = screen.getByTestId('zone-crossing-event');
      expect(event).toHaveClass('bg-orange-500/10');
      expect(event).toHaveClass('border-orange-500/30');
    });
  });

  describe('filtering', () => {
    it('renders event type filter options', () => {
      renderWithProviders(<ZoneCrossingFeed />);

      const select = screen.getByLabelText('Filter by event type');
      const options = within(select).getAllByRole('option');

      expect(options).toHaveLength(4); // All + 3 types
      expect(options[0]).toHaveValue('all');
      expect(options[1]).toHaveValue('enter');
      expect(options[2]).toHaveValue('exit');
      expect(options[3]).toHaveValue('dwell');
    });

    it('renders zone filter options', () => {
      renderWithProviders(<ZoneCrossingFeed />);

      const select = screen.getByLabelText('Filter by zone');
      const options = within(select).getAllByRole('option');

      expect(options).toHaveLength(3); // All + 2 zones
      expect(options[0]).toHaveValue('all');
    });

    it('includes zones from events in zone filter', () => {
      mockEvents = [
        createMockEvent({ zone_id: 'zone-3', zone_name: 'Custom Zone' }),
      ];

      renderWithProviders(<ZoneCrossingFeed />);

      const select = screen.getByLabelText('Filter by zone');
      expect(within(select).getByText('Custom Zone')).toBeInTheDocument();
    });

    it('includes common entity types in entity filter', () => {
      renderWithProviders(<ZoneCrossingFeed />);

      const select = screen.getByLabelText('Filter by entity type');
      const options = within(select).getAllByRole('option');

      expect(options.length).toBeGreaterThanOrEqual(4); // All + person, vehicle, unknown
    });

    it('updates state when event type filter changes', async () => {
      const user = userEvent.setup();

      renderWithProviders(<ZoneCrossingFeed />);

      const select = screen.getByLabelText('Filter by event type');
      await user.selectOptions(select, 'enter');

      // Component should update internal state (we test the filter select value)
      expect(select).toHaveValue('enter');
    });

    it('updates state when zone filter changes', async () => {
      const user = userEvent.setup();

      renderWithProviders(<ZoneCrossingFeed />);

      const select = screen.getByLabelText('Filter by zone');
      await user.selectOptions(select, 'zone-1');

      expect(select).toHaveValue('zone-1');
    });

    it('updates state when entity type filter changes', async () => {
      const user = userEvent.setup();

      renderWithProviders(<ZoneCrossingFeed />);

      const select = screen.getByLabelText('Filter by entity type');
      await user.selectOptions(select, 'person');

      expect(select).toHaveValue('person');
    });

    it('uses initial filters from props', () => {
      renderWithProviders(
        <ZoneCrossingFeed
          initialFilters={{
            eventType: ZoneCrossingType.ENTER,
            zoneId: 'zone-1',
          }}
        />
      );

      expect(screen.getByLabelText('Filter by event type')).toHaveValue('enter');
      expect(screen.getByLabelText('Filter by zone')).toHaveValue('zone-1');
    });

    it('uses zoneId prop for initial zone filter', () => {
      renderWithProviders(<ZoneCrossingFeed zoneId="zone-2" />);

      expect(screen.getByLabelText('Filter by zone')).toHaveValue('zone-2');
    });
  });

  describe('connection status', () => {
    it('shows Live indicator when connected', () => {
      mockIsConnected = true;

      renderWithProviders(<ZoneCrossingFeed enableRealtime />);

      expect(screen.getByText('Live')).toBeInTheDocument();
      const status = screen.getByTestId('connection-status');
      expect(status).toHaveClass('bg-green-500/10');
    });

    it('shows Offline indicator when disconnected', () => {
      mockIsConnected = false;

      renderWithProviders(<ZoneCrossingFeed enableRealtime />);

      expect(screen.getByText('Offline')).toBeInTheDocument();
      const status = screen.getByTestId('connection-status');
      expect(status).toHaveClass('bg-gray-700');
    });

    it('hides connection indicator when realtime disabled', () => {
      renderWithProviders(<ZoneCrossingFeed enableRealtime={false} />);

      expect(screen.queryByTestId('connection-status')).not.toBeInTheDocument();
      expect(screen.queryByText('Live')).not.toBeInTheDocument();
      expect(screen.queryByText('Offline')).not.toBeInTheDocument();
    });
  });

  describe('clear functionality', () => {
    it('shows clear button when events exist', () => {
      mockEvents = [createMockEvent()];

      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument();
    });

    it('hides clear button when no events', () => {
      mockEvents = [];

      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.queryByRole('button', { name: /clear/i })).not.toBeInTheDocument();
    });

    it('calls clearEvents when clear button clicked', async () => {
      const user = userEvent.setup();
      mockEvents = [createMockEvent()];

      renderWithProviders(<ZoneCrossingFeed />);

      const clearButton = screen.getByRole('button', { name: /clear/i });
      await user.click(clearButton);

      expect(mockClearEvents).toHaveBeenCalledTimes(1);
    });
  });

  describe('event click handling', () => {
    it('calls onEventClick when event is clicked', async () => {
      const user = userEvent.setup();
      const onEventClick = vi.fn();
      mockEvents = [createMockEvent({ entity_id: 'test-entity' })];

      renderWithProviders(<ZoneCrossingFeed onEventClick={onEventClick} />);

      const event = screen.getByTestId('zone-crossing-event');
      await user.click(event);

      expect(onEventClick).toHaveBeenCalledTimes(1);
      expect(onEventClick).toHaveBeenCalledWith(
        expect.objectContaining({ entity_id: 'test-entity' })
      );
    });

    it('makes event clickable when onEventClick provided', () => {
      const onEventClick = vi.fn();
      mockEvents = [createMockEvent()];

      renderWithProviders(<ZoneCrossingFeed onEventClick={onEventClick} />);

      const event = screen.getByTestId('zone-crossing-event');
      expect(event).toHaveAttribute('role', 'button');
      expect(event).toHaveAttribute('tabIndex', '0');
    });

    it('does not make event clickable when onEventClick not provided', () => {
      mockEvents = [createMockEvent()];

      renderWithProviders(<ZoneCrossingFeed />);

      const event = screen.getByTestId('zone-crossing-event');
      expect(event).not.toHaveAttribute('role');
      expect(event).not.toHaveAttribute('tabIndex');
    });

    it('handles keyboard activation', async () => {
      const user = userEvent.setup();
      const onEventClick = vi.fn();
      mockEvents = [createMockEvent()];

      renderWithProviders(<ZoneCrossingFeed onEventClick={onEventClick} />);

      const event = screen.getByTestId('zone-crossing-event');
      event.focus();
      await user.keyboard('{Enter}');

      expect(onEventClick).toHaveBeenCalledTimes(1);
    });

    it('handles space key activation', async () => {
      const user = userEvent.setup();
      const onEventClick = vi.fn();
      mockEvents = [createMockEvent()];

      renderWithProviders(<ZoneCrossingFeed onEventClick={onEventClick} />);

      const event = screen.getByTestId('zone-crossing-event');
      event.focus();
      await user.keyboard(' ');

      expect(onEventClick).toHaveBeenCalledTimes(1);
    });
  });

  describe('entity type display', () => {
    it('displays Person for person entity type', () => {
      mockEvents = [createMockEvent({ entity_type: 'person' })];

      renderWithProviders(<ZoneCrossingFeed />);

      const eventCard = screen.getByTestId('zone-crossing-event');
      expect(within(eventCard).getByText('Person')).toBeInTheDocument();
    });

    it('displays Vehicle for vehicle entity type', () => {
      mockEvents = [createMockEvent({ entity_type: 'vehicle' })];

      renderWithProviders(<ZoneCrossingFeed />);

      const eventCard = screen.getByTestId('zone-crossing-event');
      expect(within(eventCard).getByText('Vehicle')).toBeInTheDocument();
    });

    it('displays Unknown for unknown entity type', () => {
      mockEvents = [createMockEvent({ entity_type: 'unknown' })];

      renderWithProviders(<ZoneCrossingFeed />);

      const eventCard = screen.getByTestId('zone-crossing-event');
      expect(within(eventCard).getByText('Unknown')).toBeInTheDocument();
    });

    it('displays Unknown label for unrecognized entity type', () => {
      mockEvents = [createMockEvent({ entity_type: 'custom_type' })];

      renderWithProviders(<ZoneCrossingFeed />);

      const eventCard = screen.getByTestId('zone-crossing-event');
      // Should fall back to 'Unknown' label
      expect(within(eventCard).getByText('Unknown')).toBeInTheDocument();
    });
  });

  describe('dwell time display', () => {
    it('displays seconds for short dwell times', () => {
      mockEvents = [createMockEvent({ dwell_time: 30 })];

      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.getByText('30s')).toBeInTheDocument();
    });

    it('displays minutes and seconds for medium dwell times', () => {
      mockEvents = [createMockEvent({ dwell_time: 125 })];

      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.getByText('2m 5s')).toBeInTheDocument();
    });

    it('displays hours and minutes for long dwell times', () => {
      mockEvents = [createMockEvent({ dwell_time: 3720 })];

      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.getByText('1h 2m')).toBeInTheDocument();
    });
  });

  describe('thumbnail handling', () => {
    it('renders thumbnail image when URL provided', () => {
      mockEvents = [
        createMockEvent({
          thumbnail_url: 'http://example.com/thumb.jpg',
          entity_type: 'person',
        }),
      ];

      renderWithProviders(<ZoneCrossingFeed />);

      const img = screen.getByAltText('person thumbnail');
      expect(img).toBeInTheDocument();
      expect(img).toHaveAttribute('src', 'http://example.com/thumb.jpg');
    });

    it('renders entity icon when no thumbnail', () => {
      mockEvents = [createMockEvent({ thumbnail_url: null, entity_type: 'person' })];

      renderWithProviders(<ZoneCrossingFeed />);

      // Should have the icon instead of image
      expect(screen.queryByRole('img')).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has accessible filter labels', () => {
      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.getByLabelText('Filter by event type')).toBeInTheDocument();
      expect(screen.getByLabelText('Filter by zone')).toBeInTheDocument();
      expect(screen.getByLabelText('Filter by entity type')).toBeInTheDocument();
    });

    it('has accessible clear button', () => {
      mockEvents = [createMockEvent()];

      renderWithProviders(<ZoneCrossingFeed />);

      expect(screen.getByRole('button', { name: /clear/i })).toBeInTheDocument();
    });

    it('provides title attribute for connection status', () => {
      mockIsConnected = true;

      renderWithProviders(<ZoneCrossingFeed enableRealtime />);

      const status = screen.getByTestId('connection-status');
      expect(status).toHaveAttribute('title', 'Real-time updates active');
    });

    it('provides title for zone name (tooltip)', () => {
      mockEvents = [createMockEvent({ zone_name: 'Very Long Zone Name That Might Be Truncated' })];

      renderWithProviders(<ZoneCrossingFeed />);

      const zoneName = screen.getByTitle('Very Long Zone Name That Might Be Truncated');
      expect(zoneName).toBeInTheDocument();
    });
  });
});

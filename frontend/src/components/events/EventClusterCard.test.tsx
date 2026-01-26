/**
 * Tests for EventClusterCard component
 */

import { describe, it, expect, vi } from 'vitest';

import EventClusterCard from './EventClusterCard';
import { renderWithProviders, screen, userEvent } from '../../test-utils/renderWithProviders';

import type { Event } from '../../services/api';
import type { EventCluster } from '../../utils/eventClustering';

function createMockEvent(overrides: Partial<Event> = {}): Event {
  return {
    id: 1,
    camera_id: 'camera_123',
    started_at: '2024-01-15T10:00:00Z',
    ended_at: '2024-01-15T10:01:00Z',
    risk_score: 50,
    risk_level: 'medium',
    summary: 'Test event',
    thumbnail_url: 'https://example.com/thumb.jpg',
    reviewed: false,
    flagged: false, // NEM-3839
    detection_count: 1,
    notes: null,
    version: 1, // Optimistic locking version (NEM-3625)
    ...overrides,
  };
}

function createMockCluster(overrides: Partial<EventCluster> = {}): EventCluster {
  const hasCameraNameOverride = overrides && 'cameraName' in overrides;
  return {
    clusterId: 'cluster-test-123',
    cameraId: 'camera_123',
    cameraName: hasCameraNameOverride ? overrides.cameraName : 'Front Door',
    events: [createMockEvent({ id: 1 }), createMockEvent({ id: 2 }), createMockEvent({ id: 3 })],
    eventCount: 3,
    startTime: '2024-01-15T10:00:00Z',
    endTime: '2024-01-15T10:04:00Z',
    highestRiskScore: 75,
    highestRiskLevel: 'high',
    thumbnails: ['https://example.com/1.jpg', 'https://example.com/2.jpg'],
    ...overrides,
  };
}

describe('EventClusterCard', () => {
  describe('Rendering', () => {
    it('renders cluster with camera name', () => {
      renderWithProviders(<EventClusterCard cluster={createMockCluster()} />);
      expect(screen.getByText('Front Door')).toBeInTheDocument();
    });

    it('displays event count', () => {
      renderWithProviders(<EventClusterCard cluster={createMockCluster({ eventCount: 5 })} />);
      expect(screen.getByText(/5 events/i)).toBeInTheDocument();
    });

    it('shows time range', () => {
      renderWithProviders(<EventClusterCard cluster={createMockCluster()} />);
      expect(screen.getByText(/\d{2}:\d{2}\s*-\s*\d{2}:\d{2}/)).toBeInTheDocument();
    });

    it('displays highest risk level badge', () => {
      renderWithProviders(
        <EventClusterCard cluster={createMockCluster({ highestRiskLevel: 'critical' })} />
      );
      const riskBadge = screen.getByTestId('risk-badge');
      expect(riskBadge).toHaveTextContent(/critical/i);
    });

    it('shows highest risk score', () => {
      renderWithProviders(
        <EventClusterCard cluster={createMockCluster({ highestRiskScore: 92 })} />
      );
      expect(screen.getByText('92')).toBeInTheDocument();
    });

    it('displays Unknown Camera when cameraName is undefined', () => {
      renderWithProviders(
        <EventClusterCard cluster={createMockCluster({ cameraName: undefined })} />
      );
      expect(screen.getByText('Unknown Camera')).toBeInTheDocument();
    });
  });

  describe('Thumbnail Strip', () => {
    it('renders thumbnail images', () => {
      renderWithProviders(
        <EventClusterCard
          cluster={createMockCluster({ thumbnails: ['a.jpg', 'b.jpg', 'c.jpg'] })}
        />
      );
      const images = screen.getAllByRole('img');
      expect(images.length).toBeGreaterThanOrEqual(3);
    });

    it('handles empty thumbnails array', () => {
      renderWithProviders(<EventClusterCard cluster={createMockCluster({ thumbnails: [] })} />);
      expect(screen.getByText(/\d+ events/i)).toBeInTheDocument();
    });
  });

  describe('Risk Level Styling', () => {
    it('applies critical styling', () => {
      renderWithProviders(
        <EventClusterCard cluster={createMockCluster({ highestRiskLevel: 'critical' })} />
      );
      expect(screen.getByTestId('risk-badge')).toHaveTextContent(/critical/i);
    });

    it('applies high styling', () => {
      renderWithProviders(
        <EventClusterCard cluster={createMockCluster({ highestRiskLevel: 'high' })} />
      );
      expect(screen.getByTestId('risk-badge')).toHaveTextContent(/high/i);
    });

    it('applies medium styling', () => {
      renderWithProviders(
        <EventClusterCard cluster={createMockCluster({ highestRiskLevel: 'medium' })} />
      );
      expect(screen.getByTestId('risk-badge')).toHaveTextContent(/medium/i);
    });

    it('applies low styling', () => {
      renderWithProviders(
        <EventClusterCard cluster={createMockCluster({ highestRiskLevel: 'low' })} />
      );
      expect(screen.getByTestId('risk-badge')).toHaveTextContent(/low/i);
    });
  });

  describe('Expand/Collapse', () => {
    it('starts collapsed by default', () => {
      renderWithProviders(<EventClusterCard cluster={createMockCluster()} />);
      expect(screen.getByRole('button', { name: /expand|view/i })).toBeInTheDocument();
    });

    it('expands to show individual events on click', async () => {
      const user = userEvent.setup();
      const cluster = createMockCluster({
        events: [
          createMockEvent({ id: 1, summary: 'First event' }),
          createMockEvent({ id: 2, summary: 'Second event' }),
          createMockEvent({ id: 3, summary: 'Third event' }),
        ],
      });
      renderWithProviders(<EventClusterCard cluster={cluster} />);

      await user.click(screen.getByRole('button', { name: /expand to view/i }));

      expect(screen.getByText('First event')).toBeInTheDocument();
      expect(screen.getByText('Second event')).toBeInTheDocument();
    });

    it('collapses back when clicking collapse button', async () => {
      const user = userEvent.setup();
      const cluster = createMockCluster({
        events: [
          createMockEvent({ id: 1, summary: 'Event to hide' }),
          createMockEvent({ id: 2, summary: 'Another' }),
          createMockEvent({ id: 3, summary: 'Third' }),
        ],
      });
      renderWithProviders(<EventClusterCard cluster={cluster} />);

      await user.click(screen.getByRole('button', { name: /expand to view/i }));
      expect(screen.getByText('Event to hide')).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: /collapse cluster/i }));
      expect(screen.queryByText('Event to hide')).not.toBeInTheDocument();
    });
  });

  describe('Event Click Callbacks', () => {
    it('calls onEventClick when clicking an expanded event', async () => {
      const user = userEvent.setup();
      const onEventClick = vi.fn();
      const cluster = createMockCluster({
        events: [
          createMockEvent({ id: 42, summary: 'Clickable' }),
          createMockEvent({ id: 43, summary: 'Another' }),
          createMockEvent({ id: 44, summary: 'Third' }),
        ],
      });
      renderWithProviders(<EventClusterCard cluster={cluster} onEventClick={onEventClick} />);

      await user.click(screen.getByRole('button', { name: /expand to view/i }));
      await user.click(screen.getByText('Clickable'));

      expect(onEventClick).toHaveBeenCalledWith(42);
    });
  });

  describe('Accessibility', () => {
    it('has appropriate data-testid', () => {
      renderWithProviders(<EventClusterCard cluster={createMockCluster()} />);
      expect(screen.getByTestId('event-cluster-card')).toBeInTheDocument();
    });

    it('expand button is keyboard accessible', async () => {
      const user = userEvent.setup();
      const cluster = createMockCluster({
        events: [
          createMockEvent({ id: 1, summary: 'KB accessible' }),
          createMockEvent({ id: 2, summary: 'Second' }),
          createMockEvent({ id: 3, summary: 'Third' }),
        ],
      });
      renderWithProviders(<EventClusterCard cluster={cluster} />);

      const expandButton = screen.getByRole('button', { name: /expand to view/i });
      expandButton.focus();
      expect(expandButton).toHaveFocus();

      await user.keyboard('{Enter}');
      expect(screen.getByText('KB accessible')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles null summaries in events', async () => {
      const user = userEvent.setup();
      const cluster = createMockCluster({
        events: [
          createMockEvent({ id: 1, summary: null }),
          createMockEvent({ id: 2, summary: null }),
          createMockEvent({ id: 3, summary: null }),
        ],
      });
      renderWithProviders(<EventClusterCard cluster={cluster} />);

      await user.click(screen.getByRole('button', { name: /expand to view/i }));
      expect(screen.getAllByText(/No summary/i).length).toBeGreaterThan(0);
    });

    it('handles 0 risk score', () => {
      renderWithProviders(
        <EventClusterCard cluster={createMockCluster({ highestRiskScore: 0 })} />
      );
      expect(screen.getByText('0')).toBeInTheDocument();
    });
  });

  describe('Thumbnail Grid (NEM-3620)', () => {
    it('displays thumbnails in a grid layout', () => {
      const thumbnails = ['1.jpg', '2.jpg', '3.jpg', '4.jpg', '5.jpg'];
      renderWithProviders(
        <EventClusterCard cluster={createMockCluster({ thumbnails })} />
      );
      const grid = screen.getByTestId('thumbnail-grid');
      expect(grid).toBeInTheDocument();
      expect(grid.querySelectorAll('img').length).toBe(5);
    });

    it('shows "+N more" indicator when more than 6 thumbnails', () => {
      const thumbnails = ['1.jpg', '2.jpg', '3.jpg', '4.jpg', '5.jpg', '6.jpg', '7.jpg', '8.jpg'];
      renderWithProviders(
        <EventClusterCard cluster={createMockCluster({ thumbnails })} />
      );
      expect(screen.getByTestId('thumbnail-more-indicator')).toBeInTheDocument();
      expect(screen.getByText('+2 more')).toBeInTheDocument();
    });

    it('does not show "+N more" when 6 or fewer thumbnails', () => {
      const thumbnails = ['1.jpg', '2.jpg', '3.jpg', '4.jpg', '5.jpg', '6.jpg'];
      renderWithProviders(
        <EventClusterCard cluster={createMockCluster({ thumbnails })} />
      );
      expect(screen.queryByTestId('thumbnail-more-indicator')).not.toBeInTheDocument();
    });
  });

  describe('Risk Level Breakdown (NEM-3620)', () => {
    it('displays aggregated risk level counts', () => {
      const cluster = createMockCluster({
        events: [
          createMockEvent({ id: 1, risk_level: 'critical', risk_score: 90 }),
          createMockEvent({ id: 2, risk_level: 'high', risk_score: 75 }),
          createMockEvent({ id: 3, risk_level: 'high', risk_score: 70 }),
          createMockEvent({ id: 4, risk_level: 'medium', risk_score: 50 }),
          createMockEvent({ id: 5, risk_level: 'low', risk_score: 20 }),
        ],
        eventCount: 5,
      });
      renderWithProviders(<EventClusterCard cluster={cluster} />);

      const breakdown = screen.getByTestId('risk-breakdown');
      expect(breakdown).toBeInTheDocument();
      expect(screen.getByText('1 critical')).toBeInTheDocument();
      expect(screen.getByText('2 high')).toBeInTheDocument();
      expect(screen.getByText('1 medium')).toBeInTheDocument();
      expect(screen.getByText('1 low')).toBeInTheDocument();
    });

    it('only shows risk levels that have events', () => {
      const cluster = createMockCluster({
        events: [
          createMockEvent({ id: 1, risk_level: 'high', risk_score: 75 }),
          createMockEvent({ id: 2, risk_level: 'high', risk_score: 70 }),
        ],
        eventCount: 2,
      });
      renderWithProviders(<EventClusterCard cluster={cluster} />);

      expect(screen.getByText('2 high')).toBeInTheDocument();
      expect(screen.queryByText(/critical/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/medium/i)).not.toBeInTheDocument();
      expect(screen.queryByText(/low/i)).not.toBeInTheDocument();
    });
  });

  describe('Bulk Actions (NEM-3620)', () => {
    it('shows bulk mark reviewed button when onBulkMarkReviewed is provided', () => {
      const onBulkMarkReviewed = vi.fn();
      const cluster = createMockCluster({
        events: [
          createMockEvent({ id: 1, reviewed: false }),
          createMockEvent({ id: 2, reviewed: false }),
          createMockEvent({ id: 3, reviewed: false }),
        ],
      });
      renderWithProviders(
        <EventClusterCard cluster={cluster} onBulkMarkReviewed={onBulkMarkReviewed} />
      );

      expect(screen.getByTestId('bulk-mark-reviewed-btn')).toBeInTheDocument();
    });

    it('hides bulk mark reviewed button when all events are reviewed', () => {
      const onBulkMarkReviewed = vi.fn();
      const cluster = createMockCluster({
        events: [
          createMockEvent({ id: 1, reviewed: true }),
          createMockEvent({ id: 2, reviewed: true }),
          createMockEvent({ id: 3, reviewed: true }),
        ],
      });
      renderWithProviders(
        <EventClusterCard cluster={cluster} onBulkMarkReviewed={onBulkMarkReviewed} />
      );

      expect(screen.queryByTestId('bulk-mark-reviewed-btn')).not.toBeInTheDocument();
    });

    it('calls onBulkMarkReviewed with all event IDs when clicked', async () => {
      const user = userEvent.setup();
      const onBulkMarkReviewed = vi.fn();
      const cluster = createMockCluster({
        events: [
          createMockEvent({ id: 10, reviewed: false }),
          createMockEvent({ id: 20, reviewed: false }),
          createMockEvent({ id: 30, reviewed: false }),
        ],
      });
      renderWithProviders(
        <EventClusterCard cluster={cluster} onBulkMarkReviewed={onBulkMarkReviewed} />
      );

      await user.click(screen.getByTestId('bulk-mark-reviewed-btn'));

      expect(onBulkMarkReviewed).toHaveBeenCalledWith([10, 20, 30]);
    });

    it('shows loading state during bulk action', () => {
      const onBulkMarkReviewed = vi.fn();
      const cluster = createMockCluster({
        events: [
          createMockEvent({ id: 1, reviewed: false }),
          createMockEvent({ id: 2, reviewed: false }),
        ],
      });
      renderWithProviders(
        <EventClusterCard
          cluster={cluster}
          onBulkMarkReviewed={onBulkMarkReviewed}
          bulkActionLoading={true}
        />
      );

      const btn = screen.getByTestId('bulk-mark-reviewed-btn');
      expect(btn).toBeDisabled();
    });

    it('does not show bulk button when onBulkMarkReviewed is not provided', () => {
      const cluster = createMockCluster({
        events: [
          createMockEvent({ id: 1, reviewed: false }),
          createMockEvent({ id: 2, reviewed: false }),
        ],
      });
      renderWithProviders(<EventClusterCard cluster={cluster} />);

      expect(screen.queryByTestId('bulk-mark-reviewed-btn')).not.toBeInTheDocument();
    });
  });
});

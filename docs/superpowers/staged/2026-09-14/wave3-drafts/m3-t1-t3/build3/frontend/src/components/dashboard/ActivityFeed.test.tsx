import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import ActivityFeed, { type ActivityEvent } from './ActivityFeed';

describe('ActivityFeed', () => {
  // Base time for consistent testing
  const BASE_TIME = new Date('2024-01-15T10:00:00Z').getTime();

  // Mock events for testing
  const mockEvents: ActivityEvent[] = [
    {
      id: '1',
      timestamp: new Date(BASE_TIME - 2 * 60 * 1000).toISOString(), // 2 mins ago
      camera_name: 'Front Door',
      risk_score: 15,
      summary: 'Person detected approaching the front entrance',
      thumbnail_url: 'https://example.com/thumbnail1.jpg',
    },
    {
      id: '2',
      timestamp: new Date(BASE_TIME - 5 * 60 * 1000).toISOString(), // 5 mins ago
      camera_name: 'Back Yard',
      risk_score: 45,
      summary: 'Motion detected near the back fence',
      thumbnail_url: 'https://example.com/thumbnail2.jpg',
    },
    {
      id: '3',
      timestamp: new Date(BASE_TIME - 15 * 60 * 1000).toISOString(), // 15 mins ago
      camera_name: 'Garage',
      risk_score: 72,
      summary: 'Unknown vehicle parked in driveway',
      thumbnail_url: 'https://example.com/thumbnail3.jpg',
    },
    {
      id: '4',
      timestamp: new Date(BASE_TIME - 90 * 60 * 1000).toISOString(), // 90 mins ago
      camera_name: 'Side Gate',
      risk_score: 88,
      summary: 'Multiple people detected near gate',
    },
  ];

  // Mock system time for consistent testing
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(BASE_TIME);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('rendering', () => {
    it('renders component with title', () => {
      render(<ActivityFeed events={mockEvents} />);
      expect(screen.getByText('Live Activity')).toBeInTheDocument();
    });

    it('renders header by default (showHeader=true)', () => {
      render(<ActivityFeed events={mockEvents} />);
      expect(screen.getByText('Live Activity')).toBeInTheDocument();
      expect(screen.getByLabelText('Pause auto-scroll')).toBeInTheDocument();
    });

    it('hides header when showHeader=false', () => {
      render(<ActivityFeed events={mockEvents} showHeader={false} />);
      expect(screen.queryByText('Live Activity')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Pause auto-scroll')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Resume auto-scroll')).not.toBeInTheDocument();
    });

    it('still renders events when showHeader=false', () => {
      render(<ActivityFeed events={mockEvents} showHeader={false} />);
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Back Yard')).toBeInTheDocument();
    });

    it('still renders footer when showHeader=false and events exist', () => {
      render(<ActivityFeed events={mockEvents} showHeader={false} />);
      expect(screen.getByText('Showing 4 of 4 events')).toBeInTheDocument();
    });

    it('renders all events when count is below maxItems', () => {
      render(<ActivityFeed events={mockEvents} maxItems={10} />);
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('Back Yard')).toBeInTheDocument();
      expect(screen.getByText('Garage')).toBeInTheDocument();
      expect(screen.getByText('Side Gate')).toBeInTheDocument();
    });

    it('limits events to maxItems', () => {
      render(<ActivityFeed events={mockEvents} maxItems={2} />);
      // slice(-2) takes the last 2 items: Garage and Side Gate
      expect(screen.queryByText('Front Door')).not.toBeInTheDocument();
      expect(screen.queryByText('Back Yard')).not.toBeInTheDocument();
      expect(screen.getByText('Garage')).toBeInTheDocument();
      expect(screen.getByText('Side Gate')).toBeInTheDocument();
    });

    it('shows last events in array when limiting', () => {
      render(<ActivityFeed events={mockEvents} maxItems={1} />);
      // slice(-1) takes the last item in the array: Side Gate
      expect(screen.getByText('Side Gate')).toBeInTheDocument();
      expect(screen.queryByText('Front Door')).not.toBeInTheDocument();
    });

    it('renders event summaries', () => {
      render(<ActivityFeed events={mockEvents} />);
      expect(
        screen.getByText('Person detected approaching the front entrance')
      ).toBeInTheDocument();
      expect(screen.getByText('Motion detected near the back fence')).toBeInTheDocument();
    });

    it('renders risk badges for each event', () => {
      render(<ActivityFeed events={mockEvents} />);
      expect(screen.getByText('Low (15)')).toBeInTheDocument();
      expect(screen.getByText('Medium (45)')).toBeInTheDocument();
      expect(screen.getByText('High (72)')).toBeInTheDocument();
      expect(screen.getByText('Critical (88)')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(<ActivityFeed events={mockEvents} className="custom-class" />);
      expect(container.firstChild).toHaveClass('custom-class');
    });
  });

  describe('empty state', () => {
    it('renders empty state when no events', () => {
      render(<ActivityFeed events={[]} />);
      expect(screen.getByText('No Activity Yet')).toBeInTheDocument();
      expect(
        screen.getByText('Security events will appear here as they occur.')
      ).toBeInTheDocument();
    });

    it('renders camera icon in empty state', () => {
      const { container } = render(<ActivityFeed events={[]} />);
      const svg = container.querySelector('svg.lucide-camera');
      expect(svg).toBeInTheDocument();
    });

    it('does not render footer in empty state', () => {
      render(<ActivityFeed events={[]} />);
      expect(screen.queryByText(/Showing/)).not.toBeInTheDocument();
    });
  });

  describe('thumbnails', () => {
    it('renders thumbnails when thumbnail_url is provided', () => {
      render(<ActivityFeed events={mockEvents} />);
      const images = screen.getAllByRole('img');
      expect(images.length).toBeGreaterThan(0);
      expect(images[0]).toHaveAttribute('src', 'https://example.com/thumbnail1.jpg');
    });

    it('renders placeholder when thumbnail_url is not provided', () => {
      const eventsWithoutThumbnails = mockEvents.slice(3, 4); // Side Gate has no thumbnail
      const { container } = render(<ActivityFeed events={eventsWithoutThumbnails} />);
      const placeholderIcons = container.querySelectorAll('svg.lucide-camera');
      // Should have at least one camera icon (in the thumbnail placeholder area)
      expect(placeholderIcons.length).toBeGreaterThan(0);
    });

    it('includes alt text for thumbnails', () => {
      render(<ActivityFeed events={mockEvents} />);
      expect(screen.getByAltText('Thumbnail for Front Door')).toBeInTheDocument();
    });

    it('shows placeholder when thumbnail fails to load', async () => {
      const singleEvent: ActivityEvent[] = [
        {
          id: '1',
          timestamp: new Date(BASE_TIME - 2 * 60 * 1000).toISOString(),
          camera_name: 'Front Door',
          risk_score: 15,
          summary: 'Person detected approaching the front entrance',
          thumbnail_url: 'https://example.com/invalid-image.jpg',
        },
      ];

      const { container } = render(<ActivityFeed events={singleEvent} />);

      // Initially renders with image
      const img = screen.getByAltText('Thumbnail for Front Door');
      expect(img).toBeInTheDocument();

      // Simulate image load error
      const { fireEvent } = await import('@testing-library/react');
      fireEvent.error(img);

      // Should now show placeholder
      const placeholder = screen.getByTestId('card-thumbnail-placeholder');
      expect(placeholder).toBeInTheDocument();

      // Image should no longer be present
      expect(screen.queryByAltText('Thumbnail for Front Door')).not.toBeInTheDocument();

      // Layout should still be intact (placeholder has correct size)
      expect(placeholder).toHaveClass('h-20', 'w-20');

      // Camera icon should be visible
      const cameraIcons = container.querySelectorAll('svg.lucide-camera');
      expect(cameraIcons.length).toBeGreaterThan(0);
    });

    it('maintains layout when thumbnail fails to load', async () => {
      const singleEvent: ActivityEvent[] = [
        {
          id: '1',
          timestamp: new Date(BASE_TIME - 2 * 60 * 1000).toISOString(),
          camera_name: 'Front Door',
          risk_score: 15,
          summary: 'Person detected approaching the front entrance',
          thumbnail_url: 'https://example.com/broken-url.jpg',
        },
      ];

      render(<ActivityFeed events={singleEvent} />);

      const img = screen.getByAltText('Thumbnail for Front Door');
      const { fireEvent } = await import('@testing-library/react');
      fireEvent.error(img);

      // Verify the detection card is still intact
      const detectionCard = screen.getByTestId('detection-card-1');
      expect(detectionCard).toBeInTheDocument();

      // Verify camera name and summary are still visible
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(
        screen.getByText('Person detected approaching the front entrance')
      ).toBeInTheDocument();
    });
  });

  describe('timestamp formatting', () => {
    it('formats recent timestamps as "Just now"', () => {
      const recentEvent: ActivityEvent = {
        id: '5',
        timestamp: new Date(BASE_TIME - 30 * 1000).toISOString(), // 30 seconds ago
        camera_name: 'Test Camera',
        risk_score: 10,
        summary: 'Test event',
      };
      render(<ActivityFeed events={[recentEvent]} />);
      expect(screen.getByText('Just now')).toBeInTheDocument();
    });

    it('formats timestamps less than 60 minutes as "X mins ago"', () => {
      render(<ActivityFeed events={mockEvents} />);
      expect(screen.getByText('2 mins ago')).toBeInTheDocument();
      expect(screen.getByText('5 mins ago')).toBeInTheDocument();
      expect(screen.getByText('15 mins ago')).toBeInTheDocument();
    });

    it('formats timestamps as "1 min ago" for exactly one minute', () => {
      const oneMinuteAgo: ActivityEvent = {
        id: '6',
        timestamp: new Date(BASE_TIME - 60 * 1000).toISOString(),
        camera_name: 'Test Camera',
        risk_score: 10,
        summary: 'Test event',
      };
      render(<ActivityFeed events={[oneMinuteAgo]} />);
      expect(screen.getByText('1 min ago')).toBeInTheDocument();
    });

    it('formats timestamps as "X hours ago" for events less than 24 hours old', () => {
      render(<ActivityFeed events={mockEvents} />);
      expect(screen.getByText('1 hour ago')).toBeInTheDocument();
    });

    it('formats timestamps as absolute date for older events', () => {
      const oldEvent: ActivityEvent = {
        id: '7',
        timestamp: new Date(BASE_TIME - 48 * 60 * 60 * 1000).toISOString(), // 48 hours ago
        camera_name: 'Test Camera',
        risk_score: 10,
        summary: 'Test event',
      };
      render(<ActivityFeed events={[oldEvent]} />);
      const timeElement = screen.getByText(/Jan/);
      expect(timeElement).toBeInTheDocument();
    });

    it('includes datetime attribute on time elements', () => {
      render(<ActivityFeed events={mockEvents.slice(0, 1)} />);
      const timeElement = screen.getByText('2 mins ago');
      expect(timeElement).toHaveAttribute('dateTime');
    });
  });

  describe('auto-scroll', () => {
    it('renders pause button when autoScroll is enabled', () => {
      render(<ActivityFeed events={mockEvents} autoScroll={true} />);
      expect(screen.getByLabelText('Pause auto-scroll')).toBeInTheDocument();
      expect(screen.getByText('Pause')).toBeInTheDocument();
    });

    it('renders resume button when autoScroll is disabled', () => {
      render(<ActivityFeed events={mockEvents} autoScroll={false} />);
      expect(screen.getByLabelText('Resume auto-scroll')).toBeInTheDocument();
      expect(screen.getByText('Resume')).toBeInTheDocument();
    });

    it('toggles auto-scroll state when button is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      render(<ActivityFeed events={mockEvents} autoScroll={true} />);

      const toggleButton = screen.getByLabelText('Pause auto-scroll');
      await user.click(toggleButton);

      expect(screen.getByLabelText('Resume auto-scroll')).toBeInTheDocument();
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('defaults autoScroll to true', () => {
      render(<ActivityFeed events={mockEvents} />);
      expect(screen.getByLabelText('Pause auto-scroll')).toBeInTheDocument();
    });

    it('applies smooth scroll behavior when autoScroll is enabled', () => {
      const { container } = render(<ActivityFeed events={mockEvents} autoScroll={true} />);
      const scrollContainer = container.querySelector('.overflow-y-auto');
      expect(scrollContainer).toHaveStyle({ scrollBehavior: 'smooth' });
    });

    it('applies auto scroll behavior when autoScroll is disabled', () => {
      const { container } = render(<ActivityFeed events={mockEvents} autoScroll={false} />);
      const scrollContainer = container.querySelector('.overflow-y-auto');
      expect(scrollContainer).toHaveStyle({ scrollBehavior: 'auto' });
    });
  });

  describe('event interactions', () => {
    it('calls onEventClick when event is clicked', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      render(<ActivityFeed events={mockEvents} onEventClick={handleClick} />);

      const eventCard = screen.getByLabelText(/Event from Front Door/);
      await user.click(eventCard);

      expect(handleClick).toHaveBeenCalledWith('1');
      expect(handleClick).toHaveBeenCalledTimes(1);
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('calls onEventClick with correct event ID', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      render(<ActivityFeed events={mockEvents} onEventClick={handleClick} />);

      const garageEvent = screen.getByLabelText(/Event from Garage/);
      await user.click(garageEvent);

      expect(handleClick).toHaveBeenCalledWith('3');
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('does not call onEventClick when undefined', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      render(<ActivityFeed events={mockEvents} />);

      const eventCard = screen.getByLabelText(/Event from Front Door/);
      await user.click(eventCard);

      // Should not throw error
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('triggers click on Enter key press', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      render(<ActivityFeed events={mockEvents} onEventClick={handleClick} />);

      const eventCard = screen.getByLabelText(/Event from Front Door/);
      eventCard.focus();
      await user.keyboard('{Enter}');

      expect(handleClick).toHaveBeenCalledWith('1');
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('triggers click on Space key press', async () => {
      vi.useRealTimers();
      const user = userEvent.setup();
      const handleClick = vi.fn();
      render(<ActivityFeed events={mockEvents} onEventClick={handleClick} />);

      const eventCard = screen.getByLabelText(/Event from Front Door/);
      eventCard.focus();
      await user.keyboard(' ');

      expect(handleClick).toHaveBeenCalledWith('1');
      vi.useFakeTimers({ shouldAdvanceTime: true });
      vi.setSystemTime(BASE_TIME);
    });

    it('applies hover styles when onEventClick is provided', () => {
      render(<ActivityFeed events={mockEvents} onEventClick={vi.fn()} />);
      const eventCard = screen.getByLabelText(/Event from Front Door/);
      expect(eventCard).toHaveClass('hover:border-[#76B900]');
    });

    it('shows hover indicator when onEventClick is provided', () => {
      render(<ActivityFeed events={mockEvents} onEventClick={vi.fn()} />);
      const eventCard = screen.getByLabelText(/Event from Front Door/);
      const hoverIndicator = eventCard.querySelector('div.bg-\\[\\#76B900\\]');
      expect(hoverIndicator).toBeInTheDocument();
    });
  });

  describe('footer', () => {
    it('displays event count in footer', () => {
      render(<ActivityFeed events={mockEvents} />);
      expect(screen.getByText('Showing 4 of 4 events')).toBeInTheDocument();
    });

    it('displays correct count when events are limited', () => {
      render(<ActivityFeed events={mockEvents} maxItems={2} />);
      expect(screen.getByText('Showing 2 of 4 events')).toBeInTheDocument();
    });

    it('does not display footer when no events', () => {
      render(<ActivityFeed events={[]} />);
      expect(screen.queryByText(/Showing/)).not.toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('includes aria-label for event cards', () => {
      render(<ActivityFeed events={mockEvents} />);
      const eventCard = screen.getByLabelText(/Event from Front Door/);
      expect(eventCard).toBeInTheDocument();
    });

    it('includes risk level in aria-label', () => {
      render(<ActivityFeed events={mockEvents} />);
      const criticalEvent = screen.getByLabelText(/risk level critical/i);
      expect(criticalEvent).toBeInTheDocument();
    });

    it('makes event cards keyboard focusable', () => {
      render(<ActivityFeed events={mockEvents} onEventClick={vi.fn()} />);
      const eventCard = screen.getByLabelText(/Event from Front Door/);
      expect(eventCard).toHaveAttribute('tabIndex', '0');
    });

    it('includes role="button" for clickable events', () => {
      render(<ActivityFeed events={mockEvents} onEventClick={vi.fn()} />);
      const eventCard = screen.getByLabelText(/Event from Front Door/);
      expect(eventCard).toHaveAttribute('role', 'button');
    });

    it('includes aria-label for toggle button', () => {
      render(<ActivityFeed events={mockEvents} autoScroll={true} />);
      expect(screen.getByLabelText('Pause auto-scroll')).toBeInTheDocument();
    });
  });

  describe('layout and styling', () => {
    it('applies NVIDIA theme colors', () => {
      const { container } = render(<ActivityFeed events={mockEvents} />);
      const component = container.firstChild as HTMLElement;
      expect(component).toHaveClass('bg-gray-900');
    });

    it('applies rounded corners', () => {
      const { container } = render(<ActivityFeed events={mockEvents} />);
      const component = container.firstChild as HTMLElement;
      expect(component).toHaveClass('rounded-lg');
    });

    it('applies shadow styling', () => {
      const { container } = render(<ActivityFeed events={mockEvents} />);
      const component = container.firstChild as HTMLElement;
      expect(component).toHaveClass('shadow-lg');
    });

    it('applies flexbox layout', () => {
      const { container } = render(<ActivityFeed events={mockEvents} />);
      const component = container.firstChild as HTMLElement;
      expect(component).toHaveClass('flex', 'flex-col');
    });

    it('applies full height', () => {
      const { container } = render(<ActivityFeed events={mockEvents} />);
      const component = container.firstChild as HTMLElement;
      expect(component).toHaveClass('h-full');
    });
  });

  describe('edge cases', () => {
    it('handles invalid timestamp gracefully', () => {
      const invalidEvent: ActivityEvent = {
        id: '8',
        timestamp: 'invalid-date',
        camera_name: 'Test Camera',
        risk_score: 10,
        summary: 'Test event',
      };
      render(<ActivityFeed events={[invalidEvent]} />);
      // The component should render the original timestamp string for invalid dates without crashing
      const timeElement = screen.getByText('invalid-date');
      expect(timeElement).toBeInTheDocument();
      expect(timeElement.tagName).toBe('TIME');
    });

    it('handles missing thumbnail with placeholder', () => {
      const noThumbnailEvent: ActivityEvent = {
        id: '9',
        timestamp: new Date(BASE_TIME).toISOString(),
        camera_name: 'Test Camera',
        risk_score: 10,
        summary: 'Test event',
      };
      const { container } = render(<ActivityFeed events={[noThumbnailEvent]} />);
      const placeholderIcon = container.querySelector('svg.lucide-camera');
      expect(placeholderIcon).toBeInTheDocument();
    });

    it('handles very long summaries with line clamp', () => {
      const longSummaryEvent: ActivityEvent = {
        id: '10',
        timestamp: new Date(BASE_TIME).toISOString(),
        camera_name: 'Test Camera',
        risk_score: 10,
        summary:
          'This is a very long summary that should be clamped to two lines maximum to prevent overflow and maintain a clean layout in the activity feed component',
      };
      render(<ActivityFeed events={[longSummaryEvent]} />);
      const summary = screen.getByText(/This is a very long summary/);
      expect(summary).toHaveClass('line-clamp-2');
    });

    it('handles single event', () => {
      render(<ActivityFeed events={mockEvents.slice(0, 1)} />);
      expect(screen.getByText('Showing 1 of 1 events')).toBeInTheDocument();
    });

    it('handles maxItems of 0', () => {
      render(<ActivityFeed events={mockEvents} maxItems={0} />);
      expect(screen.getByText('No Activity Yet')).toBeInTheDocument();
    });

    it('handles very large maxItems', () => {
      render(<ActivityFeed events={mockEvents} maxItems={1000} />);
      expect(screen.getByText('Showing 4 of 4 events')).toBeInTheDocument();
    });
  });

  describe('new event handling', () => {
    it('renders new events when they are added', () => {
      const { rerender } = render(
        <ActivityFeed events={mockEvents.slice(0, 2)} autoScroll={true} />
      );

      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.queryByText('Garage')).not.toBeInTheDocument();

      // Add new events
      rerender(<ActivityFeed events={mockEvents} autoScroll={true} />);

      expect(screen.getByText('Garage')).toBeInTheDocument();
      expect(screen.getByText('Side Gate')).toBeInTheDocument();
    });

    it('renders new events when autoScroll is disabled', () => {
      const { rerender } = render(
        <ActivityFeed events={mockEvents.slice(0, 2)} autoScroll={false} />
      );

      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.queryByText('Garage')).not.toBeInTheDocument();

      // Add new events
      rerender(<ActivityFeed events={mockEvents} autoScroll={false} />);

      expect(screen.getByText('Garage')).toBeInTheDocument();
      expect(screen.getByText('Side Gate')).toBeInTheDocument();
    });
  });
});

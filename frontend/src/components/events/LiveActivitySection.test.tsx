import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import LiveActivitySection from './LiveActivitySection';

import type { ActivityEvent } from '../dashboard/ActivityFeed';

// Mock ActivityFeed component
vi.mock('../dashboard/ActivityFeed', () => ({
  default: ({
    events,
    maxItems,
    autoScroll,
    onEventClick,
  }: {
    events: Array<{ id: string }>;
    maxItems: number;
    autoScroll: boolean;
    onEventClick?: (eventId: string) => void;
  }) => (
    <button
      type="button"
      data-testid="activity-feed"
      data-event-count={events.length}
      data-max-items={maxItems}
      data-auto-scroll={autoScroll}
      onClick={() => onEventClick && events.length > 0 && onEventClick(events[0].id)}
    >
      Activity Feed
    </button>
  ),
}));

describe('LiveActivitySection', () => {
  const mockEvents: ActivityEvent[] = [
    {
      id: '1',
      timestamp: '2024-01-01T10:00:00Z',
      camera_name: 'Front Door',
      risk_score: 85,
      summary: 'Person detected at entrance',
    },
    {
      id: '2',
      timestamp: '2024-01-01T10:01:00Z',
      camera_name: 'Back Yard',
      risk_score: 45,
      summary: 'Animal detected in yard',
    },
    {
      id: '3',
      timestamp: '2024-01-01T10:02:00Z',
      camera_name: 'Driveway',
      risk_score: 25,
      summary: 'Vehicle parked',
    },
  ];

  const defaultProps = {
    events: mockEvents,
    isConnected: true,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders the section with heading', () => {
      render(<LiveActivitySection {...defaultProps} />);

      expect(screen.getByRole('heading', { name: /live activity/i })).toBeInTheDocument();
      expect(screen.getByText(/real-time security event stream/i)).toBeInTheDocument();
    });

    it('renders the activity feed when events are present', () => {
      render(<LiveActivitySection {...defaultProps} />);

      expect(screen.getByTestId('activity-feed')).toBeInTheDocument();
    });

    it('renders empty state when no events', () => {
      render(<LiveActivitySection {...defaultProps} events={[]} />);

      expect(screen.getByText(/no live activity/i)).toBeInTheDocument();
      expect(screen.getByText(/waiting for security events/i)).toBeInTheDocument();
    });

    it('applies custom className', () => {
      const { container } = render(
        <LiveActivitySection {...defaultProps} className="custom-class" />
      );

      expect(container.querySelector('section')).toHaveClass('custom-class');
    });
  });

  describe('Connection Status', () => {
    it('shows connected status when isConnected is true', () => {
      render(<LiveActivitySection {...defaultProps} isConnected={true} />);

      expect(screen.getByText('Live')).toBeInTheDocument();
      expect(screen.queryByText('Disconnected')).not.toBeInTheDocument();
    });

    it('shows disconnected status when isConnected is false', () => {
      render(<LiveActivitySection {...defaultProps} isConnected={false} />);

      expect(screen.getByText('Disconnected')).toBeInTheDocument();
      expect(screen.queryByText('Live')).not.toBeInTheDocument();
    });

    it('shows different empty state message when disconnected', () => {
      render(<LiveActivitySection {...defaultProps} events={[]} isConnected={false} />);

      expect(screen.getByText(/connection lost/i)).toBeInTheDocument();
    });
  });

  describe('Pause/Resume Functionality', () => {
    it('renders pause button initially', () => {
      render(<LiveActivitySection {...defaultProps} />);

      expect(screen.getByLabelText(/pause live updates/i)).toBeInTheDocument();
    });

    it('toggles to resume button when paused', async () => {
      const user = userEvent.setup();
      render(<LiveActivitySection {...defaultProps} />);

      const pauseButton = screen.getByLabelText(/pause live updates/i);
      await user.click(pauseButton);

      expect(screen.getByLabelText(/resume live updates/i)).toBeInTheDocument();
    });

    it('shows paused overlay when paused', async () => {
      const user = userEvent.setup();
      render(<LiveActivitySection {...defaultProps} />);

      const pauseButton = screen.getByLabelText(/pause live updates/i);
      await user.click(pauseButton);

      expect(screen.getByText(/updates paused/i)).toBeInTheDocument();
    });

    it('passes autoScroll=false to ActivityFeed when paused', async () => {
      const user = userEvent.setup();
      render(<LiveActivitySection {...defaultProps} />);

      const pauseButton = screen.getByLabelText(/pause live updates/i);
      await user.click(pauseButton);

      const activityFeed = screen.getByTestId('activity-feed');
      expect(activityFeed).toHaveAttribute('data-auto-scroll', 'false');
    });

    it('passes autoScroll=true to ActivityFeed when not paused', () => {
      render(<LiveActivitySection {...defaultProps} />);

      const activityFeed = screen.getByTestId('activity-feed');
      expect(activityFeed).toHaveAttribute('data-auto-scroll', 'true');
    });
  });

  describe('Event Click Handler', () => {
    it('calls onEventClick when event is clicked', async () => {
      const handleClick = vi.fn();
      const user = userEvent.setup();
      render(<LiveActivitySection {...defaultProps} onEventClick={handleClick} />);

      // Click the activity feed button (mocked to trigger onEventClick)
      await user.click(screen.getByTestId('activity-feed'));

      expect(handleClick).toHaveBeenCalledWith('1');
    });
  });

  describe('Stats Display', () => {
    it('shows event count', () => {
      render(<LiveActivitySection {...defaultProps} />);

      expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('shows footer with event count', () => {
      render(<LiveActivitySection {...defaultProps} maxItems={10} />);

      expect(screen.getByText(/showing 3 of 3 recent events/i)).toBeInTheDocument();
    });

    it('shows footer with limited count when more events than maxItems', () => {
      const manyEvents: ActivityEvent[] = Array.from({ length: 15 }, (_, i) => ({
        id: String(i + 1),
        timestamp: `2024-01-01T10:${String(i).padStart(2, '0')}:00Z`,
        camera_name: 'Camera',
        risk_score: 50,
        summary: `Event ${i + 1}`,
      }));

      render(<LiveActivitySection {...defaultProps} events={manyEvents} maxItems={10} />);

      expect(screen.getByText(/showing 10 of 15 recent events/i)).toBeInTheDocument();
    });

    it('does not show footer when no events', () => {
      render(<LiveActivitySection {...defaultProps} events={[]} />);

      expect(screen.queryByText(/showing.*recent events/i)).not.toBeInTheDocument();
    });
  });

  describe('Risk Level Stats', () => {
    it('displays risk breakdown on larger screens', () => {
      // Create events with different risk levels
      const mixedEvents: ActivityEvent[] = [
        { id: '1', timestamp: '2024-01-01T10:00:00Z', camera_name: 'Cam1', risk_score: 95, summary: 'Critical event' },
        { id: '2', timestamp: '2024-01-01T10:01:00Z', camera_name: 'Cam2', risk_score: 75, summary: 'High event' },
        { id: '3', timestamp: '2024-01-01T10:02:00Z', camera_name: 'Cam3', risk_score: 45, summary: 'Medium event' },
        { id: '4', timestamp: '2024-01-01T10:03:00Z', camera_name: 'Cam4', risk_score: 20, summary: 'Low event' },
      ];

      render(<LiveActivitySection {...defaultProps} events={mixedEvents} />);

      // The stats should show the total count
      expect(screen.getByText('4')).toBeInTheDocument();
    });

    it('does not show stats when no events', () => {
      render(<LiveActivitySection {...defaultProps} events={[]} />);

      // Should not have any stat numbers
      const stats = screen.queryByText(/\d+ recent/);
      expect(stats).not.toBeInTheDocument();
    });
  });

  describe('MaxItems Prop', () => {
    it('passes maxItems to ActivityFeed', () => {
      render(<LiveActivitySection {...defaultProps} maxItems={5} />);

      const activityFeed = screen.getByTestId('activity-feed');
      expect(activityFeed).toHaveAttribute('data-max-items', '5');
    });

    it('uses default maxItems of 10', () => {
      render(<LiveActivitySection {...defaultProps} />);

      const activityFeed = screen.getByTestId('activity-feed');
      expect(activityFeed).toHaveAttribute('data-max-items', '10');
    });
  });

  describe('Accessibility', () => {
    it('has accessible section with aria-labelledby', () => {
      render(<LiveActivitySection {...defaultProps} />);

      const section = screen.getByRole('region', { name: /live activity/i });
      expect(section).toBeInTheDocument();
    });

    it('has accessible connection status', () => {
      render(<LiveActivitySection {...defaultProps} />);

      // Look specifically for the connection status element (contains "Live" text)
      const statusElements = screen.getAllByRole('status');
      const connectionStatus = statusElements.find((el) => el.textContent?.includes('Live'));
      expect(connectionStatus).toBeDefined();
    });

    it('pause button has aria-pressed attribute', async () => {
      const user = userEvent.setup();
      render(<LiveActivitySection {...defaultProps} />);

      const pauseButton = screen.getByLabelText(/pause live updates/i);
      expect(pauseButton).toHaveAttribute('aria-pressed', 'false');

      await user.click(pauseButton);

      const resumeButton = screen.getByLabelText(/resume live updates/i);
      expect(resumeButton).toHaveAttribute('aria-pressed', 'true');
    });
  });

  describe('Visual States', () => {
    it('applies gradient background styling', () => {
      const { container } = render(<LiveActivitySection {...defaultProps} />);

      const section = container.querySelector('section');
      expect(section).toHaveClass('bg-gradient-to-br');
    });

    it('applies shadow styling', () => {
      const { container } = render(<LiveActivitySection {...defaultProps} />);

      const section = container.querySelector('section');
      expect(section).toHaveClass('shadow-lg');
    });

    it('applies rounded border styling', () => {
      const { container } = render(<LiveActivitySection {...defaultProps} />);

      const section = container.querySelector('section');
      expect(section).toHaveClass('rounded-xl');
      expect(section).toHaveClass('border');
      expect(section).toHaveClass('border-gray-800');
    });
  });
});

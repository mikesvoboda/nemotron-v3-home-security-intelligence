import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import AlertCameraGroup from './AlertCameraGroup';

import type { Event } from '../../services/api';

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

describe('AlertCameraGroup', () => {
  const mockAlerts: Event[] = [
    {
      id: 1,
      camera_id: 'camera-1',
      started_at: '2024-01-01T10:00:00Z',
      ended_at: '2024-01-01T10:02:00Z',
      risk_score: 90,
      risk_level: 'critical',
      summary: 'Unknown person at door',
      reviewed: false,
      detection_count: 5,
      notes: null,
    },
    {
      id: 2,
      camera_id: 'camera-1',
      started_at: '2024-01-01T09:00:00Z',
      ended_at: '2024-01-01T09:05:00Z',
      risk_score: 75,
      risk_level: 'high',
      summary: 'Person detected near entrance',
      reviewed: false,
      detection_count: 3,
      notes: null,
    },
    {
      id: 3,
      camera_id: 'camera-1',
      started_at: '2024-01-01T08:00:00Z',
      ended_at: '2024-01-01T08:01:00Z',
      risk_score: 80,
      risk_level: 'high',
      summary: 'Vehicle in driveway',
      reviewed: false,
      detection_count: 2,
      notes: null,
    },
  ];

  const defaultProps = {
    cameraId: 'camera-1',
    cameraName: 'Front Door',
    alerts: mockAlerts,
    onSnooze: vi.fn(),
    onDismissAll: vi.fn(),
    onAlertClick: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders camera name in header', () => {
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} />);

      // Camera name appears in both the header and the event cards
      // Use getAllByText and check that at least one exists
      const cameraNames = screen.getAllByText('Front Door');
      expect(cameraNames.length).toBeGreaterThan(0);
    });

    it('displays alert count', () => {
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} />);

      expect(screen.getByText('3 alerts')).toBeInTheDocument();
    });

    it('displays singular "alert" when count is 1', () => {
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} alerts={[mockAlerts[0]]} />);

      expect(screen.getByText('1 alert')).toBeInTheDocument();
    });

    it('displays severity summary badges', () => {
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} />);

      // Should show "1 critical" and "2 high" badges
      expect(screen.getByText('1 critical')).toBeInTheDocument();
      expect(screen.getByText('2 high')).toBeInTheDocument();
    });

    it('only shows badges for present severity levels', () => {
      const highOnlyAlerts = mockAlerts.filter((a) => a.risk_level === 'high');
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} alerts={highOnlyAlerts} />);

      expect(screen.queryByText(/critical/i)).not.toBeInTheDocument();
      expect(screen.getByText('2 high')).toBeInTheDocument();
    });
  });

  describe('Collapsible Behavior', () => {
    it('starts expanded by default', () => {
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} />);

      // Alerts should be visible
      expect(screen.getByText('Unknown person at door')).toBeInTheDocument();
      expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
    });

    it('collapses when header is clicked', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} />);

      // Click the toggle button to collapse
      const toggleButton = screen.getByRole('button', { name: /front door.*3 alerts/i });
      await user.click(toggleButton);

      // Alerts should no longer be visible
      await waitFor(() => {
        expect(screen.queryByText('Unknown person at door')).not.toBeInTheDocument();
      });
    });

    it('expands when collapsed header is clicked', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} defaultExpanded={false} />);

      // Alerts should not be visible initially
      expect(screen.queryByText('Unknown person at door')).not.toBeInTheDocument();

      // Click the toggle button to expand
      const toggleButton = screen.getByRole('button', { name: /front door.*3 alerts/i });
      await user.click(toggleButton);

      // Alerts should now be visible
      await waitFor(() => {
        expect(screen.getByText('Unknown person at door')).toBeInTheDocument();
      });
    });

    it('has correct ARIA attributes', () => {
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} />);

      const toggleButton = screen.getByRole('button', { name: /front door.*3 alerts/i });
      expect(toggleButton).toHaveAttribute('aria-expanded', 'true');
    });

    it('updates ARIA attributes when collapsed', async () => {
      const user = userEvent.setup();
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} />);

      const toggleButton = screen.getByRole('button', { name: /front door.*3 alerts/i });
      await user.click(toggleButton);

      expect(toggleButton).toHaveAttribute('aria-expanded', 'false');
    });
  });

  describe('Dismiss All', () => {
    it('shows dismiss all button', () => {
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} />);

      expect(screen.getByRole('button', { name: /dismiss all/i })).toBeInTheDocument();
    });

    it('calls onDismissAll with cameraId when clicked', async () => {
      const user = userEvent.setup();
      const onDismissAll = vi.fn();
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} onDismissAll={onDismissAll} />);

      const dismissButton = screen.getByRole('button', { name: /dismiss all/i });
      await user.click(dismissButton);

      expect(onDismissAll).toHaveBeenCalledWith('camera-1');
    });

    it('does not show dismiss all button when onDismissAll is not provided', () => {
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} onDismissAll={undefined} />);

      expect(screen.queryByRole('button', { name: /dismiss all/i })).not.toBeInTheDocument();
    });
  });

  describe('Alert Cards', () => {
    it('renders all alerts as EventCards', () => {
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} />);

      expect(screen.getByText('Unknown person at door')).toBeInTheDocument();
      expect(screen.getByText('Person detected near entrance')).toBeInTheDocument();
      expect(screen.getByText('Vehicle in driveway')).toBeInTheDocument();
    });

    it('calls onAlertClick when an alert card is clicked', async () => {
      const user = userEvent.setup();
      const onAlertClick = vi.fn();
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} onAlertClick={onAlertClick} />);

      // Click on the first alert card
      const firstAlert = screen.getByTestId('event-card-1');
      await user.click(firstAlert);

      expect(onAlertClick).toHaveBeenCalledWith(1);
    });

    it('passes snooze handler to alert cards', async () => {
      const user = userEvent.setup();
      const onSnooze = vi.fn();
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} onSnooze={onSnooze} />);

      // Find the snooze button on the first card
      const firstCard = screen.getByTestId('event-card-1');
      const snoozeButton = within(firstCard).getByRole('button', { name: /snooze/i });
      await user.click(snoozeButton);

      // Should open snooze menu
      const snooze15Min = screen.getByText('15 minutes');
      await user.click(snooze15Min);

      expect(onSnooze).toHaveBeenCalledWith('1', 900);
    });
  });

  describe('Styling', () => {
    it('applies custom className', () => {
      const { container } = renderWithQueryClient(
        <AlertCameraGroup {...defaultProps} className="custom-class" />
      );

      expect(container.querySelector('.custom-class')).toBeInTheDocument();
    });

    it('has proper data-testid', () => {
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} />);

      expect(screen.getByTestId('alert-camera-group-camera-1')).toBeInTheDocument();
    });
  });

  describe('Severity Sorting', () => {
    it('shows highest severity first in summary', () => {
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} />);

      // Check that critical badge appears before high badge in the DOM
      const criticalBadge = screen.getByText('1 critical');
      const highBadge = screen.getByText('2 high');

      // criticalBadge should come before highBadge
      expect(
        criticalBadge.compareDocumentPosition(highBadge) & Node.DOCUMENT_POSITION_FOLLOWING
      ).toBeTruthy();
    });
  });

  describe('Edge Cases', () => {
    it('handles empty alerts array', () => {
      renderWithQueryClient(<AlertCameraGroup {...defaultProps} alerts={[]} />);

      // With no alerts, the camera name only appears in the header
      expect(screen.getByText('Front Door')).toBeInTheDocument();
      expect(screen.getByText('0 alerts')).toBeInTheDocument();
    });

    it('handles unknown camera name', () => {
      renderWithQueryClient(
        <AlertCameraGroup {...defaultProps} cameraName="Unknown Camera" alerts={[]} />
      );

      // With no alerts, the camera name only appears once in the header
      expect(screen.getByText('Unknown Camera')).toBeInTheDocument();
    });
  });
});

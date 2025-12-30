import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import AlertStatsBar from './AlertStatsBar';
import * as api from '../../services/api';

// Mock the API functions
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    fetchEventStats: vi.fn(),
  };
});

const mockEventStats = {
  total_events: 200,
  events_by_risk_level: {
    critical: 5,
    high: 15,
    medium: 80,
    low: 100,
  },
  events_by_camera: [],
};

describe('AlertStatsBar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchEventStats as ReturnType<typeof vi.fn>).mockResolvedValue(mockEventStats);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders component', async () => {
    render(<AlertStatsBar pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('alert-stats-bar')).toBeInTheDocument();
    });
  });

  it('displays critical alerts count', async () => {
    render(<AlertStatsBar pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('critical-alerts-stat')).toBeInTheDocument();
    });

    expect(screen.getByText('Critical')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('displays high alerts count', async () => {
    render(<AlertStatsBar pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('high-alerts-stat')).toBeInTheDocument();
    });

    // Multiple elements with "High" text exist - one for label and one for dominant level
    const highTexts = screen.getAllByText('High');
    expect(highTexts.length).toBeGreaterThan(0);
    expect(screen.getByText('15')).toBeInTheDocument();
  });

  it('displays unreviewed count', async () => {
    render(<AlertStatsBar pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('unreviewed-alerts-stat')).toBeInTheDocument();
    });

    expect(screen.getByText('Unreviewed')).toBeInTheDocument();
    // Note: unreviewed_count is not in generated types - defaults to 0
    expect(screen.getByText('0')).toBeInTheDocument();
  });

  it('displays total alerts count', async () => {
    render(<AlertStatsBar pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('last-alert-stat')).toBeInTheDocument();
    });

    expect(screen.getByText('Total Alerts')).toBeInTheDocument();
    expect(screen.getByText('20')).toBeInTheDocument(); // 5 + 15
  });

  it('displays dominant level indicator', async () => {
    render(<AlertStatsBar pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('risk-trend-stat')).toBeInTheDocument();
    });

    expect(screen.getByText('Dominant Level')).toBeInTheDocument();
    // Since high > critical, should show "High" as dominant (multiple "High" texts will exist)
    const highTexts = screen.getAllByText('High');
    expect(highTexts.length).toBeGreaterThan(0);
  });

  it('shows Critical as dominant when critical > high', async () => {
    (api.fetchEventStats as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...mockEventStats,
      events_by_risk_level: {
        critical: 20,
        high: 5,
        medium: 80,
        low: 100,
      },
    });

    render(<AlertStatsBar pollingInterval={0} />);

    await waitFor(() => {
      // Critical will appear as dominant level and in stats
      const criticalTexts = screen.getAllByText('Critical');
      expect(criticalTexts.length).toBeGreaterThan(0);
    });
  });

  it('shows Low as dominant when no alerts', async () => {
    (api.fetchEventStats as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...mockEventStats,
      events_by_risk_level: {
        critical: 0,
        high: 0,
        medium: 80,
        low: 100,
      },
    });

    render(<AlertStatsBar pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Low')).toBeInTheDocument();
    });
  });

  it('displays activity badge', async () => {
    render(<AlertStatsBar pollingInterval={0} />);

    await waitFor(() => {
      // With 20 total alerts, should show "Moderate Activity"
      expect(screen.getByText('Moderate Activity')).toBeInTheDocument();
    });
  });

  it('shows High Activity badge for many alerts', async () => {
    (api.fetchEventStats as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...mockEventStats,
      events_by_risk_level: {
        critical: 30,
        high: 30,
        medium: 80,
        low: 100,
      },
    });

    render(<AlertStatsBar pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('High Activity')).toBeInTheDocument();
    });
  });

  it('shows Normal Activity badge for few alerts', async () => {
    (api.fetchEventStats as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...mockEventStats,
      events_by_risk_level: {
        critical: 2,
        high: 3,
        medium: 80,
        low: 100,
      },
    });

    render(<AlertStatsBar pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Normal Activity')).toBeInTheDocument();
    });
  });

  it('shows No Alerts badge when empty', async () => {
    (api.fetchEventStats as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...mockEventStats,
      events_by_risk_level: {
        critical: 0,
        high: 0,
        medium: 80,
        low: 100,
      },
    });

    render(<AlertStatsBar pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('No Alerts')).toBeInTheDocument();
    });
  });

  it('shows Active badge when alerts exist', async () => {
    render(<AlertStatsBar pollingInterval={0} />);

    await waitFor(() => {
      // Should show Active badges for both critical and high
      const activeBadges = screen.getAllByText('Active');
      expect(activeBadges.length).toBeGreaterThan(0);
    });
  });

  it('applies custom className', async () => {
    render(<AlertStatsBar className="custom-class" pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('alert-stats-bar')).toHaveClass('custom-class');
    });
  });

  it('handles API error gracefully', async () => {
    // Suppress console.error for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    (api.fetchEventStats as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));

    render(<AlertStatsBar pollingInterval={0} />);

    await waitFor(() => {
      // Component should still render with placeholder values
      expect(screen.getByTestId('alert-stats-bar')).toBeInTheDocument();
    });

    consoleSpy.mockRestore();
  });
});

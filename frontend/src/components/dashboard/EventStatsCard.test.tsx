import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import EventStatsCard from './EventStatsCard';
import * as api from '../../services/api';

// Mock the API functions
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    fetchEventStats: vi.fn(),
    fetchCameras: vi.fn(),
  };
});

// Mock ResizeObserver for Tremor charts
beforeEach(() => {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

const mockEventStats = {
  total_events: 1500,
  events_by_risk_level: {
    critical: 10,
    high: 35,
    medium: 150,
    low: 1305,
  },
  events_by_camera: [
    { camera_id: 'cam-1', camera_name: 'Front Door', event_count: 500 },
    { camera_id: 'cam-2', camera_name: 'Back Yard', event_count: 400 },
    { camera_id: 'cam-3', camera_name: 'Garage', event_count: 300 },
    { camera_id: 'cam-4', camera_name: 'Side Gate', event_count: 200 },
    { camera_id: 'cam-5', camera_name: 'Driveway', event_count: 100 },
  ],
};

const mockCameras = [
  { id: 'cam-1', name: 'Front Door', folder_path: '/cams/front', status: 'online', created_at: '2024-01-01T00:00:00Z', last_seen_at: '2024-01-02T00:00:00Z' },
  { id: 'cam-2', name: 'Back Yard', folder_path: '/cams/back', status: 'online', created_at: '2024-01-01T00:00:00Z', last_seen_at: '2024-01-02T00:00:00Z' },
  { id: 'cam-3', name: 'Garage', folder_path: '/cams/garage', status: 'online', created_at: '2024-01-01T00:00:00Z', last_seen_at: '2024-01-02T00:00:00Z' },
  { id: 'cam-4', name: 'Side Gate', folder_path: '/cams/side', status: 'offline', created_at: '2024-01-01T00:00:00Z', last_seen_at: '2024-01-02T00:00:00Z' },
  { id: 'cam-5', name: 'Driveway', folder_path: '/cams/driveway', status: 'online', created_at: '2024-01-01T00:00:00Z', last_seen_at: '2024-01-02T00:00:00Z' },
];

describe('EventStatsCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchEventStats as ReturnType<typeof vi.fn>).mockResolvedValue(mockEventStats);
    (api.fetchCameras as ReturnType<typeof vi.fn>).mockResolvedValue(mockCameras);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders component with title after loading', async () => {
    render(<EventStatsCard pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Event Statistics')).toBeInTheDocument();
    });
  });

  it('fetches data on mount', async () => {
    render(<EventStatsCard pollingInterval={0} />);

    await waitFor(() => {
      expect(api.fetchEventStats).toHaveBeenCalled();
      expect(api.fetchCameras).toHaveBeenCalled();
    });
  });

  it('displays total events count', async () => {
    render(<EventStatsCard pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('total-events-stat')).toBeInTheDocument();
    });

    expect(screen.getByText('Total Events')).toBeInTheDocument();
    expect(screen.getByText('1.5K')).toBeInTheDocument();
  });

  it('displays high priority count (critical + high)', async () => {
    render(<EventStatsCard pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('high-priority-stat')).toBeInTheDocument();
    });

    expect(screen.getByText('High Priority')).toBeInTheDocument();
    // 10 + 35 = 45, but unreviewed is also 45, so use within to scope
    const highPriorityStat = screen.getByTestId('high-priority-stat');
    expect(highPriorityStat).toHaveTextContent('45');
  });

  it('displays unreviewed count', async () => {
    render(<EventStatsCard pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('unreviewed-stat')).toBeInTheDocument();
    });

    expect(screen.getByText('Unreviewed')).toBeInTheDocument();
  });

  it('displays active cameras count', async () => {
    render(<EventStatsCard pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('cameras-stat')).toBeInTheDocument();
    });

    expect(screen.getByText('Active Cameras')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument(); // 4 enabled cameras
  });

  it('displays risk level breakdown', async () => {
    render(<EventStatsCard pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('risk-level-critical')).toBeInTheDocument();
    });

    expect(screen.getByTestId('risk-level-critical')).toBeInTheDocument();
    expect(screen.getByTestId('risk-level-high')).toBeInTheDocument();
    expect(screen.getByTestId('risk-level-medium')).toBeInTheDocument();
    expect(screen.getByTestId('risk-level-low')).toBeInTheDocument();
  });

  it('displays error state when API fails', async () => {
    (api.fetchEventStats as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('Network error'));

    render(<EventStatsCard pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('stats-error')).toBeInTheDocument();
    });

    expect(screen.getByText('Network error')).toBeInTheDocument();
  });

  it('handles refresh button click', async () => {
    const user = userEvent.setup();
    render(<EventStatsCard pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByLabelText('Refresh statistics')).toBeInTheDocument();
    });

    await user.click(screen.getByLabelText('Refresh statistics'));

    await waitFor(() => {
      expect(api.fetchEventStats).toHaveBeenCalledTimes(2);
    });
  });

  it('hides camera breakdown when disabled', async () => {
    render(<EventStatsCard showCameraBreakdown={false} pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Event Statistics')).toBeInTheDocument();
    });

    // Should not have fetched cameras
    expect(api.fetchCameras).not.toHaveBeenCalled();
  });

  it('applies custom className', async () => {
    render(<EventStatsCard className="custom-class" pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('event-stats-card')).toHaveClass('custom-class');
    });
  });

  it('formats large numbers with K suffix', async () => {
    render(<EventStatsCard pollingInterval={0} />);

    await waitFor(() => {
      // 1500 should be formatted as 1.5K
      expect(screen.getByText('1.5K')).toBeInTheDocument();
    });
  });

  it('displays percentage in risk level breakdown', async () => {
    render(<EventStatsCard pollingInterval={0} />);

    await waitFor(() => {
      expect(screen.getByTestId('risk-level-critical')).toBeInTheDocument();
    });

    // Critical is 10 out of 1500 = 0.7%
    expect(screen.getByText('0.7% of total')).toBeInTheDocument();
  });
});

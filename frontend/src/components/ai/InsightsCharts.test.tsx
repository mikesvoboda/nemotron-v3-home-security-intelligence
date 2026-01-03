/**
 * Tests for InsightsCharts component
 */

import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';

import InsightsCharts from './InsightsCharts';

// Mock the fetchEventStats API
vi.mock('../../services/api', () => ({
  fetchEventStats: vi.fn(() =>
    Promise.resolve({
      total_events: 100,
      events_by_risk_level: {
        critical: 5,
        high: 15,
        medium: 30,
        low: 50,
      },
      events_by_camera: [
        { camera_id: 'cam-1', camera_name: 'Front Door', event_count: 60 },
        { camera_id: 'cam-2', camera_name: 'Backyard', event_count: 40 },
      ],
    })
  ),
}));

describe('InsightsCharts', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the main container', async () => {
    render(<InsightsCharts />);
    await waitFor(() => {
      expect(screen.getByTestId('insights-charts')).toBeInTheDocument();
    });
  });

  it('renders detection distribution card', async () => {
    render(<InsightsCharts />);
    await waitFor(() => {
      expect(screen.getByTestId('detection-distribution-card')).toBeInTheDocument();
    });
  });

  it('renders risk distribution card', async () => {
    render(<InsightsCharts />);
    await waitFor(() => {
      expect(screen.getByTestId('risk-distribution-card')).toBeInTheDocument();
    });
  });

  it('renders detection class distribution title', async () => {
    render(<InsightsCharts />);
    await waitFor(() => {
      expect(screen.getByText('Detection Class Distribution')).toBeInTheDocument();
    });
  });

  it('renders risk score distribution title', async () => {
    render(<InsightsCharts />);
    await waitFor(() => {
      expect(screen.getByText('Risk Score Distribution')).toBeInTheDocument();
    });
  });

  it('displays total events count', async () => {
    render(<InsightsCharts />);
    await waitFor(() => {
      expect(screen.getByText('Total Events: 100')).toBeInTheDocument();
    });
  });

  it('displays risk level labels', async () => {
    render(<InsightsCharts />);
    await waitFor(() => {
      expect(screen.getByText('Low')).toBeInTheDocument();
      expect(screen.getByText('Medium')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
      expect(screen.getByText('Critical')).toBeInTheDocument();
    });
  });

  it('displays placeholder when no detection class data provided', async () => {
    render(<InsightsCharts />);
    await waitFor(() => {
      expect(screen.getByText('No detections recorded yet')).toBeInTheDocument();
    });
  });

  it('renders with detection class data', async () => {
    const detectionsByClass = {
      person: 50,
      vehicle: 30,
      animal: 15,
      package: 5,
    };

    render(<InsightsCharts detectionsByClass={detectionsByClass} />);

    await waitFor(() => {
      expect(screen.getByText('Person')).toBeInTheDocument();
      expect(screen.getByText('Vehicle')).toBeInTheDocument();
      expect(screen.getByText('Animal')).toBeInTheDocument();
      expect(screen.getByText('Package')).toBeInTheDocument();
    });
  });

  it('displays total detections when provided', async () => {
    const detectionsByClass = {
      person: 50,
      vehicle: 30,
    };

    render(<InsightsCharts detectionsByClass={detectionsByClass} />);

    await waitFor(() => {
      expect(screen.getByText(/Total Detections:/)).toBeInTheDocument();
      expect(screen.getByText('80')).toBeInTheDocument();
    });
  });

  it('applies custom className', async () => {
    render(<InsightsCharts className="custom-class" />);
    await waitFor(() => {
      expect(screen.getByTestId('insights-charts')).toHaveClass('custom-class');
    });
  });
});

describe('InsightsCharts error handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows error message when API fails', async () => {
    const { fetchEventStats } = await import('../../services/api');
    vi.mocked(fetchEventStats).mockRejectedValueOnce(new Error('Network error'));

    render(<InsightsCharts />);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });
});

describe('InsightsCharts with empty event stats', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows placeholder when no events exist', async () => {
    const { fetchEventStats } = await import('../../services/api');
    vi.mocked(fetchEventStats).mockResolvedValueOnce({
      total_events: 0,
      events_by_risk_level: {
        critical: 0,
        high: 0,
        medium: 0,
        low: 0,
      },
      events_by_camera: [],
    });

    render(<InsightsCharts />);

    await waitFor(() => {
      expect(screen.getByText('No events recorded yet')).toBeInTheDocument();
    });
  });
});

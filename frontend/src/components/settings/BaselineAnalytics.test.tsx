import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import BaselineAnalytics from './BaselineAnalytics';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api');

describe('BaselineAnalytics', () => {
  const mockCameras = [
    { id: 'cam1', name: 'Front Door', folder_path: '/export/foscam/front_door', status: 'online' as const, created_at: '2024-01-01T00:00:00Z' },
    { id: 'cam2', name: 'Back Yard', folder_path: '/export/foscam/back_yard', status: 'online' as const, created_at: '2024-01-01T00:00:00Z' },
  ];

  const mockActivityBaseline: api.ActivityBaselineResponse = {
    camera_id: 'cam1',
    entries: [
      { hour: 12, day_of_week: 0, avg_count: 3.5, sample_count: 15, is_peak: true },
      { hour: 17, day_of_week: 4, avg_count: 5.2, sample_count: 20, is_peak: true },
    ],
    total_samples: 500,
    peak_hour: 17,
    peak_day: 4,
    learning_complete: true,
    min_samples_required: 10,
  };

  const mockClassBaseline: api.ClassBaselineResponse = {
    camera_id: 'cam1',
    entries: [
      { object_class: 'person', hour: 17, frequency: 3.5, sample_count: 45 },
      { object_class: 'vehicle', hour: 8, frequency: 2.1, sample_count: 30 },
    ],
    unique_classes: ['person', 'vehicle'],
    total_samples: 75,
    most_common_class: 'person',
  };

  const mockAnomalyConfig: api.AnomalyConfig = {
    threshold_stdev: 2.0,
    min_samples: 10,
    decay_factor: 0.1,
    window_days: 30,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    vi.mocked(api.fetchCameraActivityBaseline).mockResolvedValue(mockActivityBaseline);
    vi.mocked(api.fetchCameraClassBaseline).mockResolvedValue(mockClassBaseline);
    vi.mocked(api.fetchAnomalyConfig).mockResolvedValue(mockAnomalyConfig);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders component with title', async () => {
    render(<BaselineAnalytics />);

    await waitFor(() => {
      expect(screen.getByText('Baseline Analytics')).toBeInTheDocument();
    });
  });

  it('shows loading state initially', () => {
    vi.mocked(api.fetchCameras).mockImplementation(
      () => new Promise(() => {}) // Never resolves
    );

    render(<BaselineAnalytics />);

    expect(screen.getByText('Loading baseline data...')).toBeInTheDocument();
  });

  it('displays camera selector when cameras are loaded', async () => {
    render(<BaselineAnalytics />);

    // Wait for cameras to load and first one to be selected
    await waitFor(() => {
      expect(api.fetchCameras).toHaveBeenCalled();
    });

    // Check that baseline data is fetched for first camera
    await waitFor(() => {
      expect(api.fetchCameraActivityBaseline).toHaveBeenCalledWith('cam1');
    });
  });

  it('auto-selects first camera when none specified', async () => {
    render(<BaselineAnalytics />);

    await waitFor(() => {
      // Should fetch baseline for first camera
      expect(api.fetchCameraActivityBaseline).toHaveBeenCalledWith('cam1');
    });
  });

  it('uses initialCameraId when provided', async () => {
    render(<BaselineAnalytics initialCameraId="cam2" />);

    await waitFor(() => {
      expect(api.fetchCameraActivityBaseline).toHaveBeenCalledWith('cam2');
    });
  });

  it('displays baseline status indicator', async () => {
    render(<BaselineAnalytics />);

    await waitFor(() => {
      expect(screen.getByText('Front Door Baseline Status')).toBeInTheDocument();
    });
  });

  it('shows learning complete message', async () => {
    render(<BaselineAnalytics />);

    await waitFor(() => {
      expect(screen.getByText('Baseline learning complete - anomaly detection active')).toBeInTheDocument();
    });
  });

  it('shows learning in progress message', async () => {
    const incompleteBaseline = { ...mockActivityBaseline, learning_complete: false };
    vi.mocked(api.fetchCameraActivityBaseline).mockResolvedValue(incompleteBaseline);

    render(<BaselineAnalytics />);

    await waitFor(() => {
      expect(screen.getByText('Collecting data - anomaly detection will activate when learning completes')).toBeInTheDocument();
    });
  });

  it('displays total samples count', async () => {
    render(<BaselineAnalytics />);

    await waitFor(() => {
      expect(screen.getByText('500')).toBeInTheDocument();
      expect(screen.getByText('total samples')).toBeInTheDocument();
    });
  });

  it('renders ActivityHeatmap component', async () => {
    render(<BaselineAnalytics />);

    await waitFor(() => {
      expect(screen.getByText('Activity Heatmap')).toBeInTheDocument();
    });
  });

  it('renders ClassFrequencyChart component', async () => {
    render(<BaselineAnalytics />);

    await waitFor(() => {
      expect(screen.getByText('Object Class Distribution')).toBeInTheDocument();
    });
  });

  it('renders AnomalyConfigPanel component', async () => {
    render(<BaselineAnalytics />);

    await waitFor(() => {
      expect(screen.getByText('Anomaly Detection Settings')).toBeInTheDocument();
    });
  });

  it('shows error when cameras fail to load', async () => {
    vi.mocked(api.fetchCameras).mockRejectedValue(new Error('Failed to fetch cameras'));

    render(<BaselineAnalytics />);

    await waitFor(() => {
      expect(screen.getByText('Error loading baseline data')).toBeInTheDocument();
      expect(screen.getByText('Failed to fetch cameras')).toBeInTheDocument();
    });
  });

  it('shows error when baseline fails to load', async () => {
    vi.mocked(api.fetchCameraActivityBaseline).mockRejectedValue(new Error('Baseline error'));

    render(<BaselineAnalytics />);

    await waitFor(() => {
      expect(screen.getByText('Error loading baseline data')).toBeInTheDocument();
      expect(screen.getByText('Baseline error')).toBeInTheDocument();
    });
  });

  it('shows no cameras message when list is empty', async () => {
    vi.mocked(api.fetchCameras).mockResolvedValue([]);

    render(<BaselineAnalytics />);

    await waitFor(() => {
      expect(screen.getByText('No cameras configured')).toBeInTheDocument();
      expect(screen.getByText('Add cameras in the Cameras settings tab')).toBeInTheDocument();
    });
  });

  it('has refresh button', async () => {
    render(<BaselineAnalytics />);

    await waitFor(() => {
      expect(screen.getByTitle('Refresh baseline data')).toBeInTheDocument();
    });
  });

  it('applies custom className', async () => {
    const { container } = render(<BaselineAnalytics className="custom-class" />);

    await waitFor(() => {
      expect(screen.getByText('Baseline Analytics')).toBeInTheDocument();
    });

    expect(container.firstChild).toHaveClass('custom-class');
  });
});

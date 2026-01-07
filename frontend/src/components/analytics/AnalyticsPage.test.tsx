import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import AnalyticsPage from './AnalyticsPage';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    fetchCameras: vi.fn(),
    fetchCameraActivityBaseline: vi.fn(),
    fetchCameraClassBaseline: vi.fn(),
    fetchAnomalyConfig: vi.fn(),
    updateAnomalyConfig: vi.fn(),
    fetchSceneChanges: vi.fn(),
    acknowledgeSceneChange: vi.fn(),
  };
});

describe('AnalyticsPage', () => {
  const mockCameras = [
    { id: 'cam1', name: 'Front Door', folder_path: '/export/foscam/front_door', status: 'online' as const, created_at: '2024-01-01T00:00:00Z' },
    { id: 'cam2', name: 'Back Yard', folder_path: '/export/foscam/back_yard', status: 'online' as const, created_at: '2024-01-01T00:00:00Z' },
  ];

  const mockActivityBaseline = {
    camera_id: 'cam1',
    entries: [
      { hour: 0, day_of_week: 0, avg_count: 0.5, sample_count: 30, is_peak: false },
      { hour: 17, day_of_week: 4, avg_count: 5.2, sample_count: 30, is_peak: true },
    ],
    total_samples: 60,
    peak_hour: 17,
    peak_day: 4,
    learning_complete: true,
    min_samples_required: 10,
  };

  const mockClassBaseline = {
    camera_id: 'cam1',
    entries: [
      { object_class: 'person', hour: 17, frequency: 3.5, sample_count: 45 },
    ],
    unique_classes: ['person'],
    total_samples: 45,
    most_common_class: 'person',
  };

  const mockAnomalyConfig = {
    threshold_stdev: 2.0,
    min_samples: 10,
    decay_factor: 0.1,
    window_days: 30,
  };

  const mockSceneChanges = {
    camera_id: 'cam1',
    scene_changes: [],
    total_changes: 0,
    next_cursor: null,
    has_more: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    vi.mocked(api.fetchCameraActivityBaseline).mockResolvedValue(mockActivityBaseline);
    vi.mocked(api.fetchCameraClassBaseline).mockResolvedValue(mockClassBaseline);
    vi.mocked(api.fetchAnomalyConfig).mockResolvedValue(mockAnomalyConfig);
    vi.mocked(api.fetchSceneChanges).mockResolvedValue(mockSceneChanges);
  });

  it('renders the page header', () => {
    render(<AnalyticsPage />);

    expect(screen.getByText('Analytics')).toBeInTheDocument();
    expect(screen.getByText(/View activity patterns/)).toBeInTheDocument();
  });

  it('shows loading state initially with skeleton loaders', () => {
    render(<AnalyticsPage />);

    // Skeleton loaders display chart skeletons during loading
    expect(screen.getAllByTestId('chart-skeleton').length).toBeGreaterThan(0);
  });

  it('loads and displays camera selector', async () => {
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('camera-selector')).toBeInTheDocument();
    });

    const selector = screen.getByTestId('camera-selector');
    expect(selector).toHaveValue('cam1');
  });

  it('fetches baseline data for selected camera', async () => {
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(api.fetchCameraActivityBaseline).toHaveBeenCalledWith('cam1');
      expect(api.fetchCameraClassBaseline).toHaveBeenCalledWith('cam1');
      expect(api.fetchAnomalyConfig).toHaveBeenCalled();
    });
  });

  it('displays activity heatmap after loading', async () => {
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('Weekly Activity Pattern')).toBeInTheDocument();
    });
  });

  it('displays class frequency chart after loading', async () => {
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('Object Class Distribution')).toBeInTheDocument();
    });
  });

  it('displays anomaly config panel after loading', async () => {
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('Anomaly Detection Settings')).toBeInTheDocument();
    });
  });

  it('shows learning status badge', async () => {
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('Learning Complete')).toBeInTheDocument();
    });
  });

  it('shows total samples count', async () => {
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('60')).toBeInTheDocument();
    });
  });

  it('changes camera when selector changes', async () => {
    const user = userEvent.setup();
    render(<AnalyticsPage />);

    // Wait for cameras to load (selector should have cam1 selected)
    await waitFor(() => {
      const selector = screen.getByTestId('camera-selector');
      expect(selector).toHaveValue('cam1');
    });

    const selector = screen.getByTestId('camera-selector');
    await user.selectOptions(selector, 'cam2');

    await waitFor(() => {
      expect(api.fetchCameraActivityBaseline).toHaveBeenCalledWith('cam2');
    });
  });

  it('shows error state when fetch fails', async () => {
    vi.mocked(api.fetchCameraActivityBaseline).mockRejectedValue(new Error('Network error'));

    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load baseline data')).toBeInTheDocument();
    });
  });

  it('shows refresh button', async () => {
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('analytics-refresh-button')).toBeInTheDocument();
    });
  });

  it('refreshes data when refresh button is clicked', async () => {
    const user = userEvent.setup();
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('analytics-refresh-button')).toBeInTheDocument();
    });

    const refreshButton = screen.getByTestId('analytics-refresh-button');
    await user.click(refreshButton);

    await waitFor(() => {
      expect(api.fetchCameraActivityBaseline).toHaveBeenCalledTimes(2);
    });
  });

  it('shows empty state when no cameras', async () => {
    vi.mocked(api.fetchCameras).mockResolvedValue([]);

    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('No Cameras Found')).toBeInTheDocument();
    });
  });
});

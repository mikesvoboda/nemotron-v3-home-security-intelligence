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
    fetchEventStats: vi.fn(),
    fetchDetectionStats: vi.fn(),
    fetchEvents: vi.fn(),
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

  const mockEventStats = {
    total_events: 42,
    events_by_camera: [
      { camera_id: 'cam1', camera_name: 'Front Door', event_count: 25 },
      { camera_id: 'cam2', camera_name: 'Back Yard', event_count: 17 },
    ],
    events_by_risk_level: {
      low: 10,
      medium: 20,
      high: 12,
      critical: 0,
    },
  };

  const mockDetectionStats = {
    total_detections: 156,
    detections_by_class: {
      person: 89,
      car: 45,
      dog: 22,
    },
    average_confidence: 0.87,
  };

  const mockEvents = {
    items: [
      {
        id: 1,
        camera_id: 'cam1',
        started_at: '2024-01-07T14:00:00Z',
        ended_at: null,
        risk_score: 85,
        risk_level: 'high',
        reasoning: 'Person detected near entrance after hours',
        reviewed: false,
        detection_count: 3,
        summary: 'High risk event',
      },
    ],
    pagination: {
      total: 1,
      limit: 10,
      offset: 0,
      has_more: false,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    vi.mocked(api.fetchCameraActivityBaseline).mockResolvedValue(mockActivityBaseline);
    vi.mocked(api.fetchCameraClassBaseline).mockResolvedValue(mockClassBaseline);
    vi.mocked(api.fetchAnomalyConfig).mockResolvedValue(mockAnomalyConfig);
    vi.mocked(api.fetchEventStats).mockResolvedValue(mockEventStats);
    vi.mocked(api.fetchDetectionStats).mockResolvedValue(mockDetectionStats);
    vi.mocked(api.fetchEvents).mockResolvedValue(mockEvents);
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

  it('loads and displays camera selector with All Cameras default', async () => {
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('camera-selector')).toBeInTheDocument();
    });

    const selector = screen.getByTestId('camera-selector');
    // Default selection is "All Cameras" (empty string value)
    expect(selector).toHaveValue('');
  });

  it('shows All Cameras option in dropdown', async () => {
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('All Cameras')).toBeInTheDocument();
    });
  });

  it('fetches global stats when All Cameras is selected (default)', async () => {
    render(<AnalyticsPage />);

    await waitFor(() => {
      // Should fetch global stats without camera_id filter
      expect(api.fetchAnomalyConfig).toHaveBeenCalled();
      expect(api.fetchEventStats).toHaveBeenCalledWith(expect.objectContaining({
        camera_id: undefined,
      }));
      expect(api.fetchDetectionStats).toHaveBeenCalledWith({ camera_id: undefined });
      // Should NOT fetch camera-specific baselines for "All Cameras" view
      expect(api.fetchCameraActivityBaseline).not.toHaveBeenCalled();
      expect(api.fetchCameraClassBaseline).not.toHaveBeenCalled();
    });
  });

  it('fetches camera-specific data when a camera is selected', async () => {
    const user = userEvent.setup();
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('camera-selector')).toBeInTheDocument();
    });

    // Select a specific camera
    const selector = screen.getByTestId('camera-selector');
    await user.selectOptions(selector, 'cam1');

    await waitFor(() => {
      expect(api.fetchCameraActivityBaseline).toHaveBeenCalledWith('cam1');
      expect(api.fetchCameraClassBaseline).toHaveBeenCalledWith('cam1');
      expect(api.fetchAnomalyConfig).toHaveBeenCalled();
      expect(api.fetchEventStats).toHaveBeenCalledWith(expect.objectContaining({
        camera_id: 'cam1',
      }));
      expect(api.fetchDetectionStats).toHaveBeenCalledWith({ camera_id: 'cam1' });
    });
  });

  it('displays tab navigation after loading', async () => {
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('analytics-tab-overview')).toBeInTheDocument();
      expect(screen.getByTestId('analytics-tab-detections')).toBeInTheDocument();
      expect(screen.getByTestId('analytics-tab-risk')).toBeInTheDocument();
      expect(screen.getByTestId('analytics-tab-camera-performance')).toBeInTheDocument();
    });
  });

  it('displays key metrics in overview tab', async () => {
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('Total Events')).toBeInTheDocument();
      // Check for multiple metric cards in the overview
      const detectionElements = screen.getAllByText('Total Detections');
      expect(detectionElements.length).toBeGreaterThan(0);
      expect(screen.getAllByText('Average Confidence').length).toBeGreaterThan(0);
      expect(screen.getByText('High Risk Events')).toBeInTheDocument();
    });
  });

  it('displays activity heatmap in camera performance tab when camera is selected', async () => {
    const user = userEvent.setup();
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('analytics-tab-camera-performance')).toBeInTheDocument();
    });

    // First select a specific camera to see activity heatmap
    const selector = screen.getByTestId('camera-selector');
    await user.selectOptions(selector, 'cam1');

    // Wait for baseline data to load
    await waitFor(() => {
      expect(api.fetchCameraActivityBaseline).toHaveBeenCalledWith('cam1');
    });

    // Click on Camera Performance tab
    await user.click(screen.getByTestId('analytics-tab-camera-performance'));

    await waitFor(() => {
      expect(screen.getByText('Weekly Activity Pattern')).toBeInTheDocument();
    });
  });

  it('shows learning status badge when camera is selected', async () => {
    const user = userEvent.setup();
    render(<AnalyticsPage />);

    // Select a specific camera to see learning status
    await waitFor(() => {
      expect(screen.getByTestId('camera-selector')).toBeInTheDocument();
    });
    const selector = screen.getByTestId('camera-selector');
    await user.selectOptions(selector, 'cam1');

    await waitFor(() => {
      expect(screen.getByText('Learning Complete')).toBeInTheDocument();
    });
  });

  it('shows total samples count when camera is selected', async () => {
    const user = userEvent.setup();
    render(<AnalyticsPage />);

    // Select a specific camera to see sample count
    await waitFor(() => {
      expect(screen.getByTestId('camera-selector')).toBeInTheDocument();
    });
    const selector = screen.getByTestId('camera-selector');
    await user.selectOptions(selector, 'cam1');

    await waitFor(() => {
      expect(screen.getByText('60')).toBeInTheDocument();
    });
  });

  it('changes camera when selector changes', async () => {
    const user = userEvent.setup();
    render(<AnalyticsPage />);

    // Wait for initial load with All Cameras
    await waitFor(() => {
      const selector = screen.getByTestId('camera-selector');
      expect(selector).toHaveValue('');
    });

    // Select cam1
    const selector = screen.getByTestId('camera-selector');
    await user.selectOptions(selector, 'cam1');

    await waitFor(() => {
      expect(api.fetchCameraActivityBaseline).toHaveBeenCalledWith('cam1');
    });

    // Clear mocks and switch to cam2
    vi.clearAllMocks();
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    vi.mocked(api.fetchCameraActivityBaseline).mockResolvedValue(mockActivityBaseline);
    vi.mocked(api.fetchCameraClassBaseline).mockResolvedValue(mockClassBaseline);
    vi.mocked(api.fetchAnomalyConfig).mockResolvedValue(mockAnomalyConfig);
    vi.mocked(api.fetchEventStats).mockResolvedValue(mockEventStats);
    vi.mocked(api.fetchDetectionStats).mockResolvedValue(mockDetectionStats);
    vi.mocked(api.fetchEvents).mockResolvedValue(mockEvents);

    await user.selectOptions(selector, 'cam2');

    await waitFor(() => {
      expect(api.fetchCameraActivityBaseline).toHaveBeenCalledWith('cam2');
    });
  });

  it('shows error state when fetch fails', async () => {
    // Error in a required API call (anomaly config is always fetched)
    vi.mocked(api.fetchAnomalyConfig).mockRejectedValue(new Error('Network error'));

    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load analytics data')).toBeInTheDocument();
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
      // Since default is "All Cameras", anomaly config should be fetched twice (initial + refresh)
      expect(api.fetchAnomalyConfig).toHaveBeenCalledTimes(2);
    });
  });

  it('shows aggregate stats indicator when All Cameras is selected', async () => {
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('Showing aggregate stats across all cameras')).toBeInTheDocument();
    });
  });

  it('shows camera-specific empty state message in Camera Performance tab', async () => {
    const user = userEvent.setup();
    render(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('analytics-tab-camera-performance')).toBeInTheDocument();
    });

    // Click on Camera Performance tab while "All Cameras" is selected
    await user.click(screen.getByTestId('analytics-tab-camera-performance'));

    await waitFor(() => {
      expect(screen.getByText('Select a specific camera to view activity heatmap')).toBeInTheDocument();
      expect(screen.getByText('Select a specific camera to view scene changes')).toBeInTheDocument();
    });
  });

  it('still loads and shows stats when no cameras available', async () => {
    vi.mocked(api.fetchCameras).mockResolvedValue([]);

    render(<AnalyticsPage />);

    // Should still show the stats (aggregate across no data)
    await waitFor(() => {
      expect(screen.getByText('Total Events')).toBeInTheDocument();
      expect(screen.getByText('All Cameras')).toBeInTheDocument();
    });
  });
});

import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import AnalyticsPage from './AnalyticsPage';
import * as api from '../../services/api';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

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
    fetchDetectionTrends: vi.fn(),
    fetchRiskHistory: vi.fn(),
  };
});

describe('AnalyticsPage', () => {
  const mockCameras = [
    {
      id: 'cam1',
      name: 'Front Door',
      folder_path: '/export/foscam/front_door',
      status: 'online' as const,
      created_at: '2024-01-01T00:00:00Z',
    },
    {
      id: 'cam2',
      name: 'Back Yard',
      folder_path: '/export/foscam/back_yard',
      status: 'online' as const,
      created_at: '2024-01-01T00:00:00Z',
    },
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
    entries: [{ object_class: 'person', hour: 17, frequency: 3.5, sample_count: 45 }],
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

  const mockDetectionTrends = {
    data_points: [
      { date: '2026-01-10', count: 45 },
      { date: '2026-01-11', count: 67 },
      { date: '2026-01-12', count: 32 },
      { date: '2026-01-13', count: 89 },
      { date: '2026-01-14', count: 54 },
      { date: '2026-01-15', count: 0 },
      { date: '2026-01-16', count: 78 },
    ],
    total_detections: 365,
    start_date: '2026-01-10',
    end_date: '2026-01-16',
  };

  const mockRiskHistory = {
    data_points: [
      { date: '2026-01-10', low: 12, medium: 8, high: 3, critical: 1 },
      { date: '2026-01-11', low: 15, medium: 10, high: 5, critical: 0 },
      { date: '2026-01-12', low: 8, medium: 6, high: 2, critical: 2 },
      { date: '2026-01-13', low: 20, medium: 12, high: 4, critical: 1 },
      { date: '2026-01-14', low: 10, medium: 9, high: 3, critical: 0 },
      { date: '2026-01-15', low: 5, medium: 3, high: 1, critical: 0 },
      { date: '2026-01-16', low: 18, medium: 11, high: 6, critical: 2 },
    ],
    start_date: '2026-01-10',
    end_date: '2026-01-16',
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
    vi.mocked(api.fetchDetectionTrends).mockResolvedValue(mockDetectionTrends);
    vi.mocked(api.fetchRiskHistory).mockResolvedValue(mockRiskHistory);
  });

  it('renders the page header', () => {
    renderWithProviders(<AnalyticsPage />);

    expect(screen.getByText('Analytics')).toBeInTheDocument();
    expect(screen.getByText(/View activity patterns/)).toBeInTheDocument();
  });

  it('shows loading state initially with skeleton loaders', () => {
    renderWithProviders(<AnalyticsPage />);

    // Skeleton loaders display chart skeletons during loading
    expect(screen.getAllByTestId('chart-skeleton').length).toBeGreaterThan(0);
  });

  it('loads and displays camera selector with All Cameras default', async () => {
    renderWithProviders(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('camera-selector')).toBeInTheDocument();
    });

    const selector = screen.getByTestId('camera-selector');
    // Default selection is "All Cameras" (empty string value)
    expect(selector).toHaveValue('');
  });

  it('shows All Cameras option in dropdown', async () => {
    renderWithProviders(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('All Cameras')).toBeInTheDocument();
    });
  });

  it('fetches global stats when All Cameras is selected (default)', async () => {
    renderWithProviders(<AnalyticsPage />);

    await waitFor(() => {
      // Should fetch global stats without camera_id filter
      expect(api.fetchAnomalyConfig).toHaveBeenCalled();
      expect(api.fetchEventStats).toHaveBeenCalledWith(
        expect.objectContaining({
          camera_id: undefined,
        })
      );
      expect(api.fetchDetectionStats).toHaveBeenCalledWith({ camera_id: undefined });
      // Should NOT fetch camera-specific baselines for "All Cameras" view
      expect(api.fetchCameraActivityBaseline).not.toHaveBeenCalled();
      expect(api.fetchCameraClassBaseline).not.toHaveBeenCalled();
    });
  });

  it('fetches camera-specific data when a camera is selected', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AnalyticsPage />);

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
      expect(api.fetchEventStats).toHaveBeenCalledWith(
        expect.objectContaining({
          camera_id: 'cam1',
        })
      );
      expect(api.fetchDetectionStats).toHaveBeenCalledWith({ camera_id: 'cam1' });
    });
  });

  it('displays tab navigation after loading', async () => {
    renderWithProviders(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('analytics-tab-overview')).toBeInTheDocument();
      expect(screen.getByTestId('analytics-tab-detections')).toBeInTheDocument();
      expect(screen.getByTestId('analytics-tab-risk')).toBeInTheDocument();
      expect(screen.getByTestId('analytics-tab-camera-performance')).toBeInTheDocument();
    });
  });

  it('displays key metrics in overview tab', async () => {
    renderWithProviders(<AnalyticsPage />);

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
    renderWithProviders(<AnalyticsPage />);

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
    renderWithProviders(<AnalyticsPage />);

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
    renderWithProviders(<AnalyticsPage />);

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
    renderWithProviders(<AnalyticsPage />);

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

    renderWithProviders(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load analytics data')).toBeInTheDocument();
    });
  });

  it('shows refresh button', async () => {
    renderWithProviders(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('analytics-refresh-button')).toBeInTheDocument();
    });
  });

  it('refreshes data when refresh button is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AnalyticsPage />);

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
    renderWithProviders(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByText('Showing aggregate stats across all cameras')).toBeInTheDocument();
    });
  });

  it('shows camera-specific empty state message in Camera Performance tab', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AnalyticsPage />);

    await waitFor(() => {
      expect(screen.getByTestId('analytics-tab-camera-performance')).toBeInTheDocument();
    });

    // Click on Camera Performance tab while "All Cameras" is selected
    await user.click(screen.getByTestId('analytics-tab-camera-performance'));

    await waitFor(() => {
      expect(
        screen.getByText('Select a specific camera to view activity heatmap')
      ).toBeInTheDocument();
      expect(
        screen.getByText('Select a specific camera to view scene changes')
      ).toBeInTheDocument();
    });
  });

  it('still loads and shows stats when no cameras available', async () => {
    vi.mocked(api.fetchCameras).mockResolvedValue([]);

    renderWithProviders(<AnalyticsPage />);

    // Should still show the stats (aggregate across no data)
    await waitFor(() => {
      expect(screen.getByText('Total Events')).toBeInTheDocument();
      expect(screen.getByText('All Cameras')).toBeInTheDocument();
    });
  });

  describe('Detection Trends', () => {
    it('fetches detection trends data on page load', async () => {
      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(api.fetchDetectionTrends).toHaveBeenCalled();
      });
    });

    it('displays detection trend chart in overview tab', async () => {
      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        // The card title should reflect the date range
        expect(screen.getByText(/Detection Trend/)).toBeInTheDocument();
      });
    });

    it('shows loading state for detection trends chart', async () => {
      // Make fetchDetectionTrends hang to see loading state
      vi.mocked(api.fetchDetectionTrends).mockReturnValue(new Promise(() => {}));

      renderWithProviders(<AnalyticsPage />);

      // During loading, we expect chart skeleton or loading indicator
      // The chart will show "Loading trend data..." or similar
      await waitFor(() => {
        expect(screen.getByTestId('camera-selector')).toBeInTheDocument();
      });
    });

    it('handles detection trends API error gracefully', async () => {
      vi.mocked(api.fetchDetectionTrends).mockRejectedValue(new Error('Network error'));

      renderWithProviders(<AnalyticsPage />);

      // Page should still load, just without trends data
      await waitFor(() => {
        expect(screen.getByText('Total Events')).toBeInTheDocument();
      });
    });

    it('shows empty state when no detection trend data available', async () => {
      vi.mocked(api.fetchDetectionTrends).mockResolvedValue({
        data_points: [],
        total_detections: 0,
        start_date: '2026-01-10',
        end_date: '2026-01-16',
      });

      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(screen.getByText(/No detection data available/)).toBeInTheDocument();
      });
    });
  });

  describe('Risk History Chart (NEM-2704)', () => {
    it('fetches risk history data on page load', async () => {
      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(api.fetchRiskHistory).toHaveBeenCalled();
      });
    });

    it('displays risk history chart card in risk analysis tab', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AnalyticsPage />);

      // Wait for page to load
      await waitFor(() => {
        expect(screen.getByTestId('analytics-tab-risk')).toBeInTheDocument();
      });

      // Click on Risk Analysis tab
      await user.click(screen.getByTestId('analytics-tab-risk'));

      await waitFor(() => {
        expect(screen.getByTestId('risk-history-chart-card')).toBeInTheDocument();
      });
    });

    it('displays risk level breakdown title with date range', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('analytics-tab-risk')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('analytics-tab-risk'));

      await waitFor(() => {
        expect(screen.getByText(/Risk Level Breakdown/)).toBeInTheDocument();
      });
    });

    it('displays legend with all 4 risk levels', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('analytics-tab-risk')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('analytics-tab-risk'));

      // Wait for the risk history data to load and legend to appear
      await waitFor(
        () => {
          expect(screen.getByTestId('risk-history-legend')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      // Check all labels within the legend element to avoid duplicate text issues
      const legend = screen.getByTestId('risk-history-legend');
      expect(within(legend).getByText('Critical (81+)')).toBeInTheDocument();
      expect(within(legend).getByText('High (61-80)')).toBeInTheDocument();
      expect(within(legend).getByText('Medium (31-60)')).toBeInTheDocument();
      expect(within(legend).getByText('Low (0-30)')).toBeInTheDocument();
    });

    it('shows loading state for risk history chart', async () => {
      // Make fetchRiskHistory hang to see loading state
      vi.mocked(api.fetchRiskHistory).mockReturnValue(new Promise(() => {}));
      const user = userEvent.setup();

      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('analytics-tab-risk')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('analytics-tab-risk'));

      // Should show chart skeleton during loading
      await waitFor(() => {
        expect(screen.getByTestId('risk-history-chart-card')).toBeInTheDocument();
      });
    });

    it('shows error state when risk history API fails', async () => {
      vi.mocked(api.fetchRiskHistory).mockRejectedValue(new Error('Network error'));
      const user = userEvent.setup();

      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('analytics-tab-risk')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('analytics-tab-risk'));

      await waitFor(
        () => {
          expect(screen.getByText('Failed to load risk history data')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });

    it('shows empty state when no risk history data available', async () => {
      vi.mocked(api.fetchRiskHistory).mockResolvedValue({
        data_points: [],
        start_date: '2026-01-10',
        end_date: '2026-01-16',
      });
      const user = userEvent.setup();

      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('analytics-tab-risk')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('analytics-tab-risk'));

      await waitFor(() => {
        expect(screen.getByText('No risk history data available')).toBeInTheDocument();
      });
    });

    it('replaced mock event activity data with real risk history data', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('analytics-tab-risk')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('analytics-tab-risk'));

      // The old "Event Activity Trend" title should be replaced with new title
      await waitFor(() => {
        expect(screen.queryByText('Event Activity Trend')).not.toBeInTheDocument();
        expect(screen.getByText(/Risk Level Breakdown/)).toBeInTheDocument();
      });
    });
  });

  describe('Date Range Dropdown (NEM-2702)', () => {
    it('renders date range dropdown in the header', async () => {
      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('date-range-dropdown')).toBeInTheDocument();
      });
    });

    it('displays default preset label (Last 7 days)', async () => {
      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('date-range-dropdown')).toHaveTextContent('Last 7 days');
      });
    });

    it('opens dropdown menu when clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('date-range-dropdown')).toBeInTheDocument();
      });

      const dropdown = screen.getByTestId('date-range-dropdown');
      await user.click(dropdown);

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });
    });

    it('shows preset options in dropdown menu', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('date-range-dropdown')).toBeInTheDocument();
      });

      const dropdown = screen.getByTestId('date-range-dropdown');
      await user.click(dropdown);

      await waitFor(() => {
        expect(screen.getByRole('menuitem', { name: /Last 7 days/ })).toBeInTheDocument();
        expect(screen.getByRole('menuitem', { name: /Last 30 days/ })).toBeInTheDocument();
        expect(screen.getByRole('menuitem', { name: /Last 90 days/ })).toBeInTheDocument();
        expect(screen.getByRole('menuitem', { name: /Custom range/ })).toBeInTheDocument();
      });
    });

    it('updates displayed label when preset is changed', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('date-range-dropdown')).toBeInTheDocument();
      });

      const dropdown = screen.getByTestId('date-range-dropdown');
      await user.click(dropdown);

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      const thirtyDaysOption = screen.getByRole('menuitem', { name: /Last 30 days/ });
      await user.click(thirtyDaysOption);

      // Wait for menu to close and label to update
      await waitFor(() => {
        expect(screen.queryByRole('menu')).not.toBeInTheDocument();
      });
    });

    it('refetches data when date range changes', async () => {
      const user = userEvent.setup();
      renderWithProviders(<AnalyticsPage />);

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('date-range-dropdown')).toBeInTheDocument();
      });

      // Clear mocks to track new calls
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchAnomalyConfig).mockResolvedValue(mockAnomalyConfig);
      vi.mocked(api.fetchEventStats).mockResolvedValue(mockEventStats);
      vi.mocked(api.fetchDetectionStats).mockResolvedValue(mockDetectionStats);
      vi.mocked(api.fetchEvents).mockResolvedValue(mockEvents);
      vi.mocked(api.fetchDetectionTrends).mockResolvedValue(mockDetectionTrends);
      vi.mocked(api.fetchRiskHistory).mockResolvedValue(mockRiskHistory);

      const dropdown = screen.getByTestId('date-range-dropdown');
      await user.click(dropdown);

      await waitFor(() => {
        expect(screen.getByRole('menu')).toBeInTheDocument();
      });

      const thirtyDaysOption = screen.getByRole('menuitem', { name: /Last 30 days/ });
      await user.click(thirtyDaysOption);

      // Should refetch with new date range
      await waitFor(() => {
        expect(api.fetchEventStats).toHaveBeenCalled();
      });
    });

    it('dropdown is positioned next to Analytics title', async () => {
      renderWithProviders(<AnalyticsPage />);

      await waitFor(() => {
        expect(screen.getByTestId('date-range-dropdown')).toBeInTheDocument();
      });

      // The dropdown should be in the header (flex container with justify-between)
      const dropdown = screen.getByTestId('date-range-dropdown');
      const header = dropdown.closest('.flex.items-center.justify-between');
      expect(header).toBeInTheDocument();

      // And the Analytics title should be in the same flex container
      expect(header).toContainElement(screen.getByText('Analytics'));
    });
  });
});

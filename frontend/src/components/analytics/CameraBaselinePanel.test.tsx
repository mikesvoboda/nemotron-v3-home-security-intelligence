/**
 * Tests for CameraBaselinePanel component
 *
 * TDD: Tests written first to define the expected behavior.
 * @see NEM-3576 - Camera Baseline Activity API Integration
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import CameraBaselinePanel from './CameraBaselinePanel';
import * as api from '../../services/api';

import type { ActivityBaselineResponse, BaselineSummaryResponse } from '../../services/api';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchCameraBaseline: vi.fn(),
  fetchCameraActivityBaseline: vi.fn(),
  fetchCameraClassBaseline: vi.fn(),
}));

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  });

const renderWithProviders = (ui: React.ReactElement) => {
  const queryClient = createTestQueryClient();
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
};

describe('CameraBaselinePanel', () => {
  const mockCameraId = 'cam-1';
  const mockCameraName = 'Front Door';

  const mockBaselineSummary: BaselineSummaryResponse = {
    camera_id: mockCameraId,
    camera_name: mockCameraName,
    baseline_established: '2026-01-01T00:00:00Z',
    data_points: 720,
    hourly_patterns: {
      '0': { avg_detections: 0.5, std_dev: 0.3, sample_count: 30 },
      '17': { avg_detections: 5.2, std_dev: 1.1, sample_count: 30 },
    },
    daily_patterns: {
      monday: { avg_detections: 45, peak_hour: 17, total_samples: 24 },
    },
    object_baselines: {
      person: { avg_hourly: 2.3, peak_hour: 17, total_detections: 550 },
    },
    current_deviation: {
      score: 1.8,
      interpretation: 'slightly_above_normal',
      contributing_factors: ['person_count_elevated'],
    },
  };

  const mockActivityBaseline: ActivityBaselineResponse = {
    camera_id: mockCameraId,
    entries: [
      { hour: 0, day_of_week: 0, avg_count: 0.5, sample_count: 30, is_peak: false },
      { hour: 17, day_of_week: 4, avg_count: 5.2, sample_count: 30, is_peak: true },
    ],
    total_samples: 720,
    peak_hour: 17,
    peak_day: 4,
    learning_complete: true,
    min_samples_required: 10,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCameraBaseline).mockResolvedValue(mockBaselineSummary);
    vi.mocked(api.fetchCameraActivityBaseline).mockResolvedValue(mockActivityBaseline);
    vi.mocked(api.fetchCameraClassBaseline).mockResolvedValue({
      camera_id: mockCameraId,
      entries: [],
      unique_classes: ['person', 'vehicle'],
      total_samples: 100,
      most_common_class: 'person',
    });
  });

  describe('loading state', () => {
    it('renders loading state initially', () => {
      vi.mocked(api.fetchCameraBaseline).mockImplementation(() => new Promise(() => {}));
      vi.mocked(api.fetchCameraActivityBaseline).mockImplementation(() => new Promise(() => {}));

      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      expect(screen.getByText(/loading baseline/i)).toBeInTheDocument();
    });
  });

  describe('data display', () => {
    it('renders camera name in header', async () => {
      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByText(mockCameraName)).toBeInTheDocument();
      });
    });

    it('renders ActivityHeatmap component with fetched data', async () => {
      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByText(/weekly activity pattern/i)).toBeInTheDocument();
      });
    });

    it('displays learning progress when not complete', async () => {
      vi.mocked(api.fetchCameraActivityBaseline).mockResolvedValue({
        ...mockActivityBaseline,
        learning_complete: false,
        entries: mockActivityBaseline.entries.slice(0, 50), // Partial data
      });

      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByText(/learning/i)).toBeInTheDocument();
      });
    });

    it('displays current deviation status when available', async () => {
      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByText(/slightly above normal/i)).toBeInTheDocument();
      });
    });

    it('displays deviation score', async () => {
      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByText(/1.8/)).toBeInTheDocument();
      });
    });

    it('displays contributing factors', async () => {
      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByText(/person_count_elevated/i)).toBeInTheDocument();
      });
    });
  });

  describe('empty state', () => {
    it('shows empty state when no baseline data exists', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        data_points: 0,
        baseline_established: null,
        current_deviation: null,
      });
      vi.mocked(api.fetchCameraActivityBaseline).mockResolvedValue({
        ...mockActivityBaseline,
        entries: [],
        learning_complete: false,
      });

      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByText(/no baseline data/i)).toBeInTheDocument();
      });
    });
  });

  describe('error handling', () => {
    it('displays error message when API fails', async () => {
      vi.mocked(api.fetchCameraBaseline).mockRejectedValue(new Error('Network error'));
      vi.mocked(api.fetchCameraActivityBaseline).mockRejectedValue(new Error('Network error'));

      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(
        () => {
          expect(screen.getByText(/error loading baseline/i)).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('data points display', () => {
    it('displays total data points', async () => {
      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByText(/720/)).toBeInTheDocument();
      });
    });

    it('displays baseline established date', async () => {
      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        // Should display "Since" label with a date
        expect(screen.getByText(/since/i)).toBeInTheDocument();
      });
    });
  });

  describe('deviation interpretation display', () => {
    it('displays far_below_normal interpretation correctly', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        current_deviation: {
          score: 1.0,
          interpretation: 'far_below_normal',
          contributing_factors: [],
        },
      });

      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByText(/far below normal/i)).toBeInTheDocument();
      });
    });

    it('displays below_normal interpretation correctly', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        current_deviation: {
          score: 1.0,
          interpretation: 'below_normal',
          contributing_factors: [],
        },
      });

      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByText(/below normal/i)).toBeInTheDocument();
      });
    });

    it('displays normal interpretation correctly', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        current_deviation: {
          score: 1.0,
          interpretation: 'normal',
          contributing_factors: [],
        },
      });

      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByText(/^normal$/i)).toBeInTheDocument();
      });
    });

    it('displays above_normal interpretation correctly', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        current_deviation: {
          score: 1.0,
          interpretation: 'above_normal',
          contributing_factors: [],
        },
      });

      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByText(/above normal/i)).toBeInTheDocument();
      });
    });

    it('displays far_above_normal interpretation correctly', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        current_deviation: {
          score: 1.0,
          interpretation: 'far_above_normal',
          contributing_factors: [],
        },
      });

      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByText(/far above normal/i)).toBeInTheDocument();
      });
    });
  });

  describe('test data id attributes', () => {
    it('has testid for main container', async () => {
      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByTestId('camera-baseline-panel')).toBeInTheDocument();
      });
    });

    it('has testid for deviation status', async () => {
      renderWithProviders(<CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />);

      await waitFor(() => {
        expect(screen.getByTestId('deviation-status')).toBeInTheDocument();
      });
    });
  });
});

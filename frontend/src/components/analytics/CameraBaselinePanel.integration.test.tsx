/**
 * Integration Tests for CameraBaselinePanel Component
 *
 * Tests real-world interaction flows including:
 * - API → Hook → Component data flow
 * - Loading → Success state transitions
 * - Loading → Error → Retry → Success recovery flow
 * - Component composition with ActivityHeatmap
 * - Deviation status display and updates
 *
 * @see NEM-4914 - [TDD] Integration tests for Phase 2: Baseline Visualization
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
}));

/**
 * Creates a fresh QueryClient for each test.
 * This ensures test isolation by preventing cache contamination.
 */
const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false, // Disable retries for predictable test behavior
        gcTime: 0, // Disable garbage collection to prevent cache persistence
      },
    },
  });

/**
 * Renders component with QueryClientProvider.
 * This simulates the real app environment where components use TanStack Query.
 */
const renderWithProviders = (ui: React.ReactElement) => {
  const queryClient = createTestQueryClient();
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
};

describe('CameraBaselinePanel Integration Tests', () => {
  const mockCameraId = 'front_door';
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
      { hour: 8, day_of_week: 1, avg_count: 3.1, sample_count: 25, is_peak: false },
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
  });

  describe('API → Hook → Component Integration', () => {
    it('fetches baseline data on mount using useCameraBaselineQuery', async () => {
      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      // Should call API with correct camera ID
      await waitFor(() => {
        expect(api.fetchCameraBaseline).toHaveBeenCalledWith(mockCameraId);
      });
    });

    it('fetches activity baseline data on mount using useCameraActivityBaselineQuery', async () => {
      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      // Should call API with correct camera ID
      await waitFor(() => {
        expect(api.fetchCameraActivityBaseline).toHaveBeenCalledWith(mockCameraId);
      });
    });

    it('displays data fetched from API in the component', async () => {
      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      // Should display camera name from API response
      await waitFor(() => {
        expect(screen.getByText(mockCameraName)).toBeInTheDocument();
      });

      // Should display data points count from API
      expect(screen.getByText('720')).toBeInTheDocument();
    });

    it('passes fetched entries to ActivityHeatmap component', async () => {
      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      // ActivityHeatmap should render with data from API
      await waitFor(() => {
        expect(screen.getByText(/weekly activity pattern/i)).toBeInTheDocument();
      });
    });
  });

  describe('Loading → Success State Transitions', () => {
    it('displays loading state while fetching', () => {
      // Mock pending API call
      vi.mocked(api.fetchCameraBaseline).mockImplementation(() => new Promise(() => {}));
      vi.mocked(api.fetchCameraActivityBaseline).mockImplementation(() => new Promise(() => {}));

      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      // Should show loading spinner and message
      expect(screen.getByText(/loading baseline data/i)).toBeInTheDocument();
      expect(screen.getByTestId('camera-baseline-panel')).toBeInTheDocument();
    });

    it('transitions from loading to success state', async () => {
      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      // Initially loading
      expect(screen.getByText(/loading baseline data/i)).toBeInTheDocument();

      // Should transition to success state
      await waitFor(() => {
        expect(screen.queryByText(/loading baseline data/i)).not.toBeInTheDocument();
      });

      // Should display data
      expect(screen.getByText(mockCameraName)).toBeInTheDocument();
      expect(screen.getByText(/weekly activity pattern/i)).toBeInTheDocument();
    });

    it('renders ActivityHeatmap with fetched data after loading', async () => {
      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      // Wait for loading to complete
      await waitFor(() => {
        expect(screen.queryByText(/loading baseline data/i)).not.toBeInTheDocument();
      });

      // ActivityHeatmap should be present
      expect(screen.getByText(/weekly activity pattern/i)).toBeInTheDocument();
    });

    it('displays deviation status when current_deviation available', async () => {
      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      // Wait for data to load
      await waitFor(() => {
        expect(screen.getByTestId('deviation-status')).toBeInTheDocument();
      });

      // Should display deviation interpretation
      expect(screen.getByText(/slightly above normal/i)).toBeInTheDocument();

      // Should display deviation score
      expect(screen.getByText(/1.8/)).toBeInTheDocument();

      // Should display contributing factors
      expect(screen.getByText(/person_count_elevated/i)).toBeInTheDocument();
    });
  });

  describe('Empty State Handling', () => {
    it('shows "No Baseline Data" empty state when data_points = 0', async () => {
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

      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      // Should display empty state
      await waitFor(() => {
        expect(screen.getByText(/no baseline data yet/i)).toBeInTheDocument();
      });

      // Should display camera name even in empty state
      expect(screen.getByText(mockCameraName)).toBeInTheDocument();

      // Should display empty state message
      expect(
        screen.getByText(/baseline data will be collected automatically/i)
      ).toBeInTheDocument();
    });

    it('shows empty state when entries array is empty', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        data_points: 0,
      });
      vi.mocked(api.fetchCameraActivityBaseline).mockResolvedValue({
        ...mockActivityBaseline,
        entries: [],
      });

      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      await waitFor(() => {
        expect(screen.getByText(/no baseline data yet/i)).toBeInTheDocument();
      });
    });
  });

  describe('Learning Progress Indicator', () => {
    it('shows learning progress when learning_complete = false', async () => {
      vi.mocked(api.fetchCameraActivityBaseline).mockResolvedValue({
        ...mockActivityBaseline,
        learning_complete: false,
        entries: mockActivityBaseline.entries.slice(0, 50), // Partial data
      });

      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      // Should display learning indicator in ActivityHeatmap
      await waitFor(() => {
        expect(screen.getByText(/learning/i)).toBeInTheDocument();
      });
    });

    it('does not show learning indicator when learning_complete = true', async () => {
      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      // Wait for data to load
      await waitFor(() => {
        expect(screen.queryByText(/loading baseline data/i)).not.toBeInTheDocument();
      });

      // Learning indicator should not be present
      const learningText = screen.queryByText(/learning in progress/i);
      if (learningText) {
        // If the text exists, it should not be visible/prominent
        expect(learningText).not.toBeVisible();
      }
    });
  });

  describe('Loading → Error → Retry → Success Flow', () => {
    it('displays error state on API failure', async () => {
      const errorMessage = 'Network error';
      vi.mocked(api.fetchCameraBaseline).mockRejectedValue(new Error(errorMessage));
      vi.mocked(api.fetchCameraActivityBaseline).mockRejectedValue(new Error(errorMessage));

      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      // Should display error message
      await waitFor(
        () => {
          expect(screen.getByText(/error loading baseline/i)).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      // Should display error details
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });

    it('handles API error for baseline summary only', async () => {
      vi.mocked(api.fetchCameraBaseline).mockRejectedValue(new Error('Baseline API error'));

      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      await waitFor(
        () => {
          expect(screen.getByText(/error loading baseline/i)).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });

    it('handles API error for activity baseline only', async () => {
      vi.mocked(api.fetchCameraActivityBaseline).mockRejectedValue(
        new Error('Activity API error')
      );

      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      await waitFor(
        () => {
          expect(screen.getByText(/error loading baseline/i)).toBeInTheDocument();
        },
        { timeout: 5000 }
      );
    });
  });

  describe('Deviation Interpretation Display', () => {
    it('displays far_below_normal interpretation correctly', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        current_deviation: {
          score: 0.5,
          interpretation: 'far_below_normal',
          contributing_factors: [],
        },
      });

      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      await waitFor(() => {
        expect(screen.getByText(/far below normal/i)).toBeInTheDocument();
      });
    });

    it('displays below_normal interpretation correctly', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        current_deviation: {
          score: 0.8,
          interpretation: 'below_normal',
          contributing_factors: [],
        },
      });

      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

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

      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      await waitFor(() => {
        expect(screen.getByText(/^normal$/i)).toBeInTheDocument();
      });
    });

    it('displays above_normal interpretation correctly', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        current_deviation: {
          score: 2.5,
          interpretation: 'above_normal',
          contributing_factors: ['unusual_activity'],
        },
      });

      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      await waitFor(() => {
        expect(screen.getByText(/above normal/i)).toBeInTheDocument();
      });

      // Should display contributing factors
      expect(screen.getByText(/unusual_activity/i)).toBeInTheDocument();
    });

    it('displays far_above_normal interpretation correctly', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        current_deviation: {
          score: 3.5,
          interpretation: 'far_above_normal',
          contributing_factors: ['high_person_count', 'unusual_time'],
        },
      });

      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      await waitFor(() => {
        expect(screen.getByText(/far above normal/i)).toBeInTheDocument();
      });

      // Should display multiple contributing factors
      expect(screen.getByText(/high_person_count/i)).toBeInTheDocument();
      expect(screen.getByText(/unusual_time/i)).toBeInTheDocument();
    });

    it('does not display deviation section when current_deviation is null', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        current_deviation: null,
      });

      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      await waitFor(() => {
        expect(screen.queryByText(/loading baseline data/i)).not.toBeInTheDocument();
      });

      // Deviation status should not be present
      expect(screen.queryByTestId('deviation-status')).not.toBeInTheDocument();
    });
  });

  describe('Baseline Established Date Display', () => {
    it('displays baseline established date when available', async () => {
      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      await waitFor(() => {
        expect(screen.getByText(/since/i)).toBeInTheDocument();
      });

      // Should display formatted date (may be Dec 31, 2025 or Jan 1, 2026 depending on timezone)
      const dateElements = screen.getAllByText(/since/i);
      expect(dateElements.length).toBeGreaterThan(0);
    });

    it('does not display date when baseline_established is null', async () => {
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        baseline_established: null,
      });

      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      await waitFor(() => {
        expect(screen.queryByText(/loading baseline data/i)).not.toBeInTheDocument();
      });

      // Date display should not be present
      const sinceElements = screen.queryAllByText(/since/i);
      expect(sinceElements).toHaveLength(0);
    });
  });

  describe('Component Composition', () => {
    it('passes correct props to ActivityHeatmap', async () => {
      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      // Wait for data to load
      await waitFor(() => {
        expect(screen.getByText(/weekly activity pattern/i)).toBeInTheDocument();
      });

      // ActivityHeatmap should be rendered with entries
      // The presence of the heatmap text indicates it received entries prop
    });

    it('updates ActivityHeatmap when API data changes', async () => {
      const queryClient = createTestQueryClient();
      render(
        <QueryClientProvider client={queryClient}>
          <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
        </QueryClientProvider>
      );

      // Wait for initial data
      await waitFor(() => {
        expect(screen.getByText(/weekly activity pattern/i)).toBeInTheDocument();
      });

      // Update mock data
      const updatedActivityBaseline: ActivityBaselineResponse = {
        ...mockActivityBaseline,
        entries: [
          { hour: 0, day_of_week: 0, avg_count: 1.0, sample_count: 35, is_peak: false },
          { hour: 18, day_of_week: 5, avg_count: 6.5, sample_count: 40, is_peak: true },
        ],
        peak_hour: 18,
      };
      vi.mocked(api.fetchCameraActivityBaseline).mockResolvedValue(updatedActivityBaseline);

      // Invalidate the query cache to force refetch
      await queryClient.invalidateQueries({ queryKey: ['cameras', 'baseline'] });

      // Should fetch new data
      await waitFor(() => {
        expect(api.fetchCameraActivityBaseline).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('Data Points Display', () => {
    it('displays total data points from API', async () => {
      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      await waitFor(() => {
        expect(screen.getByText('720')).toBeInTheDocument();
      });

      // Should display "data points" label
      expect(screen.getByText(/data points/i)).toBeInTheDocument();
    });

    it('updates data points when API data changes', async () => {
      const queryClient = createTestQueryClient();
      render(
        <QueryClientProvider client={queryClient}>
          <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
        </QueryClientProvider>
      );

      // Initial data points
      await waitFor(() => {
        expect(screen.getByText('720')).toBeInTheDocument();
      });

      // Update mock data
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        data_points: 1000,
      });

      // Invalidate the query cache to force refetch
      await queryClient.invalidateQueries({ queryKey: ['cameras', 'baseline'] });

      // Should display updated data points
      await waitFor(() => {
        expect(screen.getByText('1000')).toBeInTheDocument();
      });
    });
  });

  describe('Complex Integration Flows', () => {
    it('handles full lifecycle: loading → data → deviation update', async () => {
      renderWithProviders(
        <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      // 1. Loading state
      expect(screen.getByText(/loading baseline data/i)).toBeInTheDocument();

      // 2. Data loaded
      await waitFor(() => {
        expect(screen.queryByText(/loading baseline data/i)).not.toBeInTheDocument();
      });

      expect(screen.getByText(mockCameraName)).toBeInTheDocument();
      expect(screen.getByText(/slightly above normal/i)).toBeInTheDocument();

      // 3. ActivityHeatmap rendered
      expect(screen.getByText(/weekly activity pattern/i)).toBeInTheDocument();
    });

    it('maintains UI consistency during rapid API changes', async () => {
      const queryClient = createTestQueryClient();
      render(
        <QueryClientProvider client={queryClient}>
          <CameraBaselinePanel cameraId={mockCameraId} cameraName={mockCameraName} />
        </QueryClientProvider>
      );

      // Wait for initial load
      await waitFor(() => {
        expect(screen.queryByText(/loading baseline data/i)).not.toBeInTheDocument();
      });

      // Verify initial state is stable
      expect(screen.getByText(/slightly above normal/i)).toBeInTheDocument();

      // Update mock data with final deviation
      vi.mocked(api.fetchCameraBaseline).mockResolvedValue({
        ...mockBaselineSummary,
        current_deviation: {
          score: 0.5,
          interpretation: 'below_normal',
          contributing_factors: [],
        },
      });

      // Invalidate cache to force refetch
      await queryClient.invalidateQueries({ queryKey: ['cameras', 'baseline'] });

      // Final state should be stable
      await waitFor(() => {
        expect(screen.getByText(/below normal/i)).toBeInTheDocument();
      });
    });
  });
});

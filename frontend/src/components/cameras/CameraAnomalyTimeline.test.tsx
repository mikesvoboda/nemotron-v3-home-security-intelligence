/**
 * Tests for CameraAnomalyTimeline component (NEM-3577)
 *
 * Tests cover:
 * - Loading state
 * - Error state
 * - Empty state
 * - Data rendering
 * - Severity indicators
 * - Timestamp formatting
 * - Props handling
 */
import { screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import CameraAnomalyTimeline from './CameraAnomalyTimeline';
import * as api from '../../services/api';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

// Mock the API module
vi.mock('../../services/api', () => ({
  fetchCameraAnomalies: vi.fn(),
}));

describe('CameraAnomalyTimeline', () => {
  const mockCameraId = 'front-door';
  const mockCameraName = 'Front Door';

  const mockAnomaliesResponse = {
    camera_id: 'front-door',
    anomalies: [
      {
        timestamp: '2026-01-03T02:30:00Z',
        detection_class: 'vehicle',
        anomaly_score: 0.95,
        expected_frequency: 0.1,
        observed_frequency: 5.0,
        reason: 'Vehicle detected at 2:30 AM when rarely seen at this hour',
      },
      {
        timestamp: '2026-01-04T14:00:00Z',
        detection_class: 'person',
        anomaly_score: 0.78,
        expected_frequency: 2.5,
        observed_frequency: 12.0,
        reason: 'Unusual number of people detected during typically quiet period',
      },
      {
        timestamp: '2026-01-02T08:00:00Z',
        detection_class: 'animal',
        anomaly_score: 0.45,
        expected_frequency: 1.0,
        observed_frequency: 3.0,
        reason: 'More animals than usual detected in the morning',
      },
    ],
    count: 3,
    period_days: 7,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchCameraAnomalies as ReturnType<typeof vi.fn>).mockResolvedValue(
      mockAnomaliesResponse
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('loading state', () => {
    it('displays loading spinner while fetching', () => {
      (api.fetchCameraAnomalies as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} />);

      expect(screen.getByTestId('camera-anomaly-timeline-loading')).toBeInTheDocument();
    });

    it('shows title during loading when showHeader is true', () => {
      (api.fetchCameraAnomalies as ReturnType<typeof vi.fn>).mockReturnValue(
        new Promise(() => {})
      );

      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} showHeader />);

      expect(screen.getByText('Baseline Anomalies')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('displays error message when fetch fails', async () => {
      const errorMessage = 'Failed to fetch camera anomalies';
      (api.fetchCameraAnomalies as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error(errorMessage)
      );

      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} />);

      await waitFor(
        () => {
          expect(screen.getByTestId('camera-anomaly-timeline-error')).toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      expect(screen.getByText('Failed to load anomaly data')).toBeInTheDocument();
    });
  });

  describe('empty state', () => {
    it('displays empty message when no anomalies', async () => {
      (api.fetchCameraAnomalies as ReturnType<typeof vi.fn>).mockResolvedValue({
        camera_id: 'front-door',
        anomalies: [],
        count: 0,
        period_days: 7,
      });

      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByTestId('camera-anomaly-timeline-empty')).toBeInTheDocument();
      });

      expect(screen.getByText('No anomalies detected')).toBeInTheDocument();
    });

    it('shows camera name in empty state when provided', async () => {
      (api.fetchCameraAnomalies as ReturnType<typeof vi.fn>).mockResolvedValue({
        camera_id: 'front-door',
        anomalies: [],
        count: 0,
        period_days: 7,
      });

      renderWithProviders(
        <CameraAnomalyTimeline cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      await waitFor(() => {
        expect(screen.getByText('Front Door is operating normally')).toBeInTheDocument();
      });
    });
  });

  describe('data rendering', () => {
    it('renders anomaly items after successful fetch', async () => {
      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByTestId('camera-anomaly-timeline')).toBeInTheDocument();
      });

      expect(screen.getByTestId('anomaly-list')).toBeInTheDocument();
      expect(screen.getByTestId('anomaly-item-0')).toBeInTheDocument();
      expect(screen.getByTestId('anomaly-item-1')).toBeInTheDocument();
      expect(screen.getByTestId('anomaly-item-2')).toBeInTheDocument();
    });

    it('displays anomaly count in header', async () => {
      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByText('3 anomalies')).toBeInTheDocument();
      });
    });

    it('displays period days in header', async () => {
      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByText('Last 7 days')).toBeInTheDocument();
      });
    });

    it('displays detection class for each anomaly', async () => {
      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByText('vehicle')).toBeInTheDocument();
        expect(screen.getByText('person')).toBeInTheDocument();
        expect(screen.getByText('animal')).toBeInTheDocument();
      });
    });

    it('displays reason for each anomaly', async () => {
      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(
          screen.getByText('Vehicle detected at 2:30 AM when rarely seen at this hour')
        ).toBeInTheDocument();
      });
    });

    it('sorts anomalies by timestamp (most recent first)', async () => {
      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByTestId('anomaly-list')).toBeInTheDocument();
      });

      // The first item should be Jan 4 (most recent)
      const firstItem = screen.getByTestId('anomaly-item-0');
      expect(firstItem).toHaveAttribute('data-anomaly-severity', 'high');

      // The last item should be Jan 2 (oldest)
      const lastItem = screen.getByTestId('anomaly-item-2');
      expect(lastItem).toHaveAttribute('data-anomaly-severity', 'low');
    });
  });

  describe('severity indicators', () => {
    it('displays critical severity for score >= 0.9', async () => {
      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} />);

      await waitFor(() => {
        // The vehicle anomaly has score 0.95
        // After sorting, the first item is the person (Jan 4), second is vehicle (Jan 3)
        // Actually, the vehicle is sorted to position 1 (Jan 3 is between Jan 4 and Jan 2)
        const vehicleItem = screen.getByTestId('anomaly-item-1');
        expect(vehicleItem).toHaveAttribute('data-anomaly-severity', 'critical');
      });
    });

    it('displays high severity for score >= 0.75 and < 0.9', async () => {
      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} />);

      await waitFor(() => {
        // The person anomaly has score 0.78
        const personItem = screen.getByTestId('anomaly-item-0');
        expect(personItem).toHaveAttribute('data-anomaly-severity', 'high');
      });
    });

    it('displays low severity for score < 0.5', async () => {
      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} />);

      await waitFor(() => {
        // The animal anomaly has score 0.45
        const animalItem = screen.getByTestId('anomaly-item-2');
        expect(animalItem).toHaveAttribute('data-anomaly-severity', 'low');
      });
    });

    it('displays severity badge with percentage', async () => {
      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByText(/Critical \(95%\)/)).toBeInTheDocument();
        expect(screen.getByText(/High \(78%\)/)).toBeInTheDocument();
        expect(screen.getByText(/Low \(45%\)/)).toBeInTheDocument();
      });
    });
  });

  describe('props handling', () => {
    it('passes days parameter to API', async () => {
      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} days={30} />);

      await waitFor(() => {
        expect(api.fetchCameraAnomalies).toHaveBeenCalledWith(mockCameraId, 30);
      });
    });

    it('hides header when showHeader is false', async () => {
      renderWithProviders(
        <CameraAnomalyTimeline cameraId={mockCameraId} showHeader={false} />
      );

      await waitFor(() => {
        expect(screen.getByTestId('camera-anomaly-timeline')).toBeInTheDocument();
      });

      expect(screen.queryByText('Baseline Anomalies')).not.toBeInTheDocument();
    });

    it('displays camera name in header when provided', async () => {
      renderWithProviders(
        <CameraAnomalyTimeline cameraId={mockCameraId} cameraName={mockCameraName} />
      );

      await waitFor(() => {
        expect(screen.getByText(mockCameraName)).toBeInTheDocument();
      });
    });

    it('applies custom className', async () => {
      renderWithProviders(
        <CameraAnomalyTimeline cameraId={mockCameraId} className="custom-class" />
      );

      await waitFor(() => {
        const card = screen.getByTestId('camera-anomaly-timeline');
        expect(card).toHaveClass('custom-class');
      });
    });
  });

  describe('legend', () => {
    it('displays severity legend', async () => {
      renderWithProviders(<CameraAnomalyTimeline cameraId={mockCameraId} />);

      await waitFor(() => {
        expect(screen.getByText('Critical (90%+)')).toBeInTheDocument();
        expect(screen.getByText('High (75-89%)')).toBeInTheDocument();
        expect(screen.getByText('Medium (50-74%)')).toBeInTheDocument();
        expect(screen.getByText('Low (<50%)')).toBeInTheDocument();
      });
    });
  });
});

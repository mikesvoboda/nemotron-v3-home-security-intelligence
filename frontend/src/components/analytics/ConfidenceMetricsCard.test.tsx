import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ConfidenceMetricsCard from './ConfidenceMetricsCard';
import * as api from '../../services/api';

import type { DetectionStatsResponse } from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../../services/api')>();
  return {
    ...actual,
    fetchDetectionStats: vi.fn(),
  };
});

// Mock Tremor components
vi.mock('@tremor/react', () => ({
  Card: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => (
    <div data-testid={props['data-testid'] as string}>{children}</div>
  ),
  Title: ({ children }: React.PropsWithChildren) => <h3>{children}</h3>,
  Text: ({ children, className }: React.PropsWithChildren<{ className?: string }>) => (
    <span className={className}>{children}</span>
  ),
  ProgressBar: (props: Record<string, unknown>) => (
    <div data-testid={props['data-testid'] as string}>ProgressBar</div>
  ),
}));

describe('ConfidenceMetricsCard', () => {
  const mockFetchDetectionStats = vi.mocked(api.fetchDetectionStats);

  const mockHighConfidenceStats: DetectionStatsResponse = {
    total_detections: 1000,
    detections_by_class: { person: 500, car: 300, truck: 200 },
    average_confidence: 0.92,
  };

  const mockMediumConfidenceStats: DetectionStatsResponse = {
    ...mockHighConfidenceStats,
    average_confidence: 0.75,
  };

  const mockLowConfidenceStats: DetectionStatsResponse = {
    ...mockHighConfidenceStats,
    average_confidence: 0.55,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockFetchDetectionStats.mockResolvedValue(mockHighConfidenceStats);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders the card with data', async () => {
      render(<ConfidenceMetricsCard />);
      await waitFor(() => {
        expect(screen.getByTestId('confidence-metrics-card')).toBeInTheDocument();
      });
    });

    it('displays confidence value', async () => {
      render(<ConfidenceMetricsCard />);
      await waitFor(() => {
        expect(screen.getByTestId('confidence-value')).toHaveTextContent('92.0%');
      });
    });

    it('displays total detections', async () => {
      render(<ConfidenceMetricsCard />);
      await waitFor(() => {
        expect(screen.getByTestId('confidence-total-detections')).toHaveTextContent('1,000');
      });
    });
  });

  describe('confidence levels', () => {
    it('displays high confidence level for >= 85%', async () => {
      render(<ConfidenceMetricsCard />);
      await waitFor(() => {
        expect(screen.getByTestId('confidence-level-label')).toHaveTextContent('High Confidence');
      });
    });

    it('displays medium confidence level for 70-84%', async () => {
      mockFetchDetectionStats.mockResolvedValue(mockMediumConfidenceStats);
      render(<ConfidenceMetricsCard />);
      await waitFor(() => {
        expect(screen.getByTestId('confidence-level-label')).toHaveTextContent('Medium Confidence');
      });
    });

    it('displays low confidence level for < 70%', async () => {
      mockFetchDetectionStats.mockResolvedValue(mockLowConfidenceStats);
      render(<ConfidenceMetricsCard />);
      await waitFor(() => {
        expect(screen.getByTestId('confidence-level-label')).toHaveTextContent('Low Confidence');
      });
    });
  });

  describe('loading state', () => {
    it('shows loading spinner initially', () => {
      mockFetchDetectionStats.mockReturnValue(new Promise(() => {}));
      render(<ConfidenceMetricsCard />);
      expect(screen.getByTestId('confidence-metrics-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error message when fetch fails', async () => {
      mockFetchDetectionStats.mockRejectedValue(new Error('Network error'));
      render(<ConfidenceMetricsCard />);
      await waitFor(() => {
        expect(screen.getByTestId('confidence-metrics-error')).toBeInTheDocument();
      });
    });
  });

  describe('empty state', () => {
    it('shows empty state when no detections', async () => {
      mockFetchDetectionStats.mockResolvedValue({
        ...mockHighConfidenceStats,
        total_detections: 0,
        average_confidence: null,
      });
      render(<ConfidenceMetricsCard />);
      await waitFor(() => {
        expect(screen.getByTestId('confidence-metrics-empty')).toBeInTheDocument();
      });
    });
  });

  describe('API integration', () => {
    it('calls fetchDetectionStats on mount', async () => {
      render(<ConfidenceMetricsCard />);
      await waitFor(() => {
        expect(mockFetchDetectionStats).toHaveBeenCalledTimes(1);
      });
    });

    it('passes cameraId to fetchDetectionStats when provided', async () => {
      render(<ConfidenceMetricsCard cameraId="camera-123" />);
      await waitFor(() => {
        expect(mockFetchDetectionStats).toHaveBeenCalledWith({ camera_id: 'camera-123' });
      });
    });

    it('sets up refresh interval when provided', async () => {
      const setIntervalSpy = vi.spyOn(globalThis, 'setInterval');
      render(<ConfidenceMetricsCard refreshInterval={5000} />);
      await waitFor(() => {
        expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 5000);
      });
      setIntervalSpy.mockRestore();
    });
  });
});

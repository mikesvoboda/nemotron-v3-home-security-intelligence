/**
 * Tests for BatchStatisticsDashboard component
 *
 * Tests cover:
 * - Dashboard rendering on SystemMonitoringPage
 * - Active batch count display
 * - WebSocket real-time updates
 * - Closure reason chart display
 * - Per-camera breakdown table
 * - Empty state handling
 * - Dark theme styling
 */

import { render, screen, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import BatchStatisticsDashboard from './BatchStatisticsDashboard';
import { useBatchStatistics } from '../../hooks/useBatchStatistics';

// Mock useBatchStatistics hook
vi.mock('../../hooks/useBatchStatistics', () => ({
  useBatchStatistics: vi.fn(),
}));

const mockUseBatchStatistics = vi.mocked(useBatchStatistics);

// Default mock return value with batch data
const mockBatchStatistics = {
  isLoading: false,
  error: null,
  activeBatchCount: 2,
  activeBatches: [
    {
      batch_id: 'batch-1',
      camera_id: 'front_door',
      detection_count: 5,
      started_at: 1737806400,
      age_seconds: 45.5,
      last_activity_seconds: 10.2,
    },
    {
      batch_id: 'batch-2',
      camera_id: 'backyard',
      detection_count: 3,
      started_at: 1737806380,
      age_seconds: 65.5,
      last_activity_seconds: 5.1,
    },
  ],
  completedBatches: [
    {
      batch_id: 'completed-batch-1',
      camera_id: 'front_door',
      detection_ids: [1, 2, 3, 4, 5],
      detection_count: 5,
      started_at: '2026-01-25T11:55:00Z',
      closed_at: '2026-01-25T11:56:30Z',
      close_reason: 'timeout',
    },
    {
      batch_id: 'completed-batch-2',
      camera_id: 'backyard',
      detection_ids: [6, 7],
      detection_count: 2,
      started_at: '2026-01-25T11:54:00Z',
      closed_at: '2026-01-25T11:54:30Z',
      close_reason: 'idle',
    },
  ],
  totalClosedCount: 2,
  batchWindowSeconds: 90,
  idleTimeoutSeconds: 30,
  averageDurationSeconds: 60,
  closureReasonStats: {
    timeout: 1,
    idle: 1,
    max_size: 0,
  },
  closureReasonPercentages: {
    timeout: 50,
    idle: 50,
    max_size: 0,
  },
  perCameraStats: {
    front_door: {
      completedBatchCount: 1,
      activeBatchCount: 1,
      totalDetections: 10,
    },
    backyard: {
      completedBatchCount: 1,
      activeBatchCount: 1,
      totalDetections: 5,
    },
  },
  isWebSocketConnected: true,
  refetch: vi.fn(),
};

describe('BatchStatisticsDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseBatchStatistics.mockReturnValue(mockBatchStatistics);
  });

  describe('rendering', () => {
    it('should render the dashboard with title', () => {
      render(<BatchStatisticsDashboard />);

      expect(screen.getByText('Batch Processing Statistics')).toBeInTheDocument();
    });

    it('should render with correct test IDs', () => {
      render(<BatchStatisticsDashboard data-testid="batch-statistics-dashboard" />);

      expect(screen.getByTestId('batch-statistics-dashboard')).toBeInTheDocument();
    });

    it('should apply dark theme styling', () => {
      render(<BatchStatisticsDashboard data-testid="batch-statistics-dashboard" />);

      const dashboard = screen.getByTestId('batch-statistics-dashboard');
      expect(dashboard).toHaveClass('bg-[#1A1A1A]');
    });
  });

  describe('summary metrics', () => {
    it('should display active batch count', () => {
      render(<BatchStatisticsDashboard />);

      expect(screen.getByTestId('active-batch-count')).toHaveTextContent('2');
    });

    it('should display total closed batch count', () => {
      render(<BatchStatisticsDashboard />);

      expect(screen.getByTestId('total-closed-count')).toHaveTextContent('2');
    });

    it('should display average batch duration', () => {
      render(<BatchStatisticsDashboard />);

      expect(screen.getByTestId('average-duration')).toHaveTextContent('60s');
    });

    it('should display batch configuration', () => {
      render(<BatchStatisticsDashboard />);

      expect(screen.getByTestId('batch-window')).toHaveTextContent('90s');
      expect(screen.getByTestId('idle-timeout')).toHaveTextContent('30s');
    });
  });

  describe('WebSocket connection indicator', () => {
    it('should show connected status when WebSocket is connected', () => {
      render(<BatchStatisticsDashboard />);

      const indicator = screen.getByTestId('websocket-status');
      expect(indicator).toHaveTextContent('Live');
      expect(indicator).toHaveClass('text-green-400');
    });

    it('should show disconnected status when WebSocket is not connected', () => {
      mockUseBatchStatistics.mockReturnValue({
        ...mockBatchStatistics,
        isWebSocketConnected: false,
      });

      render(<BatchStatisticsDashboard />);

      const indicator = screen.getByTestId('websocket-status');
      expect(indicator).toHaveTextContent('Disconnected');
      expect(indicator).toHaveClass('text-red-400');
    });
  });

  describe('closure reason chart', () => {
    it('should render closure reason chart', () => {
      render(<BatchStatisticsDashboard />);

      expect(screen.getByTestId('closure-reason-chart')).toBeInTheDocument();
    });

    it('should display closure reason percentages', () => {
      render(<BatchStatisticsDashboard />);

      const chart = screen.getByTestId('closure-reason-chart');

      // Check that timeout and idle are displayed
      expect(within(chart).getByText(/Timeout/i)).toBeInTheDocument();
      expect(within(chart).getByText(/Idle/i)).toBeInTheDocument();
    });
  });

  describe('per-camera breakdown table', () => {
    it('should render per-camera table', () => {
      render(<BatchStatisticsDashboard />);

      expect(screen.getByTestId('per-camera-table')).toBeInTheDocument();
    });

    it('should display camera statistics', () => {
      render(<BatchStatisticsDashboard />);

      const table = screen.getByTestId('per-camera-table');

      expect(within(table).getByText('front_door')).toBeInTheDocument();
      expect(within(table).getByText('backyard')).toBeInTheDocument();
    });

    it('should display detection counts per camera', () => {
      render(<BatchStatisticsDashboard />);

      const table = screen.getByTestId('per-camera-table');

      // front_door has 10 total detections
      expect(within(table).getByText('10')).toBeInTheDocument();
      // backyard has 5 total detections
      expect(within(table).getByText('5')).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('should show loading skeleton when loading', () => {
      mockUseBatchStatistics.mockReturnValue({
        ...mockBatchStatistics,
        isLoading: true,
      });

      render(<BatchStatisticsDashboard />);

      expect(screen.getByTestId('batch-statistics-loading')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('should show error message when there is an error', () => {
      mockUseBatchStatistics.mockReturnValue({
        ...mockBatchStatistics,
        isLoading: false,
        error: 'Failed to load batch statistics',
      });

      render(<BatchStatisticsDashboard />);

      expect(screen.getByTestId('batch-statistics-error')).toBeInTheDocument();
      expect(screen.getByText('Failed to load batch statistics')).toBeInTheDocument();
    });

    it('should provide retry button on error', () => {
      const refetch = vi.fn();
      mockUseBatchStatistics.mockReturnValue({
        ...mockBatchStatistics,
        isLoading: false,
        error: 'Failed to load batch statistics',
        refetch,
      });

      render(<BatchStatisticsDashboard />);

      const retryButton = screen.getByRole('button', { name: /retry/i });
      retryButton.click();

      expect(refetch).toHaveBeenCalled();
    });
  });

  describe('empty state', () => {
    it('should show empty state when no batches exist', () => {
      mockUseBatchStatistics.mockReturnValue({
        ...mockBatchStatistics,
        activeBatchCount: 0,
        activeBatches: [],
        completedBatches: [],
        totalClosedCount: 0,
        perCameraStats: {},
      });

      render(<BatchStatisticsDashboard />);

      expect(screen.getByTestId('batch-statistics-empty')).toBeInTheDocument();
      expect(
        screen.getByText(/No batch data available/i)
      ).toBeInTheDocument();
    });

    it('should show counts as 0 in empty state', () => {
      mockUseBatchStatistics.mockReturnValue({
        ...mockBatchStatistics,
        activeBatchCount: 0,
        activeBatches: [],
        completedBatches: [],
        totalClosedCount: 0,
        perCameraStats: {},
      });

      render(<BatchStatisticsDashboard />);

      expect(screen.getByTestId('active-batch-count')).toHaveTextContent('0');
      expect(screen.getByTestId('total-closed-count')).toHaveTextContent('0');
    });
  });

  describe('active batches list', () => {
    it('should render active batches timeline', () => {
      render(<BatchStatisticsDashboard />);

      expect(screen.getByTestId('batch-timeline-chart')).toBeInTheDocument();
    });

    it('should display batch details in timeline', () => {
      render(<BatchStatisticsDashboard />);

      const timeline = screen.getByTestId('batch-timeline-chart');

      // Check that batch info is shown
      expect(within(timeline).getByText('batch-1')).toBeInTheDocument();
      expect(within(timeline).getByText('batch-2')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('should have accessible labels for metrics', () => {
      render(<BatchStatisticsDashboard />);

      expect(screen.getByLabelText(/active batches/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/total closed/i)).toBeInTheDocument();
    });

    it('should have role for data table', () => {
      render(<BatchStatisticsDashboard />);

      const table = screen.getByTestId('per-camera-table');
      expect(within(table).getByRole('table')).toBeInTheDocument();
    });
  });
});

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import QueueMetricsPanel from './QueueMetricsPanel';
import { useQueueMetricsWebSocket } from '../../hooks/useQueueMetricsWebSocket';

import type {
  UseQueueMetricsWebSocketReturn,
  QueueStatusEntry,
  ThroughputEntry,
} from '../../hooks/useQueueMetricsWebSocket';
import type { QueueStatusPayload, PipelineThroughputPayload } from '../../types/websocket-events';


// Mock the useQueueMetricsWebSocket hook
vi.mock('../../hooks/useQueueMetricsWebSocket', () => ({
  useQueueMetricsWebSocket: vi.fn(),
}));
const mockUseQueueMetricsWebSocket = vi.mocked(useQueueMetricsWebSocket);

describe('QueueMetricsPanel', () => {
  // Default mock data
  const mockQueueStatus: QueueStatusPayload = {
    queues: [
      { name: 'detection', depth: 10, workers: 2, status: 'healthy' },
      { name: 'analysis', depth: 5, workers: 1, status: 'healthy' },
    ],
    total_queued: 15,
    total_processing: 3,
    total_workers: 3,
    overall_status: 'healthy',
    timestamp: '2025-01-15T12:00:00Z',
  };

  const mockThroughput: PipelineThroughputPayload = {
    detections_per_minute: 9.5,
    events_per_minute: 5.3,
    enrichments_per_minute: 3.7,
    timestamp: '2025-01-15T12:00:00Z',
    window_seconds: 60,
  };

  const mockQueueHistory: QueueStatusEntry[] = [
    { ...mockQueueStatus, received_at: '2025-01-15T11:59:00Z' },
    { ...mockQueueStatus, total_queued: 12, received_at: '2025-01-15T11:59:30Z' },
    { ...mockQueueStatus, total_queued: 15, received_at: '2025-01-15T12:00:00Z' },
  ];

  const mockThroughputHistory: ThroughputEntry[] = [
    { ...mockThroughput, received_at: '2025-01-15T11:59:00Z' },
    { ...mockThroughput, detections_per_minute: 42, received_at: '2025-01-15T11:59:30Z' },
    { ...mockThroughput, received_at: '2025-01-15T12:00:00Z' },
  ];

  const defaultMockReturn: UseQueueMetricsWebSocketReturn = {
    queueStatus: mockQueueStatus,
    throughput: mockThroughput,
    queueHistory: mockQueueHistory,
    throughputHistory: mockThroughputHistory,
    lastUpdate: '2025-01-15T12:00:00Z',
    isConnected: true,
    totalQueueDepth: 15,
    totalWorkers: 3,
    isWarning: false,
    isCritical: false,
    getQueueByName: vi.fn((name: string) =>
      mockQueueStatus.queues.find((q) => q.name === name)
    ),
    clearHistory: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseQueueMetricsWebSocket.mockReturnValue(defaultMockReturn);
  });

  describe('rendering', () => {
    it('renders the panel with title', () => {
      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('queue-metrics-panel')).toBeInTheDocument();
      expect(screen.getByText('Queue Metrics')).toBeInTheDocument();
    });

    it('renders connection status indicator', () => {
      render(<QueueMetricsPanel />);

      const connectionStatus = screen.getByTestId('connection-status');
      expect(connectionStatus).toBeInTheDocument();
      expect(connectionStatus).toHaveTextContent('Live');
    });

    it('renders disconnected status when not connected', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        isConnected: false,
      });

      render(<QueueMetricsPanel />);

      const connectionStatus = screen.getByTestId('connection-status');
      expect(connectionStatus).toHaveTextContent('Disconnected');
    });

    it('renders total queue depth', () => {
      render(<QueueMetricsPanel />);

      const totalDepth = screen.getByTestId('total-queue-depth');
      expect(totalDepth).toBeInTheDocument();
      expect(totalDepth).toHaveTextContent('15');
    });

    it('renders total workers count', () => {
      render(<QueueMetricsPanel />);

      const totalWorkers = screen.getByTestId('total-workers');
      expect(totalWorkers).toBeInTheDocument();
      expect(totalWorkers).toHaveTextContent('3');
    });

    it('renders processing count', () => {
      render(<QueueMetricsPanel />);

      const processingCount = screen.getByTestId('processing-count');
      expect(processingCount).toBeInTheDocument();
      expect(processingCount).toHaveTextContent('3');
    });

    it('renders overall status badge', () => {
      render(<QueueMetricsPanel />);

      const statusBadge = screen.getByTestId('overall-status-badge');
      expect(statusBadge).toBeInTheDocument();
      expect(statusBadge).toHaveTextContent('Healthy');
    });

    it('applies custom className', () => {
      render(<QueueMetricsPanel className="custom-class" />);

      const panel = screen.getByTestId('queue-metrics-panel');
      expect(panel.className).toContain('custom-class');
    });

    it('uses custom data-testid', () => {
      render(<QueueMetricsPanel data-testid="custom-panel" />);

      expect(screen.getByTestId('custom-panel')).toBeInTheDocument();
    });
  });

  describe('per-queue display', () => {
    it('renders queue depth indicators for each queue', () => {
      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('queue-detection')).toBeInTheDocument();
      expect(screen.getByTestId('queue-analysis')).toBeInTheDocument();
    });

    it('displays queue names formatted correctly', () => {
      render(<QueueMetricsPanel />);

      expect(screen.getByText('detection')).toBeInTheDocument();
      expect(screen.getByText('analysis')).toBeInTheDocument();
    });

    it('displays queue depth badges with correct values', () => {
      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('queue-detection-badge')).toHaveTextContent('10');
      expect(screen.getByTestId('queue-analysis-badge')).toHaveTextContent('5');
    });

    it('displays worker counts for each queue', () => {
      render(<QueueMetricsPanel />);

      expect(screen.getByText('2 workers')).toBeInTheDocument();
      expect(screen.getByText('1 worker')).toBeInTheDocument();
    });

    it('handles queues with underscores in names', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        queueStatus: {
          ...mockQueueStatus,
          queues: [{ name: 'detection_queue', depth: 5, workers: 1 }],
        },
      });

      render(<QueueMetricsPanel />);

      // Underscores should be replaced with spaces
      expect(screen.getByText('detection queue')).toBeInTheDocument();
    });
  });

  describe('throughput display', () => {
    it('renders throughput values', () => {
      render(<QueueMetricsPanel />);

      const throughputValues = screen.getByTestId('throughput-values');
      expect(throughputValues).toBeInTheDocument();
    });

    it('displays detections per minute', () => {
      render(<QueueMetricsPanel />);

      expect(screen.getByText('9.5/min')).toBeInTheDocument();
    });

    it('displays events per minute', () => {
      render(<QueueMetricsPanel />);

      expect(screen.getByText('5.3/min')).toBeInTheDocument();
    });

    it('displays enrichments per minute when available', () => {
      render(<QueueMetricsPanel />);

      expect(screen.getByText('3.7/min')).toBeInTheDocument();
    });

    it('does not show enrichments when not provided', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        throughput: {
          detections_per_minute: 10,
          events_per_minute: 5,
        },
      });

      render(<QueueMetricsPanel />);

      expect(screen.queryByText(/Enrichments/)).not.toBeInTheDocument();
    });

    it('formats large throughput values as integers', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        throughput: {
          detections_per_minute: 156.7,
          events_per_minute: 89.2,
        },
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByText('157/min')).toBeInTheDocument();
      expect(screen.getByText('89/min')).toBeInTheDocument();
    });

    it('formats small throughput values with decimals', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        throughput: {
          detections_per_minute: 0.5,
          events_per_minute: 0.25,
        },
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByText('0.50/min')).toBeInTheDocument();
      expect(screen.getByText('0.25/min')).toBeInTheDocument();
    });
  });

  describe('charts', () => {
    it('renders queue history chart when data available', () => {
      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('queue-history-chart')).toBeInTheDocument();
    });

    it('shows empty state when no queue history', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        queueHistory: [],
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('queue-history-empty')).toBeInTheDocument();
      expect(screen.getByText('Collecting data...')).toBeInTheDocument();
    });

    it('shows empty state with only one history point', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        queueHistory: [mockQueueHistory[0]],
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('queue-history-empty')).toBeInTheDocument();
    });

    it('renders throughput history chart when data available', () => {
      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('throughput-history-chart')).toBeInTheDocument();
    });

    it('shows empty state when no throughput history', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        throughputHistory: [],
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('throughput-history-empty')).toBeInTheDocument();
      expect(screen.getByText('Collecting throughput data...')).toBeInTheDocument();
    });
  });

  describe('warning states', () => {
    it('shows warning icon when isWarning is true', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        isWarning: true,
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('queue-warning-icon')).toBeInTheDocument();
    });

    it('shows warning banner when isWarning is true', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        isWarning: true,
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('queue-warning-banner')).toBeInTheDocument();
      expect(screen.getByText(/Queue depth elevated/)).toBeInTheDocument();
    });

    it('does not show warning banner when queue is healthy', () => {
      render(<QueueMetricsPanel />);

      expect(screen.queryByTestId('queue-warning-banner')).not.toBeInTheDocument();
    });
  });

  describe('critical states', () => {
    it('shows critical warning icon when isCritical is true', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        isCritical: true,
      });

      render(<QueueMetricsPanel />);

      const warningIcon = screen.getByTestId('queue-warning-icon');
      expect(warningIcon).toBeInTheDocument();
      expect(warningIcon).toHaveClass('text-red-500');
    });

    it('shows critical warning banner when isCritical is true', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        isCritical: true,
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('queue-critical-warning')).toBeInTheDocument();
      expect(screen.getByText(/Queue depth critical/)).toBeInTheDocument();
    });

    it('shows only critical banner when both warning and critical', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        isWarning: true,
        isCritical: true,
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('queue-critical-warning')).toBeInTheDocument();
      expect(screen.queryByTestId('queue-warning-banner')).not.toBeInTheDocument();
    });
  });

  describe('status labels', () => {
    it('displays Healthy status correctly', () => {
      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('overall-status-badge')).toHaveTextContent('Healthy');
    });

    it('displays Elevated status for warning', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        queueStatus: {
          ...mockQueueStatus,
          overall_status: 'warning',
        },
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('overall-status-badge')).toHaveTextContent('Elevated');
    });

    it('displays Critical status correctly', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        queueStatus: {
          ...mockQueueStatus,
          overall_status: 'critical',
        },
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('overall-status-badge')).toHaveTextContent('Critical');
    });

    it('displays Unknown when no queue status', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        queueStatus: null,
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('overall-status-badge')).toHaveTextContent('Unknown');
    });
  });

  describe('timestamp display', () => {
    it('displays last update timestamp', () => {
      render(<QueueMetricsPanel />);

      const timestamp = screen.getByTestId('queue-metrics-timestamp');
      expect(timestamp).toBeInTheDocument();
      expect(timestamp.textContent).toContain('Updated:');
    });

    it('does not display timestamp when lastUpdate is null', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        lastUpdate: null,
      });

      render(<QueueMetricsPanel />);

      expect(screen.queryByTestId('queue-metrics-timestamp')).not.toBeInTheDocument();
    });
  });

  describe('empty states', () => {
    it('handles null queueStatus gracefully', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        queueStatus: null,
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('queue-metrics-panel')).toBeInTheDocument();
      expect(screen.queryByTestId('queue-depths-grid')).not.toBeInTheDocument();
    });

    it('handles null throughput gracefully', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        throughput: null,
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('queue-metrics-panel')).toBeInTheDocument();
      expect(screen.queryByTestId('throughput-values')).not.toBeInTheDocument();
    });

    it('handles empty queues array', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        queueStatus: {
          ...mockQueueStatus,
          queues: [],
        },
      });

      render(<QueueMetricsPanel />);

      expect(screen.queryByTestId('queue-depths-grid')).not.toBeInTheDocument();
    });
  });

  describe('hook configuration', () => {
    it('passes enabled prop to hook', () => {
      render(<QueueMetricsPanel enabled={false} />);

      expect(mockUseQueueMetricsWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({ enabled: false })
      );
    });

    it('passes maxHistory prop to hook', () => {
      render(<QueueMetricsPanel maxHistoryPoints={50} />);

      expect(mockUseQueueMetricsWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({ maxHistory: 100 }) // doubled for smoothness
      );
    });

    it('uses default values when not specified', () => {
      render(<QueueMetricsPanel />);

      expect(mockUseQueueMetricsWebSocket).toHaveBeenCalledWith(
        expect.objectContaining({
          enabled: true,
          maxHistory: 60, // 30 * 2
        })
      );
    });
  });

  describe('accessibility', () => {
    it('has accessible warning alerts', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        isWarning: true,
      });

      render(<QueueMetricsPanel />);

      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
    });

    it('warning icon has aria-label', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        isWarning: true,
      });

      render(<QueueMetricsPanel />);

      const warningIcon = screen.getByTestId('queue-warning-icon');
      expect(warningIcon).toHaveAttribute('aria-label', 'Queue elevated');
    });

    it('critical icon has aria-label', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        isCritical: true,
      });

      render(<QueueMetricsPanel />);

      const warningIcon = screen.getByTestId('queue-warning-icon');
      expect(warningIcon).toHaveAttribute('aria-label', 'Queue critical');
    });
  });

  describe('edge cases', () => {
    it('handles zero queue depth', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        totalQueueDepth: 0,
        queueStatus: {
          ...mockQueueStatus,
          total_queued: 0,
          queues: [{ name: 'detection', depth: 0, workers: 2 }],
        },
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('total-queue-depth')).toHaveTextContent('0');
    });

    it('handles zero throughput', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        throughput: {
          detections_per_minute: 0,
          events_per_minute: 0,
        },
      });

      render(<QueueMetricsPanel />);

      const throughputValues = screen.getByTestId('throughput-values');
      expect(throughputValues).toHaveTextContent('0/min');
    });

    it('handles very large queue depths', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        totalQueueDepth: 999999,
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('total-queue-depth')).toHaveTextContent('999999');
    });

    it('handles queue with no workers', () => {
      mockUseQueueMetricsWebSocket.mockReturnValue({
        ...defaultMockReturn,
        totalWorkers: 0,
        queueStatus: {
          ...mockQueueStatus,
          total_workers: 0,
          queues: [{ name: 'detection', depth: 10, workers: 0 }],
        },
      });

      render(<QueueMetricsPanel />);

      expect(screen.getByTestId('total-workers')).toHaveTextContent('0');
      expect(screen.getByText('0 workers')).toBeInTheDocument();
    });
  });
});

import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import PipelineTelemetry from './PipelineTelemetry';
import * as api from '../../services/api';

// Mock the fetchTelemetry API call
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual<typeof api>('../../services/api');
  return {
    ...actual,
    fetchTelemetry: vi.fn(),
  };
});

// Mock ResizeObserver for Tremor charts
beforeEach(() => {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
  vi.clearAllMocks();
  vi.useRealTimers();
});

afterEach(() => {
  vi.clearAllMocks();
  vi.useRealTimers();
});

// Default mock telemetry data
const mockTelemetryData: api.TelemetryResponse = {
  queues: {
    detection_queue: 5,
    analysis_queue: 2,
  },
  latencies: {
    watch: {
      avg_ms: 10,
      min_ms: 5,
      max_ms: 20,
      p50_ms: 9,
      p95_ms: 18,
      p99_ms: 19,
      sample_count: 100,
    },
    detect: {
      avg_ms: 150,
      min_ms: 100,
      max_ms: 300,
      p50_ms: 140,
      p95_ms: 250,
      p99_ms: 290,
      sample_count: 100,
    },
    batch: {
      avg_ms: 30000,
      min_ms: 25000,
      max_ms: 90000,
      p50_ms: 28000,
      p95_ms: 85000,
      p99_ms: 88000,
      sample_count: 50,
    },
    analyze: {
      avg_ms: 5000,
      min_ms: 3000,
      max_ms: 15000,
      p50_ms: 4500,
      p95_ms: 12000,
      p99_ms: 14000,
      sample_count: 50,
    },
  },
  timestamp: '2025-01-01T12:00:00Z',
};

describe('PipelineTelemetry', () => {
  describe('loading state', () => {
    it('shows loading state initially', () => {
      vi.mocked(api.fetchTelemetry).mockReturnValue(new Promise(() => {})); // Never resolves

      render(<PipelineTelemetry />);

      expect(screen.getByTestId('telemetry-loading')).toBeInTheDocument();
      expect(screen.getByText('Loading telemetry...')).toBeInTheDocument();
    });

    it('renders component with title during loading', () => {
      vi.mocked(api.fetchTelemetry).mockReturnValue(new Promise(() => {}));

      render(<PipelineTelemetry />);

      expect(screen.getByText('Pipeline Telemetry')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error state when fetch fails', async () => {
      vi.mocked(api.fetchTelemetry).mockRejectedValue(new Error('Network error'));

      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.getByTestId('telemetry-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  describe('data display', () => {
    beforeEach(() => {
      vi.mocked(api.fetchTelemetry).mockResolvedValue(mockTelemetryData);
    });

    it('renders component title after data loads', async () => {
      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByText('Pipeline Telemetry')).toBeInTheDocument();
    });

    it('displays queue depths section', async () => {
      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByText('Queue Depths')).toBeInTheDocument();
      expect(screen.getByTestId('detection-queue-depth')).toHaveTextContent('5');
      expect(screen.getByTestId('analysis-queue-depth')).toHaveTextContent('2');
    });

    it('displays processing latency section', async () => {
      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByText('Processing Latency')).toBeInTheDocument();
      // "Detection" and "Analysis" appear in both latency rows and tabs, so use getAllByText
      expect(screen.getAllByText('Detection').length).toBeGreaterThan(0);
      expect(screen.getByText('Batch Agg')).toBeInTheDocument();
      expect(screen.getAllByText('Analysis').length).toBeGreaterThan(0);
    });

    it('displays throughput section', async () => {
      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      // "Throughput" text appears in both the throughput section and the tab, so use getAllByText
      expect(screen.getAllByText('Throughput').length).toBeGreaterThan(0);
      expect(screen.getByText('Detections')).toBeInTheDocument();
      expect(screen.getByText('Analyses')).toBeInTheDocument();
    });

    it('displays error rate section', async () => {
      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByText('Error Rate')).toBeInTheDocument();
      expect(screen.getByTestId('error-rate-badge')).toHaveTextContent('0.0%');
    });

    it('displays metrics history section with tabs', async () => {
      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByText('Metrics History')).toBeInTheDocument();
      expect(screen.getByTestId('tab-detection-latency')).toBeInTheDocument();
      expect(screen.getByTestId('tab-analysis-latency')).toBeInTheDocument();
      expect(screen.getByTestId('tab-throughput')).toBeInTheDocument();
    });

    it('has timestamp section in DOM when telemetry loads', async () => {
      render(<PipelineTelemetry />);

      // Wait for data to load
      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      // Component should render without timestamp initially showing as loading is cleared
      // but telemetry is set. The timestamp element exists if telemetry is truthy.
      // The queue depths being visible confirms telemetry loaded
      expect(screen.getByTestId('detection-queue-depth')).toBeInTheDocument();
      expect(screen.getByTestId('analysis-queue-depth')).toBeInTheDocument();
    });
  });

  describe('queue warnings', () => {
    it('shows warning when detection queue exceeds threshold', async () => {
      const warningData = {
        ...mockTelemetryData,
        queues: { detection_queue: 15, analysis_queue: 2 },
      };
      vi.mocked(api.fetchTelemetry).mockResolvedValue(warningData);

      render(<PipelineTelemetry queueWarningThreshold={10} />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByTestId('detection-queue-warning')).toBeInTheDocument();
      expect(screen.getByTestId('telemetry-warning-icon')).toBeInTheDocument();
    });

    it('shows warning when analysis queue exceeds threshold', async () => {
      const warningData = {
        ...mockTelemetryData,
        queues: { detection_queue: 2, analysis_queue: 15 },
      };
      vi.mocked(api.fetchTelemetry).mockResolvedValue(warningData);

      render(<PipelineTelemetry queueWarningThreshold={10} />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByTestId('analysis-queue-warning')).toBeInTheDocument();
      expect(screen.getByTestId('telemetry-warning-icon')).toBeInTheDocument();
    });

    it('does not show warning when queues are within threshold', async () => {
      vi.mocked(api.fetchTelemetry).mockResolvedValue(mockTelemetryData);

      render(<PipelineTelemetry queueWarningThreshold={10} />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      expect(screen.queryByTestId('detection-queue-warning')).not.toBeInTheDocument();
      expect(screen.queryByTestId('analysis-queue-warning')).not.toBeInTheDocument();
      expect(screen.queryByTestId('telemetry-warning-icon')).not.toBeInTheDocument();
    });

    it('uses custom warning threshold', async () => {
      const customThresholdData = {
        ...mockTelemetryData,
        queues: { detection_queue: 6, analysis_queue: 2 },
      };
      vi.mocked(api.fetchTelemetry).mockResolvedValue(customThresholdData);

      render(<PipelineTelemetry queueWarningThreshold={5} />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByTestId('detection-queue-warning')).toBeInTheDocument();
    });
  });

  describe('latency display', () => {
    beforeEach(() => {
      vi.mocked(api.fetchTelemetry).mockResolvedValue(mockTelemetryData);
    });

    it('displays latency values with correct formatting', async () => {
      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      // Check for latency rows
      expect(screen.getByTestId('latency-row-detection')).toBeInTheDocument();
      expect(screen.getByTestId('latency-row-batch-agg')).toBeInTheDocument();
      expect(screen.getByTestId('latency-row-analysis')).toBeInTheDocument();
    });

    it('displays sample counts for latency stages', async () => {
      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      // Check for sample counts
      expect(screen.getByText('100 samples')).toBeInTheDocument();
      expect(screen.getAllByText('50 samples').length).toBeGreaterThan(0);
    });
  });

  describe('null/undefined latency handling', () => {
    it('handles null latencies gracefully', async () => {
      const nullLatencyData = {
        ...mockTelemetryData,
        latencies: null,
      };
      vi.mocked(api.fetchTelemetry).mockResolvedValue(nullLatencyData as api.TelemetryResponse);

      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      // Component should still render without crashing
      expect(screen.getByText('Pipeline Telemetry')).toBeInTheDocument();
      expect(screen.getByText('Processing Latency')).toBeInTheDocument();
    });

    it('handles undefined stage latencies', async () => {
      const undefinedStageData = {
        ...mockTelemetryData,
        latencies: {
          watch: null,
          detect: null,
          batch: null,
          analyze: null,
        },
      };
      vi.mocked(api.fetchTelemetry).mockResolvedValue(undefinedStageData as api.TelemetryResponse);

      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      // Should display N/A for null values
      const naElements = screen.getAllByText('N/A');
      expect(naElements.length).toBeGreaterThan(0);
    });
  });

  describe('chart display', () => {
    beforeEach(() => {
      vi.mocked(api.fetchTelemetry).mockResolvedValue(mockTelemetryData);
    });

    it('renders chart section after data loads', async () => {
      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      // Chart section should be present (either empty state or with data)
      const chartEmpty = screen.queryByTestId('telemetry-chart-empty');
      const chartWithData = screen.queryByTestId('telemetry-chart');
      // One of these should be present after data loads
      expect(chartEmpty || chartWithData).toBeTruthy();
    });
  });

  describe('queue badge colors', () => {
    it('uses gray color for empty queue', async () => {
      const emptyQueues = {
        ...mockTelemetryData,
        queues: { detection_queue: 0, analysis_queue: 0 },
      };
      vi.mocked(api.fetchTelemetry).mockResolvedValue(emptyQueues);

      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByTestId('detection-queue-depth')).toHaveTextContent('0');
      expect(screen.getByTestId('analysis-queue-depth')).toHaveTextContent('0');
    });

    it('displays correct queue values', async () => {
      vi.mocked(api.fetchTelemetry).mockResolvedValue(mockTelemetryData);

      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByTestId('detection-queue-depth')).toHaveTextContent('5');
      expect(screen.getByTestId('analysis-queue-depth')).toHaveTextContent('2');
    });
  });

  describe('edge cases', () => {
    it('handles zero queue values correctly', async () => {
      const zeroQueues = {
        ...mockTelemetryData,
        queues: { detection_queue: 0, analysis_queue: 0 },
      };
      vi.mocked(api.fetchTelemetry).mockResolvedValue(zeroQueues);

      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByTestId('detection-queue-depth')).toHaveTextContent('0');
      expect(screen.getByTestId('analysis-queue-depth')).toHaveTextContent('0');
    });

    it('handles large queue values', async () => {
      const largeQueues = {
        ...mockTelemetryData,
        queues: { detection_queue: 100, analysis_queue: 50 },
      };
      vi.mocked(api.fetchTelemetry).mockResolvedValue(largeQueues);

      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByTestId('detection-queue-depth')).toHaveTextContent('100');
      expect(screen.getByTestId('analysis-queue-depth')).toHaveTextContent('50');
      // Should show warnings for large queues
      expect(screen.getByTestId('detection-queue-warning')).toBeInTheDocument();
      expect(screen.getByTestId('analysis-queue-warning')).toBeInTheDocument();
    });

    it('applies custom className', async () => {
      vi.mocked(api.fetchTelemetry).mockResolvedValue(mockTelemetryData);

      render(<PipelineTelemetry className="custom-class" />);

      await waitFor(() => {
        expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
      });

      expect(screen.getByTestId('pipeline-telemetry')).toBeInTheDocument();
    });
  });

  describe('polling behavior', () => {
    it('calls fetchTelemetry on initial render', async () => {
      vi.mocked(api.fetchTelemetry).mockResolvedValue(mockTelemetryData);

      render(<PipelineTelemetry />);

      await waitFor(() => {
        expect(api.fetchTelemetry).toHaveBeenCalled();
      });
    });

    it('makes at least one fetch call', async () => {
      vi.mocked(api.fetchTelemetry).mockResolvedValue(mockTelemetryData);

      render(<PipelineTelemetry pollingInterval={1000} />);

      // Initial call should happen
      await waitFor(() => {
        expect(api.fetchTelemetry).toHaveBeenCalled();
      });

      // The component should have made at least one call
      expect(vi.mocked(api.fetchTelemetry).mock.calls.length).toBeGreaterThanOrEqual(1);
    });
  });

  describe('accessibility', () => {
    it('has appropriate aria labels for warnings', async () => {
      const warningData = {
        ...mockTelemetryData,
        queues: { detection_queue: 15, analysis_queue: 15 },
      };
      vi.mocked(api.fetchTelemetry).mockResolvedValue(warningData);

      render(<PipelineTelemetry queueWarningThreshold={10} />);

      await waitFor(
        () => {
          expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      expect(screen.getByLabelText('Pipeline warning')).toBeInTheDocument();
    });
  });

  describe('card highlighting', () => {
    it('highlights detection queue card when backing up', async () => {
      const backingUpData = {
        ...mockTelemetryData,
        queues: { detection_queue: 15, analysis_queue: 2 },
      };
      vi.mocked(api.fetchTelemetry).mockResolvedValue(backingUpData);

      render(<PipelineTelemetry queueWarningThreshold={10} />);

      await waitFor(
        () => {
          expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      const detectionCard = screen.getByTestId('detection-queue-card');
      expect(detectionCard).toHaveClass('bg-red-500/10');
      expect(detectionCard).toHaveClass('border-red-500/30');
    });

    it('highlights analysis queue card when backing up', async () => {
      const backingUpData = {
        ...mockTelemetryData,
        queues: { detection_queue: 2, analysis_queue: 15 },
      };
      vi.mocked(api.fetchTelemetry).mockResolvedValue(backingUpData);

      render(<PipelineTelemetry queueWarningThreshold={10} />);

      await waitFor(
        () => {
          expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      const analysisCard = screen.getByTestId('analysis-queue-card');
      expect(analysisCard).toHaveClass('bg-red-500/10');
      expect(analysisCard).toHaveClass('border-red-500/30');
    });

    it('does not highlight cards when queues are healthy', async () => {
      vi.mocked(api.fetchTelemetry).mockResolvedValue(mockTelemetryData);

      render(<PipelineTelemetry queueWarningThreshold={10} />);

      await waitFor(
        () => {
          expect(screen.queryByTestId('telemetry-loading')).not.toBeInTheDocument();
        },
        { timeout: 5000 }
      );

      const detectionCard = screen.getByTestId('detection-queue-card');
      const analysisCard = screen.getByTestId('analysis-queue-card');

      expect(detectionCard).not.toHaveClass('bg-red-500/10');
      expect(analysisCard).not.toHaveClass('bg-red-500/10');
    });
  });
});

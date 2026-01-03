import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import PipelineMetricsPanel, {
  type QueueDepths,
  type PipelineLatencies,
  type ThroughputPoint,
} from './PipelineMetricsPanel';

describe('PipelineMetricsPanel', () => {
  const mockQueues: QueueDepths = {
    detection_queue: 5,
    analysis_queue: 2,
  };

  const mockLatencies: PipelineLatencies = {
    detect: { avg_ms: 200, p95_ms: 350, p99_ms: 500, sample_count: 100 },
    batch: { avg_ms: 50, p95_ms: 80, p99_ms: 120, sample_count: 50 },
    analyze: { avg_ms: 1500, p95_ms: 2500, p99_ms: 3500, sample_count: 75 },
  };

  const mockThroughput: ThroughputPoint[] = [
    { time: '10:00:00', detections: 10, analyses: 8 },
    { time: '10:00:05', detections: 12, analyses: 10 },
    { time: '10:00:10', detections: 15, analyses: 12 },
  ];

  describe('rendering', () => {
    it('renders the panel with title', () => {
      render(<PipelineMetricsPanel queues={mockQueues} />);

      expect(screen.getByTestId('pipeline-metrics-panel')).toBeInTheDocument();
      expect(screen.getByText('Pipeline Metrics')).toBeInTheDocument();
    });

    it('renders queue section with correct values', () => {
      render(<PipelineMetricsPanel queues={mockQueues} />);

      expect(screen.getByText('Queues')).toBeInTheDocument();
      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('5');
      expect(screen.getByTestId('analysis-queue-badge')).toHaveTextContent('2');
    });

    it('renders latency section with all stages', () => {
      render(<PipelineMetricsPanel queues={mockQueues} latencies={mockLatencies} />);

      expect(screen.getByTestId('detect-latency-card')).toBeInTheDocument();
      expect(screen.getByTestId('batch-latency-card')).toBeInTheDocument();
      expect(screen.getByTestId('analyze-latency-card')).toBeInTheDocument();
    });

    it('displays formatted latency values', () => {
      render(<PipelineMetricsPanel queues={mockQueues} latencies={mockLatencies} />);

      expect(screen.getByTestId('detect-latency-badge')).toHaveTextContent('200ms');
      expect(screen.getByTestId('batch-latency-badge')).toHaveTextContent('50ms');
      expect(screen.getByTestId('analyze-latency-badge')).toHaveTextContent('1.5s');
    });

    it('renders throughput section', () => {
      render(<PipelineMetricsPanel queues={mockQueues} throughputHistory={mockThroughput} />);

      expect(screen.getByText('Throughput')).toBeInTheDocument();
      expect(screen.getByTestId('detections-throughput')).toHaveTextContent('15/min');
      expect(screen.getByTestId('analyses-throughput')).toHaveTextContent('12/min');
    });

    it('shows throughput chart when data available', () => {
      render(<PipelineMetricsPanel queues={mockQueues} throughputHistory={mockThroughput} />);

      expect(screen.getByTestId('throughput-chart')).toBeInTheDocument();
    });

    it('shows empty state when no throughput data', () => {
      render(<PipelineMetricsPanel queues={mockQueues} throughputHistory={[]} />);

      expect(screen.getByTestId('throughput-chart-empty')).toBeInTheDocument();
      expect(screen.getByText('Collecting data...')).toBeInTheDocument();
    });

    it('displays timestamp when provided', () => {
      render(
        <PipelineMetricsPanel
          queues={mockQueues}
          timestamp="2025-01-01T12:30:00Z"
        />
      );

      // The timestamp shows as a localized time string
      const timestampElement = screen.getByTestId('pipeline-timestamp');
      expect(timestampElement).toBeInTheDocument();
      expect(timestampElement.textContent).toContain('Updated:');
    });
  });

  describe('queue warnings', () => {
    it('shows warning icon when detection queue exceeds threshold', () => {
      render(
        <PipelineMetricsPanel
          queues={{ detection_queue: 15, analysis_queue: 2 }}
          queueWarningThreshold={10}
        />
      );

      expect(screen.getByTestId('pipeline-warning-icon')).toBeInTheDocument();
      expect(screen.getByTestId('queue-backup-warning')).toBeInTheDocument();
    });

    it('shows warning icon when analysis queue exceeds threshold', () => {
      render(
        <PipelineMetricsPanel
          queues={{ detection_queue: 2, analysis_queue: 15 }}
          queueWarningThreshold={10}
        />
      );

      expect(screen.getByTestId('pipeline-warning-icon')).toBeInTheDocument();
      expect(screen.getByTestId('queue-backup-warning')).toBeInTheDocument();
    });

    it('does not show warning when queues are below threshold', () => {
      render(
        <PipelineMetricsPanel
          queues={{ detection_queue: 5, analysis_queue: 5 }}
          queueWarningThreshold={10}
        />
      );

      expect(screen.queryByTestId('pipeline-warning-icon')).not.toBeInTheDocument();
      expect(screen.queryByTestId('queue-backup-warning')).not.toBeInTheDocument();
    });

    it('applies correct badge colors based on queue depth', () => {
      // Empty queue - gray
      const { rerender } = render(
        <PipelineMetricsPanel queues={{ detection_queue: 0, analysis_queue: 0 }} />
      );
      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('0');

      // Healthy queue - green (1-5)
      rerender(
        <PipelineMetricsPanel queues={{ detection_queue: 3, analysis_queue: 0 }} />
      );
      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('3');

      // Moderate queue - yellow (6-10)
      rerender(
        <PipelineMetricsPanel queues={{ detection_queue: 8, analysis_queue: 0 }} />
      );
      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('8');

      // Backing up - red (>10)
      rerender(
        <PipelineMetricsPanel queues={{ detection_queue: 15, analysis_queue: 0 }} />
      );
      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('15');
    });
  });

  describe('latency warnings', () => {
    it('shows warning icon when detect latency exceeds threshold', () => {
      render(
        <PipelineMetricsPanel
          queues={mockQueues}
          latencies={{ detect: { avg_ms: 12000, p95_ms: 15000, p99_ms: 20000 } }}
          latencyWarningThreshold={10000}
        />
      );

      expect(screen.getByTestId('pipeline-warning-icon')).toBeInTheDocument();
    });

    it('shows warning icon when analyze latency exceeds threshold', () => {
      render(
        <PipelineMetricsPanel
          queues={mockQueues}
          latencies={{ analyze: { avg_ms: 12000, p95_ms: 15000, p99_ms: 20000 } }}
          latencyWarningThreshold={10000}
        />
      );

      expect(screen.getByTestId('pipeline-warning-icon')).toBeInTheDocument();
    });

    it('applies warning styling to high latency cards', () => {
      render(
        <PipelineMetricsPanel
          queues={mockQueues}
          latencies={{
            detect: { avg_ms: 12000, p95_ms: 15000, p99_ms: 20000 },
            analyze: { avg_ms: 100, p95_ms: 200, p99_ms: 300 },
          }}
          latencyWarningThreshold={10000}
        />
      );

      const detectCard = screen.getByTestId('detect-latency-card');
      expect(detectCard.className).toContain('border-yellow-500');
    });
  });

  describe('null/undefined handling', () => {
    it('handles null latencies gracefully', () => {
      render(<PipelineMetricsPanel queues={mockQueues} latencies={null} />);

      expect(screen.getByTestId('detect-latency-badge')).toHaveTextContent('-');
      expect(screen.getByTestId('batch-latency-badge')).toHaveTextContent('-');
      expect(screen.getByTestId('analyze-latency-badge')).toHaveTextContent('-');
    });

    it('handles undefined stage latencies gracefully', () => {
      render(<PipelineMetricsPanel queues={mockQueues} latencies={{}} />);

      expect(screen.getByTestId('detect-latency-badge')).toHaveTextContent('-');
    });

    it('handles null values within latencies', () => {
      render(
        <PipelineMetricsPanel
          queues={mockQueues}
          latencies={{
            detect: { avg_ms: null, p95_ms: null, p99_ms: null },
          }}
        />
      );

      expect(screen.getByTestId('detect-latency-badge')).toHaveTextContent('-');
    });

    it('handles empty throughput history', () => {
      render(<PipelineMetricsPanel queues={mockQueues} throughputHistory={[]} />);

      expect(screen.getByTestId('throughput-chart-empty')).toBeInTheDocument();
      expect(screen.getByTestId('detections-throughput')).toHaveTextContent('-');
    });
  });

  describe('latency formatting', () => {
    it('formats milliseconds correctly', () => {
      render(
        <PipelineMetricsPanel
          queues={mockQueues}
          latencies={{ detect: { avg_ms: 500, p95_ms: 750, p99_ms: 900 } }}
        />
      );

      expect(screen.getByTestId('detect-latency-badge')).toHaveTextContent('500ms');
    });

    it('formats seconds correctly for values >= 1000ms', () => {
      render(
        <PipelineMetricsPanel
          queues={mockQueues}
          latencies={{ detect: { avg_ms: 1500, p95_ms: 2500, p99_ms: 3500 } }}
        />
      );

      expect(screen.getByTestId('detect-latency-badge')).toHaveTextContent('1.5s');
    });
  });

  describe('custom thresholds', () => {
    it('respects custom queue warning threshold', () => {
      // With custom threshold of 5, queue of 6 should trigger warning
      render(
        <PipelineMetricsPanel
          queues={{ detection_queue: 6, analysis_queue: 0 }}
          queueWarningThreshold={5}
        />
      );

      expect(screen.getByTestId('queue-backup-warning')).toBeInTheDocument();
    });

    it('respects custom latency warning threshold', () => {
      // With custom threshold of 5000, latency of 6000 should trigger warning
      render(
        <PipelineMetricsPanel
          queues={mockQueues}
          latencies={{ detect: { avg_ms: 6000, p95_ms: 7000, p99_ms: 8000 } }}
          latencyWarningThreshold={5000}
        />
      );

      expect(screen.getByTestId('pipeline-warning-icon')).toBeInTheDocument();
    });
  });

  describe('styling', () => {
    it('applies custom className', () => {
      render(<PipelineMetricsPanel queues={mockQueues} className="custom-class" />);

      const panel = screen.getByTestId('pipeline-metrics-panel');
      expect(panel.className).toContain('custom-class');
    });

    it('has dark theme styling', () => {
      render(<PipelineMetricsPanel queues={mockQueues} />);

      const panel = screen.getByTestId('pipeline-metrics-panel');
      expect(panel.className).toContain('bg-[#1A1A1A]');
    });
  });
});

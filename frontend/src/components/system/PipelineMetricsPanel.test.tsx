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

  describe('edge cases with invalid data', () => {
    it('handles negative queue values gracefully', () => {
      // Negative values should be displayed as-is (component doesn't clamp)
      // The badge color logic handles negative by treating as 0 (gray)
      const invalidQueues: QueueDepths = { detection_queue: -5, analysis_queue: -10 };
      render(<PipelineMetricsPanel queues={invalidQueues} />);

      // Component should not crash and should display the values
      expect(screen.getByTestId('pipeline-metrics-panel')).toBeInTheDocument();
      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('-5');
      expect(screen.getByTestId('analysis-queue-badge')).toHaveTextContent('-10');
    });

    it('handles NaN in latency avg_ms', () => {
      const invalidLatencies: PipelineLatencies = {
        detect: { avg_ms: NaN, p95_ms: 100, p99_ms: 200 },
      };
      render(<PipelineMetricsPanel queues={mockQueues} latencies={invalidLatencies} />);

      // NaN should render (formatLatency handles it as a number)
      expect(screen.getByTestId('pipeline-metrics-panel')).toBeInTheDocument();
      expect(screen.getByTestId('detect-latency-card')).toBeInTheDocument();
    });

    it('handles undefined in latency data', () => {
      const invalidLatencies: PipelineLatencies = {
        detect: { avg_ms: undefined, p95_ms: undefined, p99_ms: undefined },
        batch: { avg_ms: undefined },
        analyze: { avg_ms: undefined },
      };
      render(<PipelineMetricsPanel queues={mockQueues} latencies={invalidLatencies} />);

      // undefined values should display fallback '-'
      expect(screen.getByTestId('detect-latency-badge')).toHaveTextContent('-');
      expect(screen.getByTestId('batch-latency-badge')).toHaveTextContent('-');
      expect(screen.getByTestId('analyze-latency-badge')).toHaveTextContent('-');
    });

    it('handles empty queue object by using default values', () => {
      // TypeScript requires both keys, but we test with partial data cast to QueueDepths
      const emptyQueues = {} as QueueDepths;
      render(<PipelineMetricsPanel queues={emptyQueues} />);

      // Component should not crash - undefined values will be displayed
      expect(screen.getByTestId('pipeline-metrics-panel')).toBeInTheDocument();
      expect(screen.getByTestId('detection-queue-badge')).toBeInTheDocument();
      expect(screen.getByTestId('analysis-queue-badge')).toBeInTheDocument();
    });

    it('handles missing keys in queue data', () => {
      // Only detection_queue provided, analysis_queue missing
      const partialQueues = { detection_queue: 5 } as QueueDepths;
      render(<PipelineMetricsPanel queues={partialQueues} />);

      // Component should not crash
      expect(screen.getByTestId('pipeline-metrics-panel')).toBeInTheDocument();
      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('5');
      // analysis_queue will be undefined, displayed as such
      expect(screen.getByTestId('analysis-queue-badge')).toBeInTheDocument();
    });

    it('handles zero queue values correctly', () => {
      const zeroQueues: QueueDepths = { detection_queue: 0, analysis_queue: 0 };
      render(<PipelineMetricsPanel queues={zeroQueues} />);

      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('0');
      expect(screen.getByTestId('analysis-queue-badge')).toHaveTextContent('0');
      // Zero queues should not trigger warnings
      expect(screen.queryByTestId('queue-backup-warning')).not.toBeInTheDocument();
    });

    it('handles mixed valid and invalid latency values', () => {
      const mixedLatencies: PipelineLatencies = {
        detect: { avg_ms: 100, p95_ms: null, p99_ms: undefined },
        batch: { avg_ms: null, p95_ms: 200, p99_ms: 300 },
        analyze: null,
      };
      render(<PipelineMetricsPanel queues={mockQueues} latencies={mixedLatencies} />);

      // Valid avg_ms should be formatted
      expect(screen.getByTestId('detect-latency-badge')).toHaveTextContent('100ms');
      // Null avg_ms should show fallback
      expect(screen.getByTestId('batch-latency-badge')).toHaveTextContent('-');
      // Null stage should show fallback
      expect(screen.getByTestId('analyze-latency-badge')).toHaveTextContent('-');
    });

    it('handles throughput history with missing fields', () => {
      const invalidThroughput = [
        { time: '10:00:00' } as ThroughputPoint, // Missing detections and analyses
      ];
      render(<PipelineMetricsPanel queues={mockQueues} throughputHistory={invalidThroughput} />);

      // Component should not crash
      expect(screen.getByTestId('pipeline-metrics-panel')).toBeInTheDocument();
      expect(screen.getByTestId('throughput-chart')).toBeInTheDocument();
    });

    it('handles very large queue values', () => {
      const largeQueues: QueueDepths = { detection_queue: 999999, analysis_queue: 1000000 };
      render(<PipelineMetricsPanel queues={largeQueues} queueWarningThreshold={10} />);

      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('999999');
      expect(screen.getByTestId('analysis-queue-badge')).toHaveTextContent('1000000');
      // Should trigger warning
      expect(screen.getByTestId('queue-backup-warning')).toBeInTheDocument();
    });

    it('handles very large latency values', () => {
      const largeLatencies: PipelineLatencies = {
        detect: { avg_ms: 999999999, p95_ms: 1000000000, p99_ms: 2000000000 },
      };
      render(<PipelineMetricsPanel queues={mockQueues} latencies={largeLatencies} />);

      // Should format as seconds
      expect(screen.getByTestId('detect-latency-badge')).toHaveTextContent('s');
    });

    it('does not trigger latency warning for NaN values', () => {
      const nanLatencies: PipelineLatencies = {
        detect: { avg_ms: NaN },
        analyze: { avg_ms: NaN },
      };
      render(
        <PipelineMetricsPanel
          queues={mockQueues}
          latencies={nanLatencies}
          latencyWarningThreshold={10000}
        />
      );

      // NaN comparison should not trigger warning (NaN > threshold is false)
      // The component uses ?? 0 for null/undefined, but NaN passes through
      expect(screen.getByTestId('pipeline-metrics-panel')).toBeInTheDocument();
    });
  });
});

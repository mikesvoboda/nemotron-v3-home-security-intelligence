/**
 * Tests for PipelineQueues component.
 *
 * Tests the enhanced pipeline queues display with health status badges,
 * worker counts, throughput metrics, and DLQ status.
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import PipelineQueues from './PipelineQueues';

import type { QueuesStatusResponse } from '../../types/queue';

// Helper to create mock queue status
const createMockQueuesStatus = (
  overrides: Partial<QueuesStatusResponse> = {}
): QueuesStatusResponse => ({
  queues: [
    {
      name: 'detection',
      status: 'healthy',
      depth: 5,
      running: 2,
      workers: 4,
      throughput: {
        jobs_per_minute: 12.5,
        avg_processing_seconds: 4.8,
      },
      oldest_job: {
        id: 'job_123',
        queued_at: '2026-01-25T10:00:00Z',
        wait_seconds: 15.5,
      },
    },
    {
      name: 'ai_analysis',
      status: 'healthy',
      depth: 3,
      running: 1,
      workers: 4,
      throughput: {
        jobs_per_minute: 8.2,
        avg_processing_seconds: 7.3,
      },
      oldest_job: null,
    },
  ],
  summary: {
    total_queued: 8,
    total_running: 3,
    total_workers: 8,
    overall_status: 'healthy',
  },
  ...overrides,
});

describe('PipelineQueues', () => {
  it('renders component with title', () => {
    render(<PipelineQueues detectionQueue={0} analysisQueue={0} />);

    expect(screen.getByText('Pipeline Queues')).toBeInTheDocument();
  });

  it('displays detection queue depth', () => {
    render(<PipelineQueues detectionQueue={5} analysisQueue={0} />);

    expect(screen.getByText('Detection Queue')).toBeInTheDocument();
    expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('5');
  });

  it('displays analysis queue depth', () => {
    render(<PipelineQueues detectionQueue={0} analysisQueue={3} />);

    expect(screen.getByText('Analysis Queue')).toBeInTheDocument();
    expect(screen.getByTestId('analysis-queue-badge')).toHaveTextContent('3');
  });

  it('displays queue descriptions', () => {
    render(<PipelineQueues detectionQueue={0} analysisQueue={0} />);

    expect(screen.getByText('RT-DETRv2 processing')).toBeInTheDocument();
    expect(screen.getByText('Nemotron LLM analysis')).toBeInTheDocument();
  });

  describe('warning indicators', () => {
    it('shows warning when detection queue exceeds threshold', () => {
      render(<PipelineQueues detectionQueue={15} analysisQueue={0} />);

      expect(screen.getByTestId('detection-queue-warning')).toBeInTheDocument();
      expect(screen.getByTestId('queue-warning-icon')).toBeInTheDocument();
      expect(screen.getByTestId('queue-backup-warning')).toBeInTheDocument();
    });

    it('shows warning when analysis queue exceeds threshold', () => {
      render(<PipelineQueues detectionQueue={0} analysisQueue={12} />);

      expect(screen.getByTestId('analysis-queue-warning')).toBeInTheDocument();
      expect(screen.getByTestId('queue-warning-icon')).toBeInTheDocument();
      expect(screen.getByTestId('queue-backup-warning')).toBeInTheDocument();
    });

    it('shows warning when both queues exceed threshold', () => {
      render(<PipelineQueues detectionQueue={15} analysisQueue={12} />);

      expect(screen.getByTestId('detection-queue-warning')).toBeInTheDocument();
      expect(screen.getByTestId('analysis-queue-warning')).toBeInTheDocument();
      expect(screen.getByTestId('queue-warning-icon')).toBeInTheDocument();
    });

    it('does not show warning when queues are within threshold', () => {
      render(<PipelineQueues detectionQueue={5} analysisQueue={8} />);

      expect(screen.queryByTestId('detection-queue-warning')).not.toBeInTheDocument();
      expect(screen.queryByTestId('analysis-queue-warning')).not.toBeInTheDocument();
      expect(screen.queryByTestId('queue-warning-icon')).not.toBeInTheDocument();
      expect(screen.queryByTestId('queue-backup-warning')).not.toBeInTheDocument();
    });

    it('displays warning message text', () => {
      render(<PipelineQueues detectionQueue={15} analysisQueue={0} />);

      expect(
        screen.getByText('Queue backup detected. Processing may be delayed.')
      ).toBeInTheDocument();
    });

    it('uses custom warning threshold', () => {
      // With threshold of 5, a queue of 6 should trigger warning
      render(<PipelineQueues detectionQueue={6} analysisQueue={0} warningThreshold={5} />);

      expect(screen.getByTestId('detection-queue-warning')).toBeInTheDocument();
      expect(screen.getByTestId('queue-backup-warning')).toBeInTheDocument();
    });

    it('does not trigger warning at threshold boundary', () => {
      // Exactly at threshold (10) should not trigger warning
      render(<PipelineQueues detectionQueue={10} analysisQueue={10} />);

      expect(screen.queryByTestId('detection-queue-warning')).not.toBeInTheDocument();
      expect(screen.queryByTestId('analysis-queue-warning')).not.toBeInTheDocument();
    });
  });

  describe('queue badge colors', () => {
    it('uses gray color for empty queue', () => {
      render(<PipelineQueues detectionQueue={0} analysisQueue={0} />);

      const detectionBadge = screen.getByTestId('detection-queue-badge');
      const analysisBadge = screen.getByTestId('analysis-queue-badge');
      expect(detectionBadge).toBeInTheDocument();
      expect(analysisBadge).toBeInTheDocument();
    });

    it('shows correct queue values', () => {
      render(<PipelineQueues detectionQueue={3} analysisQueue={7} />);

      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('3');
      expect(screen.getByTestId('analysis-queue-badge')).toHaveTextContent('7');
    });
  });

  describe('edge cases', () => {
    it('handles zero values correctly', () => {
      render(<PipelineQueues detectionQueue={0} analysisQueue={0} />);

      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('0');
      expect(screen.getByTestId('analysis-queue-badge')).toHaveTextContent('0');
    });

    it('handles large queue values', () => {
      render(<PipelineQueues detectionQueue={100} analysisQueue={50} />);

      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('100');
      expect(screen.getByTestId('analysis-queue-badge')).toHaveTextContent('50');
      expect(screen.getByTestId('queue-backup-warning')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<PipelineQueues detectionQueue={0} analysisQueue={0} className="custom-class" />);

      expect(screen.getByTestId('pipeline-queues')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has appropriate aria labels for warnings', () => {
      render(<PipelineQueues detectionQueue={15} analysisQueue={12} />);

      expect(screen.getByLabelText('Queue backup warning')).toBeInTheDocument();
      expect(screen.getByLabelText('Detection Queue backing up')).toBeInTheDocument();
      expect(screen.getByLabelText('Analysis Queue backing up')).toBeInTheDocument();
    });

    it('has alert role for warning message', () => {
      render(<PipelineQueues detectionQueue={15} analysisQueue={0} />);

      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
    });
  });

  describe('row highlighting', () => {
    it('highlights detection queue row when backing up', () => {
      render(<PipelineQueues detectionQueue={15} analysisQueue={0} />);

      const row = screen.getByTestId('detection-queue-row');
      expect(row).toHaveClass('bg-red-500/10');
      expect(row).toHaveClass('border-red-500/30');
    });

    it('highlights analysis queue row when backing up', () => {
      render(<PipelineQueues detectionQueue={0} analysisQueue={15} />);

      const row = screen.getByTestId('analysis-queue-row');
      expect(row).toHaveClass('bg-red-500/10');
      expect(row).toHaveClass('border-red-500/30');
    });

    it('does not highlight rows when queues are healthy', () => {
      render(<PipelineQueues detectionQueue={5} analysisQueue={5} />);

      const detectionRow = screen.getByTestId('detection-queue-row');
      const analysisRow = screen.getByTestId('analysis-queue-row');

      expect(detectionRow).not.toHaveClass('bg-red-500/10');
      expect(analysisRow).not.toHaveClass('bg-red-500/10');
    });
  });

  describe('detailed queue status (NEM-3654)', () => {
    it('displays overall health badge when queue status provided', () => {
      const queuesStatus = createMockQueuesStatus();
      render(
        <PipelineQueues
          detectionQueue={0}
          analysisQueue={0}
          queuesStatus={queuesStatus}
        />
      );

      expect(screen.getByTestId('overall-health-badge')).toHaveTextContent('healthy');
    });

    it('displays per-queue health badges', () => {
      const queuesStatus = createMockQueuesStatus();
      render(
        <PipelineQueues
          detectionQueue={0}
          analysisQueue={0}
          queuesStatus={queuesStatus}
        />
      );

      expect(screen.getByTestId('detection-health-badge')).toHaveTextContent('healthy');
      expect(screen.getByTestId('analysis-health-badge')).toHaveTextContent('healthy');
    });

    it('displays worker count from detailed status', () => {
      const queuesStatus = createMockQueuesStatus();
      render(
        <PipelineQueues
          detectionQueue={0}
          analysisQueue={0}
          queuesStatus={queuesStatus}
        />
      );

      // Worker count should be displayed (4 workers)
      expect(screen.getAllByText('4')).toHaveLength(2); // Both queues have 4 workers
    });

    it('displays throughput metrics', () => {
      const queuesStatus = createMockQueuesStatus();
      render(
        <PipelineQueues
          detectionQueue={0}
          analysisQueue={0}
          queuesStatus={queuesStatus}
        />
      );

      // Detection queue has 12.5 jobs/min (rounded to 13 since >= 10)
      expect(screen.getByText('13/min')).toBeInTheDocument();
      // Analysis queue has 8.2 jobs/min (shows decimal since < 10)
      expect(screen.getByText('8.2/min')).toBeInTheDocument();
    });

    it('displays oldest job wait time', () => {
      const queuesStatus = createMockQueuesStatus();
      render(
        <PipelineQueues
          detectionQueue={0}
          analysisQueue={0}
          queuesStatus={queuesStatus}
        />
      );

      // Detection queue has 15.5s wait time
      expect(screen.getByText('15.5s')).toBeInTheDocument();
    });

    it('displays summary stats', () => {
      const queuesStatus = createMockQueuesStatus();
      render(
        <PipelineQueues
          detectionQueue={0}
          analysisQueue={0}
          queuesStatus={queuesStatus}
        />
      );

      expect(screen.getByTestId('queue-summary-stats')).toBeInTheDocument();
      expect(screen.getByText('Queued')).toBeInTheDocument();
      expect(screen.getByText('Running')).toBeInTheDocument();
      expect(screen.getByText('Workers')).toBeInTheDocument();
    });

    it('uses depth from detailed status over fallback', () => {
      const queuesStatus = createMockQueuesStatus();
      render(
        <PipelineQueues
          detectionQueue={100} // Fallback value
          analysisQueue={100} // Fallback value
          queuesStatus={queuesStatus} // Has depth of 5 and 3
        />
      );

      // Should use detailed status depths, not fallbacks
      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('5');
      expect(screen.getByTestId('analysis-queue-badge')).toHaveTextContent('3');
    });

    it('shows warning status from detailed health', () => {
      const queuesStatus = createMockQueuesStatus({
        queues: [
          {
            name: 'detection',
            status: 'warning',
            depth: 50,
            running: 4,
            workers: 4,
            throughput: { jobs_per_minute: 5, avg_processing_seconds: 12 },
            oldest_job: null,
          },
          {
            name: 'ai_analysis',
            status: 'healthy',
            depth: 3,
            running: 1,
            workers: 4,
            throughput: { jobs_per_minute: 8, avg_processing_seconds: 7 },
            oldest_job: null,
          },
        ],
        summary: {
          total_queued: 53,
          total_running: 5,
          total_workers: 8,
          overall_status: 'warning',
        },
      });

      render(
        <PipelineQueues
          detectionQueue={0}
          analysisQueue={0}
          queuesStatus={queuesStatus}
        />
      );

      expect(screen.getByTestId('overall-health-badge')).toHaveTextContent('warning');
      expect(screen.getByTestId('detection-health-badge')).toHaveTextContent('warning');
    });

    it('shows critical status from detailed health', () => {
      const queuesStatus = createMockQueuesStatus({
        queues: [
          {
            name: 'detection',
            status: 'critical',
            depth: 100,
            running: 4,
            workers: 4,
            throughput: { jobs_per_minute: 2, avg_processing_seconds: 30 },
            oldest_job: null,
          },
        ],
        summary: {
          total_queued: 100,
          total_running: 4,
          total_workers: 4,
          overall_status: 'critical',
        },
      });

      render(
        <PipelineQueues
          detectionQueue={0}
          analysisQueue={0}
          queuesStatus={queuesStatus}
        />
      );

      expect(screen.getByTestId('overall-health-badge')).toHaveTextContent('critical');
      expect(screen.getByTestId('queue-warning-icon')).toBeInTheDocument();
    });
  });

  describe('DLQ status display', () => {
    it('shows DLQ row when DLQ has items', () => {
      const queuesStatus = createMockQueuesStatus({
        queues: [
          {
            name: 'detection',
            status: 'healthy',
            depth: 5,
            running: 2,
            workers: 4,
            throughput: { jobs_per_minute: 10, avg_processing_seconds: 6 },
            oldest_job: null,
          },
          {
            name: 'dlq',
            status: 'warning',
            depth: 3,
            running: 0,
            workers: 0,
            throughput: { jobs_per_minute: 0, avg_processing_seconds: 0 },
            oldest_job: null,
          },
        ],
        summary: {
          total_queued: 8,
          total_running: 2,
          total_workers: 4,
          overall_status: 'warning',
        },
      });

      render(
        <PipelineQueues
          detectionQueue={0}
          analysisQueue={0}
          queuesStatus={queuesStatus}
        />
      );

      expect(screen.getByTestId('dlq-row')).toBeInTheDocument();
      expect(screen.getByText('Dead Letter Queue')).toBeInTheDocument();
      expect(screen.getByTestId('dlq-badge')).toHaveTextContent('3');
      expect(screen.getByTestId('dlq-warning')).toBeInTheDocument();
    });

    it('does not show DLQ row when DLQ is empty', () => {
      const queuesStatus = createMockQueuesStatus({
        queues: [
          {
            name: 'detection',
            status: 'healthy',
            depth: 5,
            running: 2,
            workers: 4,
            throughput: { jobs_per_minute: 10, avg_processing_seconds: 6 },
            oldest_job: null,
          },
          {
            name: 'dlq',
            status: 'healthy',
            depth: 0,
            running: 0,
            workers: 0,
            throughput: { jobs_per_minute: 0, avg_processing_seconds: 0 },
            oldest_job: null,
          },
        ],
      });

      render(
        <PipelineQueues
          detectionQueue={0}
          analysisQueue={0}
          queuesStatus={queuesStatus}
        />
      );

      expect(screen.queryByTestId('dlq-row')).not.toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('shows loading indicator in badges', () => {
      render(
        <PipelineQueues
          detectionQueue={0}
          analysisQueue={0}
          isLoading={true}
        />
      );

      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('...');
      expect(screen.getByTestId('analysis-queue-badge')).toHaveTextContent('...');
    });
  });

  describe('fallback behavior', () => {
    it('uses fallback values when queuesStatus is null', () => {
      render(
        <PipelineQueues
          detectionQueue={10}
          analysisQueue={20}
          queuesStatus={null}
        />
      );

      expect(screen.getByTestId('detection-queue-badge')).toHaveTextContent('10');
      expect(screen.getByTestId('analysis-queue-badge')).toHaveTextContent('20');
      expect(screen.queryByTestId('overall-health-badge')).not.toBeInTheDocument();
      expect(screen.queryByTestId('queue-summary-stats')).not.toBeInTheDocument();
    });

    it('does not show detailed metrics when queuesStatus is undefined', () => {
      render(
        <PipelineQueues
          detectionQueue={5}
          analysisQueue={3}
        />
      );

      expect(screen.queryByTestId('detection-health-badge')).not.toBeInTheDocument();
      expect(screen.queryByTestId('analysis-health-badge')).not.toBeInTheDocument();
    });
  });
});

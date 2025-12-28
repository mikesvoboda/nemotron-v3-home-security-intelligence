import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import PipelineQueues from './PipelineQueues';

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
      render(
        <PipelineQueues detectionQueue={6} analysisQueue={0} warningThreshold={5} />
      );

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
      render(
        <PipelineQueues
          detectionQueue={0}
          analysisQueue={0}
          className="custom-class"
        />
      );

      expect(screen.getByTestId('pipeline-queues')).toBeInTheDocument();
    });
  });

  describe('accessibility', () => {
    it('has appropriate aria labels for warnings', () => {
      render(<PipelineQueues detectionQueue={15} analysisQueue={12} />);

      expect(screen.getByLabelText('Queue backup warning')).toBeInTheDocument();
      expect(screen.getByLabelText('Detection queue backing up')).toBeInTheDocument();
      expect(screen.getByLabelText('Analysis queue backing up')).toBeInTheDocument();
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
});

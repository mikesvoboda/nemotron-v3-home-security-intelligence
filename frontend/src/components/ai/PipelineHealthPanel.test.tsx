/**
 * Tests for PipelineHealthPanel component
 *
 * Tests the pipeline health visualization including queue depths,
 * throughput stats, error displays, and status rendering.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import PipelineHealthPanel from './PipelineHealthPanel';

// Default healthy state for testing
const healthyProps = {
  detectionQueueDepth: 5,
  analysisQueueDepth: 2,
  totalDetections: 50000,
  totalEvents: 12500,
  pipelineErrors: {},
  queueOverflows: {},
  dlqItems: {},
};

describe('PipelineHealthPanel', () => {
  describe('basic rendering', () => {
    it('renders the main container with correct testid', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByTestId('pipeline-health-panel')).toBeInTheDocument();
    });

    it('renders queue depths card', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByTestId('queue-depths-card')).toBeInTheDocument();
    });

    it('renders throughput card', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByTestId('throughput-card')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<PipelineHealthPanel {...healthyProps} className="custom-class" />);
      expect(screen.getByTestId('pipeline-health-panel')).toHaveClass('custom-class');
    });
  });

  describe('Queue Depths section', () => {
    it('displays Queue Depths title', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByText('Queue Depths')).toBeInTheDocument();
    });

    it('displays Detection Queue label', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByText('Detection Queue')).toBeInTheDocument();
    });

    it('displays Analysis Queue label', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByText('Analysis Queue')).toBeInTheDocument();
    });

    it('displays queue depths with item counts', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByText('5 items')).toBeInTheDocument();
      expect(screen.getByText('2 items')).toBeInTheDocument();
    });
  });

  describe('getQueueColor - queue status colors', () => {
    it('displays "Healthy" status for queue depth under 10', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      // Both queues are under 10, so both should show "Healthy"
      expect(screen.getAllByText('Healthy').length).toBe(2);
    });

    it('displays "Moderate load" status for queue depth 10-49', () => {
      const moderateProps = {
        ...healthyProps,
        detectionQueueDepth: 25,
        analysisQueueDepth: 15,
      };
      render(<PipelineHealthPanel {...moderateProps} />);
      expect(screen.getAllByText('Moderate load').length).toBe(2);
    });

    it('displays "Queue backlog detected" for queue depth >= 50', () => {
      const backlogProps = {
        ...healthyProps,
        detectionQueueDepth: 75,
        analysisQueueDepth: 100,
      };
      render(<PipelineHealthPanel {...backlogProps} />);
      expect(screen.getAllByText('Queue backlog detected').length).toBe(2);
    });

    it('displays mixed statuses for different queue depths', () => {
      const mixedProps = {
        ...healthyProps,
        detectionQueueDepth: 5, // Healthy
        analysisQueueDepth: 55, // Backlog
      };
      render(<PipelineHealthPanel {...mixedProps} />);
      expect(screen.getByText('Healthy')).toBeInTheDocument();
      expect(screen.getByText('Queue backlog detected')).toBeInTheDocument();
    });
  });

  describe('Pipeline Throughput section', () => {
    it('displays Pipeline Throughput title', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByText('Pipeline Throughput')).toBeInTheDocument();
    });

    it('displays Total Detections label', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByText('Total Detections')).toBeInTheDocument();
    });

    it('displays Total Events label', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByText('Total Events')).toBeInTheDocument();
    });

    it('displays detection description', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByText('Objects detected by RT-DETRv2')).toBeInTheDocument();
    });

    it('displays events description', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByText('Security events generated')).toBeInTheDocument();
    });
  });

  describe('formatNumber helper (tested through component output)', () => {
    it('displays numbers under 1000 as-is', () => {
      const smallProps = {
        ...healthyProps,
        totalDetections: 500,
        totalEvents: 125,
      };
      render(<PipelineHealthPanel {...smallProps} />);
      expect(screen.getByText('500')).toBeInTheDocument();
      expect(screen.getByText('125')).toBeInTheDocument();
    });

    it('displays numbers 1000-999999 with K suffix', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByText('50.0K')).toBeInTheDocument();
      expect(screen.getByText('12.5K')).toBeInTheDocument();
    });

    it('displays numbers >= 1000000 with M suffix', () => {
      const largeProps = {
        ...healthyProps,
        totalDetections: 5000000,
        totalEvents: 1250000,
      };
      render(<PipelineHealthPanel {...largeProps} />);
      expect(screen.getByText('5.0M')).toBeInTheDocument();
      expect(screen.getByText('1.3M')).toBeInTheDocument();
    });

    it('displays zero as "0"', () => {
      const zeroProps = {
        ...healthyProps,
        totalDetections: 0,
        totalEvents: 0,
      };
      render(<PipelineHealthPanel {...zeroProps} />);
      expect(screen.getAllByText('0').length).toBe(2);
    });
  });

  describe('All Clear Status', () => {
    it('displays Pipeline Healthy status when no errors', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByTestId('all-clear-card')).toBeInTheDocument();
      expect(screen.getByText('Pipeline Healthy')).toBeInTheDocument();
    });

    it('displays healthy message', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(
        screen.getByText('No errors, overflows, or DLQ items detected')
      ).toBeInTheDocument();
    });

    it('does not display all-clear when there are errors', () => {
      const errorProps = {
        ...healthyProps,
        pipelineErrors: { detection_error: 5 },
      };
      render(<PipelineHealthPanel {...errorProps} />);
      expect(screen.queryByTestId('all-clear-card')).not.toBeInTheDocument();
    });

    it('does not display all-clear when there are DLQ items', () => {
      const dlqProps = {
        ...healthyProps,
        dlqItems: { 'dlq:detection_queue': 3 },
      };
      render(<PipelineHealthPanel {...dlqProps} />);
      expect(screen.queryByTestId('all-clear-card')).not.toBeInTheDocument();
    });

    it('does not display all-clear when there are overflows', () => {
      const overflowProps = {
        ...healthyProps,
        queueOverflows: { detection_queue: 10 },
      };
      render(<PipelineHealthPanel {...overflowProps} />);
      expect(screen.queryByTestId('all-clear-card')).not.toBeInTheDocument();
    });
  });

  describe('Errors & Dead Letter Queue section', () => {
    it('displays errors card when there are pipeline errors', () => {
      const errorProps = {
        ...healthyProps,
        pipelineErrors: { detection_error: 5, analysis_error: 3 },
      };
      render(<PipelineHealthPanel {...errorProps} />);
      expect(screen.getByTestId('errors-card')).toBeInTheDocument();
    });

    it('displays Errors & Dead Letter Queue title', () => {
      const errorProps = {
        ...healthyProps,
        pipelineErrors: { detection_error: 5 },
      };
      render(<PipelineHealthPanel {...errorProps} />);
      expect(screen.getByText('Errors & Dead Letter Queue')).toBeInTheDocument();
    });

    it('displays Pipeline Errors section with total count', () => {
      const errorProps = {
        ...healthyProps,
        pipelineErrors: { detection_error: 5, analysis_error: 3 },
      };
      render(<PipelineHealthPanel {...errorProps} />);
      expect(screen.getByText('Pipeline Errors')).toBeInTheDocument();
      expect(screen.getByText('8 total')).toBeInTheDocument();
    });

    it('displays error types with counts', () => {
      const errorProps = {
        ...healthyProps,
        pipelineErrors: { detection_error: 5, analysis_error: 3 },
      };
      render(<PipelineHealthPanel {...errorProps} />);
      expect(screen.getByText('detection error')).toBeInTheDocument();
      expect(screen.getByText('analysis error')).toBeInTheDocument();
      expect(screen.getByText('5')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('displays Queue Overflows section', () => {
      const overflowProps = {
        ...healthyProps,
        queueOverflows: { detection_queue: 10, analysis_queue: 5 },
      };
      render(<PipelineHealthPanel {...overflowProps} />);
      expect(screen.getByText('Queue Overflows')).toBeInTheDocument();
      expect(screen.getByText('15 total')).toBeInTheDocument();
    });

    it('displays DLQ section with items', () => {
      const dlqProps = {
        ...healthyProps,
        dlqItems: { 'dlq:detection_queue': 3, 'dlq:analysis_queue': 2 },
      };
      render(<PipelineHealthPanel {...dlqProps} />);
      expect(screen.getByText('Dead Letter Queue')).toBeInTheDocument();
      // Badge shows total DLQ items - there are multiple "items" badges
      const itemTexts = screen.getAllByText(/items/);
      expect(itemTexts.length).toBeGreaterThan(0);
    });

    it('displays DLQ queue names formatted correctly', () => {
      const dlqProps = {
        ...healthyProps,
        dlqItems: { 'dlq:detection_queue': 1611, 'dlq:analysis_queue': 5 },
      };
      render(<PipelineHealthPanel {...dlqProps} />);
      const dlqSection = screen.getByTestId('dlq-items-section');
      // Check the DLQ section contains the formatted queue names
      // formatDlqQueueName converts 'dlq:detection_queue' -> 'Detection Queue'
      expect(dlqSection).toHaveTextContent('Detection Queue');
      expect(dlqSection).toHaveTextContent('Analysis Queue');
    });

    it('displays large DLQ counts with commas', () => {
      const dlqProps = {
        ...healthyProps,
        dlqItems: { 'dlq:detection_queue': 1611, 'dlq:analysis_queue': 0 },
      };
      render(<PipelineHealthPanel {...dlqProps} />);
      // Total badge shows count with commas (formatNumberWithCommas)
      expect(screen.getByTestId('dlq-total-badge')).toHaveTextContent('1,611 items');
    });

    it('displays only non-zero queues in DLQ breakdown', () => {
      // Note: The filtering of zero counts happens in useAIMetrics, not in PipelineHealthPanel
      // So we test that when only detection_queue is provided, only it is displayed
      const dlqProps = {
        ...healthyProps,
        dlqItems: { 'dlq:detection_queue': 1611 },
      };
      render(<PipelineHealthPanel {...dlqProps} />);
      const dlqSection = screen.getByTestId('dlq-items-section');
      // Detection Queue should be visible in DLQ section
      expect(dlqSection).toHaveTextContent('Detection Queue');
      // Analysis Queue should NOT be visible since it wasn't provided
      expect(dlqSection).not.toHaveTextContent('Analysis Queue');
    });

    it('displays DLQ help message', () => {
      const dlqProps = {
        ...healthyProps,
        dlqItems: { 'dlq:detection_queue': 3 },
      };
      render(<PipelineHealthPanel {...dlqProps} />);
      expect(
        screen.getByText('Failed jobs can be reviewed in Settings > DLQ Monitor')
      ).toBeInTheDocument();
    });
  });

  describe('error types display', () => {
    it('replaces underscores with spaces in error type names', () => {
      const errorProps = {
        ...healthyProps,
        pipelineErrors: { some_complex_error_type: 5 },
      };
      render(<PipelineHealthPanel {...errorProps} />);
      expect(screen.getByText('some complex error type')).toBeInTheDocument();
    });
  });

  describe('combined error states', () => {
    it('displays all error sections when all have values', () => {
      const allErrorsProps = {
        ...healthyProps,
        pipelineErrors: { detection_error: 5 },
        queueOverflows: { detection_queue: 10 },
        dlqItems: { 'dlq:detection_queue': 3 },
      };
      render(<PipelineHealthPanel {...allErrorsProps} />);

      expect(screen.getByText('Pipeline Errors')).toBeInTheDocument();
      expect(screen.getByText('Queue Overflows')).toBeInTheDocument();
      expect(screen.getByText('Dead Letter Queue')).toBeInTheDocument();
    });

    it('displays only errors section when only errors exist', () => {
      const onlyErrorsProps = {
        ...healthyProps,
        pipelineErrors: { detection_error: 5 },
        queueOverflows: {},
        dlqItems: {},
      };
      render(<PipelineHealthPanel {...onlyErrorsProps} />);

      expect(screen.getByText('Pipeline Errors')).toBeInTheDocument();
      expect(screen.queryByText('Queue Overflows')).not.toBeInTheDocument();
      expect(screen.queryByText('Dead Letter Queue')).not.toBeInTheDocument();
    });

    it('displays only DLQ section when only DLQ has items', () => {
      const onlyDlqProps = {
        ...healthyProps,
        pipelineErrors: {},
        queueOverflows: {},
        dlqItems: { 'dlq:detection_queue': 3 },
      };
      render(<PipelineHealthPanel {...onlyDlqProps} />);

      expect(screen.queryByText('Pipeline Errors')).not.toBeInTheDocument();
      expect(screen.queryByText('Queue Overflows')).not.toBeInTheDocument();
      expect(screen.getByText('Dead Letter Queue')).toBeInTheDocument();
    });
  });

  describe('edge cases', () => {
    it('handles empty error objects correctly', () => {
      render(<PipelineHealthPanel {...healthyProps} />);
      expect(screen.getByTestId('all-clear-card')).toBeInTheDocument();
    });

    it('handles zero queue depths', () => {
      const zeroQueueProps = {
        ...healthyProps,
        detectionQueueDepth: 0,
        analysisQueueDepth: 0,
      };
      render(<PipelineHealthPanel {...zeroQueueProps} />);
      expect(screen.getAllByText('0 items').length).toBe(2);
      expect(screen.getAllByText('Healthy').length).toBe(2);
    });

    it('handles boundary value for moderate load (exactly 10)', () => {
      const boundaryProps = {
        ...healthyProps,
        detectionQueueDepth: 10,
        analysisQueueDepth: 9,
      };
      render(<PipelineHealthPanel {...boundaryProps} />);
      expect(screen.getByText('Moderate load')).toBeInTheDocument();
      expect(screen.getByText('Healthy')).toBeInTheDocument();
    });

    it('handles boundary value for backlog (exactly 50)', () => {
      const boundaryProps = {
        ...healthyProps,
        detectionQueueDepth: 50,
        analysisQueueDepth: 49,
      };
      render(<PipelineHealthPanel {...boundaryProps} />);
      expect(screen.getByText('Queue backlog detected')).toBeInTheDocument();
      expect(screen.getByText('Moderate load')).toBeInTheDocument();
    });
  });

  describe('QueueDepthCard component', () => {
    it('displays correct badge for each queue depth level', () => {
      const props = {
        ...healthyProps,
        detectionQueueDepth: 5,
        analysisQueueDepth: 25,
      };
      render(<PipelineHealthPanel {...props} />);

      // Check both queues have their badges
      expect(screen.getByText('5 items')).toBeInTheDocument();
      expect(screen.getByText('25 items')).toBeInTheDocument();
    });
  });
});

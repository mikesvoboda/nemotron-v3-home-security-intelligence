/**
 * Tests for AIPerformanceSummaryRow component
 *
 * Tests the summary row display including indicators for RT-DETRv2, Nemotron,
 * queue depths, throughput, and errors. Covers threshold-based color coding,
 * tooltips, click-to-scroll behavior, and responsive layout.
 */

import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import AIPerformanceSummaryRow from './AIPerformanceSummaryRow';

import type { AIModelStatus } from '../../hooks/useAIMetrics';
import type { AILatencyMetrics } from '../../services/metricsParser';

// Default test data
const healthyRtdetr: AIModelStatus = {
  name: 'RT-DETRv2',
  status: 'healthy',
};

const healthyNemotron: AIModelStatus = {
  name: 'Nemotron',
  status: 'healthy',
};

const fastDetectionLatency: AILatencyMetrics = {
  avg_ms: 14,
  p50_ms: 12,
  p95_ms: 28,
  p99_ms: 45,
  sample_count: 1000,
};

const fastAnalysisLatency: AILatencyMetrics = {
  avg_ms: 2100,
  p50_ms: 1800,
  p95_ms: 4200,
  p99_ms: 6000,
  sample_count: 500,
};

// Mock scrollIntoView
const mockScrollIntoView = vi.fn();

beforeEach(() => {
  // Mock scrollIntoView for all elements
  Element.prototype.scrollIntoView = mockScrollIntoView;
});

afterEach(() => {
  mockScrollIntoView.mockClear();
});

describe('AIPerformanceSummaryRow', () => {
  describe('basic rendering', () => {
    it('renders the main container with correct testid', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      expect(screen.getByTestId('ai-summary-row')).toBeInTheDocument();
    });

    it('renders all 5 indicator cards', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      expect(screen.getByTestId('rtdetr-indicator')).toBeInTheDocument();
      expect(screen.getByTestId('nemotron-indicator')).toBeInTheDocument();
      expect(screen.getByTestId('queues-indicator')).toBeInTheDocument();
      expect(screen.getByTestId('throughput-indicator')).toBeInTheDocument();
      expect(screen.getByTestId('errors-indicator')).toBeInTheDocument();
    });

    it('keeps the desktop grid and the rendered card count in step', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const row = screen.getByTestId('ai-summary-row');
      // Every rendered card is an IndicatorCard button carrying data-status;
      // counting them (rather than hardcoding 6) is the point — adding a card
      // must break this by changing the count, not by needing an edit here.
      const cardCount = within(row)
        .getAllByRole('button')
        .filter((b) => b.hasAttribute('data-status')).length;
      expect(cardCount, 'the row renders no cards to divide into columns').toBeGreaterThan(0);
      const lg = Array.from(row.classList)
        .map((c) => /^lg:grid-cols-(\d+)$/.exec(c))
        .find(Boolean);
      const cols = lg ? Number(lg[1]) : 0;

      expect(
        cardCount % cols,
        `${cardCount} cards in a ${cols}-column desktop grid orphans ` +
          `${cardCount % cols} card(s) on a trailing row at 1/${cols} width. ` +
          'When a card is added or removed, the lg:grid-cols-* class must move with it.'
      ).toBe(0);
    });

    it('applies custom className', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
          className="custom-class"
        />
      );
      expect(screen.getByTestId('ai-summary-row')).toHaveClass('custom-class');
    });
  });

  describe('RT-DETRv2 indicator', () => {
    it('displays RT-DETRv2 label', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
    });

    it('displays latency value with checkmark for healthy and fast (<50ms)', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const indicator = screen.getByTestId('rtdetr-indicator');
      expect(indicator).toHaveTextContent('14ms');
    });

    it('shows green status for healthy and <50ms latency', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const indicator = screen.getByTestId('rtdetr-indicator');
      expect(indicator).toHaveAttribute('data-status', 'green');
    });

    it('shows yellow status for healthy and 50-200ms latency', () => {
      const slowDetectionLatency: AILatencyMetrics = {
        avg_ms: 100,
        p50_ms: 80,
        p95_ms: 150,
        p99_ms: 200,
        sample_count: 1000,
      };
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={slowDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const indicator = screen.getByTestId('rtdetr-indicator');
      expect(indicator).toHaveAttribute('data-status', 'yellow');
    });

    it('shows red status for >200ms latency', () => {
      const verySlowDetectionLatency: AILatencyMetrics = {
        avg_ms: 250,
        p50_ms: 220,
        p95_ms: 350,
        p99_ms: 500,
        sample_count: 1000,
      };
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={verySlowDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const indicator = screen.getByTestId('rtdetr-indicator');
      expect(indicator).toHaveAttribute('data-status', 'red');
    });

    it('shows red status when model is unhealthy', () => {
      const unhealthyRtdetr: AIModelStatus = {
        name: 'RT-DETRv2',
        status: 'unhealthy',
        message: 'Connection failed',
      };
      render(
        <AIPerformanceSummaryRow
          rtdetr={unhealthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const indicator = screen.getByTestId('rtdetr-indicator');
      expect(indicator).toHaveAttribute('data-status', 'red');
    });
  });

  describe('Nemotron indicator', () => {
    it('displays Nemotron label', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      expect(screen.getByText('Nemotron')).toBeInTheDocument();
    });

    it('displays latency in seconds for healthy and <5s', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const indicator = screen.getByTestId('nemotron-indicator');
      expect(indicator).toHaveTextContent('2.1s');
    });

    it('shows green status for healthy and <5s latency', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const indicator = screen.getByTestId('nemotron-indicator');
      expect(indicator).toHaveAttribute('data-status', 'green');
    });

    it('shows yellow status for healthy and 5-15s latency', () => {
      const slowAnalysisLatency: AILatencyMetrics = {
        avg_ms: 8000,
        p50_ms: 7000,
        p95_ms: 12000,
        p99_ms: 14000,
        sample_count: 500,
      };
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={slowAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const indicator = screen.getByTestId('nemotron-indicator');
      expect(indicator).toHaveAttribute('data-status', 'yellow');
    });

    it('shows red status for >15s latency', () => {
      const verySlowAnalysisLatency: AILatencyMetrics = {
        avg_ms: 18000,
        p50_ms: 16000,
        p95_ms: 25000,
        p99_ms: 30000,
        sample_count: 500,
      };
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={verySlowAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const indicator = screen.getByTestId('nemotron-indicator');
      expect(indicator).toHaveAttribute('data-status', 'red');
    });
  });

  describe('Queues indicator', () => {
    it('displays Queues label', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      expect(screen.getByText('Queues')).toBeInTheDocument();
    });

    it('displays total queue depth', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={5}
          analysisQueueDepth={3}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const indicator = screen.getByTestId('queues-indicator');
      expect(indicator).toHaveTextContent('8 queued');
    });

    it('shows green status for 0-10 items', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={5}
          analysisQueueDepth={3}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const indicator = screen.getByTestId('queues-indicator');
      expect(indicator).toHaveAttribute('data-status', 'green');
    });

    it('shows yellow status for 11-50 items', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={15}
          analysisQueueDepth={10}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const indicator = screen.getByTestId('queues-indicator');
      expect(indicator).toHaveAttribute('data-status', 'yellow');
    });

    it('shows red status for 50+ items', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={30}
          analysisQueueDepth={25}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const indicator = screen.getByTestId('queues-indicator');
      expect(indicator).toHaveAttribute('data-status', 'red');
    });
  });

  describe('Throughput indicator', () => {
    it('displays Throughput label', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      expect(screen.getByText('Throughput')).toBeInTheDocument();
    });

    it('displays throughput rate per minute', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
          throughputPerMinute={1.2}
        />
      );
      const indicator = screen.getByTestId('throughput-indicator');
      expect(indicator).toHaveTextContent('1.2/min');
    });

    it('shows green status for >0.5/min', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
          throughputPerMinute={1.2}
        />
      );
      const indicator = screen.getByTestId('throughput-indicator');
      expect(indicator).toHaveAttribute('data-status', 'green');
    });

    it('shows yellow status for 0.1-0.5/min', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
          throughputPerMinute={0.3}
        />
      );
      const indicator = screen.getByTestId('throughput-indicator');
      expect(indicator).toHaveAttribute('data-status', 'yellow');
    });

    it('shows red status for <0.1/min', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
          throughputPerMinute={0.05}
        />
      );
      const indicator = screen.getByTestId('throughput-indicator');
      expect(indicator).toHaveAttribute('data-status', 'red');
    });
  });

  describe('Errors indicator', () => {
    it('displays Errors label', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      expect(screen.getByText('Errors')).toBeInTheDocument();
    });

    it('displays error count', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={5}
        />
      );
      const indicator = screen.getByTestId('errors-indicator');
      expect(indicator).toHaveTextContent('5 total');
    });

    it('shows green status for 0 errors', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );
      const indicator = screen.getByTestId('errors-indicator');
      expect(indicator).toHaveAttribute('data-status', 'green');
    });

    it('shows yellow status for 1-49 errors', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={25}
        />
      );
      const indicator = screen.getByTestId('errors-indicator');
      expect(indicator).toHaveAttribute('data-status', 'yellow');
    });

    it('shows red status for 50+ errors', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={50}
        />
      );
      const indicator = screen.getByTestId('errors-indicator');
      expect(indicator).toHaveAttribute('data-status', 'red');
    });
  });

  // F-038: the inventory row promised a "DLQ error count". The hook already
  // fetched GET /api/dlq/stats into dlqItems (useAIMetrics.ts:313, :378); what
  // it never had was a render site — its only reader, ai/PipelineHealthPanel,
  // is not mounted anywhere. These tests pin the card that closes that gap.
  describe('DLQ indicator (F-038)', () => {
    const baseProps = {
      rtdetr: healthyRtdetr,
      nemotron: healthyNemotron,
      detectionLatency: fastDetectionLatency,
      analysisLatency: fastAnalysisLatency,
      detectionQueueDepth: 0,
      analysisQueueDepth: 0,
      totalDetections: 100,
      totalEvents: 50,
      totalErrors: 0,
    };

    it('renders the DLQ card with a zero state when nothing is parked', () => {
      render(<AIPerformanceSummaryRow {...baseProps} dlqCounts={{}} />);
      const card = screen.getByTestId('dlq-indicator');
      expect(screen.getByText('DLQ')).toBeInTheDocument();
      // Zero renders 'None' rather than hiding the card: a hidden card is
      // indistinguishable from a failed fetch.
      expect(card).toHaveTextContent('None');
      expect(card).toHaveAttribute('data-status', 'green');
    });

    it('renders the zero state when the prop is omitted entirely', () => {
      render(<AIPerformanceSummaryRow {...baseProps} />);
      expect(screen.getByTestId('dlq-indicator')).toHaveTextContent('None');
    });

    it('sums the per-queue map the hook builds', () => {
      render(
        <AIPerformanceSummaryRow
          {...baseProps}
          dlqCounts={{ 'dlq:detection_queue': 3, 'dlq:analysis_queue': 2 }}
        />
      );
      expect(screen.getByTestId('dlq-indicator')).toHaveTextContent('5 parked');
    });

    it('colours the first parked job yellow and a backlog red', () => {
      // Stricter than the Errors card on purpose: a parked job is a current
      // condition needing a decision, not a cumulative counter.
      const { unmount } = render(
        <AIPerformanceSummaryRow {...baseProps} dlqCounts={{ 'dlq:detection_queue': 1 }} />
      );
      expect(screen.getByTestId('dlq-indicator')).toHaveAttribute('data-status', 'yellow');
      unmount();
      render(
        <AIPerformanceSummaryRow
          {...baseProps}
          dlqCounts={{ 'dlq:detection_queue': 10, 'dlq:analysis_queue': 0 }}
        />
      );
      expect(screen.getByTestId('dlq-indicator')).toHaveAttribute('data-status', 'red');
    });

    it('names the queues in the tooltip so the total is traceable', async () => {
      render(
        <AIPerformanceSummaryRow
          {...baseProps}
          dlqCounts={{ 'dlq:detection_queue': 4, 'dlq:analysis_queue': 1 }}
        />
      );
      // Same hover idiom as this file's tooltip block: mouseEnter, then assert
      // against role=tooltip itself. (findByText on the heading would resolve
      // to the heading div alone, which never contains the per-queue rows.)
      fireEvent.mouseEnter(screen.getByTestId('dlq-indicator'));
      await waitFor(() => {
        const tooltip = screen.getByRole('tooltip');
        expect(tooltip).toHaveTextContent('Total Parked: 5');
        // The `dlq:` prefix is stripped for humans; the queue names survive.
        expect(tooltip).toHaveTextContent('detection_queue: 4');
        expect(tooltip).toHaveTextContent('analysis_queue: 1');
      });
    });

    it('is reachable by keyboard and describes itself', () => {
      render(<AIPerformanceSummaryRow {...baseProps} dlqCounts={{ 'dlq:detection_queue': 2 }} />);
      const card = screen.getByTestId('dlq-indicator');
      expect(card).toHaveAccessibleName(
        /Dead-letter queues: 2 jobs parked\. Jobs land here after their final retry fails\./
      );
      expect(card).toBeEnabled();
    });
  });

  describe('click-to-scroll behavior', () => {
    it('calls onIndicatorClick when RT-DETRv2 indicator is clicked', async () => {
      const handleClick = vi.fn();
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
          onIndicatorClick={handleClick}
        />
      );

      await userEvent.click(screen.getByTestId('rtdetr-indicator'));
      expect(handleClick).toHaveBeenCalledWith('rtdetr');
    });

    it('calls onIndicatorClick when Queues indicator is clicked', async () => {
      const handleClick = vi.fn();
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
          onIndicatorClick={handleClick}
        />
      );

      await userEvent.click(screen.getByTestId('queues-indicator'));
      expect(handleClick).toHaveBeenCalledWith('queues');
    });

    it('scrolls to element when sectionRefs are provided', async () => {
      const mockRtdetrRef = { current: document.createElement('div') };
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
          sectionRefs={{ rtdetr: mockRtdetrRef }}
        />
      );

      await userEvent.click(screen.getByTestId('rtdetr-indicator'));
      expect(mockScrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth', block: 'start' });
    });
  });

  describe('tooltip behavior', () => {
    it('shows tooltip on hover for RT-DETRv2 indicator', async () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );

      const indicator = screen.getByTestId('rtdetr-indicator');
      fireEvent.mouseEnter(indicator);

      await waitFor(() => {
        expect(screen.getByRole('tooltip')).toBeInTheDocument();
      });
    });

    it('displays detailed metrics in tooltip', async () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );

      const indicator = screen.getByTestId('rtdetr-indicator');
      fireEvent.mouseEnter(indicator);

      await waitFor(() => {
        const tooltip = screen.getByRole('tooltip');
        expect(tooltip).toHaveTextContent(/P95/i);
        expect(tooltip).toHaveTextContent(/P99/i);
      });
    });
  });

  describe('accessibility', () => {
    it('has accessible role for each indicator', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );

      const indicators = screen.getAllByRole('button');
      // 6 as of F-038: the DLQ card joined the row. This render omits
      // dlqCounts, so the count also proves the card renders its zero state
      // rather than disappearing when the hook has nothing to show.
      expect(indicators.length).toBe(6);
    });

    it('has aria-label for each indicator', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );

      expect(screen.getByTestId('rtdetr-indicator')).toHaveAttribute('aria-label');
      expect(screen.getByTestId('nemotron-indicator')).toHaveAttribute('aria-label');
    });

    it('supports keyboard navigation', async () => {
      const handleClick = vi.fn();
      const user = userEvent.setup();
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
          onIndicatorClick={handleClick}
        />
      );

      const indicator = screen.getByTestId('rtdetr-indicator');
      await user.click(indicator);

      expect(handleClick).toHaveBeenCalledWith('rtdetr');
    });
  });

  describe('null/undefined handling', () => {
    it('handles null latency values gracefully', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={null}
          analysisLatency={null}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );

      const rtdetrIndicator = screen.getByTestId('rtdetr-indicator');
      expect(rtdetrIndicator).toHaveTextContent('--');
    });

    it('handles undefined throughput gracefully', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );

      const throughputIndicator = screen.getByTestId('throughput-indicator');
      // When throughput is not provided, it should calculate from totalEvents
      expect(throughputIndicator).toBeInTheDocument();
    });
  });

  describe('responsive layout', () => {
    it('uses grid layout for indicators', () => {
      render(
        <AIPerformanceSummaryRow
          rtdetr={healthyRtdetr}
          nemotron={healthyNemotron}
          detectionLatency={fastDetectionLatency}
          analysisLatency={fastAnalysisLatency}
          detectionQueueDepth={0}
          analysisQueueDepth={0}
          totalDetections={100}
          totalEvents={50}
          totalErrors={0}
        />
      );

      const container = screen.getByTestId('ai-summary-row');
      // Grid layout should be applied via CSS classes
      expect(container).toHaveClass('grid');
    });
  });
});

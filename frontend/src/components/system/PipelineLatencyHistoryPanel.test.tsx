/**
 * Tests for PipelineLatencyHistoryPanel component (NEM-4948)
 *
 * Tests the pipeline latency history chart component including:
 * - Loading, error, and empty states
 * - View mode toggle between stages and percentiles
 * - Chart rendering for both views
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';

import PipelineLatencyHistoryPanel from './PipelineLatencyHistoryPanel';
import * as usePipelineLatencyHistoryModule from '../../hooks/usePipelineLatencyHistory';

// Mock the hook
vi.mock('../../hooks/usePipelineLatencyHistory', () => ({
  usePipelineLatencyHistory: vi.fn(),
}));

// Mock Tremor AreaChart since it requires browser APIs
vi.mock('@tremor/react', () => ({
  Card: ({ children, className, 'data-testid': testId }: { children: React.ReactNode; className?: string; 'data-testid'?: string }) => (
    <div className={className} data-testid={testId}>{children}</div>
  ),
  Title: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <h3 className={className}>{children}</h3>
  ),
  Text: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <p className={className}>{children}</p>
  ),
  AreaChart: ({ 'data-testid': testId, 'aria-label': ariaLabel }: { 'data-testid'?: string; 'aria-label'?: string }) => (
    <div data-testid={testId} aria-label={ariaLabel}>AreaChart Mock</div>
  ),
}));

describe('PipelineLatencyHistoryPanel', () => {
  const mockChartData = [
    {
      timestamp: '10:00',
      watch_to_detect: 150,
      detect_to_batch: 50,
      batch_to_analyze: 500,
      total_pipeline: 700,
    },
    {
      timestamp: '10:01',
      watch_to_detect: 155,
      detect_to_batch: 52,
      batch_to_analyze: 510,
      total_pipeline: 717,
    },
  ];

  const mockPercentileChartData = [
    {
      timestamp: '10:00',
      P50: 635,
      P95: 980,
      P99: 1250,
    },
    {
      timestamp: '10:01',
      P50: 652,
      P95: 997,
      P99: 1267,
    },
  ];

  const mockData = {
    snapshots: [],
    window_minutes: 60,
    bucket_seconds: 60,
    timestamp: '2025-01-31T10:01:00Z',
  };

  const defaultHookReturn = {
    chartData: mockChartData,
    percentileChartData: mockPercentileChartData,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
    data: mockData,
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(usePipelineLatencyHistoryModule.usePipelineLatencyHistory).mockReturnValue(defaultHookReturn);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('rendering', () => {
    it('renders the panel with title', () => {
      render(<PipelineLatencyHistoryPanel />);

      expect(screen.getByTestId('pipeline-latency-history-panel')).toBeInTheDocument();
      expect(screen.getByText('Pipeline Latency History')).toBeInTheDocument();
    });

    it('renders with custom testId', () => {
      render(<PipelineLatencyHistoryPanel data-testid="custom-test-id" />);

      expect(screen.getByTestId('custom-test-id')).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<PipelineLatencyHistoryPanel className="custom-class" />);

      const panel = screen.getByTestId('pipeline-latency-history-panel');
      expect(panel.className).toContain('custom-class');
    });

    it('displays time window and bucket size info', () => {
      render(<PipelineLatencyHistoryPanel />);

      expect(screen.getByText('Last 60 minutes, 60s buckets')).toBeInTheDocument();
    });

    it('renders view mode toggle', () => {
      render(<PipelineLatencyHistoryPanel />);

      expect(screen.getByTestId('pipeline-latency-history-panel-view-toggle')).toBeInTheDocument();
      expect(screen.getByTestId('pipeline-latency-history-panel-view-stages')).toBeInTheDocument();
      expect(screen.getByTestId('pipeline-latency-history-panel-view-percentiles')).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('shows loading indicator when loading with no data', () => {
      vi.mocked(usePipelineLatencyHistoryModule.usePipelineLatencyHistory).mockReturnValue({
        ...defaultHookReturn,
        isLoading: true,
        data: undefined,
      });

      render(<PipelineLatencyHistoryPanel />);

      expect(screen.getByTestId('pipeline-latency-history-panel-loading')).toBeInTheDocument();
    });

    it('shows loading spinner in header while fetching with existing data', () => {
      vi.mocked(usePipelineLatencyHistoryModule.usePipelineLatencyHistory).mockReturnValue({
        ...defaultHookReturn,
        isLoading: true,
      });

      render(<PipelineLatencyHistoryPanel />);

      // Should still show chart, but with loading spinner
      expect(screen.getByTestId('pipeline-latency-history-panel-chart-stages')).toBeInTheDocument();
    });
  });

  describe('error state', () => {
    it('shows error state when there is an error', () => {
      vi.mocked(usePipelineLatencyHistoryModule.usePipelineLatencyHistory).mockReturnValue({
        ...defaultHookReturn,
        error: new Error('Test error'),
      });

      render(<PipelineLatencyHistoryPanel />);

      expect(screen.getByTestId('pipeline-latency-history-panel-error')).toBeInTheDocument();
      expect(screen.getByText('Failed to load pipeline latency history')).toBeInTheDocument();
    });

    it('shows retry button in error state', () => {
      const mockRefetch = vi.fn();
      vi.mocked(usePipelineLatencyHistoryModule.usePipelineLatencyHistory).mockReturnValue({
        ...defaultHookReturn,
        error: new Error('Test error'),
        refetch: mockRefetch,
      });

      render(<PipelineLatencyHistoryPanel />);

      const retryButton = screen.getByTestId('pipeline-latency-history-panel-retry');
      expect(retryButton).toBeInTheDocument();

      fireEvent.click(retryButton);
      expect(mockRefetch).toHaveBeenCalled();
    });
  });

  describe('empty state', () => {
    it('shows empty state when no data is available', () => {
      vi.mocked(usePipelineLatencyHistoryModule.usePipelineLatencyHistory).mockReturnValue({
        ...defaultHookReturn,
        chartData: [],
        percentileChartData: [],
      });

      render(<PipelineLatencyHistoryPanel />);

      expect(screen.getByTestId('pipeline-latency-history-panel-empty')).toBeInTheDocument();
      expect(screen.getByText('No pipeline latency data available')).toBeInTheDocument();
    });
  });

  describe('view mode toggle', () => {
    it('defaults to stages view', () => {
      render(<PipelineLatencyHistoryPanel />);

      expect(screen.getByTestId('pipeline-latency-history-panel-chart-stages')).toBeInTheDocument();
      expect(screen.queryByTestId('pipeline-latency-history-panel-chart-percentiles')).not.toBeInTheDocument();
    });

    it('can start with percentiles view when initialViewMode is set', () => {
      render(<PipelineLatencyHistoryPanel initialViewMode="percentiles" />);

      expect(screen.getByTestId('pipeline-latency-history-panel-chart-percentiles')).toBeInTheDocument();
      expect(screen.queryByTestId('pipeline-latency-history-panel-chart-stages')).not.toBeInTheDocument();
    });

    it('switches to percentiles view when percentiles button is clicked', async () => {
      render(<PipelineLatencyHistoryPanel />);

      // Initially shows stages view
      expect(screen.getByTestId('pipeline-latency-history-panel-chart-stages')).toBeInTheDocument();

      // Click percentiles button
      fireEvent.click(screen.getByTestId('pipeline-latency-history-panel-view-percentiles'));

      // Now shows percentiles view
      await waitFor(() => {
        expect(screen.getByTestId('pipeline-latency-history-panel-chart-percentiles')).toBeInTheDocument();
      });
      expect(screen.queryByTestId('pipeline-latency-history-panel-chart-stages')).not.toBeInTheDocument();
    });

    it('switches back to stages view when stages button is clicked', async () => {
      render(<PipelineLatencyHistoryPanel initialViewMode="percentiles" />);

      // Initially shows percentiles view
      expect(screen.getByTestId('pipeline-latency-history-panel-chart-percentiles')).toBeInTheDocument();

      // Click stages button
      fireEvent.click(screen.getByTestId('pipeline-latency-history-panel-view-stages'));

      // Now shows stages view
      await waitFor(() => {
        expect(screen.getByTestId('pipeline-latency-history-panel-chart-stages')).toBeInTheDocument();
      });
      expect(screen.queryByTestId('pipeline-latency-history-panel-chart-percentiles')).not.toBeInTheDocument();
    });

    it('sets aria-pressed correctly on toggle buttons', () => {
      render(<PipelineLatencyHistoryPanel />);

      const stagesButton = screen.getByTestId('pipeline-latency-history-panel-view-stages');
      const percentilesButton = screen.getByTestId('pipeline-latency-history-panel-view-percentiles');

      expect(stagesButton).toHaveAttribute('aria-pressed', 'true');
      expect(percentilesButton).toHaveAttribute('aria-pressed', 'false');

      fireEvent.click(percentilesButton);

      expect(stagesButton).toHaveAttribute('aria-pressed', 'false');
      expect(percentilesButton).toHaveAttribute('aria-pressed', 'true');
    });
  });

  describe('chart accessibility', () => {
    it('stages chart has proper aria-label', () => {
      render(<PipelineLatencyHistoryPanel />);

      const chart = screen.getByTestId('pipeline-latency-history-panel-chart-stages');
      expect(chart).toHaveAttribute('aria-label', 'Pipeline latency history chart showing stage averages');
    });

    it('percentiles chart has proper aria-label', () => {
      render(<PipelineLatencyHistoryPanel initialViewMode="percentiles" />);

      const chart = screen.getByTestId('pipeline-latency-history-panel-chart-percentiles');
      expect(chart).toHaveAttribute('aria-label', 'Pipeline latency history chart showing P50, P95, and P99 percentiles');
    });
  });

  describe('hook parameters', () => {
    it('passes since and bucket_seconds to hook', () => {
      render(<PipelineLatencyHistoryPanel since={120} bucketSeconds={30} />);

      expect(usePipelineLatencyHistoryModule.usePipelineLatencyHistory).toHaveBeenCalledWith({
        since: 120,
        bucket_seconds: 30,
      });
    });

    it('uses default values when not specified', () => {
      render(<PipelineLatencyHistoryPanel />);

      expect(usePipelineLatencyHistoryModule.usePipelineLatencyHistory).toHaveBeenCalledWith({
        since: 60,
        bucket_seconds: 60,
      });
    });
  });

  describe('data display', () => {
    it('displays custom window and bucket info from data', () => {
      vi.mocked(usePipelineLatencyHistoryModule.usePipelineLatencyHistory).mockReturnValue({
        ...defaultHookReturn,
        data: {
          ...mockData,
          window_minutes: 120,
          bucket_seconds: 30,
        },
      });

      render(<PipelineLatencyHistoryPanel />);

      expect(screen.getByText('Last 120 minutes, 30s buckets')).toBeInTheDocument();
    });
  });
});

/**
 * Tests for AIPerformancePage component
 * Comprehensive test coverage for AI Performance dashboard
 */

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import AIPerformancePage from './AIPerformancePage';
import * as api from '../../services/api';

// Mock the useAIMetrics hook
const mockRefresh = vi.fn();
const mockUseAIMetrics = vi.fn();

vi.mock('../../hooks/useAIMetrics', () => ({
  useAIMetrics: (...args: unknown[]): unknown => mockUseAIMetrics(...args),
  default: (...args: unknown[]): unknown => mockUseAIMetrics(...args),
}));

// Mock child components
vi.mock('../ai-performance/AIPerformanceSummaryRow', () => ({
  default: () => <div data-testid="ai-performance-summary-row">AI Performance Summary Row</div>,
}));

// Mock the fetchConfig and fetchEventStats APIs
vi.mock('../../services/api', () => ({
  fetchConfig: vi.fn(() => Promise.resolve({ grafana_url: 'http://localhost:3002' })),
  fetchEventStats: vi.fn(() =>
    Promise.resolve({
      total_events: 100,
      events_by_risk_level: {
        critical: 5,
        high: 15,
        medium: 30,
        low: 50,
      },
      events_by_camera: [],
    })
  ),
  fetchAiAuditStats: vi.fn(() =>
    Promise.resolve({
      total_events: 1000,
      audited_events: 950,
      fully_evaluated_events: 800,
      avg_quality_score: 4.2,
      avg_consistency_rate: 4.0,
      avg_enrichment_utilization: 0.75,
      model_contribution_rates: {
        rtdetr: 1.0,
        florence: 0.85,
        clip: 0.6,
      },
      audits_by_day: [],
    })
  ),
  fetchModelLeaderboard: vi.fn(() =>
    Promise.resolve({
      entries: [
        { model_name: 'rtdetr', contribution_rate: 1.0, quality_correlation: null, event_count: 1000 },
        { model_name: 'florence', contribution_rate: 0.85, quality_correlation: null, event_count: 850 },
      ],
      period_days: 7,
    })
  ),
}));

// Default mock data for healthy state
const defaultMockData = {
  rtdetr: { name: 'RT-DETRv2', status: 'healthy' as const },
  nemotron: { name: 'Nemotron', status: 'healthy' as const },
  detectionLatency: { avg_ms: 150, p50_ms: 120, p95_ms: 280, p99_ms: 450, sample_count: 1000 },
  analysisLatency: { avg_ms: 2500, p50_ms: 2000, p95_ms: 4500, p99_ms: 8000, sample_count: 500 },
  pipelineLatency: null,
  totalDetections: 50000,
  totalEvents: 12500,
  detectionQueueDepth: 5,
  analysisQueueDepth: 2,
  pipelineErrors: {},
  queueOverflows: {},
  dlqItems: {},
  lastUpdated: new Date().toISOString(),
};

const renderWithRouter = () => {
  return render(
    <MemoryRouter>
      <AIPerformancePage />
    </MemoryRouter>
  );
};

describe('AIPerformancePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default mock implementation
    mockUseAIMetrics.mockReturnValue({
      data: defaultMockData,
      isLoading: false,
      error: null,
      refresh: mockRefresh,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('basic rendering', () => {
    it('renders the page title', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByText('AI Performance')).toBeInTheDocument();
      });
    });

    it('renders the page description', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(
          screen.getByText(/Real-time AI model metrics, latency statistics, and pipeline health/)
        ).toBeInTheDocument();
      });
    });

    it('renders the refresh button', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByTestId('refresh-button')).toBeInTheDocument();
      });
    });

    it('renders the Grafana link banner', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByTestId('grafana-banner')).toBeInTheDocument();
      });
    });

    it('renders the model status cards', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByTestId('model-status-cards')).toBeInTheDocument();
      });
    });

    it('renders RT-DETRv2 status card', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByTestId('rtdetr-status-card')).toBeInTheDocument();
        expect(screen.getByText('RT-DETRv2')).toBeInTheDocument();
      });
    });

    it('renders Nemotron status card', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByTestId('nemotron-status-card')).toBeInTheDocument();
        expect(screen.getByText('Nemotron')).toBeInTheDocument();
      });
    });

    it('renders latency panel', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByTestId('latency-panel')).toBeInTheDocument();
      });
    });

    it('renders pipeline health panel', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByTestId('pipeline-health-panel')).toBeInTheDocument();
      });
    });

    it('has correct data-testid for the page', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByTestId('ai-performance-page')).toBeInTheDocument();
      });
    });

    it('renders insights charts', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByTestId('insights-charts')).toBeInTheDocument();
      });
    });

    it('renders Model Zoo Analytics section', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByTestId('model-zoo-analytics-section')).toBeInTheDocument();
      });
    });

    it('renders Model Zoo Analytics title', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByText('Model Zoo Analytics')).toBeInTheDocument();
      });
    });

    it('renders model contribution chart in Model Zoo Analytics', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByTestId('model-contribution-chart')).toBeInTheDocument();
      });
    });

    it('renders model leaderboard in Model Zoo Analytics', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByTestId('model-leaderboard')).toBeInTheDocument();
      });
    });

    it('renders last updated timestamp', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByText(/Last updated:/)).toBeInTheDocument();
      });
    });
  });

  describe('AIPerformancePage structure', () => {
    it('renders throughput statistics in pipeline health panel', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByTestId('throughput-card')).toBeInTheDocument();
      });
    });

    it('renders queue depths card', async () => {
      renderWithRouter();
      await waitFor(() => {
        expect(screen.getByTestId('queue-depths-card')).toBeInTheDocument();
      });
    });
  });

  describe('loading state', () => {
    it('shows loading skeleton when data is loading and no cached data exists', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: { ...defaultMockData, lastUpdated: null },
        isLoading: true,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('ai-performance-loading')).toBeInTheDocument();
      });
    });

    it('loading skeleton contains animated pulse elements', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: { ...defaultMockData, lastUpdated: null },
        isLoading: true,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        const loadingContainer = screen.getByTestId('ai-performance-loading');
        const pulseElements = loadingContainer.querySelectorAll('.animate-pulse');
        expect(pulseElements.length).toBeGreaterThan(0);
      });
    });

    it('does not show loading skeleton when data exists even during refresh', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: defaultMockData,
        isLoading: true,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        expect(screen.queryByTestId('ai-performance-loading')).not.toBeInTheDocument();
        expect(screen.getByTestId('ai-performance-page')).toBeInTheDocument();
      });
    });
  });

  describe('error states', () => {
    it('shows error banner when error occurs but cached data exists', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: defaultMockData,
        isLoading: false,
        error: 'Failed to fetch metrics',
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('error-banner')).toBeInTheDocument();
        expect(screen.getByText(/Failed to fetch metrics/)).toBeInTheDocument();
      });
    });

    it('shows cached data timestamp in error banner', async () => {
      const fixedTimestamp = '2025-01-15T10:30:00Z';
      mockUseAIMetrics.mockReturnValue({
        data: { ...defaultMockData, lastUpdated: fixedTimestamp },
        isLoading: false,
        error: 'Network error',
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('error-banner')).toBeInTheDocument();
        expect(screen.getByText(/Showing cached data from/)).toBeInTheDocument();
      });
    });

    it('shows full error page when error occurs and no cached data', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: { ...defaultMockData, lastUpdated: null },
        isLoading: false,
        error: 'Connection refused',
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('Failed to Load AI Metrics')).toBeInTheDocument();
        expect(screen.getByText('Connection refused')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /Try Again/i })).toBeInTheDocument();
      });
    });

    it('calls refresh when Try Again button is clicked', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: { ...defaultMockData, lastUpdated: null },
        isLoading: false,
        error: 'Connection failed',
        refresh: mockRefresh,
      });

      const user = userEvent.setup();
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Try Again/i })).toBeInTheDocument();
      });

      const tryAgainButton = screen.getByRole('button', { name: /Try Again/i });
      await user.click(tryAgainButton);

      expect(mockRefresh).toHaveBeenCalled();
    });
  });

  describe('refresh functionality', () => {
    it('calls refresh when refresh button is clicked', async () => {
      const user = userEvent.setup();
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('refresh-button');
      await user.click(refreshButton);

      expect(mockRefresh).toHaveBeenCalled();
    });

    it('disables refresh button while refreshing', async () => {
      const user = userEvent.setup();

      // Create a slow refresh that allows us to check disabled state
      let resolveRefresh: () => void;
      const refreshPromise = new Promise<void>((resolve) => {
        resolveRefresh = resolve;
      });
      mockRefresh.mockReturnValue(refreshPromise);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('refresh-button');
      await user.click(refreshButton);

      // Button should be disabled during refresh
      expect(refreshButton).toBeDisabled();

      // Resolve the refresh
      resolveRefresh!();
      await waitFor(() => {
        expect(refreshButton).not.toBeDisabled();
      });
    });

    it('shows spinning icon while refreshing', async () => {
      const user = userEvent.setup();

      let resolveRefresh: () => void;
      const refreshPromise = new Promise<void>((resolve) => {
        resolveRefresh = resolve;
      });
      mockRefresh.mockReturnValue(refreshPromise);

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('refresh-button')).toBeInTheDocument();
      });

      const refreshButton = screen.getByTestId('refresh-button');
      await user.click(refreshButton);

      // Check for spinning animation class
      const icon = refreshButton.querySelector('svg');
      expect(icon).toHaveClass('animate-spin');

      resolveRefresh!();
      await waitFor(() => {
        const iconAfter = refreshButton.querySelector('svg');
        expect(iconAfter).not.toHaveClass('animate-spin');
      });
    });
  });

  describe('Grafana integration', () => {
    it('renders Grafana link with correct URL', async () => {
      vi.mocked(api.fetchConfig).mockResolvedValue({
        app_name: 'Test App',
        version: '1.0.0',
        retention_days: 30,
        batch_window_seconds: 90,
        batch_idle_timeout_seconds: 30,
        detection_confidence_threshold: 0.5,
        grafana_url: 'http://grafana.example.com',
      });

      renderWithRouter();

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-link');
        expect(grafanaLink).toHaveAttribute('href', 'http://grafana.example.com/d/ai-performance');
      });
    });

    it('uses default Grafana URL when config fetch fails', async () => {
      vi.mocked(api.fetchConfig).mockRejectedValue(new Error('Config fetch failed'));
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      renderWithRouter();

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-link');
        expect(grafanaLink).toHaveAttribute('href', 'http://localhost:3002/d/ai-performance');
      });

      consoleSpy.mockRestore();
    });

    it('Grafana link opens in new tab', async () => {
      renderWithRouter();

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-link');
        expect(grafanaLink).toHaveAttribute('target', '_blank');
        expect(grafanaLink).toHaveAttribute('rel', 'noopener noreferrer');
      });
    });

    it('renders Open Grafana text with external link icon', async () => {
      renderWithRouter();

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-link');
        expect(grafanaLink).toHaveTextContent('Open Grafana');
        // ExternalLink icon should be present as SVG
        expect(grafanaLink.querySelector('svg')).toBeInTheDocument();
      });
    });
  });

  describe('model status display', () => {
    it('displays healthy status for RT-DETRv2', async () => {
      renderWithRouter();

      await waitFor(() => {
        const rtdetrCard = screen.getByTestId('rtdetr-status-card');
        expect(rtdetrCard).toBeInTheDocument();
        expect(within(rtdetrCard).getByTestId('rtdetr-badge')).toHaveTextContent('healthy');
      });
    });

    it('displays healthy status for Nemotron', async () => {
      renderWithRouter();

      await waitFor(() => {
        const nemotronCard = screen.getByTestId('nemotron-status-card');
        expect(nemotronCard).toBeInTheDocument();
        expect(within(nemotronCard).getByTestId('nemotron-badge')).toHaveTextContent('healthy');
      });
    });

    it('displays unhealthy status correctly', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          rtdetr: { name: 'RT-DETRv2', status: 'unhealthy', message: 'Connection refused' },
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        const rtdetrCard = screen.getByTestId('rtdetr-status-card');
        expect(within(rtdetrCard).getByTestId('rtdetr-badge')).toHaveTextContent('unhealthy');
      });
    });

    it('displays degraded status correctly', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          nemotron: { name: 'Nemotron', status: 'degraded', message: 'High latency detected' },
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        const nemotronCard = screen.getByTestId('nemotron-status-card');
        expect(within(nemotronCard).getByTestId('nemotron-badge')).toHaveTextContent('degraded');
      });
    });

    it('displays unknown status correctly', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          rtdetr: { name: 'RT-DETRv2', status: 'unknown' },
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        const rtdetrCard = screen.getByTestId('rtdetr-status-card');
        expect(within(rtdetrCard).getByTestId('rtdetr-badge')).toHaveTextContent('unknown');
      });
    });

    it('displays latency metrics in model cards', async () => {
      renderWithRouter();

      await waitFor(() => {
        const rtdetrCard = screen.getByTestId('rtdetr-status-card');
        // Check for latency values
        expect(within(rtdetrCard).getByText('150ms')).toBeInTheDocument();
        expect(within(rtdetrCard).getByText('280ms')).toBeInTheDocument();
        expect(within(rtdetrCard).getByText('450ms')).toBeInTheDocument();
      });
    });

    it('displays sample count in model cards', async () => {
      renderWithRouter();

      await waitFor(() => {
        const rtdetrCard = screen.getByTestId('rtdetr-status-card');
        expect(within(rtdetrCard).getByText('1,000 samples')).toBeInTheDocument();
      });
    });
  });

  describe('latency panel display', () => {
    it('displays AI Service Latency card', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('ai-latency-card')).toBeInTheDocument();
        expect(screen.getByText('AI Service Latency')).toBeInTheDocument();
      });
    });

    it('displays RT-DETRv2 Detection latency stats', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('RT-DETRv2 Detection')).toBeInTheDocument();
      });
    });

    it('displays Nemotron Analysis latency stats', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('Nemotron Analysis')).toBeInTheDocument();
      });
    });

    it('shows "No data available" when latency is null', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          detectionLatency: null,
          analysisLatency: null,
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        const noDataElements = screen.getAllByText('No data available');
        expect(noDataElements.length).toBeGreaterThanOrEqual(2);
      });
    });

    it('displays pipeline latency card when data is available', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          pipelineLatency: {
            watch_to_detect: { avg_ms: 50, p50_ms: 45, p95_ms: 80, p99_ms: 100, sample_count: 100 },
            detect_to_batch: { avg_ms: 150, p50_ms: 140, p95_ms: 200, p99_ms: 250, sample_count: 100 },
            batch_to_analyze: { avg_ms: 75, p50_ms: 70, p95_ms: 90, p99_ms: 120, sample_count: 100 },
            total_pipeline: { avg_ms: 275, p50_ms: 255, p95_ms: 370, p99_ms: 470, sample_count: 100 },
            window_minutes: 60,
            timestamp: new Date().toISOString(),
          },
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('pipeline-latency-card')).toBeInTheDocument();
        expect(screen.getByText('Pipeline Stage Latency')).toBeInTheDocument();
      });
    });

    it('displays Total Pipeline stats when available', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          pipelineLatency: {
            watch_to_detect: { avg_ms: 50, p50_ms: 45, p95_ms: 80, p99_ms: 100, sample_count: 100 },
            detect_to_batch: { avg_ms: 150, p50_ms: 140, p95_ms: 200, p99_ms: 250, sample_count: 100 },
            batch_to_analyze: { avg_ms: 75, p50_ms: 70, p95_ms: 90, p99_ms: 120, sample_count: 100 },
            total_pipeline: { avg_ms: 275, p50_ms: 255, p95_ms: 370, p99_ms: 470, sample_count: 100 },
            window_minutes: 60,
            timestamp: new Date().toISOString(),
          },
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        // Use getAllByText since 'Total Pipeline' appears in dropdown and display
        const elements = screen.getAllByText('Total Pipeline');
        expect(elements.length).toBeGreaterThan(0);
      });
    });
  });

  describe('pipeline health panel display', () => {
    it('displays Queue Depths card with detection queue', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('queue-depths-card')).toBeInTheDocument();
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });
    });

    it('displays Queue Depths card with analysis queue', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('Analysis Queue')).toBeInTheDocument();
      });
    });

    it('displays throughput card with total detections', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('throughput-card')).toBeInTheDocument();
        expect(screen.getByText('Total Detections')).toBeInTheDocument();
        // 50000 is formatted as 50.0K
        expect(screen.getByText('50.0K')).toBeInTheDocument();
      });
    });

    it('displays throughput card with total events', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('Total Events')).toBeInTheDocument();
        // 12500 is formatted as 12.5K
        const throughputCard = screen.getByTestId('throughput-card');
        expect(within(throughputCard).getByText('12.5K')).toBeInTheDocument();
      });
    });

    it('displays healthy pipeline status when no errors', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('all-clear-card')).toBeInTheDocument();
        expect(screen.getByText('Pipeline Healthy')).toBeInTheDocument();
      });
    });

    it('displays errors card when pipeline errors exist', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          pipelineErrors: { detection_timeout: 5, analysis_error: 3 },
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('errors-card')).toBeInTheDocument();
        expect(screen.getByText('Pipeline Errors')).toBeInTheDocument();
      });
    });

    it('displays DLQ items when present', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          dlqItems: { detection_queue: 10, analysis_queue: 5 },
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('Dead Letter Queue')).toBeInTheDocument();
        expect(screen.getByText('15 items')).toBeInTheDocument();
      });
    });

    it('displays queue overflows when present', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          queueOverflows: { detection_queue: 3 },
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByText('Queue Overflows')).toBeInTheDocument();
      });
    });

    it('hides errors card when all error counts are zero', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          pipelineErrors: {},
          queueOverflows: {},
          dlqItems: {},
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        expect(screen.queryByTestId('errors-card')).not.toBeInTheDocument();
        expect(screen.getByTestId('all-clear-card')).toBeInTheDocument();
      });
    });
  });

  describe('hook configuration', () => {
    it('passes correct polling configuration to useAIMetrics', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(mockUseAIMetrics).toHaveBeenCalledWith({
          pollingInterval: 5000,
          enablePolling: true,
        });
      });
    });
  });

  describe('edge cases', () => {
    it('handles zero throughput values', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          totalDetections: 0,
          totalEvents: 0,
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        const zeros = screen.getAllByText('0');
        expect(zeros.length).toBeGreaterThanOrEqual(2);
      });
    });

    it('handles very large throughput values', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          totalDetections: 5000000,
          totalEvents: 1500000,
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        const throughputCard = screen.getByTestId('throughput-card');
        // 5000000 formatted as 5.0M
        expect(within(throughputCard).getByText('5.0M')).toBeInTheDocument();
        // 1500000 formatted as 1.5M
        expect(within(throughputCard).getByText('1.5M')).toBeInTheDocument();
      });
    });

    it('handles empty latency sample counts', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          detectionLatency: { avg_ms: 150, p50_ms: 120, p95_ms: 280, p99_ms: 450, sample_count: 0 },
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('ai-performance-page')).toBeInTheDocument();
      });
    });

    it('handles high queue depths with correct styling', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          detectionQueueDepth: 75,
          analysisQueueDepth: 60,
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        // Both queues show backlog - use getAllByText since there are multiple matches
        const backlogMessages = screen.getAllByText('Queue backlog detected');
        expect(backlogMessages.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('handles moderate queue depths with correct message', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          detectionQueueDepth: 25,
          analysisQueueDepth: 15,
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getAllByText('Moderate load').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('handles healthy queue depths with correct message', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          detectionQueueDepth: 3,
          analysisQueueDepth: 1,
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getAllByText('Healthy').length).toBeGreaterThanOrEqual(2);
      });
    });
  });

  describe('accessibility', () => {
    it('refresh button has accessible name', async () => {
      renderWithRouter();

      await waitFor(() => {
        const refreshButton = screen.getByTestId('refresh-button');
        expect(refreshButton).toHaveTextContent('Refresh');
      });
    });

    it('Grafana link has accessible name', async () => {
      renderWithRouter();

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-link');
        expect(grafanaLink).toHaveTextContent('Open Grafana');
      });
    });

    it('page has semantic heading structure', async () => {
      renderWithRouter();

      await waitFor(() => {
        const heading = screen.getByRole('heading', { level: 1 });
        expect(heading).toHaveTextContent('AI Performance');
      });
    });

    it('cards have data-testid for identification', async () => {
      renderWithRouter();

      await waitFor(() => {
        expect(screen.getByTestId('rtdetr-status-card')).toBeInTheDocument();
        expect(screen.getByTestId('nemotron-status-card')).toBeInTheDocument();
        expect(screen.getByTestId('latency-panel')).toBeInTheDocument();
        expect(screen.getByTestId('pipeline-health-panel')).toBeInTheDocument();
      });
    });
  });

  describe('data formatting', () => {
    it('formats milliseconds correctly for small values', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          detectionLatency: { avg_ms: 0.5, p50_ms: 0.3, p95_ms: 0.8, p99_ms: 0.9, sample_count: 100 },
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        expect(screen.getAllByText('< 1ms').length).toBeGreaterThanOrEqual(1);
      });
    });

    it('formats seconds correctly for large values', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          analysisLatency: { avg_ms: 5000, p50_ms: 4500, p95_ms: 8000, p99_ms: 12000, sample_count: 100 },
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        // formatMs uses toFixed(1) for seconds: 5000ms -> 5.0s
        expect(screen.getByText('5.0s')).toBeInTheDocument();
        expect(screen.getByText('12.0s')).toBeInTheDocument();
      });
    });

    it('formats very large latencies as minutes', async () => {
      mockUseAIMetrics.mockReturnValue({
        data: {
          ...defaultMockData,
          analysisLatency: { avg_ms: 120000, p50_ms: 100000, p95_ms: 150000, p99_ms: 180000, sample_count: 100 },
        },
        isLoading: false,
        error: null,
        refresh: mockRefresh,
      });

      renderWithRouter();

      await waitFor(() => {
        // formatMs uses toFixed(1) for minutes: 120000ms -> 2.0m
        expect(screen.getByText('2.0m')).toBeInTheDocument();
      });
    });
  });
});

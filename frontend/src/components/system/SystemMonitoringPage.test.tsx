import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest';

import SystemMonitoringPage from './SystemMonitoringPage';
import * as useHealthStatusHook from '../../hooks/useHealthStatus';
import * as useModelZooStatusHook from '../../hooks/useModelZooStatus';
import * as usePerformanceMetricsHook from '../../hooks/usePerformanceMetrics';
import * as api from '../../services/api';

// Mock the API and hooks
vi.mock('../../services/api');
vi.mock('../../hooks/useHealthStatus');
vi.mock('../../hooks/usePerformanceMetrics');
vi.mock('../../hooks/useModelZooStatus');

// Mock child components
vi.mock('../dashboard/GpuStats', () => ({
  default: ({
    utilization,
    memoryUsed,
    temperature,
    inferenceFps,
  }: {
    utilization: number | null;
    memoryUsed: number | null;
    temperature: number | null;
    inferenceFps: number | null;
  }) => (
    <div
      data-testid="gpu-stats"
      data-utilization={utilization}
      data-memory-used={memoryUsed}
      data-temperature={temperature}
      data-inference-fps={inferenceFps}
    >
      GPU Stats
    </div>
  ),
}));

vi.mock('./PipelineMetricsPanel', () => ({
  default: ({
    queues,
    latencies,
  }: {
    queues: { detection_queue: number; analysis_queue: number };
    latencies?: { detect?: { avg_ms: number }; analyze?: { avg_ms: number } } | null;
  }) => (
    <div
      data-testid="pipeline-metrics-panel"
      data-detection-queue={queues.detection_queue}
      data-analysis-queue={queues.analysis_queue}
      data-detect-latency={latencies?.detect?.avg_ms}
      data-analyze-latency={latencies?.analyze?.avg_ms}
    >
      Pipeline Metrics Panel
    </div>
  ),
}));

// Mock WorkerStatusPanel to avoid API calls during tests
vi.mock('./WorkerStatusPanel', () => ({
  default: () => <div data-testid="worker-status-panel">Worker Status Panel</div>,
}));

// Mock performance dashboard components
vi.mock('./TimeRangeSelector', () => ({
  default: ({ selectedRange }: { selectedRange: string }) => (
    <div data-testid="time-range-selector" data-selected-range={selectedRange}>
      Time Range Selector
    </div>
  ),
}));

vi.mock('./PerformanceAlerts', () => ({
  default: ({ alerts }: { alerts: unknown[] }) => (
    <div data-testid="performance-alerts" data-alert-count={alerts.length}>
      Performance Alerts
    </div>
  ),
}));

vi.mock('./AiModelsPanel', () => ({
  default: () => <div data-testid="ai-models-panel">AI Models Panel</div>,
}));

vi.mock('./DatabasesPanel', () => ({
  default: () => <div data-testid="databases-panel">Databases Panel</div>,
}));

vi.mock('./HostSystemPanel', () => ({
  default: () => <div data-testid="host-system-panel">Host System Panel</div>,
}));

vi.mock('./ContainersPanel', () => ({
  default: () => <div data-testid="containers-panel">Containers Panel</div>,
}));

vi.mock('./CircuitBreakerPanel', () => ({
  default: () => <div data-testid="circuit-breaker-panel">Circuit Breaker Panel</div>,
}));

// Mock SystemSummaryRow to avoid rendering actual component
vi.mock('./SystemSummaryRow', () => ({
  default: () => <div data-testid="system-summary-row">System Summary Row</div>,
}));

// Mock PipelineFlowVisualization to avoid rendering actual component
vi.mock('./PipelineFlowVisualization', () => ({
  default: () => <div data-testid="pipeline-flow-visualization">Pipeline Flow Visualization</div>,
}));

// Mock InfrastructureStatusGrid to avoid rendering actual component
vi.mock('./InfrastructureStatusGrid', () => ({
  default: () => <div data-testid="infrastructure-status-grid">Infrastructure Status Grid</div>,
}));

// SeverityConfigPanel was moved to Settings page (NEM-1142)
// PipelineTelemetry was removed in favor of PipelineMetricsPanel

describe('SystemMonitoringPage', () => {
  const mockSystemStats = {
    total_cameras: 4,
    total_events: 156,
    total_detections: 892,
    uptime_seconds: 86400, // 1 day
  };

  const mockTelemetry = {
    queues: {
      detection_queue: 5,
      analysis_queue: 2,
    },
    latencies: {
      detect: {
        avg_ms: 200,
        p95_ms: 350,
        p99_ms: 500,
      },
      analyze: {
        avg_ms: 1500,
        p95_ms: 2500,
        p99_ms: 3500,
      },
    },
    timestamp: '2025-01-01T12:00:00Z',
  };

  const mockGPUStats = {
    utilization: 75,
    memory_used: 8192,
    memory_total: 24576,
    temperature: 65,
    inference_fps: 30,
  };

  const mockHealthResponse = {
    status: 'healthy',
    services: {
      database: { status: 'healthy', message: 'Connected' },
      redis: { status: 'healthy', message: 'Connected' },
      rtdetr_server: { status: 'healthy', message: 'Running' },
      nemotron_server: { status: 'degraded', message: 'High latency' },
    },
    timestamp: '2025-01-01T12:00:00Z',
  };

  beforeEach(() => {
    vi.clearAllMocks();

    // Setup default mock implementations
    (api.fetchStats as Mock).mockResolvedValue(mockSystemStats);
    (api.fetchTelemetry as Mock).mockResolvedValue(mockTelemetry);
    (api.fetchGPUStats as Mock).mockResolvedValue(mockGPUStats);

    // Mock fetchConfig for config API (default to URL in config)
    (api.fetchConfig as Mock).mockResolvedValue({
      app_name: 'Home Security Intelligence',
      version: '0.1.0',
      retention_days: 30,
      batch_window_seconds: 90,
      batch_idle_timeout_seconds: 30,
      detection_confidence_threshold: 0.5,
      grafana_url: 'http://localhost:3002',
    });

    // Mock circuit breakers API
    (api.fetchCircuitBreakers as Mock).mockResolvedValue({
      circuit_breakers: {
        rtdetr_detection: {
          name: 'rtdetr_detection',
          state: 'closed',
          failure_count: 0,
          success_count: 10,
          total_calls: 100,
          rejected_calls: 0,
          config: { failure_threshold: 5, recovery_timeout: 60, half_open_max_calls: 3, success_threshold: 2 },
        },
      },
      total_count: 1,
      open_count: 0,
      timestamp: '2025-01-01T12:00:00Z',
    });

    // Mock reset circuit breaker API
    (api.resetCircuitBreaker as Mock).mockResolvedValue({
      name: 'test',
      previous_state: 'open',
      new_state: 'closed',
      message: 'Reset successful',
    });

    // SeverityConfigPanel was moved to Settings page (NEM-1142)
    // fetchSeverityMetadata mock removed


    (useHealthStatusHook.useHealthStatus as Mock).mockReturnValue({
      health: mockHealthResponse,
      services: mockHealthResponse.services,
      overallStatus: 'healthy',
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });

    // Setup mock for usePerformanceMetrics
    (usePerformanceMetricsHook.usePerformanceMetrics as Mock).mockReturnValue({
      current: {
        timestamp: '2025-01-01T12:00:00Z',
        gpu: {
          name: 'NVIDIA RTX A5500',
          utilization: 75,
          vram_used_gb: 8,
          vram_total_gb: 24,
          temperature: 65,
          power_watts: 200,
        },
        ai_models: {},
        nemotron: null,
        inference: null,
        databases: {},
        host: null,
        containers: [],
        alerts: [],
      },
      history: {
        '5m': [],
        '15m': [],
        '60m': [],
      },
      alerts: [],
      isConnected: true,
      timeRange: '5m',
      setTimeRange: vi.fn(),
    });

    // Setup mock for useModelZooStatus
    (useModelZooStatusHook.useModelZooStatus as Mock).mockReturnValue({
      models: [],
      vramStats: null,
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
  });

  describe('Loading State', () => {
    it('renders loading skeletons while fetching initial data', () => {
      // Make API call hang
      (api.fetchStats as Mock).mockImplementation(() => new Promise(() => {}));
      (api.fetchTelemetry as Mock).mockImplementation(() => new Promise(() => {}));
      (api.fetchGPUStats as Mock).mockImplementation(() => new Promise(() => {}));

      render(<SystemMonitoringPage />);

      expect(screen.getByTestId('system-monitoring-loading')).toBeInTheDocument();

      // Check for loading skeletons
      const skeletons = screen
        .getAllByRole('generic')
        .filter((el) => el.className.includes('animate-pulse'));
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('renders loading state when health status is loading', () => {
      (useHealthStatusHook.useHealthStatus as Mock).mockReturnValue({
        health: null,
        services: {},
        overallStatus: null,
        isLoading: true,
        error: null,
        refresh: vi.fn(),
      });

      render(<SystemMonitoringPage />);

      expect(screen.getByTestId('system-monitoring-loading')).toBeInTheDocument();
    });

    it('loading state has correct background color', () => {
      (api.fetchStats as Mock).mockImplementation(() => new Promise(() => {}));

      const { container } = render(<SystemMonitoringPage />);
      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass('bg-[#121212]');
    });
  });

  describe('Error State', () => {
    it('renders error message when API fails', async () => {
      const errorMessage = 'Failed to fetch system data';
      (api.fetchStats as Mock).mockRejectedValue(new Error(errorMessage));

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('system-monitoring-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Error Loading System Data')).toBeInTheDocument();
      expect(screen.getByText(errorMessage)).toBeInTheDocument();
    });

    it('renders reload button in error state', async () => {
      (api.fetchStats as Mock).mockRejectedValue(new Error('API Error'));

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /reload page/i })).toBeInTheDocument();
      });
    });

    it('error state has correct styling', async () => {
      (api.fetchStats as Mock).mockRejectedValue(new Error('API Error'));

      const { container } = render(<SystemMonitoringPage />);

      await waitFor(() => {
        const errorContainer = container.querySelector('.bg-red-500\\/10');
        expect(errorContainer).toBeInTheDocument();
      });
    });
  });

  describe('Successful Render', () => {
    it('renders page header with title', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /system monitoring/i })).toBeInTheDocument();
      });
    });

    it('renders subtitle with correct text', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(
          screen.getByText(/real-time system metrics, service health, and pipeline performance/i)
        ).toBeInTheDocument();
      });
    });

    it('renders the page with correct test id', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('system-monitoring-page')).toBeInTheDocument();
      });
    });

    it('renders all main sections', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('system-overview-card')).toBeInTheDocument();
        expect(screen.getByTestId('service-health-card')).toBeInTheDocument();
        expect(screen.getByTestId('pipeline-metrics-panel')).toBeInTheDocument();
        expect(screen.getByTestId('gpu-stats')).toBeInTheDocument();
      });
    });
  });

  describe('System Overview Card', () => {
    it('displays uptime correctly', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        // 86400 seconds = 1 day = "1d"
        expect(screen.getByText('1d')).toBeInTheDocument();
      });
    });

    it('displays uptime with hours and minutes', async () => {
      (api.fetchStats as Mock).mockResolvedValue({
        ...mockSystemStats,
        uptime_seconds: 3723, // 1h 2m 3s
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByText('1h 2m')).toBeInTheDocument();
      });
    });

    it('displays uptime for very short time', async () => {
      (api.fetchStats as Mock).mockResolvedValue({
        ...mockSystemStats,
        uptime_seconds: 30, // 30 seconds
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByText('< 1m')).toBeInTheDocument();
      });
    });

    it('displays total cameras count', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        // Total cameras count appears next to the "Cameras" label (compact layout)
        const systemOverviewCard = screen.getByTestId('system-overview-card');
        expect(systemOverviewCard).toHaveTextContent('Cameras');
        expect(systemOverviewCard).toHaveTextContent('4');
      });
    });

    it('displays total events count', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByText('156')).toBeInTheDocument();
      });
    });

    it('displays total detections count', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByText('892')).toBeInTheDocument();
      });
    });
  });

  describe('Service Health Card', () => {
    it('displays overall health badge', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('overall-health-badge')).toBeInTheDocument();
        expect(screen.getByTestId('overall-health-badge')).toHaveTextContent('Healthy');
      });
    });

    it('displays all service statuses', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('service-row-database')).toBeInTheDocument();
        expect(screen.getByTestId('service-row-redis')).toBeInTheDocument();
        expect(screen.getByTestId('service-row-rtdetr_server')).toBeInTheDocument();
        expect(screen.getByTestId('service-row-nemotron_server')).toBeInTheDocument();
      });
    });

    it('formats service names correctly', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByText('Database')).toBeInTheDocument();
        expect(screen.getByText('Redis')).toBeInTheDocument();
        expect(screen.getByText('Rtdetr Server')).toBeInTheDocument();
        expect(screen.getByText('Nemotron Server')).toBeInTheDocument();
      });
    });

    it('shows degraded service with warning styling', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const nemotronRow = screen.getByTestId('service-row-nemotron_server');
        expect(nemotronRow).toHaveClass('bg-yellow-500/10');
      });
    });

    it('displays last checked timestamp', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByText(/last checked:/i)).toBeInTheDocument();
      });
    });

    it('shows message when no services available', async () => {
      (useHealthStatusHook.useHealthStatus as Mock).mockReturnValue({
        health: { status: 'healthy', services: {}, timestamp: '2025-01-01T12:00:00Z' },
        services: {},
        overallStatus: 'healthy',
        isLoading: false,
        error: null,
        refresh: vi.fn(),
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByText('No service data available')).toBeInTheDocument();
      });
    });

    it('shows error message when health API fails', async () => {
      const errorMessage = 'Connection refused';
      (useHealthStatusHook.useHealthStatus as Mock).mockReturnValue({
        health: null,
        services: {},
        overallStatus: null,
        isLoading: false,
        error: errorMessage,
        refresh: vi.fn(),
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(
          screen.getByText(`Failed to fetch service health: ${errorMessage}`)
        ).toBeInTheDocument();
      });
    });
  });

  describe('Pipeline Metrics Component', () => {
    it('passes correct queue depths to PipelineMetricsPanel', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const pipelineMetrics = screen.getByTestId('pipeline-metrics-panel');
        expect(pipelineMetrics).toHaveAttribute('data-detection-queue', '5');
        expect(pipelineMetrics).toHaveAttribute('data-analysis-queue', '2');
      });
    });

    it('handles missing telemetry data gracefully', async () => {
      (api.fetchTelemetry as Mock).mockResolvedValue({
        queues: {
          detection_queue: 0,
          analysis_queue: 0,
        },
        timestamp: '2025-01-01T12:00:00Z',
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const pipelineMetrics = screen.getByTestId('pipeline-metrics-panel');
        expect(pipelineMetrics).toHaveAttribute('data-detection-queue', '0');
        expect(pipelineMetrics).toHaveAttribute('data-analysis-queue', '0');
      });
    });
  });

  describe('GPU Stats Component', () => {
    it('passes correct props to GpuStats', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const gpuStats = screen.getByTestId('gpu-stats');
        expect(gpuStats).toHaveAttribute('data-utilization', '75');
        expect(gpuStats).toHaveAttribute('data-memory-used', '8192');
        expect(gpuStats).toHaveAttribute('data-temperature', '65');
        expect(gpuStats).toHaveAttribute('data-inference-fps', '30');
      });
    });

    it('handles null GPU stats gracefully', async () => {
      (api.fetchGPUStats as Mock).mockResolvedValue({
        utilization: null,
        memory_used: null,
        memory_total: null,
        temperature: null,
        inference_fps: null,
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const gpuStats = screen.getByTestId('gpu-stats');
        expect(gpuStats).toBeInTheDocument();
      });
    });
  });

  describe('Latency Stats in Pipeline Metrics', () => {
    it('passes latency data to PipelineMetricsPanel', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const pipelineMetrics = screen.getByTestId('pipeline-metrics-panel');
        expect(pipelineMetrics).toHaveAttribute('data-detect-latency', '200');
        expect(pipelineMetrics).toHaveAttribute('data-analyze-latency', '1500');
      });
    });

    it('handles missing latency data gracefully', async () => {
      (api.fetchTelemetry as Mock).mockResolvedValue({
        queues: {
          detection_queue: 5,
          analysis_queue: 2,
        },
        latencies: null,
        timestamp: '2025-01-01T12:00:00Z',
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const pipelineMetrics = screen.getByTestId('pipeline-metrics-panel');
        expect(pipelineMetrics).toBeInTheDocument();
      });
    });
  });

  describe('Data Fetching', () => {
    it('fetches stats, telemetry, and GPU stats on mount', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(api.fetchStats).toHaveBeenCalledTimes(1);
        expect(api.fetchTelemetry).toHaveBeenCalledTimes(1);
        expect(api.fetchGPUStats).toHaveBeenCalledTimes(1);
      });
    });

    it('calls useHealthStatus with correct polling interval', () => {
      render(<SystemMonitoringPage />);

      expect(useHealthStatusHook.useHealthStatus).toHaveBeenCalledWith({
        pollingInterval: 30000,
      });
    });

    it('fetches all APIs in parallel', async () => {
      let statsResolve: () => void;
      let telemetryResolve: () => void;
      let gpuResolve: () => void;

      const statsPromise = new Promise<typeof mockSystemStats>((resolve) => {
        statsResolve = () => resolve(mockSystemStats);
      });

      const telemetryPromise = new Promise<typeof mockTelemetry>((resolve) => {
        telemetryResolve = () => resolve(mockTelemetry);
      });

      const gpuPromise = new Promise<typeof mockGPUStats>((resolve) => {
        gpuResolve = () => resolve(mockGPUStats);
      });

      (api.fetchStats as Mock).mockReturnValue(statsPromise);
      (api.fetchTelemetry as Mock).mockReturnValue(telemetryPromise);
      (api.fetchGPUStats as Mock).mockReturnValue(gpuPromise);

      render(<SystemMonitoringPage />);

      // Resolve all
      statsResolve!();
      telemetryResolve!();
      gpuResolve!();

      await waitFor(() => {
        expect(screen.getByTestId('system-monitoring-page')).toBeInTheDocument();
      });

      // All should be called
      expect(api.fetchStats).toHaveBeenCalledTimes(1);
      expect(api.fetchTelemetry).toHaveBeenCalledTimes(1);
      expect(api.fetchGPUStats).toHaveBeenCalledTimes(1);
    });
  });

  describe('Different Health States', () => {
    it('displays unhealthy status correctly', async () => {
      (useHealthStatusHook.useHealthStatus as Mock).mockReturnValue({
        health: {
          status: 'unhealthy',
          services: {
            database: { status: 'unhealthy', message: 'Connection refused' },
          },
          timestamp: '2025-01-01T12:00:00Z',
        },
        services: {
          database: { status: 'unhealthy', message: 'Connection refused' },
        },
        overallStatus: 'unhealthy',
        isLoading: false,
        error: null,
        refresh: vi.fn(),
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('overall-health-badge')).toHaveTextContent('Unhealthy');
        const dbRow = screen.getByTestId('service-row-database');
        expect(dbRow).toHaveClass('bg-red-500/10');
      });
    });

    it('displays degraded status correctly', async () => {
      (useHealthStatusHook.useHealthStatus as Mock).mockReturnValue({
        health: {
          status: 'degraded',
          services: {
            redis: { status: 'degraded', message: 'High latency' },
          },
          timestamp: '2025-01-01T12:00:00Z',
        },
        services: {
          redis: { status: 'degraded', message: 'High latency' },
        },
        overallStatus: 'degraded',
        isLoading: false,
        error: null,
        refresh: vi.fn(),
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('overall-health-badge')).toHaveTextContent('Degraded');
        const redisRow = screen.getByTestId('service-row-redis');
        expect(redisRow).toHaveClass('bg-yellow-500/10');
      });
    });
  });

  describe('Grafana Monitoring Banner', () => {
    it('displays the Grafana monitoring banner', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('grafana-monitoring-banner')).toBeInTheDocument();
      });
    });

    it('displays correct banner title', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByText('Monitoring Dashboard Available')).toBeInTheDocument();
      });
    });

    it('displays Grafana link with default URL when config has no custom URL', async () => {
      // Mock fetchConfig to return config without grafana_url
      (api.fetchConfig as Mock).mockResolvedValue({
        app_name: 'Home Security Intelligence',
        version: '0.1.0',
        retention_days: 30,
        batch_window_seconds: 90,
        batch_idle_timeout_seconds: 30,
        detection_confidence_threshold: 0.5,
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-link');
        expect(grafanaLink).toHaveAttribute('href', 'http://localhost:3002');
        expect(grafanaLink).toHaveAttribute('target', '_blank');
        expect(grafanaLink).toHaveAttribute('rel', 'noopener noreferrer');
      });
    });

    it('uses dynamic grafana_url from config API', async () => {
      // Mock fetchConfig to return custom grafana_url
      (api.fetchConfig as Mock).mockResolvedValue({
        app_name: 'Home Security Intelligence',
        version: '0.1.0',
        retention_days: 30,
        batch_window_seconds: 90,
        batch_idle_timeout_seconds: 30,
        detection_confidence_threshold: 0.5,
        grafana_url: 'http://custom-grafana:3333',
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-link');
        expect(grafanaLink).toHaveAttribute('href', 'http://custom-grafana:3333');
      });
    });

    it('keeps default URL when config API fails', async () => {
      // Mock fetchConfig to fail
      (api.fetchConfig as Mock).mockRejectedValue(new Error('Network error'));

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-link');
        expect(grafanaLink).toHaveAttribute('href', 'http://localhost:3002');
      });
    });

    it('mentions anonymous access in banner text', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByText(/no login required/i)).toBeInTheDocument();
      });
    });
  });

  describe('Styling and Layout', () => {
    it('has correct page structure and styling', async () => {
      const { container } = render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /system monitoring/i })).toBeInTheDocument();
      });

      // Check for dark theme background
      const darkBg = container.querySelector('[class*="bg-"]');
      expect(darkBg).toBeTruthy();

      // Check for grid layout
      const gridLayout = container.querySelector('[class*="grid"]');
      expect(gridLayout).toBeTruthy();

      // Check for responsive design classes
      const responsiveElements = container.querySelectorAll('[class*="lg:"]');
      expect(responsiveElements.length).toBeGreaterThan(0);
    });

    it('has correct max-width container', async () => {
      const { container } = render(<SystemMonitoringPage />);

      await waitFor(() => {
        const maxWidthContainer = container.querySelector('.max-w-\\[1920px\\]');
        expect(maxWidthContainer).toBeInTheDocument();
      });
    });
  });
});

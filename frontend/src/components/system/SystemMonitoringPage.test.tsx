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

// Mock new redesigned child components
vi.mock('./SummaryRow', () => ({
  default: ({ overall, gpu, pipeline, aiModels, infrastructure }: {
    overall: { id: string; label: string; status: string };
    gpu: { id: string; label: string; status: string };
    pipeline: { id: string; label: string; status: string };
    aiModels: { id: string; label: string; status: string };
    infrastructure: { id: string; label: string; status: string };
  }) => (
    <div
      data-testid="summary-row"
      data-overall-status={overall.status}
      data-gpu-status={gpu.status}
      data-pipeline-status={pipeline.status}
      data-ai-models-status={aiModels.status}
      data-infrastructure-status={infrastructure.status}
    >
      Summary Row
    </div>
  ),
}));

vi.mock('./GpuStatistics', () => ({
  default: ({
    utilization,
    temperature,
    memoryUsed,
    memoryTotal,
  }: {
    gpuName?: string | null;
    utilization?: number | null;
    temperature?: number | null;
    memoryUsed?: number | null;
    memoryTotal?: number | null;
  }) => (
    <div
      data-testid="gpu-statistics"
      data-utilization={utilization}
      data-temperature={temperature}
      data-memory-used={memoryUsed}
      data-memory-total={memoryTotal}
    >
      GPU Statistics
    </div>
  ),
}));

vi.mock('./PipelineFlow', () => ({
  default: ({
    detect,
    analyze,
    workers,
  }: {
    files: { name: string; health: string };
    detect: { name: string; health: string; queueDepth?: number };
    batch: { name: string; health: string };
    analyze: { name: string; health: string; queueDepth?: number };
    workers?: { name: string; running: boolean }[];
  }) => (
    <div
      data-testid="pipeline-flow"
      data-detect-queue={detect.queueDepth}
      data-analyze-queue={analyze.queueDepth}
      data-workers-count={workers?.length || 0}
    >
      Pipeline Flow
    </div>
  ),
}));

vi.mock('./InfrastructureGrid', () => ({
  default: ({
    postgresql,
    redis,
    containers,
    host,
    circuits,
  }: {
    postgresql: { status: string };
    redis: { status: string };
    containers: { status: string };
    host: { status: string };
    circuits: { status: string };
  }) => (
    <div
      data-testid="infrastructure-grid"
      data-postgresql-status={postgresql.status}
      data-redis-status={redis.status}
      data-containers-status={containers.status}
      data-host-status={host.status}
      data-circuits-status={circuits.status}
    >
      Infrastructure Grid
    </div>
  ),
}));

vi.mock('./ModelZooPanel', () => ({
  default: ({
    models,
    isLoading,
    error,
  }: {
    models: unknown[];
    vramStats: unknown;
    isLoading: boolean;
    error: string | null;
  }) => (
    <div
      data-testid="model-zoo-panel"
      data-models-count={models.length}
      data-is-loading={isLoading}
      data-has-error={!!error}
    >
      Model Zoo Panel
    </div>
  ),
}));

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

    // Mock fetchConfig for config API
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

    // Mock readiness API for workers
    (api.fetchReadiness as Mock).mockResolvedValue({
      workers: [
        { name: 'detection_worker', running: true },
        { name: 'analysis_worker', running: true },
      ],
    });

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
        databases: {
          postgresql: { status: 'healthy', connections_active: 5, connections_max: 20, cache_hit_ratio: 98 },
          redis: { status: 'healthy', memory_mb: 64, connected_clients: 3, hit_ratio: 95, blocked_clients: 0 },
        },
        host: { cpu_percent: 15, ram_used_gb: 8, ram_total_gb: 32, disk_used_gb: 100, disk_total_gb: 500 },
        containers: [
          { name: 'backend', health: 'healthy' },
          { name: 'frontend', health: 'healthy' },
        ],
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

    // Mock useModelZooStatus
    (useModelZooStatusHook.useModelZooStatus as Mock).mockReturnValue({
      models: [
        { name: 'clip_embedder', status: 'loaded', vram_mb: 400, category: 'embedding' },
      ],
      vramStats: { budget_mb: 1650, used_mb: 400, available_mb: 1250, usage_percent: 24 },
      isLoading: false,
      error: null,
      refresh: vi.fn(),
    });
  });

  describe('Loading State', () => {
    it('renders loading skeletons while fetching initial data', () => {
      (api.fetchStats as Mock).mockImplementation(() => new Promise(() => {}));
      (api.fetchTelemetry as Mock).mockImplementation(() => new Promise(() => {}));
      (api.fetchGPUStats as Mock).mockImplementation(() => new Promise(() => {}));

      render(<SystemMonitoringPage />);

      expect(screen.getByTestId('system-monitoring-loading')).toBeInTheDocument();
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
        expect(screen.getByTestId('summary-row')).toBeInTheDocument();
        expect(screen.getByTestId('gpu-statistics')).toBeInTheDocument();
        expect(screen.getByTestId('model-zoo-panel')).toBeInTheDocument();
        expect(screen.getByTestId('pipeline-flow')).toBeInTheDocument();
        expect(screen.getByTestId('infrastructure-grid')).toBeInTheDocument();
      });
    });
  });

  describe('Summary Row', () => {
    it('passes computed health status to SummaryRow', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const summaryRow = screen.getByTestId('summary-row');
        // With all services healthy, infrastructure should be healthy
        expect(summaryRow).toHaveAttribute('data-infrastructure-status', 'healthy');
      });
    });

    it('shows degraded status when services are degraded', async () => {
      (usePerformanceMetricsHook.usePerformanceMetrics as Mock).mockReturnValue({
        current: {
          timestamp: '2025-01-01T12:00:00Z',
          gpu: { utilization: 95, temperature: 85, vram_used_gb: 8, vram_total_gb: 24, name: 'Test GPU', power_watts: 200 },
          ai_models: {},
          nemotron: null,
          inference: null,
          databases: {
            postgresql: { status: 'degraded', connections_active: 5, connections_max: 20, cache_hit_ratio: 98 },
            redis: { status: 'healthy', memory_mb: 64, connected_clients: 3, hit_ratio: 95, blocked_clients: 0 },
          },
          host: { cpu_percent: 95, ram_used_gb: 8, ram_total_gb: 32, disk_used_gb: 100, disk_total_gb: 500 },
          containers: [],
          alerts: [],
        },
        history: { '5m': [], '15m': [], '60m': [] },
        alerts: [],
        isConnected: true,
        timeRange: '5m',
        setTimeRange: vi.fn(),
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const summaryRow = screen.getByTestId('summary-row');
        expect(summaryRow).toHaveAttribute('data-infrastructure-status', 'critical');
      });
    });
  });

  describe('GPU Statistics', () => {
    it('passes correct GPU data to GpuStatistics', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const gpuStats = screen.getByTestId('gpu-statistics');
        expect(gpuStats).toHaveAttribute('data-utilization', '75');
        expect(gpuStats).toHaveAttribute('data-temperature', '65');
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

      (usePerformanceMetricsHook.usePerformanceMetrics as Mock).mockReturnValue({
        current: {
          timestamp: '2025-01-01T12:00:00Z',
          gpu: null,
          ai_models: {},
          nemotron: null,
          inference: null,
          databases: {},
          host: null,
          containers: [],
          alerts: [],
        },
        history: { '5m': [], '15m': [], '60m': [] },
        alerts: [],
        isConnected: true,
        timeRange: '5m',
        setTimeRange: vi.fn(),
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const gpuStats = screen.getByTestId('gpu-statistics');
        expect(gpuStats).toBeInTheDocument();
      });
    });
  });

  describe('Pipeline Flow', () => {
    it('passes queue depths to PipelineFlow', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const pipelineFlow = screen.getByTestId('pipeline-flow');
        expect(pipelineFlow).toHaveAttribute('data-detect-queue', '5');
        expect(pipelineFlow).toHaveAttribute('data-analyze-queue', '2');
      });
    });

    it('passes workers data to PipelineFlow', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const pipelineFlow = screen.getByTestId('pipeline-flow');
        expect(pipelineFlow).toHaveAttribute('data-workers-count', '2');
      });
    });
  });

  describe('Infrastructure Grid', () => {
    it('passes infrastructure status to InfrastructureGrid', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const infraGrid = screen.getByTestId('infrastructure-grid');
        expect(infraGrid).toHaveAttribute('data-postgresql-status', 'healthy');
        expect(infraGrid).toHaveAttribute('data-redis-status', 'healthy');
      });
    });

    it('passes containers and host status', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const infraGrid = screen.getByTestId('infrastructure-grid');
        expect(infraGrid).toHaveAttribute('data-containers-status', 'healthy');
        expect(infraGrid).toHaveAttribute('data-host-status', 'healthy');
      });
    });
  });

  describe('Model Zoo Panel', () => {
    it('passes model zoo data to ModelZooPanel', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const modelZoo = screen.getByTestId('model-zoo-panel');
        expect(modelZoo).toHaveAttribute('data-models-count', '1');
        expect(modelZoo).toHaveAttribute('data-is-loading', 'false');
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

    it('fetches circuit breakers data', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(api.fetchCircuitBreakers).toHaveBeenCalled();
      });
    });

    it('fetches workers data from readiness endpoint', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(api.fetchReadiness).toHaveBeenCalled();
      });
    });
  });

  describe('Grafana Link', () => {
    it('displays Grafana link in header', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-link');
        expect(grafanaLink).toBeInTheDocument();
        expect(grafanaLink).toHaveAttribute('href', 'http://localhost:3002');
      });
    });

    it('uses dynamic grafana_url from config API', async () => {
      (api.fetchConfig as Mock).mockResolvedValue({
        app_name: 'Home Security Intelligence',
        version: '0.1.0',
        retention_days: 30,
        grafana_url: 'http://custom-grafana:3333',
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-link');
        expect(grafanaLink).toHaveAttribute('href', 'http://custom-grafana:3333');
      });
    });

    it('keeps default URL when config API fails', async () => {
      (api.fetchConfig as Mock).mockRejectedValue(new Error('Network error'));

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-link');
        expect(grafanaLink).toHaveAttribute('href', 'http://localhost:3002');
      });
    });
  });

  describe('Time Range Selector', () => {
    it('renders time range selector', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('time-range-selector')).toBeInTheDocument();
      });
    });
  });

  describe('Section Headers', () => {
    it('renders GPU & AI Models section header', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByText('GPU & AI Models')).toBeInTheDocument();
      });
    });

    it('renders Pipeline section header', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByText('Pipeline')).toBeInTheDocument();
      });
    });

    it('renders Infrastructure section header', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByText('Infrastructure')).toBeInTheDocument();
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

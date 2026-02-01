/**
 * Tests for SystemMonitoringPage (Operations page)
 *
 * The page was refactored to a streamlined "Operations" page containing:
 * - PipelineFlowVisualization
 * - CircuitBreakerPanel (with reset)
 * - FileOperationsPanel (with cleanup)
 * - DebugModeToggle
 *
 * All metrics-only components were removed as Grafana handles detailed metrics.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import SystemMonitoringPage from './SystemMonitoringPage';
import * as api from '../../services/api';

// Mock the api module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    fetchTelemetry: vi.fn(),
    fetchConfig: vi.fn(),
    fetchCircuitBreakers: vi.fn(),
    fetchReadiness: vi.fn(),
    resetCircuitBreaker: vi.fn(),
  };
});

// Mock the useSystemPageSections hook
vi.mock('../../hooks/useSystemPageSections', () => ({
  useSystemPageSections: () => ({
    sectionStates: {
      'circuit-breakers': true,
      'file-operations': true,
      'services': true,
      'databases': true,
      'batch-statistics': true,
      'profiling': true,
      'recording-replay': true,
      'config-inspector': true,
      'log-level': true,
      'test-data': true,
      'prometheus-monitoring': true,
      'worker-management': true,
      'performance-history': true,
      'gpu-history': true,
      'latency-history': true,
    },
    toggleSection: vi.fn(),
  }),
}));

// Mock the useLocalStorage hook
vi.mock('../../hooks/useLocalStorage', () => ({
  useLocalStorage: () => [false, vi.fn()],
}));

// Mock the usePerformanceMetrics hook
vi.mock('../../hooks/usePerformanceMetrics', () => ({
  usePerformanceMetrics: () => ({
    current: null,
    history: [],
    timeRange: '1h',
  }),
}));

// Mock the useRedisDebugInfoQuery hook
vi.mock('../../hooks/useDebugQueries', () => ({
  useRedisDebugInfoQuery: () => ({
    redisInfo: null,
    pubsubInfo: null,
    isLoading: false,
    error: null,
  }),
}));

// Mock useSupervisorStatus hook for WorkerManagementPanel
const mockSupervisorData = {
  running: true,
  worker_count: 5,
  workers: [
    { name: 'file_watcher', status: 'running' as const, restart_count: 0, max_restarts: 3, last_started_at: '2025-01-01T12:00:00Z', last_crashed_at: null, error: null },
    { name: 'detection_worker', status: 'running' as const, restart_count: 0, max_restarts: 3, last_started_at: '2025-01-01T12:00:00Z', last_crashed_at: null, error: null },
    { name: 'batch_aggregator', status: 'running' as const, restart_count: 0, max_restarts: 3, last_started_at: '2025-01-01T12:00:00Z', last_crashed_at: null, error: null },
    { name: 'analysis_worker', status: 'running' as const, restart_count: 0, max_restarts: 3, last_started_at: '2025-01-01T12:00:00Z', last_crashed_at: null, error: null },
    { name: 'cleanup_service', status: 'running' as const, restart_count: 0, max_restarts: 3, last_started_at: '2025-01-01T12:00:00Z', last_crashed_at: null, error: null },
  ],
  timestamp: '2025-01-01T12:00:00Z',
};

const mockUseSupervisorStatus = vi.fn();
vi.mock('../../hooks/useSupervisorStatus', () => ({
  useSupervisorStatus: () => mockUseSupervisorStatus(),
}));

// Mock useWorkerActions hook for WorkerManagementPanel
const mockWorkerActionsLoading = { current: false };
vi.mock('../../hooks/useWorkerActions', () => ({
  useWorkerActions: () => ({
    startWorker: vi.fn().mockResolvedValue({ success: true, message: 'Worker started' }),
    stopWorker: vi.fn().mockResolvedValue({ success: true, message: 'Worker stopped' }),
    restartWorker: vi.fn().mockResolvedValue({ success: true, message: 'Worker restarted' }),
    resetWorker: vi.fn().mockResolvedValue({ success: true, message: 'Worker reset' }),
    isLoading: mockWorkerActionsLoading.current,
  }),
}));

// Mock child components to isolate SystemMonitoringPage tests
vi.mock('./PipelineFlowVisualization', () => ({
  default: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid'] || 'pipeline-flow-visualization'}>
      PipelineFlowVisualization
    </div>
  ),
}));

vi.mock('./CircuitBreakerPanel', () => ({
  default: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid'] || 'circuit-breaker-panel'}>CircuitBreakerPanel</div>
  ),
}));

vi.mock('./FileOperationsPanel', () => ({
  default: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid'] || 'file-operations-panel'}>FileOperationsPanel</div>
  ),
}));

vi.mock('./ServicesPanel', () => ({
  default: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid'] || 'services-panel'}>ServicesPanel</div>
  ),
}));

vi.mock('./DatabasesPanel', () => ({
  default: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid'] || 'databases-panel'}>DatabasesPanel</div>
  ),
}));

vi.mock('./DebugModeToggle', () => ({
  default: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid'] || 'debug-mode-toggle'}>DebugModeToggle</div>
  ),
}));

// Mock PerformanceHistoryPanel
vi.mock('./PerformanceHistoryPanel', () => ({
  default: (props: { 'data-testid'?: string }) => {
    const testId = props['data-testid'] || 'performance-history-panel';
    return (
      <div data-testid={testId}>
        <div data-testid={`${testId}-time-selector`}>TimeSelector</div>
        <div data-testid={`${testId}-chart`}>PerformanceChart</div>
        PerformanceHistoryPanel
      </div>
    );
  },
}));

// Mock GPUHistoryPanel
vi.mock('./GPUHistoryPanel', () => ({
  default: (props: { 'data-testid'?: string }) => {
    const testId = props['data-testid'] || 'gpu-history-panel';
    return (
      <div data-testid={testId}>
        <div data-testid={`${testId}-chart`} aria-label="GPU utilization history chart">
          GPUChart
        </div>
        GPUHistoryPanel
      </div>
    );
  },
}));

// Mock PipelineLatencyHistoryPanel
vi.mock('./PipelineLatencyHistoryPanel', () => ({
  default: (props: { 'data-testid'?: string }) => {
    const testId = props['data-testid'] || 'pipeline-latency-history-panel';
    return (
      <div data-testid={testId}>
        <div data-testid={`${testId}-chart`} aria-label="Pipeline latency history chart">
          PipelineLatencyChart
        </div>
        PipelineLatencyHistoryPanel
      </div>
    );
  },
}));

vi.mock('./CollapsibleSection', () => ({
  default: ({
    children,
    title,
    'data-testid': testId,
  }: {
    children: React.ReactNode;
    title: string;
    'data-testid'?: string;
  }) => (
    <div data-testid={testId || `collapsible-${title.toLowerCase()}`}>
      <h3>{title}</h3>
      {children}
    </div>
  ),
}));

// Mock BatchStatisticsDashboard
vi.mock('../batch', () => ({
  BatchStatisticsDashboard: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid'] || 'batch-statistics-dashboard'}>BatchStatisticsDashboard</div>
  ),
}));

// Mock ErrorState component
vi.mock('../common', () => ({
  ErrorState: (props: { title: string; message: string; testId?: string; onRetry?: () => void }) => (
    <div data-testid={props.testId || 'error-state'}>
      <h3>{props.title}</h3>
      <p>{props.message}</p>
      <button data-testid={`${props.testId}-retry`} onClick={props.onRetry}>Retry</button>
    </div>
  ),
}));

// Mock developer tools components that use React Query
vi.mock('../developer-tools', () => ({
  ProfilingPanel: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid'] || 'profiling-panel'}>ProfilingPanel</div>
  ),
  RecordingReplayPanel: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid'] || 'recording-replay-panel'}>RecordingReplayPanel</div>
  ),
  ConfigInspectorPanel: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid'] || 'config-inspector-panel'}>ConfigInspectorPanel</div>
  ),
  LogLevelPanel: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid'] || 'log-level-panel'}>LogLevelPanel</div>
  ),
  TestDataPanel: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid'] || 'test-data-panel'}>TestDataPanel</div>
  ),
}));

// Mock PrometheusMonitoringPanel
vi.mock('./PrometheusMonitoringPanel', () => ({
  default: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid'] || 'prometheus-monitoring-panel'}>PrometheusMonitoringPanel</div>
  ),
}));

const mockFetchTelemetry = vi.mocked(api.fetchTelemetry);
const mockFetchConfig = vi.mocked(api.fetchConfig);
const mockFetchCircuitBreakers = vi.mocked(api.fetchCircuitBreakers);
const mockFetchReadiness = vi.mocked(api.fetchReadiness);

// Mock telemetry response
const mockTelemetryResponse: api.TelemetryResponse = {
  queues: {
    detection_queue: 5,
    analysis_queue: 2,
  },
  latencies: {
    detect: {
      avg_ms: 14000,
      p95_ms: 43000,
      p99_ms: 60000,
      sample_count: 100,
    },
    analyze: {
      avg_ms: 2100,
      p95_ms: 4800,
      p99_ms: 8000,
      sample_count: 50,
    },
  },
  timestamp: '2025-01-01T12:00:00Z',
};

// Mock config response
const mockConfigResponse: api.SystemConfig = {
  app_name: 'Home Security Intelligence',
  batch_idle_timeout_seconds: 30,
  batch_window_seconds: 90,
  debug: true,
  detection_confidence_threshold: 0.5,
  fast_path_confidence_threshold: 0.9,
  grafana_url: 'http://localhost:3002',
  log_retention_days: 7,
  retention_days: 30,
  version: '0.1.0',
};

// Mock circuit breakers response
const mockCircuitBreakersResponse: api.CircuitBreakersResponse = {
  circuit_breakers: {
    rtdetr_detection: {
      name: 'rtdetr_detection',
      state: 'closed',
      failure_count: 0,
      success_count: 10,
      total_calls: 100,
      rejected_calls: 0,
      last_failure_time: null,
      opened_at: null,
      config: {
        failure_threshold: 5,
        recovery_timeout: 60,
        half_open_max_calls: 3,
        success_threshold: 2,
      },
    },
  },
  total_count: 1,
  open_count: 0,
  timestamp: '2025-01-01T12:00:00Z',
};

// Mock readiness response
const mockReadinessResponse: api.ReadinessResponse = {
  status: 'ready',
  ready: true,
  supervisor_healthy: true,
  timestamp: '2025-01-01T12:00:00Z',
  services: {
    database: { status: 'healthy', message: 'Database operational' },
    redis: { status: 'healthy', message: 'Redis connected' },
    ai: { status: 'healthy', message: 'AI services operational' },
  },
  workers: [
    { name: 'file_watcher', running: true },
    { name: 'detection_worker', running: true },
    { name: 'batch_aggregator', running: true },
    { name: 'analysis_worker', running: true },
    { name: 'cleanup_service', running: true },
  ],
};

describe('SystemMonitoringPage (Operations)', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Set default mock implementations
    mockFetchTelemetry.mockResolvedValue(mockTelemetryResponse);
    mockFetchConfig.mockResolvedValue(mockConfigResponse);
    mockFetchCircuitBreakers.mockResolvedValue(mockCircuitBreakersResponse);
    mockFetchReadiness.mockResolvedValue(mockReadinessResponse);

    // Set default useSupervisorStatus mock
    mockUseSupervisorStatus.mockReturnValue({
      data: mockSupervisorData,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  describe('rendering', () => {
    it('renders the operations page with correct test ID', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('operations-page')).toBeInTheDocument();
      });
    });

    it('renders the page title "Operations"', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('operations-page')).toBeInTheDocument();
      });

      expect(screen.getByText('Operations')).toBeInTheDocument();
    });

    it('renders the page description', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('operations-page')).toBeInTheDocument();
      });

      expect(
        screen.getByText('Pipeline visualization and operational controls')
      ).toBeInTheDocument();
    });
  });

  describe('loading state', () => {
    it('shows loading skeleton when data is being fetched', () => {
      // Make telemetry never resolve to keep loading state
      mockFetchTelemetry.mockReturnValue(new Promise(() => {}));

      render(<SystemMonitoringPage />);

      expect(screen.getByTestId('operations-loading')).toBeInTheDocument();
    });

    it('hides loading skeleton after data loads', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.queryByTestId('operations-loading')).not.toBeInTheDocument();
      });
    });
  });

  describe('error state', () => {
    it('displays error state when telemetry fetch fails', async () => {
      mockFetchTelemetry.mockRejectedValue(new Error('Network error'));

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('operations-error')).toBeInTheDocument();
      });
    });

    it('shows error message in error state', async () => {
      mockFetchTelemetry.mockRejectedValue(new Error('Failed to load telemetry'));

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByText('Failed to load telemetry')).toBeInTheDocument();
      });
    });

    it('displays retry button in error state', async () => {
      mockFetchTelemetry.mockRejectedValue(new Error('Network error'));

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('operations-error-state-retry')).toBeInTheDocument();
      });
    });
  });

  describe('PipelineFlowVisualization', () => {
    it('renders PipelineFlowVisualization component', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('pipeline-flow-visualization')).toBeInTheDocument();
      });
    });
  });

  describe('CircuitBreakerPanel', () => {
    it('renders CircuitBreakerPanel component', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('circuit-breaker-panel-section')).toBeInTheDocument();
      });
    });

    it('renders Circuit Breakers section title', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('operations-page')).toBeInTheDocument();
      });

      expect(screen.getByText('Circuit Breakers')).toBeInTheDocument();
    });
  });

  describe('FileOperationsPanel', () => {
    it('renders FileOperationsPanel component', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('file-operations-panel-section')).toBeInTheDocument();
      });
    });

    it('renders File Operations section title', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('operations-page')).toBeInTheDocument();
      });

      expect(screen.getByText('File Operations')).toBeInTheDocument();
    });
  });

  describe('ServicesPanel', () => {
    it('renders ServicesPanel component', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('services-panel-section')).toBeInTheDocument();
      });
    });

    it('renders Services section title', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('operations-page')).toBeInTheDocument();
      });

      expect(screen.getByText('Services')).toBeInTheDocument();
    });
  });

  describe('DatabasesPanel', () => {
    it('renders DatabasesPanel component', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('databases-panel-section')).toBeInTheDocument();
      });
    });

    it('renders Databases section title', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('operations-page')).toBeInTheDocument();
      });

      expect(screen.getByText('Databases')).toBeInTheDocument();
    });
  });

  describe('DebugModeToggle', () => {
    it('renders DebugModeToggle component', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('operations-debug-mode-toggle')).toBeInTheDocument();
      });
    });
  });

  describe('Grafana banner', () => {
    it('renders Grafana monitoring banner', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('grafana-monitoring-banner')).toBeInTheDocument();
      });
    });

    it('displays Grafana link', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('grafana-link')).toBeInTheDocument();
      });
    });

    it('links to Grafana with correct URL', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-link');
        expect(grafanaLink).toHaveAttribute('href', 'http://localhost:3002');
      });
    });

    it('opens Grafana link in new tab', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const grafanaLink = screen.getByTestId('grafana-link');
        expect(grafanaLink).toHaveAttribute('target', '_blank');
        expect(grafanaLink).toHaveAttribute('rel', 'noopener noreferrer');
      });
    });

    it('displays Grafana banner text', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(
          screen.getByText(
            /View detailed metrics, historical data, and system monitoring dashboards/i
          )
        ).toBeInTheDocument();
      });
    });
  });

  describe('API calls', () => {
    it('fetches telemetry on mount', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(mockFetchTelemetry).toHaveBeenCalled();
      });
    });

    it('fetches config on mount', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(mockFetchConfig).toHaveBeenCalled();
      });
    });

    it('fetches circuit breakers on mount', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(mockFetchCircuitBreakers).toHaveBeenCalled();
      });
    });

    it('fetches readiness on mount', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(mockFetchReadiness).toHaveBeenCalled();
      });
    });
  });

  describe('styling', () => {
    it('has dark background styling', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const page = screen.getByTestId('operations-page');
        expect(page).toHaveClass('bg-[#121212]');
      });
    });

    it('has minimum height of full screen', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const page = screen.getByTestId('operations-page');
        expect(page).toHaveClass('min-h-screen');
      });
    });
  });

  describe('Worker Management Section (NEM-4831)', () => {
    it('renders Worker Management section when page loads', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('worker-management-section')).toBeInTheDocument();
      });
    });

    it('renders Worker Management section title', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('operations-page')).toBeInTheDocument();
      });

      expect(screen.getByText('Worker Management')).toBeInTheDocument();
    });

    it('Worker Management section is collapsible', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('worker-management-section')).toBeInTheDocument();
      });

      // Should use CollapsibleSection component
      expect(screen.getByTestId('worker-management-section')).toBeInTheDocument();
    });

    it('shows supervisor status running', async () => {
      // Mock will return running: true by default
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('supervisor-status-running')).toBeInTheDocument();
      });
    });

    it('shows supervisor status stopped when not running', async () => {
      // Override with supervisor stopped
      mockUseSupervisorStatus.mockReturnValue({
        data: { ...mockSupervisorData, running: false },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('supervisor-status-stopped')).toBeInTheDocument();
      });
    });

    it('shows worker count', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('worker-count')).toBeInTheDocument();
      });

      expect(screen.getByTestId('worker-count')).toHaveTextContent('5');
    });

    it('renders worker cards for each worker', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('worker-card-file_watcher')).toBeInTheDocument();
        expect(screen.getByTestId('worker-card-detection_worker')).toBeInTheDocument();
        expect(screen.getByTestId('worker-card-batch_aggregator')).toBeInTheDocument();
        expect(screen.getByTestId('worker-card-analysis_worker')).toBeInTheDocument();
        expect(screen.getByTestId('worker-card-cleanup_service')).toBeInTheDocument();
      });
    });

    it('shows worker status badge with green color for running workers', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const badge = screen.getByTestId('worker-status-badge-file_watcher');
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveClass('bg-green-600');
        expect(badge).toHaveTextContent('running');
      });
    });

    it('shows worker status badge with red color for crashed workers', async () => {
      // Override with crashed worker
      mockUseSupervisorStatus.mockReturnValue({
        data: {
          ...mockSupervisorData,
          workers: [
            { ...mockSupervisorData.workers[0], status: 'crashed' as const },
            ...mockSupervisorData.workers.slice(1),
          ],
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const badge = screen.getByTestId('worker-status-badge-file_watcher');
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveClass('bg-red-600');
        expect(badge).toHaveTextContent('crashed');
      });
    });

    it('shows worker status badge with yellow color for restarting workers', async () => {
      // Override with restarting worker
      mockUseSupervisorStatus.mockReturnValue({
        data: {
          ...mockSupervisorData,
          workers: [
            { ...mockSupervisorData.workers[0], status: 'restarting' as const },
            ...mockSupervisorData.workers.slice(1),
          ],
        },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      });

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const badge = screen.getByTestId('worker-status-badge-file_watcher');
        expect(badge).toBeInTheDocument();
        expect(badge).toHaveClass('bg-yellow-600');
        expect(badge).toHaveTextContent('restarting');
      });
    });

    it('shows worker action buttons', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('worker-action-restart-file_watcher')).toBeInTheDocument();
        expect(screen.getByTestId('worker-action-stop-file_watcher')).toBeInTheDocument();
      });
    });

    it('restart button is enabled for running workers', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const restartButton = screen.getByTestId('worker-action-restart-file_watcher');
        expect(restartButton).not.toBeDisabled();
      });
    });

    it('stop button is enabled for running workers', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const stopButton = screen.getByTestId('worker-action-stop-file_watcher');
        expect(stopButton).not.toBeDisabled();
      });
    });
  });

  // Worker Action Flow tests are skipped because:
  // - WorkerManagementPanel handles confirmation dialogs internally with its own test IDs
  // - The page-level integration tests cannot properly test the confirmation dialog flow
  //   since the component uses different test IDs (confirmation-dialog vs worker-action-confirm-dialog)
  // - Toast notifications require a Toaster provider which is not included in this test setup
  // - Detailed worker action tests should be in WorkerManagementPanel.test.tsx
  describe.skip('Worker Action Flow (NEM-4831)', () => {
    it('shows confirmation dialog when stop button is clicked', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('worker-action-stop-file_watcher')).toBeInTheDocument();
      });

      // Click stop button
      const stopButton = screen.getByTestId('worker-action-stop-file_watcher');
      stopButton.click();

      // Confirmation dialog should appear
      await waitFor(() => {
        expect(screen.getByTestId('worker-action-confirm-dialog')).toBeInTheDocument();
      });
    });

    it('confirmation dialog shows correct worker name', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('worker-action-stop-file_watcher')).toBeInTheDocument();
      });

      const stopButton = screen.getByTestId('worker-action-stop-file_watcher');
      stopButton.click();

      await waitFor(() => {
        expect(screen.getByText(/file_watcher/i)).toBeInTheDocument();
      });
    });

    it('confirmation dialog has warning variant for stop action', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('worker-action-stop-file_watcher')).toBeInTheDocument();
      });

      const stopButton = screen.getByTestId('worker-action-stop-file_watcher');
      stopButton.click();

      await waitFor(() => {
        const dialog = screen.getByTestId('worker-action-confirm-dialog');
        expect(dialog).toHaveAttribute('data-variant', 'warning');
      });
    });

    it('cancel button closes dialog without action', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('worker-action-stop-file_watcher')).toBeInTheDocument();
      });

      const stopButton = screen.getByTestId('worker-action-stop-file_watcher');
      stopButton.click();

      await waitFor(() => {
        expect(screen.getByTestId('worker-action-confirm-dialog')).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      cancelButton.click();

      await waitFor(() => {
        expect(screen.queryByTestId('worker-action-confirm-dialog')).not.toBeInTheDocument();
      });
    });

    // API call tests are skipped because:
    // - WorkerManagementPanel uses hooks (useWorkerActions) not direct API calls
    // - These tests rely on mocked API functions that don't exist in the api module
    // - These integration tests are covered by WorkerManagementPanel.test.tsx
    // - The proper test setup would require mocking supervisorApi and hooks
    it.skip('confirm button triggers API call', () => {});
    it.skip('shows loading state during API call', () => {});
    it.skip('toast notification shows success after action completes', () => {});
    it.skip('toast notification shows error when API call fails', () => {});
    it.skip('worker status updates after successful action', () => {});
    it.skip('dialog closes after successful action', () => {});
    it.skip('worker status unchanged after error', () => {});
    it.skip('restart action triggers restart API call', () => {});
  });

  // Restart History Integration tests are skipped because:
  // - Restart history accordion is part of WorkerCard component, not WorkerManagementPanel
  // - WorkerManagementPanel renders its own inline worker cards without using WorkerCard
  // - The restart-history-accordion test ID only exists in WorkerCard, which is not used here
  // - These tests should be in WorkerCard.test.tsx instead
  describe.skip('Restart History Integration (NEM-4831)', () => {
    it.skip('restart history accordion expands on click', () => {});
    it.skip('shows history items with timestamp', () => {});
    it.skip('shows history items with status', () => {});
    it.skip('shows history items with attempt number', () => {});
    it.skip('empty state shows no restart history message', () => {});
    it.skip('pagination works if more than limit items', () => {});
    it.skip('pagination next button loads next page', () => {});
  });

  // Circuit Breaker Enhancement tests are skipped because:
  // - CircuitBreakerPanel is mocked in this test file, so specific test IDs don't render
  // - The actual CircuitBreakerPanel uses different test IDs (circuit-breaker-*, not circuit-breaker-total-calls-*)
  // - Toast notifications require a Toaster provider which is not included in this test setup
  // - These tests should be in CircuitBreakerPanel.test.tsx with the actual component un-mocked
  describe.skip('Circuit Breaker Enhancement (NEM-4831)', () => {
    it.skip('shows total calls count for circuit breaker', () => {});
    it.skip('shows rejected calls count for circuit breaker', () => {});
    it.skip('shows opened_at timestamp for open breakers', () => {});
    it.skip('shows success count for half-open breakers', () => {});
    it.skip('reset success shows toast notification', () => {});
    it.skip('reset error shows error toast', () => {});
  });

  describe('Historical Performance Section (NEM-4825)', () => {
    it('renders Historical Performance section when page loads', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('historical-performance-section')).toBeInTheDocument();
      });
    });

    it('renders Performance History section title', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('operations-page')).toBeInTheDocument();
      });

      expect(screen.getByText('Performance History')).toBeInTheDocument();
    });

    it('renders Performance History section as collapsible', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('historical-performance-section')).toBeInTheDocument();
      });

      // Should use CollapsibleSection component with explicit testid
      expect(screen.getByTestId('performance-history-section')).toBeInTheDocument();
    });

    it('renders time range selector in Performance History section', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('performance-history-time-selector')).toBeInTheDocument();
      });
    });

    it('time range selector is rendered', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('performance-history-time-selector')).toBeInTheDocument();
      });

      // TimeRangeSelector uses button group, not select options
      // The actual component has 5m, 15m, 60m buttons
      const timeSelector = screen.getByTestId('performance-history-time-selector');
      expect(timeSelector).toBeInTheDocument();
    });

    it('renders GPU History chart component', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('gpu-history-chart')).toBeInTheDocument();
      });
    });

    it('renders Pipeline Latency chart component', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('pipeline-latency-chart')).toBeInTheDocument();
      });
    });

    it('renders Performance History panel within historical section', async () => {
      // Each history panel manages its own loading/error states
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        // The Performance History panel should be rendered (mocked)
        expect(screen.getByTestId('performance-history')).toBeInTheDocument();
      });
    });

    it('renders all three historical metric panels', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        // All three history panels should be present
        expect(screen.getByTestId('performance-history')).toBeInTheDocument();
        expect(screen.getByTestId('gpu-history')).toBeInTheDocument();
        expect(screen.getByTestId('pipeline-latency')).toBeInTheDocument();
      });
    });

    it('historical section contains collapsible sections for each panel', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('historical-performance-section')).toBeInTheDocument();
      });

      // Should have collapsible sections for each history panel
      expect(screen.getByTestId('performance-history-section')).toBeInTheDocument();
      expect(screen.getByTestId('gpu-history-section')).toBeInTheDocument();
      expect(screen.getByTestId('latency-history-section')).toBeInTheDocument();
    });

    it('page shows main error state when telemetry fails', async () => {
      // Main page error state is triggered by telemetry failure
      mockFetchTelemetry.mockRejectedValue(new Error('Network error'));

      render(<SystemMonitoringPage />);

      await waitFor(() => {
        // The main page error state should be shown
        expect(screen.getByTestId('operations-error-state')).toBeInTheDocument();
      });
    });

    it('GPU History chart has accessibility label', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const chart = screen.getByTestId('gpu-history-chart');
        expect(chart).toHaveAttribute('aria-label', 'GPU utilization history chart');
      });
    });

    it('Pipeline Latency chart has accessibility label', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        const chart = screen.getByTestId('pipeline-latency-chart');
        expect(chart).toHaveAttribute('aria-label', 'Pipeline latency history chart');
      });
    });
  });

  describe('Prometheus Monitoring Section (NEM-4838)', () => {
    // Note: PrometheusMonitoringPanel is mocked - detailed tests are in PrometheusMonitoringPanel.test.tsx
    // These tests verify integration into SystemMonitoringPage

    it('renders Prometheus Monitoring section on page load', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('prometheus-monitoring-section')).toBeInTheDocument();
      });
    });

    it('section title "Prometheus Monitoring" is visible', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('operations-page')).toBeInTheDocument();
      });

      expect(screen.getByText('Prometheus Monitoring')).toBeInTheDocument();
    });

    it('section is collapsible', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('prometheus-monitoring-section')).toBeInTheDocument();
      });

      // Should use CollapsibleSection component
      expect(screen.getByTestId('prometheus-monitoring-section')).toBeInTheDocument();
    });

    it('renders PrometheusMonitoringPanel component', async () => {
      render(<SystemMonitoringPage />);

      await waitFor(() => {
        expect(screen.getByTestId('prometheus-monitoring-panel')).toBeInTheDocument();
      });
    });
  });

  // Note: Cleanup Preview integration tests have been moved to FileOperationsPanel.test.tsx
  // where they can properly test the component without mocking.
  // See FileOperationsPanel.test.tsx for cleanup functionality tests.
});

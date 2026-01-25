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
    },
    toggleSection: vi.fn(),
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

vi.mock('./DebugModeToggle', () => ({
  default: (props: { 'data-testid'?: string }) => (
    <div data-testid={props['data-testid'] || 'debug-mode-toggle'}>DebugModeToggle</div>
  ),
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
        log_retention_days: 7,
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
});

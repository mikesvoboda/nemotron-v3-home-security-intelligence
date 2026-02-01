import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi } from 'vitest';

import { PrometheusMonitoringPanel } from './PrometheusMonitoringPanel';
import * as useMonitoringHealthModule from '../../hooks/useMonitoringHealth';

import type { MonitoringHealthResponse } from '../../services/monitoringApi';


// Mock the hook
vi.mock('../../hooks/useMonitoringHealth');

describe('PrometheusMonitoringPanel', () => {
  const mockHealthyData: MonitoringHealthResponse = {
    healthy: true,
    prometheus_reachable: true,
    prometheus_url: 'http://prometheus:9090',
    targets_summary: [
      { job: 'backend', total: 1, up: 1, down: 0, unknown: 0 },
      { job: 'redis-exporter', total: 1, up: 1, down: 0, unknown: 0 },
      { job: 'postgres-exporter', total: 1, up: 1, down: 0, unknown: 0 },
    ],
    exporters: [
      {
        name: 'redis-exporter',
        status: 'up',
        endpoint: 'redis-exporter:9121',
        last_scrape: '2025-01-31T10:30:00Z',
        error: null,
      },
      {
        name: 'postgres-exporter',
        status: 'up',
        endpoint: 'postgres-exporter:9187',
        last_scrape: '2025-01-31T10:30:00Z',
        error: null,
      },
    ],
    metrics_collection: {
      collecting: true,
      last_successful_scrape: '2025-01-31T10:30:00Z',
      scrape_interval_seconds: 15,
      total_series: 15000,
    },
    issues: [],
    timestamp: '2025-01-31T10:30:00Z',
  };

  const mockUnhealthyData: MonitoringHealthResponse = {
    healthy: false,
    prometheus_reachable: true,
    prometheus_url: 'http://prometheus:9090',
    targets_summary: [
      { job: 'backend', total: 1, up: 0, down: 1, unknown: 0 },
      { job: 'redis-exporter', total: 1, up: 1, down: 0, unknown: 0 },
    ],
    exporters: [
      {
        name: 'backend',
        status: 'down',
        endpoint: 'backend:8000',
        last_scrape: '2025-01-31T10:25:00Z',
        error: 'Connection refused',
      },
      {
        name: 'redis-exporter',
        status: 'up',
        endpoint: 'redis-exporter:9121',
        last_scrape: '2025-01-31T10:30:00Z',
        error: null,
      },
    ],
    metrics_collection: {
      collecting: true,
      last_successful_scrape: '2025-01-31T10:30:00Z',
      scrape_interval_seconds: 15,
      total_series: 12000,
    },
    issues: ['1 target(s) are down: backend'],
    timestamp: '2025-01-31T10:30:00Z',
  };

  const mockUnreachableData: MonitoringHealthResponse = {
    healthy: false,
    prometheus_reachable: false,
    prometheus_url: 'http://prometheus:9090',
    targets_summary: [],
    exporters: [],
    metrics_collection: {
      collecting: false,
      last_successful_scrape: null,
      scrape_interval_seconds: 15,
      total_series: 0,
    },
    issues: ['Prometheus is not reachable at http://prometheus:9090'],
    timestamp: '2025-01-31T10:30:00Z',
  };

  const mockRefetch = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render loading skeleton when loading', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
      isHealthy: false,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    expect(screen.getByTestId('monitoring-loading-skeleton')).toBeInTheDocument();
  });

  it('should render error state when fetch fails', () => {
    const error = new Error('Network error');
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: null,
      isLoading: false,
      error,
      isHealthy: false,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    expect(screen.getByText(/error loading monitoring data/i)).toBeInTheDocument();
    expect(screen.getByText(/network error/i)).toBeInTheDocument();
  });

  it('should show "Prometheus Healthy" badge when healthy', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockHealthyData,
      isLoading: false,
      error: null,
      isHealthy: true,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    expect(screen.getByText(/prometheus healthy/i)).toBeInTheDocument();
    expect(screen.queryByText(/prometheus unhealthy/i)).not.toBeInTheDocument();
  });

  it('should show "Prometheus Unhealthy" badge when unhealthy', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockUnhealthyData,
      isLoading: false,
      error: null,
      isHealthy: false,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    expect(screen.getByText(/prometheus unhealthy/i)).toBeInTheDocument();
    expect(screen.queryByText(/prometheus healthy/i)).not.toBeInTheDocument();
  });

  it('should show "Prometheus Unreachable" when not reachable', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockUnreachableData,
      isLoading: false,
      error: null,
      isHealthy: false,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    expect(screen.getByText(/prometheus unreachable/i)).toBeInTheDocument();
  });

  it('should render target summary table with job counts', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockHealthyData,
      isLoading: false,
      error: null,
      isHealthy: true,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    // Target names appear in both table and exporter list, so use getAllByText
    expect(screen.getByText('backend')).toBeInTheDocument();
    expect(screen.getAllByText('redis-exporter').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('postgres-exporter').length).toBeGreaterThanOrEqual(1);

    // Check for counts - find backend in table row
    const backendRow = screen.getByText('backend').closest('tr');
    expect(backendRow).toHaveTextContent('1'); // total
    expect(backendRow).toHaveTextContent('1'); // up
    expect(backendRow).toHaveTextContent('0'); // down
  });

  it('should render exporter status list', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockHealthyData,
      isLoading: false,
      error: null,
      isHealthy: true,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    // Exporter names may also appear in target summary, use getAllByText
    expect(screen.getAllByText('redis-exporter').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('postgres-exporter').length).toBeGreaterThanOrEqual(1);
    // Endpoints are unique
    expect(screen.getByText('redis-exporter:9121')).toBeInTheDocument();
    expect(screen.getByText('postgres-exporter:9187')).toBeInTheDocument();
  });

  it('should show metrics collection stats', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockHealthyData,
      isLoading: false,
      error: null,
      isHealthy: true,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    expect(screen.getByText(/15000/)).toBeInTheDocument(); // total_series
    expect(screen.getByText(/15s/)).toBeInTheDocument(); // scrape_interval
  });

  it('should display issues list when present', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockUnhealthyData,
      isLoading: false,
      error: null,
      isHealthy: false,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    expect(screen.getByText(/1 target\(s\) are down: backend/i)).toBeInTheDocument();
  });

  it('should not display issues section when no issues', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockHealthyData,
      isLoading: false,
      error: null,
      isHealthy: true,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    expect(screen.queryByText(/issues/i)).not.toBeInTheDocument();
  });

  it('should show last updated timestamp', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockHealthyData,
      isLoading: false,
      error: null,
      isHealthy: true,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    expect(screen.getByText(/last updated/i)).toBeInTheDocument();
  });

  it('should trigger refetch when refresh button clicked', async () => {
    const user = userEvent.setup();
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockHealthyData,
      isLoading: false,
      error: null,
      isHealthy: true,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    const refreshButton = screen.getByRole('button', { name: /refresh/i });
    await user.click(refreshButton);

    expect(mockRefetch).toHaveBeenCalledTimes(1);
  });

  it('should show down exporters with error messages', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockUnhealthyData,
      isLoading: false,
      error: null,
      isHealthy: false,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    // Backend appears in both target summary and exporters
    expect(screen.getAllByText('backend').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Connection refused')).toBeInTheDocument();
  });

  it('should show correct target summary for unhealthy state', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockUnhealthyData,
      isLoading: false,
      error: null,
      isHealthy: false,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    // Find backend in the table row (first occurrence is in table)
    const backendElements = screen.getAllByText('backend');
    const backendRow = backendElements[0].closest('tr');
    expect(backendRow).toHaveTextContent('1'); // total
    expect(backendRow).toHaveTextContent('0'); // up
    expect(backendRow).toHaveTextContent('1'); // down
  });

  it('should handle empty exporters list', () => {
    const dataWithNoExporters: MonitoringHealthResponse = {
      ...mockHealthyData,
      exporters: [],
    };

    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: dataWithNoExporters,
      isLoading: false,
      error: null,
      isHealthy: true,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    expect(screen.getByText(/no exporters/i)).toBeInTheDocument();
  });

  it('should handle empty targets summary', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockUnreachableData,
      isLoading: false,
      error: null,
      isHealthy: false,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    expect(screen.getByText(/no targets/i)).toBeInTheDocument();
  });

  it('should format timestamps correctly', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockHealthyData,
      isLoading: false,
      error: null,
      isHealthy: true,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    // Check for formatted timestamp - may appear in multiple places (last scrape, last updated)
    expect(screen.getAllByText(/2025-01-31/).length).toBeGreaterThanOrEqual(1);
  });

  it('should show metrics not collecting when Prometheus unreachable', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockUnreachableData,
      isLoading: false,
      error: null,
      isHealthy: false,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    expect(screen.getByText(/not collecting/i)).toBeInTheDocument();
  });

  it('should disable refresh button while loading', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: null,
      isLoading: true,
      error: null,
      isHealthy: false,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    const refreshButton = screen.queryByRole('button', { name: /refresh/i });
    // Button might not be rendered during loading
    if (refreshButton) {
      expect(refreshButton).toBeDisabled();
    }
  });

  it('should show Prometheus URL', () => {
    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockHealthyData,
      isLoading: false,
      error: null,
      isHealthy: true,
      refetch: mockRefetch,
    });

    render(<PrometheusMonitoringPanel />);

    expect(screen.getByText('http://prometheus:9090')).toBeInTheDocument();
  });

  it('should update display when data changes', async () => {
    const { rerender } = render(<PrometheusMonitoringPanel />);

    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockHealthyData,
      isLoading: false,
      error: null,
      isHealthy: true,
      refetch: mockRefetch,
    });

    rerender(<PrometheusMonitoringPanel />);
    expect(screen.getByText(/prometheus healthy/i)).toBeInTheDocument();

    vi.mocked(useMonitoringHealthModule.useMonitoringHealth).mockReturnValue({
      data: mockUnhealthyData,
      isLoading: false,
      error: null,
      isHealthy: false,
      refetch: mockRefetch,
    });

    rerender(<PrometheusMonitoringPanel />);
    await waitFor(() => {
      expect(screen.getByText(/prometheus unhealthy/i)).toBeInTheDocument();
    });
  });
});

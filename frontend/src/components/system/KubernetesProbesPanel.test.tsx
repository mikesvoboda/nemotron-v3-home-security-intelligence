import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import KubernetesProbesPanel from './KubernetesProbesPanel';
import * as api from '../../services/api';

import type { LivenessProbeResponse, ReadinessResponse } from '../../services/api';

// Mock the API module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    fetchLivenessProbe: vi.fn(),
    fetchReadiness: vi.fn(),
  };
});

describe('KubernetesProbesPanel', () => {
  const mockLivenessHealthy: LivenessProbeResponse = {
    status: 'alive',
    timestamp: '2026-01-30T10:00:00Z',
  };

  const mockReadinessHealthy: ReadinessResponse = {
    ready: true,
    status: 'ready',
    services: {
      database: { status: 'healthy', message: null, details: null },
      redis: { status: 'healthy', message: null, details: null },
      ai: { status: 'healthy', message: null, details: null },
    },
    workers: [
      { name: 'detection_worker', running: true, message: null },
      { name: 'analysis_worker', running: true, message: null },
      { name: 'batch_aggregator', running: true, message: null },
    ],
    timestamp: '2026-01-30T10:00:00Z',
    supervisor_healthy: true,
  };

  const mockReadinessUnhealthy: ReadinessResponse = {
    ready: false,
    status: 'not_ready',
    services: {
      database: { status: 'healthy', message: null, details: null },
      redis: { status: 'unhealthy', message: 'Connection refused', details: null },
      ai: { status: 'degraded', message: 'YOLO offline', details: null },
    },
    workers: [
      { name: 'detection_worker', running: false, message: 'Stopped' },
      { name: 'analysis_worker', running: true, message: null },
      { name: 'batch_aggregator', running: true, message: null },
    ],
    timestamp: '2026-01-30T10:00:00Z',
    supervisor_healthy: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', () => {
    vi.mocked(api.fetchLivenessProbe).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.fetchReadiness).mockReturnValue(new Promise(() => {}));

    render(<KubernetesProbesPanel />);

    expect(screen.getByTestId('kubernetes-probes-panel-loading')).toBeInTheDocument();
    expect(screen.getByText('Kubernetes Probes')).toBeInTheDocument();
  });

  it('renders healthy state correctly', async () => {
    vi.mocked(api.fetchLivenessProbe).mockResolvedValue(mockLivenessHealthy);
    vi.mocked(api.fetchReadiness).mockResolvedValue(mockReadinessHealthy);

    render(<KubernetesProbesPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('kubernetes-probes-panel')).toBeInTheDocument();
    });

    // Check overall badge
    expect(screen.getByTestId('probes-overall-badge')).toHaveTextContent('All Passing');

    // Check probe cards
    expect(screen.getByTestId('probe-card-liveness')).toBeInTheDocument();
    expect(screen.getByTestId('probe-card-readiness')).toBeInTheDocument();

    // Check status badges
    expect(screen.getByTestId('probe-status-badge-liveness')).toHaveTextContent('Passing');
    expect(screen.getByTestId('probe-status-badge-readiness')).toHaveTextContent('Passing');

    // Check descriptions
    expect(screen.getByText('Liveness Probe')).toBeInTheDocument();
    expect(screen.getByText('Readiness Probe')).toBeInTheDocument();

    // Check service and worker counts
    expect(screen.getByTestId('readiness-services-badge')).toHaveTextContent('Services: 3/3');
    expect(screen.getByTestId('readiness-workers-badge')).toHaveTextContent('Workers: 3/3');
  });

  it('renders unhealthy readiness state correctly', async () => {
    vi.mocked(api.fetchLivenessProbe).mockResolvedValue(mockLivenessHealthy);
    vi.mocked(api.fetchReadiness).mockResolvedValue(mockReadinessUnhealthy);

    render(<KubernetesProbesPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('kubernetes-probes-panel')).toBeInTheDocument();
    });

    // Check overall badge shows issues
    expect(screen.getByTestId('probes-overall-badge')).toHaveTextContent('Issues Detected');

    // Liveness should still be healthy
    expect(screen.getByTestId('probe-status-badge-liveness')).toHaveTextContent('Passing');

    // Readiness should show failing
    expect(screen.getByTestId('probe-status-badge-readiness')).toHaveTextContent('Failing');

    // Check service and worker counts (1 service healthy out of 3, 2 workers out of 3)
    expect(screen.getByTestId('readiness-services-badge')).toHaveTextContent('Services: 1/3');
    expect(screen.getByTestId('readiness-workers-badge')).toHaveTextContent('Workers: 2/3');

    // Check supervisor unhealthy badge
    expect(screen.getByTestId('readiness-supervisor-badge')).toHaveTextContent('Supervisor Unhealthy');
  });

  it('renders error state when both fetches fail', async () => {
    vi.mocked(api.fetchLivenessProbe).mockRejectedValue(new Error('Network error'));
    vi.mocked(api.fetchReadiness).mockRejectedValue(new Error('Network error'));

    render(<KubernetesProbesPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('kubernetes-probes-panel')).toBeInTheDocument();
    });

    // Should still render the panel but show unhealthy status
    expect(screen.getByTestId('probe-status-badge-liveness')).toHaveTextContent('Failing');
    expect(screen.getByTestId('probe-status-badge-readiness')).toHaveTextContent('Failing');
  });

  it('handles refresh button click', async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchLivenessProbe).mockResolvedValue(mockLivenessHealthy);
    vi.mocked(api.fetchReadiness).mockResolvedValue(mockReadinessHealthy);

    render(<KubernetesProbesPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('kubernetes-probes-panel')).toBeInTheDocument();
    });

    // Initial fetch
    expect(api.fetchLivenessProbe).toHaveBeenCalledTimes(1);
    expect(api.fetchReadiness).toHaveBeenCalledTimes(1);

    // Click refresh
    const refreshBtn = screen.getByTestId('probes-refresh-btn');
    await user.click(refreshBtn);

    // Should trigger another fetch
    await waitFor(() => {
      expect(api.fetchLivenessProbe).toHaveBeenCalledTimes(2);
      expect(api.fetchReadiness).toHaveBeenCalledTimes(2);
    });
  });

  it('displays informational text about probes', async () => {
    vi.mocked(api.fetchLivenessProbe).mockResolvedValue(mockLivenessHealthy);
    vi.mocked(api.fetchReadiness).mockResolvedValue(mockReadinessHealthy);

    render(<KubernetesProbesPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('kubernetes-probes-panel')).toBeInTheDocument();
    });

    // Check info text
    expect(screen.getByText(/Used by Kubernetes to determine if the container needs to be/)).toBeInTheDocument();
    expect(screen.getByText(/Used by Kubernetes to determine if the container can receive/)).toBeInTheDocument();
  });

  it('handles partial fetch failure gracefully', async () => {
    vi.mocked(api.fetchLivenessProbe).mockResolvedValue(mockLivenessHealthy);
    vi.mocked(api.fetchReadiness).mockRejectedValue(new Error('Redis connection failed'));

    render(<KubernetesProbesPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('kubernetes-probes-panel')).toBeInTheDocument();
    });

    // Liveness should be healthy
    expect(screen.getByTestId('probe-status-badge-liveness')).toHaveTextContent('Passing');

    // Readiness should show failing due to error
    expect(screen.getByTestId('probe-status-badge-readiness')).toHaveTextContent('Failing');
  });

  it('applies custom className', async () => {
    vi.mocked(api.fetchLivenessProbe).mockResolvedValue(mockLivenessHealthy);
    vi.mocked(api.fetchReadiness).mockResolvedValue(mockReadinessHealthy);

    render(<KubernetesProbesPanel className="custom-class" />);

    await waitFor(() => {
      expect(screen.getByTestId('kubernetes-probes-panel')).toBeInTheDocument();
    });

    const panel = screen.getByTestId('kubernetes-probes-panel');
    expect(panel.className).toContain('custom-class');
  });

  it('uses custom data-testid', async () => {
    vi.mocked(api.fetchLivenessProbe).mockResolvedValue(mockLivenessHealthy);
    vi.mocked(api.fetchReadiness).mockResolvedValue(mockReadinessHealthy);

    render(<KubernetesProbesPanel data-testid="custom-testid" />);

    await waitFor(() => {
      expect(screen.getByTestId('custom-testid')).toBeInTheDocument();
    });
  });

  it('displays response time when available', async () => {
    vi.mocked(api.fetchLivenessProbe).mockResolvedValue(mockLivenessHealthy);
    vi.mocked(api.fetchReadiness).mockResolvedValue(mockReadinessHealthy);

    render(<KubernetesProbesPanel />);

    await waitFor(() => {
      expect(screen.getByTestId('kubernetes-probes-panel')).toBeInTheDocument();
    });

    // Response time should be displayed (regex because exact value varies)
    const responseTimeElements = screen.getAllByText(/Response time:/);
    expect(responseTimeElements.length).toBeGreaterThan(0);
  });
});

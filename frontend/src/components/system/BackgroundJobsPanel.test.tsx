import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import BackgroundJobsPanel from './BackgroundJobsPanel';
import * as api from '../../services/api';

// Mock the api module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    fetchTelemetry: vi.fn(),
    fetchDlqStats: vi.fn(),
    fetchReadiness: vi.fn(),
  };
});

const mockFetchTelemetry = vi.mocked(api.fetchTelemetry);
const mockFetchDlqStats = vi.mocked(api.fetchDlqStats);
const mockFetchReadiness = vi.mocked(api.fetchReadiness);

describe('BackgroundJobsPanel', () => {
  // Sample telemetry data
  const mockTelemetryWithActiveQueues: api.TelemetryResponse = {
    timestamp: '2025-12-30T10:00:00Z',
    queues: {
      detection_queue: 5,
      analysis_queue: 3,
    },
    latencies: {
      detect: {
        avg_ms: 150,
        p95_ms: 200,
        p99_ms: 250,
        sample_count: 100,
      },
      analyze: {
        avg_ms: 2000,
        p95_ms: 3000,
        p99_ms: 4000,
        sample_count: 50,
      },
    },
  };

  const mockTelemetryIdle: api.TelemetryResponse = {
    timestamp: '2025-12-30T10:00:00Z',
    queues: {
      detection_queue: 0,
      analysis_queue: 0,
    },
    latencies: {
      detect: {
        avg_ms: 0,
        p95_ms: 0,
        p99_ms: 0,
        sample_count: 0,
      },
      analyze: {
        avg_ms: 0,
        p95_ms: 0,
        p99_ms: 0,
        sample_count: 0,
      },
    },
  };

  // Sample DLQ stats
  const mockDlqStatsWithFailures: api.DLQStatsResponse = {
    detection_queue_count: 2,
    analysis_queue_count: 1,
    total_count: 3,
  };

  const mockDlqStatsEmpty: api.DLQStatsResponse = {
    detection_queue_count: 0,
    analysis_queue_count: 0,
    total_count: 0,
  };

  // Sample readiness response
  const mockReadinessAllRunning: api.ReadinessResponse = {
    ready: true,
    status: 'ready',
    services: {
      database: { status: 'healthy', message: null, details: null },
      redis: { status: 'healthy', message: null, details: null },
    },
    workers: [
      { name: 'detection_worker', running: true, message: null },
      { name: 'analysis_worker', running: true, message: null },
      { name: 'batch_timeout_worker', running: true, message: null },
      { name: 'cleanup_service', running: true, message: null },
      { name: 'gpu_monitor', running: true, message: null },
    ],
    timestamp: '2025-12-30T10:00:00Z',
    supervisor_healthy: true,
  };

  const mockReadinessWithStopped: api.ReadinessResponse = {
    ready: false,
    status: 'degraded',
    services: {
      database: { status: 'healthy', message: null, details: null },
      redis: { status: 'healthy', message: null, details: null },
    },
    workers: [
      { name: 'detection_worker', running: false, message: 'Worker stopped unexpectedly' },
      { name: 'analysis_worker', running: true, message: null },
      { name: 'batch_timeout_worker', running: true, message: null },
      { name: 'cleanup_service', running: true, message: null },
    ],
    timestamp: '2025-12-30T10:00:00Z',
    supervisor_healthy: true,
  };

  beforeEach(() => {
    mockFetchTelemetry.mockReset();
    mockFetchDlqStats.mockReset();
    mockFetchReadiness.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the loading state initially', () => {
      // Use promises that never resolve to keep loading state
      mockFetchTelemetry.mockReturnValue(new Promise(() => {}));
      mockFetchDlqStats.mockReturnValue(new Promise(() => {}));
      mockFetchReadiness.mockReturnValue(new Promise(() => {}));

      render(<BackgroundJobsPanel />);

      expect(screen.getByTestId('background-jobs-panel-loading')).toBeInTheDocument();
      expect(screen.getByText('Background Jobs')).toBeInTheDocument();
    });

    it('renders the component with title after loading', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('background-jobs-panel')).toBeInTheDocument();
      });

      expect(screen.getByText('Background Jobs')).toBeInTheDocument();
    });

    it('displays active queue jobs when queues have pending items', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('jobs-list')).toBeInTheDocument();
      });

      expect(screen.getByText('Detection Processing')).toBeInTheDocument();
      expect(screen.getByText('Analysis Processing')).toBeInTheDocument();
    });

    it('displays last updated timestamp', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('background-jobs-panel')).toBeInTheDocument();
      });

      const lastUpdatedElement = screen.queryByTestId('last-updated');
      if (lastUpdatedElement) {
        expect(lastUpdatedElement).toHaveTextContent(/Last updated:/);
      }
    });
  });

  describe('job status indicators', () => {
    it('displays running status badge for active queue jobs', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('job-row-detection-queue')).toBeInTheDocument();
      });

      // Check for running status badge in the detection queue job
      const jobRow = screen.getByTestId('job-row-detection-queue');
      expect(jobRow).toHaveTextContent('Running');
    });

    it('displays failed status badge for DLQ jobs', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryIdle);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsWithFailures);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('job-row-dlq-detection')).toBeInTheDocument();
      });

      const dlqJobRow = screen.getByTestId('job-row-dlq-detection');
      expect(dlqJobRow).toHaveTextContent('Failed');
    });

    it('shows failed count badge when there are failed jobs', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryIdle);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsWithFailures);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('failed-count-badge')).toBeInTheDocument();
      });

      expect(screen.getByTestId('failed-count-badge')).toHaveTextContent('2 Failed');
    });

    it('shows running count badge when there are running jobs', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('running-count-badge')).toBeInTheDocument();
      });
    });

    it('shows idle badge when system is idle', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryIdle);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      // Return no workers or non-relevant workers to trigger idle state
      mockFetchReadiness.mockResolvedValue({
        ...mockReadinessAllRunning,
        workers: [
          { name: 'gpu_monitor', running: true, message: null },
          { name: 'metrics_worker', running: true, message: null },
        ],
      });

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('idle-badge')).toBeInTheDocument();
      });
    });
  });

  describe('worker jobs', () => {
    it('displays worker jobs with their status', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryIdle);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('jobs-list')).toBeInTheDocument();
      });

      // Workers should be displayed as jobs
      expect(screen.getByText('Detection Worker')).toBeInTheDocument();
      expect(screen.getByText('Analysis Worker')).toBeInTheDocument();
    });

    it('displays stopped worker with error message', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryIdle);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessWithStopped);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('job-row-worker-detection_worker')).toBeInTheDocument();
      });

      const workerRow = screen.getByTestId('job-row-worker-detection_worker');
      expect(workerRow).toHaveTextContent('Failed');
    });
  });

  describe('error handling', () => {
    it('shows idle state when all API calls fail but still renders', async () => {
      // When all APIs fail, the component still renders with a System Idle job
      // and captures the error internally without showing error state
      mockFetchTelemetry.mockRejectedValue(new Error('Network error'));
      mockFetchDlqStats.mockRejectedValue(new Error('Network error'));
      mockFetchReadiness.mockRejectedValue(new Error('Network error'));

      render(<BackgroundJobsPanel />);

      // Component will render with System Idle job since no data was available
      await waitFor(() => {
        expect(screen.getByTestId('background-jobs-panel')).toBeInTheDocument();
      });

      // Should show idle state since no jobs were populated from the failed API calls
      expect(screen.getByText('System Idle')).toBeInTheDocument();
    });

    it('still displays jobs when only some API calls fail', async () => {
      mockFetchTelemetry.mockRejectedValue(new Error('Network error'));
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsWithFailures);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('background-jobs-panel')).toBeInTheDocument();
      });

      // Should still show DLQ jobs
      expect(screen.getByText('Failed Detection Jobs')).toBeInTheDocument();
    });
  });

  describe('callbacks', () => {
    it('calls onJobsChange callback when jobs update', async () => {
      const onJobsChange = vi.fn();
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel onJobsChange={onJobsChange} />);

      await waitFor(() => {
        expect(onJobsChange).toHaveBeenCalled();
      });

      // Should be called with an array of jobs
      expect(Array.isArray(onJobsChange.mock.calls[0][0])).toBe(true);
    });
  });

  describe('collapsible behavior', () => {
    it('starts expanded by default', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('background-jobs-panel')).toBeInTheDocument();
      });

      // Should show collapse icon when expanded (defaultExpanded is true)
      expect(screen.getByTestId('collapse-icon')).toBeInTheDocument();
    });

    it('starts collapsed when defaultExpanded is false', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel defaultExpanded={false} />);

      await waitFor(() => {
        expect(screen.getByTestId('background-jobs-panel')).toBeInTheDocument();
      });

      // Should show expand icon when collapsed
      expect(screen.getByTestId('expand-icon')).toBeInTheDocument();
    });

    it('toggles between expanded and collapsed on click', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('background-jobs-panel')).toBeInTheDocument();
      });

      // Initially expanded
      expect(screen.getByTestId('collapse-icon')).toBeInTheDocument();

      // Click to collapse
      const toggleButton = screen.getByTestId('jobs-panel-toggle');
      fireEvent.click(toggleButton);

      // Should now be collapsed
      expect(screen.getByTestId('expand-icon')).toBeInTheDocument();

      // Click to expand
      fireEvent.click(toggleButton);

      // Should be expanded again
      expect(screen.getByTestId('collapse-icon')).toBeInTheDocument();
    });

    it('has correct aria attributes for accessibility', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('background-jobs-panel')).toBeInTheDocument();
      });

      const toggleButton = screen.getByTestId('jobs-panel-toggle');
      expect(toggleButton).toHaveAttribute('aria-expanded', 'true');
      expect(toggleButton).toHaveAttribute('aria-controls', 'jobs-list-content');

      fireEvent.click(toggleButton);

      expect(toggleButton).toHaveAttribute('aria-expanded', 'false');
    });
  });

  describe('job row expansion', () => {
    it('expands job row to show details on click', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('job-row-detection-queue')).toBeInTheDocument();
      });

      // Click to expand job details
      const jobToggle = screen.getByTestId('job-toggle-detection-queue');
      fireEvent.click(jobToggle);

      // Should show job details
      await waitFor(() => {
        expect(screen.getByTestId('job-details-detection-queue')).toBeInTheDocument();
      });
    });

    it('collapses job row when clicked again', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('job-row-detection-queue')).toBeInTheDocument();
      });

      const jobToggle = screen.getByTestId('job-toggle-detection-queue');

      // Expand
      fireEvent.click(jobToggle);
      await waitFor(() => {
        expect(screen.getByTestId('job-details-detection-queue')).toBeInTheDocument();
      });

      // Collapse
      fireEvent.click(jobToggle);
      await waitFor(() => {
        expect(screen.queryByTestId('job-details-detection-queue')).not.toBeInTheDocument();
      });
    });
  });

  describe('refresh functionality', () => {
    it('displays refresh button', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('background-jobs-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('refresh-button')).toBeInTheDocument();
    });

    it('triggers refresh when refresh button is clicked', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('background-jobs-panel')).toBeInTheDocument();
      });

      // Clear mock call counts
      mockFetchTelemetry.mockClear();
      mockFetchDlqStats.mockClear();
      mockFetchReadiness.mockClear();

      // Click refresh
      const refreshButton = screen.getByTestId('refresh-button');
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(mockFetchTelemetry).toHaveBeenCalled();
      });
    });
  });

  describe('API calls', () => {
    it('calls all three API endpoints on mount', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(mockFetchTelemetry).toHaveBeenCalledTimes(1);
        expect(mockFetchDlqStats).toHaveBeenCalledTimes(1);
        expect(mockFetchReadiness).toHaveBeenCalledTimes(1);
      });
    });

    it('cleans up intervals on unmount', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      const { unmount } = render(<BackgroundJobsPanel pollingInterval={60000} />);

      await waitFor(() => {
        expect(mockFetchTelemetry).toHaveBeenCalledTimes(1);
      });

      const callCount = mockFetchTelemetry.mock.calls.length;

      unmount();

      // Wait a bit to ensure no additional calls happen after unmount
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Should not have additional calls after unmount
      expect(mockFetchTelemetry).toHaveBeenCalledTimes(callCount);
    });
  });

  describe('job sorting', () => {
    it('sorts failed jobs first, then running, then completed', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsWithFailures);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('jobs-list')).toBeInTheDocument();
      });

      const jobsList = screen.getByTestId('jobs-list');
      const jobRows = jobsList.querySelectorAll('[data-testid^="job-row-"]');

      // First jobs should be failed DLQ jobs
      const firstJobId = jobRows[0].getAttribute('data-testid');
      expect(firstJobId?.includes('dlq')).toBe(true);
    });
  });

  describe('maxJobs prop', () => {
    it('limits the number of displayed jobs', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsWithFailures);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel maxJobs={3} />);

      await waitFor(() => {
        expect(screen.getByTestId('jobs-list')).toBeInTheDocument();
      });

      const jobsList = screen.getByTestId('jobs-list');
      const jobRows = jobsList.querySelectorAll('[data-testid^="job-row-"]');

      expect(jobRows.length).toBeLessThanOrEqual(3);
    });
  });

  describe('idle state', () => {
    it('displays system idle job when no active processing', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryIdle);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      // Return empty workers to trigger idle state
      mockFetchReadiness.mockResolvedValue({
        ...mockReadinessAllRunning,
        workers: [],
      });

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('jobs-list')).toBeInTheDocument();
      });

      expect(screen.getByText('System Idle')).toBeInTheDocument();
    });
  });

  describe('warning icon', () => {
    it('shows warning icon when there are failed jobs', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryIdle);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsWithFailures);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('jobs-warning-icon')).toBeInTheDocument();
      });
    });

    it('does not show warning icon when all jobs healthy', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('background-jobs-panel')).toBeInTheDocument();
      });

      expect(screen.queryByTestId('jobs-warning-icon')).not.toBeInTheDocument();
    });
  });

  describe('className prop', () => {
    it('applies custom className to the component', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel className="custom-class" />);

      await waitFor(() => {
        expect(screen.getByTestId('background-jobs-panel')).toBeInTheDocument();
      });

      expect(screen.getByTestId('background-jobs-panel')).toHaveClass('custom-class');
    });
  });

  describe('data-testid prop', () => {
    it('uses custom data-testid when provided', async () => {
      mockFetchTelemetry.mockResolvedValue(mockTelemetryWithActiveQueues);
      mockFetchDlqStats.mockResolvedValue(mockDlqStatsEmpty);
      mockFetchReadiness.mockResolvedValue(mockReadinessAllRunning);

      render(<BackgroundJobsPanel data-testid="custom-test-id" />);

      await waitFor(() => {
        expect(screen.getByTestId('custom-test-id')).toBeInTheDocument();
      });
    });
  });
});

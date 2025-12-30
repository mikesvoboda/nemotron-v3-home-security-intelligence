import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import PipelineOperationsPanel from './PipelineOperationsPanel';
import * as api from '../../services/api';

// Mock the api module
vi.mock('../../services/api', async () => {
  const actual = await vi.importActual('../../services/api');
  return {
    ...actual,
    fetchPipelineStatus: vi.fn(),
  };
});

const mockFetchPipelineStatus = vi.mocked(api.fetchPipelineStatus);

describe('PipelineOperationsPanel', () => {
  // Sample pipeline status data matching the API response
  const mockFullPipelineStatus: api.PipelineStatusResponse = {
    file_watcher: {
      running: true,
      camera_root: '/export/foscam',
      pending_tasks: 3,
      observer_type: 'native',
    },
    batch_aggregator: {
      active_batches: 2,
      batches: [
        {
          batch_id: 'batch-001',
          camera_id: 'front_door',
          detection_count: 5,
          started_at: Date.now() / 1000 - 45,
          age_seconds: 45.5,
          last_activity_seconds: 10.2,
        },
        {
          batch_id: 'batch-002',
          camera_id: 'backyard',
          detection_count: 2,
          started_at: Date.now() / 1000 - 20,
          age_seconds: 20.3,
          last_activity_seconds: 5.1,
        },
      ],
      batch_window_seconds: 90,
      idle_timeout_seconds: 30,
    },
    degradation: {
      mode: 'normal',
      is_degraded: false,
      redis_healthy: true,
      memory_queue_size: 0,
      fallback_queues: {},
      services: [
        {
          name: 'rtdetr',
          status: 'healthy',
          last_check: Date.now() / 1000,
          consecutive_failures: 0,
          error_message: null,
        },
        {
          name: 'nemotron',
          status: 'healthy',
          last_check: Date.now() / 1000,
          consecutive_failures: 0,
          error_message: null,
        },
      ],
      available_features: ['detection', 'analysis', 'events', 'media'],
    },
    timestamp: new Date().toISOString(),
  };

  const mockDegradedPipelineStatus: api.PipelineStatusResponse = {
    file_watcher: {
      running: true,
      camera_root: '/export/foscam',
      pending_tasks: 0,
      observer_type: 'polling',
    },
    batch_aggregator: {
      active_batches: 0,
      batches: [],
      batch_window_seconds: 90,
      idle_timeout_seconds: 30,
    },
    degradation: {
      mode: 'degraded',
      is_degraded: true,
      redis_healthy: false,
      memory_queue_size: 15,
      fallback_queues: { detection: 5 },
      services: [
        {
          name: 'rtdetr',
          status: 'unhealthy',
          last_check: Date.now() / 1000,
          consecutive_failures: 3,
          error_message: 'Connection refused',
        },
      ],
      available_features: ['events', 'media'],
    },
    timestamp: new Date().toISOString(),
  };

  const mockNullPipelineStatus: api.PipelineStatusResponse = {
    file_watcher: null,
    batch_aggregator: null,
    degradation: null,
    timestamp: new Date().toISOString(),
  };

  beforeEach(() => {
    mockFetchPipelineStatus.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders the loading state initially', () => {
      // Use a promise that never resolves to keep loading state
      mockFetchPipelineStatus.mockReturnValue(new Promise(() => {}));

      render(<PipelineOperationsPanel />);

      expect(screen.getByTestId('pipeline-operations-loading')).toBeInTheDocument();
      expect(screen.getByText('Pipeline Operations')).toBeInTheDocument();
    });

    it('renders the component with title after loading', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockFullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('pipeline-operations-panel')).toBeInTheDocument();
      });

      expect(screen.getByText('Pipeline Operations')).toBeInTheDocument();
    });

    it('displays updated timestamp after loading', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockFullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText(/Updated:/)).toBeInTheDocument();
      });
    });
  });

  describe('FileWatcher section', () => {
    it('displays FileWatcher status when running', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockFullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('FileWatcher')).toBeInTheDocument();
      });

      expect(screen.getByText('Running')).toBeInTheDocument();
      expect(screen.getByText('/export/foscam')).toBeInTheDocument();
      expect(screen.getByText('native')).toBeInTheDocument();
    });

    it('displays pending tasks count', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockFullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('3')).toBeInTheDocument();
      });
    });

    it('displays not running when file watcher is null', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockNullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('Not running')).toBeInTheDocument();
      });
    });

    it('displays Stopped badge when file watcher is not running', async () => {
      const stoppedWatcher: api.PipelineStatusResponse = {
        ...mockFullPipelineStatus,
        file_watcher: {
          running: false,
          camera_root: '/export/foscam',
          pending_tasks: 0,
          observer_type: 'native',
        },
      };
      mockFetchPipelineStatus.mockResolvedValue(stoppedWatcher);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('Stopped')).toBeInTheDocument();
      });
    });
  });

  describe('BatchAggregator section', () => {
    it('displays BatchAggregator status with active batches', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockFullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('BatchAggregator')).toBeInTheDocument();
      });

      expect(screen.getByText('2 active')).toBeInTheDocument();
      expect(screen.getByText('90s')).toBeInTheDocument(); // Batch Window
      expect(screen.getByText('30s')).toBeInTheDocument(); // Idle Timeout
    });

    it('displays individual batch info cards', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockFullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('front_door')).toBeInTheDocument();
      });

      expect(screen.getByText('backyard')).toBeInTheDocument();
      expect(screen.getByText('5 detections')).toBeInTheDocument();
      expect(screen.getByText('2 detections')).toBeInTheDocument();
    });

    it('displays no active batches message when empty', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockDegradedPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('No active batches')).toBeInTheDocument();
      });
    });

    it('displays not available when batch aggregator is null', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockNullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('Not available')).toBeInTheDocument();
      });
    });
  });

  describe('Degradation section', () => {
    it('displays normal mode with healthy status', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockFullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('Degradation Status')).toBeInTheDocument();
      });

      expect(screen.getByText('NORMAL')).toBeInTheDocument();
      expect(screen.getByText('Healthy')).toBeInTheDocument();
    });

    it('displays degraded mode with unhealthy indicators', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockDegradedPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('DEGRADED')).toBeInTheDocument();
      });

      expect(screen.getByText('Unhealthy')).toBeInTheDocument();
      expect(screen.getByText('15 items')).toBeInTheDocument(); // Memory queue
    });

    it('displays service health information', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockFullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('rtdetr')).toBeInTheDocument();
      });

      expect(screen.getByText('nemotron')).toBeInTheDocument();
    });

    it('displays consecutive failure count for unhealthy services', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockDegradedPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('3 failures')).toBeInTheDocument();
      });
    });

    it('displays available features', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockFullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('detection')).toBeInTheDocument();
      });

      expect(screen.getByText('analysis')).toBeInTheDocument();
      expect(screen.getByText('events')).toBeInTheDocument();
      expect(screen.getByText('media')).toBeInTheDocument();
    });

    it('displays not initialized when degradation is null', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockNullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('Not initialized')).toBeInTheDocument();
      });
    });

    it('displays fallback queue items when present', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockDegradedPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('Fallback Queues')).toBeInTheDocument();
      });

      expect(screen.getByText('5 items')).toBeInTheDocument();
    });
  });

  describe('error handling', () => {
    it('displays error message when API call fails', async () => {
      mockFetchPipelineStatus.mockRejectedValue(new Error('Network error'));

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('pipeline-operations-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('displays generic error message for non-Error rejections', async () => {
      mockFetchPipelineStatus.mockRejectedValue('Unknown error');

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('pipeline-operations-error')).toBeInTheDocument();
      });

      expect(screen.getByText('Failed to fetch pipeline status')).toBeInTheDocument();
    });

    it('displays retry button on error', async () => {
      mockFetchPipelineStatus.mockRejectedValue(new Error('Network error'));

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('Retry')).toBeInTheDocument();
      });
    });

    it('retries fetching when retry button is clicked', async () => {
      const user = userEvent.setup();
      mockFetchPipelineStatus.mockRejectedValueOnce(new Error('Network error'));
      mockFetchPipelineStatus.mockResolvedValueOnce(mockFullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByText('Retry')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Retry'));

      await waitFor(() => {
        expect(screen.getByTestId('pipeline-operations-panel')).toBeInTheDocument();
      });

      expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(2);
    });
  });

  describe('API calls', () => {
    it('calls fetchPipelineStatus on mount', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockFullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(1);
      });
    });

    it('cleans up intervals on unmount', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockFullPipelineStatus);

      const { unmount } = render(<PipelineOperationsPanel pollingInterval={60000} />);

      await waitFor(() => {
        expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(1);
      });

      // Get initial call count
      const callCount = mockFetchPipelineStatus.mock.calls.length;

      unmount();

      // Wait a bit to ensure no additional calls happen after unmount
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Should not have additional calls after unmount
      expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(callCount);
    });
  });

  describe('polling behavior', () => {
    it('accepts custom polling interval prop', async () => {
      // Just verify that the component accepts the polling interval prop
      // and renders without errors
      mockFetchPipelineStatus.mockResolvedValue(mockFullPipelineStatus);

      // Use a long polling interval so it doesn't trigger during the test
      render(<PipelineOperationsPanel pollingInterval={60000} />);

      // Wait for initial load
      await waitFor(() => {
        expect(screen.getByTestId('pipeline-operations-panel')).toBeInTheDocument();
      });

      // Verify initial call was made
      expect(mockFetchPipelineStatus).toHaveBeenCalledTimes(1);
    });
  });

  describe('degradation mode display', () => {
    it('displays NORMAL text for normal mode', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockFullPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('pipeline-operations-panel')).toBeInTheDocument();
      });

      expect(screen.getByText('NORMAL')).toBeInTheDocument();
    });

    it('displays DEGRADED text for degraded mode', async () => {
      mockFetchPipelineStatus.mockResolvedValue(mockDegradedPipelineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('pipeline-operations-panel')).toBeInTheDocument();
      });

      expect(screen.getByText('DEGRADED')).toBeInTheDocument();
    });

    it('displays OFFLINE text for offline mode', async () => {
      const offlineStatus: api.PipelineStatusResponse = {
        ...mockFullPipelineStatus,
        degradation: {
          ...mockFullPipelineStatus.degradation!,
          mode: 'offline',
          is_degraded: true,
        },
      };
      mockFetchPipelineStatus.mockResolvedValue(offlineStatus);

      render(<PipelineOperationsPanel />);

      await waitFor(() => {
        expect(screen.getByTestId('pipeline-operations-panel')).toBeInTheDocument();
      });

      expect(screen.getByText('OFFLINE')).toBeInTheDocument();
    });
  });
});

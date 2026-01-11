import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi, afterEach } from 'vitest';

import DlqMonitor from './DlqMonitor';
import * as api from '../../services/api';

// Mock the API module
vi.mock('../../services/api');

describe('DlqMonitor', () => {
  const mockStats: api.DLQStatsResponse = {
    detection_queue_count: 2,
    analysis_queue_count: 1,
    total_count: 3,
  };

  const mockEmptyStats: api.DLQStatsResponse = {
    detection_queue_count: 0,
    analysis_queue_count: 0,
    total_count: 0,
  };

  const mockDetectionJobs: api.DLQJobsResponse = {
    queue_name: 'dlq:detection_queue',
    items: [
      {
        original_job: {
          camera_id: 'front_door',
          file_path: '/export/foscam/front_door/image_001.jpg',
          timestamp: '2025-12-23T10:30:00.000000',
        },
        error: 'Connection refused: detector service unavailable',
        attempt_count: 3,
        first_failed_at: '2025-12-23T10:30:05.000000',
        last_failed_at: '2025-12-23T10:30:15.000000',
        queue_name: 'detection_queue',
      },
      {
        original_job: {
          camera_id: 'back_yard',
          file_path: '/export/foscam/back_yard/image_002.jpg',
          timestamp: '2025-12-23T10:31:00.000000',
        },
        error: 'Timeout waiting for response',
        attempt_count: 2,
        first_failed_at: '2025-12-23T10:31:05.000000',
        last_failed_at: '2025-12-23T10:31:10.000000',
        queue_name: 'detection_queue',
      },
    ],
    pagination: {
      total: 2,
      limit: 100,
      offset: 0,
      has_more: false,
    },
  };

  const mockAnalysisJobs: api.DLQJobsResponse = {
    queue_name: 'dlq:analysis_queue',
    items: [
      {
        original_job: {
          event_id: 123,
          detections: [],
        },
        error: 'LLM service unavailable',
        attempt_count: 5,
        first_failed_at: '2025-12-23T11:00:00.000000',
        last_failed_at: '2025-12-23T11:00:30.000000',
        queue_name: 'analysis_queue',
      },
    ],
    pagination: {
      total: 1,
      limit: 100,
      offset: 0,
      has_more: false,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
    // Default mocks
    vi.mocked(api.fetchDlqStats).mockResolvedValue(mockStats);
    vi.mocked(api.fetchDlqJobs).mockImplementation((queueName) => {
      if (queueName === 'dlq:detection_queue') {
        return Promise.resolve(mockDetectionJobs);
      }
      return Promise.resolve(mockAnalysisJobs);
    });
    vi.mocked(api.requeueAllDlqJobs).mockResolvedValue({
      success: true,
      message: 'Requeued 2 jobs',
      job: null,
    });
    vi.mocked(api.clearDlq).mockResolvedValue({
      success: true,
      message: 'Cleared 2 jobs from dlq:detection_queue',
      queue_name: 'dlq:detection_queue',
    });
  });

  afterEach(() => {
    vi.clearAllTimers();
  });

  it('renders component with title', async () => {
    render(<DlqMonitor refreshInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Dead Letter Queue')).toBeInTheDocument();
    });
  });

  it('shows loading skeleton while fetching stats', () => {
    vi.mocked(api.fetchDlqStats).mockImplementation(() => new Promise(() => {}));

    render(<DlqMonitor refreshInterval={0} />);

    const skeletons = document.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('displays total failed job count badge', async () => {
    render(<DlqMonitor refreshInterval={0} />);

    await waitFor(() => {
      const badge = screen.getByTestId('dlq-total-badge');
      expect(badge).toHaveTextContent('3 failed');
    });
  });

  it('displays empty state when no failed jobs', async () => {
    vi.mocked(api.fetchDlqStats).mockResolvedValue(mockEmptyStats);

    render(<DlqMonitor refreshInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('No failed jobs in queue')).toBeInTheDocument();
    });
  });

  it('displays error message when fetch fails', async () => {
    vi.mocked(api.fetchDlqStats).mockRejectedValue(new Error('Network error'));

    render(<DlqMonitor refreshInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('displays generic error for non-Error objects', async () => {
    vi.mocked(api.fetchDlqStats).mockRejectedValue('Unknown error');

    render(<DlqMonitor refreshInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load DLQ stats')).toBeInTheDocument();
    });
  });

  it('shows queue cards for queues with failed jobs', async () => {
    render(<DlqMonitor refreshInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      expect(screen.getByText('Analysis Queue')).toBeInTheDocument();
    });
  });

  it('does not show badge when no failed jobs exist', async () => {
    vi.mocked(api.fetchDlqStats).mockResolvedValue(mockEmptyStats);

    render(<DlqMonitor refreshInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('No failed jobs in queue')).toBeInTheDocument();
    });

    expect(screen.queryByTestId('dlq-total-badge')).not.toBeInTheDocument();
  });

  describe('queue expansion', () => {
    it('expands queue when clicked', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(api.fetchDlqJobs).toHaveBeenCalledWith('dlq:detection_queue');
      });
    });

    it('displays job details when expanded', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(
          screen.getByText('Connection refused: detector service unavailable')
        ).toBeInTheDocument();
      });

      expect(screen.getByText('Timeout waiting for response')).toBeInTheDocument();
    });

    it('shows attempt count for jobs', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(screen.getByText('Attempts: 3')).toBeInTheDocument();
      });

      expect(screen.getByText('Attempts: 2')).toBeInTheDocument();
    });

    it('shows error when fetching jobs fails', async () => {
      vi.mocked(api.fetchDlqJobs).mockRejectedValue(new Error('Failed to fetch jobs'));

      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(screen.getByText('Failed to fetch jobs')).toBeInTheDocument();
      });
    });

    it('collapses queue when clicked again', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(
          screen.getByText('Connection refused: detector service unavailable')
        ).toBeInTheDocument();
      });

      // Click again to collapse
      fireEvent.click(detectionQueueButton);

      // Jobs should no longer be visible
      expect(
        screen.queryByText('Connection refused: detector service unavailable')
      ).not.toBeInTheDocument();
    });
  });

  describe('requeue functionality', () => {
    it('shows confirmation dialog when clicking Requeue All', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(screen.getByText('Requeue All')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Requeue All'));

      expect(screen.getByText(/Requeue all 2 jobs\?/)).toBeInTheDocument();
      expect(screen.getByText('Confirm')).toBeInTheDocument();
      expect(screen.getByText('Cancel')).toBeInTheDocument();
    });

    it('cancels requeue when clicking Cancel', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(screen.getByText('Requeue All')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Requeue All'));
      fireEvent.click(screen.getByText('Cancel'));

      expect(screen.queryByText(/Requeue all 2 jobs\?/)).not.toBeInTheDocument();
    });

    it('calls requeue API when confirming', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(screen.getByText('Requeue All')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Requeue All'));
      fireEvent.click(screen.getByText('Confirm'));

      await waitFor(() => {
        expect(api.requeueAllDlqJobs).toHaveBeenCalledWith('dlq:detection_queue');
      });
    });

    it('shows success message after requeue', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(screen.getByText('Requeue All')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Requeue All'));
      fireEvent.click(screen.getByText('Confirm'));

      await waitFor(() => {
        expect(screen.getByText('Requeued 2 jobs')).toBeInTheDocument();
      });
    });

    it('shows error message when requeue fails', async () => {
      vi.mocked(api.requeueAllDlqJobs).mockRejectedValue(new Error('Requeue failed'));

      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(screen.getByText('Requeue All')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Requeue All'));
      fireEvent.click(screen.getByText('Confirm'));

      await waitFor(() => {
        expect(screen.getByText('Requeue failed')).toBeInTheDocument();
      });
    });
  });

  describe('clear functionality', () => {
    it('shows confirmation dialog when clicking Clear All', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(screen.getByText('Clear All')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Clear All'));

      expect(screen.getByText(/Permanently delete all 2 jobs\?/)).toBeInTheDocument();
    });

    it('calls clear API when confirming', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(screen.getByText('Clear All')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Clear All'));
      fireEvent.click(screen.getByText('Confirm'));

      await waitFor(() => {
        expect(api.clearDlq).toHaveBeenCalledWith('dlq:detection_queue');
      });
    });

    it('shows success message after clear', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(screen.getByText('Clear All')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Clear All'));
      fireEvent.click(screen.getByText('Confirm'));

      await waitFor(() => {
        expect(screen.getByText('Cleared 2 jobs from dlq:detection_queue')).toBeInTheDocument();
      });
    });

    it('shows error message when clear fails', async () => {
      vi.mocked(api.clearDlq).mockRejectedValue(new Error('Clear failed'));

      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(screen.getByText('Clear All')).toBeInTheDocument();
      });

      fireEvent.click(screen.getByText('Clear All'));
      fireEvent.click(screen.getByText('Confirm'));

      await waitFor(() => {
        expect(screen.getByText('Clear failed')).toBeInTheDocument();
      });
    });
  });

  describe('refresh functionality', () => {
    it('refresh button triggers stats reload', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      // Wait for initial load to complete - use badge which indicates stats loaded
      await waitFor(() => {
        expect(screen.getByTestId('dlq-total-badge')).toBeInTheDocument();
      });

      // Initial call should have happened (check outside waitFor for clarity)
      expect(api.fetchDlqStats).toHaveBeenCalledTimes(1);

      // Click refresh button using aria-label for reliable selection
      const refreshButton = screen.getByLabelText('Refresh DLQ stats');
      expect(refreshButton).toBeInTheDocument();
      fireEvent.click(refreshButton);

      await waitFor(() => {
        expect(api.fetchDlqStats).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('footer', () => {
    it('displays explanatory text', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(
          screen.getByText(/Dead Letter Queue stores failed processing jobs/i)
        ).toBeInTheDocument();
      });
    });
  });

  describe('accessibility', () => {
    it('queue buttons have proper aria-labels', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByLabelText('Toggle Detection Queue details')).toBeInTheDocument();
      });
    });

    it('queue buttons have aria-expanded state', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      expect(detectionQueueButton).toHaveAttribute('aria-expanded', 'false');

      fireEvent.click(detectionQueueButton);

      expect(detectionQueueButton).toHaveAttribute('aria-expanded', 'true');
    });
  });

  describe('custom className', () => {
    it('applies custom className to component', async () => {
      render(<DlqMonitor className="custom-test-class" refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Dead Letter Queue')).toBeInTheDocument();
      });

      const card = screen.getByText('Dead Letter Queue').closest('.custom-test-class');
      expect(card).toBeInTheDocument();
    });
  });

  describe('auto-refresh', () => {
    it('does not auto-refresh when refreshInterval is 0', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      // Wait for initial load
      await waitFor(() => {
        expect(api.fetchDlqStats).toHaveBeenCalledTimes(1);
      });

      // Wait a bit to ensure no additional calls
      await new Promise((resolve) => setTimeout(resolve, 100));

      // Should still only have the initial call
      expect(api.fetchDlqStats).toHaveBeenCalledTimes(1);
    });

    it('sets up auto-refresh when refreshInterval is positive', async () => {
      // Use a short interval for testing - 100ms
      render(<DlqMonitor refreshInterval={100} />);

      // Wait for initial load
      await waitFor(() => {
        expect(api.fetchDlqStats).toHaveBeenCalledTimes(1);
      });

      // Wait for the interval to trigger (add margin for test environment)
      await new Promise((resolve) => setTimeout(resolve, 150));

      // Should have been called at least twice
      await waitFor(() => {
        expect(api.fetchDlqStats).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('formatTimestamp error handling', () => {
    it('displays Invalid Date when timestamp cannot be parsed', async () => {
      const statsWithInvalidTimestamps: api.DLQStatsResponse = {
        detection_queue_count: 1,
        analysis_queue_count: 0,
        total_count: 1,
      };

      const invalidTimestampJobs: api.DLQJobsResponse = {
        queue_name: 'dlq:detection_queue',
        items: [
          {
            original_job: { camera_id: 'test' },
            error: 'Test error with invalid timestamps',
            attempt_count: 1,
            first_failed_at: 'invalid-date-string',
            last_failed_at: 'another-invalid-date',
            queue_name: 'detection_queue',
          },
        ],
        pagination: {
          total: 1,
          limit: 100,
          offset: 0,
          has_more: false,
        },
      };

      vi.mocked(api.fetchDlqStats).mockResolvedValue(statsWithInvalidTimestamps);
      vi.mocked(api.fetchDlqJobs).mockResolvedValue(invalidTimestampJobs);

      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        // Wait for the error message to appear which confirms jobs loaded
        expect(screen.getByText('Test error with invalid timestamps')).toBeInTheDocument();
      });

      // Now check that invalid timestamps show "Invalid Date"
      expect(screen.getByText(/Attempts: 1/)).toBeInTheDocument();
      // new Date('invalid-string').toLocaleString() returns "Invalid Date"
      expect(screen.getAllByText(/Invalid Date/i).length).toBeGreaterThan(0);
    });
  });

  describe('clear confirmation cancel button', () => {
    it('cancels clear when clicking Cancel button', async () => {
      render(<DlqMonitor refreshInterval={0} />);

      await waitFor(() => {
        expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      });

      const detectionQueueButton = screen.getByLabelText('Toggle Detection Queue details');
      fireEvent.click(detectionQueueButton);

      await waitFor(() => {
        expect(screen.getByText('Clear All')).toBeInTheDocument();
      });

      // Click Clear All to show confirmation
      fireEvent.click(screen.getByText('Clear All'));

      // Verify confirmation is shown
      expect(screen.getByText(/Permanently delete all 2 jobs\?/)).toBeInTheDocument();

      // Find and click the Cancel button within the clear confirmation
      const cancelButtons = screen.getAllByText('Cancel');
      const clearCancelButton = cancelButtons.find((button) => {
        const parent = button.closest('div');
        return parent?.textContent?.includes('Permanently delete');
      });

      expect(clearCancelButton).toBeDefined();
      fireEvent.click(clearCancelButton!);

      // Confirmation should be hidden
      await waitFor(() => {
        expect(screen.queryByText(/Permanently delete all 2 jobs\?/)).not.toBeInTheDocument();
      });

      // Clear API should NOT have been called
      expect(api.clearDlq).not.toHaveBeenCalled();
    });
  });
});

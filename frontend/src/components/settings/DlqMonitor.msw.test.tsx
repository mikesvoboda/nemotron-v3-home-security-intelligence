/**
 * DlqMonitor MSW Test Example
 *
 * Demonstrates MSW patterns for components that fetch data on mount and
 * support user actions (requeue, clear).
 *
 * @see src/mocks/handlers.ts - Default API handlers
 * @see src/mocks/server.ts - MSW server configuration
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { http, HttpResponse, delay } from 'msw';
import { beforeEach, describe, expect, it } from 'vitest';

import DlqMonitor from './DlqMonitor';
import { server } from '../../mocks/server';
import { clearInFlightRequests } from '../../services/api';

import type { DLQStatsResponse, DLQJobsResponse, DLQRequeueResponse, DLQClearResponse } from '../../services/api';

// ============================================================================
// Test Data
// ============================================================================

const mockStats: DLQStatsResponse = {
  detection_queue_count: 2,
  analysis_queue_count: 1,
  total_count: 3,
};

const mockEmptyStats: DLQStatsResponse = {
  detection_queue_count: 0,
  analysis_queue_count: 0,
  total_count: 0,
};

const mockDetectionJobs: DLQJobsResponse = {
  queue_name: 'dlq:detection_queue',
  jobs: [
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
  count: 2,
};

const mockAnalysisJobs: DLQJobsResponse = {
  queue_name: 'dlq:analysis_queue',
  jobs: [
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
  count: 1,
};

// ============================================================================
// Tests
// ============================================================================

describe('DlqMonitor (MSW)', () => {
  beforeEach(() => {
    clearInFlightRequests();
  });

  it('renders component with title', async () => {
    server.use(
      http.get('/api/dlq/stats', () => {
        return HttpResponse.json(mockStats);
      })
    );

    render(<DlqMonitor refreshInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Dead Letter Queue')).toBeInTheDocument();
    });
  });

  it('shows loading skeleton while fetching stats', () => {
    server.use(
      http.get('/api/dlq/stats', async () => {
        await delay('infinite');
        return HttpResponse.json(mockStats);
      })
    );

    render(<DlqMonitor refreshInterval={0} />);

    const skeletons = document.querySelectorAll('.skeleton');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('displays total failed job count badge', async () => {
    server.use(
      http.get('/api/dlq/stats', () => {
        return HttpResponse.json(mockStats);
      })
    );

    render(<DlqMonitor refreshInterval={0} />);

    await waitFor(() => {
      const badge = screen.getByTestId('dlq-total-badge');
      expect(badge).toHaveTextContent('3 failed');
    });
  });

  it('displays empty state when no failed jobs', async () => {
    server.use(
      http.get('/api/dlq/stats', () => {
        return HttpResponse.json(mockEmptyStats);
      })
    );

    render(<DlqMonitor refreshInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('No failed jobs in queue')).toBeInTheDocument();
    });
  });

  it('displays error message when fetch fails', async () => {
    // Use 400 to avoid retry backoff
    server.use(
      http.get('/api/dlq/stats', () => {
        return HttpResponse.json(
          { detail: 'Network error' },
          { status: 400 }
        );
      })
    );

    render(<DlqMonitor refreshInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  it('shows queue cards for queues with failed jobs', async () => {
    server.use(
      http.get('/api/dlq/stats', () => {
        return HttpResponse.json(mockStats);
      })
    );

    render(<DlqMonitor refreshInterval={0} />);

    await waitFor(() => {
      expect(screen.getByText('Detection Queue')).toBeInTheDocument();
      expect(screen.getByText('Analysis Queue')).toBeInTheDocument();
    });
  });

  describe('queue expansion', () => {
    it('displays job details when expanded', async () => {
      server.use(
        http.get('/api/dlq/stats', () => {
          return HttpResponse.json(mockStats);
        }),
        http.get('/api/dlq/jobs/:queueName', ({ params }) => {
          const queueName = params.queueName as string;
          if (queueName === 'dlq:detection_queue') {
            return HttpResponse.json(mockDetectionJobs);
          }
          return HttpResponse.json(mockAnalysisJobs);
        })
      );

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
      server.use(
        http.get('/api/dlq/stats', () => {
          return HttpResponse.json(mockStats);
        }),
        http.get('/api/dlq/jobs/:queueName', () => {
          return HttpResponse.json(mockDetectionJobs);
        })
      );

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
  });

  describe('requeue functionality', () => {
    it('calls requeue API when confirming', async () => {
      let requeueCalled = false;
      server.use(
        http.get('/api/dlq/stats', () => {
          return HttpResponse.json(mockStats);
        }),
        http.get('/api/dlq/jobs/:queueName', () => {
          return HttpResponse.json(mockDetectionJobs);
        }),
        // The actual API endpoint is /api/dlq/requeue-all/:queueName
        http.post('/api/dlq/requeue-all/:queueName', () => {
          requeueCalled = true;
          const response: DLQRequeueResponse = {
            success: true,
            message: 'Requeued 2 jobs',
            job: null,
          };
          return HttpResponse.json(response);
        })
      );

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
        expect(requeueCalled).toBe(true);
      });
    });

    it('shows success message after requeue', async () => {
      server.use(
        http.get('/api/dlq/stats', () => {
          return HttpResponse.json(mockStats);
        }),
        http.get('/api/dlq/jobs/:queueName', () => {
          return HttpResponse.json(mockDetectionJobs);
        }),
        http.post('/api/dlq/requeue-all/:queueName', () => {
          const response: DLQRequeueResponse = {
            success: true,
            message: 'Requeued 2 jobs',
            job: null,
          };
          return HttpResponse.json(response);
        })
      );

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
      server.use(
        http.get('/api/dlq/stats', () => {
          return HttpResponse.json(mockStats);
        }),
        http.get('/api/dlq/jobs/:queueName', () => {
          return HttpResponse.json(mockDetectionJobs);
        }),
        http.post('/api/dlq/requeue-all/:queueName', () => {
          return HttpResponse.json(
            { detail: 'Requeue failed' },
            { status: 400 }
          );
        })
      );

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
    it('calls clear API when confirming', async () => {
      let clearCalled = false;
      server.use(
        http.get('/api/dlq/stats', () => {
          return HttpResponse.json(mockStats);
        }),
        http.get('/api/dlq/jobs/:queueName', () => {
          return HttpResponse.json(mockDetectionJobs);
        }),
        // The actual API endpoint is DELETE /api/dlq/:queueName
        http.delete('/api/dlq/:queueName', () => {
          clearCalled = true;
          const response: DLQClearResponse = {
            success: true,
            message: 'Cleared 2 jobs from dlq:detection_queue',
            queue_name: 'dlq:detection_queue',
          };
          return HttpResponse.json(response);
        })
      );

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
        expect(clearCalled).toBe(true);
      });
    });

    it('shows success message after clear', async () => {
      server.use(
        http.get('/api/dlq/stats', () => {
          return HttpResponse.json(mockStats);
        }),
        http.get('/api/dlq/jobs/:queueName', () => {
          return HttpResponse.json(mockDetectionJobs);
        }),
        http.delete('/api/dlq/:queueName', () => {
          const response: DLQClearResponse = {
            success: true,
            message: 'Cleared 2 jobs from dlq:detection_queue',
            queue_name: 'dlq:detection_queue',
          };
          return HttpResponse.json(response);
        })
      );

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
  });
});

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import LogsDashboard from './LogsDashboard';
import * as api from '../../services/api';

import type { Camera, LogEntry, LogsResponse, LogStats } from '../../services/api';

// Mock API module
vi.mock('../../services/api');

describe('LogsDashboard', () => {
  const mockCameras: Camera[] = [
    {
      id: 'camera-1',
      name: 'Front Door',
      folder_path: '/path/to/front',
      status: 'online',
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T12:00:00Z',
    },
    {
      id: 'camera-2',
      name: 'Back Yard',
      folder_path: '/path/to/back',
      status: 'online',
      created_at: '2024-01-01T00:00:00Z',
      last_seen_at: '2024-01-01T12:00:00Z',
    },
  ];

  const mockLogs: LogEntry[] = [
    {
      id: 1,
      timestamp: '2024-01-01T10:00:00Z',
      level: 'ERROR',
      component: 'api',
      message: 'Failed to process request',
      camera_id: 'camera-1',
      event_id: 1,
      request_id: 'req-123',
      detection_id: null,
      duration_ms: 150,
      extra: { error_code: '500' },
      source: 'backend',
    },
    {
      id: 2,
      timestamp: '2024-01-01T11:00:00Z',
      level: 'INFO',
      component: 'detector',
      message: 'Detection completed successfully',
      camera_id: 'camera-2',
      event_id: null,
      request_id: null,
      detection_id: 5,
      duration_ms: 250,
      extra: null,
      source: 'backend',
    },
    {
      id: 3,
      timestamp: '2024-01-01T12:00:00Z',
      level: 'WARNING',
      component: 'frontend',
      message: 'Slow API response',
      camera_id: null,
      event_id: null,
      request_id: 'req-456',
      detection_id: null,
      duration_ms: 3000,
      extra: { threshold_ms: 2000 },
      source: 'frontend',
    },
  ];

  const mockLogsResponse: LogsResponse = {
    logs: mockLogs,
    count: 3,
    limit: 50,
    offset: 0,
  };

  const mockLogStats: LogStats = {
    total_today: 150,
    errors_today: 5,
    warnings_today: 10,
    by_component: {
      api: 50,
      detector: 40,
      frontend: 30,
      file_watcher: 30,
    },
    by_level: {
      ERROR: 5,
      WARNING: 10,
      INFO: 100,
      DEBUG: 35,
    },
    top_component: 'api',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
    vi.mocked(api.fetchLogs).mockResolvedValue(mockLogsResponse);
    vi.mocked(api.fetchLogStats).mockResolvedValue(mockLogStats);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('Rendering', () => {
    it('renders the dashboard header', () => {
      render(<LogsDashboard />);

      expect(screen.getByText('System Logs')).toBeInTheDocument();
      expect(
        screen.getByText(
          'View and filter all system logs from backend services and frontend components'
        )
      ).toBeInTheDocument();
    });

    it('displays loading state initially', () => {
      render(<LogsDashboard />);

      expect(screen.getByText('Loading logs...')).toBeInTheDocument();
    });

    it('displays logs after loading', async () => {
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Failed to process request')).toBeInTheDocument();
      });

      expect(screen.getByText('Detection completed successfully')).toBeInTheDocument();
      expect(screen.getByText('Slow API response')).toBeInTheDocument();
    });

    it('displays log statistics', async () => {
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Log Statistics')).toBeInTheDocument();
      });
    });

    it('displays filter panel', async () => {
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });
    });

    it('displays result count', async () => {
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Showing 1-3 of 3 logs')).toBeInTheDocument();
      });
    });
  });

  describe('Filtering', () => {
    it('filters logs by level', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const levelSelect = screen.getByLabelText('Log Level');
      await user.selectOptions(levelSelect, 'ERROR');

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(
          expect.objectContaining({ level: 'ERROR', offset: 0 })
        );
      });
    });

    it('filters logs by component', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const componentSelect = screen.getByLabelText('Component');
      await user.selectOptions(componentSelect, 'api');

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(
          expect.objectContaining({ component: 'api', offset: 0 })
        );
      });
    });

    it('filters logs by camera', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const cameraSelect = screen.getByLabelText('Camera');
      await user.selectOptions(cameraSelect, 'camera-1');

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(
          expect.objectContaining({ camera_id: 'camera-1', offset: 0 })
        );
      });
    });

    it('filters logs by date range', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Show Filters')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Show Filters'));

      const startDateInput = screen.getByLabelText('Start Date');
      const endDateInput = screen.getByLabelText('End Date');

      await user.type(startDateInput, '2024-01-01');
      await user.type(endDateInput, '2024-01-31');

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(
          expect.objectContaining({
            start_date: '2024-01-01',
            end_date: '2024-01-31',
            offset: 0,
          })
        );
      });
    });

    it('searches logs by message content', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search log messages...')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search log messages...');
      await user.type(searchInput, 'Failed');

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(
          expect.objectContaining({ search: 'Failed', offset: 0 })
        );
      });
    });

    it('clears search query', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search log messages...')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search log messages...');
      await user.type(searchInput, 'Failed');

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(expect.objectContaining({ search: 'Failed' }));
      });

      // Click clear button
      const clearButton = screen.getByLabelText('Clear search');
      await user.click(clearButton);

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(
          expect.not.objectContaining({ search: expect.anything() })
        );
      });
    });

    it('resets to first page when filters change', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      // Mock response for pagination
      const manyLogs: LogEntry[] = Array.from({ length: 100 }, (_, i) => ({
        id: i + 1,
        timestamp: `2024-01-01T${String(i % 24).padStart(2, '0')}:00:00Z`,
        level: 'INFO' as const,
        component: 'api',
        message: `Log message ${i + 1}`,
        camera_id: null,
        event_id: null,
        request_id: null,
        detection_id: null,
        duration_ms: null,
        extra: null,
        source: 'backend',
      }));

      vi.mocked(api.fetchLogs).mockResolvedValue({
        logs: manyLogs.slice(0, 50),
        count: 100,
        limit: 50,
        offset: 0,
      });

      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
      });

      // Navigate to page 2
      const nextButton = screen.getByLabelText('Next page');
      await user.click(nextButton);

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(expect.objectContaining({ offset: 50 }));
      });

      // Now apply a filter - this should reset to page 1
      await user.click(screen.getByText('Show Filters'));

      const levelSelect = screen.getByLabelText('Log Level');
      await user.selectOptions(levelSelect, 'ERROR');

      // Should reset to offset 0 when filters change
      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(
          expect.objectContaining({ level: 'ERROR', offset: 0 })
        );
      });
    });
  });

  describe('Pagination', () => {
    beforeEach(() => {
      // Mock response with more logs for pagination
      const manyLogs: LogEntry[] = Array.from({ length: 100 }, (_, i) => ({
        id: i + 1,
        timestamp: `2024-01-01T${String(i % 24).padStart(2, '0')}:00:00Z`,
        level: 'INFO' as const,
        component: 'api',
        message: `Log message ${i + 1}`,
        camera_id: null,
        event_id: null,
        request_id: null,
        detection_id: null,
        duration_ms: null,
        extra: null,
        source: 'backend',
      }));

      vi.mocked(api.fetchLogs).mockResolvedValue({
        logs: manyLogs.slice(0, 50),
        count: 100,
        limit: 50,
        offset: 0,
      });
    });

    it('navigates to next page', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
      });

      const nextButton = screen.getByLabelText('Next page');
      expect(nextButton).not.toBeDisabled();

      await user.click(nextButton);

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(expect.objectContaining({ offset: 50 }));
      });
    });

    it('navigates to previous page', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
      });

      // Navigate to page 2 first
      const nextButton = screen.getByLabelText('Next page');
      await user.click(nextButton);

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(expect.objectContaining({ offset: 50 }));
      });

      // Now navigate back to page 1
      const prevButton = screen.getByLabelText('Previous page');
      await user.click(prevButton);

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(expect.objectContaining({ offset: 0 }));
      });
    });

    it('disables previous button on first page', async () => {
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
      });

      const prevButton = screen.getByLabelText('Previous page');
      expect(prevButton).toBeDisabled();
    });

    it('disables next button on last page', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
      });

      // Navigate to page 2 (last page)
      const nextButton = screen.getByLabelText('Next page');
      await user.click(nextButton);

      await waitFor(() => {
        expect(nextButton).toBeDisabled();
      });
    });
  });

  describe('Log Detail Modal', () => {
    it('opens modal when clicking on a log row', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Failed to process request')).toBeInTheDocument();
      });

      // Click on the log row
      const logRow = screen.getByText('Failed to process request').closest('tr');
      expect(logRow).toBeInTheDocument();

      if (logRow) {
        await user.click(logRow);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });
      }
    });

    it('closes modal when clicking close button', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Failed to process request')).toBeInTheDocument();
      });

      // Open modal
      const logRow = screen.getByText('Failed to process request').closest('tr');
      if (logRow) {
        await user.click(logRow);

        await waitFor(() => {
          expect(screen.getByRole('dialog')).toBeInTheDocument();
        });

        // Close modal - get first close button in dialog
        const dialog = screen.getByRole('dialog');
        const closeButtons = within(dialog).getAllByLabelText('Close modal');
        await user.click(closeButtons[0]);

        await waitFor(() => {
          expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
        });
      }
    });
  });

  describe('Error Handling', () => {
    it('displays error message when fetching logs fails', async () => {
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchLogStats).mockResolvedValue(mockLogStats);
      vi.mocked(api.fetchLogs).mockRejectedValue(new Error('Network error'));

      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Error Loading Logs')).toBeInTheDocument();
      });

      expect(screen.getByText('Network error')).toBeInTheDocument();
    });

    it('handles camera fetch errors gracefully', async () => {
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockRejectedValue(new Error('Camera fetch failed'));
      vi.mocked(api.fetchLogs).mockResolvedValue(mockLogsResponse);
      vi.mocked(api.fetchLogStats).mockResolvedValue(mockLogStats);

      render(<LogsDashboard />);

      // Should still load logs
      await waitFor(() => {
        expect(screen.getByText('Failed to process request')).toBeInTheDocument();
      });
    });

    it('handles log stats fetch errors gracefully', async () => {
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchLogs).mockResolvedValue(mockLogsResponse);
      vi.mocked(api.fetchLogStats).mockRejectedValue(new Error('Stats fetch failed'));

      render(<LogsDashboard />);

      // Should still load logs
      await waitFor(() => {
        expect(screen.getByText('Failed to process request')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling with non-Error objects', () => {
    it('displays generic error message when error is not an Error instance', async () => {
      vi.clearAllMocks();
      vi.mocked(api.fetchCameras).mockResolvedValue(mockCameras);
      vi.mocked(api.fetchLogStats).mockResolvedValue(mockLogStats);
      vi.mocked(api.fetchLogs).mockRejectedValue('string error');

      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Error Loading Logs')).toBeInTheDocument();
      });

      expect(screen.getByText('Failed to load logs')).toBeInTheDocument();
    });
  });

  describe('Empty States', () => {
    it('shows empty state when no logs exist', async () => {
      vi.mocked(api.fetchLogs).mockResolvedValue({
        logs: [],
        count: 0,
        limit: 50,
        offset: 0,
      });

      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('No Logs Found')).toBeInTheDocument();
      });

      expect(screen.getByText(/No logs match the current filters/)).toBeInTheDocument();
    });

    it('shows filtered empty state when filters match no logs', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Failed to process request')).toBeInTheDocument();
      });

      // Apply filter that returns no results
      vi.mocked(api.fetchLogs).mockResolvedValue({
        logs: [],
        count: 0,
        limit: 50,
        offset: 0,
      });

      await user.click(screen.getByText('Show Filters'));

      const levelSelect = screen.getByLabelText('Log Level');
      await user.selectOptions(levelSelect, 'CRITICAL');

      await waitFor(() => {
        expect(screen.getByText('No Logs Found')).toBeInTheDocument();
      });

      expect(screen.getByText(/No logs match the current filters/)).toBeInTheDocument();
    });
  });

  describe('Stats Card Filter Integration', () => {
    it('filters logs by ERROR level when clicking Errors Today card', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Log Statistics')).toBeInTheDocument();
      });

      // Click on Errors Today card
      const errorCard = screen.getByRole('button', { name: 'Filter by errors' });
      await user.click(errorCard);

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(
          expect.objectContaining({ level: 'ERROR', offset: 0 })
        );
      });
    });

    it('filters logs by WARNING level when clicking Warnings Today card', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Log Statistics')).toBeInTheDocument();
      });

      // Click on Warnings Today card
      const warningCard = screen.getByRole('button', { name: 'Filter by warnings' });
      await user.click(warningCard);

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(
          expect.objectContaining({ level: 'WARNING', offset: 0 })
        );
      });
    });

    it('clears level filter when clicking already active stats card (toggle off)', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Log Statistics')).toBeInTheDocument();
      });

      // Click on Errors Today card to activate
      const errorCard = screen.getByRole('button', { name: 'Filter by errors' });
      await user.click(errorCard);

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(
          expect.objectContaining({ level: 'ERROR' })
        );
      });

      // Click again to deactivate (toggle off)
      await user.click(errorCard);

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(
          expect.objectContaining({ level: undefined })
        );
      });
    });

    it('syncs stats card filter with filter dropdown', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Log Statistics')).toBeInTheDocument();
      });

      // Click on Errors Today card
      const errorCard = screen.getByRole('button', { name: 'Filter by errors' });
      await user.click(errorCard);

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(
          expect.objectContaining({ level: 'ERROR' })
        );
      });

      // Open filters and verify dropdown shows ERROR
      await user.click(screen.getByText('Show Filters'));

      await waitFor(() => {
        const levelSelect = screen.getByLabelText('Log Level');
        expect(levelSelect).toHaveValue('ERROR');
      });
    });

    it('updates stats card active state when filter dropdown changes', async () => {
      const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
      render(<LogsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Log Statistics')).toBeInTheDocument();
      });

      // Open filters
      await user.click(screen.getByText('Show Filters'));

      // Select ERROR from dropdown
      const levelSelect = screen.getByLabelText('Log Level');
      await user.selectOptions(levelSelect, 'ERROR');

      await waitFor(() => {
        expect(api.fetchLogs).toHaveBeenCalledWith(
          expect.objectContaining({ level: 'ERROR' })
        );
      });

      // Verify the Errors Today card shows active state
      const errorCard = screen.getByRole('button', { name: 'Filter by errors' });
      expect(errorCard).toHaveClass('ring-2');
      expect(errorCard).toHaveClass('ring-red-500');
    });
  });
});

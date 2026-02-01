import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { WorkerManagementPanel } from './WorkerManagementPanel';
import * as useSupervisorStatusHook from '../../hooks/useSupervisorStatus';
import * as useWorkerActionsHook from '../../hooks/useWorkerActions';

vi.mock('../../hooks/useSupervisorStatus');
vi.mock('../../hooks/useWorkerActions');

describe('WorkerManagementPanel', () => {
  const mockRefetch = vi.fn();
  const mockStartWorker = vi.fn();
  const mockStopWorker = vi.fn();
  const mockRestartWorker = vi.fn();
  const mockResetWorker = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(useWorkerActionsHook.useWorkerActions).mockReturnValue({
      startWorker: mockStartWorker,
      stopWorker: mockStopWorker,
      restartWorker: mockRestartWorker,
      resetWorker: mockResetWorker,
      isLoading: false,
      error: null,
    });
  });

  it('renders loading skeleton when loading', () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
      refetch: mockRefetch,
    });

    render(<WorkerManagementPanel />);

    expect(screen.getByTestId('worker-management-loading')).toBeInTheDocument();
  });

  it('renders error state with retry button', () => {
    const errorMessage = 'Failed to load supervisor status';
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error(errorMessage),
      refetch: mockRefetch,
    });

    render(<WorkerManagementPanel />);

    expect(screen.getByTestId('worker-management-error')).toBeInTheDocument();
    expect(screen.getByText(errorMessage)).toBeInTheDocument();

    const retryButton = screen.getByRole('button', { name: /retry/i });
    fireEvent.click(retryButton);

    expect(mockRefetch).toHaveBeenCalledTimes(1);
  });

  it('renders supervisor status header', () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 4,
        workers: [],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    render(<WorkerManagementPanel />);

    expect(screen.getByTestId('supervisor-status-header')).toBeInTheDocument();
    expect(screen.getByText(/worker count/i)).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
  });

  it('renders worker cards for each worker', () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 2,
        workers: [
          {
            name: 'file_watcher',
            status: 'running',
            restart_count: 0,
            max_restarts: 5,
            last_started_at: '2025-01-31T10:00:00Z',
            last_crashed_at: null,
            error: null,
          },
          {
            name: 'detection_worker',
            status: 'stopped',
            restart_count: 0,
            max_restarts: 5,
            last_started_at: null,
            last_crashed_at: null,
            error: null,
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    render(<WorkerManagementPanel />);

    expect(screen.getByTestId('worker-card-file_watcher')).toBeInTheDocument();
    expect(screen.getByTestId('worker-card-detection_worker')).toBeInTheDocument();
  });

  it('shows correct status badge for running worker', () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 1,
        workers: [
          {
            name: 'file_watcher',
            status: 'running',
            restart_count: 0,
            max_restarts: 5,
            last_started_at: '2025-01-31T10:00:00Z',
            last_crashed_at: null,
            error: null,
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    render(<WorkerManagementPanel />);

    const statusBadge = screen.getByTestId('worker-status-badge-file_watcher');
    expect(statusBadge).toHaveTextContent(/running/i);
    expect(statusBadge).toHaveClass('bg-green-600');
  });

  it('shows correct status badge for stopped worker', () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 1,
        workers: [
          {
            name: 'file_watcher',
            status: 'stopped',
            restart_count: 0,
            max_restarts: 5,
            last_started_at: null,
            last_crashed_at: null,
            error: null,
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    render(<WorkerManagementPanel />);

    const statusBadge = screen.getByTestId('worker-status-badge-file_watcher');
    expect(statusBadge).toHaveTextContent(/stopped/i);
    expect(statusBadge).toHaveClass('bg-gray-600');
  });

  it('shows correct status badge for crashed worker', () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 1,
        workers: [
          {
            name: 'detection_worker',
            status: 'crashed',
            restart_count: 2,
            max_restarts: 5,
            last_started_at: '2025-01-31T09:00:00Z',
            last_crashed_at: '2025-01-31T10:00:00Z',
            error: 'Connection lost',
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    render(<WorkerManagementPanel />);

    const statusBadge = screen.getByTestId('worker-status-badge-detection_worker');
    expect(statusBadge).toHaveTextContent(/crashed/i);
    expect(statusBadge).toHaveClass('bg-yellow-600');
  });

  it('shows correct status badge for failed worker', () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 1,
        workers: [
          {
            name: 'detection_worker',
            status: 'failed',
            restart_count: 5,
            max_restarts: 5,
            last_started_at: '2025-01-31T08:00:00Z',
            last_crashed_at: '2025-01-31T10:00:00Z',
            error: 'Max restarts exceeded',
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    render(<WorkerManagementPanel />);

    const statusBadge = screen.getByTestId('worker-status-badge-detection_worker');
    expect(statusBadge).toHaveTextContent(/failed/i);
    expect(statusBadge).toHaveClass('bg-red-600');
  });

  it('shows restart count in format "X/Y"', () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 1,
        workers: [
          {
            name: 'detection_worker',
            status: 'running',
            restart_count: 3,
            max_restarts: 5,
            last_started_at: '2025-01-31T10:00:00Z',
            last_crashed_at: '2025-01-31T09:00:00Z',
            error: null,
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    render(<WorkerManagementPanel />);

    expect(screen.getByTestId('worker-restart-count-detection_worker')).toHaveTextContent(
      '3/5'
    );
  });

  it('shows last crash time if available', () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 1,
        workers: [
          {
            name: 'detection_worker',
            status: 'crashed',
            restart_count: 2,
            max_restarts: 5,
            last_started_at: '2025-01-31T09:00:00Z',
            last_crashed_at: '2025-01-31T10:00:00Z',
            error: 'Connection lost',
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    render(<WorkerManagementPanel />);

    expect(
      screen.getByTestId('worker-last-crash-detection_worker')
    ).toBeInTheDocument();
  });

  it('shows error message if worker has error', () => {
    const errorMessage = 'Connection timeout';
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 1,
        workers: [
          {
            name: 'detection_worker',
            status: 'crashed',
            restart_count: 3,
            max_restarts: 5,
            last_started_at: '2025-01-31T09:00:00Z',
            last_crashed_at: '2025-01-31T10:00:00Z',
            error: errorMessage,
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    render(<WorkerManagementPanel />);

    expect(screen.getByText(errorMessage)).toBeInTheDocument();
  });

  it('start button calls startWorker when clicked', async () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 1,
        workers: [
          {
            name: 'file_watcher',
            status: 'stopped',
            restart_count: 0,
            max_restarts: 5,
            last_started_at: null,
            last_crashed_at: null,
            error: null,
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    mockStartWorker.mockResolvedValue({
      success: true,
      message: 'Started',
      worker_name: 'file_watcher',
    });

    render(<WorkerManagementPanel />);

    const startButton = screen.getByTestId('worker-start-button-file_watcher');
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(mockStartWorker).toHaveBeenCalledWith('file_watcher');
    });
  });

  it('stop button calls stopWorker when clicked', async () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 1,
        workers: [
          {
            name: 'file_watcher',
            status: 'running',
            restart_count: 0,
            max_restarts: 5,
            last_started_at: '2025-01-31T10:00:00Z',
            last_crashed_at: null,
            error: null,
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    mockStopWorker.mockResolvedValue({
      success: true,
      message: 'Stopped',
      worker_name: 'file_watcher',
    });

    render(<WorkerManagementPanel />);

    const stopButton = screen.getByTestId('worker-stop-button-file_watcher');
    fireEvent.click(stopButton);

    // Confirm the action in the dialog
    const confirmButton = screen.getByTestId('confirm-button');
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(mockStopWorker).toHaveBeenCalledWith('file_watcher');
    });
  });

  it('restart button calls restartWorker when clicked', async () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 1,
        workers: [
          {
            name: 'file_watcher',
            status: 'running',
            restart_count: 1,
            max_restarts: 5,
            last_started_at: '2025-01-31T10:00:00Z',
            last_crashed_at: '2025-01-31T09:30:00Z',
            error: null,
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    mockRestartWorker.mockResolvedValue({
      success: true,
      message: 'Restarted',
      worker_name: 'file_watcher',
    });

    render(<WorkerManagementPanel />);

    const restartButton = screen.getByTestId('worker-restart-button-file_watcher');
    fireEvent.click(restartButton);

    // Confirm the action in the dialog
    const confirmButton = screen.getByTestId('confirm-button');
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(mockRestartWorker).toHaveBeenCalledWith('file_watcher');
    });
  });

  it('reset button appears only for failed workers', () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 2,
        workers: [
          {
            name: 'running_worker',
            status: 'running',
            restart_count: 0,
            max_restarts: 5,
            last_started_at: '2025-01-31T10:00:00Z',
            last_crashed_at: null,
            error: null,
          },
          {
            name: 'failed_worker',
            status: 'failed',
            restart_count: 5,
            max_restarts: 5,
            last_started_at: '2025-01-31T08:00:00Z',
            last_crashed_at: '2025-01-31T10:00:00Z',
            error: 'Max restarts exceeded',
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    render(<WorkerManagementPanel />);

    expect(
      screen.queryByTestId('worker-reset-button-running_worker')
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId('worker-reset-button-failed_worker')
    ).toBeInTheDocument();
  });

  it('confirmation dialog appears before dangerous actions', async () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 1,
        workers: [
          {
            name: 'file_watcher',
            status: 'running',
            restart_count: 0,
            max_restarts: 5,
            last_started_at: '2025-01-31T10:00:00Z',
            last_crashed_at: null,
            error: null,
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    render(<WorkerManagementPanel />);

    const stopButton = screen.getByTestId('worker-stop-button-file_watcher');
    fireEvent.click(stopButton);

    // Confirmation dialog should appear
    expect(screen.getByTestId('confirmation-dialog')).toBeInTheDocument();
    expect(screen.getByText(/are you sure/i)).toBeInTheDocument();

    // Confirm the action
    const confirmButton = screen.getByTestId('confirm-button');
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(mockStopWorker).toHaveBeenCalledWith('file_watcher');
    });
  });

  it('disabled state for buttons during operations', () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 1,
        workers: [
          {
            name: 'file_watcher',
            status: 'running',
            restart_count: 0,
            max_restarts: 5,
            last_started_at: '2025-01-31T10:00:00Z',
            last_crashed_at: null,
            error: null,
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    vi.mocked(useWorkerActionsHook.useWorkerActions).mockReturnValue({
      startWorker: mockStartWorker,
      stopWorker: mockStopWorker,
      restartWorker: mockRestartWorker,
      resetWorker: mockResetWorker,
      isLoading: true, // Operation in progress
      error: null,
    });

    render(<WorkerManagementPanel />);

    const stopButton = screen.getByTestId('worker-stop-button-file_watcher');
    const restartButton = screen.getByTestId('worker-restart-button-file_watcher');

    expect(stopButton).toBeDisabled();
    expect(restartButton).toBeDisabled();
  });

  it('handles empty worker list', () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 0,
        workers: [],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    render(<WorkerManagementPanel />);

    expect(screen.getByTestId('no-workers-message')).toBeInTheDocument();
  });

  it('refreshes data after worker action', async () => {
    vi.mocked(useSupervisorStatusHook.useSupervisorStatus).mockReturnValue({
      data: {
        running: true,
        worker_count: 1,
        workers: [
          {
            name: 'file_watcher',
            status: 'stopped',
            restart_count: 0,
            max_restarts: 5,
            last_started_at: null,
            last_crashed_at: null,
            error: null,
          },
        ],
        timestamp: '2025-01-31T10:35:00Z',
      },
      isLoading: false,
      error: null,
      refetch: mockRefetch,
    });

    mockStartWorker.mockResolvedValue({
      success: true,
      message: 'Started',
      worker_name: 'file_watcher',
    });

    render(<WorkerManagementPanel />);

    const startButton = screen.getByTestId('worker-start-button-file_watcher');
    fireEvent.click(startButton);

    await waitFor(() => {
      expect(mockStartWorker).toHaveBeenCalledWith('file_watcher');
      expect(mockRefetch).toHaveBeenCalled();
    });
  });
});

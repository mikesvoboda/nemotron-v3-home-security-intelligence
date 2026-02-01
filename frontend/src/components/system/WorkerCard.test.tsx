/**
 * Tests for WorkerCard component (NEM-4831).
 *
 * Tests worker card rendering including:
 * - Worker name and status display
 * - Status badge colors (green=running, red=crashed, yellow=restarting)
 * - Restart count and max restarts
 * - Last started/crashed timestamps
 * - Action buttons (restart, stop)
 * - Error messages
 * - Restart history accordion
 */
import { screen, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import WorkerCard from './WorkerCard';
import { renderWithProviders } from '../../test-utils/renderWithProviders';

import type { RestartHistoryItem } from '../../hooks/useRestartHistory';

describe('WorkerCard', () => {
  const mockWorker = {
    name: 'file_watcher',
    status: 'running' as const,
    restart_count: 0,
    max_restarts: 5,
    last_started_at: '2025-01-31T10:00:00Z',
    last_crashed_at: null,
    error: null,
  };

  const mockRestartHistory: RestartHistoryItem[] = [
    {
      worker_name: 'file_watcher',
      status: 'success',
      attempt: 1,
      timestamp: '2025-01-31T09:00:00Z',
      error: null,
    },
    {
      worker_name: 'file_watcher',
      status: 'success',
      attempt: 2,
      timestamp: '2025-01-31T09:30:00Z',
      error: null,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders worker name', () => {
      renderWithProviders(
        <WorkerCard worker={mockWorker} restartHistory={[]} onRestart={vi.fn()} onStop={vi.fn()} />
      );

      expect(screen.getByText('file_watcher')).toBeInTheDocument();
    });

    it('renders worker status badge', () => {
      renderWithProviders(
        <WorkerCard worker={mockWorker} restartHistory={[]} onRestart={vi.fn()} onStop={vi.fn()} />
      );

      expect(screen.getByTestId('worker-status-badge-file_watcher')).toBeInTheDocument();
    });

    it('renders restart count', () => {
      renderWithProviders(
        <WorkerCard worker={mockWorker} restartHistory={[]} onRestart={vi.fn()} onStop={vi.fn()} />
      );

      expect(screen.getByText(/restart count/i)).toBeInTheDocument();
      expect(screen.getByText('0 / 5')).toBeInTheDocument();
    });

    it('renders last started timestamp', () => {
      renderWithProviders(
        <WorkerCard worker={mockWorker} restartHistory={[]} onRestart={vi.fn()} onStop={vi.fn()} />
      );

      expect(screen.getByText(/last started/i)).toBeInTheDocument();
      expect(screen.getByText(/2025-01-31/)).toBeInTheDocument();
    });

    it('renders action buttons', () => {
      renderWithProviders(
        <WorkerCard worker={mockWorker} restartHistory={[]} onRestart={vi.fn()} onStop={vi.fn()} />
      );

      expect(screen.getByTestId('worker-action-restart-file_watcher')).toBeInTheDocument();
      expect(screen.getByTestId('worker-action-stop-file_watcher')).toBeInTheDocument();
    });

    it('renders card with correct testid', () => {
      renderWithProviders(
        <WorkerCard worker={mockWorker} restartHistory={[]} onRestart={vi.fn()} onStop={vi.fn()} />
      );

      expect(screen.getByTestId('worker-card-file_watcher')).toBeInTheDocument();
    });
  });

  describe('status badge colors', () => {
    it('shows green badge for running status', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, status: 'running' }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const badge = screen.getByTestId('worker-status-badge-file_watcher');
      expect(badge).toHaveClass('bg-green-600');
      expect(badge).toHaveTextContent('running');
    });

    it('shows red badge for crashed status', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, status: 'crashed' }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const badge = screen.getByTestId('worker-status-badge-file_watcher');
      expect(badge).toHaveClass('bg-red-600');
      expect(badge).toHaveTextContent('crashed');
    });

    it('shows yellow badge for restarting status', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, status: 'restarting' }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const badge = screen.getByTestId('worker-status-badge-file_watcher');
      expect(badge).toHaveClass('bg-yellow-600');
      expect(badge).toHaveTextContent('restarting');
    });

    it('shows gray badge for stopped status', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, status: 'stopped' }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const badge = screen.getByTestId('worker-status-badge-file_watcher');
      expect(badge).toHaveClass('bg-gray-600');
      expect(badge).toHaveTextContent('stopped');
    });

    it('shows red badge for failed status', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, status: 'failed' }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const badge = screen.getByTestId('worker-status-badge-file_watcher');
      expect(badge).toHaveClass('bg-red-600');
      expect(badge).toHaveTextContent('failed');
    });
  });

  describe('restart count display', () => {
    it('shows restart count and max restarts', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, restart_count: 2, max_restarts: 5 }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      expect(screen.getByText('2 / 5')).toBeInTheDocument();
    });

    it('highlights restart count in red when at max', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, restart_count: 5, max_restarts: 5 }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const countElement = screen.getByText('5 / 5');
      expect(countElement).toHaveClass('text-red-400');
    });

    it('highlights restart count in yellow when near max', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, restart_count: 4, max_restarts: 5 }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const countElement = screen.getByText('4 / 5');
      expect(countElement).toHaveClass('text-yellow-400');
    });

    it('shows normal color when restart count is low', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, restart_count: 1, max_restarts: 5 }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const countElement = screen.getByText('1 / 5');
      expect(countElement).toHaveClass('text-gray-300');
    });
  });

  describe('timestamp display', () => {
    it('shows last started timestamp when available', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, last_started_at: '2025-01-31T10:00:00Z' }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      expect(screen.getByText(/last started/i)).toBeInTheDocument();
      expect(screen.getByText(/2025-01-31/)).toBeInTheDocument();
    });

    it('shows never started when last_started_at is null', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, last_started_at: null }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      expect(screen.getByText(/never started/i)).toBeInTheDocument();
    });

    it('shows last crashed timestamp when available', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, last_crashed_at: '2025-01-31T10:30:00Z' }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      expect(screen.getByText(/last crashed/i)).toBeInTheDocument();
      expect(screen.getByText(/2025-01-31.*10:30/)).toBeInTheDocument();
    });

    it('does not show last crashed when null', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, last_crashed_at: null }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      expect(screen.queryByText(/last crashed/i)).not.toBeInTheDocument();
    });
  });

  describe('error display', () => {
    it('shows error message when present', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, error: 'Connection timeout' }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      expect(screen.getByText(/error/i)).toBeInTheDocument();
      expect(screen.getByText('Connection timeout')).toBeInTheDocument();
    });

    it('shows error with red styling', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, error: 'Max restarts exceeded' }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const errorElement = screen.getByText('Max restarts exceeded');
      expect(errorElement).toHaveClass('text-red-400');
    });

    it('does not show error section when error is null', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, error: null }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
    });
  });

  describe('action buttons', () => {
    it('restart button calls onRestart with worker name', async () => {
      const onRestart = vi.fn();
      const { user } = renderWithProviders(
        <WorkerCard worker={mockWorker} restartHistory={[]} onRestart={onRestart} onStop={vi.fn()} />
      );

      await user.click(screen.getByTestId('worker-action-restart-file_watcher'));

      expect(onRestart).toHaveBeenCalledWith('file_watcher');
    });

    it('stop button calls onStop with worker name', async () => {
      const onStop = vi.fn();
      const { user } = renderWithProviders(
        <WorkerCard worker={mockWorker} restartHistory={[]} onRestart={vi.fn()} onStop={onStop} />
      );

      await user.click(screen.getByTestId('worker-action-stop-file_watcher'));

      expect(onStop).toHaveBeenCalledWith('file_watcher');
    });

    it('restart button is disabled for stopped workers', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, status: 'stopped' }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      expect(screen.getByTestId('worker-action-restart-file_watcher')).toBeDisabled();
    });

    it('stop button is disabled for stopped workers', () => {
      renderWithProviders(
        <WorkerCard
          worker={{ ...mockWorker, status: 'stopped' }}
          restartHistory={[]}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      expect(screen.getByTestId('worker-action-stop-file_watcher')).toBeDisabled();
    });

    it('restart button has restart icon', () => {
      renderWithProviders(
        <WorkerCard worker={mockWorker} restartHistory={[]} onRestart={vi.fn()} onStop={vi.fn()} />
      );

      const restartButton = screen.getByTestId('worker-action-restart-file_watcher');
      expect(within(restartButton).getByTestId('restart-icon')).toBeInTheDocument();
    });

    it('stop button has stop icon', () => {
      renderWithProviders(
        <WorkerCard worker={mockWorker} restartHistory={[]} onRestart={vi.fn()} onStop={vi.fn()} />
      );

      const stopButton = screen.getByTestId('worker-action-stop-file_watcher');
      expect(within(stopButton).getByTestId('stop-icon')).toBeInTheDocument();
    });
  });

  describe('restart history accordion', () => {
    it('renders restart history accordion', () => {
      renderWithProviders(
        <WorkerCard
          worker={mockWorker}
          restartHistory={mockRestartHistory}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      expect(screen.getByTestId('restart-history-accordion')).toBeInTheDocument();
    });

    it('accordion is collapsed by default', () => {
      renderWithProviders(
        <WorkerCard
          worker={mockWorker}
          restartHistory={mockRestartHistory}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const content = screen.getByTestId('restart-history-content');
      expect(content).not.toHaveClass('expanded');
    });

    it('accordion expands when clicked', async () => {
      const { user } = renderWithProviders(
        <WorkerCard
          worker={mockWorker}
          restartHistory={mockRestartHistory}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const accordion = screen.getByTestId('restart-history-accordion');
      await user.click(accordion);

      const content = screen.getByTestId('restart-history-content');
      expect(content).toHaveClass('expanded');
    });

    it('shows restart history items when expanded', async () => {
      const { user } = renderWithProviders(
        <WorkerCard
          worker={mockWorker}
          restartHistory={mockRestartHistory}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const accordion = screen.getByTestId('restart-history-accordion');
      await user.click(accordion);

      expect(screen.getByTestId('restart-history-item-0')).toBeInTheDocument();
      expect(screen.getByTestId('restart-history-item-1')).toBeInTheDocument();
    });

    it('history items show timestamp', async () => {
      const { user } = renderWithProviders(
        <WorkerCard
          worker={mockWorker}
          restartHistory={mockRestartHistory}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const accordion = screen.getByTestId('restart-history-accordion');
      await user.click(accordion);

      expect(screen.getByText(/2025-01-31.*09:00/)).toBeInTheDocument();
    });

    it('history items show status', async () => {
      const { user } = renderWithProviders(
        <WorkerCard
          worker={mockWorker}
          restartHistory={mockRestartHistory}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const accordion = screen.getByTestId('restart-history-accordion');
      await user.click(accordion);

      expect(screen.getAllByText(/success/i).length).toBeGreaterThan(0);
    });

    it('history items show attempt number', async () => {
      const { user } = renderWithProviders(
        <WorkerCard
          worker={mockWorker}
          restartHistory={mockRestartHistory}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const accordion = screen.getByTestId('restart-history-accordion');
      await user.click(accordion);

      expect(screen.getByText(/attempt 1/i)).toBeInTheDocument();
      expect(screen.getByText(/attempt 2/i)).toBeInTheDocument();
    });

    it('shows empty state when no history', async () => {
      const { user } = renderWithProviders(
        <WorkerCard worker={mockWorker} restartHistory={[]} onRestart={vi.fn()} onStop={vi.fn()} />
      );

      const accordion = screen.getByTestId('restart-history-accordion');
      await user.click(accordion);

      expect(screen.getByTestId('restart-history-empty-state')).toBeInTheDocument();
      expect(screen.getByText(/no restart history/i)).toBeInTheDocument();
    });

    it('accordion shows history count badge', () => {
      renderWithProviders(
        <WorkerCard
          worker={mockWorker}
          restartHistory={mockRestartHistory}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      expect(screen.getByTestId('restart-history-count-badge')).toBeInTheDocument();
      expect(screen.getByTestId('restart-history-count-badge')).toHaveTextContent('2');
    });
  });

  describe('accessibility', () => {
    it('restart button has aria-label', () => {
      renderWithProviders(
        <WorkerCard worker={mockWorker} restartHistory={[]} onRestart={vi.fn()} onStop={vi.fn()} />
      );

      const restartButton = screen.getByTestId('worker-action-restart-file_watcher');
      expect(restartButton).toHaveAttribute('aria-label', 'Restart worker file_watcher');
    });

    it('stop button has aria-label', () => {
      renderWithProviders(
        <WorkerCard worker={mockWorker} restartHistory={[]} onRestart={vi.fn()} onStop={vi.fn()} />
      );

      const stopButton = screen.getByTestId('worker-action-stop-file_watcher');
      expect(stopButton).toHaveAttribute('aria-label', 'Stop worker file_watcher');
    });

    it('status badge has aria-label', () => {
      renderWithProviders(
        <WorkerCard worker={mockWorker} restartHistory={[]} onRestart={vi.fn()} onStop={vi.fn()} />
      );

      const badge = screen.getByTestId('worker-status-badge-file_watcher');
      expect(badge).toHaveAttribute('aria-label', 'Worker status: running');
    });

    it('accordion has aria-expanded attribute', () => {
      renderWithProviders(
        <WorkerCard
          worker={mockWorker}
          restartHistory={mockRestartHistory}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const accordion = screen.getByTestId('restart-history-accordion');
      expect(accordion).toHaveAttribute('aria-expanded', 'false');
    });

    it('accordion aria-expanded changes when clicked', async () => {
      const { user } = renderWithProviders(
        <WorkerCard
          worker={mockWorker}
          restartHistory={mockRestartHistory}
          onRestart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const accordion = screen.getByTestId('restart-history-accordion');
      await user.click(accordion);

      expect(accordion).toHaveAttribute('aria-expanded', 'true');
    });
  });
});

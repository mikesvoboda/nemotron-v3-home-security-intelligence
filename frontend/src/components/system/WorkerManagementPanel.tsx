/**
 * WorkerManagementPanel component for managing background workers (NEM-4831).
 *
 * Main panel displaying supervisor status and worker cards with:
 * - Supervisor status header with worker count
 * - Grid of worker cards with status and actions
 * - Confirmation dialogs for dangerous actions
 * - Toast notifications for action results
 *
 * @example
 * ```tsx
 * <WorkerManagementPanel data-testid="worker-management-panel" />
 * ```
 */

import { AlertCircle, Play, RefreshCw, RotateCcw } from 'lucide-react';
import { memo, useState, useCallback } from 'react';
import { toast } from 'sonner';

import { useSupervisorStatus, type WorkerStatus } from '../../hooks/useSupervisorStatus';
import { useWorkerActions } from '../../hooks/useWorkerActions';

export interface WorkerManagementPanelProps {
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
}

/**
 * Get badge color class for worker status
 */
function getStatusColorClass(status: WorkerStatus['status']): string {
  switch (status) {
    case 'running':
      return 'bg-green-600 text-white';
    case 'stopped':
      return 'bg-gray-600 text-white';
    case 'restarting':
      return 'bg-yellow-600 text-white';
    case 'crashed':
    case 'failed':
      return 'bg-red-600 text-white';
    default:
      return 'bg-gray-600 text-white';
  }
}

/**
 * Format timestamp for display
 */
function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

/**
 * Format relative time
 */
function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);

  if (diffMinutes < 1) return 'Just now';
  if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes === 1 ? '' : 's'} ago`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? '' : 's'} ago`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} day${diffDays === 1 ? '' : 's'} ago`;
}

/**
 * Confirmation dialog state
 */
interface ConfirmDialogState {
  isOpen: boolean;
  workerName: string;
  action: 'stop' | 'restart' | null;
}

/**
 * WorkerManagementPanel - Main panel for worker management
 */
export const WorkerManagementPanel = memo(function WorkerManagementPanel({
  'data-testid': testId = 'worker-management-panel',
}: WorkerManagementPanelProps) {
  const { data, isLoading, error, refetch } = useSupervisorStatus({ pollInterval: 10000 });
  const {
    startWorker: apiStartWorker,
    stopWorker: apiStopWorker,
    restartWorker: apiRestartWorker,
    resetWorker: apiResetWorker,
    isLoading: actionsLoading,
  } = useWorkerActions();

  // Confirmation dialog state
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState>({
    isOpen: false,
    workerName: '',
    action: null,
  });

  // Handle start worker action (no confirmation needed)
  const handleStartWorker = useCallback(
    async (name: string) => {
      try {
        const result = await apiStartWorker(name);
        if (result.success) {
          toast.success(`Worker "${name}" started successfully`);
          await refetch();
        }
      } catch (err) {
        toast.error(`Failed to start worker: ${err instanceof Error ? err.message : 'Unknown error'}`);
      }
    },
    [apiStartWorker, refetch]
  );

  // Show confirmation dialog for stop
  const handleStopClick = useCallback((name: string) => {
    setConfirmDialog({ isOpen: true, workerName: name, action: 'stop' });
  }, []);

  // Show confirmation dialog for restart
  const handleRestartClick = useCallback((name: string) => {
    setConfirmDialog({ isOpen: true, workerName: name, action: 'restart' });
  }, []);

  // Handle confirmed action
  const handleConfirmAction = useCallback(async () => {
    const { workerName, action } = confirmDialog;
    if (!action) return;

    try {
      let result;
      if (action === 'stop') {
        result = await apiStopWorker(workerName);
        if (result.success) {
          toast.success(`Worker "${workerName}" stopped successfully`);
        }
      } else if (action === 'restart') {
        result = await apiRestartWorker(workerName);
        if (result.success) {
          toast.success(`Worker "${workerName}" restarted successfully`);
        }
      }
      await refetch();
    } catch (err) {
      toast.error(
        `Failed to ${action} worker: ${err instanceof Error ? err.message : 'Unknown error'}`
      );
    } finally {
      setConfirmDialog({ isOpen: false, workerName: '', action: null });
    }
  }, [confirmDialog, apiStopWorker, apiRestartWorker, refetch]);

  // Handle cancel dialog
  const handleCancelDialog = useCallback(() => {
    setConfirmDialog({ isOpen: false, workerName: '', action: null });
  }, []);

  // Handle reset worker (for failed workers)
  const handleResetWorker = useCallback(
    async (name: string) => {
      try {
        const result = await apiResetWorker(name);
        if (result.success) {
          toast.success(`Worker "${name}" restart count reset successfully`);
          await refetch();
        }
      } catch (err) {
        toast.error(
          `Failed to reset worker: ${err instanceof Error ? err.message : 'Unknown error'}`
        );
      }
    },
    [apiResetWorker, refetch]
  );

  // Loading state
  if (isLoading) {
    return (
      <div className="p-4" data-testid="worker-management-loading">
        <div className="space-y-4">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg bg-gray-800" />
          ))}
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="p-4" data-testid="worker-management-error">
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <div className="flex-1">
            <p className="font-medium text-red-400">Error loading worker status</p>
            <p className="text-sm text-gray-400">{error.message}</p>
          </div>
          <button
            type="button"
            onClick={() => void refetch()}
            className="rounded-md bg-red-500/20 px-3 py-1.5 text-sm font-medium text-red-400 hover:bg-red-500/30"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Empty state
  if (!data?.workers || data.workers.length === 0) {
    return (
      <div className="p-4" data-testid={testId}>
        <div data-testid="supervisor-status-header" className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">Worker Count</span>
            <span className="font-medium text-white">{data?.worker_count ?? 0}</span>
          </div>
        </div>
        <div
          className="py-8 text-center text-gray-500"
          data-testid="no-workers-message"
        >
          No workers registered with the supervisor
        </div>
      </div>
    );
  }

  return (
    <div className="p-4" data-testid={testId}>
      {/* Supervisor Status Header */}
      <div data-testid="supervisor-status-header" className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-400">Worker Count</span>
            <span className="font-medium text-white" data-testid="worker-count">{data.worker_count}</span>
          </div>
          <div
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              data.running ? 'bg-green-600 text-white' : 'bg-red-600 text-white'
            }`}
            data-testid={data.running ? 'supervisor-status-running' : 'supervisor-status-stopped'}
          >
            {data.running ? 'Running' : 'Stopped'}
          </div>
        </div>
        <button
          type="button"
          onClick={() => void refetch()}
          className="flex items-center gap-1 rounded-md bg-gray-700 px-2 py-1 text-sm text-gray-300 hover:bg-gray-600"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* Worker Cards Grid */}
      <div className="grid gap-4 md:grid-cols-2">
        {data.workers.map((worker) => (
          <div
            key={worker.name}
            className="rounded-lg border border-gray-700 bg-gray-800/50 p-4"
            data-testid={`worker-card-${worker.name}`}
          >
            {/* Header: Name and Status */}
            <div className="flex items-center justify-between">
              <h3 className="font-medium text-white">{worker.name}</h3>
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${getStatusColorClass(worker.status)}`}
                data-testid={`worker-status-badge-${worker.name}`}
              >
                {worker.status}
              </span>
            </div>

            {/* Stats */}
            <div className="mt-3 space-y-1 text-sm">
              <div
                className="flex items-center justify-between"
                data-testid={`worker-restart-count-${worker.name}`}
              >
                <span className="text-gray-400">Restarts</span>
                <span className="text-gray-300">
                  {worker.restart_count}/{worker.max_restarts}
                </span>
              </div>

              {worker.last_crashed_at && (
                <div
                  className="flex items-center justify-between"
                  data-testid={`worker-last-crash-${worker.name}`}
                >
                  <span className="text-gray-400">Last Crash</span>
                  <span className="text-gray-300" title={formatTimestamp(worker.last_crashed_at)}>
                    {formatRelativeTime(worker.last_crashed_at)}
                  </span>
                </div>
              )}
            </div>

            {/* Error Message */}
            {worker.error && (
              <div className="mt-2 rounded-md bg-red-500/10 p-2 text-xs text-red-400">
                {worker.error}
              </div>
            )}

            {/* Action Buttons */}
            <div className="mt-4 flex flex-wrap items-center gap-2">
              {/* Start Button (only for stopped workers) */}
              {worker.status === 'stopped' && (
                <button
                  type="button"
                  onClick={() => void handleStartWorker(worker.name)}
                  disabled={actionsLoading}
                  className="flex items-center gap-1 rounded-md bg-[#76B900] px-2 py-1 text-xs font-medium text-white hover:bg-[#6aa800] disabled:opacity-50"
                  data-testid={`worker-start-button-${worker.name}`}
                >
                  <Play className="h-3.5 w-3.5" />
                  Start
                </button>
              )}

              {/* Stop Button (only for running workers) */}
              {worker.status === 'running' && (
                <button
                  type="button"
                  onClick={() => handleStopClick(worker.name)}
                  disabled={actionsLoading}
                  className="flex items-center gap-1 rounded-md bg-gray-700 px-2 py-1 text-xs font-medium text-white hover:bg-gray-600 disabled:opacity-50"
                  data-testid={`worker-action-stop-${worker.name}`}
                >
                  Stop
                </button>
              )}

              {/* Restart Button (for running workers) */}
              {worker.status === 'running' && (
                <button
                  type="button"
                  onClick={() => handleRestartClick(worker.name)}
                  disabled={actionsLoading}
                  className="flex items-center gap-1 rounded-md bg-gray-700 px-2 py-1 text-xs font-medium text-white hover:bg-gray-600 disabled:opacity-50"
                  data-testid={`worker-action-restart-${worker.name}`}
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  Restart
                </button>
              )}

              {/* Reset Button (only for failed workers) */}
              {worker.status === 'failed' && (
                <button
                  type="button"
                  onClick={() => void handleResetWorker(worker.name)}
                  disabled={actionsLoading}
                  className="flex items-center gap-1 rounded-md bg-amber-600 px-2 py-1 text-xs font-medium text-white hover:bg-amber-500 disabled:opacity-50"
                  data-testid={`worker-reset-button-${worker.name}`}
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                  Reset
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Confirmation Dialog */}
      {confirmDialog.isOpen && (
        // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
          data-testid="confirmation-dialog"
          onClick={handleCancelDialog}
        >
          {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions */}
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-dialog-title"
            className="max-w-md rounded-lg bg-gray-900 p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="confirm-dialog-title" className="text-lg font-medium text-white">
              {confirmDialog.action === 'stop' ? 'Stop' : 'Restart'} Worker
            </h3>
            <p className="mt-2 text-sm text-gray-400">
              Are you sure you want to {confirmDialog.action} worker &quot;{confirmDialog.workerName}&quot;?
              {confirmDialog.action === 'stop' && ' This will interrupt any ongoing work.'}
            </p>
            <div className="mt-4 flex justify-end gap-3">
              <button
                type="button"
                onClick={handleCancelDialog}
                className="rounded-md bg-gray-700 px-4 py-2 text-sm font-medium text-white hover:bg-gray-600"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => void handleConfirmAction()}
                className={`rounded-md px-4 py-2 text-sm font-medium text-white ${
                  confirmDialog.action === 'stop'
                    ? 'bg-amber-600 hover:bg-amber-500'
                    : 'bg-[#76B900] hover:bg-[#6aa800]'
                }`}
                data-testid="confirm-button"
              >
                {confirmDialog.action === 'stop' ? 'Stop' : 'Restart'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

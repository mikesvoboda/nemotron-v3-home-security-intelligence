/**
 * WorkerCard component for displaying individual worker status (NEM-4831).
 *
 * Displays worker information including:
 * - Worker name and status badge
 * - Restart count with max restarts
 * - Last started/crashed timestamps
 * - Error messages
 * - Action buttons (restart, stop)
 * - Collapsible restart history
 *
 * @example
 * ```tsx
 * <WorkerCard
 *   worker={workerStatus}
 *   restartHistory={history}
 *   onRestart={(name) => restartWorker(name)}
 *   onStop={(name) => stopWorker(name)}
 * />
 * ```
 */

import { ChevronDown, RefreshCw, Square } from 'lucide-react';
import { memo, useState } from 'react';

import type { RestartHistoryItem } from '../../hooks/useRestartHistory';
import type { WorkerStatus } from '../../hooks/useSupervisorStatus';

export interface WorkerCardProps {
  /** Worker status information */
  worker: WorkerStatus;
  /** Restart history for this worker */
  restartHistory: RestartHistoryItem[];
  /** Callback when restart button is clicked */
  onRestart: (name: string) => void;
  /** Callback when stop button is clicked */
  onStop: (name: string) => void;
}

/**
 * Get badge class for worker status
 */
function getStatusBadgeClass(status: WorkerStatus['status']): string {
  switch (status) {
    case 'running':
      return 'bg-green-600';
    case 'stopped':
      return 'bg-gray-600';
    case 'crashed':
    case 'failed':
      return 'bg-red-600';
    case 'restarting':
      return 'bg-yellow-600';
    default:
      return 'bg-gray-600';
  }
}

/**
 * Get restart count color based on ratio
 */
function getRestartCountClass(restartCount: number, maxRestarts: number): string {
  if (restartCount >= maxRestarts) {
    return 'text-red-400';
  }
  if (restartCount >= maxRestarts - 1) {
    return 'text-yellow-400';
  }
  return 'text-gray-300';
}

/**
 * Format timestamp for display (ISO-style date with time in UTC)
 */
function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  const hours = String(date.getUTCHours()).padStart(2, '0');
  const minutes = String(date.getUTCMinutes()).padStart(2, '0');
  const seconds = String(date.getUTCSeconds()).padStart(2, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
}

/**
 * WorkerCard - Individual worker status card
 */
const WorkerCard = memo(function WorkerCard({
  worker,
  restartHistory,
  onRestart,
  onStop,
}: WorkerCardProps) {
  const [isHistoryExpanded, setIsHistoryExpanded] = useState(false);

  const isStopped = worker.status === 'stopped';
  const statusBadgeClass = getStatusBadgeClass(worker.status);
  const restartCountClass = getRestartCountClass(worker.restart_count, worker.max_restarts);

  return (
    <div
      className="rounded-lg border border-gray-700 bg-gray-800/50 p-4"
      data-testid={`worker-card-${worker.name}`}
    >
      {/* Header: Name and Status Badge */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-medium text-white">{worker.name}</h3>
        <span
          className={`rounded-full px-2 py-1 text-xs font-medium text-white ${statusBadgeClass}`}
          data-testid={`worker-status-badge-${worker.name}`}
          aria-label={`Worker status: ${worker.status}`}
        >
          {worker.status}
        </span>
      </div>

      {/* Stats Section */}
      <div className="mt-3 space-y-2">
        {/* Restart Count */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-400">Restart Count</span>
          <span className={restartCountClass}>
            {worker.restart_count} / {worker.max_restarts}
          </span>
        </div>

        {/* Last Started */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-400">Last Started</span>
          <span className="text-gray-300">
            {worker.last_started_at ? formatTimestamp(worker.last_started_at) : 'Never started'}
          </span>
        </div>

        {/* Last Crashed (only if available) */}
        {worker.last_crashed_at && (
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Last Crashed</span>
            <span className="text-gray-300">{formatTimestamp(worker.last_crashed_at)}</span>
          </div>
        )}
      </div>

      {/* Error Message (if present) */}
      {worker.error && (
        <div className="mt-3 rounded-md bg-red-500/10 p-2">
          <span className="text-xs text-gray-400">Error: </span>
          <span className="text-sm text-red-400">{worker.error}</span>
        </div>
      )}

      {/* Action Buttons */}
      <div className="mt-4 flex items-center gap-2">
        <button
          type="button"
          onClick={() => onRestart(worker.name)}
          disabled={isStopped}
          className="flex items-center gap-1 rounded-md bg-gray-700 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500/50 disabled:cursor-not-allowed disabled:opacity-50"
          data-testid={`worker-action-restart-${worker.name}`}
          aria-label={`Restart worker ${worker.name}`}
        >
          <RefreshCw className="h-4 w-4" data-testid="restart-icon" />
          Restart
        </button>
        <button
          type="button"
          onClick={() => onStop(worker.name)}
          disabled={isStopped}
          className="flex items-center gap-1 rounded-md bg-gray-700 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500/50 disabled:cursor-not-allowed disabled:opacity-50"
          data-testid={`worker-action-stop-${worker.name}`}
          aria-label={`Stop worker ${worker.name}`}
        >
          <Square className="h-4 w-4" data-testid="stop-icon" />
          Stop
        </button>
      </div>

      {/* Restart History Accordion */}
      <div className="mt-4 border-t border-gray-700 pt-3">
        <button
          type="button"
          onClick={() => setIsHistoryExpanded(!isHistoryExpanded)}
          className="flex w-full items-center justify-between text-sm text-gray-400 hover:text-gray-300"
          data-testid="restart-history-accordion"
          aria-expanded={isHistoryExpanded}
        >
          <span className="flex items-center gap-2">
            Restart History
            <span
              className="rounded-full bg-gray-700 px-2 py-0.5 text-xs text-gray-300"
              data-testid="restart-history-count-badge"
            >
              {restartHistory.length}
            </span>
          </span>
          <ChevronDown
            className={`h-4 w-4 transition-transform ${isHistoryExpanded ? 'rotate-180' : ''}`}
          />
        </button>

        <div
          className={`mt-2 ${isHistoryExpanded ? 'expanded' : ''}`}
          data-testid="restart-history-content"
        >
          {isHistoryExpanded && (
            <>
              {restartHistory.length === 0 ? (
                <div
                  className="py-2 text-center text-sm text-gray-500"
                  data-testid="restart-history-empty-state"
                >
                  No restart history available
                </div>
              ) : (
                <div className="space-y-2">
                  {restartHistory.map((item, index) => (
                    <div
                      key={`${item.timestamp}-${item.attempt}`}
                      className="rounded-md bg-gray-900/50 p-2 text-sm"
                      data-testid={`restart-history-item-${index}`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-gray-400">Attempt {item.attempt}</span>
                        <span
                          className={`text-xs font-medium ${
                            item.status === 'success' ? 'text-green-400' : 'text-red-400'
                          }`}
                        >
                          {item.status}
                        </span>
                      </div>
                      <div className="mt-1 text-xs text-gray-500">
                        {formatTimestamp(item.timestamp)}
                      </div>
                      {item.error && (
                        <div className="mt-1 text-xs text-red-400">{item.error}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
});

export default WorkerCard;

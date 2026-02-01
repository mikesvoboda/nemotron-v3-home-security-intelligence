/**
 * WorkerStatusPanel - Displays pipeline worker health status from WebSocket events
 *
 * NEM-3127, NEM-3402: Provides a dedicated panel showing real-time worker health
 * status received via WebSocket. Displays overall pipeline health and individual
 * worker cards with status indicators.
 *
 * Worker status states:
 * - running: Worker is healthy (green)
 * - stopped: Worker has stopped (yellow/warning)
 * - error: Worker encountered an error (red)
 * - starting: Worker is restarting (yellow/warning)
 *
 * @example
 * ```tsx
 * <WorkerStatusPanel data-testid="worker-status-panel" />
 * ```
 */

import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Activity,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { memo, useMemo } from 'react';

import { useWorkerStatusWebSocket } from '../../hooks/useWorkerStatusWebSocket';

import type {
  WorkerStatusEntry,
  PipelineHealthStatus,
} from '../../hooks/useWorkerStatusWebSocket';

// ============================================================================
// Types
// ============================================================================

export interface WorkerStatusPanelProps {
  /** Additional CSS classes */
  className?: string;
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get badge color for pipeline health status
 */
function getPipelineHealthColor(
  health: PipelineHealthStatus
): 'emerald' | 'yellow' | 'red' | 'gray' {
  switch (health) {
    case 'healthy':
      return 'emerald';
    case 'warning':
      return 'yellow';
    case 'error':
      return 'red';
    default:
      return 'gray';
  }
}

/**
 * Get display text for pipeline health status
 */
function getPipelineHealthText(health: PipelineHealthStatus): string {
  switch (health) {
    case 'healthy':
      return 'Healthy';
    case 'warning':
      return 'Warning';
    case 'error':
      return 'Error';
    default:
      return 'Unknown';
  }
}

/**
 * Get color class for worker state
 */
function getWorkerStateColorClass(state: WorkerStatusEntry['state']): string {
  switch (state) {
    case 'running':
      return 'border-green-500/30 bg-green-500/10';
    case 'stopped':
    case 'stopping':
      return 'border-yellow-500/30 bg-yellow-500/10';
    case 'starting':
      return 'border-yellow-500/30 bg-yellow-500/10';
    case 'error':
      return 'border-red-500/30 bg-red-500/10';
    default:
      return 'border-gray-700 bg-gray-800/50';
  }
}

/**
 * Get badge color for worker state
 */
function getWorkerStateBadgeColor(
  state: WorkerStatusEntry['state']
): 'emerald' | 'yellow' | 'red' | 'gray' {
  switch (state) {
    case 'running':
      return 'emerald';
    case 'stopped':
    case 'stopping':
    case 'starting':
      return 'yellow';
    case 'error':
      return 'red';
    default:
      return 'gray';
  }
}

/**
 * Get display text for worker state
 */
function getWorkerStateText(state: WorkerStatusEntry['state']): string {
  switch (state) {
    case 'running':
      return 'Running';
    case 'stopped':
      return 'Stopped';
    case 'stopping':
      return 'Stopping';
    case 'starting':
      return 'Restarting';
    case 'error':
      return 'Error';
    default:
      return 'Unknown';
  }
}

/**
 * Format timestamp for display
 */
function formatTimestamp(isoString: string): string {
  const date = new Date(isoString);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
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
  const diffSeconds = Math.floor(diffMs / 1000);

  if (diffSeconds < 60) return 'Just now';

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

/**
 * Format worker type for display
 */
function formatWorkerType(type: string): string {
  // Convert snake_case to Title Case
  return type
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Status icon for worker state
 */
function WorkerStateIcon({ state }: { state: WorkerStatusEntry['state'] }) {
  switch (state) {
    case 'running':
      return <CheckCircle className="h-4 w-4 text-green-500" data-testid="worker-icon-running" />;
    case 'stopped':
    case 'stopping':
      return <AlertTriangle className="h-4 w-4 text-yellow-500" data-testid="worker-icon-stopped" />;
    case 'starting':
      return <RefreshCw className="h-4 w-4 animate-spin text-yellow-500" data-testid="worker-icon-restarting" />;
    case 'error':
      return <XCircle className="h-4 w-4 text-red-500" data-testid="worker-icon-error" />;
    default:
      return <AlertTriangle className="h-4 w-4 text-gray-500" data-testid="worker-icon-unknown" />;
  }
}

/**
 * Individual worker status card
 */
interface WorkerCardProps {
  worker: WorkerStatusEntry;
}

const WorkerCard = memo(function WorkerCard({ worker }: WorkerCardProps) {
  const colorClass = getWorkerStateColorClass(worker.state);
  const badgeColor = getWorkerStateBadgeColor(worker.state);
  const stateText = getWorkerStateText(worker.state);

  return (
    <div
      className={clsx('rounded-lg border p-3 transition-colors', colorClass)}
      data-testid={`worker-status-card-${worker.name}`}
    >
      {/* Header: Name and Status Badge */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          <WorkerStateIcon state={worker.state} />
          <div className="flex flex-col">
            <Text className="text-sm font-medium text-gray-200">{worker.name}</Text>
            <Text className="text-xs text-gray-500">{formatWorkerType(worker.type)}</Text>
          </div>
        </div>
        <Badge
          color={badgeColor}
          size="xs"
          data-testid={`worker-status-badge-${worker.name}`}
        >
          {stateText}
        </Badge>
      </div>

      {/* Last Updated */}
      <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
        <span>Last updated</span>
        <span title={formatTimestamp(worker.lastUpdated)}>
          {formatRelativeTime(worker.lastUpdated)}
        </span>
      </div>

      {/* Restart info (if restarting) */}
      {worker.restartAttempt !== undefined && worker.maxRestartAttempts !== undefined && (
        <div className="mt-1 flex items-center justify-between text-xs text-gray-500">
          <span>Restart attempt</span>
          <span>
            {worker.restartAttempt}/{worker.maxRestartAttempts}
          </span>
        </div>
      )}

      {/* Health check failures */}
      {worker.failureCount !== undefined && worker.failureCount > 0 && (
        <div className="mt-1 flex items-center justify-between text-xs text-yellow-500">
          <span>Health check failures</span>
          <span>{worker.failureCount}</span>
        </div>
      )}

      {/* Error message */}
      {worker.lastError && (
        <div className="mt-2 rounded-md bg-red-500/10 p-2">
          <Text className="text-xs text-red-400" data-testid={`worker-error-${worker.name}`}>
            {worker.lastError}
          </Text>
          {worker.lastErrorType && (
            <Text className="mt-1 text-xs text-gray-500">Type: {worker.lastErrorType}</Text>
          )}
          {worker.recoverable !== undefined && (
            <Text className="mt-1 text-xs text-gray-500">
              Recoverable: {worker.recoverable ? 'Yes' : 'No'}
            </Text>
          )}
        </div>
      )}
    </div>
  );
});

// ============================================================================
// Main Component
// ============================================================================

/**
 * WorkerStatusPanel - Displays pipeline worker health status
 *
 * Shows:
 * - Overall pipeline health indicator
 * - WebSocket connection status
 * - Worker count (running/total)
 * - Individual worker cards with status
 */
export const WorkerStatusPanel = memo(function WorkerStatusPanel({
  className,
  'data-testid': testId = 'worker-status-panel',
}: WorkerStatusPanelProps) {
  const {
    workers,
    isConnected,
    pipelineHealth,
    hasError,
    runningCount,
    totalCount,
  } = useWorkerStatusWebSocket({ enabled: true });

  // Sort workers: errors first, then warnings, then running
  const sortedWorkers = useMemo(() => {
    return Object.values(workers).sort((a, b) => {
      const stateOrder: Record<string, number> = {
        error: 0,
        stopped: 1,
        stopping: 1,
        starting: 2,
        running: 3,
      };
      const aOrder = stateOrder[a.state] ?? 4;
      const bOrder = stateOrder[b.state] ?? 4;
      if (aOrder !== bOrder) return aOrder - bOrder;
      return a.name.localeCompare(b.name);
    });
  }, [workers]);

  const healthColor = getPipelineHealthColor(pipelineHealth);
  const healthText = getPipelineHealthText(pipelineHealth);

  // Empty state - no workers tracked yet
  if (totalCount === 0) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid={testId}
      >
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <Title className="flex items-center gap-2 text-white">
            <Activity className="h-5 w-5 text-[#76B900]" />
            Pipeline Workers
          </Title>
          <div className="flex items-center gap-2">
            {isConnected ? (
              <Wifi className="h-4 w-4 text-green-500" data-testid="ws-connected" />
            ) : (
              <WifiOff className="h-4 w-4 text-red-500" data-testid="ws-disconnected" />
            )}
          </div>
        </div>

        {/* Empty state */}
        <div
          className="flex h-32 items-center justify-center text-gray-500"
          data-testid="no-workers-message"
        >
          <Text className="text-sm">
            {isConnected
              ? 'Waiting for worker status updates...'
              : 'WebSocket disconnected. Reconnecting...'}
          </Text>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className={clsx(
        'border-gray-800 bg-[#1A1A1A] shadow-lg',
        hasError && 'border-red-500/30',
        className
      )}
      data-testid={testId}
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Activity className="h-5 w-5 text-[#76B900]" />
          Pipeline Workers
        </Title>
        <div className="flex items-center gap-3">
          {/* WebSocket status */}
          <div className="flex items-center gap-1">
            {isConnected ? (
              <Wifi className="h-4 w-4 text-green-500" data-testid="ws-connected" />
            ) : (
              <WifiOff className="h-4 w-4 text-red-500" data-testid="ws-disconnected" />
            )}
          </div>
          {/* Pipeline health badge */}
          <Badge color={healthColor} size="sm" data-testid="pipeline-health-badge">
            {healthText}
          </Badge>
        </div>
      </div>

      {/* Summary bar */}
      <div className="mb-4 flex items-center justify-between rounded-lg bg-gray-800/50 px-3 py-2">
        <Text className="text-sm text-gray-400">Worker Status</Text>
        <div className="flex items-center gap-2">
          <Badge
            color={runningCount === totalCount ? 'emerald' : runningCount === 0 ? 'red' : 'yellow'}
            size="sm"
            data-testid="worker-count-badge"
          >
            {runningCount}/{totalCount} Running
          </Badge>
        </div>
      </div>

      {/* Worker cards grid */}
      <div className="grid gap-3 sm:grid-cols-2" data-testid="worker-cards-container">
        {sortedWorkers.map((worker) => (
          <WorkerCard key={worker.name} worker={worker} />
        ))}
      </div>
    </Card>
  );
});

export default WorkerStatusPanel;

/**
 * WorkerStatusIndicator - Pipeline worker health indicator component (NEM-3127)
 *
 * Displays the overall health status of pipeline workers with an expandable
 * dropdown showing individual worker status. Uses the worker status store
 * which is updated by the useWorkerEvents hook via WebSocket events.
 *
 * Status Indicators:
 * - Green (healthy): All workers running
 * - Yellow (warning): Some workers stopped or restarting
 * - Red (error): One or more workers have errors
 * - Gray (unknown): No worker status data received yet
 *
 * @example
 * ```tsx
 * // Basic usage in header
 * <WorkerStatusIndicator />
 *
 * // With custom styling
 * <WorkerStatusIndicator className="ml-4" showLabel />
 * ```
 */

import { clsx } from 'clsx';
import { Activity, AlertTriangle, CheckCircle, XCircle, RefreshCw, Server } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { useWorkerStatusState } from '../../stores/worker-status-store';
import { STATUS_BG_CLASSES, STATUS_TEXT_CLASSES } from '../../theme/colors';

import type { PipelineHealthStatus, WorkerStatus } from '../../stores/worker-status-store';
import type { WorkerState } from '../../types/websocket-events';

// ============================================================================
// Types
// ============================================================================

export interface WorkerStatusIndicatorProps {
  /** Optional CSS class name */
  className?: string;
  /** Whether to show the status label text */
  showLabel?: boolean;
  /** Compact mode - only show dot indicator */
  compact?: boolean;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get display configuration for a pipeline health status.
 */
function getHealthConfig(health: PipelineHealthStatus): {
  label: string;
  dotColor: string;
  textColor: string;
  icon: typeof CheckCircle;
  pulse: boolean;
} {
  switch (health) {
    case 'healthy':
      return {
        label: 'Healthy',
        dotColor: STATUS_BG_CLASSES.healthy,
        textColor: STATUS_TEXT_CLASSES.healthy,
        icon: CheckCircle,
        pulse: true,
      };
    case 'warning':
      return {
        label: 'Warning',
        dotColor: STATUS_BG_CLASSES.warning,
        textColor: STATUS_TEXT_CLASSES.warning,
        icon: AlertTriangle,
        pulse: false,
      };
    case 'error':
      return {
        label: 'Error',
        dotColor: STATUS_BG_CLASSES.error,
        textColor: STATUS_TEXT_CLASSES.error,
        icon: XCircle,
        pulse: false,
      };
    case 'unknown':
    default:
      return {
        label: 'Unknown',
        dotColor: STATUS_BG_CLASSES.unknown,
        textColor: STATUS_TEXT_CLASSES.unknown,
        icon: Server,
        pulse: false,
      };
  }
}

/**
 * Get display configuration for a worker state.
 */
function getWorkerStateConfig(state: WorkerState): {
  label: string;
  dotColor: string;
  textColor: string;
  icon: typeof CheckCircle;
} {
  switch (state) {
    case 'running':
      return {
        label: 'Running',
        dotColor: STATUS_BG_CLASSES.healthy,
        textColor: STATUS_TEXT_CLASSES.healthy,
        icon: CheckCircle,
      };
    case 'starting':
      return {
        label: 'Starting',
        dotColor: STATUS_BG_CLASSES.warning,
        textColor: STATUS_TEXT_CLASSES.warning,
        icon: RefreshCw,
      };
    case 'stopping':
      return {
        label: 'Stopping',
        dotColor: STATUS_BG_CLASSES.warning,
        textColor: STATUS_TEXT_CLASSES.warning,
        icon: AlertTriangle,
      };
    case 'stopped':
      return {
        label: 'Stopped',
        dotColor: STATUS_BG_CLASSES.inactive,
        textColor: STATUS_TEXT_CLASSES.inactive,
        icon: Server,
      };
    case 'error':
      return {
        label: 'Error',
        dotColor: STATUS_BG_CLASSES.error,
        textColor: STATUS_TEXT_CLASSES.error,
        icon: XCircle,
      };
    default:
      return {
        label: 'Unknown',
        dotColor: STATUS_BG_CLASSES.unknown,
        textColor: STATUS_TEXT_CLASSES.unknown,
        icon: Server,
      };
  }
}

/**
 * Format worker type for display.
 */
function formatWorkerType(type: string): string {
  const typeMap: Record<string, string> = {
    detection: 'Detection',
    analysis: 'Analysis',
    timeout: 'Timeout',
    metrics: 'Metrics',
  };
  return typeMap[type] ?? type.charAt(0).toUpperCase() + type.slice(1);
}

// ============================================================================
// Sub-Components
// ============================================================================

interface WorkerDetailRowProps {
  worker: WorkerStatus;
}

function WorkerDetailRow({ worker }: WorkerDetailRowProps) {
  const config = getWorkerStateConfig(worker.state);
  const Icon = config.icon;

  return (
    <div
      className="flex items-center justify-between py-1.5"
      data-testid={`worker-row-${worker.name}`}
    >
      <div className="flex flex-col">
        <span className="text-sm text-gray-300">{worker.name}</span>
        <span className="text-xs text-gray-500">{formatWorkerType(worker.type)}</span>
      </div>
      <div className="flex items-center gap-2">
        <Icon
          className={clsx(
            'h-3 w-3',
            config.textColor,
            worker.state === 'starting' && 'animate-spin'
          )}
          aria-hidden="true"
        />
        <div
          className={clsx('h-2 w-2 rounded-full', config.dotColor)}
          data-testid={`worker-indicator-${worker.name}`}
          aria-hidden="true"
        />
        <span className={clsx('text-xs font-medium', config.textColor)}>{config.label}</span>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * WorkerStatusIndicator displays pipeline worker health with expandable details.
 */
export default function WorkerStatusIndicator({
  className,
  showLabel = true,
  compact = false,
}: WorkerStatusIndicatorProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const dropdownTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Get state from store (using shallow hook for optimized re-renders - NEM-3790)
  const { workers, pipelineHealth, hasError, hasWarning, runningCount, totalCount } =
    useWorkerStatusState();

  const workerList = Object.values(workers);
  const config = getHealthConfig(pipelineHealth);
  const Icon = config.icon;

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (dropdownTimeoutRef.current) {
        clearTimeout(dropdownTimeoutRef.current);
      }
    };
  }, []);

  const handleMouseEnter = () => {
    if (dropdownTimeoutRef.current) {
      clearTimeout(dropdownTimeoutRef.current);
    }
    setIsExpanded(true);
  };

  const handleMouseLeave = () => {
    dropdownTimeoutRef.current = setTimeout(() => {
      setIsExpanded(false);
    }, 150);
  };

  // Compact mode - just show the status dot
  if (compact) {
    return (
      <div
        className={clsx('relative', className)}
        data-testid="worker-status-indicator"
        aria-label={`Pipeline workers: ${config.label}`}
      >
        <div
          className={clsx('h-2 w-2 rounded-full', config.dotColor, config.pulse && 'animate-pulse')}
          data-testid="worker-status-dot"
        />
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={clsx('relative flex cursor-pointer items-center gap-2', className)}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleMouseEnter}
      onBlur={handleMouseLeave}
      data-testid="worker-status-indicator"
      role="button"
      tabIndex={0}
      aria-label={`Pipeline workers: ${config.label}`}
      aria-haspopup="true"
      aria-expanded={isExpanded}
    >
      {/* Status Icon */}
      <Icon className={clsx('h-4 w-4', config.textColor)} aria-hidden="true" />

      {/* Status Dot */}
      <div
        className={clsx('h-2 w-2 rounded-full', config.dotColor, config.pulse && 'animate-pulse')}
        data-testid="worker-status-dot"
        aria-hidden="true"
      />

      {/* Status Label - hidden on small screens unless showLabel is true */}
      {showLabel && (
        <span className="hidden text-sm text-text-secondary sm:inline">
          Pipeline: <span className={config.textColor}>{config.label}</span>
          {totalCount > 0 && (
            <span className="ml-1 text-gray-500">
              ({runningCount}/{totalCount})
            </span>
          )}
        </span>
      )}

      {/* Dropdown */}
      {isExpanded && (
        <div
          className="absolute left-0 top-full z-50 mt-2 min-w-[280px] rounded-lg border border-gray-700 bg-gray-900 p-3 shadow-lg"
          role="tooltip"
          data-testid="worker-status-dropdown"
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
              Pipeline Workers
            </span>
            {totalCount > 0 && (
              <span className={clsx('text-xs', config.textColor)}>
                {runningCount} of {totalCount} running
              </span>
            )}
          </div>

          {workerList.length === 0 ? (
            <div className="py-4 text-center text-sm text-gray-500">
              <Activity className="mx-auto mb-2 h-6 w-6" />
              No workers detected yet
            </div>
          ) : (
            <div className="divide-y divide-gray-800">
              {workerList.map((worker) => (
                <WorkerDetailRow key={worker.name} worker={worker} />
              ))}
            </div>
          )}

          {/* Error summary */}
          {hasError && (
            <div className="mt-2 border-t border-gray-800 pt-2">
              <div className="flex items-center gap-1 text-xs text-red-400">
                <XCircle className="h-3 w-3" />
                Some workers have errors
              </div>
            </div>
          )}

          {/* Warning summary (only if no errors) */}
          {!hasError && hasWarning && (
            <div className="mt-2 border-t border-gray-800 pt-2">
              <div className="flex items-center gap-1 text-xs text-yellow-400">
                <AlertTriangle className="h-3 w-3" />
                Some workers are stopped or restarting
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

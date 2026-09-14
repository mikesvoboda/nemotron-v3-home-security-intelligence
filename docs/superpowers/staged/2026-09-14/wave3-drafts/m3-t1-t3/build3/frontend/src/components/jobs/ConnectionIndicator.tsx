/**
 * ConnectionIndicator - Visual indicator for WebSocket connection status
 *
 * Shows connection status for job log streaming:
 * - Green dot with pulse when connected
 * - Yellow dot when reconnecting
 * - Gray dot when disconnected
 * - Red dot when failed
 *
 * NEM-2711
 */

import { clsx } from 'clsx';
import { useState } from 'react';

import type { JobLogsConnectionStatus } from '../../hooks/useJobLogsWebSocket';

// ============================================================================
// Types
// ============================================================================

export type IndicatorSize = 'sm' | 'md' | 'lg';

export interface ConnectionIndicatorProps {
  /** Current connection status */
  status: JobLogsConnectionStatus;
  /** Number of reconnection attempts (shown when reconnecting) */
  reconnectCount?: number;
  /** Whether to show the status label */
  showLabel?: boolean;
  /** Whether to show tooltip on hover */
  showTooltip?: boolean;
  /** Size of the indicator dot */
  size?: IndicatorSize;
  /** Additional CSS classes */
  className?: string;
  /** Callback when clicked (useful for retry in failed state) */
  onRetry?: () => void;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get the color classes for the indicator dot based on status.
 */
function getDotClasses(status: JobLogsConnectionStatus): string {
  switch (status) {
    case 'connected':
      return 'bg-green-500 animate-pulse';
    case 'reconnecting':
      return 'bg-yellow-500';
    case 'disconnected':
      return 'bg-gray-500';
    case 'failed':
      return 'bg-red-500';
    default:
      return 'bg-gray-500';
  }
}

/**
 * Get the label text for the status.
 */
function getStatusLabel(status: JobLogsConnectionStatus): string {
  switch (status) {
    case 'connected':
      return 'Live';
    case 'reconnecting':
      return 'Reconnecting';
    case 'disconnected':
      return 'Offline';
    case 'failed':
      return 'Failed';
    default:
      return 'Unknown';
  }
}

/**
 * Get the screen reader label for the status.
 */
function getAccessibleLabel(status: JobLogsConnectionStatus): string {
  switch (status) {
    case 'connected':
      return 'Connected - Log streaming active';
    case 'reconnecting':
      return 'Reconnecting - Attempting to restore connection';
    case 'disconnected':
      return 'Disconnected - Log streaming inactive';
    case 'failed':
      return 'Failed - Connection could not be established';
    default:
      return 'Unknown connection status';
  }
}

/**
 * Get the label color classes based on status.
 */
function getLabelClasses(status: JobLogsConnectionStatus): string {
  switch (status) {
    case 'connected':
      return 'text-green-400';
    case 'reconnecting':
      return 'text-yellow-400';
    case 'disconnected':
      return 'text-gray-400';
    case 'failed':
      return 'text-red-400';
    default:
      return 'text-gray-400';
  }
}

/**
 * Get size classes for the dot.
 */
function getSizeClasses(size: IndicatorSize): string {
  switch (size) {
    case 'sm':
      return 'h-2 w-2';
    case 'md':
      return 'h-3 w-3';
    case 'lg':
      return 'h-4 w-4';
    default:
      return 'h-2 w-2';
  }
}

// ============================================================================
// Component
// ============================================================================

/**
 * ConnectionIndicator displays the WebSocket connection status for job log streaming.
 *
 * @example
 * ```tsx
 * <ConnectionIndicator
 *   status={connectionStatus}
 *   showLabel
 *   onRetry={handleRetry}
 * />
 * ```
 */
export default function ConnectionIndicator({
  status,
  reconnectCount,
  showLabel = false,
  showTooltip = false,
  size = 'sm',
  className,
  onRetry,
}: ConnectionIndicatorProps) {
  const [isTooltipVisible, setIsTooltipVisible] = useState(false);

  const handleClick = () => {
    if (status === 'failed' && onRetry) {
      onRetry();
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if ((event.key === 'Enter' || event.key === ' ') && status === 'failed' && onRetry) {
      event.preventDefault();
      onRetry();
    }
  };

  const handleMouseEnter = () => {
    if (showTooltip) {
      setIsTooltipVisible(true);
    }
  };

  const handleMouseLeave = () => {
    setIsTooltipVisible(false);
  };

  const dotClasses = getDotClasses(status);
  const sizeClasses = getSizeClasses(size);
  const labelClasses = getLabelClasses(status);
  const label = getStatusLabel(status);
  const accessibleLabel = getAccessibleLabel(status);

  // Make interactive when failed and onRetry is provided
  const isInteractive = status === 'failed' && onRetry;

  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions -- role, tabIndex, and keyboard handlers are conditionally set based on isInteractive
    <div
      className={clsx(
        'relative inline-flex items-center gap-1.5',
        isInteractive && 'cursor-pointer',
        className
      )}
      data-testid="connection-indicator"
      role={isInteractive ? 'button' : 'status'}
      aria-live="polite"
      tabIndex={isInteractive ? 0 : undefined}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {/* Status dot */}
      <span
        className={clsx('rounded-full', dotClasses, sizeClasses)}
        data-testid="connection-dot"
        aria-hidden="true"
      />

      {/* Label (optional) */}
      {showLabel && (
        <span className={clsx('text-xs font-medium', labelClasses)}>
          {label}
          {status === 'reconnecting' && reconnectCount !== undefined && reconnectCount > 0 && (
            <span className="ml-1">({reconnectCount})</span>
          )}
        </span>
      )}

      {/* Screen reader only label */}
      <span className="sr-only">{accessibleLabel}</span>

      {/* Tooltip */}
      {showTooltip && isTooltipVisible && (
        <div
          className="absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 whitespace-nowrap rounded bg-gray-900 px-2 py-1 text-xs text-gray-100 shadow-lg"
          role="tooltip"
        >
          {status === 'connected' && 'Real-time log streaming active'}
          {status === 'reconnecting' && `Reconnecting... (attempt ${reconnectCount ?? 0})`}
          {status === 'disconnected' && 'Log streaming disconnected'}
          {status === 'failed' && 'Connection failed - click to retry'}
          <div className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
        </div>
      )}
    </div>
  );
}

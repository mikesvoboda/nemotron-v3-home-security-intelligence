import { AlertTriangle, RefreshCw, WifiOff, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { useAnnounce } from '../../hooks/useAnnounce';

import type { ConnectionState } from '../../hooks/useWebSocketStatus';

export interface ConnectionStatusBannerProps {
  /** Current connection state */
  connectionState: ConnectionState;
  /** Timestamp when disconnection started (null if connected) */
  disconnectedSince: Date | null;
  /** Current reconnection attempt count */
  reconnectAttempts?: number;
  /** Maximum reconnection attempts before giving up */
  maxReconnectAttempts?: number;
  /** Callback to manually retry connection */
  onRetry: () => void;
  /** Threshold in ms after which data is considered stale (default: 60000 = 1 minute) */
  staleThresholdMs?: number;
  /** Whether the system is falling back to REST API polling */
  isPollingFallback?: boolean;
}

/**
 * Format duration since disconnection
 */
function formatDuration(ms: number): string {
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m`;
  }
  const hours = Math.floor(minutes / 60);
  return `${hours}h`;
}

/**
 * Get banner styling based on connection state
 */
function getBannerStyling(state: ConnectionState): {
  bgClass: string;
  textClass: string;
  borderClass: string;
} {
  switch (state) {
    case 'reconnecting':
      return {
        bgClass: 'bg-yellow-900/30',
        textClass: 'text-yellow-400',
        borderClass: 'border-yellow-500/50',
      };
    case 'failed':
      return {
        bgClass: 'bg-orange-900/30',
        textClass: 'text-orange-400',
        borderClass: 'border-orange-500/50',
      };
    case 'disconnected':
    default:
      return {
        bgClass: 'bg-red-900/30',
        textClass: 'text-red-400',
        borderClass: 'border-red-500/50',
      };
  }
}

/**
 * Get icon component based on connection state
 */
function getStateIcon(state: ConnectionState, className: string) {
  switch (state) {
    case 'reconnecting':
      return <RefreshCw className={`${className} motion-safe:animate-spin`} aria-hidden="true" />;
    case 'failed':
      return <AlertTriangle className={className} aria-hidden="true" />;
    case 'disconnected':
    default:
      return <WifiOff className={className} aria-hidden="true" />;
  }
}

/**
 * Get state label text
 */
function getStateLabel(state: ConnectionState): string {
  switch (state) {
    case 'reconnecting':
      return 'Reconnecting';
    case 'failed':
      return 'Connection Failed';
    case 'disconnected':
    default:
      return 'Disconnected';
  }
}

/**
 * ConnectionStatusBanner Component
 *
 * Displays a prominent banner when WebSocket connection is lost.
 * Shows connection state, duration of disconnection, and indicates
 * when data may be stale.
 */
export default function ConnectionStatusBanner({
  connectionState,
  disconnectedSince,
  reconnectAttempts = 0,
  maxReconnectAttempts = 5,
  onRetry,
  staleThresholdMs = 60000, // Default 1 minute
  isPollingFallback = false,
}: ConnectionStatusBannerProps) {
  const [isDismissed, setIsDismissed] = useState(false);
  const [duration, setDuration] = useState(0);
  const { announce } = useAnnounce();
  const previousStateRef = useRef<ConnectionState | undefined>(undefined);

  // Reset dismissed state when connection state changes
  useEffect(() => {
    if (connectionState === 'connected') {
      setIsDismissed(false);
    }
  }, [connectionState]);

  // Announce connection state changes to screen readers
  useEffect(() => {
    // Skip initial render and only announce on state changes
    if (previousStateRef.current === undefined) {
      previousStateRef.current = connectionState;
      return;
    }

    if (previousStateRef.current !== connectionState) {
      const label = getStateLabel(connectionState);
      const politeness = connectionState === 'failed' ? 'assertive' : 'polite';

      if (connectionState === 'connected') {
        announce('Connection restored', politeness);
      } else if (connectionState === 'reconnecting') {
        announce(`${label}: Attempt ${reconnectAttempts} of ${maxReconnectAttempts}`, politeness);
      } else {
        announce(label, politeness);
      }

      previousStateRef.current = connectionState;
    }
  }, [connectionState, reconnectAttempts, maxReconnectAttempts, announce]);

  // Update duration timer
  useEffect(() => {
    if (!disconnectedSince || connectionState === 'connected') {
      setDuration(0);
      return;
    }

    // Initial calculation
    setDuration(Date.now() - disconnectedSince.getTime());

    // Update every second
    const interval = setInterval(() => {
      setDuration(Date.now() - disconnectedSince.getTime());
    }, 1000);

    return () => clearInterval(interval);
  }, [disconnectedSince, connectionState]);

  // Don't render if connected or dismissed
  if (connectionState === 'connected' || isDismissed) {
    return null;
  }

  const styling = getBannerStyling(connectionState);
  const isDataStale = duration >= staleThresholdMs;
  const showRetryButton = connectionState === 'failed';

  return (
    <div
      className={`flex items-center justify-between gap-4 rounded-lg border px-4 py-3 ${styling.bgClass} ${styling.borderClass}`}
      role="alert"
      aria-live="polite"
      data-testid="connection-status-banner"
    >
      {/* Left side: Icon and message */}
      <div className="flex items-center gap-3">
        {getStateIcon(connectionState, `h-5 w-5 ${styling.textClass}`)}

        <div className="flex flex-col gap-0.5">
          {/* Main status message */}
          <div className="flex items-center gap-2">
            <span className={`font-medium ${styling.textClass}`}>
              {getStateLabel(connectionState)}
            </span>

            {/* Reconnection counter */}
            {connectionState === 'reconnecting' && (
              <span className="text-xs text-yellow-400/80" data-testid="reconnect-counter">
                Attempt {reconnectAttempts}/{maxReconnectAttempts}
              </span>
            )}

            {/* Duration */}
            {disconnectedSince && (
              <span className="text-xs text-text-secondary" data-testid="disconnected-duration">
                ({formatDuration(duration)})
              </span>
            )}
          </div>

          {/* Stale data warning */}
          {isDataStale && (
            <div className="text-xs text-yellow-400/80" data-testid="stale-data-warning">
              Data may be stale: events and system status may be outdated
            </div>
          )}

          {/* Polling fallback indicator */}
          {isPollingFallback && (
            <div className="text-xs text-blue-400" data-testid="polling-fallback-indicator">
              Using REST API fallback for data updates
            </div>
          )}
        </div>
      </div>

      {/* Right side: Action buttons */}
      <div className="flex items-center gap-2">
        {/* Retry button (only for failed state) */}
        {showRetryButton && (
          <button
            onClick={onRetry}
            className="rounded-md bg-orange-600 px-3 py-1 text-sm font-medium text-white transition-colors hover:bg-orange-500"
            data-testid="retry-button"
            aria-label="Retry connection"
          >
            Retry
          </button>
        )}

        {/* Dismiss button */}
        <button
          onClick={() => setIsDismissed(true)}
          className="rounded-md p-1 text-text-secondary transition-colors hover:bg-gray-700 hover:text-white"
          data-testid="dismiss-button"
          aria-label="Dismiss notification"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

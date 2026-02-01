import { AlertTriangle, CheckCircle, RefreshCw, Wifi, WifiOff, XCircle } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import type { ConnectionState } from '../../hooks/useWebSocketStatus';

export interface WebSocketEndpointStatus {
  /** Display name for the endpoint */
  name: string;
  /** Current connection state */
  state: ConnectionState;
  /** Current reconnection attempt count */
  reconnectAttempts: number;
  /** Maximum reconnection attempts before giving up */
  maxReconnectAttempts: number;
  /** Whether max retries have been exhausted */
  hasExhaustedRetries: boolean;
  /** Timestamp of the last message received */
  lastMessageTime: Date | null;
}

export interface WebSocketStatusIndicatorProps {
  /** Array of endpoint statuses to display */
  endpoints: WebSocketEndpointStatus[];
  /** Optional callback to retry all connections after failure */
  onRetry?: () => void;
  /** Whether currently falling back to REST API polling */
  isPollingFallback?: boolean;
  /** Show compact mode (icon only) */
  compact?: boolean;
  /** Size variant */
  size?: 'sm' | 'md';
}

/**
 * Get color classes based on connection state
 */
function getStateColor(state: ConnectionState): {
  bg: string;
  text: string;
  dot: string;
} {
  switch (state) {
    case 'connected':
      return {
        bg: 'bg-green-500/10',
        text: 'text-green-400',
        dot: 'bg-green-500',
      };
    case 'reconnecting':
      return {
        bg: 'bg-yellow-500/10',
        text: 'text-yellow-400',
        dot: 'bg-yellow-500',
      };
    case 'failed':
      return {
        bg: 'bg-orange-500/10',
        text: 'text-orange-400',
        dot: 'bg-orange-500',
      };
    case 'disconnected':
    default:
      return {
        bg: 'bg-red-500/10',
        text: 'text-red-400',
        dot: 'bg-red-500',
      };
  }
}

/**
 * Get icon component based on connection state
 */
function StatusIcon({
  state,
  className,
}: {
  state: ConnectionState;
  className: string;
}) {
  switch (state) {
    case 'connected':
      return <Wifi className={className} aria-hidden="true" />;
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
 * Get small status icon for endpoint indicators
 */
function EndpointStatusIcon({ state }: { state: ConnectionState }) {
  switch (state) {
    case 'connected':
      return <CheckCircle className="h-3 w-3 text-green-500" aria-hidden="true" />;
    case 'reconnecting':
      return (
        <RefreshCw
          className="h-3 w-3 text-yellow-500 motion-safe:animate-spin"
          aria-hidden="true"
        />
      );
    case 'failed':
      return <AlertTriangle className="h-3 w-3 text-orange-500" aria-hidden="true" />;
    case 'disconnected':
    default:
      return <XCircle className="h-3 w-3 text-red-500" aria-hidden="true" />;
  }
}

/**
 * Format time since last message
 */
function formatTimeSince(lastMessageTime: Date | null): string {
  if (!lastMessageTime) {
    return 'No messages yet';
  }

  const now = new Date();
  const diffMs = now.getTime() - lastMessageTime.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  if (diffSec < 5) {
    return 'Just now';
  } else if (diffSec < 60) {
    return `${diffSec}s ago`;
  } else if (diffSec < 3600) {
    const mins = Math.floor(diffSec / 60);
    return `${mins}m ago`;
  } else {
    const hours = Math.floor(diffSec / 3600);
    return `${hours}h ago`;
  }
}

/**
 * Get overall connection state from multiple endpoints
 */
function getOverallState(endpoints: WebSocketEndpointStatus[]): ConnectionState {
  if (endpoints.length === 0) {
    return 'disconnected';
  }

  const allConnected = endpoints.every((e) => e.state === 'connected');
  if (allConnected) {
    return 'connected';
  }

  const anyFailed = endpoints.some((e) => e.state === 'failed');
  if (anyFailed) {
    return 'failed';
  }

  const anyReconnecting = endpoints.some((e) => e.state === 'reconnecting');
  if (anyReconnecting) {
    return 'reconnecting';
  }

  return 'disconnected';
}

/**
 * Get state label for display
 */
function getStateLabel(state: ConnectionState, reconnectAttempts: number): string {
  switch (state) {
    case 'connected':
      return 'Connected';
    case 'reconnecting':
      return `Reconnecting${reconnectAttempts > 0 ? ` (${reconnectAttempts})` : ''}`;
    case 'failed':
      return 'Connection Failed';
    case 'disconnected':
      return 'Disconnected';
  }
}

interface EndpointRowProps {
  endpoint: WebSocketEndpointStatus;
}

function EndpointRow({ endpoint }: EndpointRowProps) {
  const [timeSince, setTimeSince] = useState(() => formatTimeSince(endpoint.lastMessageTime));
  const stateColors = getStateColor(endpoint.state);

  // Update time since every second
  useEffect(() => {
    const interval = setInterval(() => {
      setTimeSince(formatTimeSince(endpoint.lastMessageTime));
    }, 1000);

    return () => clearInterval(interval);
  }, [endpoint.lastMessageTime]);

  return (
    <div
      className="flex items-center justify-between py-1.5"
      data-testid={`endpoint-${endpoint.name.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <div className="flex items-center gap-2">
        <EndpointStatusIcon state={endpoint.state} />
        <div
          className={`h-2 w-2 rounded-full ${stateColors.dot}`}
          aria-hidden="true"
        />
        <span className="text-sm text-gray-300">{endpoint.name}</span>
      </div>
      <div className="flex items-center gap-2">
        {endpoint.state === 'reconnecting' && (
          <span className="text-xs text-yellow-400">
            {endpoint.reconnectAttempts}/{endpoint.maxReconnectAttempts}
          </span>
        )}
        {endpoint.state === 'failed' && (
          <span className="text-xs text-orange-400">Failed</span>
        )}
        <span className="text-xs text-gray-500">{timeSince}</span>
      </div>
    </div>
  );
}

interface TooltipContentProps {
  endpoints: WebSocketEndpointStatus[];
  isPollingFallback?: boolean;
}

function TooltipContent({ endpoints, isPollingFallback }: TooltipContentProps) {
  const connectedCount = endpoints.filter((e) => e.state === 'connected').length;
  const totalCount = endpoints.length;

  return (
    <div
      className="absolute right-0 top-full z-50 mt-2 min-w-[240px] rounded-lg border border-gray-700 bg-gray-900 p-3 shadow-lg"
      role="tooltip"
      data-testid="websocket-indicator-tooltip"
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
          WebSocket Connections
        </span>
        <span className="text-xs text-gray-500">
          {connectedCount}/{totalCount}
        </span>
      </div>
      <div className="divide-y divide-gray-800">
        {endpoints.map((endpoint) => (
          <EndpointRow key={endpoint.name} endpoint={endpoint} />
        ))}
      </div>
      {isPollingFallback && (
        <div className="mt-2 border-t border-gray-800 pt-2">
          <div className="text-xs text-blue-400">
            Using REST API fallback (auto-reconnect enabled)
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * A compact WebSocket connection status indicator.
 *
 * Shows connection health across multiple WebSocket endpoints with
 * a tooltip for detailed status. Suitable for header/footer placement.
 *
 * @example
 * ```tsx
 * const endpoints = [
 *   { name: 'Events', state: 'connected', ... },
 *   { name: 'System', state: 'reconnecting', ... },
 * ];
 *
 * <WebSocketStatusIndicator
 *   endpoints={endpoints}
 *   onRetry={handleRetry}
 * />
 * ```
 */
export default function WebSocketStatusIndicator({
  endpoints,
  onRetry,
  isPollingFallback = false,
  compact = false,
  size = 'sm',
}: WebSocketStatusIndicatorProps) {
  const [isTooltipVisible, setIsTooltipVisible] = useState(false);
  const tooltipTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const overallState = getOverallState(endpoints);
  const stateColors = getStateColor(overallState);
  const totalReconnectAttempts = endpoints.reduce((sum, e) => sum + e.reconnectAttempts, 0);
  const hasAnyFailed = endpoints.some((e) => e.hasExhaustedRetries);

  // Icon size based on size prop
  const iconSize = size === 'sm' ? 'h-3.5 w-3.5' : 'h-4 w-4';
  const dotSize = size === 'sm' ? 'h-1.5 w-1.5' : 'h-2 w-2';

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (tooltipTimeoutRef.current) {
        clearTimeout(tooltipTimeoutRef.current);
      }
    };
  }, []);

  const handleMouseEnter = () => {
    if (tooltipTimeoutRef.current) {
      clearTimeout(tooltipTimeoutRef.current);
    }
    setIsTooltipVisible(true);
  };

  const handleMouseLeave = () => {
    tooltipTimeoutRef.current = setTimeout(() => {
      setIsTooltipVisible(false);
    }, 150);
  };

  const handleClick = () => {
    if (overallState === 'failed' && onRetry) {
      onRetry();
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if ((event.key === 'Enter' || event.key === ' ') && overallState === 'failed' && onRetry) {
      event.preventDefault();
      onRetry();
    }
  };

  const connectedCount = endpoints.filter((e) => e.state === 'connected').length;
  const totalCount = endpoints.length;

  return (
    <div
      className={`relative flex items-center gap-1.5 rounded px-2 py-1 ${stateColors.bg} ${
        overallState === 'failed' && onRetry ? 'cursor-pointer hover:opacity-80' : 'cursor-pointer'
      }`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      data-testid="websocket-status-indicator"
      role="button"
      tabIndex={0}
      aria-label={`WebSocket status: ${getStateLabel(overallState, totalReconnectAttempts)} - ${connectedCount} of ${totalCount} connected${hasAnyFailed ? ' - Click to retry' : ''}`}
      aria-haspopup="true"
    >
      {/* Status Icon */}
      <StatusIcon state={overallState} className={`${iconSize} ${stateColors.text}`} />

      {/* Status Label - show when not compact */}
      {!compact && (
        <>
          {overallState === 'connected' ? (
            <span className={`text-xs font-medium ${stateColors.text}`}>
              {connectedCount}/{totalCount}
            </span>
          ) : overallState === 'reconnecting' ? (
            <span className={`text-xs font-medium ${stateColors.text}`}>
              {totalReconnectAttempts > 0 ? totalReconnectAttempts : 'Retrying'}
            </span>
          ) : overallState === 'failed' ? (
            <span className={`text-xs font-medium ${stateColors.text}`}>Failed</span>
          ) : (
            <span className={`text-xs font-medium ${stateColors.text}`}>Offline</span>
          )}
        </>
      )}

      {/* Polling Fallback Indicator */}
      {isPollingFallback && (
        <span className="text-xs font-medium text-blue-400" data-testid="polling-indicator">
          REST
        </span>
      )}

      {/* Status Dot */}
      <div
        className={`${dotSize} rounded-full ${stateColors.dot} ${
          overallState === 'connected' ? 'motion-safe:animate-pulse' : ''
        }`}
        data-testid="status-dot"
        aria-hidden="true"
      />

      {/* Tooltip */}
      {isTooltipVisible && (
        <TooltipContent endpoints={endpoints} isPollingFallback={isPollingFallback} />
      )}
    </div>
  );
}

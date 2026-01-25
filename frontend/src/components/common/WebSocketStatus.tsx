import { AlertTriangle, CheckCircle, RefreshCw, Wifi, WifiOff, XCircle } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import type { ChannelStatus, ConnectionState } from '../../hooks/useWebSocketStatus';

export interface WebSocketStatusProps {
  eventsChannel: ChannelStatus;
  systemChannel: ChannelStatus;
  showDetails?: boolean;
  /** Optional callback to retry connection after failure */
  onRetry?: () => void;
  /** Whether currently falling back to REST API polling */
  isPollingFallback?: boolean;
}

/**
 * Get color classes based on connection state
 */
function getStateColor(state: ConnectionState): {
  bg: string;
  text: string;
  border: string;
} {
  switch (state) {
    case 'connected':
      return {
        bg: 'bg-green-500',
        text: 'text-green-400',
        border: 'border-green-500',
      };
    case 'reconnecting':
      return {
        bg: 'bg-yellow-500',
        text: 'text-yellow-400',
        border: 'border-yellow-500',
      };
    case 'failed':
      return {
        bg: 'bg-orange-500',
        text: 'text-orange-400',
        border: 'border-orange-500',
      };
    case 'disconnected':
    default:
      return {
        bg: 'bg-red-500',
        text: 'text-red-400',
        border: 'border-red-500',
      };
  }
}

/**
 * Get icon component based on connection state
 */
function getStateIcon(state: ConnectionState, className: string) {
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
 * Get small status icon for channel indicators (accessibility improvement)
 */
function ChannelStatusIcon({ state }: { state: ConnectionState }) {
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
 * Get overall connection state from multiple channels
 */
function getOverallState(
  eventsChannel: ChannelStatus,
  systemChannel: ChannelStatus
): ConnectionState {
  if (eventsChannel.state === 'connected' && systemChannel.state === 'connected') {
    return 'connected';
  }
  // If any channel has failed (exhausted retries), overall state is failed
  if (eventsChannel.state === 'failed' || systemChannel.state === 'failed') {
    return 'failed';
  }
  if (eventsChannel.state === 'reconnecting' || systemChannel.state === 'reconnecting') {
    return 'reconnecting';
  }
  return 'disconnected';
}

/**
 * Get state label for display
 */
function getStateLabel(state: ConnectionState): string {
  switch (state) {
    case 'connected':
      return 'Connected';
    case 'reconnecting':
      return 'Reconnecting';
    case 'failed':
      return 'Connection Failed';
    case 'disconnected':
      return 'Disconnected';
  }
}

interface ChannelIndicatorProps {
  channel: ChannelStatus;
}

function ChannelIndicator({ channel }: ChannelIndicatorProps) {
  const [timeSince, setTimeSince] = useState(() => formatTimeSince(channel.lastMessageTime));
  const stateColors = getStateColor(channel.state);

  // Update time since every second
  useEffect(() => {
    const interval = setInterval(() => {
      setTimeSince(formatTimeSince(channel.lastMessageTime));
    }, 1000);

    return () => clearInterval(interval);
  }, [channel.lastMessageTime]);

  return (
    <div
      className="flex items-center justify-between py-1.5"
      data-testid={`channel-${channel.name.toLowerCase()}`}
    >
      <div className="flex items-center gap-2">
        {/* Status Icon (accessibility improvement - not color-only) */}
        <ChannelStatusIcon state={channel.state} />
        <div
          className={`h-2 w-2 rounded-full ${stateColors.bg}`}
          data-testid={`channel-dot-${channel.name.toLowerCase()}`}
          aria-hidden="true"
        />
        <span className="text-sm text-gray-300">{channel.name}</span>
        <span className="sr-only">{getStateLabel(channel.state)}</span>
      </div>
      <div className="flex items-center gap-2">
        {channel.state === 'reconnecting' && (
          <span
            className="text-xs text-yellow-400"
            data-testid={`reconnect-counter-${channel.name.toLowerCase()}`}
          >
            Attempt {channel.reconnectAttempts}/{channel.maxReconnectAttempts}
          </span>
        )}
        {channel.state === 'failed' && (
          <span
            className="text-xs text-orange-400"
            data-testid={`failed-indicator-${channel.name.toLowerCase()}`}
          >
            Retries exhausted
          </span>
        )}
        <span
          className="text-xs text-gray-500"
          data-testid={`last-message-${channel.name.toLowerCase()}`}
        >
          {timeSince}
        </span>
      </div>
    </div>
  );
}

interface WebSocketTooltipProps {
  eventsChannel: ChannelStatus;
  systemChannel: ChannelStatus;
  isVisible: boolean;
  isPollingFallback?: boolean;
}

function WebSocketTooltip({
  eventsChannel,
  systemChannel,
  isVisible,
  isPollingFallback,
}: WebSocketTooltipProps) {
  if (!isVisible) {
    return null;
  }

  return (
    <div
      className="absolute right-0 top-full z-50 mt-2 min-w-[220px] rounded-lg border border-gray-700 bg-gray-900 p-3 shadow-lg"
      role="tooltip"
      data-testid="websocket-tooltip"
    >
      <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">
        WebSocket Channels
      </div>
      <div className="divide-y divide-gray-800">
        <ChannelIndicator channel={eventsChannel} />
        <ChannelIndicator channel={systemChannel} />
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

export default function WebSocketStatus({
  eventsChannel,
  systemChannel,
  showDetails = false,
  onRetry,
  isPollingFallback = false,
}: WebSocketStatusProps) {
  const [isTooltipVisible, setIsTooltipVisible] = useState(false);
  const tooltipTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const overallState = getOverallState(eventsChannel, systemChannel);
  const stateColors = getStateColor(overallState);

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

  const totalReconnectAttempts = eventsChannel.reconnectAttempts + systemChannel.reconnectAttempts;
  const hasAnyFailed = eventsChannel.hasExhaustedRetries || systemChannel.hasExhaustedRetries;

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if ((event.key === 'Enter' || event.key === ' ') && overallState === 'failed' && onRetry) {
      event.preventDefault();
      onRetry();
    }
  };

  return (
    <div
      className={`relative flex items-center gap-2 ${
        overallState === 'failed' && onRetry ? 'cursor-pointer hover:opacity-80' : 'cursor-pointer'
      }`}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      data-testid="websocket-status"
      role="button"
      tabIndex={0}
      aria-label={`WebSocket connection status: ${getStateLabel(overallState)}${
        hasAnyFailed ? ' - Click to retry' : ''
      }`}
      aria-haspopup="true"
    >
      {/* Connection Icon */}
      <div className={`flex items-center gap-1.5 ${stateColors.text}`}>
        {getStateIcon(overallState, 'h-4 w-4')}
      </div>

      {/* Status Label (shown when showDetails is true, reconnecting, or failed) */}
      {(showDetails || overallState === 'reconnecting' || overallState === 'failed') && (
        <span className={`text-xs font-medium ${stateColors.text}`} data-testid="connection-label">
          {overallState === 'reconnecting'
            ? `Reconnecting (${totalReconnectAttempts})`
            : overallState === 'failed'
              ? 'Connection Failed'
              : getStateLabel(overallState)}
        </span>
      )}

      {/* Polling Fallback Indicator */}
      {isPollingFallback && (
        <span className="text-xs font-medium text-blue-400" data-testid="polling-indicator">
          Polling
        </span>
      )}

      {/* Status Dot */}
      <div
        className={`h-2 w-2 rounded-full ${stateColors.bg} ${overallState === 'connected' ? 'motion-safe:animate-pulse' : ''}`}
        data-testid="overall-status-dot"
        aria-hidden="true"
      />

      {/* Tooltip with channel details */}
      <WebSocketTooltip
        eventsChannel={eventsChannel}
        systemChannel={systemChannel}
        isVisible={isTooltipVisible}
        isPollingFallback={isPollingFallback}
      />
    </div>
  );
}

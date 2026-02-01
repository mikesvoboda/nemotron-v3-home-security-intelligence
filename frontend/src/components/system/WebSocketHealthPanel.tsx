import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Radio,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import { useEffect, useState, useCallback, useRef } from 'react';

import {
  fetchWebSocketHealth,
  type WebSocketHealthResponse,
  type WebSocketBroadcasterHealthStatus,
  type WebSocketCircuitState,
} from '../../services/api';

/**
 * Props for WebSocketHealthPanel component
 */
export interface WebSocketHealthPanelProps {
  /** Polling interval in milliseconds (default: 30000) */
  pollingInterval?: number;
  /** Additional CSS classes */
  className?: string;
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
}

/**
 * Get badge color for circuit state
 */
function getStateColor(state: WebSocketCircuitState): 'emerald' | 'red' | 'yellow' | 'gray' {
  switch (state) {
    case 'closed':
      return 'emerald';
    case 'open':
      return 'red';
    case 'half_open':
      return 'yellow';
    case 'unavailable':
    default:
      return 'gray';
  }
}

/**
 * Get human-readable label for circuit state
 */
function getStateLabel(state: WebSocketCircuitState): string {
  switch (state) {
    case 'closed':
      return 'Healthy';
    case 'open':
      return 'Open (Failing)';
    case 'half_open':
      return 'Testing';
    case 'unavailable':
      return 'Unavailable';
    default:
      return 'Unknown';
  }
}

/**
 * Status icon component
 */
function StatusIcon({ state, isDegraded }: { state: WebSocketCircuitState; isDegraded: boolean }) {
  if (isDegraded || state === 'open') {
    return <XCircle className="h-4 w-4 text-red-500" data-testid="status-icon-error" />;
  }
  if (state === 'half_open') {
    return <AlertTriangle className="h-4 w-4 text-yellow-500" data-testid="status-icon-warning" />;
  }
  if (state === 'closed') {
    return <CheckCircle className="h-4 w-4 text-green-500" data-testid="status-icon-healthy" />;
  }
  return <AlertTriangle className="h-4 w-4 text-gray-500" data-testid="status-icon-unknown" />;
}

/**
 * Broadcaster status card
 */
interface BroadcasterCardProps {
  name: string;
  displayName: string;
  description: string;
  status: WebSocketBroadcasterHealthStatus | null | undefined;
}

function BroadcasterCard({ name, displayName, description, status }: BroadcasterCardProps) {
  const state: WebSocketCircuitState = status?.state ?? 'unavailable';
  const isDegraded = status?.is_degraded ?? true;
  const failureCount = status?.failure_count ?? 0;
  const message = status?.message;

  return (
    <div
      className={clsx(
        'rounded-lg border p-3 transition-colors',
        state === 'closed' && !isDegraded && 'border-gray-700 bg-gray-800/50',
        (state === 'open' || isDegraded) && 'border-red-500/30 bg-red-500/10',
        state === 'half_open' && 'border-yellow-500/30 bg-yellow-500/10',
        state === 'unavailable' && 'border-gray-600 bg-gray-800/30'
      )}
      data-testid={`broadcaster-card-${name}`}
    >
      <div className="flex items-start justify-between gap-2">
        {/* Left side: Status and info */}
        <div className="flex items-start gap-2">
          <StatusIcon state={state} isDegraded={isDegraded} />
          <div className="flex flex-col">
            <Text className="text-sm font-medium text-gray-200">{displayName}</Text>
            <Text className="text-xs text-gray-500">{description}</Text>
            {failureCount > 0 && (
              <Text className="mt-1 text-xs text-yellow-400">
                {failureCount} consecutive failure{failureCount === 1 ? '' : 's'}
              </Text>
            )}
            {message && (
              <Text className="mt-1 text-xs text-gray-400">{message}</Text>
            )}
          </div>
        </div>

        {/* Right side: Status badge */}
        <div className="flex flex-col items-end gap-2">
          <Badge
            color={getStateColor(state)}
            size="xs"
            data-testid={`broadcaster-status-badge-${name}`}
          >
            {getStateLabel(state)}
          </Badge>
          {isDegraded && state !== 'unavailable' && (
            <Badge color="red" size="xs" data-testid={`broadcaster-degraded-badge-${name}`}>
              Degraded
            </Badge>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * WebSocketHealthPanel - Displays WebSocket broadcaster health status (NEM-4949)
 *
 * Shows:
 * - Event broadcaster status (handles security events)
 * - System broadcaster status (handles system updates)
 * - Circuit breaker states for each broadcaster
 * - Degradation indicators
 */
export default function WebSocketHealthPanel({
  pollingInterval = 30000,
  className,
  'data-testid': testId = 'websocket-health-panel',
}: WebSocketHealthPanelProps) {
  const [data, setData] = useState<WebSocketHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  // Track if component is mounted
  const isMountedRef = useRef(true);

  // Fetch WebSocket health data
  const fetchData = useCallback(async (isRefresh = false) => {
    if (!isMountedRef.current) return;

    if (isRefresh) {
      setRefreshing(true);
    }

    try {
      const response = await fetchWebSocketHealth();
      if (isMountedRef.current) {
        setData(response);
        setError(null);
        setLoading(false);
        setRefreshing(false);
      }
    } catch (err) {
      if (isMountedRef.current) {
        console.error('Failed to fetch WebSocket health:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch WebSocket health');
        setLoading(false);
        setRefreshing(false);
      }
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    isMountedRef.current = true;
    void fetchData();

    return () => {
      isMountedRef.current = false;
    };
  }, [fetchData]);

  // Polling
  useEffect(() => {
    if (pollingInterval <= 0) return;

    const intervalId = setInterval(() => {
      void fetchData();
    }, pollingInterval);

    return () => clearInterval(intervalId);
  }, [pollingInterval, fetchData]);

  // Handle refresh button click
  const handleRefresh = () => {
    void fetchData(true);
  };

  // Calculate overall health
  const eventHealthy = data?.event_broadcaster?.state === 'closed' && !data.event_broadcaster.is_degraded;
  const systemHealthy = data?.system_broadcaster?.state === 'closed' && !data.system_broadcaster.is_degraded;
  const allHealthy = eventHealthy && systemHealthy;
  const hasIssues = !allHealthy && data !== null;

  // Loading state
  if (loading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid={`${testId}-loading`}
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Radio className="h-5 w-5 text-[#76B900]" />
          WebSocket Health
        </Title>
        <div className="space-y-3">
          {Array.from({ length: 2 }, (_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-lg bg-gray-800"></div>
          ))}
        </div>
      </Card>
    );
  }

  // Error state
  if (error && !data) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid={`${testId}-error`}
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Radio className="h-5 w-5 text-[#76B900]" />
          WebSocket Health
        </Title>
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <XCircle className="h-5 w-5 text-red-500" />
          <div>
            <Text className="text-sm font-medium text-red-400">Failed to load</Text>
            <Text className="text-xs text-gray-400">{error}</Text>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className={clsx(
        'border-gray-800 bg-[#1A1A1A] shadow-lg',
        hasIssues && 'border-yellow-500/30',
        className
      )}
      data-testid={testId}
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Radio className="h-5 w-5 text-[#76B900]" />
          WebSocket Health
        </Title>
        <div className="flex items-center gap-2">
          <Badge
            color={allHealthy ? 'emerald' : hasIssues ? 'yellow' : 'gray'}
            size="sm"
            data-testid="websocket-overall-badge"
          >
            {allHealthy ? 'All Healthy' : hasIssues ? 'Issues Detected' : 'Unknown'}
          </Badge>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="rounded p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white disabled:opacity-50"
            data-testid="websocket-refresh-btn"
            title="Refresh status"
          >
            {refreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </button>
        </div>
      </div>

      {/* Broadcaster cards */}
      <div className="space-y-3">
        <BroadcasterCard
          name="event"
          displayName="Event Broadcaster"
          description="Handles real-time security event distribution"
          status={data?.event_broadcaster}
        />
        <BroadcasterCard
          name="system"
          displayName="System Broadcaster"
          description="Handles system status updates (GPU, cameras, queues)"
          status={data?.system_broadcaster}
        />
      </div>

      {/* Last updated timestamp */}
      {data?.timestamp && (
        <p className="mt-4 text-xs text-gray-500" data-testid="websocket-last-updated">
          Last updated: {new Date(data.timestamp).toLocaleTimeString()}
        </p>
      )}
    </Card>
  );
}

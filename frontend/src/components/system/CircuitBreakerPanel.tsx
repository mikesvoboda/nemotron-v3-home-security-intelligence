import { Card, Title, Text, Badge, Button } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Zap,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  AlertCircle,
  Bug,
  Radio,
  Wifi,
} from 'lucide-react';

import type { WebSocketBroadcasterStatus } from '../../services/api';
import type {
  CircuitBreakerStateEnum,
  CircuitBreakerStatusResponse,
  CircuitBreakersResponse,
} from '../../types/generated';

/**
 * WebSocket status for debug mode
 */
export interface WebSocketDebugStatus {
  event_broadcaster: WebSocketBroadcasterStatus;
  system_broadcaster: WebSocketBroadcasterStatus;
}

/**
 * Props for CircuitBreakerPanel component
 */
export interface CircuitBreakerPanelProps {
  /** Circuit breakers data from API */
  data: CircuitBreakersResponse | null;
  /** Loading state */
  loading: boolean;
  /** Error message if fetch failed */
  error: string | null;
  /** Callback when reset button is clicked */
  onReset: (name: string) => void | Promise<void>;
  /** Additional CSS classes */
  className?: string;
  /** Optional data-testid attribute for testing */
  'data-testid'?: string;
  /** Whether debug mode is enabled - shows additional debug info */
  debugMode?: boolean;
  /** WebSocket broadcaster status (only shown when debugMode is true) */
  webSocketStatus?: WebSocketDebugStatus | null;
  /** Whether WebSocket status is loading */
  webSocketLoading?: boolean;
  /** Error message if WebSocket status failed to load */
  webSocketError?: string | null;
}

/**
 * Get badge color based on circuit breaker state
 */
function getStateColor(state: CircuitBreakerStateEnum): 'green' | 'red' | 'yellow' {
  switch (state) {
    case 'closed':
      return 'green';
    case 'open':
      return 'red';
    case 'half_open':
      return 'yellow';
    default:
      return 'red';
  }
}

/**
 * Get icon based on circuit breaker state
 */
function StateIcon({ state }: { state: CircuitBreakerStateEnum }) {
  switch (state) {
    case 'closed':
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    case 'open':
      return <XCircle className="h-4 w-4 text-red-500" />;
    case 'half_open':
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    default:
      return <AlertCircle className="h-4 w-4 text-gray-500" />;
  }
}

/**
 * Format monotonic time (seconds) for display
 * Monotonic times are relative to system start, so we show a relative time
 */
function formatMonotonicTime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return 'N/A';
  // Show as "Xs ago" if recent, or "X min ago" for older
  const now = performance.now() / 1000;
  const diff = now - seconds;
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`;
  return `${Math.round(diff / 3600)}h ago`;
}

/**
 * Check if circuit breaker is in a healthy state
 */
function isHealthy(state: CircuitBreakerStateEnum): boolean {
  return state === 'closed';
}

/**
 * CircuitBreakerPanel - Displays circuit breaker status with reset capability
 *
 * Shows:
 * - Circuit breaker name and state (CLOSED=green, OPEN=red, HALF_OPEN=yellow)
 * - Failure count and last failure time
 * - Configuration (threshold, timeout)
 * - Reset button for non-closed breakers
 */
/**
 * Get color for circuit state badge
 */
function getCircuitStateColor(state: string): 'green' | 'yellow' | 'red' | 'gray' {
  switch (state.toUpperCase()) {
    case 'CLOSED':
      return 'green';
    case 'HALF_OPEN':
      return 'yellow';
    case 'OPEN':
      return 'red';
    default:
      return 'gray';
  }
}

export default function CircuitBreakerPanel({
  data,
  loading,
  error,
  onReset,
  className,
  'data-testid': testId = 'circuit-breaker-panel',
  debugMode = false,
  webSocketStatus = null,
  webSocketLoading = false,
  webSocketError = null,
}: CircuitBreakerPanelProps) {
  // Loading state
  if (loading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="circuit-breaker-panel-loading"
      >
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="h-5 w-5 animate-pulse rounded bg-gray-700" />
            <div className="h-6 w-40 animate-pulse rounded bg-gray-700" />
          </div>
          <div className="h-6 w-24 animate-pulse rounded bg-gray-700" />
        </div>
        <div className="space-y-3">
          {[1, 2].map((i) => (
            <div key={i} className="h-20 animate-pulse rounded-lg bg-gray-800/50" />
          ))}
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="circuit-breaker-panel-error"
      >
        <div className="mb-4 flex items-center gap-2">
          <Zap className="h-5 w-5 text-[#76B900]" />
          <Title className="text-white">Circuit Breakers</Title>
        </div>
        <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <Text className="text-red-400">{error}</Text>
        </div>
      </Card>
    );
  }

  // Get circuit breakers as array
  const breakers = data?.circuit_breakers ? Object.values(data.circuit_breakers) : [];

  // Calculate summary stats
  const healthyCount = breakers.filter((b) => isHealthy(b.state)).length;
  const totalCount = breakers.length;

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid={testId}
    >
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Zap className="h-5 w-5 text-[#76B900]" />
          Circuit Breakers
        </Title>
        <Badge
          color={healthyCount === totalCount ? 'green' : 'red'}
          size="sm"
          data-testid="circuit-breaker-summary"
        >
          {healthyCount}/{totalCount} Healthy
        </Badge>
      </div>

      {breakers.length === 0 ? (
        <div className="flex h-32 items-center justify-center">
          <Text className="text-sm text-gray-500">No circuit breakers available</Text>
        </div>
      ) : (
        <div className="space-y-3">
          {breakers.map((breaker) => (
            <CircuitBreakerRow key={breaker.name} breaker={breaker} onReset={onReset} />
          ))}
        </div>
      )}

      {/* Debug Section - WebSocket Status */}
      {debugMode && (
        <div
          className="mt-4 rounded-lg border border-orange-500/30 bg-orange-500/5 p-3"
          data-testid="websocket-debug-section"
        >
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Bug className="h-4 w-4 text-orange-500" />
              <Text className="text-sm font-medium text-orange-400">WebSocket Broadcasters</Text>
              <Badge color="orange" size="xs">
                DEBUG
              </Badge>
            </div>
            {webSocketStatus && (
              <Text className="text-xs text-gray-400">
                {webSocketStatus.event_broadcaster.connection_count +
                  webSocketStatus.system_broadcaster.connection_count}{' '}
                connections
              </Text>
            )}
          </div>

          {/* Loading state */}
          {webSocketLoading && (
            <div className="space-y-2" data-testid="websocket-debug-loading">
              <div className="h-16 animate-pulse rounded bg-gray-700/50" />
              <div className="h-16 animate-pulse rounded bg-gray-700/50" />
            </div>
          )}

          {/* Error state */}
          {webSocketError && !webSocketLoading && (
            <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2">
              <AlertCircle className="h-4 w-4 text-red-500" />
              <Text className="text-xs text-red-400">{webSocketError}</Text>
            </div>
          )}

          {/* Empty state */}
          {!webSocketLoading && !webSocketError && !webSocketStatus && (
            <Text className="text-sm text-gray-500">No WebSocket status available</Text>
          )}

          {/* WebSocket status content */}
          {!webSocketLoading && !webSocketError && webSocketStatus && (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {/* Event Broadcaster */}
              <BroadcasterCard
                name="Event Broadcaster"
                status={webSocketStatus.event_broadcaster}
                icon={<Radio className="h-4 w-4 text-blue-400" />}
              />

              {/* System Broadcaster */}
              <BroadcasterCard
                name="System Broadcaster"
                status={webSocketStatus.system_broadcaster}
                icon={<Wifi className="h-4 w-4 text-green-400" />}
              />
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

/**
 * BroadcasterCard - Displays a single WebSocket broadcaster's status
 */
interface BroadcasterCardProps {
  name: string;
  status: WebSocketBroadcasterStatus;
  icon: React.ReactNode;
}

function BroadcasterCard({ name, status, icon }: BroadcasterCardProps) {
  return (
    <div className="rounded border border-gray-700 bg-gray-800/50 p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {icon}
          <Text className="text-sm font-medium text-gray-200">{name}</Text>
        </div>
        <Badge color={getCircuitStateColor(status.circuit_state)} size="xs">
          {status.circuit_state}
        </Badge>
      </div>

      <div className="space-y-1 text-xs">
        <div className="flex items-center justify-between">
          <Text className="text-gray-500">Connections</Text>
          <Text className="font-medium text-gray-200">{status.connection_count}</Text>
        </div>

        <div className="flex items-center justify-between">
          <Text className="text-gray-500">Listening</Text>
          <Badge color={status.is_listening ? 'green' : 'gray'} size="xs">
            {status.is_listening ? 'Yes' : 'No'}
          </Badge>
        </div>

        {status.is_degraded && (
          <div className="flex items-center justify-between">
            <Text className="text-gray-500">Status</Text>
            <Badge color="yellow" size="xs">
              Degraded
            </Badge>
          </div>
        )}

        {status.channel_name && (
          <div className="flex items-center justify-between">
            <Text className="text-gray-500">Channel</Text>
            <Badge color="blue" size="xs">
              {status.channel_name}
            </Badge>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * CircuitBreakerRow - Displays a single circuit breaker's status
 */
interface CircuitBreakerRowProps {
  breaker: CircuitBreakerStatusResponse;
  onReset: (name: string) => void | Promise<void>;
}

function CircuitBreakerRow({ breaker, onReset }: CircuitBreakerRowProps) {
  const canReset = breaker.state !== 'closed';

  return (
    <div
      className={clsx(
        'rounded-lg border p-3',
        breaker.state === 'closed' && 'border-gray-700 bg-gray-800/50',
        breaker.state === 'open' && 'border-red-500/30 bg-red-500/10',
        breaker.state === 'half_open' && 'border-yellow-500/30 bg-yellow-500/10'
      )}
      data-testid={`circuit-breaker-${breaker.name}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          {/* Name and Status */}
          <div className="mb-2 flex items-center gap-2">
            <StateIcon state={breaker.state} />
            <Text className="font-medium text-gray-200">{breaker.name}</Text>
            <Badge
              color={getStateColor(breaker.state)}
              size="xs"
              data-testid={`circuit-breaker-status-${breaker.name}`}
            >
              {breaker.state}
            </Badge>
          </div>

          {/* Metrics Row */}
          <div className="flex flex-wrap gap-4 text-xs text-gray-400">
            <div>
              <span className="text-gray-500">Failures: </span>
              <span
                className={breaker.failure_count > 0 ? 'text-red-400' : 'text-gray-300'}
                data-testid={`failure-count-${breaker.name}`}
              >
                {breaker.failure_count}
              </span>
            </div>
            <div>
              <span className="text-gray-500">Last Failure: </span>
              <span data-testid={`last-failure-${breaker.name}`}>
                {formatMonotonicTime(breaker.last_failure_time)}
              </span>
            </div>
          </div>

          {/* Configuration */}
          <div
            className="mt-2 flex flex-wrap gap-3 text-xs text-gray-500"
            data-testid={`config-${breaker.name}`}
          >
            <span>Threshold: {breaker.config.failure_threshold}</span>
            <span>Timeout: {breaker.config.recovery_timeout}s</span>
            <span>Half-open calls: {breaker.config.half_open_max_calls}</span>
          </div>
        </div>

        {/* Reset Button */}
        {canReset && (
          <Button
            size="xs"
            variant="secondary"
            icon={RefreshCw}
            onClick={() => {
              void onReset(breaker.name);
            }}
            aria-label={`Reset ${breaker.name} circuit breaker`}
            data-testid={`reset-button-${breaker.name}`}
            className="ml-2"
          >
            Reset
          </Button>
        )}
      </div>
    </div>
  );
}

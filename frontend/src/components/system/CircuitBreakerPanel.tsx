import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Shield,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Zap,
} from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import { fetchCircuitBreakers, resetCircuitBreaker } from '../../services/api';

import type {
  CircuitBreakersResponse,
  CircuitBreakerStatusResponse,
  CircuitBreakerStateEnum,
} from '../../services/api';

/**
 * Props for CircuitBreakerPanel component
 */
export interface CircuitBreakerPanelProps {
  /** Polling interval in milliseconds (default: 10000) */
  pollingInterval?: number;
  /** Whether the panel starts expanded (default: true) */
  defaultExpanded?: boolean;
}

/**
 * Human-readable names for circuit breakers
 */
const CIRCUIT_BREAKER_DISPLAY_NAMES: Record<string, string> = {
  rtdetr: 'RT-DETR Detection',
  nemotron: 'Nemotron Analysis',
  websocket: 'WebSocket Broadcast',
  redis: 'Redis Connection',
  postgres: 'PostgreSQL Connection',
};

/**
 * Descriptions for each circuit breaker
 */
const CIRCUIT_BREAKER_DESCRIPTIONS: Record<string, string> = {
  rtdetr: 'Object detection AI service',
  nemotron: 'Risk analysis LLM service',
  websocket: 'Real-time event broadcasting',
  redis: 'Cache and queue backend',
  postgres: 'Primary database connection',
};

/**
 * Gets display name for a circuit breaker
 */
function getDisplayName(name: string): string {
  return (
    CIRCUIT_BREAKER_DISPLAY_NAMES[name] ||
    name.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

/**
 * Gets description for a circuit breaker
 */
function getDescription(name: string): string {
  return CIRCUIT_BREAKER_DESCRIPTIONS[name] || 'External service protection';
}

/**
 * Gets badge color for circuit state
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
      return 'yellow';
  }
}

/**
 * Gets state display text
 */
function getStateText(state: CircuitBreakerStateEnum): string {
  switch (state) {
    case 'closed':
      return 'Closed';
    case 'open':
      return 'Open';
    case 'half_open':
      return 'Half Open';
    default:
      return state;
  }
}

/**
 * Gets icon for circuit state
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
      return <AlertTriangle className="h-4 w-4 text-gray-500" />;
  }
}

/**
 * CircuitBreakerRow - Displays a single circuit breaker's status
 */
interface CircuitBreakerRowProps {
  name: string;
  status: CircuitBreakerStatusResponse;
  onReset: (name: string) => Promise<void>;
  isResetting: boolean;
}

function CircuitBreakerRow({ name, status, onReset, isResetting }: CircuitBreakerRowProps) {
  const displayName = getDisplayName(name);
  const description = getDescription(name);
  const canReset = status.state !== 'closed';

  return (
    <div
      className={clsx(
        'flex items-center justify-between rounded-lg border p-3 transition-colors',
        status.state === 'closed' && 'border-transparent bg-gray-800/50',
        status.state === 'open' && 'border-red-500/30 bg-red-500/10',
        status.state === 'half_open' && 'border-yellow-500/30 bg-yellow-500/10'
      )}
      data-testid={`circuit-breaker-row-${name}`}
    >
      <div className="flex items-center gap-3">
        {/* State Icon */}
        <StateIcon state={status.state} />

        {/* Circuit Info */}
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <Text className="text-sm font-medium text-gray-300">{displayName}</Text>
            <Badge
              color={getStateColor(status.state)}
              size="xs"
              data-testid={`circuit-breaker-state-${name}`}
            >
              {getStateText(status.state)}
            </Badge>
          </div>
          <Text className="text-xs text-gray-500">{description}</Text>
        </div>
      </div>

      {/* Metrics and Actions */}
      <div className="flex items-center gap-4">
        {/* Metrics */}
        <div className="flex items-center gap-3 text-xs">
          <div className="text-center">
            <Text className="text-gray-500">Calls</Text>
            <Text
              className="font-medium text-gray-300"
              data-testid={`total-calls-${name}`}
            >
              {status.total_calls.toLocaleString()}
            </Text>
          </div>
          {status.state !== 'closed' && (
            <>
              <div className="text-center">
                <Text className="text-gray-500">Failures</Text>
                <Text
                  className="font-medium text-red-400"
                  data-testid={`failure-count-${name}`}
                >
                  {status.failure_count}
                </Text>
              </div>
              <div className="text-center">
                <Text className="text-gray-500">Rejected</Text>
                <Text
                  className="font-medium text-orange-400"
                  data-testid={`rejected-calls-${name}`}
                >
                  {status.rejected_calls}
                </Text>
              </div>
            </>
          )}
        </div>

        {/* Reset Button */}
        {canReset && (
          <button
            type="button"
            onClick={() => void onReset(name)}
            disabled={isResetting}
            className={clsx(
              'flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors',
              isResetting
                ? 'cursor-not-allowed bg-gray-700 text-gray-500'
                : 'bg-[#76B900] text-white hover:bg-[#76B900]/80'
            )}
            data-testid={`reset-button-${name}`}
          >
            <RefreshCw className={clsx('h-3 w-3', isResetting && 'animate-spin')} />
            Reset
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * CircuitBreakerPanel - Displays status of all circuit breakers
 *
 * Shows:
 * - All circuit breakers with their current state (closed/open/half_open)
 * - Metrics: total calls, failure count, rejected calls
 * - Reset button for non-closed circuit breakers
 * - Color-coded status indicators
 *
 * Fetches data from GET /api/system/circuit-breakers endpoint.
 */
export default function CircuitBreakerPanel({
  pollingInterval = 10000,
  defaultExpanded = true,
}: CircuitBreakerPanelProps) {
  const [data, setData] = useState<CircuitBreakersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resetting, setResetting] = useState<string | null>(null);
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const fetchData = useCallback(async () => {
    try {
      const response = await fetchCircuitBreakers();
      setData(response);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch circuit breakers:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch circuit breaker status');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleReset = useCallback(
    async (name: string) => {
      setResetting(name);
      try {
        await resetCircuitBreaker(name);
        // Refresh the data after reset
        await fetchData();
      } catch (err) {
        console.error(`Failed to reset circuit breaker ${name}:`, err);
        // Still refresh to show current state
        await fetchData();
      } finally {
        setResetting(null);
      }
    },
    [fetchData]
  );

  // Initial fetch
  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  // Polling
  useEffect(() => {
    const interval = setInterval(() => {
      void fetchData();
    }, pollingInterval);

    return () => clearInterval(interval);
  }, [pollingInterval, fetchData]);

  // Loading state
  if (loading) {
    return (
      <Card
        className="border-gray-800 bg-[#1A1A1A] shadow-lg"
        data-testid="circuit-breaker-panel-loading"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Shield className="h-5 w-5 text-[#76B900]" />
          Circuit Breakers
        </Title>
        <div className="space-y-3">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-gray-800"></div>
          ))}
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card
        className="border-gray-800 bg-[#1A1A1A] shadow-lg"
        data-testid="circuit-breaker-panel-error"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Shield className="h-5 w-5 text-[#76B900]" />
          Circuit Breakers
        </Title>
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertTriangle className="h-5 w-5 text-red-500" />
          <div>
            <Text className="text-sm font-medium text-red-400">
              Failed to load circuit breaker status
            </Text>
            <Text className="text-xs text-gray-400">{error}</Text>
          </div>
        </div>
      </Card>
    );
  }

  const circuitBreakers = data?.circuit_breakers ?? {};
  const circuitBreakerEntries = Object.entries(circuitBreakers);
  const openCount = data?.open_count ?? 0;

  return (
    <Card
      className={clsx(
        'border-gray-800 bg-[#1A1A1A] shadow-lg',
        openCount > 0 && 'border-red-500/50'
      )}
      data-testid="circuit-breaker-panel"
    >
      {/* Collapsible Header */}
      <button
        type="button"
        className="flex w-full items-center justify-between text-left"
        onClick={() => setIsExpanded(!isExpanded)}
        data-testid="circuit-breaker-panel-toggle"
        aria-expanded={isExpanded}
        aria-controls="circuit-breaker-list-content"
      >
        <Title className="flex items-center gap-2 text-white">
          <Shield className="h-5 w-5 text-[#76B900]" />
          Circuit Breakers
          {openCount > 0 && (
            <Zap
              className="h-4 w-4 text-red-500"
              data-testid="open-circuit-warning"
              aria-label="Circuit breaker open"
            />
          )}
        </Title>

        <div className="flex items-center gap-2">
          {/* Summary Badges */}
          {openCount > 0 && (
            <Badge color="red" size="sm" data-testid="open-count-badge">
              {openCount} Open
            </Badge>
          )}
          <Badge
            color={openCount === 0 ? 'green' : 'amber'}
            size="sm"
            data-testid="total-count-badge"
          >
            {circuitBreakerEntries.length} Total
          </Badge>
          {/* Expand/Collapse Icon */}
          {isExpanded ? (
            <ChevronUp className="h-5 w-5 text-gray-400" data-testid="collapse-icon" />
          ) : (
            <ChevronDown className="h-5 w-5 text-gray-400" data-testid="expand-icon" />
          )}
        </div>
      </button>

      {/* Collapsible Content */}
      <div
        id="circuit-breaker-list-content"
        className={clsx(
          'overflow-hidden transition-all duration-300 ease-in-out',
          isExpanded ? 'mt-4 max-h-[1000px] opacity-100' : 'max-h-0 opacity-0'
        )}
        data-testid="circuit-breaker-list-content"
      >
        {/* Circuit Breakers List */}
        <div className="space-y-2" data-testid="circuit-breakers-list">
          {circuitBreakerEntries.length > 0 ? (
            circuitBreakerEntries.map(([name, status]) => (
              <CircuitBreakerRow
                key={name}
                name={name}
                status={status}
                onReset={handleReset}
                isResetting={resetting === name}
              />
            ))
          ) : (
            <Text className="py-4 text-center text-gray-500">
              No circuit breakers configured
            </Text>
          )}
        </div>

        {/* Last Updated */}
        {data?.timestamp && (
          <Text className="mt-4 text-xs text-gray-500" data-testid="last-updated">
            Last updated: {new Date(data.timestamp).toLocaleTimeString()}
          </Text>
        )}
      </div>
    </Card>
  );
}

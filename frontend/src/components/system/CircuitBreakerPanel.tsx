import { Card, Title, Text, Badge, Button } from '@tremor/react';
import { clsx } from 'clsx';
import {
  ShieldCheck,
  ShieldAlert,
  ShieldQuestion,
  RefreshCw,
  AlertTriangle,
  RotateCcw,
  Activity,
} from 'lucide-react';
import { useEffect, useState, useCallback } from 'react';

import {
  fetchCircuitBreakers,
  resetCircuitBreaker,
  type CircuitBreakerStatus,
  type CircuitBreakerState,
} from '../../services/api';

/**
 * Props for CircuitBreakerPanel component
 */
export interface CircuitBreakerPanelProps {
  /** Polling interval in milliseconds (default: 10000) */
  pollingInterval?: number;
  /** Optional callback when circuit breaker status changes */
  onStatusChange?: (breakers: CircuitBreakerStatus[]) => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Human-readable names for circuit breakers
 */
const CIRCUIT_BREAKER_DISPLAY_NAMES: Record<string, string> = {
  rtdetr: 'RT-DETR Service',
  nemotron: 'Nemotron LLM',
  ai_service: 'AI Service',
  redis: 'Redis Cache',
  database: 'Database',
};

/**
 * Descriptions for each circuit breaker's function
 */
const CIRCUIT_BREAKER_DESCRIPTIONS: Record<string, string> = {
  rtdetr: 'Object detection model service',
  nemotron: 'LLM risk analysis service',
  ai_service: 'Combined AI pipeline',
  redis: 'Cache and queue storage',
  database: 'PostgreSQL data storage',
};

/**
 * Gets display name for a circuit breaker
 */
function getDisplayName(name: string): string {
  return (
    CIRCUIT_BREAKER_DISPLAY_NAMES[name] ||
    name
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

/**
 * Gets description for a circuit breaker
 */
function getDescription(name: string): string {
  return CIRCUIT_BREAKER_DESCRIPTIONS[name] || 'External service circuit breaker';
}

/**
 * Get icon and color for circuit state
 */
function getStateDisplay(state: CircuitBreakerState): {
  icon: React.ReactNode;
  color: 'green' | 'red' | 'yellow';
  label: string;
  bgColor: string;
  borderColor: string;
  iconColor: string;
} {
  switch (state) {
    case 'closed':
      return {
        icon: <ShieldCheck className="h-5 w-5" />,
        color: 'green',
        label: 'Closed',
        bgColor: 'bg-green-500/10',
        borderColor: 'border-green-500/30',
        iconColor: 'text-green-500',
      };
    case 'open':
      return {
        icon: <ShieldAlert className="h-5 w-5" />,
        color: 'red',
        label: 'Open',
        bgColor: 'bg-red-500/10',
        borderColor: 'border-red-500/30',
        iconColor: 'text-red-500',
      };
    case 'half_open':
      return {
        icon: <ShieldQuestion className="h-5 w-5" />,
        color: 'yellow',
        label: 'Half-Open',
        bgColor: 'bg-yellow-500/10',
        borderColor: 'border-yellow-500/30',
        iconColor: 'text-yellow-500',
      };
    default:
      return {
        icon: <ShieldQuestion className="h-5 w-5" />,
        color: 'yellow',
        label: 'Unknown',
        bgColor: 'bg-gray-500/10',
        borderColor: 'border-gray-500/30',
        iconColor: 'text-gray-500',
      };
  }
}

/**
 * CircuitBreakerRow - Displays a single circuit breaker's status
 */
interface CircuitBreakerRowProps {
  breaker: CircuitBreakerStatus;
  onReset: (name: string) => void | Promise<void>;
  resetting: boolean;
}

function CircuitBreakerRow({ breaker, onReset, resetting }: CircuitBreakerRowProps) {
  const displayName = getDisplayName(breaker.name);
  const description = getDescription(breaker.name);
  const stateDisplay = getStateDisplay(breaker.state);

  return (
    <div
      className={clsx(
        'flex items-center justify-between rounded-lg border p-3 transition-colors',
        stateDisplay.bgColor,
        stateDisplay.borderColor
      )}
      data-testid={`circuit-breaker-row-${breaker.name}`}
    >
      <div className="flex items-center gap-3">
        {/* Status Icon */}
        <div className={stateDisplay.iconColor}>{stateDisplay.icon}</div>

        {/* Circuit Breaker Info */}
        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <Text className="text-sm font-medium text-gray-300">{displayName}</Text>
            <Badge color={stateDisplay.color} size="xs" data-testid={`state-badge-${breaker.name}`}>
              {stateDisplay.label}
            </Badge>
          </div>
          <Text className="text-xs text-gray-500">{description}</Text>

          {/* Metrics */}
          <div className="mt-1 flex items-center gap-4 text-xs text-gray-500">
            <span>
              Failures: <span className="text-gray-400">{breaker.failure_count}</span>/
              {breaker.config.failure_threshold}
            </span>
            <span>
              Total calls: <span className="text-gray-400">{breaker.total_calls.toLocaleString()}</span>
            </span>
            {breaker.rejected_calls > 0 && (
              <span className="text-red-400">
                Rejected: {breaker.rejected_calls.toLocaleString()}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Reset Button (only for non-closed states) */}
      {breaker.state !== 'closed' && (
        <Button
          size="xs"
          variant="secondary"
          onClick={() => void onReset(breaker.name)}
          disabled={resetting}
          className="text-gray-400 hover:text-white"
          data-testid={`reset-button-${breaker.name}`}
        >
          <RotateCcw className={clsx('mr-1 h-3 w-3', resetting && 'animate-spin')} />
          Reset
        </Button>
      )}
    </div>
  );
}

/**
 * CircuitBreakerPanel - Displays the status of all circuit breakers
 *
 * Shows:
 * - All circuit breakers with their current state (closed/open/half-open)
 * - Visual state indicators with appropriate colors
 * - Failure counts and thresholds
 * - Reset button for non-closed circuits
 *
 * Fetches data from GET /api/system/circuit-breakers endpoint.
 */
export default function CircuitBreakerPanel({
  pollingInterval = 10000,
  onStatusChange,
  className,
}: CircuitBreakerPanelProps) {
  const [breakers, setBreakers] = useState<CircuitBreakerStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resetting, setResetting] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchStatus = useCallback(async (isRefresh = false) => {
    try {
      if (isRefresh) {
        setIsRefreshing(true);
      }
      const response = await fetchCircuitBreakers();
      const breakerList = Object.values(response.circuit_breakers);
      setBreakers(breakerList);
      setLastUpdated(new Date(response.timestamp));
      setError(null);
      onStatusChange?.(breakerList);
    } catch (err) {
      console.error('Failed to fetch circuit breaker status:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch circuit breaker status');
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  }, [onStatusChange]);

  const handleReset = useCallback(
    async (name: string) => {
      setResetting(name);
      try {
        await resetCircuitBreaker(name);
        // Refresh status after reset
        await fetchStatus();
      } catch (err) {
        console.error(`Failed to reset circuit breaker ${name}:`, err);
        setError(err instanceof Error ? err.message : `Failed to reset ${name}`);
      } finally {
        setResetting(null);
      }
    },
    [fetchStatus]
  );

  // Initial fetch
  useEffect(() => {
    void fetchStatus();
  }, [fetchStatus]);

  // Polling
  useEffect(() => {
    const interval = setInterval(() => {
      void fetchStatus();
    }, pollingInterval);

    return () => clearInterval(interval);
  }, [pollingInterval, fetchStatus]);

  // Calculate summary stats
  const closedCount = breakers.filter((b) => b.state === 'closed').length;
  const openCount = breakers.filter((b) => b.state === 'open').length;
  const halfOpenCount = breakers.filter((b) => b.state === 'half_open').length;

  // Sort breakers: open first, then half-open, then closed
  const sortedBreakers = [...breakers].sort((a, b) => {
    const stateOrder: Record<CircuitBreakerState, number> = {
      open: 0,
      half_open: 1,
      closed: 2,
    };
    return stateOrder[a.state] - stateOrder[b.state];
  });

  // Loading state
  if (loading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="circuit-breaker-panel-loading"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Activity className="h-5 w-5 text-[#76B900]" />
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
  if (error && breakers.length === 0) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="circuit-breaker-panel-error"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Activity className="h-5 w-5 text-[#76B900]" />
          Circuit Breakers
        </Title>
        <div className="flex items-center gap-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4">
          <AlertTriangle className="h-5 w-5 text-red-500" />
          <div>
            <Text className="text-sm font-medium text-red-400">Failed to load circuit breaker status</Text>
            <Text className="text-xs text-gray-400">{error}</Text>
          </div>
          <Button
            size="xs"
            variant="secondary"
            onClick={() => void fetchStatus()}
            className="ml-auto"
          >
            <RefreshCw className="mr-1 h-3 w-3" />
            Retry
          </Button>
        </div>
      </Card>
    );
  }

  // Empty state
  if (breakers.length === 0) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="circuit-breaker-panel-empty"
      >
        <Title className="mb-4 flex items-center gap-2 text-white">
          <Activity className="h-5 w-5 text-[#76B900]" />
          Circuit Breakers
        </Title>
        <Text className="py-4 text-center text-gray-500">
          No circuit breakers registered yet
        </Text>
      </Card>
    );
  }

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="circuit-breaker-panel"
    >
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Activity className="h-5 w-5 text-[#76B900]" />
          Circuit Breakers
        </Title>

        {/* Summary Badges */}
        <div className="flex items-center gap-2">
          {openCount > 0 && (
            <Badge color="red" size="sm" data-testid="open-count-badge">
              {openCount} Open
            </Badge>
          )}
          {halfOpenCount > 0 && (
            <Badge color="yellow" size="sm" data-testid="half-open-count-badge">
              {halfOpenCount} Half-Open
            </Badge>
          )}
          <Badge
            color={openCount === 0 ? 'green' : 'gray'}
            size="sm"
            data-testid="closed-count-badge"
          >
            {closedCount}/{breakers.length} Healthy
          </Badge>
        </div>
      </div>

      {/* Status Summary */}
      <div className="mb-4 flex items-center justify-center gap-6 rounded-lg bg-gray-800/30 p-3">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-green-500" />
          <Text className="text-sm text-gray-300">
            <span className="font-bold text-white">{closedCount}</span> Closed
          </Text>
        </div>
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 text-red-500" />
          <Text className="text-sm text-gray-300">
            <span className="font-bold text-white">{openCount}</span> Open
          </Text>
        </div>
        <div className="flex items-center gap-2">
          <ShieldQuestion className="h-4 w-4 text-yellow-500" />
          <Text className="text-sm text-gray-300">
            <span className="font-bold text-white">{halfOpenCount}</span> Testing
          </Text>
        </div>
      </div>

      {/* Error banner (if error but we have cached data) */}
      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2">
          <AlertTriangle className="h-4 w-4 text-amber-500" />
          <Text className="text-xs text-amber-400">{error}</Text>
        </div>
      )}

      {/* Circuit Breakers List */}
      <div className="space-y-2" data-testid="circuit-breakers-list">
        {sortedBreakers.map((breaker) => (
          <CircuitBreakerRow
            key={breaker.name}
            breaker={breaker}
            onReset={handleReset}
            resetting={resetting === breaker.name}
          />
        ))}
      </div>

      {/* Last Updated */}
      {lastUpdated && (
        <div className="mt-4 flex items-center justify-between">
          <Text className="text-xs text-gray-500" data-testid="last-updated">
            Last updated: {lastUpdated.toLocaleTimeString()}
          </Text>
          <Button
            size="xs"
            variant="secondary"
            onClick={() => void fetchStatus(true)}
            disabled={isRefreshing}
            className="text-gray-400 hover:text-white"
          >
            <RefreshCw className={clsx('h-3 w-3', isRefreshing && 'animate-spin')} />
          </Button>
        </div>
      )}
    </Card>
  );
}

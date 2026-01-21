/**
 * CircuitBreakerDebugPanel Component
 *
 * Circuit breaker debug panel for the Developer Tools page.
 * Provides detailed view of all circuit breakers with reset controls.
 *
 * Features:
 * - All circuit breaker states with detailed info
 * - Failure/success counts and timestamps
 * - Configuration details (threshold, timeout, half-open calls)
 * - Manual reset controls for non-closed breakers
 * - Health summary badge
 *
 * @see NEM-3173 - Build Debug Tools admin panel
 */

import { Card, Title, Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Zap,
  RefreshCw,
  AlertCircle,
  Loader2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RotateCcw,
  Info,
} from 'lucide-react';
import { useCallback } from 'react';

import { useCircuitBreakerDebugQuery } from '../../hooks/useCircuitBreakerDebugQuery';
import { useToast } from '../../hooks/useToast';

// ============================================================================
// Types
// ============================================================================

export interface CircuitBreakerDebugPanelProps {
  /** Additional CSS classes */
  className?: string;
}

type CircuitBreakerState = 'closed' | 'open' | 'half_open';

interface CircuitBreakerInfo {
  name: string;
  state: CircuitBreakerState;
  failure_count: number;
  success_count: number;
  last_failure_time: number | null;
  config: {
    failure_threshold: number;
    recovery_timeout: number;
    half_open_max_calls: number;
  };
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Get badge color based on circuit breaker state
 */
function getStateColor(state: CircuitBreakerState): 'green' | 'red' | 'yellow' {
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
function StateIcon({ state }: { state: CircuitBreakerState }) {
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
 * Format monotonic timestamp for display
 */
function formatTimestamp(timestamp: number | null): string {
  if (timestamp === null) return 'N/A';
  // Monotonic time - show as relative
  const now = performance.now() / 1000;
  const diff = now - timestamp;
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`;
  return `${Math.round(diff / 3600)}h ago`;
}

// ============================================================================
// Sub-Components
// ============================================================================

/**
 * Loading state component
 */
function LoadingState() {
  return (
    <div
      className="flex items-center justify-center py-12"
      data-testid="circuit-breaker-debug-loading"
    >
      <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
      <span className="ml-3 text-gray-400">Loading circuit breakers...</span>
    </div>
  );
}

/**
 * Error state component
 */
function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div
      className="rounded-lg border border-red-500/30 bg-red-500/10 p-4"
      data-testid="circuit-breaker-debug-error"
    >
      <div className="flex items-center gap-3">
        <AlertCircle className="h-5 w-5 text-red-400" />
        <div className="flex-1">
          <Text className="font-medium text-red-400">Failed to load circuit breakers</Text>
          <Text className="text-sm text-red-400/80">{message}</Text>
        </div>
        <button
          onClick={onRetry}
          className="rounded-md border border-red-500/30 px-3 py-1 text-sm text-red-400 hover:bg-red-500/10"
          aria-label="Retry"
        >
          Retry
        </button>
      </div>
    </div>
  );
}

/**
 * Empty state component
 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-gray-700 bg-gray-800/50 py-12">
      <Zap className="h-10 w-10 text-gray-500" />
      <Text className="mt-3 text-gray-400">No circuit breakers registered</Text>
      <Text className="text-sm text-gray-500">Circuit breakers will appear here when registered</Text>
    </div>
  );
}

/**
 * Circuit breaker row component
 */
function CircuitBreakerRow({
  breaker,
  onReset,
  isResetPending,
}: {
  breaker: CircuitBreakerInfo;
  onReset: (name: string) => void;
  isResetPending: boolean;
}) {
  const canReset = breaker.state !== 'closed';

  return (
    <div
      className={clsx(
        'rounded-lg border p-4',
        breaker.state === 'closed' && 'border-gray-700 bg-gray-800/50',
        breaker.state === 'open' && 'border-red-500/30 bg-red-500/10',
        breaker.state === 'half_open' && 'border-yellow-500/30 bg-yellow-500/10'
      )}
      data-testid={`circuit-breaker-row-${breaker.name}`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          {/* Name and Status */}
          <div className="mb-2 flex items-center gap-2">
            <StateIcon state={breaker.state} />
            <Text className="font-medium text-gray-200">{breaker.name}</Text>
            <Badge color={getStateColor(breaker.state)} size="xs">
              {breaker.state}
            </Badge>
          </div>

          {/* Stats Grid */}
          <div className="mb-2 grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
            <div>
              <Text className="text-gray-500">Failures</Text>
              <Text
                className={clsx(
                  'font-medium',
                  breaker.failure_count > 0 ? 'text-red-400' : 'text-gray-200'
                )}
              >
                {breaker.failure_count}
              </Text>
            </div>
            <div>
              <Text className="text-gray-500">Successes</Text>
              <Text className="font-medium text-gray-200">{breaker.success_count}</Text>
            </div>
            <div>
              <Text className="text-gray-500">Last Failure</Text>
              <Text className="font-medium text-gray-200">
                {formatTimestamp(breaker.last_failure_time)}
              </Text>
            </div>
            <div>
              <Text className="text-gray-500">Threshold</Text>
              <Text className="font-medium text-gray-200">{breaker.config.failure_threshold}</Text>
            </div>
          </div>

          {/* Configuration */}
          <div className="flex flex-wrap gap-3 text-xs text-gray-500">
            <span>Threshold: {breaker.config.failure_threshold}</span>
            <span>Timeout: {breaker.config.recovery_timeout}s</span>
            <span>Half-open calls: {breaker.config.half_open_max_calls}</span>
          </div>
        </div>

        {/* Reset Button */}
        {canReset && (
          <button
            onClick={() => onReset(breaker.name)}
            disabled={isResetPending}
            className={clsx(
              'ml-4 flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
              isResetPending
                ? 'cursor-not-allowed bg-gray-700 text-gray-400'
                : 'bg-gray-700 text-gray-200 hover:bg-gray-600'
            )}
            aria-label={`Reset ${breaker.name} circuit breaker`}
          >
            {isResetPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RotateCcw className="h-4 w-4" />
            )}
            Reset
          </button>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * CircuitBreakerDebugPanel - Debug view of all circuit breakers
 *
 * Usage:
 * ```tsx
 * <CircuitBreakerDebugPanel />
 * ```
 */
export default function CircuitBreakerDebugPanel({ className }: CircuitBreakerDebugPanelProps) {
  const { success, error: showError } = useToast();

  const {
    data,
    isLoading,
    isRefetching,
    error,
    refetch,
    resetBreaker,
    isResetPending,
  } = useCircuitBreakerDebugQuery();

  // Handle refresh
  const handleRefresh = useCallback(() => {
    void refetch();
  }, [refetch]);

  // Handle reset
  const handleReset = useCallback(
    async (name: string) => {
      try {
        await resetBreaker(name);
        success(`Circuit breaker "${name}" reset successfully`);
      } catch {
        showError(`Failed to reset circuit breaker "${name}"`);
      }
    },
    [resetBreaker, success, showError]
  );

  // Calculate summary stats
  const breakers = data?.circuit_breakers
    ? Object.values(data.circuit_breakers) as CircuitBreakerInfo[]
    : [];
  const healthyCount = breakers.filter((b) => b.state === 'closed').length;
  const totalCount = breakers.length;

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="circuit-breaker-debug-panel"
    >
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Zap className="h-5 w-5 text-[#76B900]" />
          Circuit Breakers (Debug)
        </Title>
        <div className="flex items-center gap-2">
          {/* Summary Badge */}
          {data && totalCount > 0 && (
            <Badge
              color={healthyCount === totalCount ? 'green' : 'red'}
              size="sm"
            >
              {healthyCount}/{totalCount} Healthy
            </Badge>
          )}

          {/* Refresh Button */}
          <button
            onClick={handleRefresh}
            disabled={isLoading || isRefetching}
            className="flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-white transition-colors hover:border-[#76B900] hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
            aria-label="Refresh"
          >
            <RefreshCw className={clsx('h-4 w-4', isRefetching && 'animate-spin')} />
            Refresh
          </button>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error.message} onRetry={handleRefresh} />
      ) : !data || totalCount === 0 ? (
        <EmptyState />
      ) : (
        <div className="space-y-3">
          {breakers.map((breaker) => (
            <CircuitBreakerRow
              key={breaker.name}
              breaker={breaker}
              onReset={(name) => void handleReset(name)}
              isResetPending={isResetPending}
            />
          ))}

          {/* Last Updated */}
          <div className="flex items-center gap-2 pt-2 text-xs text-gray-500">
            <Info className="h-3 w-3" />
            Last updated: {new Date(data.timestamp).toLocaleString()}
          </div>
        </div>
      )}
    </Card>
  );
}

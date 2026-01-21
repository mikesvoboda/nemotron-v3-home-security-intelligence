/**
 * MemorySnapshotPanel Component
 *
 * Memory analysis panel for the Developer Tools page.
 * Provides process memory stats, GC controls, and tracemalloc tracing.
 *
 * Features:
 * - Process RSS and VMS memory display
 * - Garbage collector statistics and manual GC trigger
 * - Tracemalloc tracing start/stop
 * - Top memory objects by type table
 * - Production warning callout
 *
 * @see NEM-3173 - Build Debug Tools admin panel
 */

import { Card, Title, Text, Callout, Badge, ProgressBar } from '@tremor/react';
import { clsx } from 'clsx';
import {
  HardDrive,
  RefreshCw,
  AlertTriangle,
  Loader2,
  Trash2,
  Play,
  Square,
  AlertCircle,
  Info,
} from 'lucide-react';
import { useCallback } from 'react';

import { useMemoryStatsQuery } from '../../hooks/useMemoryStatsQuery';
import { useToast } from '../../hooks/useToast';

// ============================================================================
// Types
// ============================================================================

export interface MemorySnapshotPanelProps {
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Format a number with commas for display
 */
function formatNumber(num: number): string {
  return num.toLocaleString('en-US');
}

// ============================================================================
// Sub-Components
// ============================================================================

/**
 * Loading state component
 */
function LoadingState() {
  return (
    <div className="flex items-center justify-center py-12" data-testid="memory-panel-loading">
      <Loader2 className="h-8 w-8 animate-spin text-[#76B900]" />
      <span className="ml-3 text-gray-400">Loading memory stats...</span>
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
      data-testid="memory-panel-error"
    >
      <div className="flex items-center gap-3">
        <AlertCircle className="h-5 w-5 text-red-400" />
        <div className="flex-1">
          <Text className="font-medium text-red-400">Failed to load memory stats</Text>
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
    <div
      className="flex flex-col items-center justify-center rounded-lg border border-gray-700 bg-gray-800/50 py-12"
      data-testid="memory-panel-empty"
    >
      <HardDrive className="h-10 w-10 text-gray-500" />
      <Text className="mt-3 text-gray-400">No memory data available</Text>
      <Text className="text-sm text-gray-500">Click refresh to load memory statistics</Text>
    </div>
  );
}

/**
 * Memory metric card component
 */
function MemoryMetricCard({
  label,
  value,
  icon,
  color = 'green',
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  color?: 'green' | 'blue' | 'yellow';
}) {
  const colorClasses = {
    green: 'border-[#76B900]/30 bg-[#76B900]/10',
    blue: 'border-blue-500/30 bg-blue-500/10',
    yellow: 'border-yellow-500/30 bg-yellow-500/10',
  };

  return (
    <div className={clsx('rounded-lg border p-4', colorClasses[color])}>
      <div className="flex items-center gap-2 text-gray-400">
        {icon}
        <span className="text-sm">{label}</span>
      </div>
      <div className="mt-2 text-2xl font-semibold text-white">{value}</div>
    </div>
  );
}

/**
 * GC statistics section
 */
function GCStatsSection({
  gcStats,
}: {
  gcStats: {
    collections: number[];
    collected: number;
    uncollectable: number;
    thresholds: number[];
  };
}) {
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
      <Text className="mb-3 font-medium text-gray-200">Garbage Collector</Text>
      <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
        <div>
          <Text className="text-gray-500">Collected</Text>
          <Text className="font-medium text-gray-200">{formatNumber(gcStats.collected)}</Text>
        </div>
        <div>
          <Text className="text-gray-500">Uncollectable</Text>
          <Text
            className={clsx(
              'font-medium',
              gcStats.uncollectable > 0 ? 'text-yellow-400' : 'text-gray-200'
            )}
          >
            {formatNumber(gcStats.uncollectable)}
          </Text>
        </div>
        <div>
          <Text className="text-gray-500">Gen 0 Collections</Text>
          <Text className="font-medium text-gray-200">
            {formatNumber(gcStats.collections[0] ?? 0)}
          </Text>
        </div>
        <div>
          <Text className="text-gray-500">Gen 2 Collections</Text>
          <Text className="font-medium text-gray-200">
            {formatNumber(gcStats.collections[2] ?? 0)}
          </Text>
        </div>
      </div>
    </div>
  );
}

/**
 * Tracemalloc status section
 */
function TracemallocSection({
  stats,
  onStart,
  onStop,
  isStartPending,
  isStopPending,
}: {
  stats: {
    enabled: boolean;
    current_bytes: number;
    peak_bytes: number;
    top_allocations: Array<{
      file: string;
      size_bytes: number;
      size_human: string;
      count: number;
    }>;
  };
  onStart: () => void;
  onStop: () => void;
  isStartPending: boolean;
  isStopPending: boolean;
}) {
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Text className="font-medium text-gray-200">Tracemalloc</Text>
          <Badge color={stats.enabled ? 'green' : 'gray'} size="xs">
            {stats.enabled ? 'Active' : 'Inactive'}
          </Badge>
        </div>
        {!stats.enabled ? (
          <button
            onClick={onStart}
            disabled={isStartPending}
            className={clsx(
              'flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
              isStartPending
                ? 'cursor-not-allowed bg-gray-700 text-gray-400'
                : 'bg-[#76B900] text-white hover:bg-[#8ACE00]'
            )}
            aria-label={isStartPending ? 'Starting tracing' : 'Start tracing'}
          >
            {isStartPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Start Tracing
          </button>
        ) : (
          <button
            onClick={onStop}
            disabled={isStopPending}
            className={clsx(
              'flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
              isStopPending
                ? 'cursor-not-allowed bg-gray-700 text-gray-400'
                : 'bg-red-700 text-white hover:bg-red-800'
            )}
            aria-label={isStopPending ? 'Stopping tracing' : 'Stop tracing'}
          >
            {isStopPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Square className="h-4 w-4" />
            )}
            Stop Tracing
          </button>
        )}
      </div>

      {stats.enabled && (
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <Text className="text-gray-500">Current</Text>
            <Text className="font-medium text-gray-200">
              {(stats.current_bytes / 1024 / 1024).toFixed(1)} MB
            </Text>
          </div>
          <div>
            <Text className="text-gray-500">Peak</Text>
            <Text className="font-medium text-gray-200">
              {(stats.peak_bytes / 1024 / 1024).toFixed(1)} MB
            </Text>
          </div>
        </div>
      )}

      {!stats.enabled && (
        <Text className="text-sm text-gray-500">
          Enable tracemalloc to track memory allocations with file/line info
        </Text>
      )}
    </div>
  );
}

/**
 * Top objects table component
 */
function TopObjectsTable({
  objects,
  totalRss,
}: {
  objects: Array<{
    type_name: string;
    count: number;
    size_bytes: number;
    size_human: string;
  }>;
  totalRss: number;
}) {
  if (objects.length === 0) {
    return (
      <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-6 text-center">
        <Text className="text-gray-400">No object statistics available</Text>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800/50 p-4">
      <Text className="mb-3 font-medium text-gray-200">Top Memory Objects by Type</Text>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" role="table">
          <thead>
            <tr className="border-b border-gray-700 text-left text-gray-400">
              <th className="pb-2 pr-4">Type</th>
              <th className="pb-2 pr-4 text-right">Count</th>
              <th className="pb-2 pr-4 text-right">Size</th>
              <th className="pb-2 pr-4">% of RSS</th>
            </tr>
          </thead>
          <tbody>
            {objects.map((obj, index) => {
              const percentage = totalRss > 0 ? (obj.size_bytes / totalRss) * 100 : 0;
              return (
                <tr key={`${obj.type_name}-${index}`} className="border-b border-gray-800">
                  <td className="py-2 pr-4 font-mono text-gray-200">{obj.type_name}</td>
                  <td className="py-2 pr-4 text-right text-gray-300">
                    {formatNumber(obj.count)}
                  </td>
                  <td className="py-2 pr-4 text-right text-gray-300">{obj.size_human}</td>
                  <td className="py-2 pr-4">
                    <div className="flex items-center gap-2">
                      <div className="w-24">
                        <ProgressBar
                          value={Math.min(percentage, 100)}
                          color="green"
                          className="h-2"
                        />
                      </div>
                      <span className="text-xs text-gray-400">{percentage.toFixed(1)}%</span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * MemorySnapshotPanel - Memory analysis and debugging controls
 *
 * Usage:
 * ```tsx
 * <MemorySnapshotPanel />
 * ```
 */
export default function MemorySnapshotPanel({ className }: MemorySnapshotPanelProps) {
  const { success, error: showError } = useToast();

  const {
    data,
    isLoading,
    isRefetching,
    error,
    refetch,
    triggerGc,
    startTracemalloc,
    stopTracemalloc,
    isGcPending,
    isTracemallocStartPending,
    isTracemallocStopPending,
  } = useMemoryStatsQuery();

  // Handle refresh
  const handleRefresh = useCallback(() => {
    void refetch();
  }, [refetch]);

  // Handle GC trigger
  const handleTriggerGc = useCallback(async () => {
    try {
      const result = await triggerGc();
      success(`GC completed: ${result.collected.total} objects collected, ${result.memory.freed_human} freed`);
    } catch {
      showError('Failed to trigger garbage collection');
    }
  }, [triggerGc, success, showError]);

  // Handle start tracemalloc
  const handleStartTracemalloc = useCallback(async () => {
    try {
      await startTracemalloc();
      success('Tracemalloc started');
    } catch {
      showError('Failed to start tracemalloc');
    }
  }, [startTracemalloc, success, showError]);

  // Handle stop tracemalloc
  const handleStopTracemalloc = useCallback(async () => {
    try {
      const result = await stopTracemalloc();
      if (result.final_stats) {
        success(`Tracemalloc stopped. Peak: ${result.final_stats.peak_human}`);
      } else {
        success('Tracemalloc stopped');
      }
    } catch {
      showError('Failed to stop tracemalloc');
    }
  }, [stopTracemalloc, success, showError]);

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="memory-panel"
    >
      <div className="mb-4 flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <HardDrive className="h-5 w-5 text-[#76B900]" />
          Memory Snapshot
        </Title>
        <div className="flex items-center gap-2">
          {/* Force GC Button */}
          <button
            onClick={() => void handleTriggerGc()}
            disabled={isGcPending || isLoading}
            className={clsx(
              'flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
              isGcPending
                ? 'cursor-not-allowed bg-gray-700 text-gray-400'
                : 'border border-yellow-500/30 bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20'
            )}
            aria-label={isGcPending ? 'Running GC' : 'Force GC'}
          >
            {isGcPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
            {isGcPending ? 'Running GC...' : 'Force GC'}
          </button>

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

      {/* Production Warning */}
      <Callout
        title="Performance Impact"
        icon={AlertTriangle}
        color="yellow"
        className="mb-4"
      >
        <span className="text-sm">
          Force GC may impact performance temporarily. Tracemalloc adds memory tracking overhead.
          Use in development or during debugging only.
        </span>
      </Callout>

      {/* Content */}
      {isLoading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message={error.message} onRetry={handleRefresh} />
      ) : !data ? (
        <EmptyState />
      ) : (
        <div className="space-y-4">
          {/* Memory Metrics */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <MemoryMetricCard
              label="RSS Memory"
              value={data.process_rss_human}
              icon={<HardDrive className="h-4 w-4" />}
              color="green"
            />
            <MemoryMetricCard
              label="Virtual Memory"
              value={data.process_vms_human}
              icon={<HardDrive className="h-4 w-4" />}
              color="blue"
            />
          </div>

          {/* GC Stats */}
          <GCStatsSection gcStats={data.gc_stats} />

          {/* Tracemalloc */}
          <TracemallocSection
            stats={data.tracemalloc_stats}
            onStart={() => void handleStartTracemalloc()}
            onStop={() => void handleStopTracemalloc()}
            isStartPending={isTracemallocStartPending}
            isStopPending={isTracemallocStopPending}
          />

          {/* Top Objects Table */}
          <TopObjectsTable
            objects={data.top_objects}
            totalRss={data.process_rss_bytes}
          />

          {/* Last Updated */}
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <Info className="h-3 w-3" />
            Last updated: {new Date(data.timestamp).toLocaleString()}
          </div>
        </div>
      )}
    </Card>
  );
}

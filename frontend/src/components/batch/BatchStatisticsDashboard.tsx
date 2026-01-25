/**
 * BatchStatisticsDashboard - Dashboard for batch processing statistics
 *
 * Displays:
 * - Summary metrics (active batches, total closed, avg duration)
 * - Active batch timeline
 * - Closure reason distribution chart
 * - Per-camera breakdown table
 *
 * Data sources:
 * - REST API /api/system/pipeline for active batch status
 * - WebSocket detection.batch events for real-time updates
 *
 * @module components/batch/BatchStatisticsDashboard
 */

import { Card, Title, Badge, Text } from '@tremor/react';
import { clsx } from 'clsx';
import {
  Layers,
  Activity,
  Clock,
  CheckCircle,
  RefreshCw,
  Wifi,
  WifiOff,
  AlertTriangle,
} from 'lucide-react';

import BatchClosureReasonChart from './BatchClosureReasonChart';
import BatchPerCameraTable from './BatchPerCameraTable';
import BatchTimelineChart from './BatchTimelineChart';
import { useBatchStatistics } from '../../hooks/useBatchStatistics';

// ============================================================================
// Types
// ============================================================================

export interface BatchStatisticsDashboardProps {
  /** Additional CSS classes */
  className?: string;
  /** Test ID for the component */
  'data-testid'?: string;
}

// ============================================================================
// Component
// ============================================================================

/**
 * BatchStatisticsDashboard - Main dashboard for batch processing statistics
 */
export default function BatchStatisticsDashboard({
  className,
  'data-testid': testId = 'batch-statistics-dashboard',
}: BatchStatisticsDashboardProps) {
  const {
    isLoading,
    error,
    activeBatchCount,
    activeBatches,
    totalClosedCount,
    batchWindowSeconds,
    idleTimeoutSeconds,
    averageDurationSeconds,
    closureReasonStats,
    closureReasonPercentages,
    perCameraStats,
    isWebSocketConnected,
    refetch,
  } = useBatchStatistics();

  // Check if we have any data
  const hasData =
    activeBatchCount > 0 ||
    totalClosedCount > 0 ||
    Object.keys(perCameraStats).length > 0;

  // Loading state
  if (isLoading) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="batch-statistics-loading"
      >
        <div className="animate-pulse space-y-4">
          <div className="h-6 w-48 rounded bg-gray-700" />
          <div className="grid grid-cols-4 gap-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-20 rounded bg-gray-700" />
            ))}
          </div>
          <div className="h-48 rounded bg-gray-700" />
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card
        className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
        data-testid="batch-statistics-error"
      >
        <div className="flex flex-col items-center gap-4 py-8">
          <AlertTriangle className="h-12 w-12 text-red-500" />
          <Text className="text-center text-red-400">{error}</Text>
          <button
            onClick={() => void refetch()}
            className="flex items-center gap-2 rounded-md bg-gray-700 px-4 py-2 text-sm text-white transition-colors hover:bg-gray-600"
            aria-label="Retry loading batch statistics"
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        </div>
      </Card>
    );
  }

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid={testId}
    >
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Layers className="h-6 w-6 text-[#76B900]" />
          <Title className="text-white">Batch Processing Statistics</Title>
        </div>
        <div className="flex items-center gap-3">
          {/* WebSocket Status Indicator */}
          <Badge
            data-testid="websocket-status"
            className={clsx(
              'flex items-center gap-1',
              isWebSocketConnected ? 'text-green-400' : 'text-red-400'
            )}
            color={isWebSocketConnected ? 'green' : 'red'}
          >
            {isWebSocketConnected ? (
              <>
                <Wifi className="h-3 w-3" />
                Live
              </>
            ) : (
              <>
                <WifiOff className="h-3 w-3" />
                Disconnected
              </>
            )}
          </Badge>
        </div>
      </div>

      {/* Summary Metrics */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-5">
        {/* Active Batches */}
        <div
          className="rounded-lg bg-gray-800/50 p-4"
          aria-label="Active batches"
        >
          <div className="flex items-center gap-2 text-gray-400">
            <Activity className="h-4 w-4" />
            <Text className="text-sm">Active Batches</Text>
          </div>
          <span
            className="mt-2 block text-2xl font-bold text-white"
            data-testid="active-batch-count"
          >
            {activeBatchCount}
          </span>
        </div>

        {/* Total Closed */}
        <div
          className="rounded-lg bg-gray-800/50 p-4"
          aria-label="Total closed batches"
        >
          <div className="flex items-center gap-2 text-gray-400">
            <CheckCircle className="h-4 w-4" />
            <Text className="text-sm">Total Closed</Text>
          </div>
          <span
            className="mt-2 block text-2xl font-bold text-white"
            data-testid="total-closed-count"
          >
            {totalClosedCount}
          </span>
        </div>

        {/* Average Duration */}
        <div className="rounded-lg bg-gray-800/50 p-4">
          <div className="flex items-center gap-2 text-gray-400">
            <Clock className="h-4 w-4" />
            <Text className="text-sm">Avg Duration</Text>
          </div>
          <span
            className="mt-2 block text-2xl font-bold text-white"
            data-testid="average-duration"
          >
            {Math.round(averageDurationSeconds)}s
          </span>
        </div>

        {/* Batch Window */}
        <div className="rounded-lg bg-gray-800/50 p-4">
          <div className="flex items-center gap-2 text-gray-400">
            <Clock className="h-4 w-4" />
            <Text className="text-sm">Batch Window</Text>
          </div>
          <span
            className="mt-2 block text-2xl font-bold text-gray-300"
            data-testid="batch-window"
          >
            {batchWindowSeconds}s
          </span>
        </div>

        {/* Idle Timeout */}
        <div className="rounded-lg bg-gray-800/50 p-4">
          <div className="flex items-center gap-2 text-gray-400">
            <Clock className="h-4 w-4" />
            <Text className="text-sm">Idle Timeout</Text>
          </div>
          <span
            className="mt-2 block text-2xl font-bold text-gray-300"
            data-testid="idle-timeout"
          >
            {idleTimeoutSeconds}s
          </span>
        </div>
      </div>

      {/* Empty State */}
      {!hasData && (
        <div
          className="flex flex-col items-center gap-4 rounded-lg border border-gray-700 bg-gray-800/30 py-12"
          data-testid="batch-statistics-empty"
        >
          <Layers className="h-12 w-12 text-gray-600" />
          <Text className="text-center text-gray-400">
            No batch data available. Batch events will appear here once the AI
            pipeline begins processing detections.
          </Text>
        </div>
      )}

      {/* Charts and Tables */}
      {hasData && (
        <div className="space-y-6">
          {/* Active Batches Timeline */}
          <BatchTimelineChart
            activeBatches={activeBatches}
            batchWindowSeconds={batchWindowSeconds}
          />

          {/* Two-column layout for charts */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Closure Reason Chart */}
            <BatchClosureReasonChart
              closureReasonStats={closureReasonStats}
              closureReasonPercentages={closureReasonPercentages}
              totalBatches={totalClosedCount}
            />

            {/* Per-Camera Table */}
            <BatchPerCameraTable perCameraStats={perCameraStats} />
          </div>
        </div>
      )}
    </Card>
  );
}

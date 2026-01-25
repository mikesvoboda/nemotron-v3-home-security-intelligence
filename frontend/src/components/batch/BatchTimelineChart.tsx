/**
 * BatchTimelineChart - Timeline visualization for active batches
 *
 * Displays active batches as horizontal progress bars showing:
 * - Batch ID and camera
 * - Age as percentage of batch window
 * - Detection count
 * - Last activity indicator
 *
 * @module components/batch/BatchTimelineChart
 */

import { Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import { Camera, Clock, Hash } from 'lucide-react';

import type { BatchInfoResponse } from '../../types/generated';

// ============================================================================
// Types
// ============================================================================

export interface BatchTimelineChartProps {
  /** Active batches to display */
  activeBatches: BatchInfoResponse[];
  /** Batch window timeout in seconds */
  batchWindowSeconds: number;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Component
// ============================================================================

/**
 * BatchTimelineChart - Visual timeline of active batches
 */
export default function BatchTimelineChart({
  activeBatches,
  batchWindowSeconds,
  className,
}: BatchTimelineChartProps) {
  // Empty state
  if (activeBatches.length === 0) {
    return (
      <div
        className={clsx('rounded-lg border border-gray-700 bg-gray-800/30 p-4', className)}
        data-testid="batch-timeline-chart"
      >
        <Text className="text-center text-gray-400">
          No active batches. New batches will appear here when detections arrive.
        </Text>
      </div>
    );
  }

  return (
    <div
      className={clsx('rounded-lg border border-gray-700 bg-gray-800/30 p-4', className)}
      data-testid="batch-timeline-chart"
    >
      <Text className="mb-4 text-sm font-medium text-gray-300">Active Batches</Text>

      <div className="space-y-3">
        {activeBatches.map((batch) => {
          // Calculate progress percentage
          const progressPercent = Math.min(
            100,
            (batch.age_seconds / batchWindowSeconds) * 100
          );

          // Determine color based on age
          const isNearTimeout = progressPercent > 80;
          const isMidway = progressPercent > 50;

          return (
            <div
              key={batch.batch_id}
              className="rounded-md border border-gray-700 bg-gray-800/50 p-3"
            >
              {/* Header row */}
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Text className="font-mono text-sm text-white">
                    {batch.batch_id}
                  </Text>
                  <Badge
                    color="blue"
                    size="sm"
                    className="flex items-center gap-1"
                  >
                    <Camera className="h-3 w-3" />
                    {batch.camera_id}
                  </Badge>
                </div>
                <div className="flex items-center gap-3">
                  <Badge
                    color="violet"
                    size="sm"
                    className="flex items-center gap-1"
                  >
                    <Hash className="h-3 w-3" />
                    {batch.detection_count}
                  </Badge>
                  <Text className="text-xs text-gray-500">
                    <Clock className="mr-1 inline h-3 w-3" />
                    {Math.round(batch.last_activity_seconds)}s ago
                  </Text>
                </div>
              </div>

              {/* Progress bar */}
              <div className="relative h-2 overflow-hidden rounded-full bg-gray-700">
                <div
                  className={clsx(
                    'h-full transition-all duration-500',
                    isNearTimeout
                      ? 'bg-red-500'
                      : isMidway
                        ? 'bg-yellow-500'
                        : 'bg-[#76B900]'
                  )}
                  style={{ width: `${progressPercent}%` }}
                />
              </div>

              {/* Age info */}
              <div className="mt-1 flex justify-between">
                <Text className="text-xs text-gray-500">
                  Age: {Math.round(batch.age_seconds)}s
                </Text>
                <Text className="text-xs text-gray-500">
                  Window: {batchWindowSeconds}s
                </Text>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

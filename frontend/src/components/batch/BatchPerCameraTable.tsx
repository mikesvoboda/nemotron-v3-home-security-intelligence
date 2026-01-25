/**
 * BatchPerCameraTable - Table showing per-camera batch statistics
 *
 * Displays for each camera:
 * - Camera ID
 * - Active batch count
 * - Completed batch count
 * - Total detections
 *
 * @module components/batch/BatchPerCameraTable
 */

import { Text, Badge } from '@tremor/react';
import { clsx } from 'clsx';
import { Camera } from 'lucide-react';

import type { PerCameraStats } from '../../hooks/useBatchStatistics';

// ============================================================================
// Types
// ============================================================================

export interface BatchPerCameraTableProps {
  /** Per-camera statistics */
  perCameraStats: PerCameraStats;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Component
// ============================================================================

/**
 * BatchPerCameraTable - Table of per-camera batch statistics
 */
export default function BatchPerCameraTable({
  perCameraStats,
  className,
}: BatchPerCameraTableProps) {
  const cameraIds = Object.keys(perCameraStats);

  // Empty state
  if (cameraIds.length === 0) {
    return (
      <div
        className={clsx('rounded-lg border border-gray-700 bg-gray-800/30 p-4', className)}
        data-testid="per-camera-table"
      >
        <Text className="mb-4 text-sm font-medium text-gray-300">Per-Camera Breakdown</Text>
        <Text className="text-center text-gray-400">
          No camera data available. Statistics will appear as batches are processed.
        </Text>
      </div>
    );
  }

  return (
    <div
      className={clsx('rounded-lg border border-gray-700 bg-gray-800/30 p-4', className)}
      data-testid="per-camera-table"
    >
      <Text className="mb-4 text-sm font-medium text-gray-300">Per-Camera Breakdown</Text>

      <div className="overflow-x-auto">
        <table className="w-full" role="table">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="pb-2 text-left text-xs font-medium text-gray-400">
                Camera
              </th>
              <th className="pb-2 text-center text-xs font-medium text-gray-400">
                Active
              </th>
              <th className="pb-2 text-center text-xs font-medium text-gray-400">
                Completed
              </th>
              <th className="pb-2 text-right text-xs font-medium text-gray-400">
                Detections
              </th>
            </tr>
          </thead>
          <tbody>
            {cameraIds.map((cameraId) => {
              const stats = perCameraStats[cameraId];
              return (
                <tr
                  key={cameraId}
                  className="border-b border-gray-800 last:border-0"
                >
                  <td className="py-2">
                    <div className="flex items-center gap-2">
                      <Camera className="h-4 w-4 text-gray-500" />
                      <Text className="text-sm text-white">{cameraId}</Text>
                    </div>
                  </td>
                  <td className="py-2 text-center">
                    {stats.activeBatchCount > 0 ? (
                      <Badge color="green" size="sm">
                        {stats.activeBatchCount}
                      </Badge>
                    ) : (
                      <Text className="text-sm text-gray-500">0</Text>
                    )}
                  </td>
                  <td className="py-2 text-center">
                    <Text className="text-sm text-gray-300">
                      {stats.completedBatchCount}
                    </Text>
                  </td>
                  <td className="py-2 text-right">
                    <Text className="text-sm font-medium text-white">
                      {stats.totalDetections}
                    </Text>
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

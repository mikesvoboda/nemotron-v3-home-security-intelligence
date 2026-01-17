/**
 * CameraUptimeCard - Display camera uptime statistics
 *
 * Shows uptime percentage for each camera using a BarList visualization.
 * Colors indicate health status based on uptime percentage:
 * - Green (emerald): >= 95% - Healthy
 * - Yellow: 80-94% - Degraded
 * - Orange: 60-79% - Warning
 * - Red: < 60% - Critical
 */

import { Card, Title, Text } from '@tremor/react';
import { AlertCircle, Loader2 } from 'lucide-react';
import { useMemo } from 'react';

import {
  useCameraUptimeQuery,
  type CameraUptimeDateRange,
} from '../../hooks/useCameraUptimeQuery';

// ============================================================================
// Types
// ============================================================================

interface CameraUptimeCardProps {
  /** Date range for uptime calculation */
  dateRange: CameraUptimeDateRange;
}

/**
 * Health status based on uptime percentage.
 */
type UptimeStatus = 'healthy' | 'degraded' | 'warning' | 'critical';

// ============================================================================
// Constants
// ============================================================================

/**
 * Color mapping for Tremor BarList based on uptime status.
 */
const STATUS_COLORS: Record<UptimeStatus, string> = {
  healthy: 'emerald',
  degraded: 'yellow',
  warning: 'orange',
  critical: 'red',
};

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Determine the health status based on uptime percentage.
 *
 * @param percentage - Uptime percentage (0-100)
 * @returns UptimeStatus indicating health level
 */
function getUptimeStatus(percentage: number): UptimeStatus {
  if (percentage >= 95) return 'healthy';
  if (percentage >= 80) return 'degraded';
  if (percentage >= 60) return 'warning';
  return 'critical';
}

/**
 * Format a date string for display (e.g., "Jan 10").
 *
 * @param dateStr - ISO date string (YYYY-MM-DD)
 * @returns Formatted date string
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00');
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ============================================================================
// Component
// ============================================================================

/**
 * CameraUptimeCard displays camera uptime statistics in a BarList visualization.
 *
 * Fetches camera uptime data for the specified date range and displays
 * each camera's uptime percentage with color-coded health status.
 *
 * @param props - Component props
 * @returns React element
 */
export default function CameraUptimeCard({ dateRange }: CameraUptimeCardProps) {
  const { cameras, isLoading, error } = useCameraUptimeQuery(dateRange);

  // Sort cameras by uptime percentage (highest first) and prepare BarList data
  const barListData = useMemo(() => {
    return [...cameras]
      .sort((a, b) => b.uptime_percentage - a.uptime_percentage)
      .map((cam) => ({
        name: cam.camera_name,
        value: cam.uptime_percentage,
        color: STATUS_COLORS[getUptimeStatus(cam.uptime_percentage)],
        // Store original data for test assertions
        cameraId: cam.camera_id,
        status: getUptimeStatus(cam.uptime_percentage),
      }));
  }, [cameras]);

  // Format date range for display
  const dateRangeLabel = `${formatDate(dateRange.startDate)} - ${formatDate(dateRange.endDate)}`;

  // Loading state
  if (isLoading) {
    return (
      <Card data-testid="camera-uptime-loading">
        <Title>Camera Uptime</Title>
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card data-testid="camera-uptime-error">
        <Title>Camera Uptime</Title>
        <div className="flex h-48 flex-col items-center justify-center text-red-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>Failed to load camera uptime data</Text>
        </div>
      </Card>
    );
  }

  // Empty state
  if (cameras.length === 0) {
    return (
      <Card data-testid="camera-uptime-empty">
        <Title>Camera Uptime</Title>
        <div className="flex h-48 flex-col items-center justify-center text-gray-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>No cameras available</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card data-testid="camera-uptime-card">
      <div className="mb-4 flex items-center justify-between">
        <Title>Camera Uptime</Title>
        <Text className="text-gray-400">{dateRangeLabel}</Text>
      </div>

      {/* Custom BarList with data attributes for testing */}
      <div className="space-y-3">
        {barListData.map((item) => {
          const percentage = item.value;
          const status = item.status;
          const color = STATUS_COLORS[status];

          return (
            <div
              key={item.cameraId}
              data-testid={`camera-uptime-item-${item.cameraId}`}
              data-uptime-status={status}
              className="group"
            >
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="text-gray-300">{item.name}</span>
                <span className="font-medium text-white">{percentage.toFixed(1)}%</span>
              </div>
              <div className="h-6 overflow-hidden rounded bg-gray-800">
                <div
                  className={`h-full rounded transition-all duration-300 group-hover:brightness-110 bg-${color}-500`}
                  style={{
                    width: `${percentage}%`,
                    backgroundColor:
                      color === 'emerald'
                        ? '#10B981'
                        : color === 'yellow'
                          ? '#F59E0B'
                          : color === 'orange'
                            ? '#F97316'
                            : '#EF4444',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-4 border-t border-gray-800 pt-4 text-xs text-gray-400">
        <div className="flex items-center gap-1.5">
          <div className="h-2.5 w-2.5 rounded-sm bg-emerald-500" />
          <span>Healthy (95%+)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2.5 w-2.5 rounded-sm bg-yellow-500" />
          <span>Degraded (80-94%)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2.5 w-2.5 rounded-sm bg-orange-500" />
          <span>Warning (60-79%)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2.5 w-2.5 rounded-sm bg-red-500" />
          <span>Critical (&lt;60%)</span>
        </div>
      </div>
    </Card>
  );
}

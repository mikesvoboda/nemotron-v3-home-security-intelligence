/**
 * CameraUptimeCard - Display camera uptime statistics
 *
 * Shows uptime percentage for each camera using a BarList visualization.
 * Colors indicate health status based on uptime percentage:
 * - Green (emerald): >= 95% - Healthy
 * - Yellow: 80-94% - Degraded
 * - Orange: 60-79% - Warning
 * - Red: < 60% - Critical
 *
 * Also displays trend indicators comparing to previous period.
 */

import { Card, Title, Text } from '@tremor/react';
import { AlertCircle, Loader2, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { useMemo } from 'react';

import { useCameraUptimeQuery, type CameraUptimeDateRange } from '../../hooks/useCameraUptimeQuery';

// ============================================================================
// Types
// ============================================================================

interface CameraUptimeCardProps {
  /** Date range for uptime calculation */
  dateRange: CameraUptimeDateRange;
  /** Whether to show trend indicators comparing to previous period */
  showTrend?: boolean;
}

/**
 * Trend direction for uptime comparison.
 */
type TrendDirection = 'up' | 'down' | 'stable';

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
 * Calculate trend direction and change percentage.
 *
 * @param current - Current uptime percentage
 * @param previous - Previous period uptime percentage (if available)
 * @returns Trend direction and change value
 */
function calculateTrend(
  current: number,
  previous: number | undefined
): { direction: TrendDirection; change: number } {
  if (previous === undefined) {
    return { direction: 'stable', change: 0 };
  }

  const change = current - previous;
  const threshold = 0.5; // Consider stable if change is within 0.5%

  if (Math.abs(change) < threshold) {
    return { direction: 'stable', change: 0 };
  }

  return {
    direction: change > 0 ? 'up' : 'down',
    change: Math.abs(change),
  };
}

/**
 * Calculate previous period date range based on current range.
 *
 * @param dateRange - Current date range
 * @returns Previous period date range with same duration
 */
function getPreviousPeriodRange(dateRange: CameraUptimeDateRange): CameraUptimeDateRange {
  const startDate = new Date(dateRange.startDate + 'T00:00:00');
  const endDate = new Date(dateRange.endDate + 'T00:00:00');

  // Calculate duration in days
  const durationMs = endDate.getTime() - startDate.getTime();
  const durationDays = Math.ceil(durationMs / (1000 * 60 * 60 * 24)) + 1;

  // Calculate previous period
  const prevEndDate = new Date(startDate);
  prevEndDate.setDate(prevEndDate.getDate() - 1);

  const prevStartDate = new Date(prevEndDate);
  prevStartDate.setDate(prevStartDate.getDate() - durationDays + 1);

  return {
    startDate: prevStartDate.toISOString().split('T')[0],
    endDate: prevEndDate.toISOString().split('T')[0],
  };
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
export default function CameraUptimeCard({ dateRange, showTrend = true }: CameraUptimeCardProps) {
  const { cameras, isLoading, error } = useCameraUptimeQuery(dateRange);

  // Calculate previous period for trend comparison
  const previousPeriodRange = useMemo(() => getPreviousPeriodRange(dateRange), [dateRange]);

  // Fetch previous period data for trend indicators
  const { cameras: previousCameras } = useCameraUptimeQuery(previousPeriodRange, {
    enabled: showTrend,
  });

  // Build a lookup map for previous period uptime by camera_id
  const previousUptimeMap = useMemo(() => {
    const map = new Map<string, number>();
    previousCameras.forEach((cam) => {
      map.set(cam.camera_id, cam.uptime_percentage);
    });
    return map;
  }, [previousCameras]);

  // Sort cameras by uptime percentage (highest first) and prepare BarList data
  const barListData = useMemo(() => {
    return [...cameras]
      .sort((a, b) => b.uptime_percentage - a.uptime_percentage)
      .map((cam) => {
        const previousUptime = previousUptimeMap.get(cam.camera_id);
        const trend = calculateTrend(cam.uptime_percentage, previousUptime);

        return {
          name: cam.camera_name,
          value: cam.uptime_percentage,
          color: STATUS_COLORS[getUptimeStatus(cam.uptime_percentage)],
          // Store original data for test assertions
          cameraId: cam.camera_id,
          status: getUptimeStatus(cam.uptime_percentage),
          // Trend data
          trend,
          previousUptime,
        };
      });
  }, [cameras, previousUptimeMap]);

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
              data-trend-direction={item.trend.direction}
              className="group"
            >
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="text-gray-300">{item.name}</span>
                <div className="flex items-center gap-2">
                  {/* Trend indicator */}
                  {showTrend && item.trend.direction !== 'stable' && (
                    <span
                      className={`flex items-center gap-0.5 text-xs ${
                        item.trend.direction === 'up' ? 'text-green-400' : 'text-red-400'
                      }`}
                      data-testid={`trend-indicator-${item.cameraId}`}
                      title={`${item.trend.direction === 'up' ? '+' : '-'}${item.trend.change.toFixed(1)}% vs previous period`}
                    >
                      {item.trend.direction === 'up' ? (
                        <TrendingUp className="h-3.5 w-3.5" />
                      ) : (
                        <TrendingDown className="h-3.5 w-3.5" />
                      )}
                      <span>{item.trend.change.toFixed(1)}%</span>
                    </span>
                  )}
                  {showTrend && item.trend.direction === 'stable' && item.previousUptime !== undefined && (
                    <span
                      className="flex items-center gap-0.5 text-xs text-gray-500"
                      data-testid={`trend-indicator-${item.cameraId}`}
                      title="No change vs previous period"
                    >
                      <Minus className="h-3.5 w-3.5" />
                    </span>
                  )}
                  <span className="font-medium text-white">{percentage.toFixed(1)}%</span>
                </div>
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

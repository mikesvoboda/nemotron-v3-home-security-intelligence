/**
 * CameraAnalyticsDetail - Per-camera analytics view
 *
 * Displays detection statistics for a selected camera or all cameras.
 * Shows:
 * - Total detection count
 * - Average confidence score
 * - Class distribution with bar visualization
 *
 * Features:
 * - Color-coded bars for class distribution
 * - Loading skeleton state
 * - Error state with retry hint
 * - Empty state when no detections
 */

import { Card, Title, Text } from '@tremor/react';
import { AlertCircle, BarChart3, Loader2, Target } from 'lucide-react';
import { useMemo } from 'react';

/**
 * Props for CameraAnalyticsDetail component
 */
export interface CameraAnalyticsDetailProps {
  /** Total number of detections */
  totalDetections: number;
  /** Detection counts by object class */
  detectionsByClass: Record<string, number>;
  /** Average confidence score (0-1), null if unavailable */
  averageConfidence: number | null;
  /** Whether data is loading */
  isLoading: boolean;
  /** Error object if fetch failed */
  error: Error | null;
  /** Camera name for title, undefined for "All Cameras" */
  cameraName?: string;
}

/**
 * Color palette for class distribution bars
 */
const CLASS_COLORS = [
  '#76B900', // NVIDIA green
  '#3B82F6', // Blue
  '#F59E0B', // Amber
  '#EF4444', // Red
  '#8B5CF6', // Purple
  '#06B6D4', // Cyan
  '#EC4899', // Pink
  '#14B8A6', // Teal
];

/**
 * Get a color for a class based on its index
 */
function getClassColor(index: number): string {
  return CLASS_COLORS[index % CLASS_COLORS.length];
}

/**
 * CameraAnalyticsDetail - Display detection statistics for a camera
 *
 * @param props - Component props
 * @returns React element
 *
 * @example
 * ```tsx
 * <CameraAnalyticsDetail
 *   totalDetections={1250}
 *   detectionsByClass={{ person: 500, car: 350 }}
 *   averageConfidence={0.87}
 *   isLoading={false}
 *   error={null}
 *   cameraName="Front Door"
 * />
 * ```
 */
export default function CameraAnalyticsDetail({
  totalDetections,
  detectionsByClass,
  averageConfidence,
  isLoading,
  error,
  cameraName,
}: CameraAnalyticsDetailProps) {
  // Sort classes by count (descending)
  const sortedClasses = useMemo(() => {
    return Object.entries(detectionsByClass)
      .sort(([, a], [, b]) => b - a)
      .map(([className, count]) => ({
        className,
        count,
        percentage: totalDetections > 0 ? (count / totalDetections) * 100 : 0,
      }));
  }, [detectionsByClass, totalDetections]);

  // Format confidence as percentage
  const confidenceDisplay = useMemo(() => {
    if (averageConfidence === null) return 'N/A';
    return `${Math.round(averageConfidence * 100)}%`;
  }, [averageConfidence]);

  // Title based on camera selection
  const title = cameraName ? `${cameraName} Analytics` : 'Detection Analytics';

  // Loading state
  if (isLoading) {
    return (
      <Card data-testid="camera-analytics-loading">
        <Title className="mb-4">{title}</Title>
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card data-testid="camera-analytics-error">
        <Title className="mb-4">{title}</Title>
        <div className="flex h-48 flex-col items-center justify-center text-red-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text className="text-red-400">Failed to load analytics data</Text>
          <Text className="mt-1 text-sm text-gray-500">
            Please try refreshing the page
          </Text>
        </div>
      </Card>
    );
  }

  // Empty state
  if (totalDetections === 0) {
    return (
      <Card data-testid="camera-analytics-empty">
        <Title className="mb-4">{title}</Title>
        <div className="flex h-48 flex-col items-center justify-center text-gray-400">
          <BarChart3 className="mb-2 h-8 w-8" />
          <Text className="text-gray-400">No detections found</Text>
          <Text className="mt-1 text-sm text-gray-500">
            {cameraName
              ? `No detections recorded for ${cameraName}`
              : 'No detections have been recorded yet'}
          </Text>
        </div>
      </Card>
    );
  }

  return (
    <Card data-testid="camera-analytics-detail">
      <Title className="mb-6">{title}</Title>

      {/* Stats cards row */}
      <div className="mb-6 grid grid-cols-2 gap-4">
        {/* Total Detections */}
        <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4">
          <div className="flex items-center gap-2 text-gray-400">
            <BarChart3 className="h-4 w-4" />
            <Text className="text-sm">Total Detections</Text>
          </div>
          <p className="mt-2 text-3xl font-bold text-white">
            {totalDetections.toLocaleString()}
          </p>
        </div>

        {/* Average Confidence */}
        <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4">
          <div className="flex items-center gap-2 text-gray-400">
            <Target className="h-4 w-4" />
            <Text className="text-sm">Average Confidence</Text>
          </div>
          <p className="mt-2 text-3xl font-bold text-white">{confidenceDisplay}</p>
        </div>
      </div>

      {/* Class Distribution */}
      <div>
        <Text className="mb-3 text-sm font-medium text-gray-400">
          Detection by Class
        </Text>
        <div className="space-y-3">
          {sortedClasses.map((item, index) => (
            <div
              key={item.className}
              data-testid={`class-item-${item.className}`}
              className="group"
            >
              <div className="mb-1 flex items-center justify-between text-sm">
                <span className="text-gray-300">{item.className}</span>
                <span className="font-medium text-white">{item.count}</span>
              </div>
              <div className="h-4 overflow-hidden rounded bg-gray-800">
                <div
                  className="h-full rounded transition-all duration-300 group-hover:brightness-110"
                  style={{
                    width: `${item.percentage}%`,
                    backgroundColor: getClassColor(index),
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

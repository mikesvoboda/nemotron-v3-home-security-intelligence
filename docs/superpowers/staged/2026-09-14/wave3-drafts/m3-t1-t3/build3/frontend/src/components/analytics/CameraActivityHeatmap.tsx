/**
 * CameraActivityHeatmap - Display camera activity as a visual heatmap
 *
 * Shows camera activity levels with color intensity based on event count
 * and max risk score. Includes thumbnail of highest-risk detection per camera.
 *
 * Color coding by risk level (matching frontend/src/utils/risk.ts):
 * - Green: Low risk (0-29)
 * - Yellow: Medium risk (30-59)
 * - Orange: High risk (60-84)
 * - Red: Critical risk (85-100)
 *
 * @see NEM-5388, NEM-5389, NEM-5390, NEM-5391 - Camera Activity Heatmap feature
 */

import { Card, Title, Text } from '@tremor/react';
import { AlertCircle, Loader2, Camera } from 'lucide-react';
import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import {
  useCameraActivityQuery,
  type CameraActivityDateRange,
} from '../../hooks/useCameraActivityQuery';
import { getRiskBgClass } from '../../utils/risk';

import type { CameraActivityDataPoint, RiskLevel } from '../../types/analytics';

// ============================================================================
// Types
// ============================================================================

interface CameraActivityHeatmapProps {
  /** Date range for activity calculation */
  dateRange: CameraActivityDateRange;
  /** Callback when a camera is clicked (optional, defaults to navigation) */
  onCameraClick?: (cameraId: string) => void;
}

// ============================================================================
// Constants
// ============================================================================

/**
 * Risk level Tailwind border classes.
 */
const RISK_BORDER_CLASSES: Record<RiskLevel, string> = {
  low: 'border-green-500',
  medium: 'border-yellow-500',
  high: 'border-orange-500',
  critical: 'border-red-500',
};

// ============================================================================
// Utility Functions
// ============================================================================

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

/**
 * Get thumbnail URL from path.
 *
 * @param thumbnailPath - Path to thumbnail or null
 * @returns Full URL for thumbnail image
 */
function getThumbnailUrl(thumbnailPath: string | null): string | null {
  if (!thumbnailPath) return null;
  // If path starts with http, it's already a full URL
  if (thumbnailPath.startsWith('http')) return thumbnailPath;
  // Otherwise, construct the API URL
  return `/api/media/thumbnail?path=${encodeURIComponent(thumbnailPath)}`;
}

// ============================================================================
// Component
// ============================================================================

/**
 * CameraActivityHeatmap displays camera activity as a visual heatmap grid.
 *
 * Each camera is shown as a card with:
 * - Thumbnail of highest-risk detection (or placeholder)
 * - Camera name and event count
 * - Risk indicator border color
 * - Max risk score
 *
 * Clicking a camera navigates to the timeline filtered by that camera.
 *
 * @param props - Component props
 * @returns React element
 */
export default function CameraActivityHeatmap({
  dateRange,
  onCameraClick,
}: CameraActivityHeatmapProps) {
  const navigate = useNavigate();
  const { cameras, isLoading, error } = useCameraActivityQuery(dateRange);

  // Handle camera click - navigate to timeline with camera filter
  const handleCameraClick = useCallback(
    (cameraId: string) => {
      if (onCameraClick) {
        onCameraClick(cameraId);
      } else {
        void navigate(`/timeline?camera=${cameraId}`);
      }
    },
    [onCameraClick, navigate]
  );

  // Format date range for display
  const dateRangeLabel = `${formatDate(dateRange.startDate)} - ${formatDate(dateRange.endDate)}`;

  // Loading state
  if (isLoading) {
    return (
      <Card data-testid="camera-activity-loading">
        <Title>Camera Activity</Title>
        <div className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      </Card>
    );
  }

  // Error state
  if (error) {
    return (
      <Card data-testid="camera-activity-error">
        <Title>Camera Activity</Title>
        <div className="flex h-48 flex-col items-center justify-center text-red-400">
          <AlertCircle className="mb-2 h-8 w-8" />
          <Text>Failed to load camera activity data</Text>
        </div>
      </Card>
    );
  }

  // Empty state
  if (cameras.length === 0) {
    return (
      <Card data-testid="camera-activity-empty">
        <Title>Camera Activity</Title>
        <div className="flex h-48 flex-col items-center justify-center text-gray-400">
          <Camera className="mb-2 h-8 w-8" />
          <Text>No camera activity in this period</Text>
        </div>
      </Card>
    );
  }

  return (
    <Card data-testid="camera-activity-card">
      <div className="mb-4 flex items-center justify-between">
        <Title>Camera Activity</Title>
        <Text className="text-gray-400">{dateRangeLabel}</Text>
      </div>

      {/* Camera activity grid */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
        {cameras.map((camera) => (
          <CameraActivityItem
            key={camera.camera_id}
            camera={camera}
            onClick={() => handleCameraClick(camera.camera_id)}
          />
        ))}
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-4 border-t border-gray-800 pt-4 text-xs text-gray-400">
        <div className="flex items-center gap-1.5">
          <div className="h-2.5 w-2.5 rounded-sm bg-green-500" />
          <span>Low</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2.5 w-2.5 rounded-sm bg-yellow-500" />
          <span>Medium</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2.5 w-2.5 rounded-sm bg-orange-500" />
          <span>High</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="h-2.5 w-2.5 rounded-sm bg-red-500" />
          <span>Critical</span>
        </div>
      </div>
    </Card>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

interface CameraActivityItemProps {
  camera: CameraActivityDataPoint;
  onClick: () => void;
}

/**
 * Individual camera activity card.
 */
function CameraActivityItem({ camera, onClick }: CameraActivityItemProps) {
  const thumbnailUrl = getThumbnailUrl(camera.thumbnail_path);
  const riskLevel = camera.risk_level ?? 'low';
  const borderClass = RISK_BORDER_CLASSES[riskLevel];

  // Construct aria-label for accessibility
  const ariaLabel = `${camera.camera_name}: ${camera.event_count} events${camera.max_risk_score !== null ? `, risk score ${camera.max_risk_score}` : ''}`;

  return (
    <div
      data-testid={`camera-activity-item-${camera.camera_id}`}
      data-risk-level={riskLevel}
      aria-label={ariaLabel}
      tabIndex={0}
      role="button"
      className={`group cursor-pointer overflow-hidden rounded-lg border-2 bg-gray-900 transition-all hover:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-[#76B900] ${borderClass}`}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
    >
      {/* Thumbnail or placeholder */}
      <div className="relative aspect-video bg-gray-800">
        {thumbnailUrl ? (
          <img
            src={thumbnailUrl}
            alt={`${camera.camera_name} highest risk detection`}
            data-testid={`camera-thumbnail-${camera.camera_id}`}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div
            data-testid={`camera-placeholder-${camera.camera_id}`}
            className="flex h-full w-full items-center justify-center"
          >
            <Camera className="h-8 w-8 text-gray-600" />
          </div>
        )}

        {/* Risk score badge */}
        {camera.max_risk_score !== null && (
          <div
            className={`absolute right-2 top-2 rounded px-1.5 py-0.5 text-xs font-medium ${getRiskBgClass(riskLevel)} text-white`}
          >
            Risk: {camera.max_risk_score}
          </div>
        )}
      </div>

      {/* Camera info */}
      <div className="p-2">
        <div className="truncate text-sm font-medium text-white group-hover:text-[#76B900]">
          {camera.camera_name}
        </div>
        <div className="text-xs text-gray-400">
          {camera.event_count} {camera.event_count === 1 ? 'event' : 'events'}
        </div>
      </div>
    </div>
  );
}

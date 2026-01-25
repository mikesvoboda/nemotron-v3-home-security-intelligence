/**
 * CameraAnalyticsSelector - Camera dropdown for analytics filtering
 *
 * A Tremor Select component that allows users to filter analytics
 * by a specific camera or view aggregate data for all cameras.
 *
 * Features:
 * - "All Cameras" option for aggregate view
 * - Individual camera selection for per-camera analytics
 * - Loading state with spinner
 * - Accessible with keyboard navigation
 */

import { Select, SelectItem, Text } from '@tremor/react';
import { Camera, Loader2 } from 'lucide-react';

import type { CameraOption } from '../../hooks/useCameraAnalytics';

/**
 * Props for CameraAnalyticsSelector component
 */
export interface CameraAnalyticsSelectorProps {
  /** List of camera options including "All Cameras" */
  cameras: CameraOption[];
  /** Currently selected camera ID (empty string for "All Cameras") */
  selectedCameraId: string;
  /** Callback when camera selection changes */
  onCameraChange: (cameraId: string) => void;
  /** Whether the camera list is loading */
  isLoading?: boolean;
  /** Whether the selector is disabled */
  disabled?: boolean;
  /** Optional className for styling */
  className?: string;
}

/**
 * CameraAnalyticsSelector - Dropdown for filtering analytics by camera
 *
 * Renders a Tremor Select with camera options. The "All Cameras" option
 * is represented by an empty string value and shows aggregate analytics.
 *
 * @param props - Component props
 * @returns React element
 *
 * @example
 * ```tsx
 * <CameraAnalyticsSelector
 *   cameras={camerasWithAll}
 *   selectedCameraId={selectedCameraId ?? ''}
 *   onCameraChange={setSelectedCameraId}
 *   isLoading={isLoadingCameras}
 * />
 * ```
 */
export default function CameraAnalyticsSelector({
  cameras,
  selectedCameraId,
  onCameraChange,
  isLoading = false,
  disabled = false,
  className = '',
}: CameraAnalyticsSelectorProps) {
  return (
    <div
      className={`flex items-center gap-2 ${className}`}
      data-testid="camera-analytics-selector"
    >
      <Camera className="h-4 w-4 text-gray-400" />
      <Text className="text-sm font-medium text-gray-300">Camera</Text>

      {isLoading && (
        <Loader2
          className="h-4 w-4 animate-spin text-gray-400"
          data-testid="camera-selector-loading"
        />
      )}

      <Select
        value={selectedCameraId}
        onValueChange={onCameraChange}
        disabled={disabled || isLoading}
        className="w-48"
        placeholder="Select camera..."
      >
        {cameras.map((camera) => (
          <SelectItem
            key={camera.id || 'all-cameras'}
            value={camera.id}
            data-testid={`camera-option-${camera.id || 'all'}`}
          >
            {camera.name}
          </SelectItem>
        ))}
      </Select>
    </div>
  );
}

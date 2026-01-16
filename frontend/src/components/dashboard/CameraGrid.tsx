import { clsx } from 'clsx';
import {
  AlertCircle,
  Camera,
  Circle,
  Clock,
  HelpCircle,
  Video,
  VideoOff,
  WifiOff,
} from 'lucide-react';
import { memo, useCallback, useEffect, useState } from 'react';

import { useCameraStatusWebSocket } from '../../hooks/useCameraStatusWebSocket';

import type { CameraStatusEventPayload, CameraStatusValue } from '../../types/websocket-events';

/**
 * Camera status information for the grid
 */
export interface CameraStatus {
  id: string;
  name: string;
  status: 'online' | 'offline' | 'error' | 'recording' | 'unknown';
  thumbnail_url?: string;
  last_seen_at?: string;
  error_message?: string;
}

/**
 * Props for the CameraGrid component
 */
export interface CameraGridProps {
  cameras: CameraStatus[];
  selectedCameraId?: string;
  onCameraClick?: (cameraId: string) => void;
  className?: string;
  /**
   * Enable real-time WebSocket updates for camera status (NEM-2295).
   * When enabled, camera status changes will be reflected immediately.
   * @default false
   */
  enableWebSocketUpdates?: boolean;
  /**
   * Callback when a camera status changes via WebSocket (NEM-2295).
   */
  onCameraStatusChange?: (event: CameraStatusEventPayload) => void;
}

/**
 * Get status indicator color classes based on camera status
 */
function getStatusColor(status: CameraStatus['status']): string {
  const colors = {
    online: 'bg-green-500',
    recording: 'bg-yellow-500',
    offline: 'bg-gray-500',
    error: 'bg-red-500',
    unknown: 'bg-gray-500',
  };
  return colors[status];
}

/**
 * Get status label text
 */
function getStatusLabel(status: CameraStatus['status']): string {
  const labels = {
    online: 'Online',
    recording: 'Recording',
    offline: 'Offline',
    error: 'Error',
    unknown: 'Unknown',
  };
  return labels[status];
}

/**
 * Get icon based on camera status
 */
function getStatusIcon(status: CameraStatus['status']) {
  switch (status) {
    case 'recording':
      return Video;
    case 'offline':
      return WifiOff;
    case 'error':
      return AlertCircle;
    case 'unknown':
      return HelpCircle;
    case 'online':
    default:
      return Camera;
  }
}

/**
 * Get placeholder background classes based on camera status
 */
function getPlaceholderStyles(status: CameraStatus['status']): {
  bgClass: string;
  iconColorClass: string;
  textColorClass: string;
} {
  switch (status) {
    case 'error':
      return {
        bgClass: 'bg-gradient-to-br from-red-950/50 to-gray-900',
        iconColorClass: 'text-red-400',
        textColorClass: 'text-red-300',
      };
    case 'offline':
      return {
        bgClass: 'bg-gradient-to-br from-gray-800 to-gray-900',
        iconColorClass: 'text-gray-500',
        textColorClass: 'text-gray-400',
      };
    case 'unknown':
      return {
        bgClass: 'bg-gradient-to-br from-gray-800/80 to-gray-900',
        iconColorClass: 'text-gray-500',
        textColorClass: 'text-gray-400',
      };
    case 'recording':
      return {
        bgClass: 'bg-gradient-to-br from-yellow-950/30 to-gray-900',
        iconColorClass: 'text-yellow-500',
        textColorClass: 'text-yellow-300',
      };
    case 'online':
    default:
      return {
        bgClass: 'bg-gray-900',
        iconColorClass: 'text-gray-600',
        textColorClass: 'text-gray-400',
      };
  }
}

/**
 * Get status-specific message for placeholder
 */
function getPlaceholderMessage(status: CameraStatus['status'], errorMessage?: string): string {
  switch (status) {
    case 'error':
      return errorMessage || 'Connection error';
    case 'offline':
      return 'Camera is offline';
    case 'unknown':
      return 'Status unknown';
    case 'recording':
      return 'No preview available';
    case 'online':
    default:
      return 'No image available';
  }
}

/**
 * Format relative time for display (e.g., "5 mins ago", "2 hours ago")
 */
function formatRelativeTime(timestamp: string): string {
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins === 1) return '1 min ago';
  if (diffMins < 60) return `${diffMins} mins ago`;
  if (diffHours === 1) return '1 hour ago';
  if (diffHours < 24) return `${diffHours} hours ago`;
  if (diffDays === 1) return '1 day ago';
  if (diffDays < 7) return `${diffDays} days ago`;

  // Fallback to formatted date
  return then.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

/**
 * Props for the CameraCard component
 */
interface CameraCardProps {
  camera: CameraStatus;
  isSelected: boolean;
  onClick?: () => void;
  /**
   * Whether this camera recently changed status (NEM-2295).
   * Used to show a visual indicator for real-time updates.
   */
  recentlyChanged?: boolean;
}

/**
 * Individual camera card component
 */
const CameraCard = memo(function CameraCard({
  camera,
  isSelected,
  onClick,
  recentlyChanged = false,
}: CameraCardProps) {
  const StatusIcon = getStatusIcon(camera.status);
  // Only attempt to load thumbnail for online or recording cameras
  // Offline/error/unknown cameras won't have accessible snapshots
  const canLoadThumbnail = camera.status === 'online' || camera.status === 'recording';
  const hasThumbnail = Boolean(camera.thumbnail_url) && canLoadThumbnail;
  const [imageLoading, setImageLoading] = useState(true);
  const [imageError, setImageError] = useState(false);

  // Show placeholder if no thumbnail URL, camera is not active, or if image failed to load
  const showPlaceholder = !hasThumbnail || imageError;

  return (
    <button
      onClick={() => onClick?.()}
      className={clsx(
        'relative flex w-full flex-col overflow-hidden rounded-lg border transition-all duration-250',
        'bg-card hover:bg-gray-850 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background',
        isSelected ? 'border-primary shadow-nvidia-glow' : 'border-gray-800 hover:border-gray-700',
        onClick && 'cursor-pointer',
        // NEM-2295: Visual indicator for recently changed status
        recentlyChanged && 'ring-2 ring-yellow-500/50 ring-offset-1 ring-offset-background'
      )}
      aria-label={`Camera ${camera.name}, status: ${getStatusLabel(camera.status)}`}
      aria-pressed={isSelected}
      data-testid={`camera-card-${camera.id}`}
    >
      {/* Thumbnail or placeholder */}
      <div className="relative aspect-video w-full bg-gray-900">
        {/* Loading skeleton - shown while image is loading */}
        {hasThumbnail && imageLoading && !imageError && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="h-full w-full animate-pulse bg-gray-800" />
          </div>
        )}

        {/* Actual thumbnail image */}
        {hasThumbnail && !imageError && (
          <img
            src={camera.thumbnail_url}
            alt={`${camera.name} thumbnail`}
            className={clsx(
              'h-full w-full object-cover transition-opacity duration-300',
              imageLoading ? 'opacity-0' : 'opacity-100'
            )}
            loading="lazy"
            onLoad={() => setImageLoading(false)}
            onError={() => {
              setImageLoading(false);
              setImageError(true);
            }}
          />
        )}

        {/* Placeholder - shown when no thumbnail or on error */}
        {showPlaceholder && (
          <div
            className={clsx(
              'flex h-full w-full flex-col items-center justify-center',
              getPlaceholderStyles(camera.status).bgClass
            )}
            data-testid={`camera-placeholder-${camera.id}`}
          >
            <StatusIcon
              className={clsx('h-10 w-10', getPlaceholderStyles(camera.status).iconColorClass)}
              aria-hidden="true"
            />
            <span
              className={clsx(
                'mt-2 text-xs font-medium',
                getPlaceholderStyles(camera.status).textColorClass
              )}
            >
              {getPlaceholderMessage(camera.status, camera.error_message)}
            </span>
            {/* Show last seen time for offline cameras */}
            {camera.status === 'offline' && camera.last_seen_at && (
              <span className="mt-1 flex items-center gap-1 text-xs text-gray-500">
                <Clock className="h-3 w-3" aria-hidden="true" />
                Last seen {formatRelativeTime(camera.last_seen_at)}
              </span>
            )}
          </div>
        )}

        {/* Status indicator badge - top-right corner */}
        <div className="absolute right-2 top-2 flex items-center gap-1.5 rounded-full bg-black/80 px-2 py-1 backdrop-blur-sm">
          <Circle className={clsx('h-2 w-2 fill-current', getStatusColor(camera.status))} />
          <span className="text-xs font-medium text-white">{getStatusLabel(camera.status)}</span>
        </div>
      </div>

      {/* Camera name */}
      <div className="flex items-center justify-between border-t border-gray-800 bg-gray-900/50 px-3 py-2">
        <span className="truncate text-sm font-medium text-white">{camera.name}</span>
        {camera.last_seen_at && (
          <span className="ml-2 text-xs text-text-secondary">
            {new Date(camera.last_seen_at).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        )}
      </div>
    </button>
  );
});

/**
 * Duration in milliseconds to show the "recently changed" visual indicator.
 * After this time, the highlight animation will fade out.
 */
const RECENTLY_CHANGED_DURATION_MS = 5000;

/**
 * CameraGrid component displays a responsive grid of camera thumbnails
 * with status indicators and selection highlighting.
 *
 * Features:
 * - Responsive grid: 1 column on mobile, 2 on tablet, 3 on medium, 4 on desktop
 * - Graceful handling of uneven camera counts (1, 3, 5, 7, etc.) with centered layout
 * - Consistent card sizes regardless of camera count
 * - Status indicators: green=online, yellow=recording, red=offline, gray=unknown
 * - Click handlers for camera selection
 * - Placeholder for cameras without thumbnails
 * - NVIDIA theme with dark backgrounds and subtle borders
 * - Real-time WebSocket updates for camera status (NEM-2295)
 */
export default function CameraGrid({
  cameras,
  selectedCameraId,
  onCameraClick,
  className,
  enableWebSocketUpdates = false,
  onCameraStatusChange,
}: CameraGridProps) {
  // Track which cameras have recently changed status (NEM-2295)
  const [recentlyChangedCameras, setRecentlyChangedCameras] = useState<Set<string>>(new Set());

  // Track status overrides from WebSocket updates
  const [statusOverrides, setStatusOverrides] = useState<Record<string, CameraStatusValue>>({});

  // Handle status changes from WebSocket
  const handleCameraStatusChange = useCallback(
    (event: CameraStatusEventPayload) => {
      // Update status override
      setStatusOverrides((prev) => ({
        ...prev,
        [event.camera_id]: event.status,
      }));

      // Mark camera as recently changed
      setRecentlyChangedCameras((prev) => {
        const next = new Set(prev);
        next.add(event.camera_id);
        return next;
      });

      // Clear the "recently changed" indicator after a delay
      setTimeout(() => {
        setRecentlyChangedCameras((prev) => {
          const next = new Set(prev);
          next.delete(event.camera_id);
          return next;
        });
      }, RECENTLY_CHANGED_DURATION_MS);

      // Call external callback if provided
      onCameraStatusChange?.(event);
    },
    [onCameraStatusChange]
  );

  // Subscribe to camera status WebSocket events
  // The hook manages the WebSocket connection lifecycle automatically
  useCameraStatusWebSocket({
    enabled: enableWebSocketUpdates,
    onCameraStatusChange: handleCameraStatusChange,
  });

  // Merge camera props with status overrides
  const mergedCameras = cameras.map((camera) => {
    const override = statusOverrides[camera.id];
    if (override) {
      return {
        ...camera,
        status: override,
      };
    }
    return camera;
  });

  // Clear status overrides when cameras prop changes (to avoid stale data)
  useEffect(() => {
    const cameraIds = new Set(cameras.map((c) => c.id));
    setStatusOverrides((prev) => {
      const next: Record<string, CameraStatusValue> = {};
      for (const [id, status] of Object.entries(prev)) {
        if (cameraIds.has(id)) {
          next[id] = status;
        }
      }
      return next;
    });
  }, [cameras]);

  if (cameras.length === 0) {
    return (
      <div
        className={clsx(
          'flex items-center justify-center rounded-lg border border-dashed border-gray-700 bg-gradient-to-br from-gray-900 to-gray-950 p-12',
          className
        )}
        data-testid="camera-grid-empty"
      >
        <div className="text-center">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-gray-800/50">
            <VideoOff className="h-8 w-8 text-gray-500" aria-hidden="true" />
          </div>
          <p className="mt-4 text-sm font-medium text-text-secondary">No cameras configured</p>
          <p className="mt-2 text-xs text-text-muted">
            Add cameras in Settings to start monitoring
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={clsx(
        'grid gap-4',
        // Responsive grid: 1 column on mobile, 2 on tablet, 3 on large screens
        // This provides better space utilization in the 2-column dashboard layout
        'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
        // Center items to handle uneven camera counts gracefully
        'justify-items-center',
        className
      )}
      role="group"
      aria-label="Camera grid"
      data-testid="camera-grid"
    >
      {mergedCameras.map((camera) => (
        <CameraCard
          key={camera.id}
          camera={camera}
          isSelected={camera.id === selectedCameraId}
          onClick={onCameraClick ? () => onCameraClick(camera.id) : undefined}
          recentlyChanged={recentlyChangedCameras.has(camera.id)}
        />
      ))}
    </div>
  );
}

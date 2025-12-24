import { clsx } from 'clsx';
import { Camera, Circle, Video, VideoOff } from 'lucide-react';

/**
 * Camera status information for the grid
 */
export interface CameraStatus {
  id: string;
  name: string;
  status: 'online' | 'offline' | 'recording' | 'unknown';
  thumbnail_url?: string;
  last_seen_at?: string;
}

/**
 * Props for the CameraGrid component
 */
export interface CameraGridProps {
  cameras: CameraStatus[];
  selectedCameraId?: string;
  onCameraClick?: (cameraId: string) => void;
  className?: string;
}

/**
 * Get status indicator color classes based on camera status
 */
function getStatusColor(status: CameraStatus['status']): string {
  const colors = {
    online: 'bg-green-500',
    recording: 'bg-yellow-500',
    offline: 'bg-red-500',
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
      return VideoOff;
    case 'online':
    case 'unknown':
    default:
      return Camera;
  }
}

/**
 * Individual camera card component
 */
function CameraCard({
  camera,
  isSelected,
  onClick,
}: {
  camera: CameraStatus;
  isSelected: boolean;
  onClick?: () => void;
}) {
  const StatusIcon = getStatusIcon(camera.status);
  const hasThumbnail = Boolean(camera.thumbnail_url);

  return (
    <button
      onClick={() => onClick?.()}
      className={clsx(
        'relative flex flex-col overflow-hidden rounded-lg border transition-all duration-250',
        'bg-card hover:bg-gray-850 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background',
        isSelected
          ? 'border-primary shadow-nvidia-glow'
          : 'border-gray-800 hover:border-gray-700',
        onClick && 'cursor-pointer'
      )}
      aria-label={`Camera ${camera.name}, status: ${getStatusLabel(camera.status)}`}
      aria-pressed={isSelected}
    >
      {/* Thumbnail or placeholder */}
      <div className="relative aspect-video w-full bg-gray-900">
        {hasThumbnail ? (
          <img
            src={camera.thumbnail_url}
            alt={`${camera.name} thumbnail`}
            className="h-full w-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <StatusIcon className="h-12 w-12 text-gray-700" />
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
}

/**
 * CameraGrid component displays a responsive grid of camera thumbnails
 * with status indicators and selection highlighting.
 *
 * Features:
 * - 2x4 responsive grid (adjusts for smaller screens)
 * - Status indicators: green=online, yellow=recording, red=offline, gray=unknown
 * - Click handlers for camera selection
 * - Placeholder for cameras without thumbnails
 * - NVIDIA theme with dark backgrounds and subtle borders
 */
export default function CameraGrid({
  cameras,
  selectedCameraId,
  onCameraClick,
  className,
}: CameraGridProps) {
  if (cameras.length === 0) {
    return (
      <div
        className={clsx(
          'flex items-center justify-center rounded-lg border border-gray-800 bg-card p-12',
          className
        )}
      >
        <div className="text-center">
          <Camera className="mx-auto h-12 w-12 text-gray-700" />
          <p className="mt-4 text-sm font-medium text-text-secondary">No cameras configured</p>
          <p className="mt-1 text-xs text-text-muted">Add cameras to start monitoring</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={clsx(
        'grid gap-4',
        // Responsive grid: 1 column on mobile, 2 on tablet, 4 on desktop
        'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4',
        className
      )}
      role="list"
      aria-label="Camera grid"
    >
      {cameras.map((camera) => (
        <CameraCard
          key={camera.id}
          camera={camera}
          isSelected={camera.id === selectedCameraId}
          onClick={onCameraClick ? () => onCameraClick(camera.id) : undefined}
        />
      ))}
    </div>
  );
}

/**
 * SceneChangeIndicator - Visual indicator component for scene change events (NEM-3575)
 *
 * Displays a pulsing indicator badge when a camera has recent scene change activity.
 * Used in camera grid and detail views to alert users of potential tampering.
 *
 * @module components/cameras/SceneChangeIndicator
 */

import { clsx } from 'clsx';
import { AlertTriangle, ShieldAlert } from 'lucide-react';
import { memo } from 'react';

import type { CameraActivityState } from '../../hooks/useSceneChangeEvents';

/**
 * Props for the SceneChangeIndicator component
 */
export interface SceneChangeIndicatorProps {
  /** Activity state from useSceneChangeEvents hook */
  activityState?: CameraActivityState;
  /** Compact mode for smaller spaces (badge only) */
  compact?: boolean;
  /** Additional CSS classes */
  className?: string;
  /** Show detailed info (change type and time) */
  showDetails?: boolean;
}

/**
 * Get display info for change type
 */
function getChangeTypeDisplay(changeType: string): {
  label: string;
  severity: 'high' | 'medium' | 'low';
  icon: typeof AlertTriangle;
} {
  switch (changeType) {
    case 'view_blocked':
      return { label: 'View Blocked', severity: 'high', icon: ShieldAlert };
    case 'view_tampered':
      return { label: 'Tampered', severity: 'high', icon: ShieldAlert };
    case 'angle_changed':
      return { label: 'Angle Changed', severity: 'medium', icon: AlertTriangle };
    default:
      return { label: 'Scene Change', severity: 'low', icon: AlertTriangle };
  }
}

/**
 * Format time since activity
 */
function formatTimeSince(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);

  if (diffSeconds < 60) {
    return 'just now';
  } else if (diffMinutes < 60) {
    return `${diffMinutes}m ago`;
  } else {
    const diffHours = Math.floor(diffMinutes / 60);
    return `${diffHours}h ago`;
  }
}

/**
 * SceneChangeIndicator component
 *
 * Visual indicator for scene change detection on a camera. Shows when camera
 * view may have been tampered with, blocked, or changed.
 *
 * @example
 * ```tsx
 * const { getActivityState } = useSceneChangeEvents();
 * const activity = getActivityState('front_door');
 *
 * <SceneChangeIndicator activityState={activity} />
 * ```
 */
function SceneChangeIndicatorComponent({
  activityState,
  compact = false,
  className,
  showDetails = false,
}: SceneChangeIndicatorProps) {
  // Don't render if no activity or not active
  if (!activityState || !activityState.isActive) {
    return null;
  }

  const { label, severity, icon: Icon } = getChangeTypeDisplay(activityState.lastChangeType);

  // Severity-based styling
  const severityClasses = {
    high: 'bg-red-500/90 text-white',
    medium: 'bg-amber-500/90 text-white',
    low: 'bg-yellow-500/90 text-black',
  };

  const pulseClasses = {
    high: 'animate-pulse',
    medium: 'animate-pulse',
    low: '',
  };

  if (compact) {
    // Compact badge mode - just icon with pulse
    return (
      <div
        className={clsx(
          'flex items-center justify-center rounded-full p-1',
          severityClasses[severity],
          pulseClasses[severity],
          className
        )}
        title={`${label} - ${activityState.cameraName}`}
        data-testid="scene-change-indicator-compact"
        aria-label={`Scene change detected: ${label}`}
      >
        <Icon className="h-3 w-3" aria-hidden="true" />
      </div>
    );
  }

  // Full badge mode
  return (
    <div
      className={clsx(
        'flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-medium backdrop-blur-sm',
        severityClasses[severity],
        pulseClasses[severity],
        className
      )}
      data-testid="scene-change-indicator"
      role="alert"
      aria-live="polite"
    >
      <Icon className="h-3 w-3" aria-hidden="true" />
      <span>{label}</span>
      {showDetails && (
        <span className="ml-1 text-xs opacity-75">
          {formatTimeSince(activityState.lastActivityAt)}
        </span>
      )}
    </div>
  );
}

/**
 * Memoized SceneChangeIndicator for performance
 */
export const SceneChangeIndicator = memo(SceneChangeIndicatorComponent);

export default SceneChangeIndicator;

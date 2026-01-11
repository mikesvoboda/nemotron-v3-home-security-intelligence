/**
 * SceneChangeAlert - Badge component for displaying scene change notifications.
 *
 * Displays a badge with count of unacknowledged scene changes that can be clicked
 * to show details or navigate to the scene change management page.
 *
 * Features:
 * - Badge with count of unacknowledged scene changes
 * - Expandable dropdown showing recent scene change alerts
 * - Ability to dismiss individual alerts or all at once
 * - Color-coded severity indicators
 * - Accessible with keyboard navigation
 */
import { clsx } from 'clsx';
import { AlertTriangle, Camera, ChevronDown, X } from 'lucide-react';
import { useEffect, useRef, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

import { formatChangeType, getChangeSeverity } from '../../hooks/useSceneChangeAlerts';

import type { SceneChangeAlert as SceneChangeAlertType } from '../../hooks/useSceneChangeAlerts';

export interface SceneChangeAlertProps {
  /** List of scene change alerts */
  alerts: SceneChangeAlertType[];
  /** Count of unacknowledged alerts */
  unacknowledgedCount: number;
  /** Whether there are any unacknowledged alerts */
  hasAlerts: boolean;
  /** Callback to dismiss a specific alert */
  onDismiss: (id: number) => void;
  /** Callback to dismiss all alerts */
  onDismissAll: () => void;
  /** Optional class name for styling */
  className?: string;
}

/**
 * Get color configuration based on severity.
 */
function getSeverityConfig(severity: 'high' | 'medium' | 'low'): {
  bgColor: string;
  textColor: string;
  borderColor: string;
} {
  switch (severity) {
    case 'high':
      return {
        bgColor: 'bg-red-500/10',
        textColor: 'text-red-400',
        borderColor: 'border-red-500/30',
      };
    case 'medium':
      return {
        bgColor: 'bg-orange-500/10',
        textColor: 'text-orange-400',
        borderColor: 'border-orange-500/30',
      };
    case 'low':
    default:
      return {
        bgColor: 'bg-yellow-500/10',
        textColor: 'text-yellow-400',
        borderColor: 'border-yellow-500/30',
      };
  }
}

/**
 * Format timestamp for display.
 */
function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) {
    return 'Just now';
  } else if (diffMins < 60) {
    return `${diffMins}m ago`;
  } else if (diffMins < 1440) {
    const hours = Math.floor(diffMins / 60);
    return `${hours}h ago`;
  } else {
    return date.toLocaleDateString();
  }
}

interface AlertItemProps {
  alert: SceneChangeAlertType;
  onDismiss: (id: number) => void;
}

function AlertItem({ alert, onDismiss }: AlertItemProps) {
  const severity = getChangeSeverity(alert.changeType);
  const config = getSeverityConfig(severity);

  const handleDismiss = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onDismiss(alert.id);
    },
    [alert.id, onDismiss]
  );

  return (
    <div
      className={clsx(
        'flex items-start justify-between gap-2 rounded border px-3 py-2',
        config.bgColor,
        config.borderColor
      )}
      data-testid={`scene-change-alert-${alert.id}`}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <Camera className={clsx('h-3.5 w-3.5 flex-shrink-0', config.textColor)} />
          <span className="text-sm font-medium text-white truncate">{alert.cameraId}</span>
        </div>
        <div className="mt-1 flex items-center gap-2">
          <span className={clsx('text-xs font-medium', config.textColor)}>
            {formatChangeType(alert.changeType)}
          </span>
          <span className="text-xs text-gray-500">
            {formatTimestamp(alert.detectedAt)}
          </span>
        </div>
        <div className="mt-0.5 text-xs text-gray-500">
          Similarity: {(alert.similarityScore * 100).toFixed(1)}%
        </div>
      </div>
      <button
        onClick={handleDismiss}
        className="flex-shrink-0 p-1 text-gray-500 hover:text-gray-300 transition-colors"
        aria-label={`Dismiss alert for ${alert.cameraId}`}
        data-testid={`dismiss-alert-${alert.id}`}
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

/**
 * SceneChangeAlert badge component for the header.
 */
export default function SceneChangeAlert({
  alerts,
  unacknowledgedCount,
  hasAlerts,
  onDismiss,
  onDismissAll,
  className,
}: SceneChangeAlertProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const dropdownTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Filter to only show undismissed alerts
  const activeAlerts = alerts.filter((alert) => !alert.dismissed);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (dropdownTimeoutRef.current) {
        clearTimeout(dropdownTimeoutRef.current);
      }
    };
  }, []);

  const handleMouseEnter = () => {
    if (dropdownTimeoutRef.current) {
      clearTimeout(dropdownTimeoutRef.current);
    }
    setIsExpanded(true);
  };

  const handleMouseLeave = () => {
    dropdownTimeoutRef.current = setTimeout(() => {
      setIsExpanded(false);
    }, 150);
  };

  const handleViewAll = () => {
    setIsExpanded(false);
    void navigate('/analytics');
  };

  // Don't render if no alerts
  if (!hasAlerts) {
    return null;
  }

  return (
    <div
      ref={containerRef}
      className={clsx('relative', className)}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      data-testid="scene-change-alert"
      role="group"
      aria-label="Scene change alerts"
    >
      {/* Badge Button */}
      <button
        className="flex items-center gap-1.5 rounded-md bg-orange-500/20 px-2.5 py-1.5 text-orange-400 transition-colors hover:bg-orange-500/30 focus:outline-none focus:ring-2 focus:ring-orange-500/50"
        onClick={() => setIsExpanded(!isExpanded)}
        aria-label={`${unacknowledgedCount} scene change alert${unacknowledgedCount !== 1 ? 's' : ''}`}
        aria-haspopup="true"
        aria-expanded={isExpanded}
        data-testid="scene-change-badge"
      >
        <AlertTriangle className="h-4 w-4" aria-hidden="true" />
        <span className="text-sm font-medium">{unacknowledgedCount}</span>
        <ChevronDown
          className={clsx(
            'h-3.5 w-3.5 transition-transform',
            isExpanded && 'rotate-180'
          )}
          aria-hidden="true"
        />
      </button>

      {/* Dropdown */}
      {isExpanded && (
        <div
          className="absolute right-0 top-full z-50 mt-2 w-72 max-h-96 overflow-hidden rounded-lg border border-gray-700 bg-gray-900 shadow-lg"
          role="menu"
          data-testid="scene-change-dropdown"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-gray-800 px-3 py-2">
            <div className="text-sm font-semibold text-white">
              Scene Change Alerts
            </div>
            <button
              onClick={onDismissAll}
              className="text-xs text-gray-400 hover:text-white transition-colors"
              data-testid="dismiss-all-alerts"
            >
              Dismiss All
            </button>
          </div>

          {/* Alert List */}
          <div className="max-h-64 overflow-y-auto p-2 space-y-2">
            {activeAlerts.length === 0 ? (
              <div className="py-4 text-center text-sm text-gray-500">
                No active alerts
              </div>
            ) : (
              activeAlerts.slice(0, 10).map((alert) => (
                <AlertItem key={alert.id} alert={alert} onDismiss={onDismiss} />
              ))
            )}
          </div>

          {/* Footer */}
          <div className="border-t border-gray-800 px-3 py-2">
            <button
              onClick={handleViewAll}
              className="w-full text-center text-xs text-[#76B900] hover:text-[#8BD000] transition-colors"
              data-testid="view-all-scene-changes"
            >
              View All Scene Changes
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

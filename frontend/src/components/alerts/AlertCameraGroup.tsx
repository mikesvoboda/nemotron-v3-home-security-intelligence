import { Transition } from '@headlessui/react';
import { clsx } from 'clsx';
import { Camera, ChevronDown, X } from 'lucide-react';
import { Fragment, useMemo, useState } from 'react';

import { getRiskLevel, type RiskLevel } from '../../utils/risk';
import EventCard from '../events/EventCard';

import type { Event } from '../../services/api';
import type { Detection } from '../events/EventCard';

export interface AlertCameraGroupProps {
  /** Camera ID */
  cameraId: string;
  /** Camera display name */
  cameraName: string;
  /** Alerts for this camera */
  alerts: Event[];
  /** Whether the group is expanded by default */
  defaultExpanded?: boolean;
  /** Callback when an alert is snoozed */
  onSnooze?: (eventId: string, seconds: number) => void;
  /** Callback when dismiss all is clicked */
  onDismissAll?: (cameraId: string) => void;
  /** Callback when an alert card is clicked */
  onAlertClick?: (eventId: number) => void;
  /** Additional CSS classes */
  className?: string;
}

// Severity order for sorting badges (highest first)
const SEVERITY_ORDER: RiskLevel[] = ['critical', 'high', 'medium', 'low'];

// Severity rank for sorting alerts (lower number = higher priority)
const SEVERITY_RANK: Record<RiskLevel, number> = {
  critical: 0,
  high: 1,
  medium: 2,
  low: 3,
};

/**
 * AlertCameraGroup - Groups alerts by camera with collapsible sections
 *
 * Features:
 * - Collapsible section header with camera name
 * - Alert count per camera
 * - Severity summary badges (e.g., "2 critical", "3 high")
 * - "Dismiss all" option per camera group
 * - Smooth animations on expand/collapse
 */
export default function AlertCameraGroup({
  cameraId,
  cameraName,
  alerts,
  defaultExpanded = true,
  onSnooze,
  onDismissAll,
  onAlertClick,
  className,
}: AlertCameraGroupProps) {
  const [isOpen, setIsOpen] = useState(defaultExpanded);

  // Calculate severity counts
  const severityCounts = useMemo(() => {
    const counts: Record<RiskLevel, number> = {
      critical: 0,
      high: 0,
      medium: 0,
      low: 0,
    };

    alerts.forEach((alert) => {
      const level = (alert.risk_level as RiskLevel) || getRiskLevel(alert.risk_score || 0);
      counts[level]++;
    });

    return counts;
  }, [alerts]);

  // Get severity badges in order
  const severityBadges = useMemo(() => {
    return SEVERITY_ORDER.filter((level) => severityCounts[level] > 0).map((level) => ({
      level,
      count: severityCounts[level],
    }));
  }, [severityCounts]);

  // Sort alerts by severity (critical first) then by timestamp (newest first)
  const sortedAlerts = useMemo(() => {
    return [...alerts].sort((a, b) => {
      const levelA = (a.risk_level as RiskLevel) || getRiskLevel(a.risk_score || 0);
      const levelB = (b.risk_level as RiskLevel) || getRiskLevel(b.risk_score || 0);
      const rankDiff = SEVERITY_RANK[levelA] - SEVERITY_RANK[levelB];
      if (rankDiff !== 0) return rankDiff;
      // Same severity - sort by timestamp (newest first)
      return new Date(b.started_at).getTime() - new Date(a.started_at).getTime();
    });
  }, [alerts]);

  // Check if this group has any critical alerts (for special styling)
  const hasCriticalAlerts = severityCounts.critical > 0;

  // Convert Event to EventCard props
  const getEventCardProps = (event: Event) => {
    const detections: Detection[] = [];

    return {
      id: String(event.id),
      timestamp: event.started_at,
      camera_name: cameraName,
      risk_score: event.risk_score || 0,
      risk_label: event.risk_level || getRiskLevel(event.risk_score || 0),
      summary: event.summary || 'No summary available',
      detections,
      started_at: event.started_at,
      ended_at: event.ended_at,
      thumbnail_url: event.thumbnail_url ?? undefined,
      onClick: onAlertClick ? () => onAlertClick(event.id) : undefined,
      onSnooze,
      snooze_until: event.snooze_until,
    };
  };

  const alertCount = alerts.length;
  const alertLabel = alertCount === 1 ? '1 alert' : `${alertCount} alerts`;

  const handleToggle = () => {
    setIsOpen(!isOpen);
  };

  return (
    <div
      className={clsx(
        'rounded-lg border bg-[#1A1A1A]',
        hasCriticalAlerts
          ? 'border-red-500/50 shadow-[0_0_10px_rgba(239,68,68,0.2)]'
          : 'border-gray-800',
        className
      )}
      data-testid={`alert-camera-group-${cameraId}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between rounded-t-lg bg-[#1A1A1A] p-4">
        {/* Clickable toggle area */}
        <button
          onClick={handleToggle}
          className="flex flex-1 items-center gap-3 text-left transition-colors hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-[#76B900]/50 focus:ring-offset-2 focus:ring-offset-[#1A1A1A]"
          aria-expanded={isOpen}
          aria-label={`${cameraName} - ${alertLabel}`}
        >
          <Camera className="h-5 w-5 text-gray-400" aria-hidden="true" />
          <span className="text-lg font-semibold text-white">{cameraName}</span>
          <span className="text-sm text-gray-400">{alertLabel}</span>
          <ChevronDown
            className={clsx(
              'h-5 w-5 text-gray-400 transition-transform duration-200',
              isOpen ? 'rotate-180' : ''
            )}
            aria-hidden="true"
          />
        </button>

        {/* Action buttons - separate from toggle */}
        <div className="flex items-center gap-3">
          {/* Severity summary badges */}
          <div className="flex items-center gap-2">
            {severityBadges.map(({ level, count }) => (
              <span
                key={level}
                className={clsx(
                  'rounded-full px-2 py-0.5 text-xs font-medium',
                  level === 'critical' && 'bg-red-500/20 text-red-400',
                  level === 'high' && 'bg-orange-500/20 text-orange-400',
                  level === 'medium' && 'bg-yellow-500/20 text-yellow-400',
                  level === 'low' && 'bg-blue-500/20 text-blue-400'
                )}
              >
                {count} {level}
              </span>
            ))}
          </div>

          {/* Dismiss all button */}
          {onDismissAll && (
            <button
              onClick={() => onDismissAll(cameraId)}
              className="flex items-center gap-1.5 rounded-md bg-gray-700/50 px-3 py-1.5 text-sm font-medium text-gray-300 transition-colors hover:bg-gray-700"
              aria-label={`Dismiss all alerts for ${cameraName}`}
            >
              <X className="h-4 w-4" />
              Dismiss All
            </button>
          )}
        </div>
      </div>

      {/* Content panel */}
      <Transition
        as={Fragment}
        show={isOpen}
        enter="transition duration-200 ease-out"
        enterFrom="transform opacity-0 -translate-y-2"
        enterTo="transform opacity-100 translate-y-0"
        leave="transition duration-150 ease-in"
        leaveFrom="transform opacity-100 translate-y-0"
        leaveTo="transform opacity-0 -translate-y-2"
      >
        <div className="rounded-b-lg border-t border-gray-800 bg-[#1A1A1A] p-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
            {sortedAlerts.map((alert) => (
              <EventCard key={alert.id} {...getEventCardProps(alert)} />
            ))}
          </div>

          {alerts.length === 0 && (
            <p className="py-4 text-center text-sm text-gray-500">No alerts for this camera.</p>
          )}
        </div>
      </Transition>
    </div>
  );
}

/**
 * MobileEventCard - Compact event card optimized for mobile devices
 *
 * Single-line layout with thumbnail, summary, and actions.
 * Supports swipe gestures for quick actions (e.g., swipe left to delete).
 * All touch targets meet minimum 44px size requirement.
 */

import { Clock, Eye, Trash, Timer } from 'lucide-react';
import { memo } from 'react';

import { useSwipeGesture } from '../../hooks/useSwipeGesture';
import { getRiskLevel } from '../../utils/risk';
import { formatDuration } from '../../utils/time';
import ObjectTypeBadge from '../common/ObjectTypeBadge';
import RiskBadge from '../common/RiskBadge';

import type { Detection } from './EventCard';

export interface MobileEventCardAction {
  label: string;
  onClick: (eventId: string) => void;
  icon: 'eye' | 'trash';
}

export interface MobileEventCardProps {
  id: string;
  timestamp: string;
  camera_name: string;
  risk_score: number;
  risk_label: string;
  summary: string;
  thumbnail_url?: string;
  detections: Detection[];
  started_at?: string;
  ended_at?: string | null;
  onSwipeLeft?: (eventId: string) => void;
  onSwipeRight?: (eventId: string) => void;
  onClick?: (eventId: string) => void;
  actions?: MobileEventCardAction[];
  className?: string;
}

/**
 * MobileEventCard component displays a security event in compact mobile format
 */
const MobileEventCard = memo(function MobileEventCard({
  id,
  timestamp,
  camera_name,
  risk_score,
  summary,
  thumbnail_url,
  detections,
  started_at,
  ended_at,
  onSwipeLeft,
  onSwipeRight,
  onClick,
  actions = [],
  className = '',
}: MobileEventCardProps) {
  // Format timestamp
  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);

      if (diffMins < 60) {
        return diffMins <= 1 ? 'Just now' : `${diffMins}m ago`;
      }

      const diffHours = Math.floor(diffMins / 60);
      if (diffHours < 24) {
        return `${diffHours}h ago`;
      }

      const diffDays = Math.floor(diffHours / 24);
      return `${diffDays}d ago`;
    } catch {
      return isoString;
    }
  };

  // Get risk level
  const riskLevel = getRiskLevel(risk_score);

  // Get unique object types
  const uniqueObjectTypes = Array.from(new Set(detections.map((d) => d.label.toLowerCase())));

  // Setup swipe gesture
  const swipeRef = useSwipeGesture({
    onSwipe: (direction) => {
      if (direction === 'left' && onSwipeLeft) {
        onSwipeLeft(id);
      } else if (direction === 'right' && onSwipeRight) {
        onSwipeRight(id);
      }
    },
  });

  // Handle card click
  const handleClick = (e?: React.MouseEvent<HTMLDivElement> | React.KeyboardEvent<HTMLDivElement>) => {
    // Don't trigger if clicking on action buttons
    if (e) {
      const target = e.target as HTMLElement;
      if (target.closest('button')) {
        return;
      }
    }

    if (onClick) {
      onClick(id);
    }
  };

  // Get icon component for action
  const getActionIcon = (icon: string) => {
    switch (icon) {
      case 'eye':
        return Eye;
      case 'trash':
        return Trash;
      default:
        return Eye;
    }
  };

  return (
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <div
      ref={swipeRef}
      data-testid={`event-card-${id}`}
      className={`flex min-h-[44px] flex-row items-center gap-3 rounded-lg border border-gray-800 bg-[#1F1F1F] p-3 shadow transition-colors ${onClick ? 'cursor-pointer hover:bg-[#252525]' : ''} ${className}`}
      onClick={handleClick}
      onKeyDown={(e) => {
        if (onClick && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          handleClick();
        }
      }}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      {/* Thumbnail */}
      {thumbnail_url && (
        <div className="h-16 w-16 flex-shrink-0 overflow-hidden rounded-md bg-black">
          <img
            src={thumbnail_url}
            alt={`${camera_name} at ${formatTimestamp(timestamp)}`}
            className="h-full w-full object-cover"
          />
        </div>
      )}

      {/* Content */}
      <div className="min-w-0 flex-1">
        {/* Header row */}
        <div className="mb-1 flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <h3 className="truncate text-sm font-semibold text-white" title={camera_name}>
              {camera_name}
            </h3>
            <div className="flex items-center gap-2 text-xs text-text-secondary">
              <Clock className="h-3 w-3 flex-shrink-0" />
              <span>{formatTimestamp(timestamp)}</span>
              {(started_at || ended_at !== undefined) && (
                <>
                  <span>•</span>
                  <Timer className="h-3 w-3 flex-shrink-0" />
                  <span>{formatDuration(started_at || timestamp, ended_at ?? null)}</span>
                </>
              )}
            </div>
          </div>
          <RiskBadge level={riskLevel} score={risk_score} showScore={true} size="sm" />
        </div>

        {/* Summary */}
        <p className="mb-2 line-clamp-2 text-xs text-gray-300">{summary}</p>

        {/* Object badges */}
        {uniqueObjectTypes.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {uniqueObjectTypes.map((type) => (
              <ObjectTypeBadge key={type} type={type} size="sm" />
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      {actions.length > 0 && (
        <div className="flex flex-col gap-2">
          {actions.map((action) => {
            const Icon = getActionIcon(action.icon);
            return (
              <button
                key={action.label}
                onClick={(e) => {
                  e.stopPropagation();
                  action.onClick(id);
                }}
                className="flex h-11 w-11 items-center justify-center rounded-lg bg-gray-800 text-gray-400 transition-colors hover:bg-gray-700 hover:text-white"
                aria-label={`${action.label} ${id}`}
                type="button"
              >
                <Icon className="h-5 w-5" />
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
});

export default MobileEventCard;

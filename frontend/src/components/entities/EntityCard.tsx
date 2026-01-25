import { AlertTriangle, Camera, Car, Clock, Eye, Flame, ShieldCheck, User } from 'lucide-react';
import { memo, useState } from 'react';

import PlaceholderThumbnail from './PlaceholderThumbnail';

import type { TrustStatus } from '../../services/api';

/**
 * Supported entity types for the EntityCard component.
 * Note: The API may return other string values, which will be handled as 'vehicle' by default.
 */
export type EntityType = 'person' | 'vehicle';

/**
 * Activity tier based on sighting count and recency.
 * - hot: 20+ sightings AND seen within 24 hours
 * - active: 10+ sightings OR seen within 48 hours
 * - normal: 3+ sightings
 * - cold: less than 3 sightings
 */
export type ActivityTier = 'hot' | 'active' | 'normal' | 'cold';

/**
 * Calculate activity tier based on appearance count and last seen time.
 * @param appearanceCount - Number of times the entity has been seen
 * @param lastSeen - ISO timestamp of when the entity was last seen
 * @param now - Current timestamp (optional, defaults to Date.now() for testing)
 * @returns The calculated activity tier
 */
// eslint-disable-next-line react-refresh/only-export-components
export function getActivityTier(
  appearanceCount: number,
  lastSeen: string,
  now: number = Date.now()
): ActivityTier {
  const lastSeenTime = new Date(lastSeen).getTime();
  const hoursSinceLastSeen = (now - lastSeenTime) / (1000 * 60 * 60);

  // Hot: 20+ sightings AND seen within 24 hours
  if (appearanceCount >= 20 && hoursSinceLastSeen <= 24) {
    return 'hot';
  }

  // Active: 10+ sightings OR seen within 48 hours
  if (appearanceCount >= 10 || hoursSinceLastSeen <= 48) {
    return 'active';
  }

  // Normal: 3+ sightings
  if (appearanceCount >= 3) {
    return 'normal';
  }

  // Cold: less than 3 sightings
  return 'cold';
}

/**
 * CSS classes for each activity tier applied to the card container.
 */
// eslint-disable-next-line react-refresh/only-export-components
export const tierStyles: Record<ActivityTier, string> = {
  hot: 'ring-2 ring-red-500 scale-105 z-10',
  active: 'ring-1 ring-[#76B900]',
  normal: '',
  cold: 'opacity-70',
};

export interface EntityCardProps {
  id: string;
  /** Entity type - accepts string from API (values other than 'person' treated as 'vehicle') */
  entity_type: string;
  first_seen: string;
  last_seen: string;
  appearance_count: number;
  cameras_seen?: string[];
  thumbnail_url?: string | null;
  /** Trust status for the entity - 'trusted', 'untrusted', or 'unclassified' (default) */
  trust_status?: TrustStatus | null;
  /** Activity tier for visual weight - calculated from appearance_count and last_seen */
  activity_tier?: ActivityTier;
  onClick?: (entityId: string) => void;
  className?: string;
}

/**
 * EntityCard component displays a tracked entity (person or vehicle) with
 * summary information including appearance count, cameras seen, and timestamps.
 */
const EntityCard = memo(function EntityCard({
  id,
  entity_type,
  first_seen,
  last_seen,
  appearance_count,
  cameras_seen = [],
  thumbnail_url = null,
  trust_status = null,
  activity_tier,
  onClick,
  className = '',
}: EntityCardProps) {
  // Track image loading error state
  const [imageError, setImageError] = useState(false);

  // Normalize entity_type to known type ('person' | 'vehicle')
  const normalizedType: EntityType = entity_type === 'person' ? 'person' : 'vehicle';

  // Trust status is already normalized by the parent component
  const normalizedTrustStatus = trust_status;

  // Get tier styling (empty string if no tier or normal tier)
  const tierClassName = activity_tier ? tierStyles[activity_tier] : '';

  // Format timestamp to relative time
  const formatTimestamp = (isoString: string): string => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now.getTime() - date.getTime();
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return 'Just now';
      if (diffMins < 60) return `${diffMins} minutes ago`;
      if (diffHours < 24) return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
      if (diffDays < 7) return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;

      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      });
    } catch {
      return isoString;
    }
  };

  // Truncate entity ID for display
  const truncateId = (entityId: string): string => {
    return entityId.length > 12 ? `${entityId.substring(0, 12)}...` : entityId;
  };

  // Get entity type display label
  const entityTypeLabel = normalizedType === 'person' ? 'Person' : 'Vehicle';

  // Handle card click
  const handleClick = () => {
    if (onClick) {
      onClick(id);
    }
  };

  // Handle keyboard navigation
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.key === 'Enter' || e.key === ' ') && onClick) {
      e.preventDefault();
      onClick(id);
    }
  };

  const isClickable = !!onClick;

  return (
    <div
      className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 shadow-lg transition-all hover:border-gray-700 ${isClickable ? 'cursor-pointer hover:bg-[#252525]' : ''} ${tierClassName} ${className}`}
      data-testid="entity-card"
      data-activity-tier={activity_tier}
      {...(isClickable && {
        onClick: handleClick,
        onKeyDown: handleKeyDown,
        role: 'button',
        tabIndex: 0,
        'aria-label': `View entity ${entityTypeLabel} ${truncateId(id)}`,
      })}
    >
      {/* Header: Entity type badge, trust badge, and ID */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Entity type badge */}
          <span className="flex items-center gap-1.5 rounded-full bg-[#76B900]/20 px-2.5 py-1 text-xs font-semibold text-[#76B900]">
            {normalizedType === 'person' ? (
              <User className="lucide-user h-3.5 w-3.5" />
            ) : (
              <Car className="lucide-car h-3.5 w-3.5" />
            )}
            {entityTypeLabel}
          </span>
          {/* Trust status badge */}
          {normalizedTrustStatus === 'trusted' && (
            <span
              className="trusted flex items-center gap-1 rounded-full bg-green-500/20 px-2 py-0.5 text-xs font-medium text-green-400"
              data-testid="trust-badge-trusted"
              aria-label="Trusted entity"
            >
              <ShieldCheck className="h-3 w-3" />
              <span className="sr-only">Trust status: </span>
              Trusted
            </span>
          )}
          {normalizedTrustStatus === 'untrusted' && (
            <span
              className="suspicious warning flex items-center gap-1 rounded-full bg-amber-500/20 px-2 py-0.5 text-xs font-medium text-amber-400"
              data-testid="trust-badge-suspicious"
              aria-label="Suspicious entity"
            >
              <AlertTriangle className="h-3 w-3" />
              <span className="sr-only">Trust status: </span>
              Suspicious
            </span>
          )}
          {/* Activity tier badges */}
          {activity_tier === 'hot' && (
            <span
              className="flex animate-pulse items-center gap-1 rounded-full bg-red-500/20 px-2 py-0.5 text-xs font-bold text-red-400"
              data-testid="activity-badge-hot"
              aria-label="Hot activity - frequently seen recently"
            >
              <Flame className="h-3 w-3" />
              HOT
            </span>
          )}
          {activity_tier === 'active' && (
            <span
              className="flex items-center gap-1 rounded-full bg-[#76B900]/20 px-2 py-0.5 text-xs font-medium text-[#76B900]"
              data-testid="activity-badge-active"
              aria-label="Active - recently seen"
            >
              Active
            </span>
          )}
        </div>
        {/* Entity ID */}
        <span className="text-xs text-text-muted" title={id}>
          {truncateId(id)}
        </span>
      </div>

      {/* Thumbnail or placeholder */}
      <div
        data-testid="thumbnail-container"
        className="mb-3 flex h-32 items-center justify-center overflow-hidden rounded-md bg-black/40"
      >
        {thumbnail_url && !imageError ? (
          <img
            src={thumbnail_url}
            alt={`${entityTypeLabel} entity thumbnail`}
            className="h-full w-full object-cover"
            onError={() => setImageError(true)}
          />
        ) : (
          <PlaceholderThumbnail entityType={normalizedType} />
        )}
      </div>

      {/* Stats: Appearances and Cameras */}
      <div className="mb-3 flex items-center justify-around">
        {/* Appearances */}
        <div className="flex flex-col items-center">
          <div className="flex items-center gap-1 text-lg font-bold text-white">
            <Eye className="h-4 w-4 text-text-secondary" />
            <span>{appearance_count}</span>
          </div>
          <span className="text-xs text-text-secondary">
            {appearance_count === 1 ? 'appearance' : 'appearances'}
          </span>
        </div>

        {/* Divider */}
        <div className="h-8 w-px bg-gray-700" />

        {/* Cameras */}
        <div className="flex flex-col items-center" title={cameras_seen.join(', ')}>
          <div className="flex items-center gap-1 text-lg font-bold text-white">
            <Camera className="h-4 w-4 text-text-secondary" />
            <span>{cameras_seen.length}</span>
          </div>
          <span className="text-xs text-text-secondary">
            {cameras_seen.length === 1 ? 'camera' : 'cameras'}
          </span>
        </div>
      </div>

      {/* Timestamps */}
      <div className="space-y-1.5 text-xs text-text-secondary">
        <div className="flex items-center gap-1.5">
          <Clock className="h-3.5 w-3.5" />
          <span>Last seen:</span>
          <span className="text-gray-300">{formatTimestamp(last_seen)}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Clock className="h-3.5 w-3.5" />
          <span>First seen:</span>
          <span className="text-gray-300">{formatTimestamp(first_seen)}</span>
        </div>
      </div>
    </div>
  );
});

export default EntityCard;

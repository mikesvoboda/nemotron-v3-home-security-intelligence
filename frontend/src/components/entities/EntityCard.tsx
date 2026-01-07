import { Camera, Car, Clock, Eye, User } from 'lucide-react';
import { memo } from 'react';

export interface EntityCardProps {
  id: string;
  entity_type: 'person' | 'vehicle';
  first_seen: string;
  last_seen: string;
  appearance_count: number;
  cameras_seen: string[];
  thumbnail_url: string | null;
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
  cameras_seen,
  thumbnail_url,
  onClick,
  className = '',
}: EntityCardProps) {
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
  const entityTypeLabel = entity_type === 'person' ? 'Person' : 'Vehicle';

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
      className={`rounded-lg border border-gray-800 bg-[#1F1F1F] p-4 shadow-lg transition-all hover:border-gray-700 ${isClickable ? 'cursor-pointer hover:bg-[#252525]' : ''} ${className}`}
      data-testid="entity-card"
      {...(isClickable && {
        onClick: handleClick,
        onKeyDown: handleKeyDown,
        role: 'button',
        tabIndex: 0,
        'aria-label': `View entity ${entityTypeLabel} ${truncateId(id)}`,
      })}
    >
      {/* Header: Entity type badge and ID */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Entity type badge */}
          <span className="flex items-center gap-1.5 rounded-full bg-[#76B900]/20 px-2.5 py-1 text-xs font-semibold text-[#76B900]">
            {entity_type === 'person' ? (
              <User className="lucide-user h-3.5 w-3.5" />
            ) : (
              <Car className="lucide-car h-3.5 w-3.5" />
            )}
            {entityTypeLabel}
          </span>
        </div>
        {/* Entity ID */}
        <span className="text-xs text-text-muted" title={id}>
          {truncateId(id)}
        </span>
      </div>

      {/* Thumbnail or placeholder */}
      <div className="mb-3 flex h-32 items-center justify-center overflow-hidden rounded-md bg-black/40">
        {thumbnail_url ? (
          <img
            src={thumbnail_url}
            alt={`${entityTypeLabel} entity thumbnail`}
            className="h-full w-full object-cover"
          />
        ) : (
          <div
            data-testid="entity-placeholder"
            className="flex h-full w-full items-center justify-center text-gray-600"
          >
            {entity_type === 'person' ? (
              <User className="h-16 w-16" />
            ) : (
              <Car className="h-16 w-16" />
            )}
          </div>
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
        <div
          className="flex flex-col items-center"
          title={cameras_seen.join(', ')}
        >
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

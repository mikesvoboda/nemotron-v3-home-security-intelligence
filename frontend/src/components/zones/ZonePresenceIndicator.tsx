/**
 * ZonePresenceIndicator - Component for displaying household member presence in a zone
 *
 * This component shows avatars/icons of members currently present in a zone,
 * with visual indicators for active presence (pulse animation) and stale
 * presence (fade effect).
 *
 * Features:
 * - Avatar display with initials for members
 * - Pulse animation for active presence (detected within 30s)
 * - Fade effect for stale presence (detected more than 5 min ago)
 * - Count badge when members exceed maxAvatars
 * - Tooltip showing member names and time since detection
 *
 * @module components/zones/ZonePresenceIndicator
 *
 * @example
 * ```tsx
 * <ZonePresenceIndicator
 *   zoneId="zone-123"
 *   maxAvatars={3}
 *   size="md"
 *   showCount
 * />
 * ```
 */

import { clsx } from 'clsx';
import { Users } from 'lucide-react';

import { getInitials, formatTimeSince } from './zonePresenceUtils';
import { useZonePresence, type ZonePresenceMember } from '../../hooks/useZonePresence';

// ============================================================================
// Types
// ============================================================================

/**
 * Avatar size variants.
 */
export type AvatarSize = 'sm' | 'md' | 'lg';

/**
 * Props for the ZonePresenceIndicator component.
 */
export interface ZonePresenceIndicatorProps {
  /** ID of the zone to track presence for */
  zoneId: string;
  /** Maximum number of avatars to display before showing count badge */
  maxAvatars?: number;
  /** Whether to show the count badge for overflow members */
  showCount?: boolean;
  /** Size variant for avatars */
  size?: AvatarSize;
  /** Additional CSS classes */
  className?: string;
}

// ============================================================================
// Constants
// ============================================================================

/** Size configuration for avatar variants */
const SIZE_CONFIG: Record<AvatarSize, { container: string; text: string; badge: string }> = {
  sm: {
    container: 'h-6 w-6',
    text: 'text-xs',
    badge: 'text-[10px] h-4 min-w-4',
  },
  md: {
    container: 'h-8 w-8',
    text: 'text-sm',
    badge: 'text-xs h-5 min-w-5',
  },
  lg: {
    container: 'h-10 w-10',
    text: 'text-base',
    badge: 'text-sm h-6 min-w-6',
  },
};

/** Role-based color mapping */
const ROLE_COLORS: Record<string, string> = {
  resident: 'bg-primary text-white',
  family: 'bg-blue-500 text-white',
  service_worker: 'bg-amber-500 text-white',
  frequent_visitor: 'bg-green-500 text-white',
};

// ============================================================================
// Subcomponents
// ============================================================================

/**
 * Individual avatar for a member.
 */
interface MemberAvatarProps {
  member: ZonePresenceMember;
  size: AvatarSize;
  showTooltip?: boolean;
}

function MemberAvatar({ member, size, showTooltip = true }: MemberAvatarProps) {
  const sizeConfig = SIZE_CONFIG[size];
  const roleColor = ROLE_COLORS[member.role] || ROLE_COLORS.resident;
  const initials = getInitials(member.name);
  const timeSince = formatTimeSince(member.lastSeen);

  return (
    <div
      className="group relative"
      title={showTooltip ? `${member.name} - ${timeSince}` : undefined}
      data-testid={`presence-avatar-${member.id}`}
    >
      <div
        className={clsx(
          'relative flex items-center justify-center rounded-full border-2 border-gray-800 font-medium transition-opacity',
          sizeConfig.container,
          sizeConfig.text,
          roleColor,
          member.isStale && 'opacity-50',
          member.isActive && 'ring-2 ring-primary ring-offset-2 ring-offset-gray-900'
        )}
      >
        {/* Pulse animation for active members */}
        {member.isActive && (
          <span
            className="absolute inset-0 animate-ping rounded-full bg-primary opacity-30"
            data-testid={`presence-pulse-${member.id}`}
          />
        )}
        <span className="relative z-10">{initials}</span>
      </div>

      {/* Tooltip on hover */}
      {showTooltip && (
        <div
          className={clsx(
            'pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 whitespace-nowrap rounded bg-gray-900 px-2 py-1 text-xs text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100',
            'border border-gray-700'
          )}
          role="tooltip"
        >
          <div className="font-medium">{member.name}</div>
          <div className="text-gray-400">{timeSince}</div>
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
        </div>
      )}
    </div>
  );
}

/**
 * Count badge for overflow members.
 */
interface CountBadgeProps {
  count: number;
  members: ZonePresenceMember[];
  size: AvatarSize;
}

function CountBadge({ count, members, size }: CountBadgeProps) {
  const sizeConfig = SIZE_CONFIG[size];
  const tooltipContent = members.map((m) => `${m.name} (${formatTimeSince(m.lastSeen)})`).join('\n');

  return (
    <div
      className="group relative"
      title={tooltipContent}
      data-testid="presence-count-badge"
    >
      <div
        className={clsx(
          'flex items-center justify-center rounded-full border-2 border-gray-800 bg-gray-700 px-1 font-medium text-gray-200',
          sizeConfig.badge
        )}
      >
        +{count}
      </div>

      {/* Tooltip on hover */}
      <div
        className={clsx(
          'pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 whitespace-pre rounded bg-gray-900 px-2 py-1 text-xs text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100',
          'border border-gray-700'
        )}
        role="tooltip"
      >
        {members.map((m) => (
          <div key={m.id} className="py-0.5">
            <span className="font-medium">{m.name}</span>
            <span className="text-gray-400"> - {formatTimeSince(m.lastSeen)}</span>
          </div>
        ))}
        <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900" />
      </div>
    </div>
  );
}

/**
 * Empty state when no one is present.
 */
interface EmptyStateProps {
  size: AvatarSize;
}

function EmptyState({ size }: EmptyStateProps) {
  const sizeConfig = SIZE_CONFIG[size];

  return (
    <div
      className={clsx(
        'flex items-center justify-center rounded-full border-2 border-dashed border-gray-600 bg-gray-800/50 text-gray-500',
        sizeConfig.container
      )}
      title="No one present"
      data-testid="presence-empty-state"
    >
      <Users className={clsx(size === 'sm' ? 'h-3 w-3' : size === 'md' ? 'h-4 w-4' : 'h-5 w-5')} />
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * ZonePresenceIndicator component.
 *
 * Displays avatars of household members currently present in a zone,
 * with visual indicators for active and stale presence.
 *
 * @param props - Component props
 * @returns Rendered component
 */
export default function ZonePresenceIndicator({
  zoneId,
  maxAvatars = 3,
  showCount = true,
  size = 'md',
  className,
}: ZonePresenceIndicatorProps) {
  const { members, isLoading, presentCount } = useZonePresence(zoneId);

  // Loading state
  if (isLoading) {
    return (
      <div
        className={clsx('flex items-center gap-1', className)}
        data-testid="presence-loading"
      >
        <div
          className={clsx(
            'animate-pulse rounded-full bg-gray-700',
            SIZE_CONFIG[size].container
          )}
        />
      </div>
    );
  }

  // Empty state
  if (presentCount === 0) {
    return (
      <div
        className={clsx('flex items-center gap-1', className)}
        data-testid="presence-container"
      >
        <EmptyState size={size} />
      </div>
    );
  }

  // Split members into visible and overflow
  const visibleMembers = members.slice(0, maxAvatars);
  const overflowMembers = members.slice(maxAvatars);
  const hasOverflow = overflowMembers.length > 0;

  return (
    <div
      className={clsx('flex items-center', className)}
      data-testid="presence-container"
      role="group"
      aria-label={`${presentCount} ${presentCount === 1 ? 'person' : 'people'} present`}
    >
      {/* Stacked avatars */}
      <div className="flex -space-x-2">
        {visibleMembers.map((member) => (
          <MemberAvatar key={member.id} member={member} size={size} />
        ))}

        {/* Overflow count badge */}
        {hasOverflow && showCount && (
          <CountBadge
            count={overflowMembers.length}
            members={overflowMembers}
            size={size}
          />
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Exports
// ============================================================================

// Export subcomponents for testing purposes
// Note: getInitials and formatTimeSince are not exported to avoid react-refresh warnings
// They are tested through component tests
export { MemberAvatar, CountBadge, EmptyState };

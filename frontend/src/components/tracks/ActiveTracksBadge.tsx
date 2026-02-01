import { clsx } from 'clsx';

export interface ActiveTracksBadgeProps {
  /** Number of active tracks */
  count: number;
  /** Whether data is loading */
  isLoading?: boolean;
  /** Optional className for additional styling */
  className?: string;
}

/**
 * Small badge showing the number of active tracks.
 *
 * Designed to be displayed on camera cards to show real-time
 * tracking activity. Shows a pulsing animation when tracks are active.
 */
export function ActiveTracksBadge({
  count,
  isLoading = false,
  className = '',
}: ActiveTracksBadgeProps) {
  if (isLoading) {
    return (
      <span
        className={clsx(
          'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
          'bg-gray-500/10 text-gray-400',
          className
        )}
        data-testid="active-tracks-badge-loading"
      >
        ...
      </span>
    );
  }

  if (count === 0) {
    return null; // Don't show badge when no active tracks
  }

  return (
    <span
      className={clsx(
        'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
        'bg-blue-500/10 text-blue-400',
        className
      )}
      role="status"
      aria-label={`${count} active ${count === 1 ? 'track' : 'tracks'}`}
      data-testid="active-tracks-badge"
    >
      <span
        className="w-2 h-2 mr-1.5 rounded-full bg-blue-500 animate-pulse"
        aria-hidden="true"
      />
      {count} active
    </span>
  );
}

export default ActiveTracksBadge;

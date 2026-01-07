/**
 * Time and duration utility functions for formatting timestamps and durations
 */

/**
 * Format duration between two timestamps in human-readable format
 * @param startedAt - ISO timestamp string when event started
 * @param endedAt - ISO timestamp string when event ended (null if ongoing)
 * @returns Formatted duration string (e.g., "2m 30s", "1h 15m", "ongoing")
 */
export function formatDuration(startedAt: string, endedAt: string | null): string {
  try {
    const start = new Date(startedAt);
    const end = endedAt ? new Date(endedAt) : new Date();

    // Check for invalid dates
    if (isNaN(start.getTime()) || isNaN(end.getTime())) {
      return 'unknown';
    }

    // Calculate duration in milliseconds
    const durationMs = end.getTime() - start.getTime();

    // If duration is negative, return "0s"
    if (durationMs < 0) {
      return '0s';
    }

    // If event is ongoing (no ended_at), show "ongoing" for recent events
    if (!endedAt) {
      const now = new Date();
      const timeSinceStart = now.getTime() - start.getTime();

      // If event started within last 5 minutes, show "ongoing"
      if (timeSinceStart < 5 * 60 * 1000) {
        return 'ongoing';
      }
      // Otherwise show duration with "ongoing" suffix
      return `${formatDurationValue(timeSinceStart)} (ongoing)`;
    }

    return formatDurationValue(durationMs);
  } catch {
    return 'unknown';
  }
}

/**
 * Format duration value in milliseconds to human-readable string
 * @param durationMs - Duration in milliseconds
 * @returns Formatted string (e.g., "2m 30s", "1h 15m 30s")
 */
function formatDurationValue(durationMs: number): string {
  const seconds = Math.floor(durationMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  const remainingSeconds = seconds % 60;
  const remainingMinutes = minutes % 60;
  const remainingHours = hours % 24;

  // Format based on duration magnitude
  if (days > 0) {
    // Show days and hours for durations over a day
    if (remainingHours > 0) {
      return `${days}d ${remainingHours}h`;
    }
    return `${days}d`;
  }

  if (hours > 0) {
    // Show hours and minutes for durations over an hour
    if (remainingMinutes > 0) {
      return `${hours}h ${remainingMinutes}m`;
    }
    return `${hours}h`;
  }

  if (minutes > 0) {
    // Show minutes and seconds for durations over a minute
    if (remainingSeconds > 0) {
      return `${minutes}m ${remainingSeconds}s`;
    }
    return `${minutes}m`;
  }

  // Show seconds for durations under a minute
  return `${seconds}s`;
}

/**
 * Get a short label for duration display
 * @param startedAt - ISO timestamp string when event started
 * @param endedAt - ISO timestamp string when event ended (null if ongoing)
 * @returns Short label like "2m 30s" or "ongoing"
 */
export function getDurationLabel(startedAt: string, endedAt: string | null): string {
  return formatDuration(startedAt, endedAt);
}

/**
 * Check if an event is currently ongoing
 * @param endedAt - ISO timestamp string when event ended (null if ongoing)
 * @returns True if event is ongoing, false otherwise
 */
export function isEventOngoing(endedAt: string | null): boolean {
  return endedAt === null;
}

/**
 * Format a timestamp as relative time (e.g., "2 hours ago", "3 days ago")
 * @param timestamp - ISO timestamp string or null
 * @returns Formatted relative time string or "Never" if null
 */
export function formatRelativeTime(timestamp: string | null): string {
  if (!timestamp) {
    return 'Never';
  }

  try {
    const date = new Date(timestamp);
    const now = new Date();

    if (isNaN(date.getTime())) {
      return 'Invalid date';
    }

    const diffMs = now.getTime() - date.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSeconds < 60) {
      return 'Just now';
    }

    if (diffMinutes < 60) {
      return diffMinutes === 1 ? '1 minute ago' : `${diffMinutes} minutes ago`;
    }

    if (diffHours < 24) {
      return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
    }

    if (diffDays < 30) {
      return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;
    }

    // For older dates, show absolute date
    return date.toLocaleDateString();
  } catch {
    return 'Invalid date';
  }
}

/**
 * Check if a timestamp is stale (older than specified hours)
 * @param timestamp - ISO timestamp string or null
 * @param staleAfterHours - Number of hours after which timestamp is considered stale (default: 24)
 * @returns True if timestamp is stale, false otherwise
 */
export function isTimestampStale(timestamp: string | null, staleAfterHours: number = 24): boolean {
  if (!timestamp) {
    return true;
  }

  try {
    const date = new Date(timestamp);
    const now = new Date();

    if (isNaN(date.getTime())) {
      return true;
    }

    const diffMs = now.getTime() - date.getTime();
    const diffHours = diffMs / (1000 * 60 * 60);

    return diffHours > staleAfterHours;
  } catch {
    return true;
  }
}

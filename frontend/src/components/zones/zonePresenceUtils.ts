/**
 * Utility functions for ZonePresenceIndicator component
 *
 * Extracted to separate file for react-refresh compatibility
 * and better testability.
 *
 * @module components/zones/zonePresenceUtils
 */

/**
 * Get initials from a name.
 *
 * @param name - Full name to extract initials from
 * @returns Two-character initials in uppercase
 *
 * @example
 * getInitials('John Doe') // 'JD'
 * getInitials('John') // 'JO'
 * getInitials('John Middle Doe') // 'JD'
 */
export function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

/**
 * Format time since last seen into human-readable string.
 *
 * @param timestamp - ISO timestamp string
 * @returns Human-readable time difference string
 *
 * @example
 * formatTimeSince('2025-01-21T12:00:00Z') // 'Just now', '5m ago', '2h ago', etc.
 */
export function formatTimeSince(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diffMs = now - then;

  const seconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (seconds < 60) {
    return 'Just now';
  } else if (minutes < 60) {
    return `${minutes}m ago`;
  } else if (hours < 24) {
    return `${hours}h ago`;
  } else {
    return `${Math.floor(hours / 24)}d ago`;
  }
}

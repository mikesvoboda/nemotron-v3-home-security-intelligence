/**
 * Snooze utility functions for managing event snooze state
 *
 * Provides utilities for checking snooze status and formatting snooze
 * information for display in the UI.
 */

/**
 * Snooze duration constants in milliseconds
 */
export const SNOOZE_DURATIONS = {
  '15min': 15 * 60 * 1000,
  '1hour': 60 * 60 * 1000,
  '4hours': 4 * 60 * 60 * 1000,
  '24hours': 24 * 60 * 60 * 1000,
} as const;

/**
 * Snooze duration options for UI display
 */
export const SNOOZE_OPTIONS = [
  { label: '15 minutes', value: 15 * 60 },
  { label: '1 hour', value: 60 * 60 },
  { label: '4 hours', value: 4 * 60 * 60 },
  { label: '24 hours', value: 24 * 60 * 60 },
] as const;

/**
 * Check if an event is currently snoozed
 *
 * An event is considered snoozed if snooze_until is set and is
 * in the future (greater than the current time).
 *
 * @param snoozeUntil - ISO timestamp string or null
 * @returns True if event is currently snoozed, false otherwise
 */
export function isSnoozed(snoozeUntil: string | null | undefined): boolean {
  if (!snoozeUntil) {
    return false;
  }

  try {
    const snoozeDate = new Date(snoozeUntil);
    const now = new Date();

    if (isNaN(snoozeDate.getTime())) {
      return false;
    }

    return snoozeDate.getTime() > now.getTime();
  } catch {
    return false;
  }
}

/**
 * Get the remaining snooze time in milliseconds
 *
 * @param snoozeUntil - ISO timestamp string or null
 * @returns Remaining time in milliseconds, or 0 if not snoozed
 */
export function getSnoozeRemainingMs(snoozeUntil: string | null | undefined): number {
  if (!snoozeUntil) {
    return 0;
  }

  try {
    const snoozeDate = new Date(snoozeUntil);
    const now = new Date();

    if (isNaN(snoozeDate.getTime())) {
      return 0;
    }

    const remaining = snoozeDate.getTime() - now.getTime();
    return remaining > 0 ? remaining : 0;
  } catch {
    return 0;
  }
}

/**
 * Format the snooze end time for display
 *
 * @param snoozeUntil - ISO timestamp string or null
 * @returns Formatted time string (e.g., "3:45 PM") or empty string if not snoozed
 */
export function formatSnoozeEndTime(snoozeUntil: string | null | undefined): string {
  if (!snoozeUntil || !isSnoozed(snoozeUntil)) {
    return '';
  }

  try {
    const snoozeDate = new Date(snoozeUntil);

    if (isNaN(snoozeDate.getTime())) {
      return '';
    }

    return snoozeDate.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return '';
  }
}

/**
 * Format the remaining snooze duration for display
 *
 * @param snoozeUntil - ISO timestamp string or null
 * @returns Formatted duration string (e.g., "15 min remaining", "1h 30m remaining")
 */
export function formatSnoozeRemaining(snoozeUntil: string | null | undefined): string {
  const remainingMs = getSnoozeRemainingMs(snoozeUntil);

  if (remainingMs <= 0) {
    return '';
  }

  const remainingSeconds = Math.floor(remainingMs / 1000);
  const remainingMinutes = Math.floor(remainingSeconds / 60);
  const remainingHours = Math.floor(remainingMinutes / 60);

  if (remainingHours >= 1) {
    const mins = remainingMinutes % 60;
    if (mins > 0) {
      return `${remainingHours}h ${mins}m remaining`;
    }
    return `${remainingHours}h remaining`;
  }

  if (remainingMinutes >= 1) {
    return `${remainingMinutes} min remaining`;
  }

  return 'Less than 1 min remaining';
}

/**
 * Get a full snooze status message
 *
 * @param snoozeUntil - ISO timestamp string or null
 * @returns Status message (e.g., "Snoozed until 3:45 PM (15 min remaining)")
 */
export function getSnoozeStatusMessage(snoozeUntil: string | null | undefined): string {
  if (!isSnoozed(snoozeUntil)) {
    return '';
  }

  const endTime = formatSnoozeEndTime(snoozeUntil);
  const remaining = formatSnoozeRemaining(snoozeUntil);

  if (endTime && remaining) {
    return `Snoozed until ${endTime} (${remaining})`;
  }

  if (endTime) {
    return `Snoozed until ${endTime}`;
  }

  return 'Snoozed';
}

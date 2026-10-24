/**
 * Frontend mirror of the Trash purge rule (F4.3, spec 4n-trash.md).
 *
 * The daily job purges each trashed event at the earlier of
 * `deleted_at + trash_retention_days` and `started_at + retention_days`
 * (backend/services/event_purger.py `purge_deadline_for_event`). Trash shows
 * that date, so this module computes the same deadline from the same inputs —
 * if the two ever disagree, Trash is lying about when an event disappears.
 *
 * `trash_retention_days = 0` turns off only the Trash clock: the general
 * retention deadline (`started_at + retention_days`) still purges the event.
 * The backend field validates `ge=0`, so a negative value cannot arrive, but
 * the mirror treats it the same way (off) rather than adding days.
 *
 * @module utils/trashPurge
 */

/** The Trash clock is disabled and only general retention purges the event. */
export const TRASH_RETENTION_DISABLED = 0;

/** Backend default when /api/system/config predates B4.4 and omits the field. */
export const DEFAULT_TRASH_RETENTION_DAYS = 30;

export interface TrashPurgeConfig {
  /** General event retention (days); purges at started_at + this. */
  retentionDays: number;
  /**
   * Trash clock (days); purges at deleted_at + this, unless disabled (<= 0).
   * May be undefined when the backend predates the field — callers should
   * resolve that to DEFAULT_TRASH_RETENTION_DAYS before calling.
   */
  trashRetentionDays: number | undefined;
}

/**
 * Compute when a trashed event will be purged, mirroring
 * `purge_deadline_for_event` (event_purger.py:59-73).
 *
 * @param deletedAt - when the event entered Trash
 * @param startedAt - when the event itself began (general retention anchor)
 * @param config - the two retention day counts from /api/system/config
 * @returns the purge deadline, or null when no clock applies
 *   (retention_days must be >= 1 per the backend schema, so null in practice
 *   only guards against malformed config)
 */
export function purgeDeadlineForEvent(
  deletedAt: Date | string,
  startedAt: Date | string,
  config: TrashPurgeConfig
): Date | null {
  const deleted = new Date(deletedAt);
  const started = new Date(startedAt);

  if (Number.isNaN(deleted.getTime()) || Number.isNaN(started.getTime())) {
    return null;
  }

  const retentionDays = config.retentionDays;
  if (typeof retentionDays !== 'number' || !Number.isFinite(retentionDays) || retentionDays <= 0) {
    // The backend validates retention_days >= 1; anything else is malformed
    // config, and inventing a deadline from it would print a false date.
    return null;
  }

  const retentionDeadline = new Date(started.getTime() + retentionDays * 24 * 60 * 60 * 1000);

  const trashDays = config.trashRetentionDays;
  if (typeof trashDays !== 'number' || !Number.isFinite(trashDays) || trashDays <= 0) {
    // Trash clock disabled (0, the backend's "off" value) or absent/malformed.
    return retentionDeadline;
  }

  const trashDeadline = new Date(deleted.getTime() + trashDays * 24 * 60 * 60 * 1000);
  return trashDeadline.getTime() < retentionDeadline.getTime() ? trashDeadline : retentionDeadline;
}

/**
 * Format a purge deadline for the Trash card chip.
 *
 * Dates within a year render as a plain calendar date; anything further out
 * (or clock-skewed into the past beyond the deadline math) still shows a full
 * date rather than a relative "in N days" that could contradict the card's
 * "Deleted X ago" chip.
 */
export function formatPurgeDate(deadline: Date | null): string {
  if (deadline === null) {
    return 'No purge scheduled';
  }
  return deadline.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

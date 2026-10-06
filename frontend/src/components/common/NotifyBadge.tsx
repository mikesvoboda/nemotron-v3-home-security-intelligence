import { clsx } from 'clsx';
import { Bell, BellOff } from 'lucide-react';

/**
 * The persisted notify decision on an event (ISS-001, the OD-31 narrow
 * reading: the decision recorded in `event_notify_decisions` IS the
 * delivery the smallest slice owes). Two states are RENDERABLE; absence is
 * deliberately NOT one of them:
 *
 *  - `notify === true`  -> "Notifies": the owner's preferences flagged this
 *    event to be notified, and the decision is on the record.
 *  - `notify === false` -> "Not notifying": a REAL decision not to page -
 *    distinct from absence, and it must render (an operator who asks "why
 *    was I not paged?" needs the event to say so).
 *  - `undefined` / `null` -> NO DECISION: legacy events, replay rows,
 *    events from other emitters. The badge renders NOTHING: absence is not
 *    False (the same contract `verification` keeps, backend/api/schemas/
 *    event_verification.py), so inventing a third visual state would turn
 *    "we never decided" into a fake decision.
 *
 * Colors stay out of the risk palette on purpose (same reasoning as
 * VerdictBadge's docstring): this is a delivery-status marker, not a
 * severity claim, and a green/red here would read as "safe/dangerous".
 */
export interface NotifyBadgeProps {
  /** The event's persisted decision; absent/null renders nothing. */
  notify?: boolean | null;
  /** 'sm' matches the compact card badges; 'md' for detail views. */
  size?: 'sm' | 'md';
  className?: string;
}

export default function NotifyBadge({ notify, size = 'sm', className }: NotifyBadgeProps) {
  if (notify === undefined || notify === null) return null;

  const label = notify ? 'Notifies' : 'Not notifying';
  const Icon = notify ? Bell : BellOff;
  // Notifying = the blue the app uses for "pushed to you" chrome; not
  // notifying = muted gray, readable but de-emphasized (the VerdictBadge
  // doctrine: a dismissal stays listed, never hidden).
  const tone = notify ? 'bg-blue-500/10 text-blue-300' : 'bg-gray-700 text-gray-400 opacity-80';
  const iconSize = size === 'sm' ? 'h-3 w-3' : 'h-4 w-4';
  const boxSize = size === 'sm' ? 'text-xs px-1.5 py-0.5' : 'text-sm px-2 py-0.5';

  return (
    <span
      // role=status like the sibling badges: the decision arriving with a
      // live event is a status announcement.
      role="status"
      aria-label={`Notification decision: ${label}`}
      data-notify={notify ? 'yes' : 'no'}
      className={clsx(
        'inline-flex items-center gap-1 rounded-full font-medium',
        boxSize,
        tone,
        className
      )}
    >
      <Icon className={iconSize} aria-hidden="true" />
      <span>{label}</span>
    </span>
  );
}

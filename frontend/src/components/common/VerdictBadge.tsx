import { clsx } from 'clsx';
import { AlertOctagon, Ban, CheckCircle, EyeOff, HelpCircle } from 'lucide-react';

import type { EventVerificationPayload } from '../../types/generated/websocket';

/**
 * The five states an operator can actually see on an event card: the four
 * spec §4 verdicts, plus 'unverified' for an event that has NO verification
 * row (legacy events, and vlm-mode events not analyzed yet).
 *
 * The value is the VERDICT STRING as the payload/DB carry it, or undefined/
 * 'none' for no row - NOT a boolean and not null-derived. `risk_score ===
 * null` is not this state's source of truth: a `rejected` verdict can carry
 * a real score, and `verification_failed` carries NULL (D11), so keying on
 * the score conflates "dismissed" with "broken". The ActivityFeed interim
 * chip keyed on the score; reading the row is the 1.6 replacement.
 */
export type VerdictBadgeValue = EventVerificationPayload['verdict'] | 'none' | null | undefined;

type BadgeState = EventVerificationPayload['verdict'] | 'unverified';

/** Spec §4 verdict labels, spelled for a human (never the snake_case token). */
const LABELS: Record<BadgeState, string> = {
  confirmed: 'Confirmed',
  rejected: 'Rejected',
  uncertain: 'Uncertain',
  verification_failed: 'Verification failed',
  unverified: 'Unverified',
};

const ICONS: Record<BadgeState, typeof CheckCircle> = {
  confirmed: CheckCircle,
  rejected: Ban,
  uncertain: HelpCircle,
  // Its own icon, not rejected's: "could not answer" is not "said no".
  verification_failed: AlertOctagon,
  unverified: EyeOff,
};

/**
 * Color is the whole message here, so the four+one treatments are deliberately
 * distinct and deliberately NOT all "risk colors":
 *  - confirmed = the NVIDIA green (this is the path's success state);
 *  - rejected = muted gray, de-emphasized but READABLE (plan Task 6: stays
 *    listed, never hidden - "what did we dismiss?" is an audit question);
 *  - uncertain = amber (needs a human, same family as the risk amber);
 *  - verification_failed = red (a broken verification is an incident, not a
 *    dismissal - folding it into gray is how silent failures ship);
 *  - unverified = the gray the interim chip already uses, kept word-for-word
 *    so nothing downstream re-keys on it.
 * Tailwind classes use the same tokens the sibling RiskBadge already ships
 * (bg-risk-low/10 + text-risk-low = the NVIDIA green; bg-risk-medium/10 +
 * text-risk-medium = the amber) and the reds the rest of the codebase uses
 * for broken/error state (bg-red-500/10 text-red-400, the house spelling).
 */
const CLASSES: Record<BadgeState, string> = {
  confirmed: 'bg-risk-low/10 text-risk-low',
  rejected: 'bg-gray-700 text-gray-400 opacity-80',
  uncertain: 'bg-risk-medium/10 text-risk-medium',
  verification_failed: 'bg-red-500/10 text-red-400',
  unverified: 'bg-gray-700 text-gray-300',
};

function resolveState(verdict: VerdictBadgeValue): BadgeState {
  if (verdict === undefined || verdict === null || verdict === 'none') return 'unverified';
  return verdict;
}

/**
 * The human label for a verdict - exported so a card's aria-label can name
 * the SAME word the badge shows (one source; a second spelling would drift).
 */
export function verdictLabel(verdict: VerdictBadgeValue): string {
  return LABELS[resolveState(verdict)];
}

/**
 * The filter bar's verdict vocabulary: [API value, human label]. The label
 * is read from LABELS - the badge's own table - so the chip that filters
 * "Verification failed" is spelled exactly like the badge that shows it.
 *
 * The filter accepts ALL FIVE values, including `none` for never-verified
 * events (the backend's NOT EXISTS pseudo-verdict - the human sees
 * "Unverified", the wire carries 'none'). Unlike the CHECK constraint,
 * which only ever stores the four real verdicts, a filter must be able to
 * ask for "no row" - that asymmetry is deliberate and pinned backend-side.
 */
export const VERDICT_CHIP_FILTERS = (
  ['confirmed', 'rejected', 'uncertain', 'verification_failed', 'none'] as const
).map((value) => [value, LABELS[resolveState(value)]] as const);

export interface VerdictBadgeProps {
  /** The verification verdict, or undefined/'none'/null for no verification row. */
  verdict: VerdictBadgeValue;
  /** 'sm' matches the compact RiskBadge used on cards; 'md' for detail views. */
  size?: 'sm' | 'md';
  className?: string;
}

/**
 * Shared VLM verdict badge (plan Task 6). Generalizes the ActivityFeed
 * interim "Unverified" chip to the full spec §4 vocabulary, and is the
 * single place the verdict→label and verdict→color mapping lives, so the
 * cards, the list, the detail panel and the WS live-feed cannot drift.
 */
export default function VerdictBadge({ verdict, size = 'sm', className }: VerdictBadgeProps) {
  const state = resolveState(verdict);
  const Icon = ICONS[state];
  const label = LABELS[state];
  const iconSize = size === 'sm' ? 'h-3 w-3' : 'h-4 w-4';
  const boxSize = size === 'sm' ? 'text-xs px-1.5 py-0.5' : 'text-sm px-2 py-0.5';

  return (
    <span
      // role=status, like RiskBadge: a verdict arriving on a live event is a
      // status announcement, and the interim chip had no role at all.
      role="status"
      aria-label={`Verification verdict: ${label}`}
      data-verdict={state}
      className={clsx(
        'inline-flex items-center gap-1 whitespace-nowrap rounded font-medium',
        boxSize,
        CLASSES[state],
        className
      )}
    >
      <Icon className={iconSize} aria-hidden="true" />
      {label}
    </span>
  );
}

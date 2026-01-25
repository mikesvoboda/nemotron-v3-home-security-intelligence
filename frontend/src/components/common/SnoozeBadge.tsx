/**
 * SnoozeBadge - Displays snooze status for an event
 *
 * Shows a visual indicator when an event is snoozed, including
 * the time remaining until the snooze expires.
 *
 * NEM-3640: Event Snooze Feature
 *
 * @example
 * ```tsx
 * <SnoozeBadge snoozeUntil={event.snooze_until} />
 * ```
 */

import { clsx } from 'clsx';
import { Moon } from 'lucide-react';
import { memo, useEffect, useState } from 'react';

import { isSnoozed, formatSnoozeEndTime, formatSnoozeRemaining } from '../../utils/snooze';

// ============================================================================
// Types
// ============================================================================

export interface SnoozeBadgeProps {
  /** ISO timestamp until which the event is snoozed */
  snoozeUntil: string | null | undefined;

  /** Size variant */
  size?: 'sm' | 'md' | 'lg';

  /** Show the end time (e.g., "until 3:45 PM") */
  showEndTime?: boolean;

  /** Show remaining time (e.g., "15 min remaining") */
  showRemaining?: boolean;

  /** Additional CSS classes */
  className?: string;
}

// Update interval for remaining time display (1 minute)
const UPDATE_INTERVAL_MS = 60 * 1000;

// ============================================================================
// Component
// ============================================================================

/**
 * SnoozeBadge displays a badge indicating that an event is snoozed.
 *
 * Automatically updates the remaining time display and hides
 * itself when the snooze period expires.
 */
const SnoozeBadge = memo(function SnoozeBadge({
  snoozeUntil,
  size = 'sm',
  showEndTime = true,
  showRemaining = false,
  className,
}: SnoozeBadgeProps) {
  // Track if currently snoozed (updates over time)
  const [isCurrentlySnoozed, setIsCurrentlySnoozed] = useState(() => isSnoozed(snoozeUntil));
  const [remainingText, setRemainingText] = useState(() => formatSnoozeRemaining(snoozeUntil));

  // Update snooze status periodically
  useEffect(() => {
    // Initial check
    setIsCurrentlySnoozed(isSnoozed(snoozeUntil));
    setRemainingText(formatSnoozeRemaining(snoozeUntil));

    // Set up interval to update status
    const interval = setInterval(() => {
      const snoozed = isSnoozed(snoozeUntil);
      setIsCurrentlySnoozed(snoozed);
      if (snoozed) {
        setRemainingText(formatSnoozeRemaining(snoozeUntil));
      }
    }, UPDATE_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [snoozeUntil]);

  // Don't render if not snoozed
  if (!isCurrentlySnoozed) {
    return null;
  }

  // Size-based styling
  const sizeClasses = {
    sm: {
      container: 'px-2 py-0.5 gap-1 text-xs',
      icon: 'w-3 h-3',
    },
    md: {
      container: 'px-2.5 py-1 gap-1.5 text-sm',
      icon: 'w-3.5 h-3.5',
    },
    lg: {
      container: 'px-3 py-1.5 gap-2 text-base',
      icon: 'w-4 h-4',
    },
  }[size];

  const endTimeText = formatSnoozeEndTime(snoozeUntil);

  // Build display text
  let displayText = 'Snoozed';
  if (showEndTime && endTimeText) {
    displayText = `Snoozed until ${endTimeText}`;
  }

  return (
    <span
      className={clsx(
        // Base styles
        'inline-flex items-center rounded-full font-medium',
        // Purple/blue color scheme for snooze
        'bg-indigo-500/20 text-indigo-400',
        'border border-indigo-500/30',
        // Size classes
        sizeClasses.container,
        className
      )}
      title={showRemaining && remainingText ? remainingText : undefined}
      data-testid="snooze-badge"
    >
      <Moon className={clsx(sizeClasses.icon, 'flex-shrink-0')} aria-hidden="true" />
      <span className="truncate">{displayText}</span>
      {showRemaining && remainingText && (
        <span className="text-indigo-400/70 hidden sm:inline">({remainingText})</span>
      )}
    </span>
  );
});

export default SnoozeBadge;

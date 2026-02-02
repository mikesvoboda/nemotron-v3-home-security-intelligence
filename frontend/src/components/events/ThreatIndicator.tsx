/**
 * ThreatIndicator - Display weapon/threat detection badges on EventCard (NEM-5019)
 *
 * Shows badges for each detected threat with confidence percentages,
 * styled according to priority level (critical for firearms/knives, warning for blunt weapons).
 */

import { clsx } from 'clsx';
import { AlertOctagon, AlertTriangle } from 'lucide-react';

import {
  formatThreatClassName,
  formatConfidencePercent,
  getThreatPriorityConfig,
} from '../../types/threat';

import type { ThreatData } from '../../types/threat';

export interface ThreatIndicatorProps {
  /** List of threat detections to display */
  threats: ThreatData[] | null | undefined;
  /** Enable compact mode (shows only first threat + count) */
  compact?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Single threat badge component
 */
function ThreatBadge({
  threat,
  index,
}: {
  threat: ThreatData;
  index: number;
}) {
  const config = getThreatPriorityConfig(threat.is_high_priority);
  const displayName = formatThreatClassName(threat.class_name);
  const confidencePercent = formatConfidencePercent(threat.confidence);

  const ariaLabel = threat.is_high_priority
    ? `${threat.class_name} detected with ${confidencePercent} confidence, high priority`
    : `${threat.class_name} detected with ${confidencePercent} confidence`;

  return (
    <span
      data-testid={`threat-badge-${index}`}
      aria-label={ariaLabel}
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold border truncate',
        config.bgColor,
        config.borderColor,
        config.textColor
      )}
    >
      {threat.is_high_priority ? (
        <AlertOctagon className="h-3.5 w-3.5 flex-shrink-0" data-testid="critical-icon" />
      ) : (
        <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0" data-testid="warning-icon" />
      )}
      <span className="truncate">{displayName}</span>
      <span className="flex-shrink-0">{confidencePercent}</span>
    </span>
  );
}

/**
 * Overflow count badge for compact mode
 */
function OverflowBadge({ count }: { count: number }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center justify-center rounded-full px-2 py-1 text-xs font-semibold',
        'bg-gray-600 text-white border border-gray-700'
      )}
    >
      +{count}
    </span>
  );
}

/**
 * ThreatIndicator component
 *
 * Renders threat detection badges sorted by confidence (highest first).
 * Supports compact mode which shows only the highest confidence threat
 * plus a count of additional threats.
 */
export default function ThreatIndicator({
  threats,
  compact = false,
  className,
}: ThreatIndicatorProps) {
  // Return null for empty/null/undefined threats
  if (!threats || threats.length === 0) {
    return null;
  }

  // Sort threats by confidence (highest first)
  const sortedThreats = [...threats].sort((a, b) => b.confidence - a.confidence);

  // Check if any threat is high priority
  const hasHighPriority = sortedThreats.some((t) => t.is_high_priority);

  // Build container aria-label
  const threatCount = sortedThreats.length;
  const threatWord = threatCount === 1 ? 'threat' : 'threats';
  const containerAriaLabel = `${threatCount} ${threatWord} detected`;

  // Determine which threats to display
  const threatsToDisplay = compact ? sortedThreats.slice(0, 1) : sortedThreats;
  const overflowCount = compact ? sortedThreats.length - 1 : 0;

  return (
    <div
      data-testid="threat-indicator"
      role={hasHighPriority ? 'alert' : 'status'}
      aria-live={hasHighPriority ? 'assertive' : 'polite'}
      aria-label={containerAriaLabel}
      className={clsx(
        'flex flex-wrap items-center gap-2',
        compact && 'compact',
        className
      )}
    >
      {threatsToDisplay.map((threat, index) => (
        <ThreatBadge key={`${threat.class_name}-${index}`} threat={threat} index={index} />
      ))}
      {overflowCount > 0 && <OverflowBadge count={overflowCount} />}
    </div>
  );
}

/**
 * PersonJourneyTimeline - Vertical timeline showing a person's appearances
 *
 * Displays a chronological timeline of when a person was detected at different
 * cameras, with optional thumbnails, confidence indicators, and date grouping.
 *
 * @module components/face-recognition/PersonJourneyTimeline
 * @see docs/plans/2025-01-31-face-recognition-ui-design.md
 * @see NEM-4688 Phase 3 - Person Tracking
 */

import { clsx } from 'clsx';
import { Camera, Clock, User } from 'lucide-react';
import { useMemo } from 'react';

import type { PersonAppearance } from '../../types/faceRecognition';
import type React from 'react';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the PersonJourneyTimeline component.
 */
export interface PersonJourneyTimelineProps {
  /** Array of appearances to display in the timeline */
  appearances: PersonAppearance[];
  /** Callback when an appearance is clicked */
  onViewAppearance?: (appearance: PersonAppearance) => void;
  /** Whether to show thumbnails for each appearance */
  showThumbnails?: boolean;
  /** Optional additional CSS classes */
  className?: string;
}

/**
 * Internal type for grouped appearances by date.
 */
interface DateGroup {
  date: string;
  label: string;
  appearances: PersonAppearance[];
}

// ============================================================================
// Helpers
// ============================================================================

/**
 * Format a timestamp for display in the timeline.
 * Returns time in 12-hour format (e.g., "8:15 AM").
 */
function formatTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  } catch {
    return isoString;
  }
}

/**
 * Get the date portion of an ISO timestamp (YYYY-MM-DD).
 */
function getDateKey(isoString: string): string {
  return isoString.split('T')[0];
}

/**
 * Format a date for display as a section header.
 * Returns "Today", "Yesterday", or the full date.
 */
function formatDateLabel(dateKey: string): string {
  const date = new Date(dateKey + 'T00:00:00Z');
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const dateStr = date.toISOString().split('T')[0];
  const todayStr = today.toISOString().split('T')[0];
  const yesterdayStr = yesterday.toISOString().split('T')[0];

  if (dateStr === todayStr) {
    return 'Today';
  }
  if (dateStr === yesterdayStr) {
    return 'Yesterday';
  }

  return date.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * Get the confidence color class based on the confidence value.
 */
function getConfidenceColorClass(confidence: number): string {
  if (confidence >= 0.9) {
    return 'text-green-400';
  }
  if (confidence >= 0.7) {
    return 'text-yellow-400';
  }
  return 'text-red-400';
}

/**
 * Sort appearances chronologically and group by date if spanning multiple days.
 */
function groupAppearancesByDate(appearances: PersonAppearance[]): DateGroup[] | null {
  if (appearances.length === 0) {
    return null;
  }

  // Sort by timestamp (oldest first)
  const sorted = [...appearances].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  // Check if all appearances are on the same day
  const uniqueDates = new Set(sorted.map((a) => getDateKey(a.timestamp)));
  if (uniqueDates.size <= 1) {
    return null; // No need for date grouping
  }

  // Group by date
  const groups: Map<string, PersonAppearance[]> = new Map();
  for (const appearance of sorted) {
    const dateKey = getDateKey(appearance.timestamp);
    const group = groups.get(dateKey) || [];
    group.push(appearance);
    groups.set(dateKey, group);
  }

  // Convert to array with labels
  return Array.from(groups.entries()).map(([date, apps]) => ({
    date,
    label: formatDateLabel(date),
    appearances: apps,
  }));
}

// ============================================================================
// Sub-components
// ============================================================================

/**
 * Thumbnail component for appearance images.
 */
function Thumbnail({
  url,
  cameraName,
}: {
  url: string | null | undefined;
  cameraName: string;
}): React.ReactElement {
  if (!url) {
    return (
      <div
        data-testid="thumbnail-placeholder"
        className="flex h-12 w-12 items-center justify-center rounded bg-gray-700"
      >
        <User className="h-6 w-6 text-gray-500" />
      </div>
    );
  }

  return (
    <img src={url} alt={`Thumbnail at ${cameraName}`} className="h-12 w-12 rounded object-cover" />
  );
}

/**
 * Single timeline node component.
 */
function TimelineNode({
  appearance,
  isLast,
  onViewAppearance,
  showThumbnails,
}: {
  appearance: PersonAppearance;
  isLast: boolean;
  onViewAppearance?: (appearance: PersonAppearance) => void;
  showThumbnails?: boolean;
}): React.ReactElement {
  const isClickable = !!onViewAppearance;
  const confidencePercent = Math.round(appearance.confidence * 100);

  const handleClick = (): void => {
    if (onViewAppearance) {
      onViewAppearance(appearance);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent): void => {
    if (onViewAppearance && (e.key === 'Enter' || e.key === ' ')) {
      e.preventDefault();
      onViewAppearance(appearance);
    }
  };

  /**
   * When clickable, the li element gets role="button" which makes it an interactive element.
   * The lint rules don't recognize that role="button" transforms the semantic meaning.
   */
  /* eslint-disable jsx-a11y/no-noninteractive-element-interactions */
  return (
    <li
      data-testid={`timeline-node-${appearance.detection_id}`}
      className={clsx(
        'relative flex w-full items-start gap-3 rounded-lg p-2 text-left',
        isClickable && 'cursor-pointer hover:bg-gray-800',
        'transition-colors'
      )}
      onClick={isClickable ? handleClick : undefined}
      onKeyDown={isClickable ? handleKeyDown : undefined}
      tabIndex={isClickable ? 0 : undefined}
      role={isClickable ? 'button' : undefined}
      aria-label={isClickable ? `View appearance at ${appearance.camera_name}` : undefined}
    >
      {/* Timeline dot and connector */}
      <div className="relative flex flex-col items-center pt-1">
        <div data-testid="timeline-dot" className="h-3 w-3 rounded-full bg-[#76B900]" />
        {!isLast && (
          <div
            data-testid="timeline-connector"
            className="mt-1 h-full min-h-[2rem] border-l-2 border-gray-600"
            aria-hidden="true"
          />
        )}
      </div>

      {/* Content */}
      <div className="flex flex-1 items-start gap-3">
        {/* Main info */}
        <div className="min-w-0 flex-1">
          {/* Time and Camera */}
          <div className="flex items-center gap-2">
            <span
              data-testid="timeline-time"
              className="flex items-center gap-1 text-sm text-gray-400"
            >
              <Clock className="h-3 w-3" />
              {formatTime(appearance.timestamp)}
            </span>
          </div>

          {/* Camera name */}
          <div className="mt-1 flex items-center gap-2">
            <Camera className="h-4 w-4 text-gray-500" />
            <span data-testid="timeline-camera-name" className="truncate font-medium text-white">
              {appearance.camera_name}
            </span>
          </div>

          {/* Confidence */}
          <span
            data-testid="confidence-indicator"
            className={clsx(
              'mt-1 inline-block text-xs',
              getConfidenceColorClass(appearance.confidence)
            )}
          >
            {confidencePercent}% confidence
          </span>
        </div>

        {/* Thumbnail */}
        {showThumbnails && (
          <Thumbnail url={appearance.thumbnail_url} cameraName={appearance.camera_name} />
        )}
      </div>
    </li>
  );
  /* eslint-enable jsx-a11y/no-noninteractive-element-interactions */
}

/**
 * Empty state component.
 */
function EmptyState(): React.ReactElement {
  return (
    <div data-testid="timeline-empty-state" className="py-8 text-center text-gray-500">
      <User className="mx-auto mb-2 h-8 w-8 opacity-50" />
      <p>No appearances recorded for this person.</p>
    </div>
  );
}

/**
 * Date header component for multi-day grouping.
 */
function DateHeader({ label }: { label: string }): React.ReactElement {
  return (
    <div
      data-testid="date-header"
      className="mb-2 mt-4 text-sm font-semibold text-gray-300 first:mt-0"
    >
      {label}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

/**
 * PersonJourneyTimeline displays a vertical timeline of a person's appearances.
 *
 * Features:
 * - Chronological ordering (oldest to newest)
 * - Date grouping for multi-day spans
 * - Optional thumbnails
 * - Confidence indicators with color coding
 * - Click support for viewing full detection
 * - Keyboard accessible
 *
 * @example
 * ```tsx
 * <PersonJourneyTimeline
 *   appearances={appearances}
 *   onViewAppearance={(a) => console.log('Clicked', a)}
 *   showThumbnails
 * />
 * ```
 */
export default function PersonJourneyTimeline({
  appearances,
  onViewAppearance,
  showThumbnails = false,
  className,
}: PersonJourneyTimelineProps): React.ReactElement {
  // Sort and optionally group appearances
  const sortedAppearances = useMemo(() => {
    return [...appearances].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
  }, [appearances]);

  const dateGroups = useMemo(() => groupAppearancesByDate(appearances), [appearances]);

  // Handle empty state
  if (appearances.length === 0) {
    return (
      <div
        data-testid="person-journey-timeline"
        className={clsx('rounded-lg bg-[#1A1A1A] p-4', className)}
      >
        <EmptyState />
      </div>
    );
  }

  // Render with date groups
  if (dateGroups) {
    return (
      <div
        data-testid="person-journey-timeline"
        className={clsx('rounded-lg bg-[#1A1A1A] p-4', className)}
      >
        {dateGroups.map((group, groupIndex) => (
          <div key={group.date}>
            <DateHeader label={group.label} />
            <ul className="space-y-0">
              {group.appearances.map((appearance, index) => {
                const isLastInGroup = index === group.appearances.length - 1;
                const isLastOverall = groupIndex === dateGroups.length - 1 && isLastInGroup;

                return (
                  <TimelineNode
                    key={appearance.detection_id}
                    appearance={appearance}
                    isLast={isLastOverall}
                    onViewAppearance={onViewAppearance}
                    showThumbnails={showThumbnails}
                  />
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    );
  }

  // Render without date groups (single day)
  return (
    <div
      data-testid="person-journey-timeline"
      className={clsx('rounded-lg bg-[#1A1A1A] p-4', className)}
    >
      <ul className="space-y-0">
        {sortedAppearances.map((appearance, index) => (
          <TimelineNode
            key={appearance.detection_id}
            appearance={appearance}
            isLast={index === sortedAppearances.length - 1}
            onViewAppearance={onViewAppearance}
            showThumbnails={showThumbnails}
          />
        ))}
      </ul>
    </div>
  );
}

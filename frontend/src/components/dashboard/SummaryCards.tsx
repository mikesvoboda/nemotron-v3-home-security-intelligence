/**
 * Summary cards for displaying hourly and daily event summaries.
 *
 * Displays LLM-generated narrative summaries of high/critical security events.
 * Styled using Tremor components for consistency with the rest of the dashboard.
 *
 * @see NEM-2923 - Bullet list support
 * @see NEM-2926 - Visual hierarchy improvements
 */

import { Card, Text } from '@tremor/react';
import { formatDistanceToNow, parseISO } from 'date-fns';
import { ChevronRight, Clock, Calendar, RefreshCw } from 'lucide-react';
import { useMemo } from 'react';

import { SeverityBadge } from './SeverityBadge';
import { SummaryBulletList } from './SummaryBulletList';

import type { Summary, SummaryBulletPoint, SummaryType } from '@/types/summary';

import {
  calculateSeverity,
  shouldShowCriticalAnimation,
  type SeverityResult,
} from '@/utils/severityCalculator';
import { extractBulletPoints } from '@/utils/summaryParser';

interface SummaryCardProps {
  /** Type of summary: 'hourly' or 'daily' */
  type: SummaryType;
  /** The summary data, or null if unavailable */
  summary: Summary | null;
  /** Whether the summary is loading */
  isLoading?: boolean;
  /** Callback when "View Full Summary" is clicked */
  onViewFull?: (summary: Summary) => void;
}

/**
 * Format the time window for display.
 * For hourly: "Last 60 minutes"
 * For daily: "Since midnight"
 */
function formatTimeWindow(type: SummaryType): string {
  return type === 'hourly' ? 'Last 60 minutes' : 'Since midnight';
}

/**
 * Single summary card component.
 */
export function SummaryCard({ type, summary, isLoading, onViewFull }: SummaryCardProps) {
  const isHourly = type === 'hourly';
  const title = isHourly ? 'Hourly Summary' : 'Daily Summary';
  const Icon = isHourly ? Clock : Calendar;

  // Calculate severity based on content, risk score, and event count
  const severity: SeverityResult = summary
    ? calculateSeverity({
        content: summary.content,
        eventCount: summary.eventCount,
        maxRiskScore: summary.maxRiskScore,
      })
    : calculateSeverity({ content: '', eventCount: 0 });

  // Determine if critical animation should show
  const showCriticalAnimation = summary && shouldShowCriticalAnimation(severity.level);

  // Format "X minutes ago" text for footer
  const generatedAgoText = summary?.generatedAt
    ? `Generated ${formatDistanceToNow(parseISO(summary.generatedAt), { addSuffix: false })} ago`
    : '';

  // Format event count for footer
  const eventCountText = summary
    ? `${summary.eventCount} ${summary.eventCount === 1 ? 'event' : 'events'} analyzed`
    : '';

  // Get bullet points: use backend-provided data or extract from content
  const bulletPoints: SummaryBulletPoint[] = useMemo(() => {
    if (!summary) return [];
    // Prefer backend-provided bullet points
    if (summary.bulletPoints && summary.bulletPoints.length > 0) {
      return summary.bulletPoints;
    }
    // Fall back to extracting from prose content
    return extractBulletPoints(summary.content);
  }, [summary]);

  // Determine whether to show bullet list or prose fallback
  const hasBulletPoints = bulletPoints.length > 0;

  // Loading state
  if (isLoading) {
    return (
      <Card
        className="relative mb-4 overflow-hidden border-gray-800 bg-[#1A1A1A] pl-4"
        data-testid={`summary-card-${type}-loading`}
      >
        {/* Left accent bar - gray for loading */}
        <div
          className="absolute bottom-0 left-0 top-0 w-1"
          style={{ backgroundColor: '#d1d5db' }}
          data-testid="accent-bar"
        />

        {/* Header */}
        <div className="mb-3">
          {/* Top row: placeholder badge + time window */}
          <div className="mb-2 flex items-center justify-between">
            <div className="h-6 w-24 animate-pulse rounded-full bg-gray-700" />
            <span className="text-xs text-gray-400">{formatTimeWindow(type)}</span>
          </div>
          {/* Title row */}
          <div className="flex items-center gap-2">
            <Icon className="h-5 w-5 text-gray-500" aria-hidden="true" />
            <span className="text-sm font-medium text-gray-300">{title}</span>
          </div>
        </div>

        {/* Content skeleton */}
        <div className="animate-pulse" data-testid="loading-skeleton">
          <div className="mb-2 h-4 w-3/4 rounded bg-gray-700" />
          <div className="h-4 w-1/2 rounded bg-gray-700" />
        </div>
      </Card>
    );
  }

  // No summary available
  if (!summary) {
    return (
      <Card
        className="relative mb-4 overflow-hidden border-gray-800 bg-[#1A1A1A] pl-4"
        data-testid={`summary-card-${type}-empty`}
      >
        {/* Left accent bar - gray for empty */}
        <div
          className="absolute bottom-0 left-0 top-0 w-1"
          style={{ backgroundColor: '#6b7280' }}
          data-testid="accent-bar"
        />

        {/* Header */}
        <div className="mb-3">
          {/* Top row: No badge for empty state + time window */}
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs text-gray-500">No data</span>
            <span className="text-xs text-gray-400">{formatTimeWindow(type)}</span>
          </div>
          {/* Title row */}
          <div className="flex items-center gap-2">
            <Icon className="h-5 w-5 text-gray-500" aria-hidden="true" />
            <span className="text-sm font-medium text-gray-300">{title}</span>
          </div>
        </div>

        {/* Empty state message */}
        <Text className="italic text-gray-500">
          No summary available yet. Summaries are generated every 5 minutes.
        </Text>
      </Card>
    );
  }

  // Build card class with optional critical animation
  const cardClass = showCriticalAnimation
    ? 'relative mb-4 overflow-hidden border-gray-800 bg-[#1A1A1A] pl-4 animate-pulse-critical'
    : 'relative mb-4 overflow-hidden border-gray-800 bg-[#1A1A1A] pl-4';

  return (
    <Card
      className={cardClass}
      data-testid={`summary-card-${type}`}
      data-severity={severity.level}
    >
      {/* Left accent bar */}
      <div
        className="absolute bottom-0 left-0 top-0 w-1"
        style={{ backgroundColor: severity.borderColor }}
        data-testid="accent-bar"
      />

      {/* Header */}
      <div className="mb-3">
        {/* Top row: Severity badge (left) + Time window (right) */}
        <div className="mb-2 flex items-center justify-between">
          <SeverityBadge
            level={severity.level}
            count={summary.eventCount}
            pulsing={showCriticalAnimation ?? undefined}
            size="sm"
            data-testid={`summary-badge-${type}`}
          />
          <span className="text-xs text-gray-400" data-testid={`time-window-${type}`}>
            {formatTimeWindow(type)}
          </span>
        </div>
        {/* Title row */}
        <div className="flex items-center gap-2">
          <Icon className="h-5 w-5 text-gray-400" aria-hidden="true" />
          <span className="text-sm font-medium text-gray-300">{title}</span>
        </div>
      </div>

      {/* Content */}
      <div data-testid={`summary-content-${type}`}>
        {hasBulletPoints ? (
          <SummaryBulletList
            bullets={bulletPoints}
            maxItems={4}
            testIdPrefix={`summary-bullet-${type}`}
          />
        ) : (
          <Text className="line-clamp-3 leading-relaxed text-gray-300">{summary.content}</Text>
        )}
      </div>

      {/* View Full Summary Link */}
      {onViewFull && (
        <button
          type="button"
          onClick={() => onViewFull(summary)}
          className="mt-3 flex items-center gap-1 text-sm text-blue-400 transition-colors hover:text-blue-300"
          data-testid={`summary-view-full-${type}`}
        >
          <span>View Full Summary</span>
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
      )}

      {/* Footer */}
      <div
        className="mt-4 flex items-center justify-between border-t border-gray-800 pt-3"
        data-testid={`summary-footer-${type}`}
      >
        {/* Generated time with refresh icon */}
        <div
          className="flex items-center gap-1.5 text-xs text-gray-500"
          data-testid={`summary-updated-${type}`}
        >
          <RefreshCw className="h-3 w-3" aria-hidden="true" />
          <span>{generatedAgoText}</span>
        </div>
        {/* Event count */}
        <span className="text-xs text-gray-500" data-testid={`summary-event-count-${type}`}>
          {eventCountText}
        </span>
      </div>
    </Card>
  );
}

interface SummaryCardsProps {
  /** Hourly summary data */
  hourly: Summary | null;
  /** Daily summary data */
  daily: Summary | null;
  /** Whether summaries are loading */
  isLoading?: boolean;
  /** Callback when "View Full Summary" is clicked */
  onViewFull?: (summary: Summary) => void;
}

/**
 * Container component for both summary cards.
 *
 * Displays hourly summary on top, daily summary below.
 *
 * @example
 * ```tsx
 * function Dashboard() {
 *   const { hourly, daily, isLoading } = useSummaries();
 *   return <SummaryCards hourly={hourly} daily={daily} isLoading={isLoading} />;
 * }
 * ```
 */
export function SummaryCards({ hourly, daily, isLoading, onViewFull }: SummaryCardsProps) {
  return (
    <div className="space-y-4" data-testid="summary-cards">
      <SummaryCard type="hourly" summary={hourly} isLoading={isLoading} onViewFull={onViewFull} />
      <SummaryCard type="daily" summary={daily} isLoading={isLoading} onViewFull={onViewFull} />
    </div>
  );
}

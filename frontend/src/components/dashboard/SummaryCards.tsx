/**
 * Summary cards for displaying hourly and daily event summaries.
 *
 * Displays LLM-generated narrative summaries of high/critical security events.
 * Styled using Tremor components for consistency with the rest of the dashboard.
 */

import { Badge, Card, Flex, Text, Title } from '@tremor/react';
import { formatDistanceToNow, parseISO } from 'date-fns';
import { CheckCircle, Clock, Calendar } from 'lucide-react';

import type { Summary, SummaryType } from '@/types/summary';

interface SummaryCardProps {
  /** Type of summary: 'hourly' or 'daily' */
  type: SummaryType;
  /** The summary data, or null if unavailable */
  summary: Summary | null;
  /** Whether the summary is loading */
  isLoading?: boolean;
}

/**
 * Single summary card component.
 */
export function SummaryCard({ type, summary, isLoading }: SummaryCardProps) {
  const isHourly = type === 'hourly';
  const title = isHourly ? 'Hourly Summary' : 'Daily Summary';
  const Icon = isHourly ? Clock : Calendar;

  // Determine card styling based on event count
  const hasEvents = summary && summary.eventCount > 0;

  // Format "updated X ago" text
  const updatedText = summary?.generatedAt
    ? `Updated ${formatDistanceToNow(parseISO(summary.generatedAt), { addSuffix: false })} ago`
    : '';

  // Loading state
  if (isLoading) {
    return (
      <Card
        className="mb-4 border-l-4 border-gray-800 bg-[#1A1A1A]"
        style={{ borderLeftColor: '#d1d5db' }} // gray-300
        data-testid={`summary-card-${type}-loading`}
      >
        <Flex justifyContent="start" className="mb-2 gap-2">
          <Icon className="h-5 w-5 text-gray-500" aria-hidden="true" />
          <Title className="text-white">{title}</Title>
        </Flex>
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
        className="mb-4 border-l-4 border-gray-800 bg-[#1A1A1A]"
        style={{ borderLeftColor: '#6b7280' }} // gray-500
        data-testid={`summary-card-${type}-empty`}
      >
        <Flex justifyContent="start" className="mb-2 gap-2">
          <Icon className="h-5 w-5 text-gray-500" aria-hidden="true" />
          <Title className="text-white">{title}</Title>
        </Flex>
        <Text className="italic text-gray-500">
          No summary available yet. Summaries are generated every 5 minutes.
        </Text>
      </Card>
    );
  }

  // Determine border color class - use inline style to ensure it applies over Tremor defaults
  const borderColor = hasEvents ? '#f59e0b' : '#10b981'; // amber-500 : emerald-500

  return (
    <Card
      className="mb-4 border-l-4 border-gray-800 bg-[#1A1A1A]"
      style={{ borderLeftColor: borderColor }}
      data-testid={`summary-card-${type}`}
      data-has-events={hasEvents ? 'true' : 'false'}
    >
      {/* Header */}
      <Flex justifyContent="between" alignItems="center" className="mb-3">
        <Flex justifyContent="start" className="gap-2">
          <Icon className="h-5 w-5 text-gray-400" aria-hidden="true" />
          <Title className="text-white">{title}</Title>
        </Flex>
        <Badge
          color={hasEvents ? 'amber' : 'emerald'}
          icon={hasEvents ? undefined : CheckCircle}
          data-testid={`summary-badge-${type}`}
        >
          {hasEvents
            ? `${summary.eventCount} event${summary.eventCount > 1 ? 's' : ''}`
            : 'All clear'}
        </Badge>
      </Flex>

      {/* Content */}
      <div data-testid={`summary-content-${type}`}>
        <Text className="leading-relaxed text-gray-300">{summary.content}</Text>
      </div>

      {/* Footer */}
      <div data-testid={`summary-updated-${type}`}>
        <Text className="mt-3 text-sm text-gray-500">{updatedText}</Text>
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
export function SummaryCards({ hourly, daily, isLoading }: SummaryCardsProps) {
  return (
    <div className="space-y-4" data-testid="summary-cards">
      <SummaryCard type="hourly" summary={hourly} isLoading={isLoading} />
      <SummaryCard type="daily" summary={daily} isLoading={isLoading} />
    </div>
  );
}

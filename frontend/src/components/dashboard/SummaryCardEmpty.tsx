/**
 * SummaryCardEmpty - Empty state component for summary cards.
 *
 * Displays when there is no activity to summarize for a given time period.
 * Shows a contextual icon (Clock for hourly, Calendar for daily) with a
 * friendly message and optional action button.
 *
 * @see SummaryCards.tsx - Parent component that uses this empty state
 * @see NEM-2928
 */

import { Card, Flex, Text, Title } from '@tremor/react';
import { clsx } from 'clsx';
import { Calendar, Clock } from 'lucide-react';

import type { SummaryType } from '@/types/summary';

/**
 * Props for the SummaryCardEmpty component.
 */
export interface SummaryCardEmptyProps {
  /** Type of summary: 'hourly' or 'daily' - determines icon and messaging */
  type: SummaryType;
  /** Optional callback when "View All Events" button is clicked */
  onViewEvents?: () => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * SummaryCardEmpty provides a user-friendly empty state when there is
 * no security activity to summarize.
 *
 * Features:
 * - Contextual icon based on summary type (Clock/Calendar)
 * - Informative message explaining the empty state
 * - Optional "View All Events" button for navigation
 * - Dark theme styling consistent with NVIDIA design system
 *
 * @example
 * ```tsx
 * // Basic usage
 * <SummaryCardEmpty type="hourly" />
 *
 * // With view events action
 * <SummaryCardEmpty
 *   type="daily"
 *   onViewEvents={() => navigate('/events')}
 * />
 *
 * // With custom class
 * <SummaryCardEmpty type="hourly" className="mb-4" />
 * ```
 */
export function SummaryCardEmpty({
  type,
  onViewEvents,
  className,
}: SummaryCardEmptyProps) {
  const isHourly = type === 'hourly';
  const title = isHourly ? 'Hourly Summary' : 'Daily Summary';
  const Icon = isHourly ? Clock : Calendar;

  // Context-specific messaging
  const timeframeText = isHourly ? 'the past hour' : 'today';

  return (
    <Card
      className={clsx('mb-4 border-l-4 border-gray-800 bg-[#1A1A1A]', className)}
      style={{ borderLeftColor: '#6b7280' }} // gray-500 - neutral empty state
      data-testid={`summary-card-empty-${type}`}
    >
      {/* Header */}
      <Flex justifyContent="start" className="mb-3 gap-2">
        <Icon className="h-5 w-5 text-gray-500" aria-hidden="true" />
        <Title className="text-white">{title}</Title>
      </Flex>

      {/* Empty state content */}
      <div
        className="flex flex-col items-center py-4 text-center"
        data-testid={`summary-card-empty-content-${type}`}
      >
        <div
          className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-gray-800"
          aria-hidden="true"
        >
          <Icon className="h-6 w-6 text-gray-500" />
        </div>

        <Text className="mb-1 font-medium text-gray-300">
          No activity to summarize
        </Text>

        <Text className="text-sm text-gray-500">
          No high-priority events detected {timeframeText}.
        </Text>

        {/* Optional action button */}
        {onViewEvents && (
          <button
            type="button"
            onClick={onViewEvents}
            className={clsx(
              'mt-4 inline-flex items-center gap-2 rounded-md px-4 py-2',
              'bg-gray-800 text-sm font-medium text-[#76B900]',
              'transition-colors hover:bg-gray-700',
              'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]'
            )}
            data-testid={`summary-card-empty-view-events-${type}`}
          >
            View All Events
          </button>
        )}
      </div>
    </Card>
  );
}

export default SummaryCardEmpty;

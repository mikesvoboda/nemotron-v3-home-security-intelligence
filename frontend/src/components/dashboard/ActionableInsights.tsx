/**
 * ActionableInsights - Displays prioritized actionable insights from event analysis
 *
 * Features:
 * - Three insight types: entity (unknown persons), trend (activity patterns), camera (activity)
 * - Priority-based color coding (high=red, medium=yellow, low=green)
 * - Clickable cards that navigate to relevant views
 * - Expandable list for many insights
 * - Loading skeleton state
 * - Empty state messaging
 *
 * Related Linear issues: NEM-5418, NEM-5419, NEM-5420, NEM-5421
 */

import { Card, Text, Title } from '@tremor/react';
import { clsx } from 'clsx';
import {
  User,
  TrendingUp,
  Camera,
  ChevronDown,
  ChevronUp,
  Lightbulb,
  AlertTriangle,
} from 'lucide-react';
import { useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * Insight schema matching backend InsightSchema
 * TODO: Import from generated types once available
 */
export interface InsightSchema {
  type: 'camera' | 'entity' | 'trend';
  priority: number;
  title: string;
  description: string;
  action_url: string | null;
}

export interface ActionableInsightsProps {
  /** List of insights to display */
  insights: InsightSchema[];
  /** Additional CSS classes */
  className?: string;
  /** Maximum insights to show before "Show more" button */
  maxInsights?: number;
  /** Loading state for skeleton display */
  isLoading?: boolean;
}

/**
 * Get icon component for insight type
 */
function getInsightIcon(type: InsightSchema['type']) {
  switch (type) {
    case 'entity':
      return User;
    case 'trend':
      return TrendingUp;
    case 'camera':
      return Camera;
    default:
      return Lightbulb;
  }
}

/**
 * Get priority-based styling
 */
function getPriorityStyles(priority: number): {
  border: string;
  bg: string;
  icon: string;
  text: string;
} {
  if (priority >= 8) {
    // High priority (unknown persons, critical trends)
    return {
      border: 'border-l-red-500',
      bg: 'bg-red-500/10',
      icon: 'text-red-500',
      text: 'text-red-400',
    };
  } else if (priority >= 5) {
    // Medium priority (camera activity, notable trends)
    return {
      border: 'border-l-yellow-500',
      bg: 'bg-yellow-500/10',
      icon: 'text-yellow-500',
      text: 'text-yellow-400',
    };
  } else {
    // Low priority (informational)
    return {
      border: 'border-l-green-500',
      bg: 'bg-green-500/10',
      icon: 'text-green-500',
      text: 'text-green-400',
    };
  }
}

/**
 * Loading skeleton for insights
 */
function InsightSkeleton() {
  return (
    <div className="animate-pulse space-y-3">
      {[1, 2, 3].map((i) => (
        <div
          key={i}
          className="flex items-start gap-3 rounded-lg border-l-4 border-gray-700 bg-gray-800/50 p-3"
        >
          <div className="h-8 w-8 rounded-lg bg-gray-700" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-32 rounded bg-gray-700" />
            <div className="h-3 w-48 rounded bg-gray-700" />
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * Empty state for no insights
 */
function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center">
      <div className="mb-3 rounded-full bg-green-500/10 p-3">
        <Lightbulb className="h-6 w-6 text-green-500" />
      </div>
      <Text className="text-gray-300">No actionable insights</Text>
      <Text className="text-sm text-gray-500">Property is quiet with no notable activity</Text>
    </div>
  );
}

/**
 * Individual insight card
 */
function InsightCard({
  insight,
  index,
  onClick,
}: {
  insight: InsightSchema;
  index: number;
  onClick?: () => void;
}) {
  const Icon = getInsightIcon(insight.type);
  const styles = getPriorityStyles(insight.priority);
  const isClickable = !!insight.action_url;

  const content = (
    <>
      <div className={clsx('flex-shrink-0 rounded-lg p-2', styles.bg)}>
        <Icon className={clsx('h-5 w-5', styles.icon)} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Text className={clsx('font-medium', styles.text)}>{insight.title}</Text>
          {insight.priority >= 8 && (
            <AlertTriangle className={clsx('h-4 w-4 flex-shrink-0', styles.icon)} />
          )}
        </div>
        <Text className="truncate text-sm text-gray-400">{insight.description}</Text>
      </div>
      {isClickable && (
        <ChevronDown className="h-4 w-4 flex-shrink-0 rotate-[-90deg] text-gray-500" />
      )}
    </>
  );

  const baseClasses = clsx(
    'flex w-full items-start gap-3 rounded-lg border-l-4 bg-[#1E1E1E] p-3 transition-colors',
    styles.border
  );

  if (isClickable) {
    return (
      <button
        data-testid={`insight-card-${index}`}
        className={clsx(
          baseClasses,
          'cursor-pointer text-left hover:bg-gray-800/50',
          'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]'
        )}
        onClick={onClick}
        aria-label={`${insight.title}: ${insight.description}. Click to view details.`}
      >
        {content}
      </button>
    );
  }

  return (
    <div data-testid={`insight-card-${index}`} className={baseClasses}>
      {content}
    </div>
  );
}

/**
 * ActionableInsights - Displays prioritized actionable insights
 */
export default function ActionableInsights({
  insights,
  className,
  maxInsights = 3,
  isLoading = false,
}: ActionableInsightsProps) {
  const navigate = useNavigate();
  const [isExpanded, setIsExpanded] = useState(false);

  // Sort insights by priority (highest first)
  const sortedInsights = useMemo(() => {
    return [...insights].sort((a, b) => b.priority - a.priority);
  }, [insights]);

  // Determine which insights to show
  const shouldShowExpander = sortedInsights.length > maxInsights;
  const visibleInsights = isExpanded ? sortedInsights : sortedInsights.slice(0, maxInsights);

  // Handle insight click
  const handleInsightClick = useCallback(
    (insight: InsightSchema) => {
      if (insight.action_url) {
        void navigate(insight.action_url);
      }
    },
    [navigate]
  );

  // Toggle expanded state
  const toggleExpanded = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="actionable-insights"
    >
      <div className="mb-4 flex items-center gap-2">
        <Lightbulb className="h-5 w-5 text-[#76B900]" />
        <Title className="text-white">Actionable Insights</Title>
      </div>

      {isLoading ? (
        <InsightSkeleton />
      ) : sortedInsights.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="space-y-3">
          {visibleInsights.map((insight, index) => (
            <InsightCard
              key={`${insight.type}-${insight.title}-${index}`}
              insight={insight}
              index={index}
              onClick={() => handleInsightClick(insight)}
            />
          ))}

          {shouldShowExpander && (
            <button
              onClick={toggleExpanded}
              className={clsx(
                'flex w-full items-center justify-center gap-1 rounded-lg py-2 text-sm',
                'text-gray-400 transition-colors hover:bg-gray-800/50 hover:text-white',
                'focus:outline-none focus:ring-2 focus:ring-[#76B900]'
              )}
            >
              {isExpanded ? (
                <>
                  Show less <ChevronUp className="h-4 w-4" />
                </>
              ) : (
                <>
                  Show more ({sortedInsights.length - maxInsights} more){' '}
                  <ChevronDown className="h-4 w-4" />
                </>
              )}
            </button>
          )}
        </div>
      )}
    </Card>
  );
}

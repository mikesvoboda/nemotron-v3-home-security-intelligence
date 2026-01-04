/**
 * RecommendationsPanel - Displays grouped prompt improvement suggestions
 *
 * Shows aggregated recommendations from AI audit analysis, grouped by category
 * with frequency counts and priority indicators.
 */

import { Card, Title, Badge, Text, Accordion, AccordionHeader, AccordionBody, AccordionList } from '@tremor/react';
import { clsx } from 'clsx';
import { Lightbulb, AlertTriangle, Info, ArrowRight } from 'lucide-react';

import type { AiAuditRecommendationItem } from '../../services/api';

export interface RecommendationsPanelProps {
  /** Recommendation items */
  recommendations: AiAuditRecommendationItem[];
  /** Total events analyzed */
  totalEventsAnalyzed: number;
  /** Callback when user clicks to open a recommendation in Prompt Playground */
  onOpenPlayground?: (recommendation: AiAuditRecommendationItem) => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Category labels and descriptions
 */
const CATEGORY_INFO: Record<string, { label: string; description: string; icon: typeof Lightbulb }> = {
  missing_context: {
    label: 'Missing Context',
    description: 'Information that would help the AI make better assessments',
    icon: AlertTriangle,
  },
  unused_data: {
    label: 'Unused Data',
    description: 'Provided data that was not useful for analysis',
    icon: Info,
  },
  model_gaps: {
    label: 'Model Gaps',
    description: 'AI models that should have provided data but did not',
    icon: AlertTriangle,
  },
  format_suggestions: {
    label: 'Format Suggestions',
    description: 'Ways to improve the prompt structure',
    icon: Lightbulb,
  },
  confusing_sections: {
    label: 'Confusing Sections',
    description: 'Parts of the prompt that were unclear or contradictory',
    icon: Info,
  },
};

/**
 * Get priority badge color
 */
function getPriorityColor(priority: string): 'red' | 'yellow' | 'gray' {
  switch (priority) {
    case 'high':
      return 'red';
    case 'medium':
      return 'yellow';
    default:
      return 'gray';
  }
}

/**
 * Group recommendations by category
 */
function groupByCategory(recommendations: AiAuditRecommendationItem[]): Map<string, AiAuditRecommendationItem[]> {
  const grouped = new Map<string, AiAuditRecommendationItem[]>();

  for (const rec of recommendations) {
    const existing = grouped.get(rec.category) || [];
    existing.push(rec);
    grouped.set(rec.category, existing);
  }

  return grouped;
}

/**
 * RecommendationsPanel - Grouped recommendations display
 */
export default function RecommendationsPanel({
  recommendations,
  totalEventsAnalyzed,
  onOpenPlayground,
  className,
}: RecommendationsPanelProps) {
  const groupedRecommendations = groupByCategory(recommendations);
  const hasRecommendations = recommendations.length > 0;

  // Get total high priority count
  const highPriorityCount = recommendations.filter((r) => r.priority === 'high').length;

  return (
    <Card
      className={clsx('border-gray-800 bg-[#1A1A1A] shadow-lg', className)}
      data-testid="recommendations-panel"
    >
      <div className="flex items-center justify-between">
        <Title className="flex items-center gap-2 text-white">
          <Lightbulb className="h-5 w-5 text-[#76B900]" />
          Prompt Improvement Recommendations
        </Title>
        <div className="flex items-center gap-3">
          {highPriorityCount > 0 && (
            <Badge color="red" size="sm">
              {highPriorityCount} High Priority
            </Badge>
          )}
          <Text className="text-sm text-gray-400">
            From {totalEventsAnalyzed.toLocaleString()} events
          </Text>
        </div>
      </div>

      {hasRecommendations ? (
        <AccordionList className="mt-4" data-testid="recommendations-accordion">
          {Array.from(groupedRecommendations.entries()).map(([category, items]) => {
            const categoryInfo = CATEGORY_INFO[category] || {
              label: category,
              description: '',
              icon: Info,
            };
            const CategoryIcon = categoryInfo.icon;
            const categoryHighPriority = items.filter((i) => i.priority === 'high').length;

            return (
              <Accordion key={category} data-testid={`recommendation-category-${category}`}>
                <AccordionHeader className="text-white hover:bg-gray-800/50">
                  <div className="flex w-full items-center justify-between pr-4">
                    <div className="flex items-center gap-3">
                      <CategoryIcon className="h-5 w-5 text-[#76B900]" />
                      <div>
                        <span className="font-medium">{categoryInfo.label}</span>
                        <Text className="text-xs text-gray-400">{categoryInfo.description}</Text>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge color="gray" size="sm">
                        {items.length} items
                      </Badge>
                      {categoryHighPriority > 0 && (
                        <Badge color="red" size="sm">
                          {categoryHighPriority} high
                        </Badge>
                      )}
                    </div>
                  </div>
                </AccordionHeader>
                <AccordionBody className="bg-black/20">
                  <ul className="space-y-3">
                    {items
                      .sort((a, b) => {
                        // Sort by priority (high first), then by frequency
                        const priorityOrder: Record<string, number> = { high: 0, medium: 1, low: 2 };
                        const aPriority = priorityOrder[a.priority] ?? 3;
                        const bPriority = priorityOrder[b.priority] ?? 3;
                        if (aPriority !== bPriority) return aPriority - bPriority;
                        return b.frequency - a.frequency;
                      })
                      .map((item, index) => (
                        <li
                          key={index}
                          className="flex items-start justify-between gap-4 rounded-lg bg-gray-900/50 p-3"
                          data-testid={`recommendation-item-${category}-${index}`}
                        >
                          <div className="flex items-start gap-2">
                            <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-[#76B900]" />
                            <span className="text-sm text-gray-300">{item.suggestion}</span>
                          </div>
                          <div className="flex flex-shrink-0 items-center gap-2">
                            <Badge color={getPriorityColor(item.priority)} size="xs">
                              {item.priority}
                            </Badge>
                            <Text className="text-xs text-gray-500">
                              {item.frequency}x
                            </Text>
                            {onOpenPlayground && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onOpenPlayground(item);
                                }}
                                className="ml-2 rounded p-1 text-gray-400 transition-colors hover:bg-gray-700 hover:text-[#76B900]"
                                aria-label="Open in Prompt Playground"
                                title="Open in Prompt Playground"
                                data-testid={`open-playground-${category}-${index}`}
                              >
                                <ArrowRight className="h-4 w-4" />
                              </button>
                            )}
                          </div>
                        </li>
                      ))}
                  </ul>
                </AccordionBody>
              </Accordion>
            );
          })}
        </AccordionList>
      ) : (
        <div className="flex h-48 items-center justify-center">
          <div className="text-center">
            <Lightbulb className="mx-auto mb-2 h-8 w-8 text-gray-600" />
            <p className="text-gray-500">No recommendations available</p>
            <p className="mt-1 text-xs text-gray-600">
              Recommendations will appear here once events are fully evaluated
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}

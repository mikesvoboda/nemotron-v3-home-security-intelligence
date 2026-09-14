/**
 * SuggestionExplanation - Expandable "Why This Matters" component
 *
 * Provides educational context about why a suggestion would improve the prompt.
 * Features:
 * - Expand/collapse with chevron animation
 * - Impact summary section
 * - Evidence from source events with clickable links
 * - Category-specific prompt engineering tips
 * - Dark theme with NVIDIA green accents
 * - Full keyboard accessibility
 */

import { clsx } from 'clsx';
import { ChevronRight, ChevronDown, Lightbulb, BarChart2, Sparkles } from 'lucide-react';
import { useState, useCallback } from 'react';

import type { EnrichedSuggestion } from '../../services/api';
import type { JSX } from 'react';

export interface SuggestionExplanationProps {
  /** The suggestion with explanation data */
  suggestion: EnrichedSuggestion;
  /** Callback when user clicks an event link */
  onEventClick?: (eventId: number) => void;
  /** Whether to start expanded */
  defaultExpanded?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Category-specific prompt engineering tips
 */
const CATEGORY_TIPS: Record<EnrichedSuggestion['category'], string> = {
  missing_context:
    'Temporal context variables work best near other time-related fields like timestamp and day_of_week.',
  unused_data: 'Consider removing unused fields to reduce token count and improve inference speed.',
  model_gaps:
    'Adding model-specific sections improves accuracy by giving each model the context it needs.',
  format_suggestions:
    'Clear section headers help the AI navigate complex prompts and extract relevant information.',
};

export default function SuggestionExplanation({
  suggestion,
  onEventClick,
  defaultExpanded = false,
  className,
}: SuggestionExplanationProps): JSX.Element {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  const handleToggle = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        handleToggle();
      }
    },
    [handleToggle]
  );

  const handleEventClick = useCallback(
    (eventId: number) => {
      onEventClick?.(eventId);
    },
    [onEventClick]
  );

  const handleEventKeyDown = useCallback(
    (event: React.KeyboardEvent, eventId: number) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        handleEventClick(eventId);
      }
    },
    [handleEventClick]
  );

  const hasEvents = suggestion.sourceEventIds.length > 0;
  const eventCount = suggestion.sourceEventIds.length;
  const tip = CATEGORY_TIPS[suggestion.category];

  return (
    <div
      data-testid="suggestion-explanation"
      className={clsx('rounded-lg border border-gray-700 bg-[#1A1A1A]', className)}
    >
      {/* Collapsible Header */}
      <button
        type="button"
        onClick={handleToggle}
        onKeyDown={handleKeyDown}
        aria-expanded={isExpanded}
        aria-controls="suggestion-explanation-content"
        className="flex w-full items-center gap-2 rounded-lg px-4 py-3 text-left transition-colors hover:bg-gray-800/50 focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]"
      >
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 text-[#76B900] transition-transform" />
        ) : (
          <ChevronRight className="h-4 w-4 text-gray-400 transition-transform" />
        )}
        <span className="text-sm font-medium text-gray-200">Why this matters</span>
      </button>

      {/* Expandable Content */}
      <div
        id="suggestion-explanation-content"
        className={clsx(
          'overflow-hidden transition-all duration-200 ease-in-out',
          isExpanded ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0'
        )}
        style={{ visibility: isExpanded ? 'visible' : 'hidden' }}
      >
        <div className="space-y-4 px-4 pb-4">
          {/* Impact Section */}
          <div className="rounded-lg border border-[#76B900]/30 bg-[#76B900]/10 p-3">
            <div className="flex items-start gap-2">
              <Lightbulb className="mt-0.5 h-4 w-4 flex-shrink-0 text-[#76B900]" />
              <div>
                <span className="text-xs font-semibold uppercase tracking-wide text-[#76B900]">
                  Impact
                </span>
                <p className="mt-1 text-sm text-gray-300">{suggestion.impactExplanation}</p>
              </div>
            </div>
          </div>

          {/* Evidence Section */}
          <div className="rounded-lg border border-gray-700 bg-black/20 p-3">
            <div className="flex items-start gap-2">
              <BarChart2 className="mt-0.5 h-4 w-4 flex-shrink-0 text-gray-400" />
              <div className="flex-1">
                <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                  Evidence
                </span>
                {hasEvents ? (
                  <>
                    <p className="mt-1 text-sm text-gray-300">
                      This suggestion came from {eventCount} events:
                    </p>
                    <ul className="mt-2 space-y-1">
                      {suggestion.sourceEventIds.map((eventId) => (
                        <li key={eventId} className="flex items-center gap-2">
                          <span className="text-sm text-gray-400">Event #{eventId}</span>
                          {onEventClick && (
                            <button
                              type="button"
                              onClick={() => handleEventClick(eventId)}
                              onKeyDown={(e) => handleEventKeyDown(e, eventId)}
                              className="text-xs text-[#76B900] hover:text-[#8CD100] hover:underline focus:outline-none focus:ring-1 focus:ring-[#76B900] focus:ring-offset-1 focus:ring-offset-[#1A1A1A]"
                              aria-label={`View event #${eventId}`}
                            >
                              view event
                            </button>
                          )}
                        </li>
                      ))}
                    </ul>
                  </>
                ) : (
                  <p className="mt-1 text-sm text-gray-500">
                    No events associated with this suggestion.
                  </p>
                )}
              </div>
            </div>
          </div>

          {/* Tip Section */}
          {tip && (
            <div className="rounded-lg border border-gray-700 bg-black/20 p-3">
              <div className="flex items-start gap-2">
                <Sparkles className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-400" />
                <div>
                  <span className="text-xs font-semibold uppercase tracking-wide text-amber-400">
                    Tip
                  </span>
                  <p className="mt-1 text-sm text-gray-300">{tip}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

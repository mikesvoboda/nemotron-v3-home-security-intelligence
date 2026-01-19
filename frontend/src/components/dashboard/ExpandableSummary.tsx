/**
 * ExpandableSummary - Collapsible/Expandable Summary Details Component
 *
 * Displays summary content with a toggle to show/hide full details.
 * Features smooth 300ms animation, keyboard accessibility, and sessionStorage persistence.
 *
 * @see NEM-2925
 */

import clsx from 'clsx';
import { formatDistanceToNow, parseISO, format } from 'date-fns';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { useRef, useEffect, useState, useCallback, useId } from 'react';

import type { Summary } from '@/types/summary';

import { useSummaryExpansion } from '@/hooks/useSummaryExpansion';

// NVIDIA brand green color
const NVIDIA_GREEN = '#76B900';

/**
 * Props for the ExpandableSummary component.
 */
export interface ExpandableSummaryProps {
  /** The summary data to display */
  summary: Summary;
  /** Whether the summary should be expanded by default */
  defaultExpanded?: boolean;
  /** Callback fired when expansion state changes */
  onExpandChange?: (expanded: boolean) => void;
  /** Additional CSS class name */
  className?: string;
  /** Type of summary for unique ID generation ('hourly' or 'daily') */
  summaryType?: 'hourly' | 'daily';
}

/**
 * Extract bullet points from content if available.
 * Looks for lines starting with bullet characters.
 *
 * @param content - The summary content
 * @returns Array of bullet point strings, or null if none found
 */
function extractBulletPoints(content: string): string[] | null {
  // Match lines starting with common bullet characters: -, *, or numbered lists
  const bulletRegex = /^[\s]*[-*\u2022]\s+(.+)$/gm;
  const numberedRegex = /^[\s]*\d+[.)]\s+(.+)$/gm;

  const bullets: string[] = [];

  // Extract dash/asterisk bullets
  let match: RegExpExecArray | null;
  while ((match = bulletRegex.exec(content)) !== null) {
    bullets.push(match[1].trim());
  }

  // Extract numbered bullets
  while ((match = numberedRegex.exec(content)) !== null) {
    bullets.push(match[1].trim());
  }

  return bullets.length > 0 ? bullets : null;
}

/**
 * Truncate prose content to a reasonable preview length.
 *
 * @param content - The full content
 * @param maxLength - Maximum characters to show (default: 150)
 * @returns Truncated string with ellipsis if needed
 */
function truncateProse(content: string, maxLength = 150): string {
  if (content.length <= maxLength) {
    return content;
  }

  // Find the last complete word within maxLength
  const truncated = content.substring(0, maxLength);
  const lastSpace = truncated.lastIndexOf(' ');

  if (lastSpace > maxLength * 0.7) {
    return truncated.substring(0, lastSpace) + '...';
  }

  return truncated + '...';
}

/**
 * Check if user prefers reduced motion.
 *
 * @returns true if reduced motion is preferred
 */
function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * ExpandableSummary component with smooth animation and accessibility.
 *
 * @example
 * ```tsx
 * <ExpandableSummary
 *   summary={summary}
 *   defaultExpanded={false}
 *   onExpandChange={(expanded) => console.log('Expanded:', expanded)}
 * />
 * ```
 */
export function ExpandableSummary({
  summary,
  defaultExpanded = false,
  onExpandChange,
  className,
  summaryType = 'hourly',
}: ExpandableSummaryProps) {
  // Generate unique IDs for ARIA attributes
  const uniqueId = useId();
  const buttonId = `expandable-summary-button-${uniqueId}`;
  const contentId = `expandable-summary-content-${uniqueId}`;

  // Use persisted expansion state
  const { isExpanded, setExpanded } = useSummaryExpansion({
    summaryId: `${summaryType}-${summary.id}`,
    defaultExpanded,
  });

  // Ref to measure content height for animation
  const contentRef = useRef<HTMLDivElement>(null);
  const [contentHeight, setContentHeight] = useState<number>(0);

  // Track whether reduced motion is preferred
  const [reducedMotion, setReducedMotion] = useState(false);

  // Initialize reduced motion preference
  useEffect(() => {
    setReducedMotion(prefersReducedMotion());

    // Listen for preference changes
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const handleChange = (e: MediaQueryListEvent) => {
      setReducedMotion(e.matches);
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  // Measure content height for smooth animation
  useEffect(() => {
    if (contentRef.current) {
      const observer = new ResizeObserver((entries) => {
        for (const entry of entries) {
          setContentHeight(entry.contentRect.height);
        }
      });

      observer.observe(contentRef.current);
      return () => observer.disconnect();
    }
  }, []);

  // Handle toggle with callback
  const handleToggle = useCallback(() => {
    const newExpanded = !isExpanded;
    setExpanded(newExpanded);
    onExpandChange?.(newExpanded);
  }, [isExpanded, setExpanded, onExpandChange]);

  // Handle keyboard events
  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        handleToggle();
      }
    },
    [handleToggle]
  );

  // Extract bullet points or prepare truncated preview
  const bulletPoints = extractBulletPoints(summary.content);
  const truncatedContent = truncateProse(summary.content);
  const hasLongContent =
    summary.content.length > 150 || bulletPoints !== null;

  // Format metadata
  const windowStart = format(parseISO(summary.windowStart), 'MMM d, h:mm a');
  const windowEnd = format(parseISO(summary.windowEnd), 'h:mm a');
  const generatedAgo = formatDistanceToNow(parseISO(summary.generatedAt), {
    addSuffix: true,
  });

  // Animation styles
  const animationDuration = reducedMotion ? '0ms' : '300ms';

  return (
    <div
      className={clsx('expandable-summary', className)}
      data-testid="expandable-summary"
      data-expanded={isExpanded}
    >
      {/* Collapsed Preview */}
      {!isExpanded && (
        <div
          className="text-gray-300"
          data-testid="expandable-summary-preview"
        >
          {bulletPoints ? (
            <ul className="list-inside list-disc space-y-1">
              {bulletPoints.slice(0, 2).map((point, index) => (
                <li key={index} className="text-sm">
                  {point}
                </li>
              ))}
              {bulletPoints.length > 2 && (
                <li className="text-sm text-gray-500">
                  ...and {bulletPoints.length - 2} more
                </li>
              )}
            </ul>
          ) : (
            <p className="text-sm leading-relaxed">{truncatedContent}</p>
          )}
        </div>
      )}

      {/* Expanded Content with Animation */}
      <div
        className="overflow-hidden"
        style={{
          height: isExpanded ? contentHeight : 0,
          transition: `height ${animationDuration} ease-in-out`,
          opacity: isExpanded ? 1 : 0,
        }}
        aria-hidden={!isExpanded}
      >
        <div
          ref={contentRef}
          id={contentId}
          className="rounded-lg bg-gray-800/50 p-4"
          data-testid="expandable-summary-expanded"
        >
          {/* Full Narrative */}
          <div className="mb-4">
            {bulletPoints ? (
              <ul className="list-inside list-disc space-y-2 text-gray-300">
                {bulletPoints.map((point, index) => (
                  <li key={index}>{point}</li>
                ))}
              </ul>
            ) : (
              <p className="leading-relaxed text-gray-300">{summary.content}</p>
            )}
          </div>

          {/* Metadata Footer */}
          <div
            className="border-t border-gray-700 pt-3 text-sm text-gray-500"
            data-testid="expandable-summary-metadata"
          >
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              <span>
                Time window: {windowStart} - {windowEnd}
              </span>
              <span>Generated {generatedAgo}</span>
              {summary.eventCount > 0 && (
                <span>
                  {summary.eventCount}{' '}
                  {summary.eventCount === 1 ? 'event' : 'events'}
                </span>
              )}
              {summary.maxRiskScore !== undefined && (
                <span>Max risk: {summary.maxRiskScore}</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Toggle Button */}
      {hasLongContent && (
        <button
          id={buttonId}
          type="button"
          onClick={handleToggle}
          onKeyDown={handleKeyDown}
          aria-expanded={isExpanded}
          aria-controls={contentId}
          className={clsx(
            'mt-3 flex items-center gap-1.5 text-sm font-medium transition-colors',
            'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
            'focus-visible:ring-offset-gray-900'
          )}
          style={{
            color: NVIDIA_GREEN,
          }}
          data-testid="expandable-summary-toggle"
        >
          {isExpanded ? (
            <>
              <ChevronUp
                className="h-4 w-4"
                aria-hidden="true"
                data-testid="chevron-up-icon"
              />
              <span>Hide Details</span>
            </>
          ) : (
            <>
              <ChevronDown
                className="h-4 w-4"
                aria-hidden="true"
                data-testid="chevron-down-icon"
              />
              <span>View Full Summary</span>
            </>
          )}
        </button>
      )}
    </div>
  );
}

export default ExpandableSummary;

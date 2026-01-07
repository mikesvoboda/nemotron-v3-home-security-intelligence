import { ChevronDown, ChevronUp } from 'lucide-react';
import { memo, useCallback, useMemo, useState } from 'react';

export interface TruncatedTextProps {
  /** The text to display (and potentially truncate) */
  text: string;
  /** Maximum number of characters before truncation (default: 200) */
  maxLength?: number;
  /** Maximum number of lines before truncation (takes precedence over maxLength) */
  maxLines?: number;
  /** Whether the text starts expanded (default: false) */
  initialExpanded?: boolean;
  /** Custom label for the "Show more" button */
  showMoreLabel?: string;
  /** Custom label for the "Show less" button */
  showLessLabel?: string;
  /** Callback fired when expanded state changes */
  onToggle?: (isExpanded: boolean) => void;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Truncates text at a word boundary near the specified maxLength.
 * Tries to avoid cutting words in half.
 */
function truncateAtWordBoundary(text: string, maxLength: number): string {
  if (text.length <= maxLength) {
    return text;
  }

  // Find the last space before maxLength
  const truncated = text.substring(0, maxLength);
  const lastSpaceIndex = truncated.lastIndexOf(' ');

  // If no space found, just cut at maxLength
  if (lastSpaceIndex === -1) {
    return truncated.trimEnd() + '...';
  }

  return truncated.substring(0, lastSpaceIndex).trimEnd() + '...';
}

/**
 * TruncatedText component displays text with optional truncation and expand/collapse functionality.
 *
 * Features:
 * - Truncates long text with "Show more" / "Show less" toggle
 * - Supports character-based (maxLength) or line-based (maxLines) truncation
 * - Smooth expand/collapse animation
 * - Maintains readability with dark theme styling
 * - Accessible with proper ARIA attributes
 */
const TruncatedText = memo(function TruncatedText({
  text,
  maxLength = 200,
  maxLines,
  initialExpanded = false,
  showMoreLabel = 'Show more',
  showLessLabel = 'Show less',
  onToggle,
  className = '',
}: TruncatedTextProps) {
  const [isExpanded, setIsExpanded] = useState(initialExpanded);

  // Determine if text needs truncation
  const shouldTruncate = useMemo(() => {
    if (!text || text.trim().length === 0) {
      return false;
    }
    // If maxLines is set, we always show truncation controls for long text
    // (actual line truncation is CSS-based)
    if (maxLines !== undefined) {
      // For line-based truncation, we need to show controls if text is long enough
      // This is a heuristic since we can't easily measure rendered lines
      return text.length > maxLength || text.split('\n').length > maxLines;
    }
    return text.length > maxLength;
  }, [text, maxLength, maxLines]);

  // Get truncated text for display
  const displayText = useMemo(() => {
    if (!shouldTruncate || isExpanded) {
      return text;
    }
    return truncateAtWordBoundary(text, maxLength);
  }, [text, maxLength, shouldTruncate, isExpanded]);

  // Handle toggle click
  const handleToggle = useCallback(() => {
    const newExpanded = !isExpanded;
    setIsExpanded(newExpanded);
    onToggle?.(newExpanded);
  }, [isExpanded, onToggle]);

  // If text is empty, render nothing special
  if (!text) {
    return (
      <div className={className} data-testid="truncated-text">
        <p className="text-sm leading-relaxed text-gray-200">{text}</p>
      </div>
    );
  }

  // Build line-clamp style if maxLines is specified and not expanded
  const lineClampStyle = maxLines && !isExpanded
    ? {
        display: '-webkit-box',
        WebkitLineClamp: maxLines,
        WebkitBoxOrient: 'vertical' as const,
        overflow: 'hidden',
      }
    : undefined;

  return (
    <div
      className={`transition-all duration-300 ease-in-out ${className}`}
      data-testid="truncated-text"
    >
      <p
        className="text-sm leading-relaxed text-gray-200"
        style={lineClampStyle}
      >
        {displayText}
      </p>
      {shouldTruncate && (
        <button
          type="button"
          onClick={handleToggle}
          className="mt-1 inline-flex items-center gap-1 text-sm font-medium text-[#76B900] transition-colors hover:text-[#88d200]"
          aria-expanded={isExpanded}
        >
          {isExpanded ? (
            <>
              {showLessLabel}
              <ChevronUp className="h-4 w-4" aria-hidden="true" />
            </>
          ) : (
            <>
              {showMoreLabel}
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
            </>
          )}
        </button>
      )}
    </div>
  );
});

export default TruncatedText;

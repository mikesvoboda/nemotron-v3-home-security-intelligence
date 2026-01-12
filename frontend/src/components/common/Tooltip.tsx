import { useEffect, useRef, useState } from 'react';

export interface TooltipProps {
  /** Content to display in the tooltip */
  content: React.ReactNode;
  /** The element that triggers the tooltip */
  children: React.ReactElement;
  /** Position of the tooltip relative to the trigger (default: 'top') */
  position?: 'top' | 'bottom' | 'left' | 'right';
  /** Delay before showing tooltip in ms (default: 200) */
  delay?: number;
  /** Additional CSS classes for the tooltip */
  className?: string;
  /** Disable the tooltip */
  disabled?: boolean;
}

/**
 * Tooltip component for displaying contextual information on hover.
 *
 * Provides accessible tooltip functionality with customizable positioning,
 * delay, and content. Supports keyboard focus for accessibility.
 *
 * @example
 * ```tsx
 * <Tooltip content="Risk level tuned based on your feedback">
 *   <button>
 *     <SlidersHorizontal className="h-4 w-4" />
 *   </button>
 * </Tooltip>
 * ```
 */
export default function Tooltip({
  content,
  children,
  position = 'top',
  delay = 200,
  className = '',
  disabled = false,
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const triggerRef = useRef<HTMLDivElement>(null);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const showTooltip = () => {
    if (disabled) return;

    timeoutRef.current = setTimeout(() => {
      setIsVisible(true);
    }, delay);
  };

  const hideTooltip = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }
    setIsVisible(false);
  };

  const handleFocus = () => {
    if (disabled) return;
    setIsVisible(true);
  };

  const handleBlur = () => {
    setIsVisible(false);
  };

  // Position classes for the tooltip
  const positionClasses: Record<typeof position, string> = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };

  // Arrow classes for the tooltip
  const arrowClasses: Record<typeof position, string> = {
    top: 'top-full left-1/2 -translate-x-1/2 border-t-gray-900 border-x-transparent border-b-transparent',
    bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-gray-900 border-x-transparent border-t-transparent',
    left: 'left-full top-1/2 -translate-y-1/2 border-l-gray-900 border-y-transparent border-r-transparent',
    right: 'right-full top-1/2 -translate-y-1/2 border-r-gray-900 border-y-transparent border-l-transparent',
  };

  // Generate unique ID for tooltip aria-describedby
  const tooltipId = `tooltip-${Math.random().toString(36).substring(2, 9)}`;

  return (
    // The wrapper div captures hover/focus events to show tooltip on interactive children
    // The children (buttons, links, etc.) provide the actual interactive semantics
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <div
      ref={triggerRef}
      className="relative inline-flex"
      onMouseEnter={showTooltip}
      onMouseLeave={hideTooltip}
      onFocus={handleFocus}
      onBlur={handleBlur}
      aria-describedby={isVisible && !disabled ? tooltipId : undefined}
    >
      {children}
      {isVisible && !disabled && (
        <div
          id={tooltipId}
          role="tooltip"
          data-testid="tooltip"
          className={`absolute z-50 max-w-xs rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-xs text-gray-200 shadow-lg ${positionClasses[position]} ${className}`}
        >
          {content}
          {/* Arrow */}
          <div
            className={`absolute h-0 w-0 border-4 ${arrowClasses[position]}`}
            aria-hidden="true"
          />
        </div>
      )}
    </div>
  );
}

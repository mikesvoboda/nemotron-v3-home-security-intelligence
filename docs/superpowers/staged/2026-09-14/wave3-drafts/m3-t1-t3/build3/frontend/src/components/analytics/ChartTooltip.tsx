/**
 * ChartTooltip - NVIDIA-themed tooltip component for analytics charts.
 *
 * Provides consistent, accessible tooltips with dark theme styling
 * that match the NVIDIA design language.
 *
 * @module components/analytics/ChartTooltip
 * @see NEM-3524
 */

import { clsx } from 'clsx';
import { useState, useCallback, useRef, useEffect } from 'react';

import type { ReactNode } from 'react';

/**
 * Props for ChartTooltip component.
 */
export interface ChartTooltipProps {
  /** Content to display in the tooltip */
  content: ReactNode;
  /** Children element that triggers the tooltip */
  children: ReactNode;
  /** Optional position preference */
  position?: 'top' | 'bottom' | 'left' | 'right';
  /** Optional additional CSS classes for the tooltip */
  className?: string;
  /** Whether the tooltip is disabled */
  disabled?: boolean;
  /** Optional delay before showing tooltip (ms) */
  delay?: number;
}

/**
 * Tooltip content item for displaying key-value pairs.
 */
export interface TooltipItem {
  /** Label for the item */
  label: string;
  /** Value to display */
  value: string | number;
  /** Optional color indicator */
  color?: string;
  /** Optional icon */
  icon?: ReactNode;
}

/**
 * Props for TooltipContent helper component.
 */
export interface TooltipContentProps {
  /** Title of the tooltip */
  title?: string;
  /** Subtitle or secondary info */
  subtitle?: string;
  /** Array of items to display */
  items?: TooltipItem[];
  /** Optional footer text */
  footer?: string;
}

/**
 * TooltipContent - Helper component for structured tooltip content.
 */
export function TooltipContent({ title, subtitle, items, footer }: TooltipContentProps) {
  return (
    <div className="space-y-1.5">
      {title && <div className="font-semibold text-white">{title}</div>}
      {subtitle && <div className="text-xs text-gray-400">{subtitle}</div>}
      {items && items.length > 0 && (
        <div className="space-y-1 pt-1">
          {items.map((item, index) => (
            <div key={index} className="flex items-center justify-between gap-3 text-sm">
              <div className="flex items-center gap-1.5">
                {item.color && (
                  <span
                    className="h-2.5 w-2.5 rounded-sm"
                    style={{ backgroundColor: item.color }}
                  />
                )}
                {item.icon}
                <span className="text-gray-300">{item.label}</span>
              </div>
              <span className="font-medium text-white">{item.value}</span>
            </div>
          ))}
        </div>
      )}
      {footer && (
        <div className="border-t border-gray-700 pt-1.5 text-xs text-gray-500">{footer}</div>
      )}
    </div>
  );
}

/**
 * ChartTooltip - NVIDIA-themed tooltip for chart elements.
 *
 * @example Basic usage
 * ```tsx
 * <ChartTooltip content="Click to view details">
 *   <button>Hover me</button>
 * </ChartTooltip>
 * ```
 *
 * @example With structured content
 * ```tsx
 * <ChartTooltip
 *   content={
 *     <TooltipContent
 *       title="Monday 8:00 AM"
 *       items={[
 *         { label: 'Average', value: '5.2', color: '#76B900' },
 *         { label: 'Samples', value: '30' },
 *       ]}
 *       footer="Peak activity hour"
 *     />
 *   }
 * >
 *   <div className="cell" />
 * </ChartTooltip>
 * ```
 */
export default function ChartTooltip({
  content,
  children,
  position = 'top',
  className,
  disabled = false,
  delay = 100,
}: ChartTooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<number | null>(null);

  const calculatePosition = useCallback(() => {
    if (!triggerRef.current || !tooltipRef.current) return;

    const triggerRect = triggerRef.current.getBoundingClientRect();
    const tooltipRect = tooltipRef.current.getBoundingClientRect();
    const padding = 8;

    let top = 0;
    let left = 0;

    switch (position) {
      case 'top':
        top = triggerRect.top - tooltipRect.height - padding;
        left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2;
        break;
      case 'bottom':
        top = triggerRect.bottom + padding;
        left = triggerRect.left + triggerRect.width / 2 - tooltipRect.width / 2;
        break;
      case 'left':
        top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2;
        left = triggerRect.left - tooltipRect.width - padding;
        break;
      case 'right':
        top = triggerRect.top + triggerRect.height / 2 - tooltipRect.height / 2;
        left = triggerRect.right + padding;
        break;
    }

    // Keep tooltip within viewport
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    if (left < padding) left = padding;
    if (left + tooltipRect.width > viewportWidth - padding) {
      left = viewportWidth - tooltipRect.width - padding;
    }
    if (top < padding) top = padding;
    if (top + tooltipRect.height > viewportHeight - padding) {
      top = viewportHeight - tooltipRect.height - padding;
    }

    setTooltipPosition({ top, left });
  }, [position]);

  const showTooltip = useCallback(() => {
    if (disabled) return;
    timeoutRef.current = window.setTimeout(() => {
      setIsVisible(true);
    }, delay);
  }, [disabled, delay]);

  const hideTooltip = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    setIsVisible(false);
  }, []);

  useEffect(() => {
    if (isVisible) {
      calculatePosition();
    }
  }, [isVisible, calculatePosition]);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  if (disabled) {
    return <>{children}</>;
  }

  return (
    <>
      {/* eslint-disable-next-line jsx-a11y/no-static-element-interactions -- Wrapper passes events to children */}
      <span
        ref={triggerRef}
        onMouseEnter={showTooltip}
        onMouseLeave={hideTooltip}
        onFocus={showTooltip}
        onBlur={hideTooltip}
        className="inline-block"
      >
        {children}
      </span>
      {isVisible && (
        <div
          ref={tooltipRef}
          role="tooltip"
          className={clsx(
            'fixed z-50 max-w-xs rounded-lg px-3 py-2 text-sm shadow-xl',
            'border border-gray-700 bg-gray-900',
            'pointer-events-none',
            'animate-in fade-in-0 zoom-in-95 duration-100',
            className
          )}
          style={{
            top: tooltipPosition.top,
            left: tooltipPosition.left,
          }}
          data-testid="chart-tooltip"
        >
          {content}
        </div>
      )}
    </>
  );
}

export { ChartTooltip };

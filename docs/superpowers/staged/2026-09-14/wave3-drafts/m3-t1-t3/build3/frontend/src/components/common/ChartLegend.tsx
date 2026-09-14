/**
 * ChartLegend - Mobile-friendly legend component for charts
 *
 * Features:
 * - Horizontal, vertical, or auto orientation
 * - Collapsible with "+N more" button when items exceed maxVisibleItems
 * - Clickable items for filtering (via onItemClick callback)
 * - 44px minimum touch targets for accessibility
 * - Truncated labels with configurable max width
 * - Optional value display with custom formatting
 */

import { clsx } from 'clsx';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { useState, useCallback } from 'react';

/**
 * Legend item data structure
 */
export interface ChartLegendItem {
  /** Display name of the legend item */
  name: string;
  /** Numeric value associated with the item */
  value: number;
  /** Color for the legend dot (hex, rgb, or CSS color name) */
  color: string;
}

/**
 * Legend orientation options
 */
export type ChartLegendOrientation = 'horizontal' | 'vertical' | 'auto';

/**
 * ChartLegend component props
 */
export interface ChartLegendProps {
  /** Array of legend items to display */
  items: ChartLegendItem[];
  /** Layout orientation - auto switches based on viewport */
  orientation?: ChartLegendOrientation;
  /** Maximum visible items before collapsing (0 = no collapse) */
  maxVisibleItems?: number;
  /** Callback when an item is clicked (for filtering) */
  onItemClick?: (item: ChartLegendItem) => void;
  /** Show values next to labels */
  showValue?: boolean;
  /** Custom value formatter */
  valueFormatter?: (value: number) => string;
  /** Use compact styling (smaller text/margins) */
  compact?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Default value formatter
 */
const defaultValueFormatter = (value: number): string => value.toString();

/**
 * ChartLegend component for displaying chart legends with mobile optimization
 *
 * @example
 * ```tsx
 * const items = [
 *   { name: 'Person', value: 150, color: '#10b981' },
 *   { name: 'Vehicle', value: 89, color: '#3b82f6' },
 * ];
 *
 * <ChartLegend
 *   items={items}
 *   orientation="horizontal"
 *   maxVisibleItems={3}
 *   onItemClick={(item) => console.log('Clicked:', item)}
 * />
 * ```
 */
export default function ChartLegend({
  items,
  orientation = 'horizontal',
  maxVisibleItems = 0,
  onItemClick,
  showValue = false,
  valueFormatter = defaultValueFormatter,
  compact = false,
  className,
}: ChartLegendProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Toggle expand/collapse
  const handleToggleExpand = useCallback(() => {
    setIsExpanded((prev) => !prev);
  }, []);

  // Handle item click
  const handleItemClick = useCallback(
    (item: ChartLegendItem) => {
      if (onItemClick) {
        onItemClick(item);
      }
    },
    [onItemClick]
  );

  // Return null for empty items
  if (items.length === 0) {
    return null;
  }

  // Determine if collapse is needed
  const shouldCollapse = maxVisibleItems > 0 && items.length > maxVisibleItems;
  const visibleItems = shouldCollapse && !isExpanded ? items.slice(0, maxVisibleItems) : items;
  const hiddenCount = items.length - maxVisibleItems;

  // Determine orientation class
  const isVertical = orientation === 'vertical';
  const orientationClass = isVertical ? 'flex-col' : 'flex-wrap';

  // Label max width based on compact mode
  const labelMaxWidth = compact ? 'max-w-[60px]' : 'max-w-[100px]';

  return (
    <div
      data-testid="chart-legend"
      className={clsx('flex gap-2', orientationClass, compact ? 'gap-1' : 'gap-2', className)}
      role="list"
      aria-label="Chart legend"
    >
      {visibleItems.map((item) => {
        const ItemWrapper = onItemClick ? 'button' : 'div';
        const itemProps = onItemClick
          ? {
              onClick: () => handleItemClick(item),
              onKeyDown: (e: React.KeyboardEvent) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleItemClick(item);
                }
              },
              type: 'button' as const,
            }
          : {};

        return (
          <ItemWrapper
            key={item.name}
            data-testid="legend-item"
            className={clsx(
              'flex min-h-11 items-center gap-2 rounded-md px-2',
              'transition-colors',
              onItemClick && [
                'cursor-pointer',
                'hover:bg-gray-800/50',
                'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
              ],
              compact ? 'text-xs' : 'text-sm'
            )}
            role="listitem"
            {...itemProps}
          >
            {/* Color dot */}
            <span
              data-testid="legend-color-dot"
              className={clsx('flex-shrink-0 rounded-full', compact ? 'h-2 w-2' : 'h-3 w-3')}
              style={{ backgroundColor: item.color }}
              aria-hidden="true"
            />

            {/* Label */}
            <span className={clsx('truncate text-gray-300', labelMaxWidth)} title={item.name}>
              {item.name}
            </span>

            {/* Value (optional) */}
            {showValue && <span className="ml-1 text-gray-500">{valueFormatter(item.value)}</span>}
          </ItemWrapper>
        );
      })}

      {/* Expand/collapse button */}
      {shouldCollapse && (
        <button
          onClick={handleToggleExpand}
          className={clsx(
            'flex min-h-11 items-center gap-1 rounded-md px-2',
            'text-[#76B900] transition-colors',
            'hover:bg-gray-800/50',
            'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
            compact ? 'text-xs' : 'text-sm'
          )}
          type="button"
          aria-expanded={isExpanded}
          aria-label={isExpanded ? 'Show fewer items' : `Show ${hiddenCount} more items`}
        >
          {isExpanded ? (
            <>
              <span>Show less</span>
              <ChevronUp className="h-4 w-4" aria-hidden="true" />
            </>
          ) : (
            <>
              <span>+{hiddenCount} more</span>
              <ChevronDown className="h-4 w-4" aria-hidden="true" />
            </>
          )}
        </button>
      )}
    </div>
  );
}

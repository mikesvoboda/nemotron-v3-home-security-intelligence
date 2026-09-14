/**
 * ResponsiveChart - Wrapper component for responsive charts with mobile optimization
 *
 * Features:
 * - Title and subtitle support
 * - Legend integration with configurable position
 * - Fullscreen expansion button on mobile
 * - Loading skeleton state
 * - Error state with retry
 * - Empty state
 * - Children render prop with dimensions
 * - Fullscreen modal for detailed viewing
 */

import { clsx } from 'clsx';
import { AnimatePresence, motion } from 'framer-motion';
import { Maximize2, X, AlertTriangle, BarChart3 } from 'lucide-react';
import { useState, useRef, useCallback } from 'react';
import { createPortal } from 'react-dom';

import ChartLegend from './ChartLegend';
import Skeleton from './Skeleton';
import { useChartDimensions } from '../../hooks/useChartDimensions';

import type { ChartLegendItem, ChartLegendOrientation } from './ChartLegend';
import type { UseChartDimensionsOptions } from '../../hooks/useChartDimensions';

/**
 * Legend position options
 */
export type LegendPosition = 'top' | 'bottom' | 'right' | 'none';

/**
 * Dimensions passed to children render prop
 */
export interface ChartRenderDimensions {
  /** Container width in pixels */
  width: number;
  /** Calculated height in pixels */
  height: number;
}

/**
 * ResponsiveChart component props
 */
export interface ResponsiveChartProps {
  /** Chart title */
  title?: string;
  /** Chart subtitle */
  subtitle?: string;
  /** Legend items to display */
  legendItems?: ChartLegendItem[];
  /** Legend position (default: 'top') */
  legendPosition?: LegendPosition;
  /** Legend orientation (default: 'horizontal') */
  legendOrientation?: ChartLegendOrientation;
  /** Maximum visible legend items before collapse */
  legendMaxItems?: number;
  /** Callback when legend item is clicked */
  onLegendItemClick?: (item: ChartLegendItem) => void;
  /** Whether to show fullscreen button on mobile */
  enableFullscreen?: boolean;
  /** Loading state */
  isLoading?: boolean;
  /** Error message */
  error?: string | null;
  /** Callback for retry on error */
  onRetry?: () => void;
  /** Empty state */
  isEmpty?: boolean;
  /** Custom empty message */
  emptyMessage?: string;
  /** Chart dimension options */
  dimensionOptions?: UseChartDimensionsOptions;
  /** Additional CSS classes */
  className?: string;
  /** Children render prop receiving dimensions */
  children: (dimensions: ChartRenderDimensions) => React.ReactNode;
}

/**
 * ResponsiveChart provides a wrapper for charts with mobile optimization
 *
 * @example
 * ```tsx
 * <ResponsiveChart
 *   title="Detection Distribution"
 *   legendItems={legendData}
 *   enableFullscreen
 * >
 *   {({ width, height }) => (
 *     <DonutChart
 *       data={chartData}
 *       width={width}
 *       height={height}
 *     />
 *   )}
 * </ResponsiveChart>
 * ```
 */
export default function ResponsiveChart({
  title,
  subtitle,
  legendItems,
  legendPosition = 'top',
  legendOrientation = 'horizontal',
  legendMaxItems = 5,
  onLegendItemClick,
  enableFullscreen = false,
  isLoading = false,
  error = null,
  onRetry,
  isEmpty = false,
  emptyMessage = 'No data to display',
  dimensionOptions,
  className,
  children,
}: ResponsiveChartProps) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Get responsive dimensions
  const { width, height, isMobile, isCompact } = useChartDimensions(containerRef, dimensionOptions);

  // Open fullscreen modal
  const handleOpenFullscreen = useCallback(() => {
    setIsFullscreen(true);
  }, []);

  // Close fullscreen modal
  const handleCloseFullscreen = useCallback(() => {
    setIsFullscreen(false);
  }, []);

  // Render legend component
  const renderLegend = () => {
    if (!legendItems || legendItems.length === 0 || legendPosition === 'none') {
      return null;
    }

    return (
      <ChartLegend
        items={legendItems}
        orientation={legendOrientation}
        maxVisibleItems={legendMaxItems}
        onItemClick={onLegendItemClick}
        compact={isCompact}
      />
    );
  };

  // Render loading skeleton
  const renderLoading = () => (
    <div data-testid="chart-loading-skeleton" className="space-y-2">
      <Skeleton variant="rectangular" width="100%" height={height || 180} />
      <div className="flex gap-2">
        <Skeleton variant="text" width={60} height={16} />
        <Skeleton variant="text" width={60} height={16} />
        <Skeleton variant="text" width={60} height={16} />
      </div>
    </div>
  );

  // Render error state
  const renderError = () => (
    <div
      data-testid="chart-error"
      className="flex flex-col items-center justify-center py-8 text-center"
      style={{ minHeight: height || 180 }}
    >
      <AlertTriangle className="mb-2 h-8 w-8 text-yellow-500" aria-hidden="true" />
      <p className="text-sm text-gray-400">{error}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className={clsx(
            'mt-3 rounded-md px-4 py-2 text-sm font-medium',
            'bg-[#76B900] text-black hover:bg-[#88d200]',
            'focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-[#1A1A1A]',
            'min-h-11' // Touch target
          )}
          type="button"
        >
          Retry
        </button>
      )}
    </div>
  );

  // Render empty state
  const renderEmpty = () => (
    <div
      data-testid="chart-empty"
      className="flex flex-col items-center justify-center py-8 text-center"
      style={{ minHeight: height || 180 }}
    >
      <BarChart3 className="mb-2 h-8 w-8 text-gray-600" aria-hidden="true" />
      <p className="text-sm text-gray-500">{emptyMessage}</p>
    </div>
  );

  // Render fullscreen modal
  const renderFullscreenModal = () => {
    if (!isFullscreen || typeof document === 'undefined') {
      return null;
    }

    return createPortal(
      <AnimatePresence>
        <motion.div
          data-testid="fullscreen-modal"
          className="fixed inset-0 z-50 flex flex-col bg-[#0D0D0D]"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-gray-800 px-4 py-3">
            <div>
              {title && <h2 className="text-lg font-semibold text-white">{title}</h2>}
              {subtitle && <p className="text-sm text-gray-400">{subtitle}</p>}
            </div>
            <button
              onClick={handleCloseFullscreen}
              className={clsx(
                'flex h-11 min-h-11 w-11 min-w-11 items-center justify-center rounded-lg',
                'text-gray-400 hover:bg-gray-800 hover:text-white',
                'focus:outline-none focus:ring-2 focus:ring-[#76B900]'
              )}
              type="button"
              aria-label="Close fullscreen"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Chart content */}
          <div className="flex-1 overflow-auto p-4">
            {/* Fullscreen legend */}
            {legendItems && legendItems.length > 0 && (
              <div className="mb-4">
                <ChartLegend
                  items={legendItems}
                  orientation="horizontal"
                  maxVisibleItems={0} // Show all in fullscreen
                  onItemClick={onLegendItemClick}
                />
              </div>
            )}

            {/* Chart - use larger dimensions in fullscreen */}
            <div className="flex items-center justify-center" style={{ minHeight: '60vh' }}>
              {children({
                width: typeof window !== 'undefined' ? window.innerWidth - 32 : 400,
                height:
                  typeof window !== 'undefined' ? Math.min(window.innerHeight - 200, 500) : 300,
              })}
            </div>
          </div>
        </motion.div>
      </AnimatePresence>,
      document.body
    );
  };

  // Determine content to render
  const renderContent = () => {
    if (isLoading) {
      return renderLoading();
    }

    if (error) {
      return renderError();
    }

    if (isEmpty) {
      return renderEmpty();
    }

    return (
      <>
        {/* Top legend */}
        {legendPosition === 'top' && <div className="mb-3">{renderLegend()}</div>}

        {/* Chart container */}
        <div ref={containerRef} className="w-full" data-testid="chart-container">
          {children({ width, height })}
        </div>

        {/* Bottom legend */}
        {legendPosition === 'bottom' && <div className="mt-3">{renderLegend()}</div>}

        {/* Right legend */}
        {legendPosition === 'right' && (
          <div className="ml-4 flex-shrink-0">
            <ChartLegend
              items={legendItems || []}
              orientation="vertical"
              maxVisibleItems={legendMaxItems}
              onItemClick={onLegendItemClick}
              compact={isCompact}
            />
          </div>
        )}
      </>
    );
  };

  return (
    <>
      <figure
        data-testid="responsive-chart"
        className={clsx('relative', legendPosition === 'right' && 'flex items-start', className)}
        role="figure"
        aria-label={title}
      >
        {/* Header with title and fullscreen button */}
        {(title || (enableFullscreen && isMobile)) && (
          <div className="mb-3 flex items-start justify-between">
            <div>
              {title && <h3 className="text-sm font-medium text-white">{title}</h3>}
              {subtitle && <p className="text-xs text-gray-400">{subtitle}</p>}
            </div>

            {/* Fullscreen button (mobile only) */}
            {enableFullscreen && isMobile && !isLoading && !error && !isEmpty && (
              <button
                onClick={handleOpenFullscreen}
                className={clsx(
                  'flex h-11 min-h-11 w-11 min-w-11 items-center justify-center rounded-lg',
                  'text-gray-400 hover:bg-gray-800 hover:text-white',
                  'focus:outline-none focus:ring-2 focus:ring-[#76B900]'
                )}
                type="button"
                aria-label="Expand chart to fullscreen"
              >
                <Maximize2 className="h-5 w-5" />
              </button>
            )}
          </div>
        )}

        {/* Main content */}
        <div className={clsx(legendPosition === 'right' && 'flex-1')}>{renderContent()}</div>
      </figure>

      {/* Fullscreen modal */}
      {renderFullscreenModal()}
    </>
  );
}

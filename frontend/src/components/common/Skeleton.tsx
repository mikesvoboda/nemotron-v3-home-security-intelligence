import { clsx } from 'clsx';

/**
 * Skeleton variant types for different use cases
 */
export type SkeletonVariant = 'text' | 'circular' | 'rectangular';

/**
 * Skeleton component props
 */
export interface SkeletonProps {
  /**
   * Shape variant of the skeleton
   * - text: Small rounded corners, default 1em height and 100% width
   * - circular: Fully rounded (pill shape)
   * - rectangular: Larger rounded corners (rounded-lg)
   * @default 'text'
   */
  variant?: SkeletonVariant;
  /**
   * Width of the skeleton (number for px, or string like '100%')
   */
  width?: number | string;
  /**
   * Height of the skeleton (number for px, or string like '100%')
   */
  height?: number | string;
  /**
   * Number of lines to render (for text variant)
   * @default 1
   */
  lines?: number;
  /**
   * Additional CSS classes
   */
  className?: string;
  /**
   * Data test ID for testing
   */
  'data-testid'?: string;
}

/**
 * Mapping of variant to CSS classes
 */
const variantClasses: Record<SkeletonVariant, string> = {
  text: 'rounded',
  circular: 'rounded-full',
  rectangular: 'rounded-lg',
};

/**
 * Default dimensions by variant
 */
const defaultDimensions: Record<SkeletonVariant, { width?: string; height?: string }> = {
  text: { width: '100%', height: '1em' },
  circular: {},
  rectangular: {},
};

/**
 * Skeleton loading placeholder component
 *
 * Used to display a loading state placeholder while content is being fetched.
 * Supports multiple variants for different content shapes.
 *
 * @example
 * ```tsx
 * // Text placeholder
 * <Skeleton variant="text" width={200} height={20} />
 *
 * // Avatar placeholder
 * <Skeleton variant="circular" width={48} height={48} />
 *
 * // Card placeholder
 * <Skeleton variant="rectangular" width="100%" height={200} />
 *
 * // Multiple lines of text
 * <Skeleton variant="text" lines={3} />
 * ```
 */
export default function Skeleton({
  variant = 'text',
  width,
  height,
  lines = 1,
  className,
  'data-testid': dataTestId,
}: SkeletonProps) {
  const defaults = defaultDimensions[variant];

  // For circular variant, if only one dimension specified, use it for both
  let finalWidth = width;
  let finalHeight = height;

  if (variant === 'circular') {
    if (width !== undefined && height === undefined) {
      finalHeight = width;
    } else if (height !== undefined && width === undefined) {
      finalWidth = height;
    }
  }

  // Apply defaults if no dimensions provided
  const widthStyle = finalWidth !== undefined
    ? (typeof finalWidth === 'number' ? `${finalWidth}px` : finalWidth)
    : defaults.width;
  const heightStyle = finalHeight !== undefined
    ? (typeof finalHeight === 'number' ? `${finalHeight}px` : finalHeight)
    : defaults.height;

  const baseClasses = clsx(
    'bg-gray-800',
    'animate-pulse',
    variantClasses[variant],
    className
  );

  // Render multiple lines if lines > 1
  if (lines > 1) {
    return (
      <div
        className="flex flex-col gap-2"
        data-testid={dataTestId}
        aria-hidden="true"
        role="presentation"
      >
        {Array.from({ length: lines }, (_, index) => {
          const isLastLine = index === lines - 1;
          const lineWidth = isLastLine && variant === 'text' ? '80%' : widthStyle;

          return (
            <div
              key={index}
              className={baseClasses}
              style={{
                width: lineWidth,
                height: heightStyle,
              }}
              data-skeleton-line=""
              data-testid={dataTestId ? `${dataTestId}-line-${index}` : undefined}
            />
          );
        })}
      </div>
    );
  }

  return (
    <div
      className={baseClasses}
      style={{
        width: widthStyle,
        height: heightStyle,
      }}
      data-testid={dataTestId}
      aria-hidden="true"
      role="presentation"
    />
  );
}

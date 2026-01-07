import { clsx } from 'clsx';

import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

export interface EmptyStateAction {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary';
}

export interface EmptyStateProps {
  /**
   * The icon to display in the empty state
   * Pass a Lucide icon component
   */
  icon: LucideIcon;

  /**
   * The main title of the empty state
   */
  title: string;

  /**
   * The description text explaining why the state is empty
   * and/or what the user can do
   */
  description: string | ReactNode;

  /**
   * Optional action button(s) for the user to take
   */
  actions?: EmptyStateAction[];

  /**
   * Optional additional content to display below the description
   * Useful for suggestions or tips
   */
  children?: ReactNode;

  /**
   * Visual variant of the icon container
   * - 'default': NVIDIA green accent circle
   * - 'muted': Gray circle
   * - 'warning': Yellow/orange accent
   */
  variant?: 'default' | 'muted' | 'warning';

  /**
   * Size of the empty state
   * - 'sm': Compact size for smaller containers
   * - 'md': Default size
   * - 'lg': Larger size for full-page empty states
   */
  size?: 'sm' | 'md' | 'lg';

  /**
   * Additional CSS classes
   */
  className?: string;

  /**
   * Test ID for testing
   */
  testId?: string;
}

/**
 * EmptyState component provides a consistent, visually appealing way to display
 * empty states across the application. It follows the NVIDIA dark theme design
 * with green accents and provides flexibility for different use cases.
 *
 * Features:
 * - Consistent icon presentation with colored background
 * - Clear title and description
 * - Optional action buttons
 * - Support for additional content (tips, suggestions)
 * - Multiple visual variants and sizes
 * - Dark theme compatible
 */
export default function EmptyState({
  icon: Icon,
  title,
  description,
  actions,
  children,
  variant = 'default',
  size = 'md',
  className,
  testId = 'empty-state',
}: EmptyStateProps) {
  // Icon container styling based on variant
  const iconContainerClasses = clsx(
    'mx-auto flex items-center justify-center rounded-full',
    {
      // Default: NVIDIA green accent
      'bg-[#76B900]/10': variant === 'default',
      // Muted: Gray
      'bg-gray-800': variant === 'muted',
      // Warning: Yellow/orange
      'bg-yellow-500/10': variant === 'warning',
    },
    {
      // Size variations for icon container
      'h-12 w-12': size === 'sm',
      'h-16 w-16 md:h-20 md:w-20': size === 'md',
      'h-20 w-20 md:h-24 md:w-24': size === 'lg',
    }
  );

  // Icon styling based on variant
  const iconClasses = clsx({
    // Default: NVIDIA green
    'text-[#76B900]': variant === 'default',
    // Muted: Gray
    'text-gray-500': variant === 'muted',
    // Warning: Yellow
    'text-yellow-500': variant === 'warning',
  });

  // Icon size based on size prop
  const iconSize = {
    sm: 'h-6 w-6',
    md: 'h-8 w-8 md:h-10 md:w-10',
    lg: 'h-10 w-10 md:h-12 md:w-12',
  }[size];

  // Title styling based on size
  const titleClasses = clsx('font-semibold text-white', {
    'text-base': size === 'sm',
    'text-lg md:text-xl': size === 'md',
    'text-xl md:text-2xl': size === 'lg',
  });

  // Description styling based on size
  const descriptionClasses = clsx('text-gray-400', {
    'text-xs': size === 'sm',
    'text-sm': size === 'md',
    'text-sm md:text-base': size === 'lg',
  });

  // Spacing based on size
  const spacingClasses = clsx({
    'mb-3': size === 'sm',
    'mb-4 md:mb-6': size === 'md',
    'mb-6': size === 'lg',
  });

  return (
    <div
      className={clsx(
        'flex flex-col items-center justify-center px-4 py-8 text-center',
        {
          'min-h-[200px]': size === 'sm',
          'min-h-[300px] md:min-h-[400px]': size === 'md',
          'min-h-[400px] md:min-h-[500px]': size === 'lg',
        },
        className
      )}
      data-testid={testId}
    >
      {/* Icon Container */}
      <div className={clsx(iconContainerClasses, spacingClasses)}>
        <Icon className={clsx(iconClasses, iconSize)} aria-hidden="true" />
      </div>

      {/* Title */}
      <h2 className={clsx(titleClasses, 'mb-2 md:mb-3')}>{title}</h2>

      {/* Description */}
      <div className={clsx(descriptionClasses, 'max-w-md')}>
        {typeof description === 'string' ? <p>{description}</p> : description}
      </div>

      {/* Actions */}
      {actions && actions.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-center gap-3 md:mt-6">
          {actions.map((action, index) => (
            <button
              key={index}
              onClick={action.onClick}
              className={clsx(
                'rounded-md px-4 py-2 text-sm font-medium transition-colors',
                action.variant === 'primary'
                  ? 'bg-[#76B900] text-black hover:bg-[#88d200]'
                  : 'border border-gray-700 bg-[#1A1A1A] text-gray-300 hover:border-gray-600 hover:bg-[#252525]'
              )}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}

      {/* Additional Content (e.g., tips, suggestions) */}
      {children && <div className="mt-4 w-full max-w-md md:mt-6">{children}</div>}
    </div>
  );
}

import { forwardRef, type ButtonHTMLAttributes, type ReactElement, type ReactNode } from 'react';

import Tooltip from './Tooltip';

/**
 * IconButton size options - all sizes enforce minimum 44x44px touch target (WCAG 2.5.5 AAA)
 */
export type IconButtonSize = 'sm' | 'md' | 'lg';

/**
 * IconButton variant options
 */
export type IconButtonVariant = 'ghost' | 'outline' | 'solid';

/**
 * IconButton component props
 *
 * NOTE: aria-label is required for accessibility - icon-only buttons must have descriptive labels
 */
export interface IconButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> {
  /**
   * Icon element to render (typically a Lucide icon)
   */
  icon: ReactElement;
  /**
   * Required accessible label for the button
   * Screen readers will announce this text
   */
  'aria-label': string;
  /**
   * Button size variant - all sizes meet WCAG 2.5.5 AAA 44x44px minimum
   * @default 'md'
   */
  size?: IconButtonSize;
  /**
   * Visual variant of the button
   * @default 'ghost'
   */
  variant?: IconButtonVariant;
  /**
   * Whether the button is in a loading state
   * Shows a spinner and disables the button
   * @default false
   */
  isLoading?: boolean;
  /**
   * Whether the button is in an active/selected state
   * @default false
   */
  isActive?: boolean;
  /**
   * Optional tooltip text - shown on hover when provided
   */
  tooltip?: ReactNode;
  /**
   * Tooltip position
   * @default 'top'
   */
  tooltipPosition?: 'top' | 'bottom' | 'left' | 'right';
}

/**
 * Size classes - ALL sizes enforce minimum 44x44px (h-11 w-11 = 2.75rem = 44px)
 * This ensures WCAG 2.5.5 AAA compliance for touch target sizes
 */
const sizeClasses: Record<IconButtonSize, string> = {
  sm: 'h-11 w-11 min-h-11 min-w-11 [&>svg]:h-4 [&>svg]:w-4',
  md: 'h-11 w-11 min-h-11 min-w-11 [&>svg]:h-5 [&>svg]:w-5',
  lg: 'h-12 w-12 min-h-12 min-w-12 [&>svg]:h-6 [&>svg]:w-6',
};

/**
 * Variant classes for different button styles
 */
const variantClasses: Record<IconButtonVariant, string> = {
  ghost:
    'bg-transparent text-gray-400 hover:bg-gray-800 hover:text-white active:bg-gray-700',
  outline:
    'border border-gray-700 bg-transparent text-gray-400 hover:border-gray-600 hover:bg-gray-800 hover:text-white active:bg-gray-700',
  solid:
    'bg-gray-800 text-white hover:bg-gray-700 active:bg-gray-600',
};

/**
 * Active state classes for each variant
 */
const activeClasses: Record<IconButtonVariant, string> = {
  ghost: 'bg-gray-800 text-white',
  outline: 'border-[#76B900] bg-[#76B900]/10 text-[#76B900]',
  solid: 'bg-[#76B900] text-black',
};

/**
 * Loading spinner component
 */
function LoadingSpinner({ className }: { className?: string }) {
  return (
    <svg
      className={`animate-spin ${className || 'h-5 w-5'}`}
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

/**
 * IconButton - Accessible icon-only button with enforced 44x44px minimum touch target
 *
 * Features:
 * - WCAG 2.5.5 AAA compliant touch target (minimum 44x44px on all sizes)
 * - Required aria-label for accessibility
 * - Loading state with spinner
 * - Active/selected state
 * - Optional tooltip support
 * - Focus ring styling with NVIDIA green accent
 * - Multiple variants (ghost, outline, solid)
 *
 * @example
 * ```tsx
 * // Basic usage
 * <IconButton
 *   icon={<X />}
 *   aria-label="Close modal"
 *   onClick={onClose}
 * />
 *
 * // With tooltip
 * <IconButton
 *   icon={<Settings />}
 *   aria-label="Open settings"
 *   tooltip="Settings"
 *   variant="outline"
 * />
 *
 * // Loading state
 * <IconButton
 *   icon={<Save />}
 *   aria-label="Save changes"
 *   isLoading={isSaving}
 * />
 *
 * // Active state
 * <IconButton
 *   icon={<Filter />}
 *   aria-label="Toggle filter"
 *   isActive={isFilterActive}
 * />
 * ```
 */
const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  (
    {
      icon,
      'aria-label': ariaLabel,
      size = 'md',
      variant = 'ghost',
      isLoading = false,
      isActive = false,
      tooltip,
      tooltipPosition = 'top',
      className = '',
      disabled,
      type = 'button',
      ...props
    },
    ref
  ) => {
    const baseClasses = [
      // Layout
      'inline-flex items-center justify-center',
      // Shape
      'rounded-lg',
      // Transition
      'transition-colors duration-150',
      // Focus styles - NVIDIA green ring
      'focus:outline-none focus-visible:ring-2 focus-visible:ring-[#76B900] focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900',
      // Size classes (enforces min 44x44px)
      sizeClasses[size],
      // Variant classes
      isActive ? activeClasses[variant] : variantClasses[variant],
      // Disabled state
      disabled || isLoading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer',
      // Loading cursor
      isLoading ? 'cursor-wait' : '',
      // Custom classes
      className,
    ]
      .filter(Boolean)
      .join(' ');

    const button = (
      <button
        ref={ref}
        type={type}
        className={baseClasses}
        disabled={disabled || isLoading}
        aria-label={ariaLabel}
        aria-busy={isLoading}
        aria-pressed={isActive}
        {...props}
      >
        {isLoading ? <LoadingSpinner /> : icon}
      </button>
    );

    // Wrap in tooltip if provided
    if (tooltip) {
      return (
        <Tooltip content={tooltip} position={tooltipPosition} disabled={disabled || isLoading}>
          {button}
        </Tooltip>
      );
    }

    return button;
  }
);

IconButton.displayName = 'IconButton';

export default IconButton;

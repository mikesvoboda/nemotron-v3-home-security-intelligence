import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';

/**
 * Button variant options
 */
export type ButtonVariant =
  | 'primary'
  | 'secondary'
  | 'ghost'
  | 'outline'
  | 'outline-primary'
  | 'danger';

/**
 * Button size options
 */
export type ButtonSize = 'sm' | 'md' | 'lg';

/**
 * Button component props
 */
export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /**
   * Visual variant of the button
   * @default 'primary'
   */
  variant?: ButtonVariant;
  /**
   * Size of the button
   * @default 'md'
   */
  size?: ButtonSize;
  /**
   * Whether the button is in a loading state
   * @default false
   */
  isLoading?: boolean;
  /**
   * Icon to display before the button text
   */
  leftIcon?: ReactNode;
  /**
   * Icon to display after the button text
   */
  rightIcon?: ReactNode;
  /**
   * Whether this is an icon-only button
   * @default false
   */
  isIconOnly?: boolean;
  /**
   * Whether the button should take full width
   * @default false
   */
  fullWidth?: boolean;
  /**
   * Button children (text/content)
   */
  children?: ReactNode;
}

/**
 * Mapping of variant to CSS class
 */
const variantClasses: Record<ButtonVariant, string> = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  ghost: 'btn-ghost',
  outline: 'btn-outline',
  'outline-primary': 'btn-outline-primary',
  danger: 'btn-danger',
};

/**
 * Mapping of size to CSS class
 */
const sizeClasses: Record<ButtonSize, string> = {
  sm: 'btn-sm',
  md: '',
  lg: 'btn-lg',
};

/**
 * Loading spinner component for button loading state
 */
function LoadingSpinner() {
  return (
    <svg
      className="h-4 w-4 animate-spin"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

/**
 * Button component with multiple variants, sizes, and states.
 *
 * Features:
 * - Multiple visual variants (primary, secondary, ghost, outline, danger)
 * - Three sizes (sm, md, lg)
 * - Loading state with spinner
 * - Icon support (left, right, icon-only)
 * - Full width option
 * - WCAG 2.1 AA compliant focus indicators
 * - Smooth hover and active state transitions
 *
 * @example
 * ```tsx
 * // Basic usage
 * <Button>Click me</Button>
 *
 * // With variant and size
 * <Button variant="secondary" size="lg">Large Secondary</Button>
 *
 * // With icons
 * <Button leftIcon={<PlusIcon />}>Add Item</Button>
 *
 * // Loading state
 * <Button isLoading>Saving...</Button>
 *
 * // Icon only
 * <Button variant="ghost" isIconOnly aria-label="Close">
 *   <XIcon />
 * </Button>
 * ```
 */
const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      isLoading = false,
      leftIcon,
      rightIcon,
      isIconOnly = false,
      fullWidth = false,
      children,
      className = '',
      disabled,
      type = 'button',
      ...props
    },
    ref
  ) => {
    const baseClasses = [
      variantClasses[variant],
      sizeClasses[size],
      isIconOnly ? 'btn-icon' : '',
      fullWidth ? 'w-full' : '',
      isLoading ? 'cursor-wait' : '',
      className,
    ]
      .filter(Boolean)
      .join(' ');

    return (
      <button
        ref={ref}
        type={type}
        className={baseClasses}
        disabled={disabled || isLoading}
        aria-busy={isLoading}
        {...props}
      >
        {isLoading && (
          <span className="mr-2">
            <LoadingSpinner />
          </span>
        )}
        {!isLoading && leftIcon && <span className="mr-2">{leftIcon}</span>}
        {children}
        {!isLoading && rightIcon && <span className="ml-2">{rightIcon}</span>}
      </button>
    );
  }
);

Button.displayName = 'Button';

export default Button;

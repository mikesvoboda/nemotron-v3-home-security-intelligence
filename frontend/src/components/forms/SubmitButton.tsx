/**
 * SubmitButton - A form submit button that uses React 19's useFormStatus.
 *
 * This component automatically shows a pending state when the parent form
 * is submitting, without requiring prop drilling. It uses the new React 19
 * useFormStatus hook to access the form's pending state.
 *
 * @see NEM-3356 - Implement useActionState and useFormStatus for forms
 *
 * @example
 * ```tsx
 * import { useActionState } from 'react';
 *
 * function MyForm() {
 *   const [state, action, isPending] = useActionState(submitAction, initialState);
 *
 *   return (
 *     <form action={action}>
 *       <input name="email" required />
 *       <SubmitButton>Subscribe</SubmitButton>
 *     </form>
 *   );
 * }
 * ```
 */

import { clsx } from 'clsx';
import { Loader2 } from 'lucide-react';
import { type ReactNode } from 'react';
import { useFormStatus } from 'react-dom';

// ============================================================================
// Types
// ============================================================================

/**
 * Button variant styles.
 */
export type SubmitButtonVariant = 'primary' | 'secondary' | 'danger';

/**
 * Button size options.
 */
export type SubmitButtonSize = 'sm' | 'md' | 'lg';

/**
 * Props for the SubmitButton component.
 */
export interface SubmitButtonProps {
  /** Button content */
  children: ReactNode;
  /** Visual style variant */
  variant?: SubmitButtonVariant;
  /** Button size */
  size?: SubmitButtonSize;
  /** Additional class names */
  className?: string;
  /** Text to display while pending */
  pendingText?: string;
  /** Whether the button is disabled (in addition to form pending state) */
  disabled?: boolean;
  /** Icon to display before the text */
  icon?: ReactNode;
  /** Icon to display while pending (defaults to Loader2) */
  pendingIcon?: ReactNode;
  /** Full width button */
  fullWidth?: boolean;
  /** Test ID for testing */
  'data-testid'?: string;
}

// ============================================================================
// Style Mappings
// ============================================================================

const variantStyles: Record<SubmitButtonVariant, string> = {
  primary:
    'bg-[#76B900] text-gray-950 hover:bg-[#5c8f00] focus:ring-[#76B900] disabled:bg-[#76B900]/50',
  secondary:
    'bg-gray-700 text-white hover:bg-gray-600 focus:ring-gray-500 border border-gray-600 disabled:bg-gray-700/50',
  danger:
    'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500 disabled:bg-red-600/50',
};

const sizeStyles: Record<SubmitButtonSize, string> = {
  sm: 'px-3 py-1.5 text-sm gap-1.5',
  md: 'px-4 py-2 text-sm gap-2',
  lg: 'px-6 py-3 text-base gap-2.5',
};

const iconSizeStyles: Record<SubmitButtonSize, string> = {
  sm: 'h-3.5 w-3.5',
  md: 'h-4 w-4',
  lg: 'h-5 w-5',
};

// ============================================================================
// Component
// ============================================================================

/**
 * A form submit button that automatically shows pending state.
 *
 * Uses React 19's useFormStatus hook to detect when the parent form
 * is submitting, and displays appropriate loading UI without prop drilling.
 *
 * Features:
 * - Automatic pending state detection via useFormStatus
 * - Multiple visual variants (primary, secondary, danger)
 * - Size options (sm, md, lg)
 * - Custom pending text and icons
 * - Full accessibility support
 *
 * @example
 * ```tsx
 * // Basic usage
 * <SubmitButton>Save Changes</SubmitButton>
 *
 * // With custom pending text
 * <SubmitButton pendingText="Saving...">Save Changes</SubmitButton>
 *
 * // With icon
 * <SubmitButton icon={<Save className="h-4 w-4" />}>Save</SubmitButton>
 *
 * // Secondary variant
 * <SubmitButton variant="secondary">Cancel</SubmitButton>
 *
 * // Full width
 * <SubmitButton fullWidth>Submit Form</SubmitButton>
 * ```
 */
export function SubmitButton({
  children,
  variant = 'primary',
  size = 'md',
  className,
  pendingText,
  disabled = false,
  icon,
  pendingIcon,
  fullWidth = false,
  'data-testid': testId,
}: SubmitButtonProps) {
  // Get form pending state from React 19's useFormStatus
  const { pending } = useFormStatus();

  // Determine if button should be disabled
  const isDisabled = disabled || pending;

  // Get icon size class
  const iconSize = iconSizeStyles[size];

  // Default pending icon is a spinning loader
  const defaultPendingIcon = <Loader2 className={clsx(iconSize, 'animate-spin')} />;

  return (
    <button
      type="submit"
      disabled={isDisabled}
      className={clsx(
        // Base styles
        'inline-flex items-center justify-center rounded-md font-medium transition-colors',
        'focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-900',
        'disabled:cursor-not-allowed disabled:opacity-60',
        // Variant styles
        variantStyles[variant],
        // Size styles
        sizeStyles[size],
        // Full width
        fullWidth && 'w-full',
        // Custom className
        className
      )}
      data-testid={testId}
      aria-busy={pending}
      aria-disabled={isDisabled}
    >
      {/* Icon - show pending icon when pending, otherwise show regular icon */}
      {pending ? (
        pendingIcon || defaultPendingIcon
      ) : (
        icon && <span className={iconSize}>{icon}</span>
      )}

      {/* Text content */}
      <span>{pending ? (pendingText || children) : children}</span>
    </button>
  );
}

// ============================================================================
// Convenience Exports
// ============================================================================

/**
 * Primary submit button (green NVIDIA color).
 */
export function PrimarySubmitButton(props: Omit<SubmitButtonProps, 'variant'>) {
  return <SubmitButton {...props} variant="primary" />;
}

/**
 * Secondary submit button (gray).
 */
export function SecondarySubmitButton(props: Omit<SubmitButtonProps, 'variant'>) {
  return <SubmitButton {...props} variant="secondary" />;
}

/**
 * Danger submit button (red).
 */
export function DangerSubmitButton(props: Omit<SubmitButtonProps, 'variant'>) {
  return <SubmitButton {...props} variant="danger" />;
}

export default SubmitButton;

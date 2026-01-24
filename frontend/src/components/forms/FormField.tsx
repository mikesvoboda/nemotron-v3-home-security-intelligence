/**
 * FormField - A form field component that integrates with React 19 form actions.
 *
 * This component provides a complete form field with label, input, and error
 * display that works with the FormActionState from useFormAction.
 *
 * @see NEM-3356 - Implement useActionState and useFormStatus for forms
 *
 * @example
 * ```tsx
 * import { useActionState } from 'react';
 *
 * function MyForm() {
 *   const [state, action] = useActionState(submitAction, { status: 'idle' });
 *
 *   return (
 *     <form action={action}>
 *       <FormField
 *         name="email"
 *         label="Email Address"
 *         type="email"
 *         error={state.fieldErrors?.email}
 *         required
 *       />
 *       <SubmitButton>Subscribe</SubmitButton>
 *     </form>
 *   );
 * }
 * ```
 */

import { clsx } from 'clsx';
import { AlertCircle } from 'lucide-react';
import { type InputHTMLAttributes, type ReactNode, forwardRef, useId } from 'react';
import { useFormStatus } from 'react-dom';

// ============================================================================
// Types
// ============================================================================

/**
 * Props for the FormField component.
 */
export interface FormFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  /** Field name (used for form data) */
  name: string;
  /** Field label */
  label: string;
  /** Error message to display */
  error?: string;
  /** Help text displayed below the input */
  helpText?: string;
  /** Whether the field is required */
  required?: boolean;
  /** Additional class name for the wrapper */
  className?: string;
  /** Additional class name for the input */
  inputClassName?: string;
  /** Leading icon or element */
  leadingIcon?: ReactNode;
  /** Trailing icon or element */
  trailingIcon?: ReactNode;
  /** Test ID for testing */
  'data-testid'?: string;
}

// ============================================================================
// Component
// ============================================================================

/**
 * A form field component with label, input, and error display.
 *
 * Features:
 * - Automatic disabled state when form is pending (via useFormStatus)
 * - Accessible error display with aria attributes
 * - Support for leading/trailing icons
 * - Help text support
 * - Works with React 19 form actions
 *
 * @example
 * ```tsx
 * // Basic usage
 * <FormField name="name" label="Full Name" required />
 *
 * // With error
 * <FormField
 *   name="email"
 *   label="Email"
 *   type="email"
 *   error="Invalid email format"
 * />
 *
 * // With icon
 * <FormField
 *   name="search"
 *   label="Search"
 *   leadingIcon={<Search className="h-4 w-4" />}
 * />
 * ```
 */
export const FormField = forwardRef<HTMLInputElement, FormFieldProps>(
  (
    {
      name,
      label,
      error,
      helpText,
      required = false,
      className,
      inputClassName,
      leadingIcon,
      trailingIcon,
      'data-testid': testId,
      ...inputProps
    },
    ref
  ) => {
    // Generate unique IDs for accessibility
    const generatedId = useId();
    const inputId = `${name}-${generatedId}`;
    const errorId = `${name}-error-${generatedId}`;
    const helpTextId = `${name}-help-${generatedId}`;

    // Get form pending state
    const { pending } = useFormStatus();

    // Determine if field should be disabled
    const isDisabled = inputProps.disabled || pending;

    // Build aria-describedby
    const ariaDescribedBy = [
      error && errorId,
      helpText && helpTextId,
    ].filter(Boolean).join(' ') || undefined;

    return (
      <div className={clsx('space-y-1.5', className)} data-testid={testId}>
        {/* Label */}
        <label
          htmlFor={inputId}
          className="block text-sm font-medium text-gray-300"
        >
          {label}
          {required && (
            <span className="ml-1 text-red-400" aria-hidden="true">
              *
            </span>
          )}
        </label>

        {/* Input wrapper */}
        <div className="relative">
          {/* Leading icon */}
          {leadingIcon && (
            <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-gray-400">
              {leadingIcon}
            </div>
          )}

          {/* Input */}
          <input
            ref={ref}
            id={inputId}
            name={name}
            disabled={isDisabled}
            required={required}
            aria-invalid={!!error}
            aria-describedby={ariaDescribedBy}
            className={clsx(
              // Base styles
              'block w-full rounded-md border bg-[#1A1A1A] text-white placeholder-gray-500 transition-colors',
              'focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-offset-gray-900',
              'disabled:cursor-not-allowed disabled:opacity-50',
              // Size
              'px-3 py-2 text-sm',
              // Leading icon padding
              leadingIcon && 'pl-10',
              // Trailing icon padding
              trailingIcon && 'pr-10',
              // Border color based on error state
              error
                ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
                : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]',
              // Custom class name
              inputClassName
            )}
            {...inputProps}
          />

          {/* Trailing icon */}
          {trailingIcon && (
            <div className="absolute inset-y-0 right-0 flex items-center pr-3 text-gray-400">
              {trailingIcon}
            </div>
          )}
        </div>

        {/* Error message */}
        {error && (
          <div
            id={errorId}
            role="alert"
            className="flex items-center gap-1.5 text-sm text-red-400"
          >
            <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        {/* Help text */}
        {helpText && !error && (
          <p id={helpTextId} className="text-xs text-gray-500">
            {helpText}
          </p>
        )}
      </div>
    );
  }
);

FormField.displayName = 'FormField';

// ============================================================================
// Textarea Variant
// ============================================================================

/**
 * Props for the FormTextarea component.
 */
export interface FormTextareaProps
  extends Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, 'id'> {
  /** Field name (used for form data) */
  name: string;
  /** Field label */
  label: string;
  /** Error message to display */
  error?: string;
  /** Help text displayed below the input */
  helpText?: string;
  /** Whether the field is required */
  required?: boolean;
  /** Additional class name for the wrapper */
  className?: string;
  /** Additional class name for the textarea */
  textareaClassName?: string;
  /** Test ID for testing */
  'data-testid'?: string;
}

/**
 * A form textarea component with label and error display.
 */
export const FormTextarea = forwardRef<HTMLTextAreaElement, FormTextareaProps>(
  (
    {
      name,
      label,
      error,
      helpText,
      required = false,
      className,
      textareaClassName,
      'data-testid': testId,
      ...textareaProps
    },
    ref
  ) => {
    const generatedId = useId();
    const textareaId = `${name}-${generatedId}`;
    const errorId = `${name}-error-${generatedId}`;
    const helpTextId = `${name}-help-${generatedId}`;

    const { pending } = useFormStatus();
    const isDisabled = textareaProps.disabled || pending;

    const ariaDescribedBy = [
      error && errorId,
      helpText && helpTextId,
    ].filter(Boolean).join(' ') || undefined;

    return (
      <div className={clsx('space-y-1.5', className)} data-testid={testId}>
        <label
          htmlFor={textareaId}
          className="block text-sm font-medium text-gray-300"
        >
          {label}
          {required && (
            <span className="ml-1 text-red-400" aria-hidden="true">
              *
            </span>
          )}
        </label>

        <textarea
          ref={ref}
          id={textareaId}
          name={name}
          disabled={isDisabled}
          required={required}
          aria-invalid={!!error}
          aria-describedby={ariaDescribedBy}
          className={clsx(
            'block w-full rounded-md border bg-[#1A1A1A] text-white placeholder-gray-500 transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-offset-gray-900',
            'disabled:cursor-not-allowed disabled:opacity-50',
            'px-3 py-2 text-sm',
            'min-h-[100px] resize-y',
            error
              ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
              : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]',
            textareaClassName
          )}
          {...textareaProps}
        />

        {error && (
          <div
            id={errorId}
            role="alert"
            className="flex items-center gap-1.5 text-sm text-red-400"
          >
            <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        {helpText && !error && (
          <p id={helpTextId} className="text-xs text-gray-500">
            {helpText}
          </p>
        )}
      </div>
    );
  }
);

FormTextarea.displayName = 'FormTextarea';

// ============================================================================
// Select Variant
// ============================================================================

/**
 * Props for the FormSelect component.
 */
export interface FormSelectProps
  extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'id'> {
  /** Field name (used for form data) */
  name: string;
  /** Field label */
  label: string;
  /** Error message to display */
  error?: string;
  /** Help text displayed below the select */
  helpText?: string;
  /** Whether the field is required */
  required?: boolean;
  /** Additional class name for the wrapper */
  className?: string;
  /** Additional class name for the select */
  selectClassName?: string;
  /** Options for the select */
  children: ReactNode;
  /** Test ID for testing */
  'data-testid'?: string;
}

/**
 * A form select component with label and error display.
 */
export const FormSelect = forwardRef<HTMLSelectElement, FormSelectProps>(
  (
    {
      name,
      label,
      error,
      helpText,
      required = false,
      className,
      selectClassName,
      children,
      'data-testid': testId,
      ...selectProps
    },
    ref
  ) => {
    const generatedId = useId();
    const selectId = `${name}-${generatedId}`;
    const errorId = `${name}-error-${generatedId}`;
    const helpTextId = `${name}-help-${generatedId}`;

    const { pending } = useFormStatus();
    const isDisabled = selectProps.disabled || pending;

    const ariaDescribedBy = [
      error && errorId,
      helpText && helpTextId,
    ].filter(Boolean).join(' ') || undefined;

    return (
      <div className={clsx('space-y-1.5', className)} data-testid={testId}>
        <label
          htmlFor={selectId}
          className="block text-sm font-medium text-gray-300"
        >
          {label}
          {required && (
            <span className="ml-1 text-red-400" aria-hidden="true">
              *
            </span>
          )}
        </label>

        <select
          ref={ref}
          id={selectId}
          name={name}
          disabled={isDisabled}
          required={required}
          aria-invalid={!!error}
          aria-describedby={ariaDescribedBy}
          className={clsx(
            'block w-full rounded-md border bg-[#1A1A1A] text-white transition-colors',
            'focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-offset-gray-900',
            'disabled:cursor-not-allowed disabled:opacity-50',
            'px-3 py-2 text-sm',
            error
              ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
              : 'border-gray-700 focus:border-[#76B900] focus:ring-[#76B900]',
            selectClassName
          )}
          {...selectProps}
        >
          {children}
        </select>

        {error && (
          <div
            id={errorId}
            role="alert"
            className="flex items-center gap-1.5 text-sm text-red-400"
          >
            <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        {helpText && !error && (
          <p id={helpTextId} className="text-xs text-gray-500">
            {helpText}
          </p>
        )}
      </div>
    );
  }
);

FormSelect.displayName = 'FormSelect';

export default FormField;

import { clsx } from 'clsx';
import { Eye, EyeOff } from 'lucide-react';
import { useId, useState, type ChangeEvent, type InputHTMLAttributes } from 'react';

/**
 * Props for the PasswordInput component
 */
export interface PasswordInputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'onChange'> {
  /**
   * Label text for the input field
   */
  label: string;
  /**
   * Current value of the input
   */
  value: string;
  /**
   * Callback when value changes
   */
  onChange: (e: ChangeEvent<HTMLInputElement>) => void;
  /**
   * Error message to display below the input
   */
  error?: string;
  /**
   * Additional CSS class for the container
   */
  className?: string;
}

/**
 * Password input component with show/hide toggle functionality.
 *
 * Features:
 * - Show/hide password toggle with Eye/EyeOff icons
 * - Accessible label association
 * - Error state with styling and aria-describedby
 * - Required indicator with asterisk
 * - Disabled state for both input and toggle button
 *
 * @example
 * ```tsx
 * <PasswordInput
 *   label="RTSP Password"
 *   value={password}
 *   onChange={(e) => setPassword(e.target.value)}
 *   error={errors.password}
 * />
 * ```
 */
export default function PasswordInput({
  label,
  value,
  onChange,
  error,
  className,
  disabled,
  required,
  id: providedId,
  ...props
}: PasswordInputProps) {
  const [showPassword, setShowPassword] = useState(false);
  const generatedId = useId();
  const inputId = providedId ?? `password-input-${generatedId}`;
  const errorId = `${inputId}-error`;

  const toggleVisibility = () => {
    setShowPassword((prev) => !prev);
  };

  return (
    <div className={clsx('space-y-1', className)}>
      <span className="block text-sm font-medium text-text-primary">
        <label htmlFor={inputId}>{label}</label>
        {required && <span className="ml-1 text-red-500">*</span>}
      </span>
      <div className="relative">
        <input
          {...props}
          type={showPassword ? 'text' : 'password'}
          id={inputId}
          value={value}
          onChange={onChange}
          disabled={disabled}
          required={required}
          aria-describedby={error ? errorId : undefined}
          className={clsx(
            'block w-full rounded-lg border bg-card px-3 py-2 pr-10 text-text-primary focus:outline-none focus:ring-2',
            error
              ? 'border-red-500 focus:border-red-500 focus:ring-red-500'
              : 'border-gray-800 focus:border-primary focus:ring-primary',
            disabled && 'cursor-not-allowed opacity-50'
          )}
        />
        <button
          type="button"
          onClick={toggleVisibility}
          disabled={disabled}
          aria-label={showPassword ? 'Hide password' : 'Toggle password visibility'}
          className={clsx(
            'absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-gray-400 transition-colors',
            'hover:bg-gray-800 hover:text-text-primary focus:outline-none focus:ring-2 focus:ring-primary',
            disabled && 'cursor-not-allowed opacity-50'
          )}
        >
          {showPassword ? (
            <EyeOff className="h-5 w-5" aria-hidden="true" />
          ) : (
            <Eye className="h-5 w-5" aria-hidden="true" />
          )}
        </button>
      </div>
      {error && (
        <p id={errorId} className="text-sm text-red-500">
          {error}
        </p>
      )}
    </div>
  );
}

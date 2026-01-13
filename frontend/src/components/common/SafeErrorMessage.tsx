import { clsx } from 'clsx';

import { extractErrorMessage, sanitizeErrorMessage } from '../../utils/sanitize';

/**
 * Size variants for the error message text
 */
type ErrorMessageSize = 'xs' | 'sm' | 'md' | 'lg';

/**
 * Color variants for the error message
 */
type ErrorMessageColor = 'red' | 'gray' | 'yellow';

export interface SafeErrorMessageProps {
  /**
   * The error message to display. Can be a string or Error object.
   * The message will be sanitized to prevent XSS attacks.
   */
  message: string | Error | null | undefined;

  /**
   * Size of the error message text
   * @default 'sm'
   */
  size?: ErrorMessageSize;

  /**
   * Color of the error message text
   * @default 'red'
   */
  color?: ErrorMessageColor;

  /**
   * Additional CSS classes to apply
   */
  className?: string;

  /**
   * Test ID for testing
   */
  testId?: string;

  /**
   * If true, renders as a span instead of a p tag
   * @default false
   */
  inline?: boolean;

  /**
   * Maximum number of lines to display before truncating
   * Uses CSS line-clamp for truncation
   */
  maxLines?: number;
}

/**
 * Size classes mapping
 */
const sizeClasses: Record<ErrorMessageSize, string> = {
  xs: 'text-xs',
  sm: 'text-sm',
  md: 'text-base',
  lg: 'text-lg',
};

/**
 * Color classes mapping
 */
const colorClasses: Record<ErrorMessageColor, string> = {
  red: 'text-red-400',
  gray: 'text-gray-400',
  yellow: 'text-yellow-400',
};

/**
 * SafeErrorMessage component displays error messages safely by sanitizing
 * the content to prevent XSS (Cross-Site Scripting) attacks.
 *
 * This component should be used whenever displaying error messages that may
 * contain user-controlled input, such as:
 * - API error responses
 * - Form validation errors from user input
 * - File/path errors that include user-provided names
 * - Any error message that could potentially contain untrusted data
 *
 * Features:
 * - XSS protection via DOMPurify sanitization
 * - Supports Error objects and strings
 * - Configurable size, color, and display options
 * - Follows NVIDIA dark theme design patterns
 *
 * @example
 * ```tsx
 * // Basic usage with string
 * <SafeErrorMessage message="Failed to load data" />
 *
 * // With Error object
 * <SafeErrorMessage message={error} />
 *
 * // Custom styling
 * <SafeErrorMessage
 *   message="Network error"
 *   size="xs"
 *   color="gray"
 *   className="mt-1"
 * />
 *
 * // Inline display
 * <SafeErrorMessage message={error} inline />
 * ```
 */
export default function SafeErrorMessage({
  message,
  size = 'sm',
  color = 'red',
  className,
  testId = 'safe-error-message',
  inline = false,
  maxLines,
}: SafeErrorMessageProps) {
  // Extract and sanitize the message
  const rawMessage = extractErrorMessage(message);

  // If no message, render nothing
  if (!rawMessage) {
    return null;
  }

  const sanitizedMessage = sanitizeErrorMessage(rawMessage);

  // If sanitization results in empty string, render nothing
  if (!sanitizedMessage) {
    return null;
  }

  // Build the CSS classes
  const classes = clsx(
    sizeClasses[size],
    colorClasses[color],
    maxLines && `line-clamp-${maxLines}`,
    className
  );

  // Render as span or p based on inline prop
  const Tag = inline ? 'span' : 'p';

  return (
    <Tag className={classes} data-testid={testId}>
      {sanitizedMessage}
    </Tag>
  );
}

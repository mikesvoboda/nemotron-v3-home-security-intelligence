/* eslint-disable react-refresh/only-export-components */
/**
 * ApiErrorBoundary - Centralized error boundary for API errors (NEM-3179)
 *
 * This component provides a unified way to handle API errors across the application.
 * It catches errors from React Query queries and mutations, as well as render-time
 * API errors, displaying appropriate UI based on error type.
 *
 * Features:
 * - Catches API errors globally within its subtree
 * - Shows appropriate error UI based on error type (transient vs permanent)
 * - Provides retry mechanisms for transient errors
 * - Distinguishes between error types using RFC 7807 problem details
 * - Integrates with React Query's error handling
 *
 * Error Classification:
 * - **Transient errors** (retryable): Service unavailable, timeouts, rate limits
 * - **Permanent errors** (non-retryable): Not found, validation errors, auth errors
 *
 * @example
 * ```tsx
 * // Basic usage - wraps components that make API calls
 * <ApiErrorBoundary>
 *   <MyComponent />
 * </ApiErrorBoundary>
 *
 * // With custom fallback
 * <ApiErrorBoundary
 *   fallback={(error, reset) => (
 *     <div>
 *       <p>Error: {error.message}</p>
 *       <button onClick={reset}>Try Again</button>
 *     </div>
 *   )}
 * >
 *   <MyComponent />
 * </ApiErrorBoundary>
 *
 * // With error callback for analytics/logging
 * <ApiErrorBoundary
 *   onError={(error) => trackError('api-error', error)}
 *   onRetry={() => analytics.track('retry-clicked')}
 * >
 *   <MyComponent />
 * </ApiErrorBoundary>
 * ```
 */

import { AlertTriangle, RefreshCw, WifiOff, AlertCircle } from 'lucide-react';
import * as React from 'react';
import { Component, type ErrorInfo, type ReactNode, useCallback } from 'react';

import { ApiError, isTimeoutError } from '../../services/api';
import { logger } from '../../services/logger';
import {
  handleApiError as handleApiErrorUtil,
  shouldRetry,
  type ErrorConfig,
} from '../../utils/error-handling';

// ============================================================================
// Types
// ============================================================================

/**
 * Function that receives error details and returns a React node.
 */
export type FallbackRenderFunction = (error: Error, resetError: () => void) => ReactNode;

/**
 * Props for the ApiErrorBoundary component.
 */
export interface ApiErrorBoundaryProps {
  /** Child components to wrap */
  children: ReactNode;
  /** Optional custom fallback UI or render function */
  fallback?: ReactNode | FallbackRenderFunction;
  /** Optional callback when an error is caught */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  /** Optional callback when retry is clicked */
  onRetry?: () => void;
  /** Optional component name for logging context */
  componentName?: string;
  /** Whether to show toast notifications on error (default: false for boundary, toasts are shown elsewhere) */
  showToast?: boolean;
}

/**
 * State for the ApiErrorBoundary component.
 */
export interface ApiErrorBoundaryState {
  /** Whether an error has been caught */
  hasError: boolean;
  /** The caught error, if any */
  error: Error | null;
  /** React error info */
  errorInfo: ErrorInfo | null;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Determine if an error is transient (retryable).
 *
 * Checks multiple signals:
 * 1. TimeoutError is always transient
 * 2. ApiError with retryable error_code in problemDetails
 * 3. ApiError with retryable HTTP status code (429, 502, 503, 504)
 *
 * @param error - The error to check
 * @returns true if the error is transient and may succeed on retry
 */
export function isTransientError(error: Error | null): boolean {
  if (!error) return false;
  return shouldRetry(error);
}

/**
 * Get the appropriate icon for an error type.
 *
 * @param error - The error to get icon for
 * @returns Icon component
 */
function getErrorIcon(error: Error | null): React.ComponentType<{ className?: string }> {
  if (!error) return AlertTriangle;

  if (isTimeoutError(error)) {
    return WifiOff;
  }

  if (error instanceof ApiError) {
    const status = error.status;
    if (status === 429) return AlertCircle; // Rate limited
    if (status >= 500) return AlertTriangle; // Server error
    if (status === 404) return AlertCircle; // Not found
  }

  return AlertTriangle;
}

/**
 * Get user-friendly title for an error.
 *
 * @param error - The error to get title for
 * @returns User-friendly error title
 */
function getErrorTitle(error: Error | null): string {
  if (!error) return 'Something went wrong';

  if (isTimeoutError(error)) {
    return 'Request Timed Out';
  }

  if (error instanceof ApiError) {
    // Use RFC 7807 title if available
    if (error.problemDetails?.title) {
      return error.problemDetails.title;
    }

    // Fall back to status-based title
    switch (error.status) {
      case 400:
        return 'Invalid Request';
      case 401:
        return 'Authentication Required';
      case 403:
        return 'Access Denied';
      case 404:
        return 'Not Found';
      case 429:
        return 'Rate Limit Exceeded';
      case 500:
        return 'Server Error';
      case 502:
        return 'Bad Gateway';
      case 503:
        return 'Service Unavailable';
      case 504:
        return 'Gateway Timeout';
      default:
        return 'API Error';
    }
  }

  return 'Something went wrong';
}

/**
 * Get user-friendly description for an error.
 *
 * @param error - The error to get description for
 * @param isTransient - Whether the error is transient
 * @returns User-friendly error description
 */
function getErrorDescription(error: Error | null, isTransient: boolean): string {
  if (!error) {
    return 'An unexpected error occurred. Please try again.';
  }

  // Use RFC 7807 detail if available
  if (error instanceof ApiError && error.problemDetails?.detail) {
    return error.problemDetails.detail;
  }

  if (isTransient) {
    return 'This is a temporary issue. Please try again in a moment.';
  }

  return error.message || 'An unexpected error occurred.';
}

// ============================================================================
// ApiErrorFallback Component
// ============================================================================

/**
 * Props for the ApiErrorFallback component.
 */
export interface ApiErrorFallbackProps {
  /** The error that was caught */
  error: Error;
  /** Whether the error is transient (retryable) */
  isTransient: boolean;
  /** Callback to retry the failed operation */
  onRetry: () => void;
  /** Callback to refresh the page */
  onRefresh: () => void;
}

/**
 * Default fallback UI for API errors.
 *
 * Displays an appropriate error message with retry/refresh options
 * based on whether the error is transient or permanent.
 */
export function ApiErrorFallback({
  error,
  isTransient,
  onRetry,
  onRefresh,
}: ApiErrorFallbackProps): React.ReactElement {
  const Icon = getErrorIcon(error);
  const title = getErrorTitle(error);
  const description = getErrorDescription(error, isTransient);

  // Determine color scheme based on error severity
  const isWarning = isTransient || (error instanceof ApiError && error.status === 429);
  const colorClass = isWarning ? 'yellow' : 'red';

  return (
    <div
      role="alert"
      aria-live="polite"
      className={`flex min-h-[200px] flex-col items-center justify-center rounded-lg border border-${colorClass}-500/20 bg-${colorClass}-500/5 p-8 text-center`}
      data-testid="api-error-fallback"
    >
      <Icon className={`mb-4 h-12 w-12 text-${colorClass}-500`} aria-hidden="true" />
      <h2 className="mb-2 text-lg font-semibold text-white">{title}</h2>
      <p className="mb-4 max-w-md text-sm text-gray-400">{description}</p>

      {/* Show error code if available */}
      {(() => {
        const errorCode =
          error instanceof ApiError
            ? (error.problemDetails?.error_code as string | undefined)
            : undefined;
        return errorCode ? (
          <p className="mb-4 rounded bg-gray-800/50 px-3 py-1 font-mono text-xs text-gray-500">
            Code: {errorCode}
          </p>
        ) : null;
      })()}

      <div className="flex flex-wrap justify-center gap-3">
        {/* Show retry button only for transient errors */}
        {isTransient && (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-2 rounded-md bg-primary-500 px-4 py-2 text-sm font-medium text-gray-950 transition-colors hover:bg-primary-600 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2 focus:ring-offset-gray-900"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Retry
          </button>
        )}

        {/* Always show refresh page button */}
        <button
          type="button"
          onClick={onRefresh}
          className="inline-flex items-center gap-2 rounded-md bg-gray-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 focus:ring-offset-gray-900"
        >
          Refresh Page
        </button>
      </div>
    </div>
  );
}

// ============================================================================
// ApiErrorBoundary Component
// ============================================================================

/**
 * Error boundary that catches and handles API errors.
 *
 * This class component extends React's error boundary pattern to provide
 * specialized handling for API errors, including:
 * - Transient vs permanent error classification
 * - Automatic retry support for transient errors
 * - RFC 7807 problem details support
 * - Integration with the error handling utility
 */
export class ApiErrorBoundary extends Component<ApiErrorBoundaryProps, ApiErrorBoundaryState> {
  constructor(props: ApiErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  /**
   * Update state when an error is caught during rendering.
   */
  static getDerivedStateFromError(error: Error): Partial<ApiErrorBoundaryState> {
    return {
      hasError: true,
      error,
    };
  }

  /**
   * Log error information and call optional callback.
   */
  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Store error info in state
    this.setState({ errorInfo });

    // Log to centralized logger
    logger.error('API Error Boundary caught error', {
      error: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      name: error.name,
      component: this.props.componentName,
      isApiError: error instanceof ApiError,
      status: error instanceof ApiError ? error.status : undefined,
      errorCode:
        error instanceof ApiError
          ? (error.problemDetails?.error_code as string | undefined)
          : undefined,
    });

    // Call optional error callback
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  /**
   * Reset the error state and attempt to re-render children.
   */
  handleReset = (): void => {
    // Call onRetry callback if provided
    if (this.props.onRetry) {
      this.props.onRetry();
    }

    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  /**
   * Refresh the page.
   */
  handleRefresh = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    const { hasError, error } = this.state;
    const { children, fallback } = this.props;

    if (hasError && error) {
      const isTransient = isTransientError(error);

      // If fallback is a function, call it with error and reset
      if (typeof fallback === 'function') {
        return fallback(error, this.handleReset);
      }

      // If fallback is a ReactNode, render it
      if (fallback) {
        return fallback;
      }

      // Default fallback UI
      return (
        <ApiErrorFallback
          error={error}
          isTransient={isTransient}
          onRetry={this.handleReset}
          onRefresh={this.handleRefresh}
        />
      );
    }

    return children;
  }
}

// ============================================================================
// useApiErrorHandler Hook
// ============================================================================

/**
 * Hook that returns a function to handle API errors in mutations and queries.
 *
 * This hook provides access to the error handling utility with toast notifications
 * and error configuration lookup. Use it in mutation onError callbacks or when
 * you need to manually handle API errors.
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const handleError = useApiErrorHandler();
 *
 *   const mutation = useMutation({
 *     mutationFn: api.updateCamera,
 *     onError: (error) => {
 *       const config = handleError(error);
 *       if (config.retryable) {
 *         // Schedule retry
 *       }
 *     },
 *   });
 * }
 * ```
 *
 * @returns Error handler function that shows toast and returns ErrorConfig
 */
export function useApiErrorHandler(): (error: unknown) => ErrorConfig {
  return useCallback((error: unknown): ErrorConfig => {
    return handleApiErrorUtil(error);
  }, []);
}

export default ApiErrorBoundary;

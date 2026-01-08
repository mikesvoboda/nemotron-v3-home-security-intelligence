import { AlertOctagon, RefreshCw } from 'lucide-react';
import { Component, type ErrorInfo, type ReactNode } from 'react';

import { logger } from '../../services/logger';

/**
 * Generates a fingerprint for an error to enable deduplication.
 * Uses the error message and first line of stack trace.
 */
function getErrorFingerprint(error: Error): string {
  const firstStackLine = error.stack?.split('\n')[1]?.trim() || '';
  return `${error.message}:${firstStackLine}`;
}

/** Set of logged error fingerprints to prevent duplicate logs */
const loggedErrors = new Set<string>();

/**
 * Clear the error fingerprint cache.
 * Useful for testing and long-running sessions.
 */
export function clearErrorCache(): void {
  loggedErrors.clear();
}

export interface ErrorBoundaryProps {
  /** Child components to wrap */
  children: ReactNode;
  /** Optional custom fallback UI */
  fallback?: ReactNode;
  /** Optional callback when an error is caught */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  /** Optional title for the error message */
  title?: string;
  /** Optional description for the error message */
  description?: string;
  /** Optional component name for better error context in logs */
  componentName?: string;
}

export interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

/**
 * ErrorBoundary catches JavaScript errors in child components and displays
 * a fallback UI instead of crashing the entire application.
 *
 * Usage:
 * ```tsx
 * <ErrorBoundary>
 *   <MyComponent />
 * </ErrorBoundary>
 * ```
 *
 * With custom fallback:
 * ```tsx
 * <ErrorBoundary fallback={<div>Something went wrong</div>}>
 *   <MyComponent />
 * </ErrorBoundary>
 * ```
 */
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
    };
  }

  /**
   * Update state when an error is caught during rendering
   */
  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return {
      hasError: true,
      error,
    };
  }

  /**
   * Log error information for debugging.
   * Uses the centralized logger service to capture errors in both
   * development and production environments for debugging via source maps.
   * Implements error deduplication to prevent flooding logs with repeated errors.
   */
  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Generate fingerprint for deduplication
    const fingerprint = getErrorFingerprint(error);

    // Only log if this error hasn't been logged before
    if (!loggedErrors.has(fingerprint)) {
      loggedErrors.add(fingerprint);

      // Log to centralized logger for production debugging (supports source map lookup)
      logger.error('React component error', {
        error: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
        name: error.name,
        component: this.props.componentName,
        url: window.location.href,
      });
    }

    // Update state with error info
    this.setState({ errorInfo });

    // Call optional error callback
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  /**
   * Reset the error state and attempt to re-render children
   */
  handleRetry = (): void => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });
  };

  /**
   * Refresh the page
   */
  handleRefresh = (): void => {
    window.location.reload();
  };

  render(): ReactNode {
    const { hasError, error, errorInfo } = this.state;
    const { children, fallback, title, description } = this.props;

    if (hasError) {
      // Use custom fallback if provided
      if (fallback) {
        return fallback;
      }

      // Default fallback UI
      return (
        <div
          role="alert"
          aria-live="assertive"
          className="flex min-h-[200px] flex-col items-center justify-center rounded-lg border border-red-500/20 bg-red-500/5 p-8 text-center"
        >
          <AlertOctagon className="mb-4 h-12 w-12 text-red-500" aria-hidden="true" />
          <h2 className="mb-2 text-lg font-semibold text-white">
            {title || 'Something went wrong'}
          </h2>
          <p className="mb-4 max-w-md text-sm text-gray-400">
            {description ||
              'An unexpected error occurred. You can try to recover by clicking the button below, or refresh the page.'}
          </p>
          {error && (
            <p className="mb-4 max-w-md rounded bg-gray-800/50 px-3 py-2 font-mono text-xs text-red-400">
              {error.message}
            </p>
          )}
          {import.meta.env.DEV && errorInfo?.componentStack && (
            <details className="mb-4 max-w-md text-left">
              <summary className="cursor-pointer text-xs text-gray-500">Component Stack</summary>
              <pre className="mt-2 max-h-32 overflow-auto rounded bg-gray-800/50 p-2 text-xs text-gray-400">
                {errorInfo.componentStack}
              </pre>
            </details>
          )}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={this.handleRetry}
              className="inline-flex items-center gap-2 rounded-md bg-gray-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 focus:ring-offset-gray-900"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Try Again
            </button>
            <button
              type="button"
              onClick={this.handleRefresh}
              className="inline-flex items-center gap-2 rounded-md bg-gray-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-600 focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2 focus:ring-offset-gray-900"
            >
              Refresh Page
            </button>
          </div>
        </div>
      );
    }

    return children;
  }
}

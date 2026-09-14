/**
 * FeatureErrorBoundary - Granular error boundary for feature isolation.
 *
 * Unlike the general ErrorBoundary, this component is designed to wrap individual
 * features (like CameraGrid, RiskGauge, etc.) to prevent errors in one feature
 * from crashing the entire application.
 *
 * Features:
 * - Feature-specific error messages with the feature name in the title
 * - Compact fallback UI suitable for inline use
 * - Optional custom fallback and error callback
 * - Recovery via "Try again" button
 * - Logging through the centralized logger service
 *
 * @example
 * ```tsx
 * // Basic usage
 * <FeatureErrorBoundary feature="Camera Grid">
 *   <CameraGrid />
 * </FeatureErrorBoundary>
 *
 * // With custom fallback
 * <FeatureErrorBoundary
 *   feature="Risk Gauge"
 *   fallback={<div>Risk data unavailable</div>}
 * >
 *   <RiskGauge />
 * </FeatureErrorBoundary>
 *
 * // With error callback for analytics
 * <FeatureErrorBoundary
 *   feature="Live Activity Feed"
 *   onError={(error, info) => trackError('activity-feed', error)}
 * >
 *   <ActivityFeed />
 * </FeatureErrorBoundary>
 * ```
 */

import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Component, type ErrorInfo, type ReactNode } from 'react';

import { logger } from '../../services/logger';

/**
 * Props for the FeatureErrorBoundary component.
 */
export interface FeatureErrorBoundaryProps {
  /** Child components to wrap */
  children: ReactNode;
  /** Name of the feature for error messages and logging */
  feature: string;
  /** Optional custom fallback UI to display on error */
  fallback?: ReactNode;
  /** Optional callback when an error is caught */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  /** Optional compact mode for smaller inline displays */
  compact?: boolean;
}

/**
 * Internal state for the error boundary.
 */
export interface FeatureErrorBoundaryState {
  /** Whether an error has been caught */
  hasError: boolean;
  /** The caught error, if any */
  error: Error | null;
}

/**
 * FeatureErrorBoundary catches JavaScript errors in child components and displays
 * a feature-specific fallback UI instead of crashing the entire application.
 *
 * This enables graceful degradation where one broken feature doesn't prevent
 * the rest of the dashboard from working.
 */
export class FeatureErrorBoundary extends Component<
  FeatureErrorBoundaryProps,
  FeatureErrorBoundaryState
> {
  constructor(props: FeatureErrorBoundaryProps) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
    };
  }

  /**
   * Update state when an error is caught during rendering.
   */
  static getDerivedStateFromError(error: Error): Partial<FeatureErrorBoundaryState> {
    return {
      hasError: true,
      error,
    };
  }

  /**
   * Log error information for debugging.
   * Uses the centralized logger service to capture errors.
   */
  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Log to centralized logger with feature context
    logger.error(`Error in ${this.props.feature}`, {
      error: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      name: error.name,
      feature: this.props.feature,
    });

    // Call optional error callback
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }
  }

  /**
   * Reset the error state and attempt to re-render children.
   */
  handleRetry = (): void => {
    this.setState({
      hasError: false,
      error: null,
    });
  };

  render(): ReactNode {
    const { hasError, error } = this.state;
    const { children, fallback, feature, compact = false } = this.props;

    if (hasError) {
      // Use custom fallback if provided
      if (fallback) {
        return fallback;
      }

      // Compact fallback UI for inline displays
      if (compact) {
        return (
          <div
            role="alert"
            aria-live="polite"
            className="flex items-center gap-2 rounded-md border border-red-500/30 bg-red-900/20 px-3 py-2"
            data-testid="feature-error-compact"
          >
            <AlertTriangle className="h-4 w-4 flex-shrink-0 text-red-400" aria-hidden="true" />
            <span className="text-sm text-red-300">{feature} unavailable</span>
            <button
              type="button"
              onClick={this.handleRetry}
              className="ml-auto text-xs text-[#76B900] hover:underline focus:outline-none focus:ring-1 focus:ring-[#76B900]"
              aria-label={`Retry loading ${feature}`}
            >
              Retry
            </button>
          </div>
        );
      }

      // Default fallback UI
      return (
        <div
          role="alert"
          aria-live="polite"
          className="rounded-lg border border-red-500/50 bg-red-900/20 p-4"
          data-testid="feature-error-boundary"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle
              className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-400"
              aria-hidden="true"
            />
            <div className="flex-1">
              <h3 className="font-medium text-red-400">{feature} encountered an error</h3>
              {error && <p className="mt-1 text-sm text-gray-400">{error.message}</p>}
              <button
                type="button"
                onClick={this.handleRetry}
                className="mt-3 inline-flex items-center gap-2 rounded-md bg-gray-700/50 px-3 py-1.5 text-sm font-medium text-[#76B900] transition-colors hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-900"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                Try again
              </button>
            </div>
          </div>
        </div>
      );
    }

    return children;
  }
}

export default FeatureErrorBoundary;

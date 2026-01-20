/**
 * HOC (Higher-Order Component) for wrapping components with FeatureErrorBoundary.
 *
 * This provides an alternative pattern to the direct component wrapper, allowing
 * for cleaner code when you want to wrap a component declaratively at export time.
 *
 * @example
 * ```tsx
 * // At the bottom of a component file:
 * function AlertsContent() {
 *   // ... component implementation
 * }
 *
 * export const AlertsPage = withFeatureErrorBoundary(AlertsContent, 'Alerts');
 *
 * // Or with custom fallback:
 * export const AlertsPage = withFeatureErrorBoundary(
 *   AlertsContent,
 *   'Alerts',
 *   { fallback: <AlertsFallback /> }
 * );
 * ```
 */

import { FeatureErrorBoundary } from '../components/common/FeatureErrorBoundary';

import type { ErrorInfo, ReactNode, ComponentType } from 'react';

/**
 * Options for the withFeatureErrorBoundary HOC.
 */
export interface WithFeatureErrorBoundaryOptions {
  /** Optional custom fallback UI to display on error */
  fallback?: ReactNode;
  /** Optional callback when an error is caught */
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  /** Optional compact mode for smaller inline displays */
  compact?: boolean;
}

/**
 * Higher-Order Component that wraps a component with FeatureErrorBoundary.
 *
 * This allows for declarative error boundary wrapping at component export time,
 * keeping the component file clean while ensuring proper error isolation.
 *
 * @param WrappedComponent - The component to wrap with error boundary
 * @param featureName - Name of the feature for error messages and logging
 * @param options - Optional configuration for the error boundary
 * @returns A new component wrapped with FeatureErrorBoundary
 *
 * @example
 * ```tsx
 * // Basic usage
 * export const AlertsPage = withFeatureErrorBoundary(AlertsContent, 'Alerts');
 *
 * // With custom fallback
 * export const AlertsPage = withFeatureErrorBoundary(
 *   AlertsContent,
 *   'Alerts',
 *   {
 *     fallback: (
 *       <div className="p-4 text-red-400">
 *         <AlertTriangle className="h-8 w-8 mb-2" />
 *         <p>Unable to load alerts</p>
 *       </div>
 *     ),
 *   }
 * );
 *
 * // With error callback for analytics
 * export const AlertsPage = withFeatureErrorBoundary(
 *   AlertsContent,
 *   'Alerts',
 *   {
 *     onError: (error, info) => {
 *       trackError('alerts-page-crash', { error, info });
 *     },
 *   }
 * );
 * ```
 */
export function withFeatureErrorBoundary<P extends object>(
  WrappedComponent: ComponentType<P>,
  featureName: string,
  options: WithFeatureErrorBoundaryOptions = {}
): ComponentType<P> {
  const { fallback, onError, compact } = options;

  // Create the wrapped component with a display name for debugging
  function WithFeatureErrorBoundary(props: P) {
    return (
      <FeatureErrorBoundary
        feature={featureName}
        fallback={fallback}
        onError={onError}
        compact={compact}
      >
        <WrappedComponent {...props} />
      </FeatureErrorBoundary>
    );
  }

  // Set display name for React DevTools
  const wrappedName = WrappedComponent.displayName || WrappedComponent.name || 'Component';
  WithFeatureErrorBoundary.displayName = `WithFeatureErrorBoundary(${wrappedName})`;

  return WithFeatureErrorBoundary;
}

export default withFeatureErrorBoundary;

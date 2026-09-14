/**
 * ActionErrorBoundary - Error boundary that integrates with React 19 form actions.
 *
 * This component extends the standard ErrorBoundary to handle errors from
 * form actions, providing a unified error handling experience that works
 * with both synchronous errors (caught during render) and async action errors.
 *
 * @see NEM-3358 - Enhance Error Boundaries with Actions integration
 *
 * Features:
 * - Catches render-time errors like a standard error boundary
 * - Displays action error states from useActionState
 * - Provides graceful degradation for failed actions
 * - Supports custom fallback UI for different error types
 * - Integrates with the logger and Sentry
 *
 * @example
 * ```tsx
 * import { useActionState } from 'react';
 *
 * function MyForm() {
 *   const [state, action, isPending] = useActionState(submitAction, { status: 'idle' });
 *
 *   return (
 *     <ActionErrorBoundary
 *       actionState={state}
 *       feature="Settings Form"
 *       onRetry={() => window.location.reload()}
 *     >
 *       <form action={action}>
 *         <input name="name" />
 *         <SubmitButton>Save</SubmitButton>
 *       </form>
 *     </ActionErrorBoundary>
 *   );
 * }
 * ```
 */

import { clsx } from 'clsx';
import { AlertCircle, AlertTriangle, RefreshCw, XCircle } from 'lucide-react';
import { Component, type ErrorInfo, type ReactNode, useCallback } from 'react';

import { logger } from '../../services/logger';
import { captureError, isSentryEnabled } from '../../services/sentry';

import type { FormActionState } from '../../hooks/useFormAction';

// ============================================================================
// Types
// ============================================================================

/**
 * Error severity levels for display styling.
 */
export type ErrorSeverity = 'warning' | 'error' | 'critical';

/**
 * Props for the ActionErrorBoundary component.
 */
export interface ActionErrorBoundaryProps {
  /** Child components to render */
  children: ReactNode;
  /** Action state from useActionState (optional) */
  actionState?: FormActionState;
  /** Name of the feature for error messages and logging */
  feature: string;
  /** Custom fallback UI for render errors */
  renderErrorFallback?: ReactNode;
  /** Custom fallback UI for action errors */
  actionErrorFallback?: (state: FormActionState, onRetry: () => void) => ReactNode;
  /** Called when retry is clicked for action errors */
  onRetry?: () => void;
  /** Called when an error (render or action) is caught */
  onError?: (error: Error | string, type: 'render' | 'action') => void;
  /** Whether to show a compact error display */
  compact?: boolean;
  /** Additional class name */
  className?: string;
}

/**
 * State for the ActionErrorBoundary component.
 */
export interface ActionErrorBoundaryState {
  /** Whether a render error has been caught */
  hasRenderError: boolean;
  /** The caught render error, if any */
  renderError: Error | null;
  /** React error info */
  errorInfo: ErrorInfo | null;
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Determine error severity from an action state.
 */
function getActionErrorSeverity(state: FormActionState): ErrorSeverity {
  // Field-level validation errors are warnings
  if (state.fieldErrors && Object.keys(state.fieldErrors).length > 0) {
    return 'warning';
  }
  return 'error';
}

/**
 * Get an icon for the error severity.
 */
function getErrorIcon(severity: ErrorSeverity): typeof AlertTriangle {
  switch (severity) {
    case 'warning':
      return AlertCircle;
    case 'critical':
      return XCircle;
    default:
      return AlertTriangle;
  }
}

/**
 * Get color classes for the error severity.
 */
function getSeverityColors(severity: ErrorSeverity): {
  border: string;
  bg: string;
  text: string;
  icon: string;
} {
  switch (severity) {
    case 'warning':
      return {
        border: 'border-yellow-500/50',
        bg: 'bg-yellow-500/10',
        text: 'text-yellow-400',
        icon: 'text-yellow-500',
      };
    case 'critical':
      return {
        border: 'border-red-600/50',
        bg: 'bg-red-600/10',
        text: 'text-red-400',
        icon: 'text-red-500',
      };
    default:
      return {
        border: 'border-red-500/50',
        bg: 'bg-red-500/10',
        text: 'text-red-400',
        icon: 'text-red-400',
      };
  }
}

// ============================================================================
// Action Error Display Components
// ============================================================================

/**
 * Props for the ActionErrorDisplay component.
 */
export interface ActionErrorDisplayProps {
  /** The action state with error */
  state: FormActionState;
  /** Feature name for display */
  feature: string;
  /** Called when retry is clicked */
  onRetry?: () => void;
  /** Compact display mode */
  compact?: boolean;
  /** Additional class name */
  className?: string;
}

/**
 * Displays an action error with retry option.
 *
 * This is a functional component for displaying action errors inline.
 * Can be used standalone or as part of ActionErrorBoundary.
 */
export function ActionErrorDisplay({
  state,
  feature,
  onRetry,
  compact = false,
  className,
}: ActionErrorDisplayProps) {
  const severity = getActionErrorSeverity(state);
  const colors = getSeverityColors(severity);
  const Icon = getErrorIcon(severity);

  const handleRetry = useCallback(() => {
    onRetry?.();
  }, [onRetry]);

  // Compact inline display
  if (compact) {
    return (
      <div
        role="alert"
        aria-live="polite"
        className={clsx(
          'flex items-center gap-2 rounded-md border px-3 py-2',
          colors.border,
          colors.bg,
          className
        )}
        data-testid="action-error-compact"
      >
        <Icon className={clsx('h-4 w-4 flex-shrink-0', colors.icon)} aria-hidden="true" />
        <span className={clsx('text-sm', colors.text)}>
          {state.error || `${feature} action failed`}
        </span>
        {onRetry && (
          <button
            type="button"
            onClick={handleRetry}
            className="ml-auto text-xs text-[#76B900] hover:underline focus:outline-none focus:ring-1 focus:ring-[#76B900]"
            aria-label={`Retry ${feature}`}
          >
            Retry
          </button>
        )}
      </div>
    );
  }

  // Full display
  return (
    <div
      role="alert"
      aria-live="polite"
      className={clsx('rounded-lg border p-4', colors.border, colors.bg, className)}
      data-testid="action-error-boundary"
    >
      <div className="flex items-start gap-3">
        <Icon className={clsx('mt-0.5 h-5 w-5 flex-shrink-0', colors.icon)} aria-hidden="true" />
        <div className="flex-1">
          <h3 className={clsx('font-medium', colors.text)}>{feature} encountered an error</h3>
          {state.error && <p className="mt-1 text-sm text-gray-400">{state.error}</p>}

          {/* Display field errors if present */}
          {state.fieldErrors && Object.keys(state.fieldErrors).length > 0 && (
            <div className="mt-3">
              <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                Field Errors
              </p>
              <ul className="mt-1 space-y-1">
                {Object.entries(state.fieldErrors).map(([field, message]) => (
                  <li key={field} className="text-sm text-gray-400">
                    <span className="font-medium text-gray-300">{field}:</span> {message}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {onRetry && (
            <button
              type="button"
              onClick={handleRetry}
              className="mt-3 inline-flex items-center gap-2 rounded-md bg-gray-700/50 px-3 py-1.5 text-sm font-medium text-[#76B900] transition-colors hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-[#76B900] focus:ring-offset-2 focus:ring-offset-gray-900"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              Try again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// ActionErrorBoundary Class Component
// ============================================================================

/**
 * Error boundary that handles both render errors and action errors.
 *
 * This class component catches errors during render and also displays
 * action errors from useActionState, providing a unified error handling
 * experience for forms and other interactive components.
 */
export class ActionErrorBoundary extends Component<
  ActionErrorBoundaryProps,
  ActionErrorBoundaryState
> {
  constructor(props: ActionErrorBoundaryProps) {
    super(props);
    this.state = {
      hasRenderError: false,
      renderError: null,
      errorInfo: null,
    };
  }

  /**
   * Update state when a render error is caught.
   */
  static getDerivedStateFromError(error: Error): Partial<ActionErrorBoundaryState> {
    return {
      hasRenderError: true,
      renderError: error,
    };
  }

  /**
   * Log error information and call optional callback.
   */
  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    this.setState({ errorInfo });

    // Log to centralized logger
    logger.error(`Render error in ${this.props.feature}`, {
      error: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      name: error.name,
      feature: this.props.feature,
    });

    // Report to Sentry if enabled
    if (isSentryEnabled()) {
      captureError(error, {
        tags: {
          component: 'ActionErrorBoundary',
          feature: this.props.feature,
        },
        extra: {
          componentStack: errorInfo.componentStack,
        },
      });
    }

    // Call optional error callback
    if (this.props.onError) {
      this.props.onError(error, 'render');
    }
  }

  /**
   * Check if action state has changed to error and log it.
   */
  componentDidUpdate(prevProps: ActionErrorBoundaryProps): void {
    const { actionState, feature, onError } = this.props;

    // Check if action just errored
    if (actionState?.status === 'error' && prevProps.actionState?.status !== 'error') {
      // Log the action error
      logger.warn(`Action error in ${feature}`, {
        error: actionState.error,
        fieldErrors: actionState.fieldErrors,
        feature,
      });

      // Call optional error callback
      if (onError && actionState.error) {
        onError(actionState.error, 'action');
      }
    }
  }

  /**
   * Reset the render error state.
   */
  handleRenderRetry = (): void => {
    this.setState({
      hasRenderError: false,
      renderError: null,
      errorInfo: null,
    });
  };

  /**
   * Handle retry for action errors.
   */
  handleActionRetry = (): void => {
    if (this.props.onRetry) {
      this.props.onRetry();
    }
  };

  render(): ReactNode {
    const {
      children,
      actionState,
      feature,
      renderErrorFallback,
      actionErrorFallback,
      compact = false,
      className,
    } = this.props;
    const { hasRenderError, renderError } = this.state;

    // Render error takes priority
    if (hasRenderError && renderError) {
      // Use custom fallback if provided
      if (renderErrorFallback) {
        return renderErrorFallback;
      }

      // Default render error display
      const colors = getSeverityColors('critical');
      const Icon = getErrorIcon('critical');

      return (
        <div
          role="alert"
          aria-live="assertive"
          className={clsx('rounded-lg border p-4', colors.border, colors.bg, className)}
          data-testid="action-error-boundary-render"
        >
          <div className="flex items-start gap-3">
            <Icon
              className={clsx('mt-0.5 h-5 w-5 flex-shrink-0', colors.icon)}
              aria-hidden="true"
            />
            <div className="flex-1">
              <h3 className={clsx('font-medium', colors.text)}>{feature} crashed</h3>
              <p className="mt-1 text-sm text-gray-400">{renderError.message}</p>
              <button
                type="button"
                onClick={this.handleRenderRetry}
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

    // Check for action error state
    if (actionState?.status === 'error') {
      // Use custom fallback if provided
      if (actionErrorFallback) {
        return actionErrorFallback(actionState, this.handleActionRetry);
      }

      // Default action error display
      return (
        <>
          <ActionErrorDisplay
            state={actionState}
            feature={feature}
            onRetry={this.handleActionRetry}
            compact={compact}
            className={className}
          />
          {/* Still render children below the error so the form is accessible */}
          {children}
        </>
      );
    }

    // No errors - render children normally
    return children;
  }
}

// ============================================================================
// Convenience Exports
// ============================================================================

/**
 * Hook-friendly wrapper for displaying action errors.
 *
 * Use this when you want to display action errors inline without
 * the full error boundary functionality.
 *
 * @example
 * ```tsx
 * function MyForm() {
 *   const [state, action] = useActionState(submitAction, { status: 'idle' });
 *
 *   return (
 *     <form action={action}>
 *       <FormActionError state={state} feature="Contact Form" />
 *       <input name="email" />
 *       <SubmitButton>Submit</SubmitButton>
 *     </form>
 *   );
 * }
 * ```
 */
export function FormActionError({
  state,
  feature,
  onRetry,
  compact,
  className,
}: ActionErrorDisplayProps): ReactNode {
  if (state.status !== 'error') {
    return null;
  }

  return (
    <ActionErrorDisplay
      state={state}
      feature={feature}
      onRetry={onRetry}
      compact={compact}
      className={className}
    />
  );
}

export default ActionErrorBoundary;

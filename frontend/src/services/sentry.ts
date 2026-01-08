/**
 * Sentry Error Tracking Integration
 *
 * Provides centralized error tracking, performance monitoring, and session replay
 * for the Home Security Dashboard frontend.
 *
 * Configuration is controlled via environment variables:
 * - VITE_SENTRY_DSN: Sentry DSN (required to enable Sentry)
 * - VITE_SENTRY_ENVIRONMENT: Environment name (default: 'production')
 * - VITE_SENTRY_TRACES_SAMPLE_RATE: Transaction sample rate (default: 0.1)
 * - VITE_SENTRY_REPLAY_SAMPLE_RATE: Session replay sample rate (default: 0.1)
 * - VITE_SENTRY_REPLAY_ON_ERROR_RATE: Replay on error sample rate (default: 1.0)
 *
 * @example
 * // Initialize Sentry in main.tsx
 * import { initSentry } from './services/sentry';
 * initSentry();
 *
 * @example
 * // Capture an error
 * import { captureError } from './services/sentry';
 * try {
 *   // code that might throw
 * } catch (error) {
 *   captureError(error, { tags: { component: 'MyComponent' } });
 * }
 *
 * @example
 * // Add a breadcrumb for debugging
 * import { addBreadcrumb } from './services/sentry';
 * addBreadcrumb({
 *   category: 'ui.click',
 *   message: 'User clicked submit button',
 *   level: 'info',
 * });
 */

import * as Sentry from '@sentry/react';

/**
 * Sentry initialization configuration options.
 * Extends Sentry's BrowserOptions with typed environment variable defaults.
 */
export interface SentryConfig {
  /** Sentry DSN - required to enable Sentry */
  dsn?: string;
  /** Environment name (e.g., 'production', 'staging', 'development') */
  environment?: string;
  /** Release version identifier */
  release?: string;
  /** Sample rate for performance transactions (0.0 to 1.0) */
  tracesSampleRate?: number;
  /** Sample rate for session replays (0.0 to 1.0) */
  replaysSessionSampleRate?: number;
  /** Sample rate for replays when an error occurs (0.0 to 1.0) */
  replaysOnErrorSampleRate?: number;
  /** Enable debug mode for development */
  debug?: boolean;
}

/**
 * Breadcrumb data structure for tracking user actions and navigation.
 */
export interface BreadcrumbData {
  /** Breadcrumb message */
  message: string;
  /** Category for grouping breadcrumbs (e.g., 'http', 'ui.click', 'navigation') */
  category: string;
  /** Severity level */
  level?: 'fatal' | 'error' | 'warning' | 'info' | 'debug';
  /** Additional data to include with the breadcrumb */
  data?: Record<string, unknown>;
}

/**
 * User context for error attribution.
 */
export interface UserContext {
  /** Unique user identifier */
  id?: string;
  /** User email address */
  email?: string;
  /** Username */
  username?: string;
  /** Additional user data */
  [key: string]: unknown;
}

/**
 * Context for error capture with tags and extra data.
 */
export interface CaptureContext {
  /** Tags for error categorization and filtering */
  tags?: Record<string, string>;
  /** Extra data to include with the error */
  extra?: Record<string, unknown>;
  /** Severity level */
  level?: Sentry.SeverityLevel;
}

// Track initialization state
let isInitialized = false;

/**
 * Parses a numeric environment variable with a default fallback.
 *
 * @param value - The environment variable value (string or undefined)
 * @param defaultValue - Default value if parsing fails
 * @returns Parsed number or default
 */
function parseEnvNumber(value: string | undefined, defaultValue: number): number {
  if (!value) return defaultValue;
  const parsed = parseFloat(value);
  return isNaN(parsed) ? defaultValue : parsed;
}

/**
 * Checks if Sentry is enabled based on DSN configuration.
 *
 * @returns true if VITE_SENTRY_DSN is configured, false otherwise
 */
export function isSentryEnabled(): boolean {
  const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;
  return Boolean(dsn && dsn.trim().length > 0);
}

/**
 * Initializes Sentry with configuration from environment variables.
 *
 * This should be called once at application startup (typically in main.tsx).
 * If VITE_SENTRY_DSN is not set, Sentry will not be initialized and
 * all tracking functions will be no-ops.
 *
 * @param customConfig - Optional custom configuration to merge with env defaults
 */
export function initSentry(customConfig?: Partial<SentryConfig>): void {
  const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;

  // Don't initialize if DSN is not configured
  if (!dsn || dsn.trim().length === 0) {
    return;
  }

  // Avoid double initialization
  if (isInitialized) {
    return;
  }

  const environment =
    (import.meta.env.VITE_SENTRY_ENVIRONMENT as string | undefined) || 'production';
  const tracesSampleRate = parseEnvNumber(
    import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE as string | undefined,
    0.1
  );
  const replaysSessionSampleRate = parseEnvNumber(
    import.meta.env.VITE_SENTRY_REPLAY_SAMPLE_RATE as string | undefined,
    0.1
  );
  const replaysOnErrorSampleRate = parseEnvNumber(
    import.meta.env.VITE_SENTRY_REPLAY_ON_ERROR_RATE as string | undefined,
    1.0
  );

  Sentry.init({
    dsn,
    environment,
    tracesSampleRate,
    replaysSessionSampleRate,
    replaysOnErrorSampleRate,
    integrations: [Sentry.browserTracingIntegration(), Sentry.replayIntegration()],
    // Merge custom config last to allow overrides
    ...customConfig,
  });

  isInitialized = true;
}

/**
 * Captures an error and sends it to Sentry.
 *
 * This function is safe to call even if Sentry is not initialized -
 * it will be a no-op if DSN is not configured.
 *
 * @param error - The error to capture (Error object or any value)
 * @param context - Optional context with tags and extra data
 */
export function captureError(error: unknown, context?: CaptureContext): void {
  if (!isSentryEnabled()) {
    return;
  }

  Sentry.captureException(error, context);
}

/**
 * Captures a message and sends it to Sentry.
 *
 * Use this for non-error events that you want to track, such as
 * important user actions or system state changes.
 *
 * @param message - The message to capture
 * @param level - Optional severity level (default: 'info')
 */
export function captureMessage(message: string, level?: Sentry.SeverityLevel): void {
  if (!isSentryEnabled()) {
    return;
  }

  Sentry.captureMessage(message, level);
}

/**
 * Adds a breadcrumb to the current Sentry scope.
 *
 * Breadcrumbs provide context for errors by tracking user actions,
 * navigation, and API calls leading up to an error.
 *
 * @param breadcrumb - Breadcrumb data including message, category, and optional data
 */
export function addBreadcrumb(breadcrumb: BreadcrumbData): void {
  if (!isSentryEnabled()) {
    return;
  }

  Sentry.addBreadcrumb(breadcrumb);
}

/**
 * Sets user context for error attribution.
 *
 * Call this after user login to associate errors with specific users.
 * Pass null to clear user context (e.g., on logout).
 *
 * @param user - User context object or null to clear
 */
export function setUserContext(user: UserContext | null): void {
  if (!isSentryEnabled()) {
    return;
  }

  Sentry.setUser(user);
}

/**
 * Sets additional context for the current scope.
 *
 * Use this to add structured data that should be included with all
 * subsequent error reports.
 *
 * @param name - Context name (e.g., 'camera', 'event')
 * @param context - Context data object
 */
export function setContext(name: string, context: Record<string, unknown>): void {
  if (!isSentryEnabled()) {
    return;
  }

  Sentry.setContext(name, context);
}

/**
 * Creates an API breadcrumb for tracking HTTP requests.
 *
 * This is a convenience wrapper around addBreadcrumb specifically
 * for tracking API calls.
 *
 * @param method - HTTP method (GET, POST, etc.)
 * @param url - Request URL
 * @param statusCode - Response status code
 * @param duration - Request duration in milliseconds (optional)
 */
export function addApiBreadcrumb(
  method: string,
  url: string,
  statusCode: number,
  duration?: number
): void {
  const level: BreadcrumbData['level'] = statusCode >= 400 ? 'error' : 'info';

  addBreadcrumb({
    category: 'http',
    message: `${method} ${url}`,
    level,
    data: {
      method,
      url,
      status_code: statusCode,
      ...(duration !== undefined && { duration_ms: duration }),
    },
  });
}

// Re-export Sentry's ErrorBoundary for use in React components
export { ErrorBoundary as SentryErrorBoundary } from '@sentry/react';

/**
 * Global Error Reporting Service
 *
 * NEM-2726: Provides global error handlers for uncaught exceptions and promise rejections.
 *
 * Features:
 * - Captures uncaught exceptions via window 'error' event
 * - Captures unhandled promise rejections via 'unhandledrejection' event
 * - Filters out noisy/expected errors (ResizeObserver, cross-origin, Network errors)
 * - Rate limits duplicate errors to prevent spam
 * - Reports errors to backend endpoint for centralized logging
 *
 * This module should be initialized early in the application lifecycle,
 * before React renders, to catch any errors during startup.
 *
 * @example
 * // Initialize in main.tsx before ReactDOM.createRoot()
 * import { initializeErrorReporting } from './services/errorReporting';
 * initializeErrorReporting();
 */

/**
 * Configuration options for error reporting.
 */
export interface ErrorReportingConfig {
  /** Whether error reporting is enabled (default: true) */
  enabled: boolean;
  /** Backend endpoint for error reporting (default: '/api/logs/frontend') */
  endpoint: string;
  /** Rate limit window in milliseconds for duplicate errors (default: 10000) */
  rateLimitMs: number;
}

const defaultConfig: ErrorReportingConfig = {
  enabled: true,
  endpoint: '/api/logs/frontend',
  rateLimitMs: 10000,
};

/**
 * Patterns for errors that should be ignored.
 * These are typically browser noise, cross-origin errors, or errors handled elsewhere.
 */
const IGNORED_ERROR_PATTERNS: RegExp[] = [
  // ResizeObserver errors - benign browser behavior, not actual errors
  /ResizeObserver loop limit exceeded/i,
  /ResizeObserver loop completed with undelivered notifications/i,
  // Cross-origin script errors - no useful information available
  /^Script error\.?$/i,
  // Network errors - handled by API interceptor
  /^Network Error$/i,
  // AbortError - intentional request cancellation
  /AbortError/i,
  // Fetch aborted errors
  /The operation was aborted/i,
  /signal is aborted/i,
];

// Module state
let isInitialized = false;
let config: ErrorReportingConfig = { ...defaultConfig };
let errorHandler: ((event: ErrorEvent) => void) | null = null;
let rejectionHandler: ((event: PromiseRejectionEvent) => void) | null = null;
const rateLimitMap = new Map<string, number>();

/**
 * Checks if an error message matches any of the ignored patterns.
 *
 * @param message - The error message to check
 * @returns true if the error should be ignored
 */
export function isErrorIgnored(message: string): boolean {
  return IGNORED_ERROR_PATTERNS.some((pattern) => pattern.test(message));
}

/**
 * Generates a key for rate limiting based on error characteristics.
 *
 * @param message - Error message
 * @param filename - Source file (optional)
 * @param lineno - Line number (optional)
 * @returns A string key for rate limiting
 */
function generateRateLimitKey(message: string, filename?: string, lineno?: number): string {
  return `${message}:${filename || ''}:${lineno || ''}`;
}

/**
 * Checks if an error should be rate limited (already reported recently).
 *
 * @param key - The rate limit key
 * @returns true if the error should be suppressed
 */
function isRateLimited(key: string): boolean {
  const now = Date.now();
  const lastReported = rateLimitMap.get(key);

  if (lastReported && now - lastReported < config.rateLimitMs) {
    return true;
  }

  rateLimitMap.set(key, now);
  return false;
}

/**
 * Reports an error to the backend endpoint.
 *
 * @param errorData - The error data to report
 */
async function reportToBackend(errorData: Record<string, unknown>): Promise<void> {
  try {
    await fetch(config.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        level: 'ERROR',
        component: 'error_reporting',
        message: errorData.message || 'Unknown error',
        extra: errorData,
      }),
    });
  } catch {
    // Silently fail - we don't want error reporting to cause more errors
  }
}

/**
 * Handles uncaught exceptions from the 'error' event.
 *
 * @param event - The error event
 */
function handleError(event: ErrorEvent): void {
  if (!config.enabled) {
    return;
  }

  const message = event.message || 'Unknown error';

  // Filter out ignored errors
  if (isErrorIgnored(message)) {
    return;
  }

  // Check for AbortError in the error object
  if (event.error instanceof DOMException && event.error.name === 'AbortError') {
    return;
  }

  // Generate rate limit key
  const rateLimitKey = generateRateLimitKey(message, event.filename, event.lineno);

  // Skip if rate limited
  if (isRateLimited(rateLimitKey)) {
    return;
  }

  const errorData = {
    message,
    filename: event.filename || undefined,
    lineno: event.lineno || undefined,
    colno: event.colno || undefined,
    stack: (event.error as Error | undefined)?.stack || undefined,
    type: 'uncaught_exception',
    url: window.location.href,
    timestamp: new Date().toISOString(),
  };

  // Log to console
  console.error('[ErrorReporting] Uncaught exception:', errorData);

  // Report to backend
  void reportToBackend(errorData);
}

/**
 * Handles unhandled promise rejections from the 'unhandledrejection' event.
 *
 * @param event - The promise rejection event
 */
function handleRejection(event: PromiseRejectionEvent): void {
  if (!config.enabled) {
    return;
  }

  const reason: unknown = event.reason;

  // Safely convert reason to string, handling objects that may not have a good toString
  const safeStringify = (value: unknown): string => {
    if (value === undefined) return 'undefined';
    if (value === null) return 'null';
    if (typeof value === 'string') return value;
    if (value instanceof Error) return value.message;
    try {
      return JSON.stringify(value);
    } catch {
      return '[Object]';
    }
  };

  const message = reason instanceof Error ? reason.message : safeStringify(reason);
  const reasonString = reason instanceof Error ? `${reason.name}: ${reason.message}` : safeStringify(reason);

  // Filter out ignored errors
  if (isErrorIgnored(message) || isErrorIgnored(reasonString)) {
    return;
  }

  // Check for AbortError
  if (reason instanceof DOMException && reason.name === 'AbortError') {
    return;
  }

  // Generate rate limit key
  const rateLimitKey = generateRateLimitKey(reasonString);

  // Skip if rate limited
  if (isRateLimited(rateLimitKey)) {
    return;
  }

  const errorData = {
    reason: reasonString,
    stack: reason instanceof Error ? reason.stack : undefined,
    type: 'unhandled_rejection',
    url: window.location.href,
    timestamp: new Date().toISOString(),
  };

  // Log to console
  console.error('[ErrorReporting] Unhandled promise rejection:', errorData);

  // Report to backend
  void reportToBackend(errorData);
}

/**
 * Initializes global error reporting handlers.
 *
 * This function should be called once, early in the application lifecycle,
 * before React renders. It sets up event listeners for:
 * - Uncaught exceptions (window 'error' event)
 * - Unhandled promise rejections ('unhandledrejection' event)
 *
 * @param customConfig - Optional custom configuration to merge with defaults
 *
 * @example
 * // Basic initialization
 * initializeErrorReporting();
 *
 * @example
 * // With custom configuration
 * initializeErrorReporting({
 *   enabled: true,
 *   endpoint: '/api/custom/errors',
 *   rateLimitMs: 5000,
 * });
 */
export function initializeErrorReporting(customConfig?: Partial<ErrorReportingConfig>): void {
  // Prevent double initialization
  if (isInitialized) {
    return;
  }

  // Merge custom config with defaults
  config = { ...defaultConfig, ...customConfig };

  // Create bound handlers
  errorHandler = handleError;
  rejectionHandler = handleRejection;

  // Add event listeners
  window.addEventListener('error', errorHandler);
  window.addEventListener('unhandledrejection', rejectionHandler);

  isInitialized = true;
}

/**
 * Cleans up error reporting handlers.
 *
 * This removes the event listeners added by initializeErrorReporting.
 * Useful for testing or when the application is being torn down.
 */
export function cleanupErrorReporting(): void {
  if (!isInitialized) {
    return;
  }

  if (errorHandler) {
    window.removeEventListener('error', errorHandler);
    errorHandler = null;
  }

  if (rejectionHandler) {
    window.removeEventListener('unhandledrejection', rejectionHandler);
    rejectionHandler = null;
  }

  // Clear rate limit map
  rateLimitMap.clear();

  // Reset config to defaults
  config = { ...defaultConfig };

  isInitialized = false;
}

/**
 * Clears the rate limit cache.
 *
 * This is primarily useful for testing to reset rate limiting state between tests.
 * In production, rate limiting helps prevent spam and should not be cleared.
 */
export function clearRateLimitCache(): void {
  rateLimitMap.clear();
}

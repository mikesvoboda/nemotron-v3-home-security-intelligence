/**
 * API Client Interceptors
 * NEM-1564: Global error handling and request logging
 *
 * Provides interceptors for the fetch API to add:
 * - Request logging (outgoing requests with timing)
 * - Response logging (incoming responses with duration)
 * - Global error handling (show notifications for 5xx errors)
 * - Retry logic for transient failures
 *
 * @example
 * ```typescript
 * import { createInterceptedFetch, defaultRequestInterceptor, defaultResponseInterceptor } from './interceptors';
 *
 * const customFetch = createInterceptedFetch({
 *   requestInterceptors: [defaultRequestInterceptor],
 *   responseInterceptors: [defaultResponseInterceptor],
 * });
 *
 * // Use like regular fetch
 * const response = await customFetch('/api/data');
 * ```
 */

/**
 * Request interceptor function type.
 * Called before the request is made, can modify URL and options.
 */
export type RequestInterceptor = (
  url: string,
  options?: RequestInit & { _requestStartTime?: number }
) => {
  url: string;
  options?: RequestInit & { _requestStartTime?: number };
};

/**
 * Response interceptor function type.
 * Called after the response is received, can modify or handle the response.
 */
export type ResponseInterceptor = (
  response: Response,
  url: string,
  options?: RequestInit & { _requestStartTime?: number }
) => Response;

/**
 * Async response interceptor with retry capability.
 * Can trigger retries by calling the provided fetch function.
 */
export type AsyncResponseInterceptor = (
  response: Response,
  url: string,
  options: RequestInit & { _requestStartTime?: number },
  retryFetch: typeof fetch
) => Promise<Response>;

/**
 * Configuration for intercepted fetch.
 */
export interface InterceptorConfig {
  /** Interceptors to run before each request */
  requestInterceptors?: RequestInterceptor[];
  /** Interceptors to run after each response */
  responseInterceptors?: ResponseInterceptor[];
  /** Async interceptors (for retry logic) */
  asyncResponseInterceptors?: AsyncResponseInterceptor[];
}

/**
 * Default request interceptor that logs outgoing requests.
 * Also adds timing information for calculating request duration.
 */
export const defaultRequestInterceptor: RequestInterceptor = (url, options) => {
  const method = options?.method || 'GET';

  // eslint-disable-next-line no-console
  console.log(`[API] ${method} ${url}`);

  return {
    url,
    options: {
      ...options,
      _requestStartTime: Date.now(),
    },
  };
};

/**
 * Default response interceptor that logs responses with timing.
 * Handles different log levels based on status code.
 */
export const defaultResponseInterceptor: ResponseInterceptor = (response, url, options) => {
  const duration = options?._requestStartTime ? Date.now() - options._requestStartTime : null;

  const durationStr = duration !== null ? ` (${duration}ms)` : '';
  const method = options?.method || 'GET';
  const status = response.status;

  if (status >= 500) {
    // Server errors - log as error
    console.error(`[API] ${method} ${url} - ${status}${durationStr}`);
  } else if (status >= 400) {
    // Client errors - log as warning
    console.warn(`[API] ${method} ${url} - ${status}${durationStr}`);
  } else {
    // Success - log normally
    // eslint-disable-next-line no-console
    console.log(`[API] ${method} ${url} - ${status}${durationStr}`);
  }

  return response;
};

/**
 * Retry interceptor configuration.
 */
export interface RetryConfig {
  /** Maximum number of retry attempts (default: 3) */
  maxRetries?: number;
  /** Base delay between retries in milliseconds (default: 1000) */
  retryDelay?: number;
  /** Whether to use exponential backoff (default: true) */
  useExponentialBackoff?: boolean;
  /** HTTP status codes that should trigger a retry (default: 500-599) */
  retryStatusCodes?: number[];
}

/**
 * Creates a retry interceptor with configurable retry logic.
 *
 * @param config - Retry configuration
 * @returns An async response interceptor that handles retries
 */
export function createRetryInterceptor(config: RetryConfig = {}): AsyncResponseInterceptor {
  const {
    maxRetries = 3,
    retryDelay = 1000,
    useExponentialBackoff = true,
    retryStatusCodes,
  } = config;

  return async (response, url, options, retryFetch) => {
    // Check if we should retry this response
    const shouldRetry = retryStatusCodes
      ? retryStatusCodes.includes(response.status)
      : response.status >= 500 && response.status < 600;

    if (!shouldRetry) {
      return response;
    }

    // Attempt retries
    let lastResponse = response;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      // Calculate delay with optional exponential backoff
      const delay = useExponentialBackoff ? retryDelay * Math.pow(2, attempt) : retryDelay;

      await sleep(delay);

      try {
        // Strip the internal timing property before retrying
        const cleanOptions = { ...options };
        delete (cleanOptions as { _requestStartTime?: number })._requestStartTime;

        lastResponse = await retryFetch(url, cleanOptions);

        // If successful, return immediately
        if (lastResponse.ok) {
          return lastResponse;
        }

        // If not a retryable error, return
        const shouldRetryAgain = retryStatusCodes
          ? retryStatusCodes.includes(lastResponse.status)
          : lastResponse.status >= 500 && lastResponse.status < 600;

        if (!shouldRetryAgain) {
          return lastResponse;
        }
      } catch {
        // Network error - continue retrying
      }
    }

    return lastResponse;
  };
}

/**
 * Helper function to sleep for a specified duration.
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Creates a fetch function with interceptors applied.
 *
 * @param config - Interceptor configuration
 * @returns A fetch-compatible function with interceptors
 */
export function createInterceptedFetch(config: InterceptorConfig): typeof fetch {
  const {
    requestInterceptors = [],
    responseInterceptors = [],
    asyncResponseInterceptors = [],
  } = config;

  return async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    // Get URL string from input
    let url: string;
    if (typeof input === 'string') {
      url = input;
    } else if (input instanceof URL) {
      url = input.href;
    } else {
      // Request object
      url = input.url;
    }
    let options: RequestInit & { _requestStartTime?: number } = init || {};

    // Apply request interceptors
    for (const interceptor of requestInterceptors) {
      const result = interceptor(url, options);
      url = result.url;
      options = result.options || {};
    }

    // Make the actual fetch request
    let response = await fetch(url, options);

    // Apply response interceptors
    for (const interceptor of responseInterceptors) {
      response = interceptor(response, url, options);
    }

    // Apply async response interceptors (for retry logic)
    for (const interceptor of asyncResponseInterceptors) {
      response = await interceptor(response, url, options, fetch);
    }

    return response;
  };
}

/**
 * Pre-configured intercepted fetch with logging.
 * Ready to use as a drop-in replacement for fetch.
 */
export const interceptedFetch = createInterceptedFetch({
  requestInterceptors: [defaultRequestInterceptor],
  responseInterceptors: [defaultResponseInterceptor],
});

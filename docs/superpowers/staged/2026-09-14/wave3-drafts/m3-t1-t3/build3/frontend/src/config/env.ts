/**
 * Environment Variable Validation
 * NEM-1528: Type-safe configuration with runtime validation
 *
 * Validates all VITE_* environment variables at startup and provides
 * type-safe access to configuration values.
 *
 * Environment Variables:
 * - VITE_API_BASE_URL: Base URL for REST API (optional, defaults to relative URLs)
 * - VITE_WS_BASE_URL: Base URL for WebSocket connections (optional, falls back to window.location)
 * - VITE_API_KEY: API key for authentication (optional)
 *
 * @example
 * ```typescript
 * import { getEnvConfig, getBaseUrl, isDevelopment } from './config/env';
 *
 * const config = getEnvConfig();
 * console.log(config.apiBaseUrl);
 *
 * // Or use convenience getters
 * const baseUrl = getBaseUrl();
 * if (isDevelopment()) {
 *   console.log('Running in development mode');
 * }
 * ```
 */

/**
 * Validated environment configuration type.
 */
export interface EnvConfig {
  /** Base URL for REST API calls (empty string = relative URLs) */
  apiBaseUrl: string;
  /** Base URL for WebSocket connections (undefined = use window.location) */
  wsBaseUrl: string | undefined;
  /** API key for authentication (undefined = no auth) */
  apiKey: string | undefined;
  /** Current Vite mode (development, production, test) */
  mode: string;
  /** True if running in development mode */
  isDevelopment: boolean;
  /** True if running in production mode */
  isProduction: boolean;
  /** True if running in test mode */
  isTest: boolean;
}

/**
 * Custom error class for environment validation failures.
 * Provides structured error information for debugging configuration issues.
 */
export class EnvValidationError extends Error {
  public readonly validationErrors: string[];

  constructor(message: string, errors: string[] = []) {
    const fullMessage = errors.length > 0 ? `${message}:\n  - ${errors.join('\n  - ')}` : message;

    super(fullMessage);
    this.name = 'EnvValidationError';
    this.validationErrors = errors;

    // Ensure proper prototype chain for instanceof checks
    Object.setPrototypeOf(this, EnvValidationError.prototype);
  }
}

/**
 * Validates if a string is a valid URL with allowed protocols.
 *
 * @param url - The URL string to validate
 * @param required - If false, empty strings are considered valid (default: true)
 * @returns True if the URL is valid
 */
export function isValidUrl(url: string, required: boolean = true): boolean {
  // Empty string is valid for optional URLs (will use relative paths)
  if (url === '') {
    return !required;
  }

  try {
    const parsed = new URL(url);
    // Only allow http, https, ws, wss protocols
    return ['http:', 'https:', 'ws:', 'wss:'].includes(parsed.protocol);
  } catch {
    return false;
  }
}

/**
 * Validates if a URL uses WebSocket protocol (ws or wss).
 *
 * @param url - The URL string to validate
 * @returns True if the URL uses ws:// or wss:// protocol
 */
function isWebSocketUrl(url: string): boolean {
  if (url === '') return true; // Empty is valid (will use fallback)

  try {
    const parsed = new URL(url);
    return ['ws:', 'wss:'].includes(parsed.protocol);
  } catch {
    return false;
  }
}

/**
 * Raw environment variables type (what we receive from import.meta.env).
 */
interface RawEnv {
  VITE_API_BASE_URL?: string;
  VITE_WS_BASE_URL?: string;
  VITE_API_KEY?: string;
  MODE?: string;
  DEV?: boolean;
  PROD?: boolean;
}

/**
 * Validates environment variables and returns a typed configuration object.
 * Throws EnvValidationError if any required variables are invalid.
 *
 * @param env - Raw environment object (typically import.meta.env)
 * @returns Validated EnvConfig object
 * @throws EnvValidationError if validation fails
 */
export function validateEnv(env: RawEnv): EnvConfig {
  const errors: string[] = [];

  // Get values with defaults
  const apiBaseUrl = env.VITE_API_BASE_URL ?? '';
  const wsBaseUrl = env.VITE_WS_BASE_URL;
  const apiKey = env.VITE_API_KEY;
  const mode = env.MODE ?? 'development';

  // Validate VITE_API_BASE_URL (optional, but if provided must be valid URL)
  if (apiBaseUrl !== '' && !isValidUrl(apiBaseUrl)) {
    errors.push(`VITE_API_BASE_URL must be a valid URL (http/https), got: "${apiBaseUrl}"`);
  }

  // Validate VITE_WS_BASE_URL (optional, but if provided must be valid ws/wss URL)
  if (wsBaseUrl !== undefined && wsBaseUrl !== '') {
    if (!isValidUrl(wsBaseUrl)) {
      errors.push(`VITE_WS_BASE_URL must be a valid URL, got: "${wsBaseUrl}"`);
    } else if (!isWebSocketUrl(wsBaseUrl)) {
      errors.push(`VITE_WS_BASE_URL must use ws:// or wss:// protocol, got: "${wsBaseUrl}"`);
    }
  }

  // Throw if there are validation errors
  if (errors.length > 0) {
    throw new EnvValidationError('Environment validation failed', errors);
  }

  // Return validated config
  return {
    apiBaseUrl,
    wsBaseUrl: wsBaseUrl || undefined,
    apiKey: apiKey || undefined,
    mode,
    isDevelopment: mode === 'development',
    isProduction: mode === 'production',
    isTest: mode === 'test',
  };
}

// Cached configuration (validated once at startup)
let cachedConfig: EnvConfig | null = null;

/**
 * Gets the validated environment configuration.
 * The configuration is validated once and cached for subsequent calls.
 *
 * @returns Validated EnvConfig object
 * @throws EnvValidationError on first call if validation fails
 */
export function getEnvConfig(): EnvConfig {
  if (cachedConfig === null) {
    cachedConfig = validateEnv(import.meta.env as RawEnv);
  }
  return cachedConfig;
}

/**
 * Resets the cached configuration.
 * Primarily used for testing to allow re-validation with different env values.
 * @internal
 */
export function resetEnvCache(): void {
  cachedConfig = null;
}

// ============================================================================
// Convenience Getters
// ============================================================================

/**
 * Gets the base URL for REST API calls.
 * @returns Base URL string (empty string means relative URLs)
 */
export function getBaseUrl(): string {
  return getEnvConfig().apiBaseUrl;
}

/**
 * Gets the base URL for WebSocket connections.
 * @returns WebSocket base URL or undefined (will fall back to window.location)
 */
export function getWsBaseUrl(): string | undefined {
  return getEnvConfig().wsBaseUrl;
}

/**
 * Gets the API key for authentication.
 * @returns API key or undefined if not configured
 */
export function getApiKey(): string | undefined {
  return getEnvConfig().apiKey;
}

/**
 * Checks if running in development mode.
 * @returns True if MODE === 'development'
 */
export function isDevelopment(): boolean {
  return getEnvConfig().isDevelopment;
}

/**
 * Checks if running in production mode.
 * @returns True if MODE === 'production'
 */
export function isProduction(): boolean {
  return getEnvConfig().isProduction;
}

/**
 * Checks if running in test mode.
 * @returns True if MODE === 'test'
 */
export function isTest(): boolean {
  return getEnvConfig().isTest;
}

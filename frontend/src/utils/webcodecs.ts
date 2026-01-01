/**
 * WebCodecs API feature detection and fallback utilities
 *
 * WebCodecs API requires a secure context (HTTPS, localhost, or file://).
 * This module provides feature detection and graceful fallbacks for
 * environments where WebCodecs is not available.
 *
 * @see https://developer.mozilla.org/en-US/docs/Web/API/WebCodecs_API
 */

/**
 * Checks if the current browsing context is secure
 * Secure contexts include: HTTPS, localhost, 127.0.0.1, file://
 */
export function isSecureContext(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  return window.isSecureContext ?? false;
}

/**
 * Checks if the VideoDecoder API is available
 * VideoDecoder requires a secure context
 */
export function isVideoDecoderSupported(): boolean {
  if (!isSecureContext()) {
    return false;
  }
  return typeof VideoDecoder !== 'undefined';
}

/**
 * Checks if the VideoEncoder API is available
 * VideoEncoder requires a secure context
 */
export function isVideoEncoderSupported(): boolean {
  if (!isSecureContext()) {
    return false;
  }
  return typeof VideoEncoder !== 'undefined';
}

/**
 * Checks if the AudioDecoder API is available
 * AudioDecoder requires a secure context
 */
export function isAudioDecoderSupported(): boolean {
  if (!isSecureContext()) {
    return false;
  }
  return typeof AudioDecoder !== 'undefined';
}

/**
 * Checks if the AudioEncoder API is available
 * AudioEncoder requires a secure context
 */
export function isAudioEncoderSupported(): boolean {
  if (!isSecureContext()) {
    return false;
  }
  return typeof AudioEncoder !== 'undefined';
}

/**
 * Checks if any WebCodecs APIs are available
 */
export function isWebCodecsSupported(): boolean {
  return (
    isVideoDecoderSupported() ||
    isVideoEncoderSupported() ||
    isAudioDecoderSupported() ||
    isAudioEncoderSupported()
  );
}

/**
 * WebCodecs feature status with detailed information
 */
export interface WebCodecsStatus {
  /** Whether WebCodecs APIs are available */
  available: boolean;
  /** Whether the context is secure */
  secureContext: boolean;
  /** Individual API availability */
  apis: {
    videoDecoder: boolean;
    videoEncoder: boolean;
    audioDecoder: boolean;
    audioEncoder: boolean;
  };
  /** Human-readable status message */
  message: string;
  /** Recommended action if not available */
  recommendation: string | null;
}

/**
 * Get comprehensive WebCodecs feature status
 * Useful for displaying status in UI or debugging
 */
export function getWebCodecsStatus(): WebCodecsStatus {
  const secureContext = isSecureContext();
  const videoDecoder = isVideoDecoderSupported();
  const videoEncoder = isVideoEncoderSupported();
  const audioDecoder = isAudioDecoderSupported();
  const audioEncoder = isAudioEncoderSupported();
  const available = videoDecoder || videoEncoder || audioDecoder || audioEncoder;

  let message: string;
  let recommendation: string | null = null;

  if (available) {
    message = 'WebCodecs APIs are available';
  } else if (!secureContext) {
    message = 'WebCodecs APIs require a secure context (HTTPS)';
    recommendation =
      'Access the application via HTTPS, localhost, or 127.0.0.1 to enable advanced video processing features';
  } else {
    message = 'WebCodecs APIs are not supported by this browser';
    recommendation = 'Use a modern browser that supports WebCodecs (Chrome 94+, Edge 94+, Opera 80+)';
  }

  return {
    available,
    secureContext,
    apis: {
      videoDecoder,
      videoEncoder,
      audioDecoder,
      audioEncoder,
    },
    message,
    recommendation,
  };
}

/**
 * Logs WebCodecs availability status to console
 * Useful for debugging in development environments
 *
 * @param logLevel - Console log level to use ('log' | 'warn' | 'error' | 'info')
 */
export function logWebCodecsStatus(logLevel: 'log' | 'warn' | 'error' | 'info' = 'info'): void {
  const status = getWebCodecsStatus();

  if (!status.available) {
    // Use warn level for unavailable status to make it visible but not alarming
    // eslint-disable-next-line no-console
    console[logLevel === 'info' ? 'warn' : logLevel](
      `[WebCodecs] ${status.message}${status.recommendation ? `. ${status.recommendation}` : ''}`
    );
  } else {
    // eslint-disable-next-line no-console
    console[logLevel]('[WebCodecs] Available:', status.apis);
  }
}

/**
 * Safe wrapper that executes a callback only if WebCodecs is available
 * Falls back to an optional alternative when not available
 *
 * @param webCodecsCallback - Function to execute if WebCodecs is available
 * @param fallbackCallback - Optional function to execute if WebCodecs is not available
 * @returns Result of either callback, or undefined if neither executes
 */
export function withWebCodecs<T>(
  webCodecsCallback: () => T,
  fallbackCallback?: () => T
): T | undefined {
  if (isWebCodecsSupported()) {
    return webCodecsCallback();
  }

  if (fallbackCallback) {
    return fallbackCallback();
  }

  return undefined;
}

/**
 * Type guard for checking WebCodecs availability before using APIs
 * Helps with TypeScript narrowing
 *
 * @example
 * ```typescript
 * if (canUseVideoDecoder()) {
 *   const decoder = new VideoDecoder(config);
 * }
 * ```
 */
export function canUseVideoDecoder(): boolean {
  return isVideoDecoderSupported();
}

/**
 * Type guard for checking VideoEncoder availability
 */
export function canUseVideoEncoder(): boolean {
  return isVideoEncoderSupported();
}

/**
 * Error message for when WebCodecs is required but not available
 */
export const WEBCODECS_NOT_AVAILABLE_MESSAGE =
  'This feature requires WebCodecs API which is only available in secure contexts (HTTPS). ' +
  'Please access the application via HTTPS or localhost to use this feature.';

/**
 * Creates a user-friendly error for WebCodecs unavailability
 */
export class WebCodecsNotAvailableError extends Error {
  public readonly isSecureContext: boolean;
  public readonly recommendation: string | null;

  constructor() {
    const status = getWebCodecsStatus();
    super(status.message);
    this.name = 'WebCodecsNotAvailableError';
    this.isSecureContext = status.secureContext;
    this.recommendation = status.recommendation;
  }
}

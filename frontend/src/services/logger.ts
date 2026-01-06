/**
 * Frontend logging service that captures errors and events,
 * batches them efficiently, and sends to the backend for storage.
 *
 * NEM-1554: Optimized with efficient batching:
 * - Single batched request instead of multiple parallel requests
 * - Uses navigator.sendBeacon() on page unload for reliability
 * - Configurable max queue size to prevent memory issues
 * - Page unload handler for guaranteed delivery of final logs
 */

type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

interface LogEntry {
  level: LogLevel;
  component: string;
  message: string;
  extra?: Record<string, unknown>;
  timestamp: string;
}

/**
 * Configuration options for the Logger.
 */
interface LoggerConfig {
  /** Number of entries to accumulate before flushing (default: 10) */
  batchSize: number;
  /** Interval in ms between automatic flushes (default: 5000) */
  flushIntervalMs: number;
  /** Endpoint for individual log entries (fallback) */
  endpoint: string;
  /** Endpoint for batched log entries (preferred) */
  batchEndpoint?: string;
  /** Whether logging is enabled (default: true) */
  enabled: boolean;
  /** Maximum queue size to prevent memory issues (default: 100) */
  maxQueueSize: number;
}

const defaultConfig: LoggerConfig = {
  batchSize: 10,
  flushIntervalMs: 5000,
  endpoint: '/api/logs/frontend',
  batchEndpoint: '/api/logs/frontend/batch',
  enabled: true,
  maxQueueSize: 100,
};

class Logger {
  private queue: LogEntry[] = [];
  private config: LoggerConfig;
  private flushTimer: ReturnType<typeof setInterval> | null = null;
  private isDestroyed: boolean = false;
  private boundBeforeUnload: (() => void) | null = null;

  constructor(config: Partial<LoggerConfig> = {}) {
    this.config = { ...defaultConfig, ...config };
    this.startFlushTimer();
    this.setupGlobalHandlers();
    this.setupUnloadHandler();
  }

  private startFlushTimer(): void {
    // Clear existing timer if present (defensive programming for future extensibility)
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
    }
    this.flushTimer = setInterval(() => {
      void this.flush();
    }, this.config.flushIntervalMs);
  }

  private setupGlobalHandlers(): void {
    // Capture unhandled errors
    window.onerror = (message, source, lineno, colno, error) => {
      this.error('Unhandled error', {
        message: typeof message === 'string' ? message : message?.type ?? 'Unknown error',
        source,
        lineno,
        colno,
        stack: error?.stack,
      });
      return false;
    };

    // Capture unhandled promise rejections
    window.onunhandledrejection = (event) => {
      const reason = event.reason as Error | undefined;
      this.error('Unhandled promise rejection', {
        reason: String(event.reason),
        stack: reason?.stack,
      });
    };
  }

  /**
   * Sets up beforeunload handler to flush logs when the page is closing.
   * Uses sendBeacon for reliable delivery during page unload.
   */
  private setupUnloadHandler(): void {
    if (typeof window !== 'undefined') {
      this.boundBeforeUnload = () => {
        this.flushWithBeacon();
      };
      window.addEventListener('beforeunload', this.boundBeforeUnload);
      // Also handle visibilitychange for mobile browsers
      window.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') {
          this.flushWithBeacon();
        }
      });
    }
  }

  private log(
    level: LogLevel,
    component: string,
    message: string,
    extra?: Record<string, unknown>
  ): void {
    const entry: LogEntry = {
      level,
      component,
      message,
      extra: {
        ...extra,
        url: window.location.href,
      },
      timestamp: new Date().toISOString(),
    };

    // Always log to console in development
    const consoleMethod =
      level === 'ERROR' || level === 'CRITICAL' ? 'error' : level === 'WARNING' ? 'warn' : 'log';
    // eslint-disable-next-line no-console
    console[consoleMethod](`[${level}] ${component}: ${message}`, extra);

    if (!this.config.enabled) return;

    // Enforce max queue size to prevent memory issues
    if (this.queue.length >= this.config.maxQueueSize) {
      // Drop oldest entry to make room
      this.queue.shift();
    }

    this.queue.push(entry);

    if (this.queue.length >= this.config.batchSize) {
      void this.flush();
    }
  }

  /**
   * Flushes the log queue by sending all entries in a single batched request.
   * This is more efficient than sending individual requests.
   */
  async flush(): Promise<void> {
    if (this.queue.length === 0 || this.isDestroyed) return;

    const entries = [...this.queue];
    this.queue = [];

    try {
      if (this.config.batchEndpoint) {
        // Send as a single batched request (preferred)
        await fetch(this.config.batchEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            entries: entries.map((entry) => ({
              level: entry.level,
              component: entry.component,
              message: entry.message,
              extra: entry.extra,
              timestamp: entry.timestamp,
            })),
          }),
        });
      } else {
        // Fallback to individual requests (legacy behavior)
        await Promise.all(
          entries.map((entry) =>
            fetch(this.config.endpoint, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                level: entry.level,
                component: entry.component,
                message: entry.message,
                extra: entry.extra,
              }),
            })
          )
        );
      }
    } catch (err) {
      // On failure, preserve entries if queue isn't full
      if (this.queue.length + entries.length <= this.config.maxQueueSize) {
        this.queue.unshift(...entries);
      }
      console.error('Failed to flush logs:', err);
    }
  }

  /**
   * Flushes the log queue using navigator.sendBeacon() for reliable delivery.
   * This is used during page unload when async requests may not complete.
   * Falls back to regular fetch if sendBeacon is not available.
   */
  flushWithBeacon(): void {
    if (this.queue.length === 0) return;

    const entries = [...this.queue];
    this.queue = [];

    const endpoint = this.config.batchEndpoint || this.config.endpoint;
    const payload = JSON.stringify({
      entries: entries.map((entry) => ({
        level: entry.level,
        component: entry.component,
        message: entry.message,
        extra: entry.extra,
        timestamp: entry.timestamp,
      })),
    });

    // Try sendBeacon first (most reliable during page unload)
    if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      const blob = new Blob([payload], { type: 'application/json' });
      const sent = navigator.sendBeacon(endpoint, blob);
      if (sent) {
        return;
      }
      // If sendBeacon fails, fall through to fetch
    }

    // Fallback to async fetch (may not complete during unload)
    void fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload,
      // Use keepalive to improve chances of completion during unload
      keepalive: true,
    }).catch(() => {
      // Silently fail - we're unloading anyway
    });
  }

  /**
   * Returns the current number of entries in the queue.
   * Useful for testing and debugging.
   */
  getQueueSize(): number {
    return this.queue.length;
  }

  debug(message: string, extra?: Record<string, unknown>): void {
    this.log('DEBUG', 'frontend', message, extra);
  }

  info(message: string, extra?: Record<string, unknown>): void {
    this.log('INFO', 'frontend', message, extra);
  }

  warn(message: string, extra?: Record<string, unknown>): void {
    this.log('WARNING', 'frontend', message, extra);
  }

  error(message: string, extra?: Record<string, unknown>): void {
    this.log('ERROR', 'frontend', message, extra);
  }

  event(eventName: string, extra?: Record<string, unknown>): void {
    this.log('INFO', 'user_event', eventName, extra);
  }

  apiError(endpoint: string, status: number, message: string): void {
    this.log('ERROR', 'api', `API error: ${endpoint}`, {
      endpoint,
      status,
      message,
    });
  }

  forComponent(component: string): ComponentLogger {
    return new ComponentLogger(this, component);
  }

  restart(): void {
    // Restart the flush timer with current configuration
    this.isDestroyed = false;
    this.startFlushTimer();
  }

  destroy(): void {
    this.isDestroyed = true;
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }
    if (this.boundBeforeUnload && typeof window !== 'undefined') {
      window.removeEventListener('beforeunload', this.boundBeforeUnload);
    }
    // Final flush attempt
    this.flushWithBeacon();
  }
}

class ComponentLogger {
  constructor(
    private parentLogger: Logger,
    private component: string
  ) {}

  private log(level: LogLevel, message: string, extra?: Record<string, unknown>): void {
    (this.parentLogger as unknown as { log: Logger['log'] }).log(
      level,
      this.component,
      message,
      extra
    );
  }

  debug(message: string, extra?: Record<string, unknown>): void {
    this.log('DEBUG', message, extra);
  }

  info(message: string, extra?: Record<string, unknown>): void {
    this.log('INFO', message, extra);
  }

  warn(message: string, extra?: Record<string, unknown>): void {
    this.log('WARNING', message, extra);
  }

  error(message: string, extra?: Record<string, unknown>): void {
    this.log('ERROR', message, extra);
  }
}

export const logger = new Logger();
export type { LogLevel, LogEntry, ComponentLogger, LoggerConfig };
// Export Logger class for testing purposes
export { Logger };

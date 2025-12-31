/**
 * Frontend logging service that captures errors and events,
 * batches them, and sends to the backend for storage.
 */

type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

interface LogEntry {
  level: LogLevel;
  component: string;
  message: string;
  extra?: Record<string, unknown>;
  timestamp: string;
}

interface LoggerConfig {
  batchSize: number;
  flushIntervalMs: number;
  endpoint: string;
  enabled: boolean;
}

const defaultConfig: LoggerConfig = {
  batchSize: 10,
  flushIntervalMs: 5000,
  endpoint: '/api/logs/frontend',
  enabled: true,
};

class Logger {
  private queue: LogEntry[] = [];
  private config: LoggerConfig;
  private flushTimer: ReturnType<typeof setInterval> | null = null;

  constructor(config: Partial<LoggerConfig> = {}) {
    this.config = { ...defaultConfig, ...config };
    this.startFlushTimer();
    this.setupGlobalHandlers();
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

    this.queue.push(entry);

    if (this.queue.length >= this.config.batchSize) {
      void this.flush();
    }
  }

  async flush(): Promise<void> {
    if (this.queue.length === 0) return;

    const entries = [...this.queue];
    this.queue = [];

    try {
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
    } catch (err) {
      if (this.queue.length < 100) {
        this.queue.unshift(...entries);
      }
      console.error('Failed to flush logs:', err);
    }
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
    this.startFlushTimer();
  }

  destroy(): void {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
    }
    void this.flush();
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
export type { LogLevel, LogEntry, ComponentLogger };
// Export Logger class for testing purposes
export { Logger };

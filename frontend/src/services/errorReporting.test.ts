/**
 * Tests for error reporting service.
 *
 * NEM-2726: Global error handlers for uncaught exceptions and promise rejections.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Helper to generate unique test identifiers to avoid rate limiting between tests
let testCounter = 0;
function uniqueTestId(): string {
  return `test_${Date.now()}_${++testCounter}`;
}

describe('errorReporting', () => {
  let addEventListenerSpy: ReturnType<typeof vi.spyOn>;
  let removeEventListenerSpy: ReturnType<typeof vi.spyOn>;
  let consoleSpy: {
    log: ReturnType<typeof vi.spyOn>;
    warn: ReturnType<typeof vi.spyOn>;
    error: ReturnType<typeof vi.spyOn>;
  };
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    vi.resetModules();

    // Import and cleanup any existing handlers before tests
    const { cleanupErrorReporting, clearRateLimitCache } = await import('./errorReporting');
    cleanupErrorReporting();
    clearRateLimitCache();

    addEventListenerSpy = vi.spyOn(window, 'addEventListener');
    removeEventListenerSpy = vi.spyOn(window, 'removeEventListener');

    consoleSpy = {
      log: vi.spyOn(console, 'log').mockImplementation(() => {}),
      warn: vi.spyOn(console, 'warn').mockImplementation(() => {}),
      error: vi.spyOn(console, 'error').mockImplementation(() => {}),
    };

    fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(async () => {
    // Cleanup error reporting handlers
    const { cleanupErrorReporting, clearRateLimitCache } = await import('./errorReporting');
    cleanupErrorReporting();
    clearRateLimitCache();

    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.resetModules();
  });

  describe('initializeErrorReporting', () => {
    it('adds error event listener', async () => {
      const { initializeErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      expect(addEventListenerSpy).toHaveBeenCalledWith('error', expect.any(Function));
    });

    it('adds unhandledrejection event listener', async () => {
      const { initializeErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      expect(addEventListenerSpy).toHaveBeenCalledWith('unhandledrejection', expect.any(Function));
    });

    it('does not initialize twice', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();
      const callCountAfterFirst = addEventListenerSpy.mock.calls.length;

      initializeErrorReporting();
      expect(addEventListenerSpy.mock.calls.length).toBe(callCountAfterFirst);

      cleanupErrorReporting();
    });

    it('can be re-initialized after cleanup', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();
      cleanupErrorReporting();

      const callCountAfterCleanup = addEventListenerSpy.mock.calls.length;
      initializeErrorReporting();

      expect(addEventListenerSpy.mock.calls.length).toBeGreaterThan(Number(callCountAfterCleanup));
      cleanupErrorReporting();
    });
  });

  describe('cleanupErrorReporting', () => {
    it('removes event listeners', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();
      cleanupErrorReporting();

      expect(removeEventListenerSpy).toHaveBeenCalledWith('error', expect.any(Function));
      expect(removeEventListenerSpy).toHaveBeenCalledWith(
        'unhandledrejection',
        expect.any(Function)
      );
    });
  });

  describe('error filtering', () => {
    it('ignores ResizeObserver loop limit exceeded errors', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const errorEvent = new ErrorEvent('error', {
        message: 'ResizeObserver loop limit exceeded',
        error: new Error('ResizeObserver loop limit exceeded'),
      });

      window.dispatchEvent(errorEvent);

      // Should not log the error
      expect(consoleSpy.error).not.toHaveBeenCalledWith(
        expect.stringContaining('[ErrorReporting]'),
        expect.anything()
      );

      cleanupErrorReporting();
    });

    it('ignores ResizeObserver loop completed with undelivered notifications', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const errorEvent = new ErrorEvent('error', {
        message: 'ResizeObserver loop completed with undelivered notifications.',
        error: new Error('ResizeObserver loop completed with undelivered notifications.'),
      });

      window.dispatchEvent(errorEvent);

      // Should not log the error
      expect(consoleSpy.error).not.toHaveBeenCalledWith(
        expect.stringContaining('[ErrorReporting]'),
        expect.anything()
      );

      cleanupErrorReporting();
    });

    it('ignores Script error (cross-origin errors)', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const errorEvent = new ErrorEvent('error', {
        message: 'Script error.',
        filename: '',
        lineno: 0,
        colno: 0,
      });

      window.dispatchEvent(errorEvent);

      // Should not log the error
      expect(consoleSpy.error).not.toHaveBeenCalledWith(
        expect.stringContaining('[ErrorReporting]'),
        expect.anything()
      );

      cleanupErrorReporting();
    });

    it('ignores Network Error (handled by API interceptor)', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const errorEvent = new ErrorEvent('error', {
        message: 'Network Error',
        error: new Error('Network Error'),
      });

      window.dispatchEvent(errorEvent);

      // Should not log the error
      expect(consoleSpy.error).not.toHaveBeenCalledWith(
        expect.stringContaining('[ErrorReporting]'),
        expect.anything()
      );

      cleanupErrorReporting();
    });

    it('ignores AbortError (intentional request cancellation)', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const abortError = new DOMException('The operation was aborted', 'AbortError');
      const errorEvent = new ErrorEvent('error', {
        message: 'AbortError: The operation was aborted',
        error: abortError,
      });

      window.dispatchEvent(errorEvent);

      // Should not log the error
      expect(consoleSpy.error).not.toHaveBeenCalledWith(
        expect.stringContaining('[ErrorReporting]'),
        expect.anything()
      );

      cleanupErrorReporting();
    });
  });

  describe('uncaught exception handling', () => {
    it('logs uncaught exceptions', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const testError = new Error('Test uncaught exception');
      testError.stack = 'Error: Test uncaught exception\n    at test.ts:10:5';
      const errorEvent = new ErrorEvent('error', {
        message: 'Test uncaught exception',
        error: testError,
        filename: 'test.ts',
        lineno: 10,
        colno: 5,
      });

      window.dispatchEvent(errorEvent);

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining('[ErrorReporting] Uncaught exception'),
        expect.objectContaining({
          message: 'Test uncaught exception',
        })
      );

      cleanupErrorReporting();
    });

    it('includes error details in log', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const testError = new Error('Test error with details');
      testError.stack = 'Error: Test error with details\n    at file.ts:20:10';
      const errorEvent = new ErrorEvent('error', {
        message: 'Test error with details',
        error: testError,
        filename: 'file.ts',
        lineno: 20,
        colno: 10,
      });

      window.dispatchEvent(errorEvent);

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining('[ErrorReporting]'),
        expect.objectContaining({
          message: 'Test error with details',
          filename: 'file.ts',
          lineno: 20,
          colno: 10,
          stack: expect.stringContaining('Error: Test error with details'),
        })
      );

      cleanupErrorReporting();
    });
  });

  describe('unhandled promise rejection handling', () => {
    it('logs unhandled promise rejections', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const testError = new Error('Test promise rejection');
      testError.stack = 'Error: Test promise rejection\n    at promise.ts:5:1';
      const rejectionEvent = new PromiseRejectionEvent('unhandledrejection', {
        promise: Promise.reject(testError),
        reason: testError,
      });

      // Catch the rejection to avoid test pollution
      rejectionEvent.promise.catch(() => {});

      window.dispatchEvent(rejectionEvent);

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining('[ErrorReporting] Unhandled promise rejection'),
        expect.objectContaining({
          reason: 'Error: Test promise rejection',
        })
      );

      cleanupErrorReporting();
    });

    it('handles non-Error rejection reasons', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      // Create a promise that rejects with a string (testing non-Error rejection handling)
      // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors -- testing non-Error rejection
      const rejectingPromise = Promise.reject('string rejection');
      const rejectionEvent = new PromiseRejectionEvent('unhandledrejection', {
        promise: rejectingPromise,
        reason: 'string rejection',
      });

      // Catch the rejection to avoid test pollution
      rejectionEvent.promise.catch(() => {});

      window.dispatchEvent(rejectionEvent);

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining('[ErrorReporting] Unhandled promise rejection'),
        expect.objectContaining({
          reason: 'string rejection',
        })
      );

      cleanupErrorReporting();
    });

    it('ignores Network Error rejections', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const networkError = new Error('Network Error');
      const rejectionEvent = new PromiseRejectionEvent('unhandledrejection', {
        promise: Promise.reject(networkError),
        reason: networkError,
      });

      // Catch the rejection to avoid test pollution
      rejectionEvent.promise.catch(() => {});

      window.dispatchEvent(rejectionEvent);

      // Should not log the error
      expect(consoleSpy.error).not.toHaveBeenCalledWith(
        expect.stringContaining('[ErrorReporting]'),
        expect.anything()
      );

      cleanupErrorReporting();
    });

    it('ignores AbortError rejections', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const abortError = new DOMException('The operation was aborted', 'AbortError');
      const rejectionEvent = new PromiseRejectionEvent('unhandledrejection', {
        promise: Promise.reject(abortError),
        reason: abortError,
      });

      // Catch the rejection to avoid test pollution
      rejectionEvent.promise.catch(() => {});

      window.dispatchEvent(rejectionEvent);

      // Should not log the error
      expect(consoleSpy.error).not.toHaveBeenCalledWith(
        expect.stringContaining('[ErrorReporting]'),
        expect.anything()
      );

      cleanupErrorReporting();
    });
  });

  describe('rate limiting', () => {
    it('rate limits identical errors', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const testError = new Error('Repeated error');
      testError.stack = 'Error: Repeated error\n    at test.ts:1:1';

      // Fire the same error multiple times rapidly
      for (let i = 0; i < 10; i++) {
        const errorEvent = new ErrorEvent('error', {
          message: 'Repeated error',
          error: testError,
          filename: 'test.ts',
          lineno: 1,
          colno: 1,
        });
        window.dispatchEvent(errorEvent);
      }

      // Should only log the first occurrence within the rate limit window
      const errorCalls = consoleSpy.error.mock.calls.filter((call: unknown[]) =>
        String(call[0]).includes('[ErrorReporting]')
      );

      // First error should be logged, subsequent ones within rate limit should be suppressed
      expect(errorCalls.length).toBeLessThan(10);

      cleanupErrorReporting();
    });

    it('allows different errors to be logged', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const testId = uniqueTestId();

      // Fire different errors with unique identifiers
      for (let i = 0; i < 3; i++) {
        const message = `Different error ${testId}_${i}`;
        const testError = new Error(message);
        testError.stack = `Error: ${message}\n    at test_${i}.ts:${i}:1`;
        const errorEvent = new ErrorEvent('error', {
          message,
          error: testError,
          filename: `test_${i}.ts`,
          lineno: i,
          colno: 1,
        });
        window.dispatchEvent(errorEvent);
      }

      // All different errors should be logged
      const errorCalls = consoleSpy.error.mock.calls.filter(
        (call: unknown[]) =>
          String(call[0]).includes('[ErrorReporting]') &&
          String((call[1] as { message?: string } | undefined)?.message).includes(testId)
      );

      expect(errorCalls.length).toBe(3);

      cleanupErrorReporting();
    });

    it('respects rate limit window expiry', async () => {
      vi.useFakeTimers();

      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const testId = uniqueTestId();
      const message = `Timed error ${testId}`;
      const testError = new Error(message);
      testError.stack = `Error: ${message}\n    at test_timed.ts:1:1`;
      const createErrorEvent = () =>
        new ErrorEvent('error', {
          message,
          error: testError,
          filename: 'test_timed.ts',
          lineno: 1,
          colno: 1,
        });

      // Fire first error
      window.dispatchEvent(createErrorEvent());

      // Wait for rate limit window to expire (default 10 seconds)
      vi.advanceTimersByTime(11000);

      // Fire same error again
      window.dispatchEvent(createErrorEvent());

      // Both errors should be logged (one before window, one after)
      const errorCalls = consoleSpy.error.mock.calls.filter(
        (call: unknown[]) =>
          String(call[0]).includes('[ErrorReporting]') &&
          String((call[1] as { message?: string } | undefined)?.message).includes(testId)
      );

      expect(errorCalls.length).toBe(2);

      cleanupErrorReporting();
      vi.useRealTimers();
    });
  });

  describe('backend reporting', () => {
    it('sends errors to backend endpoint', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const testError = new Error('Backend test error');
      testError.stack = 'Error: Backend test error\n    at test.ts:1:1';
      const errorEvent = new ErrorEvent('error', {
        message: 'Backend test error',
        error: testError,
        filename: 'test.ts',
        lineno: 1,
        colno: 1,
      });

      window.dispatchEvent(errorEvent);

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 10));

      expect(fetchMock).toHaveBeenCalledWith(
        '/api/logs/frontend',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: expect.any(String),
        })
      );

      cleanupErrorReporting();
    });

    it('handles backend errors gracefully', async () => {
      fetchMock.mockRejectedValueOnce(new Error('Backend unavailable'));

      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting();

      const testError = new Error('Error when backend down');
      testError.stack = 'Error: Error when backend down\n    at test.ts:1:1';
      const errorEvent = new ErrorEvent('error', {
        message: 'Error when backend down',
        error: testError,
        filename: 'test.ts',
        lineno: 1,
        colno: 1,
      });

      // Should not throw
      expect(() => window.dispatchEvent(errorEvent)).not.toThrow();

      cleanupErrorReporting();
    });
  });

  describe('configuration', () => {
    it('can be configured with custom options', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting({
        enabled: true,
        endpoint: '/api/custom/errors',
        rateLimitMs: 5000,
      });

      const testError = new Error('Custom config error');
      testError.stack = 'Error: Custom config error\n    at test.ts:1:1';
      const errorEvent = new ErrorEvent('error', {
        message: 'Custom config error',
        error: testError,
        filename: 'test.ts',
        lineno: 1,
        colno: 1,
      });

      window.dispatchEvent(errorEvent);

      // Wait for async operations
      await new Promise((resolve) => setTimeout(resolve, 10));

      expect(fetchMock).toHaveBeenCalledWith(
        '/api/custom/errors',
        expect.objectContaining({
          method: 'POST',
        })
      );

      cleanupErrorReporting();
    });

    it('can be disabled', async () => {
      const { initializeErrorReporting, cleanupErrorReporting } = await import('./errorReporting');
      initializeErrorReporting({
        enabled: false,
      });

      const testId = uniqueTestId();
      const message = `Disabled error ${testId}`;
      const testError = new Error(message);
      testError.stack = `Error: ${message}\n    at test_disabled.ts:1:1`;
      const errorEvent = new ErrorEvent('error', {
        message,
        error: testError,
        filename: 'test_disabled.ts',
        lineno: 1,
        colno: 1,
      });

      window.dispatchEvent(errorEvent);

      // Should not log anything with our test ID (filter out noise from other sources)
      const errorCalls = consoleSpy.error.mock.calls.filter(
        (call: unknown[]) =>
          String(call[0]).includes('[ErrorReporting]') &&
          String((call[1] as { message?: string } | undefined)?.message).includes(testId)
      );

      expect(errorCalls.length).toBe(0);

      cleanupErrorReporting();
    });
  });

  describe('isErrorIgnored export', () => {
    it('correctly identifies ignored errors', async () => {
      const { isErrorIgnored } = await import('./errorReporting');

      expect(isErrorIgnored('ResizeObserver loop limit exceeded')).toBe(true);
      expect(isErrorIgnored('ResizeObserver loop completed with undelivered notifications.')).toBe(
        true
      );
      expect(isErrorIgnored('Script error.')).toBe(true);
      expect(isErrorIgnored('Network Error')).toBe(true);
      expect(isErrorIgnored('AbortError: The operation was aborted')).toBe(true);
      expect(isErrorIgnored('Some real error')).toBe(false);
    });
  });

  describe('type exports', () => {
    it('exports ErrorReportingConfig type', async () => {
      const module = await import('./errorReporting');
      // TypeScript will verify the type exists at compile time
      // This test just ensures the module exports are accessible
      expect(module.initializeErrorReporting).toBeDefined();
      expect(module.cleanupErrorReporting).toBeDefined();
      expect(module.isErrorIgnored).toBeDefined();
    });
  });
});

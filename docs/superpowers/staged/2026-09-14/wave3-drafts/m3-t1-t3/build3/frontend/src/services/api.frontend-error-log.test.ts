/**
 * Tests for logFrontendError API function.
 * NEM-2725: Wire React error boundaries to backend logging endpoint.
 *
 * These tests follow TDD - they were written before the implementation.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';

import {
  logFrontendError,
  logFrontendErrorNoThrow,
  createFrontendErrorPayload,
  type FrontendErrorLogRequest,
} from './api';

// Helper to create mock fetch response
function createMockResponse<T>(data: T, status = 200, statusText = 'OK'): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText,
    json: () => Promise.resolve(data),
    headers: new Headers({ 'Content-Type': 'application/json' }),
  } as Response;
}

function createMockErrorResponse(status: number, statusText: string, detail?: string): Response {
  const errorBody = detail ? { detail } : null;
  return {
    ok: false,
    status,
    statusText,
    json: () => Promise.resolve(errorBody),
    headers: new Headers({ 'Content-Type': 'application/json' }),
  } as Response;
}

/**
 * The shipped fetchApi retries 5xx/network failures MAX_RETRIES=3 times with
 * exponential backoff (BASE_DELAY_MS=1000 -> delays 1s/2s/4s). Two hazards for
 * single-shot mocks here: (a) real-timer waits, and (b) once a
 * mockResolvedValueOnce queue is exhausted the retry call falls THROUGH the
 * spy into msw's global interceptor, whose /api/logs/frontend handler answers
 * 204 -> handleResponse resolves undefined -> "promise resolved instead of
 * rejecting". Wrap failure-path calls in this helper: fake timers drive the
 * ladder deterministically (repo idiom, api.test.ts:2888) while the caller
 * keeps a PERSISTENT (non-Once) failing mock so every attempt fails and the
 * ladder terminates in ApiError(500) / ApiError(0).
 */
async function drainRetryBackoff<T>(
  start: () => Promise<T>,
  catcher?: (error: unknown) => unknown
): Promise<T> {
  vi.useFakeTimers();
  try {
    const promise = start();
    // fetchApi's in-flight dedup path (POST requests) wraps fetchWithRetry in
    // .finally() — a transform, NOT a catcher — so the rejection is briefly
    // unmarked and vitest's unhandled-rejection hook flags it before a
    // test-side await attaches (the pattern's own :1321 comment calls this
    // path racy by design; callers should pass a signal). Attaching the
    // caller's catcher at start time marks the chain handled immediately.
    // Unannotated ternary types as Promise<T> | Promise<unknown>; awaiting
    // yields unknown, cast at the return (annotating the union here would
    // trip @typescript-eslint/no-redundant-type-constituents: T | unknown).
    const tracked = catcher ? promise.catch(catcher) : promise;
    await vi.advanceTimersByTimeAsync(7000); // 1000 + 2000 + 4000 backoff sum
    // When a catcher is passed the call REJECTS (both callers assert via
    // expect(rejects) on the caller-held promise), so the resolved-T branch is
    // the only one reachable here; cast satisfies tsc, not runtime.
    return (await tracked) as T;
  } finally {
    vi.useRealTimers();
  }
}

describe('logFrontendError', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  describe('successful logging', () => {
    it('sends error log to POST /api/logs/frontend', async () => {
      const mockResponse = { id: 123, status: 'created' };
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse, 201));

      const payload: FrontendErrorLogRequest = {
        level: 'ERROR',
        message: 'Test error message',
        component: 'TestComponent',
        url: 'http://localhost:5173/dashboard',
        user_agent: 'Mozilla/5.0',
        extra: {
          stack: 'Error: Test\n    at TestComponent',
          source: 'error_boundary',
        },
      };

      const result = await logFrontendError(payload);

      expect(fetchSpy).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/logs\/frontend$/),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(payload),
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it('includes all required fields in the request', async () => {
      const mockResponse = { id: 456, status: 'created' };
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse, 201));

      const payload: FrontendErrorLogRequest = {
        level: 'ERROR',
        message: 'Component crashed',
        component: 'RiskGauge',
      };

      await logFrontendError(payload);

      const [, options] = fetchSpy.mock.calls[0] as [string, RequestInit];
      const body = JSON.parse(options.body as string) as FrontendErrorLogRequest;

      expect(body.level).toBe('ERROR');
      expect(body.message).toBe('Component crashed');
      expect(body.component).toBe('RiskGauge');
    });

    it('includes optional fields when provided', async () => {
      const mockResponse = { id: 789, status: 'created' };
      fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse, 201));

      const payload: FrontendErrorLogRequest = {
        level: 'ERROR',
        message: 'Render error',
        component: 'Dashboard',
        url: 'http://localhost/dashboard',
        user_agent: 'Chrome/120',
        extra: {
          stack: 'Error: Render failed\n    at Dashboard.render',
          source: 'error_boundary',
          timestamp: '2025-01-01T10:00:00Z',
          componentStack: '\n    in Dashboard\n    in App',
          customField: 'custom value',
        },
      };

      await logFrontendError(payload);

      const [, options] = fetchSpy.mock.calls[0] as [string, RequestInit];
      const body = JSON.parse(options.body as string) as FrontendErrorLogRequest;

      expect(body.url).toBe('http://localhost/dashboard');
      expect(body.user_agent).toBe('Chrome/120');
      expect(body.extra?.stack).toContain('Error: Render failed');
      expect(body.extra?.source).toBe('error_boundary');
      expect(body.extra?.componentStack).toContain('Dashboard');
      expect(body.extra?.customField).toBe('custom value');
    });
  });

  describe('error handling', () => {
    it('throws ApiError on server error', async () => {
      // 500 IS retried (shouldRetry: status 0 || 5xx) — persistent mock so all
      // 4 attempts fail; see drainRetryBackoff for why.
      fetchSpy.mockResolvedValue(createMockErrorResponse(500, 'Internal Server Error'));

      const payload: FrontendErrorLogRequest = {
        level: 'ERROR',
        message: 'Test error',
        component: 'Test',
      };

      // Catcher attached at start time (marks dedup-chain rejection handled).
      let caught: unknown;
      await drainRetryBackoff(
        () => logFrontendError(payload),
        (error) => {
          caught = error;
        }
      );
      expect(caught).toBeInstanceOf(Error);
    });

    it('throws ApiError on validation error', async () => {
      fetchSpy.mockResolvedValueOnce(
        createMockErrorResponse(422, 'Unprocessable Entity', 'Invalid log level')
      );

      const payload: FrontendErrorLogRequest = {
        level: 'INVALID' as FrontendErrorLogRequest['level'],
        message: 'Test error',
        component: 'Test',
      };

      await expect(logFrontendError(payload)).rejects.toThrow();
    });

    it('throws ApiError on network error', async () => {
      // Network errors ARE retried — persistent rejection so the ladder ends
      // in ApiError(0, 'Network error'); see drainRetryBackoff.
      fetchSpy.mockRejectedValue(new Error('Network error'));

      const payload: FrontendErrorLogRequest = {
        level: 'ERROR',
        message: 'Test error',
        component: 'Test',
      };

      let caught: unknown;
      await drainRetryBackoff(
        () => logFrontendError(payload),
        (error) => {
          caught = error;
        }
      );
      expect(caught).toBeInstanceOf(Error);
    });
  });
});

describe('logFrontendErrorNoThrow', () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;
  let consoleWarnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, 'fetch');
    consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    fetchSpy.mockRestore();
    consoleWarnSpy.mockRestore();
  });

  it('returns true on successful logging', async () => {
    const mockResponse = { id: 123, status: 'created' };
    fetchSpy.mockResolvedValueOnce(createMockResponse(mockResponse, 201));

    const payload: FrontendErrorLogRequest = {
      level: 'ERROR',
      message: 'Test error',
      component: 'TestComponent',
    };

    const result = await logFrontendErrorNoThrow(payload);

    expect(result).toBe(true);
  });

  it('returns false and logs warning on server error without throwing', async () => {
    // Persistent 500 across all retry attempts (see drainRetryBackoff).
    fetchSpy.mockResolvedValue(createMockErrorResponse(500, 'Internal Server Error'));

    const payload: FrontendErrorLogRequest = {
      level: 'ERROR',
      message: 'Test error',
      component: 'Test',
    };

    const result = await drainRetryBackoff(() => logFrontendErrorNoThrow(payload));

    expect(result).toBe(false);
    expect(consoleWarnSpy).toHaveBeenCalledWith(
      'Failed to log frontend error to backend:',
      expect.any(Error)
    );
  });

  it('returns false and logs warning on network error without throwing', async () => {
    fetchSpy.mockRejectedValue(new Error('Network error'));

    const payload: FrontendErrorLogRequest = {
      level: 'ERROR',
      message: 'Test error',
      component: 'Test',
    };

    const result = await drainRetryBackoff(() => logFrontendErrorNoThrow(payload));

    expect(result).toBe(false);
    expect(consoleWarnSpy).toHaveBeenCalled();
  });

  it('prevents app crash when logging fails', async () => {
    fetchSpy.mockRejectedValue(new Error('Backend unavailable'));

    const payload: FrontendErrorLogRequest = {
      level: 'ERROR',
      message: 'Critical error',
      component: 'App',
    };

    // Should not throw
    const result = await drainRetryBackoff(() => logFrontendErrorNoThrow(payload));

    expect(result).toBe(false);
    // App continues running
  });
});

describe('createFrontendErrorPayload', () => {
  it('creates payload from Error object', () => {
    const error = new Error('Test error message');
    error.stack = 'Error: Test error message\n    at TestComponent';

    const payload = createFrontendErrorPayload(error, {
      component: 'TestComponent',
    });

    expect(payload.level).toBe('ERROR');
    expect(payload.message).toBe('Test error message');
    expect(payload.component).toBe('TestComponent');
    expect(payload.extra?.stack).toBe(error.stack);
    expect(payload.extra?.source).toBe('error_boundary');
    expect(payload.url).toBeDefined();
    expect(payload.user_agent).toBeDefined();
  });

  it('includes component stack when provided', () => {
    const error = new Error('Render error');
    const componentStack = '\n    in Dashboard\n    in App';

    const payload = createFrontendErrorPayload(error, {
      component: 'Dashboard',
      componentStack,
    });

    expect(payload.extra?.componentStack).toBe(componentStack);
  });

  it('extracts component name from errorInfo when not explicitly provided', () => {
    const error = new Error('Component error');
    const componentStack = '\n    at ErrorBoundary\n    in SomeComponent\n    in App';

    const payload = createFrontendErrorPayload(error, {
      componentStack,
    });

    // Should extract component name from stack or use default
    expect(payload.component).toBeDefined();
  });

  it('uses custom source when provided', () => {
    const error = new Error('Unhandled rejection');

    const payload = createFrontendErrorPayload(error, {
      component: 'GlobalHandler',
      source: 'unhandled_rejection',
    });

    expect(payload.extra?.source).toBe('unhandled_rejection');
  });

  it('includes timestamp in ISO format', () => {
    const error = new Error('Test error');

    const payload = createFrontendErrorPayload(error, {
      component: 'Test',
    });

    expect(payload.extra?.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/);
  });

  it('includes additional context when provided', () => {
    const error = new Error('Test error');

    const payload = createFrontendErrorPayload(error, {
      component: 'Test',
      context: {
        userId: '123',
        action: 'click',
      },
    });

    expect(payload.extra?.userId).toBe('123');
    expect(payload.extra?.action).toBe('click');
  });

  it('handles Error without stack trace', () => {
    const error = new Error('No stack error');
    delete (error as Partial<Error>).stack;

    const payload = createFrontendErrorPayload(error, {
      component: 'Test',
    });

    expect(payload.message).toBe('No stack error');
    // stack should be undefined or empty string
    expect(payload.extra?.stack).toBeFalsy();
  });
});

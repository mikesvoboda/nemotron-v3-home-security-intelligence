/**
 * Tests for AbortController-based timeout handling in API functions
 * TDD: These tests are written first to define expected behavior
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  anySignal,
  fetchWithTimeout,
  DEFAULT_TIMEOUT_MS,
  TimeoutError,
  isTimeoutError,
} from './api';

describe('anySignal', () => {
  it('returns a signal that aborts when any input signal aborts', () => {
    const controller1 = new AbortController();
    const controller2 = new AbortController();

    const combined = anySignal([controller1.signal, controller2.signal]);

    expect(combined.aborted).toBe(false);

    controller1.abort();

    expect(combined.aborted).toBe(true);
  });

  it('returns already-aborted signal if any input is already aborted', () => {
    const controller1 = new AbortController();
    const controller2 = new AbortController();

    controller1.abort();

    const combined = anySignal([controller1.signal, controller2.signal]);

    expect(combined.aborted).toBe(true);
  });

  it('propagates abort reason from the signal that triggered abort', () => {
    const controller1 = new AbortController();
    const controller2 = new AbortController();

    const combined = anySignal([controller1.signal, controller2.signal]);

    const reason = new Error('custom abort reason');
    controller2.abort(reason);

    expect(combined.aborted).toBe(true);
    expect(combined.reason).toBe(reason);
  });

  it('handles empty array of signals', () => {
    const combined = anySignal([]);

    // Empty array should return a non-aborted signal
    expect(combined.aborted).toBe(false);
  });

  it('handles single signal', () => {
    const controller = new AbortController();

    const combined = anySignal([controller.signal]);

    expect(combined.aborted).toBe(false);

    controller.abort();

    expect(combined.aborted).toBe(true);
  });

  it('only triggers once even if multiple signals abort', () => {
    const controller1 = new AbortController();
    const controller2 = new AbortController();
    const controller3 = new AbortController();

    const combined = anySignal([controller1.signal, controller2.signal, controller3.signal]);
    let abortCount = 0;

    combined.addEventListener('abort', () => {
      abortCount++;
    });

    controller1.abort();
    controller2.abort();
    controller3.abort();

    // Only the first abort should trigger the combined signal
    expect(abortCount).toBe(1);
  });
});

describe('TimeoutError', () => {
  it('creates error with correct name and message', () => {
    const error = new TimeoutError(5000);

    expect(error.name).toBe('TimeoutError');
    expect(error.message).toBe('Request timed out after 5000ms');
    expect(error.timeout).toBe(5000);
  });

  it('is instanceof Error', () => {
    const error = new TimeoutError(5000);

    expect(error).toBeInstanceOf(Error);
  });
});

describe('isTimeoutError', () => {
  it('returns true for TimeoutError', () => {
    const error = new TimeoutError(5000);
    expect(isTimeoutError(error)).toBe(true);
  });

  it('returns true for Error with TimeoutError name', () => {
    const error = new Error('timeout');
    error.name = 'TimeoutError';
    expect(isTimeoutError(error)).toBe(true);
  });

  it('returns false for regular Error', () => {
    const error = new Error('Network error');
    expect(isTimeoutError(error)).toBe(false);
  });

  it('returns false for AbortError', () => {
    const error = new DOMException('aborted', 'AbortError');
    expect(isTimeoutError(error)).toBe(false);
  });

  it('returns false for null', () => {
    expect(isTimeoutError(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isTimeoutError(undefined)).toBe(false);
  });
});

describe('DEFAULT_TIMEOUT_MS', () => {
  it('is defined and is a reasonable value', () => {
    expect(DEFAULT_TIMEOUT_MS).toBeDefined();
    expect(typeof DEFAULT_TIMEOUT_MS).toBe('number');
    expect(DEFAULT_TIMEOUT_MS).toBeGreaterThan(0);
    expect(DEFAULT_TIMEOUT_MS).toBeLessThanOrEqual(60000); // At most 60 seconds
  });
});

describe('fetchWithTimeout', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('completes successfully when request finishes before timeout', async () => {
    const mockResponse = new Response(JSON.stringify({ data: 'test' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });

    const fetchMock = vi.fn().mockResolvedValue(mockResponse);
    vi.stubGlobal('fetch', fetchMock);

    const promise = fetchWithTimeout('https://api.example.com/data', {
      timeout: 5000,
    });

    // Fast-forward time slightly (but not to timeout)
    await vi.advanceTimersByTimeAsync(100);

    const response = await promise;

    expect(response).toBe(mockResponse);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.example.com/data',
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      })
    );
  });

  it('throws TimeoutError when request exceeds timeout', async () => {
    // Create a fetch that never resolves
    const fetchMock = vi.fn().mockImplementation(
      (_url: string, options: RequestInit) =>
        new Promise((_resolve, reject) => {
          // Listen for abort and reject accordingly
          if (options.signal) {
            options.signal.addEventListener('abort', () => {
              reject(new DOMException('The operation was aborted', 'AbortError'));
            });
          }
        })
    );
    vi.stubGlobal('fetch', fetchMock);

    const promise = fetchWithTimeout('https://api.example.com/slow', {
      timeout: 1000,
    });

    // Attach error handler before advancing timers to prevent unhandled rejection
    const errorPromise = promise.catch((error) => error);

    // Fast-forward past the timeout
    await vi.advanceTimersByTimeAsync(1001);

    // Now await the result
    const caughtError = await errorPromise;

    expect(caughtError).toBeInstanceOf(TimeoutError);
    expect(caughtError).toMatchObject({
      name: 'TimeoutError',
      timeout: 1000,
    });
  });

  it('uses DEFAULT_TIMEOUT_MS when no timeout specified', async () => {
    const fetchMock = vi.fn().mockImplementation(
      (_url: string, options: RequestInit) =>
        new Promise((_resolve, reject) => {
          if (options.signal) {
            options.signal.addEventListener('abort', () => {
              reject(new DOMException('The operation was aborted', 'AbortError'));
            });
          }
        })
    );
    vi.stubGlobal('fetch', fetchMock);

    const promise = fetchWithTimeout('https://api.example.com/slow', {});

    // Attach error handler before advancing timers to prevent unhandled rejection
    const errorPromise = promise.catch((error) => error);

    // Fast-forward past the default timeout
    await vi.advanceTimersByTimeAsync(DEFAULT_TIMEOUT_MS + 1);

    // Now await the result
    const caughtError = await errorPromise;

    expect(caughtError).toBeInstanceOf(TimeoutError);
  });

  it('respects external signal for cancellation', async () => {
    const externalController = new AbortController();

    const fetchMock = vi.fn().mockImplementation(
      (_url: string, options: RequestInit) =>
        new Promise((_resolve, reject) => {
          if (options.signal) {
            options.signal.addEventListener('abort', () => {
              reject(new DOMException('The operation was aborted', 'AbortError'));
            });
          }
        })
    );
    vi.stubGlobal('fetch', fetchMock);

    const promise = fetchWithTimeout('https://api.example.com/data', {
      timeout: 30000,
      signal: externalController.signal,
    });

    // Abort externally before timeout
    externalController.abort();

    // Handle the promise rejection properly
    let caughtError: unknown;
    try {
      await promise;
    } catch (error) {
      caughtError = error;
    }

    // External abort should throw AbortError, not TimeoutError
    expect(caughtError).toBeInstanceOf(DOMException);
    expect(caughtError).toMatchObject({
      name: 'AbortError',
    });
  });

  it('clears timeout when request completes successfully', async () => {
    const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout');

    const mockResponse = new Response('ok', { status: 200 });
    const fetchMock = vi.fn().mockResolvedValue(mockResponse);
    vi.stubGlobal('fetch', fetchMock);

    await fetchWithTimeout('https://api.example.com/data', { timeout: 5000 });

    expect(clearTimeoutSpy).toHaveBeenCalled();
  });

  it('clears timeout when request fails with non-timeout error', async () => {
    const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout');

    const fetchMock = vi.fn().mockRejectedValue(new Error('Network error'));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      fetchWithTimeout('https://api.example.com/data', { timeout: 5000 })
    ).rejects.toThrow('Network error');

    expect(clearTimeoutSpy).toHaveBeenCalled();
  });

  it('passes through other fetch options', async () => {
    const mockResponse = new Response('created', { status: 201 });
    const fetchMock = vi.fn().mockResolvedValue(mockResponse);
    vi.stubGlobal('fetch', fetchMock);

    await fetchWithTimeout('https://api.example.com/data', {
      timeout: 5000,
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ test: true }),
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.example.com/data',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ test: true }),
        signal: expect.any(AbortSignal),
      })
    );
  });

  it('combines external signal and timeout signal correctly', async () => {
    const externalController = new AbortController();

    // Fetch that captures the signal
    let capturedSignal: AbortSignal | undefined;
    const fetchMock = vi.fn().mockImplementation((_url: string, options: RequestInit) => {
      capturedSignal = options.signal ?? undefined;
      return new Promise((_resolve, reject) => {
        if (options.signal) {
          options.signal.addEventListener('abort', () => {
            reject(new DOMException('The operation was aborted', 'AbortError'));
          });
        }
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const promise = fetchWithTimeout('https://api.example.com/data', {
      timeout: 5000,
      signal: externalController.signal,
    });

    // Neither signal has fired yet
    expect(capturedSignal).toBeDefined();
    expect(capturedSignal!.aborted).toBe(false);

    // Attach error handler before advancing timers to prevent unhandled rejection
    const errorPromise = promise.catch((error) => error);

    // Timeout should abort the combined signal
    await vi.advanceTimersByTimeAsync(5001);

    // Now await the result
    const caughtError = await errorPromise;

    expect(caughtError).toBeDefined();
  });

  it('handles already-aborted external signal', async () => {
    const externalController = new AbortController();
    externalController.abort();

    const fetchMock = vi.fn().mockImplementation(
      (_url: string, options: RequestInit) =>
        new Promise((_resolve, reject) => {
          if (options.signal?.aborted) {
            reject(new DOMException('The operation was aborted', 'AbortError'));
            return;
          }
          if (options.signal) {
            options.signal.addEventListener('abort', () => {
              reject(new DOMException('The operation was aborted', 'AbortError'));
            });
          }
        })
    );
    vi.stubGlobal('fetch', fetchMock);

    const promise = fetchWithTimeout('https://api.example.com/data', {
      timeout: 5000,
      signal: externalController.signal,
    });

    // Handle the promise rejection properly
    let caughtError: unknown;
    try {
      await promise;
    } catch (error) {
      caughtError = error;
    }

    expect(caughtError).toBeInstanceOf(DOMException);
  });

  it('timeout of 0 effectively disables timeout (uses default)', async () => {
    // A timeout of 0 should not immediately timeout
    // It should fall back to default or be treated as "no timeout"
    const mockResponse = new Response('ok', { status: 200 });
    const fetchMock = vi.fn().mockResolvedValue(mockResponse);
    vi.stubGlobal('fetch', fetchMock);

    // Request should complete normally
    const response = await fetchWithTimeout('https://api.example.com/data', {
      timeout: 0,
    });

    expect(response).toBe(mockResponse);
  });
});

describe('fetchWithTimeout integration patterns', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('demonstrates React cleanup pattern with timeout', async () => {
    const externalController = new AbortController();

    const fetchMock = vi.fn().mockImplementation(
      (_url: string, options: RequestInit) =>
        new Promise((resolve, reject) => {
          const timeoutId = setTimeout(() => {
            resolve(new Response('ok', { status: 200 }));
          }, 100);

          if (options.signal) {
            options.signal.addEventListener('abort', () => {
              clearTimeout(timeoutId);
              reject(new DOMException('The operation was aborted', 'AbortError'));
            });
          }
        })
    );
    vi.stubGlobal('fetch', fetchMock);

    // Start a request
    const promise = fetchWithTimeout('https://api.example.com/data', {
      timeout: 5000,
      signal: externalController.signal,
    });

    // Simulate React useEffect cleanup before request completes
    externalController.abort();

    // Handle the promise rejection properly
    let caughtError: unknown;
    try {
      await promise;
    } catch (error) {
      caughtError = error;
    }

    expect(caughtError).toBeInstanceOf(DOMException);
  });

  it('demonstrates multiple concurrent requests with different timeouts', async () => {
    const results: string[] = [];

    const fetchMock = vi.fn().mockImplementation(
      (url: string, options: RequestInit) =>
        new Promise((resolve, reject) => {
          // Simulate different response times based on URL
          const delay = url.includes('fast') ? 100 : 2000;
          const timeoutId = setTimeout(() => {
            resolve(new Response(url, { status: 200 }));
          }, delay);

          if (options.signal) {
            options.signal.addEventListener('abort', () => {
              clearTimeout(timeoutId);
              reject(new DOMException('aborted', 'AbortError'));
            });
          }
        })
    );
    vi.stubGlobal('fetch', fetchMock);

    // Start two requests with different timeouts
    const fastPromise = fetchWithTimeout('https://api.example.com/fast', { timeout: 500 })
      .then(() => results.push('fast-success'))
      .catch(() => results.push('fast-timeout'));

    const slowPromise = fetchWithTimeout('https://api.example.com/slow', { timeout: 500 })
      .then(() => results.push('slow-success'))
      .catch(() => results.push('slow-timeout'));

    // Advance time to complete fast request but timeout slow one
    await vi.advanceTimersByTimeAsync(600);

    await Promise.allSettled([fastPromise, slowPromise]);

    expect(results).toContain('fast-success');
    expect(results).toContain('slow-timeout');
  });
});

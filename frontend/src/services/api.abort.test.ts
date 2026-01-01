/**
 * Tests for AbortController support in API functions
 * Verifies that requests can be cancelled and AbortErrors are handled gracefully
 */
import { describe, it, expect } from 'vitest';

import { isAbortError, ApiError, FetchOptions } from './api';

describe('isAbortError', () => {
  it('returns true for AbortError', () => {
    const error = new DOMException('The operation was aborted', 'AbortError');
    expect(isAbortError(error)).toBe(true);
  });

  it('returns true for Error with AbortError name', () => {
    const error = new Error('aborted');
    error.name = 'AbortError';
    expect(isAbortError(error)).toBe(true);
  });

  it('returns false for regular Error', () => {
    const error = new Error('Network error');
    expect(isAbortError(error)).toBe(false);
  });

  it('returns false for ApiError', () => {
    const error = new ApiError(404, 'Not found');
    expect(isAbortError(error)).toBe(false);
  });

  it('returns false for null', () => {
    expect(isAbortError(null)).toBe(false);
  });

  it('returns false for undefined', () => {
    expect(isAbortError(undefined)).toBe(false);
  });

  it('returns false for string', () => {
    expect(isAbortError('error')).toBe(false);
  });

  it('returns false for object without name property', () => {
    expect(isAbortError({ message: 'error' })).toBe(false);
  });
});

describe('FetchOptions interface', () => {
  it('allows signal property', () => {
    const controller = new AbortController();
    const options: FetchOptions = {
      signal: controller.signal,
    };
    expect(options.signal).toBe(controller.signal);
  });

  it('allows method and body properties', () => {
    const options: FetchOptions = {
      method: 'POST',
      body: JSON.stringify({ test: true }),
    };
    expect(options.method).toBe('POST');
    expect(options.body).toBe('{"test":true}');
  });
});

describe('AbortController pattern usage', () => {
  it('demonstrates proper AbortController cleanup pattern', async () => {
    const results: string[] = [];
    const controller = new AbortController();

    // Simulate a fetch that respects AbortSignal
    const fetchWithSignal = (signal: AbortSignal): Promise<string> => {
      return new Promise((resolve, reject) => {
        // Check if already aborted
        if (signal.aborted) {
          reject(new DOMException('The operation was aborted', 'AbortError'));
          return;
        }

        const timeoutId = setTimeout(() => {
          if (!signal.aborted) {
            resolve('success');
          }
        }, 100);

        // Set up abort handler
        signal.addEventListener(
          'abort',
          () => {
            clearTimeout(timeoutId);
            reject(new DOMException('The operation was aborted', 'AbortError'));
          },
          { once: true }
        );
      });
    };

    // Start the fetch
    const promise = fetchWithSignal(controller.signal)
      .then((result) => results.push(result))
      .catch((err) => {
        if (!isAbortError(err)) {
          throw err;
        }
        results.push('aborted');
      });

    // Abort immediately
    controller.abort();

    await promise;

    expect(results).toEqual(['aborted']);
  });

  it('demonstrates rapid filter change scenario', async () => {
    const completedRequests: number[] = [];

    // Helper to create a cancellable async operation
    const createRequest = (id: number, signal: AbortSignal): Promise<void> => {
      return new Promise((resolve, reject) => {
        if (signal.aborted) {
          reject(new DOMException('aborted', 'AbortError'));
          return;
        }

        const timeoutId = setTimeout(() => {
          if (!signal.aborted) {
            completedRequests.push(id);
          }
          resolve();
        }, 10);

        signal.addEventListener(
          'abort',
          () => {
            clearTimeout(timeoutId);
            resolve(); // Resolve instead of reject to avoid unhandled promise
          },
          { once: true }
        );
      });
    };

    // Simulate 3 rapid filter changes - each one cancels the previous
    const controller1 = new AbortController();
    const controller2 = new AbortController();
    const controller3 = new AbortController();

    // Start all requests
    const p1 = createRequest(1, controller1.signal);
    const p2 = createRequest(2, controller2.signal);
    const p3 = createRequest(3, controller3.signal);

    // Cancel first two (simulating filter changes)
    controller1.abort();
    controller2.abort();

    // Wait for all to complete
    await Promise.all([p1, p2, p3]);

    // Only the last request should have completed
    expect(completedRequests).toEqual([3]);
  });

  it('demonstrates cleanup in useEffect pattern', () => {
    let cleanupCalled = false;
    const controller = new AbortController();

    // Simulate React useEffect cleanup
    const cleanup = () => {
      controller.abort();
      cleanupCalled = true;
    };

    // Trigger cleanup (simulating component unmount or dependency change)
    cleanup();

    expect(cleanupCalled).toBe(true);
    expect(controller.signal.aborted).toBe(true);
  });

  it('demonstrates error handling that silently ignores AbortError', () => {
    const errors: Error[] = [];
    const controller = new AbortController();

    // Pre-abort the controller
    controller.abort();

    try {
      // This would be our API call
      throw new DOMException('The operation was aborted', 'AbortError');
    } catch (err) {
      // Pattern used in components: only track non-abort errors
      if (!isAbortError(err)) {
        errors.push(err as Error);
      }
    }

    // AbortError should be silently ignored
    expect(errors).toHaveLength(0);
  });

  it('demonstrates error handling that captures real errors', () => {
    const errors: Error[] = [];

    try {
      // This would be a real API error
      throw new ApiError(500, 'Server error');
    } catch (err) {
      // Pattern used in components: only track non-abort errors
      if (!isAbortError(err)) {
        errors.push(err as Error);
      }
    }

    // Real errors should be captured
    expect(errors).toHaveLength(1);
    expect(errors[0]).toBeInstanceOf(ApiError);
  });
});

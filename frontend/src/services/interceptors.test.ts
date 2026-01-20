/**
 * Tests for API Client Interceptors
 * NEM-1564: Global error handling and request logging
 *
 * Following TDD - RED phase: write tests first, then implement
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import {
  createInterceptedFetch,
  type RequestInterceptor,
  type ResponseInterceptor,
  type InterceptorConfig,
  defaultRequestInterceptor,
  defaultResponseInterceptor,
  createRetryInterceptor,
  getLastRequestId,
  getLastCorrelationId,
  getRequestIdForUrl,
  setLastRequestId,
  setLastCorrelationId,
  setRequestIdForUrl,
  clearRequestIds,
} from './interceptors';

// Type for the mock fetch function
type MockFetch = ReturnType<typeof vi.fn<typeof fetch>>;

describe('interceptors', () => {
  let fetchMock: MockFetch;
  let consoleSpy: {
    log: ReturnType<typeof vi.spyOn>;
    warn: ReturnType<typeof vi.spyOn>;
    error: ReturnType<typeof vi.spyOn>;
  };

  beforeEach(() => {
    fetchMock = vi.fn<typeof fetch>();
    vi.stubGlobal('fetch', fetchMock);

    consoleSpy = {
      log: vi.spyOn(console, 'log').mockImplementation(() => {}),
      warn: vi.spyOn(console, 'warn').mockImplementation(() => {}),
      error: vi.spyOn(console, 'error').mockImplementation(() => {}),
    };
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  describe('createInterceptedFetch', () => {
    it('returns a function that wraps fetch', () => {
      const interceptedFetch = createInterceptedFetch({});
      expect(typeof interceptedFetch).toBe('function');
    });

    it('calls the original fetch with intercepted request', async () => {
      fetchMock.mockResolvedValue(new Response('OK', { status: 200 }));

      const interceptedFetch = createInterceptedFetch({});
      await interceptedFetch('/api/test');

      expect(fetchMock).toHaveBeenCalledWith('/api/test', expect.any(Object));
    });

    it('applies request interceptors before fetch', async () => {
      fetchMock.mockResolvedValue(new Response('OK', { status: 200 }));

      const requestInterceptor: RequestInterceptor = (url, options) => {
        return {
          url,
          options: {
            ...options,
            headers: {
              ...(options?.headers || {}),
              'X-Custom-Header': 'test-value',
            },
          },
        };
      };

      const interceptedFetch = createInterceptedFetch({
        requestInterceptors: [requestInterceptor],
      });

      await interceptedFetch('/api/test');

      expect(fetchMock).toHaveBeenCalledWith(
        '/api/test',
        expect.objectContaining({
          headers: expect.objectContaining({
            'X-Custom-Header': 'test-value',
          }),
        })
      );
    });

    it('applies response interceptors after fetch', async () => {
      const originalResponse = new Response('OK', { status: 200 });
      fetchMock.mockResolvedValue(originalResponse);

      let interceptedResponse: Response | null = null;
      const responseInterceptor: ResponseInterceptor = (response) => {
        interceptedResponse = response;
        return response;
      };

      const interceptedFetch = createInterceptedFetch({
        responseInterceptors: [responseInterceptor],
      });

      await interceptedFetch('/api/test');

      expect(interceptedResponse).toBe(originalResponse);
    });

    it('chains multiple request interceptors', async () => {
      fetchMock.mockResolvedValue(new Response('OK', { status: 200 }));

      const order: string[] = [];

      const interceptor1: RequestInterceptor = (url, options) => {
        order.push('first');
        return { url, options };
      };

      const interceptor2: RequestInterceptor = (url, options) => {
        order.push('second');
        return { url, options };
      };

      const interceptedFetch = createInterceptedFetch({
        requestInterceptors: [interceptor1, interceptor2],
      });

      await interceptedFetch('/api/test');

      expect(order).toEqual(['first', 'second']);
    });

    it('chains multiple response interceptors', async () => {
      fetchMock.mockResolvedValue(new Response('OK', { status: 200 }));

      const order: string[] = [];

      const interceptor1: ResponseInterceptor = (response) => {
        order.push('first');
        return response;
      };

      const interceptor2: ResponseInterceptor = (response) => {
        order.push('second');
        return response;
      };

      const interceptedFetch = createInterceptedFetch({
        responseInterceptors: [interceptor1, interceptor2],
      });

      await interceptedFetch('/api/test');

      expect(order).toEqual(['first', 'second']);
    });
  });

  describe('defaultRequestInterceptor', () => {
    it('logs outgoing requests', () => {
      const result = defaultRequestInterceptor('/api/test', { method: 'GET' });

      expect(consoleSpy.log).toHaveBeenCalled();
      expect(result.url).toBe('/api/test');
    });

    it('adds request start time to options', () => {
      const result = defaultRequestInterceptor('/api/test', { method: 'POST' });

      expect(result.options).toHaveProperty('_requestStartTime');
      expect(typeof result.options?._requestStartTime).toBe('number');
    });

    it('preserves existing options', () => {
      const result = defaultRequestInterceptor('/api/test', {
        method: 'PUT',
        body: JSON.stringify({ data: 'test' }),
      });

      expect(result.options?.method).toBe('PUT');
      expect(result.options?.body).toBe(JSON.stringify({ data: 'test' }));
    });
  });

  describe('defaultResponseInterceptor', () => {
    it('logs successful responses', () => {
      const response = new Response('OK', { status: 200 });
      const result = defaultResponseInterceptor(response, '/api/test', {
        _requestStartTime: Date.now() - 100,
      });

      expect(consoleSpy.log).toHaveBeenCalled();
      expect(result).toBe(response);
    });

    it('logs error responses', () => {
      const response = new Response('Not Found', { status: 404 });
      const result = defaultResponseInterceptor(response, '/api/test', {});

      expect(consoleSpy.warn).toHaveBeenCalled();
      expect(result).toBe(response);
    });

    it('logs server error responses as errors', () => {
      const response = new Response('Server Error', { status: 500 });
      const result = defaultResponseInterceptor(response, '/api/test', {});

      expect(consoleSpy.error).toHaveBeenCalled();
      expect(result).toBe(response);
    });

    it('calculates request duration when start time is provided', () => {
      const response = new Response('OK', { status: 200 });
      const startTime = Date.now() - 150;

      defaultResponseInterceptor(response, '/api/test', {
        _requestStartTime: startTime,
      });

      // Check that duration was logged
      const logCall = consoleSpy.log.mock.calls.find((call: unknown[]) =>
        String(call[0]).includes('API')
      );
      expect(logCall).toBeDefined();
    });
  });

  describe('createRetryInterceptor', () => {
    it('returns an interceptor function', () => {
      const interceptor = createRetryInterceptor({ maxRetries: 3 });
      expect(typeof interceptor).toBe('function');
    });

    it('does not retry successful responses', async () => {
      const interceptor = createRetryInterceptor({ maxRetries: 3 });
      const response = new Response('OK', { status: 200 });

      const result = await interceptor(response, '/api/test', {}, fetchMock);

      expect(result).toBe(response);
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it('does not retry 4xx client errors', async () => {
      const interceptor = createRetryInterceptor({ maxRetries: 3 });
      const response = new Response('Bad Request', { status: 400 });

      const result = await interceptor(response, '/api/test', {}, fetchMock);

      expect(result).toBe(response);
      expect(fetchMock).not.toHaveBeenCalled();
    });

    it('retries 5xx server errors', async () => {
      const interceptor = createRetryInterceptor({
        maxRetries: 2,
        retryDelay: 10,
      });

      const errorResponse = new Response('Server Error', { status: 500 });
      const successResponse = new Response('OK', { status: 200 });

      fetchMock.mockResolvedValueOnce(successResponse);

      const result = await interceptor(errorResponse, '/api/test', {}, fetchMock);

      expect(result).toBe(successResponse);
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it('respects maxRetries limit', async () => {
      const interceptor = createRetryInterceptor({
        maxRetries: 2,
        retryDelay: 10,
      });

      const errorResponse = new Response('Server Error', { status: 500 });

      fetchMock.mockResolvedValue(errorResponse);

      const result = await interceptor(errorResponse, '/api/test', {}, fetchMock);

      // Should have retried maxRetries times
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(result.status).toBe(500);
    });

    it('uses exponential backoff for retry delays', async () => {
      vi.useFakeTimers();

      const interceptor = createRetryInterceptor({
        maxRetries: 3,
        retryDelay: 100,
        useExponentialBackoff: true,
      });

      const errorResponse = new Response('Server Error', { status: 500 });
      fetchMock.mockResolvedValue(errorResponse);

      const resultPromise = interceptor(errorResponse, '/api/test', {}, fetchMock);

      // First retry: 100ms
      await vi.advanceTimersByTimeAsync(100);
      // Second retry: 200ms
      await vi.advanceTimersByTimeAsync(200);
      // Third retry: 400ms
      await vi.advanceTimersByTimeAsync(400);

      await resultPromise;

      vi.useRealTimers();

      expect(fetchMock).toHaveBeenCalledTimes(3);
    });
  });

  describe('InterceptorConfig type', () => {
    it('allows empty configuration', () => {
      const config: InterceptorConfig = {};
      expect(config).toBeDefined();
    });

    it('allows custom interceptors', () => {
      const config: InterceptorConfig = {
        requestInterceptors: [(url, options) => ({ url, options })],
        responseInterceptors: [(response) => response],
      };
      expect(config.requestInterceptors).toHaveLength(1);
      expect(config.responseInterceptors).toHaveLength(1);
    });
  });

  describe('Request ID Context Store', () => {
    beforeEach(() => {
      clearRequestIds();
    });

    it('stores and retrieves last request ID', () => {
      expect(getLastRequestId()).toBeNull();

      setLastRequestId('req-123');
      expect(getLastRequestId()).toBe('req-123');

      setLastRequestId('req-456');
      expect(getLastRequestId()).toBe('req-456');
    });

    it('stores and retrieves last correlation ID', () => {
      expect(getLastCorrelationId()).toBeNull();

      setLastCorrelationId('corr-abc');
      expect(getLastCorrelationId()).toBe('corr-abc');

      setLastCorrelationId('corr-def');
      expect(getLastCorrelationId()).toBe('corr-def');
    });

    it('stores and retrieves request ID for specific URL', () => {
      expect(getRequestIdForUrl('/api/test')).toBeNull();

      setRequestIdForUrl('/api/test', 'req-111');
      expect(getRequestIdForUrl('/api/test')).toBe('req-111');

      setRequestIdForUrl('/api/other', 'req-222');
      expect(getRequestIdForUrl('/api/test')).toBe('req-111');
      expect(getRequestIdForUrl('/api/other')).toBe('req-222');
    });

    it('clears all stored request IDs', () => {
      setLastRequestId('req-123');
      setLastCorrelationId('corr-abc');
      setRequestIdForUrl('/api/test', 'req-456');

      clearRequestIds();

      expect(getLastRequestId()).toBeNull();
      expect(getLastCorrelationId()).toBeNull();
      expect(getRequestIdForUrl('/api/test')).toBeNull();
    });
  });

  describe('defaultResponseInterceptor request ID capture', () => {
    beforeEach(() => {
      clearRequestIds();
    });

    it('captures X-Request-ID header from response', () => {
      const headers = new Headers();
      headers.set('X-Request-ID', 'backend-req-789');

      const response = new Response('OK', { status: 200, headers });
      defaultResponseInterceptor(response, '/api/test', {});

      expect(getLastRequestId()).toBe('backend-req-789');
      expect(getRequestIdForUrl('/api/test')).toBe('backend-req-789');
    });

    it('captures X-Correlation-ID header from response', () => {
      const headers = new Headers();
      headers.set('X-Correlation-ID', 'trace-xyz');

      const response = new Response('OK', { status: 200, headers });
      defaultResponseInterceptor(response, '/api/test', {});

      expect(getLastCorrelationId()).toBe('trace-xyz');
    });

    it('captures both request ID and correlation ID', () => {
      const headers = new Headers();
      headers.set('X-Request-ID', 'req-111');
      headers.set('X-Correlation-ID', 'corr-222');

      const response = new Response('OK', { status: 200, headers });
      defaultResponseInterceptor(response, '/api/data', {});

      expect(getLastRequestId()).toBe('req-111');
      expect(getLastCorrelationId()).toBe('corr-222');
      expect(getRequestIdForUrl('/api/data')).toBe('req-111');
    });

    it('does not overwrite when headers are missing', () => {
      setLastRequestId('existing-req');
      setLastCorrelationId('existing-corr');

      const response = new Response('OK', { status: 200 });
      defaultResponseInterceptor(response, '/api/test', {});

      // Should not overwrite existing values when headers are not present
      expect(getLastRequestId()).toBe('existing-req');
      expect(getLastCorrelationId()).toBe('existing-corr');
    });

    it('includes request ID in error logs for 4xx responses', () => {
      const headers = new Headers();
      headers.set('X-Request-ID', 'error-req-404');

      const response = new Response('Not Found', { status: 404, headers });
      defaultResponseInterceptor(response, '/api/missing', { method: 'GET' });

      expect(consoleSpy.warn).toHaveBeenCalledWith(
        expect.stringContaining('[Request-ID: error-req-404]')
      );
    });

    it('includes request ID in error logs for 5xx responses', () => {
      const headers = new Headers();
      headers.set('X-Request-ID', 'error-req-500');

      const response = new Response('Server Error', { status: 500, headers });
      defaultResponseInterceptor(response, '/api/broken', { method: 'POST' });

      expect(consoleSpy.error).toHaveBeenCalledWith(
        expect.stringContaining('[Request-ID: error-req-500]')
      );
    });

    it('does not include request ID in success logs', () => {
      const headers = new Headers();
      headers.set('X-Request-ID', 'success-req-200');

      const response = new Response('OK', { status: 200, headers });
      defaultResponseInterceptor(response, '/api/success', { method: 'GET' });

      // Success logs should not include request ID for cleaner output
      expect(consoleSpy.log).toHaveBeenCalled();
      const logCall = consoleSpy.log.mock.calls.find((call: unknown[]) =>
        String(call[0]).includes('/api/success')
      );
      expect(logCall?.[0]).not.toContain('[Request-ID:');
    });
  });
});
